"""Settings prepare their complete view before publishing root metadata/state."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.config import load_project_config, prepare_project_settings
from lixity.server.pdf_context import project_settings_token
from lixity.server.views import build_server_dashboard
from tests.support import recording_handler


def handler_for(root: Path):
    return recording_handler(root, source_input=root / "manuscript.md",
                             dashboard_html="Old HTML", dashboard_info={"old": True})


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


@pytest.mark.parametrize("save_defaults", [None, False, True])
def test_analysis_defaults_persist_only_with_explicit_opt_in(tmp_path: Path, save_defaults):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic\n\n## One\n\nA scene.\n")
    path = tmp_path / "lixity.toml"
    original = 'language = "de"\nfdr_q = 0.01\nmin_chapters = 7\n'
    path.write_text(original)
    handler = handler_for(tmp_path)
    payload = {"language": "auto", "fdr_q": 0.013000000000003,
               "project_token": project_settings_token(tmp_path, str(manuscript))}
    if save_defaults is not None:
        payload["save_analysis_defaults"] = save_defaults
    handler._handle_settings(payload)
    assert handler.response[0] == 200, handler.response
    assert handler.language == "auto"
    assert handler.thresholds.fdr_q == 0.013000000000003
    if save_defaults:
        saved = load_project_config(tmp_path)
        assert saved["language"] == "auto"
        assert saved["fdr_q"] == 0.013000000000003
        assert saved["min_chapters"] == 7
        assert "z_mild" not in saved, "Unposted active thresholds must not become project defaults"
    else:
        assert path.read_text() == original
    assert manuscript.read_text() == "# Synthetic\n\n## One\n\nA scene.\n"


@pytest.mark.parametrize("token", [None, "stale"])
def test_saving_analysis_defaults_requires_current_project_context(tmp_path: Path, token):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = handler_for(tmp_path)
    payload = {"language": "fr", "save_analysis_defaults": True}
    if token is not None:
        payload["project_token"] = token
    handler._handle_settings(payload)
    assert handler.response[0] == 409
    assert handler.language == "en"
    assert handler.dashboard_html == "Old HTML"
    assert not (tmp_path / "lixity.toml").exists()


@pytest.mark.parametrize("change", ["lixity.toml", "pyproject.toml", "selected_project"])
def test_analysis_defaults_reject_actual_changed_project_context(tmp_path: Path, change: str):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = handler_for(tmp_path)
    token = project_settings_token(tmp_path, str(manuscript))
    if change == "selected_project":
        other = tmp_path / "other"
        other.mkdir()
        other_source = other / "manuscript.md"
        other_source.write_text("## One\n\nAnother synthetic scene.\n")
        handler.__class__.workspace_root = str(other)
        handler.__class__.source_input = str(other_source)
    else:
        (tmp_path / change).write_text('language = "de"\n' if change == "lixity.toml"
                                      else '[tool.lixity]\nlanguage = "de"\n')
    handler._handle_settings({"language": "fr", "save_analysis_defaults": True, "project_token": token})
    assert handler.response[0] == 409
    assert handler.language == "en"
    assert handler.dashboard_html == "Old HTML"
    assert load_project_config(tmp_path).get("language") == (None if change == "selected_project" else "de")
    if change == "selected_project":
        assert not (other / "lixity.toml").exists()


def test_analysis_defaults_cannot_create_a_project_from_an_idle_workspace(tmp_path: Path):
    handler = handler_for(tmp_path)
    handler.__class__.source_input = None
    handler._handle_settings({"language": "fr", "save_analysis_defaults": True})
    assert handler.response[0] == 409
    assert handler.language == "en"
    assert not (tmp_path / "lixity.toml").exists()


@pytest.mark.parametrize("invalid", ["true", 1, None, []])
def test_analysis_defaults_opt_in_requires_a_boolean(tmp_path: Path, invalid):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = handler_for(tmp_path)
    handler._handle_settings({"language": "fr", "save_analysis_defaults": invalid,
                              "project_token": project_settings_token(tmp_path, str(manuscript))})
    assert handler.response[0] == 400
    assert handler.language == "en"
    assert not (tmp_path / "lixity.toml").exists()


@pytest.mark.parametrize("invalid", [None, False, 0, "", [], {}])
def test_saving_a_language_default_cannot_turn_invalid_input_into_the_active_language(tmp_path: Path, invalid):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = handler_for(tmp_path)
    handler._handle_settings({"language": invalid, "save_analysis_defaults": True,
                              "project_token": project_settings_token(tmp_path, str(manuscript))})
    assert handler.response[0] == 400
    assert handler.language == "en"
    assert not (tmp_path / "lixity.toml").exists()


def test_saved_analysis_defaults_validate_project_values_and_keep_session_on_failure(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    path = tmp_path / "lixity.toml"
    original = 'z_mild = 5.0\nz_strong = 6.0\n'
    path.write_text(original)
    handler = handler_for(tmp_path)
    handler._handle_settings({"z_strong": 4.0, "save_analysis_defaults": True,
                              "project_token": project_settings_token(tmp_path, str(manuscript))})
    assert handler.response[0] == 400
    assert path.read_text() == original
    assert handler.thresholds.z_strong == 3.5
    assert handler.dashboard_html == "Old HTML"


@pytest.mark.parametrize("failure", ["decode", "render", "write"])
@pytest.mark.parametrize("save_defaults", [False, True])
def test_failed_settings_preparation_or_commit_keeps_original_data_and_session(
    tmp_path: Path, failure: str, save_defaults: bool,
):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_bytes(b"# Synthetic\n\n## One\n\nA scene.\n" if failure != "decode" else b"\xff\xfe")
    path = tmp_path / "lixity.toml"
    original = b'author_name = "Before"\n'
    path.write_bytes(original)
    handler = handler_for(tmp_path)
    payload = {"author_name": "After", "language": "de"}
    if save_defaults:
        payload.update(save_analysis_defaults=True,
                       project_token=project_settings_token(tmp_path, str(manuscript)))
    if failure == "render":
        context = patch("lixity.server.views.render_analysis", side_effect=ValueError("Synthetic render failure"))
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


@pytest.mark.parametrize("save_defaults", [False, True])
def test_config_change_between_token_check_and_preparation_is_not_overwritten(tmp_path: Path, save_defaults: bool):
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

    changes = ({"save_analysis_defaults": True, "fdr_q": 0.02} if save_defaults
               else {"publication": {"publisher_name": "Before", "year": "2026"}})
    with patch("lixity.server.routes_project.prepare_project_settings", side_effect=prepare_after_edit):
        handler._handle_settings({**changes, "project_token": token, "language": "de"})
    assert handler.response[0] == 409
    assert path.read_text() == concurrent
    assert handler.language == "en"
    assert handler.dashboard_html == "Old HTML"
