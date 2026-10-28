"""Private, immutable project-local references for Qwen Base speech synthesis.

Reference identities cover exact WAV bytes and the exact UTF-8 transcript. Files
are explicit author data, not cache entries, and must be included in backups.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .speech_direction import SpeechSegment

from .io import FileUtils
from .research.repository import Repository
from .speech_qwen import MAX_BASE_REQUEST_BYTES, MAX_REFERENCE_BYTES, _decode_reference

_SCHEMA = "lixity-audio-reference/1"
_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECORD_BYTES = MAX_BASE_REQUEST_BYTES


@dataclass(frozen=True)
class SpeechReference:
    """An exact verified reference snapshot; private contents are not repr'd."""

    id: str
    audio: bytes = field(repr=False)
    transcript: str = field(repr=False)


def _identity(audio: bytes, transcript: str) -> str:
    text = transcript.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(_SCHEMA.encode("ascii") + b"\0")
    digest.update(len(audio).to_bytes(8, "big"))
    digest.update(audio)
    digest.update(len(text).to_bytes(8, "big"))
    digest.update(text)
    return digest.hexdigest()


def _repository(project: str | Path) -> Repository:
    root = Path(project).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Audio references require an existing project directory")
    return Repository(root)


def _path(repository: Repository, reference_id: str) -> Path:
    if not isinstance(reference_id, str) or not _IDENTITY.fullmatch(reference_id):
        raise ValueError("Invalid audio reference identity")
    return repository.safe(repository.root / ".lixity" / "audio-references" / f"{reference_id}.json")


def _read_record(repository: Repository, reference_id: str) -> SpeechReference:
    path = _path(repository, reference_id)
    # O_NONBLOCK prevents an unexpected FIFO from hanging a project read;
    # O_NOFOLLOW guards the final component independently of the path check.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_RECORD_BYTES:
            raise ValueError("Audio reference is not a bounded regular file")
        raw = stream.read(_MAX_RECORD_BYTES + 1)
    if len(raw) > _MAX_RECORD_BYTES:
        raise ValueError("Audio reference exceeds the supported size")
    try:
        obj = json.loads(raw)
        if (not isinstance(obj, dict) or set(obj) != {"schema_version", "id", "audio", "transcript"}
                or obj["schema_version"] != _SCHEMA or obj["id"] != reference_id):
            raise ValueError("Invalid audio reference record")
        audio, _frames = _decode_reference(obj["audio"], obj["transcript"])
        if _identity(audio, obj["transcript"]) != reference_id:
            raise ValueError("Audio reference identity does not match its contents")
    except (TypeError, UnicodeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid audio reference record") from exc
    return SpeechReference(reference_id, audio, obj["transcript"])


def load_reference(project: str | Path, reference_id: str) -> SpeechReference:
    """Read and verify an explicitly selected reference without creating files."""
    return _read_record(_repository(project), reference_id)


def references_for_plan(project: str | Path, plan: list[SpeechSegment]) -> dict[str, SpeechReference]:
    """Snapshot each distinct explicit Base reference needed by a plan."""
    ids = {row.profile.reference_id for row in plan if row.text and row.profile.engine == "qwen3-base"}
    return {reference_id: load_reference(project, reference_id) for reference_id in sorted(ids)}


def references_unchanged(project: str | Path, references: dict[str, SpeechReference]) -> bool:
    """Return false if any bound reference is missing, unreadable or changed."""
    try:
        return all(load_reference(project, key) == value for key, value in references.items())
    except (OSError, ValueError):
        return False


def validate_reference(reference: SpeechReference) -> None:
    """Reject an altered in-memory snapshot before using it for synthesis."""
    if not isinstance(reference, SpeechReference) or not _IDENTITY.fullmatch(reference.id):
        raise ValueError("Invalid audio reference identity")
    encoded = base64.b64encode(reference.audio).decode("ascii")
    _decode_reference(encoded, reference.transcript)
    if _identity(reference.audio, reference.transcript) != reference.id:
        raise ValueError("Audio reference identity does not match its contents")


def read_reference_input(path: str | Path, maximum: int) -> bytes:
    """Read one explicitly supplied bounded regular file, without following a final symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("Reference input must be a bounded regular file")
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("Reference input exceeds the supported size")
    return content


def save_reference(project: str | Path, audio: bytes, transcript: str) -> SpeechReference:
    """Create or reuse the immutable reference; never overwrite a corrupt record."""
    if not isinstance(audio, bytes) or len(audio) > MAX_REFERENCE_BYTES:
        raise ValueError("Invalid or oversized reference audio")
    encoded = base64.b64encode(audio).decode("ascii")
    _decode_reference(encoded, transcript)
    reference_id = _identity(audio, transcript)
    reference = SpeechReference(reference_id, audio, transcript)
    raw = json.dumps({"schema_version": _SCHEMA, "id": reference_id, "audio": encoded,
                      "transcript": transcript}, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > _MAX_RECORD_BYTES:
        raise ValueError("Audio reference exceeds the supported size")
    repository = _repository(project)
    path = _path(repository, reference_id)
    with repository.locked():
        try:
            existing = _read_record(repository, reference_id)
        except FileNotFoundError:
            def check() -> None:
                repository.safe(path)
                if path.exists():
                    raise ValueError("Audio reference appeared during creation; retry")

            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            FileUtils.atomic_write_bytes_if_changed(str(path), raw, before_replace=check)
        else:
            if existing != reference:
                raise ValueError("Existing audio reference identity does not match")
    return reference
