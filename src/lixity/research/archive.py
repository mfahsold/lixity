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
import json
import os
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Extraction, SourceVersion
from .repository import Repository, ResearchError, sync_directory

EXPORT_SCHEMA_VERSION = "research-export-local/1"
MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB ceiling


def _file_digest_and_size(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def export_archive(project: str | Path, output: str | Path) -> dict[str, Any]:
    """Export the authoritative research store to an integrity-verified tar.gz archive.

    The archive packages accepted history, manifests, and source blobs.
    Disposable caches and locks are excluded.
    """
    repository = Repository(project)
    if not repository.safe(repository.data / "HEAD.json").exists():
        raise ResearchError("Research store does not exist; cannot export")

    snapshot = repository.snapshot()

    # Collect all authoritative files making up the research store
    files_to_pack: dict[str, Path] = {}

    # 1. Root pointers and manifests
    head_path = repository.safe(repository.data / "HEAD.json")
    project_path = repository.safe(repository.data / "project.json")
    files_to_pack["research/HEAD.json"] = head_path
    files_to_pack["research/project.json"] = project_path

    # Active manifest and any ancestor manifests in the chain
    manifest_digest: str | None = snapshot.digest
    while manifest_digest:
        m_path = repository.safe(repository.data / "manifests" / f"{manifest_digest}.json")
        if m_path.is_file():
            files_to_pack[f"research/manifests/{manifest_digest}.json"] = m_path
        else:
            break
        # Read parent if available
        try:
            m_data = json.loads(m_path.read_text(encoding="utf-8"))
            manifest_digest = m_data.get("parent")
        except (OSError, json.JSONDecodeError):
            break

    # 2. Record revision files
    for entry in snapshot.manifest.entries:
        rec_path = repository.record_path(entry)
        if not rec_path.is_file():
            raise ResearchError(f"Missing record file for entry {entry.ref}: {rec_path}")
        rel_path = f"research/revisions/{entry.kind}/{entry.ref.id[9:]}/{entry.ref.revision}.json"
        files_to_pack[rel_path] = rec_path

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
        files_to_pack[f"research/blobs/{sha}"] = b_path

    # Build file checksums
    file_manifest: dict[str, dict[str, Any]] = {}
    for rel_path, abs_path in files_to_pack.items():
        sha256, size = _file_digest_and_size(abs_path)
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
        "file_count": len(files_to_pack),
        "files": file_manifest,
    }

    out_path = Path(output).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_tar = out_path.with_name(f".tmp-export-{os.getpid()}-{out_path.name}")

    try:
        manifest_bytes = (
            json.dumps(export_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

        with tarfile.open(temp_tar, mode="w:gz") as tar:
            # Add EXPORT_MANIFEST.json
            ti = tarfile.TarInfo(name="EXPORT_MANIFEST.json")
            ti.size = len(manifest_bytes)
            ti.mtime = int(datetime.now(timezone.utc).timestamp())
            ti.mode = 0o644
            import io
            tar.addfile(ti, io.BytesIO(manifest_bytes))

            # Add each research file
            for rel_path, abs_path in files_to_pack.items():
                tar.add(abs_path, arcname=rel_path)

        os.replace(temp_tar, out_path)
        sync_directory(out_path.parent)
    finally:
        if temp_tar.exists():
            with contextlib.suppress(OSError):
                temp_tar.unlink(missing_ok=True)

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "output_path": str(out_path),
        "file_count": len(files_to_pack),
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
                for member in tar.getmembers():
                    name = member.name
                    if os.path.isabs(name) or name.startswith("/") or ".." in Path(name).parts:
                        raise ResearchError(f"Dangerous archive entry detected: {name}")
                    if member.issym() or member.islnk() or member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                        raise ResearchError(f"Unsupported archive member type: {name}")
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
        except (OSError, json.JSONDecodeError) as exc:
            raise ResearchError("Invalid or unreadable EXPORT_MANIFEST.json") from exc

        if manifest_data.get("schema_version") != EXPORT_SCHEMA_VERSION:
            raise ResearchError(f"Unsupported export schema version: {manifest_data.get('schema_version')}")

        files_manifest = manifest_data.get("files")
        if not isinstance(files_manifest, dict) or not files_manifest:
            raise ResearchError("EXPORT_MANIFEST.json contains no file entries")

        # 3. Verify all file checksums
        for rel_path, expected in files_manifest.items():
            if not isinstance(expected, dict) or "sha256" not in expected:
                raise ResearchError(f"Invalid manifest metadata for {rel_path}")
            extracted_file = temp_stage / rel_path
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

        staged_repo = Repository(temp_stage)
        snapshot = staged_repo.snapshot()

        if snapshot.digest != manifest_data.get("snapshot"):
            raise ResearchError("Restored snapshot digest does not match export manifest")
        if snapshot.project.id != manifest_data.get("project_id"):
            raise ResearchError("Restored project ID does not match export manifest")

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
