"""Immutable local objects and snapshots with a single atomic publication point."""

import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from .models import (
    ENTITY,
    Activity,
    Blob,
    Claim,
    Decision,
    Dossier,
    Entity,
    Entry,
    EvidenceLink,
    Extraction,
    Head,
    Manifest,
    Passage,
    Project,
    Record,
    Reference,
    Source,
    SourceVersion,
    StrictModel,
    Tombstone,
    reference,
)


class ResearchError(ValueError):
    """An invalid, conflicting or unavailable research operation."""


def encode(value: StrictModel) -> bytes:
    return (json.dumps(value.model_dump(mode="json"), ensure_ascii=False,
                       sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish(path: Path, content: bytes, *, replace: bool = False) -> None:
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        sync_directory(directory.parent)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".staged-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.is_symlink() or path.read_bytes() != content:
                    raise ResearchError("Immutable object conflict") from None
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def replace_head(path: Path, content: bytes) -> None:
    publish(path, content, replace=True)


Model = TypeVar("Model", bound=Record)


@dataclass(frozen=True)
class Snapshot:
    digest: str
    manifest: Manifest
    records: dict[str, Entity]
    texts: dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    def get(self, ref: Reference, expected: type[Model]) -> Model:
        record = self.records.get(ref.id)
        if not isinstance(record, expected) or record.revision != ref.revision:
            raise ResearchError("Missing or incompatible pinned reference")
        return record

    @property
    def project(self) -> Project:
        return self.get(Reference(id=self.manifest.project_id), Project)


class Repository:
    def __init__(self, project: str | Path):
        self.root = Path(project).expanduser().resolve()
        self.data = self.root / "research"
        self.cache = self.root / ".lixity" / "research"

    def safe(self, path: Path) -> Path:
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise ResearchError("Research path escapes the project") from None
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ResearchError("Symlinks are not allowed inside the research store")
        return path

    @contextmanager
    def locked(self) -> Iterator[None]:
        lock = self.safe(self.cache / "writer.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a+b") as stream:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    if stream.tell() == 0:
                        stream.write(b"0")
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ResearchError("Research writer is busy; retry after it finishes") from None
            try:
                yield
            finally:
                if sys.platform == "win32":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def read(self, path: Path, *, maximum: int = 32 * 1024 * 1024) -> bytes:
        with self.safe(path).open("rb") as stream:
            content = stream.read(maximum + 1)
        if len(content) > maximum:
            raise ResearchError("Research object exceeds the supported size")
        return content

    def verified(self, path: Path, expected: str) -> bytes:
        content = self.read(path)
        if digest(content) != expected:
            raise ResearchError("Research object checksum mismatch")
        return content

    def record_path(self, entry: Entry) -> Path:
        return self.safe(self.data / "revisions" / entry.kind / entry.ref.id[9:] / f"{entry.ref.revision}.json")

    def snapshot(self) -> Snapshot:
        try:
            head = Head.model_validate_json(self.read(self.data / "HEAD.json", maximum=4096))
            manifest = Manifest.model_validate_json(self.verified(self.data / "manifests" / f"{head.sha256}.json", head.sha256))
            records: dict[str, Entity] = {}
            for entry in manifest.entries:
                record = ENTITY.validate_json(self.verified(self.record_path(entry), entry.sha256))
                if record.id in records or reference(record) != entry.ref or record.kind != entry.kind:
                    raise ResearchError("Duplicate or mismatched record identity")
                records[record.id] = record
            snapshot = Snapshot(head.sha256, manifest, records)
            self.validate(snapshot)
            if self.read(self.data / "project.json") != encode(snapshot.project):
                raise ResearchError("Project configuration does not match its accepted revision")
            return snapshot
        except (ValidationError, json.JSONDecodeError):
            raise ResearchError("Invalid or unsupported research schema") from None
        except FileNotFoundError:
            raise ResearchError("Research store is missing or incomplete; initialize or restore it") from None

    def validate(self, snapshot: Snapshot) -> None:
        project = snapshot.project
        sequences: set[tuple[str, int]] = set()
        descriptors: dict[str, Blob] = {}
        for record in snapshot.records.values():
            if record.project_id != project.id:
                raise ResearchError("Cross-project reference rejected")
            if isinstance(record, Project) and record.id != project.id:
                raise ResearchError("Multiple project records rejected")
            if isinstance(record, SourceVersion):
                snapshot.get(record.source_ref, Source)
                if descriptors.setdefault(record.blob.sha256, record.blob) != record.blob:
                    raise ResearchError("Inconsistent descriptors for the same blob")
                key = (record.source_ref.id, record.sequence)
                if key in sequences:
                    raise ResearchError("Duplicate source version sequence")
                sequences.add(key)
            elif isinstance(record, Activity):
                snapshot.get(record.source_version_ref, SourceVersion)
            elif isinstance(record, Extraction):
                version = snapshot.get(record.source_version_ref, SourceVersion)
                activity = snapshot.get(record.activity_ref, Activity)
                if activity.source_version_ref != record.source_version_ref or version.blob != record.text_blob:
                    raise ResearchError("Extraction provenance does not match source bytes")
            elif isinstance(record, Passage):
                snapshot.get(record.extraction_ref, Extraction)
            elif isinstance(record, Dossier):
                for ref in record.evidence_refs:
                    snapshot.get(ref, Passage)
            elif isinstance(record, Claim):
                if record.dossier_ref:
                    snapshot.get(record.dossier_ref, Dossier)
            elif isinstance(record, EvidenceLink):
                snapshot.get(record.claim_ref, Claim)
                snapshot.get(record.passage_ref, Passage)
            elif isinstance(record, Decision):
                if record.claim_ref:
                    snapshot.get(record.claim_ref, Claim)
            elif isinstance(record, Tombstone):
                pass

    def read_blob(self, descriptor: Blob) -> bytes:
        content = self.verified(self.data / "blobs" / descriptor.sha256, descriptor.sha256)
        if len(content) != descriptor.byte_length:
            raise ResearchError("Research blob length mismatch")
        return content

    def quote(self, snapshot: Snapshot, passage: Passage) -> tuple[Source, SourceVersion]:
        extraction = snapshot.get(passage.extraction_ref, Extraction)
        version = snapshot.get(extraction.source_version_ref, SourceVersion)
        checksum = extraction.text_blob.sha256
        if checksum not in snapshot.texts:
            snapshot.texts[checksum] = self.read_blob(extraction.text_blob).decode("utf-8")
        content = snapshot.texts[checksum]
        if content[passage.start:passage.end] != passage.verbatim:
            raise ResearchError("Citation does not match its archived text")
        return snapshot.get(version.source_ref, Source), version

    def commit(
        self,
        additions: list[Entity],
        blobs: dict[str, bytes],
        expected: Snapshot | None,
        removals: set[str] | None = None,
        delete_blobs: set[str] | None = None,
    ) -> Snapshot:
        with self.locked():
            current = self.snapshot() if self.safe(self.data / "HEAD.json").exists() else None
            if (current.digest if current else None) != (expected.digest if expected else None):
                raise ResearchError("Research snapshot changed; retry from the current HEAD")
            records = dict(current.records) if current else {}
            entries = list(current.manifest.entries) if current else []

            if removals:
                records = {k: v for k, v in records.items() if k not in removals}
                entries = [e for e in entries if e.ref.id not in removals]

            for record in additions:
                if record.id in records:
                    raise ResearchError("Accepted records cannot be overwritten")
                records[record.id] = record
                entries.append(Entry(kind=record.kind, ref=reference(record), sha256=digest(encode(record))))
            project = next((record for record in records.values() if isinstance(record, Project)), None)
            if project is None:
                raise ResearchError("Project record required")
            manifest = Manifest(project_id=project.id, generation=current.manifest.generation + 1 if current else 1,
                                parent=current.digest if current else None, entries=entries)
            manifest_bytes = encode(manifest)
            candidate = Snapshot(digest(manifest_bytes), manifest, records)
            self.validate(candidate)
            for checksum, content in blobs.items():
                if digest(content) != checksum:
                    raise ResearchError("Blob digest does not match bytes")
                publish(self.safe(self.data / "blobs" / checksum), content)
            for record in additions:
                if isinstance(record, SourceVersion):
                    self.read_blob(record.blob)
                elif isinstance(record, Passage):
                    self.quote(candidate, record)
            for record, entry in zip(additions, entries[len(entries) - len(additions):], strict=True):
                publish(self.record_path(entry), encode(record))

            if removals and current:
                for entry in current.manifest.entries:
                    if entry.ref.id in removals:
                        rec_path = self.record_path(entry)
                        if rec_path.exists():
                            rec_path.unlink()

            if delete_blobs:
                for blob_sha in delete_blobs:
                    blob_path = self.safe(self.data / "blobs" / blob_sha)
                    if blob_path.exists():
                        blob_path.unlink()

            publish(self.safe(self.data / "project.json"), encode(project))
            publish(self.safe(self.data / "manifests" / f"{candidate.digest}.json"), manifest_bytes)
            replace_head(self.safe(self.data / "HEAD.json"), encode(Head(sha256=candidate.digest)))

            if removals:
                cache_db = self.safe(self.cache / "catalogue.sqlite3")
                if cache_db.exists():
                    cache_db.unlink()

            return candidate

    def citation(self, snapshot: Snapshot, passage: Passage) -> dict[str, Any]:
        source, version = self.quote(snapshot, passage)
        withdrawn = any(
            isinstance(rec, Tombstone)
            and rec.operation in ("withdraw", "purge")
            and rec.target_ref.id in (version.id, source.id)
            for rec in snapshot.records.values()
        )
        return {
            "schema_version": "research-citation-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "passage_id": passage.id, "revision": passage.revision,
            "source_id": source.id, "source_title": source.title,
            "source_version_id": version.id, "source_sha256": version.blob.sha256,
            "verbatim": passage.verbatim, "start": passage.start, "end": passage.end,
            "offset_unit": "unicode_codepoint", "language": passage.language,
            "verification": passage.verification, "redistribution": version.redistribution,
            "context": version.context.model_dump(), "context_status": "user_supplied_unverified",
            "availability": "withdrawn" if withdrawn else "available",
        }
