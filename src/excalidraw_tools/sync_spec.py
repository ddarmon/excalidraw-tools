#!/usr/bin/env python3
"""Derive or update a sidecar .spec.json from an .excalidraw file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from excalidraw_tools.spec import default_spec_path, resolve_spec_path, sync_spec_for_diagram


def _run(args: argparse.Namespace) -> int:
    spec_path = resolve_spec_path(args.diagram, args.spec)
    if spec_path is None:
        spec_path = default_spec_path(args.diagram)

    try:
        out = sync_spec_for_diagram(args.diagram, spec_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote spec: {out}")
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("sync-spec", help="Derive/update a .spec.json from an .excalidraw file")
    p.add_argument("--diagram", type=Path, required=True, help="Input .excalidraw file")
    p.add_argument(
        "--spec",
        nargs="?",
        const="AUTO",
        help="Output spec path; omit value to use <diagram>.spec.json",
    )
    p.set_defaults(func=_run)
