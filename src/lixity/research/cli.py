"""Lazy research command dispatch; machine-readable stdout, diagnostics on stderr."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError


def configure(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="research_command", required=True)
    commands.add_parser("schema", help="Export the experimental entity JSON schema")
    for name, help_text in (
        ("init", "Create an explicit local research project"),
        ("ingest", "Archive local UTF-8 text or PDF; scans require a configured OCR worker"),
        ("reindex", "Rebuild the disposable SQLite/FTS5 search index"),
        ("search", "Search the latest source versions with literal words"),
        ("cite", "Resolve an immutable source passage"),
        ("audit", "Check retained records, hashes and citation positions"),
        ("analyze", "Analyze verified source text and return metrics and style reference (JSON)"),
        ("dashboard", "Render local HTML source report"),
        ("compare", "Compare research source against manuscript (lexical overlap, keyness, register, chapter grounding)"),
        ("sources", "List active sources, versions, tags, and passage counts"),
        ("dossier", "Create, list or inspect research dossiers"),
        ("claim", "Create, list or revise research claims and hypotheses"),
        ("link-evidence", "Create, inspect or revise a passage-to-claim evidence link"),
        ("decision", "Create, list or revise author decisions and fact deviations"),
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
    ):
        command = commands.add_parser(name, help=help_text)
        if name not in ("restore", "ocr-status", "zotero-restore"):
            command.add_argument("--project", required=True, help="Explicit project directory")
        elif name == "ocr-status":
            command.add_argument("--project", help="Optional project directory")
            command.add_argument("--worker-cmd", help="Explicit OCR worker binary or command to inspect")
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
                command.add_argument("--attachment-key", required=True)
                command.add_argument("--source-id", help="Explicitly refresh a matching prior capture")
                command.add_argument("--expected-server-id", help="Require the previewed Zotero instance")
                command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
                command.add_argument("--allow-retention", action="store_true")
                command.add_argument("--dry-run", action="store_true")
                command.add_argument("--progress", action="store_true", help="Report real-time progress phases on stderr")
        if name in ("dossier", "claim", "link-evidence", "decision"):
            command.add_argument("--update", action="store_true", help="Revise the named record")
            command.add_argument("--history", action="store_true", help="List immutable revisions")
            command.add_argument("--inspect", action="store_true", help="Inspect the latest record")
            command.add_argument("--revision", type=int, help="Inspect one historical revision")
            command.add_argument("--expected-snapshot", help="Snapshot digest required for an update")
            command.add_argument("--expected-revision", type=int, help="Latest revision required for an update")
            command.add_argument("--change-kind", choices=("correction", "supersession"), help="Reason category for an update")
            command.add_argument("--reason", help="Why this authored record is being revised")
            command.add_argument("--actor", default="local-author")
        if name == "init":
            command.add_argument("--title", required=True)
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"), default="en")
            command.add_argument("--actor", default="local-author")
        elif name == "ingest":
            command.add_argument("--file", nargs="+", required=True, help="Path(s) to local UTF-8 text or PDF file(s)")
            command.add_argument("--title")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
            command.add_argument("--source-id", help="Refresh this source without invalidating old citations")
            command.add_argument("--actor", default="local-author")
            command.add_argument("--allow-retention", action="store_true", help="Confirm permission to retain a local copy, not to redistribute it")
            command.add_argument("--dry-run", action="store_true", help="Validate and preview; do not write")
            command.add_argument("--context", help="Path to JSON file containing source criticism context")
            command.add_argument("--origin-url", help="Original HTTP(S) source URL (metadata only; never fetched)")
            command.add_argument("--progress", action="store_true", help="Report real-time progress phases on stderr")
        elif name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--scope", choices=("sources", "dossiers", "claims", "decisions", "all"),
                                 default="sources", help="Search sources (default) or current authored records")
            command.add_argument("--limit", type=int, choices=range(1, 101), default=20, metavar="1..100")
            command.add_argument("--strict", action="store_true", help="Fail if search index is stale instead of refreshing automatically")
        elif name == "cite":
            command.add_argument("--passage", required=True)
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
        elif name == "sources":
            command.add_argument("--source-id", help="Optional source UUID to inspect passages")
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
        elif name == "link-evidence":
            command.add_argument("--evidence-link-id", help="Evidence-link UUID to inspect or revise")
            command.add_argument("--claim-id", help="Claim UUID")
            command.add_argument("--claim-revision", type=int, help="Explicit claim revision to pin on update")
            command.add_argument("--passage-id", help="Passage citation UUID")
            command.add_argument("--relation", choices=("supports", "contradicts", "qualifies", "contextualizes"))
            command.add_argument("--rationale", help="Reviewer rationale for link")
            command.add_argument("--reviewer", help="Reviewer identifier")
        elif name == "decision":
            command.add_argument("--decision-id", help="Decision UUID to inspect or revise")
            command.add_argument("--title", help="Title for new author decision")
            command.add_argument("--rationale", help="Artistic or historical rationale")
            command.add_argument("--claim-id", help="Optional claim UUID being decided upon")
            command.add_argument("--claim-revision", type=int, help="Explicit claim revision to pin on update")
            command.add_argument("--dossier-id", help="Associated dossier UUID")
            command.add_argument("--dossiers", help="Comma-separated dossier UUIDs impacted by this decision")
            command.add_argument("--deviation-from-fact", action=argparse.BooleanOptionalAction,
                                 default=None, help="Set or clear intentional deviation from historical evidence")
            command.add_argument("--impact-on-plot", help="Description of plot or worldbuilding impact")
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


def _revision_changes(args: argparse.Namespace) -> dict[str, Any]:
    """Collect only flags supplied for an authored-record update."""
    kind = args.research_command
    fields = {
        "dossier": ("title", "language", "tags", "evidence"),
        "claim": ("title", "statement", "confidence", "time_period", "place", "actors", "dossier_id", "dossier_revision", "tags"),
        "link-evidence": ("claim_id", "claim_revision", "passage_id", "relation", "rationale", "reviewer"),
        "decision": ("title", "rationale", "claim_id", "claim_revision", "deviation_from_fact", "impact_on_plot"),
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
            field == "rationale" and kind == "link-evidence"
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
    if kind == "dossier" and args.file is not None:
        body_path = Path(args.file)
        new_content = body_path.read_text(encoding="utf-8") if body_path.is_file() else args.file
        if getattr(args, "section", None):
            from . import api
            record_id = getattr(args, "dossier_id", None)
            if record_id:
                current_dossier = api.get_dossier(args.project, record_id)
                changes["body"] = api.update_section(current_dossier["body"], args.section, new_content)
            else:
                changes["body"] = new_content
        else:
            changes["body"] = new_content
    elif kind == "dossier" and getattr(args, "section", None) and getattr(args, "update", False):
        from .repository import ResearchError
        raise ResearchError("Updating a dossier section requires --file with new section content")
    return changes


def _revision_action(args: argparse.Namespace) -> dict[str, Any] | None:
    """Dispatch explicit history, inspection and revision modes for existing commands."""
    from . import api
    from .repository import ResearchError

    command = args.research_command
    kind = "evidence_link" if command == "link-evidence" else command
    record_id = getattr(args, {
        "dossier": "dossier_id", "claim": "claim_id",
        "link-evidence": "evidence_link_id", "decision": "decision_id",
    }[command])
    association_revision = getattr(args, "dossier_revision", None) if command == "claim" else getattr(args, "claim_revision", None)
    if association_revision is not None and not args.update:
        raise ResearchError("An explicit associated revision requires --update")
    requested = args.update or args.history or args.inspect or args.revision is not None
    if command in ("link-evidence", "decision") and record_id:
        requested = True
    if not requested:
        return None
    if not record_id:
        raise ResearchError(f"{kind} ID is required for revision, history or inspection")
    if sum(bool(mode) for mode in (args.update, args.history, args.inspect, args.revision is not None)) > 1:
        raise ResearchError("Choose one of --update, --history, --inspect or --revision")
    if args.update:
        if not args.expected_snapshot or args.expected_revision is None or not args.change_kind or not args.reason:
            raise ResearchError("Updates require --expected-snapshot, --expected-revision, --change-kind and --reason")
        if args.expected_revision < 1:
            raise ResearchError("Expected revision must be positive")
        changes = _revision_changes(args)
        if not changes:
            raise ResearchError("At least one changed field is required")
        return api.revise_record(
            args.project, kind, record_id, changes=changes,
            expected_snapshot=args.expected_snapshot,
            expected_revision=args.expected_revision,
            change_kind=args.change_kind, reason=args.reason, actor=args.actor,
        )
    if args.history:
        return api.record_history(args.project, kind, record_id)
    if args.revision is not None and args.revision < 1:
        raise ResearchError("Revision must be positive")
    return api.get_record(args.project, kind, record_id, revision=args.revision)


def run(args: argparse.Namespace) -> int:
    import sqlite3

    from . import api
    from .repository import ResearchError

    try:
        command = args.research_command
        result: dict[str, Any]
        if command == "schema":
            result = api.schema()
        elif command == "init":
            result = api.init(args.project, title=args.title, language=args.language, actor=args.actor)
        elif command == "ingest":
            context: dict[str, Any] | None = None
            if getattr(args, "context", None):
                context_path = Path(args.context)
                if context_path.is_file():
                    context = json.loads(context_path.read_text(encoding="utf-8"))
                else:
                    context = json.loads(args.context)
            start_time = time.monotonic()

            def _cli_progress(stage: str, message: str) -> None:
                if getattr(args, "progress", False) or sys.stderr.isatty():
                    elapsed = time.monotonic() - start_time
                    print(f"[{stage}] ({elapsed:.1f}s) {message}", file=sys.stderr, flush=True)

            files = args.file if isinstance(args.file, list) else [args.file]
            if len(files) > 1:
                if args.source_id:
                    raise ResearchError("Cannot specify --source-id when ingesting multiple files")
                items: list[dict[str, Any]] = []
                succeeded = 0
                failed = 0
                def _ingest_one(file_item: Any) -> tuple[dict[str, Any], bool]:
                    try:
                        res = api.ingest(args.project, file_item, allow_retention=args.allow_retention,
                                         language=args.language, actor=args.actor, dry_run=args.dry_run,
                                         context=context, origin_url=args.origin_url,
                                         progress_callback=_cli_progress)
                        return ({"file": str(file_item), "ok": True, "source_id": res["source_id"], "passages": res["passages"]}, True)
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
                result = api.ingest(args.project, files[0], allow_retention=args.allow_retention,
                                    source_id=args.source_id, title=args.title, language=args.language,
                                    actor=args.actor, dry_run=args.dry_run, context=context, origin_url=args.origin_url,
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

                result = zotero.ingest(args.project, library=args.library, attachment_key=args.attachment_key,
                                       source_id=args.source_id, language=args.language, expected_server_id=args.expected_server_id,
                                       allow_retention=args.allow_retention, dry_run=args.dry_run,
                                       progress_callback=_zotero_progress)
        elif command == "reindex":
            result = api.reindex(args.project)
        elif command == "search":
            result = api.search(args.project, args.query, limit=args.limit, scope=args.scope, ensure_fresh=not args.strict)
            if not args.strict and any("refreshed" in w for w in result.get("warnings", [])):
                print("[search] Search index was refreshed to current snapshot (use --strict to require manual reindexing)", file=sys.stderr)
        elif command == "cite":
            result = api.cite(args.project, args.passage)
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
            result = api.compare_source(
                args.project,
                args.source_id,
                args.manuscript,
                version_id=args.version_id,
                language=getattr(args, "language", None),
                top_n=getattr(args, "top_n", 20),
            )
        elif command == "sources":
            if getattr(args, "source_id", None):
                result = api.get_source(args.project, args.source_id)
            else:
                result = api.list_sources(args.project)
        elif command in ("dossier", "claim", "link-evidence", "decision") and (
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
        elif command == "link-evidence":
            if not args.claim_id or not args.passage_id:
                raise ResearchError("--claim-id and --passage-id are required to create an evidence link")
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
            result = api.ocr_status(getattr(args, "worker_cmd", None))
        else:
            result = api.audit(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("ok") is False else 0
    except ResearchError as error:
        print(f"[error] {error}", file=sys.stderr)
    except (OSError, ValidationError, UnicodeError, sqlite3.Error, ValueError):
        print("[error] Research operation failed; check paths, permissions, schema and storage integrity", file=sys.stderr)
    return 1
