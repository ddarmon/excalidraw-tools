---
name: excalidraw
description: Create, edit, validate, render, and iterate on Excalidraw diagrams (.excalidraw JSON). Use when users ask to draw or modify diagrams, inspect existing drawings, connect nodes, move/relabel/recolor/delete elements, or review what is in a diagram file.
---

# Excalidraw Interactive Diagramming

Use this skill as a deterministic workflow around the `excalidraw-tools` CLI.

## Core Workflow

**Never write raw `.excalidraw` JSON by hand or via custom generator scripts.** The `excalidraw-tools` package handles per-type defaults (roundness, seed generation, index ordering) that are easy to get wrong manually.

Follow this loop on every diagram task:

1. Create or edit diagrams using `excalidraw-tools build`, `excalidraw-tools edit`, or scripts that import from `excalidraw_tools` (see Create Diagrams below)
2. Validate with `excalidraw-tools validate`
3. Render preview with the Chromium renderer path when available (`/render/png`)
4. Show preview image and describe changes
5. Iterate on user feedback
6. When done, tell the user the paths to **both** the `.excalidraw` file and the `.png` file

Always render after changes. The preview is the shared whiteboard view.

### PNG Output Naming

Always save the rendered PNG with the same base name as the `.excalidraw` file. For example, if the diagram is `/tmp/foo.excalidraw`, render to `/tmp/foo.png` (not a generic name like `excalidraw_preview.png`).

### Preferred Rendering Path (Default)

Prefer this path whenever it is available:

1. Check renderer health:

```bash
curl -fsS http://localhost:3004/healthz >/dev/null
```

2. Render PNG with browser-accurate text shaping (use matching base name):

```bash
curl -fsS -X POST "http://localhost:3004/render/png" \
  -H "Content-Type: text/plain" \
  --data-binary "@/tmp/FILE.excalidraw" \
  -o /tmp/FILE.png
```

If a custom render font was chosen for the session, append `fontMap` to the URL:

```bash
curl -fsS -X POST "http://localhost:3004/render/png?fontMap=Helvetica:CMU+Serif" \
  -H "Content-Type: text/plain" \
  --data-binary "@/tmp/FILE.excalidraw" \
  -o /tmp/FILE.png
```

If available in the repo, `scripts/render_diagrams.sh` is the preferred batch/single-file wrapper:

```bash
scripts/render_diagrams.sh --input FILE.excalidraw
```

This path is the default. Use fallback only when this path is unavailable.

### Fallback Rendering Path (Only If Needed)

Use Matplotlib preview rendering only when the Chromium path is not available (use matching base name):

```bash
excalidraw-tools preview /tmp/FILE.excalidraw --output /tmp/FILE.png
```

The preview renderer is approximate and should not be preferred if `/render/png` works.

## Math Text Conventions

Use renderer-safe math text in all diagram labels and annotations:

- Standardize on Unicode math-like text in labels (for example: `xₙ`, `xₙ₊₁`, `c₁`, `x²`, `φ(α)`, `≤`, `≥`, `−`, `√π`).
- Do not use math delimiters such as `$...$`, `\(...\)`, or `\[...\]`.
- Avoid LaTeX-like `_` / `^` forms in final diagram text.
- Prefer ASCII-safe alternatives only if a specific glyph renders inconsistently (`<=`, `>=`, `-`, `'`).

When updating an existing diagram, normalize math labels to Unicode format before final render.

## Session Setup

At the start of a diagram session, ask two questions:

### 1. Spec file preference

"Do you want a sidecar `.spec.json` for this diagram?"

Offer three choices:
1. No spec file
2. Create/update spec on request
3. Keep spec synced after every round

If the user chooses option 3, keep using `--sync-spec` on each build/edit command for the rest of that session unless they change preference.

### 2. Diagram style

"What style? **Hand-drawn** (default) or **Clean**?"

| Preset     | Font          | Roughness | Description                    |
|------------|---------------|-----------|--------------------------------|
| Hand-drawn | Virgil (1)    | 1         | Sketchy, informal (Excalidraw default) |
| Clean      | Helvetica (2) | 0         | Crisp, presentation-ready      |

If the user picks **Clean**, use `fontFamily: 2` and `roughness: 0` as session defaults — in specs (via the `style` block), in `excalidraw-tools edit` flags (`--font-family 2 --crisp`), and in library scripts.

If the user specifies individual values (e.g., "Cascadia font, sketchy"), use those instead. Available built-in fonts: 1=Virgil, 2=Helvetica, 3=Cascadia.

### 3. Render font

"Do you want a **custom render font**? The renderer can substitute any built-in Excalidraw font with a custom font at render time."

Common choices (system fonts available in the renderer container):

| Render font       | Maps from     | fontMap value                  |
|--------------------|---------------|--------------------------------|
| CMU Serif          | Helvetica (2) | `Helvetica:CMU+Serif`          |
| CMU Sans Serif     | Helvetica (2) | `Helvetica:CMU+Sans+Serif`     |
| CMU Typewriter Text| Cascadia (3)  | `Cascadia:CMU+Typewriter+Text` |

If the user picks a custom render font, store the `fontMap` query string for the session and **append it to every render curl command**. The `.excalidraw` file still uses the built-in fontFamily integer (e.g., `fontFamily: 2`); the substitution happens at render time only.

If the user does not want a custom font, omit `fontMap` from render commands (the built-in font renders as-is).

## Tooling Layout

The `excalidraw-tools` CLI provides these subcommands:

- `excalidraw-tools build`: Build a new diagram from a compact JSON spec
- `excalidraw-tools edit`: Deterministic edits (`move`, `relabel`, `recolor`, `delete`, `add-box`, `connect`)
- `excalidraw-tools validate`: Schema and linkage validation
- `excalidraw-tools preview`: Approximate PNG preview renderer (matplotlib)
- `excalidraw-tools sync-spec`: Derive/update a `.spec.json` from an `.excalidraw` file
- `excalidraw-tools golden-check`: Regression check against golden fixture

The Python library is importable as `excalidraw_tools`:

```python
from excalidraw_tools import IdFactory, make_shape, new_document, save_diagram
```

## Create Diagrams

Always use the tools — never write raw `.excalidraw` JSON.

1. **Spec + build (default):** Write a spec JSON with `nodes` and `edges`, then generate with `excalidraw-tools build`. Iterate with `excalidraw-tools edit` subcommands.
2. **Library fallback:** If the spec format or edit commands cannot express what you need (e.g., dashed lines, standalone text, tick marks), write a small Python script that **imports from `excalidraw_tools`** (e.g., `from excalidraw_tools import IdFactory, make_shape, new_document, save_diagram`). This ensures correct per-type defaults.

**Warning — `make_shape` and element types:**
- Do **not** use `make_shape` with `etype="line"`. It produces elements missing the required `points` array, which crashes the Kroki renderer (error: `Cannot read properties of undefined (reading 'length')`).
- For grid lines, rules, or separators, use thin rectangles instead (e.g., `width=1` for vertical lines, `height=1` for horizontal lines).

### Step 1: Spec + Build

1. Write a spec JSON with `nodes` and `edges`.
2. Generate diagram:

```bash
excalidraw-tools build --spec diagram.spec.json --output system-architecture.excalidraw
```

If continuous spec sync is enabled:

```bash
excalidraw-tools build --spec diagram.spec.json --output system-architecture.excalidraw --sync-spec
```

3. Validate and render (Chromium path first, Matplotlib fallback only if needed). Always use a matching base name for the PNG. If a session render font is active, append `?fontMap=...` to the curl URL:

```bash
excalidraw-tools validate /tmp/system-architecture.excalidraw
if curl -fsS http://localhost:3004/healthz >/dev/null; then
  curl -fsS -X POST "http://localhost:3004/render/png" \
    -H "Content-Type: text/plain" \
    --data-binary "@/tmp/system-architecture.excalidraw" \
    -o /tmp/system-architecture.png
else
  excalidraw-tools preview /tmp/system-architecture.excalidraw --output /tmp/system-architecture.png
fi
```

### Spec Format (Minimal)

```json
{
  "seed": 42,
  "updated": 1700000000000,
  "style": {
    "fontFamily": 2,
    "roughness": 0
  },
  "nodes": [
    {
      "id": "api",
      "type": "rectangle",
      "label": "API",
      "x": 120,
      "y": 220,
      "width": 200,
      "height": 80,
      "stroke": "#7048e8",
      "background": "#d0bfff"
    }
  ],
  "edges": []
}
```

The `style` block is optional. When omitted, defaults are `fontFamily: 1` (Virgil) and `roughness: 1` (sketchy). Per-node `fontFamily` or `roughness` overrides the style block.

## Edit Diagrams

Use `excalidraw-tools edit` subcommands.

### Move a shape (and reroute connected arrows)

```bash
excalidraw-tools edit move --input diagram.excalidraw --label "API" --dx 220 --dy 0
```

### Relabel text

```bash
excalidraw-tools edit relabel --input diagram.excalidraw --label "API" --text "Gateway API"
```

### Recolor a shape

```bash
excalidraw-tools edit recolor --input diagram.excalidraw --label "Gateway API" --stroke "#1971c2" --background "#a5d8ff"
```

### Delete a labeled shape/text

```bash
excalidraw-tools edit delete --input diagram.excalidraw --label "Legacy Service"
```

### Add a new box

```bash
excalidraw-tools edit add-box --input diagram.excalidraw --label "Cache" --x 520 --y 220 --width 180 --height 80 --stroke "#fd7e14" --background "#ffe8cc"
```

For clean style, add `--font-family 2 --crisp`.

### Connect two labeled shapes

```bash
excalidraw-tools edit connect --input diagram.excalidraw --from-label "Gateway API" --to-label "Cache" --from-edge right --to-edge left --elbowed --label "Redis"
```

If continuous spec sync is enabled, append `--sync-spec` to each edit command.

After any edit, run validate + render.

## Sync Spec from Existing Diagram

If a diagram already exists and no spec is present, derive one:

```bash
excalidraw-tools sync-spec --diagram system-architecture.excalidraw --spec
```

Omit `--spec` value to use the default sidecar path (`system-architecture.spec.json`).

## Reading Existing Diagrams

When asked what is in a file:

1. Render it first
2. Describe structure (shapes, labels, arrows, layout)
3. Mention handwritten `freedraw` content as approximate

Use (always match the PNG base name to the `.excalidraw` file):

```bash
if curl -fsS http://localhost:3004/healthz >/dev/null; then
  curl -fsS -X POST "http://localhost:3004/render/png" \
    -H "Content-Type: text/plain" \
    --data-binary "@FILE.excalidraw" \
    -o FILE.png
else
  excalidraw-tools preview FILE.excalidraw --output FILE.png
fi
```

## Validation and Regression

Before finalizing major changes to this skill:

```bash
excalidraw-tools validate assets/golden/simple-flow.excalidraw
excalidraw-tools golden-check
```

`golden-check` verifies:
- schema validity
- expected element counts
- deterministic golden hash
- spec round-trip consistency
- render smoke test

## Rendering Notes

Default rendering should use the Chromium-backed `/render/png` path (browser-accurate text shaping and spacing).

The `excalidraw-tools preview` command is fallback-only and intentionally approximate:
- uses Matplotlib, not Excalidraw's browser renderer
- applies `invert_yaxis()` to match screen coordinates
- good for review loops when the Chromium path is unavailable
- does **not** support `fontMap` — custom font substitution only works with the Chromium renderer

If exact visual parity is required, open the `.excalidraw` file in Excalidraw.

### Font substitution at render time

The Chromium renderer supports a `fontMap` query parameter that replaces Excalidraw's built-in font names in the SVG before rasterization. Format: `fontMap=FROM:TO` (comma-separated for multiple). The `.excalidraw` file is unchanged; substitution is render-only.

For fonts registered in `renderer/fonts/fonts.json` (custom `.otf`/`.ttf`/`.woff2` files), the renderer also injects `@font-face` CSS rules so Chromium can resolve them. System fonts installed in the container (e.g., CMU via `fonts-cmu`) need no `fonts.json` entry.

## References

Load detailed references only when needed:

- `references/json-format.md`: Required fields and element rules
- `references/arrows.md`: Arrow routing patterns and edge math
