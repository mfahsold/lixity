"""Private bounded speech segment reuse; no manuscript text in cache metadata."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .audio_pcm import SPEECH_PCM_FORMAT, read_pcm_wav
from .io import FileUtils
from .speech_engines import native_engine
from .speech_profiles import (
    EXTERNAL_ENGINES,
    AudioProfile,
    audio_capabilities,
    mlx_audio_uses_model_speed,
    profile_uses_reference,
)
from .speech_worker import MAX_RESPONSE_BYTES

if TYPE_CHECKING:
    from .speech_references import VoiceReference

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

    External entries also bind the endpoint, adapter and credential environment
    name. Clear derived data after changing checkpoint bytes or a provider's
    named model in place; cached audio is not a quality verdict.
    """

    def __init__(self, directory: Path, *, max_bytes: int = CACHE_BYTES) -> None:
        if directory.is_symlink():
            raise ValueError("Symlink speech cache directory is not allowed")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory, self.max_bytes = directory, max_bytes

    def _paths(
        self,
        text: str,
        profile: AudioProfile,
        reference: VoiceReference | None = None,
        *,
        reference_set: bool = False,
    ) -> tuple[str, Path, Path]:
        from .speech_references import SpeechReferenceSet

        request: dict[str, Any] = {"schema_version": _SCHEMA, "model": profile.model if profile.engine in EXTERNAL_ENGINES else native_engine(profile.engine).model, "text": text,
                   "language": profile.language, "voice": profile.voice,
                   "instructions": profile.instructions}
        if profile.engine in EXTERNAL_ENGINES:
            from .speech_providers import ADAPTER_ID, speech_endpoint

            request.update(endpoint=speech_endpoint(profile.base_url),
                           adapter=ADAPTER_ID if profile.engine == "openai-compatible" else "lixity-mlx-audio/1",
                           api_key_env=profile.api_key_env or "")
            if mlx_audio_uses_model_speed(profile):
                request["speed"] = profile.speed
        else:
            if profile.engine == "qwen3-design":
                request["voice_description"] = profile.voice_description
            if profile.engine == "ims-toucan":
                from .speech_controls import phoneme_spans

                request["adapter"] = "lixity-toucan/2"
                request["phonemes"] = {
                    text[start:end]: replacement
                    for start, end, replacement in phoneme_spans(text, profile.phonemes)
                }
                request["prosody"] = profile.prosody.model_dump()
        if profile_uses_reference(profile):
            request["reference_id"] = profile.reference_id
            is_reference_set = reference_set or isinstance(reference, SpeechReferenceSet)
            if is_reference_set:
                if reference is not None and reference.id != profile.reference_id:
                    raise ValueError("Reference set does not match the selected voice profile")
                request["reference_mode"] = "set"
                capability = audio_capabilities()[profile.engine]
                aggregation = capability.get("reference_set_aggregation")
                if aggregation is not None:
                    request["reference_set_aggregation"] = aggregation
                    request["reference_set_aggregation_version"] = capability["reference_set_aggregation_version"]
                fallback = capability.get("reference_set_fallback")
                if fallback is not None:
                    request["reference_set_fallback"] = fallback
                    if isinstance(reference, SpeechReferenceSet):
                        index = reference.fallback_part_index
                        if type(index) is not int or not 1 <= index <= len(reference.parts):
                            raise ValueError("Invalid Qwen Base reference-set fallback part")
                        request["reference_set_fallback_index"] = index
        key = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        audio, metadata = self.directory / (key + ".wav"), self.directory / (key + ".json")
        if audio.is_symlink() or metadata.is_symlink():
            raise ValueError("Symlink speech cache entry is not allowed")
        return key, audio, metadata

    @staticmethod
    def _valid_audio(data: bytes) -> bool:
        try:
            return 44 < len(data) <= MAX_RESPONSE_BYTES and read_pcm_wav(data)[0] == SPEECH_PCM_FORMAT
        except ValueError:
            return False

    def get(
        self,
        text: str,
        profile: AudioProfile,
        reference: VoiceReference | None = None,
        *,
        reference_set: bool = False,
    ) -> bytes | None:
        key, audio, metadata = self._paths(text, profile, reference, reference_set=reference_set)
        try:
            raw_record, _ = FileUtils.read_bounded_regular_bytes(metadata, maximum=4096)
            record = json.loads(raw_record.decode("utf-8"))
            if (not isinstance(record, dict) or record.get("schema_version") != _SCHEMA
                    or record.get("request_sha256") != key):
                return None
            data, _ = FileUtils.read_bounded_regular_bytes(audio, maximum=MAX_RESPONSE_BYTES)
            if (record.get("byte_length") != len(data)
                    or record.get("audio_sha256") != hashlib.sha256(data).hexdigest()
                    or not self._valid_audio(data)):
                return None
            return data
        except (OSError, ValueError):
            # Derived data is reconstructible; a missing/invalid pair is a miss.
            return None

    def put(
        self,
        text: str,
        profile: AudioProfile,
        data: bytes,
        reference: VoiceReference | None = None,
        *,
        reference_set: bool = False,
    ) -> None:
        if not self._valid_audio(data):
            raise ValueError("Only complete mono 24 kHz PCM can be retained")
        key, audio, metadata = self._paths(text, profile, reference, reference_set=reference_set)
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
