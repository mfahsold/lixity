"""Read-only chronology from explicit calendar labels, not inferred historical dates."""

import calendar
import re
from datetime import date
from typing import Any

from .models import Claim, Tombstone
from .repository import Snapshot

#: Recognized single values, most precise first: ISO day, ISO month, CE year.
_ENDPOINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}"), "day"),
    (re.compile(r"[0-9]{4}-[0-9]{2}"), "month"),
    (re.compile(r"[0-9]{4}"), "year"),
)

#: Range separators. A hyphen between two four-digit years is unambiguous
#: (`1929-1933`) and joins the typographic dash; ISO month/day hyphens are
#: never split. The remaining separators cannot appear inside an endpoint.
_RANGE_SPLIT = re.compile(
    r"\s+-\s+|\s*[\u2013\u2014/]\s*|\s*\.\.\s*|(?<=\d{4})[ \t]*-[ \t]*(?=\d{4})"
)

#: Example formats shown in creation warnings; mirror the usage documentation.
PERIOD_FORMATS = "1926, 1926-03, 1926-03-15 or 1924\u20131926 (also 1924-1926)"


class _Unrecognized(ValueError):
    """Label is not an explicit calendar value in the supported grammar."""


def _endpoint(value: str) -> tuple[date, date, str] | None:
    """Parse one calendar value; invalid calendar dates raise ``ValueError``."""
    for pattern, precision in _ENDPOINTS:
        if not pattern.fullmatch(value):
            continue
        if precision == "day":
            moment = date.fromisoformat(value)
            return moment, moment, precision
        if precision == "month":
            year, month = int(value[:4]), int(value[5:7])
            if not 1 <= month <= 12:
                raise ValueError(f"Month out of range: {value}")
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, 1), date(year, month, last_day), precision
        year = int(value)
        return date(year, 1, 1), date(year, 12, 31), precision
    return None


def _period(value: str) -> tuple[date, date, str]:
    """Resolve one label into start, end and precision, or raise for its reason."""
    single = _endpoint(value)
    if single is not None:
        return single
    parts = _RANGE_SPLIT.split(value)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise _Unrecognized(value)
    first, last = _endpoint(parts[0].strip()), _endpoint(parts[1].strip())
    if first is None or last is None or first[2] != last[2]:
        raise _Unrecognized(value)
    return first[0], last[1], first[2]


def parse_period(label: str | None) -> tuple[dict[str, str] | None, str | None]:
    """Place CE years, ISO months/dates and same-precision ranges; retain all other labels."""
    if not label or not label.strip():
        return None, "missing"
    try:
        start, end, precision = _period(label.strip())
    except _Unrecognized:
        return None, "unrecognized"
    except ValueError:
        return None, "invalid"
    if start > end:
        return None, "invalid"
    return {"start": start.isoformat(), "end": end.isoformat(), "precision": precision}, None


def period_warnings(label: str | None) -> list[str]:
    """Warn about a period that will not appear on the chronology; never blocks a write."""
    if not label or not label.strip():
        return []
    period, _reason = parse_period(label)
    if period is not None:
        return []
    return [
        f"Time period '{label.strip()}' is not placed in the chronology. "
        f"Use a four-digit year, YYYY-MM, an ISO date or a same-precision range "
        f"({PERIOD_FORMATS})."
    ]


def timeline_data(snapshot: Snapshot, *, dossier_id: str | None = None) -> dict[str, Any]:
    """Project current claims without changing labels, records, caches or HEAD."""
    unavailable = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone)
    }
    dated: list[dict[str, Any]] = []
    unplaced: list[dict[str, Any]] = []
    for claim in snapshot.records.values():
        if not isinstance(claim, Claim) or claim.id in unavailable:
            continue
        if dossier_id and (claim.dossier_ref is None or claim.dossier_ref.id != dossier_id):
            continue
        entry: dict[str, Any] = {
            "claim_id": claim.id,
            "revision": claim.revision,
            "title": claim.title,
            "statement": claim.statement,
            "confidence": claim.confidence,
            "time_period": claim.scope.time_period,
            "place": claim.scope.place,
            "actors": claim.scope.actors,
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
    dated.sort(
        key=lambda entry: (
            entry["period"]["start"],
            entry["period"]["end"],
            entry["title"].casefold(),
            entry["claim_id"],
        )
    )
    unplaced.sort(key=lambda entry: (entry["title"].casefold(), entry["claim_id"]))
    return {
        "schema_version": "research-timeline-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "dated": dated,
        "unplaced": unplaced,
    }
