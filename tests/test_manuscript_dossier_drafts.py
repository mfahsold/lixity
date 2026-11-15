"""Tests for deterministic manuscript-driven dossier drafts and direct timeline tab."""

from __future__ import annotations

import json
from pathlib import Path

from lixity.cli import main as lixity_cli_main
from lixity.mcp import _TOOLS, handle_message
from lixity.research import api as research_api
from lixity.research.manuscript_drafts import DRAFT_SCHEMA, extract_manuscript_dossier_drafts
from lixity.ui.research_panel import render_research_panel
from lixity.workspace_labels import WORKSPACE_LABELS

SAMPLE_MANUSCRIPT = """# Dolomiten Test

## Chapter 1: Arrival in Bozen

The conductor handed Matteo a folded ticket in the cold morning fog.

At the gate, someone called out to Matteo from the platform.

"Are you certain?" Chiara asked, watching Matteo closely.

***

"Always," Matteo replied quietly, looking back at Chiara.

## Chapter 2: The Archive

The archivist greeted Chiara and unlocked the heavy wooden door.

The ledger lay open on the desk for Chiara to read.

"Look at the date," Chiara told Matteo.

## Chapter 3: Return

Rain fell as Matteo walked back across the bridge with Chiara.

Near the square, the bells startled Matteo before Chiara spoke.

"We found it," Matteo told Chiara.
"""


def test_extract_manuscript_dossier_drafts_character_and_scene() -> None:
    payload = extract_manuscript_dossier_drafts(SAMPLE_MANUSCRIPT, language="en")
    assert payload["schema_version"] == DRAFT_SCHEMA
    assert payload["language"] == "en"
    assert payload["chapters"] == 3

    char_drafts = [d for d in payload["drafts"] if d["kind"] == "character"]
    assert len(char_drafts) >= 1
    names = {d["evidence_hints"]["character"] for d in char_drafts}
    assert "Matteo" in names
    matteo = next(d for d in char_drafts if d["evidence_hints"]["character"] == "Matteo")
    assert "character" in matteo["tags"]
    assert "manuscript-draft" in matteo["tags"]
    assert "chapters" in matteo["body"]

    scene_only = extract_manuscript_dossier_drafts(SAMPLE_MANUSCRIPT, language="en", kind="scene")
    assert len(scene_only["drafts"]) >= 1
    assert all(d["kind"] == "scene" for d in scene_only["drafts"])
    assert scene_only["drafts"][0]["evidence_hints"]["chapters"] == 3


def test_api_and_cli_create_dossier_from_manuscript(tmp_path: Path, capsys: object) -> None:
    project = tmp_path / "novel"
    project.mkdir()
    research_api.init(project, title="Dolomiten", language="en")
    manuscript = project / "manuscript.md"
    manuscript.write_text(SAMPLE_MANUSCRIPT, encoding="utf-8")

    drafts = research_api.manuscript_dossier_drafts(project, manuscript, language="en")
    assert len(drafts["drafts"]) >= 2
    first_id = drafts["drafts"][0]["id"]

    created = research_api.create_dossier_from_manuscript(
        project,
        manuscript,
        draft_id=first_id,
        language="en",
    )
    assert created["title"] == drafts["drafts"][0]["title"]
    assert created["dossier_id"]
    assert created["draft"]["id"] == first_id

    rc = lixity_cli_main(
        [
            "research",
            "dossier-drafts",
            "--project",
            str(project),
            "--manuscript",
            str(manuscript),
            "--kind",
            "scene",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    cli_payload = json.loads(captured.out)
    assert len(cli_payload["drafts"]) >= 1
    assert all(d["kind"] == "scene" for d in cli_payload["drafts"])


def test_mcp_manuscript_dossier_drafts() -> None:
    tool_names = {t["name"] for t in _TOOLS}
    assert "lixity_manuscript_dossier_drafts" in tool_names

    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "lixity_manuscript_dossier_drafts",
                "arguments": {
                    "text": SAMPLE_MANUSCRIPT,
                    "language": "en",
                    "kind": "all",
                },
            },
        }
    )
    assert resp is not None
    assert "result" in resp
    result = resp["result"]
    assert not result.get("isError", False)
    data = json.loads(result["content"][0]["text"])
    assert data["schema_version"] == DRAFT_SCHEMA
    assert data["chapters"] == 3
    assert len(data["drafts"]) >= 2


def test_research_panel_has_direct_timeline_tab_and_draft_controls() -> None:
    html = render_research_panel(WORKSPACE_LABELS["de"], read_only=False)
    assert 'id="research-tab-timeline"' in html
    assert 'id="rtab-timeline"' in html
    assert 'id="r-manuscript-dossier-btn"' in html
    assert 'id="r-manuscript-drafts"' in html


def test_extract_drafts_accepts_full_project_config() -> None:
    result = extract_manuscript_dossier_drafts(
        SAMPLE_MANUSCRIPT,
        language="de",
        settings={
            "language": "de",
            "characters": {"Matteo": {"aliases": ["Teo"], "pov_in_chapters": [1, 3]}},
            "scene_analysis": {"titles": {"1:1": "Eröffnung"}},
        },
        kind="all",
    )
    assert any(d["kind"] == "character" for d in result["drafts"])
    assert any(d["kind"] == "scene" for d in result["drafts"])


def test_manuscript_dossier_drafts_excludes_existing_by_default(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    research_api.init(project, title="Filter Test", language="en")
    manuscript = project / "novel.md"
    manuscript.write_text(SAMPLE_MANUSCRIPT, encoding="utf-8")

    initial = research_api.manuscript_dossier_drafts(project, manuscript, language="en")
    char_drafts = [d for d in initial["drafts"] if d["kind"] == "character"]
    assert char_drafts
    first_id = char_drafts[0]["id"]
    research_api.create_dossier_from_manuscript(project, manuscript, draft_id=first_id, language="en")

    after = research_api.manuscript_dossier_drafts(project, manuscript, language="en")
    assert after["skipped_existing"] >= 1
    assert all(d["id"] != first_id for d in after["drafts"])

    including = research_api.manuscript_dossier_drafts(project, manuscript, language="en", exclude_existing=False)
    assert including["skipped_existing"] == 0
    assert any(d["id"] == first_id for d in including["drafts"])
