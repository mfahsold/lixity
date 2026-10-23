"""Compressed manifest storage preserves canonical hashes and explicit migration."""

import gzip
import tarfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.research import api
from lixity.research.models import Head
from lixity.research.repository import (
    Repository,
    ResearchConflictError,
    ResearchError,
    ResearchStorageError,
    digest,
)


@pytest.fixture
def current_project(tmp_path):
    project = tmp_path / "synthetic-current"
    api.init(project, title="Synthetic compressed storage")
    api.create_dossier(project, "Synthetic dossier", "Synthetic original notes.")
    source = tmp_path / "synthetic-source.txt"
    source.write_bytes(b"Synthetic retained source bytes.\n")
    api.ingest(project, source, allow_retention=True)
    return project


def legacy_copy(project: Path) -> None:
    """Convert a synthetic fixture into the exact former physical layout."""
    for path in (project / "research" / "manifests").glob("*.json.gz"):
        path.with_suffix("").write_bytes(gzip.decompress(path.read_bytes()))
        path.unlink()
    (project / "research" / "storage.json").unlink(missing_ok=True)


def test_new_archive_uses_only_compressed_manifest_layout(current_project):
    research = current_project / "research"
    assert (research / "storage.json").is_file()
    assert not list((research / "manifests").glob("*.json"))
    snapshot = Repository(current_project).snapshot()
    raw = Repository(current_project).read_manifest(snapshot.digest)
    assert digest(raw) == snapshot.digest
    assert api.audit(current_project)["ok"]


def test_legacy_archive_requires_explicit_migration(current_project):
    legacy_copy(current_project)
    with pytest.raises(ResearchStorageError, match="migration"):
        Repository(current_project).snapshot()


def test_migration_preserves_head_records_sources_and_portable_backup(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    research = current_project / "research"
    immutable = {p.relative_to(research): p.read_bytes() for parent in ("revisions", "blobs")
                 for p in (research / parent).rglob("*") if p.is_file()}
    head = (research / "HEAD.json").read_bytes()
    manifests = {p.stem: p.read_bytes() for p in (research / "manifests").glob("*.json")}
    backup = tmp_path / "before-migration.tar.gz"
    result = migrate_storage(current_project, backup)
    assert result["schema_version"] == "research-storage-migration-local/1"
    assert result["manifests_converted"] == len(manifests)
    assert result["original_manifest_bytes"] == sum(map(len, manifests.values()))
    assert result["snapshot"] == Head.model_validate_json(head).sha256
    assert (research / "HEAD.json").read_bytes() == head
    assert immutable == {p: (research / p).read_bytes() for p in immutable}
    assert not list((research / "manifests").glob("*.json"))
    for checksum, raw in manifests.items():
        assert Repository(current_project).read_manifest(checksum) == raw
    assert api.audit(current_project)["ok"]
    with tarfile.open(backup) as archive:
        names = archive.getnames()
        assert "research/storage.json" not in names
        assert not any(name.endswith(".json.gz") for name in names)
        for checksum, raw in manifests.items():
            stream = archive.extractfile(f"research/manifests/{checksum}.json")
            assert stream is not None and stream.read() == raw
    restored = tmp_path / "restored"
    api.restore_archive(backup, restored)
    assert api.audit(restored)["ok"]
    assert (restored / "research/storage.json").is_file()
    assert Repository(restored).snapshot().digest == result["snapshot"]
    assert migrate_storage(current_project, backup)["already_current"]


def test_migration_refuses_overwriting_existing_backup(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    backup = tmp_path / "existing.tar.gz"
    backup.write_bytes(b"Existing synthetic backup")
    with pytest.raises(ResearchStorageError, match="exist"):
        migrate_storage(current_project, backup)
    assert backup.read_bytes() == b"Existing synthetic backup"
    assert not (current_project / "research/storage.json").exists()


def test_migration_refuses_stale_requested_snapshot(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    with pytest.raises(ResearchConflictError, match="snapshot"):
        migrate_storage(current_project, tmp_path / "backup.tar.gz", expected_snapshot="0" * 64)
    assert not (current_project / "research/storage.json").exists()


def test_compressed_manifest_rejects_truncation_corruption_and_bombs(current_project):
    repository = Repository(current_project)
    checksum = repository.snapshot().digest
    path = repository.manifest_path(checksum)
    raw = repository.read_manifest(checksum)
    original = path.read_bytes()
    candidates = [original[:-8], original[:-1] + bytes([original[-1] ^ 1]), gzip.compress(raw + b"changed")]
    with patch("lixity.research.repository.MAX_RESEARCH_OBJECT_BYTES", 1024):
        candidates.append(gzip.compress(b"x" * 2048))
        for content in candidates:
            path.write_bytes(content)
            with pytest.raises(ResearchStorageError):
                repository.read_manifest(checksum)


def test_migration_retries_staging_interruption_with_same_verified_backup(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    backup = tmp_path / "retry-backup.tar.gz"
    original = Repository.write_manifest
    failed = False

    def write_then_interrupt(repository, checksum, content):
        nonlocal failed
        original(repository, checksum, content)
        if repository.root == current_project and not failed:
            failed = True
            raise OSError("Synthetic interruption after gzip staging")

    with (patch.object(Repository, "write_manifest", side_effect=write_then_interrupt, autospec=True),
          pytest.raises(OSError, match="staging")):
        migrate_storage(current_project, backup)
    assert backup.is_file()
    before = backup.read_bytes()
    assert not (current_project / "research/storage.json").exists()
    assert list((current_project / "research/manifests").glob("*.json"))
    assert migrate_storage(current_project, backup)["manifests_converted"] > 0
    assert backup.read_bytes() == before
    assert api.audit(current_project)["ok"]


def test_migration_retries_cleanup_after_marker_publication(current_project, tmp_path):
    from lixity.research import storage
    from lixity.research.repository import publish

    legacy_copy(current_project)
    backup = tmp_path / "marker-backup.tar.gz"

    def publish_then_interrupt(path, content, **kwargs):
        publish(path, content, **kwargs)
        if path == current_project / "research/storage.json":
            raise OSError("Synthetic interruption after marker publication")

    with (patch.object(storage, "publish", side_effect=publish_then_interrupt),
          pytest.raises(ResearchStorageError, match="publication was interrupted")):
        storage.migrate_storage(current_project, backup)
    assert api.audit(current_project)["ok"]
    assert list((current_project / "research/manifests").glob("*.json"))
    assert storage.migrate_storage(current_project, backup)["already_current"]
    assert not list((current_project / "research/manifests").glob("*.json"))
    assert api.audit(current_project)["ok"]


def test_migration_preserves_unpublished_manifest_and_recovery_artifacts(current_project, tmp_path):
    from lixity.research.models import Manifest
    from lixity.research.repository import encode
    from lixity.research.storage import migrate_storage

    snapshot = Repository(current_project).snapshot()
    legacy_copy(current_project)
    orphan = Manifest.model_validate({**snapshot.manifest.model_dump(), "generation": 99})
    raw = encode(orphan)
    path = current_project / "research/manifests" / f"{digest(raw)}.json"
    path.write_bytes(raw)
    recovery = current_project / "research/revisions/synthetic.unpublished"
    recovery.write_bytes(b"Synthetic retained recovery bytes")
    migrate_storage(current_project, tmp_path / "orphan-backup.tar.gz")
    assert path.read_bytes() == raw
    assert recovery.read_bytes() == b"Synthetic retained recovery bytes"
    assert api.audit(current_project)["ok"]


def test_migration_rejects_head_race_after_backup_verification(current_project, tmp_path):
    from lixity.research import storage
    from lixity.research.repository import encode

    snapshot = Repository(current_project).snapshot()
    legacy_copy(current_project)
    original = storage.restore_archive

    def restore_then_change_head(*args, **kwargs):
        result = original(*args, **kwargs)
        (current_project / "research/HEAD.json").write_bytes(encode(Head(sha256=snapshot.manifest.parent)))
        return result

    with (patch.object(storage, "restore_archive", side_effect=restore_then_change_head),
          pytest.raises(ResearchConflictError, match="snapshot changed")):
        storage.migrate_storage(current_project, tmp_path / "race-backup.tar.gz")
    assert not (current_project / "research/storage.json").exists()


def test_migration_requires_writer_lock_and_external_backup(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    with pytest.raises(ResearchStorageError, match="outside"):
        migrate_storage(current_project, current_project / "research/backup.tar.gz")
    with (Repository(current_project).locked(),
          pytest.raises(ResearchStorageError, match="writer is busy")):
        migrate_storage(current_project, tmp_path / "busy-backup.tar.gz")
    assert not (current_project / "research/storage.json").exists()


def test_migration_reports_and_retries_plaintext_cleanup_failure(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    legacy_copy(current_project)
    original = Path.unlink
    failed = False

    def fail_one_plaintext(path, *args, **kwargs):
        nonlocal failed
        if path.parent == current_project / "research/manifests" and path.suffix == ".json" and not failed:
            failed = True
            raise PermissionError("Synthetic cleanup denial")
        return original(path, *args, **kwargs)

    backup = tmp_path / "cleanup-backup.tar.gz"
    with (patch.object(Path, "unlink", side_effect=fail_one_plaintext, autospec=True),
          pytest.raises(ResearchStorageError, match="published and valid")):
        migrate_storage(current_project, backup)
    assert api.audit(current_project)["ok"]
    assert len(list((current_project / "research/manifests").glob("*.json"))) == 1
    assert migrate_storage(current_project, backup)["already_current"]
    assert not list((current_project / "research/manifests").glob("*.json"))


def test_migration_fails_closed_on_damaged_ancestry_or_conflicting_gzip(current_project, tmp_path):
    from lixity.research.storage import migrate_storage

    snapshot = Repository(current_project).snapshot()
    legacy_copy(current_project)
    compressed = Repository(current_project).manifest_path(snapshot.digest)
    compressed.write_bytes(b"Unverified staged gzip bytes")
    with pytest.raises(ResearchStorageError, match="compressed"):
        migrate_storage(current_project, tmp_path / "conflict-backup.tar.gz")
    assert compressed.read_bytes() == b"Unverified staged gzip bytes"
    assert not (current_project / "research/storage.json").exists()
    compressed.unlink()
    ancestor = current_project / "research/manifests" / f"{snapshot.manifest.parent}.json"
    ancestor.unlink()
    backup = tmp_path / "missing-ancestor-backup.tar.gz"
    with pytest.raises(ResearchError, match="history"):
        migrate_storage(current_project, backup)
    assert not backup.exists()
    assert not (current_project / "research/storage.json").exists()
