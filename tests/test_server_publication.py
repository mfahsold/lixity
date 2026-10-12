"""Settings prepare their complete view before publishing root metadata/state."""

from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import pytest

from lixity.config import load_project_config, prepare_project_settings
from lixity.server.handler import LixityServerHandler
from lixity.server.pdf_context import project_settings_token
from lixity.server.views import build_server_dashboard


def handler_for(root: Path):
    class Handler(LixityServerHandler):
        workspace_root = str(root)
        source_input = str(root / "manuscript.md")
        exports_dir = str(root / "exports")
        research_dir = None
        title = None
        title_custom = False
        language = "en"
        dashboard_html = "Old HTML"
        dashboard_info: ClassVar[dict] = {"old": True}

        def _json(self, payload, code=200):
            self.response = code, payload

    return object.__new__(Handler)


def test_settings_save_prepares_complete_metadata_and_returns_fresh_context(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic\n\n## One\n\nA simple synthetic scene.\n")
    handler = handler_for(tmp_path)
    previous = project_settings_token(tmp_path, str(manuscript))
    handler._handle_settings({
        "title": "Saved Book", "author_name": "Synthetic Writer", "language": "de",
        "publication": {"enabled": True, "publisher_name": "Synthetic Publisher"},
        "project_token": previous,
    })
    assert handler.response[0] == 200
    saved = load_project_config(tmp_path)
    assert saved["title"] == "Saved Book"
    assert saved["publication"]["publisher_name"] == "Synthetic Publisher"
    current = project_settings_token(tmp_path, str(manuscript))
    assert handler.response[1]["project_token"] == current != previous
    assert 'value="Saved Book"' in handler.dashboard_html
    assert 'value="Synthetic Publisher"' in handler.dashboard_html
    assert current in handler.dashboard_html


@pytest.mark.parametrize("failure", ["decode", "render", "write"])
def test_failed_settings_preparation_or_commit_keeps_original_data_and_session(tmp_path: Path, failure: str):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_bytes(b"# Synthetic\n\n## One\n\nA scene.\n" if failure != "decode" else b"\xff\xfe")
    path = tmp_path / "lixity.toml"
    original = b'author_name = "Before"\n'
    path.write_bytes(original)
    handler = handler_for(tmp_path)
    payload = {"author_name": "After", "language": "de"}
    if failure == "render":
        context = patch("lixity.server.views.render_dashboard", side_effect=ValueError("Synthetic render failure"))
    elif failure == "write":
        context = patch("lixity.io.os.replace", side_effect=OSError("Synthetic replace failure"))
    else:
        from contextlib import nullcontext
        context = nullcontext()
    with context:
        handler._handle_settings(payload)
    assert handler.response[0] == 400
    assert path.read_bytes() == original
    assert handler.language == "en"
    assert handler.title is None
    assert handler.dashboard_html == "Old HTML"
    assert handler.dashboard_info == {"old": True}


def test_publication_save_refuses_missing_stale_and_changed_root_context(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic\n\n## One\n\nA scene.\n")
    handler = handler_for(tmp_path)
    payload = {"publication": {"enabled": True}, "language": "de"}
    handler._handle_settings(payload)
    assert handler.response[0] == 409
    assert handler.language == "en"
    old = project_settings_token(tmp_path, str(manuscript))
    (tmp_path / "lixity.toml").write_text('title = "Concurrent"\n')
    handler._handle_settings({**payload, "project_token": old})
    assert handler.response[0] == 409
    assert load_project_config(tmp_path)["title"] == "Concurrent"


def test_bad_publication_config_does_not_hide_manuscript_analysis(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic\n\n## One\n\nA scene.\n")
    (tmp_path / "lixity.toml").write_text(
        '[publication]\nyear = "202X"\npublisher_name = "Synthetic preserved publisher"\n'
        'publisher_address = "Synthetic preserved address"\n')
    html, info = build_server_dashboard(str(manuscript), project_root=tmp_path)
    assert info["chapters"] == 1
    assert "four-digit year" in html
    for value in ("202X", "Synthetic preserved publisher", "Synthetic preserved address"):
        assert value in html, "Repairing one field must not hide the rest of the entered metadata"


def test_research_only_publication_save_does_not_persist_display_title(tmp_path: Path):
    (tmp_path / "research").mkdir()
    handler = handler_for(tmp_path)
    handler.__class__.source_input = None
    handler.__class__.research_dir = str(tmp_path)
    token = project_settings_token(tmp_path, None)
    handler._handle_settings({"publication": {"enabled": True, "publisher_name": "Synthetic Publisher"},
                              "project_token": token})
    assert handler.response[0] == 200
    settings = load_project_config(tmp_path)
    assert "title" not in settings
    assert "author_name" not in settings
    assert settings["publication"]["publisher_name"] == "Synthetic Publisher"


def test_config_change_between_token_check_and_preparation_is_not_overwritten(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic\n\n## One\n\nA scene.\n")
    path = tmp_path / "lixity.toml"
    path.write_text('[publication]\npublisher_name = "Before"\n')
    handler = handler_for(tmp_path)
    token = project_settings_token(tmp_path, str(manuscript))
    concurrent = '[publication]\npublisher_name = "Concurrent"\n'

    def prepare_after_edit(root, changes):
        path.write_text(concurrent)
        return prepare_project_settings(root, changes)

    with patch("lixity.server.routes_project.prepare_project_settings", side_effect=prepare_after_edit):
        handler._handle_settings({"publication": {"publisher_name": "Before", "year": "2026"},
                                  "project_token": token, "language": "de"})
    assert handler.response[0] == 409
    assert path.read_text() == concurrent
    assert handler.language == "en"
    assert handler.dashboard_html == "Old HTML"
