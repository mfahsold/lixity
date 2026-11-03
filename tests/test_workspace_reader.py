"""Optional dossier reads remain bound to the manuscript shown in an older tab."""

from urllib.parse import urlencode

import pytest

from lixity.research import api
from lixity.server.pdf_context import manuscript_pdf_token
from tests.support import LoopbackServer, make_handler, send


@pytest.fixture
def reader_server(tmp_path):
    api.init(tmp_path, title="Synthetic project", language="en")
    dossier = api.create_dossier(tmp_path, title="Synthetic dossier", body="Synthetic research notes.")
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic novel\n\n## Chapter\n\nA synthetic manuscript paragraph.\n")

    handler = make_handler(tmp_path, source_input=manuscript, research_dir=tmp_path,
                           title="Synthetic project")
    handler.refresh()
    server = LoopbackServer(handler).start()
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
        language=handler.language, title=handler.title, thresholds=handler.thresholds)
    try:
        yield server.port, tmp_path, handler, token, dossier["dossier_id"]
    finally:
        server.close()


def read(port, query):
    response = send(port, "/api/research/dossiers?" + urlencode(query, doseq=True), timeout=10)
    return response.status, response.json


def contents(project):
    return {str(path.relative_to(project)): path.read_bytes() for path in project.rglob("*") if path.is_file()}


def test_context_bound_dossier_list_and_reader_preserve_legacy_data_and_files(reader_server):
    port, project, _handler, token, dossier_id = reader_server
    before = contents(project)
    legacy_status, legacy = read(port, {})
    status, data = read(port, {"project_token": token})
    assert legacy_status == status == 200 and data == legacy
    legacy_status, legacy = read(port, {"id": dossier_id})
    status, data = read(port, {"id": dossier_id, "project_token": token})
    assert legacy_status == status == 200 and data == legacy
    assert data["body"] == "Synthetic research notes."
    assert contents(project) == before


def test_old_tab_cannot_mix_its_manuscript_with_another_selection(reader_server):
    port, project, handler, token, dossier_id = reader_server
    before = contents(project)
    with handler._workspace_lock:
        handler.title = "Another selected title"
    for query in ({"project_token": token}, {"id": dossier_id, "project_token": token}):
        status, data = read(port, query)
        assert status == 409 and not data["ok"]
        assert "dossiers" not in data and "body" not in data
    assert read(port, {"id": dossier_id})[0] == 200
    assert contents(project) == before


@pytest.mark.parametrize("token", ["", "not-a-token", ["a" * 64, "b" * 64]])
def test_malformed_context_token_is_an_explicit_error(reader_server, token):
    port, project, _handler, _token, _dossier_id = reader_server
    before = contents(project)
    status, data = read(port, {"project_token": token})
    assert status == 400 and not data["ok"]
    assert contents(project) == before


def test_reading_controls_renders_teleprompter_button():
    from lixity.style_profile import ChapterProfile
    from lixity.ui.manuscript_reader import reading_controls

    chapters = [ChapterProfile(
        num=1, title="Erstes Kapitel", start_line=1, end_line=10, words=100, paragraphs=5,
        present_hits=10, past_hits=10, dominant="past", flagged=0, asl=15.0, dialog_pct=0.2, function_word_pct=0.4,
    )]
    labels = {
        "reading_chapter": "Kapitel",
        "reading_appearance": "Darstellung",
        "reading_size": "Textgröße",
        "reading_smaller": "Kleiner",
        "reading_larger": "Größer",
        "reading_width": "Breite",
        "reading_narrow": "Schmal",
        "reading_standard": "Standard",
        "reading_wide": "Breit",
        "reading_spacing": "Zeilenabstand",
        "reading_compact": "Kompakt",
        "reading_relaxed": "Großzügig",
        "reading_shortcuts": "Tastatur",
        "reading_shortcut_actions": "Aktionen",
        "reading_shortcut_search": "Suche",
        "reading_shortcut_close": "Schließen",
        "reading_focus": "Fokusmodus",
        "reading_help_focus": "Fokusmodus Hilfe",
        "reading_teleprompter": "Teleprompter",
        "reading_help_teleprompter": "Teleprompter Hilfe",
        "reading_analysis": "Analyse",
        "reading_help_analysis": "Analyse Hilfe",
        "reading_on": "An",
        "reading_off": "Aus",
        "reading_read": "Lesen",
        "reading_inspect": "Prüfen",
    }
    html_out = reading_controls(chapters, labels)
    assert 'id="reader-teleprompter"' in html_out
    assert 'aria-label="Teleprompter"' in html_out
    assert '<kbd>P</kbd>' in html_out

