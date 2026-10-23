"""Explicit dossier-scoped corrections of retained media provenance metadata."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from .images import IMAGE_TYPES, _image_tokens, validate_image, validate_image_changes
from .media import MEDIA_TYPES, validate_media
from .models import (
    Dossier,
    Entity,
    Extraction,
    Reference,
    Source,
    SourceContext,
    SourceVersion,
    Tombstone,
)
from .repository import Repository, ResearchConflictError, ResearchError
from .revisions import _apply_changes, _record


def update_dossier_media_context(
    project: str | Path, dossier_id: str, source_id: str, source_version_id: str, *,
    expected_snapshot: str, expected_revision: int, context: Mapping[str, Any],
    reason: str, actor: str = "local-author", dry_run: bool = False,
) -> dict[str, Any]:
    """Correct provenance and repin this dossier; retain all prior records and bytes.

    The patch starts from the explicitly selected version's context. All active
    occurrences of that exact attachment pin in this dossier change together;
    code, captions, alternative text and other dossiers remain byte-for-byte.
    Extracted documents require their separate text-provenance workflow.
    """
    from .api import envelope

    if (type(expected_revision) is not int or expected_revision < 1
            or not isinstance(expected_snapshot, str) or not expected_snapshot):
        raise ResearchError("Media context correction requires an expected snapshot and dossier revision")
    if type(dry_run) is not bool:
        raise ResearchError("Media context dry_run must be a boolean")
    if not isinstance(actor, str) or not 1 <= len(actor) <= 200:
        raise ResearchError("Media context actor must be text of 1 to 200 characters")
    if (not isinstance(context, Mapping)
            or set(context) - {"origin_url", "provenance_note"}):
        raise ResearchError("Media context correction accepts only origin_url and provenance_note")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ResearchError("Media context correction requires a nonblank reason of at most 2000 characters")
    repository = Repository(project)
    snapshot = repository.snapshot()
    dossier = _record(snapshot, "dossier", dossier_id)
    if not isinstance(dossier, Dossier):
        raise ResearchError("Media context correction requires a dossier")
    if snapshot.digest != expected_snapshot or dossier.revision != expected_revision:
        raise ResearchConflictError("Research snapshot or dossier revision changed; reload and retry correction")
    try:
        source = snapshot.get(Reference(id=source_id), Source)
        selected = snapshot.get(Reference(id=source_version_id), SourceVersion)
    except ValidationError:
        raise ResearchError("Invalid source or source version identifier") from None
    if selected.source_ref.id != source.id:
        raise ResearchError("Selected media version does not belong to the requested source")
    versions = [record for record in snapshot.records.values()
                if isinstance(record, SourceVersion) and record.source_ref.id == source.id]
    latest = max(versions, key=lambda record: record.sequence)
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    if unavailable & {source.id, selected.id, latest.id}:
        raise ResearchError("Selected media source or version has been withdrawn or purged")
    if selected.blob != latest.blob:
        raise ResearchError("The latest source version has different bytes; review source versions before correcting metadata")
    if selected.blob.media_type not in IMAGE_TYPES | MEDIA_TYPES:
        raise ResearchError("Context correction requires retained image, PDF or video media")
    if any(isinstance(record, Extraction) and record.source_version_ref.id in {selected.id, latest.id}
           for record in snapshot.records.values()):
        raise ResearchError("Extracted media requires its text-provenance workflow; metadata correction cannot discard extraction lineage")
    content = repository.read_blob(selected.blob)
    checked = validate_image(content) if selected.blob.media_type in IMAGE_TYPES else validate_media(content)
    if checked["media_type"] != selected.blob.media_type:
        raise ResearchError("Retained media does not match its blob descriptor")
    try:
        corrected = SourceContext.model_validate({**selected.context.model_dump(), **dict(context)})
    except ValidationError as exc:
        raise ResearchError(str(exc)) from None

    is_media = selected.blob.media_type in MEDIA_TYPES
    namespace = "media" if is_media else "image"
    old_destination = f"lixity:{namespace}/{source.id}/{selected.id}"
    matches = [match for match in _image_tokens(dossier.body, media=is_media)
               if match.group(2) == old_destination]
    if not matches:
        raise ResearchError("Selected source version has no active canonical attachment references in this dossier")
    additions: list[Entity] = []
    if corrected == selected.context:
        replacement = selected
    elif corrected == latest.context:
        replacement = latest
    else:
        replacement = SourceVersion(**envelope(snapshot.project.id, actor), source_ref=selected.source_ref,
            sequence=latest.sequence + 1, blob=selected.blob, retention_confirmed=True,
            redistribution=selected.redistribution, context=corrected,
            schema_version=("research-local/9" if is_media else
                            "research-local/3" if corrected.external_reference else
                            "research-local/2" if corrected.origin_url else "research-local/1"))
        additions.append(replacement)
    changed = replacement.id != selected.id
    revised = dossier
    if changed:
        body = dossier.body
        destination = f"lixity:{namespace}/{source.id}/{replacement.id}"
        for match in reversed(matches):
            body = body[:match.start(2)] + destination + body[match.end(2):]
        revised = cast(Dossier, _apply_changes(snapshot, dossier, {"body": body},
            change_kind="correction", reason=reason, actor=actor))
        additions.append(revised)
        candidate, _ = repository.prepare_commit(additions, snapshot)
        validate_image_changes(candidate, revised.body, dossier.body)
        if not dry_run:
            snapshot = repository.commit(additions, {}, snapshot)
    elif dry_run:
        repository.prepare_commit([], snapshot)
    return {
        "schema_version": "research-media-context-preview-local/1" if dry_run else "research-media-context-local/1",
        "project_id": snapshot.project.id, "snapshot": snapshot.digest,
        "dossier_id": dossier.id, "dossier_revision": revised.revision,
        "source_id": source.id, "previous_source_version_id": selected.id,
        "source_version_id": replacement.id, "source_sha256": selected.blob.sha256,
        "context_before": {"origin_url": selected.context.origin_url, "provenance_note": selected.context.provenance_note},
        "context_after": {"origin_url": corrected.origin_url, "provenance_note": corrected.provenance_note},
        "references_updated": len(matches) if changed else 0,
        "changed": changed, "dry_run": dry_run,
    }
