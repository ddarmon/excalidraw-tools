#!/usr/bin/env python3
"""Validate Excalidraw JSON files for schema and linkage consistency."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from excalidraw_tools.lib import (
    ARROW_REQUIRED_FIELDS,
    BASE_REQUIRED_FIELDS,
    ROUNDNESS_BY_TYPE,
    TEXT_REQUIRED_FIELDS,
)

ROOT_REQUIRED_FIELDS = {"type", "version", "source", "elements", "appState", "files"}
SUPPORTED_TYPES = {"rectangle", "ellipse", "diamond", "arrow", "line", "text", "freedraw"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_point(point: Any) -> bool:
    return (
        isinstance(point, list)
        and len(point) == 2
        and _is_number(point[0])
        and _is_number(point[1])
    )


def _bound_contains(parent: Dict[str, Any], child_id: str, child_type: str) -> bool:
    bound = parent.get("boundElements")
    if not isinstance(bound, list):
        return False
    for item in bound:
        if not isinstance(item, dict):
            continue
        if item.get("id") == child_id and item.get("type") == child_type:
            return True
    return False


def validate_document(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    missing_root = sorted(ROOT_REQUIRED_FIELDS - set(data.keys()))
    if missing_root:
        errors.append(f"missing root keys: {', '.join(missing_root)}")

    if data.get("type") != "excalidraw":
        errors.append("root.type must be 'excalidraw'")

    elements = data.get("elements")
    if not isinstance(elements, list):
        errors.append("root.elements must be a list")
        return errors

    ids: List[str] = []
    id_index: Dict[str, Dict[str, Any]] = {}

    for idx, elem in enumerate(elements):
        prefix = f"elements[{idx}]"
        if not isinstance(elem, dict):
            errors.append(f"{prefix} must be an object")
            continue

        elem_id = elem.get("id")
        if not isinstance(elem_id, str) or not elem_id:
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            ids.append(elem_id)
            id_index[elem_id] = elem

        missing = sorted(BASE_REQUIRED_FIELDS - set(elem.keys()))
        if missing:
            errors.append(f"{prefix} missing base keys: {', '.join(missing)}")

        elem_type = elem.get("type")
        if elem_type not in SUPPORTED_TYPES:
            errors.append(f"{prefix}.type unsupported: {elem_type}")

        if elem_type in ROUNDNESS_BY_TYPE and "roundness" in elem:
            expected = ROUNDNESS_BY_TYPE[elem_type]
            if expected is None:
                if elem["roundness"] is not None:
                    errors.append(f"{prefix}.roundness should be null for {elem_type}")
            elif elem["roundness"] != expected:
                errors.append(f"{prefix}.roundness should be {expected} for {elem_type}")

        bound = elem.get("boundElements")
        if bound is not None and not isinstance(bound, list):
            errors.append(f"{prefix}.boundElements must be list or null")

    duplicates = sorted({eid for eid in ids if ids.count(eid) > 1})
    if duplicates:
        errors.append(f"duplicate element ids: {', '.join(duplicates)}")

    for idx, elem in enumerate(elements):
        if not isinstance(elem, dict):
            continue
        prefix = f"elements[{idx}] ({elem.get('id', 'unknown')})"
        elem_type = elem.get("type")

        if elem_type == "text":
            missing = sorted(TEXT_REQUIRED_FIELDS - set(elem.keys()))
            if missing:
                errors.append(f"{prefix} missing text keys: {', '.join(missing)}")

            container_id = elem.get("containerId")
            if container_id:
                parent = id_index.get(container_id)
                if parent is None:
                    errors.append(f"{prefix}.containerId references missing element: {container_id}")
                elif not _bound_contains(parent, elem.get("id"), "text"):
                    errors.append(
                        f"{prefix} container {container_id} does not reference this text in boundElements"
                    )

        if elem_type == "arrow":
            missing = sorted(ARROW_REQUIRED_FIELDS - set(elem.keys()))
            if missing:
                errors.append(f"{prefix} missing arrow keys: {', '.join(missing)}")

            points = elem.get("points")
            if not isinstance(points, list) or len(points) < 2:
                errors.append(f"{prefix}.points must contain at least two points")
            elif any(not _validate_point(p) for p in points):
                errors.append(f"{prefix}.points must be [x, y] number pairs")

            for binding_key in ("startBinding", "endBinding"):
                binding = elem.get(binding_key)
                if binding is None:
                    continue
                if not isinstance(binding, dict):
                    errors.append(f"{prefix}.{binding_key} must be object or null")
                    continue
                target_id = binding.get("elementId")
                if not isinstance(target_id, str) or not target_id:
                    errors.append(f"{prefix}.{binding_key}.elementId must be a non-empty string")
                elif target_id not in id_index:
                    errors.append(f"{prefix}.{binding_key} references missing element: {target_id}")

            for binding_key, side in (("startBinding", "start"), ("endBinding", "end")):
                binding = elem.get(binding_key)
                if not isinstance(binding, dict):
                    continue
                target_id = binding.get("elementId")
                parent = id_index.get(target_id)
                if parent is None:
                    continue
                if not _bound_contains(parent, elem.get("id"), "arrow"):
                    errors.append(
                        f"{prefix} {side} target {target_id} does not reference this arrow in boundElements"
                    )

    return errors


def validate_file(path: Path) -> Tuple[bool, List[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"{path}: failed to parse JSON: {exc}"]

    errors = validate_document(data)
    if errors:
        return False, [f"{path}: {err}" for err in errors]
    return True, [f"{path}: OK"]


def _run(args: argparse.Namespace) -> int:
    all_errors: List[str] = []
    for path in args.files:
        ok, messages = validate_file(path)
        if ok:
            print(messages[0])
        else:
            all_errors.extend(messages)

    if all_errors:
        for message in all_errors:
            print(message, file=sys.stderr)
        return 1
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("validate", help="Validate .excalidraw JSON files")
    p.add_argument("files", nargs="+", type=Path, help=".excalidraw JSON file(s) to validate")
    p.set_defaults(func=_run)
