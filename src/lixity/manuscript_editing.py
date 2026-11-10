"""Revision-bound UTF-8 manuscript writes and bounded local recovery.

The lock coordinates in-process writers only. External editors can still race
the final check/replace; retained versions support recovery, not universal locks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from threading import RLock
from typing import Any

from .io import FileUtils

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

    def __init__(self, root: Path, source: Path) -> None:
        self.root = root.resolve(strict=True)
        if source.is_symlink():
            raise ValueError("Editing a manuscript symlink is not supported")
        self.source = source.resolve(strict=True)
        if not self.source.is_relative_to(self.root) or self.source.suffix.lower() not in {".md", ".txt", ".markdown"}:
            raise ValueError("Choose a Markdown or text manuscript inside the selected project")
        self.document = _digest((str(self.root) + "\0" + str(self.source)).encode())
        self.directory = self.root / ".lixity" / "editing"

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
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS recovery (document TEXT, id TEXT, kind TEXT, content BLOB, created REAL, PRIMARY KEY(document,id))")
        db.execute("CREATE TABLE IF NOT EXISTS receipts (document TEXT, id TEXT, request TEXT, response TEXT, created REAL, PRIMARY KEY(document,id))")
        db.commit()
        return db

    def open(self) -> dict[str, Any]:
        with SOURCE_WRITE_LOCK:
            data = self._read()
            text, _, _ = _decode(data)
            recovery: list[dict[str, Any]] = []
            if self.directory.exists():
                with closing(self._database()) as db:
                    recovery = [{"id": row[0], "kind": row[1], "created": row[2]}
                                for row in db.execute("SELECT id,kind,created FROM recovery WHERE document=? ORDER BY created DESC", (self.document,))]
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
            return {"schema_version": "lixity-editor/1", "document": self.document,
                    "revision": _digest(row[0]), "id": identifier, "kind": row[1],
                    "text": _decode(row[0])[0]}

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
            if receipt:
                if receipt[0] != request:
                    raise ValueError("Operation identifier was reused for different content")
                response: dict[str, str] = json.loads(receipt[1])
                return response
            original = self._read()
            _, newline, bom = _decode(original)
            candidate = bom + text.replace("\n", newline).encode("utf-8")
            if len(candidate) > MAX_TEXT_BYTES:
                raise ValueError("Encoded manuscript exceeds the 4 MiB editing limit")
            prior = db.execute("SELECT content FROM recovery WHERE document=? AND id=?", (document, operation)).fetchone()
            if prior and prior[0] != candidate:
                raise ValueError("Operation identifier was reused for different content")
            count = db.execute("SELECT count(*) FROM recovery WHERE document=? AND kind='draft'", (document,)).fetchone()[0]
            if not prior and count >= 8:
                raise ValueError("Eight recovery drafts retained; recover or remove a draft before saving")
            with db:
                db.execute("INSERT OR REPLACE INTO recovery VALUES (?,?,?,?,?)", (document, operation, "draft", candidate, time.time()))
            # A retry after replacement but before receipt persistence is safe
            # only when this exact operation was already journaled.
            if _digest(original) != revision and not (prior and original == candidate):
                raise EditConflict("Manuscript changed elsewhere; your draft is retained")
            identity = self.source.stat()
            def guard() -> None:
                current = self.source.stat()
                if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino) or self._read() != original:
                    raise EditConflict("Manuscript changed while saving; your draft is retained")
            if original != candidate:
                with db:
                    db.execute("INSERT OR REPLACE INTO recovery VALUES (?,?,?,?,?)", (document, _digest(original), "version", original, time.time()))
                FileUtils.atomic_write_bytes_if_changed(str(self.source), candidate, before_replace=guard)
            response = {"document": document, "revision": _digest(candidate)}
            with db:
                db.execute("DELETE FROM recovery WHERE document=? AND id=? AND kind='draft'", (document, operation))
                db.execute("INSERT INTO receipts VALUES (?,?,?,?,?)", (document, operation, request, json.dumps(response), time.time()))
                db.execute("DELETE FROM recovery WHERE document=? AND kind='version' AND id NOT IN (SELECT id FROM recovery WHERE document=? AND kind='version' ORDER BY created DESC LIMIT 20)", (document, document))
                db.execute("DELETE FROM receipts WHERE document=? AND id NOT IN (SELECT id FROM receipts WHERE document=? ORDER BY created DESC LIMIT 100)", (document, document))
            return response

    def discard(self, identifier: str) -> None:
        """Explicitly remove a selected recovery copy, never the manuscript."""
        if not _ID.fullmatch(identifier):
            raise ValueError("Invalid recovery identifier")
        with SOURCE_WRITE_LOCK, closing(self._database()) as db, db:
            db.execute("DELETE FROM recovery WHERE document=? AND id=?", (self.document, identifier))
