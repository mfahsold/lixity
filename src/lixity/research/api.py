"""Explicit-project API for local evidence ingestion, lookup and integrity checks."""

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import ValidationError

from . import catalogue
from .models import (
    ENTITY,
    Activity,
    Blob,
    Claim,
    ClaimScope,
    Decision,
    Dossier,
    Entity,
    EvidenceLink,
    EvidenceRelation,
    Extraction,
    Passage,
    Project,
    Reference,
    Source,
    SourceContext,
    SourceVersion,
    Tombstone,
    reference,
)
from .repository import Repository, ResearchError, digest

MAX_SOURCE_BYTES = 2 * 1024 * 1024


def envelope(project_id: str, actor: str) -> dict[str, Any]:
    return {"id": uuid4().urn, "project_id": project_id, "created_by": actor,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}


def init(project: str | Path, *, title: str, language: str = "en", actor: str = "local-author") -> dict[str, Any]:
    repository = Repository(project)
    if repository.safe(repository.data).exists():
        raise ResearchError("Research directory already exists; refusing to overwrite it")
    identifier = uuid4().urn
    values = envelope(identifier, actor)
    values.update(id=identifier, title=title, language=language)
    record = Project.model_validate(values)
    snapshot = repository.commit([record], {}, None)
    return {"schema_version": "research-init-local/1", "project_id": identifier, "snapshot": snapshot.digest}


def ingest(project: str | Path, file: str | Path, *, allow_retention: bool = False,
           source_id: str | None = None, title: str | None = None,
           language: str | None = None, actor: str = "local-author", dry_run: bool = False,
           context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if allow_retention is not True:
        raise ResearchError("Explicit local retention permission is required (--allow-retention)")
    repository = Repository(project)
    snapshot = repository.snapshot()
    path = Path(file).expanduser()
    if not path.is_file():
        raise ResearchError("Source must be a local UTF-8 text file")
    with path.open("rb") as stream:
        content = stream.read(MAX_SOURCE_BYTES + 1)
    if not content or len(content) > MAX_SOURCE_BYTES or b"\x00" in content:
        raise ResearchError("Source must be nonempty text of at most 2 MiB, without NUL bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise ResearchError("Only UTF-8 text is supported; PDF/OCR is not implemented") from None
    spans = [(match.start(), match.start() + len(match.group().rstrip()))
             for match in re.finditer(r"\S.*?(?=\n\s*\n|\Z)", text, re.DOTALL)]
    if not spans or len(spans) > 5000:
        raise ResearchError("Source must contain between 1 and 5000 nonempty paragraphs")
    records: list[Entity] = []
    if source_id:
        source = snapshot.get(Reference(id=source_id), Source)
        if (title is not None and title != source.title) or (language is not None and language != source.language):
            raise ResearchError("Source refresh cannot change its title or language in this pilot")
    else:
        values = envelope(snapshot.project.id, actor)
        values.update(title=title or path.name, language=language or snapshot.project.language)
        source = Source.model_validate(values)
        records.append(source)
    checksum = digest(content)
    versions = [record for record in snapshot.records.values()
                if isinstance(record, SourceVersion) and record.source_ref.id == source.id]
    latest = max(versions, key=lambda record: record.sequence) if versions else None
    source_context = (SourceContext.model_validate(dict(context)) if context is not None
                      else latest.context if latest else SourceContext())
    if latest is not None and latest.blob.sha256 == checksum and latest.context == source_context:
        repository.read_blob(latest.blob)
        return {"schema_version": "research-ingest-local/1", "source_id": source.id,
                "source_version_id": latest.id, "snapshot": snapshot.digest,
                "unchanged": True, "dry_run": dry_run, "passages": len(spans)}
    descriptor = Blob(sha256=checksum, byte_length=len(content))
    version = SourceVersion(**envelope(snapshot.project.id, actor), source_ref=reference(source),
                            sequence=latest.sequence + 1 if latest else 1, blob=descriptor,
                            retention_confirmed=True, context=source_context)
    activity = Activity(**envelope(snapshot.project.id, actor), source_version_ref=reference(version))
    extraction = Extraction(**envelope(snapshot.project.id, actor), source_version_ref=reference(version),
                            activity_ref=reference(activity), text_blob=descriptor)
    records.extend([version, activity, extraction])
    for start, end in spans:
        records.append(Passage(**envelope(snapshot.project.id, actor), extraction_ref=reference(extraction),
                               start=start, end=end, verbatim=text[start:end], language=source.language))
    result = {"schema_version": "research-ingest-local/1", "source_id": source.id,
              "source_version_id": version.id, "unchanged": False,
              "passages": len(spans), "dry_run": dry_run}
    result["snapshot"] = snapshot.digest if dry_run else repository.commit(records, {checksum: content}, snapshot).digest
    return result


def reindex(project: str | Path) -> dict[str, Any]:
    return catalogue.reindex(Repository(project))


def search(project: str | Path, query: str, *, limit: int = 20) -> dict[str, Any]:
    return catalogue.search(Repository(project), query, limit=limit)


def cite(project: str | Path, passage_id: str) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()
    passage = snapshot.get(Reference(id=passage_id), Passage)
    return repository.citation(snapshot, passage)


def audit(project: str | Path) -> dict[str, Any]:
    repository = Repository(project)
    errors: list[str] = []
    count = 0
    head: str | None = None
    try:
        snapshot = repository.snapshot()
        count = len(snapshot.records)
        head = snapshot.digest
        checked: set[str] = set()
        for record in snapshot.records.values():
            if isinstance(record, SourceVersion) and record.blob.sha256 not in checked:
                repository.read_blob(record.blob)
                checked.add(record.blob.sha256)
            elif isinstance(record, Passage):
                repository.quote(snapshot, record)
    except (OSError, ResearchError, ValidationError, UnicodeDecodeError):
        errors.append("Research integrity check failed: missing, invalid or modified records/bytes")
    return {"schema_version": "research-audit-local/1", "ok": not errors,
            "snapshot": head, "records": count, "errors": errors,
            "scope": "retained source records and citations; not factual accuracy or index freshness"}


def schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **ENTITY.json_schema()}


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


def compare_source(
    project: str | Path,
    source_id: str,
    manuscript: str | Path,
    *,
    version_id: str | None = None,
    language: str | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """Compare verified research source against manuscript text or file."""
    from .analysis import compare_source_to_manuscript

    return compare_source_to_manuscript(
        project,
        source_id,
        manuscript,
        version_id=version_id,
        language=language,
        top_n=top_n,
    )


def withdraw(
    project: str | Path,
    source_id: str,
    *,
    version_id: str | None = None,
    reason: str = "Withdrawn by user",
    actor: str = "local-author",
) -> dict[str, Any]:
    reason = reason.strip() if reason else "Withdrawn by user"
    if not (1 <= len(reason) <= 500):
        raise ResearchError("Withdrawal reason must be between 1 and 500 characters")
    repository = Repository(project)
    snapshot = repository.snapshot()

    source = snapshot.get(Reference(id=source_id), Source)
    target_kind: Literal["source", "source_version"]
    if version_id is not None:
        version = snapshot.get(Reference(id=version_id), SourceVersion)
        if version.source_ref.id != source.id:
            raise ResearchError("Source version does not belong to the requested source")
        target_ref = reference(version)
        target_kind = "source_version"
    else:
        target_ref = reference(source)
        target_kind = "source"

    already_tombstoned = any(
        isinstance(rec, Tombstone) and rec.target_ref.id in (target_ref.id, source.id)
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
    new_snapshot = repository.commit([tombstone], {}, snapshot)
    return {
        "schema_version": "research-withdraw-local/1",
        "operation": "withdraw",
        "source_id": source.id,
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
        target_ref=target_ref,
        target_kind=target_kind,
        operation="purge",
        reason=reason,
    )

    if dry_run:
        new_digest = snapshot.digest
    else:
        new_snapshot = repository.commit(
            [tombstone],
            {},
            snapshot,
            removals=records_to_remove,
            delete_blobs=deleted_blobs,
        )
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
    repository = Repository(project)
    snapshot = repository.snapshot()

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
    for record in snapshot.records.values():
        if isinstance(record, Passage):
            ver_id = extraction_to_version.get(record.extraction_ref.id)
            if ver_id:
                passages_per_version[ver_id] = passages_per_version.get(ver_id, 0) + 1

    sources_list: list[dict[str, Any]] = []
    for record in snapshot.records.values():
        if not isinstance(record, Source) or record.id in withdrawn_or_purged:
            continue
        versions = [
            v
            for v in snapshot.records.values()
            if isinstance(v, SourceVersion) and v.source_ref.id == record.id and v.id not in withdrawn_or_purged
        ]
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

    return {
        "id": source.id,
        "title": source.title,
        "language": source.language,
        "version_id": latest.id,
        "sequence": latest.sequence,
        "byte_length": latest.blob.byte_length,
        "sha256": latest.blob.sha256,
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


def create_dossier(
    project: str | Path,
    title: str,
    body: str,
    *,
    language: str = "en",
    tags: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create and commit a new Dossier record."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    title = title.strip()
    if not (1 <= len(title) <= 500):
        raise ResearchError("Dossier title must be between 1 and 500 characters")

    evidence_refs = [Reference(id=eid) for eid in (evidence_ids or [])]
    for ref in evidence_refs:
        snapshot.get(ref, Passage)

    dossier = Dossier(
        **envelope(snapshot.project.id, actor),
        title=title,
        language=language,  # type: ignore[arg-type]
        tags=tags or [],
        body=body,
        evidence_refs=evidence_refs,
    )
    new_snapshot = repository.commit([dossier], {}, snapshot)
    return {
        "schema_version": "research-dossier-local/1",
        "dossier_id": dossier.id,
        "title": dossier.title,
        "snapshot": new_snapshot.digest,
    }


def list_dossiers(project: str | Path) -> dict[str, Any]:
    """List all active dossiers in the project."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    dossiers_list = [
        {
            "id": record.id,
            "title": record.title,
            "language": record.language,
            "tags": record.tags,
            "evidence_count": len(record.evidence_refs),
            "created_at": record.created_at,
            "created_by": record.created_by,
            "excerpt": record.body[:300].strip(),
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
    try:
        return repository.citation(snapshot, snapshot.get(ref, Passage))
    except (ResearchError, KeyError):
        return {"id": ref.id, "error": "Citation unavailable or missing"}


def get_dossier(project: str | Path, dossier_id: str) -> dict[str, Any]:
    """Retrieve full details of a specific dossier, including resolved evidence citations."""
    repository = Repository(project)
    snapshot = repository.snapshot()

    dossier = snapshot.get(Reference(id=dossier_id), Dossier)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    if dossier.id in withdrawn_or_purged:
        raise ResearchError("Dossier has been withdrawn or purged")

    resolved_citations = [_resolve_evidence_citation(repository, snapshot, ref) for ref in dossier.evidence_refs]

    return {
        "id": dossier.id,
        "title": dossier.title,
        "language": dossier.language,
        "tags": dossier.tags,
        "body": dossier.body,
        "created_at": dossier.created_at,
        "created_by": dossier.created_by,
        "citations": resolved_citations,
    }


def create_claim(
    project: str | Path,
    *,
    title: str,
    statement: str,
    confidence: Literal["hypothetical", "evidenced", "disputed"] = "hypothetical",
    time_period: str | None = None,
    place: str | None = None,
    actors: list[str] | None = None,
    dossier_id: str | None = None,
    tags: list[str] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()

    dossier_ref = None
    if dossier_id:
        dossier = snapshot.get(Reference(id=dossier_id), Dossier)
        dossier_ref = reference(dossier)

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
    }


def list_claims(project: str | Path, *, dossier_id: str | None = None) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()

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
            "title": record.title,
            "statement": record.statement,
            "confidence": record.confidence,
            "scope": {
                "time_period": record.scope.time_period,
                "place": record.scope.place,
                "actors": record.scope.actors,
            },
            "dossier_id": record.dossier_ref.id if record.dossier_ref else None,
            "tags": record.tags,
            "created_at": record.created_at,
            "created_by": record.created_by,
        })

    claims_list.sort(key=lambda c: str(c["created_at"]), reverse=True)
    return {
        "schema_version": "research-claims-local/1",
        "claims": claims_list,
    }


def link_evidence(
    project: str | Path,
    *,
    claim_id: str,
    passage_id: str,
    relation: EvidenceRelation = "supports",
    rationale: str | None = None,
    reviewer: str = "author",
    actor: str = "local-author",
) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()

    claim = snapshot.get(Reference(id=claim_id), Claim)
    passage = snapshot.get(Reference(id=passage_id), Passage)

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

        citation = _resolve_evidence_citation(repository, snapshot, record.passage_ref)
        links_list.append({
            "id": record.id,
            "claim_id": record.claim_ref.id,
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
    actor: str = "local-author",
) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()

    claim_ref = None
    if claim_id:
        claim = snapshot.get(Reference(id=claim_id), Claim)
        claim_ref = reference(claim)

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
    )

    new_snapshot = repository.commit([decision], {}, snapshot)
    return {
        "schema_version": "research-decision-local/1",
        "decision_id": decision.id,
        "title": decision.title,
        "deviation_from_fact": decision.deviation_from_fact,
        "snapshot": new_snapshot.digest,
    }


def list_decisions(project: str | Path) -> dict[str, Any]:
    repository = Repository(project)
    snapshot = repository.snapshot()

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
            "title": record.title,
            "rationale": record.rationale,
            "claim_id": record.claim_ref.id if record.claim_ref else None,
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



