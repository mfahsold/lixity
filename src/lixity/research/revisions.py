"""Explicit edits and history for the existing authored research records."""

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import (
    Claim,
    ClaimScope,
    Decision,
    Dossier,
    EvidenceLink,
    Passage,
    Reference,
    SourceVersion,
    Tombstone,
    reference,
)
from .repository import Repository, ResearchConflictError, ResearchError, Snapshot

Authored = Dossier | Claim | EvidenceLink | Decision
KINDS: dict[str, type[Authored]] = {
    "dossier": Dossier, "claim": Claim, "evidence_link": EvidenceLink, "decision": Decision,
}
FIELDS = {
    "dossier": {"title", "body", "language", "tags", "evidence_ids"},
    "claim": {"title", "statement", "confidence", "time_period", "place", "actors", "dossier_id", "dossier_revision", "tags"},
    "evidence_link": {"claim_id", "claim_revision", "passage_id", "relation", "rationale", "reviewer"},
    "decision": {"title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot", "dossier_ids", "dossier_revisions"},
}


def _record(snapshot: Snapshot, kind: str, identifier: str, revision: int | None = None, *,
            unavailable: set[str] | None = None) -> Authored:
    if not isinstance(kind, str) or kind not in KINDS:
        raise ResearchError("Only dossiers, claims, evidence links and decisions can be revised")
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ResearchError("Revision must be a positive integer")
    try:
        Reference(id=identifier)
        record = (snapshot.latest(identifier, KINDS[kind]) if revision is None else
                  snapshot.get(Reference(id=identifier, revision=revision), KINDS[kind]))
    except ValidationError:
        raise ResearchError("Invalid record identifier") from None
    if unavailable is None:
        unavailable = {r.target_ref.id for r in snapshot.records.values() if isinstance(r, Tombstone)}
    if identifier in unavailable:
        raise ResearchError("Record has been withdrawn or purged")
    return record


def resolve_evidence_citation(repository: Repository, snapshot: Snapshot, ref: Reference) -> dict[str, Any]:
    """Keep unavailable evidence explicit without exposing unverified quotes."""
    try:
        citation = repository.citation(snapshot, snapshot.get(ref, Passage))
    except ResearchError:
        purged = any(isinstance(r, Tombstone) and r.operation == "purge" and
                     r.target_kind == "passage" and r.target_ref == ref for r in snapshot.records.values())
        result: dict[str, Any] = {"id": ref.id, "passage_id": ref.id, "error": "Citation unavailable or missing"}
        if purged:
            result["availability"] = "purged"
        return result
    unavailable = {r.target_ref.id for r in snapshot.records.values() if isinstance(r, Tombstone)}
    versions = [r for r in snapshot.records.values() if isinstance(r, SourceVersion)
                and r.source_ref.id == citation["source_id"] and r.id not in unavailable]
    cited = snapshot.get(Reference(id=citation["source_version_id"]), SourceVersion)
    latest = max(versions, key=lambda r: r.sequence) if versions and citation["source_id"] not in unavailable else cited
    citation.update(source_sequence=cited.sequence, latest_source_version_id=latest.id,
                    latest_source_sequence=latest.sequence, newer_source_available=latest.sequence > cited.sequence)
    return citation


def source_updates(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updates: dict[tuple[str, str], dict[str, Any]] = {}
    for citation in citations:
        if citation.get("newer_source_available"):
            key = (citation["source_id"], citation["source_version_id"])
            updates[key] = {
                "source_id": citation["source_id"], "source_title": citation["source_title"],
                "cited_version_id": citation["source_version_id"],
                "latest_version_id": citation["latest_source_version_id"],
                "cited_sequence": citation["source_sequence"], "latest_sequence": citation["latest_source_sequence"],
            }
    return list(updates.values())


def _view(repository: Repository, snapshot: Snapshot, record: Authored) -> dict[str, Any]:
    refs: list[Reference] = []
    links: list[EvidenceLink] = []
    association: Reference | None = None
    association_kind = "claim"
    citation_scope = "pinned_passages"
    if isinstance(record, Dossier):
        refs = record.evidence_refs
    elif isinstance(record, EvidenceLink):
        links = [record]
        association = record.claim_ref
    else:
        claim_ref = reference(record) if isinstance(record, Claim) else record.claim_ref
        association = record.dossier_ref if isinstance(record, Claim) else record.claim_ref
        association_kind = "dossier" if isinstance(record, Claim) else "claim"
        citation_scope = "current_links_to_pinned_claim_revision"
        if claim_ref:
            # A current evidence relation is still explicit about which claim
            # revision it refers to; do not silently move it to a revised claim.
            links = [r for r in snapshot.records.values()
                     if isinstance(r, EvidenceLink) and r.claim_ref == claim_ref]
    citations = [resolve_evidence_citation(repository, snapshot, ref) for ref in dict.fromkeys(refs)]
    for link in links:
        citation = resolve_evidence_citation(repository, snapshot, link.passage_ref)
        citation.update(evidence_link_id=link.id, evidence_link_revision=link.revision,
                        claim_revision=link.claim_ref.revision)
        citations.append(citation)
    reference_updates = []
    if association:
        target = snapshot.latest(association.id, KINDS[association_kind])
        if target.revision > association.revision:
            reference_updates.append({"kind": association_kind, "id": association.id,
                                      "pinned_revision": association.revision, "latest_revision": target.revision})
    latest = snapshot.latest(record.id, KINDS[record.kind])
    from .images import resolve_dossier_images
    return {
        "schema_version": "research-record-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "record": record.model_dump(mode="json"),
        "latest_revision": latest.revision, "is_latest": latest.revision == record.revision,
        "citations": citations, "citation_scope": citation_scope,
        "source_updates": source_updates(citations), "reference_updates": reference_updates,
        **({"images": resolve_dossier_images(snapshot, record.body)} if isinstance(record, Dossier) else {}),
    }


def get_record(project: str | Path, kind: str, record_id: str, *, revision: int | None = None) -> dict[str, Any]:
    """Read the current record or an explicitly pinned historical revision."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    return _view(repository, snapshot, _record(snapshot, kind, record_id, revision))


def record_history(project: str | Path, kind: str, record_id: str) -> dict[str, Any]:
    """List accepted revisions, newest first, without copying their bodies."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    latest = _record(snapshot, kind, record_id)
    records = sorted((r for r in snapshot.revisions.values() if r.id == record_id),
                     key=lambda r: r.revision, reverse=True)
    from .images import resolve_dossier_images
    return {
        "schema_version": "research-history-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "record_id": record_id, "kind": kind,
        "latest_revision": latest.revision,
        "revisions": [{"revision": r.revision, "created_at": r.created_at,
                       "created_by": r.created_by, "change": r.model_dump(mode="json").get("change"),
                       **({"images": resolve_dossier_images(snapshot, r.body)} if isinstance(r, Dossier) else {})}
                      for r in records],
    }


def _association(snapshot: Snapshot, identifier: Any, expected: type[Authored],
                 existing: Reference | None, revision: Any = None) -> dict[str, Any] | None:
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ResearchError("Associated revision must be a positive integer")
    if identifier is None or identifier == "":
        if revision is not None:
            raise ResearchError("An associated revision requires a record ID")
        return None
    if not isinstance(identifier, str):
        raise ResearchError("Associated record ID must be a string or null")
    # Submitting an unchanged form must not repin its historical association.
    if revision is not None:
        return reference(snapshot.get(Reference(id=identifier, revision=revision), expected)).model_dump()
    if existing and existing.id == identifier:
        return existing.model_dump()
    return reference(snapshot.latest(identifier, expected)).model_dump()


def revise_record(
    project: str | Path, kind: str, record_id: str, *, changes: Mapping[str, Any],
    expected_snapshot: str, expected_revision: int, change_kind: str, reason: str,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Append one explicit authored revision; a stale draft never overwrites work."""
    if not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
        raise ResearchError("Expected snapshot must be a SHA-256 digest")
    if type(expected_revision) is not int or expected_revision < 1:
        raise ResearchError("Expected revision must be a positive integer")
    if not isinstance(changes, Mapping) or not changes:
        raise ResearchError("Provide at least one editable field")
    if change_kind not in ("correction", "supersession"):
        raise ResearchError("Choose correction or supersession explicitly")
    if not isinstance(reason, str) or not reason.strip():
        raise ResearchError("A revision reason is required")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; reload the current record before saving")
    previous = _record(snapshot, kind, record_id)
    if previous.revision != expected_revision:
        raise ResearchConflictError("Record revision changed; reload the current record before saving")
    if set(changes) - FIELDS[kind]:
        raise ResearchError("The change contains unknown or immutable fields")
    revised = _apply_changes(snapshot, previous, changes, change_kind=change_kind, reason=reason, actor=actor)
    accepted = repository.commit([revised], {}, snapshot)
    return _view(repository, accepted, revised)


def _apply_changes(
    snapshot: Snapshot, previous: Authored, changes: Mapping[str, Any], *,
    change_kind: str, reason: str, actor: str,
) -> Authored:
    """Build a validated record without publishing it."""
    kind = previous.kind
    if set(changes) - FIELDS[kind]:
        raise ResearchError("The change contains unknown or immutable fields")
    values = previous.model_dump(mode="json")
    direct = {k: v for k, v in changes.items() if k not in
              {"evidence_ids", "dossier_id", "claim_id", "claim_revision", "dossier_revision", "passage_id", "time_period", "place", "actors", "dossier_ids", "dossier_revisions"}}
    for name in ("title", "statement", "rationale", "reviewer", "impact_on_plot"):
        if isinstance(direct.get(name), str):
            direct[name] = direct[name].strip()
            if not direct[name] and (name == "impact_on_plot" or
                                     (name == "rationale" and isinstance(previous, EvidenceLink))):
                direct[name] = None
    values.update(direct)
    try:
        if isinstance(previous, Dossier) and "evidence_ids" in changes:
            ids = changes["evidence_ids"]
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                raise ResearchError("Evidence IDs must be a list of passage identifiers")
            values["evidence_refs"] = [Reference(id=i).model_dump() for i in dict.fromkeys(ids)]
        if isinstance(previous, Claim):
            scope = previous.scope.model_dump()
            scope.update({k: changes[k] for k in ("time_period", "place", "actors") if k in changes})
            for name in ("time_period", "place"):
                if isinstance(scope[name], str):
                    scope[name] = scope[name].strip() or None
            values["scope"] = ClaimScope.model_validate(scope).model_dump()
            if "dossier_id" in changes or "dossier_revision" in changes:
                identifier = changes.get("dossier_id", previous.dossier_ref.id if previous.dossier_ref else None)
                values["dossier_ref"] = _association(snapshot, identifier, Dossier, previous.dossier_ref, changes.get("dossier_revision"))
        if isinstance(previous, (EvidenceLink, Decision)) and ("claim_id" in changes or "claim_revision" in changes):
            identifier = changes.get("claim_id", previous.claim_ref.id if previous.claim_ref else None)
            values["claim_ref"] = _association(snapshot, identifier, Claim, previous.claim_ref, changes.get("claim_revision"))
        if isinstance(previous, Decision) and ("dossier_ids" in changes or "dossier_revisions" in changes):
            ids = changes.get("dossier_ids", [ref.id for ref in previous.dossier_refs])
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                raise ResearchError("Dossier IDs must be a list of dossier identifiers")
            pins = changes.get("dossier_revisions", {})
            if (not isinstance(pins, Mapping) or set(pins) - set(ids)
                    or any(type(pin) is not int or pin < 1 for pin in pins.values())):
                raise ResearchError("Dossier revisions must map selected dossier IDs to positive existing revisions")
            retained = {ref.id: ref for ref in previous.dossier_refs}
            values["dossier_refs"] = [_association(snapshot, i, Dossier, retained.get(i), pins.get(i)) for i in dict.fromkeys(ids) if i]
        if isinstance(previous, EvidenceLink) and "passage_id" in changes:
            values["passage_ref"] = Reference(id=changes["passage_id"]).model_dump()
        values.update(schema_version="research-local/2", revision=previous.revision + 1,
                      created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                      created_by=actor,
                      change={"change_kind": change_kind, "reason": reason.strip(), "previous_revision": previous.revision})
        revised = KINDS[kind].model_validate(values)
    except ValidationError:
        raise ResearchError("Invalid revision fields; check required text, types and size limits") from None
    return revised


def _editable_values(record: Authored) -> dict[str, Any]:
    """Flatten editable fields, keeping an association and its revision together."""
    values: dict[str, Any] = {}
    for name in sorted(FIELDS[record.kind]):
        if name in ("claim_revision", "dossier_revision", "dossier_revisions"):
            continue
        if name in ("claim_id", "dossier_id"):
            ref = getattr(record, name.replace("_id", "_ref"))
            values[name] = ref.model_dump() if ref else None
        elif name == "evidence_ids" and isinstance(record, Dossier):
            values[name] = [ref.id for ref in record.evidence_refs]
        elif name == "dossier_ids" and isinstance(record, Decision):
            values[name] = [ref.model_dump() for ref in record.dossier_refs]
        elif name == "passage_id" and isinstance(record, EvidenceLink):
            values[name] = record.passage_ref.id
        elif name in ("time_period", "place", "actors") and isinstance(record, Claim):
            values[name] = getattr(record.scope, name)
        else:
            values[name] = getattr(record, name)
    return values


def _field_change(name: str, value: Any) -> dict[str, Any]:
    if name == "dossier_ids":
        return {name: [ref["id"] for ref in value], "dossier_revisions": {ref["id"]: ref["revision"] for ref in value}}
    if name in ("claim_id", "dossier_id"):
        if value is None:
            return {name: None}
        return {name: value["id"], name.replace("_id", "_revision"): value["revision"]}
    return {name: value}


def _validate_revision_links(snapshot: Snapshot, previous: Authored, revised: Authored) -> None:
    """Check new links using the same constraints as the append-only commit."""
    if isinstance(revised, Dossier):
        from .images import validate_image_changes
        validate_image_changes(snapshot, revised.body, previous.body if isinstance(previous, Dossier) else "")
        retained = previous.evidence_refs if isinstance(previous, Dossier) else []
        for ref in revised.evidence_refs:
            if ref not in retained:
                snapshot.get(ref, Passage)
    elif isinstance(revised, Claim) and revised.dossier_ref:
        snapshot.get(revised.dossier_ref, Dossier)
    elif isinstance(revised, (EvidenceLink, Decision)):
        if revised.claim_ref:
            snapshot.get(revised.claim_ref, Claim)
        if isinstance(revised, EvidenceLink) and (
            not isinstance(previous, EvidenceLink) or revised.passage_ref != previous.passage_ref
        ):
            snapshot.get(revised.passage_ref, Passage)


def prepare_record_revision(
    project: str | Path, kind: str, record_id: str, *, base_revision: int,
    changes: Mapping[str, Any], resolutions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Prepare a read-only three-way reconciliation; never save or choose a conflict.

    The archive supplies both the base and current values. ``resolutions`` must
    explicitly choose ``current`` or ``mine`` for a conflicting editable field.
    Associations and their pinned revisions are one field. Save the returned
    changes through ``revise_record`` with the returned current tokens; it will
    still reject another concurrent change.
    """
    if type(base_revision) is not int or base_revision < 1:
        raise ResearchError("Base revision must be a positive integer")
    if not isinstance(changes, Mapping) or not changes:
        raise ResearchError("Provide at least one editable field")
    if resolutions is None:
        resolutions = {}
    if not isinstance(resolutions, Mapping) or any(value not in ("current", "mine") for value in resolutions.values()):
        raise ResearchError("Choose current or mine for each conflicting field")
    repository = Repository(project)
    snapshot = repository.snapshot()
    current = _record(snapshot, kind, record_id)
    base = _record(snapshot, kind, record_id, base_revision)
    draft = _apply_changes(snapshot, base, changes, change_kind="correction", reason="Preview only", actor="local-author")
    _validate_revision_links(snapshot, base, draft)
    before, now, mine = (_editable_values(record) for record in (base, current, draft))
    conflicts = []
    merged: dict[str, Any] = {}
    conflicting_fields = set()
    for name in before:
        if mine[name] == before[name]:
            continue
        desired = mine[name]
        if now[name] != before[name] and now[name] != mine[name]:
            conflicting_fields.add(name)
            if name not in resolutions:
                conflicts.append({"field": name, "base": before[name], "current": now[name], "mine": mine[name]})
                continue
            desired = now[name] if resolutions[name] == "current" else mine[name]
        if desired != now[name]:
            merged.update(_field_change(name, desired))
    if set(resolutions) - conflicting_fields:
        raise ResearchError("Resolution names must identify fields with conflicting changes")
    candidate = _apply_changes(snapshot, current, merged, change_kind="correction", reason="Preview only", actor="local-author")
    _validate_revision_links(snapshot, current, candidate)
    return {
        "schema_version": "research-revision-preview-local/1", "base_revision": base_revision,
        "current": _view(repository, snapshot, current), "changes": merged,
        "conflicts": conflicts, "ready": not conflicts, "has_changes": bool(merged),
    }


def prepare_dossier_section(
    project: str | Path, record_id: str, *, base_revision: int,
    section: str, content: str, resolutions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reconcile a selected section without replacing unrelated current prose."""
    from .api import _section_spans, _section_subtree_end, update_section

    if type(base_revision) is not int or base_revision < 1:
        raise ResearchError("Base revision must be a positive integer")
    if not isinstance(section, str) or not section.strip() or not isinstance(content, str):
        raise ResearchError("Provide a section heading and text content")
    if resolutions is None:
        resolutions = {}
    if not isinstance(resolutions, Mapping) or any(
        key != "body" or value not in ("current", "mine") for key, value in resolutions.items()
    ):
        raise ResearchError("Choose current or mine for the conflicting section body")
    repository = Repository(project)
    snapshot = repository.snapshot()
    base = _record(snapshot, "dossier", record_id, base_revision)
    current = _record(snapshot, "dossier", record_id)
    if not isinstance(base, Dossier) or not isinstance(current, Dossier):
        raise ResearchError("Section editing requires a dossier")

    def selected_text(body: str) -> str:
        spans = _section_spans(body)
        matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
        if not matches:
            raise ResearchError(f"Section '{section}' not found")
        if len(matches) != 1:
            raise ResearchError(f"Section '{section}' is ambiguous")
        selected = matches[0]
        content = body[selected.content_start:_section_subtree_end(spans, selected, len(body))]
        return content.replace("\r\n", "\n").replace("\r", "\n").strip("\n")

    before, now = selected_text(base.body), selected_text(current.body)
    mine = content.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    conflicted = mine != before and now != before and now != mine
    if resolutions and not conflicted:
        raise ResearchError("A resolution requires a conflicting section body")
    conflicts = []
    changes: dict[str, Any] = {}
    if conflicted and "body" not in resolutions:
        conflicts.append({"field": "body", "base": before, "current": now, "mine": mine})
    elif mine != before:
        desired = now if resolutions.get("body") == "current" else mine
        if desired != now:
            changes["body"] = update_section(current.body, section, desired)
    candidate = _apply_changes(snapshot, current, changes, change_kind="correction",
                               reason="Preview only", actor="local-author")
    _validate_revision_links(snapshot, current, candidate)
    return {"schema_version": "research-revision-preview-local/1", "base_revision": base_revision,
            "section": section, "current": _view(repository, snapshot, current), "changes": changes,
            "conflicts": conflicts, "ready": not conflicts, "has_changes": bool(changes)}


def _revision_batch(
    snapshot: Snapshot, operations: list[Mapping[str, Any]], actor: str,
) -> tuple[list[Authored], list[dict[str, Any]]]:
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
        raise ResearchError("Provide between 1 and 100 revision operations")
    if not isinstance(actor, str) or not actor.strip():
        raise ResearchError("A revision actor is required")
    revised: list[Authored] = []
    prepared: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    for operation in operations:
        if not isinstance(operation, Mapping) or set(operation) != {
            "kind", "id", "expected_revision", "changes", "change_kind", "reason"
        }:
            raise ResearchError("Each revision operation requires kind, id, expected_revision, changes, change_kind and reason")
        kind, identifier = operation["kind"], operation["id"]
        previous = _record(snapshot, kind, identifier, unavailable=unavailable)
        if identifier in identifiers:
            raise ResearchError("A record may appear only once in a revision batch")
        identifiers.add(identifier)
        expected_revision = operation["expected_revision"]
        if type(expected_revision) is not int or expected_revision < 1:
            raise ResearchError("Expected revision must be a positive integer")
        if previous.revision != expected_revision:
            raise ResearchConflictError("Record revision changed; prepare the batch against current records")
        changes, change_kind, reason = operation["changes"], operation["change_kind"], operation["reason"]
        if not isinstance(changes, Mapping) or not changes:
            raise ResearchError("Provide at least one editable field for each revision")
        if change_kind not in ("correction", "supersession") or not isinstance(reason, str) or not reason.strip():
            raise ResearchError("Choose correction or supersession and provide a revision reason")
        candidate = _apply_changes(snapshot, previous, changes, change_kind=change_kind, reason=reason, actor=actor.strip())
        _validate_revision_links(snapshot, previous, candidate)
        revised.append(candidate)
        prepared.append({"kind": kind, "id": identifier, "expected_revision": expected_revision,
                         "changes": dict(changes), "change_kind": change_kind, "reason": reason.strip()})
    return revised, prepared


def prepare_record_revisions(
    project: str | Path, operations: list[Mapping[str, Any]], *, actor: str = "local-author",
) -> dict[str, Any]:
    """Validate a read-only batch of existing records against one current snapshot.

    Every operation supplies kind/id, expected_revision, changes, change_kind
    and reason. References must already exist; future revisions from other
    operations are not implicitly pinned. Review the returned operations and
    snapshot before explicitly calling ``apply_record_revisions``.
    """
    snapshot = Repository(project).snapshot()
    _records, prepared = _revision_batch(snapshot, operations, actor)
    return {"schema_version": "research-revision-batch-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "operations": prepared, "ready": True}


def apply_record_revisions(
    project: str | Path, operations: list[Mapping[str, Any]], *, expected_snapshot: str,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Append all reviewed revisions with one atomic HEAD publication, or none."""
    if not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
        raise ResearchError("Expected snapshot must be a SHA-256 digest")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; prepare the batch again before applying")
    records, _prepared = _revision_batch(snapshot, operations, actor)
    accepted = repository.commit(list(records), {}, snapshot)
    return {"schema_version": "research-revision-batch-local/1", "project_id": accepted.project.id,
            "snapshot": accepted.digest, "records": [
                {"kind": record.kind, "id": record.id, "revision": record.revision}
                for record in records
            ]}
