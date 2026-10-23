"""Immutable local objects and snapshots with a single atomic publication point."""

import errno
import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
import zlib
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import ValidationError

from .acknowledgements import latest_acknowledgements
from .limits import MAX_IMAGE_BYTES, MAX_PDF_BYTES, MAX_RESEARCH_OBJECT_BYTES
from .models import (
    ENTITY,
    Activity,
    AuthoredRecord,
    Blob,
    Claim,
    ClaimRelation,
    Decision,
    DecisionAcknowledgement,
    Dossier,
    Entity,
    Entry,
    EvidenceLink,
    Extraction,
    Head,
    Manifest,
    ManuscriptClaimLink,
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

STORAGE_MARKER = b'{"manifest_encoding":"gzip","schema_version":"research-storage-local/1"}\n'


class ResearchError(ValueError):
    """An invalid, conflicting or unavailable research operation."""


class ResearchConflictError(ResearchError):
    """The caller's accepted snapshot or revision has changed."""


class ResearchStorageError(ResearchError):
    """The archive cannot be safely read or written; an item cannot be skipped."""


class ResearchCleanupError(ResearchStorageError):
    """A snapshot was committed, but listed local artifacts still need cleanup."""

    def __init__(self, accepted_snapshot: str, pending_paths: Iterable[Path], *, project_root: Path):
        self.accepted_snapshot = accepted_snapshot
        self.pending_paths = tuple(sorted(set(pending_paths)))
        paths = ", ".join(path.relative_to(project_root).as_posix() for path in self.pending_paths[:5])
        if len(self.pending_paths) > 5:
            paths += f"; {len(self.pending_paths) - 5} more pending paths"
        super().__init__(
            f"Research snapshot {accepted_snapshot} was committed, but cleanup is incomplete "
            f"({len(self.pending_paths)} pending artifacts): {paths}. "
            "Check storage and permissions before cleaning these retained artifacts. Do not repeat the write."
        )


class ResearchPublicationError(ResearchStorageError):
    """Publication failed with a visible candidate or an unknown HEAD outcome."""

    def __init__(self, candidate_snapshot: str, *, published: bool):
        self.candidate_snapshot = candidate_snapshot
        self.published_snapshot = candidate_snapshot if published else None
        self.outcome: Literal["published", "unknown"] = "published" if published else "unknown"
        message = (
            f"Research snapshot {candidate_snapshot} was published, but durability could not be confirmed."
            if published else
            f"Research publication outcome is unknown for candidate snapshot {candidate_snapshot}; HEAD could not be confirmed."
        )
        super().__init__(message + " Recovery artifacts were retained. Reload and review current state before retrying.")


def _lock_failure(path: Path, error: OSError, *, acquiring: bool = False) -> ResearchStorageError:
    """Describe the failed OS operation without changing the locking protocol."""
    busy = acquiring and (error.errno == errno.EAGAIN or (
        sys.platform == "win32" and error.errno in (errno.EACCES, errno.EDEADLK)
    ))
    if busy:
        context = "Research writer is busy; retry after it finishes"
    elif error.errno == errno.EROFS:
        context = "Research writer lock is on a read-only filesystem; use a writable project location"
    elif error.errno in (errno.EACCES, errno.EPERM):
        context = "Research writer lock access denied; check project directory permissions"
    else:
        context = "Research writer lock I/O failed; check project filesystem availability"
    return ResearchStorageError(f"{context}: {path} ({error})")


def encode(value: StrictModel) -> bytes:
    fields = value.model_dump(mode="json")
    if isinstance(value, AuthoredRecord) and value.change is None:
        fields.pop("change", None)
    content = (json.dumps(fields, ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(content) > MAX_RESEARCH_OBJECT_BYTES:
        raise ResearchError("Research object exceeds the supported size")
    return content


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
    revisions: dict[tuple[str, int], Entity] = field(default_factory=dict)
    lifecycle: dict[tuple[str, str, str], Tombstone] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lifecycle", {
            (record.operation, record.target_kind, record.target_ref.id): record
            for record in self.records.values() if isinstance(record, Tombstone)
        })
        if not self.revisions:
            object.__setattr__(self, "revisions", {
                (record.id, record.revision): record for record in self.records.values()
            })

    def get(self, ref: Reference, expected: type[Model]) -> Model:
        record = self.revisions.get((ref.id, ref.revision))
        if not isinstance(record, expected):
            raise ResearchError("Missing or incompatible pinned reference")
        return record

    def latest(self, record_id: str, expected: type[Model]) -> Model:
        record = self.records.get(record_id)
        if not isinstance(record, expected):
            raise ResearchError("Missing or incompatible record identity")
        return record

    @property
    def project(self) -> Project:
        return self.get(Reference(id=self.manifest.project_id), Project)


class Repository:
    def __init__(self, project: str | Path):
        self.root = Path(project).expanduser().resolve()
        self.data = self.root / "research"
        self.cache = self.root / ".lixity" / "research"
        #: Pre-computed strings for the per-object safety check: a snapshot of a
        #: large archive runs it tens of thousands of times.
        self._root_text = str(self.root)
        self._revisions_text = str(self.data / "revisions")
        #: Last verified snapshot of this instance. Reused only while HEAD still
        #: names the same manifest, so another process's commit is always seen.
        self._snapshot: Snapshot | None = None

    def safe(self, path: Path) -> Path:
        """Rejects paths outside the project or through a symlinked component.

        The check runs once per archive object, so it stays on plain strings and
        ``os.path`` calls: the previous per-component ``pathlib`` checks
        dominated the profile of large archives.
        """
        root, text = self._root_text, os.fspath(path)
        if text != root and not text.startswith(root + os.sep):
            raise ResearchStorageError("Research path escapes the project")
        current = root
        for part in text[len(root):].split(os.sep):
            if not part:
                continue
            if part == os.pardir:
                raise ResearchStorageError("Parent traversal is not allowed inside the research store")
            current = os.path.join(current, part)
            if os.path.islink(current):
                raise ResearchStorageError("Symlinks are not allowed inside the research store")
        return path

    @contextmanager
    def locked(self) -> Iterator[None]:
        lock = self.safe(self.cache / "writer.lock")
        try:
            lock.parent.mkdir(parents=True, exist_ok=True)
            stream = lock.open("a+b")
        except OSError as exc:
            raise _lock_failure(lock, exc) from exc
        with stream:
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
            except OSError as exc:
                raise _lock_failure(lock, exc, acquiring=True) from exc
            try:
                yield
            finally:
                if sys.platform == "win32":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def read(self, path: Path, *, maximum: int = MAX_RESEARCH_OBJECT_BYTES) -> bytes:
        with self.safe(path).open("rb") as stream:
            # Small records should not allocate the full object ceiling per read.
            first_size = min(8192, maximum + 1)
            content = stream.read(first_size)
            if len(content) == first_size and first_size <= maximum:
                if stream.seekable():
                    # A large seekable object needs only one full payload buffer.
                    stream.seek(0)
                    content = stream.read(maximum + 1)
                else:
                    content += stream.read(maximum + 1 - len(content))
        if len(content) > maximum:
            raise ResearchStorageError("Research object exceeds the supported size")
        return content

    def verified(self, path: Path, expected: str, *, maximum: int = MAX_RESEARCH_OBJECT_BYTES) -> bytes:
        content = self.read(path, maximum=maximum)
        if digest(content) != expected:
            raise ResearchStorageError("Research object checksum mismatch")
        return content

    def require_storage(self) -> None:
        """Require the current explicit physical layout before normal access."""
        try:
            marker = self.read(self.data / "storage.json", maximum=4096)
        except FileNotFoundError as exc:
            if not self.safe(self.data / "HEAD.json").exists():
                raise ResearchStorageError("Research store is missing or incomplete; initialize or restore it") from exc
            raise ResearchStorageError("Research manifest storage requires explicit migration to compressed storage") from exc
        try:
            fields = json.loads(marker)
        except (ValueError, UnicodeError) as exc:
            raise ResearchStorageError("Invalid research storage layout") from exc
        if fields != json.loads(STORAGE_MARKER):
            raise ResearchStorageError("Unsupported research storage layout")

    def manifest_path(self, checksum: str) -> Path:
        """Resolve a canonical JSON content hash into the current physical layout."""
        return self.safe(self._manifest_path(checksum))

    def _manifest_path(self, checksum: str) -> Path:
        """Construct a manifest path; its I/O owner must still check containment."""
        if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
            raise ResearchStorageError("Invalid manifest content digest")
        return self.data / "manifests" / f"{checksum}.json.gz"

    def read_manifest(self, checksum: str) -> bytes:
        """Bound decompression and verify the exact original JSON content hash."""
        self.require_storage()
        return self._read_compressed_manifest(checksum)

    def _read_compressed_manifest(self, checksum: str) -> bytes:
        """Verify a staged gzip object before a migration publishes its marker."""
        compressed = self.read(self._manifest_path(checksum), maximum=MAX_RESEARCH_OBJECT_BYTES + 65536)
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
                content = stream.read(MAX_RESEARCH_OBJECT_BYTES + 1)
        except (OSError, EOFError, zlib.error) as exc:
            raise ResearchStorageError("Invalid or truncated compressed research manifest") from exc
        if len(content) > MAX_RESEARCH_OBJECT_BYTES:
            raise ResearchStorageError("Research object exceeds the supported size")
        if digest(content) != checksum:
            raise ResearchStorageError("Research object checksum mismatch")
        return content

    def write_manifest(self, checksum: str, content: bytes) -> None:
        """Publish deterministic gzip without changing canonical JSON bytes."""
        if len(content) > MAX_RESEARCH_OBJECT_BYTES or digest(content) != checksum:
            raise ResearchStorageError("Invalid research manifest content")
        if self.manifest_path(checksum).exists():
            if self._read_compressed_manifest(checksum) != content:
                raise ResearchStorageError("Immutable compressed manifest conflict")
            return
        publish(self.manifest_path(checksum), gzip.compress(content, compresslevel=6, mtime=0))

    def record_path(self, entry: Entry) -> Path:
        return self.safe(self._record_path(entry))

    def _record_path(self, entry: Entry) -> Path:
        """Construct a revision path; its I/O owner must still check containment."""
        return Path(self._revisions_text, entry.kind, entry.ref.id[9:], f"{entry.ref.revision}.json")

    def snapshot(self, kinds: frozenset[str] | None = None) -> Snapshot:
        """Read the accepted snapshot; ``kinds`` narrows large archives.

        List commands pass the record kinds they inspect (project and tombstone
        state are always read) so a large archive is not fully loaded per call.
        Cross-kind invariants that need a filtered-out kind are skipped, so a
        caller must include every kind whose records it reads. Write paths and
        lookups keep the default full snapshot.
        """
        try:
            head = Head.model_validate_json(self.read(self.data / "HEAD.json", maximum=4096))
            if kinds is None:
                cached = self._snapshot
                if cached is not None and cached.digest == head.sha256:
                    self.require_storage()
                    return cached
            wanted = None if kinds is None else kinds | {"project", "tombstone"}
            manifest = Manifest.model_validate_json(self.read_manifest(head.sha256))
            records: dict[str, Entity] = {}
            revisions: dict[tuple[str, int], Entity] = {}
            for entry in manifest.entries:
                if wanted is not None and entry.kind not in wanted:
                    continue
                record = ENTITY.validate_json(self.verified(self._record_path(entry), entry.sha256))
                key = (record.id, record.revision)
                if key in revisions or reference(record) != entry.ref or record.kind != entry.kind:
                    raise ResearchError("Duplicate or mismatched record identity")
                revisions[key] = record
                previous = records.get(record.id)
                if previous is not None and previous.kind != record.kind:
                    raise ResearchError("Record identity cannot change kind")
                if previous is None or previous.revision < record.revision:
                    records[record.id] = record
            snapshot = Snapshot(head.sha256, manifest, records, revisions=revisions)
            self.validate(snapshot, kinds=wanted)
            if self.read(self.data / "project.json") != encode(snapshot.project):
                raise ResearchError("Project configuration does not match its accepted revision")
            if kinds is None:
                self._snapshot = snapshot
            return snapshot
        except (ValidationError, json.JSONDecodeError):
            raise ResearchStorageError("Invalid or unsupported research schema") from None
        except FileNotFoundError as exc:
            raise ResearchStorageError("Research store is missing or incomplete; initialize or restore it") from exc
        except ResearchStorageError:
            raise
        except ResearchError as exc:
            raise ResearchStorageError(str(exc)) from exc

    def validate(self, snapshot: Snapshot, *, kinds: frozenset[str] | None = None) -> None:
        """Archive invariants for the loaded records.

        With ``kinds`` (a list-command filter), checks that need a record kind
        outside the filter are skipped; per-record and same-kind invariants
        still run. Write paths always validate the full archive.
        """
        project = snapshot.project

        def loaded(kind: str) -> bool:
            return kinds is None or kind in kinds

        histories: dict[str, list[Entity]] = {}
        for (record_id, number), record in snapshot.revisions.items():
            if (record_id, number) != (record.id, record.revision) or record_id not in snapshot.records:
                raise ResearchError("Mismatched revision index")
            histories.setdefault(record_id, []).append(record)
        for record in snapshot.records.values():
            history = histories.get(record.id, [])
            if len(history) != record.revision or any(
                (record.id, number) not in snapshot.revisions
                for number in range(1, record.revision + 1)
            ):
                raise ResearchError("Authored revision history must be contiguous")
            if any(revision.kind != record.kind for revision in history):
                raise ResearchError("Record identity cannot change kind")
            if isinstance(record, Dossier):
                first_geography = min((revision.revision for revision in history
                                       if revision.schema_version == "research-local/8"), default=None)
                if first_geography is not None and any(
                    revision.revision >= first_geography and revision.schema_version != "research-local/8"
                    for revision in history
                ):
                    raise ResearchError("Dossier revisions must retain version 8 after geography opt-in")
            if int(record.schema_version.rsplit("/", 1)[1]) > int(snapshot.manifest.schema_version.rsplit("/", 1)[1]):
                raise ResearchError(f"Version {record.schema_version[-1]} records require manifest version {record.schema_version[-1]} or later")
        sequences: set[tuple[str, int]] = set()
        descriptors: dict[str, Blob] = {}
        purged_passages = {
            record.target_ref
            for record in snapshot.records.values()
            if isinstance(record, Tombstone)
            and record.operation == "purge"
            and record.target_kind == "passage"
        }
        for record in snapshot.revisions.values():
            if record.project_id != project.id:
                raise ResearchError("Cross-project reference rejected")
            if isinstance(record, Project) and record.id != project.id:
                raise ResearchError("Multiple project records rejected")
            if isinstance(record, SourceVersion):
                from .images import IMAGE_TYPES
                if record.blob.media_type in IMAGE_TYPES and record.blob.byte_length > MAX_IMAGE_BYTES:
                    raise ResearchError("Image blobs must be at most 16 MiB")
                if loaded("source"):
                    snapshot.get(record.source_ref, Source)
                if descriptors.setdefault(record.blob.sha256, record.blob) != record.blob:
                    raise ResearchError("Inconsistent descriptors for the same blob")
                key = (record.source_ref.id, record.sequence)
                if key in sequences:
                    raise ResearchError("Duplicate source version sequence")
                sequences.add(key)
            elif isinstance(record, Activity):
                if loaded("source_version"):
                    snapshot.get(record.source_version_ref, SourceVersion)
            elif isinstance(record, Extraction):
                if loaded("source_version") and loaded("activity"):
                    version = snapshot.get(record.source_version_ref, SourceVersion)
                    activity = snapshot.get(record.activity_ref, Activity)
                    if activity.source_version_ref != record.source_version_ref:
                        raise ResearchError("Extraction provenance does not match source bytes")
                    if activity.operation == "extract_utf8" and version.blob != record.text_blob:
                        raise ResearchError("Extraction provenance does not match source bytes")
                if descriptors.setdefault(record.text_blob.sha256, record.text_blob) != record.text_blob:
                    raise ResearchError("Inconsistent descriptors for the same blob")
            elif isinstance(record, Passage):
                if loaded("extraction"):
                    snapshot.get(record.extraction_ref, Extraction)
            elif isinstance(record, Dossier):
                if loaded("source_version"):
                    from .images import resolve_dossier_images
                    resolve_dossier_images(snapshot, record.body)
                if loaded("passage"):
                    for ref in record.evidence_refs:
                        if ref not in purged_passages or ref.id in snapshot.records:
                            snapshot.get(ref, Passage)
            elif isinstance(record, Claim):
                if record.dossier_ref and loaded("dossier"):
                    snapshot.get(record.dossier_ref, Dossier)
            elif isinstance(record, ClaimRelation):
                if loaded("claim"):
                    snapshot.get(record.from_claim_ref, Claim)
                    snapshot.get(record.to_claim_ref, Claim)
            elif isinstance(record, ManuscriptClaimLink):
                if loaded("claim"):
                    snapshot.get(record.claim_ref, Claim)
            elif isinstance(record, EvidenceLink):
                if loaded("claim"):
                    snapshot.get(record.claim_ref, Claim)
                if loaded("passage") and (record.passage_ref not in purged_passages or record.passage_ref.id in snapshot.records):
                    snapshot.get(record.passage_ref, Passage)
            elif isinstance(record, Decision):
                if record.claim_ref and loaded("claim"):
                    snapshot.get(record.claim_ref, Claim)
                if loaded("dossier"):
                    for ref in record.dossier_refs:
                        snapshot.get(ref, Dossier)
            elif isinstance(record, DecisionAcknowledgement):
                if loaded("decision") and loaded("dossier"):
                    snapshot.get(record.decision_ref, Decision)
                    snapshot.get(record.dossier_ref, Dossier)
                    if record.supersedes_ref:
                        snapshot.get(record.supersedes_ref, DecisionAcknowledgement)
            elif isinstance(record, Tombstone):
                pass
        try:
            latest_acknowledgements(snapshot.records.values())
        except ValueError as error:
            raise ResearchError(str(error)) from None

    def read_blob(self, descriptor: Blob) -> bytes:
        if type(descriptor.byte_length) is not int or not 0 <= descriptor.byte_length <= MAX_PDF_BYTES:
            raise ResearchError(f"Invalid research blob length; supported blobs are at most {MAX_PDF_BYTES // (1024 * 1024)} MiB")
        content = self.verified(self.data / "blobs" / descriptor.sha256, descriptor.sha256,
                                maximum=MAX_PDF_BYTES)
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

    def _preserve_unpublished_revision(self, path: Path, record: Entity, current: Snapshot | None) -> None:
        """Preserve a valid unaccepted next revision before reusing its numbered slot.

        The caller holds the writer lock. Accepted authored history is never
        removed, so the current manifest is authoritative for accepted slots.
        Restoring only HEAD is unsupported; restore the whole archive instead.
        """
        if not path.exists():
            return
        content = self.read(path)
        if content == encode(record):
            return
        if (current is None or not isinstance(record, AuthoredRecord)
                or (record.id, record.revision) in current.revisions):
            raise ResearchError("Immutable object conflict")
        previous = current.records.get(record.id)
        try:
            unpublished = ENTITY.validate_json(content)
        except ValidationError:
            raise ResearchError("Invalid unpublished revision; preserve the archive for recovery") from None
        if (not isinstance(unpublished, AuthoredRecord) or previous is None
                or unpublished.id != record.id or unpublished.kind != record.kind
                or unpublished.project_id != current.project.id
                or unpublished.revision != record.revision
                or unpublished.revision != previous.revision + 1):
            raise ResearchError("Incompatible unpublished revision; preserve the archive for recovery")
        preserved = self.safe(path.with_name(f"{record.revision}.{digest(content)}.unpublished"))
        publish(preserved, content)
        path.unlink()
        sync_directory(path.parent)

    def commit(
        self,
        additions: list[Entity],
        blobs: dict[str, bytes],
        expected: Snapshot | None,
        removals: set[str] | None = None,
        delete_blobs: set[str] | None = None,
    ) -> Snapshot:
        try:
            return self._commit(additions, blobs, expected, removals, delete_blobs)
        except (ResearchConflictError, ResearchStorageError):
            raise
        except ResearchError as exc:
            raise ResearchStorageError(str(exc)) from exc

    def prepare_commit(
        self, additions: list[Entity], current: Snapshot | None,
        removals: set[str] | None = None,
    ) -> tuple[Snapshot, bytes]:
        """Validate a prospective snapshot and encode its manifest without I/O.

        Writers still lock, reload and compare HEAD before calling this
        owner. Read-only authored previews use their observed snapshot;
        filesystem availability and retained blob checks remain write-time.
        """
        records = dict(current.records) if current else {}
        revisions = dict(current.revisions) if current else {}
        entries = list(current.manifest.entries) if current else []

        if removals:
            if any(isinstance(records.get(record_id), (AuthoredRecord, DecisionAcknowledgement)) for record_id in removals):
                raise ResearchError("Authored revision history cannot be removed")
            records = {k: v for k, v in records.items() if k not in removals}
            revisions = {key: record for key, record in revisions.items() if key[0] not in removals}
            entries = [e for e in entries if e.ref.id not in removals]

        for record in additions:
            try:
                ENTITY.validate_json(encode(record))
            except ValidationError:
                raise ResearchError("Invalid or unsupported research schema") from None
            previous = records.get(record.id)
            if previous is not None:
                if (not isinstance(record, AuthoredRecord) or previous.kind != record.kind
                        or record.revision != previous.revision + 1):
                    raise ResearchError("Accepted records cannot be overwritten; append the next authored revision")
            elif record.revision != 1:
                raise ResearchError("A record must start at revision 1")
            records[record.id] = record
            revisions[(record.id, record.revision)] = record
            entries.append(Entry(kind=record.kind, ref=reference(record), sha256=digest(encode(record))))
        project = next((record for record in records.values() if isinstance(record, Project)), None)
        if project is None:
            raise ResearchError("Project record required")
        schema: Literal["research-manifest-local/1", "research-manifest-local/2", "research-manifest-local/3", "research-manifest-local/4", "research-manifest-local/5", "research-manifest-local/6", "research-manifest-local/7", "research-manifest-local/8", "research-manifest-local/9"]
        schema = ("research-manifest-local/9" if any(record.schema_version == "research-local/9" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/9")
                  else "research-manifest-local/8" if any(record.schema_version == "research-local/8" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/8")
                  else "research-manifest-local/7" if any(record.schema_version == "research-local/7" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/7")
                  else "research-manifest-local/6" if any(record.schema_version == "research-local/6" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/6")
                  else "research-manifest-local/5" if any(record.schema_version == "research-local/5" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/5")
                  else "research-manifest-local/4" if any(record.schema_version == "research-local/4" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/4")
                  else "research-manifest-local/3" if any(record.schema_version == "research-local/3" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/3")
                  else "research-manifest-local/2" if any(record.schema_version == "research-local/2" for record in records.values())
                  or (current and current.manifest.schema_version == "research-manifest-local/2")
                  else "research-manifest-local/1")
        manifest = Manifest(schema_version=schema, project_id=project.id, generation=current.manifest.generation + 1 if current else 1,
                            parent=current.digest if current else None, entries=entries)
        manifest_bytes = encode(manifest)
        candidate = Snapshot(digest(manifest_bytes), manifest, records, revisions=revisions)
        for record in additions:
            if isinstance(record, Dossier):
                from .images import validate_image_changes
                predecessor = current.records.get(record.id) if current else None
                retained = predecessor.evidence_refs if isinstance(predecessor, Dossier) else []
                validate_image_changes(candidate, record.body, predecessor.body if isinstance(predecessor, Dossier) else "")
                for ref in record.evidence_refs:
                    if ref not in retained:
                        candidate.get(ref, Passage)
            elif isinstance(record, EvidenceLink):
                predecessor = current.records.get(record.id) if current else None
                if not isinstance(predecessor, EvidenceLink) or record.passage_ref != predecessor.passage_ref:
                    candidate.get(record.passage_ref, Passage)
            elif isinstance(record, Tombstone) and record.operation == "purge" and record.target_kind == "passage":
                if current is None or not removals or record.target_ref.id not in removals:
                    raise ResearchError("Passage purge tombstone requires an accepted passage removal")
                current.get(record.target_ref, Passage)
            elif isinstance(record, Tombstone) and record.operation == "purge" and record.target_kind == "source_version":
                if current is None or not removals or record.target_ref.id not in removals:
                    raise ResearchError("Source version purge tombstone requires an accepted version removal")
                removed_version = current.get(record.target_ref, SourceVersion)
                if record.source_ref is not None and record.source_ref != removed_version.source_ref:
                    raise ResearchError("Purge tombstone source ownership does not match the removed source version")
        self.validate(candidate)
        return candidate, manifest_bytes

    def _commit(
        self,
        additions: list[Entity],
        blobs: dict[str, bytes],
        expected: Snapshot | None,
        removals: set[str] | None,
        delete_blobs: set[str] | None,
    ) -> Snapshot:
        with self.locked():
            current = self.snapshot() if self.safe(self.data / "HEAD.json").exists() else None
            if (current.digest if current else None) != (expected.digest if expected else None):
                raise ResearchConflictError("Research snapshot changed; retry from the current HEAD")
            # An unchanged operation still checks HEAD under the writer lock.
            if current is not None and not (additions or blobs or removals or delete_blobs):
                return current
            candidate, manifest_bytes = self.prepare_commit(additions, current, removals)
            entries = candidate.manifest.entries
            project = candidate.project
            cleanup_paths: list[Path] = []
            if removals and current:
                cleanup_paths.extend(self.record_path(entry) for entry in current.manifest.entries
                                     if entry.ref.id in removals)
            if delete_blobs:
                cleanup_paths.extend(self.safe(self.data / "blobs" / sha) for sha in sorted(delete_blobs))
            if removals:
                cleanup_paths.append(self.safe(self.cache / "catalogue.sqlite3"))
            for checksum, content in blobs.items():
                if digest(content) != checksum:
                    raise ResearchError("Blob digest does not match bytes")
                publish(self.safe(self.data / "blobs" / checksum), content)
            for record in additions:
                if isinstance(record, SourceVersion):
                    content = self.read_blob(record.blob)
                    from .images import IMAGE_TYPES, validate_image
                    from .media import VIDEO_TYPES, validate_media
                    if record.blob.media_type in IMAGE_TYPES:
                        image = validate_image(content)
                        if image["media_type"] != record.blob.media_type:
                            raise ResearchError("Image bytes do not match their blob media type")
                    elif (record.blob.media_type in VIDEO_TYPES
                          or (record.blob.media_type == "application/pdf" and record.schema_version == "research-local/9")):
                        if validate_media(content)["media_type"] != record.blob.media_type:
                            raise ResearchError("Media bytes do not match their blob media type")
                elif isinstance(record, Passage):
                    self.quote(candidate, record)
            created_paths: list[Path] = []
            try:
                for record, entry in zip(additions, entries[len(entries) - len(additions):], strict=True):
                    path = self.record_path(entry)
                    self._preserve_unpublished_revision(path, record, current)
                    if (isinstance(record, AuthoredRecord) and record.revision > 1
                            and not removals and not delete_blobs and not path.exists()):
                        created_paths.append(path)
                    publish(path, encode(record))

                publish(self.safe(self.data / "project.json"), encode(project))
                if current is None:
                    publish(self.safe(self.data / "storage.json"), STORAGE_MARKER)
                self.write_manifest(candidate.digest, manifest_bytes)
                replace_head(self.safe(self.data / "HEAD.json"), encode(Head(sha256=candidate.digest)))
            except (OSError, ResearchError) as error:
                # Only clean this attempt's authored revision files when HEAD
                # is known to be unchanged. Visible or uninspectable publication
                # retains every recovery file and never claims durable success.
                try:
                    head = Head.model_validate_json(self.read(self.data / "HEAD.json"))
                except FileNotFoundError:
                    head = None
                except (OSError, ResearchError, ValidationError):
                    raise ResearchPublicationError(candidate.digest, published=False) from error
                observed = head.sha256 if head else None
                if observed == candidate.digest:
                    raise ResearchPublicationError(candidate.digest, published=True) from error
                if observed != (current.digest if current else None):
                    raise ResearchPublicationError(candidate.digest, published=False) from error
                for path in created_paths:
                    with suppress(OSError):
                        path.unlink(missing_ok=True)
                raise

            # Orphan deletion and cache invalidation happen only after HEAD has been
            # atomically rotated. A crash here leaves unreferenced but harmless files;
            # a crash before replace_head leaves the old, fully consistent archive intact.
            self._snapshot = candidate
            pending_paths = []
            cleanup_cause: OSError | ResearchError | None = None
            for path in cleanup_paths:
                try:
                    self.safe(path).unlink(missing_ok=True)
                except (OSError, ResearchError) as error:  # noqa: PERF203 - Attempt every independent filesystem cleanup.
                    pending_paths.append(path)
                    if cleanup_cause is None:
                        cleanup_cause = error
            if pending_paths:
                raise ResearchCleanupError(candidate.digest, pending_paths, project_root=self.root) from cleanup_cause
            return candidate

    def citation(self, snapshot: Snapshot, passage: Passage) -> dict[str, Any]:
        source, version = self.quote(snapshot, passage)
        withdrawn = any(
            operation in ("withdraw", "purge") and identifier in (version.id, source.id)
            for operation, _kind, identifier in snapshot.lifecycle
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


class _PlainManifestRepository(Repository):
    """Former physical layout, restricted to explicit migration and portable restore.

    Normal application reads and writes always use ``Repository``. This transport
    never selects a format per file and never writes new accepted revisions.
    """

    def require_storage(self) -> None:
        pass

    def manifest_path(self, checksum: str) -> Path:
        return super().manifest_path(checksum).with_suffix("")

    def read_manifest(self, checksum: str) -> bytes:
        return self.verified(self.manifest_path(checksum), checksum)
