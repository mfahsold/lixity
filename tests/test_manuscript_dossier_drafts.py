"""Tests for deterministic manuscript-driven dossier drafts and direct timeline tab."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode

import pytest
from support import LoopbackServer, make_handler

from lixity.characters import _name_pattern, character_presence
from lixity.cli import main as lixity_cli_main
from lixity.mcp import _TOOLS, handle_message
from lixity.research import api as research_api
from lixity.research.character_evidence import _chapter_passages
from lixity.research.manuscript_drafts import DRAFT_SCHEMA, extract_manuscript_dossier_drafts
from lixity.server.pdf_context import research_context_token
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


def test_legacy_regex_matches_keep_grouped_and_zero_width_locations() -> None:
    body = "Anna\n\nMaria hielt Wache.\n\n> Anna rief.\n>\n> Maria wartete."
    expression = r"Anna\s+Maria|(?=\n\nMaria wartete)"
    mentions, passages = _chapter_passages(body, [_name_pattern(expression)])
    assert mentions == character_presence("## Kapitel\n\n" + body, {expression: "Anna"})[0].mentions == 2
    assert passages == [
        {"start_line": 1, "end_line": 3, "text": "Anna\n\nMaria hielt Wache.",
         "matches": [{"start": 0, "end": 11}]},
        {"start_line": 5, "end_line": 5, "text": "Anna rief.",
         "matches": [{"start": 10, "end": 10}]},
    ]


def test_figure_reading_context_fills_only_missing_adjacent_sentences() -> None:
    body = "\n\n".join((
        "Far away. Dr. Vale checked the hall. The clock had stopped.",
        "Anna entered. The lamp hummed.",
        "A guard crossed the yard. Rain followed. The gate shut.",
        "The trail curved. Anna heard the gate. Silence returned. The path vanished.",
        "Anna paused.",
        "***",
        "Unrelated scene. It starts beyond the divider.",
    ))
    mentions, passages = _chapter_passages(body, [_name_pattern("Anna")], context_language="en")
    assert mentions == len(passages) == 3
    first, middle, last = passages
    assert first["text"] == "Anna entered. The lamp hummed."
    assert first["context_before"] == "Dr. Vale checked the hall. The clock had stopped."
    assert first["context_after"] == "A guard crossed the yard."
    assert middle["context_before"] == "The gate shut."
    assert middle["context_after"] == ""
    assert last["context_before"] == last["context_after"] == ""
    assert [item["text"][span["start"]:span["end"]] for item in passages for span in item["matches"]] == ["Anna"] * 3


def test_figure_reading_context_stays_in_one_quotation_block() -> None:
    body = "The narrator begins.\n\n> The wind rises.\n>\n> Anna waits.\n>\n> The door opens.\n\nThe narrator stops."
    _, (passage,) = _chapter_passages(body, [_name_pattern("Anna")], context_language="en")
    assert passage["context_before"] == "The wind rises."
    assert passage["text"] == "Anna waits."
    assert passage["context_after"] == "The door opens."


def test_saved_character_evidence_is_complete_paged_and_context_bound(tmp_path: Path) -> None:
    project = tmp_path
    manuscript = project / "novel.md"
    long_passage = "😀 **Anna** rief Nanni. " + "Die übrige Beschreibung bleibt lesbar. " * 20 + "Letzter Satz."
    middle = [f"Anna nannte die Nummer {num}." for num in range(23)]
    prose = "\n\n".join(["## Ankunft", "Die Wache schlief. Die Glocke läutete.", long_passage, *middle,
                          "## Pause", "Nur die anderen gingen weiter.",
                          "## Rückkehr", "> Nanni blieb noch.", "`Anna` [Weiter](https://example.test/Anna)."])
    manuscript.write_text(prose, encoding="utf-8")
    config = project / "lixity.toml"
    config.write_text('[characters.Anna]\naliases = ["Nanni"]\npov_in_chapters = [2]\n', encoding="utf-8")
    init = research_api.init(project, title="Figurendossier", language="de")
    record = research_api.create_dossier(project, "Figur: Anna", "## Überblick\n\nEigene Notizen.",
                                        tags=["manuscript-draft", "character"])
    manual = research_api.create_dossier(project, "Figur: Andere", "Eigene Notizen.", tags=["character"])
    token = research_context_token(project)

    def path(**params: str | int) -> str:
        return "/api/research/dossier-character?" + urlencode({"research_token": token, **params})

    with LoopbackServer(make_handler(project, source_input=manuscript, language="de")) as server:
        dossier_base = "/api/research/dossiers?id=" + record["dossier_id"]
        assert server.request_json(dossier_base)[1]["character_analysis_available"] is True
        assert "character_analysis_available" not in server.request_json(dossier_base + "&revision=1")[1]
        record_base = "/api/research/record?kind=dossier&id="
        assert server.request_json(record_base + record["dossier_id"])[1]["character_analysis_available"] is True
        assert "character_analysis_available" not in server.request_json(record_base + record["dossier_id"] + "&revision=1")[1]
        assert "character_analysis_available" not in server.request_json(record_base + manual["dossier_id"])[1]
        assert server.request(path(id=manual["dossier_id"])).status == 404
        assert server.request(path(id=record["dossier_id"], research_token="0" * 64)).status == 409
        assert server.request(path(id=record["dossier_id"], offset=20)).status == 400

        status, first = server.request_json(path(id=record["dossier_id"]))
        assert status == 200, first
        assert first["project_id"] == init["project_id"]
        assert first["source_sha256"] == sha256(prose.encode()).hexdigest()
        assert first["aliases"] == ["Nanni"]
        assert first["declared_pov_chapters"] == [2]
        assert first["mentions"] == 26
        assert first["chapters_with_mentions"] == 2
        assert first["longest_gap"] == 1
        assert [row["mentions"] for row in first["chapters"]] == [25, 0, 1]
        assert first["dialogue"]["status"] == "insufficient_turns"
        assert first["passage_count"] == 25
        passage = first["passages"][0]
        assert passage["text"].endswith("Letzter Satz.")
        assert passage["context_before"] == "Die Wache schlief. Die Glocke läutete."
        assert passage["context_after"] == ""
        assert [passage["text"][span["start"]:span["end"]] for span in passage["matches"]] == ["Anna", "Nanni"]
        accepted = first["analysis_sha256"]
        next_page = path(id=record["dossier_id"], analysis_sha256=accepted, offset=first["next_offset"])
        status, rest = server.request_json(next_page)
        assert status == 200, rest
        assert len(rest["passages"]) + len(first["passages"]) == 25
        assert rest["passages"][-1]["text"] == "Nanni blieb noch."
        assert rest["next_offset"] is None
        status, empty = server.request_json(path(id=record["dossier_id"], chapter=2, analysis_sha256=accepted))
        assert status == 200, empty
        assert empty["passages"] == [] and empty["passage_count"] == 0
        config.write_text('[characters.Anna]\naliases = []\n', encoding="utf-8")
        assert server.request(next_page).status == 409
    assert manuscript.read_text(encoding="utf-8") == prose
    assert research_api.get_dossier(project, record["dossier_id"])["body"] == "## Überblick\n\nEigene Notizen."


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


def test_configured_place_drafts_use_counted_prose_and_exact_unicode_names(tmp_path: Path) -> None:
    manuscript = tmp_path / "novel.md"
    prefix = "Sie prüfte die Spuren am Ufer. " * 12
    manuscript.write_text(
        f"## Abfahrt\n\n{prefix}Sie kam in Mühle an. In MÖHLE wartete schon der Fischer.\n\n"
        "~~~text\nMühle und Möhle stehen im Codeblock.\n~~~\n\nIn Bern endete die Reise.",
        encoding="utf-8",
    )
    (tmp_path / "lixity.toml").write_text('language = "de"\nlocations = ["Mühle", "Möhle", "Bern"]\n', encoding="utf-8")
    result = research_api.manuscript_dossier_drafts(tmp_path, manuscript, kind="location")
    proposals = {item["evidence_hints"]["location"]: item for item in result["drafts"]}
    assert set(proposals) == {"Mühle", "Möhle", "Bern"}
    assert len({item["id"] for item in proposals.values()}) == 3
    for name, item in proposals.items():
        hints = item["evidence_hints"]
        assert hints["basis"] == "configured" and hints["mentions"] == 1
        assert name.casefold() in hints["first_hit"]["quote"].casefold()
        assert name.casefold() in item["body"].casefold()
    assert proposals["Mühle"]["evidence_hints"]["first_hit"]["quote"].startswith("…")


@pytest.mark.parametrize(("language", "direction", "reference"), [
    ("de", "Sie zog nach Nordhafen.", "In Nordhafen begann die Reise."),
    ("en", "She sailed toward Nordhafen.", "The ferry waited in Nordhafen."),
    ("es", "El barco siguió hacia Nordhafen.", "El ferry esperaba en Nordhafen."),
    ("fr", "Elle partit vers Nordhafen.", "Le ferry attendait à Nordhafen."),
    ("it", "Partì verso Nordhafen.", "Il traghetto aspettava a Nordhafen."),
    ("nl", "Ze ging naar Nordhafen.", "De boot wachtte in Nordhafen."),
    ("pt", "O barco seguiu para Nordhafen.", "O ferry esperava em Nordhafen."),
])
def test_place_suggestions_require_a_directional_cue_in_counted_prose(
    language: str, direction: str, reference: str,
) -> None:
    text = (f"## Leaving\n\n{direction}\n\n{reference}\n\n"
            "Sie packte in Eile. Sie ging in Eile.\n\n~~~text\nTo Atlantis. In Atlantis.\n~~~\n")
    result = extract_manuscript_dossier_drafts(text, language=language, kind="location")
    draft, = result["drafts"]
    assert draft["evidence_hints"]["location"] == "Nordhafen"
    assert draft["evidence_hints"]["basis"] == "inferred"
    assert draft["evidence_hints"]["mentions"] == 2
    assert direction in draft["body"]


def test_scene_drafts_include_all_units_in_order_with_scope_and_passages() -> None:
    scenes = "\n\n***\n\n".join(f"Ist der Weg {number} frei? Dann gehen wir los." for number in range(1, 46))
    text = f"## Aufbruch\n\n{scenes}\n\n## Ankunft\n\nAm Tor wartete niemand. Sie klopfte.\n"
    overview, *units = extract_manuscript_dossier_drafts(text, language="de", kind="scene")["drafts"]
    assert [draft["id"] for draft in units] == [*(f"scene:1:{n}" for n in range(1, 46)), "scene:2:1"]
    assert overview["id"] == "scenes:manuscript"
    assert overview["evidence_hints"]["chapter_fallback"] is True
    assert "Kapitel 1 · Szene 45" in overview["body"]
    assert units[0]["evidence_hints"]["scene_scope"] == "scene"
    assert "Ist der Weg 1 frei?" in units[0]["body"]
    assert "Dann gehen wir los." in units[0]["body"]
    assert "Frage" in units[0]["body"]
    assert units[-1]["evidence_hints"]["scene_scope"] == "chapter"
    assert "das ganze Kapitel" in units[-1]["body"]


def test_character_draft_first_passage_uses_counted_alias_and_readable_excerpt() -> None:
    prose = ("Quiet footsteps return to the courtyard. " * 8) + (
        "nox waits near the wall. After the watch has passed, she follows the frozen lane. " * 4
    )
    payload = extract_manuscript_dossier_drafts(
        "## The courtyard\n\n```text\nRowan remains in a note.\n```\n\n" + prose,
        settings={"characters": {"Rowan": {"aliases": ["Nox"], "pov_in_chapters": [1]}}},
        kind="character",
    )
    draft, = payload["drafts"]
    first = draft["evidence_hints"]["first_hit"]
    assert first["chapter"] == 1 and first["line"] > 1
    assert first["quote"].startswith("…") and first["quote"].endswith("…")
    assert "nox waits near the wall." in first["quote"]
    assert "remains in a note" not in draft["body"]
    assert "Declared viewpoint chapters" in draft["body"]


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
