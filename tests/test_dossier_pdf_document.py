"""Dossier PDFs keep the structure and geography of one saved version."""

import pytest

from lixity.pdf_document import CENTRE, LEFT, Table
from lixity.pdf_layouts import dossier_pdf
from lixity.research import api
from lixity.research.dossier_pdf import compose_dossier_pdf
from lixity.research.models import Reference
from tests.research_support import revise_record
from tests.test_pdf_export import CHOSEN, HAVE_FONTS
from tests.test_pdf_page_information import captured_layout
from tests.test_research_geography import geography

pytestmark = pytest.mark.skipif(not HAVE_FONTS, reason="requires usable host TrueType fonts")


def test_dossier_outline_and_table_formats(monkeypatch):
    body = (
        "## Questions ##\n\n"
        "Section\tQuestion\n1. Context\tWhere was the gate?\n\n"
        "## Recorded places\n\n"
        "| Area | Count |\n| North-West | 12 |\n\n"
        "## Chapter totals\n\n"
        "| Chapter | Label | Count |\n| :--- | :---: | ---: |\n| 3 | `line_count` | 9 |\n\n"
        "One marker | in prose.\nA second marker | in prose."
    )
    data, document, pages = captured_layout(
        monkeypatch, dossier_pdf, title="Synthetic dossier", revision_label="Version 2",
        language="en", body=body, choice=CHOSEN,
    )
    assert b"/Type /Outlines" in data
    assert [title for page in pages for title, _y in page.bookmarks] == [
        "Synthetic dossier", "Questions", "Recorded places", "Chapter totals",
    ]
    tables = [block for block in document.blocks if isinstance(block, Table)]
    assert [table.rows for table in tables] == [
        [["Section", "Question"], ["1. Context", "Where was the gate?"]],
        [["Area", "Count"], ["North-West", "12"]],
        [["Chapter", "Label", "Count"], ["3", "line_count", "9"]],
    ]
    assert tables[2].alignments == [LEFT, CENTRE, "right"]
    visible = " ".join(line.text for page in pages for line in page.lines)
    assert "One marker | in prose. A second marker | in prose." in visible


def test_dossier_keeps_excerpt_labels_with_their_quotation(monkeypatch):
    body = "\n\n".join(
        f"**Line {number}**\n\n> **Passage {number}**\n>\n> Quotation for {number}."
        for number in range(24)
    )
    _, _, pages = captured_layout(
        monkeypatch, dossier_pdf, title="Synthetic excerpts", revision_label="Version 1",
        language="en", body=body, choice=CHOSEN,
    )
    assert len(pages) > 1
    page_by_text = {line.text: page for page, item in enumerate(pages) for line in item.lines}
    for number in range(24):
        assert page_by_text[f"Line {number}"] == page_by_text[f"Passage {number}"]
        assert page_by_text[f"Line {number}"] == page_by_text[f"Quotation for {number}."]


def test_pdf_places_follow_selected_saved_revision(monkeypatch, tmp_path):
    api.init(tmp_path, title="Synthetic geographic notes")
    dossier = api.create_dossier(tmp_path, "Synthetisches Dossier", "## Notizen\n\nText.",
                                 language="de", geography=geography())
    identifier = dossier["dossier_id"]
    current_geography = geography()
    current_geography["features"] = current_geography["features"][:1]
    revise_record(tmp_path, "dossier", identifier, {"language": "fr", "geography": current_geography})

    def pdf_for_version(revision):
        rendered = compose_dossier_pdf(tmp_path, Reference(id=identifier, revision=revision))
        assert rendered is not None
        return rendered[1]

    _, _, historical = captured_layout(monkeypatch, pdf_for_version, revision=1)
    _, _, current = captured_layout(monkeypatch, pdf_for_version, revision=2)

    historical_text = " ".join(line.text for page in historical for line in page.lines)
    current_text = " ".join(line.text for page in current for line in page.lines)
    for value in ("Fassung 1", "Orte und Wege", "Synthetic gate", "Basalt archway", "1924",
                  "13,4°", "52,5°", "Canal journey", "≈ 1,30 km", "Departure → Arrival",
                  "Marshland", "Unlocated estate", "Großkreisabschnitte"):
        assert value in historical_text
    assert "Orte und Wege" in [title for page in historical for title, _y in page.bookmarks]
    assert "Version 2" in current_text and "Orte und Wege" not in current_text
    assert "Lieux et trajets" in current_text and "1 localisé · 0 non situé · 1 au total" in current_text
    assert "Canal journey" not in current_text
