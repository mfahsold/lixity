"""Story and scene storyboard export to JSON Canvas 1.0 format."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .research.canvas import CanvasEdge, CanvasNode, JSONCanvas


def export_scenes_canvas(scenes_report: dict[str, Any]) -> JSONCanvas:
    """Generate a narrative storyboard canvas from scenes report."""
    canvas = JSONCanvas()
    items = scenes_report.get("items", [])
    if not items:
        return canvas

    x_gap = 40
    y_gap = 60
    node_width = 260
    node_height = 180

    prev_node_id: str | None = None

    # Group by chapter if available
    chapters: dict[int, list[dict[str, Any]]] = {}
    for item in items:
        chap_num = item.get("chapter", 1)
        chapters.setdefault(chap_num, []).append(item)

    for chap_num, chap_items in sorted(chapters.items()):
        row = chap_num - 1
        # Create chapter group node
        group_width = len(chap_items) * (node_width + x_gap) + 40
        group_node = CanvasNode(
            id=f"group-chapter-{chap_num}",
            type="group",
            x=20,
            y=row * (node_height + y_gap) + 20,
            width=group_width,
            height=node_height + 40,
            label=f"Chapter {chap_num}",
            color="6",  # Purple
        )
        canvas.nodes.append(group_node)

        for col, sc in enumerate(chap_items):
            sc_id = f"scene-{chap_num}-{sc.get('scene', col + 1)}"
            x = 40 + col * (node_width + x_gap)
            y = row * (node_height + y_gap) + 40

            words = sc.get("words", 0)
            dialog_pct = sc.get("dialog_pct", 0)
            status = sc.get("status", "")
            title = sc.get("title") or f"Scene {chap_num}:{sc.get('scene', col + 1)}"

            text_lines = [
                f"### {title}",
                f"**Words:** {words} | **Dialog:** {dialog_pct:.0f}%",
            ]
            if status:
                text_lines.append(f"**Status:** {status}")
            if sc.get("summary"):
                text_lines.append(f"\n{sc['summary']}")

            node = CanvasNode(
                id=sc_id,
                type="text",
                x=x,
                y=y,
                width=node_width,
                height=node_height - 20,
                text="\n".join(text_lines),
                color="2",  # Orange
            )
            canvas.nodes.append(node)

            # Sequential narrative edge
            if prev_node_id:
                edge = CanvasEdge(
                    id=f"flow-{prev_node_id}-{sc_id}-{uuid4().hex[:6]}",
                    fromNode=prev_node_id,
                    toNode=sc_id,
                    fromSide="right" if col > 0 else "bottom",
                    toSide="left" if col > 0 else "top",
                    label="",
                )
                canvas.edges.append(edge)

            prev_node_id = sc_id

    return canvas
