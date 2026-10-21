"""Archive export and restoration with cryptographic verification and path safety.

This module implements BagIt-inspired portable archiving (RFC 8493) for the
authoritative Lixity research store. It packages the content-addressable
repository (HEAD, manifests, records, blobs, and project configuration) into
a gzip-compressed tar archive containing an explicit EXPORT_MANIFEST.json.
Disposable search indexes and locks are excluded; restoration targets a clean
directory and verifies all checksums before placing the archive.
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from pydantic import TypeAdapter, ValidationError

from .models import Digest, Extraction, Head, Identifier, Manifest, SourceVersion
from .repository import (
    Repository,
    ResearchError,
    ResearchStorageError,
    Snapshot,
    encode,
    sync_directory,
)

EXPORT_SCHEMA_VERSION = "research-export-local/1"
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB ceiling
_MANIFEST_DIGEST = TypeAdapter(Digest)
_PROJECT_IDENTIFIER = TypeAdapter(Identifier)


def _file_digest_and_size(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def _manifest_history(repository: Repository, snapshot: Snapshot) -> list[tuple[str, Path]]:
    """Verify the whole accepted ancestry before reading or publishing a backup."""
    checksum: str | None = snapshot.digest
    generation = snapshot.manifest.generation
    seen: set[str] = set()
    history: list[tuple[str, Path]] = []
    while checksum is not None:
        try:
            checksum = _MANIFEST_DIGEST.validate_python(checksum)
        except ValidationError as exc:
            raise ResearchError("Invalid manifest history selector") from exc
        if checksum in seen:
            raise ResearchError("Repeated manifest in research history")
        seen.add(checksum)
        path = repository.safe(repository.data / "manifests" / f"{checksum}.json")
        try:
            manifest = Manifest.model_validate_json(repository.verified(path, checksum))
        except (OSError, ValidationError) as exc:
            raise ResearchError("Missing, damaged or unsupported manifest history") from exc
        if manifest.project_id != snapshot.manifest.project_id:
            raise ResearchError("Manifest history belongs to another project")
        if manifest.generation != generation:
            raise ResearchError("Manifest history generations are not contiguous")
        history.append((checksum, path))
        generation -= 1
        checksum = manifest.parent
        if (checksum is None) != (generation == 0):
            raise ResearchError("Manifest history is incomplete or has an invalid root")
    return history


class _HashingReader(io.RawIOBase):
    """Hash the exact bytes consumed by the tar writer without buffering blobs."""

    def __init__(self, stream: BinaryIO):
        self.stream = stream
        self.hasher = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        content = self.stream.read(size)
        self.hasher.update(content)
        return content


def _add_bytes(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    member = tarfile.TarInfo(name=name)
    member.size = len(content)
    member.mtime = int(datetime.now(timezone.utc).timestamp())
    member.mode = 0o644
    tar.addfile(member, io.BytesIO(content))


def export_archive(project: str | Path, output: str | Path) -> dict[str, Any]:
    """Export accepted history and source bytes under the repository writer lock.

    Writers receive the usual busy error until the self-contained compressed
    candidate is complete. Disposable caches and locks are excluded.
    """
    repository = Repository(project)
    if not repository.safe(repository.data / "HEAD.json").exists():
        raise ResearchError("Research store does not exist; cannot export")

    out_path = Path(output).expanduser().resolve()
    if any(out_path.is_relative_to(protected.resolve())
           for protected in (repository.data, repository.cache)):
        raise ResearchError("Export output must be outside the research store and cache")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_tar: Path | None = None
    try:
        with repository.locked():
            snapshot = repository.snapshot()

            # Collect all authoritative files making up the research store
            files_to_pack: dict[str, tuple[Path, str]] = {}

            # 1. Root pointers and manifests
            root_bytes = {
                "research/HEAD.json": encode(Head(sha256=snapshot.digest)),
                "research/project.json": encode(snapshot.project),
            }

            # Active manifest and any ancestor manifests in the chain
            for manifest_digest, m_path in _manifest_history(repository, snapshot):
                files_to_pack[f"research/manifests/{manifest_digest}.json"] = (m_path, manifest_digest)

            # 2. Record revision files
            for entry in snapshot.manifest.entries:
                rec_path = repository.record_path(entry)
                if not rec_path.is_file():
                    raise ResearchError(f"Missing record file for entry {entry.ref}: {rec_path}")
                rel_path = f"research/revisions/{entry.kind}/{entry.ref.id[9:]}/{entry.ref.revision}.json"
                files_to_pack[rel_path] = (rec_path, entry.sha256)

            # 3. Blobs referenced by SourceVersions and Extractions
            blob_shas: set[str] = set()
            for rec in snapshot.revisions.values():
                if isinstance(rec, SourceVersion):
                    blob_shas.add(rec.blob.sha256)
                elif isinstance(rec, Extraction):
                    blob_shas.add(rec.text_blob.sha256)

            for sha in sorted(blob_shas):
                b_path = repository.safe(repository.data / "blobs" / sha)
                if not b_path.is_file():
                    raise ResearchError(f"Missing blob file: {b_path}")
                files_to_pack[f"research/blobs/{sha}"] = (b_path, sha)

            # Build file checksums
            file_manifest: dict[str, dict[str, Any]] = {
                name: {"sha256": hashlib.sha256(content).hexdigest(), "byte_length": len(content)}
                for name, content in root_bytes.items()
            }
            for rel_path, (abs_path, expected_digest) in files_to_pack.items():
                sha256, size = _file_digest_and_size(abs_path)
                if sha256 != expected_digest:
                    raise ResearchStorageError("Research object checksum mismatch during export")
                file_manifest[rel_path] = {"sha256": sha256, "byte_length": size}

            export_manifest = {
                "schema_version": EXPORT_SCHEMA_VERSION,
                "project_id": snapshot.project.id,
                "project_title": snapshot.project.title,
                "snapshot": snapshot.digest,
                "manifest_schema_version": snapshot.manifest.schema_version,
                "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "record_count": len(snapshot.revisions),
                "blob_count": len(blob_shas),
                "file_count": len(file_manifest),
                "files": file_manifest,
            }

            manifest_bytes = (
                json.dumps(export_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            # Match restore's ceiling for all regular member payloads, including metadata.
            total_uncompressed = len(manifest_bytes) + sum(
                entry["byte_length"] for entry in file_manifest.values()
            )
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise ResearchError("Archive exceeds uncompressed size safety ceiling")

            descriptor, temporary = tempfile.mkstemp(dir=out_path.parent, prefix=".tmp-export-")
            temp_tar = Path(temporary)
            os.close(descriptor)
            with tarfile.open(temp_tar, mode="w:gz") as tar:
                _add_bytes(tar, "EXPORT_MANIFEST.json", manifest_bytes)
                for name, content in root_bytes.items():
                    _add_bytes(tar, name, content)
                for name, (path, _) in files_to_pack.items():
                    with repository.safe(path).open("rb") as stream:
                        member = tar.gettarinfo(fileobj=stream, arcname=name)
                        if member.size != file_manifest[name]["byte_length"]:
                            raise ResearchStorageError("Research file changed during export")
                        reader = _HashingReader(stream)
                        tar.addfile(member, reader)
                        if reader.hasher.hexdigest() != file_manifest[name]["sha256"]:
                            raise ResearchStorageError("Research file checksum changed during export")

        # The candidate no longer depends on repository files; release writers.
        with temp_tar.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temp_tar, out_path)
        try:
            sync_directory(out_path.parent)
        except OSError as exc:
            raise ResearchStorageError(
                "Research export was published, but durability could not be confirmed. "
                "Inspect the output archive before retrying."
            ) from exc
    finally:
        if temp_tar is not None:
            with contextlib.suppress(OSError):
                temp_tar.unlink(missing_ok=True)

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "output_path": str(out_path),
        "file_count": len(file_manifest),
        "record_count": len(snapshot.revisions),
        "blob_count": len(blob_shas),
    }


def restore_archive(archive_path: str | Path, target_dir: str | Path) -> dict[str, Any]:
    """Restore and verify a research archive into a target directory.

    Refuses to overwrite an existing research store or non-empty project.
    Validates all file checksums, manifest integrity, and repository rules
    before placing the research store.
    """
    archive = Path(archive_path).expanduser().resolve()
    if not archive.is_file():
        raise ResearchError(f"Archive file does not exist: {archive}")

    target = Path(target_dir).expanduser().resolve()
    target_research = target / "research"
    if target_research.exists():
        raise ResearchError(
            f"Target directory already contains a research store: {target_research}; refusing to overwrite"
        )
    if target.exists() and any(target.iterdir()):
        raise ResearchError(
            f"Target directory is not empty: {target}; restoration must target a clean directory"
        )

    target.mkdir(parents=True, exist_ok=True)
    temp_stage = Path(tempfile.mkdtemp(dir=target, prefix=".restore-stage-"))

    try:
        # 1. Unpack with traversal and bomb protection
        total_uncompressed = 0
        try:
            with tarfile.open(archive, mode="r:*") as tar:
                seen_names: set[str] = set()
                for member in tar.getmembers():
                    name = member.name
                    if os.path.isabs(name) or name.startswith("/") or ".." in Path(name).parts:
                        raise ResearchError(f"Dangerous archive entry detected: {name}")
                    normalized_name = Path(name).as_posix()
                    if normalized_name in seen_names:
                        raise ResearchError("Duplicate archive entry")
                    seen_names.add(normalized_name)
                    if not (member.isfile() or member.isdir()):
                        raise ResearchError(f"Unsupported archive member type: {name}")
                    if normalized_name == "EXPORT_MANIFEST.json" and not member.isfile():
                        raise ResearchError("Export manifest must be a regular file")
                    if member.isfile():
                        total_uncompressed += member.size
                        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                            raise ResearchError("Archive exceeds uncompressed size safety ceiling")

                if hasattr(tarfile, "data_filter"):
                    tar.extractall(path=temp_stage, filter="data")
                else:
                    tar.extractall(path=temp_stage)  # noqa: S202
        except tarfile.TarError as exc:
            raise ResearchError(f"Corrupt or invalid tar archive: {exc}") from exc

        # 2. Check and validate EXPORT_MANIFEST.json
        manifest_path = temp_stage / "EXPORT_MANIFEST.json"
        if not manifest_path.is_file():
            raise ResearchError("Archive is missing EXPORT_MANIFEST.json")

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ResearchError("Invalid or unreadable EXPORT_MANIFEST.json") from exc

        if not isinstance(manifest_data, dict):
            raise ResearchError("Export manifest must be a JSON object")
        if manifest_data.get("schema_version") != EXPORT_SCHEMA_VERSION:
            raise ResearchError("Unsupported export schema version")
        try:
            _MANIFEST_DIGEST.validate_python(manifest_data.get("snapshot"))
        except ValidationError as exc:
            raise ResearchError("Invalid export snapshot digest") from exc
        try:
            _PROJECT_IDENTIFIER.validate_python(manifest_data.get("project_id"))
        except ValidationError as exc:
            raise ResearchError("Invalid export project identifier") from exc

        files_manifest = manifest_data.get("files")
        if not isinstance(files_manifest, dict) or not files_manifest:
            raise ResearchError("EXPORT_MANIFEST.json contains no file entries")

        # Validate the whole inventory before reading any inventory-selected path.
        for expected in files_manifest.values():
            if not isinstance(expected, dict):
                raise ResearchError("Invalid export manifest metadata")
            try:
                _MANIFEST_DIGEST.validate_python(expected.get("sha256"))
            except ValidationError as exc:
                raise ResearchError("Invalid export file digest") from exc
            if "byte_length" in expected and (
                type(expected["byte_length"]) is not int or expected["byte_length"] < 0
            ):
                raise ResearchError("Invalid export file byte_length")

        # 3. Verify all file checksums
        staged_repo = Repository(temp_stage)
        for rel_path, expected in files_manifest.items():
            extracted_file = staged_repo.safe(temp_stage / rel_path)
            if not extracted_file.is_file():
                raise ResearchError(f"Archive missing expected file: {rel_path}")
            actual_sha, actual_size = _file_digest_and_size(extracted_file)
            if actual_sha != expected["sha256"]:
                raise ResearchError(f"Checksum mismatch for restored file {rel_path}")
            if "byte_length" in expected and actual_size != expected["byte_length"]:
                raise ResearchError(f"Size mismatch for restored file {rel_path}")

        # 4. Open snapshot using repository validation
        staged_research = temp_stage / "research"
        if not staged_research.is_dir():
            raise ResearchError("Archive did not extract a valid research directory")

        snapshot = staged_repo.snapshot()

        if snapshot.digest != manifest_data.get("snapshot"):
            raise ResearchError("Restored snapshot digest does not match export manifest")
        if snapshot.project.id != manifest_data.get("project_id"):
            raise ResearchError("Restored project ID does not match export manifest")
        _manifest_history(staged_repo, snapshot)

        # 5. Atomically move staged research directory to target
        os.replace(staged_research, target_research)
        sync_directory(target)

        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "project_id": snapshot.project.id,
            "snapshot": snapshot.digest,
            "restored_to": str(target),
            "record_count": len(snapshot.revisions),
            "file_count": len(files_manifest),
        }
    finally:
        if temp_stage.exists():
            shutil.rmtree(temp_stage, ignore_errors=True)
