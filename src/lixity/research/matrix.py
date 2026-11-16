"""Claim-evidence-decision matrix and research gap analysis for local research archives."""

import csv
import io
import warnings
from pathlib import Path
from typing import Any, Literal, get_args

from . import editorial
from .models import (
    Claim,
    Decision,
    Dossier,
    EvidenceLink,
    ManuscriptClaimLink,
    Tombstone,
)
from .repository import Repository, ResearchError, Snapshot
from .revisions import EvidenceCitationReader
from .sections import extract_sections
from .timeline import timeline_data

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
    return _claim_matrix_data(repository, snapshot)


def _claim_matrix_data(repository: Repository, snapshot: Snapshot) -> dict[str, Any]:
    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }

    # Map dossiers by ID (latest revision)
    dossiers_by_id: dict[str, Dossier] = {}
    for record in snapshot.records.values():
        if (
            isinstance(record, Dossier)
            and record.id not in withdrawn_or_purged
            and (
                record.id not in dossiers_by_id
                or record.revision > dossiers_by_id[record.id].revision
            )
        ):
            dossiers_by_id[record.id] = record

    # Map claims by ID (latest revision)
    claims_by_id: dict[str, Claim] = {}
    for record in snapshot.records.values():
        if (
            isinstance(record, Claim)
            and record.id not in withdrawn_or_purged
            and (
                record.id not in claims_by_id or record.revision > claims_by_id[record.id].revision
            )
        ):
            claims_by_id[record.id] = record

    # Evidence links grouped by claim_id
    evidence_by_claim: dict[str, list[dict[str, Any]]] = {}
    total_evidence_count = 0
    reader = EvidenceCitationReader(repository, snapshot)
    for record in snapshot.records.values():
        if isinstance(record, EvidenceLink) and record.id not in withdrawn_or_purged:
            cid = record.claim_ref.id
            if cid not in evidence_by_claim:
                evidence_by_claim[cid] = []
            citation = reader.read(record.passage_ref)
            evidence_by_claim[cid].append(
                {
                    "link_id": record.id,
                    "relation": record.relation,
                    "rationale": record.rationale,
                    "passage_id": record.passage_ref.id,
                    "source_title": citation.get("source_title", ""),
                    "verbatim": citation.get("verbatim", ""),
                    "citation": citation,
                }
            )
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

        matrix_claims.append(
            {
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
            }
        )

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


def render_claim_matrix(data: dict[str, Any], *, format: Literal["md", "csv"] = "md") -> str:
    """Render a `claim_matrix` result as Markdown or CSV."""
    project_title = data.get("project_title", "")
    summary = data.get("summary", {})
    matrix_claims = data.get("claims", [])

    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
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
            ]
        )
        for c in matrix_claims:
            ev_list = c["evidence"] or [{}]
            dec_list = c["decisions"] or [{}]
            for ev in ev_list:
                for dec in dec_list:
                    writer.writerow(
                        [
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
                        ]
                    )
        return out.getvalue()

    lines = [
        f"# Research Claim-Evidence Matrix: {project_title}",
        "",
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
            dec_str = (
                ", ".join(
                    f"{d['title']}{' [DEVIATION]' if d['deviation_from_fact'] else ''}"
                    for d in c["decisions"]
                )
                or "–"
            )
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


def research_gaps(project: str | Path) -> dict[str, Any]:
    """Audit a research archive for unsupported, disputed, unanchored, or unplaced claims and pending decisions."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    matrix = _claim_matrix_data(repository, snapshot)
    review = editorial.editorial_review_data(
        snapshot, outline=lambda body: list(extract_sections(body))
    )
    chrono = timeline_data(snapshot)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    anchored_claim_ids = {
        record.claim_ref.id
        for record in snapshot.records.values()
        if isinstance(record, ManuscriptClaimLink) and record.id not in withdrawn_or_purged
    }

    unsupported_claims: list[dict[str, Any]] = []
    disputed_claims: list[dict[str, Any]] = []
    unanchored_claims: list[dict[str, Any]] = []
    for claim in matrix.get("claims", []):
        cid = str(claim.get("claim_id") or "")
        counts = claim.get("evidence_counts") or {}
        entry = {
            "claim_id": cid,
            "title": claim.get("title", ""),
            "confidence": claim.get("confidence", ""),
            "status": claim.get("status", ""),
            "dossier_title": claim.get("dossier_title"),
        }
        if int(counts.get("supports", 0)) == 0:
            unsupported_claims.append(entry)
        if int(counts.get("contradicts", 0)) > 0 or claim.get("confidence") == "disputed":
            disputed_claims.append({**entry, "contradicts": int(counts.get("contradicts", 0))})
        if cid and cid not in anchored_claim_ids:
            unanchored_claims.append(entry)

    unplaced_timeline = [
        {
            "claim_id": item.get("claim_id", ""),
            "title": item.get("title", ""),
            "time_period": item.get("time_period", ""),
            "reason": item.get("reason", ""),
        }
        for item in chrono.get("unplaced", [])
    ]

    pending_decisions = [
        {
            "decision_id": item.get("decision_id", ""),
            "title": item.get("title", ""),
            "reasons": list(item.get("reasons") or ()),
        }
        for item in review.get("candidates", [])
        if item.get("kind") == "decision"
    ]

    summary = matrix.get("summary", {})
    return {
        "schema_version": "research-gaps-local/1",
        "ok": True,
        "project_id": matrix.get("project_id", ""),
        "project_title": matrix.get("project_title", ""),
        "summary": {
            "total_claims": int(summary.get("total_claims", len(matrix.get("claims", [])))),
            "total_decisions": int(summary.get("total_decisions", 0)),
            "unsupported_claims": len(unsupported_claims),
            "disputed_claims": len(disputed_claims),
            "unanchored_claims": len(unanchored_claims),
            "unplaced_timeline_claims": len(unplaced_timeline),
            "pending_decisions": len(pending_decisions),
        },
        "unsupported_claims": unsupported_claims,
        "disputed_claims": disputed_claims,
        "unanchored_claims": unanchored_claims,
        "unplaced_timeline_claims": unplaced_timeline,
        "pending_decisions": pending_decisions,
    }
