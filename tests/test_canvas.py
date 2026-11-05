"""Unit tests for JSON Canvas 1.0 export and import in Lixity."""

import json

from lixity.canvas import export_scenes_canvas
from lixity.research.canvas import (
    CanvasEdge,
    CanvasNode,
    JSONCanvas,
    import_research_canvas,
)


def test_json_canvas_schema_validation():
    canvas = JSONCanvas(
        nodes=[
            CanvasNode(id="n1", type="text", x=0, y=0, width=200, height=100, text="Hello Canvas", color="1"),
            CanvasNode(id="n2", type="group", x=220, y=0, width=300, height=200, label="Group A", color="6"),
        ],
        edges=[
            CanvasEdge(id="e1", fromNode="n1", toNode="n2", fromSide="right", toSide="left", label="links"),
        ],
    )
    raw = canvas.to_json()
    parsed = json.loads(raw)
    assert len(parsed["nodes"]) == 2
    assert len(parsed["edges"]) == 1
    assert parsed["nodes"][0]["id"] == "n1"
    assert parsed["nodes"][0]["type"] == "text"
    assert parsed["nodes"][0]["text"] == "Hello Canvas"
    assert parsed["edges"][0]["fromNode"] == "n1"
    assert parsed["edges"][0]["toNode"] == "n2"


def test_export_scenes_canvas():
    scenes_report = {
        "items": [
            {"chapter": 1, "scene": 1, "title": "Opening", "words": 850, "dialog_pct": 35.0, "status": "draft", "summary": "Arrival at harbour"},
            {"chapter": 1, "scene": 2, "title": "Confrontation", "words": 1200, "dialog_pct": 60.0, "status": "revised", "summary": "Meeting with supervisor"},
            {"chapter": 2, "scene": 1, "title": "The Warehouse", "words": 950, "dialog_pct": 20.0, "status": "final", "summary": "Exploring storage block 4"},
        ]
    }
    canvas = export_scenes_canvas(scenes_report)
    assert len(canvas.nodes) == 5  # 2 chapter groups + 3 scenes
    assert len(canvas.edges) == 2  # 2 narrative progression edges

    group_nodes = [n for n in canvas.nodes if n.type == "group"]
    text_nodes = [n for n in canvas.nodes if n.type == "text"]
    assert len(group_nodes) == 2
    assert len(text_nodes) == 3

    assert "Chapter 1" in (group_nodes[0].label or "")
    assert "Opening" in (text_nodes[0].text or "")
    assert "850" in (text_nodes[0].text or "")


def test_import_research_canvas():
    sample_canvas = {
        "nodes": [
            {"id": "node-1", "type": "text", "x": 0, "y": 0, "width": 250, "height": 150, "text": "### Harbour Crane 1900\nHistorical crane specifications and coal usage."},
            {"id": "node-2", "type": "text", "x": 300, "y": 0, "width": 250, "height": 150, "text": "### Dock Strike\nStarted November 1896."},
            {"id": "node-3", "type": "file", "x": 0, "y": 200, "width": 250, "height": 150, "file": "notes/speicherstadt.md"},
        ],
        "edges": [
            {"id": "e1", "fromNode": "node-1", "toNode": "node-2", "label": "context"},
        ],
    }
    candidates = import_research_canvas(sample_canvas)
    assert len(candidates) == 3
    assert candidates[0]["title"] == "Harbour Crane 1900"
    assert "coal usage" in candidates[0]["body"]
    assert "node-2" in candidates[0]["connected_node_ids"]
    assert candidates[1]["title"] == "Dock Strike"
    assert candidates[2]["node_type"] == "file"
    assert candidates[2]["file"] == "notes/speicherstadt.md"
