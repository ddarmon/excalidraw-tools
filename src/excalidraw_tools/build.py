#!/usr/bin/env python3
"""Build a new .excalidraw file from a compact JSON spec."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

from excalidraw_tools.lib import IdFactory, add_label, connect, make_shape, make_text, new_document, save_diagram
from excalidraw_tools.spec import resolve_spec_path, sync_spec_for_data

VALID_SHAPES = {"rectangle", "ellipse", "diamond"}


def _load_spec(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to parse spec JSON: {exc}") from exc


def _require_list(spec: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = spec.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"spec.{key} must be a list")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError(f"spec.{key} entries must be objects")
    return value


def _read_style(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Read optional top-level style block with defaults."""
    style = spec.get("style", {})
    if not isinstance(style, dict):
        raise ValueError("spec.style must be an object")
    return {
        "fontFamily": int(style.get("fontFamily", 1)),
        "roughness": int(style.get("roughness", 1)),
    }


def build(spec: Dict[str, Any]) -> Dict[str, Any]:
    nodes = _require_list(spec, "nodes")
    edges = _require_list(spec, "edges")
    style = _read_style(spec)

    elements: List[Dict[str, Any]] = []
    ids = IdFactory(seed=spec.get("seed", 42), start_index=0)
    aliases: Dict[str, Dict[str, Any]] = {}

    for idx, node in enumerate(nodes):
        alias = node.get("id")
        if not isinstance(alias, str) or not alias:
            raise ValueError(f"nodes[{idx}].id must be a non-empty string")
        if alias in aliases:
            raise ValueError(f"duplicate node id: {alias}")

        ntype = node.get("type", "rectangle")
        if ntype not in VALID_SHAPES:
            raise ValueError(f"nodes[{idx}].type must be one of: {', '.join(sorted(VALID_SHAPES))}")

        x = float(node.get("x", 0))
        y = float(node.get("y", 0))
        width = float(node.get("width", 200))
        height = float(node.get("height", 80))
        stroke = str(node.get("stroke", "#1e1e1e"))
        background = str(node.get("background", "transparent"))
        stroke_width = int(node.get("strokeWidth", 2))
        stroke_style = str(node.get("strokeStyle", "solid"))
        roughness = int(node.get("roughness", style["roughness"]))

        shape = make_shape(
            elements,
            ids,
            ntype,
            x,
            y,
            width,
            height,
            stroke=stroke,
            background=background,
            stroke_width=stroke_width,
            stroke_style=stroke_style,
            roughness=roughness,
            element_id=alias,
        )
        aliases[alias] = shape

        label = node.get("label")
        if label:
            add_label(
                elements,
                ids,
                shape,
                str(label),
                font_size=int(node.get("fontSize", 20)),
                font_family=int(node.get("fontFamily", style["fontFamily"])),
            )

    for idx, edge in enumerate(edges):
        src = edge.get("from")
        dst = edge.get("to")
        if not isinstance(src, str) or src not in aliases:
            raise ValueError(f"edges[{idx}].from references unknown node: {src}")
        if not isinstance(dst, str) or dst not in aliases:
            raise ValueError(f"edges[{idx}].to references unknown node: {dst}")

        arrow = connect(
            elements,
            ids,
            aliases[src],
            aliases[dst],
            source_edge=str(edge.get("fromEdge", "bottom")),
            target_edge=str(edge.get("toEdge", "top")),
            stroke=str(edge.get("stroke", "#1e1e1e")),
            elbowed=bool(edge.get("elbowed", False)),
        )

        edge_label = edge.get("label")
        if edge_label:
            end = arrow["points"][-1]
            label_x = arrow["x"] + end[0] / 2 - 35
            label_y = arrow["y"] + end[1] / 2 - 10
            make_text(
                elements,
                ids,
                str(edge_label),
                label_x,
                label_y,
                70,
                20,
                container_id=None,
                font_size=int(edge.get("fontSize", 14)),
                font_family=int(edge.get("fontFamily", style["fontFamily"])),
                stroke=str(edge.get("stroke", "#1e1e1e")),
            )

    updated = spec.get("updated")
    if updated is not None:
        updated_ts = int(updated)
        for elem in elements:
            elem["updated"] = updated_ts

    return new_document(elements)


def _run(args: argparse.Namespace) -> int:
    try:
        spec = _load_spec(args.spec)
        doc = build(spec)
        save_diagram(args.output, doc)

        sync_target = resolve_spec_path(args.output, args.sync_spec)
        if sync_target is not None:
            sync_spec_for_data(doc, sync_target)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {len(doc['elements'])} elements to {args.output}")
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("build", help="Build a new .excalidraw file from a spec JSON")
    p.add_argument("--spec", type=Path, required=True, help="Path to diagram spec JSON")
    p.add_argument("--output", type=Path, required=True, help="Output .excalidraw path")
    p.add_argument(
        "--sync-spec",
        nargs="?",
        const="AUTO",
        help="Write sidecar spec path; omit value to use <output>.spec.json",
    )
    p.set_defaults(func=_run)
