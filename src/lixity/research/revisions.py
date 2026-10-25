"""Explicit edits and history for the existing authored research records."""

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from .acknowledgements import latest_acknowledgements
from .geography import summarize_geography
from .models import (
    Claim,
    ClaimRelation,
    ClaimScope,
    Decision,
    DecisionAcknowledgement,
    Dossier,
    EvidenceLink,
    ManuscriptAnchor,
    ManuscriptClaimLink,
    Passage,
    Reference,
    SourceVersion,
    Tombstone,
    normalize_claim_relation,
    reference,
)
from .repository import Repository, ResearchConflictError, ResearchError, Snapshot, encode
from .sections import (
    _section_candidates,
    _section_spans,
    _section_subtree_end,
    update_preamble,
    update_section,
)
from .timeline import period_warnings

Authored = Dossier | Claim | ClaimRelation | EvidenceLink | ManuscriptClaimLink | Decision
BatchRecord = Authored | DecisionAcknowledgement
KINDS: dict[str, type[Authored]] = {
    "dossier": Dossier, "claim": Claim, "evidence_link": EvidenceLink, "decision": Decision,
    "claim_relation": ClaimRelation,
    "manuscript_claim_link": ManuscriptClaimLink,
}
FIELDS = {
    "dossier": {"title", "body", "language", "tags", "evidence_ids", "geography"},
    "claim": {"title", "statement", "confidence", "time_period", "place", "actors", "dossier_id", "dossier_revision", "tags"},
    "claim_relation": {"from_claim_id", "from_claim_revision", "to_claim_id", "to_claim_revision", "relation", "state", "rationale"},
    "manuscript_claim_link": {"claim_id", "claim_revision", "state", "note"},
    "evidence_link": {"claim_id", "claim_revision", "passage_id", "relation", "rationale", "reviewer"},
    "decision": {"title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot", "dossier_ids", "dossier_revisions"},
}
MANUSCRIPT_BATCH_ANCHOR_FIELDS = {
    "expected_source_sha256",
    "accept_moved",
    "new_quote",
    "quote",
    "line",
    "selection",
    "manuscript",
    "language",
}


def dossier_withdrawal(snapshot: Snapshot, identifier: str) -> dict[str, Any]:
    """Annotate explicit historical reads without making retired records active."""
    tombstones = [record for record in snapshot.records.values()
                  if isinstance(record, Tombstone) and record.target_ref.id == identifier]
    if any(record.operation == "purge" for record in tombstones):
        return {}
    withdrawn = next((record for record in tombstones if record.target_kind == "dossier"
                      and record.operation == "withdraw"), None)
    if withdrawn is None:
        return {}
    return {"availability": "withdrawn", "withdrawal": {
        "id": withdrawn.id, "target_revision": withdrawn.target_ref.revision,
        "reason": withdrawn.reason, "created_at": withdrawn.created_at, "created_by": withdrawn.created_by}}


def require_active_dossier_association(snapshot: Snapshot, selected: Reference,
                                       existing: Reference | None = None) -> None:
    """Retain old pins, but do not create or repin associations to retired notes."""
    if selected != existing and any(isinstance(record, Tombstone) and record.target_ref.id == selected.id
                                    for record in snapshot.records.values()):
        raise ResearchError("A withdrawn or purged dossier cannot receive new associations or revision pins")


def _record(snapshot: Snapshot, kind: str, identifier: str, revision: int | None = None, *,
            unavailable: set[str] | None = None, include_withdrawn: bool = False) -> Authored:
    if not isinstance(kind, str) or kind not in KINDS:
        raise ResearchError("Only dossiers, claims, claim relations, manuscript links, evidence links and decisions can be revised")
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
    if identifier in unavailable and not (include_withdrawn and kind == "dossier"
                                          and dossier_withdrawal(snapshot, identifier)):
        raise ResearchError("Record has been withdrawn or purged")
    return record


def _latest_citation_versions(snapshot: Snapshot) -> dict[str, SourceVersion]:
    """Project active version heads once within one already verified read."""
    unavailable = {r.target_ref.id for r in snapshot.records.values() if isinstance(r, Tombstone)}
    latest: dict[str, SourceVersion] = {}
    for record in snapshot.records.values():
        if (isinstance(record, SourceVersion) and record.id not in unavailable
                and record.source_ref.id not in unavailable):
            previous = latest.get(record.source_ref.id)
            if previous is None or record.sequence > previous.sequence:
                latest[record.source_ref.id] = record
    return latest


class EvidenceCitationReader:
    """Resolve a batch against one snapshot; never retained across public reads.

    Snapshot-derived lookups are shared only for this batch. Every citation verifies
    its exact passage against retained bytes through Repository.citation().
    """

    def __init__(self, repository: Repository, snapshot: Snapshot):
        self.repository = repository
        self.snapshot = snapshot
        self._versions: dict[str, SourceVersion] | None = None
        self._purged_passages: set[Reference] | None = None

    def read(self, ref: Reference) -> dict[str, Any]:
        repository, snapshot = self.repository, self.snapshot
        try:
            citation = repository.citation(snapshot, snapshot.get(ref, Passage))
        except ResearchError:
            if self._purged_passages is None:
                self._purged_passages = {r.target_ref for r in snapshot.records.values()
                                         if isinstance(r, Tombstone) and r.operation == "purge"
                                         and r.target_kind == "passage"}
            result: dict[str, Any] = {"id": ref.id, "passage_id": ref.id, "error": "Citation unavailable or missing"}
            if ref in self._purged_passages:
                result["availability"] = "purged"
            return result
        if self._versions is None:
            self._versions = _latest_citation_versions(snapshot)
        cited = snapshot.get(Reference(id=citation["source_version_id"]), SourceVersion)
        latest = self._versions.get(citation["source_id"], cited)
        citation.update(source_sequence=cited.sequence, latest_source_version_id=latest.id,
                        latest_source_sequence=latest.sequence, newer_source_available=latest.sequence > cited.sequence)
        return citation


def resolve_evidence_citation(repository: Repository, snapshot: Snapshot, ref: Reference) -> dict[str, Any]:
    """Keep unavailable evidence explicit without exposing unverified quotes."""
    return EvidenceCitationReader(repository, snapshot).read(ref)


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


def claim_relation_view(snapshot: Snapshot, record: ClaimRelation) -> dict[str, Any]:
    """Resolve recorded endpoint revisions without applying them to newer claims."""
    def endpoint(ref: Reference) -> dict[str, Any]:
        claim = snapshot.get(ref, Claim)
        current = snapshot.latest(ref.id, Claim)
        return {"claim_id": claim.id, "revision": claim.revision, "current_revision": current.revision,
                "title": claim.title, "time_period": claim.scope.time_period, "confidence": claim.confidence}

    first, second = endpoint(record.from_claim_ref), endpoint(record.to_claim_ref)
    return {"relation_id": record.id, "revision": record.revision, "relation": record.relation,
            "state": record.state, "rationale": record.rationale, "from_claim": first, "to_claim": second,
            "review_needed": any(claim["revision"] != claim["current_revision"] for claim in (first, second))}


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
    elif isinstance(record, ClaimRelation):
        citation_scope = "pinned_claim_revisions"
    elif isinstance(record, ManuscriptClaimLink):
        association = record.claim_ref
        citation_scope = "manuscript_association"
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
    reader = EvidenceCitationReader(repository, snapshot)
    citations = [reader.read(ref) for ref in dict.fromkeys(refs)]
    for link in links:
        citation = reader.read(link.passage_ref)
        citation.update(evidence_link_id=link.id, evidence_link_revision=link.revision,
                        claim_revision=link.claim_ref.revision)
        citations.append(citation)
    reference_updates = []
    if association:
        target = snapshot.latest(association.id, KINDS[association_kind])
        if target.revision > association.revision:
            reference_updates.append({"kind": association_kind, "id": association.id,
                                      "pinned_revision": association.revision, "latest_revision": target.revision})
    relation_view = claim_relation_view(snapshot, record) if isinstance(record, ClaimRelation) else None
    if relation_view:
        for role in ("from", "to"):
            endpoint = relation_view[role + "_claim"]
            if endpoint["current_revision"] > endpoint["revision"]:
                reference_updates.append({"kind": "claim", "id": endpoint["claim_id"],
                                          "pinned_revision": endpoint["revision"],
                                          "latest_revision": endpoint["current_revision"], "role": role})
    latest = snapshot.latest(record.id, KINDS[record.kind])
    from .images import resolve_dossier_images, resolve_dossier_media
    return {
        "schema_version": "research-record-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "kind": record.kind, "record_id": record.id,
        "record": record.model_dump(mode="json"),
        "latest_revision": latest.revision, "is_latest": latest.revision == record.revision,
        "citations": citations, "citation_scope": citation_scope,
        "source_updates": source_updates(citations), "reference_updates": reference_updates,
        **({"images": resolve_dossier_images(snapshot, record.body),
            "media": resolve_dossier_media(snapshot, record.body),
            "geography_summary": summarize_geography(record.geography)} if isinstance(record, Dossier) else {}),
        **(dossier_withdrawal(snapshot, record.id) if isinstance(record, Dossier) else {}),
        **({key: relation_view[key] for key in ("from_claim", "to_claim", "review_needed")} if relation_view else {}),
    }


def get_record(project: str | Path, kind: str, record_id: str, *, revision: int | None = None) -> dict[str, Any]:
    """Read the current record or an explicitly pinned historical revision."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    return _view(repository, snapshot, _record(snapshot, kind, record_id, revision,
                                              include_withdrawn=revision is not None))


def record_history(project: str | Path, kind: str, record_id: str) -> dict[str, Any]:
    """List accepted revisions, newest first, without copying their bodies."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    return _record_history(snapshot, kind, record_id)


def _record_history(snapshot: Snapshot, kind: str, record_id: str) -> dict[str, Any]:
    latest = _record(snapshot, kind, record_id, include_withdrawn=True)
    # Repository validation guarantees every accepted revision from 1 to latest.
    records = [cast(Authored, snapshot.revisions[(record_id, number)]) for number in range(latest.revision, 0, -1)]
    from .images import resolve_dossier_images, resolve_dossier_media
    return {
        "schema_version": "research-history-local/1", "project_id": snapshot.project.id,
        "snapshot": snapshot.digest, "record_id": record_id, "kind": kind,
        "latest_revision": latest.revision,
        **(dossier_withdrawal(snapshot, record_id) if isinstance(latest, Dossier) else {}),
        "revisions": [{"revision": r.revision, "created_at": r.created_at,
                       "created_by": r.created_by, "change": r.change.model_dump(mode="json") if r.change else None,
                       **({"images": resolve_dossier_images(snapshot, r.body),
                           "media": resolve_dossier_media(snapshot, r.body),
                           "geography_feature_count": len(r.geography.features) if r.geography else 0}
                          if isinstance(r, Dossier) else {})}
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
        selected = reference(snapshot.get(Reference(id=identifier, revision=revision), expected))
    elif existing and existing.id == identifier:
        selected = existing
    else:
        selected = reference(snapshot.latest(identifier, expected))
    if expected is Dossier:
        require_active_dossier_association(snapshot, selected, existing)
    return selected.model_dump()


def require_association_pins(record: Mapping[str, Any], changes: Mapping[str, Any]) -> None:
    """Without a reviewed archive digest, new associations need explicit versions."""
    for name in ("claim", "dossier", "from_claim", "to_claim"):
        identifier = changes.get(name + "_id")
        existing = record.get(name + "_ref")
        if (identifier and (not existing or identifier != existing["id"])
                and changes.get(name + "_revision") is None):
            flag = name.replace("_", "-")
            raise ResearchError(f"A changed association requires --{flag}-revision when --expected-snapshot is omitted; "
                                "inspect the target or use a reviewed --expected-snapshot")
    if "dossier_ids" in changes:
        existing_ids = {ref["id"] for ref in record.get("dossier_refs", [])}
        added = set(changes["dossier_ids"]) - existing_ids
        pins = changes.get("dossier_revisions", {})
        if added and (not isinstance(pins, Mapping) or any(identifier not in pins for identifier in added)):
            raise ResearchError("New dossier associations require explicit --dossier-revisions pins when "
                                "--expected-snapshot is omitted; inspect the targets or use a reviewed --expected-snapshot")


def revise_record(
    project: str | Path, kind: str, record_id: str, *, changes: Mapping[str, Any],
    expected_revision: int, change_kind: str, reason: str,
    expected_snapshot: str | None = None, actor: str = "local-author", section: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Append an authored change, or return the current record for an unchanged edit.

    Without ``expected_snapshot`` the current revision is checked and its
    snapshot forwarded, matching the CLI update flow; changed associations then
    need explicit revision pins. The strict HTTP route keeps sending its
    reviewed snapshot. Claims report unplaceable periods as ``warnings``.
    """
    if type(dry_run) is not bool:
        raise ResearchError("dry_run must be a boolean")
    repository = Repository(project)
    if expected_snapshot is not None and (
        not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot)
    ):
        raise ResearchError("Expected snapshot must be a SHA-256 digest")
    snapshot = repository.snapshot()
    if expected_snapshot is not None and snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; reload the current record before saving")
    previous = _record(snapshot, kind, record_id)
    changes = _section_changes(previous, changes, section)
    revised = _revision_candidate(snapshot, previous, changes=changes, expected_revision=expected_revision,
                                  change_kind=change_kind, reason=reason, actor=actor)
    if expected_snapshot is None:
        require_association_pins(previous.model_dump(mode="json"), changes)
    additions = [] if revised is previous else [revised]
    if dry_run:
        if additions:
            repository.prepare_commit(list(additions), snapshot)
        return {"schema_version": "research-revision-write-preview-local/1", "project_id": snapshot.project.id,
                "snapshot": snapshot.digest, "kind": kind, "record_id": record_id,
                "from_revision": previous.revision, "to_revision": None,
                "expected_revision": expected_revision, "changes": dict(changes),
                "candidate": revised.model_dump(mode="json"), "fields": _comparison_fields(previous, revised),
                "ready": True, "dry_run": True,
                **({"warnings": period_warnings(revised.scope.time_period)} if isinstance(revised, Claim) else {})}
    accepted = repository.commit(list(additions), {}, snapshot)
    view = _view(repository, accepted, revised)
    if isinstance(revised, Claim):
        view["warnings"] = period_warnings(revised.scope.time_period)
    return view


def _revision_candidate(snapshot: Snapshot, previous: Authored, *, changes: Mapping[str, Any],
                        expected_revision: int, change_kind: str, reason: str, actor: str) -> Authored:
    """Validate an operation, retaining its prior record when content is unchanged."""
    if type(expected_revision) is not int or expected_revision < 1:
        raise ResearchError("Expected revision must be a positive integer")
    if previous.revision != expected_revision:
        raise ResearchConflictError("Record revision changed; the reviewed revision is no longer current")
    if not isinstance(changes, Mapping) or not changes:
        raise ResearchError("Provide at least one editable field")
    if change_kind not in ("correction", "supersession"):
        raise ResearchError("Choose correction or supersession explicitly")
    if not isinstance(reason, str) or not reason.strip():
        raise ResearchError("A revision reason is required")
    if not isinstance(actor, str) or not actor.strip():
        raise ResearchError("A revision actor is required")
    revised = _apply_changes(snapshot, previous, changes, change_kind=change_kind, reason=reason, actor=actor)
    _validate_revision_links(snapshot, previous, revised)
    # Validate the complete candidate first, then ignore only its encoding and
    # revision metadata. Reapplying a value must not create obsolete pin warnings.
    metadata = {"schema_version", "revision", "created_at", "created_by", "change"}
    if previous.model_dump(exclude=metadata) == revised.model_dump(exclude=metadata):
        return previous
    return revised


def _section_text(body: str, section: str) -> str:
    spans = _section_spans(body)
    matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
    if not matches:
        raise ResearchError(f"Section '{section}' not found; available: {_section_candidates(spans)}")
    if len(matches) != 1:
        raise ResearchError(f"Section '{section}' is ambiguous")
    selected = matches[0]
    content = body[selected.content_start:_section_subtree_end(spans, selected, len(body))]
    return content.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def _section_changes(record: Authored, changes: Mapping[str, Any], section: str | None) -> Mapping[str, Any]:
    """Resolve a section draft against its observed dossier, keeping other fields."""
    if isinstance(changes, Mapping) and "preamble" in changes:
        if not isinstance(record, Dossier) or "body" in changes or section is not None:
            raise ResearchError("Choose a dossier preamble, section or full body replacement, not both")
        updated = dict(changes)
        content = updated.pop("preamble")
        updated["body"] = update_preamble(record.body, content)
        changes = updated
    if section is None:
        return changes
    if not isinstance(record, Dossier):
        raise ResearchError("Section editing requires a dossier")
    if (not isinstance(section, str) or not section.strip() or not isinstance(changes, Mapping)
            or not isinstance(changes.get("body"), str)):
        raise ResearchError("Provide a section heading and text content")
    return {**changes, "body": update_section(record.body, section, changes["body"])}


def _apply_changes(
    snapshot: Snapshot, previous: Authored, changes: Mapping[str, Any], *,
    change_kind: str, reason: str, actor: str,
) -> Authored:
    """Build a validated record without publishing it."""
    kind = previous.kind
    changes = _section_changes(previous, changes, None)
    if set(changes) - FIELDS[kind]:
        raise ResearchError("The change contains unknown or immutable fields")
    values = previous.model_dump(mode="json")
    direct = {k: v for k, v in changes.items() if k not in
              {"preamble", "evidence_ids", "dossier_id", "claim_id", "claim_revision", "dossier_revision", "passage_id", "time_period", "place", "actors", "dossier_ids", "dossier_revisions", "from_claim_id", "from_claim_revision", "to_claim_id", "to_claim_revision"}}
    for name in ("title", "statement", "rationale", "reviewer", "impact_on_plot"):
        if isinstance(direct.get(name), str):
            direct[name] = direct[name].strip()
            if not direct[name] and (name == "impact_on_plot" or
                                     (name == "rationale" and isinstance(previous, (EvidenceLink, ClaimRelation)))):
                direct[name] = None
    if isinstance(previous, ClaimRelation) and "relation" in direct:
        try:
            direct["relation"] = normalize_claim_relation(direct["relation"])
        except ValueError as exc:
            raise ResearchError(str(exc)) from None
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
        if isinstance(previous, (EvidenceLink, ManuscriptClaimLink, Decision)) and ("claim_id" in changes or "claim_revision" in changes):
            identifier = changes.get("claim_id", previous.claim_ref.id if previous.claim_ref else None)
            values["claim_ref"] = _association(snapshot, identifier, Claim, previous.claim_ref, changes.get("claim_revision"))
        if isinstance(previous, ClaimRelation):
            for role in ("from", "to"):
                name = role + "_claim"
                if name + "_id" in changes or name + "_revision" in changes:
                    existing = getattr(previous, name + "_ref")
                    identifier = changes.get(name + "_id", existing.id)
                    values[name + "_ref"] = _association(snapshot, identifier, Claim, existing, changes.get(name + "_revision"))
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
        schema_version = ("research-local/8" if isinstance(previous, Dossier)
                          and (previous.schema_version == "research-local/8" or values.get("geography") is not None)
                          else previous.revision_schema_version)
        values.update(schema_version=schema_version, revision=previous.revision + 1,
                      created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                      created_by=actor,
                      change={"change_kind": change_kind, "reason": reason.strip(), "previous_revision": previous.revision})
        revised = KINDS[kind].model_validate(values)
    except ValidationError:
        raise ResearchError("Invalid revision fields; check required text, types and size limits") from None
    encode(revised)
    return revised


def _editable_values(record: Authored) -> dict[str, Any]:
    """Flatten editable fields, keeping an association and its revision together."""
    values: dict[str, Any] = {}
    for name in sorted(FIELDS[record.kind]):
        if name in ("claim_revision", "dossier_revision", "dossier_revisions", "from_claim_revision", "to_claim_revision"):
            continue
        if name in ("claim_id", "dossier_id", "from_claim_id", "to_claim_id"):
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
        elif name == "geography" and isinstance(record, Dossier):
            values[name] = record.geography.model_dump(mode="json") if record.geography else None
        else:
            values[name] = getattr(record, name)
    return values


def _field_change(name: str, value: Any) -> dict[str, Any]:
    if name == "dossier_ids":
        return {name: [ref["id"] for ref in value], "dossier_revisions": {ref["id"]: ref["revision"] for ref in value}}
    if name in ("claim_id", "dossier_id", "from_claim_id", "to_claim_id"):
        if value is None:
            return {name: None}
        return {name: value["id"], name.replace("_id", "_revision"): value["revision"]}
    return {name: value}


def _comparison_fields(before: Authored, after: Authored) -> list[dict[str, Any]]:
    """Compare editable values, preserving scope and association-pin semantics."""
    previous, current = _editable_values(before), _editable_values(after)
    return [{"field": name, "before": value, "after": current[name]}
            for name, value in previous.items() if value != current[name]]


def preview_record_changes(project: str | Path, kind: str, record_id: str, *,
                           changes: Mapping[str, Any], section: str | None = None) -> dict[str, Any]:
    """Compare a supplied draft with HEAD from one observed snapshot; never write."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    current = _record(snapshot, kind, record_id)
    draft = _revision_candidate(snapshot, current, changes=_section_changes(current, changes, section),
                                expected_revision=current.revision, change_kind="correction",
                                reason="Preview only", actor="local-author")
    return {"schema_version": "research-revision-comparison-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "kind": kind, "record_id": record_id,
            "from_revision": current.revision, "to_revision": None,
            "fields": _comparison_fields(current, draft)}


def compare_record_revisions(project: str | Path, kind: str, record_id: str, *,
                             from_revision: int, to_revision: int | None = None) -> dict[str, Any]:
    """Compare two accepted authored revisions from one snapshot without repinning."""
    if type(from_revision) is not int or from_revision < 1:
        raise ResearchError("From revision must be a positive integer")
    repository = Repository(project)
    snapshot = repository.snapshot()
    first = _record(snapshot, kind, record_id, from_revision, include_withdrawn=True)
    last = _record(snapshot, kind, record_id, to_revision, include_withdrawn=True)
    return {"schema_version": "research-revision-comparison-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "kind": kind, "record_id": record_id,
            "from_revision": first.revision, "to_revision": last.revision,
            **(dossier_withdrawal(snapshot, record_id) if isinstance(last, Dossier) else {}),
            "fields": _comparison_fields(first, last)}


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
    elif isinstance(revised, ClaimRelation):
        snapshot.get(revised.from_claim_ref, Claim)
        snapshot.get(revised.to_claim_ref, Claim)
    elif isinstance(revised, (EvidenceLink, ManuscriptClaimLink, Decision)):
        if revised.claim_ref:
            snapshot.get(revised.claim_ref, Claim)
        if isinstance(revised, EvidenceLink) and (
            not isinstance(previous, EvidenceLink) or revised.passage_ref != previous.passage_ref
        ):
            snapshot.get(revised.passage_ref, Passage)


def prepare_record_revision(
    project: str | Path, kind: str, record_id: str, *, base_revision: int,
    changes: Mapping[str, Any], resolutions: Mapping[str, str] | None = None,
    section: str | None = None,
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
    draft = _apply_changes(snapshot, base, _section_changes(base, changes, section),
                           change_kind="correction", reason="Preview only", actor="local-author")
    _validate_revision_links(snapshot, base, draft)
    before, now, mine = (_editable_values(record) for record in (base, current, draft))
    now_body = now.get("body", "")
    if section is not None:
        for values in (before, now, mine):
            values["body"] = _section_text(values["body"], section)
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
            merged.update({"body": update_section(now_body, section, desired)}
                          if name == "body" and section is not None else _field_change(name, desired))
    if set(resolutions) - conflicting_fields:
        raise ResearchError("Resolution names must identify fields with conflicting changes")
    # Unresolved choices do not yet form a complete candidate. Individually
    # valid endpoint edits can otherwise make a temporary causal self-link.
    if not conflicts and merged:
        candidate = _apply_changes(snapshot, current, merged, change_kind="correction", reason="Preview only", actor="local-author")
        _validate_revision_links(snapshot, current, candidate)
        repository.prepare_commit([candidate], snapshot)
    return {
        "schema_version": "research-revision-preview-local/1", "base_revision": base_revision,
        "current": _view(repository, snapshot, current), "changes": merged,
        "conflicts": conflicts, "ready": not conflicts, "has_changes": bool(merged),
        **({"section": section} if section is not None else {}),
    }


def prepare_dossier_section(
    project: str | Path, record_id: str, *, base_revision: int,
    section: str, content: str, resolutions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Reconcile a selected section through the shared authored-record preparation."""
    if not isinstance(section, str) or not section.strip() or not isinstance(content, str):
        raise ResearchError("Provide a section heading and text content")
    return prepare_record_revision(project, "dossier", record_id, base_revision=base_revision,
                                   section=section, changes={"body": content}, resolutions=resolutions)


def _prepare_batch_anchor(
    repository: Repository,
    previous: ManuscriptClaimLink,
    changes: Mapping[str, Any],
    *,
    source_cache: dict[Path, tuple[str, str]],
    paragraph_cache: dict[tuple[str, str, str | None], Any],
) -> tuple[ManuscriptAnchor, tuple[Path, str]]:
    """Verify and resolve a source-bound manuscript anchor update inside a revision batch."""
    from ..io import FileUtils
    from ..pipeline import paragraph_identity
    from .manuscript import _paragraphs, _quote_occurrences, _source_path

    if previous.state != "active" or changes.get("state", previous.state) != "active":
        raise ResearchError("Retracted associations cannot be re-pinned")
    expected_source_sha256 = changes.get("expected_source_sha256")
    if not isinstance(expected_source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
        raise ResearchError("Anchor updates in a revision batch require expected_source_sha256")
    manuscript_arg = changes.get("manuscript", previous.anchor.source_path)
    if not isinstance(manuscript_arg, str) or not manuscript_arg.strip():
        raise ResearchError("Invalid manuscript path")
    path, relative = _source_path(repository, manuscript_arg)
    if previous.anchor.source_path != relative:
        raise ResearchError("The association belongs to a different manuscript path")
    if path not in source_cache:
        try:
            source_cache[path] = FileUtils.read_source_snapshot(str(path))
        except (OSError, UnicodeError) as exc:
            raise ResearchError("Manuscript source is missing or unreadable") from exc
    text, source_sha256 = source_cache[path]
    if source_sha256 != expected_source_sha256:
        raise ResearchConflictError(
            "Manuscript source bytes changed; review the current text before saving"
        )
    language = changes.get("language")
    if language is not None and not isinstance(language, str):
        raise ResearchError("Language must be a string or null")
    cache_key = (relative, source_sha256, language)
    if cache_key not in paragraph_cache:
        paragraph_cache[cache_key] = _paragraphs(text, repository, language, None)
    paragraphs = paragraph_cache[cache_key]

    selection = changes.get("selection")
    has_quote = "new_quote" in changes or "quote" in changes
    accept_moved = changes.get("accept_moved")
    if accept_moved is not None and type(accept_moved) is not bool:
        raise ResearchError("accept_moved must be a boolean")
    if selection is not None:
        if has_quote or accept_moved:
            raise ResearchError("Choose selection or new_quote/accept_moved, not both")
        required = {"start_line", "end_line", "paragraph_sha256", "start", "end", "quote"}
        if not isinstance(selection, Mapping) or set(selection) != required:
            raise ResearchError(
                "Selection requires exact paragraph identity and Unicode codepoint offsets"
            )
        try:
            updated_anchor = ManuscriptAnchor.model_validate(
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
        matches = [p for p in paragraphs if paragraph_identity(p) == identity]
        if len(matches) != 1 or matches[0].text[updated_anchor.start : updated_anchor.end] != updated_anchor.quote:
            raise ResearchError(
                "Selection does not match one current displayed manuscript paragraph"
            )
        return updated_anchor, (path, source_sha256)

    if "new_quote" in changes and "quote" in changes and changes["new_quote"] != changes["quote"]:
        raise ResearchError("Conflicting quote and new_quote values")
    new_quote = changes["new_quote"] if "new_quote" in changes else changes.get("quote")
    line = changes.get("line")
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
            raise ResearchError("Replacement quote is ambiguous; add line to choose one")
        quote_to_pin = new_quote
    elif accept_moved is True:
        if line is not None:
            raise ResearchError("line applies only to replacement quotes")
        occurrences = _quote_occurrences(paragraphs, previous.anchor.quote)
        if len(occurrences) != 1:
            raise ResearchError(
                "Only a uniquely resolvable anchor can be re-pinned; review the manuscript first"
            )
        quote_to_pin = previous.anchor.quote
    else:
        raise ResearchError("Anchor updates require accept_moved, new_quote or selection")

    target, start = occurrences[0]
    end = start + len(quote_to_pin)
    identity = paragraph_identity(target)
    try:
        updated_anchor = ManuscriptAnchor.model_validate(
            {
                **previous.anchor.model_dump(),
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
    return updated_anchor, (path, source_sha256)


def _prepare_batch_acknowledgement(
    snapshot: Snapshot,
    operation: Mapping[str, Any],
    *,
    actor: str,
    identifiers: set[str],
    ack_pairs: set[tuple[str, str]],
    current_acknowledgements: Mapping[tuple[str, str], DecisionAcknowledgement],
) -> tuple[DecisionAcknowledgement, dict[str, Any]]:
    """Validate an explicit decision acknowledgement event inside a revision batch."""
    from . import editorial
    from .api import envelope

    allowed = {
        "kind",
        "id",
        "decision_id",
        "dossier_id",
        "expected_decision_revision",
        "expected_dossier_revision",
        "status",
        "note",
        "changes",
        "expected_revision",
        "change_kind",
        "reason",
    }
    if set(operation) - allowed:
        raise ResearchError("Invalid decision acknowledgement operation fields")
    nested = operation.get("changes")
    if nested is not None and (not isinstance(nested, Mapping) or set(nested) - {
        "decision_id",
        "dossier_id",
        "expected_decision_revision",
        "expected_dossier_revision",
        "status",
        "note",
    }):
        raise ResearchError("Invalid decision acknowledgement changes")
    source = {**(nested or {}), **{k: v for k, v in operation.items() if k != "changes"}}
    decision_id = source.get("decision_id")
    dossier_id = source.get("dossier_id")
    expected_decision_revision = source.get("expected_decision_revision")
    expected_dossier_revision = source.get("expected_dossier_revision")
    status = source.get("status")
    note = source.get("note")
    if not isinstance(decision_id, str) or not isinstance(dossier_id, str):
        raise ResearchError("Decision acknowledgement requires decision_id and dossier_id")
    if (
        type(expected_decision_revision) is not int
        or expected_decision_revision < 1
        or type(expected_dossier_revision) is not int
        or expected_dossier_revision < 1
    ):
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
    pair = (decision.id, dossier.id)
    if pair in ack_pairs:
        raise ResearchError("A decision/dossier acknowledgement pair may appear only once in a revision batch")
    ack_pairs.add(pair)
    impact = editorial.decision_graph(snapshot, decision_id=decision_id).get(decision_id)
    if impact is None or dossier_id not in {entry["id"] for entry in impact["dossiers"]}:
        raise ResearchError("Acknowledge only a dossier explicitly associated with this decision")
    if (
        not isinstance(status, str)
        or status not in {"applied", "review_needed"}
        or (note is not None and not isinstance(note, str))
    ):
        raise ResearchError("Acknowledgement requires an explicit valid status, actor and optional text note")
    previous = current_acknowledgements.get(pair)
    ack_values = envelope(snapshot.project.id, actor.strip())
    explicit_id = operation.get("id")
    if explicit_id is not None:
        if not isinstance(explicit_id, str):
            raise ResearchError("Invalid acknowledgement identifier")
        try:
            Reference(id=explicit_id)
        except ValidationError:
            raise ResearchError("Invalid acknowledgement identifier") from None
        if explicit_id in snapshot.records or explicit_id in identifiers:
            raise ResearchError("Acknowledgement identifier already exists")
        ack_values["id"] = explicit_id
    identifiers.add(ack_values["id"])
    try:
        acknowledgement = DecisionAcknowledgement(
            **ack_values,
            decision_ref=reference(decision),
            dossier_ref=reference(dossier),
            status="applied" if status == "applied" else "review_needed",
            note=note.strip() or None if note is not None else None,
            supersedes_ref=reference(previous) if previous else None,
        )
    except ValidationError:
        raise ResearchError("Invalid acknowledgement fields; check actor and note size") from None
    encode(acknowledgement)
    prepared_op: dict[str, Any] = {
        "kind": "decision_acknowledgement",
        "id": acknowledgement.id,
        "decision_id": decision.id,
        "dossier_id": dossier.id,
        "expected_decision_revision": decision.revision,
        "expected_dossier_revision": dossier.revision,
        "status": acknowledgement.status,
        "note": acknowledgement.note,
    }
    return acknowledgement, prepared_op


def _revision_batch(
    repository: Repository,
    snapshot: Snapshot,
    operations: list[Mapping[str, Any]],
    actor: str,
) -> tuple[list[BatchRecord], list[dict[str, Any]], list[tuple[Path, str]]]:
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
        raise ResearchError("Provide between 1 and 100 revision operations")
    if not isinstance(actor, str) or not actor.strip():
        raise ResearchError("A revision actor is required")
    revised: list[BatchRecord] = []
    prepared: list[dict[str, Any]] = []
    verified_sources: list[tuple[Path, str]] = []
    source_cache: dict[Path, tuple[str, str]] = {}
    paragraph_cache: dict[tuple[str, str, str | None], Any] = {}
    identifiers: set[str] = set()
    ack_pairs: set[tuple[str, str]] = set()
    current_acknowledgements: dict[tuple[str, str], DecisionAcknowledgement] | None = None
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    for operation in operations:
        if isinstance(operation, Mapping) and operation.get("kind") == "decision_acknowledgement":
            if current_acknowledgements is None:
                current_acknowledgements = latest_acknowledgements(snapshot.records.values())
            acknowledgement, prepared_ack = _prepare_batch_acknowledgement(
                snapshot,
                operation,
                actor=actor,
                identifiers=identifiers,
                ack_pairs=ack_pairs,
                current_acknowledgements=current_acknowledgements,
            )
            revised.append(acknowledgement)
            prepared.append(prepared_ack)
            continue
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
        changes, change_kind, reason = operation["changes"], operation["change_kind"], operation["reason"]
        if not isinstance(changes, Mapping) or not changes:
            raise ResearchError("Provide at least one editable field")
        updated_anchor: ManuscriptAnchor | None = None
        record_changes: Mapping[str, Any] = changes
        if isinstance(previous, ManuscriptClaimLink) and (set(changes) & MANUSCRIPT_BATCH_ANCHOR_FIELDS):
            if set(changes) - (FIELDS["manuscript_claim_link"] | MANUSCRIPT_BATCH_ANCHOR_FIELDS):
                raise ResearchError("The change contains unknown or immutable fields")
            updated_anchor, verified_source = _prepare_batch_anchor(
                repository,
                previous,
                changes,
                source_cache=source_cache,
                paragraph_cache=paragraph_cache,
            )
            verified_sources.append(verified_source)
            record_changes = {k: v for k, v in changes.items() if k not in MANUSCRIPT_BATCH_ANCHOR_FIELDS}
            if not record_changes:
                record_changes = {"note": previous.note}
        candidate = _revision_candidate(snapshot, previous, changes=record_changes, expected_revision=expected_revision,
                                        change_kind=change_kind, reason=reason, actor=actor.strip())
        if updated_anchor is not None and isinstance(previous, ManuscriptClaimLink):
            base_record = candidate if isinstance(candidate, ManuscriptClaimLink) and candidate is not previous else previous.model_copy(
                update={
                    "revision": previous.revision + 1,
                    "created_by": actor.strip(),
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "change": {
                        "change_kind": change_kind,
                        "reason": reason.strip(),
                        "previous_revision": previous.revision,
                    },
                }
            )
            candidate_with_anchor = base_record.model_copy(update={"anchor": updated_anchor})
            metadata = {"schema_version", "revision", "created_at", "created_by", "change"}
            candidate = (
                previous
                if previous.model_dump(exclude=metadata) == candidate_with_anchor.model_dump(exclude=metadata)
                else candidate_with_anchor
            )
            encode(candidate)
        revised.append(candidate)
        prepared.append({"kind": kind, "id": identifier, "expected_revision": expected_revision,
                         "changes": dict(changes), "change_kind": change_kind, "reason": reason.strip()})
    return revised, prepared, verified_sources


def _batch_operations(
    snapshot: Snapshot, value: list[Mapping[str, Any]] | Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Keep a reviewed packet's authority and observation with its operations."""
    if isinstance(value, Mapping):
        if set(value) != {"schema_version", "project_id", "snapshot", "operations", "ready"} or (
            value.get("schema_version") != "research-revision-batch-local/1" or value.get("ready") is not True
        ):
            raise ResearchError("Provide a ready research-revision-batch-local/1 preview packet")
        if value["project_id"] != snapshot.project.id:
            raise ResearchConflictError("Reviewed batch belongs to a different research project")
        if value["snapshot"] != snapshot.digest:
            raise ResearchConflictError("Reviewed batch snapshot changed; prepare and review a fresh packet")
        value = value["operations"]
    if not isinstance(value, list):
        raise ResearchError("Provide a revision operations list or a reviewed batch preview packet")
    return value


def prepare_record_revisions(
    project: str | Path, operations: list[Mapping[str, Any]] | Mapping[str, Any], *, actor: str = "local-author",
) -> dict[str, Any]:
    """Validate a read-only batch of existing records against one current snapshot.

    Every operation supplies kind/id, expected_revision, changes, change_kind
    and reason (or an explicit ``decision_acknowledgement`` operation).
    References must already exist; future revisions from other operations are
    not implicitly pinned. Review the returned operations and snapshot before
    explicitly calling ``apply_record_revisions``.
    """
    repository = Repository(project)
    snapshot = repository.snapshot()
    records, prepared, _verified_sources = _revision_batch(
        repository, snapshot, _batch_operations(snapshot, operations), actor
    )
    additions = [
        record
        for record in records
        if record.id not in snapshot.records or record.revision != snapshot.records[record.id].revision
    ]
    if additions:
        repository.prepare_commit(list(additions), snapshot)
    return {"schema_version": "research-revision-batch-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "operations": prepared, "ready": True}


def apply_record_revisions(
    project: str | Path, operations: list[Mapping[str, Any]] | Mapping[str, Any], *, expected_snapshot: str,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Append changed reviewed records atomically; unchanged records keep their revision."""
    from ..io import FileUtils

    if not isinstance(expected_snapshot, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
        raise ResearchError("Expected snapshot must be a SHA-256 digest")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if snapshot.digest != expected_snapshot:
        raise ResearchConflictError("Research snapshot changed; prepare the batch again before applying")
    records, _prepared, verified_sources = _revision_batch(
        repository, snapshot, _batch_operations(snapshot, operations), actor
    )
    additions = [
        record
        for record in records
        if record.id not in snapshot.records or record.revision != snapshot.records[record.id].revision
    ]
    for path, expected_sha256 in dict(verified_sources).items():
        if FileUtils.read_source_snapshot(str(path))[1] != expected_sha256:
            raise ResearchConflictError("Manuscript source bytes changed before saving")
    accepted = repository.commit(list(additions), {}, snapshot)
    return {"schema_version": "research-revision-batch-local/1", "project_id": accepted.project.id,
            "snapshot": accepted.digest, "records": [
                {"kind": record.kind, "id": record.id, "revision": record.revision}
                for record in records
            ]}
