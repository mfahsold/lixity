"""Explicit-project API for local evidence ingestion, lookup and integrity checks."""

import contextlib
import csv
import io
import os
import re
import tempfile
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, get_args, overload
from uuid import uuid4

from pydantic import ValidationError

from . import catalogue, editorial
from .acknowledgements import latest_acknowledgements
from .archive import (
    export_archive as export_archive,
)
from .archive import (
    restore_archive as restore_archive,
)
from .dossier_edit import (
    export_dossier_edit as export_dossier_edit,
)
from .dossier_edit import (
    prepare_dossier_edit as prepare_dossier_edit,
)
from .geography import summarize_geography
from .images import (
    IMAGE_SUFFIXES,
    IMAGE_TYPES,
    extract_image_references,
    image_descriptions,
    resolve_dossier_images,
    validate_image,
)
from .limits import MAX_IMAGE_ALT_CHARS, MAX_IMAGE_CAPTION_CHARS
from .limits import (
    MAX_IMAGE_BYTES as MAX_IMAGE_BYTES,
)
from .limits import (
    MAX_PDF_BYTES as MAX_PDF_BYTES,
)
from .limits import (
    MAX_SOURCE_BYTES as MAX_SOURCE_BYTES,
)
from .manuscript import (
    link_manuscript_claim as link_manuscript_claim,
)
from .manuscript import (
    list_manuscript_links as list_manuscript_links,
)
from .manuscript import (
    reanchor_manuscript_claim_revision as reanchor_manuscript_claim_revision,
)
from .manuscript import (
    reanchor_manuscript_link as reanchor_manuscript_link,
)
from .manuscript import (
    resolve_manuscript_anchor as resolve_manuscript_anchor,
)
from .manuscript import (
    retract_manuscript_link as retract_manuscript_link,
)
from .manuscript import (
    review_manuscript_links as review_manuscript_links,
)
from .models import (
    CLAIM_CONFIDENCES,
    ENTITY,
    EVIDENCE_RELATIONS,
    LANGUAGES,
    Activity,
    Blob,
    Claim,
    ClaimConfidence,
    ClaimRelation,
    ClaimScope,
    Decision,
    DecisionAcknowledgement,
    Dossier,
    Entity,
    EvidenceLink,
    EvidenceRelation,
    Extraction,
    Language,
    Passage,
    Project,
    Reference,
    Source,
    SourceContext,
    SourceVersion,
    Tombstone,
    normalize_claim_relation,
    reference,
)
from .ocr import (
    extract_pdf_document,
    get_ocr_diagnostics,
)
from .repository import Repository, ResearchConflictError, ResearchError, Snapshot, digest
from .revisions import (
    apply_record_revisions as apply_record_revisions,
)
from .revisions import (
    claim_relation_view,
    dossier_withdrawal,
    require_active_dossier_association,
    resolve_evidence_citation,
    source_updates,
)
from .revisions import (
    compare_record_revisions as compare_record_revisions,
)
from .revisions import (
    get_record as get_record,
)
from .revisions import (
    prepare_dossier_section as prepare_dossier_section,
)
from .revisions import (
    prepare_record_revision as prepare_record_revision,
)
from .revisions import (
    prepare_record_revisions as prepare_record_revisions,
)
from .revisions import (
    preview_record_changes as preview_record_changes,
)
from .revisions import (
    record_history as record_history,
)
from .revisions import (
    revise_record as revise_record,
)
from .sections import (
    _editable_section_titles as _editable_section_titles,
)
from .sections import (
    _extract_sections as _extract_sections,
)
from .sections import (
    _section_spans as _section_spans,
)
from .sections import (
    _section_subtree_end as _section_subtree_end,
)
from .sections import (
    extract_sections as extract_sections,
)
from .sections import (
    update_section as update_section,
)
from .timeline import period_warnings, timeline_data


def envelope(project_id: str, actor: str) -> dict[str, Any]:
    """Build the shared creation envelope: random urn ID, project, actor and UTC time."""
    return {"id": uuid4().urn, "project_id": project_id, "created_by": actor,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}


def init(project: str | Path, *, title: str, language: str = "en", actor: str = "local-author") -> dict[str, Any]:
    """Initialize a new local research archive for an explicit project directory.

    Refuses to overwrite an existing ``research/`` directory. Returns the
    ``research-init-local/1`` receipt with the project ID and snapshot digest.
    """
    repository = Repository(project)
    if repository.safe(repository.data).exists():
        raise ResearchError("Research directory already exists; refusing to overwrite it")
    identifier = uuid4().urn
    values = envelope(identifier, actor)
    values.update(id=identifier, title=title, language=language)
    record = Project.model_validate(values)
    snapshot = repository.commit([record], {}, None)
    return {"schema_version": "research-init-local/1", "project_id": identifier, "snapshot": snapshot.digest}


@dataclass
class _PreparedCapture:
    """Validated capture additions before their single repository publication."""

    records: list[Entity]
    blobs: dict[str, bytes]
    result: dict[str, Any]
    source_id: str
    base_version_id: str | None
    title: str


def _read_source_bytes(path: Path) -> bytes:
    is_pdf = path.suffix.lower() == ".pdf"
    is_image = path.suffix.lower() in IMAGE_SUFFIXES
    if not path.is_file():
        raise ResearchError("Source file is missing; supply a local PDF or UTF-8 text file")
    maximum = MAX_PDF_BYTES if is_pdf else MAX_IMAGE_BYTES if is_image else MAX_SOURCE_BYTES
    with path.open("rb") as stream:
        content = stream.read(maximum + 1)
    if is_image:
        validate_image(content, filename=path.name)
    elif is_pdf:
        if not content or len(content) > maximum:
            raise ResearchError("PDF source must be nonempty and at most 50 MiB")
    elif not content or len(content) > maximum or b"\x00" in content:
        raise ResearchError("Source must be nonempty text of at most 2 MiB, without NUL bytes")
    return content


def _prepare_ingest(repository: Repository, snapshot: Snapshot, file: str | Path, *,
                    source_id: str | None = None, title: str | None = None,
                    language: str | None = None, actor: str = "local-author", dry_run: bool = False,
                    context: Mapping[str, Any] | None = None, origin_url: str | None = None,
                    allow_fallback: bool = False, planned_source_id: str | None = None,
                    expected_source_digest: str | None = None,
                    progress_callback: Callable[[str, str], None] | None = None) -> _PreparedCapture:
    path = Path(file).expanduser()
    is_pdf = path.suffix.lower() == ".pdf"
    is_image = path.suffix.lower() in IMAGE_SUFFIXES
    if not path.is_file():
        raise ResearchError("Source must be a local UTF-8 text file" if not is_pdf else "Source must be a local PDF file")

    records: list[Entity] = []
    if source_id:
        source = snapshot.get(Reference(id=source_id), Source)
        if (title is not None and title != source.title) or (language is not None and language != source.language):
            raise ResearchError("Source refresh cannot change its title or language in this pilot")
    else:
        values = envelope(snapshot.project.id, actor)
        values.update(title=title or path.name, language=language or ("generic" if is_image else snapshot.project.language))
        if planned_source_id is not None:
            values["id"] = planned_source_id
        source = Source.model_validate(values)
        records.append(source)

    versions = [record for record in snapshot.records.values()
                if isinstance(record, SourceVersion) and record.source_ref.id == source.id]
    latest = max(versions, key=lambda record: record.sequence) if versions else None
    source_context = (SourceContext.model_validate(dict(context)) if context is not None
                      else latest.context if latest else SourceContext())
    if origin_url is not None:
        source_context = SourceContext.model_validate({**source_context.model_dump(), "origin_url": origin_url})

    if progress_callback:
        progress_callback("read", f"Reading source file {path.name}...")

    content = _read_source_bytes(path)
    if expected_source_digest is not None and digest(content) != expected_source_digest:
        raise ResearchError("Source file bytes changed since checkpoint creation")
    if is_image:
        image = validate_image(content, filename=path.name)
        checksum = digest(content)
        if latest is not None and latest.blob.sha256 == checksum and latest.context == source_context:
            repository.read_blob(latest.blob)
            result = {"schema_version": "research-ingest-local/1", "source_id": source.id,
                      "source_version_id": latest.id, "snapshot": snapshot.digest, "unchanged": True,
                      "dry_run": dry_run, "passages": 0, "warnings": [], "media_type": image["media_type"]}
            return _PreparedCapture([], {}, result, source.id, latest.id, source.title)
        version = SourceVersion(**envelope(snapshot.project.id, actor), source_ref=reference(source),
                                schema_version=("research-local/3" if source_context.external_reference else
                                                "research-local/2" if source_context.origin_url else "research-local/1"),
                                sequence=latest.sequence + 1 if latest else 1,
                                blob=Blob(sha256=checksum, byte_length=len(content), media_type=image["media_type"]),
                                retention_confirmed=True, context=source_context)
        records.append(version)
        result = {"schema_version": "research-ingest-local/1", "source_id": source.id,
                  "source_version_id": version.id, "unchanged": False, "passages": 0,
                  "dry_run": dry_run, "warnings": [], "media_type": image["media_type"]}
        return _PreparedCapture(records, {checksum: content}, result, source.id, latest.id if latest else None, source.title)
    blobs_to_commit: dict[str, bytes] = {}
    extraction_warnings: list[str] = []
    implementation: Literal["utf8-paragraphs/1", "baidu-unlimited-ocr/1", "tesseract-cli/1", "poppler-native/1"]
    if is_pdf:
        if latest is not None and latest.blob.sha256 == digest(content):
            if progress_callback:
                progress_callback("read", "Verifying retained PDF extraction...")
            repository.read_blob(latest.blob)
            prior = [record for record in snapshot.records.values() if isinstance(record, Extraction)
                     and record.source_version_ref.id == latest.id]
            if len(prior) != 1:
                raise ResearchError("PDF refresh requires one verified retained extraction")
            text = repository.read_blob(prior[0].text_blob).decode("utf-8")
            passages = sorted((record for record in snapshot.records.values() if isinstance(record, Passage)
                               and record.extraction_ref.id == prior[0].id), key=lambda record: record.start)
            if any(text[passage.start:passage.end] != passage.verbatim for passage in passages):
                raise ResearchError("Retained PDF extraction does not match its passages")
            spans = [(passage.start, passage.end) for passage in passages]
            implementation = snapshot.get(prior[0].activity_ref, Activity).implementation
        else:
            if progress_callback:
                progress_callback("ocr", "Rasterizing PDF pages and extracting text via OCR/poppler...")
            effective_fallback = allow_fallback or os.environ.get("LIXITY_OCR_FALLBACK", "").lower() in ("1", "true", "yes")
            # Extract the exact bytes retained below, even if the caller replaces its file.
            with tempfile.TemporaryDirectory(prefix="lixity-source-") as directory:
                stable_path = Path(directory) / "source.pdf"
                stable_path.write_bytes(content)
                ocr_res = extract_pdf_document(stable_path, allow_fallback=effective_fallback)
            text = ocr_res.full_text
            spans = ocr_res.spans
            extraction_warnings = ocr_res.warnings
            implementation = ocr_res.implementation_id
        if not spans or len(spans) > 5000:
            raise ResearchError("Source must contain between 1 and 5000 nonempty paragraphs")
        operation: Literal["extract_utf8", "extract_ocr"] = "extract_ocr"
        source_checksum = digest(content)
        text_bytes = text.encode("utf-8")
        text_checksum = digest(text_bytes)
        source_blob = Blob(sha256=source_checksum, byte_length=len(content), media_type="application/pdf")
        text_blob = Blob(sha256=text_checksum, byte_length=len(text_bytes), media_type="text/plain")
        blobs_to_commit[source_checksum] = content
        blobs_to_commit[text_checksum] = text_bytes
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            raise ResearchError("Text sources must be UTF-8; use a .pdf file for PDF extraction") from None
        spans = [(match.start(), match.start() + len(match.group().rstrip()))
                 for match in re.finditer(r"\S.*?(?=\n\s*\n|\Z)", text, re.DOTALL)]
        if not spans or len(spans) > 5000:
            raise ResearchError("Source must contain between 1 and 5000 nonempty paragraphs")
        operation = "extract_utf8"
        implementation = "utf8-paragraphs/1"
        source_checksum = digest(content)
        source_blob = Blob(sha256=source_checksum, byte_length=len(content), media_type="text/plain")
        text_blob = source_blob
        blobs_to_commit[source_checksum] = content

    if latest is not None and latest.blob.sha256 == source_checksum and latest.context == source_context:
        repository.read_blob(latest.blob)
        result = {"schema_version": "research-ingest-local/1", "source_id": source.id,
                "source_version_id": latest.id, "snapshot": snapshot.digest,
                "unchanged": True, "dry_run": dry_run, "passages": len(spans),
                "warnings": extraction_warnings}
        return _PreparedCapture([], {}, result, source.id, latest.id, source.title)

    version = SourceVersion(**envelope(snapshot.project.id, actor), source_ref=reference(source),
                            schema_version=("research-local/3" if source_context.external_reference else
                                            "research-local/2" if source_context.origin_url else "research-local/1"),
                            sequence=latest.sequence + 1 if latest else 1, blob=source_blob,
                            retention_confirmed=True, context=source_context)
    activity = Activity(**envelope(snapshot.project.id, actor), source_version_ref=reference(version),
                        schema_version=("research-local/4" if implementation in {"tesseract-cli/1", "poppler-native/1"}
                                        else "research-local/1"),
                        operation=operation, implementation=implementation, status="succeeded")
    extraction = Extraction(**envelope(snapshot.project.id, actor), source_version_ref=reference(version),
                            activity_ref=reference(activity), text_blob=text_blob)
    records.extend([version, activity, extraction])
    if progress_callback:
        progress_callback("passages", f"Segmenting {len(spans)} verified passages...")
    for start, end in spans:
        records.append(Passage(**envelope(snapshot.project.id, actor), extraction_ref=reference(extraction),
                               start=start, end=end, verbatim=text[start:end], language=source.language))
    result = {"schema_version": "research-ingest-local/1", "source_id": source.id,
              "source_version_id": version.id, "unchanged": False,
              "passages": len(spans), "dry_run": dry_run, "warnings": extraction_warnings}
    return _PreparedCapture(records, blobs_to_commit, result, source.id, latest.id if latest else None, source.title)


def ingest(project: str | Path, file: str | Path, *, allow_retention: bool = False,
           source_id: str | None = None, title: str | None = None,
           language: str | None = None, actor: str = "local-author", dry_run: bool = False,
           context: Mapping[str, Any] | None = None,
           origin_url: str | None = None, expected_snapshot: str | None = None,
           allow_fallback: bool = False,
           progress_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    """Ingest one local file as a retained source and indexed passages.

    Requires ``allow_retention=True``. ``source_id`` explicitly refreshes a
    matching capture, ``dry_run`` previews without writing, and
    ``expected_snapshot`` rejects a changed archive. Returns the
    ``research-ingest-local/1`` receipt; identical captures are no-ops.
    Source bytes and metadata stay untrusted evidence.
    """
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (--allow-retention)")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_snapshot is not None and snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; reload and retry capture")
    prepared = _prepare_ingest(repository, snapshot, file, source_id=source_id, title=title,
                               language=language, actor=actor, dry_run=dry_run, context=context,
                               origin_url=origin_url, allow_fallback=allow_fallback,
                               progress_callback=progress_callback)
    result = prepared.result
    if result["unchanged"]:
        return result
    if progress_callback:
        progress_callback("commit", "Publishing records to research store...")
    if dry_run:
        result["snapshot"] = snapshot.digest
    else:
        while True:
            try:
                result["snapshot"] = repository.commit(prepared.records, prepared.blobs, snapshot).digest
                break
            except ResearchConflictError as exc:
                if expected_snapshot is not None or result.get("media_type") in IMAGE_TYPES:
                    raise
                fresh = repository.snapshot()
                if source_id:
                    fresh_versions = [r for r in fresh.records.values() if isinstance(r, SourceVersion) and r.source_ref.id == prepared.source_id]
                    fresh_latest = max(fresh_versions, key=lambda r: r.sequence) if fresh_versions else None
                    if (prepared.base_version_id is None and fresh_latest is not None) or (prepared.base_version_id and fresh_latest and prepared.base_version_id != fresh_latest.id):
                        raise ResearchConflictError("Source was modified concurrently; reload and retry capture") from exc
                snapshot = fresh
    if progress_callback:
        progress_callback("complete", f"Source '{prepared.title}' ingested ({result['passages']} passages).")
    return result


def ingest_image(project: str | Path, content: bytes, *, filename: str,
                 allow_retention: bool = False, source_id: str | None = None,
                 title: str | None = None, context: Mapping[str, Any] | None = None,
                 origin_url: str | None = None, expected_snapshot: str | None = None,
                 actor: str = "local-author") -> dict[str, Any]:
    """Capture explicitly authorized local raster bytes through ordinary ingest."""
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (allow_retention: true)")
    validate_image(content, filename=filename)
    expected_snapshot = expected_snapshot if expected_snapshot is not None else Repository(project).snapshot().digest
    with tempfile.TemporaryDirectory(prefix="lixity-image-") as directory:
        path = Path(directory) / ("image" + Path(filename).suffix.lower())
        path.write_bytes(content)
        return ingest(project, path, allow_retention=True, source_id=source_id,
                      title=title if source_id else title or Path(filename).name,
                      context=context, origin_url=origin_url, expected_snapshot=expected_snapshot, actor=actor)


def read_image(project: str | Path, *, project_id: str, source_id: str, version_id: str) -> dict[str, Any]:
    """Return verified exact-version bytes for an explicitly identified project."""
    from .images import read_image as read_retained_image
    repository = Repository(project)
    return read_retained_image(repository, repository.snapshot(), project_id=project_id,
                               source_id=source_id, version_id=version_id)


def attach_dossier_image(project: str | Path, dossier_id: str, content: bytes, *, filename: str,
                         expected_snapshot: str, expected_revision: int, allow_retention: bool = False,
                         alt: str = "", caption: str | None = None, section: str | None = None,
                         title: str | None = None, context: Mapping[str, Any] | None = None,
                         origin_url: str | None = None, reason: str | None = None,
                         change_kind: str = "supersession", actor: str = "local-author") -> dict[str, Any]:
    """Publish one new image capture and dossier revision under exact CAS."""
    from .revisions import _apply_changes, _record, _view
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (allow_retention: true)")
    if not isinstance(alt, str) or len(alt) > MAX_IMAGE_ALT_CHARS or "\n" in alt or "\r" in alt:
        raise ResearchError("Image alternative text must be one line of at most 1000 characters")
    if caption is not None and (not isinstance(caption, str) or len(caption) > MAX_IMAGE_CAPTION_CHARS):
        raise ResearchError("Image caption must be text of at most 10000 characters")
    if reason is not None and (not isinstance(reason, str) or not reason.strip() or len(reason) > 2000):
        raise ResearchError("Image attachment reason must be nonblank text of at most 2000 characters")
    if type(expected_revision) is not int or expected_revision < 1 or not isinstance(expected_snapshot, str):
        raise ResearchError("Image attachment requires an expected snapshot and dossier revision")
    repository = Repository(project)
    snapshot = repository.snapshot()
    previous = _record(snapshot, "dossier", dossier_id)
    if not isinstance(previous, Dossier):
        raise ResearchError("Image attachment requires a dossier")
    if snapshot.digest != expected_snapshot or previous.revision != expected_revision:
        raise ResearchConflictError("Research snapshot or dossier revision changed; reload and retry attachment")
    validate_image(content, filename=filename)
    with tempfile.TemporaryDirectory(prefix="lixity-image-") as directory:
        path = Path(directory) / ("image" + Path(filename).suffix.lower())
        path.write_bytes(content)
        prepared = _prepare_ingest(repository, snapshot, path, title=title or Path(filename).name,
                                   context=context, origin_url=origin_url, actor=actor)
    escaped_alt = alt.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    markup = f"![{escaped_alt}](lixity:image/{prepared.source_id}/{prepared.result['source_version_id']})"
    if caption:
        markup += "\n\n" + caption
    if section is None:
        line_break = re.search(r"\r\n|\r|\n", previous.body)
        newline = line_break.group() if line_break else "\n"
        prefix = "" if not previous.body or previous.body.endswith(newline * 2) else newline if previous.body.endswith(newline) else newline * 2
        body = previous.body + prefix + markup.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline) + newline
    else:
        if not isinstance(section, str):
            raise ResearchError("Image section must identify an existing unique dossier heading")
        spans = _section_spans(previous.body)
        matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
        if len(matches) != 1:
            raise ResearchError("Image section must identify an existing unique dossier heading")
        selected = matches[0]
        existing = previous.body[selected.content_start:_section_subtree_end(spans, selected, len(previous.body))]
        body = update_section(previous.body, section, existing.rstrip() + "\n\n" + markup)
    if not any(ref.source_id == prepared.source_id and ref.source_version_id == prepared.result["source_version_id"]
               for ref in extract_image_references(body)):
        raise ResearchError("Attachment location is inside Markdown code; close it or choose another section")
    revised = _apply_changes(snapshot, previous, {"body": body}, change_kind=change_kind,
                             reason=reason if reason is not None else f"Attached image {prepared.title}.", actor=actor)
    accepted = repository.commit([*prepared.records, revised], prepared.blobs, snapshot)
    return {**_view(repository, accepted, revised), "capture": {**prepared.result, "snapshot": accepted.digest}}


def ingest_checkpoint(project: str | Path, files: Sequence[str | Path] | None = None, *,
                      checkpoint: str | Path, resume: bool = False,
                      allow_retention: bool = False, source_id: str | None = None,
                      title: str | None = None, language: str | None = None,
                      actor: str | None = None, dry_run: bool = False,
                      context: Mapping[str, Any] | None = None, origin_url: str | None = None,
                      expected_snapshot: str | None = None, allow_fallback: bool | None = None,
                      progress_callback: Callable[[str, str], None] | None = None) -> dict[str, Any]:
    """Sequential opt-in capture with retained preparation and explicit resume checks."""
    from . import checkpoints

    return checkpoints.ingest(project, files, checkpoint=checkpoint, resume=resume,
                              allow_retention=allow_retention, source_id=source_id, title=title,
                              language=language, actor=actor, dry_run=dry_run, context=context,
                              origin_url=origin_url, expected_snapshot=expected_snapshot,
                              allow_fallback=allow_fallback, progress_callback=progress_callback)


def discard_ingest_checkpoint(project: str | Path, *, checkpoint: str | Path) -> dict[str, Any]:
    """Discard local checkpoint preparation without changing accepted research records."""
    from . import checkpoints

    return checkpoints.discard(project, checkpoint)


def reindex(project: str | Path) -> dict[str, Any]:
    """Rebuild the catalogue used by search; returns ``research-index-local/1``."""
    return catalogue.reindex(Repository(project))


def search(project: str | Path, query: str, *, limit: int = 20, scope: str = "sources", ensure_fresh: bool = False) -> dict[str, Any]:
    """Search retained passages or authored records by words, limited by ``scope``.

    Sources use ``research-search-local/1``; ``dossiers``, ``claims``,
    ``decisions`` and ``all`` use ``research-search-local/2``, where hits
    carry a ``kind``.
    """
    return catalogue.search(Repository(project), query, limit=limit, scope=scope, ensure_fresh=ensure_fresh)


def cite(project: str | Path, passage_id: str) -> dict[str, Any]:
    """Resolve one retained passage ID into its full citation envelope
    (``research-citation-local/1``).
    """
    repository = Repository(project)
    snapshot = repository.snapshot()
    passage = snapshot.get(Reference(id=passage_id), Passage)
    return repository.citation(snapshot, passage)


def audit(project: str | Path) -> dict[str, Any]:
    """Check that retained blobs match their descriptors and references resolve.

    Returns ``research-audit-local/1`` with ``ok`` and the collected error
    strings; warnings remain advisory.
    """
    repository = Repository(project)
    errors: list[str] = []
    count = 0
    head: str | None = None
    try:
        snapshot = repository.snapshot()
        count = len(snapshot.revisions)
        head = snapshot.digest
        checked: set[str] = set()
        for record in snapshot.records.values():
            if isinstance(record, SourceVersion) and record.blob.sha256 not in checked:
                content = repository.read_blob(record.blob)
                if record.blob.media_type in IMAGE_TYPES:
                    image = validate_image(content)
                    if image["media_type"] != record.blob.media_type:
                        raise ResearchError("Retained image type does not match its blob descriptor")
                checked.add(record.blob.sha256)
            elif isinstance(record, Extraction) and record.text_blob.sha256 not in checked:
                repository.read_blob(record.text_blob)
                checked.add(record.text_blob.sha256)
            elif isinstance(record, Passage):
                repository.quote(snapshot, record)
        for record in snapshot.revisions.values():
            if isinstance(record, Dossier):
                if any(image["availability"] == "missing" for image in resolve_dossier_images(snapshot, record.body)):
                    errors.append(f"Dossier {record.id} revision {record.revision} has an unavailable image pin")
                try:
                    extract_image_references(record.body, strict=True)
                except ResearchError:
                    errors.append(f"Dossier {record.id} revision {record.revision} has malformed reserved image data (kept inert)")
    except (OSError, ResearchError, ValidationError, UnicodeDecodeError) as exc:
        msg = str(exc).strip()
        errors.append(f"Research integrity check failed: {msg}" if msg else "Research integrity check failed: missing, invalid or modified records/bytes")
    return {"schema_version": "research-audit-local/1", "ok": not errors,
            "snapshot": head, "records": count, "errors": errors,
            "scope": "retained source records, citations and dossier image pins; not factual accuracy, full image decoding or index freshness"}


def schema() -> dict[str, Any]:
    """Return the JSON Schema (draft 2020-12) of the research record entity union."""
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **ENTITY.json_schema()}


def ocr_status(worker_cmd: str | None = None, *, probe: bool = False) -> dict[str, Any]:
    """Inspect and report the runtime diagnostic status for OCR and PDF extraction."""
    return get_ocr_diagnostics(worker_cmd=worker_cmd, probe=probe)


def analyze_source(project: str | Path, source_id: str, *, version_id: str | None = None,
                   thresholds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Analyze verified archived text with explicit settings; never accept a claim."""
    from .analysis import analyze

    return analyze(project, source_id, version_id=version_id, thresholds=thresholds).report()


def source_dashboard(project: str | Path, source_id: str, *, version_id: str | None = None,
                     thresholds: Mapping[str, Any] | None = None) -> str:
    """Render a local read-only source report; the HTML contains private source text."""
    from .analysis import analyze

    return analyze(project, source_id, version_id=version_id, thresholds=thresholds).dashboard()


@overload
def compare_source(
    project: str | Path,
    source_id: str,
    manuscript: str | Path,
    *,
    version_id: str | None = None,
    language: str | None = None,
    top_n: int = 20,
    format: Literal["json"] = "json",
) -> dict[str, Any]: ...


@overload
def compare_source(
    project: str | Path,
    source_id: str,
    manuscript: str | Path,
    *,
    version_id: str | None = None,
    language: str | None = None,
    top_n: int = 20,
    format: Literal["md"],
) -> str: ...


def compare_source(
    project: str | Path,
    source_id: str,
    manuscript: str | Path,
    *,
    version_id: str | None = None,
    language: str | None = None,
    top_n: int = 20,
    format: Literal["json", "md"] = "json",
) -> dict[str, Any] | str:
    """Compare verified research source against manuscript text or file.

    Returns the comparison dictionary, or its Markdown rendering when
    ``format="md"``. Use `compare_source_to_manuscript` for the data alone.
    """
    from .analysis import compare_source_to_manuscript, format_compare_markdown

    result = compare_source_to_manuscript(
        project,
        source_id,
        manuscript,
        version_id=version_id,
        language=language,
        top_n=top_n,
    )
    return format_compare_markdown(result) if format == "md" else result


def withdraw(
    project: str | Path,
    source_id: str | None = None,
    *,
    version_id: str | None = None,
    dossier_id: str | None = None,
    expected_snapshot: str | None = None,
    expected_revision: int | None = None,
    dry_run: bool = False,
    reason: str = "Withdrawn by user",
    actor: str = "local-author",
) -> dict[str, Any]:
    """Withdraw a source/version or a reviewed dossier without deleting bytes.

    The source response remains ``research-withdraw-local/1``. Dossiers require
    exact snapshot/revision guards and have separate result/preview envelopes.
    """
    from .revisions import _record

    if type(dry_run) is not bool:
        raise ResearchError("dry_run must be a boolean")
    if (source_id is None) == (dossier_id is None):
        raise ResearchError("Select exactly one source or dossier to withdraw")
    if dossier_id is not None:
        if version_id is not None:
            raise ResearchError("A source version cannot select a dossier withdrawal")
        if not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
            raise ResearchError("Dossier withdrawal requires an expected snapshot SHA-256 digest")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ResearchError("Dossier withdrawal requires an exact positive expected revision")
    elif expected_snapshot is not None or expected_revision is not None or dry_run:
        raise ResearchError("Reviewed revision guards and withdrawal dry-run apply only to dossiers")
    reason = reason.strip() if reason else "Withdrawn by user"
    if not (1 <= len(reason) <= 500):
        raise ResearchError("Withdrawal reason must be between 1 and 500 characters")
    repository = Repository(project)
    snapshot = repository.snapshot()

    source = None
    target_kind: Literal["source", "source_version", "dossier"]
    if dossier_id is not None:
        if snapshot.digest != expected_snapshot:
            raise ResearchConflictError("Research snapshot changed; review the dossier before withdrawal")
        dossier = _record(snapshot, "dossier", dossier_id)
        if dossier.revision != expected_revision:
            raise ResearchConflictError("Dossier revision changed; review it before withdrawal")
        target_ref, target_kind = reference(dossier), "dossier"
    else:
        if source_id is None:
            raise ResearchError("A source identifier is required")
        source = snapshot.get(Reference(id=source_id), Source)
    if source is not None and version_id is not None:
        version = snapshot.get(Reference(id=version_id), SourceVersion)
        if version.source_ref.id != source.id:
            raise ResearchError("Source version does not belong to the requested source")
        target_ref = reference(version)
        target_kind = "source_version"
    elif source is not None:
        target_ref = reference(source)
        target_kind = "source"

    already_tombstoned = any(
        isinstance(rec, Tombstone) and rec.target_ref.id in (target_ref.id, source.id if source else target_ref.id)
        for rec in snapshot.records.values()
    )
    if already_tombstoned:
        raise ResearchError("Target has already been withdrawn or purged")

    tombstone = Tombstone(
        **envelope(snapshot.project.id, actor),
        target_ref=target_ref,
        target_kind=target_kind,
        operation="withdraw",
        reason=reason,
    )
    if dossier_id is not None and dry_run:
        repository.prepare_commit([tombstone], snapshot)
        return {"schema_version": "research-dossier-withdraw-preview-local/1", "operation": "withdraw",
                "project_id": snapshot.project.id, "target_id": target_ref.id, "target_revision": target_ref.revision,
                "snapshot": snapshot.digest, "reason": reason, "ready": True, "dry_run": True}
    new_snapshot = repository.commit([tombstone], {}, snapshot)
    if dossier_id is not None:
        return {"schema_version": "research-dossier-withdraw-local/1", "operation": "withdraw",
                "project_id": snapshot.project.id, "target_id": target_ref.id, "target_revision": target_ref.revision,
                "snapshot": new_snapshot.digest, "reason": reason}
    return {
        "schema_version": "research-withdraw-local/1",
        "operation": "withdraw",
        "source_id": source_id,
        "target_id": target_ref.id,
        "target_kind": target_kind,
        "reason": reason,
        "snapshot": new_snapshot.digest,
    }


def purge(
    project: str | Path,
    source_id: str,
    *,
    version_id: str | None = None,
    reason: str = "Purged by user",
    actor: str = "local-author",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete retained bytes for a source or version and mark it purged.

    ``dry_run`` reports the planned removal without writing; returns
    ``research-purge-local/1``. Identity metadata remains as a tombstone.
    """
    reason = reason.strip() if reason else "Purged by user"
    if not (1 <= len(reason) <= 500):
        raise ResearchError("Purge reason must be between 1 and 500 characters")
    repository = Repository(project)
    snapshot = repository.snapshot()

    source = snapshot.get(Reference(id=source_id), Source)
    target_kind: Literal["source", "source_version"]

    if version_id is not None:
        target_version = snapshot.get(Reference(id=version_id), SourceVersion)
        if target_version.source_ref.id != source.id:
            raise ResearchError("Source version does not belong to the requested source")
        versions_to_purge = [target_version]
        target_ref = reference(target_version)
        target_kind = "source_version"
        purge_source_record = False
    else:
        versions_to_purge = [
            rec
            for rec in snapshot.records.values()
            if isinstance(rec, SourceVersion) and rec.source_ref.id == source.id
        ]
        target_ref = reference(source)
        target_kind = "source"
        purge_source_record = True

    version_ids = {v.id for v in versions_to_purge}

    activities_to_purge = [
        rec
        for rec in snapshot.records.values()
        if isinstance(rec, Activity) and rec.source_version_ref.id in version_ids
    ]
    activity_ids = {a.id for a in activities_to_purge}

    extractions_to_purge = [
        rec
        for rec in snapshot.records.values()
        if isinstance(rec, Extraction) and rec.source_version_ref.id in version_ids
    ]
    extraction_ids = {e.id for e in extractions_to_purge}

    passages_to_purge = [
        rec
        for rec in snapshot.records.values()
        if isinstance(rec, Passage) and rec.extraction_ref.id in extraction_ids
    ]
    passage_ids = {p.id for p in passages_to_purge}

    records_to_remove: set[str] = set()
    records_to_remove.update(version_ids)
    records_to_remove.update(activity_ids)
    records_to_remove.update(extraction_ids)
    records_to_remove.update(passage_ids)
    if purge_source_record:
        records_to_remove.add(source.id)

    purged_blob_shas = {v.blob.sha256 for v in versions_to_purge}
    retained_shared_blobs: set[str] = set()
    deleted_blobs: set[str] = set()

    remaining_version_blobs = {
        rec.blob.sha256
        for rec in snapshot.records.values()
        if isinstance(rec, SourceVersion) and rec.id not in version_ids
    }

    for sha in purged_blob_shas:
        if sha in remaining_version_blobs:
            retained_shared_blobs.add(sha)
        else:
            deleted_blobs.add(sha)

    tombstone = Tombstone(
        **envelope(snapshot.project.id, actor),
        schema_version="research-local/2" if target_kind == "source_version" else "research-local/1",
        target_ref=target_ref,
        source_ref=reference(source) if target_kind == "source_version" else None,
        target_kind=target_kind,
        operation="purge",
        reason=reason,
    )

    if dry_run:
        new_digest = snapshot.digest
    else:
        passage_tombstones = [
            Tombstone(
                **envelope(snapshot.project.id, actor),
                target_ref=reference(passage),
                target_kind="passage",
                operation="purge",
                reason=reason,
            )
            for passage in passages_to_purge
        ]
        # Exact image pins must still resolve to an explicit placeholder after
        # source-level purge has removed the immutable version records.
        version_tombstones = [Tombstone(**envelope(snapshot.project.id, actor), target_ref=reference(version),
                                        schema_version="research-local/2", source_ref=version.source_ref,
                                        target_kind="source_version", operation="purge", reason=reason)
                              for version in versions_to_purge if purge_source_record and version.blob.media_type in IMAGE_TYPES]
        from .checkpoints import purge_guard

        with purge_guard(repository, source.id) as discard_preparation:
            new_snapshot = repository.commit(
                [tombstone, *passage_tombstones, *version_tombstones],
                {},
                snapshot,
                removals=records_to_remove,
                delete_blobs=deleted_blobs,
            )
            discard_preparation()
        new_digest = new_snapshot.digest

    return {
        "schema_version": "research-purge-local/1",
        "operation": "purge",
        "source_id": source.id,
        "target_id": target_ref.id,
        "target_kind": target_kind,
        "reason": reason,
        "dry_run": dry_run,
        "purged_versions": len(versions_to_purge),
        "purged_passages": len(passages_to_purge),
        "deleted_blobs": sorted(deleted_blobs),
        "retained_shared_blobs": sorted(retained_shared_blobs),
        "snapshot": new_digest,
    }


def list_sources(project: str | Path) -> dict[str, Any]:
    """List all active, non-withdrawn sources in the research project with their versions and metadata."""
    return _list_sources(Repository(project).snapshot())


def _list_sources(snapshot: Snapshot) -> dict[str, Any]:

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    extraction_to_version = {
        record.id: record.source_version_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Extraction)
    }

    passages_per_version: dict[str, int] = {}
    versions_per_source: dict[str, list[SourceVersion]] = {}
    for record in snapshot.records.values():
        if isinstance(record, SourceVersion) and record.id not in withdrawn_or_purged:
            versions_per_source.setdefault(record.source_ref.id, []).append(record)
        if isinstance(record, Passage):
            ver_id = extraction_to_version.get(record.extraction_ref.id)
            if ver_id:
                passages_per_version[ver_id] = passages_per_version.get(ver_id, 0) + 1

    sources_list: list[dict[str, Any]] = []
    for record in snapshot.records.values():
        if not isinstance(record, Source) or record.id in withdrawn_or_purged:
            continue
        versions = versions_per_source.get(record.id, [])
        if not versions:
            continue
        latest = max(versions, key=lambda v: v.sequence)
        sources_list.append(
            {
                "id": record.id,
                "title": record.title,
                "language": record.language,
                "version_id": latest.id,
                "sequence": latest.sequence,
                "byte_length": latest.blob.byte_length,
                "media_type": latest.blob.media_type,
                "sha256": latest.blob.sha256,
                "context": latest.context.model_dump(),
                "tags": latest.context.tags,
                "passages": passages_per_version.get(latest.id, 0),
            }
        )

    sources_list.sort(key=lambda s: str(s["title"]).lower())
    return {
        "schema_version": "research-sources-local/1",
        "project_id": snapshot.project.id,
        "project_title": snapshot.project.title,
        "project_language": snapshot.project.language,
        "sources": sources_list,
    }


def get_source(project: str | Path, source_id: str) -> dict[str, Any]:
    """Retrieve full details of a specific source including its passages."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    source = snapshot.get(Reference(id=source_id), Source)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    if source.id in withdrawn_or_purged:
        raise ResearchError("Source has been withdrawn or purged")

    versions = [
        v
        for v in snapshot.records.values()
        if isinstance(v, SourceVersion) and v.source_ref.id == source.id and v.id not in withdrawn_or_purged
    ]
    if not versions:
        raise ResearchError("Source has no active versions")
    latest = max(versions, key=lambda v: v.sequence)

    extraction_ids = {
        rec.id
        for rec in snapshot.records.values()
        if isinstance(rec, Extraction) and rec.source_version_ref.id == latest.id
    }
    passages = [
        rec
        for rec in snapshot.records.values()
        if isinstance(rec, Passage) and rec.extraction_ref.id in extraction_ids
    ]
    passages.sort(key=lambda p: (p.start, p.end))
    # The detail response exposes verbatim text, so verify it against retained
    # bytes just as citations do. Snapshot caches each decoded blob by digest.
    for passage in passages:
        repository.quote(snapshot, passage)

    full_text = ""
    extractions = [
        rec
        for rec in snapshot.records.values()
        if isinstance(rec, Extraction) and rec.id in extraction_ids
    ]
    if extractions:
        chk = extractions[0].text_blob.sha256
        if chk in snapshot.texts:
            full_text = snapshot.texts[chk]
        else:
            with contextlib.suppress(ResearchError, OSError):
                full_text = repository.read_blob(extractions[0].text_blob).decode("utf-8", errors="replace")
    if not full_text and passages:
        full_text = "\n\n".join(p.verbatim for p in passages if p.verbatim)

    return {
        "id": source.id,
        "title": source.title,
        "language": source.language,
        "version_id": latest.id,
        "sequence": latest.sequence,
        "byte_length": latest.blob.byte_length,
        "media_type": latest.blob.media_type,
        "sha256": latest.blob.sha256,
        "text": full_text,
        "context": latest.context.model_dump(),
        "tags": latest.context.tags,
        "passages": [
            {
                "id": p.id,
                "start": p.start,
                "end": p.end,
                "verbatim": p.verbatim,
            }
            for p in passages
        ],
    }


def claim_confidence(value: object) -> ClaimConfidence:
    """Normalise a submitted claim confidence at the API boundary."""
    text = str(value or "").strip().lower()
    for candidate in CLAIM_CONFIDENCES:
        if text == candidate:
            return candidate
    return "hypothetical"


def evidence_relation(value: object) -> EvidenceRelation:
    """Normalise a submitted evidence relation at the API boundary."""
    text = str(value or "").strip().lower()
    for candidate in EVIDENCE_RELATIONS:
        if text == candidate:
            return candidate
    return "supports"


def supported_language(value: object) -> Language:
    """Return the matching project language key or raise a clear error."""
    text = str(value or "").strip().lower()
    for candidate in LANGUAGES:
        if text == candidate:
            return candidate
    raise ResearchError(f"Unsupported language: {value!r}")


def create_dossier(
    project: str | Path,
    title: str,
    body: str,
    *,
    language: str = "en",
    tags: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    geography: dict[str, Any] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create and commit a new Dossier record."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    title = title.strip()
    if not (1 <= len(title) <= 500):
        raise ResearchError("Dossier title must be between 1 and 500 characters")
    language = supported_language(language)

    evidence_refs = [Reference(id=eid) for eid in dict.fromkeys(evidence_ids or [])]
    for ref in evidence_refs:
        snapshot.get(ref, Passage)

    values = envelope(snapshot.project.id, actor)
    if geography is not None:
        values["schema_version"] = "research-local/8"
    try:
        dossier = Dossier.model_validate({**values, "title": title, "language": language, "tags": tags or [],
                                          "body": body, "evidence_refs": evidence_refs, "geography": geography})
    except ValidationError as error:
        raise ResearchError(f"Invalid dossier fields: {error}") from None
    new_snapshot = repository.commit([dossier], {}, snapshot)
    return {
        "schema_version": "research-dossier-local/1",
        "dossier_id": dossier.id,
        "title": dossier.title,
        "snapshot": new_snapshot.digest,
    }


def list_dossiers(project: str | Path) -> dict[str, Any]:
    """List all active dossiers in the project."""
    return _list_dossiers(Repository(project).snapshot(
        kinds=frozenset({"dossier", "claim", "decision", "decision_acknowledgement"})))


def _list_dossiers(snapshot: Snapshot) -> dict[str, Any]:

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    purged_passages = {
        record.target_ref
        for record in snapshot.records.values()
        if isinstance(record, Tombstone)
        and record.operation == "purge"
        and record.target_kind == "passage"
    }

    dossier_reviews = editorial.dossier_reviews(snapshot)

    dossiers_list = [
        {
            "id": record.id,
            "title": record.title,
            "language": record.language,
            "tags": record.tags,
            "revision": record.revision,
            "evidence_count": len(record.evidence_refs),
            "unavailable_evidence_count": sum(ref in purged_passages for ref in record.evidence_refs),
            "created_at": record.created_at,
            "created_by": record.created_by,
            "excerpt": image_descriptions(record.body)[:300].strip(),
            "sections": list(extract_sections(record.body).keys()),
            "review_needed": any(review["status"] == "review_needed" for review in dossier_reviews.get(record.id, [])),
        }
        for record in snapshot.records.values()
        if isinstance(record, Dossier) and record.id not in withdrawn_or_purged
    ]

    dossiers_list.sort(key=lambda d: str(d["created_at"]), reverse=True)
    return {
        "schema_version": "research-dossiers-local/1",
        "dossiers": dossiers_list,
    }


def _resolve_evidence_citation(repository: Repository, snapshot: Any, ref: Reference) -> dict[str, Any]:
    return resolve_evidence_citation(repository, snapshot, ref)


def get_dossier(project: str | Path, dossier_id: str, *,
                section: str | None = None,
                revision: int | None = None,
                summary: bool = False,
                include_citations: bool = True) -> dict[str, Any]:
    """Retrieve details of a specific dossier with optional section or summary bounding."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    if revision is not None and (type(revision) is not int or revision < 1):
        raise ResearchError("Revision must be a positive integer")
    dossier = (snapshot.latest(dossier_id, Dossier) if revision is None
               else snapshot.get(Reference(id=dossier_id, revision=revision), Dossier))
    availability = dossier_withdrawal(snapshot, dossier.id)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    if dossier.id in withdrawn_or_purged and not (revision is not None and availability):
        raise ResearchError("Dossier has been withdrawn or purged")

    decision_reviews = editorial.dossier_reviews(snapshot).get(dossier.id, [])

    spans = _section_spans(dossier.body)
    sections = _extract_sections(dossier.body, spans)
    editable_sections = [] if availability else _editable_section_titles(spans)
    if summary:
        resolved_citations = [_resolve_evidence_citation(repository, snapshot, ref) for ref in dossier.evidence_refs] if include_citations else []
        return {
            "id": dossier.id,
            **availability,
            "project_id": snapshot.project.id,
            "images": resolve_dossier_images(snapshot, dossier.body[:500]),
            "title": dossier.title,
            "language": dossier.language,
            "tags": dossier.tags,
            "revision": dossier.revision,
            "snapshot": snapshot.digest,
            "created_at": dossier.created_at,
            "created_by": dossier.created_by,
            "body_length": len(dossier.body),
            "sections": list(sections.keys()),
            "editable_sections": editable_sections,
            "citation_count": len(dossier.evidence_refs),
            "geography_feature_count": len(dossier.geography.features) if dossier.geography else 0,
            "geography_summary": summarize_geography(dossier.geography),
            "excerpt": dossier.body[:500] + ("..." if len(dossier.body) > 500 else ""),
            "decision_reviews": decision_reviews,
            "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
            "source_updates": source_updates(resolved_citations) if include_citations else [],
        }

    if section is not None:
        matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
        if len(matches) > 1:
            raise ResearchError(f"Section '{section}' is ambiguous: {len(matches)} headings share this title; read the full dossier")
        matched = next((k for k in sections if k.casefold() == section.strip().casefold()), None)
        if matched is None:
            raise ResearchError(f"Section '{section}' not found in dossier; available: {', '.join(sections.keys()) or 'none'}")
        selected_content = (dossier.body[matches[0].content_start:
            _section_subtree_end(spans, matches[0], len(dossier.body))].strip("\r\n")
            if matches else sections[matched])
        return {
            "id": dossier.id,
            **availability,
            "project_id": snapshot.project.id,
            "images": resolve_dossier_images(snapshot, selected_content),
            "title": dossier.title,
            "revision": dossier.revision,
            "snapshot": snapshot.digest,
            "section": matched,
            "editable_sections": editable_sections,
            "content": selected_content,
            "decision_reviews": decision_reviews,
            "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
        }

    resolved_citations = [_resolve_evidence_citation(repository, snapshot, ref) for ref in dossier.evidence_refs] if include_citations else []

    return {
        "id": dossier.id,
        **availability,
        "project_id": snapshot.project.id,
        "images": resolve_dossier_images(snapshot, dossier.body),
        "title": dossier.title,
        "language": dossier.language,
        "tags": dossier.tags,
        "body": dossier.body,
        "geography": dossier.geography.model_dump(mode="json") if dossier.geography else None,
        "geography_summary": summarize_geography(dossier.geography),
        "sections": list(sections.keys()),
        "editable_sections": editable_sections,
        "section_map": sections,
        "created_at": dossier.created_at,
        "created_by": dossier.created_by,
        "citations": resolved_citations,
        "revision": dossier.revision,
        "snapshot": snapshot.digest,
        "source_updates": source_updates(resolved_citations),
        "decision_reviews": decision_reviews,
        "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
    }


def create_claim(
    project: str | Path,
    *,
    title: str,
    statement: str,
    confidence: ClaimConfidence = "hypothetical",
    time_period: str | None = None,
    place: str | None = None,
    actors: list[str] | None = None,
    dossier_id: str | None = None,
    tags: list[str] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create one authored claim with optional period, place, actors and dossier link.

    Returns ``research-claim-local/1``; the claim is an author assertion, not
    a verified historical fact.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()

    dossier_ref = None
    if dossier_id:
        dossier = snapshot.latest(dossier_id, Dossier)
        dossier_ref = reference(dossier)
        require_active_dossier_association(snapshot, dossier_ref)

    scope = ClaimScope(
        time_period=time_period.strip() if time_period else None,
        place=place.strip() if place else None,
        actors=[a.strip() for a in (actors or []) if a.strip()],
    )

    values = envelope(snapshot.project.id, actor)
    claim = Claim(
        id=values["id"],
        project_id=values["project_id"],
        created_at=values["created_at"],
        created_by=values["created_by"],
        title=title.strip(),
        statement=statement.strip(),
        confidence=confidence,
        scope=scope,
        dossier_ref=dossier_ref,
        tags=[t.strip() for t in (tags or []) if t.strip()],
    )

    new_snapshot = repository.commit([claim], {}, snapshot)
    return {
        "schema_version": "research-claim-local/1",
        "claim_id": claim.id,
        "title": claim.title,
        "confidence": claim.confidence,
        "snapshot": new_snapshot.digest,
        "warnings": period_warnings(claim.scope.time_period),
    }


def list_claims(project: str | Path, *, dossier_id: str | None = None) -> dict[str, Any]:
    """Return claims and their selection context from one accepted snapshot."""
    return _list_claims(Repository(project).snapshot(kinds=frozenset({"claim"})), dossier_id=dossier_id)


def _list_claims(snapshot: Snapshot, *, dossier_id: str | None = None) -> dict[str, Any]:

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    claims_list: list[dict[str, Any]] = []
    for record in snapshot.records.values():
        if not isinstance(record, Claim) or record.id in withdrawn_or_purged:
            continue
        if dossier_id and (record.dossier_ref is None or record.dossier_ref.id != dossier_id):
            continue
        claims_list.append({
            "id": record.id,
            "revision": record.revision,
            "title": record.title,
            "statement": record.statement,
            "confidence": record.confidence,
            "scope": {
                "time_period": record.scope.time_period,
                "place": record.scope.place,
                "actors": record.scope.actors,
            },
            "dossier_id": record.dossier_ref.id if record.dossier_ref else None,
            "dossier_revision": record.dossier_ref.revision if record.dossier_ref else None,
            "tags": record.tags,
            "created_at": record.created_at,
            "created_by": record.created_by,
        })

    claims_list.sort(key=lambda c: str(c["created_at"]), reverse=True)
    return {
        "schema_version": "research-claims-local/2",
        "claims": claims_list,
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
    }


def timeline(project: str | Path, dossier_id: str | None = None) -> dict[str, Any]:
    """Read conservative chronology without modifying any authored period label."""
    return timeline_data(Repository(project).snapshot(kinds=frozenset({"claim"})), dossier_id=dossier_id)


def _reviewed_snapshot(snapshot: Snapshot, expected_snapshot: str | None,
                       expected_project_id: str | None = None) -> None:
    if expected_project_id is not None:
        try:
            Reference(id=expected_project_id)
        except ValidationError:
            raise ResearchError("Expected project ID must be a complete UUID URN") from None
        if snapshot.project.id != expected_project_id:
            raise ResearchConflictError("Research project changed; review the selected project before saving")
    if expected_snapshot is not None:
        if not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
            raise ResearchError("Expected snapshot must be a SHA-256 digest")
        if snapshot.digest != expected_snapshot:
            raise ResearchConflictError("Research snapshot changed; review the current context before saving")


def create_claim_relation(
    project: str | Path, from_claim_id: str, to_claim_id: str, *, relation: str = "causes",
    rationale: str | None = None, from_claim_revision: int | None = None,
    to_claim_revision: int | None = None, expected_snapshot: str | None = None,
    expected_project_id: str | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Explicitly record an author's cause/effect assertion between pinned claims."""
    if rationale is not None and not isinstance(rationale, str):
        raise ResearchError("Relation rationale must be a string or null")
    repository = Repository(project)
    snapshot = repository.snapshot()
    _reviewed_snapshot(snapshot, expected_snapshot, expected_project_id)
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}

    def endpoint(identifier: str, revision: int | None) -> Claim:
        if not isinstance(identifier, str):
            raise ResearchError("Claim identifier must be a string")
        if revision is not None and (type(revision) is not int or revision < 1):
            raise ResearchError("Claim revision must be a positive integer")
        if identifier in unavailable:
            raise ResearchError("Claim has been withdrawn or purged")
        try:
            return (snapshot.latest(identifier, Claim) if revision is None else
                    snapshot.get(Reference(id=identifier, revision=revision), Claim))
        except ValidationError:
            raise ResearchError("Invalid claim reference") from None

    first, second = endpoint(from_claim_id, from_claim_revision), endpoint(to_claim_id, to_claim_revision)
    try:
        recorded = ClaimRelation(**envelope(snapshot.project.id, actor),
                                 from_claim_ref=reference(first), to_claim_ref=reference(second),
                                 relation=normalize_claim_relation(relation), rationale=rationale.strip() or None if rationale else None)
    except (ValidationError, ValueError):
        raise ResearchError("Invalid causal relation; choose causes/results_in, distinct claims and bounded rationale") from None
    accepted = repository.commit([recorded], {}, snapshot)
    return {"schema_version": "research-claim-relation-local/1", "relation_id": recorded.id,
            "relation": recorded.relation, "from_claim_id": first.id, "from_claim_revision": first.revision,
            "to_claim_id": second.id, "to_claim_revision": second.revision, "snapshot": accepted.digest}


def list_claim_relations(
    project: str | Path, claim_id: str | None = None, include_retracted: bool = False,
) -> dict[str, Any]:
    """Read recorded pins and flag newer endpoint revisions without retargeting."""
    if type(include_retracted) is not bool:
        raise ResearchError("include_retracted must be a boolean")
    snapshot = Repository(project).snapshot()
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    selected = [record for record in snapshot.records.values() if isinstance(record, ClaimRelation)
                and record.id not in unavailable and (include_retracted or record.state == "active")
                and (claim_id is None or claim_id in (record.from_claim_ref.id, record.to_claim_ref.id))]
    selected.sort(key=lambda record: (record.created_at, record.id), reverse=True)
    return {"schema_version": "research-claim-relations-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "archive_schema_version": snapshot.manifest.schema_version,
            "relations": [claim_relation_view(snapshot, record) for record in selected]}


def link_evidence(
    project: str | Path,
    *,
    claim_id: str,
    passage_id: str,
    relation: EvidenceRelation = "supports",
    rationale: str | None = None,
    reviewer: str = "author",
    actor: str = "local-author",
    expected_snapshot: str | None = None,
    expected_claim_revision: int | None = None,
    expected_project_id: str | None = None,
) -> dict[str, Any]:
    """Link one retained passage to a claim with an explicit interpretation.

    ``expected_*`` guards reject changed reviewed context; returns
    ``research-evidence-link-local/1``. The link records your reading, not proof.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()

    _reviewed_snapshot(snapshot, expected_snapshot, expected_project_id)
    claim = snapshot.latest(claim_id, Claim)
    if expected_claim_revision is not None:
        if type(expected_claim_revision) is not int or expected_claim_revision < 1:
            raise ResearchError("Expected claim revision must be a positive integer")
        if claim.revision != expected_claim_revision:
            raise ResearchConflictError("Claim revision changed; review the current claim before saving")
    passage = snapshot.get(Reference(id=passage_id), Passage)
    if ((expected_snapshot is not None or expected_claim_revision is not None or expected_project_id is not None)
            and repository.citation(snapshot, passage)["availability"] != "available"):
        raise ResearchError("Selected evidence source has been withdrawn or purged")

    values = envelope(snapshot.project.id, actor)
    link = EvidenceLink(
        id=values["id"],
        project_id=values["project_id"],
        created_at=values["created_at"],
        created_by=values["created_by"],
        claim_ref=reference(claim),
        passage_ref=reference(passage),
        relation=relation,
        rationale=rationale.strip() if rationale else None,
        reviewer=reviewer.strip(),
    )

    new_snapshot = repository.commit([link], {}, snapshot)
    return {
        "schema_version": "research-evidence-link-local/1",
        "evidence_link_id": link.id,
        "claim_id": claim.id,
        "passage_id": passage.id,
        "relation": link.relation,
        "snapshot": new_snapshot.digest,
    }


def list_evidence_links(project: str | Path, *, claim_id: str | None = None) -> dict[str, Any]:
    """List current evidence links, optionally filtered to one claim.

    Withdrawn and purged targets are omitted; returns
    ``research-evidence-links-local/1``.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    links_list: list[dict[str, Any]] = []
    for record in snapshot.records.values():
        if not isinstance(record, EvidenceLink) or record.id in withdrawn_or_purged:
            continue
        if claim_id and record.claim_ref.id != claim_id:
            continue

        claim_latest = snapshot.records.get(record.claim_ref.id)
        claim_latest_revision = claim_latest.revision if isinstance(claim_latest, Claim) else record.claim_ref.revision
        citation = resolve_evidence_citation(repository, snapshot, record.passage_ref)
        links_list.append({
            "id": record.id,
            "revision": record.revision,
            "claim_id": record.claim_ref.id,
            "claim_revision": record.claim_ref.revision,
            "claim_latest_revision": claim_latest_revision,
            "passage_id": record.passage_ref.id,
            "relation": record.relation,
            "rationale": record.rationale,
            "reviewer": record.reviewer,
            "citation": citation,
            "created_at": record.created_at,
            "created_by": record.created_by,
        })

    links_list.sort(key=lambda item: str(item["created_at"]), reverse=True)
    return {
        "schema_version": "research-evidence-links-local/1",
        "evidence_links": links_list,
    }


def record_decision(
    project: str | Path,
    *,
    title: str,
    rationale: str,
    claim_id: str | None = None,
    deviation_from_fact: bool = False,
    impact_on_plot: str | None = None,
    dossier_ids: list[str] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Record one authored decision with rationale and optional claim/dossier links.

    Returns ``research-decision-local/1``; a checked deviation marks an
    explicit departure from the evidence, not its accuracy.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()

    claim_ref = None
    if claim_id:
        claim = snapshot.latest(claim_id, Claim)
        claim_ref = reference(claim)

    dossier_refs = []
    if dossier_ids:
        for did in dict.fromkeys(dossier_ids):
            if did.strip():
                dossier = snapshot.latest(did.strip(), Dossier)
                selected = reference(dossier)
                require_active_dossier_association(snapshot, selected)
                dossier_refs.append(selected)

    values = envelope(snapshot.project.id, actor)
    decision = Decision(
        id=values["id"],
        project_id=values["project_id"],
        created_at=values["created_at"],
        created_by=values["created_by"],
        title=title.strip(),
        rationale=rationale.strip(),
        claim_ref=claim_ref,
        deviation_from_fact=deviation_from_fact,
        impact_on_plot=impact_on_plot.strip() if impact_on_plot else None,
        dossier_refs=dossier_refs,
    )

    new_snapshot = repository.commit([decision], {}, snapshot)
    return {
        "schema_version": "research-decision-local/1",
        "decision_id": decision.id,
        "title": decision.title,
        "deviation_from_fact": decision.deviation_from_fact,
        "dossier_ids": [ref.id for ref in decision.dossier_refs],
        "snapshot": new_snapshot.digest,
    }


def acknowledge_decision(project: str | Path, decision_id: str, dossier_id: str, *,
                         expected_snapshot: str, expected_decision_revision: int,
                         expected_dossier_revision: int, status: Literal["applied", "review_needed"],
                         note: str | None = None, actor: str = "local-author") -> dict[str, Any]:
    """Append an explicit author's acknowledgement; never edit or verify their prose."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    if snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; reload before acknowledging")
    if (type(expected_decision_revision) is not int or expected_decision_revision < 1
            or type(expected_dossier_revision) is not int or expected_dossier_revision < 1):
        raise ResearchError("Exact positive decision and dossier revisions are required")
    try:
        Reference(id=decision_id)
        Reference(id=dossier_id)
        decision = snapshot.latest(decision_id, Decision)
        dossier = snapshot.latest(dossier_id, Dossier)
    except ValidationError:
        raise ResearchError("Invalid decision or dossier identifier") from None
    if decision.revision != expected_decision_revision or dossier.revision != expected_dossier_revision:
        raise ResearchConflictError("Decision or dossier revision changed; reload before acknowledging")
    require_active_dossier_association(snapshot, reference(dossier))
    impact = editorial.decision_graph(snapshot, decision_id=decision_id).get(decision_id)
    if impact is None or dossier_id not in {entry["id"] for entry in impact["dossiers"]}:
        raise ResearchError("Acknowledge only a dossier explicitly associated with this decision")
    if (not isinstance(status, str) or status not in {"applied", "review_needed"}
            or not isinstance(actor, str) or not actor.strip()
            or (note is not None and not isinstance(note, str))):
        raise ResearchError("Acknowledgement requires an explicit valid status, actor and optional text note")
    previous = latest_acknowledgements(snapshot.records.values()).get((decision_id, dossier_id))
    try:
        acknowledgement = DecisionAcknowledgement(**envelope(snapshot.project.id, actor.strip()),
            decision_ref=reference(decision), dossier_ref=reference(dossier), status=status,
            note=note.strip() or None if note is not None else None,
            supersedes_ref=reference(previous) if previous else None)
    except ValidationError:
        raise ResearchError("Invalid acknowledgement fields; check actor and note size") from None
    committed = repository.commit([acknowledgement], {}, snapshot)
    return {"schema_version": "research-decision-acknowledgement-local/1", "project_id": snapshot.project.id,
            "acknowledgement_id": acknowledgement.id, "snapshot": committed.digest,
            "decision_id": decision.id, "decision_revision": decision.revision,
            "dossier_id": dossier.id, "dossier_revision": dossier.revision, "status": acknowledgement.status,
            "note": acknowledgement.note, "actor": acknowledgement.created_by,
            "created_at": acknowledgement.created_at, "supersedes_id": previous.id if previous else None}


def decision_impact(project: str | Path, decision_id: str) -> dict[str, Any]:
    """Inspect explicit affected dossiers and revision pins without writing."""
    return editorial.decision_impact(project, decision_id, outline=lambda body: list(extract_sections(body)))


def editorial_review(project: str | Path) -> dict[str, Any]:
    """List structural review candidates, never semantic or quality verdicts."""
    return editorial.editorial_review(project, outline=lambda body: list(extract_sections(body)))


def list_decisions(project: str | Path) -> dict[str, Any]:
    """List current author decisions; returns ``research-decisions-local/1``."""
    return _list_decisions(Repository(project).snapshot())


def _list_decisions(snapshot: Snapshot) -> dict[str, Any]:

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    decisions_list: list[dict[str, Any]] = []
    for record in snapshot.records.values():
        if not isinstance(record, Decision) or record.id in withdrawn_or_purged:
            continue
        decisions_list.append({
            "id": record.id,
            "revision": record.revision,
            "title": record.title,
            "rationale": record.rationale,
            "claim_id": record.claim_ref.id if record.claim_ref else None,
            "claim_revision": record.claim_ref.revision if record.claim_ref else None,
            "dossier_ids": [ref.id for ref in record.dossier_refs],
            "deviation_from_fact": record.deviation_from_fact,
            "impact_on_plot": record.impact_on_plot,
            "created_at": record.created_at,
            "created_by": record.created_by,
        })

    decisions_list.sort(key=lambda d: str(d["created_at"]), reverse=True)
    return {
        "schema_version": "research-decisions-local/1",
        "decisions": decisions_list,
    }


def project_overview(project: str | Path) -> dict[str, Any]:
    """Collect dashboard lists from one verified archive view, without caching."""
    snapshot = Repository(project).snapshot()
    data: dict[str, Any] = {"project_id": snapshot.project.id,
                            "project_title": snapshot.project.title,
                            "project_language": snapshot.project.language}
    for key, listing in (("sources", _list_sources(snapshot)),
                         ("dossiers", _list_dossiers(snapshot)),
                         ("claims", _list_claims(snapshot)),
                         ("decisions", _list_decisions(snapshot))):
        data[key] = listing[key]
        data[key + "_count"] = len(listing[key])
    return data


MatrixFormat = Literal["json", "md", "csv"]
MATRIX_FORMATS: tuple[MatrixFormat, ...] = get_args(MatrixFormat)
_FORMAT_SENTINEL = object()


def matrix_format(value: object) -> MatrixFormat:
    """Normalise a submitted matrix format or raise a clear error."""
    text = str(value or "").strip().lower()
    for candidate in MATRIX_FORMATS:
        if text == candidate:
            return candidate
    raise ResearchError(f"Unsupported claim matrix format: {value!r}")


def claim_matrix(
    project: str | Path,
    *,
    format: MatrixFormat | object = _FORMAT_SENTINEL,
) -> dict[str, Any] | str:
    """Return the claim-evidence-decision matrix.

    Returns plain data. For rendered output call `render_claim_matrix`, or
    `claim_matrix_format` to get data and rendering in one call.

    Deprecated: passing ``format=``. The compatibility wrapper remains accepted
    until a future release; use `render_claim_matrix` instead.
    """
    if format is not _FORMAT_SENTINEL:
        warnings.warn(
            "claim_matrix(format=...) is deprecated and will be removed in a future release; "
            "call claim_matrix() for data and render_claim_matrix(data, format=...) "
            "for rendered output",
            DeprecationWarning,
            stacklevel=2,
        )
        return claim_matrix_format(project, format=matrix_format(format))
    return claim_matrix_data(project)


def claim_matrix_data(project: str | Path) -> dict[str, Any]:
    """Compute the claim-evidence-decision matrix as plain data."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    # Map dossiers by ID (latest revision)
    dossiers_by_id: dict[str, Dossier] = {}
    for record in snapshot.records.values():
        if (isinstance(record, Dossier) and record.id not in withdrawn_or_purged
                and (record.id not in dossiers_by_id or record.revision > dossiers_by_id[record.id].revision)):
            dossiers_by_id[record.id] = record

    # Map claims by ID (latest revision)
    claims_by_id: dict[str, Claim] = {}
    for record in snapshot.records.values():
        if (isinstance(record, Claim) and record.id not in withdrawn_or_purged
                and (record.id not in claims_by_id or record.revision > claims_by_id[record.id].revision)):
            claims_by_id[record.id] = record

    # Evidence links grouped by claim_id
    evidence_by_claim: dict[str, list[dict[str, Any]]] = {}
    total_evidence_count = 0
    for record in snapshot.records.values():
        if isinstance(record, EvidenceLink) and record.id not in withdrawn_or_purged:
            cid = record.claim_ref.id
            if cid not in evidence_by_claim:
                evidence_by_claim[cid] = []
            citation = resolve_evidence_citation(repository, snapshot, record.passage_ref)
            evidence_by_claim[cid].append({
                "link_id": record.id,
                "relation": record.relation,
                "rationale": record.rationale,
                "passage_id": record.passage_ref.id,
                "source_title": citation.get("source_title", ""),
                "verbatim": citation.get("verbatim", ""),
                "citation": citation,
            })
            total_evidence_count += 1

    # Decisions grouped by claim_id
    decisions_by_claim: dict[str, list[dict[str, Any]]] = {}
    unlinked_decisions: list[dict[str, Any]] = []
    total_decisions_count = 0
    for record in snapshot.records.values():
        if isinstance(record, Decision) and record.id not in withdrawn_or_purged:
            dec_item = {
                "decision_id": record.id,
                "title": record.title,
                "rationale": record.rationale,
                "deviation_from_fact": record.deviation_from_fact,
                "impact_on_plot": record.impact_on_plot,
            }
            if record.claim_ref:
                cid = record.claim_ref.id
                if cid not in decisions_by_claim:
                    decisions_by_claim[cid] = []
                decisions_by_claim[cid].append(dec_item)
            else:
                unlinked_decisions.append(dec_item)
            total_decisions_count += 1

    matrix_claims: list[dict[str, Any]] = []
    supported_count = 0
    contradicted_count = 0
    unverified_count = 0
    deviation_count = 0

    sorted_claims = sorted(claims_by_id.values(), key=lambda c: str(c.created_at))
    for claim in sorted_claims:
        c_evidence = evidence_by_claim.get(claim.id, [])
        c_decisions = decisions_by_claim.get(claim.id, [])

        counts = {
            "supports": sum(1 for e in c_evidence if e["relation"] == "supports"),
            "contradicts": sum(1 for e in c_evidence if e["relation"] == "contradicts"),
            "qualifies": sum(1 for e in c_evidence if e["relation"] == "qualifies"),
            "contextualizes": sum(1 for e in c_evidence if e["relation"] == "contextualizes"),
            "total": len(c_evidence),
        }

        has_deviation = any(d["deviation_from_fact"] for d in c_decisions)
        if has_deviation:
            deviation_count += 1

        if counts["contradicts"] > 0:
            status = "contradicted"
            contradicted_count += 1
        elif counts["supports"] > 0:
            status = "supported"
            supported_count += 1
        else:
            status = "unverified"
            unverified_count += 1

        dossier_title = None
        dossier_id = claim.dossier_ref.id if claim.dossier_ref else None
        if dossier_id and dossier_id in dossiers_by_id:
            dossier_title = dossiers_by_id[dossier_id].title

        matrix_claims.append({
            "claim_id": claim.id,
            "revision": claim.revision,
            "title": claim.title,
            "statement": claim.statement,
            "confidence": claim.confidence,
            "scope": {
                "time_period": claim.scope.time_period,
                "place": claim.scope.place,
                "actors": claim.scope.actors,
            },
            "dossier_id": dossier_id,
            "dossier_title": dossier_title,
            "status": status,
            "has_deviation": has_deviation,
            "evidence_counts": counts,
            "evidence": c_evidence,
            "decisions": c_decisions,
            "created_at": claim.created_at,
        })

    summary = {
        "total_claims": len(matrix_claims),
        "supported_claims": supported_count,
        "contradicted_claims": contradicted_count,
        "unverified_claims": unverified_count,
        "deviation_claims": deviation_count,
        "total_evidence_links": total_evidence_count,
        "total_decisions": total_decisions_count,
    }

    return {
        "schema_version": "research-claim-matrix-local/1",
        "project_id": snapshot.project.id,
        "project_title": snapshot.project.title,
        "summary": summary,
        "claims": matrix_claims,
        "unlinked_decisions": unlinked_decisions,
    }


def render_claim_matrix(
    data: dict[str, Any], *, format: Literal["md", "csv"] = "md"
) -> str:
    """Render a `claim_matrix` result as Markdown or CSV."""
    project_id = data.get("project_id", "")
    project_title = data.get("project_title", "")
    summary = data.get("summary", {})
    matrix_claims = data.get("claims", [])

    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow([
            "claim_id",
            "title",
            "confidence",
            "status",
            "has_deviation",
            "dossier",
            "statement",
            "evidence_relation",
            "source_title",
            "passage_quote",
            "decision_title",
            "deviation_from_fact",
        ])
        for c in matrix_claims:
            ev_list = c["evidence"] or [{}]
            dec_list = c["decisions"] or [{}]
            for ev in ev_list:
                for dec in dec_list:
                    writer.writerow([
                        c["claim_id"],
                        c["title"],
                        c["confidence"],
                        c["status"],
                        "yes" if c["has_deviation"] else "no",
                        c["dossier_title"] or "",
                        c["statement"],
                        ev.get("relation", ""),
                        ev.get("source_title", ""),
                        ev.get("verbatim", ""),
                        dec.get("title", ""),
                        "yes" if dec.get("deviation_from_fact") else ("no" if dec else ""),
                    ])
        return out.getvalue()

    lines = [
        f"# Research Claim-Evidence Matrix: {project_title}",
        "",
        f"- **Project ID:** `{project_id}`",
        f"- **Total Claims:** {summary['total_claims']}",
        f"- **Supported:** {summary['supported_claims']} · **Contradicted:** {summary['contradicted_claims']} · **Unverified:** {summary['unverified_claims']}",
        f"- **Deliberate Deviations from Fact:** {summary['deviation_claims']}",
        f"- **Total Evidence Citations:** {summary['total_evidence_links']}",
        "",
        "| Claim | Confidence | Status | Dossier | Evidence (Supp / Contradict / Total) | Decisions / Deviations |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    if not matrix_claims:
        lines.append("| *(no claims recorded)* | – | – | – | – | – |")
    else:
        for c in matrix_claims:
            counts = c["evidence_counts"]
            ev_str = f"+{counts['supports']} / -{counts['contradicts']} (total: {counts['total']})"
            dec_str = ", ".join(
                f"{d['title']}{' [DEVIATION]' if d['deviation_from_fact'] else ''}"
                for d in c["decisions"]
            ) or "–"
            dossier_str = c["dossier_title"] or "–"
            dev_badge = " [DEVIATION]" if c["has_deviation"] else ""
            clean_stmt = c["statement"].replace("\n", " ").replace("|", "\\|")
            if len(clean_stmt) > 80:
                clean_stmt = clean_stmt[:80] + "..."
            clean_title = c["title"].replace("|", "\\|")
            lines.append(
                f"| **{clean_title}**<br/>*{clean_stmt}* | "
                f"`{c['confidence']}` | `{c['status']}`{dev_badge} | {dossier_str} | {ev_str} | {dec_str} |"
            )

    return "\n".join(lines) + "\n"


def claim_matrix_format(
    project: str | Path, *, format: MatrixFormat = "json"
) -> dict[str, Any] | str:
    """Data and rendering in one call, selected by `format`."""
    data = claim_matrix_data(project)
    return data if format == "json" else render_claim_matrix(data, format=format)
