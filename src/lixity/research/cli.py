"""Lazy research commands; explicit machine output and errors on stderr."""

import argparse
import json
import re
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from .limits import MAX_IMAGE_BYTES, MAX_RESEARCH_OBJECT_BYTES

OUTPUT_FORMATS: dict[str, tuple[tuple[str, ...], str]] = {
    "sources": (("text", "md", "json"), "json"),
    "audit": (("text", "md", "json"), "json"),
    "decision-impact": (("text", "md", "json"), "text"),
    "review": (("text", "md", "json"), "text"),
    "compare": (("json", "md"), "json"),
    "matrix": (("md", "csv", "json"), "md"),
    "timeline": (("text", "md", "json"), "json"),
    "dossier": (("json", "table", "text"), "json"),
    "claim": (("json", "table", "text"), "json"),
    "decision": (("json", "table", "text"), "json"),
    "review-manuscript": (("json", "table", "text"), "json"),
    "manuscript-links": (("json", "table", "text"), "json"),
    "link-manuscript": (("json", "table", "text"), "json"),
    "find-anchor": (("json", "table", "text"), "json"),
    "reconcile-manuscript": (("json", "table", "text"), "json"),
    "unlink-manuscript": (("json", "table", "text"), "json"),
}

_REVISION_FIELDS = {
    "dossier": ("title", "language", "tags", "evidence", "file", "body", "geography"),
    "claim": ("title", "statement", "confidence", "time_period", "place", "actors", "dossier_id", "dossier_revision", "tags"),
    "link-evidence": ("claim_id", "claim_revision", "passage_id", "relation", "rationale", "reviewer"),
    "decision": ("title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot",
                 "dossier_id", "dossiers", "dossier_revisions"),
    "relate": ("from_claim_id", "to_claim_id", "from_claim_revision", "to_claim_revision", "relation", "state", "rationale"),
}


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Offset must be zero or greater")
    return number


def _add_manuscript_argument(command: argparse.ArgumentParser) -> None:
    """Accept the manuscript path positionally (like analyze/scenes) or via --manuscript."""
    command.epilog = "Omit the manuscript path only when the selected project's config sets manuscript."
    selector = command.add_mutually_exclusive_group()
    selector.add_argument("manuscript", nargs="?", default=argparse.SUPPRESS,
                          help="Manuscript path inside the explicit project (default: root-local config manuscript)")
    selector.add_argument("--manuscript", dest="manuscript",
                          help="Manuscript path inside the explicit project (same as positional; default: root-local config manuscript)")


COMMAND_DEFINITIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ('init', 'Create an explicit local research project', 'Sources and captures', ()),
    ('sources', 'List active sources, versions, tags, and passage counts', 'Sources and captures', ('source',)),
    ('zotero', 'Preview a local Zotero library or item attachments (read-only)', 'Sources and captures', ()),
    ('zotero-ingest', 'Capture one selected local Zotero PDF/text attachment', 'Sources and captures', ()),
    ('ingest', 'Archive local UTF-8 text, PDF, PNG or JPEG; PDF scans require configured local OCR', 'Sources and captures', ()),
    ('dossier', 'Create, list or inspect research dossiers', 'Dossiers, claims and decisions', ('dossiers',)),
    ('dossier-image', 'Capture a local PNG/JPEG and attach it to a dossier atomically', 'Dossiers, claims and decisions', ()),
    ('claim', 'Create, list or revise research claims and hypotheses', 'Dossiers, claims and decisions', ('claims',)),
    ('decision', 'Create, list or revise author decisions and fact deviations', 'Dossiers, claims and decisions', ('decisions',)),
    ('relate', 'Record, inspect or revise an authored cause/effect assertion between claims', 'Dossiers, claims and decisions', ()),
    ('link-evidence', 'Create, inspect or revise a passage-to-claim evidence link', 'Dossiers, claims and decisions', ()),
    ('link', 'Create an evidence link with positional PASSAGE_ID CLAIM_ID', 'Dossiers, claims and decisions', ()),
    ('revise-batch', 'Preview related authored-record revisions, then apply them together explicitly', 'Dossiers, claims and decisions', ()),
    ('link-manuscript', 'Associate one reviewed manuscript quote with an exact claim revision (retention explicit)', 'Manuscript associations', ()),
    ('manuscript-links', 'List saved manuscript quote-claim associations (read-only)', 'Manuscript associations', ()),
    ('review-manuscript', 'Review saved associations against the current manuscript (read-only)', 'Manuscript associations', ()),
    ('unlink-manuscript', 'Retract one saved manuscript association (history retained)', 'Manuscript associations', ()),
    ('find-anchor', 'Resolve one displayed-text quote to exact anchor fields (read-only)', 'Manuscript associations', ()),
    ('reconcile-manuscript', 'Preview or write re-pins for uniquely moved or adjusted manuscript anchors', 'Manuscript associations', ()),
    ('search', 'Search the latest source versions with literal words', 'Search and review', ()),
    ('cite', 'Resolve an immutable source passage', 'Search and review', ()),
    ('timeline', 'Read a conservative chronology from recorded claim periods', 'Search and review', ()),
    ('matrix', 'Export a structured claim-evidence-decision matrix (markdown, CSV, or JSON)', 'Search and review', ()),
    ('review', 'List structural editorial review candidates; read-only, not semantic judgment', 'Search and review', ()),
    ('decision-impact', 'Inspect dossiers explicitly linked to an author decision; read-only', 'Search and review', ()),
    ('mark-applied', 'Record an author acknowledgement for exact decision and dossier revisions', 'Search and review', ()),
    ('reopen', 'Explicitly reopen review of exact decision and dossier revisions', 'Search and review', ()),
    ('analyze', 'Analyze verified source text and return metrics and style reference (JSON)', 'Source analysis', ()),
    ('dashboard', 'Render local HTML source report', 'Source analysis', ()),
    ('compare', 'Compare research source against manuscript (lexical overlap, keyness, register, chapter grounding)', 'Source analysis', ()),
    ('audit', 'Check retained records, hashes and citation positions', 'Archive and maintenance', ()),
    ('reindex', 'Rebuild the disposable SQLite/FTS5 search index', 'Archive and maintenance', ()),
    ('withdraw', 'Withdraw a source/version or retire a reviewed dossier without deleting retained bytes', 'Archive and maintenance', ()),
    ('purge', 'Physically delete archived source records, passages, and unshared blobs', 'Archive and maintenance', ()),
    ('export', 'Export research store to verified archive (.tar.gz)', 'Archive and maintenance', ()),
    ('restore', 'Restore research store from verified archive (.tar.gz)', 'Archive and maintenance', ()),
    ('zotero-backup', 'Back up research and a closed Zotero data directory together', 'Archive and maintenance', ()),
    ('zotero-restore', 'Verify and restore a paired backup into a new directory', 'Archive and maintenance', ()),
    ('zotero-export', 'Export active captures and provenance for additive Zotero import', 'Archive and maintenance', ()),
    ('ocr-status', 'Inspect runtime diagnostic status for OCR and PDF extraction', 'Archive and maintenance', ()),
    ('schema', 'Export the research entity JSON schema', 'Archive and maintenance', ()),
)


class _ResearchHelpFormatter(argparse.HelpFormatter):
    """Group the registered flat grammar without maintaining another command list."""

    def _format_action(self, action: argparse.Action) -> str:
        if not isinstance(action, argparse._SubParsersAction):
            return super()._format_action(action)
        groups: dict[str, list[argparse.Action]] = {}
        for choice in action._choices_actions:
            command = action.choices[choice.dest]
            groups.setdefault(command.get_default("cli_group"), []).append(choice)
        parts = []
        for group, choices in groups.items():
            parts.append(" " * self._current_indent + group + ":\n")
            self._indent()
            parts.extend(self._format_action(choice) for choice in choices)
            self._dedent()
        return "".join(parts)


def configure(parser: argparse.ArgumentParser) -> None:
    from ..language import LANGUAGE_CHOICES

    parser.formatter_class = _ResearchHelpFormatter
    commands = parser.add_subparsers(dest="research_command", required=True, metavar="COMMAND")
    for name, help_text, group, aliases in COMMAND_DEFINITIONS:
        command = commands.add_parser(name, aliases=list(aliases), help=help_text, description=help_text)
        command.set_defaults(research_command=name, cli_group=group, cli_aliases=aliases)
        if name == "schema":
            command.set_defaults(cli_output_formats=("json",), cli_default_output="json", cli_purpose=help_text)
            continue
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
            command.add_argument("--update", action="store_true", help="Update the record; accepted changes create an immutable version")
            command.add_argument("--dry-run", action="store_true", help="Validate an --update exactly without writing or acquiring the writer lock")
            command.add_argument("--compact", action="store_true", help="With --update [--dry-run], return a short receipt without the record body; default JSON stays complete")
            command.add_argument("--prepare", action="store_true", help="Preview an unsaved draft against the current version; never changes the archive")
            command.add_argument("--diff", action="store_true", help="Preview the change as a unified terminal diff; never writes")
            command.add_argument("--from-revision", type=int, help="With --diff, compare this immutable version instead of a draft")
            command.add_argument("--to-revision", type=int, help="Destination version for --diff --from-revision (default: HEAD)")
            command.add_argument("--base-revision", type=int, help="Original version of the unsaved draft being prepared")
            command.add_argument("--resolve", action="append", metavar="FIELD=current|mine",
                                 help="Explicit field choice for a --prepare conflict; repeat for each field")
            command.add_argument("--history", action="store_true", help="List immutable record versions")
            command.add_argument("--inspect", action="store_true", help="Inspect the latest record")
            command.add_argument("--revision", type=int, help="Inspect one historical version")
            command.add_argument("--expected-snapshot", help="Optional strict archive digest; if omitted, update checks --expected-revision against the current record")
            command.add_argument("--expected-revision", type=int, help="Reviewed record version required for an update; changed associations need explicit pins when snapshot is omitted")
            command.add_argument("--latest", action="store_true",
                                 help="Use the current HEAD version of the record as --expected-revision "
                                      "(single-author convenience; implies --expected-snapshot from the same read)")
            command.add_argument("--change-kind", choices=("correction", "supersession"), help="Reason category required for --update or a reviewed --output packet")
            command.add_argument("--reason", help="Why this authored record is being revised")
            command.add_argument("--actor", default="local-author")
        if name in ("link-manuscript", "review-manuscript"):
            _add_manuscript_argument(command)
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name == "link-manuscript":
            command.add_argument("--claim-id", required=True)
            command.add_argument("--claim-revision", type=int, required=True,
                                 help="Exact reviewed claim version to pin")
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
            _add_manuscript_argument(command)
            command.epilog = ((command.epilog or "") +
                              " Example: lixity research find-anchor --project . "
                              "--query '**reading room**' --query-format markdown. "
                              "Inspect the returned quote and copy only its six selection fields "
                              "before a separate, explicitly permitted link-manuscript write.")
            command.add_argument("--query", required=True,
                                 help="Exact case-sensitive paragraph quote (displayed text by default); "
                                      "link/code syntax remains and Unicode is not normalized")
            command.add_argument("--query-format", choices=("display", "markdown"), default="display",
                                 help="Use markdown for a quote copied with supported emphasis, comments or footnote anchors; "
                                      "returns the exact displayed quote, never a heading")
            command.add_argument("--line", type=int,
                                 help="Restrict the search to the paragraph containing this source line")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name == "reconcile-manuscript":
            _add_manuscript_argument(command)
            command.epilog = ("Combined anchor and claim acceptance creates one revision per association. "
                              "Multiple associations use separate commits and may partially succeed; inspect accepted/skipped "
                              "and run review-manuscript again. Claim acceptance does not resolve changed, ambiguous or unavailable anchors.")
            command.add_argument("--link-id", help="Limit preview or acceptance to this association; otherwise process eligible associations separately")
            command.add_argument("--new-quote",
                                 help="Explicitly replace a changed association's quote with the revised displayed-text quote (requires --link-id)")
            command.add_argument("--line", type=int,
                                 help="Restrict --new-quote resolution to the paragraph containing this source line")
            command.add_argument("--reason",
                                 help="Optional revision reason when updating a quote")
            command.add_argument("--accept-moved", action="store_true",
                                 help="Re-pin uniquely moved/adjusted anchors with unchanged quotes, or apply explicit --new-quote; "
                                      "without an acceptance flag the command only previews")
            command.add_argument("--accept-claim-updates", action="store_true",
                                 help="Explicitly accept newer current claim revisions; preserve anchors unless "
                                      "--accept-moved also resolves them")
            command.add_argument("--update-sha", action="store_true",
                                 help="Accepted for compatibility; anchor re-pins already refresh the source digest, "
                                      "while claim-only updates preserve anchors")
            command.add_argument("--expected-snapshot",
                                 help="Optional strict archive digest for the initial review")
            command.add_argument("--expected-source-sha256",
                                 help="Optional strict source digest; the current file bytes are used when omitted")
            command.add_argument("--actor", default="local-author")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
        if name in ("dossier", "claim", "decision", "sources"):
            command.add_argument("action", nargs="?", metavar="list|show|inspect|RECORD_ID",
                                 help="list (default), show/inspect <ID>, or a record UUID to inspect")
            command.add_argument("record_id", nargs="?", metavar="RECORD_ID",
                                 help="Record UUID to show/inspect (alias for the command's named ID option)")
        if name == "init":
            command.add_argument("--title", required=True)
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"), default="en")
            command.add_argument("--actor", default="local-author")
        elif name == "ingest":
            command.add_argument("--file", nargs="+", help="Path(s) to local UTF-8 text, PDF, PNG or JPEG file(s); required unless resuming or discarding")
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
            command.add_argument("--manuscript", help="Path to manuscript file (default: selected project config manuscript)")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--language", choices=LANGUAGE_CHOICES,
                                 help="Manuscript language (default: selected project's root-local language, otherwise en; auto explicitly detects)")
            command.add_argument("--top-n", type=int, default=20, help="Number of top terms to return (default: 20)")
            command.add_argument("--output", help="Optional output file destination")
        elif name == "sources":
            command.add_argument("--source-id", help="Optional source UUID to inspect passages")
            command.add_argument("--limit", type=int, choices=range(1, 101), metavar="1..100",
                                 help="Sources per human-output page (default: 50; JSON remains complete)")
            command.add_argument("--offset", type=_non_negative, default=0,
                                 help="Zero-based human-output page offset (default: 0)")
        elif name == "dossier":
            command.formatter_class = argparse.RawDescriptionHelpFormatter
            command.epilog = (
                "Examples (use --project PATH for an archive outside the current directory):\n"
                "  lixity research dossier ID --section Evidence --format text\n"
                "  lixity research dossier ID --section Evidence --format text --body-only > section.md\n"
                "  lixity research dossier ID --section Evidence --file section.md --diff --format text\n"
                "  lixity research dossier ID --section Evidence --file section.md --update --dry-run \\\n"
                "    --expected-revision N --change-kind correction --reason 'Reviewed evidence' --compact\n"
                "  lixity research dossier ID --section Evidence --file section.md --update "
                "--expected-revision N --change-kind correction --reason 'Reviewed evidence'\n"
                "  lixity research dossier ID --export-edit dossier-edit.md\n"
                "  lixity research dossier ID --prepare --edit-file dossier-edit.md\n\n"
                "--body-only writes the selected content as UTF-8 without display headings or an added newline.\n"
                "Redirect it to a file for source text containing terminal controls or bidi formatting.\n"
                "Only actual, unique headings listed in editable_sections are section-edit targets;\n"
                "implicit preambles are read-only selections. A selected heading includes all descendants.\n\n"
                "Inspect an ID with --format text to read recorded places, route context and approximate\n"
                "distances; --summary keeps the body excerpt short. JSON geography_summary describes the\n"
                "selected version without changing stored records. Distances join supplied coordinates\n"
                "on a sphere, "
                "not road routing, elevation or travel time; coordinate digits do not establish accuracy."
            )
            command.add_argument("--dossier-id", help="Dossier UUID to inspect")
            command.add_argument("--title", help="Title for new dossier")
            content = command.add_mutually_exclusive_group()
            content.add_argument("--file", help="Existing readable UTF-8 Markdown file; use --body for literal text")
            content.add_argument("--body", help="Literal authored Markdown body (alternative to --file PATH)")
            content.add_argument("--edit-file", help="Exported dossier edit document to reconcile with --prepare")
            command.add_argument("--export-edit", metavar="PATH", help="Export a selected version as an editable Markdown draft; never overwrites")
            command.add_argument("--output", metavar="PATH", help="With --prepare --edit-file, write a ready reviewed packet for revise-batch; never overwrites")
            command.add_argument("--tags", help="Comma-separated tags")
            command.add_argument("--tag", action="append", dest="filter_tags",
                                 help="List-only exact stored tag filter (case-sensitive); repeat to require all tags")
            command.add_argument("--evidence", help="Comma-separated passage UUIDs")
            command.add_argument("--geography", metavar="JSON_OR_FILE",
                                 help="Dossier GeoJSON FeatureCollection: Point/LineString/Polygon or null geometry, "
                                      "WGS84 [longitude, latitude], properties.label required; JSON null clears geography")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
            command.add_argument("--summary", action="store_true",
                                 help="Return metadata, geography coverage and route distances, section outline, "
                                      "and body excerpt without full text; distances are not road routing or travel time")
            command.add_argument("--section", help="Inspect or replace the named heading's content and all descendants; "
                                 "an H1 can select nearly the entire dossier (preview with --diff)")
            command.add_argument("--body-only", action="store_true",
                                 help="With a selected --section --format text read, emit only its source content; "
                                      "redirect to a file for an editable draft (no added newline)")
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
        if name == "unlink-manuscript":
            _add_manuscript_argument(command)
            command.add_argument("--link-id", required=True, help="Association to retract")
            command.add_argument("--reason", default="Withdrawn by user", help="Reason for retraction")
            command.add_argument("--expected-snapshot", help="Optional strict archive digest")
            command.add_argument("--expected-revision", type=int, help="Reviewed link revision required")
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
            if name == "withdraw":
                selection = command.add_mutually_exclusive_group(required=True)
                selection.add_argument("--source-id", help="Source UUID")
                selection.add_argument("--dossier-id", help="Dossier UUID to retire, preserving its history")
                command.add_argument("--expected-snapshot", help="Reviewed archive SHA-256 digest; required for a dossier")
                command.add_argument("--expected-revision", type=int, help="Reviewed current dossier revision; required for a dossier")
                command.add_argument("--dry-run", action="store_true", help="Preview dossier withdrawal without locking or writing")
            else:
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
        if name in _REVISION_FIELDS:
            command.set_defaults(cli_draft_arguments=tuple(
                " / ".join(action.option_strings) or action.metavar or action.dest.upper()
                for action in command._actions if action.dest in _REVISION_FIELDS[name]
            ))


def command_metadata() -> list[dict[str, Any]]:
    """Describe stdout formats and switches from the configured command parsers."""
    parser = argparse.ArgumentParser(add_help=False)
    configure(parser)
    commands = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    return [{"name": name, "purpose": command.get_default("cli_purpose"),
             "output_formats": list(command.get_default("cli_output_formats")),
             "default_output": command.get_default("cli_default_output"),
             "json_flag": "--json" if "--json" in command._option_string_actions else None,
             "aliases": list(command.get_default("cli_aliases")), "group": command.get_default("cli_group")}
            for name, command in commands.choices.items() if name == command.get_default("research_command")]


def _reconcile_outcome(project: str, manuscript: str, row: dict[str, Any], source_sha256: str,
                       actor: str, language: str | None, *, accept_moved: bool,
                       accept_claim_updates: bool, reason: str | None,
                       expected_project_id: str | None = None,
                       expected_snapshot: str | None = None) -> dict[str, Any]:
    """Apply accepted changes once per row; storage failures abort the batch."""
    from . import api
    from .repository import Repository, ResearchConflictError, ResearchError, ResearchStorageError

    try:
        current = Repository(project).snapshot()
        claim_revision = row["claim_current_revision"] if accept_claim_updates and row["claim_changed"] else None
        values: dict[str, Any] = {"expected_project_id": expected_project_id or current.project.id,
                                  "expected_snapshot": expected_snapshot or current.digest,
                                  "expected_revision": row["revision"], "expected_source_sha256": source_sha256,
                                  "actor": actor, "reason": reason}
        if accept_moved and row["anchor_state"] in ("moved", "adjusted"):
            single = api.reanchor_manuscript_link(
                project, manuscript, row["link_id"], **values,
                language=language, new_claim_revision=claim_revision)
        else:
            if claim_revision is None:
                raise ResearchError("No accepted changes for this association")
            single = api.reanchor_manuscript_claim_revision(
                project, manuscript, row["link_id"], **values, new_claim_revision=claim_revision)
    except (ResearchError, ResearchConflictError, ValueError) as error:
        if expected_snapshot is not None and isinstance(error, ResearchConflictError):
            raise
        if isinstance(error.__cause__, OSError):
            raise error.__cause__ from None
        if isinstance(error, ResearchStorageError):
            raise
        return {"ok": False, "link_id": row["link_id"], "reason": str(error)}
    # OSError / PermissionError / Read-only file system are hard system failures,
    # not per-link skips: let them propagate so the command exits non-zero.
    return {"ok": True, "link_id": single["link_id"], "revision": single["record"]["revision"],
            "snapshot": single["snapshot"]}


def _json_payload(value: str) -> Any:
    """Read inline JSON before probing paths, including values over filename limits."""
    if value.lstrip().startswith(("{", "[", '"')) or value.strip() in ("null", "true", "false"):
        return json.loads(value)
    path = Path(value)
    return json.loads(path.read_text(encoding="utf-8") if path.is_file() else value)


def _json_object(value: str, what: str) -> dict[str, Any]:
    """Read a JSON object from an inline value or a local file."""
    from .repository import ResearchError

    payload = _json_payload(value)
    if not isinstance(payload, dict):
        raise ResearchError(f"{what} must be a JSON object")
    return payload


def _source_context(value: str | None) -> dict[str, Any] | None:
    """Read a source criticism JSON object from an inline value or local file."""
    if value is None:
        return None
    return _json_object(value, "Source context")


def _geography(value: str | None) -> dict[str, Any] | None:
    """Read the optional structured geography object, with explicit null for clearing."""
    from .repository import ResearchError

    if value is None:
        return None
    payload = _json_payload(value)
    if payload is not None and not isinstance(payload, dict):
        raise ResearchError("Geography must be a GeoJSON FeatureCollection object or null")
    return payload


def _dossier_content(*, file: str | None, body: str | None) -> str | None:
    """Keep explicit UTF-8 file input distinct from literal authored text."""
    from .repository import ResearchError

    if file is not None and body is not None:
        raise ResearchError("Choose --file PATH or --body TEXT, not both")
    if file is None:
        return body
    try:
        with Path(file).open("rb") as stream:
            content = stream.read(MAX_RESEARCH_OBJECT_BYTES + 1)
    except OSError as error:
        raise ResearchError(f"Cannot read --file {file!r}: {error.strerror or error}. "
                            "Use --body TEXT for literal authored content") from error
    if len(content) > MAX_RESEARCH_OBJECT_BYTES:
        raise ResearchError("Dossier --file exceeds the supported byte size")
    try:
        return content.decode("utf-8")
    except UnicodeError as error:
        raise ResearchError(f"Dossier --file {file!r} must contain valid UTF-8") from error


def _revision_changes(args: argparse.Namespace) -> dict[str, Any]:
    """Collect only flags supplied for an authored-record update."""
    kind = args.research_command
    changes: dict[str, Any] = {}
    for field in _REVISION_FIELDS[kind]:
        # These inputs retain their existing body/geography/association loaders.
        if (kind == "dossier" and field in ("file", "body", "geography")) or (
            kind == "decision" and field in ("dossier_id", "dossiers", "dossier_revisions")
        ):
            continue
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
    if kind == "dossier" and args.geography is not None:
        changes["geography"] = _geography(args.geography)
    if kind == "dossier" and (args.file is not None or args.body is not None):
        changes["body"] = _dossier_content(file=args.file, body=args.body)
    elif kind == "dossier" and getattr(args, "section", None) and any(
        getattr(args, flag, False) for flag in ("update", "prepare", "diff")
    ):
        from .repository import ResearchError
        raise ResearchError("Updating a dossier section requires --file PATH or --body TEXT with new content")
    return changes


def _missing_draft_message(args: argparse.Namespace) -> str:
    """Derive actionable input names from the owning fields and actual parser."""
    return (f"Supply at least one draft field for {args.research_command}: {', '.join(args.cli_draft_arguments)}. "
            "Use --inspect to read the record or --history to list immutable versions")


def _revision_diff_text(comparison: dict[str, Any], *, section: str | None = None) -> str:
    """Render canonical editable-field comparisons without another archive read."""
    import difflib

    from .presentation import safe_text

    color = sys.stdout.isatty()
    paints = (("+++", "\x1b[1m"), ("---", "\x1b[1m"), ("@@", "\x1b[36m"),
              ("+", "\x1b[32m"), ("-", "\x1b[31m"))

    def paint(line: str) -> str:
        line = safe_text(line)
        if color:
            for prefix, code in paints:
                if line.startswith(prefix):
                    return f"{code}{line}\x1b[0m"
        return line

    kind, record_id = comparison["kind"], comparison["record_id"]
    first, last = comparison["from_revision"], comparison["to_revision"]
    destination = f"r{last}" if last is not None else "draft"
    lines = [f"# {kind} {record_id} @r{first} → {destination} – preview only, nothing written"]
    for item in comparison["fields"]:
        name, before, after = item["field"], item["before"], item["after"]
        if name == "body":
            if kind == "dossier" and section is not None:
                from .sections import _section_spans, _section_subtree_end

                spans = _section_spans(str(before or ""))
                selected = next((span for span in spans
                                 if span.title.casefold() == section.strip().casefold()), None)
                if selected is not None:
                    end = _section_subtree_end(spans, selected, len(str(before or "")))
                    descendants = sum(selected.start < span.start < end for span in spans)
                    if descendants:
                        noun = "heading" if descendants == 1 else "headings"
                        lines.append(f"Section scope: H{selected.level} '{selected.title}' includes "
                                     f"{descendants} descendant {noun}; replacing this subtree also "
                                     "replaces their content.")
            lines.extend(difflib.unified_diff(str(before or "").splitlines(), str(after or "").splitlines(),
                                            fromfile=f"{kind} r{first}", tofile=destination, lineterm=""))
        else:
            lines.extend([f"--- {name}", f"- {json.dumps(before, ensure_ascii=False, sort_keys=True)}",
                          f"+ {json.dumps(after, ensure_ascii=False, sort_keys=True)}"])
    if not comparison["fields"]:
        lines.append("(no changes)")
    return "\n".join(paint(line) for line in lines)


def _revision_resolutions(choices: list[str] | None) -> dict[str, Literal["current", "mine"]]:
    from .repository import ResearchError

    resolutions: dict[str, Literal["current", "mine"]] = {}
    for choice in choices or []:
        field, separator, selection = choice.partition("=")
        if not field or not separator or selection not in ("current", "mine") or field in resolutions:
            raise ResearchError("Each --resolve must name one unique FIELD=current|mine choice")
        resolutions[field] = "current" if selection == "current" else "mine"
    return resolutions


def _dossier_edit_action(args: argparse.Namespace, record_id: str | None) -> dict[str, Any] | None:
    """Adapt explicit edit documents to the existing revision and batch workflows."""
    from . import api
    from .dossier_edit import (
        decode_dossier_edit,
        read_dossier_edit,
        write_dossier_edit,
        write_research_draft_file,
    )
    from .repository import ResearchConflictError, ResearchError

    if not any(value is not None for value in (args.export_edit, args.edit_file, args.output)):
        return None
    if not record_id:
        raise ResearchError("A selected dossier ID is required for edit export or preparation")
    fields = ("title", "file", "body", "tags", "evidence", "geography", "language", "section")
    if any(getattr(args, field, None) is not None for field in fields) or args.summary or args.omit_citations:
        raise ResearchError("Edit documents cannot be combined with ordinary dossier fields or bounded reads")
    if args.export_edit is not None:
        if any((args.update, args.prepare, args.diff, args.history, args.inspect,
                args.edit_file is not None, args.output is not None)):
            raise ResearchError("--export-edit permits only a selected ID and optional --revision")
        write_dossier_edit(args.project, record_id, args.export_edit, revision=args.revision)
        return {"schema_version": "research-dossier-edit-export-local/1", "record_id": record_id,
                "output": str(Path(args.export_edit).expanduser().absolute())}
    if not args.prepare or args.edit_file is None:
        raise ResearchError("--edit-file and --output require --prepare --edit-file PATH")
    if any((args.update, args.diff, args.history, args.inspect, args.revision is not None)):
        raise ResearchError("Edit documents require --prepare without other revision modes")
    document = read_dossier_edit(args.edit_file)
    if args.base_revision is not None and args.base_revision != decode_dossier_edit(document)["base_revision"]:
        raise ResearchError("--base-revision differs from the exported edit document")
    preview = api.prepare_dossier_edit(args.project, record_id, document,
                                       resolutions=_revision_resolutions(args.resolve))
    if args.output is None:
        if args.change_kind is not None or args.reason is not None:
            raise ResearchError("A revision reason and change kind accompany --output PATH for a reviewed packet")
        return preview
    if not args.change_kind or not args.reason:
        raise ResearchError("A reviewed output packet requires --change-kind and --reason")
    if not preview["ready"] or not preview["has_changes"]:
        return preview
    current = preview["current"]
    operations: list[Mapping[str, Any]] = [
        {"kind": "dossier", "id": record_id, "expected_revision": current["record"]["revision"],
         "changes": preview["changes"], "change_kind": args.change_kind, "reason": args.reason}]
    packet = api.prepare_record_revisions(args.project, operations, actor=args.actor)
    if packet["snapshot"] != current["snapshot"]:
        raise ResearchConflictError("Research snapshot changed between reconciliation and packet preparation; prepare again")
    write_research_draft_file(args.project, args.output, json.dumps(packet, ensure_ascii=False, allow_nan=False, indent=2) + "\n")
    return packet


def _revision_action(args: argparse.Namespace) -> dict[str, Any] | None:
    """Dispatch explicit history, inspection and revision modes for existing commands."""
    from . import api
    from .repository import ResearchConflictError, ResearchError

    command = args.research_command
    kind = {"link-evidence": "evidence_link", "relate": "claim_relation"}.get(command, command)
    record_id = getattr(args, {
        "dossier": "dossier_id", "claim": "claim_id",
        "link-evidence": "evidence_link_id", "decision": "decision_id",
        "relate": "relation_id",
    }[command])
    prepare = getattr(args, "prepare", False)
    if args.compact and (not args.update or prepare or args.diff or args.history or args.inspect
                         or args.revision is not None or getattr(args, "format", "json") not in ("json", "text")
                         or getattr(args, "action", None) == "list"
                         or any(getattr(args, field, None) for field in
                                ("body_only", "summary", "omit_citations", "export_edit", "edit_file", "output"))):
        raise ResearchError("--compact requires --update [--dry-run] with JSON or text output; "
                            "it does not apply to reads, diffs, preparation or export modes")
    if command == "dossier" and args.body_only:
        fields = (*_REVISION_FIELDS["dossier"], "export_edit", "edit_file", "output")
        if (not record_id or args.section is None or args.format != "text"
                or getattr(args, "action", None) == "list"
                or any((args.update, prepare, args.diff, args.history, args.summary, args.dry_run))
                or any(getattr(args, field, None) is not None for field in fields)):
            raise ResearchError("--body-only requires a selected dossier ID, --section and --format text; "
                                "it applies only to source body reads, without authored fields or write/history modes")
    bounded_dossier = command == "dossier" and (
        args.section is not None or args.summary or args.omit_citations)
    if bounded_dossier:
        if not record_id:
            raise ResearchError("Dossier --section, --summary and --omit-citations reads require a selected ID")
        if args.section is not None and args.summary:
            raise ResearchError("Choose --section or --summary for a bounded dossier read")
        if args.section is not None and (args.history or (args.diff and args.from_revision is not None)):
            raise ResearchError("--section selects dossier body reads or draft edits, not history or saved-revision comparisons")
        read_flags = [flag for flag, selected in (("--summary", args.summary),
                                                 ("--omit-citations", args.omit_citations)) if selected]
        if read_flags and any((args.update, prepare, args.diff, args.history)):
            raise ResearchError(f"{' and '.join(read_flags)} apply only to dossier reads, not revision or history modes")
    if args.dry_run and not args.update:
        raise ResearchError("--dry-run requires --update; --prepare and --diff already leave the archive unchanged")
    if ((args.from_revision is not None or args.to_revision is not None)
            and (not args.diff or args.from_revision is None)):
        raise ResearchError("Historical comparison requires --diff --from-revision N [--to-revision M]")
    if getattr(args, "latest", False):
        if not args.update:
            raise ResearchError("--latest requires --update; --diff already previews the current record")
        if args.expected_revision is not None:
            raise ResearchError("Choose --latest or --expected-revision, not both")
    if not args.update and (args.expected_revision is not None or args.expected_snapshot is not None):
        raise ResearchError("--expected-revision and --expected-snapshot require --update")
    packet_requested = (command == "dossier" and prepare and getattr(args, "edit_file", None) is not None
                        and getattr(args, "output", None) is not None)
    if not (args.update or packet_requested) and (args.change_kind is not None or args.reason is not None):
        raise ResearchError("--change-kind and --reason require --update or --prepare --edit-file PATH --output PATH")
    if not prepare and (getattr(args, "base_revision", None) is not None or getattr(args, "resolve", None)):
        raise ResearchError("--base-revision and --resolve require --prepare")
    association_revision = getattr(args, "dossier_revision", None) if command == "claim" else getattr(args, "claim_revision", None)
    if (association_revision is not None or getattr(args, "dossier_revisions", None) is not None) and not (args.update or prepare or getattr(args, "diff", False)):
        raise ResearchError("An explicit associated revision requires --update, --prepare or --diff; omit it to create a new record")
    if command == "dossier" and (edit_result := _dossier_edit_action(args, record_id)) is not None:
        return edit_result
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
        resolutions = _revision_resolutions(args.resolve)
        changes = _revision_changes(args)
        if not changes:
            raise ResearchError(_missing_draft_message(args))
        return api.prepare_record_revision(args.project, kind, record_id,
                                           base_revision=args.base_revision, changes=changes, resolutions=resolutions,
                                           **({"section": args.section} if getattr(args, "section", None) else {}))
    if getattr(args, "diff", False):
        changes = _revision_changes(args)
        if args.from_revision is not None:
            if changes or getattr(args, "section", None):
                raise ResearchError("Historical comparison takes no draft fields or section selector")
            comparison = api.compare_record_revisions(args.project, kind, record_id,
                                                       from_revision=args.from_revision, to_revision=args.to_revision)
        elif not changes:
            raise ResearchError(_missing_draft_message(args))
        else:
            comparison = api.preview_record_changes(args.project, kind, record_id, changes=changes,
                                                    **({"section": args.section} if getattr(args, "section", None) else {}))
        return {"schema_version": "research-revision-diff-local/1", "diff": _revision_diff_text(
            comparison, section=getattr(args, "section", None) if args.format == "text" else None)}
    if args.update:
        if getattr(args, "latest", False) and args.expected_revision is None:
            current = api.get_record(args.project, kind, record_id)
            args.expected_revision = current["record"]["revision"]
            if args.expected_snapshot is None:
                args.expected_snapshot = current["snapshot"]
        if args.expected_revision is None or not args.change_kind or not args.reason:
            raise ResearchError("Updates require --expected-revision (or --latest), --change-kind and --reason; run --inspect first to read the current revision")
        if args.expected_revision < 1:
            raise ResearchError("Expected revision must be positive")
        try:
            changes = _revision_changes(args)
            if not changes:
                raise ResearchError(_missing_draft_message(args))
            options: dict[str, Any] = {}
            if getattr(args, "section", None):
                options["section"] = args.section
            if args.dry_run:
                options["dry_run"] = True
            result = api.revise_record(
                args.project, kind, record_id, changes=changes,
                expected_snapshot=args.expected_snapshot,
                expected_revision=args.expected_revision,
                change_kind=args.change_kind, reason=args.reason, actor=args.actor,
                **options,
            )
            if args.compact:
                from .presentation import revision_write_summary

                return revision_write_summary(result, expected_revision=args.expected_revision)
            return result
        except ResearchConflictError as error:
            raise ResearchConflictError(f"{error}. Use --prepare --base-revision {args.expected_revision} "
                                        "with your draft fields to review current changes before saving") from None
    if args.history:
        return api.record_history(args.project, kind, record_id)
    if args.revision is not None and args.revision < 1:
        raise ResearchError("Revision must be positive")
    if bounded_dossier:
        # The ordinary dossier branch owns bounded details for every selector.
        return None
    return api.get_record(args.project, kind, record_id, revision=args.revision)


def _resolve_manuscript_input(args: argparse.Namespace) -> None:
    """Default manuscript input only after validating the selected archive."""
    if args.research_command not in (
        "review-manuscript", "find-anchor", "link-manuscript", "unlink-manuscript",
        "reconcile-manuscript", "compare",
    ) or getattr(args, "manuscript", None) is not None:
        return
    from ..workspace import configured_manuscript
    from .repository import Repository, ResearchError

    repository = Repository(args.project)
    repository.snapshot()
    args.manuscript = configured_manuscript(repository.root)
    if args.manuscript is None:
        raise ResearchError("Supply a manuscript path or --manuscript PATH, or set manuscript in the selected project's root-local config")


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


def _record_text(result: dict[str, Any]) -> str:
    """Render a record, immutable version history, or an explicit diff preview."""
    from .presentation import geography_report, safe_text

    def prose(value: Any) -> str:
        return "\n".join(safe_text(line) for line in str(value).split("\n"))

    if result.get("schema_version") == "research-revision-write-preview-local/1":
        return _revision_diff_text(result) + "\n"
    if result.get("schema_version") == "research-revision-diff-local/1":
        return str(result["diff"]).rstrip() + "\n"
    if result.get("schema_version") == "research-history-local/1":
        lines = [f"# {safe_text(result['kind'])} {safe_text(result['record_id'])} history", "",
                 f"Latest version: {result['latest_revision']}"]
        for revision in result["revisions"]:
            lines.extend(["", f"Version {revision['revision']}",
                          f"Created: {safe_text(revision['created_at'])}",
                          f"Actor: {safe_text(revision['created_by'])}"])
            change = revision.get("change")
            if change:
                lines.append(f"{safe_text(change['change_kind'])}: {safe_text(change['reason'])}")
        return "\n".join(lines) + "\n"
    record = result.get("record") or result
    title = record.get("title") or record.get("id") or "record"
    revision = record.get("revision")
    lines = [f"# {safe_text(title)}", ""]
    if revision is not None:
        lines.append(f"Version {revision}")
    if record.get("section"):
        level = record.get("section_level")
        heading = (f"{'#' * level} {safe_text(record['section'])}" if level is not None
                   else f"Section: {safe_text(record['section'])} (implicit preamble)")
        lines.extend(["", heading])
    body = record["content"] if "content" in record else (
        record.get("body") or record.get("excerpt") or record.get("statement") or record.get("rationale"))
    if body:
        lines.extend(["", prose(body)])
    impact = record.get("impact_on_plot")
    if impact:
        lines.extend(["", f"Impact on plot: {prose(impact)}"])
    if isinstance(summary := result.get("geography_summary"), dict):
        lines.extend(["", geography_report(summary)])
    return "\n".join(lines).rstrip() + "\n"


def _normalize_cli_identifiers(args: argparse.Namespace) -> None:
    """Accept complete bare UUIDv4 selectors without loosening stored/HTTP IDs."""
    def identifier(value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                        value, flags=re.IGNORECASE):
            return "urn:uuid:" + value.lower()
        return value

    for field in ("action", "record_id", "source_id", "version_id", "passage", "passage_id", "claim_id",
                  "dossier_id", "decision_id", "relation_id", "evidence_link_id", "link_id",
                  "from_claim_id", "to_claim_id"):
        value = getattr(args, field, None)
        if isinstance(value, str):
            setattr(args, field, identifier(value))
    for field in ("evidence", "dossiers"):
        value = getattr(args, field, None)
        if isinstance(value, str):
            setattr(args, field, ",".join(identifier(part.strip()) for part in value.split(",")))
    pins = getattr(args, "dossier_revisions", None)
    if pins is not None:
        value = json.loads(pins)
        if isinstance(value, dict):
            normalized = {identifier(key): revision for key, revision in value.items()}
            if len(normalized) != len(value):
                from .repository import ResearchError
                raise ResearchError("Dossier revision keys identify the same record more than once")
            args.dossier_revisions = json.dumps(normalized)


def run(args: argparse.Namespace) -> int:
    import sqlite3

    from . import api
    from .repository import ResearchError

    try:
        _normalize_cli_identifiers(args)
        command = args.research_command
        section = getattr(args, "section", None)
        if section is not None and not section.strip():
            raise ResearchError("--section requires a nonblank heading")
        if getattr(args, "action", None) == "list":
            creation = ("title", "statement", "rationale", "impact_on_plot", "file", "body", "geography")
            if any(getattr(args, name, None) for name in creation):
                raise ResearchError("The list verb does not create records; drop the list verb or the creation fields")
        if (command not in ("schema", "init", "restore", "zotero-restore", "ocr-status")
                and args.project is None):
            args.project = _current_project()
        _resolve_manuscript_input(args)
        # Normalize positional selectors without overriding an explicit revision mode.
        if command in ("dossier", "claim", "decision", "sources"):
            action = getattr(args, "action", None)
            rid = getattr(args, "record_id", None)
            flag = {"dossier": "dossier_id", "claim": "claim_id",
                    "decision": "decision_id", "sources": "source_id"}[command]
            if action == "list" and (rid is not None or getattr(args, flag, None) is not None):
                raise ResearchError("The list verb takes no record ID")
            # If action is a verb, keep it; if it looks like a record ID, shift.
            if action in ("show", "inspect"):
                if rid is None and getattr(args, flag, None) is None:
                    raise ResearchError("show/inspect requires a record ID")
                # A dossier export owns its explicit mode, like a historical
                # read; the selector verb must not add a conflicting flag.
                if command != "dossier" or (args.revision is None and args.export_edit is None):
                    args.inspect = True
            elif action is not None and action != "list":
                if rid is not None:
                    raise ResearchError("Choose list, show/inspect RECORD_ID, or one positional record ID")
                rid = action
                args.action = None
                if not any(getattr(args, mode, None) for mode in
                           ("update", "prepare", "diff", "history", "inspect", "revision", "export_edit")):
                    args.inspect = True
            if rid is not None:
                if getattr(args, flag, None) not in (None, rid):
                    raise ResearchError("Positional record ID conflicts with the named record ID")
                setattr(args, flag, rid)
        dossier_tags: list[str] | None = None
        if command == "dossier" and (filter_tags := getattr(args, "filter_tags", None)) is not None:
            from pydantic import TypeAdapter

            from .models import Dossier

            fields = (*_REVISION_FIELDS["dossier"], "section", "revision", "export_edit", "edit_file", "output")
            modes = ("summary", "omit_citations", "update", "prepare", "diff", "history", "inspect")
            if (args.dossier_id or any(getattr(args, field, None) is not None for field in fields)
                    or any(getattr(args, mode, False) for mode in modes)):
                raise ResearchError("--tag filters dossier lists only; do not combine it with a selected record or creation/revision fields")
            try:
                dossier_tags = TypeAdapter(cast(Any, Dossier.model_fields["tags"].annotation)).validate_python(filter_tags, strict=True)
            except ValidationError as error:
                raise ResearchError(f"Invalid --tag filter: {error}") from None
            if any(not tag.strip() for tag in dossier_tags):
                raise ResearchError("--tag requires a nonblank stored tag")
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
        elif command == "unlink-manuscript":
            from .repository import ResearchConflictError

            link_review = api.review_manuscript_links(args.project, args.manuscript)
            if args.expected_snapshot is not None and link_review["snapshot"] != args.expected_snapshot:
                raise ResearchConflictError("Research snapshot changed; reload before retracting")
            row = next((item for item in link_review["links"] if item["link_id"] == args.link_id), None)
            if row is None:
                raise ResearchError("Unknown manuscript association for this manuscript")
            expected_revision = args.expected_revision if args.expected_revision is not None else row["revision"]
            result = api.retract_manuscript_link(
                args.project, args.manuscript, args.link_id,
                expected_project_id=link_review["project_id"],
                expected_snapshot=link_review["snapshot"],
                expected_revision=expected_revision,
                reason=args.reason, actor=args.actor)
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
                                                   query_format=args.query_format, line=args.line, language=args.language)
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
            if args.new_quote is not None and args.link_id is None:
                raise ResearchError("--new-quote requires --link-id")
            if args.new_quote is not None and not args.accept_moved:
                row = next((item for item in link_review["links"] if item["link_id"] == args.link_id), None)
                if row is None:
                    raise ResearchError("Unknown manuscript association for this manuscript")
                resolved = api.resolve_manuscript_anchor(
                    args.project, args.manuscript, query=args.new_quote,
                    line=args.line, language=args.language)
                result = {"schema_version": "research-manuscript-reconcile-local/1",
                          "project_id": link_review["project_id"], "snapshot": link_review["snapshot"],
                          "source_path": link_review["source_path"], "dry_run": True,
                          "candidates": [{"link_id": row["link_id"], "revision": row["revision"],
                                          "claim_title": row.get("claim_title"),
                                          "anchor_state": row["anchor_state"],
                                          "old_quote": row["anchor"]["quote"],
                                          "new_quote": resolved["quote"],
                                          "candidate_lines": [resolved["start_line"]]}]}
            elif not (args.accept_moved or args.accept_claim_updates):
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
                claim_revision = row["claim_current_revision"] if args.accept_claim_updates and row["claim_changed"] else None
                if args.accept_moved:
                    result = api.reanchor_manuscript_link(
                        args.project, args.manuscript, args.link_id,
                        expected_project_id=link_review["project_id"], expected_snapshot=link_review["snapshot"],
                        expected_revision=row["revision"], expected_source_sha256=source_sha256,
                        actor=args.actor, language=args.language, new_claim_revision=claim_revision,
                        new_quote=args.new_quote, line=args.line, reason=args.reason)
                else:
                    if claim_revision is None:
                        raise ResearchError("No changed claim revision to accept for this association")
                    result = api.reanchor_manuscript_claim_revision(
                        args.project, args.manuscript, args.link_id,
                        expected_project_id=link_review["project_id"], expected_snapshot=link_review["snapshot"],
                        expected_revision=row["revision"], expected_source_sha256=source_sha256,
                        new_claim_revision=claim_revision, actor=args.actor, reason=args.reason)
            else:
                candidates = [row for row in link_review["links"]
                              if (args.accept_moved and row["anchor_state"] in ("moved", "adjusted"))
                              or (args.accept_claim_updates and row["claim_changed"])]
                accepted: list[dict[str, Any]] = []
                skipped: list[dict[str, str]] = []
                batch_snapshot = link_review["snapshot"] if args.expected_snapshot is not None else None
                for row in candidates:
                    outcome = _reconcile_outcome(args.project, args.manuscript, row, source_sha256,
                                                 args.actor, args.language, accept_moved=args.accept_moved,
                                                 accept_claim_updates=args.accept_claim_updates, reason=args.reason,
                                                 expected_project_id=link_review["project_id"] if batch_snapshot else None,
                                                 expected_snapshot=batch_snapshot)
                    if outcome["ok"]:
                        accepted.append({"link_id": outcome["link_id"], "revision": outcome["revision"]})
                        if batch_snapshot is not None:
                            batch_snapshot = outcome["snapshot"]
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
            language = getattr(args, "language", None)
            if language is None:
                from ..config import read_explicit_project_config
                from ..language import LANGUAGE_CHOICES
                from .repository import Repository

                language = read_explicit_project_config(Repository(args.project).root).get("language", "en")
                if not isinstance(language, str) or language not in LANGUAGE_CHOICES:
                    raise ResearchError(f"Unsupported project manuscript language: {language!r}")
            format_choice: Literal["json", "md"] = "md" if getattr(args, "format", "json") == "md" else "json"
            raw = api.compare_source(
                args.project,
                args.source_id,
                args.manuscript,
                version_id=args.version_id,
                language=language,
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
            if not isinstance(operations, (list, dict)):
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
                    revision=args.revision,
                    summary=getattr(args, "summary", False),
                    include_citations=not getattr(args, "omit_citations", False),
                )
            elif getattr(args, "title", None) and (args.file is not None or args.body is not None):
                body = _dossier_content(file=args.file, body=args.body)
                if body is None:
                    raise ResearchError("Creating a dossier requires --file PATH or --body TEXT")
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
                    geography=_geography(args.geography),
                    actor=args.actor,
                )
            else:
                result = api.list_dossiers(args.project)
                if dossier_tags is not None:
                    result["dossiers"] = [dossier for dossier in result["dossiers"]
                                          if all(tag in dossier["tags"] for tag in dossier_tags)]
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
                                  dossier_id=args.dossier_id, expected_snapshot=args.expected_snapshot,
                                  expected_revision=args.expected_revision, dry_run=args.dry_run,
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
        if command in ("find-anchor", "link-manuscript", "manuscript-links", "review-manuscript",
                       "reconcile-manuscript", "unlink-manuscript") and args.format != "json":
            from .presentation import manuscript_report

            print(manuscript_report(command, result, table=args.format == "table"), end="")
            return 0
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
        if (result.get("schema_version") == "research-revision-write-summary-local/1"
                and getattr(args, "format", "json") == "text"):
            from .presentation import revision_write_report

            print(revision_write_report(result), end="")
            return 0
        if command in ("dossier", "claim", "decision") and getattr(args, "format", "json") == "text":
            if command == "dossier" and args.body_only:
                from .presentation import safe_text

                content = result["content"]
                terminal_text = content.replace("\r\n", "\n").replace("\n", "").replace("\t", "")
                if sys.stdout.isatty() and safe_text(terminal_text) != terminal_text:
                    raise ResearchError("--body-only source contains terminal controls or Unicode formatting; "
                                        "redirect stdout to a file to retain the exact source content")
                # Binary output avoids newline translation and locale-dependent encodings.
                if (buffer := getattr(sys.stdout, "buffer", None)) is not None:
                    buffer.write(content.encode("utf-8"))
                else:
                    sys.stdout.write(content)
                return 0
            list_keys = ("dossiers", "claims", "decisions")
            if isinstance(result, dict) and any(k in result for k in list_keys):
                from .presentation import record_list_report

                table = record_list_report(command, result)
                if table is not None:
                    print(table)
                    return 0
            print(_record_text(result))
            return 0
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
    except OSError as error:
        detail = f"{error.strerror or error}" if getattr(error, "strerror", None) else str(error)
        path_hint = f" ({error.filename})" if getattr(error, "filename", None) else ""
        print(f"[error] Research operation failed: {detail}{path_hint}", file=sys.stderr)
        print("[error] Check paths, permissions, schema and storage integrity", file=sys.stderr)
    except (ValidationError, UnicodeError, sqlite3.Error, ValueError) as error:
        print(f"[error] Research operation failed: {error}", file=sys.stderr)
        print("[error] Check paths, permissions, schema and storage integrity", file=sys.stderr)
    return 1
