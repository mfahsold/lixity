"""Revision-bound UTF-8 manuscript writes and bounded local recovery.

The lock coordinates in-process writers only. External editors can still race
the final check/replace; retained versions support recovery, not universal locks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import time
from collections import OrderedDict, defaultdict
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .dialogue import find_indirect_speech_spans, indirect_speech_available
from .diversity import mattr as mattr_value
from .io import FileUtils
from .language import compile_word_pattern, resolve_language
from .log import get_logger, log_event
from .markdown_parser import (
    before_appendix,
    legacy_whitespace_text,
    prose_text,
    split_chapters,
    split_scenes,
)
from .models import CorpusConfig
from .pacing import compute_rhythm_profile
from .pipeline import resolve_document_config
from .quotation import count_quoted_words, merge_quotation_spans
from .quotation_projection import quoted_prose
from .sentences import split_prose_sentences
from .sticky import measure_function_words

logger = get_logger("manuscript")

SOURCE_WRITE_LOCK = RLock()
_DOC_LOCKS_GUARD = RLock()
_DOC_LOCKS: dict[str, RLock] = {}


def document_lock(source: str | Path) -> RLock:
    """Return a re-entrant lock scoped to the resolved manuscript path."""
    key = str(Path(source).resolve())
    with _DOC_LOCKS_GUARD:
        lock = _DOC_LOCKS.get(key)
        if lock is None:
            lock = RLock()
            _DOC_LOCKS[key] = lock
        return lock
MAX_TEXT_BYTES = 4 * 1024 * 1024
_ID = re.compile(r"[a-f0-9]{32,64}\Z")
_MAX_CHAPTER_SIMILARITY_PAIRS = 16_384


class EditConflict(ValueError):
    """The caller's base no longer identifies the selected source."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes) -> tuple[str, str, bytes]:
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError("Manuscript exceeds the 4 MiB editing limit")
    bom = b"\xef\xbb\xbf" if data.startswith(b"\xef\xbb\xbf") else b""
    try:
        text = data[len(bom):].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Editing requires UTF-8; retain the original before converting") from exc
    if "\0" in text:
        raise ValueError("Binary content cannot be edited")
    crlf = "\r\n" in text
    remainder = text.replace("\r\n", "")
    if "\r" in remainder or (crlf and "\n" in remainder):
        raise ValueError("Mixed or CR-only line endings require an explicit conversion")
    return text.replace("\r\n", "\n"), "\r\n" if crlf else "\n", bom


def snapshot_settings_digest(
    language: str = "en",
    project_config: Mapping[str, Any] | None = None,
) -> str:
    """Return a deterministic digest of the effective snapshot analysis settings."""
    effective: dict[str, Any] = {
        key: value
        for key, value in (project_config or {}).items()
        if key in CorpusConfig.model_fields and key != "language"
    }
    effective["language"] = language or "en"
    effective["snapshot_method"] = "lixity-snapshot/3"
    payload = json.dumps(effective, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ManuscriptStore:
    """Selected-file editing; no request may choose a filesystem destination."""

    def __init__(
        self,
        root: Path,
        source: Path,
        *,
        language: str = "en",
        project_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.root = root.resolve(strict=True)
        if source.is_symlink():
            raise ValueError("Editing a manuscript symlink is not supported")
        self.source = source.resolve(strict=True)
        if not self.source.is_relative_to(self.root) or self.source.suffix.lower() not in {".md", ".txt", ".markdown"}:
            raise ValueError("Choose a Markdown or text manuscript inside the selected project")
        self.document = _digest((str(self.root) + "\0" + str(self.source)).encode())
        self.directory = self.root / ".lixity" / "editing"
        self.language = language or "en"
        self.project_config: dict[str, Any] = dict(project_config) if project_config else {}
        self._settings_sha256 = snapshot_settings_digest(self.language, self.project_config)
        self._snapshot_cache: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
        self._schema_ready = False

    def _read(self) -> bytes:
        if self.source.is_symlink() or not self.source.resolve(strict=True).is_relative_to(self.root):
            raise ValueError("Manuscript path changed")
        return FileUtils.read_bounded_regular_bytes(
            self.source, maximum=MAX_TEXT_BYTES, nofollow=True
        )[0]

    def _initialize_schema(self, db: sqlite3.Connection) -> None:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE IF NOT EXISTS recovery (document TEXT, id TEXT, kind TEXT, content BLOB, created REAL, PRIMARY KEY(document,id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_recovery_doc_created ON recovery (document, kind, created DESC)")
        db.execute("CREATE TABLE IF NOT EXISTS receipts (document TEXT, id TEXT, request TEXT, response TEXT, created REAL, PRIMARY KEY(document,id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_receipts_doc_created ON receipts (document, created DESC)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS manuscript_revisions ("
            "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
            "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
            "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
            "length_entropy REAL, sticky_pct REAL, indirect_speech_per_1000 REAL, "
            "flags_count INTEGER, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
            "settings_sha256 TEXT, "
            "PRIMARY KEY(document, revision))"
        )
        table_info = db.execute("PRAGMA table_info(manuscript_revisions)").fetchall()
        existing_cols = {str(row[1]) for row in table_info}
        for col_name in ("length_entropy", "sticky_pct", "indirect_speech_per_1000"):
            if col_name not in existing_cols:
                db.execute(f"ALTER TABLE manuscript_revisions ADD COLUMN {col_name} REAL")
        if "settings_sha256" not in existing_cols:
            db.execute("ALTER TABLE manuscript_revisions ADD COLUMN settings_sha256 TEXT")
        flags_col = next((row for row in table_info if str(row[1]) == "flags_count"), None)
        if flags_col is not None and int(flags_col[3]) != 0:
            db.execute(
                "CREATE TABLE manuscript_revisions_new ("
                "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
                "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
                "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
                "length_entropy REAL, sticky_pct REAL, indirect_speech_per_1000 REAL, "
                "flags_count INTEGER, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
                "settings_sha256 TEXT, "
                "PRIMARY KEY(document, revision))"
            )
            db.execute(
                "INSERT INTO manuscript_revisions_new "
                "(document, revision, parent_revision, created_at, words, sentences, "
                "asl, asl_cv, dialogue_ratio, mattr, length_entropy, sticky_pct, "
                "indirect_speech_per_1000, flags_count, chapter_metrics, settings_sha256) "
                "SELECT document, revision, parent_revision, created_at, words, sentences, "
                "asl, asl_cv, dialogue_ratio, mattr, length_entropy, sticky_pct, "
                "indirect_speech_per_1000, "
                "CASE WHEN flags_count = 0 THEN NULL ELSE flags_count END, "
                "chapter_metrics, settings_sha256 FROM manuscript_revisions"
            )
            db.execute("DROP TABLE manuscript_revisions")
            db.execute("ALTER TABLE manuscript_revisions_new RENAME TO manuscript_revisions")
        db.execute("CREATE INDEX IF NOT EXISTS idx_manuscript_revisions_doc_created ON manuscript_revisions (document, created_at DESC)")
        db.execute("PRAGMA user_version=2")
        db.commit()

    def _database(self, *, ensure_schema: bool = True) -> sqlite3.Connection:
        if self.directory.parent.is_symlink() or self.directory.is_symlink():
            raise ValueError("Recovery directory must not be a symlink")
        self.directory.parent.mkdir(mode=0o700, exist_ok=True)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        path = self.directory / "recovery.sqlite3"
        if path.is_symlink():
            raise ValueError("Recovery database must not be a symlink")
        created = not path.exists()
        if created:
            self._schema_ready = False
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        db = sqlite3.connect(path)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("PRAGMA synchronous=FULL")
            if not self._schema_ready:
                if not created and not ensure_schema:
                    version = int(db.execute("PRAGMA user_version").fetchone()[0])
                    journal_mode = str(db.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                    if version >= 2 and journal_mode == "wal":
                        self._schema_ready = True
                        return db
                self._initialize_schema(db)
                self._schema_ready = True
            return db
        except BaseException:
            db.close()
            raise

    def analyze_snapshot(self, text: str) -> dict[str, Any]:
        """Compute deterministic offline stylometric metrics for a manuscript snapshot."""
        return analyze_manuscript_snapshot(
            text, language=self.language, project_config=self.project_config
        )

    def _fixed_auto_config(self, text: str) -> CorpusConfig | None:
        if self.language.strip().lower() != "auto":
            return None
        return resolve_document_config(text, self.language, project_config=self.project_config)[0]

    def _snapshot_settings(self, config: CorpusConfig | None) -> str:
        if config is None:
            return self._settings_sha256
        return snapshot_settings_digest(config.language, self.project_config)

    def _measure_snapshot(self, text: str, config: CorpusConfig | None) -> dict[str, Any]:
        return self.analyze_snapshot(text) if config is None else analyze_manuscript_snapshot(text, config=config)

    def _cached_snapshot(self, text: str, config: CorpusConfig | None = None) -> dict[str, Any]:
        key = (self._snapshot_settings(config), _digest(text.encode("utf-8")))
        cached = self._snapshot_cache.get(key)
        if cached is not None:
            self._snapshot_cache.move_to_end(key)
            return dict(cached)
        snap = self._measure_snapshot(text, config)
        self._snapshot_cache[key] = snap
        while len(self._snapshot_cache) > 12:
            self._snapshot_cache.popitem(last=False)
        return dict(snap)

    def _insert_revision_snapshot(
        self,
        db: sqlite3.Connection,
        revision: str,
        snap: dict[str, Any],
        *,
        settings_sha256: str,
        parent_revision: str | None = None,
        created_at: float | None = None,
        flags_count: int | None = None,
    ) -> None:
        ts = float(created_at if created_at is not None else time.time())
        resolved_flags = (
            int(flags_count)
            if flags_count is not None
            else (int(snap["flags_count"]) if snap.get("flags_count") is not None else None)
        )
        db.execute(
            "INSERT OR IGNORE INTO manuscript_revisions "
            "(document, revision, parent_revision, created_at, words, sentences, asl, asl_cv, "
            "dialogue_ratio, mattr, length_entropy, sticky_pct, indirect_speech_per_1000, "
            "flags_count, chapter_metrics, settings_sha256) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                self.document,
                revision,
                parent_revision,
                ts,
                snap["words"],
                snap["sentences"],
                snap["asl"],
                snap["asl_cv"],
                snap["dialogue_ratio"],
                snap["mattr"],
                snap["length_entropy"],
                snap["sticky_pct"],
                snap["indirect_speech_per_1000"],
                resolved_flags,
                json.dumps(snap["chapter_metrics"], ensure_ascii=False),
                settings_sha256,
            ),
        )

    def _record_revision(
        self,
        db: sqlite3.Connection,
        revision: str,
        text: str,
        *,
        parent_revision: str | None = None,
        created_at: float | None = None,
        flags_count: int | None = None,
    ) -> None:
        existing = db.execute(
            "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
            (self.document, revision),
        ).fetchone()
        if existing is not None:
            return
        config = self._fixed_auto_config(text)
        snap = self._cached_snapshot(text, config)
        self._insert_revision_snapshot(
            db,
            revision,
            snap,
            settings_sha256=self._snapshot_settings(config),
            parent_revision=parent_revision,
            created_at=created_at,
            flags_count=flags_count,
        )

    def _lock(self) -> RLock:
        return document_lock(self.source)

    def open(self) -> dict[str, Any]:
        with self._lock():
            data = self._read()
            text, _, _ = _decode(data)
            recovery: list[dict[str, Any]] = []
            if (self.directory / "recovery.sqlite3").exists():
                with closing(self._database(ensure_schema=False)) as db:
                    recovery = [{"id": row["id"], "kind": row["kind"], "created": row["created"]}
                                for row in db.execute("SELECT id,kind,created FROM recovery WHERE document=? ORDER BY created DESC", (self.document,))]
            log_event(logger, "manuscript_open", level=logging.DEBUG, bytes=len(data), recovery=len(recovery))
            return {"schema_version": "lixity-editor/1", "document": self.document,
                    "revision": _digest(data), "text": text, "recovery": recovery}

    def recover(self, identifier: str) -> dict[str, str]:
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid recovery identifier")
        if not (self.directory / "recovery.sqlite3").exists():
            raise ValueError("Recovery entry is unavailable")
        with self._lock(), closing(self._database(ensure_schema=False)) as db:
            row = db.execute("SELECT content,kind FROM recovery WHERE document=? AND id=?", (self.document, identifier)).fetchone()
            if row is None:
                raise ValueError("Recovery entry is unavailable")
            content = bytes(row["content"])
            return {"schema_version": "lixity-editor/1", "document": self.document,
                    "revision": _digest(content), "id": identifier, "kind": str(row["kind"]),
                    "text": _decode(content)[0]}

    def save(self, document: str, revision: str, operation: str, text: str) -> dict[str, str]:
        if document != self.document or not re.fullmatch(r"[a-f0-9]{64}", revision) or not re.fullmatch(r"[a-f0-9]{32}", operation):
            raise ValueError("Invalid document, revision or operation")
        if "\r" in text or "\0" in text:
            raise ValueError("Editor text must use LF and contain no NUL")
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_TEXT_BYTES:
            raise ValueError("Manuscript exceeds the 4 MiB editing limit")
        request = _digest(revision.encode() + b"\0" + encoded)
        with self._lock(), closing(self._database()) as db:
            receipt = db.execute("SELECT request,response FROM receipts WHERE document=? AND id=?", (document, operation)).fetchone()
            if receipt is not None:
                if receipt["request"] != request:
                    raise ValueError("Operation identifier was reused for different content")
                response: dict[str, str] = json.loads(str(receipt["response"]))
                return response
            original = self._read()
            original_text, newline, bom = _decode(original)
            candidate = bom + text.replace("\n", newline).encode("utf-8")
            if len(candidate) > MAX_TEXT_BYTES:
                raise ValueError("Encoded manuscript exceeds the 4 MiB editing limit")
            prior = db.execute("SELECT content FROM recovery WHERE document=? AND id=?", (document, operation)).fetchone()
            if prior is not None and bytes(prior["content"]) != candidate:
                raise ValueError("Operation identifier was reused for different content")
            count = int(db.execute("SELECT count(*) AS n FROM recovery WHERE document=? AND kind='draft'", (document,)).fetchone()["n"])
            if prior is None and count >= 8:
                raise ValueError("Eight recovery drafts retained; recover or remove a draft before saving")
            with db:
                db.execute(
                    "INSERT INTO recovery (document, id, kind, content, created) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(document, id) DO UPDATE SET kind=excluded.kind, content=excluded.content, created=excluded.created",
                    (document, operation, "draft", candidate, time.time()),
                )
            # A retry after replacement but before receipt persistence is safe
            # only when this exact operation was already journaled.
            if _digest(original) != revision and not (prior is not None and original == candidate):
                log_event(logger, "manuscript_save_conflict", level=logging.WARNING, stage="revision-mismatch")
                raise EditConflict("Manuscript changed elsewhere; your draft is retained")
            identity = self.source.stat()
            def guard() -> None:
                current = self.source.stat()
                if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino) or self._read() != original:
                    log_event(logger, "manuscript_save_conflict", level=logging.WARNING, stage="write-guard")
                    raise EditConflict("Manuscript changed while saving; your draft is retained")
            if original != candidate:
                with db:
                    db.execute(
                        "INSERT INTO recovery (document, id, kind, content, created) VALUES (?,?,?,?,?) "
                        "ON CONFLICT(document, id) DO UPDATE SET kind=excluded.kind, content=excluded.content, created=excluded.created",
                        (document, _digest(original), "version", original, time.time()),
                    )
                FileUtils.atomic_write_bytes_if_changed(str(self.source), candidate, before_replace=guard)
            response = {"document": document, "revision": _digest(candidate)}
            orig_rev = _digest(original)
            target_rev = response["revision"]
            changed = original != candidate
            now = time.time()
            with db:
                orig_row = (
                    db.execute(
                        "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
                        (self.document, orig_rev),
                    ).fetchone()
                    if changed
                    else None
                )
                need_orig = changed and orig_row is None
                target_row = db.execute(
                    "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
                    (self.document, target_rev),
                ).fetchone()
                need_target = target_row is None
                db.execute("DELETE FROM recovery WHERE document=? AND id=? AND kind='draft'", (document, operation))
                db.execute("INSERT INTO receipts (document, id, request, response, created) VALUES (?,?,?,?,?)", (document, operation, request, json.dumps(response), time.time()))
                db.execute(
                    "DELETE FROM recovery WHERE document=? AND kind='version' AND id IN ("
                    "SELECT id FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY created DESC, id DESC) AS rn "
                    "FROM recovery WHERE document=? AND kind='version') WHERE rn > 20)",
                    (document, document),
                )
                db.execute(
                    "DELETE FROM receipts WHERE document=? AND id IN ("
                    "SELECT id FROM (SELECT id, ROW_NUMBER() OVER (ORDER BY created DESC, id DESC) AS rn "
                    "FROM receipts WHERE document=?) WHERE rn > 100)",
                    (document, document),
                )
        # Compute expensive stylometric snapshots outside SOURCE_WRITE_LOCK so
        # concurrent readers/writers are not blocked while preserving revision identity.
        orig_config = self._fixed_auto_config(original_text) if need_orig else None
        target_config = self._fixed_auto_config(text) if need_target else None
        orig_snap = self._measure_snapshot(original_text, orig_config) if need_orig else None
        target_snap = self._measure_snapshot(text, target_config) if need_target else None
        if orig_snap is not None or target_snap is not None:
            with self._lock(), closing(self._database()) as db, db:
                if orig_snap is not None:
                    self._insert_revision_snapshot(
                        db,
                        orig_rev,
                        orig_snap,
                        settings_sha256=self._snapshot_settings(orig_config),
                        parent_revision=None,
                        created_at=now - 0.001,
                    )
                if target_snap is not None:
                    self._insert_revision_snapshot(
                        db,
                        target_rev,
                        target_snap,
                        settings_sha256=self._snapshot_settings(target_config),
                        parent_revision=orig_rev if changed else None,
                        created_at=now,
                    )
        log_event(logger, "manuscript_save", changed=changed, bytes=len(candidate))
        return response

    def discard(self, identifier: str) -> None:
        """Explicitly remove a selected recovery copy, never the manuscript."""
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid recovery identifier")
        with self._lock(), closing(self._database()) as db, db:
            db.execute("DELETE FROM recovery WHERE document=? AND id=?", (self.document, identifier))
        log_event(logger, "manuscript_discard", kind="recovery")

    @staticmethod
    def _row_to_revision(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "revision": str(row["revision"]),
            "parent_revision": str(row["parent_revision"]) if row["parent_revision"] is not None else None,
            "created_at": float(row["created_at"]),
            "words": int(row["words"]),
            "sentences": int(row["sentences"]),
            "asl": float(row["asl"]) if row["asl"] is not None else None,
            "asl_cv": float(row["asl_cv"]) if row["asl_cv"] is not None else None,
            "dialogue_ratio": float(row["dialogue_ratio"]) if row["dialogue_ratio"] is not None else None,
            "mattr": float(row["mattr"]) if row["mattr"] is not None else None,
            "length_entropy": float(row["length_entropy"]) if row["length_entropy"] is not None else None,
            "sticky_pct": float(row["sticky_pct"]) if row["sticky_pct"] is not None else None,
            "indirect_speech_per_1000": (
                float(row["indirect_speech_per_1000"])
                if row["indirect_speech_per_1000"] is not None
                else None
            ),
            "flags_count": int(row["flags_count"]) if row["flags_count"] is not None else None,
            "chapter_metrics": json.loads(str(row["chapter_metrics"])),
        }

    def _row_settings_match(self, row: sqlite3.Row, config: CorpusConfig | None) -> bool:
        recorded = row["settings_sha256"] if "settings_sha256" in set(row.keys()) else None
        return recorded is not None and str(recorded) == self._snapshot_settings(config)

    def _retained_revision_text(self, db: sqlite3.Connection, revision: str) -> str | None:
        rec = db.execute(
            "SELECT content FROM recovery WHERE document=? AND id=? LIMIT 1",
            (self.document, revision),
        ).fetchone()
        if rec is None:
            return None
        content = bytes(rec["content"])
        return _decode(content)[0] if _digest(content) == revision else None

    def _timeline_rows(self, db: sqlite3.Connection, bounded: int) -> list[dict[str, Any]]:
        rows = db.execute(
            "SELECT revision, parent_revision, created_at, words, sentences, asl, asl_cv, "
            "dialogue_ratio, mattr, length_entropy, sticky_pct, indirect_speech_per_1000, "
            "flags_count, chapter_metrics "
            "FROM manuscript_revisions WHERE document=? "
            "ORDER BY created_at DESC, revision DESC LIMIT ?",
            (self.document, bounded),
        ).fetchall()
        return [self._row_to_revision(row) for row in reversed(rows)]

    def _recorded_revision_from_db(self, db: sqlite3.Connection, revision: str) -> dict[str, Any] | None:
        row = db.execute(
            "SELECT * FROM manuscript_revisions WHERE document=? AND revision=?",
            (self.document, revision),
        ).fetchone()
        return self._row_to_revision(row) if row is not None else None

    def _resolve_revision_for_compare(
        self,
        db: sqlite3.Connection,
        revision: str,
        fallback: dict[str, Any],
        *,
        config: CorpusConfig | None = None,
        current_bytes: tuple[str, str] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        if config is None and self.language.strip().lower() == "auto":
            return fallback, False
        row = db.execute(
            "SELECT * FROM manuscript_revisions WHERE document=? AND revision=?",
            (self.document, revision),
        ).fetchone()
        if row is None:
            return fallback, True
        if self._row_settings_match(row, config):
            return fallback, True
        text = (current_bytes[1] if current_bytes is not None and current_bytes[0] == revision
                else self._retained_revision_text(db, revision))
        if text is None:
            return fallback, False
        snap = self._cached_snapshot(text, config)
        for key in ("revision", "parent_revision", "created_at"):
            snap[key] = fallback[key]
        return snap, True

    def timeline(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return unique content snapshots by first recording time (oldest to newest)."""
        bounded = max(1, min(int(limit), 200))
        if not (self.directory / "recovery.sqlite3").exists():
            return []
        with self._lock(), closing(self._database(ensure_schema=False)) as db:
            return self._timeline_rows(db, bounded)

    def _recorded_revision(self, revision: str) -> dict[str, Any] | None:
        """Resolve an immutable measurement independently of the timeline window."""
        if not (self.directory / "recovery.sqlite3").exists():
            return None
        with self._lock(), closing(self._database(ensure_schema=False)) as db:
            return self._recorded_revision_from_db(db, revision)

    def compare(
        self,
        *,
        revision: str,
        base_text: str,
        draft_text: str,
        settings_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Measure an exact disk revision and two editor texts without opening history."""
        if not re.fullmatch(r"[a-f0-9]{64}", revision):
            raise ValueError("Invalid current revision identifier")
        if settings_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", settings_sha256):
            raise ValueError("Invalid comparison settings identifier")
        for supplied in (base_text, draft_text):
            if "\r" in supplied or "\0" in supplied:
                raise ValueError("Editor text must use LF and contain no NUL")
            if len(supplied.encode("utf-8")) > MAX_TEXT_BYTES:
                raise ValueError("Manuscript exceeds the 4 MiB editing limit")

        with self._lock():
            source = self._read()
            if _digest(source) != revision:
                raise EditConflict("The current file changed; reopen the comparison")
            current_text, _, _ = _decode(source)
        # One profile for all columns, including in projects using auto detection.
        config, _ = resolve_document_config(current_text, self.language, project_config=self.project_config)
        settings = snapshot_settings_digest(config.language, self.project_config)
        if settings_sha256 is not None and settings_sha256 != settings:
            raise EditConflict("The analysis settings changed; reopen the comparison")

        by_text: dict[str, dict[str, Any]] = {}
        measurements: dict[str, dict[str, Any]] = {}
        for key, raw in (("base", base_text), ("current", current_text), ("draft", draft_text)):
            if raw not in by_text:
                by_text[raw] = analyze_manuscript_snapshot(raw, config=config)
            digest = revision if key == "current" else _digest(raw.encode("utf-8"))
            measurements[key] = {**by_text[raw], "revision": digest}

        def _pair(prev_key: str, next_key: str) -> dict[str, Any]:
            deltas, chapter_deltas = diff_snapshots(measurements[prev_key], measurements[next_key])
            return {
                "deltas": deltas,
                "chapter_deltas": chapter_deltas,
                "chapter_matching": summarize_chapter_matching(chapter_deltas),
            }

        primary_diff: str | None = None
        if draft_text != current_text:
            primary_diff = "current_to_draft"
        elif base_text != current_text:
            primary_diff = "base_to_current"

        return {
            "schema_version": "lixity-compare/1",
            "document": self.document,
            "settings_sha256": settings,
            "measurements": measurements,
            "base_to_current": _pair("base", "current"),
            "current_to_draft": _pair("current", "draft"),
            "primary_diff": primary_diff,
        }

    def delta(self, base_revision: str | None = None, target_revision: str | None = None) -> dict[str, Any]:
        """Compare retained measurements or the captured current source, never interpolating."""
        if base_revision is not None and not _ID.fullmatch(base_revision):
            raise ValueError("Invalid base revision identifier")
        if target_revision is not None and not _ID.fullmatch(target_revision):
            raise ValueError("Invalid target revision identifier")
        target_compatible = True
        base_compatible = True
        with self._lock():
            db_exists = (self.directory / "recovery.sqlite3").exists()
            if db_exists:
                with closing(self._database(ensure_schema=False)) as db:
                    history = self._timeline_rows(db, 100)
                    by_rev = {item["revision"]: item for item in history}
                    current_bytes: tuple[str, str] | None = None
                    config: CorpusConfig | None = None
                    if target_revision is not None:
                        target = by_rev.get(target_revision) or self._recorded_revision_from_db(db, target_revision)
                        if target is None:
                            raise ValueError("Target revision not found in manuscript history")
                        try:
                            source = self._read()
                            current_bytes = (_digest(source), _decode(source)[0])
                        except (OSError, ValueError):
                            # A historical comparison can still use retained data.
                            pass
                        if self.language.strip().lower() == "auto":
                            target_text = (current_bytes[1] if current_bytes is not None and current_bytes[0] == target_revision
                                           else self._retained_revision_text(db, target_revision))
                            if target_text is not None:
                                config = self._fixed_auto_config(target_text)
                        target, target_compatible = self._resolve_revision_for_compare(
                            db, target_revision, target, config=config, current_bytes=current_bytes
                        )
                    else:
                        source = self._read()
                        text, _, _ = _decode(source)
                        revision = _digest(source)
                        current_bytes = (revision, text)
                        config = self._fixed_auto_config(text)
                        target = by_rev.get(revision) or self._recorded_revision_from_db(db, revision)
                        if target is None:
                            target = self._measure_snapshot(text, config)
                            target["revision"] = revision
                            target["created_at"] = None
                        else:
                            target, target_compatible = self._resolve_revision_for_compare(
                                db, revision, target, config=config, current_bytes=current_bytes
                            )
                    base: dict[str, Any] | None = None
                    if base_revision is not None:
                        base = by_rev.get(base_revision) or self._recorded_revision_from_db(db, base_revision)
                        if base is None:
                            raise ValueError("Base revision not found in manuscript history")
                        base, base_compatible = self._resolve_revision_for_compare(
                            db, base_revision, base, config=config, current_bytes=current_bytes
                        )
                    if (base_revision is None and len(history) >= 2
                            and any(item["revision"] == target["revision"] for item in history)
                            and (target_revision is not None or target["revision"] == history[-1]["revision"])):
                        target_day = datetime.fromtimestamp(target["created_at"], tz=timezone.utc).date()
                        same_day = [
                            item for item in history
                            if item["revision"] != target["revision"]
                            and item["created_at"] <= target["created_at"]
                            and datetime.fromtimestamp(item["created_at"], tz=timezone.utc).date() == target_day
                        ]
                        candidate_base: dict[str, Any] | None
                        if same_day:
                            candidate_base = same_day[0]
                        else:
                            idx = next(i for i, item in enumerate(history) if item["revision"] == target["revision"])
                            candidate_base = history[idx - 1] if idx > 0 else None
                        if candidate_base is not None:
                            base, base_compatible = self._resolve_revision_for_compare(
                                db, candidate_base["revision"], candidate_base, config=config, current_bytes=current_bytes
                            )
            else:
                history = []
                if target_revision is not None:
                    raise ValueError("Target revision not found in manuscript history")
                source = self._read()
                text, _, _ = _decode(source)
                revision = _digest(source)
                target = self.analyze_snapshot(text)
                target["revision"] = revision
                target["created_at"] = None
                base = None
                if base_revision is not None:
                    raise ValueError("Base revision not found in manuscript history")
        if target is None:
            raise ValueError("Target revision not found in manuscript history")
        if base is None or not (target_compatible and base_compatible):
            return {
                "schema_version": "lixity-timeline/1",
                "document": self.document,
                "has_baseline": False,
                "revisions_count": len(history),
                "base": None,
                "current": target,
                "deltas": None,
                "chapter_deltas": [],
                "chapter_matching": {"clear": True, "matched": 0, "unmatched": 0, "ambiguous": 0},
            }

        deltas, chapter_deltas = diff_snapshots(base, target)
        return {
            "schema_version": "lixity-timeline/1",
            "document": self.document,
            "has_baseline": True,
            "revisions_count": len(history),
            "base": base,
            "current": target,
            "deltas": deltas,
            "chapter_deltas": chapter_deltas,
            "chapter_matching": summarize_chapter_matching(chapter_deltas),
        }


def analyze_manuscript_snapshot(
    text: str,
    *,
    language: str = "en",
    project_config: Mapping[str, Any] | None = None,
    config: CorpusConfig | None = None,
) -> dict[str, Any]:
    """Compute deterministic offline stylometric metrics for a manuscript snapshot."""
    if config is None:
        cfg, resolved = resolve_document_config(
            text, language or "en", project_config=project_config
        )
    else:
        cfg = config
        resolved = resolve_language(cfg, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    lang_key = resolved.key
    function_words = resolved.function_words
    sticky_available = bool(function_words)
    ind_speech_available = indirect_speech_available(lang_key)

    main_text = before_appendix(text, cfg)
    clean_words = len(legacy_whitespace_text(main_text, cfg).split())

    projection = quoted_prose(main_text, cfg, language=resolved)
    prose_main = projection.text

    tokens = word_re.findall(prose_main)
    n_tokens = len(tokens)
    lower_tokens = [t.lower() for t in tokens]
    mattr_score = mattr_value(lower_tokens) if lower_tokens else None

    sentences = split_prose_sentences(prose_main, lang_key)
    sent_lengths = [n for n in (len(word_re.findall(s)) for s in sentences) if n > 0]
    total_sentences = len(sent_lengths)
    if total_sentences > 0:
        asl = sum(sent_lengths) / total_sentences
        variance = sum((x - asl) ** 2 for x in sent_lengths) / total_sentences
        sentence_cv = (math.sqrt(variance) / asl) if asl else 0.0
    else:
        asl = 0.0
        sentence_cv = 0.0

    dialog_words = count_quoted_words(prose_main, word_re, projection.analysis.spans)
    dialog_ratio = (dialog_words / n_tokens) * 100.0 if n_tokens else 0.0

    chapters: list[dict[str, Any]] = []
    all_corpus_sentence_lengths: list[int] = []
    total_sticky_sentences = 0
    total_sticky_denom = 0
    indirect_speech_words = 0
    all_indirect_speech = 0

    for number, title, body in split_chapters(main_text, cfg):
        chapter = quoted_prose(body, cfg, language=resolved, chapter_body=True)
        cl_b = chapter.text
        c_words = word_re.findall(cl_b)
        if not c_words:
            chapters.append({
                "num": int(number),
                "title": str(title),
                "words": 0,
                "asl": None,
                "dialog_pct": None,
                "sig": [],
                "text_hash": "",
            })
            continue

        n_cw = len(c_words)
        c_lower = [w.lower() for w in c_words]
        sig, text_hash = _chapter_signature(c_lower)
        c_sentences = split_prose_sentences(cl_b, lang_key)
        c_sent_tokens = [
            [w.lower() for w in word_re.findall(s)]
            for s in c_sentences
        ]
        c_sent_lengths = [len(toks) for toks in c_sent_tokens if toks]
        c_total_sents = len(c_sent_lengths)
        c_asl = (sum(c_sent_lengths) / c_total_sents) if c_total_sents else 0.0
        c_dial_words = count_quoted_words(cl_b, word_re, chapter.analysis.spans)
        c_dial_pct = (c_dial_words / n_cw) * 100.0

        chapters.append({
            "num": int(number),
            "title": str(title),
            "words": int(n_cw),
            "asl": round(float(c_asl), 2) if c_total_sents > 0 else None,
            "dialog_pct": round(float(c_dial_pct), 2) if n_cw > 0 else None,
            "sig": sig,
            "text_hash": text_hash,
        })
        all_corpus_sentence_lengths.extend(c_sent_lengths)

        if sticky_available:
            raw_scenes, _ = split_scenes(body)
            for scene_raw in raw_scenes:
                if len(raw_scenes) == 1 and scene_raw == body:
                    scene_tokens = iter(c_sent_tokens)
                else:
                    scene_clean = prose_text(scene_raw, _front_matter=False)
                    if not word_re.search(scene_clean):
                        continue
                    scene_tokens = (
                        [word.lower() for word in word_re.findall(sentence)]
                        for sentence in split_prose_sentences(scene_clean, lang_key)
                    )
                for sentence_tokens in scene_tokens:
                    if sentence_tokens:
                        total_sticky_denom += 1
                        total_sticky_sentences += measure_function_words(
                            sentence_tokens, function_words,
                            min_words=cfg.sticky_min_words, min_pct=cfg.sticky_glue_pct,
                        ).sticky

        if ind_speech_available:
            indirect_speech_words += n_cw
            for start, end in chapter.regions:
                analysis = chapter.slice_analysis(start, end)
                excluded = merge_quotation_spans((*analysis.quote_ranges, *analysis.unclear))
                all_indirect_speech += len(find_indirect_speech_spans(cl_b[start:end], excluded, lang_key))

    rhythm = compute_rhythm_profile(
        all_corpus_sentence_lengths, short_sentence_max=cfg.short_sentence_max
    )
    raw_entropy = rhythm.get("length_entropy")
    return {
        "words": int(clean_words),
        "sentences": int(total_sentences),
        "asl": round(float(asl), 3) if total_sentences > 0 else None,
        "asl_cv": round(float(sentence_cv), 4) if total_sentences > 0 else None,
        "dialogue_ratio": round(float(dialog_ratio), 3) if n_tokens > 0 else None,
        "mattr": round(float(mattr_score), 4) if mattr_score is not None else None,
        "length_entropy": round(float(raw_entropy), 4) if raw_entropy is not None else None,
        "sticky_pct": (
            round(total_sticky_sentences / total_sticky_denom * 100.0, 2)
            if total_sticky_denom else None
        ),
        "indirect_speech_per_1000": (
            round(all_indirect_speech / indirect_speech_words * 1000.0, 2)
            if indirect_speech_words else None
        ),
        "flags_count": None,
        "chapter_metrics": chapters,
    }


_GENERIC_CHAPTER_TITLE_RE = re.compile(
    r"^(?:(?:chapter|kapitel|chapitre|cap[ií]tulo|capitolo|hoofdstuk)\s+)?"
    r"(?:\d+|[ivxlcdm]+)$",
    re.IGNORECASE,
)


def _chapter_signature(tokens: list[str]) -> tuple[list[str], str]:
    """Build a compact, non-reversible content signature for chapter matching."""
    if not tokens:
        return [], ""
    text_hash = hashlib.blake2b(
        " ".join(tokens).encode("utf-8"), digest_size=8, person=b"lixityc2"
    ).hexdigest()
    if len(tokens) >= 6:
        shingles = {" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)}
    else:
        shingles = set(tokens)
    hashes = sorted(
        hashlib.blake2b(s.encode("utf-8"), digest_size=8, person=b"lixityc1").hexdigest()
        for s in shingles
    )
    return hashes[:32], text_hash


def _norm_chapter_title(title: Any) -> str:
    return " ".join(str(title or "").strip().casefold().split())


def _is_generic_chapter_title(norm_title: str) -> bool:
    return not norm_title or bool(_GENERIC_CHAPTER_TITLE_RE.fullmatch(norm_title))


def _chapter_similarity(base_ch: Mapping[str, Any], target_ch: Mapping[str, Any]) -> float | None:
    b_hash = str(base_ch.get("text_hash") or "")
    t_hash = str(target_ch.get("text_hash") or "")
    if b_hash and t_hash and b_hash == t_hash:
        return 1.0
    b_sig = base_ch.get("sig")
    t_sig = target_ch.get("sig")
    if not isinstance(b_sig, list) or not isinstance(t_sig, list) or not b_sig or not t_sig:
        return None
    set_b = set(b_sig)
    set_t = set(t_sig)
    union = len(set_b | set_t)
    return (len(set_b & set_t) / union) if union else 0.0


def _match_chapters(
    base_chapters: list[dict[str, Any]],
    target_chapters: list[dict[str, Any]],
) -> list[tuple[dict[str, Any] | None, str]]:
    """Pair target chapters with base chapters only when correspondence is clear."""
    n_b = len(base_chapters)
    n_t = len(target_chapters)
    if not n_t:
        return []
    if not n_b:
        return [(None, "unmatched") for _ in target_chapters]

    matched_t: dict[int, int] = {}
    matched_b: set[int] = set()

    def content_index(chapters: list[dict[str, Any]]) -> dict[str, list[int]]:
        index: dict[str, list[int]] = defaultdict(list)
        for i, chapter in enumerate(chapters):
            if digest := chapter.get("text_hash"):
                index[digest].append(i)
        return index

    base_by_content = content_index(base_chapters)
    target_by_content = content_index(target_chapters)
    for digest, target_indices in target_by_content.items():
        base_indices = base_by_content.get(digest, [])
        if len(base_indices) == len(target_indices) == 1:
            bi, ti = base_indices[0], target_indices[0]
            matched_t[ti] = bi
            matched_b.add(bi)

    remaining_b = [bi for bi in range(n_b) if bi not in matched_b]
    remaining_t = [ti for ti in range(n_t) if ti not in matched_t]
    base_titles = [_norm_chapter_title(ch.get("title")) for ch in base_chapters]
    target_titles = [_norm_chapter_title(ch.get("title")) for ch in target_chapters]
    stable_layout = base_titles == target_titles and all(bi == ti for ti, bi in matched_t.items())
    # Compare signatures only within a bounded remainder and require mutual leads.
    if stable_layout and len(remaining_b) * len(remaining_t) <= _MAX_CHAPTER_SIMILARITY_PAIRS:
        base_candidates: dict[int, list[tuple[float, int]]] = defaultdict(list)
        target_candidates: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for bi in remaining_b:
            for ti in remaining_t:
                score = _chapter_similarity(base_chapters[bi], target_chapters[ti])
                if score:
                    base_candidates[bi].append((score, ti))
                    target_candidates[ti].append((score, bi))
        for candidates in (*base_candidates.values(), *target_candidates.values()):
            candidates.sort(reverse=True)
        inferred: dict[int, int] = {}
        for bi, candidates in base_candidates.items():
            score, ti = candidates[0]
            target_choices = target_candidates[ti]
            base_runner_up = candidates[1][0] if len(candidates) > 1 else 0.0
            target_runner_up = target_choices[1][0] if len(target_choices) > 1 else 0.0
            if (target_choices[0][1] == bi and score >= 0.35
                    and score - max(base_runner_up, target_runner_up) >= 0.12):
                inferred[ti] = bi
        stable_layout = all(bi == ti for ti, bi in inferred.items())
        if stable_layout:
            matched_t.update(inferred)
            matched_b.update(inferred.values())

    # Titles alone cannot support a match through a structural change.
    stable_titles = (
        stable_layout
        and (n_b == 1 or (
            len(set(base_titles)) == n_b
            and not any(_is_generic_chapter_title(title) for title in base_titles)
        ))
    )
    if stable_titles:
        for i in range(n_t):
            matched_t[i] = i
            matched_b.add(i)

    has_unmatched_base = len(matched_b) < n_b
    results: list[tuple[dict[str, Any] | None, str]] = []
    for ti in range(n_t):
        if ti in matched_t:
            results.append((base_chapters[matched_t[ti]], "matched"))
        elif has_unmatched_base:
            results.append((None, "ambiguous"))
        else:
            results.append((None, "unmatched"))
    return results


def summarize_chapter_matching(chapter_deltas: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize how many target chapters have clear correspondence."""
    matched = sum(1 for ch in chapter_deltas if ch.get("match_status") == "matched")
    unmatched = sum(1 for ch in chapter_deltas if ch.get("match_status") == "unmatched")
    ambiguous = sum(1 for ch in chapter_deltas if ch.get("match_status") == "ambiguous")
    changed = sum(1 for ch in chapter_deltas if ch.get("changed"))
    return {
        "clear": ambiguous == 0,
        "matched": matched,
        "changed": changed,
        "unmatched": unmatched,
        "ambiguous": ambiguous,
    }


def diff_snapshots(
    base: dict[str, Any],
    target: dict[str, Any],
) -> tuple[dict[str, float | int | None], list[dict[str, Any]]]:
    """Compute exact global and per-chapter metric deltas between two snapshots."""
    def _diff(key: str, digits: int) -> float | int | None:
        a, b = base.get(key), target.get(key)
        if a is None or b is None:
            return None
        val = b - a
        return int(val) if digits == 0 else round(float(val), digits)

    deltas: dict[str, float | int | None] = {
        "words": _diff("words", 0),
        "sentences": _diff("sentences", 0),
        "asl": _diff("asl", 2),
        "asl_cv": _diff("asl_cv", 4),
        "dialogue_ratio": _diff("dialogue_ratio", 2),
        "mattr": _diff("mattr", 4),
        "length_entropy": _diff("length_entropy", 4),
        "sticky_pct": _diff("sticky_pct", 2),
        "indirect_speech_per_1000": _diff("indirect_speech_per_1000", 2),
        "flags_count": _diff("flags_count", 0),
    }
    base_chapters = list(base.get("chapter_metrics", []))
    target_chapters = list(target.get("chapter_metrics", []))
    pairings = _match_chapters(base_chapters, target_chapters)
    chapter_deltas: list[dict[str, Any]] = []
    for ch, (prev, match_status) in zip(target_chapters, pairings, strict=True):
        asl_d = (
            round(float(ch["asl"]) - float(prev["asl"]), 2)
            if prev is not None and ch.get("asl") is not None and prev.get("asl") is not None
            else None
        )
        dlg_d = (
            round(float(ch["dialog_pct"]) - float(prev["dialog_pct"]), 2)
            if prev is not None and ch.get("dialog_pct") is not None and prev.get("dialog_pct") is not None
            else None
        )
        words_d = int(ch["words"]) - int(prev["words"]) if prev is not None else None
        changed = (
            match_status == "matched"
            and prev is not None
            and (
                int(prev["num"]) != int(ch["num"])
                or (words_d is not None and words_d != 0)
                or (asl_d is not None and abs(asl_d) >= 0.05)
                or (dlg_d is not None and abs(dlg_d) >= 0.05)
            )
        )
        chapter_deltas.append({
            "num": int(ch["num"]),
            "title": str(ch["title"]),
            "base_num": int(prev["num"]) if prev is not None else None,
            "base_title": str(prev["title"]) if prev is not None else None,
            "match_status": match_status,
            "changed": changed,
            "words": int(ch["words"]),
            "words_delta": words_d,
            "asl": ch.get("asl"),
            "asl_delta": asl_d,
            "dialog_pct": ch.get("dialog_pct"),
            "dialog_pct_delta": dlg_d,
        })
    return deltas, chapter_deltas


def compare_texts(
    base_text: str,
    target_text: str,
    *,
    language: str = "en",
    project_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two manuscript Markdown strings and return enriched stylometric deltas."""
    config, _ = resolve_document_config(target_text, language or "en", project_config=project_config)
    base_snap = analyze_manuscript_snapshot(base_text, config=config)
    target_snap = analyze_manuscript_snapshot(target_text, config=config)
    deltas, chapter_deltas = diff_snapshots(base_snap, target_snap)
    return {
        "schema_version": "lixity-diff/1",
        "has_baseline": True,
        "base": base_snap,
        "current": target_snap,
        "deltas": deltas,
        "chapter_deltas": chapter_deltas,
        "chapter_matching": summarize_chapter_matching(chapter_deltas),
    }
