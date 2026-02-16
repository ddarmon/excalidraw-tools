#!/usr/bin/env python3
"""Render an approximate preview image from a .excalidraw JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence


def _draw_arrow(ax: Any, elem: Dict[str, Any], stroke: str, line_width: float, linestyle: str) -> None:
    points = elem.get("points") or []
    if len(points) < 2:
        return

    x = float(elem.get("x", 0))
    y = float(elem.get("y", 0))
    xs = [x + float(p[0]) for p in points]
    ys = [y + float(p[1]) for p in points]

    for idx in range(len(xs) - 1):
        if idx == len(xs) - 2:
            ax.annotate(
                "",
                xy=(xs[idx + 1], ys[idx + 1]),
                xytext=(xs[idx], ys[idx]),
                arrowprops={"arrowstyle": "->", "color": stroke, "lw": line_width},
            )
        else:
            ax.plot(
                [xs[idx], xs[idx + 1]],
                [ys[idx], ys[idx + 1]],
                color=stroke,
                linewidth=line_width,
                linestyle=linestyle,
            )


def render(in_path: Path, out_path: Path, dpi: int = 150) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.patches as patches
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            f"matplotlib is required for preview rendering: {exc}\n"
            "Install with: pip install excalidraw-tools[preview]"
        ) from exc

    data = json.loads(in_path.read_text(encoding="utf-8"))
    elements = data.get("elements", [])

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    def include(px: float, py: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, px)
        min_y = min(min_y, py)
        max_x = max(max_x, px)
        max_y = max(max_y, py)

    for elem in elements:
        if not isinstance(elem, dict) or elem.get("isDeleted"):
            continue

        etype = elem.get("type")
        x = float(elem.get("x", 0))
        y = float(elem.get("y", 0))
        width = float(elem.get("width", 0))
        height = float(elem.get("height", 0))

        background = elem.get("backgroundColor", "none")
        stroke = elem.get("strokeColor", "#1e1e1e")
        style = elem.get("strokeStyle", "solid")
        line_width = float(elem.get("strokeWidth", 2))
        linestyle = "--" if style == "dashed" else "-"
        face_color = background if background != "transparent" else "none"

        if etype == "rectangle":
            include(x, y)
            include(x + width, y + height)
            rect = patches.FancyBboxPatch(
                (x, y),
                width,
                height,
                boxstyle="round,pad=0,rounding_size=6",
                linewidth=line_width,
                edgecolor=stroke,
                facecolor=face_color,
                linestyle=linestyle,
            )
            ax.add_patch(rect)
        elif etype == "ellipse":
            include(x, y)
            include(x + width, y + height)
            ell = patches.Ellipse(
                (x + width / 2, y + height / 2),
                width,
                height,
                linewidth=line_width,
                edgecolor=stroke,
                facecolor=face_color,
                linestyle=linestyle,
            )
            ax.add_patch(ell)
        elif etype == "diamond":
            include(x, y)
            include(x + width, y + height)
            cx, cy = x + width / 2, y + height / 2
            poly = patches.Polygon(
                [(cx, y), (x + width, cy), (cx, y + height), (x, cy)],
                closed=True,
                linewidth=line_width,
                edgecolor=stroke,
                facecolor=face_color,
                linestyle=linestyle,
            )
            ax.add_patch(poly)
        elif etype == "arrow":
            arrow_points = elem.get("points") or []
            for point in arrow_points:
                if isinstance(point, list) and len(point) == 2:
                    include(x + float(point[0]), y + float(point[1]))
            _draw_arrow(ax, elem, stroke, line_width, linestyle)
        elif etype == "line":
            line_points = elem.get("points") or []
            if len(line_points) >= 2:
                xs = [x + float(p[0]) for p in line_points]
                ys = [y + float(p[1]) for p in line_points]
                for px, py in zip(xs, ys):
                    include(px, py)
                ax.plot(xs, ys, color=stroke, linewidth=line_width, linestyle=linestyle)
        elif etype == "freedraw":
            fd_points = elem.get("points") or []
            if len(fd_points) >= 2:
                xs = [x + float(p[0]) for p in fd_points]
                ys = [y + float(p[1]) for p in fd_points]
                for px, py in zip(xs, ys):
                    include(px, py)
                ax.plot(xs, ys, color=stroke, linewidth=max(1, line_width * 0.75))
        elif etype == "text":
            include(x, y)
            include(x + width, y + height)
            font_size = float(elem.get("fontSize", 16))
            text = str(elem.get("text", ""))
            ax.text(
                x + width / 2,
                y + height / 2,
                text,
                ha="center",
                va="center",
                fontsize=font_size * 0.7,
                fontfamily="sans-serif",
                color=stroke,
            )

    if min_x != float("inf") and min_y != float("inf"):
        padding = 40
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)

    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.axis("off")
    plt.tight_layout()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(out_path), dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"Saved preview to {out_path}")


def _run(args: argparse.Namespace) -> int:
    render(args.input, args.output, args.dpi)
    return 0


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("preview", help="Render approximate PNG preview (matplotlib)")
    p.add_argument("input", type=Path, help="Input .excalidraw file")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/excalidraw_preview.png"),
        help="Output image path (default: /tmp/excalidraw_preview.png)",
    )
    p.add_argument("--dpi", type=int, default=150, help="Output DPI")
    p.set_defaults(func=_run)
