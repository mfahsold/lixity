"""Bounded human CLI views; archive data never becomes markup or terminal control."""

import html
import re
import sys
from typing import Any

from rich.console import Console

from ..format import safe_text as safe_text


def _safe(value: Any, *, markdown: bool) -> str:
    text = safe_text(value)
    if markdown:
        text = re.sub(r"([\\`*_{}\[\]()#+!|~])", r"\\\1", html.escape(text, quote=False))
    return text


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
    """Show audit scope, totals and bounded failures without changing the result."""
    status = "PASSED" if result["ok"] else "FAILED"
    heading = f"Research integrity audit: {status}"
    lines = [f"## {heading}" if markdown else heading, ""]
    errors = result.get("errors", [])
    for label, value in (
        ("Checked records", result["records"]),
        ("Snapshot", result.get("snapshot") or "Unavailable"),
        ("Scope", result["scope"]),
        ("Findings", len(errors)),
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
    return "\n".join(lines) + "\n"


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
