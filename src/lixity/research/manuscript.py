"""Manual manuscript associations and read-only review of exact displayed anchors."""

import warnings
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from ..config import _load_toml
from ..io import FileUtils
from ..markdown_parser import strip_inline_markup
from ..pipeline import document_paragraph_texts, paragraph_identity, resolve_document_config
from ..status import ManuscriptFlag, ManuscriptState
from ..style_profile import ParagraphProfile, ParagraphText
from .models import (
    Claim,
    ManuscriptAnchor,
    ManuscriptClaimLink,
    Reference,
    RevisionChange,
    Tombstone,
)
from .repository import Repository, ResearchConflictError, ResearchError, Snapshot


def _source_path(repository: Repository, manuscript: str | Path) -> tuple[Path, str]:
    """Resolve inside the explicit project; traversal and escaping symlinks fail."""
    supplied = Path(manuscript).expanduser()
    if ".." in supplied.parts:
        raise ResearchError("Manuscript path must remain inside the explicit project")
    path = supplied if supplied.is_absolute() else repository.root / supplied
    try:
        relative = path.relative_to(repository.root).as_posix()
        path.resolve().relative_to(repository.root)
    except (ValueError, OSError, RuntimeError):
        raise ResearchError("Manuscript path escapes the explicit project") from None
    if relative == ".":
        raise ResearchError("Supply a manuscript file inside the explicit project")
    return path, relative


def _paragraphs(
    text: str,
    repository: Repository,
    language: str | None,
    project_config: Mapping[str, Any] | None,
) -> list[ParagraphText]:
    # Only this project's files participate. No user or ancestor config discovery.
    settings: dict[str, Any] = {}
    try:
        if project_config is None:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                for name in ("pyproject.toml", "lixity.toml"):
                    path = repository.root / name
                    if path.exists():
                        repository.safe(path)
                        settings.update(_load_toml(path))
        else:
            settings.update(project_config)
        config, _ = resolve_document_config(
            text, language or settings.get("language", "en"), project_config=settings
        )
        return document_paragraph_texts(text, config)
    except (ValueError, Warning) as exc:
        raise ResearchError("Could not resolve explicit manuscript analysis settings") from exc


def manuscript_link_view(snapshot: Snapshot, record: ManuscriptClaimLink) -> dict[str, Any]:
    """Resolve the pinned claim, preserving the earlier dossier association."""
    claim = snapshot.get(record.claim_ref, Claim)
    current = snapshot.latest(claim.id, Claim)
    changed = current.revision != claim.revision
    withdrawn = any(
        kind == "claim" and identifier == claim.id
        for _operation, kind, identifier in snapshot.lifecycle
    )
    return {
        "link_id": record.id,
        "revision": record.revision,
        "state": record.state,
        "claim_id": claim.id,
        "claim_revision": claim.revision,
        "claim_current_revision": current.revision,
        "claim_title": claim.title,
        "claim_changed": changed,
        "claim_withdrawn": withdrawn,
        "dossier_id": claim.dossier_ref.id if claim.dossier_ref else None,
        "dossier_revision": claim.dossier_ref.revision if claim.dossier_ref else None,
        "anchor": record.anchor.model_dump(mode="json"),
        "review_needed": changed or withdrawn,
        "note": record.note,
    }


def list_manuscript_links(
    project: str | Path, *, claim_id: str | None = None, include_retracted: bool = False
) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    return manuscript_links_data(snapshot, claim_id=claim_id, include_retracted=include_retracted)


def manuscript_links_data(
    snapshot: Snapshot, *, claim_id: str | None = None, include_retracted: bool = False
) -> dict[str, Any]:
    """Build the native association list from one verified archive view."""
    if claim_id is not None:
        try:
            snapshot.latest(Reference(id=claim_id).id, Claim)
        except ValidationError:
            raise ResearchError("Invalid claim identifier") from None
    links = [
        manuscript_link_view(snapshot, record)
        for record in snapshot.records.values()
        if isinstance(record, ManuscriptClaimLink)
        and (include_retracted or record.state == "active")
        and (claim_id is None or record.claim_ref.id == claim_id)
    ]
    return {
        "schema_version": "research-manuscript-links-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "archive_schema_version": snapshot.manifest.schema_version,
        "links": links,
    }


def manuscript_review_data(
    snapshot: Snapshot,
    *,
    source_path: str,
    source_sha256: str | None,
    paragraphs: Sequence[ParagraphProfile | ParagraphText],
    source_state: str = "available",
) -> dict[str, Any]:
    """Derive review flags only; resolving happens in an explicit re-pin."""
    identities = [(paragraph, paragraph_identity(paragraph)) for paragraph in paragraphs]
    rows = []
    for record in snapshot.records.values():
        if (
            not isinstance(record, ManuscriptClaimLink)
            or record.state != "active"
            or record.anchor.source_path != source_path
        ):
            continue
        row = manuscript_link_view(snapshot, record)
        displayed_flags = (ManuscriptFlag.CLAIM_CHANGED, ManuscriptFlag.CLAIM_WITHDRAWN)
        flags: list[str] = [flag for flag in displayed_flags if row[flag]]
        anchor = record.anchor
        resolved: ParagraphProfile | ParagraphText | None = None
        resolved_start: int | None = None
        resolved_end: int | None = None
        candidate_lines: list[int] = []
        if source_state != "available":
            flags.append("source_" + source_state)  # missing/unreadable keep their own code
            state = ManuscriptState.UNAVAILABLE
        else:
            if source_sha256 != anchor.source_sha256:
                flags.append(ManuscriptFlag.SOURCE_CHANGED)
            candidates = [
                p
                for p, identity in identities
                if identity["paragraph_sha256"] == anchor.paragraph_sha256
                and p.text[anchor.start : anchor.end] == anchor.quote
            ]
            exact = [
                p
                for p in candidates
                if p.start_line == anchor.start_line and p.end_line == anchor.end_line
            ]
            if len(exact) == 1:
                resolved, state = exact[0], ManuscriptState.RESOLVED
                resolved_start, resolved_end = anchor.start, anchor.end
                candidate_lines = [resolved.start_line]
            elif len(candidates) > 1:
                state = ManuscriptState.AMBIGUOUS
                flags.append(ManuscriptFlag.ANCHOR_AMBIGUOUS)
                candidate_lines = [p.start_line for p in candidates]
            elif candidates:
                resolved, state = candidates[0], ManuscriptState.MOVED
                flags.append(ManuscriptFlag.ANCHOR_MOVED)
                resolved_start, resolved_end = anchor.start, anchor.end
                candidate_lines = [resolved.start_line]
            else:
                # The pinned paragraph was edited. The recorded quote is the
                # contract: exactly one remaining occurrence keeps the anchor
                # resolvable (`adjusted`); missing or duplicated quotes need
                # review before any re-pin.
                occurrences = _quote_occurrences(paragraphs, anchor.quote)
                if len(occurrences) == 1:
                    resolved, resolved_start = occurrences[0]
                    resolved_end = resolved_start + len(anchor.quote)
                    state = ManuscriptState.ADJUSTED
                    flags.append(ManuscriptFlag.ANCHOR_ADJUSTED)
                    candidate_lines = [resolved.start_line]
                elif len(occurrences) > 1:
                    state = ManuscriptState.AMBIGUOUS
                    flags.append(ManuscriptFlag.ANCHOR_AMBIGUOUS)
                    candidate_lines = sorted({p.start_line for p, _ in occurrences})
                else:
                    state = ManuscriptState.CHANGED
                    flags.append(ManuscriptFlag.ANCHOR_CHANGED)
        # The file-level digest is informational: an edit elsewhere must not
        # re-open associations whose paragraph, line span and quote still match.
        review_blocking = [flag for flag in flags if flag != ManuscriptFlag.SOURCE_CHANGED]
        row.update(
            source_path=source_path,
            current_source_sha256=source_sha256,
            flags=flags,
            anchor_state=state,
            review_needed=bool(review_blocking),
            resolved_start_line=resolved.start_line if resolved else None,
            resolved_end_line=resolved.end_line if resolved else None,
            resolved_start=resolved_start,
            resolved_end=resolved_end,
            resolved_chapter_num=resolved.chapter_num if resolved else None,
            resolved_chapter_title=resolved.chapter_title if resolved else None,
            candidate_lines=candidate_lines,
        )
        rows.append(row)
    return {
        "schema_version": "research-manuscript-review-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "archive_schema_version": snapshot.manifest.schema_version,
        "source_path": source_path,
        "source_state": source_state,
        "current_source_sha256": source_sha256,
        "links": rows,
        "review_needed_count": sum(row["review_needed"] for row in rows),
    }


def review_manuscript_links(
    project: str | Path,
    manuscript: str | Path,
    *,
    expected_project_id: str | None = None,
    language: str | None = None,
    project_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id is not None and snapshot.project.id != expected_project_id:
        raise ResearchConflictError("Research project changed; reopen the intended project")
    path, relative = _source_path(repository, manuscript)
    state, source_sha256, paragraphs = "available", None, []
    try:
        text, source_sha256 = FileUtils.read_source_snapshot(str(path))
        paragraphs = _paragraphs(text, repository, language, project_config)
    except FileNotFoundError:
        state = "missing"
    except (OSError, UnicodeError):
        state, source_sha256 = "unreadable", None
    return manuscript_review_data(
        snapshot,
        source_path=relative,
        source_sha256=source_sha256,
        paragraphs=paragraphs,
        source_state=state,
    )


def _quote_occurrences(
    paragraphs: Sequence[ParagraphProfile | ParagraphText], quote: str, *, limit: int | None = None,
) -> list[tuple[ParagraphProfile | ParagraphText, int]]:
    """Exact quote occurrences in displayed text, stopping at an optional limit.

    The recorded quote is the link's contract: whole-paragraph hashes guard the
    pinned identity, but a still-unique quote keeps the anchor resolvable when
    the surrounding paragraph text changes.
    """
    occurrences: list[tuple[ParagraphProfile | ParagraphText, int]] = []
    for paragraph in paragraphs:
        start = paragraph.text.find(quote)
        while start != -1:
            occurrences.append((paragraph, start))
            if limit is not None and len(occurrences) >= limit:
                return occurrences
            start = paragraph.text.find(quote, start + 1)
    return occurrences


def resolve_manuscript_anchor(
    project: str | Path,
    manuscript: str | Path,
    *,
    query: str,
    query_format: Literal["display", "markdown"] = "display",
    line: int | None = None,
    language: str | None = None,
    project_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one displayed-text quote to exact selection fields (read-only).

    Offsets and quotes refer to ``ParagraphProfile.text``. The default query is
    literal displayed text; explicit Markdown queries use that same projection
    before exact matching. Neither mode includes headings or folds Unicode/case.
    """
    if query_format not in ("display", "markdown"):
        raise ResearchError("Unsupported query format; choose display or markdown")
    if not isinstance(query, str) or not query.strip():
        raise ResearchError("Provide a nonempty quote to resolve")
    if query_format == "markdown":
        query = strip_inline_markup(query)
        if not query.strip():
            raise ResearchError("Provide a nonempty displayed quote after Markdown cleanup")
    if line is not None and (type(line) is not int or line < 1):
        raise ResearchError("Line must be a positive integer")
    repository = Repository(project)
    snapshot = repository.snapshot()
    path, relative = _source_path(repository, manuscript)
    try:
        text, _source_sha256 = FileUtils.read_source_snapshot(str(path))
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source is missing or unreadable") from exc
    paragraphs = _paragraphs(text, repository, language, project_config)
    scope = "in the displayed paragraphs"
    if line is not None:
        paragraphs = [
            paragraph
            for paragraph in paragraphs
            if paragraph.start_line <= line <= paragraph.end_line
        ]
        scope = "in the paragraph at the given line"
    occurrences = _quote_occurrences(paragraphs, query, limit=2)
    if not occurrences:
        message = f"Quote was not found {scope}"
        if query_format == "display":
            message += ("; inline Markdown markers are removed from the displayed text. "
                        "For a copied Markdown quote, use find-anchor --query-format markdown")
        else:
            message += " after supported inline Markdown cleanup"
        raise ResearchError(message + "; headings are outside paragraph anchors")
    if len(occurrences) > 1:
        lines = ", ".join(
            str(paragraph.start_line) for paragraph in paragraphs if query in paragraph.text
        )
        raise ResearchError(
            f"Quote is ambiguous {scope} (lines: {lines}); add --line to choose one"
        )
    paragraph, start = occurrences[0]
    identity = paragraph_identity(paragraph)
    return {
        "schema_version": "research-anchor-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "source_path": relative,
        "start_line": paragraph.start_line,
        "end_line": paragraph.end_line,
        "paragraph_sha256": identity["paragraph_sha256"],
        "start": start,
        "end": start + len(query),
        "quote": query,
    }


def reanchor_manuscript_link(
    project: str | Path,
    manuscript: str | Path,
    link_id: str,
    *,
    expected_project_id: str,
    expected_snapshot: str,
    expected_revision: int,
    expected_source_sha256: str,
    actor: str = "local-author",
    language: str | None = None,
    project_config: Mapping[str, Any] | None = None,
    new_quote: str | None = None,
    line: int | None = None,
    reason: str | None = None,
    new_claim_revision: int | None = None,
) -> dict[str, Any]:
    """Re-pin one uniquely resolvable anchor; the earlier position stays in history.

    Moved paragraphs keep their recorded quote; adjusted paragraphs were edited
    outside the quote, so the re-pin also refreshes hash and offsets. When
    ``new_quote`` is supplied explicitly, a ``changed`` anchor is re-pinned to
    the revised displayed-text quote while the earlier quote remains in history.
    ``new_claim_revision`` explicitly accepts the current claim revision in the
    same association revision as the anchor update.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id != snapshot.project.id:
        raise ResearchConflictError("Research project changed; reopen the intended project")
    if expected_snapshot != snapshot.digest:
        raise ResearchConflictError("Research snapshot changed; reload before saving")
    try:
        record = snapshot.latest(Reference(id=link_id).id, ManuscriptClaimLink)
    except ValidationError:
        raise ResearchError("Invalid manuscript link identifier") from None
    if record.state != "active":
        raise ResearchError("Retracted associations cannot be re-pinned")
    if type(expected_revision) is not int or record.revision != expected_revision:
        raise ResearchConflictError("Manuscript link revision changed; review it before re-pinning")
    claim = (_reviewed_claim_revision(snapshot, record, new_claim_revision)
             if new_claim_revision is not None else None)
    path, relative = _source_path(repository, manuscript)
    if record.anchor.source_path != relative:
        raise ResearchError("The association belongs to a different manuscript path")
    try:
        text, source_sha256 = FileUtils.read_source_snapshot(str(path))
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source is missing or unreadable") from exc
    if source_sha256 != expected_source_sha256:
        raise ResearchConflictError(
            "Manuscript source bytes changed; review the current text before saving"
        )
    paragraphs = _paragraphs(text, repository, language, project_config)
    if new_quote is not None:
        if not isinstance(new_quote, str) or not new_quote.strip():
            raise ResearchError("Provide a nonempty replacement quote to re-pin")
        if line is not None and (type(line) is not int or line < 1):
            raise ResearchError("Line must be a positive integer")
        scoped = (
            [p for p in paragraphs if p.start_line <= line <= p.end_line]
            if line is not None
            else paragraphs
        )
        occurrences = _quote_occurrences(scoped, new_quote)
        if len(occurrences) == 0:
            raise ResearchError("Replacement quote was not found in the displayed paragraphs")
        if len(occurrences) > 1:
            raise ResearchError("Replacement quote is ambiguous; add --line to choose one")
        quote_to_pin = new_quote
    else:
        occurrences = _quote_occurrences(paragraphs, record.anchor.quote)
        if len(occurrences) != 1:
            raise ResearchError(
                "Only a uniquely resolvable anchor can be re-pinned; review the manuscript first"
            )
        quote_to_pin = record.anchor.quote
    target, start = occurrences[0]
    end = start + len(quote_to_pin)
    identity = paragraph_identity(target)
    unchanged_identity = identity["paragraph_sha256"] == record.anchor.paragraph_sha256
    quote_changed = quote_to_pin != record.anchor.quote
    anchor_unchanged = (
        not quote_changed
        and unchanged_identity
        and target.start_line == record.anchor.start_line
        and target.end_line == record.anchor.end_line
        and start == record.anchor.start
        and end == record.anchor.end
    )
    if anchor_unchanged and claim is None:
        raise ResearchError("The anchor still resolves at its recorded lines; nothing to re-pin")
    change_kind: Literal["correction", "supersession"] = (
        "supersession" if quote_changed else "correction"
    )
    default_reason = "Accept current claim revision" if anchor_unchanged else (
        "Update quote to the revised manuscript text"
        if quote_changed
        else (
            "Re-anchor to the uniquely moved paragraph"
            if unchanged_identity
            else "Re-anchor to the adjusted paragraph (quote unchanged)"
        )
    )
    revision_reason = (
        reason.strip() if isinstance(reason, str) and reason.strip() else default_reason
    )
    try:
        updated_anchor = ManuscriptAnchor.model_validate(
            {
                **record.anchor.model_dump(),
                "source_path": relative,
                "source_sha256": source_sha256,
                "start_line": target.start_line,
                "end_line": target.end_line,
                "paragraph_sha256": identity["paragraph_sha256"],
                "start": start,
                "end": end,
                "quote": quote_to_pin,
            }
        )
    except ValidationError:
        raise ResearchError("Invalid replacement quote or anchor bounds") from None
    revised = record.model_copy(
        update={
            "revision": record.revision + 1,
            "created_by": actor,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "change": RevisionChange(
                change_kind=change_kind,
                reason=revision_reason,
                previous_revision=record.revision,
            ),
            "anchor": updated_anchor,
            "claim_ref": Reference(id=claim.id, revision=claim.revision) if claim else record.claim_ref,
        }
    )
    # Recheck bytes immediately before publication; this never writes the manuscript.
    if FileUtils.read_source_snapshot(str(path))[1] != source_sha256:
        raise ResearchConflictError("Manuscript source bytes changed before saving")
    accepted = repository.commit([revised], {}, snapshot)
    return {
        "schema_version": "research-manuscript-link-local/1",
        "project_id": snapshot.project.id,
        "snapshot": accepted.digest,
        "archive_schema_version": accepted.manifest.schema_version,
        "link_id": record.id,
        "claim_id": record.claim_ref.id,
        "claim_revision": revised.claim_ref.revision,
        "record": revised.model_dump(mode="json"),
    }


def retract_manuscript_link(
    project: str | Path,
    manuscript: str | Path,
    link_id: str,
    *,
    expected_project_id: str,
    expected_snapshot: str,
    expected_revision: int,
    reason: str = "Withdrawn by user",
    actor: str = "local-author",
) -> dict[str, Any]:
    """Retract one manuscript association; the earlier revision stays in history."""
    reason = reason.strip() if isinstance(reason, str) else "Withdrawn by user"
    if not (1 <= len(reason) <= 500):
        raise ResearchError("Withdrawal reason must be between 1 and 500 characters")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id != snapshot.project.id:
        raise ResearchConflictError("Research project changed; reopen the intended project")
    if expected_snapshot != snapshot.digest:
        raise ResearchConflictError("Research snapshot changed; reload before saving")
    try:
        record = snapshot.latest(Reference(id=link_id).id, ManuscriptClaimLink)
    except ValidationError:
        raise ResearchError("Invalid manuscript link identifier") from None
    if record.state != "active":
        raise ResearchError("Association has already been retracted")
    if type(expected_revision) is not int or record.revision != expected_revision:
        raise ResearchConflictError("Manuscript link revision changed; review it before retracting")
    _path, relative = _source_path(repository, manuscript)
    if record.anchor.source_path != relative:
        raise ResearchError("The association belongs to a different manuscript path")
    revised = record.model_copy(
        update={
            "revision": record.revision + 1,
            "created_by": actor,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "state": "retracted",
            "change": RevisionChange(
                change_kind="supersession",
                reason=reason,
                previous_revision=record.revision,
            ),
        }
    )
    accepted = repository.commit([revised], {}, snapshot)
    return {
        "schema_version": "research-manuscript-link-local/1",
        "project_id": snapshot.project.id,
        "snapshot": accepted.digest,
        "archive_schema_version": accepted.manifest.schema_version,
        "link_id": record.id,
        "claim_id": record.claim_ref.id,
        "revision": revised.revision,
        "record": revised.model_dump(mode="json"),
    }


def _reviewed_claim_revision(snapshot: Snapshot, record: ManuscriptClaimLink, revision: int) -> Claim:
    """Require the reviewed, current claim revision to advance the saved pin."""
    try:
        Reference(id=record.claim_ref.id, revision=revision)
    except ValidationError:
        raise ResearchError("Invalid claim identifier or revision") from None
    claim = snapshot.latest(record.claim_ref.id, Claim)
    if claim.revision != revision:
        raise ResearchConflictError("Claim revision changed; review its current version before saving")
    if revision <= record.claim_ref.revision:
        raise ResearchError("The association already pins this claim revision")
    if any(
        isinstance(r, Tombstone) and r.target_kind == "claim" and r.target_ref.id == claim.id
        for r in snapshot.records.values()
    ):
        raise ResearchError("Claim has been withdrawn")
    return claim


def reanchor_manuscript_claim_revision(
    project: str | Path,
    manuscript: str | Path,
    link_id: str,
    *,
    expected_project_id: str,
    expected_snapshot: str,
    expected_revision: int,
    expected_source_sha256: str,
    new_claim_revision: int,
    actor: str = "local-author",
    reason: str | None = None,
) -> dict[str, Any]:
    """Re-pin one association to a newer claim revision (anchor unchanged).

    Used when a claim advanced and the manuscript link still points at the
    earlier revision. The quote, paragraph identity and offsets are preserved;
    only the pinned claim revision changes. Returns a new link revision.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id != snapshot.project.id:
        raise ResearchConflictError("Research project changed; reopen the intended project")
    if expected_snapshot != snapshot.digest:
        raise ResearchConflictError("Research snapshot changed; reload before saving")
    try:
        record = snapshot.latest(Reference(id=link_id).id, ManuscriptClaimLink)
    except ValidationError:
        raise ResearchError("Invalid manuscript link identifier") from None
    if record.state != "active":
        raise ResearchError("Retracted associations cannot be re-pinned")
    if type(expected_revision) is not int or record.revision != expected_revision:
        raise ResearchConflictError("Manuscript link revision changed; review it before re-pinning")
    path, relative = _source_path(repository, manuscript)
    if record.anchor.source_path != relative:
        raise ResearchError("The association belongs to a different manuscript path")
    try:
        _text, source_sha256 = FileUtils.read_source_snapshot(str(path))
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source is missing or unreadable") from exc
    if source_sha256 != expected_source_sha256:
        raise ResearchConflictError(
            "Manuscript source bytes changed; review the current text before saving"
        )
    claim = _reviewed_claim_revision(snapshot, record, new_claim_revision)
    revision_reason = (
        reason.strip() if isinstance(reason, str) and reason.strip() else "Accept current claim revision"
    )
    revised = record.model_copy(
        update={
            "revision": record.revision + 1,
            "created_by": actor,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "claim_ref": Reference(id=claim.id, revision=claim.revision),
            "change": RevisionChange(
                change_kind="correction",
                reason=revision_reason,
                previous_revision=record.revision,
            ),
        }
    )
    if FileUtils.read_source_snapshot(str(path))[1] != source_sha256:
        raise ResearchConflictError("Manuscript source bytes changed before saving")
    accepted = repository.commit([revised], {}, snapshot)
    return {
        "schema_version": "research-manuscript-link-local/1",
        "project_id": snapshot.project.id,
        "snapshot": accepted.digest,
        "archive_schema_version": accepted.manifest.schema_version,
        "link_id": record.id,
        "claim_id": claim.id,
        "claim_revision": claim.revision,
        "revision": revised.revision,
        "record": revised.model_dump(mode="json"),
    }


def link_manuscript_claim(
    project: str | Path,
    manuscript: str | Path,
    claim_id: str,
    *,
    claim_revision: int,
    selection: Mapping[str, Any],
    expected_project_id: str,
    expected_snapshot: str,
    expected_source_sha256: str,
    allow_retention: bool = False,
    note: str | None = None,
    actor: str = "local-author",
    language: str | None = None,
    project_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Retain one explicitly reviewed quote, guarded by exact source and archive identity."""
    if allow_retention is not True:
        raise ResearchError(
            "Explicit allow_retention=True is required to retain the selected quote"
        )
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id != snapshot.project.id:
        raise ResearchConflictError("Research project changed; reopen the intended project")
    if expected_snapshot != snapshot.digest:
        raise ResearchConflictError("Research snapshot changed; reload before saving")
    try:
        claim = snapshot.latest(Reference(id=claim_id, revision=claim_revision).id, Claim)
    except ValidationError:
        raise ResearchError("Invalid claim identifier or revision") from None
    if claim.revision != claim_revision:
        raise ResearchConflictError(
            "Claim revision changed; review its current version before saving"
        )
    if any(
        isinstance(r, Tombstone) and r.target_kind == "claim" and r.target_ref.id == claim.id
        for r in snapshot.records.values()
    ):
        raise ResearchError("Claim has been withdrawn")
    path, relative = _source_path(repository, manuscript)
    try:
        text, source_sha256 = FileUtils.read_source_snapshot(str(path))
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source is missing or unreadable") from exc
    if source_sha256 != expected_source_sha256:
        raise ResearchConflictError(
            "Manuscript source bytes changed; review the current text before saving"
        )
    required = {"start_line", "end_line", "paragraph_sha256", "start", "end", "quote"}
    if not isinstance(selection, Mapping) or set(selection) != required:
        raise ResearchError(
            "Selection requires exact paragraph identity and Unicode codepoint offsets"
        )
    try:
        anchor = ManuscriptAnchor.model_validate(
            {
                **selection,
                "source_path": relative,
                "source_sha256": source_sha256,
                "retention_confirmed": True,
            }
        )
    except ValidationError:
        raise ResearchError("Invalid manuscript selection fields or quote bounds") from None
    identity = {k: selection[k] for k in ("start_line", "end_line", "paragraph_sha256")}
    matches = [
        p
        for p in _paragraphs(text, repository, language, project_config)
        if paragraph_identity(p) == identity
    ]
    if len(matches) != 1 or matches[0].text[anchor.start : anchor.end] != anchor.quote:
        raise ResearchError(
            "Selection does not match one current displayed manuscript paragraph; "
            "offsets and quotes refer to the displayed text with inline Markdown markers removed"
        )
    from .api import envelope

    try:
        record = ManuscriptClaimLink.model_validate(
            {
                **envelope(snapshot.project.id, actor),
                "claim_ref": {"id": claim.id, "revision": claim.revision},
                "anchor": anchor.model_dump(),
                "note": note,
            }
        )
    except ValidationError:
        raise ResearchError("Invalid manuscript link note or actor") from None
    # Recheck bytes immediately before publication; this operation never writes the manuscript.
    try:
        _source_path(repository, manuscript)
        if FileUtils.read_source_snapshot(str(path))[1] != source_sha256:
            raise ResearchConflictError("Manuscript source bytes changed before saving")
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source became unavailable before saving") from exc
    accepted = repository.commit([record], {}, snapshot)
    return {
        "schema_version": "research-manuscript-link-local/1",
        "project_id": snapshot.project.id,
        "snapshot": accepted.digest,
        "archive_schema_version": accepted.manifest.schema_version,
        "link_id": record.id,
        "claim_id": claim.id,
        "claim_revision": claim.revision,
        "record": record.model_dump(mode="json"),
    }
