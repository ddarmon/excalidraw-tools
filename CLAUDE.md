# CLAUDE.md

## Project overview

`excalidraw-tools` is a Python package that provides CLI tools and a
library for creating, editing, validating, and rendering Excalidraw
diagrams. It is the tools layer behind the `excalidraw` Claude Code
skill at `~/.claude/skills/excalidraw/`.

## Project structure

```
src/excalidraw_tools/
├── __init__.py          # Public API re-exports + __version__
├── __main__.py          # CLI dispatcher (excalidraw-tools command)
├── lib.py               # Core: shapes, arrows, routing, IdFactory
├── spec.py              # Spec ↔ diagram conversion
├── validate.py          # Schema and linkage validation
├── preview.py           # Matplotlib fallback renderer
├── build.py             # Spec → .excalidraw builder
├── edit.py              # Edit operations (move/relabel/recolor/delete/add-box/connect)
├── sync_spec.py         # Spec sync CLI wrapper
├── golden_check.py      # Regression test runner
└── data/golden/         # Bundled test fixtures

docker-compose.yml           # Self-hosted Excalidraw stack definition
renderer/
├── Dockerfile               # Node image + Chromium + font packages
├── server.js                # /render/svg + /render/png API
├── package.json
└── fonts/
    └── fonts.json           # Custom font file registry
storage-backend/
├── Dockerfile               # Node 20 Alpine image
├── server.js                # Blob store for share links
└── package.json
scripts/
└── render_diagrams.sh       # Batch render helper
```

## Module dependency graph

```
lib.py                    ← foundation, stdlib only
├── spec.py
├── validate.py
├── build.py              (also imports spec)
├── edit.py               (also imports spec)
└── sync_spec.py          (imports spec only)

golden_check.py           (imports build, spec, validate)
preview.py                (standalone, matplotlib only)
```

## Key conventions

-   **Never write raw `.excalidraw` JSON.** Always use the library
    functions in `lib.py` which handle per-type defaults (roundness,
    seeds, index ordering).

-   **All CLI modules expose `add_subparser(subparsers)`** which
    registers the module as a subcommand of the unified
    `excalidraw-tools` CLI.

-   **Deterministic output.** Given the same spec seed and timestamp,
    `build()` produces byte-identical output. The golden check verifies
    this with a SHA-256 hash.

-   **No runtime dependencies.** The core library is stdlib-only.
    `matplotlib` is optional and only used by `preview.py`.

## Testing

Run the regression suite:

```bash
excalidraw-tools golden-check
```

This verifies:

1.  Schema validity of the golden fixture
2.  Element type counts match expected
3.  Deterministic SHA-256 hash matches
4.  Spec round-trip consistency
5.  Render smoke test (if matplotlib available)

## Common tasks

### Add a new edit subcommand

1.  Add a `cmd_<name>(args) -> int` function in `edit.py`
2.  Add the subparser in `edit.py`'s `add_subparser()` function
3.  Run `excalidraw-tools golden-check` to verify nothing broke

### Add a new top-level subcommand

1.  Create the module in `src/excalidraw_tools/`
2.  Implement `add_subparser(subparsers)` in that module
3.  Import and call it in `__main__.py`'s `main()` function

### Update the golden fixture

If `build()` output intentionally changes:

1.  Rebuild:
    `excalidraw-tools build --spec <golden-spec> --output <golden-path>`
2.  Compute new hash:
    `python -c "import json, hashlib; d = json.loads(open('path').read()); print(hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',',':')).encode()).hexdigest())"`
3.  Update `EXPECTED_HASH` in `golden_check.py`

### Install for development

```bash
uv tool install -e ".[preview]"
```

