"""Bounded human CLI views; archive data never becomes markup or terminal control."""

import html
import re
import sys
from typing import Any

from rich.console import Console

from ..format import safe_text as safe_text


def revision_write_summary(result: dict[str, Any], *, expected_revision: int) -> dict[str, Any]:
    """Project an existing write result without copying authored content or re-reading."""
    preview = result["schema_version"] == "research-revision-write-preview-local/1"
    record = result["candidate" if preview else "record"]
    changed = record["revision"] != expected_revision
    summary = {
        "schema_version": "research-revision-write-summary-local/1",
        **{key: result[key] for key in ("project_id", "snapshot", "kind", "record_id")},
        "dry_run": preview, "ready": True, "changed": changed,
        "base_revision": expected_revision,
        "change": record.get("change") if changed else None,
    }
    if preview:
        summary["candidate_revision"] = record["revision"]
        summary["changed_fields"] = [field["field"] for field in result["fields"]]
    else:
        summary["revision"] = record["revision"]
    if "warnings" in result:
        summary["warnings"] = result["warnings"]
    return summary


def revision_write_report(result: dict[str, Any]) -> str:
    """Describe a compact result without treating a preview as an accepted record."""
    unit = "revision" if result["kind"] == "dossier" else "version"
    if not result["changed"]:
        status = f"No changes · {unit} {result.get('candidate_revision', result.get('revision'))}"
    elif result["dry_run"]:
        status = f"Preview ready · would create {unit} {result['candidate_revision']}"
    else:
        status = f"Saved {unit} {result['revision']}"
    lines = [f"{status} · {safe_text(result['record_id'])}"]
    if result.get("changed_fields"):
        lines.append("Changed fields: " + ", ".join(safe_text(field) for field in result["changed_fields"]))
    if result.get("warnings"):
        lines.append("Warnings: " + safe_text(result["warnings"]))
    return "\n".join(lines) + "\n"


def _safe(value: Any, *, markdown: bool) -> str:
    text = safe_text(value)
    if markdown:
        text = re.sub(r"([\\`*_{}\[\]()#+!|~])", r"\\\1", html.escape(text, quote=False))
    return text


def geography_report(summary: dict[str, Any]) -> str:
    """Present the shared read-time geography summary without measuring geometry."""
    def distance_text(value: float) -> str:
        return "<0.01 km" if 0 < value < .01 else f"{value:.2f} km"

    lines = ["Places and routes: "
             f"{summary['located_feature_count']} located / {summary['feature_count']}; "
             f"{summary['unlocated_feature_count']} unplaced."]
    kinds = {"Point": "Point", "LineString": "Route", "Polygon": "Area", "unknown": "Unplaced"}
    for feature in summary["features"]:
        kind = kinds.get(feature["geometry_type"], "Unplaced")
        lines.append(f"- {feature['index'] + 1}. {safe_text(feature['label'])} — {kind}")
        context = []
        for key, title in (("feature_type", "Type"), ("time_period", "Period"), ("transport", "Transport")):
            if feature.get(key):
                context.append(f"{title}: {safe_text(feature[key])}")
        if feature.get("actors"):
            context.append("Actors: " + ", ".join(safe_text(actor) for actor in feature["actors"]))
        if context:
            lines.append("  " + "; ".join(context))
        if feature.get("waypoint_labels"):
            lines.append("  Waypoints: " + " → ".join(safe_text(item) for item in feature["waypoint_labels"]))
        distance = feature.get("route_length_km")
        if distance is not None:
            lines.append(f"  Positions: {feature['position_count']}; segments: {feature['segment_count']}; "
                         f"approximate vertex-chain distance: {distance_text(distance)}")
    if summary.get("route_length_km") is not None:
        lines.append(f"Total approximate vertex-chain distance: {distance_text(summary['route_length_km'])}.")
        lines.append("Method: shortest great-circle segments on a sphere between supplied coordinates; "
                     "not road routing or travel time; elevation is excluded.")
    lines.append("Authored locations and context; not geographic or historical verification.")
    return "\n".join(lines)


def manuscript_report(command: str, result: dict[str, Any], *, table: bool) -> str:
    """Render manuscript operations with the same safe terminal text boundary."""
    headers: tuple[str, ...]
    rows: list[list[Any]]
    if command == "find-anchor":
        heading = f"Manuscript anchor: {result['source_path']}"
        headers = ("Line", "Quote")
        rows = [[result["start_line"], result["quote"]]]
    elif command == "reconcile-manuscript" and "record" not in result:
        heading = "Manuscript reconciliation: " + ("preview" if result["dry_run"] else "applied")
        headers = ("Link ID", "Revision", "State", "Details")
        rows = [[r["link_id"], r["revision"], r["anchor_state"],
                 f"{r['old_quote']} → {r['new_quote']}" if "new_quote" in r else r.get("candidate_lines", [])]
                for r in result.get("candidates", [])]
        rows.extend([r["link_id"], r["revision"], "accepted", ""] for r in result.get("accepted", []))
        rows.extend([r["link_id"], "-", "skipped", r["reason"]] for r in result.get("skipped", []))
    else:
        if "record" in result:
            record = result["record"]
            links = [{"link_id": result["link_id"], "revision": record["revision"],
                      "anchor": record["anchor"], "state": record["state"],
                      "claim_id": record["claim_ref"]["id"]}]
        else:
            links = result["links"]
        if command == "review-manuscript":
            heading = f"Manuscript comparison: {result['source_path']} ({result['review_needed_count']} candidates)"
        else:
            heading = "Manuscript associations"
        headers = ("Link ID", "Revision", "Line", "State", "Review", "Flags", "Claim", "Quote")
        rows = []
        for link in links:
            anchor = link.get("anchor") or {}
            state = link.get("anchor_state", link["state"])
            rows.append([link["link_id"], link["revision"],
                         link.get("resolved_start_line") or anchor.get("start_line", "-"),
                         getattr(state, "value", state),
                         "[COMPARE]" if link.get("review_needed") else "-",
                         ", ".join(link.get("flags") or []) or "-",
                         link.get("claim_title") or link.get("claim_id", "-"), anchor.get("quote", "")])
    lines = [_safe(heading, markdown=False), ""]
    cells = [[_safe(getattr(value, "value", value), markdown=False) for value in row] for row in rows]
    if table:
        widths = [max([len(header), *(len(row[i]) for row in cells)]) for i, header in enumerate(headers)]
        lines.append("  ".join(header.ljust(width) for header, width in zip(headers, widths, strict=True)))
        lines.append("  ".join("-" * width for width in widths))
        lines.extend("  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)).rstrip()
                     for row in cells)
    else:
        lines.extend("- " + "; ".join(f"{header}: {value}" for header, value in zip(headers, row, strict=True))
                     for row in cells)
    lines.append(f"{len(rows)} item(s).")
    return "\n".join(lines).rstrip() + "\n"


def source_report(result: dict[str, Any], *, markdown: bool, limit: int, offset: int) -> str:
    """Summarize an active-source list or detail without exposing retained text."""
    lines: list[str] = []

    def heading(title: str) -> None:
        lines.extend([f"## {title}" if markdown else title, ""])

    def field(label: str, value: Any) -> None:
        prefix = "- " if markdown else "  "
        lines.append(f"{prefix}{label}: {_safe(value, markdown=markdown)}")

    sources = result.get("sources")
    if sources is None:
        selected = [result]
        heading("Source details")
    else:
        total = len(sources)
        selected = sources[offset:offset + limit]
        heading(f"Sources: {_safe(result.get('project_title', ''), markdown=markdown)}")
        if selected:
            lines.append(f"Showing {offset + 1}–{offset + len(selected)} of {total} active sources (offset {offset}; limit {limit}).")
        elif not total:
            lines.append("No active sources.")
        else:
            lines.append(f"No sources at offset {offset}; {total} active sources in total.")
        lines.append("")

    for index, source in enumerate(selected, offset + 1):
        heading(f"{index}. {_safe(source['title'], markdown=markdown)}")
        field("Source ID", source["id"])
        field("Status", "Active; retained source, not a verified claim")
        field("Language", source["language"])
        field("Version ID", source["version_id"])
        field("Capture sequence", source["sequence"])
        passages = source["passages"]
        field("Passages", len(passages) if isinstance(passages, list) else passages)
        field("Tags", ", ".join(source.get("tags", [])) or "None")
        field("Origin URL", source.get("context", {}).get("origin_url") or "Not recorded")
        lines.append("")

    if sources is not None and selected and offset + len(selected) < len(sources):
        lines.append(f"Next page: repeat this command with --offset {offset + len(selected)} --limit {limit}.")
    return "\n".join(lines).rstrip() + "\n"


def audit_report(result: dict[str, Any], *, markdown: bool) -> str:
    """Show audit scope, capacity and bounded findings without changing status."""
    status = "PASSED" if result["ok"] else "FAILED"
    heading = f"Research integrity audit: {status}"
    lines = [f"## {heading}" if markdown else heading, ""]
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])
    capacity = result.get("manifest_capacity", {})
    used, maximum, remaining = (
        capacity.get(key) if capacity.get(key) is not None else "Unavailable"
        for key in ("entries_used", "entries_max", "entries_remaining")
    )
    checked_manifests = result.get("manifest_history_checked")
    for label, value in (
        ("Checked revision objects", result["records"]),
        ("Manifest entries", f"{used} / {maximum} used; {remaining} remaining"),
        ("Checked manifests", checked_manifests if checked_manifests is not None else "Unavailable"),
        ("Snapshot", result.get("snapshot") or "Unavailable"),
        ("Scope", result["scope"]),
        ("Findings", len(errors)),
        ("Warnings", len(warnings)),
    ):
        lines.append(f"{'- ' if markdown else ''}{label}: {_safe(value, markdown=markdown)}")
    if errors:
        lines.append("")
        for index, error in enumerate(errors[:20], 1):
            message = str(error)
            if len(message) > 1000:
                message = message[:1000] + "… (truncated; use --format json for full details)"
            lines.append(f"{index}. {_safe(message, markdown=markdown)}")
        if len(errors) > 20:
            lines.append(f"{len(errors) - 20} further findings omitted; use --format json for full details.")
        lines.extend([
            "", "Next: check the reported record or path and its permissions. Restore missing or modified bytes from a verified backup, then repeat the audit.",
            "Do not edit archive records to silence an integrity failure.",
        ])
    if warnings:
        lines.extend(["", "### Advisory warnings" if markdown else "Advisory warnings", ""])
        for index, warning in enumerate(warnings[:20], 1):
            message = str(warning)
            if len(message) > 1000:
                message = message[:1000] + "… (truncated; use --format json for full details)"
            lines.append(f"{index}. {_safe(message, markdown=markdown)}")
        if len(warnings) > 20:
            lines.append(f"{len(warnings) - 20} further warnings omitted; use --format json for full details.")
    return "\n".join(lines) + "\n"


def timeline_report(result: dict[str, Any], *, markdown: bool) -> str:
    """Render recorded periods and unplaced claims without inventing chronology."""
    states = {"hypothetical": "Author assumption", "evidenced": "With evidence", "disputed": "Disputed"}
    lines = ["## Claim chronology" if markdown else "Claim chronology", "",
             "Placement follows recorded periods. Causal validity needs author review.", ""]
    for label, entries in (("Recorded periods", result["dated"]), ("Periods to clarify", result["unplaced"])):
        lines.extend([f"### {label}" if markdown else label, ""])
        if not entries:
            lines.extend(["No claims in this group.", ""])
        for entry in entries:
            period = _safe(entry.get("time_period") or "No period recorded", markdown=markdown)
            title = _safe(entry["title"], markdown=markdown)
            state = states.get(entry["confidence"], entry["confidence"])
            lines.append(f"- {period}: {title} ({state})")
            lines.append(f"  Claim: {_safe(entry['claim_id'], markdown=markdown)} · revision {entry['revision']}")
            if entry.get("reason"):
                lines.append("  Placement: " + _safe(entry["reason"], markdown=markdown))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def editorial_report(result: dict[str, Any], *, markdown: bool) -> str:
    """Summarize structural links without presenting candidates as contradictions."""
    reasons = {
        "decision_after_dossier": "Decision is newer than this dossier revision",
        "stale_dossier_pin": "Linked dossier revision is older than the current revision; it may be intentional",
        "stale_claim_pin": "Linked claim revision is older than the current revision; it may be intentional",
        "withdrawn_dossier": "Linked dossier has been withdrawn",
        "withdrawn_claim": "Linked claim has been withdrawn",
        "no_linked_dossier": "No explicitly linked dossier",
        "stale_author_acknowledgement": "Author acknowledgement refers to an earlier decision or dossier revision",
        "author_review_needed": "Author explicitly reopened review",
    }
    lines: list[str] = []

    def value(raw: Any) -> str:
        text = str(raw)
        if len(text) > 1000:
            text = text[:1000] + "… (truncated; use --format json for full details)"
        return _safe(text, markdown=markdown)

    def heading(title: str) -> None:
        lines.extend([f"## {title}" if markdown else title, ""])

    def field(label: str, raw: Any) -> None:
        lines.append(f"{'- ' if markdown else '  '}{label}: {value(raw)}")

    review = "candidates" in result
    heading("Editorial review candidates" if review else "Decision impact: explicit dossier links")
    lines.extend(["These are structural prompts for human review, not semantic contradictions or proof that a decision has been incorporated.", ""])
    field("Scope", result["scope"])
    field("Snapshot", result["snapshot"])
    if review:
        field("Decisions checked", result["decision_count"])
        field("Review candidates", result["candidate_count"])
        entries = result["candidates"]
        if not entries:
            lines.extend(["", "No structural review candidates were found."])
    else:
        decision = result["decision"]
        field("Decision", decision["title"])
        field("Decision ID", decision["id"])
        field("Decision revision", decision["revision"])
        entries = result["dossiers"]
        field("Linked dossiers", len(entries))
        if result["unlinked"]:
            lines.extend(["", "No explicitly linked dossiers; unrecorded relationships are outside this report."])
    lines.append("")
    for index, entry in enumerate(entries[:50], 1):
        heading(f"{index}. {value(entry['title'])}")
        if review:
            field("Decision ID", entry["decision_id"])
            field("Decision revision", entry["decision_revision"])
            field("Dossier", entry["dossier_title"] or "No explicitly linked dossier")
            field("Dossier ID", entry["dossier_id"] or "None")
        else:
            field("Dossier ID", entry["id"])
            for link in entry["links"][:20]:
                if link["via"] == "claim":
                    field("Association", f"Via claim {link['claim_id']} revision {link['claim_revision']} (current: {link['claim_current_revision']}); dossier pin {link['pinned_revision']}")
                else:
                    field("Association", f"Direct dossier link at revision {link['pinned_revision']}")
            if len(entry["links"]) > 20:
                field("Further associations", f"{len(entry['links']) - 20}; use --format json for all links")
        if entry["current_revision"] is not None:
            field("Current dossier revision", entry["current_revision"])
            field("Pinned dossier revisions", ", ".join(map(str, entry["pinned_revisions"])))
        if entry["sections"]:
            field("Sections to inspect", "; ".join(entry["sections"][:20]))
            if len(entry["sections"]) > 20:
                field("Further sections", f"{len(entry['sections']) - 20}; use --format json for all headings")
        acknowledgement = entry.get("acknowledgement")
        if acknowledgement:
            status = ("Author acknowledgement concerns earlier revisions" if not acknowledgement["current"]
                      else "Author marked applied to these revisions" if acknowledgement["status"] == "applied"
                      else "Author explicitly reopened review")
            field("Author acknowledgement", status)
            field("Acknowledged by", acknowledgement["actor"])
            if acknowledgement.get("note"):
                field("Author note", acknowledgement["note"])
        for flag in entry["flags"]:
            field("Review prompt", reasons.get(flag, flag))
        if not entry["flags"]:
            field("Review prompts", "None from the structural checks")
        lines.append("")
    if len(entries) > 50:
        lines.append(f"{len(entries) - 50} further entries omitted; use --format json for all results.")
    return "\n".join(lines).rstrip() + "\n"


def print_report(text: str, *, pager: bool) -> None:
    """Page only by explicit request with interactive input and output."""
    console = Console(file=sys.stdout, markup=False, highlight=False, force_terminal=False)
    if pager and sys.stdin.isatty() and sys.stdout.isatty():
        with console.pager(styles=False, links=False):
            console.print(text, end="", soft_wrap=True)
    else:
        console.print(text, end="", soft_wrap=True)

#: Record list envelopes: command -> (payload key, plural caption).
_RECORD_LISTS = {
    "dossier": ("dossiers", "dossier"),
    "claim": ("claims", "claim"),
    "decision": ("decisions", "decision"),
}
_RECORD_COLUMNS = (("id", "ID"), ("title", "Title"), ("revision", "Rev"), ("created_at", "Created"))


def record_list_report(command: str, result: dict[str, Any], *, markdown: bool = False) -> str | None:
    """Render a compact record list (ID, title, revision, date) for the terminal.

    Returns ``None`` when the response is not a list envelope, so the caller
    can point at ``--json`` instead of printing an empty table.
    """
    entry = _RECORD_LISTS.get(command)
    rows = result.get(entry[0]) if entry is not None and isinstance(result, dict) else None
    if entry is None or not isinstance(rows, list):
        return None
    caption = entry[1]

    def cell(row: Any, field: str) -> str:
        value = row.get(field, "") if isinstance(row, dict) else ""
        text = str(value).replace("|", "\\|")
        return text if field == "id" else text[:60]

    if markdown:
        lines = ["| " + " | ".join(name for _, name in _RECORD_COLUMNS) + " |",
                 "| " + " | ".join("---" for _ in _RECORD_COLUMNS) + " |"]
        lines.extend("| " + " | ".join(cell(row, field) for field, _ in _RECORD_COLUMNS) + " |"
                     for row in rows)
        return "\n".join(lines) + f"\n\n{len(rows)} {caption}(s)."

    widths = [max([len(name), *(len(cell(row, field)) for row in rows)])
              for field, name in _RECORD_COLUMNS]
    lines = ["  ".join(name.ljust(width) for (_, name), width in zip(_RECORD_COLUMNS, widths, strict=False)).rstrip(),
             "  ".join("-" * width for width in widths)]
    lines.extend("  ".join(cell(row, field).ljust(width)
                           for (field, _), width in zip(_RECORD_COLUMNS, widths, strict=False)).rstrip()
                 for row in rows)
    return "\n".join(lines) + f"\n{len(rows)} {caption}(s)."

