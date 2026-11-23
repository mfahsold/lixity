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


def test_preparation_keeps_release_pending_until_an_explicit_date(
        prepare_script, monkeypatch):
    root = prepare_script.ROOT
    base = "https://github.com/example/lixity/compare/"
    changelog = root / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n- Candidate change.\n\n"
        "## [0.8.2] - 2026-11-16\n\n- Previous release.\n\n"
        "## [3.0.1] - 2026-10-11\n\n- Historical release before reset.\n\n"
        f"[Unreleased]: {base}v0.8.2...HEAD\n"
        f"[0.8.2]: {base}v0.8.1...v0.8.2\n"
    )
    citation = root / "CITATION.cff"
    citation.write_text('version: "0.8.2"\ndate-released: "2026-11-16"\nauthors: []\n')
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    from sync_docs import check_or_sync_files

    def sync_citation():
        check_or_sync_files("0.9.0", root=root)

    monkeypatch.setattr(prepare_script, "run_sync", sync_citation)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "0.9.0"])
    assert prepare_script.main() == 0
    pending = changelog.read_text()
    assert "## [Unreleased]\n\n## [0.9.0] - Pending release\n\n- Candidate change." in pending
    assert f"[Unreleased]: {base}v0.8.2...HEAD" in pending
    assert f"[0.9.0]: {base}v0.8.2...HEAD" in pending
    assert citation.read_text() == 'version: "0.9.0"\nauthors: []\n'
    assert prepare_script.main() == 0 and changelog.read_text() == pending

    notes = root / "docs/releases/v0.9.0.md"
    notes.write_text("# Reviewed release notes\n")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "0.9.0", "--release-date", "2026-11-30"])
    assert prepare_script.main() == 0
    finalized = changelog.read_text()
    assert "## [0.9.0] - 2026-11-30\n\n- Candidate change." in finalized
    assert f"[Unreleased]: {base}v0.9.0...HEAD" in finalized
    assert f"[0.9.0]: {base}v0.8.2...v0.9.0" in finalized
    assert citation.read_text() == 'version: "0.9.0"\ndate-released: "2026-11-30"\nauthors: []\n'
    assert notes.read_text() == "# Reviewed release notes\n"
    assert prepare_script.main() == 0 and changelog.read_text() == finalized


def test_invalid_release_date_leaves_source_and_notes_alone(prepare_script, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "0.9.0", "--release-date", "2026-02-30"])
    assert prepare_script.main() == 1
    assert "release date must use YYYY-MM-DD" in capsys.readouterr().err
    root = prepare_script.ROOT
    assert (root / "src/lixity/_version.py").read_text() == '__version__ = "0.3.0"\n'
    assert not (root / "docs/releases/v0.9.0.md").exists()


@pytest.mark.parametrize("error_type", [OSError, RuntimeError])
def test_sync_failure_lists_edits_already_made(
        prepare_script, monkeypatch, capsys, error_type):
    root = prepare_script.ROOT
    readme = root / "README.md"
    readme.write_text("previous version pin\n")
    (root / "CHANGELOG.md").write_text("## [Unreleased]\n\n- Candidate change.\n")

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
    assert "CHANGELOG.md" in error
    assert "not rolled back" in error
    assert readme.read_text() == "partially synchronized pin\n"


def test_run_sync_invokes_all_doc_generators_for_root(prepare_script, monkeypatch, capsys):
    root = prepare_script.ROOT
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    import sync_docs

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
    monkeypatch.setattr(sync_docs, "check_or_sync_files", make_module("sync_docs", "check_or_sync_files").check_or_sync_files)
    monkeypatch.setitem(sys.modules, "build_public_site", make_module("build_public_site", "build"))
    monkeypatch.setitem(sys.modules, "build_llms_full", make_module("build_llms_full", "build"))
    monkeypatch.setitem(sys.modules, "build_guide_markdown", make_module("build_guide_markdown", "build"))
    monkeypatch.setitem(sys.modules, "build_metric_reference", make_module("build_metric_reference", "build"))

    prepare_script.run_sync()
    assert "Documentation already synchronized" in capsys.readouterr().out
    assert calls == [
        ("sync_docs", False, root),
        ("build_public_site", False, root),
        ("build_llms_full", False, root),
        ("build_guide_markdown", False, root),
        ("build_metric_reference", False, root),
        ("sync_docs", True, root),
        ("build_public_site", True, root),
        ("build_llms_full", True, root),
        ("build_guide_markdown", True, root),
        ("build_metric_reference", True, root),
    ]

    monkeypatch.setitem(sys.modules, "build_public_site", make_module("build_public_site", "build", check_result=["index.html"]))
    with pytest.raises(RuntimeError, match=r"index\.html"):
        prepare_script.run_sync()


def test_prepare_release_synchronizes_desktop_manifests(prepare_script):
    root = prepare_script.ROOT
    (root / "desktop/src-tauri").mkdir(parents=True)
    (root / "desktop/packaging/linux").mkdir(parents=True)
    cargo = root / "desktop/Cargo.toml"
    cargo.write_text('[workspace.package]\nversion = "0.9.1"\nedition = "2021"\n', encoding="utf-8")
    lock = root / "desktop/Cargo.lock"
    locked = 'version = 4\n\n[[package]]\nname = "lixity-desktop"\nversion = "0.9.1"\n\n' \
             '[[package]]\nname = "dependency"\nversion = "0.9.1"\n'
    lock.write_text(locked, encoding="utf-8")
    tauri = root / "desktop/src-tauri/tauri.conf.json"
    tauri.write_text('{\n  "productName": "Lixity",\n  "version": "0.9.1"\n}\n', encoding="utf-8")
    metainfo = root / "desktop/packaging/linux/io.github.mfahsold.Lixity.metainfo.xml"
    metainfo.write_text(
        "<component>\n  <releases>\n"
        '    <release version="0.9.1" date="2026-11-23">\n'
        '      <url type="details">https://github.com/mfahsold/lixity/releases/tag/v0.9.1</url>\n'
        "    </release>\n"
        "  </releases>\n</component>\n",
        encoding="utf-8",
    )

    prepare_script.update_desktop_manifests("0.10.0")
    assert 'version = "0.10.0"' in cargo.read_text(encoding="utf-8")
    assert lock.read_text(encoding="utf-8") == locked.replace('version = "0.9.1"', 'version = "0.10.0"', 1)
    assert '"version": "0.10.0"' in tauri.read_text(encoding="utf-8")
    xml_pending = metainfo.read_text(encoding="utf-8")
    assert '<release version="0.10.0">' in xml_pending
    assert '<release version="0.9.1" date="2026-11-23">' in xml_pending

    # Recording an explicit release date updates the existing 0.10.0 entry idempotently.
    prepare_script.update_desktop_manifests("0.10.0", release_date="2026-12-01")
    xml_dated = metainfo.read_text(encoding="utf-8")
    assert xml_dated.count('version="0.10.0"') == 1
    assert '<release version="0.10.0" date="2026-12-01">' in xml_dated
