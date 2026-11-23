"""Project-local dossier choices across read-only tools and saved reports."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from lixity.config import configuration_metadata
from lixity.dossier_draft_settings import resolve_dossier_draft_settings
from lixity.mcp import handle_message
from lixity.research import api
from lixity.research import character_evidence as evidence_module
from lixity.research.character_evidence import (
    CharacterEvidenceChanged,
    character_dossier_text,
    character_evidence,
)
from lixity.research.manuscript_drafts import extract_manuscript_dossier_drafts
from tests.research_support import capture_research

_TEXT = """# Novel

## Chapter 1: The crossing

The sky was clear. The wind had dropped. The lamps were lit.

Mira kept the key.

The waters rose. The tide turned. The boats left.

She went to Amberport. The keys were in Amberport.

The boat drifted toward Bayport. Goods were stored in Bayport.

Mira checked the lock. Mira left the key.
"""


def test_root_config_precedence_in_cli_and_explicit_author_settings(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    manuscript = root / "book.md"
    manuscript.write_text(_TEXT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text("[dossier_drafts]\ninferred_location_limit = 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.lixity.dossier_drafts]\ninferred_location_limit = 1\n", encoding="utf-8")

    def names(payload):
        return [draft["evidence_hints"]["location"] for draft in payload["drafts"]]

    status, output, _ = capture_research("dossier-drafts", "--project", str(root),
                                         "--manuscript", str(manuscript), "--kind", "location")
    assert status == 0 and names(json.loads(output)) == ["Amberport"]

    (root / "lixity.toml").write_text("[dossier_drafts]\ninferred_location_limit = 2\n", encoding="utf-8")
    archive = root / "archive"
    api.init(archive, title="Synthetic archive")
    selected = api.manuscript_dossier_drafts(archive, manuscript, kind="location", settings_root=root)
    assert names(selected) == ["Amberport", "Bayport"]

    (root / "lixity.toml").write_text("locations = ['Bayport']\n[dossier_drafts]\ninferred_location_limit = 0\n",
                                     encoding="utf-8")
    configured = api.manuscript_dossier_drafts(archive, manuscript, kind="location", settings_root=root)
    assert names(configured) == ["Bayport"]
    assert configured["drafts"][0]["evidence_hints"]["basis"] == "configured"


def test_dossier_cli_supports_configured_default_and_both_explicit_path_forms(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    manuscript = project / "book.md"
    manuscript.write_text(_TEXT, encoding="utf-8")
    external = tmp_path / "external.md"
    external.write_text(_TEXT.replace("Mira", "Noor"), encoding="utf-8")
    base = ("--project", str(project), "--kind", "character")

    status, _, error = capture_research("dossier-drafts", *base)
    assert status != 0 and "set manuscript" in error

    (project / "lixity.toml").write_text('manuscript = "book.md"\n', encoding="utf-8")
    status, output, _ = capture_research("dossier-drafts", *base)
    assert status == 0 and json.loads(output)["manuscript"] == str(manuscript)
    assert not (project / "research").exists()
    for explicit in ((str(external),), ("--manuscript", str(external))):
        status, output, _ = capture_research("dossier-drafts", *explicit, *base)
        assert status == 0 and json.loads(output)["manuscript"] == str(external)

    api.init(project, title="Synthetic project")
    status, output, _ = capture_research("dossier-drafts", *base)
    assert status == 0
    draft = next(item for item in json.loads(output)["drafts"] if item["id"] == "character:mira")
    status, output, _ = capture_research(
        "dossier-from-manuscript", *base, "--draft-id", draft["id"], "--preview-sha256", draft["preview_sha256"],
    )
    assert status == 0 and json.loads(output)["draft"]["id"] == draft["id"]


def test_draft_settings_strict_and_draft_caps_do_not_limit_configured_characters() -> None:
    settings = configuration_metadata()
    assert "dossier_drafts" in settings["project_only_keys"]
    properties = settings["dossier_drafts_schema"]["properties"]
    assert properties["inferred_character_limit"]["default"] == 12
    assert properties["inferred_location_limit"]["maximum"] == 50
    assert properties["character_context_sentences"]["default"] == 2
    assert properties["character_report_passages"]["default"] is True

    for invalid in ({"inferred_character_limit": True}, {"inferred_location_limit": -1},
                    {"character_context_sentences": 6}, {"character_report_passages": "false"}, {"typo": 0}):
        with pytest.raises(ValueError, match=r"Invalid \[dossier_drafts\]"):
            resolve_dossier_draft_settings({"dossier_drafts": invalid})

    disabled = {"dossier_drafts": {"inferred_character_limit": 0, "character_report_passages": False}}
    assert extract_manuscript_dossier_drafts(_TEXT, kind="character", settings=disabled)["drafts"] == []
    configured = extract_manuscript_dossier_drafts(_TEXT, kind="character", settings={**disabled, "characters": {"Mira": {}}})
    draft = configured["drafts"][0]
    assert draft["evidence_hints"]["first_hit"]["quote"] == "Mira kept the key."
    assert "Mira kept the key." not in draft["body"]


def test_context_and_saved_passages_settings_are_independent() -> None:
    source = sha256(_TEXT.encode("utf-8")).hexdigest()
    defaults = {"characters": {"Mira": {}}}
    settings = {**defaults, "dossier_drafts": {"character_context_sentences": 3}}
    baseline = character_evidence(_TEXT, source, character="Mira", language="en", settings=defaults)
    report = character_evidence(_TEXT, source, character="Mira", language="en", settings=settings)
    assert report["context_sentences"] == 3
    assert report["passages"][0]["text"] == "Mira kept the key."
    assert report["passages"][0]["context_before"] == "The sky was clear. The wind had dropped. The lamps were lit."
    assert baseline["passages"][0]["context_before"] == "The wind had dropped. The lamps were lit."
    with pytest.raises(CharacterEvidenceChanged):
        character_evidence(_TEXT, source, character="Mira", language="en", settings=settings,
                           expected_analysis_sha256=baseline["analysis_sha256"])

    no_context = {**defaults, "dossier_drafts": {"character_context_sentences": 0}}
    no_context_report = character_evidence(_TEXT, source, character="Mira", language="en", settings=no_context)
    assert no_context_report["passages"][0]["context_before"] == no_context_report["passages"][0]["context_after"] == ""
    assert no_context_report["passages"][0]["text"] == "Mira kept the key."

    without_passages = {**defaults, "dossier_drafts": {"character_report_passages": False}}
    compact = character_dossier_text(_TEXT, source, character="Mira", language="en", settings=without_passages)
    full = character_dossier_text(_TEXT, source, character="Mira", language="en", settings=defaults)
    assert compact["analysis_sha256"] == full["analysis_sha256"] == baseline["analysis_sha256"]
    assert compact["passage_count"] == full["passage_count"]
    assert compact["includes_passages"] is False and full["includes_passages"] is True
    assert "kept the key" in full["body"] and "kept the key" not in compact["body"]
    assert "Chapters with name matches" in compact["body"]


def test_character_pages_only_project_context_for_selected_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [f"Mira checked entry {index}." for index in range(54)]
    manuscript = "\n\n".join(f"## Ledger {start}\n\n" + "\n\n".join(rows[start:start + 18])
                               for start in range(0, len(rows), 18))
    source = sha256(manuscript.encode()).hexdigest()
    measured = []
    split = evidence_module.split_prose_sentence_spans

    def context_sentences(text: str, language: str):
        measured.append(text)
        return split(text, language)

    monkeypatch.setattr(evidence_module, "split_prose_sentence_spans", context_sentences)
    settings = {"characters": {"Mira": {}}}
    page = character_evidence(manuscript, source, character="Mira", language="en", settings=settings, offset=16)
    assert page["passage_count"] == page["mentions"] == 54
    assert [row["passage_count"] for row in page["chapters"]] == [18, 18, 18]
    assert page["next_offset"] == 36
    assert measured == [row["text"] for row in page["passages"]] == rows[16:36]

    measured.clear()
    monkeypatch.setattr(evidence_module, "_PASSAGE_TEXT_BYTES_PER_PAGE", 15)
    limited = character_evidence(manuscript, source, character="Mira", language="en", settings=settings,
                                 chapter=3, expected_analysis_sha256=page["analysis_sha256"])
    assert limited["passage_count"] == 18 and limited["next_offset"] == 1
    assert [row["text"] for row in limited["passages"]] == rows[36:37]
    assert measured == rows[36:38]

    measured.clear()
    overview = character_dossier_text(manuscript, source, character="Mira", language="en",
                                      settings={**settings, "dossier_drafts": {"character_report_passages": False}})
    assert overview["passage_count"] == 54 and measured == []


def test_mcp_can_disable_inference_without_reading_project_settings() -> None:
    def call(options):
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "lixity_manuscript_dossier_drafts",
            "arguments": {"text": _TEXT, "kind": "location", "dossier_drafts": options},
        }}
        response = handle_message(message)
        assert response is not None
        return response["result"]

    result = call({"inferred_location_limit": 0})
    assert not result.get("isError", False)
    assert json.loads(result["content"][0]["text"])["drafts"] == []
    assert call({"inferred_location_limit": True})["isError"] is True
