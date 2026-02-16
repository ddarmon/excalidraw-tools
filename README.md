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
