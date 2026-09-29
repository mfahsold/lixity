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
    "decision": {"title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot", "dossier_ids"},
}


def _record(snapshot: Snapshot, kind: str, identifier: str, revision: int | None = None) -> Authored:
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
    if any(isinstance(r, Tombstone) and r.target_ref.id == identifier for r in snapshot.records.values()):
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
    return {
        "schema_version": "research-record-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "record": record.model_dump(mode="json"),
        "latest_revision": latest.revision, "is_latest": latest.revision == record.revision,
        "citations": citations, "citation_scope": citation_scope,
        "source_updates": source_updates(citations), "reference_updates": reference_updates,
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
    return {
        "schema_version": "research-history-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "record_id": record_id, "kind": kind,
        "latest_revision": latest.revision,
        "revisions": [{"revision": r.revision, "created_at": r.created_at,
                       "created_by": r.created_by, "change": r.model_dump(mode="json").get("change")}
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
    values = previous.model_dump(mode="json")
    direct = {k: v for k, v in changes.items() if k not in
              {"evidence_ids", "dossier_id", "claim_id", "claim_revision", "dossier_revision", "passage_id", "time_period", "place", "actors", "dossier_ids"}}
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
        if isinstance(previous, Decision) and "dossier_ids" in changes:
            ids = changes["dossier_ids"]
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                raise ResearchError("Dossier IDs must be a list of dossier identifiers")
            values["dossier_refs"] = [_association(snapshot, i, Dossier, None, None) for i in dict.fromkeys(ids) if i]
        if isinstance(previous, EvidenceLink) and "passage_id" in changes:
            values["passage_ref"] = Reference(id=changes["passage_id"]).model_dump()
        values.update(schema_version="research-local/2", revision=previous.revision + 1,
                      created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                      created_by=actor,
                      change={"change_kind": change_kind, "reason": reason.strip(), "previous_revision": previous.revision})
        revised = KINDS[kind].model_validate(values)
    except ValidationError:
        raise ResearchError("Invalid revision fields; check required text, types and size limits") from None
    accepted = repository.commit([revised], {}, snapshot)
    return _view(repository, accepted, revised)
