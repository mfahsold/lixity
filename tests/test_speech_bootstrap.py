"""Explicit external voices do not depend on native default language support."""

import json
import zipfile

import pytest

from lixity.cli import main
from lixity.config import load_project_config
from lixity.speech_migration import prepare_schema4_migration
from lixity.speech_profiles import parse_audio_settings, resolve_audio_profile


@pytest.fixture
def dutch_project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    (root / "lixity.toml").write_text('language="nl"\nmanuscript="draft.md"\n')
    (root / "draft.md").write_text("De rivier stroomt.")

    def forbidden(*args, **kwargs):
        raise AssertionError("Planning must not synthesize or load references")

    monkeypatch.setattr("lixity.speech.render_speech_audio", forbidden)
    monkeypatch.setattr("lixity.speech_references.references_for_plan", forbidden)
    return root


@pytest.mark.parametrize("upgraded", [False, True])
@pytest.mark.parametrize("explicit_language", [False, True])
def test_explicit_external_cli_preserves_dutch_without_native_default(dutch_project, tmp_path, capsys, upgraded, explicit_language):
    if upgraded:
        prepare_schema4_migration(dutch_project).apply(tmp_path / "backup.zip")
    before = {p.name: p.read_bytes() for p in dutch_project.iterdir()}
    args = ["audio-export-plan", "--project", str(dutch_project),
            "--engine", "openai-compatible", "--base-url", "http://127.0.0.1:8000/v1",
            "--model", "synthetic", "--voice", "synthetic"]
    assert main([*args, *(["--language", "nl"] if explicit_language else [])]) == 0
    result = json.loads(capsys.readouterr().out)
    row = result["segments"][0]
    assert row["profile"]["engine"] == "openai-compatible"
    assert row["profile"]["language"] == "nl"
    assert row["profile"]["speed"] == 1.2
    assert row["text"] == "De rivier stroomt."
    assert {p.name: p.read_bytes() for p in dutch_project.iterdir()} == before


def test_schema4_bootstrap_is_unconfigured_and_backs_up_exact_settings(dutch_project, tmp_path):
    original = (dutch_project / "lixity.toml").read_bytes()
    source = (dutch_project / "draft.md").read_bytes()
    candidate = prepare_schema4_migration(dutch_project)
    summary = candidate.public_dict()
    assert summary["source_schema"] is None
    assert summary["retained_profile_count"] == 0
    assert summary["creates_default_profile"] is False
    assert summary["configuration_required"] is True
    assert (dutch_project / "lixity.toml").read_bytes() == original
    candidate.apply(tmp_path / "backup.zip")
    with zipfile.ZipFile(tmp_path / "backup.zip") as archive:
        assert archive.read("lixity.toml") == original
    settings = load_project_config(dutch_project)
    assert settings["language"] == "nl"
    assert settings["audio"]["selected"] == ""
    assert settings["audio"]["profiles"] == {}
    with pytest.raises(ValueError, match="No audio profile is configured"):
        resolve_audio_profile(settings, language="nl")
    assert (dutch_project / "draft.md").read_bytes() == source


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_only_schema4_allows_explicit_unconfigured_state(version):
    raw = {"schema_version": f"lixity-audio-settings/{version}", "selected": "", "profiles": {}}
    if version == 4:
        assert parse_audio_settings(raw).profiles == {}
    else:
        with pytest.raises(ValueError):
            parse_audio_settings(raw)
    with pytest.raises(ValueError):
        parse_audio_settings({**raw, "selected": "missing"})


def test_supported_default_is_unchanged_and_migration_explains_it(dutch_project):
    path = dutch_project / "lixity.toml"
    path.write_text(path.read_text().replace('"nl"', '"en"'))
    candidate = prepare_schema4_migration(dutch_project)
    summary = candidate.public_dict()
    assert summary["source_schema"] is None
    assert summary["retained_profile_count"] == 0
    assert summary["creates_default_profile"] is True
    assert summary["configuration_required"] is False
    assert resolve_audio_profile(None, language="en").voice == "Ryan"
    with pytest.raises(ValueError, match="Unsupported Qwen language"):
        resolve_audio_profile(None, language="nl")


def test_external_bootstrap_rejects_unknown_profile_and_missing_binding(dutch_project, capsys):
    args = ["audio-export-plan", "--project", str(dutch_project), "--engine", "openai-compatible",
            "--base-url", "http://127.0.0.1:8000/v1", "--model", "synthetic"]
    assert main(args) == 1
    assert "explicit --voice" in capsys.readouterr().err
    assert main([*args, "--voice", "synthetic", "--profile", "missing"]) == 1
    assert "Unknown audio profile" in capsys.readouterr().err
