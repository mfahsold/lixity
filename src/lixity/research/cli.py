"""Lazy research command dispatch; machine-readable stdout, diagnostics on stderr."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError


def configure(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="research_command", required=True)
    commands.add_parser("schema", help="Export the experimental entity JSON schema")
    for name, help_text in (
        ("init", "Create an explicit local research project"),
        ("ingest", "Archive local UTF-8 text; no PDF/OCR or network access"),
        ("reindex", "Rebuild the disposable SQLite/FTS5 search index"),
        ("search", "Search the latest source versions with literal words"),
        ("cite", "Resolve an immutable source passage"),
        ("audit", "Check retained records, hashes and citation positions"),
        ("analyze", "Analyze verified source text and return metrics and style reference (JSON)"),
        ("dashboard", "Render local HTML source report"),
        ("withdraw", "Withdraw an archived source or version, marking citations and excluding from search"),
        ("purge", "Physically delete archived source records, passages, and unshared blobs"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--project", required=True, help="Explicit project directory")
        if name == "init":
            command.add_argument("--title", required=True)
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"), default="en")
            command.add_argument("--actor", default="local-author")
        elif name == "ingest":
            command.add_argument("--file", required=True)
            command.add_argument("--title")
            command.add_argument("--language", choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"))
            command.add_argument("--source-id", help="Refresh this source without invalidating old citations")
            command.add_argument("--actor", default="local-author")
            command.add_argument("--allow-retention", action="store_true", help="Confirm permission to retain a local copy, not to redistribute it")
            command.add_argument("--dry-run", action="store_true", help="Validate and preview; do not write")
            command.add_argument("--context", help="Path to JSON file containing source criticism context")
        elif name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--limit", type=int, choices=range(1, 101), default=20, metavar="1..100")
        elif name == "cite":
            command.add_argument("--passage", required=True)
        elif name in ("analyze", "dashboard"):
            command.add_argument("--source-id", required=True, help="Source UUID")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--thresholds", help="Path to JSON file or JSON string of analysis thresholds")
        elif name in ("withdraw", "purge"):
            command.add_argument("--source-id", required=True, help="Source UUID")
            command.add_argument("--version-id", help="Explicit source version UUID")
            command.add_argument("--reason", default="Withdrawn by user" if name == "withdraw" else "Purged by user", help="Reason for action")
            command.add_argument("--actor", default="local-author")
            if name == "purge":
                command.add_argument("--dry-run", action="store_true", help="Preview records, passages and blobs to be removed without deleting")


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
            result = api.ingest(args.project, args.file, allow_retention=args.allow_retention,
                                source_id=args.source_id, title=args.title, language=args.language,
                                actor=args.actor, dry_run=args.dry_run, context=context)
        elif command == "reindex":
            result = api.reindex(args.project)
        elif command == "search":
            result = api.search(args.project, args.query, limit=args.limit)
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
        elif command == "withdraw":
            result = api.withdraw(args.project, args.source_id, version_id=args.version_id,
                                  reason=args.reason, actor=args.actor)
        elif command == "purge":
            result = api.purge(args.project, args.source_id, version_id=args.version_id,
                               reason=args.reason, actor=args.actor, dry_run=args.dry_run)
        else:
            result = api.audit(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("ok") is False else 0
    except ResearchError as error:
        print(f"[error] {error}", file=sys.stderr)
    except (OSError, ValidationError, UnicodeError, sqlite3.Error, ValueError):
        print("[error] Research operation failed; check paths, permissions, schema and storage integrity", file=sys.stderr)
    return 1
