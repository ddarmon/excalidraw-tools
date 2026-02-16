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

The `fontMap` parameter supports arbitrary `FROM:TO` mappings for any built-in font name (Virgil, Helvetica, Cascadia). Common choices (system fonts available in the renderer container):

| Render font        | Maps from      | fontMap value                   |
|--------------------|----------------|---------------------------------|
| CMU Serif          | Virgil (1)     | `Virgil:CMU+Serif`             |
| CMU Serif          | Helvetica (2)  | `Helvetica:CMU+Serif`          |
| CMU Sans Serif     | Virgil (1)     | `Virgil:CMU+Sans+Serif`        |
| CMU Sans Serif     | Helvetica (2)  | `Helvetica:CMU+Sans+Serif`     |
| CMU Typewriter Text| Cascadia (3)   | `Cascadia:CMU+Typewriter+Text` |

Match the `FROM` font to the `fontFamily` used in the diagram. For hand-drawn style (fontFamily 1), map from Virgil. For clean style (fontFamily 2), map from Helvetica.

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

## Library API Reference

All element-creating functions share this calling convention:

- First two positional args are always `(elements, ids)` where `elements` is the list being built and `ids` is an `IdFactory` instance.
- Each function **appends** the created element to `elements` and **returns** it.
- Do NOT manually set `id`, `index`, `seed`, `versionNonce`, `updated`, or `boundElements` — the library handles these.

### IdFactory

```python
ids = IdFactory(seed=42)

ids.random_id()        # → "el-hbrpoig8f1cb"  (unique element ID)
ids.random_id("arr")   # → "arr-fno6b9m80o2r" (custom prefix)
ids.nonce()            # → 1738238662          (random int for seed/versionNonce)
ids.next_index()       # → "a0", "a1", …       (fractional z-index)
ids.reserve_id("my-id")  # prevent future duplicates
```

### make_shape

```python
make_shape(elements, ids, etype, x, y, width, height, *,
           stroke="#1e1e1e", background="transparent",
           stroke_width=2, stroke_style="solid",
           roughness=1, element_id=None)
```

Supported `etype` values: `"rectangle"`, `"ellipse"`, `"diamond"`. Do **not** use `"line"` or `"arrow"` — use `make_arrow` instead.

### make_text

```python
make_text(elements, ids, content, x, y, width, height, *,
          container_id=None, font_size=20, font_family=1,
          stroke="#1e1e1e")
```

- `width`/`height` are required — estimate from text length (e.g., `width = len(text) * font_size * 0.6`, `height = font_size * 1.5`).
- Standalone text: omit `container_id` (defaults to `None`, sets `verticalAlign="top"`).
- Bound label inside a shape: set `container_id=shape["id"]` (sets `verticalAlign="middle"`). Prefer `add_label` for this.

### make_arrow

```python
make_arrow(elements, ids, x, y, points, *,
           start_id=None, end_id=None,
           stroke="#1e1e1e", stroke_width=2,
           elbowed=False, source_edge=None, target_edge=None)
```

Use for **all** line and arrow elements — including curves, tick marks, axes, and polylines. `points` is a list of `[x, y]` offsets relative to `(x, y)` (e.g., `[[0, 0], [100, 0]]` for a horizontal segment).

- Produces an arrow with `endArrowhead="arrow"` by default. For a plain line (no arrowhead), override on the returned dict: `el["endArrowhead"] = None` and `el["type"] = "line"`.
- For multi-point curves, pass many points with roundness type 2 (the default for non-elbowed arrows).
- `start_id`/`end_id` bind the arrow to shapes (updates `boundElements` on both).

### add_label

```python
add_label(elements, ids, shape, label, *,
          font_size=20, font_family=1, text_height=25)
```

Creates text centered inside `shape`. Automatically sets `containerId` and updates `shape["boundElements"]`.

### connect

```python
connect(elements, ids, source, target, *,
        source_edge="bottom", target_edge="top",
        stroke="#1e1e1e", elbowed=False)
```

High-level arrow between two shapes. Calculates edge points and routing automatically. Preferred over `make_arrow` when connecting labeled shapes.

### new_document / save_diagram / load_diagram

```python
doc = new_document(elements)          # wrap element list in document structure
save_diagram("/path/to/file.excalidraw", doc)  # path first, data second
doc = load_diagram("/path/to/file.excalidraw") # read existing diagram
```

## Create Diagrams

Always use the tools — never write raw `.excalidraw` JSON.

1. **Spec + build (default):** Write a spec JSON with `nodes` and `edges`, then generate with `excalidraw-tools build`. Iterate with `excalidraw-tools edit` subcommands.
2. **Library fallback:** If the spec format or edit commands cannot express what you need (e.g., curves, custom lines, standalone text, tick marks), write a Python script using the library API (see Library API Reference above). Minimal working example:

```python
from excalidraw_tools import (
    IdFactory, make_shape, make_text, make_arrow,
    add_label, new_document, save_diagram,
)

ids = IdFactory(seed=42)
elements = []

# Rectangle with a bound label
box = make_shape(elements, ids, "rectangle", 100, 100, 200, 80,
                 stroke="#1971c2", background="#a5d8ff")
add_label(elements, ids, box, "API Server")

# Standalone text
make_text(elements, ids, "Clients", 160, 30, 80, 25, font_size=16)

# Arrow (axis, line, or connector)
make_arrow(elements, ids, 200, 180, [[0, 0], [0, 60]],
           stroke="#e03131")

# Plain line (no arrowhead) — override the returned element
line = make_arrow(elements, ids, 50, 200, [[0, 0], [300, 0]])
line["type"] = "line"
line["endArrowhead"] = None

save_diagram("/tmp/example.excalidraw", new_document(elements))
```

**Warning — `make_shape` and element types:**
- Do **not** use `make_shape` with `etype="line"` or `etype="arrow"`. It produces elements missing the required `points` array, which crashes the Kroki renderer (error: `Cannot read properties of undefined (reading 'length')`).
- Use `make_arrow` for all lines, arrows, axes, curves, and polylines. For a plain line without an arrowhead, override the returned dict (`el["type"] = "line"` and `el["endArrowhead"] = None`).
- For simple grid lines or separators, thin rectangles also work (e.g., `width=1` for vertical, `height=1` for horizontal).

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
