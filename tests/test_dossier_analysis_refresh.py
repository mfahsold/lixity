"""Character report refreshes preserve authored text and accepted revisions."""

from pathlib import Path
from urllib.parse import urlencode

import pytest
from support import LoopbackServer, make_handler

from lixity.research import api
from lixity.research.dossier_analysis import (
    _LEGACY_REPORTS,
    mark_character_analysis,
    prepare_character_analysis,
)
from lixity.research.dossier_pdf import compose_dossier_pdf
from lixity.research.models import Reference
from lixity.research.sections import update_section
from lixity.server.pdf_context import research_context_token
from tests.research_support import revise_record


def _legacy_report(title: str, *, previous_label: bool, evidence: str = "Mira closed the gate.") -> str:
    summary, table, excerpts, old_gap, new_gap = _LEGACY_REPORTS[title]
    return (f"## {title}\n\n### {summary}\n\n- **{old_gap if previous_label else new_gap}:** 1\n\n"
            f"### {table}\n\n| 1 | 2 |\n\n### {excerpts}\n\n> {evidence}")


@pytest.mark.parametrize("heading", _LEGACY_REPORTS)
def test_legacy_copy_projection_ignores_only_confirmed_label_change(tmp_path: Path, heading: str) -> None:
    api.init(tmp_path, title="Synthetic review")
    authored = "## Author notes\n\nKeep the old key symbolic.\n\n```markdown\n" + _legacy_report(
        heading, previous_label=True, evidence="Literal fenced example.",
    ) + "\n```"
    earlier = _legacy_report(heading, previous_label=True)
    later = _legacy_report(heading, previous_label=False)
    separate = _legacy_report(heading, previous_label=False, evidence="Mira did not close the gate.")
    raw = "\n\n".join((authored, earlier, later, separate, "## Ending\n\nKeep the running joke."))
    created = api.create_dossier(tmp_path, "Character: Mira", raw, tags=["manuscript-draft", "character"])
    dossier = api.get_dossier(tmp_path, created["dossier_id"])
    assert dossier["body"] == raw
    display = dossier["display_body"]
    assert display.startswith(authored)
    assert display.count("Mira closed the gate.") == 1
    assert display.count("Mira did not close the gate.") == 1
    assert f"## {heading} (1)" in display and f"## {heading} (2)" in display
    assert display.endswith("## Ending\n\nKeep the running joke.")
    manual = api.create_dossier(tmp_path, "Named notes", raw, tags=["character"])
    assert "display_body" not in api.get_dossier(tmp_path, manual["dossier_id"])


def test_historical_preview_folds_only_when_quote_and_facts_are_present(tmp_path: Path, monkeypatch) -> None:
    api.init(tmp_path, title="Synthetische Auswertung", language="de")
    original = ("## Überblick\n- **Figur:** Mira\n- **Erwähnungen:** 3 in 2 von 3 Kapiteln (Kapitel 1, 3)\n\n"
                "## Erste Textstelle\n- Kapitel 1 (Am Tor), Zeile 4: „Mira zog den Schlü“")
    analysis = ("## Auswertung aus dem Manuskript\n\n### Figur im Manuskript\n\n"
                "Für Mira zählt Lixity 3 Namensnennungen in 2 von 3 Kapiteln.\n\n"
                "- **Längste Lücke zwischen Treffern (Kapitel):** 1\n\n### Namensnennungen pro Kapitel\n\n"
                "| Kapitel | Namensnennungen |\n| --- | --- |\n| 1 | 2 |\n| 2 | 0 |\n| 3 | 1 |\n\n"
                "### Fundstellen lesen\n\n#### Kapitel 1 · Am Tor\n\n**Kapiteltext · Zeilen 4–5**\n\n"
                "> **Textstelle**\n>\n> Mira zog den Schlüssel aus der Tasche. Mira hielt inne.")
    created = api.create_dossier(tmp_path, "Figur: Mira", original, tags=["manuscript-draft", "character"])
    identifier = created["dossier_id"]
    refreshed = analysis.replace("zwischen Treffern (Kapitel)", "zwischen Namensnennungen (Kapitel ohne Treffer)")
    raw = "\n\n".join((original, analysis, refreshed, "## Eigene Notizen\n\nDen Schlüssel später wieder erwähnen."))
    revise_record(tmp_path, "dossier", identifier, {"body": raw})
    reading = api.get_record(tmp_path, "dossier", identifier, revision=2)
    assert reading["record"]["body"] == raw
    assert "Erste Textstelle" not in reading["display_body"]
    assert reading["display_body"].count("Mira zog") == 1
    assert "Den Schlüssel später wieder erwähnen." in reading["display_body"]
    assert api.get_record(tmp_path, "dossier", identifier, revision=1)["record"]["body"] == original

    rendered = []

    def capture_pdf(**kwargs):
        rendered.append((kwargs["revision_label"], kwargs["body"]))
        return b"synthetic PDF"

    monkeypatch.setattr("lixity.research.dossier_pdf.dossier_pdf", capture_pdf)
    for revision in (1, 2):
        assert compose_dossier_pdf(tmp_path, Reference(id=identifier, revision=revision))
    assert rendered == [("Fassung 1", original), ("Fassung 2", reading["display_body"])]

    edited = original.replace("Mira zog den Schlü", "Mira zog den Schlü…") + "\n\n" + refreshed
    revise_record(tmp_path, "dossier", identifier, {"body": edited})
    assert "display_body" not in api.get_record(tmp_path, "dossier", identifier, revision=3)


def test_current_updates_replace_only_intact_generated_content() -> None:
    initial = mark_character_analysis("## Overview\n\nA short generated overview.")
    notes = "## Author notes\n\nKeep the key motif.\n"
    later_notes = "\n## Corrections\n\nCheck Mira’s resolve.\n"
    proposal = "## Evidence\n\n> Mira turned the key."
    first_refresh = prepare_character_analysis(notes + "\n" + initial + later_notes, proposal, "en")
    assert first_refresh.startswith(notes) and first_refresh.endswith(later_notes)
    assert "A short generated overview." not in first_refresh
    assert first_refresh.count("Mira turned the key.") == 1
    assert prepare_character_analysis(first_refresh, proposal, "en") == first_refresh
    revised_notes = update_section(first_refresh, "Author notes", "Keep the revised motif.")
    assert prepare_character_analysis(revised_notes, proposal, "en") == revised_notes

    with_edits = first_refresh.replace("Mira turned the key.", "Mira turned the key (verify setting).")
    updated = prepare_character_analysis(with_edits, proposal + " Then the lock clicked.", "en")
    assert updated.startswith(with_edits)
    assert updated.count("verify setting") == 1
    assert updated.count("Then the lock clicked.") == 1
    rerun = prepare_character_analysis(updated, proposal + " The door opened.", "en")
    assert rerun.startswith(with_edits)
    assert "Then the lock clicked." not in rerun
    assert rerun.count("The door opened.") == 1


def test_http_stages_selected_revision_without_mutating_archive(tmp_path: Path) -> None:
    api.init(tmp_path, title="Synthetic workbook")
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Novel\n\n## Chapter 1: The gate\n\nMira kept the key. Mira turned the lock.\n")
    (tmp_path / "lixity.toml").write_text("[characters.Mira]\naliases = []\n")
    drafts = api.manuscript_dossier_drafts(tmp_path, manuscript, kind="character")
    preview = drafts["drafts"][0]
    created = api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=preview["id"],
                                               preview_sha256=preview["preview_sha256"])
    identifier = created["dossier_id"]
    accepted = api.get_record(tmp_path, "dossier", identifier)
    assert accepted["record"]["body"] == preview["body"]
    assert "lixity:character-analysis" not in accepted["display_body"]
    listed = api.list_dossiers(tmp_path)["dossiers"][0]
    assert "lixity:character-analysis" not in listed["excerpt"]

    query = urlencode({"research_token": research_context_token(tmp_path), "id": identifier, "format": "markdown"})
    endpoint = "/api/research/dossier-character?" + query
    with LoopbackServer(make_handler(tmp_path, source_input=manuscript)) as server:
        status, markdown = server.request_json(endpoint)
        assert status == 200 and "staged_body" not in markdown
        status, proposal = server.request_json(endpoint + "&prepare=1")
        assert status == 200 and proposal["body"] == markdown["body"]
        assert proposal["existing_dossier"]["snapshot"] == accepted["snapshot"]
        assert proposal["staged_body"].count("Mira kept the key.") + proposal["staged_body"].count("**Mira** kept the key.") == 1
        assert proposal["staged_body"].count("<!-- lixity:character-analysis ") == 1
    assert api.get_record(tmp_path, "dossier", identifier) == accepted
