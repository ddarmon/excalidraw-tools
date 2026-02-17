# excalidraw-tools

CLI tools and Python library for creating, editing, validating, and
rendering [Excalidraw](https://excalidraw.com) diagrams
programmatically.

Designed to be used by LLM agents or directly from the command line. The
tools enforce correct Excalidraw JSON structure --- roundness values,
seed generation, index ordering, arrow bindings --- so you never have to
write raw `.excalidraw` JSON by hand.

## Install

```bash
uv tool install excalidraw-tools                # CLI only
uv tool install "excalidraw-tools[preview]"     # CLI + matplotlib renderer
```

Or with pip:

```bash
pip install excalidraw-tools
pip install "excalidraw-tools[preview]"
```

## Agent skill

This repo ships an [Agent Skill](https://agentskills.io) in
`skills/excalidraw/`. The skill teaches LLM agents how to use the
`excalidraw-tools` CLI to create and iterate on diagrams through a
structured workflow: build from spec, validate, render, show preview,
iterate on feedback.

The skill follows the open [SKILL.md
standard](https://agentskills.io/specification) and works with any
compatible agent, including:

-   [Claude Code](https://claude.ai/code)
-   [Cursor](https://cursor.com)
-   [OpenAI Codex](https://developers.openai.com/codex)
-   [VS Code (Copilot)](https://code.visualstudio.com)
-   [Gemini CLI](https://geminicli.com)
-   [Goose](https://block.github.io/goose/), [Amp](https://ampcode.com),
    [Roo Code](https://roocode.com), and
    [others](https://agentskills.io/home)

To use the skill, point your agent at the `skills/excalidraw/` directory
using whatever mechanism it supports (e.g., Claude Code plugin, Cursor
skills directory, `--add-dir`, etc.).

## Quick start

### Build a diagram from a spec

Write a compact JSON spec:

```json
{
  "seed": 42,
  "nodes": [
    { "id": "client", "type": "ellipse", "label": "Client", "x": 120, "y": 80, "width": 200, "height": 80 },
    { "id": "api",    "type": "rectangle", "label": "API",  "x": 120, "y": 260, "width": 200, "height": 80 }
  ],
  "edges": [
    { "from": "client", "to": "api", "fromEdge": "bottom", "toEdge": "top", "label": "HTTPS" }
  ]
}
```

Generate the diagram:

```bash
excalidraw-tools build --spec diagram.spec.json --output diagram.excalidraw
excalidraw-tools validate diagram.excalidraw
```

### Edit an existing diagram

```bash
excalidraw-tools edit move     --input diagram.excalidraw --label "API" --dx 200 --dy 0
excalidraw-tools edit relabel  --input diagram.excalidraw --label "API" --text "Gateway"
excalidraw-tools edit recolor  --input diagram.excalidraw --label "Gateway" --stroke "#1971c2" --background "#a5d8ff"
excalidraw-tools edit delete   --input diagram.excalidraw --label "Gateway"
excalidraw-tools edit add-box  --input diagram.excalidraw --label "Cache" --x 400 --y 260
excalidraw-tools edit connect  --input diagram.excalidraw --from-label "Client" --to-label "Cache"
```

### Render a preview

```bash
excalidraw-tools preview diagram.excalidraw --output diagram.png
```

For browser-accurate rendering with proper font support, see the
[Self-hosted Excalidraw stack](#self-hosted-excalidraw-stack) section
below.

## CLI reference

| Command                         | Description                                                                 |
| ------------------------------- | --------------------------------------------------------------------------- |
| `excalidraw-tools build`        | Build `.excalidraw` from a spec JSON                                        |
| `excalidraw-tools edit <sub>`   | Edit in place: `move`, `relabel`, `recolor`, `delete`, `add-box`, `connect` |
| `excalidraw-tools validate`     | Schema and linkage validation                                               |
| `excalidraw-tools preview`      | Approximate PNG via matplotlib                                              |
| `excalidraw-tools sync-spec`    | Derive/update a `.spec.json` sidecar from a diagram                         |
| `excalidraw-tools golden-check` | Regression test against bundled golden fixture                              |

Run any command with `--help` for full options.

## Self-hosted Excalidraw stack

This repo includes a Docker Compose stack that runs a fully self-hosted
Excalidraw instance with real-time collaboration, persistent share
links, and a high-fidelity rendering API. No diagram data is sent to
third-party services.

### Architecture

Collaboration and storage path:

```
┌──────────────┐    HTTP     ┌──────────────────┐
│   Browser    │◄───────────►│   Excalidraw UI  │  :3000
│              │             │   (nginx + JS)   │
│              │  WebSocket  ├──────────────────┤
│              │◄───────────►│  excalidraw-room │  :3002
│              │             │  (WS relay)      │
│              │    HTTP     ├──────────────────┤
│              │◄───────────►│ storage-backend  │  :3003
│              │             │ (blob store)     │
└──────────────┘             └──────────────────┘
```

Rendering path:

```
┌──────────────────────┐   HTTP    ┌──────────────────────┐
│  .excalidraw source  │──────────►│       renderer       │  :3004
└──────────────────────┘           │ (SVG + PNG endpoints)│
                                   └──────────┬───────────┘
                                              │
                                              │ internal HTTP
                                              ▼
                                   ┌──────────────────────┐
                                   │        kroki         │  :8000 (internal)
                                   └──────────┬───────────┘
                                              │
                                              ▼
                                   ┌──────────────────────┐
                                   │  kroki-excalidraw    │  :8004 (internal)
                                   └──────────────────────┘
```

-   **Excalidraw UI** --- the official frontend image, patched at
    startup to point at your own services instead of Excalidraw's public
    infrastructure.
-   **excalidraw-room** --- official WebSocket relay for real-time
    collaboration. Stateless.
-   **storage-backend** --- minimal Express.js blob store (\~40 lines)
    for the share-link feature. Stores encrypted scene snapshots on a
    Docker volume.
-   **renderer** --- custom Node service exposing `POST /render/svg` and
    `POST /render/png` for converting `.excalidraw` JSON to images.
-   **kroki** / **kroki-excalidraw** --- SVG conversion backend used
    internally by the renderer.

### Prerequisites

-   [Docker](https://docs.docker.com/get-docker/) and Docker Compose
    (v2+)

Verify with:

```bash
docker --version
docker compose version
```

### Setup

```bash
docker compose up -d --build
```

Verify the renderer is healthy:

```bash
curl http://localhost:3004/healthz
```

Open <http://localhost:3000> in your browser to use the Excalidraw UI
with collaboration enabled.

### Rendering API

```bash
# Excalidraw -> SVG
curl -X POST http://localhost:3004/render/svg \
  -H "Content-Type: text/plain" \
  --data-binary "@diagram.excalidraw" \
  -o diagram.svg
```

```bash
# Excalidraw -> PNG (display-sized default: width=1600)
curl -X POST "http://localhost:3004/render/png" \
  -H "Content-Type: text/plain" \
  --data-binary "@diagram.excalidraw" \
  -o diagram.png
```

```bash
# Override render size/background at request time
curl -X POST "http://localhost:3004/render/png?width=2400&background=%23ffffff" \
  -H "Content-Type: text/plain" \
  --data-binary "@diagram.excalidraw" \
  -o diagram-wide.png
```

```bash
# Render with a custom font (replace Helvetica with CMU Serif)
curl -X POST "http://localhost:3004/render/png?fontMap=Helvetica:CMU+Serif" \
  -H "Content-Type: text/plain" \
  --data-binary "@diagram.excalidraw" \
  -o diagram-cmu.png
```

Health endpoint:

```bash
curl http://localhost:3004/healthz
```

### Batch rendering

Use `scripts/render_diagrams.sh` to render one file or a directory tree.
Outputs are written next to each source `.excalidraw` file as `.png`.

```bash
# Render all diagrams recursively under diagrams/
scripts/render_diagrams.sh --input diagrams
```

```bash
# Render one file with custom settings
scripts/render_diagrams.sh \
  --input diagram.excalidraw \
  --width 2400 \
  --background "#ffffff"
```

### Font mapping

Excalidraw stores fonts as integer IDs that map to fixed CSS names:

| fontFamily | CSS name  |
| ---------- | --------- |
| 1          | Virgil    |
| 2          | Helvetica |
| 3          | Cascadia  |

The renderer can substitute these names with custom fonts at render
time.

**Default mapping** --- set via `DEFAULT_FONT_MAP` in
`docker-compose.yml`:

```yaml
- DEFAULT_FONT_MAP=Helvetica:CMU Serif
```

Multiple mappings are comma-separated:

```yaml
- DEFAULT_FONT_MAP=Helvetica:CMU Serif,Virgil:CMU Sans Serif
```

**Per-request overrides** --- pass a `fontMap` query parameter:

```bash
curl -X POST "http://localhost:3004/render/png?fontMap=Helvetica:CMU+Serif" \
  -H "Content-Type: text/plain" \
  --data-binary "@diagram.excalidraw" \
  -o diagram.png
```

**Custom font files** --- place `.otf`, `.ttf`, `.woff`, or `.woff2`
files in `renderer/fonts/` and register them in
`renderer/fonts/fonts.json`:

```json
{
  "FinancierDisplay": [
    { "file": "FinancierDisplay-Regular.otf" }
  ]
}
```

Fonts are base64-encoded and injected as `@font-face` rules at render
time. The fonts directory is volume-mounted, so you can add files and
restart the container without rebuilding:

```bash
docker compose restart renderer
```

### Configuration

Renderer environment variables (set in `docker-compose.yml`):

| Variable             | Default             | Purpose                                   |
| -------------------- | ------------------- | ----------------------------------------- |
| `KROKI_URL`          | `http://kroki:8000` | Internal Kroki base URL                   |
| `DEFAULT_WIDTH`      | `1600`              | Default PNG width when no size is passed  |
| `DEFAULT_DPI`        | `96`                | Default DPI for zoom-based renders        |
| `DEFAULT_ZOOM`       | `1`                 | Default zoom for zoom-based renders       |
| `CHROMIUM_PATH`      | `/usr/bin/chromium` | Chromium executable used for PNG output   |
| `DEFAULT_BACKGROUND` | `#ffffff`           | Default non-transparent output background |
| `REQUEST_TIMEOUT_MS` | `30000`             | Upstream render timeout                   |
| `DEFAULT_FONT_MAP`   | *(empty)*           | Default font substitutions (see above)    |
| `FONTS_DIR`          | `/app/fonts`        | Directory for custom font files           |

The Excalidraw UI service uses `VITE_APP_WS_SERVER_URL`,
`VITE_APP_BACKEND_V2_GET_URL`, and `VITE_APP_BACKEND_V2_POST_URL` to
configure collaboration and storage endpoints (patched into the built JS
at container startup via `sed`).

### Collaboration and storage

1.  Open <http://localhost:3000>.
2.  Click the hamburger menu (top-left) → **Live collaboration** →
    **Start session**.
3.  Copy the generated link and open it in another browser window.
4.  Both users see each other's cursors and drawings in real time.

Share links encrypt the scene client-side (AES-GCM) and store the
encrypted blob on the storage backend. The encryption key stays in the
URL fragment (`#`) and is never sent to the server.

Key limitations:

-   Collaboration rooms are ephemeral --- room data is lost when all
    participants leave (Firebase persistence is disabled).
-   Embedded images in share links are not stored (Firebase Storage is
    disabled). Built-in shapes and text work fine.
-   No authentication --- put an authenticating reverse proxy in front
    for restricted access.

### Managing the stack

```bash
docker compose up -d --build   # Start (rebuild custom images if changed)
docker compose down            # Stop all containers
docker compose logs -f         # Tail logs from all services
docker compose ps              # Check container status
```

Scene data is stored in the `storage-data` Docker volume. To wipe it:

```bash
docker compose down -v
```

### Deployment

For a public deployment, replace the `localhost` URLs in
`docker-compose.yml` with your public domain and add an HTTPS reverse
proxy (e.g., Caddy, nginx, or Traefik). Browsers require a secure
context for the `crypto.subtle` API that Excalidraw uses for encryption,
so collaboration will silently fail without HTTPS on non-localhost
origins.

## Python library

The package is also importable for custom diagram scripts:

```python
from excalidraw_tools import (
    IdFactory, make_shape, make_text, add_label,
    connect, new_document, save_diagram,
)

elements = []
ids = IdFactory(seed=42)

box = make_shape(elements, ids, "rectangle", 100, 100, 200, 80)
add_label(elements, ids, box, "Hello")

doc = new_document(elements)
save_diagram("hello.excalidraw", doc)
```

## Spec format

The spec is a compact JSON representation of a diagram:

-   **`seed`**: Integer seed for deterministic ID generation
-   **`updated`** *(optional)*: Timestamp applied to all elements
-   **`style`** *(optional)*:
    `{ "fontFamily": 1|2|3, "roughness": 0|1 }`
-   **`nodes`**: List of shapes (`rectangle`, `ellipse`, `diamond`)
-   **`edges`**: List of arrows connecting nodes by ID

Per-node fields: `id`, `type`, `label`, `x`, `y`, `width`, `height`,
`stroke`, `background`, `strokeWidth`, `strokeStyle`, `roughness`,
`fontSize`, `fontFamily`.

Per-edge fields: `from`, `to`, `fromEdge`, `toEdge`, `stroke`,
`elbowed`, `label`, `fontSize`, `fontFamily`.

## Dependencies

-   **Core**: Python 3.10+, stdlib only (no runtime dependencies)
-   **Preview**: matplotlib (optional, install with `[preview]`)
-   **Docker stack**: Docker + Docker Compose v2+ (optional, for
    browser-accurate rendering and self-hosted collaboration)
