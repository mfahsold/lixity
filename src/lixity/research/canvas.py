"""JSON Canvas 1.0 interchange for Lixity research knowledge and dossiers.

Conforms to the open JSON Canvas 1.0 specification (https://jsoncanvas.org/spec/1.0/).
Exports research dossiers, claims, and relations into visual boards for Obsidian
and other canvas-compatible tools, and imports canvas nodes as research candidates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .models import Claim, ClaimRelation, Decision, Dossier
from .repository import Snapshot

CanvasNodeType = Literal["text", "file", "link", "group"]
CanvasSide = Literal["top", "right", "bottom", "left"]
CanvasEnd = Literal["none", "arrow"]


class CanvasNode(BaseModel):
    id: str
    type: CanvasNodeType
    x: int
    y: int
    width: int
    height: int
    color: str | None = None
    # Type-specific attributes
    text: str | None = None
    file: str | None = None
    subpath: str | None = None
    url: str | None = None
    label: str | None = None


class CanvasEdge(BaseModel):
    id: str
    fromNode: str
    toNode: str
    fromSide: CanvasSide | None = None
    toSide: CanvasSide | None = None
    fromEnd: CanvasEnd | None = None
    toEnd: CanvasEnd | None = "arrow"
    color: str | None = None
    label: str | None = None


class JSONCanvas(BaseModel):
    nodes: list[CanvasNode] = Field(default_factory=list)
    edges: list[CanvasEdge] = Field(default_factory=list)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.model_dump(exclude_none=True), indent=indent, ensure_ascii=False)


def export_research_canvas(snapshot: Snapshot) -> JSONCanvas:
    """Generate a standard JSON Canvas from a research snapshot."""
    canvas = JSONCanvas()

    # Collect entities
    dossiers = [r for r in snapshot.records.values() if isinstance(r, Dossier)]
    claims = [r for r in snapshot.records.values() if isinstance(r, Claim)]
    relations = [r for r in snapshot.records.values() if isinstance(r, ClaimRelation)]
    decisions = [r for r in snapshot.records.values() if isinstance(r, Decision)]

    col_width = 340
    row_height = 220
    x_gap = 60
    y_gap = 50

    dossier_coords: dict[str, tuple[int, int]] = {}

    # Layout dossiers in columns (up to 3 per column)
    for idx, d in enumerate(dossiers):
        col = idx // 4
        row = idx % 4
        x = col * (col_width + x_gap)
        y = row * (row_height + y_gap)
        dossier_coords[d.id] = (x, y)

        tags_line = f"🏷️ {', '.join(d.tags)}" if d.tags else ""
        body_preview = d.body[:140] + "…" if len(d.body) > 140 else d.body
        content = f"### {d.title}\n\n{tags_line}\n\n{body_preview}".strip()

        node = CanvasNode(
            id=d.id,
            type="text",
            x=x,
            y=y,
            width=col_width,
            height=row_height,
            text=content,
            color="1",  # Red/Coral in standard canvas color palette
        )
        canvas.nodes.append(node)

    # Place claims adjacent to their primary dossier or in a dedicated section
    claim_coords: dict[str, tuple[int, int]] = {}
    claim_x_start = (len(dossiers) // 4 + 1) * (col_width + x_gap) + 40

    for idx, c in enumerate(claims):
        col = idx // 5
        row = idx % 5
        cx = claim_x_start + col * (280 + x_gap)
        cy = row * (160 + y_gap)
        claim_coords[c.id] = (cx, cy)

        claim_text = c.statement[:160] + "…" if len(c.statement) > 160 else c.statement
        content = f"**Claim: {c.title}**\n\n{claim_text}".strip()
        node = CanvasNode(
            id=c.id,
            type="text",
            x=cx,
            y=cy,
            width=280,
            height=150,
            text=content,
            color="4",  # Green
        )
        canvas.nodes.append(node)

        # Edge from dossier to claim if pinned
        dossier_id = c.dossier_ref.id if c.dossier_ref else None
        if dossier_id and dossier_id in dossier_coords:
            edge = CanvasEdge(
                id=f"edge-{dossier_id}-{c.id}-{uuid4().hex[:6]}",
                fromNode=dossier_id,
                toNode=c.id,
                fromSide="right",
                toSide="left",
                label="asserts",
            )
            canvas.edges.append(edge)

    # Claim relations as edges
    for rel in relations:
        from_id = rel.from_claim_ref.id
        to_id = rel.to_claim_ref.id
        if from_id in claim_coords and to_id in claim_coords:
            edge = CanvasEdge(
                id=f"rel-{rel.id}",
                fromNode=from_id,
                toNode=to_id,
                fromSide="bottom",
                toSide="top",
                label=rel.relation,
                color="3",  # Yellow
            )
            canvas.edges.append(edge)

    # Decisions
    decision_y_start = max((row * (row_height + y_gap) for row in range(5)), default=0) + 260
    for idx, dec in enumerate(decisions):
        dx = idx * (300 + x_gap)
        dy = decision_y_start
        content = f"**Decision: {dec.title}**\n\n{dec.rationale or ''}".strip()
        node = CanvasNode(
            id=dec.id,
            type="text",
            x=dx,
            y=dy,
            width=300,
            height=160,
            text=content,
            color="5",  # Cyan/Blue
        )
        canvas.nodes.append(node)

        for d_ref in dec.dossier_refs:
            if d_ref.id in dossier_coords:
                canvas.edges.append(
                    CanvasEdge(
                        id=f"dec-edge-{dec.id}-{d_ref.id}-{uuid4().hex[:6]}",
                        fromNode=dec.id,
                        toNode=d_ref.id,
                        fromSide="top",
                        toSide="bottom",
                        label="implements",
                    )
                )

    return canvas


def import_research_canvas(canvas_data: dict[str, Any] | str | Path) -> list[dict[str, Any]]:
    """Parse a .canvas file and extract candidate dossier notes with their links."""
    if isinstance(canvas_data, (str, Path)) and Path(canvas_data).is_file():
        raw = Path(canvas_data).read_text(encoding="utf-8")
        data = json.loads(raw)
    elif isinstance(canvas_data, str):
        data = json.loads(canvas_data)
    else:
        data = canvas_data

    canvas = JSONCanvas.model_validate(data)
    candidates: list[dict[str, Any]] = []

    # Map edges by node id
    connections: dict[str, list[str]] = {}
    for edge in canvas.edges:
        connections.setdefault(edge.fromNode, []).append(edge.toNode)
        connections.setdefault(edge.toNode, []).append(edge.fromNode)

    for node in canvas.nodes:
        if node.type not in ("text", "file"):
            continue
        text = node.text or ""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        title = lines[0].lstrip("#").strip() if lines else (node.file or f"Canvas note {node.id}")
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text

        candidate = {
            "canvas_node_id": node.id,
            "title": title,
            "body": body,
            "node_type": node.type,
            "file": node.file,
            "connected_node_ids": connections.get(node.id, []),
        }
        candidates.append(candidate)

    return candidates
