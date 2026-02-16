#!/usr/bin/env python3
"""Shared helpers for creating and editing Excalidraw JSON files."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

INDEX_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

DEFAULT_APP_STATE = {
    "gridSize": 20,
    "gridStep": 5,
    "gridModeEnabled": False,
    "viewBackgroundColor": "#ffffff",
}

BASE_REQUIRED_FIELDS = {
    "id",
    "type",
    "x",
    "y",
    "width",
    "height",
    "angle",
    "strokeColor",
    "backgroundColor",
    "fillStyle",
    "strokeWidth",
    "strokeStyle",
    "roughness",
    "opacity",
    "groupIds",
    "frameId",
    "index",
    "roundness",
    "seed",
    "version",
    "versionNonce",
    "isDeleted",
    "boundElements",
    "updated",
    "link",
    "locked",
}

TEXT_REQUIRED_FIELDS = {
    "text",
    "fontSize",
    "fontFamily",
    "textAlign",
    "verticalAlign",
    "containerId",
    "originalText",
    "autoResize",
}

ARROW_REQUIRED_FIELDS = {
    "points",
    "startBinding",
    "endBinding",
    "startArrowhead",
    "endArrowhead",
    "elbowed",
}

ROUNDNESS_BY_TYPE = {
    "rectangle": {"type": 3},
    "ellipse": {"type": 2},
    "diamond": {"type": 2},
    "text": None,
    "line": {"type": 2},
}

EDGE_TO_FIXED_POINT = {
    "top": [0.5, 0],
    "bottom": [0.5, 1],
    "left": [0, 0.5],
    "right": [1, 0.5],
}

FIXED_POINT_TO_EDGE = {
    (0.5, 0): "top",
    (0.5, 1): "bottom",
    (0, 0.5): "left",
    (1, 0.5): "right",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def index_for_rank(rank: int) -> str:
    if rank < 0:
        raise ValueError("rank must be non-negative")
    if rank < len(INDEX_CHARS):
        return f"a{INDEX_CHARS[rank]}"

    n = rank
    out: List[str] = []
    while n:
        n, rem = divmod(n, len(INDEX_CHARS))
        out.append(INDEX_CHARS[rem])
    return "b" + "".join(reversed(out))


class IdFactory:
    """Generate deterministic ids, indexes, and version nonces."""

    def __init__(
        self,
        seed: Optional[int] = None,
        start_index: int = 0,
        existing_ids: Optional[Iterable[str]] = None,
    ) -> None:
        seed_value = seed if seed is not None else now_ms()
        self._rng = random.Random(seed_value)
        self._next_rank = start_index
        self._ids = set(existing_ids or [])

    def next_index(self) -> str:
        value = index_for_rank(self._next_rank)
        self._next_rank += 1
        return value

    def nonce(self) -> int:
        return self._rng.randint(1, (2**31) - 1)

    def random_id(self, prefix: str = "el") -> str:
        while True:
            suffix = "".join(self._rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(12))
            value = f"{prefix}-{suffix}"
            if value not in self._ids:
                self._ids.add(value)
                return value

    def reserve_id(self, value: str) -> None:
        if value in self._ids:
            raise ValueError(f"duplicate element id: {value}")
        self._ids.add(value)


def new_document(elements: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements or [],
        "appState": dict(DEFAULT_APP_STATE),
        "files": {},
    }


def load_diagram(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_diagram(path: str | Path, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def touch(element: Dict[str, Any], factory: Optional[IdFactory] = None, ts: Optional[int] = None) -> None:
    element["updated"] = ts if ts is not None else now_ms()
    element["version"] = int(element.get("version", 1)) + 1
    if factory is None:
        element["versionNonce"] = random.randint(1, (2**31) - 1)
    else:
        element["versionNonce"] = factory.nonce()


def normalize_bound_elements(element: Dict[str, Any]) -> List[Dict[str, str]]:
    bound = element.get("boundElements")
    if bound is None:
        bound = []
        element["boundElements"] = bound
    return bound


def make_shape(
    elements: List[Dict[str, Any]],
    ids: IdFactory,
    etype: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    stroke: str = "#1e1e1e",
    background: str = "transparent",
    stroke_width: int = 2,
    stroke_style: str = "solid",
    roughness: int = 1,
    element_id: Optional[str] = None,
) -> Dict[str, Any]:
    if etype == "arrow":
        roundness = {"type": 2}
    else:
        roundness = ROUNDNESS_BY_TYPE.get(etype)

    if element_id is not None:
        ids.reserve_id(element_id)

    elem = {
        "id": element_id if element_id is not None else ids.random_id(),
        "type": etype,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": background,
        "fillStyle": "solid",
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "roughness": roughness,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "index": ids.next_index(),
        "roundness": roundness,
        "seed": ids.nonce(),
        "version": 1,
        "versionNonce": ids.nonce(),
        "isDeleted": False,
        "boundElements": [],
        "updated": now_ms(),
        "link": None,
        "locked": False,
    }
    elements.append(elem)
    return elem


def make_text(
    elements: List[Dict[str, Any]],
    ids: IdFactory,
    content: str,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    container_id: Optional[str] = None,
    font_size: int = 20,
    font_family: int = 1,
    stroke: str = "#1e1e1e",
) -> Dict[str, Any]:
    text = make_shape(
        elements,
        ids,
        "text",
        x,
        y,
        width,
        height,
        stroke=stroke,
        background="transparent",
    )
    text["roundness"] = None
    text.update(
        {
            "text": content,
            "fontSize": font_size,
            "fontFamily": font_family,
            "textAlign": "center",
            "verticalAlign": "middle" if container_id else "top",
            "containerId": container_id,
            "originalText": content,
            "autoResize": True,
        }
    )
    return text


def add_label(
    elements: List[Dict[str, Any]],
    ids: IdFactory,
    shape: Dict[str, Any],
    label: str,
    *,
    font_size: int = 20,
    font_family: int = 1,
    text_height: int = 25,
) -> Dict[str, Any]:
    text_width = shape["width"] - 10
    text_x = shape["x"] + 5
    text_y = shape["y"] + (shape["height"] - text_height) / 2
    text = make_text(
        elements,
        ids,
        label,
        text_x,
        text_y,
        text_width,
        text_height,
        container_id=shape["id"],
        font_size=font_size,
        font_family=font_family,
        stroke=shape.get("strokeColor", "#1e1e1e"),
    )
    normalize_bound_elements(shape).append({"id": text["id"], "type": "text"})
    return text


def edge_point(shape: Dict[str, Any], edge: str) -> Tuple[float, float]:
    x = float(shape["x"])
    y = float(shape["y"])
    width = float(shape["width"])
    height = float(shape["height"])

    if edge == "top":
        return x + width / 2, y
    if edge == "bottom":
        return x + width / 2, y + height
    if edge == "left":
        return x, y + height / 2
    if edge == "right":
        return x + width, y + height / 2
    raise ValueError(f"unsupported edge: {edge}")


def route_points(source_edge: str, target_edge: str, dx: float, dy: float) -> List[List[float]]:
    if source_edge == "bottom" and target_edge == "top":
        return [[0, 0], [0, dy]] if abs(dx) < 10 else [[0, 0], [dx, 0], [dx, dy]]
    if source_edge == "right" and target_edge == "left":
        return [[0, 0], [dx, 0]] if abs(dy) < 10 else [[0, 0], [0, dy], [dx, dy]]
    if source_edge == "right" and target_edge == "top":
        return [[0, 0], [dx, 0], [dx, dy]]
    if source_edge == "left" and target_edge == "right":
        return [[0, 0], [dx, 0]] if abs(dy) < 10 else [[0, 0], [0, dy], [dx, dy]]
    return [[0, 0], [dx, dy]]


def recalc_arrow_bounds(arrow: Dict[str, Any]) -> None:
    points = arrow.get("points") or [[0, 0]]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    arrow["width"] = max(abs(min(xs)), abs(max(xs)))
    arrow["height"] = max(abs(min(ys)), abs(max(ys)))


def make_arrow(
    elements: List[Dict[str, Any]],
    ids: IdFactory,
    x: float,
    y: float,
    points: Sequence[Sequence[float]],
    *,
    start_id: Optional[str] = None,
    end_id: Optional[str] = None,
    stroke: str = "#1e1e1e",
    stroke_width: int = 2,
    elbowed: bool = False,
    source_edge: Optional[str] = None,
    target_edge: Optional[str] = None,
) -> Dict[str, Any]:
    arrow = make_shape(
        elements,
        ids,
        "arrow",
        x,
        y,
        0,
        0,
        stroke=stroke,
        stroke_width=stroke_width,
        roughness=0 if elbowed else 1,
    )
    arrow["roundness"] = None if elbowed else {"type": 2}

    point_list = [[float(px), float(py)] for px, py in points]
    arrow["points"] = point_list
    recalc_arrow_bounds(arrow)

    start_binding = None
    end_binding = None
    if start_id:
        start_binding = {"elementId": start_id, "focus": 0, "gap": 1, "fixedPoint": None}
        if source_edge:
            start_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[source_edge]
    if end_id:
        end_binding = {"elementId": end_id, "focus": 0, "gap": 1, "fixedPoint": None}
        if target_edge:
            end_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[target_edge]

    arrow.update(
        {
            "startBinding": start_binding,
            "endBinding": end_binding,
            "startArrowhead": None,
            "endArrowhead": "arrow",
            "elbowed": elbowed,
        }
    )
    return arrow


def connect(
    elements: List[Dict[str, Any]],
    ids: IdFactory,
    source: Dict[str, Any],
    target: Dict[str, Any],
    *,
    source_edge: str = "bottom",
    target_edge: str = "top",
    stroke: str = "#1e1e1e",
    elbowed: bool = False,
) -> Dict[str, Any]:
    sx, sy = edge_point(source, source_edge)
    tx, ty = edge_point(target, target_edge)
    dx = tx - sx
    dy = ty - sy
    points = route_points(source_edge, target_edge, dx, dy)

    arrow = make_arrow(
        elements,
        ids,
        sx,
        sy,
        points,
        start_id=source["id"],
        end_id=target["id"],
        stroke=stroke,
        elbowed=elbowed,
        source_edge=source_edge,
        target_edge=target_edge,
    )

    normalize_bound_elements(source).append({"id": arrow["id"], "type": "arrow"})
    normalize_bound_elements(target).append({"id": arrow["id"], "type": "arrow"})
    return arrow


def active_elements(elements: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [elem for elem in elements if not elem.get("isDeleted")]


def build_id_index(elements: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {elem["id"]: elem for elem in elements if isinstance(elem, dict) and "id" in elem}


def find_by_label(elements: Sequence[Dict[str, Any]], label: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    label_norm = label.lower()
    id_index = build_id_index(elements)

    for elem in active_elements(elements):
        if elem.get("type") != "text":
            continue
        text = str(elem.get("text", ""))
        if label_norm not in text.lower():
            continue
        container_id = elem.get("containerId")
        if container_id:
            return id_index.get(container_id), elem
        return None, elem

    return None, None


def text_for_container(elements: Sequence[Dict[str, Any]], container_id: str) -> Optional[Dict[str, Any]]:
    for elem in active_elements(elements):
        if elem.get("type") == "text" and elem.get("containerId") == container_id:
            return elem
    return None


def arrow_endpoints(arrow: Dict[str, Any]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    x = float(arrow.get("x", 0))
    y = float(arrow.get("y", 0))
    points = arrow.get("points") or [[0, 0], [0, 0]]
    end = points[-1]
    return (x, y), (x + float(end[0]), y + float(end[1]))


def infer_edge_from_fixed_point(binding: Dict[str, Any]) -> Optional[str]:
    fp = binding.get("fixedPoint")
    if not isinstance(fp, (list, tuple)) or len(fp) != 2:
        return None
    key = (float(fp[0]), float(fp[1]))
    return FIXED_POINT_TO_EDGE.get(key)


def infer_edge_by_proximity(shape: Dict[str, Any], point: Tuple[float, float]) -> str:
    px, py = point
    distances = []
    for edge in ("top", "bottom", "left", "right"):
        ex, ey = edge_point(shape, edge)
        distances.append((abs(px - ex) + abs(py - ey), edge))
    distances.sort(key=lambda item: item[0])
    return distances[0][1]


def reroute_arrow(arrow: Dict[str, Any], id_index: Dict[str, Dict[str, Any]]) -> bool:
    start_binding = arrow.get("startBinding") or {}
    end_binding = arrow.get("endBinding") or {}

    source = id_index.get(start_binding.get("elementId"))
    target = id_index.get(end_binding.get("elementId"))

    if source and source.get("isDeleted"):
        source = None
    if target and target.get("isDeleted"):
        target = None

    start_pt, end_pt = arrow_endpoints(arrow)

    if source and target:
        source_edge = infer_edge_from_fixed_point(start_binding) or infer_edge_by_proximity(source, start_pt)
        target_edge = infer_edge_from_fixed_point(end_binding) or infer_edge_by_proximity(target, end_pt)

        sx, sy = edge_point(source, source_edge)
        tx, ty = edge_point(target, target_edge)
        dx = tx - sx
        dy = ty - sy

        arrow["x"] = sx
        arrow["y"] = sy
        arrow["points"] = route_points(source_edge, target_edge, dx, dy)
        if source_edge in EDGE_TO_FIXED_POINT:
            start_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[source_edge]
        if target_edge in EDGE_TO_FIXED_POINT:
            end_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[target_edge]
        recalc_arrow_bounds(arrow)
        return True

    if source:
        source_edge = infer_edge_from_fixed_point(start_binding) or infer_edge_by_proximity(source, start_pt)
        sx, sy = edge_point(source, source_edge)
        arrow["x"] = sx
        arrow["y"] = sy
        if source_edge in EDGE_TO_FIXED_POINT:
            start_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[source_edge]
        recalc_arrow_bounds(arrow)
        return True

    if target:
        target_edge = infer_edge_from_fixed_point(end_binding) or infer_edge_by_proximity(target, end_pt)
        tx, ty = edge_point(target, target_edge)
        points = arrow.get("points")
        if not isinstance(points, list) or len(points) < 2:
            points = [[0, 0], [tx - arrow.get("x", 0), ty - arrow.get("y", 0)]]
            arrow["points"] = points
        else:
            points[-1] = [tx - arrow.get("x", 0), ty - arrow.get("y", 0)]
        if target_edge in EDGE_TO_FIXED_POINT:
            end_binding["fixedPoint"] = EDGE_TO_FIXED_POINT[target_edge]
        recalc_arrow_bounds(arrow)
        return True

    return False


def move_shape_and_dependents(
    data: Dict[str, Any],
    shape: Dict[str, Any],
    dx: float,
    dy: float,
    ids: Optional[IdFactory] = None,
) -> None:
    elements = data.get("elements", [])
    id_index = build_id_index(elements)
    moved_arrow_ids = set()

    shape["x"] = float(shape.get("x", 0)) + dx
    shape["y"] = float(shape.get("y", 0)) + dy
    touch(shape, ids)

    label = text_for_container(elements, shape["id"])
    if label:
        label["x"] = float(label.get("x", 0)) + dx
        label["y"] = float(label.get("y", 0)) + dy
        touch(label, ids)

    for arrow in active_elements(elements):
        if arrow.get("type") != "arrow":
            continue

        start_binding = arrow.get("startBinding") or {}
        end_binding = arrow.get("endBinding") or {}
        start_match = start_binding.get("elementId") == shape.get("id")
        end_match = end_binding.get("elementId") == shape.get("id")

        if start_match or end_match:
            if reroute_arrow(arrow, id_index):
                touch(arrow, ids)
                moved_arrow_ids.add(arrow["id"])

    for item in shape.get("boundElements") or []:
        if item.get("type") != "arrow":
            continue
        arrow = id_index.get(item.get("id"))
        if not arrow or arrow.get("id") in moved_arrow_ids or arrow.get("isDeleted"):
            continue
        arrow["x"] = float(arrow.get("x", 0)) + dx
        arrow["y"] = float(arrow.get("y", 0)) + dy
        touch(arrow, ids)
