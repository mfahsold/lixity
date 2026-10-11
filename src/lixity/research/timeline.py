"""Read-only chronology from explicit calendar labels, not inferred historical dates."""

import re
from datetime import date
from typing import Any

from .models import Claim, Tombstone
from .repository import Snapshot


def parse_period(label: str | None) -> tuple[dict[str, str] | None, str | None]:
    """Place CE years, ISO dates and same-precision ranges; retain all other labels."""
    if not label or not label.strip():
        return None, "missing"
    value = label.strip()
    precision = "year"
    if re.fullmatch(r"[0-9]{4}", value):
        first = last = value
    elif re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        first = last = value
        precision = "day"
    else:
        match = re.fullmatch(r"([0-9]{4})\s*(?:-|–|—|/|\.\.)\s*([0-9]{4})", value)
        if match:
            first, last = match.groups()
        else:
            match = re.fullmatch(
                r"([0-9]{4}-[0-9]{2}-[0-9]{2})\s*(?:-|–|—|/|\.\.)\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", value,
            )
            if not match:
                return None, "unrecognized"
            first, last = match.groups()
            precision = "day"
    try:
        start = date(int(first), 1, 1) if precision == "year" else date.fromisoformat(first)
        end = date(int(last), 12, 31) if precision == "year" else date.fromisoformat(last)
    except ValueError:
        return None, "invalid"
    if start > end:
        return None, "invalid"
    return {"start": start.isoformat(), "end": end.isoformat(), "precision": precision}, None


def timeline_data(snapshot: Snapshot, *, dossier_id: str | None = None) -> dict[str, Any]:
    """Project current claims without changing labels, records, caches or HEAD."""
    unavailable = {record.target_ref.id for record in snapshot.records.values() if isinstance(record, Tombstone)}
    dated: list[dict[str, Any]] = []
    unplaced: list[dict[str, Any]] = []
    for claim in snapshot.records.values():
        if not isinstance(claim, Claim) or claim.id in unavailable:
            continue
        if dossier_id and (claim.dossier_ref is None or claim.dossier_ref.id != dossier_id):
            continue
        entry: dict[str, Any] = {
            "claim_id": claim.id, "revision": claim.revision, "title": claim.title,
            "statement": claim.statement, "confidence": claim.confidence,
            "time_period": claim.scope.time_period, "place": claim.scope.place, "actors": claim.scope.actors,
            "dossier_id": claim.dossier_ref.id if claim.dossier_ref else None,
            "dossier_revision": claim.dossier_ref.revision if claim.dossier_ref else None,
        }
        period, reason = parse_period(claim.scope.time_period)
        if period is not None:
            entry["period"] = period
            dated.append(entry)
        else:
            entry["reason"] = reason
            unplaced.append(entry)
    dated.sort(key=lambda entry: (entry["period"]["start"], entry["period"]["end"], entry["title"].casefold(), entry["claim_id"]))
    unplaced.sort(key=lambda entry: (entry["title"].casefold(), entry["claim_id"]))
    return {"schema_version": "research-timeline-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "dated": dated, "unplaced": unplaced}
