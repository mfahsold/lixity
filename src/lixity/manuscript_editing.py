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
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .dialogue import find_indirect_speech_spans, indirect_speech_available
from .diversity import mattr as mattr_value
from .io import FileUtils
from .language import (
    compile_pattern,
    compile_word_pattern,
    quotation_capture_group,
    quotation_texts,
    resolve_language,
)
from .log import get_logger, log_event
from .markdown_parser import (
    COMMENT_STRIP_RE,
    chapter_heading_spans,
    prose_paragraphs,
    prose_text,
    split_chapters,
    split_scenes,
)
from .models import CorpusConfig
from .pacing import compute_rhythm_profile
from .sentences import split_prose_sentences

logger = get_logger("manuscript")

SOURCE_WRITE_LOCK = RLock()
MAX_TEXT_BYTES = 4 * 1024 * 1024
_ID = re.compile(r"[a-f0-9]{32,64}\Z")
_RE_HEADING_LINE = re.compile(r"(?m)^#+.*$")


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
            "length_entropy REAL, sticky_pct REAL, indirect_speech_per_1000 REAL, "
            "flags_count INTEGER, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
            "PRIMARY KEY(document, revision))"
        )
        table_info = db.execute("PRAGMA table_info(manuscript_revisions)").fetchall()
        existing_cols = {str(row[1]) for row in table_info}
        for col_name in ("length_entropy", "sticky_pct", "indirect_speech_per_1000"):
            if col_name not in existing_cols:
                db.execute(f"ALTER TABLE manuscript_revisions ADD COLUMN {col_name} REAL")
        flags_col = next((row for row in table_info if str(row[1]) == "flags_count"), None)
        if flags_col is not None and int(flags_col[3]) != 0:
            db.execute(
                "CREATE TABLE manuscript_revisions_new ("
                "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
                "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
                "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
                "length_entropy REAL, sticky_pct REAL, indirect_speech_per_1000 REAL, "
                "flags_count INTEGER, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
                "PRIMARY KEY(document, revision))"
            )
            db.execute(
                "INSERT INTO manuscript_revisions_new "
                "(document, revision, parent_revision, created_at, words, sentences, "
                "asl, asl_cv, dialogue_ratio, mattr, length_entropy, sticky_pct, "
                "indirect_speech_per_1000, flags_count, chapter_metrics) "
                "SELECT document, revision, parent_revision, created_at, words, sentences, "
                "asl, asl_cv, dialogue_ratio, mattr, length_entropy, sticky_pct, "
                "indirect_speech_per_1000, "
                "CASE WHEN flags_count = 0 THEN NULL ELSE flags_count END, "
                "chapter_metrics FROM manuscript_revisions"
            )
            db.execute("DROP TABLE manuscript_revisions")
            db.execute("ALTER TABLE manuscript_revisions_new RENAME TO manuscript_revisions")
        db.execute("CREATE INDEX IF NOT EXISTS idx_manuscript_revisions_doc_created ON manuscript_revisions (document, created_at DESC)")
        db.commit()
        return db

    def analyze_snapshot(self, text: str) -> dict[str, Any]:
        """Compute deterministic offline stylometric metrics for a manuscript snapshot."""
        return analyze_manuscript_snapshot(text, language=self.language)

    def _insert_revision_snapshot(
        self,
        db: sqlite3.Connection,
        revision: str,
        snap: dict[str, Any],
        *,
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
            "flags_count, chapter_metrics) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
        snap = self.analyze_snapshot(text)
        self._insert_revision_snapshot(
            db,
            revision,
            snap,
            parent_revision=parent_revision,
            created_at=created_at,
            flags_count=flags_count,
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
            orig_rev = _digest(original)
            target_rev = response["revision"]
            changed = original != candidate
            now = time.time()
            with db:
                need_orig = (
                    changed
                    and db.execute(
                        "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
                        (self.document, orig_rev),
                    ).fetchone()
                    is None
                )
                need_target = (
                    db.execute(
                        "SELECT 1 FROM manuscript_revisions WHERE document=? AND revision=?",
                        (self.document, target_rev),
                    ).fetchone()
                    is None
                )
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
        orig_snap = self.analyze_snapshot(original_text) if need_orig else None
        target_snap = self.analyze_snapshot(text) if need_target else None
        if orig_snap is not None or target_snap is not None:
            with SOURCE_WRITE_LOCK, closing(self._database()) as db, db:
                if orig_snap is not None:
                    self._insert_revision_snapshot(
                        db,
                        orig_rev,
                        orig_snap,
                        parent_revision=None,
                        created_at=now - 0.001,
                    )
                if target_snap is not None:
                    self._insert_revision_snapshot(
                        db,
                        target_rev,
                        target_snap,
                        parent_revision=orig_rev if changed else None,
                        created_at=now,
                    )
        log_event(logger, "manuscript_save", changed=changed, bytes=len(candidate))
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

    def timeline(self, limit: int = 30) -> list[dict[str, Any]]:
        """Return unique content snapshots by first recording time (oldest to newest)."""
        bounded = max(1, min(int(limit), 200))
        if not (self.directory / "recovery.sqlite3").exists():
            return []
        with SOURCE_WRITE_LOCK, closing(self._database()) as db:
            rows = db.execute(
                "SELECT revision, parent_revision, created_at, words, sentences, asl, asl_cv, "
                "dialogue_ratio, mattr, length_entropy, sticky_pct, indirect_speech_per_1000, "
                "flags_count, chapter_metrics "
                "FROM manuscript_revisions WHERE document=? "
                "ORDER BY created_at DESC, revision DESC LIMIT ?",
                (self.document, bounded),
            ).fetchall()
        return [self._row_to_revision(row) for row in reversed(rows)]

    def _recorded_revision(self, revision: str) -> dict[str, Any] | None:
        """Resolve an immutable measurement independently of the timeline window."""
        if not (self.directory / "recovery.sqlite3").exists():
            return None
        with closing(self._database()) as db:
            row = db.execute(
                "SELECT * FROM manuscript_revisions WHERE document=? AND revision=?",
                (self.document, revision),
            ).fetchone()
        return self._row_to_revision(row) if row is not None else None

    def delta(self, base_revision: str | None = None, target_revision: str | None = None) -> dict[str, Any]:
        """Compare retained measurements or the captured current source, never interpolating."""
        if base_revision is not None and not _ID.fullmatch(base_revision):
            raise ValueError("Invalid base revision identifier")
        if target_revision is not None and not _ID.fullmatch(target_revision):
            raise ValueError("Invalid target revision identifier")
        with SOURCE_WRITE_LOCK:
            history = self.timeline(limit=100)
            by_rev = {item["revision"]: item for item in history}
            if target_revision is not None:
                target = by_rev.get(target_revision) or self._recorded_revision(target_revision)
                if target is None:
                    raise ValueError("Target revision not found in manuscript history")
            else:
                source = self._read()
                text, _, _ = _decode(source)
                revision = _digest(source)
                target = by_rev.get(revision) or self._recorded_revision(revision)
                if target is None:
                    target = self.analyze_snapshot(text)
                    target["revision"] = revision
                    target["created_at"] = None
            base: dict[str, Any] | None = None
            if base_revision is not None:
                base = by_rev.get(base_revision) or self._recorded_revision(base_revision)
                if base is None:
                    raise ValueError("Base revision not found in manuscript history")
        if (base_revision is None and len(history) >= 2 and target in history
                and (target_revision is not None or target["revision"] == history[-1]["revision"])):
            # A content snapshot is not a save event. Reused or unrecorded current
            # bytes do not identify a previous save from which to infer a baseline.
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
        }


def analyze_manuscript_snapshot(text: str, *, language: str = "en") -> dict[str, Any]:
    """Compute deterministic offline stylometric metrics for a manuscript snapshot."""
    cfg = CorpusConfig(language=language or "en")
    resolved = resolve_language(cfg, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)
    lang_key = resolved.key
    function_words = resolved.function_words
    sticky_available = bool(function_words)
    ind_speech_available = indirect_speech_available(lang_key)

    if cfg.appendix_marker and cfg.appendix_marker in text:
        main_text, _ = text.split(cfg.appendix_marker, 1)
    else:
        main_text = text

    cleaned_main = COMMENT_STRIP_RE.sub("", main_text)
    prose_parts: list[str] = []
    cursor = 0
    for start, end, _line, _title in chapter_heading_spans(cleaned_main, cfg):
        prose_parts.append(cleaned_main[cursor:start])
        prose_parts.append("\n" if cleaned_main[end - 1:end] == "\n" else "")
        cursor = end
    prose_parts.append(cleaned_main[cursor:])
    legacy_clean_main = _RE_HEADING_LINE.sub("", "".join(prose_parts))
    clean_words = len(legacy_clean_main.split())

    prose_units = prose_paragraphs(main_text, cfg)
    prose_main = "\n\n".join(prose_units)

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

    dialog_matches = quotation_texts(dialogue_re, prose_main)
    dialog_words = sum(len(word_re.findall(m)) for m in dialog_matches)
    dialog_ratio = (dialog_words / n_tokens) * 100.0 if n_tokens else 0.0

    chapters: list[dict[str, Any]] = []
    all_corpus_sentence_lengths: list[int] = []
    total_sticky_sentences = 0
    total_sticky_denom = 0
    all_dialogue_words = 0
    all_indirect_speech = 0
    capture = quotation_capture_group(dialogue_re) if ind_speech_available else 0

    for number, title, body in split_chapters(main_text, cfg):
        cl_b = prose_text(body, _front_matter=False)
        c_words = word_re.findall(cl_b)
        if not c_words:
            chapters.append({
                "num": int(number),
                "title": str(title),
                "words": 0,
                "asl": None,
                "dialog_pct": None,
            })
            continue

        n_cw = len(c_words)
        c_sentences = split_prose_sentences(cl_b, lang_key)
        c_sent_tokens = [
            [w.lower() for w in word_re.findall(s)]
            for s in c_sentences
        ]
        c_sent_lengths = [len(toks) for toks in c_sent_tokens if toks]
        c_total_sents = len(c_sent_lengths)
        c_asl = (sum(c_sent_lengths) / c_total_sents) if c_total_sents else 0.0
        c_dial = quotation_texts(dialogue_re, cl_b)
        c_dial_words = sum(len(word_re.findall(m)) for m in c_dial)
        c_dial_pct = (c_dial_words / n_cw) * 100.0

        chapters.append({
            "num": int(number),
            "title": str(title),
            "words": int(n_cw),
            "asl": round(float(c_asl), 2) if c_total_sents > 0 else None,
            "dialog_pct": round(float(c_dial_pct), 2) if n_cw > 0 else None,
        })
        all_corpus_sentence_lengths.extend(c_sent_lengths)

        if sticky_available:
            raw_scenes, _ = split_scenes(body)
            if len(raw_scenes) == 1 and raw_scenes[0] == body:
                total_sticky_denom += c_total_sents
                for toks in c_sent_tokens:
                    n_w = len(toks)
                    if n_w >= cfg.sticky_min_words:
                        glue_pct = sum(1 for tok in toks if tok in function_words) / n_w * 100.0
                        if glue_pct >= cfg.sticky_glue_pct:
                            total_sticky_sentences += 1
            else:
                for scene_raw in raw_scenes:
                    scene_clean = prose_text(scene_raw, _front_matter=False)
                    if not word_re.findall(scene_clean):
                        continue
                    for s in split_prose_sentences(scene_clean, lang_key):
                        toks = [w.lower() for w in word_re.findall(s)]
                        n_w = len(toks)
                        if not n_w:
                            continue
                        total_sticky_denom += 1
                        if n_w >= cfg.sticky_min_words:
                            glue_pct = sum(1 for tok in toks if tok in function_words) / n_w * 100.0
                            if glue_pct >= cfg.sticky_glue_pct:
                                total_sticky_sentences += 1

        if ind_speech_available:
            all_dialogue_words += n_cw
            spans = sorted(
                match.span(capture)
                for match in dialogue_re.finditer(cl_b)
                if match.start(capture) >= 0 and match.end(capture) > match.start(capture)
            )
            quoted_spans: list[tuple[int, int]] = []
            for start, end in spans:
                if quoted_spans and start <= quoted_spans[-1][1]:
                    quoted_spans[-1] = (quoted_spans[-1][0], max(end, quoted_spans[-1][1]))
                else:
                    quoted_spans.append((start, end))
            all_indirect_speech += len(find_indirect_speech_spans(cl_b, quoted_spans, lang_key))

    rhythm = compute_rhythm_profile(
        all_corpus_sentence_lengths, short_sentence_max=cfg.short_sentence_max
    )
    raw_entropy = rhythm.get("length_entropy")
    sticky_pct_val = (
        (total_sticky_sentences / total_sticky_denom * 100.0)
        if (total_sticky_denom and sticky_available)
        else 0.0
    )
    indirect_per_1000 = (
        (all_indirect_speech / all_dialogue_words * 1000.0)
        if (all_dialogue_words and ind_speech_available)
        else 0.0
    )

    return {
        "words": int(clean_words),
        "sentences": int(total_sentences),
        "asl": round(float(asl), 3) if total_sentences > 0 else None,
        "asl_cv": round(float(sentence_cv), 4) if total_sentences > 0 else None,
        "dialogue_ratio": round(float(dialog_ratio), 3) if n_tokens > 0 else None,
        "mattr": round(float(mattr_score), 4) if mattr_score is not None else None,
        "length_entropy": round(float(raw_entropy), 4) if raw_entropy is not None else None,
        "sticky_pct": (
            round(float(sticky_pct_val), 2)
            if (sticky_available and total_sentences > 0)
            else None
        ),
        "indirect_speech_per_1000": (
            round(float(indirect_per_1000), 2)
            if (ind_speech_available and clean_words > 0)
            else None
        ),
        "flags_count": None,
        "chapter_metrics": chapters,
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
    return deltas, chapter_deltas


def compare_texts(
    base_text: str,
    target_text: str,
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Compare two manuscript Markdown strings and return enriched stylometric deltas."""
    base_snap = analyze_manuscript_snapshot(base_text, language=language)
    target_snap = analyze_manuscript_snapshot(target_text, language=language)
    deltas, chapter_deltas = diff_snapshots(base_snap, target_snap)
    return {
        "schema_version": "lixity-diff/1",
        "has_baseline": True,
        "base": base_snap,
        "current": target_snap,
        "deltas": deltas,
        "chapter_deltas": chapter_deltas,
    }
