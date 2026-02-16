#!/usr/bin/env python3
"""Apply deterministic edits to an Excalidraw file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from excalidraw_tools.lib import (
    IdFactory,
    add_label,
    connect,
    load_diagram,
    make_shape,
    make_text,
    move_shape_and_dependents,
    new_document,
    save_diagram,
    touch,
)
from excalidraw_tools.spec import resolve_spec_path, sync_spec_for_data


def _build_factory(elements: List[Dict[str, Any]]) -> IdFactory:
    existing_ids = [elem.get("id") for elem in elements if isinstance(elem, dict) and "id" in elem]
    return IdFactory(start_index=len(elements), existing_ids=existing_ids)


def _match_text(elements: List[Dict[str, Any]], label: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    label_norm = label.lower().strip()

    exact_shape = None
    exact_text = None
    partial_shape = None
    partial_text = None

    for elem in elements:
        if not isinstance(elem, dict) or elem.get("isDeleted") or elem.get("type") != "text":
            continue
        text_value = str(elem.get("text", "")).strip()
        if not text_value:
            continue

        container_id = elem.get("containerId")
        container = None
        if container_id:
            container = next(
                (
                    candidate
                    for candidate in elements
                    if isinstance(candidate, dict)
                    and candidate.get("id") == container_id
                    and not candidate.get("isDeleted")
                ),
                None,
            )

        if text_value.lower() == label_norm:
            exact_shape = container
            exact_text = elem
            break

        if label_norm in text_value.lower() and partial_text is None:
            partial_shape = container
            partial_text = elem

    if exact_text is not None:
        return exact_shape, exact_text
    return partial_shape, partial_text


def _required_shape_by_label(elements: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    shape, text = _match_text(elements, label)
    if text is None:
        raise ValueError(f"could not find label: {label}")
    if shape is None:
        raise ValueError(f"label is standalone text, not a shape label: {label}")
    return shape


def _required_text_by_label(elements: List[Dict[str, Any]], label: str) -> Dict[str, Any]:
    _, text = _match_text(elements, label)
    if text is None:
        raise ValueError(f"could not find label: {label}")
    return text


def _output_path(input_path: Path, output_path: Optional[Path]) -> Path:
    return output_path if output_path else input_path


def _sync_spec_if_requested(data: Dict[str, Any], diagram_path: Path, sync_spec: Optional[str]) -> Optional[Path]:
    spec_path = resolve_spec_path(diagram_path, sync_spec)
    if spec_path is None:
        return None
    sync_spec_for_data(data, spec_path)
    return spec_path


def cmd_move(args: argparse.Namespace) -> int:
    data = load_diagram(args.input)
    elements = data.get("elements", [])
    factory = _build_factory(elements)

    shape = _required_shape_by_label(elements, args.label)
    move_shape_and_dependents(data, shape, args.dx, args.dy, factory)

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Moved '{args.label}' by dx={args.dx}, dy={args.dy} -> {out} (spec: {spec_path})")
    else:
        print(f"Moved '{args.label}' by dx={args.dx}, dy={args.dy} -> {out}")
    return 0


def cmd_relabel(args: argparse.Namespace) -> int:
    data = load_diagram(args.input)
    elements = data.get("elements", [])
    factory = _build_factory(elements)

    text_elem = _required_text_by_label(elements, args.label)
    text_elem["text"] = args.text
    text_elem["originalText"] = args.text
    touch(text_elem, factory)

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Relabeled '{args.label}' -> '{args.text}' in {out} (spec: {spec_path})")
    else:
        print(f"Relabeled '{args.label}' -> '{args.text}' in {out}")
    return 0


def cmd_recolor(args: argparse.Namespace) -> int:
    data = load_diagram(args.input)
    elements = data.get("elements", [])
    factory = _build_factory(elements)

    shape = _required_shape_by_label(elements, args.label)
    if args.stroke:
        shape["strokeColor"] = args.stroke
    if args.background:
        shape["backgroundColor"] = args.background
    touch(shape, factory)

    text_label = next(
        (
            elem
            for elem in elements
            if isinstance(elem, dict)
            and not elem.get("isDeleted")
            and elem.get("type") == "text"
            and elem.get("containerId") == shape.get("id")
        ),
        None,
    )
    if text_label and args.stroke:
        text_label["strokeColor"] = args.stroke
        touch(text_label, factory)

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Recolored '{args.label}' in {out} (spec: {spec_path})")
    else:
        print(f"Recolored '{args.label}' in {out}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    data = load_diagram(args.input)
    elements = data.get("elements", [])
    factory = _build_factory(elements)

    shape, text = _match_text(elements, args.label)
    if text is None:
        raise ValueError(f"could not find label: {args.label}")

    targets: List[Dict[str, Any]] = []
    if shape is not None:
        targets.append(shape)
        targets.extend(
            [
                elem
                for elem in elements
                if isinstance(elem, dict)
                and not elem.get("isDeleted")
                and elem.get("type") == "text"
                and elem.get("containerId") == shape.get("id")
            ]
        )
        targets.extend(
            [
                elem
                for elem in elements
                if isinstance(elem, dict)
                and not elem.get("isDeleted")
                and elem.get("type") == "arrow"
                and (
                    (elem.get("startBinding") or {}).get("elementId") == shape.get("id")
                    or (elem.get("endBinding") or {}).get("elementId") == shape.get("id")
                )
            ]
        )
    else:
        targets.append(text)

    for elem in targets:
        if elem.get("isDeleted"):
            continue
        elem["isDeleted"] = True
        touch(elem, factory)

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Deleted elements for '{args.label}' in {out} (spec: {spec_path})")
    else:
        print(f"Deleted elements for '{args.label}' in {out}")
    return 0


def cmd_add_box(args: argparse.Namespace) -> int:
    data = load_diagram(args.input) if args.input.exists() else {"elements": []}
    if "elements" not in data:
        data["elements"] = []

    if data.get("type") != "excalidraw":
        data = new_document(data.get("elements", []))

    elements = data["elements"]
    factory = _build_factory(elements)

    shape = make_shape(
        elements,
        factory,
        "rectangle",
        args.x,
        args.y,
        args.width,
        args.height,
        stroke=args.stroke,
        background=args.background,
        stroke_style="dashed" if args.dashed else "solid",
        roughness=0 if args.crisp else 1,
    )
    add_label(elements, factory, shape, args.label, font_size=args.font_size, font_family=args.font_family)

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Added box '{args.label}' ({shape['id']}) -> {out} (spec: {spec_path})")
    else:
        print(f"Added box '{args.label}' ({shape['id']}) -> {out}")
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    data = load_diagram(args.input)
    elements = data.get("elements", [])
    factory = _build_factory(elements)

    source = _required_shape_by_label(elements, args.from_label)
    target = _required_shape_by_label(elements, args.to_label)

    arrow = connect(
        elements,
        factory,
        source,
        target,
        source_edge=args.from_edge,
        target_edge=args.to_edge,
        stroke=args.stroke,
        elbowed=args.elbowed,
    )

    if args.label:
        end = arrow["points"][-1]
        label_x = arrow["x"] + end[0] / 2 - 35
        label_y = arrow["y"] + end[1] / 2 - 10
        make_text(
            elements,
            factory,
            args.label,
            label_x,
            label_y,
            70,
            20,
            container_id=None,
            font_size=args.font_size,
            font_family=args.font_family,
            stroke=args.stroke,
        )

    out = _output_path(args.input, args.output)
    save_diagram(out, data)
    spec_path = _sync_spec_if_requested(data, out, args.sync_spec)
    if spec_path:
        print(f"Connected '{args.from_label}' -> '{args.to_label}' in {out} (spec: {spec_path})")
    else:
        print(f"Connected '{args.from_label}' -> '{args.to_label}' in {out}")
    return 0


def _add_common_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True, help="Input .excalidraw file")
    parser.add_argument("--output", type=Path, help="Output path (defaults to --input)")
    parser.add_argument(
        "--sync-spec",
        nargs="?",
        const="AUTO",
        help="Write/update sidecar spec; omit value to use <output>.spec.json",
    )


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("edit", help="Edit an existing .excalidraw file")
    sub = p.add_subparsers(dest="edit_command", required=True)

    move_parser = sub.add_parser("move", help="Move a labeled shape and reroute connected arrows")
    _add_common_io(move_parser)
    move_parser.add_argument("--label", required=True, help="Shape label to move")
    move_parser.add_argument("--dx", type=float, required=True, help="X delta")
    move_parser.add_argument("--dy", type=float, required=True, help="Y delta")
    move_parser.set_defaults(func=cmd_move)

    relabel_parser = sub.add_parser("relabel", help="Change label text")
    _add_common_io(relabel_parser)
    relabel_parser.add_argument("--label", required=True, help="Existing label")
    relabel_parser.add_argument("--text", required=True, help="New label text")
    relabel_parser.set_defaults(func=cmd_relabel)

    recolor_parser = sub.add_parser("recolor", help="Recolor a labeled shape")
    _add_common_io(recolor_parser)
    recolor_parser.add_argument("--label", required=True, help="Shape label")
    recolor_parser.add_argument("--stroke", help="Stroke color hex")
    recolor_parser.add_argument("--background", help="Background color hex or transparent")
    recolor_parser.set_defaults(func=cmd_recolor)

    delete_parser = sub.add_parser("delete", help="Delete a labeled shape/text and connected arrows")
    _add_common_io(delete_parser)
    delete_parser.add_argument("--label", required=True, help="Label to delete")
    delete_parser.set_defaults(func=cmd_delete)

    add_parser = sub.add_parser("add-box", help="Add a labeled rectangle")
    _add_common_io(add_parser)
    add_parser.add_argument("--label", required=True, help="Box label")
    add_parser.add_argument("--x", type=float, required=True)
    add_parser.add_argument("--y", type=float, required=True)
    add_parser.add_argument("--width", type=float, default=200)
    add_parser.add_argument("--height", type=float, default=80)
    add_parser.add_argument("--stroke", default="#1e1e1e")
    add_parser.add_argument("--background", default="transparent")
    add_parser.add_argument("--font-size", type=int, default=20)
    add_parser.add_argument("--font-family", type=int, default=1, choices=[1, 2, 3],
                            help="1=Virgil (hand-drawn), 2=Helvetica, 3=Cascadia (mono)")
    add_parser.add_argument("--dashed", action="store_true")
    add_parser.add_argument("--crisp", action="store_true", help="Use roughness=0")
    add_parser.set_defaults(func=cmd_add_box)

    connect_parser = sub.add_parser("connect", help="Connect two labeled shapes with an arrow")
    _add_common_io(connect_parser)
    connect_parser.add_argument("--from-label", required=True)
    connect_parser.add_argument("--to-label", required=True)
    connect_parser.add_argument("--from-edge", default="bottom", choices=["top", "bottom", "left", "right"])
    connect_parser.add_argument("--to-edge", default="top", choices=["top", "bottom", "left", "right"])
    connect_parser.add_argument("--stroke", default="#1e1e1e")
    connect_parser.add_argument("--elbowed", action="store_true")
    connect_parser.add_argument("--label", help="Optional arrow label")
    connect_parser.add_argument("--font-size", type=int, default=14)
    connect_parser.add_argument("--font-family", type=int, default=1, choices=[1, 2, 3],
                                help="1=Virgil (hand-drawn), 2=Helvetica, 3=Cascadia (mono)")
    connect_parser.set_defaults(func=cmd_connect)
