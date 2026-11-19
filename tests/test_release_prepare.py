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


def test_run_sync_invokes_all_doc_generators_for_root(prepare_script, monkeypatch, capsys):
    root = prepare_script.ROOT
    (root / "scripts").mkdir(exist_ok=True)
    calls: list[tuple[str, bool, Path | None]] = []

    def make_module(name, fn_name, *, check_result=None):
        import types
        mod = types.ModuleType(name)
        def fn(*args, check_only=False, root=None, **_kwargs):
            calls.append((name, check_only, root))
            if check_only and check_result is not None:
                return list(check_result)
            return []
        setattr(mod, fn_name, fn)
        return mod

    monkeypatch.setitem(sys.modules, "check_release", type("M", (), {"source_version": staticmethod(lambda r: "0.3.0")})())
    monkeypatch.setitem(sys.modules, "sync_docs", make_module("sync_docs", "check_or_sync_files"))
    monkeypatch.setitem(sys.modules, "build_public_site", make_module("build_public_site", "build"))
    monkeypatch.setitem(sys.modules, "build_llms_full", make_module("build_llms_full", "build"))
    monkeypatch.setitem(sys.modules, "build_guide_markdown", make_module("build_guide_markdown", "build"))

    prepare_script.run_sync()
    assert "Documentation already synchronized" in capsys.readouterr().out
    assert calls == [
        ("sync_docs", False, root),
        ("build_public_site", False, root),
        ("build_llms_full", False, root),
        ("build_guide_markdown", False, root),
        ("sync_docs", True, root),
        ("build_public_site", True, root),
        ("build_llms_full", True, root),
        ("build_guide_markdown", True, root),
    ]

    monkeypatch.setitem(sys.modules, "build_public_site", make_module("build_public_site", "build", check_result=["index.html"]))
    with pytest.raises(RuntimeError, match=r"index\.html"):
        prepare_script.run_sync()
