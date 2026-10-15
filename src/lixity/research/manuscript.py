"""Manual manuscript associations and read-only review of exact displayed anchors."""

import warnings
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..config import _load_toml
from ..io import FileUtils
from ..pipeline import paragraph_identity, profile_document, resolve_document_config
from ..style_fingerprint import FingerprintThresholds
from ..style_profile import ParagraphProfile
from .models import Claim, ManuscriptAnchor, ManuscriptClaimLink, Reference, Tombstone
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


def _paragraphs(text: str, repository: Repository, language: str | None,
                project_config: Mapping[str, Any] | None) -> list[ParagraphProfile]:
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
        config, _ = resolve_document_config(text, language or settings.get("language", "en"),
                                            project_config=settings)
        return profile_document(text, config, FingerprintThresholds())[0]
    except (ValueError, Warning) as exc:
        raise ResearchError("Could not resolve explicit manuscript analysis settings") from exc


def manuscript_link_view(snapshot: Snapshot, record: ManuscriptClaimLink) -> dict[str, Any]:
    """Resolve the pinned claim, preserving the earlier dossier association."""
    claim = snapshot.get(record.claim_ref, Claim)
    current = snapshot.latest(claim.id, Claim)
    changed = current.revision != claim.revision
    withdrawn = any(isinstance(r, Tombstone) and r.target_kind == "claim"
                    and r.target_ref.id == claim.id for r in snapshot.records.values())
    return {"link_id": record.id, "revision": record.revision, "state": record.state,
            "claim_id": claim.id, "claim_revision": claim.revision,
            "claim_current_revision": current.revision, "claim_title": claim.title,
            "claim_changed": changed, "claim_withdrawn": withdrawn,
            "dossier_id": claim.dossier_ref.id if claim.dossier_ref else None,
            "dossier_revision": claim.dossier_ref.revision if claim.dossier_ref else None,
            "anchor": record.anchor.model_dump(mode="json"),
            "review_needed": changed or withdrawn, "note": record.note}


def list_manuscript_links(project: str | Path, *, claim_id: str | None = None,
                          include_retracted: bool = False) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    if claim_id is not None:
        try:
            snapshot.latest(Reference(id=claim_id).id, Claim)
        except ValidationError:
            raise ResearchError("Invalid claim identifier") from None
    links = [manuscript_link_view(snapshot, record) for record in snapshot.records.values()
             if isinstance(record, ManuscriptClaimLink)
             and (include_retracted or record.state == "active")
             and (claim_id is None or record.claim_ref.id == claim_id)]
    return {"schema_version": "research-manuscript-links-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "archive_schema_version": snapshot.manifest.schema_version,
            "links": links}


def manuscript_review_data(snapshot: Snapshot, *, source_path: str, source_sha256: str | None,
                           paragraphs: Sequence[ParagraphProfile],
                           source_state: str = "available") -> dict[str, Any]:
    """Derive review flags only; candidates never replace or resolve moved anchors."""
    identities = [(paragraph, paragraph_identity(paragraph)) for paragraph in paragraphs]
    rows = []
    for record in snapshot.records.values():
        if (not isinstance(record, ManuscriptClaimLink) or record.state != "active"
                or record.anchor.source_path != source_path):
            continue
        row = manuscript_link_view(snapshot, record)
        flags = [flag for flag in ("claim_changed", "claim_withdrawn") if row[flag]]
        anchor = record.anchor
        resolved: ParagraphProfile | None = None
        candidates: list[ParagraphProfile] = []
        if source_state != "available":
            flags.append("source_" + source_state)
            state = "unavailable"
        else:
            if source_sha256 != anchor.source_sha256:
                flags.append("source_changed")
            candidates = [p for p, identity in identities
                          if identity["paragraph_sha256"] == anchor.paragraph_sha256
                          and p.text[anchor.start:anchor.end] == anchor.quote]
            exact = [p for p in candidates
                     if p.start_line == anchor.start_line and p.end_line == anchor.end_line]
            if len(exact) == 1:
                resolved, state = exact[0], "resolved"
            elif len(candidates) > 1:
                state = "ambiguous"
                flags.append("anchor_ambiguous")
            elif candidates:
                state = "moved"
                flags.append("anchor_moved")
            else:
                state = "changed"
                flags.append("anchor_changed")
        # The file-level digest is informational: an edit elsewhere must not
        # re-open associations whose paragraph, line span and quote still match.
        review_blocking = [flag for flag in flags if flag != "source_changed"]
        row.update(source_path=source_path, current_source_sha256=source_sha256, flags=flags,
                   anchor_state=state, review_needed=bool(review_blocking),
                   resolved_start_line=resolved.start_line if resolved else None,
                   resolved_end_line=resolved.end_line if resolved else None,
                   candidate_lines=[p.start_line for p in candidates])
        rows.append(row)
    return {"schema_version": "research-manuscript-review-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "archive_schema_version": snapshot.manifest.schema_version,
            "source_path": source_path, "source_state": source_state,
            "current_source_sha256": source_sha256, "links": rows,
            "review_needed_count": sum(row["review_needed"] for row in rows)}


def review_manuscript_links(project: str | Path, manuscript: str | Path, *,
                            expected_project_id: str | None = None, language: str | None = None,
                            project_config: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    return manuscript_review_data(snapshot, source_path=relative, source_sha256=source_sha256,
                                  paragraphs=paragraphs, source_state=state)


def link_manuscript_claim(
    project: str | Path, manuscript: str | Path, claim_id: str, *, claim_revision: int,
    selection: Mapping[str, Any], expected_project_id: str, expected_snapshot: str,
    expected_source_sha256: str, allow_retention: bool = False, note: str | None = None,
    actor: str = "local-author", language: str | None = None,
    project_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Retain one explicitly reviewed quote, guarded by exact source and archive identity."""
    if allow_retention is not True:
        raise ResearchError("Explicit allow_retention=True is required to retain the selected quote")
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
        raise ResearchConflictError("Claim revision changed; review its current version before saving")
    if any(isinstance(r, Tombstone) and r.target_kind == "claim" and r.target_ref.id == claim.id
           for r in snapshot.records.values()):
        raise ResearchError("Claim has been withdrawn")
    path, relative = _source_path(repository, manuscript)
    try:
        text, source_sha256 = FileUtils.read_source_snapshot(str(path))
    except (OSError, UnicodeError) as exc:
        raise ResearchError("Manuscript source is missing or unreadable") from exc
    if source_sha256 != expected_source_sha256:
        raise ResearchConflictError("Manuscript source bytes changed; review the current text before saving")
    required = {"start_line", "end_line", "paragraph_sha256", "start", "end", "quote"}
    if not isinstance(selection, Mapping) or set(selection) != required:
        raise ResearchError("Selection requires exact paragraph identity and Unicode codepoint offsets")
    try:
        anchor = ManuscriptAnchor.model_validate({**selection, "source_path": relative,
                                                 "source_sha256": source_sha256,
                                                 "retention_confirmed": True})
    except ValidationError:
        raise ResearchError("Invalid manuscript selection fields or quote bounds") from None
    identity = {k: selection[k] for k in ("start_line", "end_line", "paragraph_sha256")}
    matches = [p for p in _paragraphs(text, repository, language, project_config)
               if paragraph_identity(p) == identity]
    if len(matches) != 1 or matches[0].text[anchor.start:anchor.end] != anchor.quote:
        raise ResearchError(
            "Selection does not match one current displayed manuscript paragraph; "
            "offsets and quotes refer to the displayed text with inline Markdown markers removed")
    from .api import envelope
    try:
        record = ManuscriptClaimLink.model_validate({**envelope(snapshot.project.id, actor),
                                                    "claim_ref": {"id": claim.id, "revision": claim.revision},
                                                    "anchor": anchor.model_dump(), "note": note})
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
    return {"schema_version": "research-manuscript-link-local/1", "project_id": snapshot.project.id,
            "snapshot": accepted.digest, "archive_schema_version": accepted.manifest.schema_version,
            "link_id": record.id, "claim_id": claim.id, "claim_revision": claim.revision,
            "record": record.model_dump(mode="json")}
