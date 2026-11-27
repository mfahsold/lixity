"""Argument registration and execution for the Research CLI's Zotero commands."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any


def configure(parser: argparse.ArgumentParser, name: str) -> None:
    if name == "zotero-backup":
        parser.add_argument(
            "--data-dir", required=True, help="Closed Zotero data directory containing zotero.sqlite"
        )
        parser.add_argument("--output", required=True, help="New directory for the paired backup")
        parser.add_argument(
            "--confirm-zotero-closed",
            action="store_true",
            help="Required acknowledgement that Zotero is closed",
        )
        return
    if name == "zotero-restore":
        parser.add_argument(
            "--from",
            dest="archive_source",
            required=True,
            help="Paired backup directory created by zotero-backup",
        )
        parser.add_argument(
            "--to",
            dest="target_dir",
            required=True,
            help="New directory for restored project and Zotero data",
        )
        return
    if name == "zotero-export":
        parser.add_argument(
            "--output",
            required=True,
            help="New directory for RIS, files and provenance manifest",
        )
        parser.add_argument(
            "--allow-retention",
            action="store_true",
            help="Required permission to copy retained source bytes, also with --dry-run",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the export without writing its output directory",
        )
        return

    parser.add_argument(
        "--library", required=True, help="Explicit Zotero library: users/0 or groups/<id>"
    )
    if name == "zotero":
        choice = parser.add_mutually_exclusive_group()
        choice.add_argument(
            "--query", default="", help="Filter local library items by query text (default: all)"
        )
        choice.add_argument("--item-key", help="Inspect an item and its attachments")
        choice.add_argument("--collections", action="store_true", help="List collections")
        parser.add_argument("--collection-key", help="Restrict item search to this collection")
        parser.add_argument(
            "--limit",
            type=int,
            choices=range(1, 101),
            default=20,
            metavar="1..100",
            help="Maximum items per page (default: 20)",
        )
        parser.add_argument("--start", type=int, default=0, help="Zero-based page offset")
        return

    key_group = parser.add_mutually_exclusive_group(required=True)
    key_group.add_argument("--attachment-key", nargs="+", help="One or more Zotero attachment keys")
    key_group.add_argument(
        "--item-key", help="Zotero parent item key to ingest all eligible attachments"
    )
    parser.add_argument(
        "--source-id", help="Explicitly refresh a matching prior capture (single attachment only)"
    )
    parser.add_argument("--expected-server-id", help="Require the previewed Zotero instance")
    parser.add_argument(
        "--language",
        choices=("en", "de", "fr", "es", "it", "pt", "nl", "generic"),
        help="Language of retained source text (default: research project language)",
    )
    parser.add_argument(
        "--allow-retention",
        action="store_true",
        help="Required permission to retain attachment bytes, also with --dry-run",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate selected attachments without accepting captures"
    )
    parser.add_argument("--progress", action="store_true", help="Report real-time progress phases on stderr")


def run(args: argparse.Namespace) -> dict[str, Any]:
    name = args.research_command
    if name in ("zotero-backup", "zotero-restore"):
        from . import zotero_backup

        if name == "zotero-restore":
            return zotero_backup.restore(args.archive_source, args.target_dir)
        return zotero_backup.backup(
            args.project, args.data_dir, args.output, confirm_closed=args.confirm_zotero_closed
        )

    from . import zotero

    if name == "zotero-export":
        return zotero.export_library(
            args.project, args.output, allow_retention=args.allow_retention, dry_run=args.dry_run
        )
    if name == "zotero":
        if args.collections:
            return zotero.collections(args.project, library=args.library, start=args.start)
        return zotero.browse(
            args.project,
            library=args.library,
            query=args.query,
            item_key=args.item_key,
            limit=args.limit,
            start=args.start,
            collection_key=args.collection_key,
        )

    from .repository import ResearchError

    start_time = time.monotonic()

    def progress(stage: str, message: str) -> None:
        if getattr(args, "progress", False) or sys.stderr.isatty():
            elapsed = time.monotonic() - start_time
            print(f"[{stage}] ({elapsed:.1f}s) {message}", file=sys.stderr, flush=True)

    if getattr(args, "item_key", None):
        if getattr(args, "source_id", None):
            raise ResearchError(
                "--source-id cannot be used when ingesting an item with multiple attachments"
            )
        return zotero.ingest_item(
            args.project,
            library=args.library,
            item_key=args.item_key,
            language=args.language,
            expected_server_id=args.expected_server_id,
            allow_retention=args.allow_retention,
            dry_run=args.dry_run,
            progress_callback=progress,
        )

    attachment_keys = args.attachment_key if isinstance(args.attachment_key, list) else [args.attachment_key]
    if len(attachment_keys) == 1:
        return zotero.ingest(
            args.project,
            library=args.library,
            attachment_key=attachment_keys[0],
            source_id=args.source_id,
            language=args.language,
            expected_server_id=args.expected_server_id,
            allow_retention=args.allow_retention,
            dry_run=args.dry_run,
            progress_callback=progress,
        )
    if getattr(args, "source_id", None):
        raise ResearchError("--source-id cannot be used when ingesting multiple attachments")
    return zotero.ingest_attachments(
        args.project,
        library=args.library,
        attachment_keys=attachment_keys,
        language=args.language,
        expected_server_id=args.expected_server_id,
        allow_retention=args.allow_retention,
        dry_run=args.dry_run,
        progress_callback=progress,
    )
