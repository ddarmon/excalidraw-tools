const cors = require("cors");
const express = require("express");
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const app = express();

const PORT = Number(process.env.PORT || 8081);
const KROKI_URL = (process.env.KROKI_URL || "http://kroki:8000").replace(/\/+$/, "");
const BODY_LIMIT = process.env.BODY_LIMIT || "50mb";
const REQUEST_TIMEOUT_MS = Number(process.env.REQUEST_TIMEOUT_MS || 30000);

const DEFAULT_DPI = Number(process.env.DEFAULT_DPI || 96);
const DEFAULT_ZOOM = Number(process.env.DEFAULT_ZOOM || 1);
const DEFAULT_WIDTH = Number(process.env.DEFAULT_WIDTH || 1600);
const DEFAULT_BACKGROUND = process.env.DEFAULT_BACKGROUND || "#ffffff";
const CHROMIUM_PATH = process.env.CHROMIUM_PATH || "/usr/bin/chromium";
const FONTS_DIR = process.env.FONTS_DIR || "/app/fonts";

// ---------------------------------------------------------------------------
// Font mapping: replace Excalidraw's built-in font names in the SVG output
// with custom fonts, and inject @font-face rules so Chromium can resolve them.
// ---------------------------------------------------------------------------

function parseFontMapString(str) {
  const map = {};
  if (!str) return map;
  for (const pair of str.split(",")) {
    const idx = pair.indexOf(":");
    if (idx > 0) {
      const from = pair.substring(0, idx).trim();
      const to = pair.substring(idx + 1).trim();
      if (from && to) map[from] = to;
    }
  }
  return map;
}

const DEFAULT_FONT_MAP = parseFontMapString(process.env.DEFAULT_FONT_MAP || "");

const FORMAT_BY_EXT = {
  ".woff2": { mime: "font/woff2",    format: "woff2" },
  ".woff":  { mime: "font/woff",     format: "woff" },
  ".otf":   { mime: "font/opentype", format: "opentype" },
  ".ttf":   { mime: "font/truetype", format: "truetype" },
};

function loadCustomFonts(dir) {
  const fonts = {};
  let config;
  try {
    config = JSON.parse(fs.readFileSync(path.join(dir, "fonts.json"), "utf8"));
  } catch {
    return fonts;
  }
  for (const [family, variants] of Object.entries(config)) {
    fonts[family] = [];
    for (const v of [].concat(variants)) {
      const filePath = path.join(dir, v.file);
      const ext = path.extname(v.file).toLowerCase();
      const info = FORMAT_BY_EXT[ext];
      if (!info) {
        console.warn(`Skipping unsupported font format: ${v.file}`);
        continue;
      }
      try {
        const data = fs.readFileSync(filePath);
        fonts[family].push({
          base64: data.toString("base64"),
          mime: info.mime,
          format: info.format,
          weight: v.weight || "normal",
          style: v.style || "normal",
        });
      } catch (err) {
        console.warn(`Failed to load font file ${filePath}: ${err.message}`);
      }
    }
  }
  return fonts;
}

const customFonts = loadCustomFonts(FONTS_DIR);

function rewriteSvgFonts(svg, fontMap) {
  let result = svg;
  for (const [from, to] of Object.entries(fontMap)) {
    result = result.replaceAll(`font-family="${from},`, `font-family="${to},`);
    result = result.replaceAll(`font-family="${from}"`, `font-family="${to}"`);
  }
  return result;
}

function buildFontFaceRules(fontMap) {
  const rules = [];
  const needed = new Set(Object.values(fontMap));
  for (const family of needed) {
    const variants = customFonts[family];
    if (!variants) continue;
    for (const v of variants) {
      rules.push(
        `@font-face { font-family: "${family}"; ` +
        `src: url(data:${v.mime};base64,${v.base64}) format("${v.format}"); ` +
        `font-weight: ${v.weight}; font-style: ${v.style}; }`
      );
    }
  }
  return rules.join("\n    ");
}

function mergeFontMap(query) {
  const perCall = parseFontMapString(query.fontMap || "");
  return { ...DEFAULT_FONT_MAP, ...perCall };
}

const MIN_SCENE = JSON.stringify({
  type: "excalidraw",
  version: 2,
  source: "https://excalidraw.com",
  elements: [],
  appState: { viewBackgroundColor: "#ffffff" },
  files: {}
});

app.use(cors());
app.use(express.raw({ type: () => true, limit: BODY_LIMIT }));

let browserPromise;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function parsePositiveInt(value, fallback, fieldName) {
  if (value === undefined) {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new HttpError(400, `Invalid ${fieldName}: must be a positive integer`);
  }
  return parsed;
}

function parsePositiveFloat(value, fallback, fieldName) {
  if (value === undefined) {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new HttpError(400, `Invalid ${fieldName}: must be a positive number`);
  }
  return parsed;
}

function parseBoolean(value, fallback) {
  if (value === undefined) {
    return fallback;
  }
  const normalized = String(value).toLowerCase();
  if (["1", "true", "yes", "y"].includes(normalized)) {
    return true;
  }
  if (["0", "false", "no", "n"].includes(normalized)) {
    return false;
  }
  throw new HttpError(400, "Invalid transparent flag: must be true/false");
}

function parseBackground(value, fallback) {
  const candidate = value || fallback;
  if (!candidate) {
    return undefined;
  }
  // Accept hex and named colors commonly used in CSS.
  if (!/^#([0-9a-fA-F]{3,8})$/.test(candidate) && !/^[a-zA-Z][a-zA-Z0-9-]{0,31}$/.test(candidate)) {
    throw new HttpError(400, "Invalid background color format");
  }
  return candidate;
}

function readSceneText(req) {
  if (!req.body || req.body.length === 0) {
    throw new HttpError(400, "Empty request body");
  }
  const bodyText = Buffer.isBuffer(req.body) ? req.body.toString("utf8") : String(req.body);
  if (!bodyText.trim()) {
    throw new HttpError(400, "Empty request body");
  }
  return bodyText;
}

async function requestSvgFromKroki(sceneText) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${KROKI_URL}/excalidraw/svg`, {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: sceneText,
      signal: controller.signal
    });
    const responseBuffer = Buffer.from(await response.arrayBuffer());
    if (!response.ok) {
      throw new HttpError(502, `Kroki error ${response.status}: ${responseBuffer.toString("utf8")}`);
    }
    return responseBuffer.toString("utf8");
  } catch (error) {
    if (error.name === "AbortError") {
      throw new HttpError(504, "Timed out while waiting for Kroki");
    }
    if (error instanceof HttpError) {
      throw error;
    }
    throw new HttpError(502, `Failed to reach Kroki: ${error.message}`);
  } finally {
    clearTimeout(timeout);
  }
}

function parseSvgDimensions(svg) {
  const svgTagMatch = svg.match(/<svg\b[^>]*>/i);
  if (!svgTagMatch) {
    throw new HttpError(500, "SVG output missing <svg> root");
  }
  const svgTag = svgTagMatch[0];

  const widthMatch = svgTag.match(/\bwidth\s*=\s*"([0-9.]+)(?:px)?"/i);
  const heightMatch = svgTag.match(/\bheight\s*=\s*"([0-9.]+)(?:px)?"/i);

  if (widthMatch && heightMatch) {
    return {
      width: Number(widthMatch[1]),
      height: Number(heightMatch[1])
    };
  }

  const viewBoxMatch = svgTag.match(/\bviewBox\s*=\s*"(-?[0-9.]+)\s+(-?[0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s*"/i);
  if (viewBoxMatch) {
    return {
      width: Number(viewBoxMatch[3]),
      height: Number(viewBoxMatch[4])
    };
  }

  throw new HttpError(500, "Could not determine SVG dimensions");
}

function computeOutputSize(base, options) {
  if (!Number.isFinite(base.width) || !Number.isFinite(base.height) || base.width <= 0 || base.height <= 0) {
    throw new HttpError(500, "Invalid SVG dimensions");
  }

  if (options.width) {
    return {
      width: options.width,
      height: Math.max(1, Math.round((base.height * options.width) / base.width))
    };
  }

  if (options.height) {
    return {
      width: Math.max(1, Math.round((base.width * options.height) / base.height)),
      height: options.height
    };
  }

  const scale = options.zoom * (options.dpi / 96);
  return {
    width: Math.max(1, Math.round(base.width * scale)),
    height: Math.max(1, Math.round(base.height * scale))
  };
}

function buildRenderHtml(svg, size, options, fontFaceRules) {
  const backgroundStyle = options.transparent ? "transparent" : options.background;
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    ${fontFaceRules || ""}
    html, body {
      margin: 0;
      padding: 0;
      width: ${size.width}px;
      height: ${size.height}px;
      overflow: hidden;
      background: ${backgroundStyle};
    }
    svg {
      display: block;
      width: ${size.width}px;
      height: ${size.height}px;
    }
  </style>
</head>
<body>${svg}</body>
</html>`;
}

async function getBrowser() {
  if (!browserPromise) {
    browserPromise = puppeteer.launch({
      executablePath: CHROMIUM_PATH,
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--font-render-hinting=medium"
      ]
    });
  }
  return browserPromise;
}

async function renderPng(svg, options, fontFaceRules) {
  const baseSize = parseSvgDimensions(svg);
  const size = computeOutputSize(baseSize, options);
  const html = buildRenderHtml(svg, size, options, fontFaceRules);

  let page;
  try {
    const browser = await getBrowser();
    page = await browser.newPage();
    await page.setViewport({
      width: size.width,
      height: size.height,
      deviceScaleFactor: 1
    });
    await page.setContent(html, {
      waitUntil: "load",
      timeout: REQUEST_TIMEOUT_MS
    });
    return await page.screenshot({
      type: "png",
      omitBackground: options.transparent
    });
  } catch (error) {
    throw new HttpError(500, `Chromium rasterization failed: ${error.message}`);
  } finally {
    if (page) {
      await page.close().catch(() => {});
    }
  }
}

function parsePngOptions(query) {
  const hasDpi = query.dpi !== undefined;
  const hasZoom = query.zoom !== undefined;
  const dpi = parsePositiveInt(query.dpi, DEFAULT_DPI, "dpi");
  const zoom = parsePositiveFloat(query.zoom, DEFAULT_ZOOM, "zoom");
  let width = query.width !== undefined ? parsePositiveInt(query.width, undefined, "width") : undefined;
  const height = query.height !== undefined ? parsePositiveInt(query.height, undefined, "height") : undefined;
  const transparent = parseBoolean(query.transparent, false);
  const background = parseBackground(query.background, DEFAULT_BACKGROUND);

  // Default to a display-sized output when no explicit sizing controls are provided.
  if (!width && !height && !hasDpi && !hasZoom) {
    width = DEFAULT_WIDTH;
  }

  return { dpi, zoom, width, height, transparent, background };
}

app.post("/render/svg", async (req, res, next) => {
  try {
    const sceneText = readSceneText(req);
    const fontMap = mergeFontMap(req.query);
    let svg = await requestSvgFromKroki(sceneText);
    svg = rewriteSvgFonts(svg, fontMap);
    res.set("Content-Type", "image/svg+xml; charset=utf-8");
    res.send(svg);
  } catch (error) {
    next(error);
  }
});

app.post("/render/png", async (req, res, next) => {
  try {
    const sceneText = readSceneText(req);
    const options = parsePngOptions(req.query);
    const fontMap = mergeFontMap(req.query);
    let svg = await requestSvgFromKroki(sceneText);
    svg = rewriteSvgFonts(svg, fontMap);
    const fontFaceRules = buildFontFaceRules(fontMap);
    const png = await renderPng(svg, options, fontFaceRules);
    res.set("Content-Type", "image/png");
    res.send(png);
  } catch (error) {
    next(error);
  }
});

app.get("/healthz", async (_req, res) => {
  const checks = {
    kroki: "unknown",
    rasterizer: "unknown"
  };

  try {
    const svg = await requestSvgFromKroki(MIN_SCENE);
    checks.kroki = "ok";

    const png = await renderPng(svg, {
      dpi: DEFAULT_DPI,
      zoom: DEFAULT_ZOOM,
      transparent: false,
      background: DEFAULT_BACKGROUND
    });
    checks.rasterizer = png.length > 0 ? "ok" : "failed";

    res.status(200).json({
      status: "ok",
      checks,
      krokiUrl: KROKI_URL
    });
  } catch (error) {
    res.status(503).json({
      status: "error",
      checks,
      message: error.message,
      krokiUrl: KROKI_URL
    });
  }
});

app.use((error, _req, res, _next) => {
  const status = error.status || 500;
  if (status >= 500) {
    console.error(error);
  }
  res.status(status).json({
    error: error.message || "Unexpected error"
  });
});

app.listen(PORT, () => {
  console.log(`Renderer listening on port ${PORT}`);
  console.log(`Using Kroki at ${KROKI_URL}`);
  console.log(`Using Chromium at ${CHROMIUM_PATH}`);
  console.log(`Fonts directory: ${FONTS_DIR}`);
  const customFamilies = Object.keys(customFonts);
  if (customFamilies.length) {
    console.log(`Custom fonts loaded: ${customFamilies.join(", ")}`);
  }
  const defaultMappings = Object.entries(DEFAULT_FONT_MAP);
  if (defaultMappings.length) {
    console.log(`Default font map: ${defaultMappings.map(([f, t]) => `${f} -> ${t}`).join(", ")}`);
  }
});
