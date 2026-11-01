"""Release migration and recovery on synthetic project copies."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from lixity.cli import main
from lixity.config import read_explicit_project_config
from lixity.speech_profiles import parse_audio_settings


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize("config_name", ["lixity.toml", "pyproject.toml"])
def test_schema4_upgrade_and_recovery_on_project_copy(tmp_path: Path, capsys, version: int, config_name: str):
    """Restoration includes whether a root settings file existed before migration."""
    original = tmp_path / "original"
    original.mkdir()
    prefix = "tool.lixity." if config_name == "pyproject.toml" else ""
    header = "[tool.lixity]\n" if prefix else ""
    config = (
        f'{header}language = "de"\nmanuscript = "draft.md"\n'
        f'[{prefix}audio]\nschema_version = "lixity-audio-settings/{version}"\nselected = "narrator"\n'
        f'[{prefix}audio.profiles.narrator]\nengine = "qwen3"\nvoice = "Ryan"\n'
        'name = "Synthetic narrator"\nlanguage = "de"\nparagraph_pause = 0.7\n'
    )
    (original / config_name).write_text(config, encoding="utf-8")
    (original / "draft.md").write_text("# Synthetic chapter\n\nA paper boat floats.\n", encoding="utf-8")
    (original / "retained.bin").write_bytes(b"synthetic retained bytes\x00\x01")
    original_files = {path.name: path.read_bytes() for path in original.iterdir()}
    source_settings = read_explicit_project_config(original)
    source_audio = parse_audio_settings(source_settings["audio"])

    project = tmp_path / "working-copy"
    shutil.copytree(original, project)
    args = ["audio-migrate", "--project", str(project), "--to-schema-4"]
    assert main(args) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["source_schema"] == f"lixity-audio-settings/{version}"
    assert preview["retained_profile_count"] == 1
    assert {path.name: path.read_bytes() for path in project.iterdir()} == original_files

    backup = tmp_path / "audio-backup.zip"
    assert main([*args, "--apply", "--backup", str(backup), "--expected-snapshot", preview["snapshot"]]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is True
    upgraded = parse_audio_settings(read_explicit_project_config(project)["audio"])
    assert upgraded == source_audio.model_copy(update={"schema_name": "lixity-audio-settings/4"})
    assert (project / "draft.md").read_bytes() == original_files["draft.md"]
    assert (project / "retained.bin").read_bytes() == original_files["retained.bin"]

    restored = tmp_path / "restored-copy"
    shutil.copytree(project, restored)
    with zipfile.ZipFile(backup) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert set(manifest["files"]) == {config_name}
        for name in manifest["files"]:
            (restored / name).write_bytes(archive.read(name))
        # A settings file created by migration has no original bytes in the ZIP.
        # Remove it only on the recovery copy after preserving post-migration edits.
        if "lixity.toml" not in manifest["files"]:
            assert (restored / "lixity.toml").exists()
            (restored / "lixity.toml").unlink()
    assert {path.name: path.read_bytes() for path in restored.iterdir()} == original_files
    assert read_explicit_project_config(restored) == source_settings
    assert read_explicit_project_config(project)["audio"]["schema_version"] == "lixity-audio-settings/4"
