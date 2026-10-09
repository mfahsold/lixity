"""Settings retain project author identity without rewriting manuscript data."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.server.handler import LixityServerHandler
from lixity.server.views import build_server_dashboard


def test_loaded_project_view_uses_author_and_read_only_identity_check(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    text = "# Synthetic Project\n\nvon Synthetic Author\n\n## Scene\n\nPublic synthetic prose.\n"
    manuscript.write_text(text, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert 'id="set-author-name"' in html
    assert 'value="Synthetic Author"' in html
    assert info["identity_check"]["author_name"]["status"] == "matched"
    assert info["identity_check"]["title"]["status"] == "matched"
    assert manuscript.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("author", ["Synthetic Author", "", "Another Author"])
def test_settings_save_persists_only_author_on_loaded_project(tmp_path: Path, author: str):
    manuscript = tmp_path / "manuscript.md"
    text = "# Synthetic Project\n\n## Scene\n\nPublic synthetic prose.\n"
    manuscript.write_text(text, encoding="utf-8")

    class Handler(LixityServerHandler):
        workspace_root = str(tmp_path)
        source_input = str(manuscript)
        title = "Synthetic Project"
        title_custom = False
        language = "en"

        @classmethod
        def refresh(cls):
            cls.refreshed = True

        def _json(self, payload, code=200):
            self.response = code, payload

    handler = object.__new__(Handler)
    before = Handler.thresholds
    handler._handle_settings({"author_name": author, "language": "de"})
    assert handler.response[0] == 200
    from lixity.config import load_project_config
    assert load_project_config(tmp_path)["author_name"] == author
    assert Handler.thresholds == before
    assert Handler.title == "Synthetic Project"
    assert manuscript.read_text(encoding="utf-8") == text


def test_no_project_rejects_author_persistence_without_mutating_session(tmp_path: Path):
    # An archive in the idle working directory is not an explicitly open project.
    (tmp_path / "research").mkdir()
    class Handler(LixityServerHandler):
        workspace_root = str(tmp_path)
        source_input = None
        research_dir = None
        language = "en"

        def _json(self, payload, code=200):
            self.response = code, payload

    handler = object.__new__(Handler)
    handler._handle_settings({"author_name": "Synthetic Author", "language": "de"})
    assert handler.response[0] == 400
    assert Handler.language == "en"
    assert not (tmp_path / "lixity.toml").exists()


def test_explicit_research_only_project_can_save_author(tmp_path: Path):
    (tmp_path / "research").mkdir()

    class Handler(LixityServerHandler):
        workspace_root = str(tmp_path)
        source_input = None
        research_dir = str(tmp_path)

    assert Handler.get_author_project_root() == tmp_path


def test_project_identity_stays_at_selected_root_for_nested_manuscript(tmp_path: Path):
    nested = tmp_path / "exports" / "manuscripts"
    nested.mkdir(parents=True)
    manuscript = nested / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\nby Project Writer\n\n## Scene\n\nSynthetic prose.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Project Writer"\n', encoding="utf-8")
    (nested / "lixity.toml").write_text('author_name = "Other Writer"\n', encoding="utf-8")

    class Handler(LixityServerHandler):
        workspace_root = str(tmp_path)
        source_input = str(manuscript)

    assert Handler.get_author_project_root() == tmp_path
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", project_root=tmp_path)
    assert 'value="Project Writer"' in html
    assert info["identity_check"]["author_name"]["status"] == "matched"


def test_invalid_configured_author_does_not_abort_analysis_view(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\n## Scene\n\nPublic synthetic prose.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text("author_name = true\n", encoding="utf-8")
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert "Synthetic Project" in html
    assert info["identity_check"]["author_name"]["status"] == "unsupported"


def test_missing_manuscript_keeps_project_author_without_claiming_a_match(tmp_path: Path):
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    html, info = build_server_dashboard(str(tmp_path / "missing.md"), title="Synthetic Project", language="en")
    assert 'value="Synthetic Author"' in html
    assert info["identity_check"]["author_name"]["status"] == "unavailable"


def test_unreadable_manuscript_reports_unavailable_identity(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\nby Synthetic Author\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    with patch("builtins.open", side_effect=PermissionError("Synthetic read failure")):
        _, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert info["identity_check"]["title"]["status"] == "unavailable"
    assert info["identity_check"]["author_name"]["status"] == "unavailable"
