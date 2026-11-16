"""Release preparation drafts claims honestly and reports partial local edits."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/prepare_release.py"


@pytest.fixture
def prepare_script(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    version = tmp_path / "src/lixity/_version.py"
    version.parent.mkdir(parents=True)
    version.write_text('__version__ = "0.3.0"\n')
    return module


def test_new_notes_mark_publication_and_verification_pending(prepare_script):
    notes = prepare_script.scaffold_release_notes("0.3.1").read_text()
    assert "Pending release" in notes
    assert "Verification (pending)" in notes
    assert "Publication (pending)" in notes
    assert "Released on" not in notes
    assert "passing" not in notes
    assert "Continuous manuscript reader" not in notes


def test_existing_reviewed_notes_are_preserved(prepare_script):
    target = prepare_script.ROOT / "docs/releases/v0.3.1.md"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"# Reviewed release\n\nActual reviewed changes.\n")
    assert prepare_script.scaffold_release_notes("0.3.1") == target
    assert target.read_bytes() == b"# Reviewed release\n\nActual reviewed changes.\n"


@pytest.mark.parametrize("error_type", [OSError, RuntimeError])
def test_sync_failure_lists_edits_already_made(
        prepare_script, monkeypatch, capsys, error_type):
    root = prepare_script.ROOT
    readme = root / "README.md"
    readme.write_text("previous version pin\n")

    def partial_sync():
        readme.write_text("partially synchronized pin\n")
        raise error_type("synthetic sync failure")

    monkeypatch.setattr(prepare_script, "run_sync", partial_sync)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "0.3.1"])
    assert prepare_script.main() == 1
    error = capsys.readouterr().err
    assert "synthetic sync failure" in error
    assert "Changes already made" in error
    assert "src/lixity/_version.py" in error
    assert "docs/releases/v0.3.1.md" in error
    assert "README.md" in error
    assert "not rolled back" in error
    assert readme.read_text() == "partially synchronized pin\n"
