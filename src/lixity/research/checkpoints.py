"""Opt-in sequential imports; preparation is private local state, never evidence."""

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, ValidationError

from . import api, ocr
from .models import (
    ENTITY,
    Activity,
    Blob,
    Digest,
    Entity,
    Extraction,
    Identifier,
    Language,
    Manifest,
    Passage,
    Reference,
    Source,
    SourceContext,
    SourceVersion,
    StrictModel,
)
from .repository import (
    Repository,
    ResearchConflictError,
    ResearchError,
    Snapshot,
    digest,
    encode,
    publish,
)

MAX_CHECKPOINT_BYTES = 64 * 1024 * 1024


class _Options(StrictModel):
    source_id: Identifier | None = None
    title: str | None = None
    language: Language | None = None
    actor: str = "local-author"
    context: SourceContext | None = None
    origin_url: str | None = None
    allow_fallback: bool = False


class _Receipt(StrictModel):
    schema_version: Literal["research-ingest-local/1"] = "research-ingest-local/1"
    source_id: Identifier
    source_version_id: Identifier
    unchanged: bool
    dry_run: Literal[False] = False
    passages: int = Field(ge=0, le=5000)
    warnings: list[str]
    snapshot: Digest | None = None


class _Prepared(StrictModel):
    expected_snapshot: Digest
    records: list[dict[str, Any]] = Field(max_length=5004)
    blobs: list[Blob]
    result: _Receipt
    title: str


class _Item(StrictModel):
    file: str
    sha256: Digest
    byte_length: int = Field(gt=0, le=api.MAX_PDF_BYTES)
    source_id: Identifier
    base_version_id: Identifier | None = None
    status: Literal["pending", "prepared", "failed", "succeeded"] = "pending"
    prepared: _Prepared | None = None
    result: _Receipt | None = None
    error: str | None = None


class _State(StrictModel):
    schema_version: Literal["research-import-checkpoint-local/1"] = "research-import-checkpoint-local/1"
    project_id: Identifier
    expected_snapshot: Digest
    configuration: Digest
    options: _Options
    items: list[_Item] = Field(min_length=1, max_length=1000)


class _Store:
    def __init__(self, repository: Repository, checkpoint: str | Path):
        self.repository = repository
        directory = repository.cache / "imports"
        requested = Path(checkpoint).expanduser()
        path = requested if requested.is_absolute() else directory / requested
        # Normalize parent traversals without resolving away a forbidden symlink.
        path = Path(os.path.abspath(path))
        if not path.is_relative_to(directory) or path == directory or path.suffix != ".json":
            raise ResearchError("Checkpoint must be a .json path inside the project's .lixity/research/imports directory")
        self.path = repository.safe(path)
        self.work = repository.safe(path.with_name(path.name + ".work"))
        self.objects = repository.safe(self.work / "objects")
        # Reuse the existing platform lock implementation at a checkpoint-specific scope.
        self.lock_repository = Repository(repository.root)
        self.lock_repository.cache = self.work

    def load(self) -> _State:
        try:
            return _State.model_validate_json(self.repository.read(self.path, maximum=MAX_CHECKPOINT_BYTES))
        except FileNotFoundError:
            raise ResearchError("Import checkpoint is missing; start one with files before resuming") from None
        except ValidationError:
            raise ResearchError("Invalid or unsupported import checkpoint; explicitly discard it if no longer needed") from None

    def save(self, state: _State) -> None:
        content = encode(state)
        if len(content) > MAX_CHECKPOINT_BYTES:
            raise ResearchError("Import checkpoint exceeds the supported size; discard it and reduce retained work or use ordinary ingest")
        publish(self.repository.safe(self.path), content, replace=True)

    def blob_path(self, index: int, sha256: str) -> Path:
        return self.repository.safe(self.objects / str(index) / sha256)

    def clear_objects(self, index: int | None = None) -> None:
        path = self.objects if index is None else self.objects / str(index)
        path = self.repository.safe(path)
        if path.exists():
            # Reject links throughout private staging before removing its own payloads.
            for child in path.rglob("*"):
                self.repository.safe(child)
            shutil.rmtree(path)

    def discard(self) -> None:
        self.clear_objects()
        self.repository.safe(self.path).unlink(missing_ok=True)


def _configuration() -> str:
    """Fingerprint configured inputs, without claiming to attest worker/model identity."""
    values = {key: value for key, value in os.environ.items()
              if key.startswith(("LIXITY_OCR_", "LIXITY_UNLIMITED_OCR_"))}
    values["TESSDATA_PREFIX"] = os.environ.get("TESSDATA_PREFIX", "")
    adapter_home = os.environ.get("LIXITY_UNLIMITED_OCR_HOME")
    resolved_home = str(Path(adapter_home).expanduser().resolve()) if adapter_home else None
    tessdata = os.environ.get("TESSDATA_PREFIX")
    resolved_tessdata = os.path.abspath(tessdata) if tessdata else None
    tools: dict[str, str | None] = {}
    for command in ("pdftoppm", "pdftotext", "pdfinfo", "tesseract", os.environ.get("LIXITY_OCR_WORKER", "")):
        if not command:
            continue
        executable = shutil.which(command)
        signature = None
        if executable:
            checksum = hashlib.sha256()
            with Path(executable).open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(block)
            signature = f"{Path(executable).resolve()}:{checksum.hexdigest()}"
        tools[command] = signature
    return digest(json.dumps({"preparation": "capture/1", "environment": values, "tools": tools,
                              "adapter_home": resolved_home, "tessdata_prefix": resolved_tessdata,
                              "model_snapshot": ocr.MODEL_SNAPSHOT,
                              "recipe_revision": ocr.INTEGRATION_RECIPE_REVISION},
                             sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _registry(repository: Repository) -> Repository:
    registry = Repository(repository.root)
    registry.cache = repository.cache / "imports" / ".registry"
    return registry


def _latest(snapshot: Snapshot, source_id: str) -> SourceVersion | None:
    versions = [record for record in snapshot.records.values()
                if isinstance(record, SourceVersion) and record.source_ref.id == source_id]
    return max(versions, key=lambda record: record.sequence) if versions else None


def _replace_item(state: _State, index: int, item: _Item, **changes: Any) -> _State:
    items = list(state.items)
    items[index] = item
    return state.model_copy(update={"items": items, **changes})


def _read_prepared(store: _Store, state: _State, index: int) -> tuple[list[Entity], dict[str, bytes]]:
    item = state.items[index]
    prepared = item.prepared
    if prepared is None:
        raise ResearchError("Import checkpoint has no retained preparation")
    try:
        records = [ENTITY.validate_json(json.dumps(record)) for record in prepared.records]
    except ValidationError:
        raise ResearchError("Invalid retained import records") from None
    if (not records or any(not isinstance(record, (Source, SourceVersion, Activity, Extraction, Passage))
                           or record.project_id != state.project_id or record.revision != 1 for record in records)
            or len({record.id for record in records}) != len(records)):
        raise ResearchError("Invalid retained capture identity or record kinds")
    versions = [record for record in records if isinstance(record, SourceVersion)]
    extractions = [record for record in records if isinstance(record, Extraction)]
    activities = [record for record in records if isinstance(record, Activity)]
    sources = [record for record in records if isinstance(record, Source)]
    passages = [record for record in records if isinstance(record, Passage)]
    from .images import IMAGE_TYPES, validate_image
    if len(versions) == 1 and versions[0].blob.media_type in IMAGE_TYPES:
        version = versions[0]
        if (extractions or activities or passages or len(sources) != (0 if state.options.source_id else 1)
                or version.id != prepared.result.source_version_id or version.source_ref.id != item.source_id
                or prepared.result.source_id != item.source_id or version.blob.sha256 != item.sha256
                or version.blob.byte_length != item.byte_length or prepared.result.passages != 0
                or (sources and sources[0].id != item.source_id) or prepared.blobs != [version.blob]):
            raise ResearchError("Invalid retained image capture structure or identity")
        content = store.repository.read(store.blob_path(index, version.blob.sha256), maximum=api.MAX_IMAGE_BYTES)
        if digest(content) != version.blob.sha256 or len(content) != version.blob.byte_length:
            raise ResearchError("Retained image blob checksum or length mismatch")
        if validate_image(content)["media_type"] != version.blob.media_type:
            raise ResearchError("Retained image bytes do not match their media type")
        return records, {version.blob.sha256: content}
    if (len(versions) != 1 or len(extractions) != 1 or len(activities) != 1 or not passages
            or len(sources) != (0 if state.options.source_id else 1)):
        raise ResearchError("Invalid retained capture structure")
    version, extraction, activity = versions[0], extractions[0], activities[0]
    if (version.id != prepared.result.source_version_id or version.source_ref.id != item.source_id
            or prepared.result.source_id != item.source_id or version.blob.sha256 != item.sha256
            or version.blob.byte_length != item.byte_length or prepared.result.passages != len(passages)
            or (sources and sources[0].id != item.source_id)
            or extraction.source_version_ref.id != version.id or activity.source_version_ref.id != version.id
            or extraction.activity_ref.id != activity.id):
        raise ResearchError("Retained capture does not match checkpoint source identity")
    descriptors = {blob.sha256: blob for blob in prepared.blobs}
    if (len(descriptors) != len(prepared.blobs) or descriptors.get(version.blob.sha256) != version.blob
            or descriptors.get(extraction.text_blob.sha256) != extraction.text_blob
            or set(descriptors) != {version.blob.sha256, extraction.text_blob.sha256}):
        raise ResearchError("Invalid retained blob descriptors")
    blobs = {}
    for blob in prepared.blobs:
        content = store.repository.read(store.blob_path(index, blob.sha256), maximum=api.MAX_PDF_BYTES)
        if digest(content) != blob.sha256 or len(content) != blob.byte_length:
            raise ResearchError("Retained import blob checksum or length mismatch")
        blobs[blob.sha256] = content
    try:
        text = blobs[extraction.text_blob.sha256].decode("utf-8")
    except UnicodeDecodeError:
        raise ResearchError("Retained extraction text is not UTF-8") from None
    if any(passage.extraction_ref.id != extraction.id or text[passage.start:passage.end] != passage.verbatim
           for passage in passages):
        raise ResearchError("Retained extraction does not match its passage spans")
    return records, blobs


def _verify_receipt(repository: Repository, snapshot: Snapshot, item: _Item) -> None:
    if item.result is None:
        raise ResearchError("Successful checkpoint item is missing its accepted receipt")
    version = snapshot.get(Reference(id=item.result.source_version_id), SourceVersion)
    snapshot.get(Reference(id=item.source_id), Source)
    if version.source_ref.id != item.source_id or version.blob.sha256 != item.sha256:
        raise ResearchError("Checkpoint receipt does not match the accepted source")
    repository.read_blob(version.blob)


def _recover(store: _Store, state: _State, snapshot: Snapshot) -> _State:
    for index, initial_item in enumerate(state.items):
        item = initial_item
        if item.status == "succeeded":
            _verify_receipt(store.repository, snapshot, item)
            store.clear_objects(index)
            continue
        if item.prepared is None:
            continue
        records, _ = _read_prepared(store, state, index)
        accepted = [snapshot.revisions.get((record.id, record.revision)) for record in records]
        if not any(record is not None for record in accepted):
            continue
        if any(record is None or encode(record) != encode(expected)
               for record, expected in zip(accepted, records, strict=True)):
            raise ResearchError("Prepared capture was changed or purged; refusing to recreate it")
        for blob in item.prepared.blobs:
            store.repository.read_blob(blob)
        # Only advance HEAD automatically when this is exactly the checkpoint's own commit.
        expected = state.expected_snapshot
        if snapshot.manifest.parent == item.prepared.expected_snapshot:
            base_digest = item.prepared.expected_snapshot
            base = Manifest.model_validate_json(store.repository.verified(
                store.repository.data / "manifests" / f"{base_digest}.json", base_digest))
            tail = snapshot.manifest.entries[len(base.entries):]
            if (snapshot.manifest.entries[:len(base.entries)] == base.entries and len(tail) == len(records)
                    and all(entry.ref.id == record.id and entry.sha256 == digest(encode(record))
                            for entry, record in zip(tail, records, strict=True))):
                expected = snapshot.digest
        receipt = item.prepared.result.model_copy(update={"snapshot": snapshot.digest})
        item = item.model_copy(update={"status": "succeeded", "result": receipt, "prepared": None, "error": None})
        state = _replace_item(state, index, item, expected_snapshot=expected)
        store.save(state)
        store.clear_objects(index)
    return state


def _result(store: _Store, state: _State) -> dict[str, Any]:
    items = []
    for item in state.items:
        result: dict[str, Any] = {"file": item.file, "status": item.status, "ok": item.status == "succeeded"}
        if item.result:
            result.update(item.result.model_dump(mode="json"))
        if item.error:
            result["error"] = item.error
        items.append(result)
    succeeded = sum(item.status == "succeeded" for item in state.items)
    failed = sum(item.error is not None for item in state.items)
    return {"schema_version": "research-checkpoint-ingest-local/1", "project_id": state.project_id,
            "checkpoint": str(store.path), "snapshot": state.expected_snapshot, "items": items,
            "succeeded": succeeded, "failed": failed, "pending": len(items) - succeeded - failed,
            "total": len(items), "complete": succeeded == len(items), "dry_run": False}


def ingest(project: str | Path, files: Sequence[str | Path] | None = None, *, checkpoint: str | Path,
           resume: bool = False, allow_retention: bool = False, source_id: str | None = None,
           title: str | None = None, language: str | None = None, actor: str | None = None,
           dry_run: bool = False, context: Mapping[str, Any] | None = None, origin_url: str | None = None,
           expected_snapshot: str | None = None, allow_fallback: bool | None = None,
           progress_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (--allow-retention)")
    if dry_run:
        raise ResearchError("Checkpoint imports cannot use --dry-run; ordinary ingest previews do not write")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_snapshot is not None and expected_snapshot != snapshot.digest:
        raise ResearchConflictError("Research snapshot changed; supply the current expected snapshot")
    store = _Store(repository, checkpoint)
    if progress_callback:
        progress_callback("checkpoint", "Validating checkpoint configuration, source identities and retained preparation...")
    supplied = {"source_id": source_id, "title": title, "language": language, "actor": actor,
                "context": SourceContext.model_validate(dict(context)) if context is not None else None,
                "origin_url": origin_url, "allow_fallback": allow_fallback}
    configuration = _configuration()
    with store.lock_repository.locked():
        if resume:
            state = store.load()
            if state.project_id != snapshot.project.id:
                raise ResearchError("Import checkpoint belongs to another project")
            if any(value is not None and getattr(state.options, key) != value for key, value in supplied.items()):
                raise ResearchError("Import checkpoint metadata or settings changed; discard it to start another capture")
            if state.configuration != configuration:
                raise ResearchError("OCR configuration changed; discard the checkpoint to extract again")
            if files is not None and [str(Path(file).expanduser().resolve()) for file in files] != [item.file for item in state.items]:
                raise ResearchError("Checkpoint file identity or order changed")
        else:
            if store.path.exists():
                raise ResearchError("Import checkpoint already exists; explicitly resume or discard it")
            if not files or len(files) > 1000 or (source_id and len(files) != 1) or (title and len(files) != 1):
                raise ResearchError("Checkpoint requires 1 to 1000 files; title and source identity apply to one file only")
            options = _Options.model_validate({key: value for key, value in supplied.items() if value is not None})
            if origin_url is not None:
                SourceContext.model_validate({**(options.context or SourceContext()).model_dump(), "origin_url": origin_url})
            if source_id:
                snapshot.get(Reference(id=source_id), Source)
            latest = _latest(snapshot, source_id) if source_id else None
            items = []
            for file in files:
                path = Path(file).expanduser().resolve()
                content = api._read_source_bytes(path)
                items.append(_Item(file=str(path), sha256=digest(content), byte_length=len(content),
                                   source_id=source_id or uuid4().urn, base_version_id=latest.id if latest else None))
            state = _State(project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
                           configuration=configuration, options=options, items=items)
            # Registration and purge share a short lock; expensive extraction does not.
            with _registry(repository).locked():
                if repository.snapshot().digest != snapshot.digest:
                    raise ResearchConflictError("Research snapshot changed before checkpoint registration")
                store.save(state)

        for item in state.items:
            content = api._read_source_bytes(Path(item.file))
            if digest(content) != item.sha256 or len(content) != item.byte_length:
                raise ResearchError("Source file bytes changed since checkpoint creation")
        state = _recover(store, state, snapshot)
        for item in state.items:
            if state.options.source_id and item.status != "succeeded":
                latest = _latest(snapshot, item.source_id)
                if latest is None or latest.id != item.base_version_id:
                    raise ResearchConflictError("Source version changed or was purged; refusing to reuse its checkpoint")
        if snapshot.digest != state.expected_snapshot:
            if expected_snapshot is None:
                raise ResearchConflictError("Research snapshot changed; resume with an explicit current --expected-snapshot")
            state = state.model_copy(update={"expected_snapshot": snapshot.digest})
            store.save(state)

        for index, initial_item in enumerate(state.items):
            item = initial_item
            if item.status == "succeeded":
                continue
            try:
                current = repository.snapshot()
                if current.digest != state.expected_snapshot:
                    raise ResearchConflictError("Research snapshot changed during checkpoint import")
                if item.prepared is None:
                    capture_options = state.options.model_dump()
                    if state.options.context is not None:
                        capture_options["context"] = state.options.context.model_dump()
                    capture = api._prepare_ingest(repository, current, item.file, **capture_options,
                                                  planned_source_id=item.source_id,
                                                  expected_source_digest=item.sha256,
                                                  progress_callback=progress_callback)
                    if capture.result["unchanged"]:
                        receipt = _Receipt.model_validate({key: value for key, value in capture.result.items() if key != "media_type"})
                        item = item.model_copy(update={"status": "succeeded", "result": receipt, "error": None})
                        state = _replace_item(state, index, item)
                        store.save(state)
                        continue
                    descriptors = {}
                    for record in capture.records:
                        if isinstance(record, SourceVersion):
                            descriptors[record.blob.sha256] = record.blob
                        elif isinstance(record, Extraction):
                            descriptors[record.text_blob.sha256] = record.text_blob
                    for sha256, content in capture.blobs.items():
                        publish(store.blob_path(index, sha256), content)
                    prepared = _Prepared(expected_snapshot=current.digest,
                                         records=[record.model_dump(mode="json") for record in capture.records],
                                         blobs=list(descriptors.values()), result=_Receipt.model_validate({key: value for key, value in capture.result.items() if key != "media_type"}),
                                         title=capture.title)
                    item = item.model_copy(update={"status": "prepared", "prepared": prepared, "error": None})
                    state = _replace_item(state, index, item)
                    store.save(state)
                elif progress_callback:
                    progress_callback("resume", "Reusing verified retained extraction...")
                records, blobs = _read_prepared(store, state, index)
                if item.prepared is None:
                    raise ResearchError("Missing prepared checkpoint item")
                prepared = item.prepared.model_copy(update={"expected_snapshot": current.digest})
                item = item.model_copy(update={"prepared": prepared, "error": None})
                state = _replace_item(state, index, item)
                store.save(state)
                if progress_callback:
                    progress_callback("commit", "Publishing records to research store...")
                committed = repository.commit(records, blobs, current)
                receipt = prepared.result.model_copy(update={"snapshot": committed.digest})
                item = item.model_copy(update={"status": "succeeded", "result": receipt, "prepared": None, "error": None})
                state = _replace_item(state, index, item, expected_snapshot=committed.digest)
                if progress_callback:
                    progress_callback("complete", f"Source '{prepared.title}' ingested ({prepared.result.passages} passages).")
                store.save(state)
                store.clear_objects(index)
            except (ResearchError, OSError, ValueError) as exc:
                accepted_item = state.items[index]
                if accepted_item.status == "succeeded" and accepted_item.result is not None:
                    warning = "Capture accepted; checkpoint bookkeeping failed. Inspect local preparation and explicitly discard it if no longer needed."
                    receipt = accepted_item.result.model_copy(update={"warnings": [*accepted_item.result.warnings, warning]})
                    state = _replace_item(state, index, accepted_item.model_copy(update={"result": receipt}))
                    store.save(state)
                    continue
                item = state.items[index].model_copy(update={"error": str(exc),
                                                             "status": "prepared" if state.items[index].prepared else "failed"})
                state = _replace_item(state, index, item)
                store.save(state)
                if isinstance(exc, ResearchConflictError):
                    break
        return _result(store, state)


def discard(project: str | Path, checkpoint: str | Path) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()
    store = _Store(repository, checkpoint)
    with store.lock_repository.locked():
        store.discard()
    return {"schema_version": "research-checkpoint-discard-local/1", "project_id": snapshot.project.id,
            "checkpoint": str(store.path), "discarded": True, "snapshot": snapshot.digest}


@contextmanager
def purge_guard(repository: Repository, source_id: str) -> Iterator[Callable[[], None]]:
    """Hold affected checkpoints while purge removes their private retained preparation."""
    directory = repository.safe(repository.cache / "imports")
    stores = []
    with _registry(repository).locked(), ExitStack() as stack:
        if directory.exists():
            for path in sorted(directory.rglob("*.json")):
                store = _Store(repository, path)
                state = store.load()
                if any(item.source_id == source_id for item in state.items):
                    stack.enter_context(store.lock_repository.locked())
                    if store.path.exists():
                        store.load()
                        stores.append(store)

        def clear() -> None:
            for store in stores:
                store.discard()

        yield clear
