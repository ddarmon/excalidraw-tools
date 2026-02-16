#!/usr/bin/env python3
"""Utilities for deriving a compact diagram spec from Excalidraw JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from excalidraw_tools.lib import (
    active_elements,
    arrow_endpoints,
    build_id_index,
    infer_edge_by_proximity,
    infer_edge_from_fixed_point,
    load_diagram,
)

NODE_TYPES = {"rectangle", "ellipse", "diamond"}
DEFAULT_NODE_STROKE = "#1e1e1e"
DEFAULT_NODE_BACKGROUND = "transparent"
DEFAULT_EDGE_STROKE = "#1e1e1e"


def _normalize_number(value: float) -> int | float:
    if float(value).is_integer():
        return int(value)
    return float(value)


def default_spec_path(diagram_path: Path) -> Path:
    if diagram_path.suffix == ".excalidraw":
        return diagram_path.with_suffix(".spec.json")
    return Path(f"{diagram_path}.spec.json")


def resolve_spec_path(diagram_path: Path, value: Optional[str]) -> Optional[Path]:
    if value is None:
        return None
    if value == "AUTO":
        return default_spec_path(diagram_path)
    return Path(value)


def _load_existing_spec(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_bound_labels(elements: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    labels: Dict[str, Dict[str, Any]] = {}
    for elem in active_elements(elements):
        if elem.get("type") != "text":
            continue
        container_id = elem.get("containerId")
        if isinstance(container_id, str) and container_id:
            labels[container_id] = elem
    return labels


def _standalone_texts(elements: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for elem in active_elements(elements):
        if elem.get("type") != "text":
            continue
        if elem.get("containerId"):
            continue
        out.append(elem)
    return out


def _text_center(text: Dict[str, Any]) -> Tuple[float, float]:
    x = float(text.get("x", 0))
    y = float(text.get("y", 0))
    w = float(text.get("width", 0))
    h = float(text.get("height", 0))
    return x + w / 2, y + h / 2


def _extract_node(shape: Dict[str, Any], label: Optional[str]) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "id": str(shape["id"]),
        "type": str(shape["type"]),
        "x": _normalize_number(float(shape.get("x", 0))),
        "y": _normalize_number(float(shape.get("y", 0))),
        "width": _normalize_number(float(shape.get("width", 0))),
        "height": _normalize_number(float(shape.get("height", 0))),
    }

    stroke = str(shape.get("strokeColor", DEFAULT_NODE_STROKE))
    background = str(shape.get("backgroundColor", DEFAULT_NODE_BACKGROUND))
    if stroke != DEFAULT_NODE_STROKE:
        node["stroke"] = stroke
    if background != DEFAULT_NODE_BACKGROUND:
        node["background"] = background

    stroke_width = int(shape.get("strokeWidth", 2))
    stroke_style = str(shape.get("strokeStyle", "solid"))
    roughness = int(shape.get("roughness", 1))
    if stroke_width != 2:
        node["strokeWidth"] = stroke_width
    if stroke_style != "solid":
        node["strokeStyle"] = stroke_style
    if roughness != 1:
        node["roughness"] = roughness

    if label:
        node["label"] = label
    return node


def _infer_arrow_label(
    arrow: Dict[str, Any],
    standalone_texts: Sequence[Dict[str, Any]],
    used_ids: set[str],
    *,
    max_distance: float = 64.0,
) -> Optional[str]:
    start, end = arrow_endpoints(arrow)
    midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for text in standalone_texts:
        text_id = str(text.get("id", ""))
        if not text_id or text_id in used_ids:
            continue
        cx, cy = _text_center(text)
        dist = ((cx - midpoint[0]) ** 2 + (cy - midpoint[1]) ** 2) ** 0.5
        if dist > max_distance:
            continue
        if best is None or dist < best[0]:
            best = (dist, text)

    if best is None:
        return None

    _, text = best
    text_id = str(text.get("id", ""))
    if text_id:
        used_ids.add(text_id)
    label = str(text.get("text", "")).strip()
    return label or None


def _extract_edges(
    elements: Sequence[Dict[str, Any]],
    id_index: Dict[str, Dict[str, Any]],
    standalone_texts: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    edges: List[Dict[str, Any]] = []
    used_text_ids: set[str] = set()

    for elem in active_elements(elements):
        if elem.get("type") != "arrow":
            continue

        start_binding = elem.get("startBinding") or {}
        end_binding = elem.get("endBinding") or {}
        start_id = start_binding.get("elementId")
        end_id = end_binding.get("elementId")
        if start_id not in id_index or end_id not in id_index:
            continue

        source = id_index[start_id]
        target = id_index[end_id]
        if source.get("type") not in NODE_TYPES or target.get("type") not in NODE_TYPES:
            continue

        start_pt, end_pt = arrow_endpoints(elem)
        from_edge = infer_edge_from_fixed_point(start_binding) or infer_edge_by_proximity(source, start_pt)
        to_edge = infer_edge_from_fixed_point(end_binding) or infer_edge_by_proximity(target, end_pt)

        edge: Dict[str, Any] = {
            "from": str(start_id),
            "to": str(end_id),
            "fromEdge": from_edge,
            "toEdge": to_edge,
        }

        stroke = str(elem.get("strokeColor", DEFAULT_EDGE_STROKE))
        if stroke != DEFAULT_EDGE_STROKE:
            edge["stroke"] = stroke

        if bool(elem.get("elbowed")):
            edge["elbowed"] = True

        label = _infer_arrow_label(elem, standalone_texts, used_text_ids)
        if label:
            edge["label"] = label

        edges.append(edge)

    def edge_sort_key(edge: Dict[str, Any]) -> Tuple[float, float, float, float, str, str]:
        source = id_index[edge["from"]]
        target = id_index[edge["to"]]
        return (
            float(source.get("y", 0)),
            float(source.get("x", 0)),
            float(target.get("y", 0)),
            float(target.get("x", 0)),
            edge["from"],
            edge["to"],
        )

    edges.sort(key=edge_sort_key)
    return edges


def diagram_to_spec(data: Dict[str, Any], existing_spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    elements = data.get("elements", [])
    id_index = build_id_index(elements)
    labels = _find_bound_labels(elements)

    nodes: List[Dict[str, Any]] = []
    for elem in active_elements(elements):
        if elem.get("type") not in NODE_TYPES:
            continue
        label_elem = labels.get(str(elem.get("id")))
        label = None
        if label_elem:
            label = str(label_elem.get("text", "")).strip() or None
        nodes.append(_extract_node(elem, label))

    nodes.sort(key=lambda n: (float(n.get("y", 0)), float(n.get("x", 0)), n["id"]))

    standalone = _standalone_texts(elements)
    edges = _extract_edges(elements, id_index, standalone)

    spec: Dict[str, Any] = {
        "seed": int((existing_spec or {}).get("seed", 42)),
        "nodes": nodes,
        "edges": edges,
    }

    if existing_spec and "updated" in existing_spec:
        spec["updated"] = int(existing_spec["updated"])

    return spec


def write_spec(spec_path: Path, spec: Dict[str, Any]) -> None:
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
        f.write("\n")


def sync_spec_for_diagram(diagram_path: Path, spec_path: Optional[Path] = None) -> Path:
    path = spec_path or default_spec_path(diagram_path)
    data = load_diagram(diagram_path)
    existing = _load_existing_spec(path)
    spec = diagram_to_spec(data, existing)
    write_spec(path, spec)
    return path


def sync_spec_for_data(data: Dict[str, Any], spec_path: Path) -> Path:
    existing = _load_existing_spec(spec_path)
    spec = diagram_to_spec(data, existing)
    write_spec(spec_path, spec)
    return spec_path
