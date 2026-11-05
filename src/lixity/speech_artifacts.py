"""Verified chapter recordings retained independently from temporary speech jobs.

One atomic pointer per chapter selects its latest completed recording. The full
manuscript digest binds that recording to an exact source revision; imported
recordings remain explicitly imported, without inferred transcript alignment.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .audio_audit import _wav_format
from .io import FileUtils
from .log import get_logger
from .research.repository import Repository
from .speech_references import read_reference_input

MAX_CHAPTER_AUDIO_BYTES = 200 * 1024 * 1024
_SCHEMA = "lixity-chapter-audio/1"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_POINTER = re.compile(r"chapter-([1-9][0-9]{0,5})\.json\Z")


@dataclass(frozen=True)
class ChapterAudioArtifact:
    """Measured public metadata; no private source text or filesystem path."""

    source_sha256: str
    chapter: int
    origin: Literal["generated", "imported"]
    audio_sha256: str
    byte_length: int
    duration_seconds: float
    channels: int
    sample_rate_hz: int
    sample_width_bits: int
    frames: int


def _binding(source_sha256: str, chapter: int) -> None:
    if not isinstance(source_sha256, str) or not _HASH.fullmatch(source_sha256):
        raise ValueError("Chapter audio requires an exact manuscript SHA-256")
    if type(chapter) is not int or not 1 <= chapter <= 999999:
        raise ValueError("Chapter audio requires a positive chapter number")


def _repository(project_root: str | Path) -> Repository:
    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Chapter audio requires an existing project directory")
    return Repository(root)


def _folder(repo: Repository) -> Path:
    return repo.safe(repo.root / ".lixity/audio/exports")


def _pointer(repo: Repository, chapter: int) -> Path:
    return repo.safe(_folder(repo) / f"chapter-{chapter}.json")


def _audio_path(repo: Repository, entry: ChapterAudioArtifact) -> Path:
    return repo.safe(_folder(repo) / f"chapter-{entry.chapter}-{entry.audio_sha256}.wav")


def _measure(audio: bytes, source_sha256: str, chapter: int,
             origin: Literal["generated", "imported"]) -> ChapterAudioArtifact:
    _binding(source_sha256, chapter)
    if origin not in ("generated", "imported"):
        raise ValueError("Unknown chapter audio origin")
    if not isinstance(audio, bytes) or not 44 < len(audio) <= MAX_CHAPTER_AUDIO_BYTES:
        raise ValueError("Chapter WAV audio is missing or exceeds the size limit")
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE" or int.from_bytes(audio[4:8], "little") + 8 != len(audio):
        raise ValueError("Chapter audio must be a complete PCM WAV file")
    try:
        _wav_format(io.BytesIO(audio))
        with wave.open(io.BytesIO(audio), "rb") as source:
            channels, width, rate, frames, compression, _ = source.getparams()
            if (compression != "NONE" or channels not in (1, 2) or width != 2
                    or not 8000 <= rate <= 192000 or frames < 1):
                raise ValueError("Chapter audio requires mono or stereo 16-bit PCM WAV, 8–192 kHz")
            if len(source.readframes(frames + 1)) != frames * channels * width:
                raise ValueError("Chapter PCM WAV data is truncated")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Chapter audio must be a complete PCM WAV file") from exc
    return ChapterAudioArtifact(source_sha256, chapter, origin, hashlib.sha256(audio).hexdigest(),
                                len(audio), frames / rate, channels, rate, width * 8, frames)


def _read_pointer(repo: Repository, chapter: int) -> ChapterAudioArtifact:
    raw = read_reference_input(_pointer(repo, chapter), 4096)
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict) or obj.pop("schema_version", None) != _SCHEMA:
            raise ValueError("Invalid chapter audio metadata schema")
        entry = ChapterAudioArtifact(**obj)
        _binding(entry.source_sha256, entry.chapter)
        if (entry.chapter != chapter or entry.origin not in ("generated", "imported")
                or not isinstance(entry.audio_sha256, str) or not _HASH.fullmatch(entry.audio_sha256)
                or type(entry.byte_length) is not int or not 44 < entry.byte_length <= MAX_CHAPTER_AUDIO_BYTES
                or type(entry.frames) is not int or entry.frames < 1
                or type(entry.channels) is not int or entry.channels not in (1, 2)
                or type(entry.sample_rate_hz) is not int or not 8000 <= entry.sample_rate_hz <= 192000
                or type(entry.sample_width_bits) is not int or entry.sample_width_bits != 16
                or type(entry.duration_seconds) not in (int, float)
                or entry.duration_seconds != entry.frames / entry.sample_rate_hz):
            raise ValueError("Invalid chapter audio metadata")
    except (TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid chapter audio metadata") from exc
    return entry


def read_project_audio(project_root: str | Path, artifact: ChapterAudioArtifact) -> bytes:
    """Read a still-current entry and verify its measured metadata and checksum."""
    repo = _repository(project_root)
    _binding(artifact.source_sha256, artifact.chapter)
    if _read_pointer(repo, artifact.chapter) != artifact:
        raise ValueError("Chapter audio selection changed; retry the export")
    audio = read_reference_input(_audio_path(repo, artifact), MAX_CHAPTER_AUDIO_BYTES)
    if _measure(audio, artifact.source_sha256, artifact.chapter, artifact.origin) != artifact:
        raise ValueError("Chapter audio checksum or measured metadata does not match")
    return audio


def list_project_audio(project_root: str | Path, *, source_sha256: str,
                       max_chapter: int) -> list[ChapterAudioArtifact]:
    """List verified exact-source recordings; never open chapters beyond the cap.

    A valid pointer for another source revision is ignored without reading its
    audio. Malformed metadata and corrupt selected audio are explicit failures.
    """
    _binding(source_sha256, 1)
    if type(max_chapter) is not int or not 0 <= max_chapter <= 999999:
        raise ValueError("Invalid chapter audio export limit")
    repo = _repository(project_root)
    folder = _folder(repo)
    if not folder.exists() or max_chapter == 0:
        return []
    entries = []
    pointers = 0
    total_bytes = 0
    for path in folder.iterdir():
        match = _POINTER.fullmatch(path.name)
        if match is None or int(match[1]) > max_chapter:
            continue
        pointers += 1
        if pointers > 1000:
            raise ValueError("Chapter audio inventory exceeds the 1000-chapter budget")
        entry = _read_pointer(repo, int(match[1]))
        if entry.source_sha256 == source_sha256:
            total_bytes += entry.byte_length
            if total_bytes > MAX_CHAPTER_AUDIO_BYTES:
                raise ValueError("Selected chapter audio exceeds the combined 200 MiB budget")
            entries.append(entry)
    for entry in entries:
        read_project_audio(project_root, entry)
    return sorted(entries, key=lambda entry: entry.chapter)


def retain_chapter_audio(project_root: str | Path, audio: bytes, *, source_sha256: str,
                         chapter: int, origin: Literal["generated", "imported"],
                         valid: Callable[[], bool] | None = None) -> ChapterAudioArtifact:
    """Atomically select a completed recording, preserving an existing one on failure.

    Callers that can change workspace context must hold their context lock while
    calling this function. The optional guard is checked before each replacement.
    """
    entry = _measure(audio, source_sha256, chapter, origin)
    repo = _repository(project_root)
    folder = _folder(repo)
    pointer, path = _pointer(repo, chapter), _audio_path(repo, entry)

    def check() -> None:
        repo.safe(pointer)
        repo.safe(path)
        if valid is not None and not valid():
            raise ValueError("Chapter audio context changed before retention; retry")

    with repo.locked():
        check()
        try:
            previous = _read_pointer(repo, chapter)
        except FileNotFoundError:
            previous = None
        if previous is not None:
            _audio_path(repo, previous)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        FileUtils.atomic_write_bytes_if_changed(str(path), audio, before_replace=check)
        try:
            check()
            raw = json.dumps({"schema_version": _SCHEMA, **asdict(entry)}, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")
            FileUtils.atomic_write_bytes_if_changed(str(pointer), raw, before_replace=check)
        except BaseException:
            if previous is None or previous.audio_sha256 != entry.audio_sha256:
                path.unlink(missing_ok=True)
            raise
        if previous is not None and previous.audio_sha256 != entry.audio_sha256:
            try:
                _audio_path(repo, previous).unlink(missing_ok=True)
            except (OSError, ValueError):
                # The pointer is already committed. Report cleanup degradation
                # without falsely reporting a failed import or exposing paths.
                get_logger("speech.artifacts").warning("chapter_audio stage=cleanup status=failed")
    return entry
