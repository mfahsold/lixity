"""Release checks must reject ambiguous, stale or source-mismatched artifacts."""

import hashlib
import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

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
    files = {
        "_version.py": b'__version__ = "0.3.0"\n',
        "__init__.py": b"from ._version import __version__\n",
        "py.typed": b"",
        "ui/assets/dashboard.css": b"body { color: black; }\n",
    }
    for name, contents in files.items():
        (source / name).write_bytes(contents)
    dist = tmp_path / "dist"
    dist.mkdir()
    return tmp_path, dist, files


def write_artifacts(tree, *, wheel_version="0.3.0", sdist_version="0.3.0",
                    changed=None, duplicate=False, sdist_changed=None, root_directory=False):
    _, dist, files = tree
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


@pytest.mark.parametrize("tag", ["v3.0.1", "0.3.0", "v0.3.0-extra"])
def test_tag_must_exactly_match_source(release_script, release_tree, tag):
    write_artifacts(release_tree)
    root, dist, _ = release_tree
    with pytest.raises(ValueError, match="tag"):
        release_script.validate(root, dist, tag)


@pytest.mark.parametrize("kwargs", [
    {"wheel_version": "0.3.00"}, {"sdist_version": "3.0.1"},
    {"changed": "ui/assets/dashboard.css"}, {"duplicate": True},
    {"sdist_changed": "ui/assets/dashboard.css"},
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
