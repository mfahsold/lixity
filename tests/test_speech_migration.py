"""Explicit audio replacement candidates and private, non-overwriting backups."""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.config import load_project_config
from lixity.speech_migration import prepare_audio_migration


@pytest.fixture
def legacy_project(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "lixity.toml").write_text('''# Keep this comment
manuscript = "manuscript.md"
[custom]
value = "Keep"
[audio]
schema_version = "lixity-audio-settings/1"
selected = "narrator"
[audio.profiles.narrator]
name = "Private profile name"
engine = "piper"
language = "de"
voice = "de_DE-thorsten-medium"
speed = 1.2
paragraph_pause = 0.7
scene_pause = 2.0
pronunciations = { "synthetic" = "example" }
''')
    (root / "pyproject.toml").write_text('[tool.lixity]\ntitle = "Synthetic project"\n')
    (root / "manuscript.md").write_text('# Synthetic\n\nA door opens.\n')
    return root


def test_dry_run_has_no_writes_or_private_configuration_in_summary(legacy_project: Path):
    before = {p.name: p.read_bytes() for p in legacy_project.iterdir()}
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    public = migration.public_dict()
    assert public["applied"] is False
    assert public["profiles"] == [{"profile_id": "narrator", "engine": "qwen3", "voice": "Ryan", "speed": 1.0}]
    assert "Private profile name" not in json.dumps(public)
    assert "A door opens" not in json.dumps(public)
    assert {p.name: p.read_bytes() for p in legacy_project.iterdir()} == before


def test_apply_backs_up_exact_configs_preserves_source_and_profile_controls(legacy_project: Path, tmp_path: Path):
    originals = {name: (legacy_project / name).read_bytes() for name in ("lixity.toml", "pyproject.toml", "manuscript.md")}
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    backup = tmp_path / "audio-backup.zip"
    assert migration.apply(backup)["applied"] is True
    with zipfile.ZipFile(backup) as archive:
        assert set(archive.namelist()) == {"lixity.toml", "pyproject.toml", "manifest.json"}
        assert archive.read("lixity.toml") == originals["lixity.toml"]
        assert archive.read("pyproject.toml") == originals["pyproject.toml"]
        assert json.loads(archive.read("manifest.json"))["snapshot"] == migration.public_dict()["snapshot"]
    profile = load_project_config(legacy_project)["audio"]["profiles"]["narrator"]
    assert profile["engine"] == "qwen3" and profile["voice"] == "Ryan" and profile["speed"] == 1.0
    assert profile["paragraph_pause"] == 0.7 and profile["scene_pause"] == 2.0
    assert profile["pronunciations"] == {"synthetic": "example"}
    assert profile["name"] == "Private profile name" and profile["instructions"] == ""
    assert '# Keep this comment\nmanuscript = "manuscript.md"\n' in (legacy_project / "lixity.toml").read_text()
    assert (legacy_project / "manuscript.md").read_bytes() == originals["manuscript.md"]


@pytest.mark.parametrize("changed", ["lixity.toml", "pyproject.toml", "manuscript.md"])
def test_apply_refuses_stale_configs_or_source_before_creating_backup(legacy_project: Path, tmp_path: Path, changed: str):
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    path = legacy_project / changed
    path.write_bytes(path.read_bytes() + b"\n# Concurrent\n")
    backup = tmp_path / "backup.zip"
    with pytest.raises(ValueError, match="changed"):
        migration.apply(backup)
    assert not backup.exists()
    assert load_project_config(legacy_project)["audio"]["profiles"]["narrator"]["engine"] == "piper"


def test_apply_never_overwrites_backup_and_rejects_backup_inside_project(legacy_project: Path, tmp_path: Path):
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    backup = tmp_path / "backup.zip"
    backup.write_bytes(b"Keep")
    with pytest.raises(ValueError, match="exists"):
        migration.apply(backup)
    assert backup.read_bytes() == b"Keep"
    with pytest.raises(ValueError, match="outside"):
        migration.apply(legacy_project / "backup.zip")
    assert not (legacy_project / "backup.zip").exists()


def test_source_change_while_backing_up_prevents_publication(legacy_project: Path, tmp_path: Path):
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    real_write = zipfile.ZipFile.writestr
    def changed_source(archive, *args, **kwargs):
        result = real_write(archive, *args, **kwargs)
        (legacy_project / "manuscript.md").write_text("# Concurrent source\n")
        return result
    with patch.object(zipfile.ZipFile, "writestr", changed_source), pytest.raises(ValueError, match="changed"):
        migration.apply(tmp_path / "backup.zip")
    assert load_project_config(legacy_project)["audio"]["profiles"]["narrator"]["engine"] == "piper"
    assert (tmp_path / "backup.zip").is_file()


def test_apply_failure_retains_verified_backup_and_original_project(legacy_project: Path, tmp_path: Path):
    original = (legacy_project / "lixity.toml").read_bytes()
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    backup = tmp_path / "backup.zip"
    with patch("lixity.io.os.replace", side_effect=OSError("Synthetic failure")), pytest.raises(OSError):
        migration.apply(backup)
    assert (legacy_project / "lixity.toml").read_bytes() == original
    with zipfile.ZipFile(backup) as archive:
        assert archive.read("lixity.toml") == original


def test_missing_replacements_never_prepare_writes(legacy_project: Path):
    before = (legacy_project / "lixity.toml").read_bytes()
    with pytest.raises(ValueError, match="explicit Qwen preset"):
        prepare_audio_migration(legacy_project, {})
    assert (legacy_project / "lixity.toml").read_bytes() == before


def test_migration_refuses_source_symlinks(legacy_project: Path, tmp_path: Path):
    source = legacy_project / "manuscript.md"
    outside = tmp_path / "outside.md"
    source.rename(outside)
    source.symlink_to(outside)
    with pytest.raises(ValueError):
        prepare_audio_migration(legacy_project, {"narrator": "Ryan"})


def test_source_selection_appearing_after_config_only_dryrun_is_stale(legacy_project: Path, tmp_path: Path):
    source = legacy_project / "manuscript.md"
    source.unlink()
    config = legacy_project / "lixity.toml"
    config.write_text(config.read_text().replace('manuscript = "manuscript.md"\n', ""))
    migration = prepare_audio_migration(legacy_project, {"narrator": "Ryan"})
    source.write_text("# New synthetic source\n")
    with pytest.raises(ValueError, match="changed"):
        migration.apply(tmp_path / "backup.zip")
    assert not (tmp_path / "backup.zip").exists()


@pytest.mark.parametrize("changed", [["--replace", "narrator=Aiden", "--instructions", "narrator=Calm"],
                                      ["--replace", "narrator=Ryan", "--instructions", "narrator=Lively"]])
def test_reviewed_cli_snapshot_rejects_changed_preset_or_style(legacy_project: Path, tmp_path: Path, capsys, changed):
    from lixity.cli import main

    original = (legacy_project / "lixity.toml").read_bytes()
    assert main(["audio-migrate", "--project", str(legacy_project), "--replace", "narrator=Ryan",
                 "--instructions", "narrator=Calm"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert "Calm" not in json.dumps(preview)
    backup = tmp_path / "backup.zip"
    assert main(["audio-migrate", "--project", str(legacy_project), *changed, "--apply",
                 "--backup", str(backup), "--expected-snapshot", preview["snapshot"]]) == 1
    assert "snapshot changed" in capsys.readouterr().err
    assert not backup.exists()
    assert (legacy_project / "lixity.toml").read_bytes() == original
