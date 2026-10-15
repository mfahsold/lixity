"""Lazy research commands; explicit machine output and errors on stderr."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from .limits import MAX_IMAGE_BYTES

OUTPUT_FORMATS: dict[str, tuple[tuple[str, ...], str]] = {
    "sources": (("text", "md", "json"), "json"),
    "audit": (("text", "md", "json"), "json"),
    "decision-impact": (("text", "md", "json"), "text"),
    "review": (("text", "md", "json"), "text"),
    "compare": (("json", "md"), "json"),
    "matrix": (("md", "csv", "json"), "md"),
    "timeline": (("text", "md", "json"), "json"),
    "dossier": (("json", "table"), "json"),
    "claim": (("json", "table"), "json"),
    "decision": (("json", "table"), "json"),
}


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Offset must be zero or greater")
    return number


def configure(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="research_command", required=True)
    schema_command = commands.add_parser("schema", help="Export the experimental entity JSON schema")
    schema_command.set_defaults(cli_output_formats=("json",), cli_default_output="json",
                                cli_purpose="Export the experimental entity JSON schema")
    for name, help_text in (
        ("init", "Create an explicit local research project"),
        ("ingest", "Archive local UTF-8 text, PDF, PNG or JPEG; PDF scans require configured local OCR"),
        ("reindex", "Rebuild the disposable SQLite/FTS5 search index"),
        ("search", "Search the latest source versions with literal words"),
        ("cite", "Resolve an immutable source passage"),
        ("audit", "Check retained records, hashes and citation positions"),
        ("analyze", "Analyze verified source text and return metrics and style reference (JSON)"),
        ("dashboard", "Render local HTML source report"),
        ("compare", "Compare research source against manuscript (lexical overlap, keyness, register, chapter grounding)"),
        ("sources", "List active sources, versions, tags, and passage counts"),
        ("dossier", "Create, list or inspect research dossiers"),
        ("dossier-image", "Capture a local PNG/JPEG and attach it to a dossier atomically"),
        ("claim", "Create, list or revise research claims and hypotheses"),
        ("timeline", "Read a conservative chronology from recorded claim periods"),
        ("relate", "Record, inspect or revise an authored cause/effect assertion between claims"),
        ("link-evidence", "Create, inspect or revise a passage-to-claim evidence link"),
        ("link", "Create an evidence link with positional PASSAGE_ID CLAIM_ID"),
        ("link-manuscript", "Associate one reviewed manuscript quote with an exact claim revision (retention explicit)"),
        ("manuscript-links", "List saved manuscript quote-claim associations (read-only)"),
        ("review-manuscript", "Review saved associations against the current manuscript (read-only)"),
        ("find-anchor", "Resolve one displayed-text quote to exact anchor fields (read-only)"),
        ("reconcile-manuscript", "Preview or write re-pins for uniquely moved or adjusted manuscript anchors"),
        ("decision", "Create, list or revise author decisions and fact deviations"),
        ("decision-impact", "Inspect dossiers explicitly linked to an author decision; read-only"),
        ("review", "List structural editorial review candidates; read-only, not semantic judgment"),
        ("mark-applied", "Record an author acknowledgement for exact decision and dossier revisions"),
        ("reopen", "Explicitly reopen review of exact decision and dossier revisions"),
        ("revise-batch", "Preview related authored-record revisions, then apply them together explicitly"),
        ("withdraw", "Withdraw an archived source or version, marking citations and excluding from search"),
        ("purge", "Physically delete archived source records, passages, and unshared blobs"),
        ("export", "Export research store to verified archive (.tar.gz)"),
        ("restore", "Restore research store from verified archive (.tar.gz)"),
        ("zotero-backup", "Back up research and a closed Zotero data directory together"),
        ("zotero-restore", "Verify and restore a paired backup into a new directory"),
        ("zotero-export", "Export active captures and provenance for additive Zotero import"),
        ("zotero", "Preview a local Zotero library or item attachments (read-only)"),
        ("zotero-ingest", "Capture one selected local Zotero PDF/text attachment"),
        ("ocr-status", "Inspect runtime diagnostic status for OCR and PDF extraction"),
        ("matrix", "Export a structured claim-evidence-decision matrix (markdown, CSV, or JSON)"),
    ):
        command = commands.add_parser(name, help=help_text)
        formats, default_format = OUTPUT_FORMATS.get(name, (("html",), "html") if name == "dashboard"
                                                    else (("json",), "json"))
        command.set_defaults(cli_output_formats=formats, cli_default_output=default_format,
                             cli_purpose=help_text)
        if name in OUTPUT_FORMATS:
            output_group = command.add_mutually_exclusive_group()
            output_group.add_argument("--format", choices=formats, default=default_format,
                                      help=f"Output format (default: {default_format})")
            output_group.add_argument("--json", dest="format", action="store_const", const="json",
                                      help="Complete JSON output (alias for --format json)")
        if name in ("sources", "audit"):
            command.add_argument("--pager", action="store_true",
                                 help="Page text/Markdown only when input and output are interactive terminals")
        if name not in ("restore", "ocr-status", "zotero-restore"):
            command.add_argument(
                "--project", required=name == "init",
                help="Explicit project directory" if name == "init" else
                "Project directory (default: current directory, only with a valid initialized research archive)",
            )
        elif name == "ocr-status":
            command.add_argument("--project", help="Optional project directory")
            command.add_argument("--worker-cmd", help="Explicit OCR worker binary or command to inspect")
            command.add_argument("--probe", action="store_true", help="Execute a live test probe against the configured OCR worker")
        if name == "zotero-backup":
            command.add_argument("--data-dir", required=True)
            command.add_argument("--output", required=True)
            command.add_argument("--confirm-zotero-closed", action="store_true")
        elif name == "zotero-restore":
            command.add_argument("--from", dest="archive_source", required=True)
            command.add_argument("--to", dest="target_dir", required=True)
        if name == "zotero-export":
            command.add_argument("--output", required=True, help="New directory for RIS, files and provenance manifest")
            command.add_argument("--allow-retention", action="store_true")
            command.add_argument("--dry-run", action="store_true")
        if name in ("zotero", "zotero-ingest"):
            command.add_argument("--library", required=True, help="Explicit Zotero library: users/0 or groups/<id>")
            if name == "zotero":
                choice = command.add_mutually_exclusive_group()
                choice.add_argument("--query", default="")
                choice.add_argument("--item-key", help="Inspect an item and its attachments")
                choice.add_argument("--collections", action="store_true", help="List collections")
                command.add_argument("--collection-key", help="Restrict item search to this collection")
                command.add_argument("--limit", type=int, choices=range(1, 101), default=20, metavar="1..100")
                command.add_argument("--start", type=int, default=0, help="Zero-based page offset")
            else:
                key_group = command.add_mutually_exclusive_group(required=True)
                key_group.add_argument("--attachment-key", nargs="+", help="One or more Zotero attachment keys")
                key_group.add_argument("--item-key", help="Zotero parent item key to ingest all eligible attachments")
                command.add_argument("--source-id", help="Explicitly refresh a matching prior capture (single attachment only)")
                command.add_argument("--expected-server-id", help="Require the previewed Zotero instance")
                command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
                command.add_argument("--allow-retention", action="store_true")
                command.add_argument("--dry-run", action="store_true")
                command.add_argument("--progress", action="store_true", help="Report real-time progress phases on stderr")
        if name in ("dossier", "claim", "link-evidence", "decision", "relate"):
            command.add_argument("--update", action="store_true", help="Revise the named record")
            command.add_argument("--prepare", action="store_true", help="Preview reconciliation with the current record; never writes")
            command.add_argument("--diff", action="store_true", help="Preview the change as a unified terminal diff; never writes")
            command.add_argument("--base-revision", type=int, help="Original revision of the draft being prepared")
            command.add_argument("--resolve", action="append", metavar="FIELD=current|mine",
                                 help="Explicit field choice for a --prepare conflict; repeat for each field")
            command.add_argument("--history", action="store_true", help="List immutable revisions")
            command.add_argument("--inspect", action="store_true", help="Inspect the latest record")
            command.add_argument("--revision", type=int, help="Inspect one historical revision")
            command.add_argument("--expected-snapshot", help="Optional strict archive digest; if omitted, update checks --expected-revision against the current record")
            command.add_argument("--expected-revision", type=int, help="Reviewed record revision required for an update; changed associations need explicit pins when snapshot is omitted")
            command.add_argument("--change-kind", choices=("correction", "supersession"), help="Reason category for an update (required with --update)")
            command.add_argument("--reason", help="Why this authored record is being revised")
            command.add_argument("--actor", default="local-author")
        if name in ("link-manuscript", "review-manuscript"):
            command.add_argument("--manuscript", required=True,
                                 help="Manuscript path inside the explicit project")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name == "link-manuscript":
            command.add_argument("--claim-id", required=True)
            command.add_argument("--claim-revision", type=int, required=True,
                                 help="Exact reviewed claim revision to pin")
            source_group = command.add_mutually_exclusive_group(required=True)
            source_group.add_argument("--selection",
                                      help="Selection JSON object (literal or local file) with start_line, "
                                           "end_line, paragraph_sha256, start, end, quote")
            source_group.add_argument("--quote",
                                      help="Displayed-text quote; resolved against the manuscript "
                                           "(combine with --line when the quote is ambiguous)")
            command.add_argument("--line", type=int,
                                 help="Restrict a --quote resolution to the paragraph containing this source line")
            command.add_argument("--expected-snapshot",
                                 help="Optional strict archive digest; the current snapshot is used when omitted")
            command.add_argument("--expected-source-sha256",
                                 help="Optional strict source digest; the current file bytes are used when omitted")
            command.add_argument("--allow-retention", action="store_true",
                                 help="Confirm permission to retain the local quote (required)")
            command.add_argument("--note")
            command.add_argument("--actor", default="local-author")
        if name == "manuscript-links":
            command.add_argument("--claim-id", help="Only associations of this claim")
            command.add_argument("--include-retracted", action="store_true")
        if name == "find-anchor":
            command.add_argument("--manuscript", required=True,
                                 help="Manuscript path inside the explicit project")
            command.add_argument("--query", required=True,
                                 help="Exact displayed-text quote (inline Markdown markers removed)")
            command.add_argument("--line", type=int,
                                 help="Restrict the search to the paragraph containing this source line")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name == "reconcile-manuscript":
            command.add_argument("--manuscript", required=True,
                                 help="Manuscript path inside the explicit project")
            command.add_argument("--link-id", help="Only this association (default: every uniquely resolvable association)")
            command.add_argument("--accept-moved", action="store_true",
                                 help="Accept uniquely resolvable anchors (moved or adjusted paragraphs); "
                                      "without this flag the command only previews")
            command.add_argument("--update-sha", action="store_true",
                                 help="Accepted for compatibility; the current file digest is always re-pinned")
            command.add_argument("--expected-snapshot",
                                 help="Optional strict archive digest for the initial review")
            command.add_argument("--expected-source-sha256",
                                 help="Optional strict source digest; the current file bytes are used when omitted")
            command.add_argument("--actor", default="local-author")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name in ("dossier", "claim", "decision", "sources"):
            command.add_argument("action", nargs="?", choices=("list",), metavar="list",
                                 help="Explicit list verb; listing is also the default without a record ID")
        if name == "init":
            command.add_argument("--title", required=True)
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"), default="en")
            command.add_argument("--actor", default="local-author")
        elif name == "ingest":
            command.add_argument("--file", nargs="+", help="Path(s) to local UTF-8 text or PDF file(s); required unless resuming or discarding")
            command.add_argument("--title")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
            command.add_argument("--source-id", help="Refresh this source without invalidating old citations")
            command.add_argument("--actor", help="Capture actor (default: local-author; resume retains the checkpoint actor)")
            command.add_argument("--allow-retention", action="store_true", help="Confirm permission to retain a local copy, not to redistribute it")
            command.add_argument("--dry-run", action="store_true", help="Validate and preview; do not write")
            command.add_argument("--context", help="Source criticism JSON object or path to its JSON file")
            command.add_argument("--origin-url", help="Original HTTP(S) source URL (metadata only; never fetched)")
            command.add_argument("--progress", action="store_true", help="Report real-time progress phases on stderr")
            command.add_argument("--fallback", "--allow-fallback", dest="fallback", action="store_true", help="Allow fallback to native PDF text layer if OCR worker fails or times out")
            checkpoint_group = command.add_mutually_exclusive_group()
            checkpoint_group.add_argument("--checkpoint", metavar="PATH", help="Opt-in .json checkpoint under the project's .lixity/research/imports directory")
            checkpoint_group.add_argument("--discard-checkpoint", metavar="PATH", help="Remove checkpoint preparation without changing accepted research records")
            command.add_argument("--resume", action="store_true", help="Resume the named checkpoint; files and omitted settings come from it")
            command.add_argument("--expected-snapshot", help="Explicit current snapshot acknowledgement for a resumed checkpoint")
        elif name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--scope", choices=("sources", "dossiers", "claims", "decisions", "all"),
                                 default="sources", help="Search sources (default) or current authored records")
            command.add_argument("--limit", type=int, choices=range(1, 101), default=20, metavar="1..100")
            command.add_argument("--strict", action="store_true", help="Fail if search index is stale instead of refreshing automatically")
        elif name == "cite":
            selection = command.add_mutually_exclusive_group(required=True)
            selection.add_argument("--passage", help="Exact retained passage UUID (historical citations supported)")
            selection.add_argument("--query", help="Find a full source paragraph by literal keywords")
            command.add_argument("--pick", type=int, help="Choose numbered query match; requires --expected-snapshot")
            command.add_argument("--expected-snapshot", help="Snapshot displayed by citation search")
        elif name in ("analyze", "dashboard"):
            command.add_argument("--source-id", required=True, help="Source UUID")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--thresholds", help="Path to JSON file or JSON string of analysis thresholds")
        elif name == "compare":
            command.add_argument("--source-id", required=True, help="Source UUID")
            command.add_argument("--manuscript", required=True, help="Path to manuscript file")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"), help="Manuscript language override")
            command.add_argument("--top-n", type=int, default=20, help="Number of top terms to return (default: 20)")
            command.add_argument("--output", help="Optional output file destination")
        elif name == "sources":
            command.add_argument("--source-id", help="Optional source UUID to inspect passages")
            command.add_argument("--limit", type=int, choices=range(1, 101), metavar="1..100",
                                 help="Sources per human-output page (default: 50; JSON remains complete)")
            command.add_argument("--offset", type=_non_negative, default=0,
                                 help="Zero-based human-output page offset (default: 0)")
        elif name == "dossier":
            command.add_argument("--dossier-id", help="Dossier UUID to inspect")
            command.add_argument("--title", help="Title for new dossier")
            command.add_argument("--file", help="Path to markdown body file or raw text")
            command.add_argument("--tags", help="Comma-separated tags")
            command.add_argument("--evidence", help="Comma-separated passage UUIDs")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
            command.add_argument("--summary", action="store_true", help="Return metadata, section outline, and body excerpt without full text")
            command.add_argument("--section", help="Inspect or update only the named heading section")
            command.add_argument("--omit-citations", action="store_true", help="Omit resolved citations from output")
        elif name == "dossier-image":
            command.add_argument("--dossier-id", required=True, help="Dossier UUID to revise")
            command.add_argument("--file", required=True, help="Path to a local PNG or JPEG image")
            command.add_argument("--expected-snapshot", required=True, help="Snapshot digest from the reviewed dossier")
            command.add_argument("--expected-revision", required=True, type=int, help="Reviewed dossier revision")
            command.add_argument("--allow-retention", action="store_true",
                                 help="Confirm permission to retain a local copy, not to redistribute it")
            command.add_argument("--alt", default="", help="One-line image alternative text")
            command.add_argument("--caption", help="Optional image caption")
            command.add_argument("--section", help="Append inside an existing unique dossier heading")
            command.add_argument("--title", help="Title for the retained image source")
            command.add_argument("--context", help="Source criticism JSON object or path to its JSON file")
            command.add_argument("--origin-url", help="Original HTTP(S) source URL (metadata only; never fetched)")
            command.add_argument("--reason", help="Why the image is being attached (default: name the image)")
            command.add_argument("--change-kind", choices=("correction", "supersession"), default="supersession")
            command.add_argument("--actor", default="local-author")
        elif name == "claim":
            command.add_argument("--claim-id", help="Claim UUID to inspect")
            command.add_argument("--title", help="Title for new claim")
            command.add_argument("--statement", help="Full factual statement or hypothesis")
            command.add_argument("--confidence", choices=("hypothetical", "evidenced", "disputed"))
            command.add_argument("--time-period", help="Temporal scope")
            command.add_argument("--place", help="Geographic scope")
            command.add_argument("--actors", help="Comma-separated key historical actors or entities")
            command.add_argument("--dossier-id", help="Optional associated dossier UUID")
            command.add_argument("--dossier-revision", type=int, help="Explicit dossier revision to pin on update")
            command.add_argument("--tags", help="Comma-separated tags")
        elif name == "timeline":
            command.add_argument("--dossier-id", help="Limit chronology to claims associated with this dossier")
        elif name == "relate":
            command.add_argument("from_claim_id", nargs="?", metavar="FROM_CLAIM", help="Cause claim UUID; omit both endpoints to list")
            command.add_argument("to_claim_id", nargs="?", metavar="TO_CLAIM", help="Outcome claim UUID")
            command.add_argument("--relation-id", help="Authored relationship UUID to inspect or revise")
            command.add_argument("--claim-id", help="List relationships touching this claim")
            command.add_argument("--include-retracted", action="store_true", help="Include withdrawn author interpretations in the list")
            command.add_argument("--from-claim-revision", type=int, help="Exact cause claim revision to pin")
            command.add_argument("--to-claim-revision", type=int, help="Exact outcome claim revision to pin")
            command.add_argument("--relation", choices=("causes", "results_in"), help="Author assertion; results_in is an alias for causes")
            command.add_argument("--rationale", help="Why the author proposes this connection")
            command.add_argument("--state", choices=("active", "retracted"), help="Explicit state change on an authored revision")
        elif name == "link-evidence":
            command.add_argument("--evidence-link-id", help="Evidence-link UUID to inspect or revise")
            command.add_argument("--claim-id", help="Claim UUID")
            command.add_argument("--claim-revision", type=int, help="Explicit claim revision to pin on update")
            command.add_argument("--passage-id", help="Passage citation UUID")
            command.add_argument("--relation", choices=("supports", "contradicts", "qualifies", "contextualizes"))
            command.add_argument("--rationale", help="Reviewer rationale for link")
            command.add_argument("--reviewer", help="Reviewer identifier")
        elif name == "link":
            command.add_argument("passage_id", metavar="PASSAGE_ID", help="Complete passage UUID URN from search or cite")
            command.add_argument("claim_id", metavar="CLAIM_ID", help="Complete claim UUID URN from the claim list")
            command.add_argument("--relation", choices=("supports", "contradicts", "qualifies", "contextualizes"),
                                 help="Evidence relation (default: supports)")
            command.add_argument("--rationale", help="Reviewer rationale for link")
            command.add_argument("--reviewer", help="Reviewer identifier (default: author)")
            command.add_argument("--actor", default="local-author")
        elif name == "decision":
            command.add_argument("--decision-id", help="Decision UUID to inspect or revise")
            command.add_argument("--title", help="Title for new author decision")
            command.add_argument("--rationale", help="Artistic or historical rationale")
            command.add_argument("--claim-id", help="Optional claim UUID being decided upon")
            command.add_argument("--claim-revision", type=int, help="Explicit claim revision to pin on update")
            command.add_argument("--dossier-id", help="Associated dossier UUID")
            command.add_argument("--dossiers", help="Comma-separated dossier UUIDs impacted by this decision")
            command.add_argument("--dossier-revisions", help="JSON map of selected dossier UUIDs to explicit revisions on update or preview")
            command.add_argument("--deviation-from-fact", action=argparse.BooleanOptionalAction,
                                 default=None, help="Set or clear intentional deviation from historical evidence")
            command.add_argument("--impact-on-plot", help="Description of plot or worldbuilding impact")
        elif name == "decision-impact":
            command.add_argument("--decision-id", required=True, help="Decision UUID")
        elif name in ("mark-applied", "reopen"):
            command.add_argument("--decision-id", required=True)
            command.add_argument("--dossier-id", required=True)
            command.add_argument("--expected-snapshot", required=True)
            command.add_argument("--expected-decision-revision", type=int, required=True)
            command.add_argument("--expected-dossier-revision", type=int, required=True)
            command.add_argument("--note", help="Optional author note; not independent verification")
            command.add_argument("--actor", default="local-author")
        elif name == "revise-batch":
            command.add_argument("--file", required=True, help="UTF-8 JSON operations list or saved batch preview")
            command.add_argument("--apply", action="store_true", help="Apply all reviewed revisions in one commit")
            command.add_argument("--expected-snapshot", help="Snapshot digest from the preview, required with --apply")
            command.add_argument("--actor", default="local-author")
        elif name in ("withdraw", "purge"):
            command.add_argument("--source-id", required=True, help="Source UUID")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--reason", default="Withdrawn by user" if name == "withdraw" else "Purged by user", help="Reason for action")
            command.add_argument("--actor", default="local-author")
            if name == "purge":
                command.add_argument("--dry-run", action="store_true", help="Preview records, passages and blobs to be removed without deleting")
        elif name == "export":
            command.add_argument("--output", required=True, help="Destination .tar.gz archive path")
        elif name == "restore":
            command.add_argument("--from", dest="archive_source", required=True, help="Source .tar.gz archive path")
            command.add_argument("--to", dest="target_dir", required=True, help="Target project directory")
        elif name == "matrix":
            command.add_argument("--output", help="Optional output file destination")


def command_metadata() -> list[dict[str, Any]]:
    """Describe stdout formats and switches from the configured command parsers."""
    parser = argparse.ArgumentParser(add_help=False)
    configure(parser)
    commands = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    return [{"name": name, "purpose": command.get_default("cli_purpose"),
             "output_formats": list(command.get_default("cli_output_formats")),
             "default_output": command.get_default("cli_default_output"),
             "json_flag": "--json" if "--json" in command._option_string_actions else None}
            for name, command in commands.choices.items()]


def _reconcile_outcome(project: str, manuscript: str, row: dict[str, Any], source_sha256: str,
                       actor: str, language: str | None) -> dict[str, Any]:
    """Re-pin one moved row, reporting a conflict instead of aborting the batch."""
    from . import api
    from .repository import Repository, ResearchConflictError, ResearchError

    try:
        current = Repository(project).snapshot()
        single = api.reanchor_manuscript_link(
            project, manuscript, row["link_id"],
            expected_project_id=current.project.id, expected_snapshot=current.digest,
            expected_revision=row["revision"], expected_source_sha256=source_sha256,
            actor=actor, language=language)
    except (ResearchError, ResearchConflictError, OSError, ValueError) as error:
        return {"ok": False, "link_id": row["link_id"], "reason": str(error)}
    return {"ok": True, "link_id": single["link_id"], "revision": single["record"]["revision"]}


def _json_object(value: str, what: str) -> dict[str, Any]:
    """Read a JSON object from an inline value or a local file."""
    from .repository import ResearchError

    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8") if path.is_file() else value)
    if not isinstance(payload, dict):
        raise ResearchError(f"{what} must be a JSON object")
    return payload


def _source_context(value: str | None) -> dict[str, Any] | None:
    """Read a source criticism JSON object from an inline value or local file."""
    if value is None:
        return None
    return _json_object(value, "Source context")


def _revision_changes(args: argparse.Namespace) -> dict[str, Any]:
    """Collect only flags supplied for an authored-record update."""
    kind = args.research_command
    fields = {
        "dossier": ("title", "language", "tags", "evidence"),
        "claim": ("title", "statement", "confidence", "time_period", "place", "actors", "dossier_id", "dossier_revision", "tags"),
        "link-evidence": ("claim_id", "claim_revision", "passage_id", "relation", "rationale", "reviewer"),
        "decision": ("title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot"),
        "relate": ("from_claim_id", "to_claim_id", "from_claim_revision", "to_claim_revision", "relation", "state", "rationale"),
    }[kind]
    changes: dict[str, Any] = {}
    for field in fields:
        value = getattr(args, field)
        if value is None:
            continue
        key = "evidence_ids" if field == "evidence" else field
        if field in ("tags", "evidence", "actors"):
            value = [item.strip() for item in value.split(",") if item.strip()]
        elif field in ("time_period", "place", "dossier_id", "claim_id", "impact_on_plot") or (
            field == "rationale" and kind in ("link-evidence", "relate")
        ):
            value = value or None
        changes[key] = value
    if kind == "decision":
        dossier_ids = []
        if getattr(args, "dossier_id", None):
            dossier_ids.append(args.dossier_id.strip())
        if getattr(args, "dossiers", None):
            dossier_ids.extend([d.strip() for d in args.dossiers.split(",") if d.strip()])
        if dossier_ids:
            changes["dossier_ids"] = list(dict.fromkeys(dossier_ids))
        if getattr(args, "dossier_revisions", None) is not None:
            changes["dossier_revisions"] = json.loads(args.dossier_revisions)
    if kind == "dossier" and args.file is not None:
        body_path = Path(args.file)
        new_content = body_path.read_text(encoding="utf-8") if body_path.is_file() else args.file
        if getattr(args, "section", None):
            from . import api
            record_id = getattr(args, "dossier_id", None)
            if record_id:
                if getattr(args, "prepare", False):
                    base = api.get_record(args.project, "dossier", record_id, revision=args.base_revision)
                    original_body = base["record"]["body"]
                else:
                    original_body = api.get_dossier(args.project, record_id)["body"]
                changes["body"] = api.update_section(original_body, args.section, new_content)
            else:
                changes["body"] = new_content
        else:
            changes["body"] = new_content
    elif kind == "dossier" and getattr(args, "section", None) and (getattr(args, "update", False) or getattr(args, "prepare", False)):
        from .repository import ResearchError
        raise ResearchError("Updating a dossier section requires --file with new section content")
    return changes


def _revision_diff_text(kind: str, record_id: str, record: dict[str, Any], preview: dict[str, Any]) -> str:
    """Render a prepared update as a human unified diff; nothing is written."""
    import difflib

    color = sys.stdout.isatty()
    paints = (("+++", "\x1b[1m"), ("---", "\x1b[1m"), ("@@", "\x1b[36m"),
              ("+", "\x1b[32m"), ("-", "\x1b[31m"))

    def paint(line: str) -> str:
        if not color:
            return line
        for prefix, code in paints:
            if line.startswith(prefix):
                return f"{code}{line}\x1b[0m"
        return line

    changes = dict(preview.get("changes") or {})
    lines = [f"# {kind} {record_id} @r{record.get('revision')} – preview only, nothing written"]
    if "body" in changes:
        diff = difflib.unified_diff(
            str(record.get("body") or "").splitlines(),
            str(changes.pop("body")).splitlines(),
            fromfile=f"{kind} r{record.get('revision')}", tofile="draft", lineterm="",
        )
        lines.extend(diff)
    for field, value in changes.items():
        lines.append(f"--- {field}")
        lines.append(f"- {json.dumps(record.get(field), ensure_ascii=False, sort_keys=True)}")
        lines.append(f"+ {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    if len(lines) == 1:
        lines.append("(no changes)")
    if preview.get("conflicts"):
        lines.append(f"! {len(preview['conflicts'])} unresolved conflict(s); resolve with --prepare --resolve")
    return "\n".join(paint(line) for line in lines)


def _revision_action(args: argparse.Namespace) -> dict[str, Any] | None:
    """Dispatch explicit history, inspection and revision modes for existing commands."""
    from . import api
    from .repository import ResearchConflictError, ResearchError
    from .revisions import require_association_pins

    command = args.research_command
    kind = {"link-evidence": "evidence_link", "relate": "claim_relation"}.get(command, command)
    record_id = getattr(args, {
        "dossier": "dossier_id", "claim": "claim_id",
        "link-evidence": "evidence_link_id", "decision": "decision_id",
        "relate": "relation_id",
    }[command])
    prepare = getattr(args, "prepare", False)
    if not prepare and (getattr(args, "base_revision", None) is not None or getattr(args, "resolve", None)):
        raise ResearchError("--base-revision and --resolve require --prepare")
    association_revision = getattr(args, "dossier_revision", None) if command == "claim" else getattr(args, "claim_revision", None)
    if (association_revision is not None or getattr(args, "dossier_revisions", None) is not None) and not (args.update or prepare or getattr(args, "diff", False)):
        raise ResearchError("An explicit associated revision requires --update, --prepare or --diff; omit it to create a new record")
    if getattr(args, "action", None) == "list":
        if record_id or args.update or prepare or getattr(args, "diff", False) or args.history or args.inspect or args.revision is not None:
            raise ResearchError("The list verb takes no record ID or revision flags")
        return None
    requested = args.update or prepare or getattr(args, "diff", False) or args.history or args.inspect or args.revision is not None
    if command in ("link-evidence", "decision", "relate") and record_id:
        requested = True
    if not requested:
        return None
    if not record_id:
        raise ResearchError(f"{kind} ID is required for revision, history or inspection")
    if sum(bool(mode) for mode in (args.update, prepare, getattr(args, "diff", False), args.history, args.inspect, args.revision is not None)) > 1:
        raise ResearchError("Choose one of --update, --prepare, --diff, --history, --inspect or --revision")
    if prepare:
        if args.base_revision is None or args.base_revision < 1:
            raise ResearchError("--prepare requires a positive --base-revision")
        resolutions: dict[str, Literal["current", "mine"]] = {}
        for choice in args.resolve or []:
            field, separator, selection = choice.partition("=")
            if not field or not separator or selection not in ("current", "mine") or field in resolutions:
                raise ResearchError("Each --resolve must name one unique FIELD=current|mine choice")
            resolutions[field] = "current" if selection == "current" else "mine"
        changes = _revision_changes(args)
        if not changes:
            raise ResearchError("At least one changed field is required")
        return api.prepare_record_revision(args.project, kind, record_id,
                                           base_revision=args.base_revision, changes=changes, resolutions=resolutions)
    if getattr(args, "diff", False):
        changes = _revision_changes(args)
        if not changes:
            raise ResearchError("At least one changed field is required")
        current = api.get_record(args.project, kind, record_id)
        preview = api.prepare_record_revision(args.project, kind, record_id,
                                              base_revision=current["record"]["revision"],
                                              changes=changes, resolutions={})
        return {"schema_version": "research-revision-diff-local/1",
                "diff": _revision_diff_text(kind, record_id, current["record"], preview)}
    if args.update:
        if args.expected_revision is None or not args.change_kind or not args.reason:
            raise ResearchError("Updates require --expected-revision, --change-kind and --reason; run --inspect first to read the current revision")
        if args.expected_revision < 1:
            raise ResearchError("Expected revision must be positive")
        try:
            changes = _revision_changes(args)
            if not changes:
                raise ResearchError("At least one changed field is required")
            expected_snapshot = args.expected_snapshot
            if expected_snapshot is None:
                current = api.get_record(args.project, kind, record_id)
                if current["record"]["revision"] != args.expected_revision:
                    raise ResearchConflictError("Record revision changed; the reviewed revision is no longer current")
                require_association_pins(current["record"], changes)
                expected_snapshot = current["snapshot"]
            return api.revise_record(
                args.project, kind, record_id, changes=changes,
                expected_snapshot=expected_snapshot,
                expected_revision=args.expected_revision,
                change_kind=args.change_kind, reason=args.reason, actor=args.actor,
            )
        except ResearchConflictError as error:
            raise ResearchConflictError(f"{error}. Use --prepare --base-revision {args.expected_revision} "
                                        "with your draft fields to review current changes before saving") from None
    if args.history:
        return api.record_history(args.project, kind, record_id)
    if args.revision is not None and args.revision < 1:
        raise ResearchError("Revision must be positive")
    return api.get_record(args.project, kind, record_id, revision=args.revision)


def _current_project() -> str:
    """Use only a verified initialized archive rooted in the current directory."""
    from .repository import Repository, ResearchError

    try:
        root = Path.cwd()
        Repository(root).snapshot()
    except (OSError, ResearchError) as error:
        raise ResearchError(
            f"No valid initialized research project in the current directory: {error}. "
            "Use --project PATH or run from the project root"
        ) from error
    return str(root)


def run(args: argparse.Namespace) -> int:
    import sqlite3

    from . import api
    from .repository import ResearchError

    try:
        command = args.research_command
        if getattr(args, "action", None) == "list":
            creation = ("title", "statement", "rationale", "impact_on_plot", "file")
            if any(getattr(args, name, None) for name in creation):
                raise ResearchError("The list verb does not create records; drop the list verb or the creation fields")
        if (command not in ("schema", "init", "restore", "zotero-restore", "ocr-status")
                and args.project is None):
            args.project = _current_project()
        if command == "ingest":
            if (args.resume and not args.checkpoint) or (not args.file and not args.resume and not args.discard_checkpoint):
                print("[error] Supply --file, or --checkpoint PATH --resume, or --discard-checkpoint PATH", file=sys.stderr)
                return 2
            if args.expected_snapshot and not args.checkpoint:
                print("[error] --expected-snapshot requires --checkpoint", file=sys.stderr)
                return 2
            if args.discard_checkpoint and any((args.file, args.resume, args.dry_run, args.source_id, args.title,
                                                 args.language, args.context, args.origin_url, args.actor, args.fallback)):
                print("[error] --discard-checkpoint cannot be combined with capture or dry-run options", file=sys.stderr)
                return 2
        if command == "revise-batch" and bool(args.apply) != (args.expected_snapshot is not None):
            print("[error] --apply and --expected-snapshot must be supplied together; omit both for a read-only preview", file=sys.stderr)
            return 2
        if command in ("sources", "audit"):
            human = getattr(args, "format", "json") != "json"
            paginated = getattr(args, "limit", None) is not None or getattr(args, "offset", 0) != 0
            if not human and (getattr(args, "pager", False) or paginated):
                print("[error] --pager, --limit and --offset require --format text or md; JSON output remains complete", file=sys.stderr)
                return 2
            if paginated and getattr(args, "source_id", None):
                print("[error] --limit and --offset apply to source lists, not --source-id details", file=sys.stderr)
                return 2
        result: dict[str, Any]
        if command == "schema":
            result = api.schema()
        elif command == "init":
            result = api.init(args.project, title=args.title, language=args.language, actor=args.actor)
        elif command in ("mark-applied", "reopen"):
            result = api.acknowledge_decision(args.project, args.decision_id, args.dossier_id,
                expected_snapshot=args.expected_snapshot, expected_decision_revision=args.expected_decision_revision,
                expected_dossier_revision=args.expected_dossier_revision,
                status="applied" if command == "mark-applied" else "review_needed", note=args.note, actor=args.actor)
        elif command == "dossier-image":
            if not args.allow_retention:
                raise ResearchError("Explicit local retention permission is required (--allow-retention)")
            context = _source_context(args.context)
            image_path = Path(args.file)
            with image_path.open("rb") as image_file:
                content = image_file.read(MAX_IMAGE_BYTES + 1)
            result = api.attach_dossier_image(
                args.project, args.dossier_id, content, filename=image_path.name,
                expected_snapshot=args.expected_snapshot, expected_revision=args.expected_revision,
                allow_retention=args.allow_retention, alt=args.alt, caption=args.caption,
                section=args.section, title=args.title, context=context, origin_url=args.origin_url,
                reason=args.reason, change_kind=args.change_kind, actor=args.actor,
            )
        elif command == "ingest":
            context = _source_context(getattr(args, "context", None))
            start_time = time.monotonic()

            def _cli_progress(stage: str, message: str) -> None:
                if getattr(args, "progress", False) or sys.stderr.isatty():
                    elapsed = time.monotonic() - start_time
                    print(f"[{stage}] ({elapsed:.1f}s) {message}", file=sys.stderr, flush=True)

            files = args.file if isinstance(args.file, list) else [args.file] if args.file else None
            if args.discard_checkpoint:
                result = api.discard_ingest_checkpoint(args.project, checkpoint=args.discard_checkpoint)
            elif args.checkpoint:
                result = api.ingest_checkpoint(args.project, files, checkpoint=args.checkpoint, resume=args.resume,
                                               allow_retention=args.allow_retention, source_id=args.source_id,
                                               title=args.title, language=args.language, actor=args.actor,
                                               dry_run=args.dry_run, context=context, origin_url=args.origin_url,
                                               expected_snapshot=args.expected_snapshot,
                                               allow_fallback=True if args.fallback else None,
                                               progress_callback=_cli_progress)
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result["complete"] else 1
            elif files is not None and len(files) > 1:
                if args.source_id:
                    raise ResearchError("Cannot specify --source-id when ingesting multiple files")
                items: list[dict[str, Any]] = []
                succeeded = 0
                failed = 0
                def _ingest_one(file_item: Any) -> tuple[dict[str, Any], bool]:
                    try:
                        res = api.ingest(args.project, file_item, allow_retention=args.allow_retention,
                                         language=args.language, actor=args.actor or "local-author", dry_run=args.dry_run,
                                         context=context, origin_url=args.origin_url,
                                         allow_fallback=getattr(args, "fallback", False),
                                         progress_callback=_cli_progress)
                        return ({"file": str(file_item), "ok": True, "source_id": res["source_id"],
                                 "passages": res["passages"], "warnings": res.get("warnings", [])}, True)
                    except (ResearchError, OSError, ValueError) as exc:
                        return ({"file": str(file_item), "ok": False, "error": str(exc)}, False)

                for f in files:
                    item, ok = _ingest_one(f)
                    items.append(item)
                    if ok:
                        succeeded += 1
                    else:
                        failed += 1
                result = {
                    "schema_version": "research-batch-ingest-local/1",
                    "items": items,
                    "succeeded": succeeded,
                    "failed": failed,
                    "total": len(files),
                    "dry_run": args.dry_run,
                }
                sys.stdout.write(json.dumps(result, indent=2) + "\n")
                return 1 if failed > 0 else 0
            else:
                if files is None:
                    raise ResearchError("Source files are required")
                result = api.ingest(args.project, files[0], allow_retention=args.allow_retention,
                                    source_id=args.source_id, title=args.title, language=args.language,
                                    actor=args.actor or "local-author", dry_run=args.dry_run, context=context, origin_url=args.origin_url,
                                    allow_fallback=getattr(args, "fallback", False),
                                    progress_callback=_cli_progress)
        elif command in ("zotero-backup", "zotero-restore"):
            from . import zotero_backup
            if command == "zotero-backup":
                result = zotero_backup.backup(args.project, args.data_dir, args.output,
                                              confirm_closed=args.confirm_zotero_closed)
            else:
                result = zotero_backup.restore(args.archive_source, args.target_dir)
        elif command == "zotero-export":
            from . import zotero
            result = zotero.export_library(args.project, args.output, allow_retention=args.allow_retention,
                                            dry_run=args.dry_run)
        elif command in ("zotero", "zotero-ingest"):
            from . import zotero
            if command == "zotero" and args.collections:
                result = zotero.collections(args.project, library=args.library, start=args.start)
            elif command == "zotero":
                result = zotero.browse(args.project, library=args.library, query=args.query,
                                       item_key=args.item_key, limit=args.limit, start=args.start, collection_key=args.collection_key)
            else:
                start_time = time.monotonic()

                def _zotero_progress(stage: str, message: str) -> None:
                    if getattr(args, "progress", False) or sys.stderr.isatty():
                        elapsed = time.monotonic() - start_time
                        print(f"[{stage}] ({elapsed:.1f}s) {message}", file=sys.stderr, flush=True)

                if getattr(args, "item_key", None):
                    if getattr(args, "source_id", None):
                        raise ResearchError("--source-id cannot be used when ingesting an item with multiple attachments")
                    result = zotero.ingest_item(
                        args.project,
                        library=args.library,
                        item_key=args.item_key,
                        language=args.language,
                        expected_server_id=args.expected_server_id,
                        allow_retention=args.allow_retention,
                        dry_run=args.dry_run,
                        progress_callback=_zotero_progress,
                    )
                else:
                    att_keys = args.attachment_key if isinstance(args.attachment_key, list) else [args.attachment_key]
                    if len(att_keys) == 1:
                        result = zotero.ingest(
                            args.project,
                            library=args.library,
                            attachment_key=att_keys[0],
                            source_id=args.source_id,
                            language=args.language,
                            expected_server_id=args.expected_server_id,
                            allow_retention=args.allow_retention,
                            dry_run=args.dry_run,
                            progress_callback=_zotero_progress,
                        )
                    else:
                        if getattr(args, "source_id", None):
                            raise ResearchError("--source-id cannot be used when ingesting multiple attachments")
                        result = zotero.ingest_attachments(
                            args.project,
                            library=args.library,
                            attachment_keys=att_keys,
                            language=args.language,
                            expected_server_id=args.expected_server_id,
                            allow_retention=args.allow_retention,
                            dry_run=args.dry_run,
                            progress_callback=_zotero_progress,
                        )
        elif command == "manuscript-links":
            result = api.list_manuscript_links(args.project, claim_id=args.claim_id,
                                               include_retracted=args.include_retracted)
        elif command == "review-manuscript":
            result = api.review_manuscript_links(args.project, args.manuscript, language=args.language)
        elif command == "link-manuscript":
            if not args.allow_retention:
                raise ResearchError("Explicit local retention permission is required (--allow-retention)")
            from ..io import FileUtils
            from .manuscript import _source_path
            from .repository import Repository

            if args.selection is not None:
                selection_payload = _json_object(args.selection, "Selection")
            else:
                resolved = api.resolve_manuscript_anchor(args.project, args.manuscript, query=args.quote,
                                                         line=args.line, language=args.language)
                selection_payload = {key: resolved[key] for key in
                                     ("start_line", "end_line", "paragraph_sha256", "start", "end", "quote")}
            repository = Repository(args.project)
            snapshot = repository.snapshot()
            source_path, _relative = _source_path(repository, args.manuscript)
            source_sha256 = args.expected_source_sha256
            if source_sha256 is None:
                source_sha256 = FileUtils.read_source_snapshot(str(source_path))[1]
            result = api.link_manuscript_claim(
                args.project, args.manuscript, args.claim_id, claim_revision=args.claim_revision,
                selection=selection_payload, expected_project_id=snapshot.project.id,
                expected_snapshot=args.expected_snapshot or snapshot.digest,
                expected_source_sha256=source_sha256, allow_retention=True,
                note=args.note, actor=args.actor, language=args.language)
        elif command == "find-anchor":
            result = api.resolve_manuscript_anchor(args.project, args.manuscript, query=args.query,
                                                   line=args.line, language=args.language)
        elif command == "reconcile-manuscript":
            from ..io import FileUtils
            from .manuscript import _source_path
            from .repository import Repository, ResearchConflictError

            repository = Repository(args.project)
            link_review = api.review_manuscript_links(args.project, args.manuscript, language=args.language)
            if args.expected_snapshot is not None and link_review["snapshot"] != args.expected_snapshot:
                raise ResearchConflictError("Research snapshot changed; reload before reconciling")
            source_path, _relative = _source_path(repository, args.manuscript)
            source_sha256 = args.expected_source_sha256
            if source_sha256 is None:
                source_sha256 = FileUtils.read_source_snapshot(str(source_path))[1]
            if not args.accept_moved:
                movable = [row for row in link_review["links"]
                           if row["anchor_state"] in ("moved", "adjusted")
                           and (args.link_id is None or row["link_id"] == args.link_id)]
                result = {"schema_version": "research-manuscript-reconcile-local/1",
                          "project_id": link_review["project_id"], "snapshot": link_review["snapshot"],
                          "source_path": link_review["source_path"], "dry_run": True,
                          "candidates": [{"link_id": row["link_id"], "revision": row["revision"],
                                          "claim_title": row.get("claim_title"),
                                          "anchor_state": row["anchor_state"],
                                          "candidate_lines": row["candidate_lines"]}
                                         for row in movable]}
            elif args.link_id is not None:
                row = next((item for item in link_review["links"] if item["link_id"] == args.link_id), None)
                if row is None:
                    raise ResearchError("Unknown manuscript association for this manuscript")
                result = api.reanchor_manuscript_link(
                    args.project, args.manuscript, args.link_id,
                    expected_project_id=link_review["project_id"], expected_snapshot=link_review["snapshot"],
                    expected_revision=row["revision"], expected_source_sha256=source_sha256,
                    actor=args.actor, language=args.language)
            else:
                movable = [row for row in link_review["links"]
                           if row["anchor_state"] in ("moved", "adjusted")]
                accepted: list[dict[str, Any]] = []
                skipped: list[dict[str, str]] = []
                for row in movable:
                    outcome = _reconcile_outcome(args.project, args.manuscript, row, source_sha256,
                                                 args.actor, args.language)
                    if outcome["ok"]:
                        accepted.append({"link_id": outcome["link_id"], "revision": outcome["revision"]})
                    else:
                        skipped.append({"link_id": outcome["link_id"], "reason": outcome["reason"]})
                result = {"schema_version": "research-manuscript-reconcile-local/1",
                          "project_id": link_review["project_id"],
                          "snapshot": Repository(args.project).snapshot().digest,
                          "source_path": link_review["source_path"], "dry_run": False,
                          "accepted": accepted, "skipped": skipped}
        elif command == "reindex":
            result = api.reindex(args.project)
        elif command == "search":
            result = api.search(args.project, args.query, limit=args.limit, scope=args.scope, ensure_fresh=not args.strict)
            if not args.strict and any("refreshed" in w for w in result.get("warnings", [])):
                print("[search] Search index was refreshed to current snapshot (use --strict to require manual reindexing)", file=sys.stderr)
        elif command == "cite":
            if args.passage:
                if args.pick is not None or args.expected_snapshot is not None:
                    raise ResearchError("--pick and --expected-snapshot apply only to --query")
                result = api.cite(args.project, args.passage)
            else:
                from .citation_selection import resolve_query

                result, selected = resolve_query(args.project, args.query, pick=args.pick,
                                                  expected_snapshot=args.expected_snapshot)
                if not selected:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 1
        elif command == "analyze":
            thresholds: dict[str, Any] | None = None
            if getattr(args, "thresholds", None):
                thresholds_path = Path(args.thresholds)
                if thresholds_path.is_file():
                    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
                else:
                    thresholds = json.loads(args.thresholds)
            result = api.analyze_source(args.project, args.source_id, version_id=args.version_id, thresholds=thresholds)
        elif command == "dashboard":
            thresholds = None
            if getattr(args, "thresholds", None):
                thresholds_path = Path(args.thresholds)
                if thresholds_path.is_file():
                    thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
                else:
                    thresholds = json.loads(args.thresholds)
            html = api.source_dashboard(args.project, args.source_id, version_id=args.version_id, thresholds=thresholds)
            sys.stdout.write(html)
            return 0
        elif command == "compare":
            format_choice: Literal["json", "md"] = "md" if getattr(args, "format", "json") == "md" else "json"
            raw = api.compare_source(
                args.project,
                args.source_id,
                args.manuscript,
                version_id=args.version_id,
                language=getattr(args, "language", None),
                top_n=getattr(args, "top_n", 20),
                format=format_choice,
            )
            if getattr(args, "output", None):
                out_path = Path(args.output).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(raw, str):
                    out_path.write_text(raw, encoding="utf-8")
                else:
                    out_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
                result = {"ok": True, "output": str(out_path), "format": format_choice}
            else:
                if isinstance(raw, str):
                    print(raw, end="")
                    return 0
                result = raw
        elif command == "sources":
            if getattr(args, "source_id", None):
                result = api.get_source(args.project, args.source_id)
            else:
                result = api.list_sources(args.project)
        elif command == "decision-impact":
            result = api.decision_impact(args.project, args.decision_id)
        elif command == "review":
            result = api.editorial_review(args.project)
        elif command == "revise-batch":
            operations = json.loads(Path(args.file).read_text(encoding="utf-8"))
            if isinstance(operations, dict) and operations.get("schema_version") == "research-revision-batch-local/1":
                operations = operations.get("operations")
            if not isinstance(operations, list) or not all(isinstance(item, dict) for item in operations):
                raise ResearchError("Batch file must contain a JSON operations list or a research-revision-batch-local/1 preview")
            if args.apply:
                result = api.apply_record_revisions(args.project, operations,
                    expected_snapshot=args.expected_snapshot, actor=args.actor)
            else:
                result = api.prepare_record_revisions(args.project, operations, actor=args.actor)
        elif command in ("dossier", "claim", "link-evidence", "decision", "relate") and (
            revision_result := _revision_action(args)
        ) is not None:
            result = revision_result
        elif command == "dossier":
            if getattr(args, "dossier_id", None):
                result = api.get_dossier(
                    args.project,
                    args.dossier_id,
                    section=getattr(args, "section", None),
                    summary=getattr(args, "summary", False),
                    include_citations=not getattr(args, "omit_citations", False),
                )
            elif getattr(args, "title", None) and getattr(args, "file", None):
                body_path = Path(args.file)
                body = body_path.read_text(encoding="utf-8") if body_path.is_file() else args.file
                raw_tags = getattr(args, "tags", "") or ""
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                raw_ev = getattr(args, "evidence", "") or ""
                evidence = [e.strip() for e in raw_ev.split(",") if e.strip()]
                result = api.create_dossier(
                    args.project,
                    args.title,
                    body,
                    language=args.language or "en",
                    tags=tags,
                    evidence_ids=evidence,
                    actor=args.actor,
                )
            else:
                result = api.list_dossiers(args.project)
        elif command == "claim":
            if getattr(args, "claim_id", None) and not getattr(args, "title", None):
                result = api.list_evidence_links(args.project, claim_id=args.claim_id)
            elif getattr(args, "title", None) and getattr(args, "statement", None):
                raw_tags = getattr(args, "tags", "") or ""
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                raw_actors = getattr(args, "actors", "") or ""
                actors = [a.strip() for a in raw_actors.split(",") if a.strip()]
                result = api.create_claim(
                    args.project,
                    title=args.title,
                    statement=args.statement,
                    confidence=args.confidence or "hypothetical",
                    time_period=getattr(args, "time_period", None),
                    place=getattr(args, "place", None),
                    actors=actors,
                    dossier_id=getattr(args, "dossier_id", None),
                    tags=tags,
                    actor=args.actor,
                )
            else:
                result = api.list_claims(args.project, dossier_id=getattr(args, "dossier_id", None))
        elif command == "timeline":
            result = api.timeline(args.project, dossier_id=args.dossier_id)
        elif command == "relate":
            if bool(args.from_claim_id) != bool(args.to_claim_id):
                raise ResearchError("Supply both FROM_CLAIM and TO_CLAIM, or omit both to list relationships")
            if args.state is not None:
                raise ResearchError("--state requires a reviewed --update or --prepare")
            if args.from_claim_id:
                if args.claim_id or args.include_retracted:
                    raise ResearchError("--claim-id and --include-retracted select lists, not new relationships")
                result = api.create_claim_relation(args.project, args.from_claim_id, args.to_claim_id,
                    relation=args.relation or "causes", rationale=args.rationale,
                    from_claim_revision=args.from_claim_revision, to_claim_revision=args.to_claim_revision,
                    expected_snapshot=args.expected_snapshot, actor=args.actor)
            else:
                if any(value is not None for value in (args.relation, args.rationale, args.from_claim_revision,
                                                       args.to_claim_revision, args.expected_snapshot)):
                    raise ResearchError("Relationship creation options require both claim endpoints")
                result = api.list_claim_relations(args.project, claim_id=args.claim_id,
                                                  include_retracted=args.include_retracted)
        elif command in ("link-evidence", "link"):
            if not args.claim_id or not args.passage_id:
                names = "PASSAGE_ID and CLAIM_ID" if command == "link" else "--claim-id and --passage-id"
                raise ResearchError(f"{names} are required to create an evidence link")
            result = api.link_evidence(
                args.project,
                claim_id=args.claim_id,
                passage_id=args.passage_id,
                relation=args.relation or "supports",
                rationale=getattr(args, "rationale", None),
                reviewer=args.reviewer or "author",
                actor=args.actor,
            )
        elif command == "decision":
            if getattr(args, "title", None) and getattr(args, "rationale", None):
                dossier_ids = []
                if getattr(args, "dossier_id", None):
                    dossier_ids.append(args.dossier_id.strip())
                if getattr(args, "dossiers", None):
                    dossier_ids.extend([d.strip() for d in args.dossiers.split(",") if d.strip()])
                result = api.record_decision(
                    args.project,
                    title=args.title,
                    rationale=args.rationale,
                    claim_id=getattr(args, "claim_id", None),
                    deviation_from_fact=bool(args.deviation_from_fact),
                    impact_on_plot=getattr(args, "impact_on_plot", None),
                    dossier_ids=dossier_ids or None,
                    actor=args.actor,
                )
            else:
                result = api.list_decisions(args.project)
        elif command == "withdraw":
            result = api.withdraw(args.project, args.source_id, version_id=args.version_id,
                                  reason=args.reason, actor=args.actor)
        elif command == "purge":
            result = api.purge(args.project, args.source_id, version_id=args.version_id,
                               reason=args.reason, actor=args.actor, dry_run=args.dry_run)
        elif command == "export":
            result = api.export_archive(args.project, args.output)
        elif command == "restore":
            result = api.restore_archive(args.archive_source, args.target_dir)
        elif command == "ocr-status":
            result = api.ocr_status(getattr(args, "worker_cmd", None), probe=getattr(args, "probe", False))
        elif command == "matrix":
            matrix = api.claim_matrix_data(args.project)
            rendered = None if args.format == "json" else api.render_claim_matrix(matrix, format=args.format)
            payload_text = rendered if rendered is not None else json.dumps(matrix, ensure_ascii=False, indent=2)
            if getattr(args, "output", None):
                out_path = Path(args.output).expanduser().resolve()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(payload_text, encoding="utf-8")
                result = {"ok": True, "output": str(out_path), "format": args.format}
            elif rendered is not None:
                print(rendered, end="")
                return 0
            else:
                result = matrix
        else:
            result = api.audit(args.project)
        if command in ("decision-impact", "review") and args.format != "json":
            from .presentation import editorial_report, print_report

            print_report(editorial_report(result, markdown=args.format == "md"), pager=False)
            return 0
        if command == "timeline" and args.format != "json":
            from .presentation import print_report, timeline_report

            print_report(timeline_report(result, markdown=args.format == "md"), pager=False)
            return 0
        if command in ("sources", "audit") and getattr(args, "format", "json") != "json":
            from .presentation import audit_report, print_report, source_report

            markdown = args.format == "md"
            if command == "sources":
                report = source_report(result, markdown=markdown, limit=args.limit or 50, offset=args.offset)
            else:
                report = audit_report(result, markdown=markdown)
            print_report(report, pager=args.pager)
            return 1 if result.get("ok") is False else 0
        if command in ("dossier", "claim", "decision") and getattr(args, "format", "json") == "table":
            from .presentation import record_list_report

            table = record_list_report(command, result)
            if table is None:
                print("[error] --format table renders the list view; omit record IDs "
                      "and use --json for a single record", file=sys.stderr)
                return 2
            print(table)
            return 0
        if isinstance(result, dict) and result.get("schema_version") == "research-revision-diff-local/1":
            print(result["diff"])
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("ok") is False else 0
    except ResearchError as error:
        print(f"[error] {error}", file=sys.stderr)
    except (OSError, ValidationError, UnicodeError, sqlite3.Error, ValueError):
        print("[error] Research operation failed; check paths, permissions, schema and storage integrity", file=sys.stderr)
    return 1
