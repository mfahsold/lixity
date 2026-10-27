"""Public migration review, backup and stale-preview boundaries."""

import hashlib
import json
import zipfile

import pytest

from lixity.cli import main


def _project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "source.md").write_text("## Synthetic\n\nA quiet river flows.\n")
    (project / "lixity.toml").write_text('''language="en"
manuscript="source.md"
[audio]
schema_version="lixity-audio-settings/1"
selected="narrator"
[audio.profiles.narrator]
name="Narrator"
engine="piper"
language="en"
voice="en_US-lessac-medium"
speed=1.2
''')
    return project


def test_cli_preview_apply_and_backup_preserve_source(tmp_path, capsys):
    project = _project(tmp_path)
    source = project / "source.md"
    original_source = source.read_bytes()
    config = project / "lixity.toml"
    original_config = config.read_bytes()
    arguments = ["audio-migrate", "--project", str(project), "--replace", "narrator=Ryan"]
    assert main(arguments) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["applied"] is False
    assert config.read_bytes() == original_config
    backup = tmp_path / "before-audio.zip"
    assert main([*arguments, "--apply", "--backup", str(backup),
                 "--expected-snapshot", preview["snapshot"]]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is True
    assert source.read_bytes() == original_source
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("lixity.toml") == original_config
        assert "source.md" not in archive.namelist()
    from lixity.config import read_explicit_project_config
    from lixity.speech_profiles import resolve_audio_profile

    profile = resolve_audio_profile(read_explicit_project_config(project))
    assert (profile.engine, profile.voice, profile.speed) == ("qwen3", "Ryan", 1.0)


def test_cli_rejects_stale_review_without_backup_or_config_write(tmp_path, capsys):
    project = _project(tmp_path)
    arguments = ["audio-migrate", "--project", str(project), "--replace", "narrator=Ryan"]
    assert main(arguments) == 0
    preview = json.loads(capsys.readouterr().out)
    (project / "source.md").write_text("## Synthetic\n\nA changed synthetic passage.\n")
    config = project / "lixity.toml"
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    backup = tmp_path / "stale.zip"
    assert main([*arguments, "--apply", "--backup", str(backup),
                 "--expected-snapshot", preview["snapshot"]]) == 1
    assert "snapshot changed" in capsys.readouterr().err
    assert not backup.exists()
    assert hashlib.sha256(config.read_bytes()).hexdigest() == digest


def test_cli_apply_requires_review_token_and_backup(tmp_path):
    project = _project(tmp_path)
    with pytest.raises(SystemExit) as error:
        main(["audio-migrate", "--project", str(project), "--replace", "narrator=Ryan", "--apply"])
    assert error.value.code == 2
