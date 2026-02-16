#!/usr/bin/env python3
"""Run deterministic checks against the golden fixture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.resources
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Sequence

from excalidraw_tools.build import build as build_from_spec
from excalidraw_tools.spec import diagram_to_spec
from excalidraw_tools.validate import validate_document

EXPECTED_HASH = "1c61a11fd19e4d761ff7aaff8d1f50bd24d38aa0584de78f3aae485aea2a0e16"
EXPECTED_COUNTS = {
    "ellipse": 1,
    "rectangle": 2,
    "arrow": 2,
    "text": 5,
}


def _default_golden_path() -> Path:
    return Path(str(importlib.resources.files("excalidraw_tools.data.golden") / "simple-flow.excalidraw"))


def _default_spec_path() -> Path:
    return Path(str(importlib.resources.files("excalidraw_tools.data.golden") / "simple-flow.spec.json"))


def canonical_hash(data: Dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_types(data: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for elem in data.get("elements", []):
        if not isinstance(elem, dict) or elem.get("isDeleted"):
            continue
        etype = elem.get("type")
        counts[etype] = counts.get(etype, 0) + 1
    return counts


def run_render_smoke(golden_path: Path) -> None:
    try:
        from excalidraw_tools.preview import render
    except RuntimeError:
        print("render smoke skipped: matplotlib unavailable")
        return

    preview = Path(tempfile.gettempdir()) / "excalidraw_golden_preview.png"
    try:
        render(golden_path, preview, dpi=150)
    except RuntimeError:
        print("render smoke skipped: matplotlib unavailable")
        return

    if not preview.exists() or preview.stat().st_size < 128:
        raise RuntimeError("render smoke failed: preview file missing or empty")


def _run(args: argparse.Namespace) -> int:
    golden = load_json(args.golden)
    errors = validate_document(golden)
    if errors:
        for err in errors:
            print(f"validation error: {err}", file=sys.stderr)
        return 1

    counts = count_types(golden)
    for etype, expected in EXPECTED_COUNTS.items():
        actual = counts.get(etype, 0)
        if actual != expected:
            print(f"count mismatch for {etype}: expected {expected}, got {actual}", file=sys.stderr)
            return 1

    actual_hash = canonical_hash(golden)
    if actual_hash != EXPECTED_HASH:
        print(
            f"golden hash mismatch: expected {EXPECTED_HASH}, got {actual_hash}",
            file=sys.stderr,
        )
        return 1

    spec = load_json(args.spec)
    synced_spec = diagram_to_spec(golden, existing_spec=spec)
    if canonical_hash(synced_spec) != canonical_hash(spec):
        print("synced spec mismatch against golden spec", file=sys.stderr)
        return 1

    rebuilt = build_from_spec(spec)
    rebuilt_hash = canonical_hash(rebuilt)
    if rebuilt_hash != actual_hash:
        print(
            f"rebuilt hash mismatch: golden {actual_hash}, rebuilt {rebuilt_hash}",
            file=sys.stderr,
        )
        return 1

    run_render_smoke(args.golden)
    print(f"golden check passed ({actual_hash})")
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("golden-check", help="Run regression checks against golden fixture")
    p.add_argument(
        "--golden",
        type=Path,
        default=None,
        help="Golden .excalidraw fixture (default: bundled)",
    )
    p.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="Spec used to generate the golden fixture (default: bundled)",
    )
    p.set_defaults(func=_run_with_defaults)


def _run_with_defaults(args: argparse.Namespace) -> int:
    if args.golden is None:
        args.golden = _default_golden_path()
    if args.spec is None:
        args.spec = _default_spec_path()
    return _run(args)
