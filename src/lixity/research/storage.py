"""Explicit, recoverable conversion of manifest storage without content changes."""

import tempfile
from pathlib import Path
from typing import Any

from .archive import _export_archive, _manifest_history, restore_archive
from .repository import (
    STORAGE_MARKER,
    Repository,
    ResearchConflictError,
    ResearchStorageError,
    Snapshot,
    _PlainManifestRepository,
    publish,
    sync_directory,
)


def _remove_plain_duplicates(repository: Repository, snapshot: Snapshot) -> None:
    """Remove only accepted plaintext copies after verifying their gzip owners."""
    pending: list[Path] = []
    for checksum, _ in _manifest_history(repository, snapshot):
        path = repository.safe(repository.manifest_path(checksum).with_suffix(""))
        if not path.exists():
            continue
        try:
            if repository.verified(path, checksum) != repository.read_manifest(checksum):
                raise ResearchStorageError("Plain and compressed manifest bytes conflict")
            path.unlink()
            sync_directory(path.parent)
        except (OSError, ResearchStorageError):
            pending.append(path)
    if pending:
        raise ResearchStorageError(
            f"Compressed manifest storage is published and valid, but {len(pending)} plaintext copies remain. "
            "Keep the verified backup and rerun the explicit storage migration to retry cleanup."
        )


def _convert_manifests(repository: _PlainManifestRepository, snapshot: Snapshot) -> dict[str, int]:
    """Stage accepted gzip objects, commit the layout marker, then clean copies.

    The caller owns the writer lock or an unpublished restore staging directory.
    Before marker publication plaintext remains authoritative. After publication
    every accepted gzip object has been verified; duplicate cleanup is retryable.
    Unpublished or unrelated recovery objects are never selected for removal.
    """
    history = _manifest_history(repository, snapshot)
    current = Repository(repository.root)
    original_bytes = compressed_bytes = 0
    for checksum, _ in history:
        content = repository.read_manifest(checksum)
        current.write_manifest(checksum, content)
        if current._read_compressed_manifest(checksum) != content:
            raise ResearchStorageError("Staged compressed manifest verification failed")
        original_bytes += len(content)
        compressed_bytes += current.manifest_path(checksum).stat().st_size
    try:
        publish(current.safe(current.data / "storage.json"), STORAGE_MARKER)
    except OSError as exc:
        raise ResearchStorageError(
            "Manifest layout publication was interrupted; all original plaintext copies were retained. "
            "Keep the verified backup and rerun the explicit storage migration to inspect and resume."
        ) from exc
    # Read through the normal owner after the one atomic layout publication.
    accepted = current.snapshot()
    if accepted.digest != snapshot.digest:
        raise ResearchStorageError("Research HEAD changed during manifest conversion")
    _manifest_history(current, accepted)
    _remove_plain_duplicates(current, accepted)
    return {
        "manifests_converted": len(history),
        "original_manifest_bytes": original_bytes,
        "compressed_manifest_bytes": compressed_bytes,
        "reclaimed_bytes": original_bytes - compressed_bytes,
    }


def migrate_storage(
    project: str | Path, backup: str | Path, *, expected_snapshot: str | None = None,
) -> dict[str, Any]:
    """Back up and explicitly migrate one project into current gzip storage.

    The backup is a non-overwriting canonical portable archive. Its restored copy
    is validated before acquiring the final migration lock; a snapshot compare
    then refuses writes made since backup selection. Interrupted staging retains
    the old store. Interrupted cleanup can be retried against the current layout.
    """
    repository = Repository(project)
    backup_path = Path(backup).expanduser().resolve()
    if any(backup_path.is_relative_to(protected.resolve())
           for protected in (repository.data, repository.cache)):
        raise ResearchStorageError("Migration backup must be outside research storage and its cache")
    if repository.safe(repository.data / "storage.json").exists():
        with repository.locked():
            snapshot = repository.snapshot()
            if expected_snapshot is not None and snapshot.digest != expected_snapshot:
                raise ResearchConflictError("Research snapshot changed; reload before migration")
            _manifest_history(repository, snapshot)
            _remove_plain_duplicates(repository, snapshot)
        return {
            "schema_version": "research-storage-migration-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "backup_path": str(backup_path), "already_current": True,
            "manifests_converted": 0, "original_manifest_bytes": 0,
            "compressed_manifest_bytes": 0, "reclaimed_bytes": 0,
        }
    plain = _PlainManifestRepository(project)
    snapshot = plain.snapshot()
    _manifest_history(plain, snapshot)
    if expected_snapshot is not None and snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; reload before migration")
    backup_exists = backup_path.exists()
    if not backup_exists:
        exported = _export_archive(plain, backup_path, overwrite=False)
        if exported["snapshot"] != snapshot.digest:
            raise ResearchConflictError("Research snapshot changed while preparing the migration backup; preserve it and retry with a new backup path")
    with tempfile.TemporaryDirectory(prefix=".verify-migration-", dir=backup_path.parent) as temporary:
        restored = Path(temporary) / "restored"
        try:
            restore_archive(backup_path, restored)
        except (OSError, ValueError) as exc:
            if backup_exists:
                raise ResearchStorageError("Migration backup exists but could not be verified; refusing to overwrite it") from exc
            raise
        restored_repository = Repository(restored)
        verified = restored_repository.snapshot()
        _manifest_history(restored_repository, verified)
        if verified.digest != snapshot.digest:
            raise ResearchConflictError("Existing migration backup names a different snapshot; preserve it and choose a new backup path")
        # Full audit checks retained descriptor sizes, citations and media pins
        # in the restored copy, without changing the original project.
        from .api import audit
        if not audit(restored)["ok"]:
            raise ResearchStorageError("Restored migration backup failed its integrity audit; original storage is unchanged")
    with plain.locked():
        # Another process must not have migrated or written after the backup.
        if plain.safe(plain.data / "storage.json").exists():
            raise ResearchConflictError("Research storage changed during migration; reload current state")
        current = plain.snapshot()
        if current.digest != snapshot.digest:
            raise ResearchConflictError("Research snapshot changed since migration backup; preserve it and retry with a new backup path")
        sizes = _convert_manifests(plain, current)
    return {
        "schema_version": "research-storage-migration-local/1", "project_id": current.project.id,
        "snapshot": current.digest, "backup_path": str(backup_path), "already_current": False,
        **sizes,
    }
