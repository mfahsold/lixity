"""Tests for deterministic manuscript-driven dossier drafts and direct timeline tab."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from support import LoopbackServer, make_handler

from lixity import dialogue
from lixity.characters import _name_pattern, character_presence, resolve_character_settings
from lixity.cli import main as lixity_cli_main
from lixity.mcp import _TOOLS, handle_message
from lixity.research import api as research_api
from lixity.research.character_evidence import (
    _auto_character_names,
    _chapter_passages,
    character_dialogue_evidence,
    character_dialogue_markdown,
    character_dossier_text,
    character_evidence,
)
from lixity.research.manuscript_drafts import DRAFT_SCHEMA, extract_manuscript_dossier_drafts
from lixity.scenes import SceneSettingsError
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
    assert "Chapters with matches 3/3" in matteo["body"]

    scene_only = extract_manuscript_dossier_drafts(SAMPLE_MANUSCRIPT, language="en", kind="scene")
    assert len(scene_only["drafts"]) >= 1
    assert all(d["kind"] == "scene" for d in scene_only["drafts"])
    assert scene_only["drafts"][0]["evidence_hints"]["chapters"] == 3


def test_dossier_dialogue_keeps_cast_ambiguity_without_narrator_or_pair_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = (
        '## Chapter 1: Arrival\n\n'
        + '"Are you ready?" Mara asked.\n\n' * dialogue.MIN_CHARACTER_VOICE_TURNS
        + '"Wait," Mara said to Ivan.\n\n'
        + '"It is late," Ivan said.\n\n'
        + 'The fog settled over the river.'
    )
    settings = {"characters": {"Mara": {}, "Ivan": {}}}
    names = resolve_character_settings(None, settings).names
    profile = dialogue.character_voice_profiles(text, names)
    assert profile["narrator"]["words"] > 0
    assert profile["character_interactions"]["pairs"] == [
        {"a": "Ivan", "b": "Mara", "turn_exchanges": 0, "co_chapters": 1},
    ]
    expected = {
        row["name"]: character_dialogue_evidence(row) for row in profile["characters"]
    }
    mara = expected["Mara"]
    assert mara is not None and mara["turns"] == dialogue.MIN_CHARACTER_VOICE_TURNS

    def unused(*_args: object) -> None:
        pytest.fail("Dossier dialogue computed the discarded narrator or pairs")

    monkeypatch.setattr(dialogue, "_narration_context", unused)
    monkeypatch.setattr(dialogue, "itertools", SimpleNamespace(combinations=unused))
    evidence = character_evidence(
        text, sha256(text.encode()).hexdigest(), character="Mara", language="en", settings=settings,
    )
    assert evidence["dialogue"] == mara
    result = extract_manuscript_dossier_drafts(text, language="en", settings=settings, kind="character")
    assert {draft["evidence_hints"]["character"] for draft in result["drafts"]} == expected.keys()
    for draft in result["drafts"]:
        voice = expected[draft["evidence_hints"]["character"]]
        assert voice is not None
        assert character_dialogue_markdown(voice, WORKSPACE_LABELS["en"], "en") in draft["body"]


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


def test_saved_character_evidence_is_complete_paged_and_context_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path
    manuscript = project / "novel.md"
    long_passage = "😀 **Anna** rief Nanni. " + "Die übrige Beschreibung bleibt lesbar. " * 20 + "Letzter Satz."
    middle = [f"Anna nannte die Nummer {max(1, num)}." for num in range(23)]
    prose = "\n\n".join(["---\ntitle: Eine fiktive Geschichte\n---", "## Ankunft", "Die Wache schlief. Die Glocke läutete.", long_passage, *middle,
                          "## Pause", "Nur die anderen gingen weiter.",
                          "## Rückkehr", "> Das Ufer war leer.\n>\n> Nanni blieb noch.\n>\n> Später sank die Sonne.",
                          "`Anna` [Weiter](https://example.test/Anna).", "```text\nAnna steht nur im Codeblock.\n```"])
    manuscript.write_text(prose, encoding="utf-8")
    config = project / "lixity.toml"
    config.write_text('[characters.Anna]\naliases = ["Nanni"]\npov_in_chapters = [2]\n', encoding="utf-8")
    init = research_api.init(project, title="Figurendossier", language="de")
    record = research_api.create_dossier(project, "Figur: Anna", "## Überblick\n\nEigene Notizen.",
                                        tags=["manuscript-draft", "character"])
    original_title = "Annas handgeschriebene Notizen"
    research_api.revise_record(project, "dossier", record["dossier_id"], expected_snapshot=record["snapshot"],
                               expected_revision=1, changes={"title": original_title}, change_kind="correction",
                               reason="A revised title preserves the original character binding.")
    manual = research_api.create_dossier(project, "Figur: Andere", "Eigene Notizen.", tags=["character"])
    missing = research_api.create_dossier(project, "Figur: Unbekannt", "Eigene Notizen.",
                                         tags=["manuscript-draft", "character"])
    token = research_context_token(project)
    head = project / "research" / "HEAD.json"
    accepted_archive = head.read_bytes()

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
        assert server.request(path(id=manual["dossier_id"], format="markdown")).status == 404
        assert server.request(path(id=record["dossier_id"], format="unknown")).status == 400
        assert server.request(path(id=record["dossier_id"], format="markdown", chapter=2)).status == 400
        assert server.request(path(id=record["dossier_id"], format="markdown", offset=0)).status == 400
        status, no_matches = server.request_json(path(id=missing["dossier_id"], format="markdown"))
        assert status == 404 and no_matches["code"] == "character-dossier-empty"

        status, first = server.request_json(path(id=record["dossier_id"]))
        assert status == 200, first
        assert first["project_id"] == init["project_id"]
        assert first["source_sha256"] == sha256(prose.encode()).hexdigest()
        assert first["aliases"] == ["Nanni"]
        assert first["declared_pov_chapters"] == [2]
        assert first["mentions"] == 26
        assert first["chapters_with_mentions"] == 2
        assert first["longest_gap"] == 1
        assert first["longest_gap_chapters"] == [2, 2]
        assert [row["mentions"] for row in first["chapters"]] == [25, 0, 1]
        assert first["dialogue"]["status"] == "insufficient_turns"
        assert first["passage_count"] == 25
        assert "body" not in first and "existing_dossier" not in first
        passage = first["passages"][0]
        assert passage["text"].endswith("Letzter Satz.")
        assert passage["context_before"] == "Die Wache schlief. Die Glocke läutete."
        assert passage["context_after"] == ""
        assert [passage["text"][span["start"]:span["end"]] for span in passage["matches"]] == ["Anna", "Nanni"]
        line = prose.splitlines().index(long_passage) + 1
        assert passage["reader_anchor"] == {"start_line": line, "end_line": line,
                                            "paragraph_sha256": sha256(passage["text"].encode()).hexdigest()}
        duplicate_lines = [number for number, text in enumerate(prose.splitlines(), 1) if text == middle[0]]
        duplicate_anchors = [row["reader_anchor"] for row in first["passages"][1:3]]
        assert [anchor["start_line"] for anchor in duplicate_anchors] == duplicate_lines
        assert duplicate_anchors[0]["paragraph_sha256"] == duplicate_anchors[1]["paragraph_sha256"]
        accepted = first["analysis_sha256"]
        next_page = path(id=record["dossier_id"], analysis_sha256=accepted, offset=first["next_offset"])
        status, rest = server.request_json(next_page)
        assert status == 200, rest
        assert len(rest["passages"]) + len(first["passages"]) == 25
        assert rest["passages"][-1]["text"] == "Nanni blieb noch."
        assert rest["passages"][-1]["context_before"] == "Das Ufer war leer."
        assert rest["passages"][-1]["context_after"] == "Später sank die Sonne."
        assert "reader_anchor" not in rest["passages"][-1]
        assert rest["next_offset"] is None
        proposal_path = path(id=record["dossier_id"], format="markdown")
        status, proposal = server.request_json(proposal_path)
        assert status == 200, proposal
        assert proposal["existing_dossier"] == {
            "id": record["dossier_id"], "title": original_title, "revision": 2,
            "project_id": init["project_id"], "snapshot": json.loads(accepted_archive)["sha256"],
        }
        for key in ("analysis_sha256", "mentions", "chapters_with_mentions", "passage_count"):
            assert proposal[key] == first[key]
        assert proposal["chapter_count"] == len(first["chapters"])
        assert "reader_anchor" not in proposal
        body = proposal["body"]
        assert "## Figur im Manuskript" in body
        assert "Kapitel mit Namensnennungen" in body
        assert "| 2 | 0 |" not in body
        assert "Die längste Lücke zwischen Treffern umfasst Kapitel 2." in body
        assert "Fundstellen lesen" in body
        assert body.count("**Anna** nannte die Nummer") == 23
        assert "Anna steht nur im Codeblock." not in body
        assert "https://example.test/Anna" not in body
        assert body.index("Die Wache schlief. Die Glocke läutete.") < body.index("Letzter Satz.")
        assert body.index("Das Ufer war leer.") < body.index("**Nanni** blieb noch.") < body.index("Später sank die Sonne.")
        assert WORKSPACE_LABELS["de"]["research_dossier_character_dialogue"] not in body
        assert WORKSPACE_LABELS["de"]["research_dossier_character_sentence_words"] not in body
        with monkeypatch.context() as patch:
            patch.setattr("lixity.server.routes_research.MAX_DOSSIER_BODY_CHARS", 1)
            status, too_large = server.request_json(proposal_path)
            assert status == 413 and too_large["code"] == "character-dossier-too-large"
            assert "body" not in too_large
        status, empty = server.request_json(path(id=record["dossier_id"], chapter=2, analysis_sha256=accepted))
        assert status == 200, empty
        assert empty["passages"] == [] and empty["passage_count"] == 0
        config.write_text('[characters.Anna]\naliases = []\n', encoding="utf-8")
        assert server.request(next_page).status == 409
    assert manuscript.read_text(encoding="utf-8") == prose
    assert head.read_bytes() == accepted_archive
    assert research_api.get_dossier(project, record["dossier_id"])["body"] == "## Überblick\n\nEigene Notizen."
    with LoopbackServer(make_handler(project, language="de")) as server:
        assert server.request(proposal_path).status == 404


@pytest.mark.parametrize("language", sorted(WORKSPACE_LABELS))
def test_character_dossier_text_has_localized_saved_sections(language: str) -> None:
    text = "## Morning\n\nA light flickered.\n\nAnna waited.\n\nThe door closed."
    report = character_dossier_text(text, sha256(text.encode()).hexdigest(), character="Anna", language=language,
                                    settings={"characters": {"Anna": {}}})
    body = report["body"]
    labels = WORKSPACE_LABELS[language]
    for part in ("heading", "distribution", "mentions", "passages", "scope", "context_before", "context_after"):
        assert labels[f"research_dossier_character_{part}"] in body
    assert labels["research_dossier_character_coverage_one"].format(covered=1, chapters=1) in body
    assert report["mentions"] == report["passage_count"] == report["chapters_with_mentions"] == report["chapter_count"] == 1
    assert body.index("A light flickered.") < body.index("**Anna** waited.") < body.index("The door closed.")
    assert f"> **{labels['research_read_passage']}**" not in body


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


def test_configured_place_matches_nfc_and_lists_chapters_with_mentions() -> None:
    manuscript = "## Arrival\n\nShe arrived in Mühle.\n\n## Pause\n\nShe rested at home."
    name = "Mu\u0308hle"
    result = extract_manuscript_dossier_drafts(manuscript, settings={"locations": [name]}, kind="location")
    place, = result["drafts"]
    assert place["evidence_hints"]["location"] == name
    assert place["evidence_hints"]["chapters"] == [1]
    assert place["evidence_hints"]["first_hit"]["quote"] == "She arrived in Mühle."
    assert "| 1 | 1 |" in place["body"] and "| 2 | 0 |" not in place["body"]
    assert "> She arrived in **Mühle**." in place["body"]
    assert WORKSPACE_LABELS["en"]["research_dossier_draft_location_last_match"] not in place["body"]


def test_place_excerpt_keeps_counted_match_adjoining_long_punctuation() -> None:
    prose = "She came from Mühle" + ("-" * 190) + " at noon.\n\nAt dusk she returned to Mühle" + ("-" * 190)
    report = extract_manuscript_dossier_drafts("## Arrival\n\n" + prose,
                                              settings={"locations": ["Mühle"]}, kind="location")
    place, = report["drafts"]
    assert place["evidence_hints"]["mentions"] == 2
    assert place["evidence_hints"]["first_hit"]["quote"] == "She came from Mühle…"
    assert "> She came from **Mühle**…" in place["body"]
    assert "> At dusk she returned to **Mühle**…" in place["body"]


def test_inferred_places_do_not_run_character_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    def unwanted(*_args, **_kwargs):
        pytest.fail("Place inference should only use declared characters")

    monkeypatch.setattr("lixity.research.manuscript_drafts._auto_character_names", unwanted)
    result = extract_manuscript_dossier_drafts("She sailed toward Northport. We waited in Northport.", kind="location")
    place, = result["drafts"]
    assert place["evidence_hints"]["location"] == "Northport"


@pytest.mark.parametrize(("scene_settings", "message"), [
    (False, "scene_analysis must be a table"),
    ({"groups": {"Walk": {}}, "assignments": {"2:1": "Walk"}}, "no longer match"),
])
def test_all_drafts_keep_other_categories_when_scene_settings_fail(scene_settings, message: str) -> None:
    manuscript = "## Arrival\n\nAnna reached Mühle."
    settings = {"characters": {"Anna": {}}, "locations": ["Mühle"], "scene_analysis": scene_settings}
    report = extract_manuscript_dossier_drafts(manuscript, settings=settings)
    assert {draft["kind"] for draft in report["drafts"]} == {"character", "location"}
    assert report["unavailable"].keys() == {"scene"}
    assert message in report["unavailable"]["scene"]
    with pytest.raises(SceneSettingsError, match=message):
        extract_manuscript_dossier_drafts(manuscript, settings=settings, kind="scene")


def test_all_drafts_keep_scenes_when_locations_have_invalid_configuration() -> None:
    manuscript = "## Arrival\n\nShe reached the village."
    settings = {"locations": "a scalar is not a list"}
    report = extract_manuscript_dossier_drafts(manuscript, settings=settings)
    assert [draft["id"] for draft in report["drafts"]] == ["scenes:manuscript", "scene:1:1"]
    assert report["unavailable"] == {"location": "locations must be a list of names or 'auto'"}
    with pytest.raises(ValueError, match="locations must be a list of names"):
        extract_manuscript_dossier_drafts(manuscript, settings=settings, kind="location")


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
    assert draft["evidence_hints"]["qualifying_mentions"] == 2
    assert draft["evidence_hints"]["reason_hit"] == draft["evidence_hints"]["first_hit"]
    assert draft["evidence_hints"]["reason_hit"]["quote"] == direction
    assert draft["evidence_hints"]["last_hit"]["quote"] == reference
    body = draft["body"]
    assert body.count("**Nordhafen**") == 2
    assert direction in body.replace("**", "")
    assert reference in body.replace("**", "")
    labels = WORKSPACE_LABELS[language]
    for key in ("research_dossier_draft_location_inferred", "research_dossier_draft_location_chapters",
                "research_dossier_draft_location_last_match", "research_dossier_draft_location_review"):
        assert body.count(labels[key]) == 1


def test_place_suggestion_distinguishes_directional_evidence_from_first_name_mention() -> None:
    text = "## Arrival\n\nNorthport was on the list.\n\nWe waited in Northport.\n\n## Departure\n\nThey sailed toward Northport."
    draft, = extract_manuscript_dossier_drafts(text, kind="location")["drafts"]
    hints = draft["evidence_hints"]
    assert hints["mentions"] == 3 and hints["qualifying_mentions"] == 2
    assert hints["first_hit"]["chapter"] == 1
    assert hints["reason_hit"] == hints["last_hit"]
    assert hints["reason_hit"]["chapter"] == 2
    assert hints["reason_hit"]["quote"] == "They sailed toward Northport."


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
    assert WORKSPACE_LABELS["de"]["research_dossier_draft_scene_review"] in units[0]["body"]
    assert units[-1]["evidence_hints"]["scene_scope"] == "chapter"
    assert "das ganze Kapitel" in units[-1]["body"]


def test_scene_edges_preserve_full_measured_sentences_and_repeat_positions() -> None:
    opening = "She noticed " + "the lantern, the key, and the old books, " * 12 + "did you see it?"
    manuscript = f"## Arrival\n\n{opening} The door opened. {opening}"
    _, scene = extract_manuscript_dossier_drafts(manuscript, kind="scene")["drafts"]
    assert scene["body"].count(f"> {opening}") == 2
    assert "Opening passage" in scene["body"] and "Closing passage" in scene["body"]
    assert "excerpt_limited" not in scene["evidence_hints"]


def test_single_sentence_scene_has_one_passage_and_a_shared_role() -> None:
    _, scene = extract_manuscript_dossier_drafts("## Arrival\n\nDid the ferry leave?", kind="scene")["drafts"]
    body = scene["body"]
    assert body.count("> Did the ferry leave?") == 1
    assert body.count("Question") == 1
    assert WORKSPACE_LABELS["en"]["research_dossier_draft_scene_single_passage"] in body


def test_oversized_scene_edges_use_marked_excerpts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lixity.research.manuscript_drafts.MAX_DOSSIER_BODY_CHARS", 700)
    opening = "She noticed " + "the lantern, the key, and the old books, " * 24 + "did you see it?"
    _, scene = extract_manuscript_dossier_drafts(f"## Arrival\n\n{opening} Please enter.", kind="scene")["drafts"]
    assert len(scene["body"]) <= 700
    assert scene["evidence_hints"]["excerpt_limited"] is True
    assert "> She noticed" in scene["body"] and "…" in scene["body"]
    assert "> Please enter." in scene["body"]
    assert WORKSPACE_LABELS["en"]["research_dossier_draft_scene_excerpts_limited"] in scene["body"]


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


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "nl", "pt"])
def test_character_draft_localizes_title_and_body_and_preserves_binding(tmp_path: Path, language: str) -> None:
    research_api.init(tmp_path, title="Synthetic archive")
    source = tmp_path / "draft.md"
    source.write_text("## Arrival\n\nRowan returned.", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text("[characters.Rowan]\n", encoding="utf-8")
    result = research_api.manuscript_dossier_drafts(tmp_path, source, language=language, kind="character")
    character, = result["drafts"]
    labels = WORKSPACE_LABELS[language]
    separator = "\u202f: " if language == "fr" else ": "
    title = labels["research_tpl_character"] + separator + "Rowan"
    assert character["title"] == title and character["id"] == "character:rowan"
    assert f"## {labels['research_dossier_character_heading']}" in character["body"]
    assert labels["research_dossier_character_scope"] in character["body"]
    assert "> Rowan returned." in character["body"]
    saved = research_api.create_dossier_from_manuscript(
        tmp_path, source, language=language, draft_id=character["id"], preview_sha256=character["preview_sha256"],
    )
    identifier = saved["dossier_id"]
    assert research_api.get_dossier(tmp_path, identifier, include_character_binding=True)["character_analysis_available"]
    research_api.revise_record(
        tmp_path, "dossier", identifier, changes={"title": "Keeper of the gate"}, expected_snapshot=saved["snapshot"],
        expected_revision=1, change_kind="correction", reason="Use the working title",
    )
    other_language = "en" if language == "de" else "de"
    existing, = research_api.manuscript_dossier_drafts(
        tmp_path, source, language=other_language, kind="character", exclude_existing=False,
    )["drafts"]
    assert existing["already_covered"] is True
    assert existing["existing_dossier"]["id"] == identifier
    assert existing["existing_dossier"]["title"] == "Keeper of the gate"
    assert existing["existing_dossier"]["revision"] == 2


def test_auto_character_limit_uses_stable_order_for_tied_counts() -> None:
    names = ["Yara", "Xena", "Wanda", "Vera", "Ulla", "Tilda", "Selma", "Rosa", "Paula", "Orla", "Nora", "Mila", "Lora", "Kaya", "Jara"]
    body = "\n\n".join(f"{name} arrived.\n\n{name} waited." for name in names)
    assert _auto_character_names([(1, "Arrival", body)]) == sorted(names)[:12]


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
