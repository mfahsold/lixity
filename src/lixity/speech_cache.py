"""Private bounded Qwen segment reuse; no manuscript text in cache metadata."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .io import FileUtils
from .speech_profiles import QWEN_BASE_MODEL, QWEN_DESIGN_MODEL, QWEN_MODEL, AudioProfile
from .speech_qwen import MAX_RESPONSE_BYTES

CACHE_BYTES = 2 * 1024**3
_SCHEMA = "lixity-speech-segment/1"
_MEMBER = re.compile(r"[0-9a-f]{64}\.(?:wav|json)\Z")


def project_audio_cache(project_root: str | Path) -> Path:
    """Keep private derived audio outside source folders, including read-only ones."""
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    if not base.is_absolute():
        raise ValueError("XDG_CACHE_HOME must be an absolute path")
    project = str(Path(project_root).expanduser().resolve())
    key = hashlib.sha256(project.encode()).hexdigest()
    return base / "lixity" / "speech" / key


class SpeechSegmentCache:
    """Reuse verified PCM for the same named model, voice, language and delivery.

    The model family is fixed. Replace/clear derived data after changing local
    checkpoint bytes within that family; cached audio is not a quality verdict.
    """

    def __init__(self, directory: Path, *, max_bytes: int = CACHE_BYTES) -> None:
        if directory.is_symlink():
            raise ValueError("Symlink speech cache directory is not allowed")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory, self.max_bytes = directory, max_bytes

    def _paths(self, text: str, profile: AudioProfile) -> tuple[str, Path, Path]:
        request = {"schema_version": _SCHEMA, "model": QWEN_MODEL, "text": text,
                   "language": profile.language, "voice": profile.voice,
                   "instructions": profile.instructions}
        if profile.engine == "qwen3-design":
            request["model"] = QWEN_DESIGN_MODEL
            request["voice_description"] = profile.voice_description
        elif profile.engine == "qwen3-base":
            request["model"] = QWEN_BASE_MODEL
            request["reference_id"] = profile.reference_id
        key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        audio, metadata = self.directory / (key + ".wav"), self.directory / (key + ".json")
        if audio.is_symlink() or metadata.is_symlink():
            raise ValueError("Symlink speech cache entry is not allowed")
        return key, audio, metadata

    @staticmethod
    def _valid_audio(data: bytes) -> bool:
        from .speech import _read_pcm

        try:
            return 44 < len(data) <= MAX_RESPONSE_BYTES and _read_pcm(data)[0] == (1, 2, 24000)
        except ValueError:
            return False

    def get(self, text: str, profile: AudioProfile) -> bytes | None:
        key, audio, metadata = self._paths(text, profile)
        try:
            if metadata.stat().st_size > 4096 or not 44 < audio.stat().st_size <= MAX_RESPONSE_BYTES:
                return None
            record = json.loads(metadata.read_text(encoding="utf-8"))
            data = audio.read_bytes()
            if (not isinstance(record, dict) or record.get("schema_version") != _SCHEMA
                    or record.get("request_sha256") != key or record.get("byte_length") != len(data)
                    or record.get("audio_sha256") != hashlib.sha256(data).hexdigest()
                    or not self._valid_audio(data)):
                return None
            return data
        except (OSError, ValueError, UnicodeError):
            # Derived data is reconstructible; a missing/invalid pair is a miss.
            return None

    def put(self, text: str, profile: AudioProfile, data: bytes) -> None:
        if not self._valid_audio(data):
            raise ValueError("Only complete Qwen PCM can be retained")
        key, audio, metadata = self._paths(text, profile)
        record = json.dumps({"schema_version": _SCHEMA, "request_sha256": key,
                             "audio_sha256": hashlib.sha256(data).hexdigest(), "byte_length": len(data)})
        if len(data) + len(record.encode()) > self.max_bytes:
            return
        FileUtils.atomic_write_bytes_if_changed(str(audio), data)
        FileUtils.atomic_write_if_changed(str(metadata), record)
        self._prune(keep=key)

    def _prune(self, *, keep: str) -> None:
        entries: dict[str, list[Path]] = {}
        for path in self.directory.iterdir():
            if _MEMBER.fullmatch(path.name) and not path.is_symlink() and path.is_file():
                entries.setdefault(path.stem, []).append(path)
        groups = []
        for key, paths in entries.items():
            try:
                stats = [p.stat() for p in paths]
            except FileNotFoundError:
                continue  # Another render may concurrently evict an entry.
            groups.append((max(s.st_mtime for s in stats), key, paths, sum(s.st_size for s in stats)))
        total = sum(group[3] for group in groups)
        for _mtime, key, paths, size in sorted(groups):
            if total <= self.max_bytes:
                break
            if key != keep:
                for path in paths:
                    path.unlink(missing_ok=True)
                total -= size
