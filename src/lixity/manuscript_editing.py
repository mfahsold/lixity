"""Revision-bound UTF-8 manuscript writes and bounded local recovery.

The lock coordinates in-process writers only. External editors can still race
the final check/replace; retained versions support recovery, not universal locks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .analyzer import CorpusAnalyzer
from .io import FileUtils
from .log import get_logger, log_event
from .models import CorpusConfig

logger = get_logger("manuscript")

SOURCE_WRITE_LOCK = RLock()
MAX_TEXT_BYTES = 4 * 1024 * 1024
_ID = re.compile(r"[a-f0-9]{32,64}\Z")


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


class ManuscriptStore:
    """Selected-file editing; no request may choose a filesystem destination."""

    def __init__(self, root: Path, source: Path, *, language: str = "en") -> None:
        self.root = root.resolve(strict=True)
        if source.is_symlink():
            raise ValueError("Editing a manuscript symlink is not supported")
        self.source = source.resolve(strict=True)
        if not self.source.is_relative_to(self.root) or self.source.suffix.lower() not in {".md", ".txt", ".markdown"}:
            raise ValueError("Choose a Markdown or text manuscript inside the selected project")
        self.document = _digest((str(self.root) + "\0" + str(self.source)).encode())
        self.directory = self.root / ".lixity" / "editing"
        self.language = language or "en"

    def _read(self) -> bytes:
        if self.source.is_symlink() or not self.source.resolve(strict=True).is_relative_to(self.root):
            raise ValueError("Manuscript path changed")
        if self.source.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("Manuscript exceeds the 4 MiB editing limit")
        return FileUtils._read_regular_bytes(str(self.source))

    def _database(self) -> sqlite3.Connection:
        if self.directory.parent.is_symlink() or self.directory.is_symlink():
            raise ValueError("Recovery directory must not be a symlink")
        self.directory.parent.mkdir(mode=0o700, exist_ok=True)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        path = self.directory / "recovery.sqlite3"
        if path.is_symlink():
            raise ValueError("Recovery database must not be a symlink")
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS recovery (document TEXT, id TEXT, kind TEXT, content BLOB, created REAL, PRIMARY KEY(document,id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_recovery_doc_created ON recovery (document, kind, created DESC)")
        db.execute("CREATE TABLE IF NOT EXISTS receipts (document TEXT, id TEXT, request TEXT, response TEXT, created REAL, PRIMARY KEY(document,id))")
        db.execute("CREATE INDEX IF NOT EXISTS idx_receipts_doc_created ON receipts (document, created DESC)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS manuscript_revisions ("
            "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
            "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
            "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
            "flags_count INTEGER NOT NULL DEFAULT 0, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
            "PRIMARY KEY(document, revision))"
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_manuscript_revisions_doc_created ON manuscript_revisions (document, created_at DESC)")
        db.commit()
        return db

    def analyze_snapshot(self, text: str) -> dict[str, Any]:
        """Compute deterministic offline stylometric metrics for a manuscript snapshot."""
        metrics = CorpusAnalyzer(CorpusConfig(language=self.language), sample_text=text).analyze_text(text)
        chapters = [
            {
                "num": int(ch.num),
                "title": str(ch.title),
                "words": int(ch.words),
                "asl": round(float(ch.asl), 2) if ch.sentences > 0 else None,
                "dialog_pct": round(float(ch.dialog_pct), 2) if ch.words > 0 else None,
            }
            for ch in metrics.chapters
        ]
        return {
            "words": int(metrics.clean_words),
            "sentences": int(metrics.total_sentences),
            "asl": round(float(metrics.asl), 3) if metrics.total_sentences > 0 else None,
            "asl_cv": round(float(metrics.sentence_cv), 4) if metrics.total_sentences > 0 else None,
            "dialogue_ratio": round(float(metrics.dialog_ratio), 3) if metrics.tokens > 0 else None,
            "mattr": round(float(metrics.mattr), 4) if metrics.mattr is not None else None,
            "flags_count": 0,
            "chapter_metrics": chapters,
        }

    def _record_revision(
        self,
        db: sqlite3.Connection,
        revision: str,
        text: str,
        *,
        parent_revision: str | None = None,
        created_at: float | None = None,
        flags_count: int = 0,
    ) -> None:
        existing = db.execute(
            "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
            (self.document, revision),
        ).fetchone()
        if existing is not None:
            return
        snap = self.analyze_snapshot(text)
        ts = float(created_at if created_at is not None else time.time())
        db.execute(
            "INSERT INTO manuscript_revisions "
            "(document, revision, parent_revision, created_at, words, sentences, asl, asl_cv, "
            "dialogue_ratio, mattr, flags_count, chapter_metrics) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
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
                int(flags_count),
                json.dumps(snap["chapter_metrics"], ensure_ascii=False),
            ),
        )

    def open(self) -> dict[str, Any]:
        with SOURCE_WRITE_LOCK:
            data = self._read()
            text, _, _ = _decode(data)
            recovery: list[dict[str, Any]] = []
            if self.directory.exists():
                with closing(self._database()) as db:
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
        with SOURCE_WRITE_LOCK, closing(self._database()) as db:
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
        with SOURCE_WRITE_LOCK, closing(self._database()) as db:
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
            now = time.time()
            with db:
                if original != candidate:
                    self._record_revision(db, _digest(original), original_text, parent_revision=None, created_at=now - 0.001)
                    self._record_revision(db, response["revision"], text, parent_revision=_digest(original), created_at=now)
                else:
                    self._record_revision(db, response["revision"], text, parent_revision=None, created_at=now)
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
            log_event(logger, "manuscript_save", changed=original != candidate, bytes=len(candidate))
            return response

    def discard(self, identifier: str) -> None:
        """Explicitly remove a selected recovery copy, never the manuscript."""
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid recovery identifier")
        with SOURCE_WRITE_LOCK, closing(self._database()) as db, db:
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
            "flags_count": int(row["flags_count"]),
            "chapter_metrics": json.loads(str(row["chapter_metrics"])),
        }

    def timeline(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return chronological revision snapshots for this manuscript (oldest to newest)."""
        bounded = max(1, min(int(limit), 200))
        if not (self.directory / "recovery.sqlite3").exists():
            return []
        with SOURCE_WRITE_LOCK, closing(self._database()) as db:
            rows = db.execute(
                "SELECT revision, parent_revision, created_at, words, sentences, asl, asl_cv, "
                "dialogue_ratio, mattr, flags_count, chapter_metrics "
                "FROM manuscript_revisions WHERE document=? "
                "ORDER BY created_at DESC, revision DESC LIMIT ?",
                (self.document, bounded),
            ).fetchall()
        return [self._row_to_revision(row) for row in reversed(rows)]

    def delta(self, base_revision: str | None = None, target_revision: str | None = None) -> dict[str, Any]:
        """Compute exact stylometric deltas between two recorded revisions (never interpolated)."""
        if base_revision is not None and not _ID.fullmatch(base_revision):
            raise ValueError("Invalid base revision identifier")
        if target_revision is not None and not _ID.fullmatch(target_revision):
            raise ValueError("Invalid target revision identifier")
        history = self.timeline(limit=100)
        if not history:
            text, _, _ = _decode(self._read())
            current_snap = self.analyze_snapshot(text)
            current_snap["revision"] = _digest(self._read())
            current_snap["created_at"] = None
            return {
                "schema_version": "lixity-timeline/1",
                "document": self.document,
                "has_baseline": False,
                "revisions_count": 0,
                "base": None,
                "current": current_snap,
                "deltas": None,
                "chapter_deltas": [],
            }
        by_rev = {item["revision"]: item for item in history}
        target = by_rev.get(target_revision) if target_revision else history[-1]
        if target is None:
            raise ValueError("Target revision not found in manuscript history")
        base: dict[str, Any] | None = None
        if base_revision is not None:
            base = by_rev.get(base_revision)
            if base is None:
                raise ValueError("Base revision not found in manuscript history")
        elif len(history) >= 2:
            # Prefer earliest revision from the same UTC day as target (session start);
            # otherwise fall back to the immediate predecessor revision.
            target_day = datetime.fromtimestamp(target["created_at"], tz=timezone.utc).date()
            same_day = [
                item for item in history
                if item["revision"] != target["revision"]
                and item["created_at"] <= target["created_at"]
                and datetime.fromtimestamp(item["created_at"], tz=timezone.utc).date() == target_day
            ]
            if same_day:
                base = same_day[0]
            else:
                idx = history.index(target)
                if idx > 0:
                    base = history[idx - 1]
        if base is None:
            return {
                "schema_version": "lixity-timeline/1",
                "document": self.document,
                "has_baseline": False,
                "revisions_count": len(history),
                "base": None,
                "current": target,
                "deltas": None,
                "chapter_deltas": [],
            }

        def _diff(key: str, digits: int) -> float | int | None:
            a, b = base.get(key), target.get(key)
            if a is None or b is None:
                return None
            val = b - a
            return int(val) if digits == 0 else round(float(val), digits)

        deltas = {
            "words": _diff("words", 0),
            "sentences": _diff("sentences", 0),
            "asl": _diff("asl", 2),
            "asl_cv": _diff("asl_cv", 4),
            "dialogue_ratio": _diff("dialogue_ratio", 2),
            "mattr": _diff("mattr", 4),
            "flags_count": _diff("flags_count", 0),
        }
        base_chapters = {int(c["num"]): c for c in base.get("chapter_metrics", [])}
        chapter_deltas: list[dict[str, Any]] = []
        for ch in target.get("chapter_metrics", []):
            prev = base_chapters.get(int(ch["num"]))
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
            chapter_deltas.append({
                "num": int(ch["num"]),
                "title": str(ch["title"]),
                "words": int(ch["words"]),
                "words_delta": words_d,
                "asl": ch.get("asl"),
                "asl_delta": asl_d,
                "dialog_pct": ch.get("dialog_pct"),
                "dialog_pct_delta": dlg_d,
            })
        return {
            "schema_version": "lixity-timeline/1",
            "document": self.document,
            "has_baseline": True,
            "revisions_count": len(history),
            "base": base,
            "current": target,
            "deltas": deltas,
            "chapter_deltas": chapter_deltas,
        }
