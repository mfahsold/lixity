"""Release checks must reject ambiguous, stale or source-mismatched artifacts."""

import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tarfile
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_release.py"


@pytest.fixture
def release_script():
    spec = importlib.util.spec_from_file_location("check_release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def release_tree(tmp_path):
    source = tmp_path / "src/lixity"
    (source / "ui/assets").mkdir(parents=True)
    (source / "locales").mkdir(parents=True)
    files = {
        "_version.py": b'__version__ = "0.3.0"\n',
        "__init__.py": b"from ._version import __version__\n",
        "py.typed": b"",
        "locales/en.json": b'{"hello": "Hello"}\n',
        "ui/assets/dashboard.css": b"body { color: black; }\n",
    }
    for name, contents in files.items():
        (source / name).write_bytes(contents)
    dist = tmp_path / "dist"
    dist.mkdir()
    return tmp_path, dist, files


def write_artifacts(tree, *, wheel_version="0.3.0", sdist_version="0.3.0",
                    changed=None, duplicate=False, sdist_changed=None, root_directory=False,
                    test_mutation=None):
    root, dist, files = tree
    wheel = dist / "lixity-0.3.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, contents in files.items():
            archive.writestr(f"lixity/{name}", b"stale" if name == changed else contents)
        archive.writestr("lixity-0.3.0.dist-info/METADATA",
                         f"Name: lixity\nVersion: {wheel_version}\n")
        if duplicate:
            archive.writestr("other.dist-info/METADATA", "Name: other\nVersion: 0.3.0\n")
    sdist = dist / "lixity-0.3.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        if root_directory:
            directory = tarfile.TarInfo("lixity-0.3.0")
            directory.type = tarfile.DIRTYPE
            archive.addfile(directory)
        members = {f"src/lixity/{name}": contents for name, contents in files.items()}
        members.update({path.relative_to(root).as_posix(): path.read_bytes()
                        for path in (root / "tests").rglob("*.py")})
        if test_mutation == "missing":
            members.pop("tests/support.py")
        elif test_mutation == "changed":
            members["tests/support.py"] = b"stale helper"
        members["PKG-INFO"] = f"Name: lixity\nVersion: {sdist_version}\n".encode()
        for name, contents in members.items():
            shipped = b"stale" if name == f"src/lixity/{sdist_changed}" else contents
            info = tarfile.TarInfo(f"lixity-0.3.0/{name}")
            info.size = len(shipped)
            archive.addfile(info, io.BytesIO(shipped))
    return wheel, sdist


def test_valid_release_and_deterministic_checksums(release_script, release_tree):
    wheel, sdist = write_artifacts(release_tree)
    root, dist, _ = release_tree
    assert release_script.validate(root, dist, "v0.3.0") == "0.3.0"
    release_script.write_checksums(dist)
    expected = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sorted((wheel, sdist))
    )
    assert (dist / "SHA256SUMS").read_text() == expected
    release_script.validate(root, dist, "v0.3.0")


def test_release_note_preflight_requires_reviewed_notes_for_the_tag(release_script, release_tree):
    root, _, _ = release_tree
    tag = "v0.3.0"
    notes = root / "docs" / "releases" / f"{tag}.md"
    notes.parent.mkdir(parents=True)
    with pytest.raises(ValueError, match=r"missing release notes for v0\.3\.0"):
        release_script.verify_release_notes(root, tag)
    for text in ("  \n", "Pending release.\n", "- Release validation (pending)\n"):
        notes.write_text(text)
        with pytest.raises(ValueError, match="pending placeholders"):
            release_script.verify_release_notes(root, tag)
    notes.write_text("# Lixity v0.3.0\n\nReviewed release notes.\n")
    release_script.verify_release_notes(root, tag)


@pytest.mark.parametrize("stale_path", ["Cargo.toml", "Cargo.lock", "src-tauri/tauri.conf.json"])
def test_desktop_source_preflight_checks_each_installer_version_pin(release_script, release_tree, stale_path):
    root, _, _ = release_tree
    desktop = root / "desktop"
    (desktop / "src-tauri").mkdir(parents=True)
    sources = {
        "Cargo.toml": '[workspace.package]\nversion = "0.3.0"\n',
        "Cargo.lock": '[[package]]\nname = "lixity-desktop"\nversion = "0.3.0"\n',
        "src-tauri/tauri.conf.json": '{"version": "0.3.0"}\n',
    }
    for path, text in sources.items():
        (desktop / path).write_text(text)
    release_script.verify_desktop_version(root, "0.3.0")
    (desktop / stale_path).write_text(sources[stale_path].replace("0.3.0", "0.2.0"))
    with pytest.raises(ValueError, match=r"version '0\.2\.0' does not match source version 0\.3\.0"):
        release_script.verify_desktop_version(root, "0.3.0")


@pytest.mark.parametrize("mutation", ["missing", "malformed", "incomplete", "duplicate",
                                     "path", "wrong hash", "tampered artifact"])
def test_declared_checksums_fail_closed_without_rewriting_evidence(
        release_script, release_tree, mutation):
    wheel, _ = write_artifacts(release_tree)
    _, dist, _ = release_tree
    release_script.write_checksums(dist)
    manifest = dist / "SHA256SUMS"
    lines = manifest.read_text().splitlines(keepends=True)
    if mutation == "missing":
        manifest.unlink()
    elif mutation == "malformed":
        manifest.write_text("not a checksum\n")
    elif mutation == "incomplete":
        manifest.write_text(lines[0])
    elif mutation == "duplicate":
        manifest.write_text("".join([*lines, lines[0]]))
    elif mutation == "path":
        manifest.write_text("".join(lines).replace(wheel.name, "../" + wheel.name))
    elif mutation == "wrong hash":
        manifest.write_text("0" * 64 + lines[0][64:] + lines[1])
    else:
        wheel.write_bytes(wheel.read_bytes() + b"tampered")
    before = {path.name: path.read_bytes() for path in dist.iterdir()}
    with pytest.raises(ValueError, match=r"checksum|SHA256SUMS"):
        release_script.verify_checksums(dist, "0.3.0")
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_verification_cli_never_repairs_declared_hashes(
        release_script, release_tree, monkeypatch, capsys):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    manifest = dist / "SHA256SUMS"
    manifest.write_bytes(b"unreviewed evidence\n")
    monkeypatch.setattr(release_script, "__file__", str(root / "scripts/check_release.py"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--dist", str(dist)])
    with pytest.raises(SystemExit) as failure:
        release_script.main()
    assert failure.value.code == 1
    assert "release check failed" in capsys.readouterr().err
    assert manifest.read_bytes() == b"unreviewed evidence\n"


def test_valid_checksums_are_read_only(release_script, release_tree, monkeypatch):
    write_artifacts(release_tree)
    _, dist, _ = release_tree
    release_script.write_checksums(dist)
    before = {path.name: path.read_bytes() for path in dist.iterdir()}

    def reject_write(*args, **kwargs):
        raise AssertionError("verification attempted to write evidence")

    monkeypatch.setattr(Path, "write_text", reject_write)
    monkeypatch.setattr(Path, "write_bytes", reject_write)
    release_script.verify_checksums(dist, "0.3.0")
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


@pytest.mark.parametrize("tag", ["v3.0.1", "0.3.0", "v0.3.0-extra"])
def test_tag_must_exactly_match_source(release_script, release_tree, tag):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    with pytest.raises(ValueError, match="tag"):
        release_script.validate(root, dist, tag)


@pytest.mark.parametrize("kwargs", [
    {"wheel_version": "0.3.00"}, {"sdist_version": "3.0.1"},
    {"changed": "ui/assets/dashboard.css"}, {"changed": "locales/en.json"},
    {"duplicate": True},
    {"sdist_changed": "ui/assets/dashboard.css"}, {"sdist_changed": "locales/en.json"},
])
def test_metadata_and_packaged_ui_must_match_source(release_script, release_tree, kwargs):
    write_artifacts(release_tree, **kwargs)
    root, dist, _ = release_tree
    with pytest.raises(ValueError):
        release_script.validate(root, dist, "v0.3.0")


@pytest.mark.parametrize("extra", ["old.whl", "old.tar.gz", "private.txt"])
def test_stale_or_unknown_artifacts_fail_closed(release_script, release_tree, extra):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    (dist / extra).write_text("do not publish")
    with pytest.raises(ValueError, match="artifacts"):
        release_script.validate(root, dist, "v0.3.0")


def test_sdist_source_mismatch_is_rejected(release_script, release_tree):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    (root / "src/lixity/_version.py").write_text('__version__ = "3.0.1"\n')
    with pytest.raises(ValueError):
        release_script.validate(root, dist)


@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_sdist_preserves_shared_test_modules(release_script, release_tree, mutation):
    root, dist, _ = release_tree
    (root / "tests").mkdir()
    (root / "tests/support.py").write_text("SYNTHETIC_FIXTURE = 'shared'\n")
    write_artifacts(release_tree, test_mutation=mutation)
    with pytest.raises(ValueError, match="sdist tests differs from source"):
        release_script.validate(root, dist)
    write_artifacts(release_tree)
    assert release_script.validate(root, dist) == "0.3.0"


def test_standard_sdist_root_directory_is_accepted(release_script, release_tree):
    write_artifacts(release_tree, root_directory=True)
    root, dist, _ = release_tree
    assert release_script.validate(root, dist) == "0.3.0"


@pytest.mark.parametrize("filename", ["private.txt", "manuscript.tar.gz", "other-1.0.whl"])
def test_build_preserves_unmanaged_output(release_script, release_tree, filename):
    root, dist, _ = release_tree
    private = dist / filename
    private.write_text("preserve me")
    with pytest.raises(ValueError, match="unmanaged"):
        release_script.build(root, dist)
    assert private.read_text() == "preserve me"


def test_bad_tag_fails_before_build_changes_outputs(release_script, release_tree):
    root, dist, _ = release_tree
    stale = dist / "lixity-old.whl"
    stale.write_bytes(b"preserve until successful build")
    with pytest.raises(ValueError, match="tag"):
        release_script.build(root, dist, "v3.0.1")
    assert stale.read_bytes() == b"preserve until successful build"


def test_source_preflight_does_not_touch_artifacts(
        release_script, release_tree, monkeypatch, capsys):
    root, dist, _ = release_tree
    sentinel = dist / "private.txt"
    sentinel.write_text("preserve me")
    monkeypatch.setattr(release_script, "__file__", str(root / "scripts/check_release.py"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--source-only", "--tag", "v0.3.0"])
    release_script.main()
    assert "release source verified: 0.3.0" in capsys.readouterr().out
    assert list(dist.iterdir()) == [sentinel]
    assert sentinel.read_text() == "preserve me"


@pytest.mark.parametrize(("tag", "notes", "expected"), [
    (None, None, "Set RELEASE_TAG"),
    ("v0.0.0", None, "does not match source version"),
    ("v0.3.0", None, "missing release notes"),
    ("v0.3.0", "Pending release.\n", "pending placeholders"),
])
def test_release_make_rejects_unusable_input_before_starting_heavy_checks(tmp_path, tag, notes, expected):
    make = shutil.which("make")
    if make is None:
        pytest.skip("GNU make is optional on this platform")
    root = SCRIPT.parents[1]
    shutil.copy2(root / "Makefile", tmp_path / "Makefile")
    (tmp_path / "scripts").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "scripts/check_release.py")
    version = tmp_path / "src/lixity/_version.py"
    version.parent.mkdir(parents=True)
    version.write_text('__version__ = "0.3.0"\n')
    if notes:
        release_notes = tmp_path / "docs/releases/v0.3.0.md"
        release_notes.parent.mkdir(parents=True)
        release_notes.write_text(notes)
    probe = tmp_path / "probe.mk"
    probe.write_text(
        "lint typecheck test docs-generated-check audit:\n"
        '\t@echo HEAVY_CHECK_STARTED\n\t@exit 19\n'
    )
    result = subprocess.run(  # noqa: S603 - fixed make targets in synthetic project
        [make, "-j4", "-f", "Makefile", "-f", "probe.mk", "release-check",
         f"VPY={sys.executable}", f"RELEASE_TAG={tag or ''}"],
        cwd=tmp_path, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "HEAVY_CHECK_STARTED" not in output
    assert expected in output


def test_fresh_build_replaces_stale_artifacts_only_after_validation(
        release_script, release_tree, monkeypatch):
    root, dist, files = release_tree
    (dist / "lixity-3.0.1-py3-none-any.whl").write_bytes(b"old wheel")
    (dist / "SHA256SUMS").write_text("old hashes")

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((root, fresh, files))

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    release_script.build(root, dist, "v0.3.0")
    assert {path.name for path in dist.iterdir()} == {
        "lixity-0.3.0-py3-none-any.whl", "lixity-0.3.0.tar.gz", "SHA256SUMS",
    }
    assert release_script.validate(root, dist, "v0.3.0") == "0.3.0"
    assert "old hashes" not in (dist / "SHA256SUMS").read_text()


def test_invalid_fresh_build_preserves_existing_artifacts(
        release_script, release_tree, monkeypatch):
    root, dist, files = release_tree
    stale = dist / "lixity-old.whl"
    stale.write_bytes(b"preserve until successful build")

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((root, fresh, files), changed="ui/assets/dashboard.css")

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    with pytest.raises(ValueError, match="differs from source"):
        release_script.build(root, dist)
    assert stale.read_bytes() == b"preserve until successful build"
    assert {path.name for path in dist.iterdir()} == {"lixity-old.whl"}


def test_build_preserves_unmanaged_output_created_during_build(
        release_script, release_tree, monkeypatch):
    root, dist, files = release_tree
    (dist / "lixity-old.whl").write_bytes(b"previous approved wheel")
    late_file = dist / "notes.txt"

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((root, fresh, files))
        late_file.write_bytes(b"new unmanaged file")

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    with pytest.raises(ValueError, match="unmanaged files"):
        release_script.build(root, dist)
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == {
        "lixity-old.whl": b"previous approved wheel", "notes.txt": b"new unmanaged file",
    }


@pytest.mark.parametrize("failure_stage", ["smoke", "copy", "copy interrupt", "promotion", "interrupt"])
def test_failed_candidate_preserves_previous_artifacts(
        release_script, release_tree, monkeypatch, failure_stage):
    source_root, dist, files = release_tree
    (dist / "lixity-old.whl").write_bytes(b"previous approved wheel")
    (dist / "SHA256SUMS").write_bytes(b"previous approved hashes")
    before = {path.name: path.read_bytes() for path in dist.iterdir()}

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((source_root, fresh, files))

    def failed_smoke(candidate, version, *, install_report, root):
        assert candidate != dist
        assert version == "0.3.0"
        assert root == source_root
        assert {path.name: path.read_bytes() for path in dist.iterdir()} == before
        raise ValueError("injected smoke failure")

    copy = release_script.shutil.copy2

    def failed_copy(source, target, *args, **kwargs):
        copy(source, target, *args, **kwargs)
        if failure_stage == "copy interrupt":
            raise KeyboardInterrupt("injected copy interruption")
        raise OSError("injected copy failure")

    rename = Path.rename

    def failed_promotion(source, target):
        if Path(target) == dist and source != dist:
            # Fail once, so restoring the backup can succeed.
            monkeypatch.setattr(Path, "rename", rename)
            if failure_stage == "interrupt":
                raise KeyboardInterrupt("injected promotion interruption")
            raise OSError("injected promotion failure")
        return rename(source, target)

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    monkeypatch.setattr(release_script, "smoke", failed_smoke if failure_stage == "smoke"
                        else lambda candidate, version, *, install_report, root: None)
    if failure_stage in {"copy", "copy interrupt"}:
        monkeypatch.setattr(release_script.shutil, "copy2", failed_copy)
    elif failure_stage in {"promotion", "interrupt"}:
        monkeypatch.setattr(Path, "rename", failed_promotion)
    expected = (KeyboardInterrupt if failure_stage in {"interrupt", "copy interrupt"}
                else (ValueError, OSError))
    with pytest.raises(expected, match="injected"):
        release_script.build(source_root, dist, "v0.3.0", smoke_wheel=True)
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_build_cli_smokes_candidate_before_replacing_output(
        release_script, release_tree, monkeypatch, tmp_path):
    source_root, dist, files = release_tree
    report = tmp_path / "install-report.json"
    stale = dist / "lixity-old.whl"
    stale.write_bytes(b"old approved bytes")

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((source_root, fresh, files))

    def inspect_smoke(candidate, version, *, install_report, root):
        assert candidate != dist
        assert root == source_root
        assert stale.read_bytes() == b"old approved bytes"
        assert version == release_script.validate(root, candidate, "v0.3.0")
        assert not report.exists()
        install_report.write_text('{}', encoding="utf-8")

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    monkeypatch.setattr(release_script, "smoke", inspect_smoke)
    monkeypatch.setattr(release_script, "__file__", str(source_root / "scripts/check_release.py"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--build", "--smoke", "--dist", str(dist),
                                      "--install-report", str(report)])
    release_script.main()
    assert not stale.exists()
    assert report.read_text(encoding="utf-8") == '{}'
    release_script.verify_checksums(dist, "0.3.0")


def test_failed_rollback_retains_and_reports_previous_artifacts(
        release_script, release_tree, monkeypatch):
    root, dist, files = release_tree
    (dist / "lixity-old.whl").write_bytes(b"previous approved bytes")

    def isolated_build(command, **kwargs):
        fresh = Path(command[-1])
        fresh.mkdir()
        write_artifacts((root, fresh, files))

    rename = Path.rename

    def failed_promotion_and_rollback(source, target):
        if Path(target) == dist:
            raise OSError("injected unavailable destination")
        return rename(source, target)

    monkeypatch.setattr(release_script.subprocess, "run", isolated_build)
    monkeypatch.setattr(Path, "rename", failed_promotion_and_rollback)
    with pytest.raises(OSError, match="previous artifacts retained at") as failure:
        release_script.build(root, dist)
    backups = list(dist.parent.glob(".dist-release-*/previous/lixity-old.whl"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"previous approved bytes"
    assert str(backups[0].parent) in str(failure.value)


def test_installed_smoke_failure_reports_captured_stderr_without_changing_artifacts(
        release_script, release_tree, monkeypatch, capsys):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    release_script.write_checksums(dist)
    before = {path.name: path.read_bytes() for path in dist.iterdir()}

    def failed_install(command, **kwargs):
        if command[1:3] == ["-m", "venv"]:
            return subprocess.CompletedProcess(command, 0)
        raise subprocess.CalledProcessError(17, command, output="synthetic install stdout",
                                            stderr="synthetic dependency resolution failure")

    monkeypatch.setattr(release_script.subprocess, "run", failed_install)
    monkeypatch.setattr(release_script, "__file__", str(root / "scripts/check_release.py"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--smoke", "--dist", str(dist)])
    with pytest.raises(SystemExit) as failure:
        release_script.main()
    assert failure.value.code == 1
    error = capsys.readouterr().err
    assert "synthetic dependency resolution failure" in error
    assert "install wheel" in error
    assert "17" in error
    assert {path.name: path.read_bytes() for path in dist.iterdir()} == before


def test_installed_workspace_stops_after_invalid_root_redirect(release_script, tmp_path, monkeypatch):
    source = tmp_path / "checkout"
    (source / "samples").mkdir(parents=True)
    sample = b"# A synthetic sample\n\nHere is a sample sentence.\n"
    (source / "samples/first-look.md").write_bytes(sample)
    project = tmp_path / "warehouse-4"
    called = []

    def run(command, label):
        called.append(command[1:3])
        if command[1] == "analyze":
            assert command[2:] == ["--project", str(project), "--json"]
            assert (project / "manuscript.md").read_bytes() == sample
            return json.dumps({"meta": {"version": "0.3.0", "language": "en"}, "metrics": {
                "clean_words": 100, "total_sentences": 5,
            }})
        if command[1:3] == ["service", "status"]:
            return json.dumps({"schema_version": "lixity-service-status/1", "ok": True,
                               "state": "running", "running_version": "0.3.0"})
        if command[1] == "doctor":
            return json.dumps({"schema_version": "lixity-doctor/1", "ok": True, "installation": {
                "distribution_version": "0.3.0", "module_path": str(tmp_path / "venv/module.py"),
            }})
        if command[1:3] == ["service", "stop"]:
            return json.dumps({"ok": True, "state": "stopped"})
        return ""

    def serve_redirect(port, path):
        assert (port, path) == (54321, "/")
        return 303, "https://example.invalid/w/abc/", "text/plain", b""

    probe = SimpleNamespace(bind=lambda address: None, getsockname=lambda: ("127.0.0.1", 54321))
    monkeypatch.setattr(release_script, "socket", SimpleNamespace(socket=lambda: nullcontext(probe)))
    monkeypatch.setattr(release_script, "_loopback_get", serve_redirect)

    with pytest.raises(ValueError, match="did not redirect to a local workspace"):
        release_script._smoke_workspace(tmp_path / "lixity", tmp_path, source, "0.3.0", run)

    assert called == [["analyze", "--project"], ["service", "start"], ["service", "status"],
                      ["doctor", "--port"], ["service", "stop"]]


def test_every_ui_asset_file_is_covered_by_package_data() -> None:
    """The wheel must ship every asset: the dashboard inlines them from package data."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["lixity"]
    package = root / "src" / "lixity"
    covered = set()
    for pattern in patterns:
        covered.update(path.resolve() for path in package.glob(pattern) if path.is_file())
    files = [path for path in (package / "ui" / "assets").rglob("*") if path.is_file()]
    missing = sorted(str(path.relative_to(package)) for path in files if path.resolve() not in covered)
    assert missing == [], f"UI assets missing from package-data: {missing}"


def test_every_locale_file_is_covered_by_package_data_manifest_and_release_check(release_script) -> None:
    """Shipped workspace locales must match pyproject.toml package-data, MANIFEST.in, and check_release."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10
        import tomli as tomllib

    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = config["tool"]["setuptools"]["package-data"]["lixity"]
    package = root / "src" / "lixity"
    covered = set()
    for pattern in patterns:
        covered.update(path.resolve() for path in package.glob(pattern) if path.is_file())
    locales = sorted((package / "locales").glob("*.json"))
    assert locales, "Expected workspace locale JSON files under src/lixity/locales/"
    missing = sorted(str(path.relative_to(package)) for path in locales if path.resolve() not in covered)
    assert missing == [], f"Locale files missing from package-data: {missing}"

    manifest = (root / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert "include src/lixity/locales/*.json" in [line.strip() for line in manifest]

    expected = release_script.package_files(root)
    for path in locales:
        key = "lixity/" + path.relative_to(package).as_posix()
        assert key in expected, f"{key} missing from check_release.package_files()"
        assert expected[key] == path.read_bytes()
