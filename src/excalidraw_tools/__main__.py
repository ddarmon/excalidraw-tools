"""Unified CLI for excalidraw-tools."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="excalidraw-tools",
        description="Create, edit, validate, and preview Excalidraw diagrams.",
    )
    sub = parser.add_subparsers(dest="command")

    from excalidraw_tools.build import add_subparser as add_build
    from excalidraw_tools.edit import add_subparser as add_edit
    from excalidraw_tools.sync_spec import add_subparser as add_sync_spec
    from excalidraw_tools.validate import add_subparser as add_validate
    from excalidraw_tools.preview import add_subparser as add_preview
    from excalidraw_tools.golden_check import add_subparser as add_golden_check

    add_build(sub)
    add_edit(sub)
    add_validate(sub)
    add_preview(sub)
    add_sync_spec(sub)
    add_golden_check(sub)

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command is None:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
