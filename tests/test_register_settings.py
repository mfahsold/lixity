"""Chapter register settings stay project-local and survive empty workspaces."""

import json
from pathlib import Path

import pytest

from lixity import config
from lixity.config import load_project_config
from lixity.models import CorpusConfig
from lixity.server.pdf_context import project_settings_token
from lixity.server.views import build_server_dashboard
from tests.support import HtmlControls, recording_handler


def test_register_settings_load_only_from_the_explicit_project(tmp_path: Path, monkeypatch):
    user = tmp_path / "user.toml"
    user.write_text('z_mild = 3.0\n[register_profiles.global_voice]\n[chapter_registers]\n"1" = "global_voice"\n')
    monkeypatch.setattr(config.os.path, "expanduser", lambda value: str(user))
    parent = tmp_path / "projects"
    parent.mkdir()
    (parent / "lixity.toml").write_text(
        'fdr_q = 0.03\n[register_profiles.parent_voice]\n[chapter_registers]\n"1" = "parent_voice"\n')
    (parent / "pyproject.toml").write_text(
        '[tool.lixity.register_profiles.pyparent_voice]\n[tool.lixity.chapter_registers]\n"1" = "pyparent_voice"\n')
    project = parent / "selected"
    project.mkdir()
    loaded = config.load_project_config(project)
    assert "register_profiles" not in loaded
    assert "chapter_registers" not in loaded
    assert loaded["z_mild"] == 3.0
    assert loaded["fdr_q"] == 0.03
    (project / "pyproject.toml").write_text(
        '[tool.lixity.register_profiles.local_voice]\n[tool.lixity.chapter_registers]\n"1" = "local_voice"\n')
    expected = {"register_profiles": {"local_voice": {}}, "chapter_registers": {"1": "local_voice"}}
    loaded = config.load_project_config(project)
    assert {key: loaded[key] for key in expected} == expected
    manuscript = project / "story.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    assert config.load_project_config(manuscript)["chapter_registers"] == {"1": "local_voice"}
    drafts = project / "drafts"
    drafts.mkdir()
    assert "register_profiles" not in config.load_project_config(drafts)
    assert "chapter_registers" not in config.load_project_config(drafts)
    monkeypatch.chdir(project)
    assert "register_profiles" not in config.load_project_config()
    assert "chapter_registers" not in config.load_project_config()


@pytest.mark.parametrize("selected", [None, "empty.md"])
def test_empty_workspace_preserves_register_editor_settings(tmp_path: Path, selected):
    (tmp_path / "lixity.toml").write_text(
        '[register_profiles.voice]\nasl = [3, 12]\n[chapter_registers]\n"1" = "voice"\n')
    source = tmp_path / selected if selected else None
    if source:
        source.write_text("")
    html, _info = build_server_dashboard(str(source) if source else None, project_root=tmp_path)
    initial = json.loads(HtmlControls(html).elements["register-editor"]["data-initial"])
    assert initial["chapter_registers"] == {"1": "voice"}
    assert initial["register_profiles"] == {"voice": {"asl": [3, 12]}}


@pytest.mark.parametrize("separator", ["\n", "\r", "\t", "\x00", "\x7f", "\x85", "\u2028", "\u2029", "\ud800"])
def test_register_names_and_selectors_reject_non_roundtrippable_text(separator):
    name = "Voice" + separator + "A"
    with pytest.raises(ValueError):
        CorpusConfig(register_profiles={name: {}})
    with pytest.raises(ValueError):
        CorpusConfig(register_profiles={"voice": {}}, chapter_registers={name: "voice"})


def test_register_settings_save_nested_profiles_and_rebuild_before_commit(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("\n\n".join(
        f"## Chapter {number}\n\n" + "The rain falls softly across the quiet garden. " * 20
        for number in range(1, 6)))
    original = '# Preserve unrelated data\ntitle = "Synthetic"\n[motifs]\nrain = "rain"\n'
    path = tmp_path / "lixity.toml"
    path.write_text(original)
    handler = recording_handler(tmp_path, source_input=tmp_path / "manuscript.md",
                                dashboard_html="Old HTML")
    token = project_settings_token(tmp_path, str(manuscript))
    profiles = {'Voice "A"': {"asl": {"lower": 5, "upper": 12}}}
    assignments = {"1": 'Voice "A"'}
    handler._handle_settings({"register_profiles": profiles, "chapter_registers": assignments,
                              "project_token": token})
    assert handler.response[0] == 200, handler.response
    saved = load_project_config(tmp_path)
    assert saved["register_profiles"] == profiles
    assert saved["chapter_registers"] == assignments
    assert saved["motifs"] == {"rain": "rain"}
    assert path.read_text().startswith(original)
    assert 'id="settings-registers"' in handler.dashboard_html
    assert 'data-register="Voice &quot;A&quot;"' in handler.dashboard_html
    assert handler.response[1]["project_token"] != token
    # Reload and replace a normal nested TOML table without losing other tables.
    path.write_text(original + '[register_profiles."Old voice"]\nasl = [4, 8]\n'
                    '[chapter_registers]\n"2" = "Old voice"\n')
    handler._handle_settings({"register_profiles": profiles, "chapter_registers": assignments,
                              "project_token": project_settings_token(tmp_path, str(manuscript))})
    assert handler.response[0] == 200, handler.response
    assert load_project_config(tmp_path)["register_profiles"] == profiles
    assert load_project_config(tmp_path)["motifs"] == {"rain": "rain"}



@pytest.mark.parametrize("changes", [
    {"register_profiles": {"voice": {"asl": [12, 3]}}, "chapter_registers": {"1": "voice"}},
    {"register_profiles": {}, "chapter_registers": {"1": "missing"}},
])
def test_register_settings_reject_invalid_or_stale_updates_without_writing(tmp_path: Path, changes):
    (tmp_path / "manuscript.md").write_text("## Opening\n\nSynthetic prose.\n")
    path = tmp_path / "lixity.toml"
    path.write_text('title = "Synthetic"\n')
    original = path.read_bytes()
    handler = recording_handler(tmp_path, source_input=tmp_path / "manuscript.md",
                                dashboard_html="Old HTML")
    handler._handle_settings({**changes, "project_token": project_settings_token(tmp_path, handler.source_input)})
    assert handler.response[0] == 400
    assert path.read_bytes() == original
    assert handler.dashboard_html == "Old HTML"
    handler._handle_settings({"register_profiles": {}, "chapter_registers": {}, "project_token": "stale"})
    assert handler.response[0] == 409
    assert path.read_bytes() == original



@pytest.mark.parametrize("relative_source", ["drafts/manuscript.md", "missing.md"])
def test_selected_root_registers_survive_nested_or_missing_manuscript(tmp_path: Path, relative_source: str):
    source = tmp_path / relative_source
    if relative_source.startswith("drafts/"):
        source.parent.mkdir()
        source.write_text("## Opening\n\n" + "Rain falls across the garden. " * 30)
    (tmp_path / "lixity.toml").write_text(
        '[register_profiles.voice]\nasl = [4, 8]\n[chapter_registers]\n"1" = "voice"\n')
    html, _ = build_server_dashboard(str(source), project_root=tmp_path)
    initial = json.loads(HtmlControls(html).elements["register-editor"]["data-initial"])
    assert initial == {"register_profiles": {"voice": {"asl": [4, 8]}},
                       "chapter_registers": {"1": "voice"}}
    if source.exists():
        assert 'data-register="voice"' in html



def test_partial_register_save_preserves_explicit_root_pyproject_profiles(tmp_path: Path):
    (tmp_path / "manuscript.md").write_text("## One\n\nA scene.\n\n## Two\n\nAnother scene.")
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.lixity.register_profiles.voice]\nasl = [4, 8]\n'
                         '[tool.lixity.chapter_registers]\n"1" = "voice"\n')
    original = pyproject.read_bytes()
    handler = recording_handler(tmp_path, source_input=tmp_path / "manuscript.md",
                                dashboard_html="Old HTML")
    handler._handle_settings({"chapter_registers": {"2": "voice"},
                              "project_token": project_settings_token(tmp_path, handler.source_input)})
    assert handler.response[0] == 200, handler.response
    saved = load_project_config(tmp_path)
    assert saved["register_profiles"] == {"voice": {"asl": [4, 8]}}
    assert saved["chapter_registers"] == {"2": "voice"}
    assert pyproject.read_bytes() == original
