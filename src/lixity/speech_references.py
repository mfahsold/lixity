"""Private, immutable project-local references for Qwen Base speech synthesis.

Reference identities cover exact WAV bytes and the exact UTF-8 transcript. Files
are explicit author data, not cache entries, and must be included in backups.
Ordered reference sets retain their complete generated probe and bind every
member recording to the manuscript and settings that produced the set.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .audio_pcm import SPEECH_PCM_FORMAT, read_pcm_wav
from .io import FileUtils
from .research.repository import Repository
from .speech_worker import MAX_BASE_REQUEST_BYTES, MAX_REFERENCE_BYTES, _decode_reference

if TYPE_CHECKING:
    from .speech_direction import SpeechSegment

_SCHEMA = "lixity-audio-reference/1"
_SET_SCHEMA = "lixity-audio-reference-set/1"
_PROBE_SCHEMA = "lixity-voice-probe-script/1"
_PROBE_METHOD_VERSION = "lixity-voice-probe-method/1"
_PROBE_DURATION_METHOD = "word_count_at_130_wpm"
_SET_AGGREGATION = {"contract": "ordered-independent-parts", "version": 1}
_IDENTITY = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECORD_BYTES = MAX_BASE_REQUEST_BYTES
_MAX_SET_RECORD_BYTES = 64 * 1024
_MIN_SET_PARTS = 3
_MAX_SET_PARTS = 6
_FRAME_BYTES_PER_SECOND = SPEECH_PCM_FORMAT[0] * SPEECH_PCM_FORMAT[1] * SPEECH_PCM_FORMAT[2]
_MIN_SET_FRAMES = 120 * _FRAME_BYTES_PER_SECOND
_MAX_SET_FRAMES = 180 * _FRAME_BYTES_PER_SECOND
_SET_FIELDS = {
    "schema_version", "id", "part_ids", "source_sha256", "settings_sha256",
    "probe_sha256", "language", "terms", "fallback_part_index", "probe",
}
_SET_SCHEMA_MARKERS = (_SET_SCHEMA, "part_ids", "fallback_part_index", "probe_sha256")
_PROBE_FIELDS = {
    "schema_version", "status", "language", "target_seconds", "estimated_seconds",
    "duration_method", "method_version", "source_sha256", "settings_sha256",
    "selected_terms", "covered_terms", "term_provenance", "warnings", "parts", "probe_sha256",
}
_PROBE_PART_FIELDS = {
    "index", "text", "words", "estimated_seconds", "terms", "substitutions", "phonemes", "sentences",
}
_PROBE_SENTENCE_FIELDS = {"text", "words", "start_line", "end_line", "terms", "dialogue"}
_PROBE_PRONUNCIATION_FIELDS = {"start", "end", "source", "replacement", "kind"}
_PROBE_TERM_KINDS = {"configured_term", "character", "lexicon", "frequent", "special_form"}


@dataclass(frozen=True)
class SpeechReference:
    """An exact verified single-reference snapshot; private contents are not repr'd."""

    id: str
    audio: bytes = field(repr=False)
    transcript: str = field(repr=False)


@dataclass(frozen=True)
class SpeechReferenceSet:
    """An immutable ordered aggregation of single references and its full probe."""

    id: str
    parts: tuple[SpeechReference, ...] = field(repr=False)
    source_sha256: str
    settings_sha256: str
    probe_sha256: str
    language: str
    terms: tuple[str, ...] = field(repr=False)
    fallback_part_index: int
    probe: dict[str, Any] = field(repr=False)

    def __post_init__(self) -> None:
        # A caller may reuse its generated script after saving. Keep this
        # snapshot independent while retaining the public dict-shaped contract.
        if isinstance(self.probe, dict):
            object.__setattr__(self, "probe", copy.deepcopy(self.probe))


VoiceReference = SpeechReference | SpeechReferenceSet


class VoiceReferenceInUse(ValueError):
    """A saved voice profile still points to the selected recording or set."""


def _identity(audio: bytes, transcript: str) -> str:
    text = transcript.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(_SCHEMA.encode("ascii") + b"\0")
    digest.update(len(audio).to_bytes(8, "big"))
    digest.update(audio)
    digest.update(len(text).to_bytes(8, "big"))
    digest.update(text)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Audio reference metadata must be canonical UTF-8 JSON") from exc


def _set_identity(
    parts: Sequence[SpeechReference],
    *,
    source_sha256: str,
    settings_sha256: str,
    probe_sha256: str,
    language: str,
    terms: Sequence[str],
    fallback_part_index: int,
    probe: dict[str, Any],
) -> str:
    """Hash a tagged, counted canonical document, never ambiguous concatenation."""
    payload = {
        "schema_version": _SET_SCHEMA,
        "aggregation": _SET_AGGREGATION,
        "part_count": len(parts),
        "part_ids": [part.id for part in parts],
        "source_sha256": source_sha256,
        "settings_sha256": settings_sha256,
        "probe_sha256": probe_sha256,
        "language": language,
        "term_count": len(terms),
        "terms": list(terms),
        "fallback_part_index": fallback_part_index,
        "probe": probe,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _repository(project: str | Path) -> Repository:
    root = Path(project).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Audio references require an existing project directory")
    return Repository(root)


def _path(repository: Repository, reference_id: str) -> Path:
    if not isinstance(reference_id, str) or not _IDENTITY.fullmatch(reference_id):
        raise ValueError("Invalid audio reference identity")
    return repository.safe(repository.root / ".lixity" / "audio-references" / f"{reference_id}.json")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> Any:
    raise ValueError("Non-finite JSON number")


def _parse_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_json_constant,
        )
    except (TypeError, UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Invalid {label} record") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {label} record")
    return value


def _read_limited(path: Path, maximum: int, label: str) -> bytes:
    # O_NONBLOCK prevents an unexpected FIFO from hanging a project read;
    # O_NOFOLLOW guards the final component independently of the path check.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{label} is not a bounded regular file")
        return stream.read(maximum + 1)


def _read_object(repository: Repository, reference_id: str, *, sets_only: bool = False) -> dict[str, Any]:
    path = _path(repository, reference_id)
    # Every set manifest is read through a 64 KiB gate. A large single /1
    # recording can still use the existing Base request bound after the gate.
    raw = _read_limited(path, _MAX_SET_RECORD_BYTES, "Audio reference")
    if len(raw) > _MAX_SET_RECORD_BYTES:
        if sets_only or any(marker.encode("utf-8") in raw for marker in _SET_SCHEMA_MARKERS):
            raise ValueError("Audio reference set exceeds the supported size")
        raw = _read_limited(path, _MAX_RECORD_BYTES, "Audio reference")
        if len(raw) > _MAX_RECORD_BYTES:
            raise ValueError("Audio reference is not a bounded regular file")
    obj = _parse_json(raw, "audio reference")
    schema = obj.get("schema_version")
    if schema == _SET_SCHEMA and len(raw) > _MAX_SET_RECORD_BYTES:
        raise ValueError("Audio reference set exceeds the supported size")
    if schema not in (_SCHEMA, _SET_SCHEMA):
        raise ValueError("Unsupported audio reference record schema; no legacy fallback is available")
    return obj


def _read_record(
    repository: Repository, reference_id: str, *, sets_only: bool = False, singles_only: bool = False,
) -> VoiceReference:
    obj = _read_object(repository, reference_id, sets_only=sets_only)
    schema = obj["schema_version"]
    if schema == _SCHEMA:
        if sets_only:
            raise ValueError("Audio reference identity belongs to a single recording, not a set")
        if set(obj) != {"schema_version", "id", "audio", "transcript"} or obj["id"] != reference_id:
            raise ValueError("Invalid audio reference record")
        audio, _frames = _decode_reference(obj["audio"], obj["transcript"])
        if _identity(audio, obj["transcript"]) != reference_id:
            raise ValueError("Audio reference identity does not match its contents")
        return SpeechReference(reference_id, audio, obj["transcript"])
    if singles_only:
        raise ValueError(
            "Audio reference identity belongs to a set; nested sets are not allowed. "
            "Use load_reference_set for a top-level set."
        )
    if set(obj) != _SET_FIELDS or obj["id"] != reference_id:
        raise ValueError("Invalid audio reference set record")
    return _load_set_record(repository, reference_id, obj)


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _IDENTITY.fullmatch(value) is not None


def _checked_language(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 20:
        raise ValueError("Invalid audio reference set language")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Invalid audio reference set language") from exc
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Invalid audio reference set language")
    return value


def _checked_terms(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("Invalid audio reference set terms")
    terms = tuple(value)
    for term in terms:
        if not isinstance(term, str) or not term or len(term) > 100:
            raise ValueError("Invalid audio reference set term")
        try:
            term.encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("Invalid audio reference set term") from exc
        if any(ord(char) < 32 or ord(char) == 127 for char in term):
            raise ValueError("Invalid audio reference set term")
    return terms


def _checked_fallback(value: object, part_count: int) -> int:
    if type(value) is not int or not 1 <= value <= part_count:
        raise ValueError("Audio reference set fallback_part_index must select an existing part")
    return value


def _probe_string(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError("Malformed voice probe script")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Malformed voice probe script") from exc
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise ValueError("Malformed voice probe script")
    return value


def _probe_terms(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Malformed voice probe script")
    terms = [_probe_string(term) for term in value]
    if any(len(term) > 100 for term in terms):
        raise ValueError("Malformed voice probe script terms")
    return terms


def _probe_warnings(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("Malformed voice probe warnings")
    for warning in value:
        if not isinstance(warning, dict) or set(warning) != {"code", "message"}:
            raise ValueError("Malformed voice probe warning")
        _probe_string(warning["code"])
        _probe_string(warning["message"])


def _probe_pronunciations(value: object, *, text: str, kind: str) -> None:
    if not isinstance(value, list):
        raise ValueError("Malformed voice probe pronunciation spans")
    for span in value:
        if not isinstance(span, dict) or set(span) != _PROBE_PRONUNCIATION_FIELDS:
            raise ValueError("Malformed voice probe pronunciation span")
        if (type(span["start"]) is not int or type(span["end"]) is not int
                or not 0 <= span["start"] < span["end"] <= len(text)):
            raise ValueError("Malformed voice probe pronunciation span")
        _probe_string(span["source"])
        _probe_string(span["replacement"])
        if span["kind"] != kind:
            raise ValueError("Malformed voice probe pronunciation kind")


def _probe_provenance(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("Malformed voice probe term provenance")
    required = {"term", "kind", "count"}
    allowed = required | {"ipa", "respelling"}
    for item in value:
        if not isinstance(item, dict) or not required <= set(item) <= allowed:
            raise ValueError("Malformed voice probe term provenance")
        _probe_string(item["term"])
        if not isinstance(item["kind"], str) or item["kind"] not in _PROBE_TERM_KINDS:
            raise ValueError("Malformed voice probe term kind")
        if type(item["count"]) is not int or item["count"] < 1:
            raise ValueError("Malformed voice probe term count")
        for key in ("ipa", "respelling"):
            if key in item:
                _probe_string(item[key])


def _validate_probe(
    probe: object, *, language: str, source_sha256: str, settings_sha256: str,
    part_count: int, expected_sha256: str,
) -> None:
    if not isinstance(probe, dict) or set(probe) != _PROBE_FIELDS:
        raise ValueError("Malformed voice probe script")
    if probe["schema_version"] != _PROBE_SCHEMA or probe["language"] != language:
        raise ValueError("Unsupported or mismatched voice probe script")
    if probe["status"] != "ready":
        raise ValueError("Voice probe script is not ready for reference publication")
    if probe["method_version"] != _PROBE_METHOD_VERSION:
        raise ValueError("Unsupported voice probe method version")
    if probe["duration_method"] != _PROBE_DURATION_METHOD:
        raise ValueError("Unsupported voice probe duration method")
    if probe["source_sha256"] != source_sha256 or probe["settings_sha256"] != settings_sha256:
        raise ValueError("Voice probe source or settings hash does not match the reference set identity")
    if type(probe["target_seconds"]) is not int or not 120 <= probe["target_seconds"] <= 180:
        raise ValueError("Malformed voice probe script duration")
    if type(probe["estimated_seconds"]) is not int or not 120 <= probe["estimated_seconds"] <= 180:
        raise ValueError("Malformed voice probe script duration")
    for key in ("selected_terms", "covered_terms"):
        terms = _probe_terms(probe[key])
        if len(terms) > 24:
            raise ValueError("Malformed voice probe script terms")
    _probe_provenance(probe["term_provenance"])
    _probe_warnings(probe["warnings"])
    parts = probe["parts"]
    if not isinstance(parts, list) or len(parts) != part_count:
        raise ValueError("Voice probe script parts do not match the reference set")
    for index, part in enumerate(parts, 1):
        if not isinstance(part, dict) or set(part) != _PROBE_PART_FIELDS:
            raise ValueError("Malformed voice probe script part")
        if type(part["index"]) is not int or part["index"] != index:
            raise ValueError("Malformed voice probe script part index")
        text = _probe_string(part["text"])
        if type(part["words"]) is not int or not 43 <= part["words"] <= 87:
            raise ValueError("Malformed voice probe script word count")
        if (type(part["estimated_seconds"]) is not int
                or part["estimated_seconds"] != round(part["words"] * 60 / 130)):
            raise ValueError("Malformed voice probe part duration")
        _probe_terms(part["terms"])
        _probe_pronunciations(part["substitutions"], text=text, kind="substitution")
        _probe_pronunciations(part["phonemes"], text=text, kind="phoneme")
        sentences = part["sentences"]
        if not isinstance(sentences, list) or not sentences:
            raise ValueError("Malformed voice probe script sentences")
        for sentence in sentences:
            if not isinstance(sentence, dict) or set(sentence) != _PROBE_SENTENCE_FIELDS:
                raise ValueError("Malformed voice probe sentence")
            _probe_string(sentence["text"])
            if type(sentence["words"]) is not int or not 4 <= sentence["words"] <= 32:
                raise ValueError("Malformed voice probe word count")
            if (type(sentence["start_line"]) is not int or type(sentence["end_line"]) is not int
                    or sentence["start_line"] < 1 or sentence["end_line"] < sentence["start_line"]):
                raise ValueError("Malformed voice probe source span")
            _probe_terms(sentence["terms"])
            if type(sentence["dialogue"]) is not bool:
                raise ValueError("Malformed voice probe dialogue marker")
    if not _valid_hash(probe["probe_sha256"]) or probe["probe_sha256"] != expected_sha256:
        raise ValueError("Voice probe checksum does not match probe_sha256")
    if _probe_sha256(probe) != expected_sha256:
        raise ValueError("Voice probe checksum does not match probe_sha256")


def _probe_sha256(probe: dict[str, Any]) -> str:
    from . import speech_probe

    exported = getattr(speech_probe, "voice_probe_sha256", None)
    if callable(exported):
        value = exported(probe)
    else:
        # Temporary local equivalent of the documented speech_probe contract.
        canonical = dict(probe)
        canonical.pop("probe_sha256", None)
        value = hashlib.sha256(_canonical_json(canonical)).hexdigest()
    if not isinstance(value, str) or _IDENTITY.fullmatch(value) is None:
        raise ValueError("Voice probe checksum is invalid")
    return value


def _checked_part_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not _MIN_SET_PARTS <= len(value) <= _MAX_SET_PARTS:
        raise ValueError("Invalid audio reference set parts")
    part_ids: list[str] = []
    for part_id in value:
        if not isinstance(part_id, str) or _IDENTITY.fullmatch(part_id) is None:
            raise ValueError("Invalid audio reference set parts")
        part_ids.append(part_id)
    if len(set(part_ids)) != len(part_ids):
        raise ValueError("Invalid audio reference set parts")
    return tuple(part_ids)


def _load_set_record(repository: Repository, reference_id: str, obj: dict[str, Any]) -> SpeechReferenceSet:
    part_ids = _checked_part_ids(obj["part_ids"])
    if not all(_valid_hash(obj[key]) for key in ("source_sha256", "settings_sha256", "probe_sha256")):
        raise ValueError("Invalid audio reference set hash")
    language = _checked_language(obj["language"])
    terms = _checked_terms(obj["terms"])
    fallback = _checked_fallback(obj["fallback_part_index"], len(part_ids))
    probe = obj["probe"]
    _validate_probe(
        probe, language=language, source_sha256=obj["source_sha256"],
        settings_sha256=obj["settings_sha256"], part_count=len(part_ids),
        expected_sha256=obj["probe_sha256"],
    )
    loaded_parts: list[SpeechReference] = []
    for part_id in part_ids:
        part = _read_record(repository, part_id, singles_only=True)
        if not isinstance(part, SpeechReference):
            raise ValueError("Audio reference sets cannot contain nested sets")
        loaded_parts.append(part)
    reference = SpeechReferenceSet(
        reference_id, tuple(loaded_parts), obj["source_sha256"], obj["settings_sha256"], obj["probe_sha256"],
        language, terms, fallback, probe,
    )
    validate_reference_set(reference)
    return reference


def load_reference(project: str | Path, reference_id: str) -> SpeechReference:
    """Read one single /1 recording; set identities require load_reference_set."""
    reference = _read_record(_repository(project), reference_id, singles_only=True)
    if isinstance(reference, SpeechReferenceSet):
        raise ValueError("Audio reference identity belongs to a set; use load_reference_set")
    return reference


def load_reference_set(project: str | Path, reference_id: str) -> SpeechReferenceSet:
    """Read and verify one bounded set manifest and all of its single parts."""
    reference = _read_record(_repository(project), reference_id, sets_only=True)
    if not isinstance(reference, SpeechReferenceSet):
        raise ValueError("Audio reference identity belongs to a single recording, not a set")
    return reference


def load_voice_reference(project: str | Path, reference_id: str) -> VoiceReference:
    """Read either a single /1 recording or an ordered reference set."""
    return _read_record(_repository(project), reference_id)


def references_for_plan(project: str | Path, plan: list[SpeechSegment]) -> dict[str, VoiceReference]:
    """Snapshot each distinct explicit single or set reference needed by a plan."""
    from .speech_profiles import profile_uses_reference

    ids = {row.profile.reference_id for row in plan if row.text and profile_uses_reference(row.profile)}
    return {reference_id: load_voice_reference(project, reference_id) for reference_id in sorted(ids)}


def references_unchanged(project: str | Path, references: Mapping[str, VoiceReference]) -> bool:
    """Return false if any bound single or set is missing, unreadable or changed."""
    try:
        return all(load_voice_reference(project, key) == value for key, value in references.items())
    except (OSError, ValueError):
        return False


def _validate_single(reference: SpeechReference) -> bytes:
    if not isinstance(reference, SpeechReference) or not _valid_hash(reference.id):
        raise ValueError("Invalid audio reference identity")
    if not isinstance(reference.audio, bytes):
        raise ValueError("Invalid audio reference snapshot")
    encoded = base64.b64encode(reference.audio).decode("ascii")
    _audio, frames = _decode_reference(encoded, reference.transcript)
    if _identity(reference.audio, reference.transcript) != reference.id:
        raise ValueError("Audio reference identity does not match its contents")
    return frames


def validate_reference(reference: VoiceReference) -> None:
    """Reject an altered in-memory single or set snapshot before synthesis."""
    if isinstance(reference, SpeechReferenceSet):
        validate_reference_set(reference)
        return
    if not isinstance(reference, SpeechReference):
        raise ValueError("Invalid voice reference snapshot")
    _validate_single(reference)


def validate_reference_set(reference: SpeechReferenceSet) -> None:
    """Verify set structure, metadata, probe checksum, identity and actual duration."""
    if not isinstance(reference, SpeechReferenceSet) or not _valid_hash(reference.id):
        raise ValueError("Invalid audio reference set identity")
    if not isinstance(reference.parts, tuple) or not _MIN_SET_PARTS <= len(reference.parts) <= _MAX_SET_PARTS:
        raise ValueError("A project voice probe requires three to six reference parts")
    if any(not isinstance(part, SpeechReference) for part in reference.parts):
        raise ValueError("Project voice probe parts must be single reference recordings")
    part_ids = tuple(part.id for part in reference.parts)
    if len(set(part_ids)) != len(part_ids):
        raise ValueError("Project voice probe parts must be distinct")
    total_frames = sum(len(_validate_single(part)) for part in reference.parts)
    if not _MIN_SET_FRAMES <= total_frames <= _MAX_SET_FRAMES:
        raise ValueError("Reference set audio must total 120 to 180 seconds")
    if not all(_valid_hash(value) for value in (
        reference.source_sha256, reference.settings_sha256, reference.probe_sha256,
    )):
        raise ValueError("Invalid audio reference set hash")
    language = _checked_language(reference.language)
    if not isinstance(reference.terms, tuple):
        raise ValueError("Invalid audio reference set terms")
    terms = _checked_terms(reference.terms)
    fallback = _checked_fallback(reference.fallback_part_index, len(reference.parts))
    _validate_probe(
        reference.probe, language=language, source_sha256=reference.source_sha256,
        settings_sha256=reference.settings_sha256, part_count=len(reference.parts),
        expected_sha256=reference.probe_sha256,
    )
    expected_id = _set_identity(
        reference.parts, source_sha256=reference.source_sha256, settings_sha256=reference.settings_sha256,
        probe_sha256=reference.probe_sha256, language=language, terms=terms,
        fallback_part_index=fallback, probe=reference.probe,
    )
    if expected_id != reference.id:
        raise ValueError("Audio reference set identity does not match its contents")


def _single_record(reference: SpeechReference) -> bytes:
    return _canonical_json({
        "schema_version": _SCHEMA,
        "id": reference.id,
        "audio": base64.b64encode(reference.audio).decode("ascii"),
        "transcript": reference.transcript,
    })


def prepare_reference(audio: bytes, transcript: str) -> SpeechReference:
    """Validate and address an immutable single /1 snapshot without writing files.

    Upload handlers can prepare every part first, then pass the returned
    snapshots to save_reference_set so no invalid request reaches the project.
    """
    if not isinstance(audio, bytes) or len(audio) > MAX_REFERENCE_BYTES:
        raise ValueError("Invalid or oversized reference audio")
    encoded = base64.b64encode(audio).decode("ascii")
    _decode_reference(encoded, transcript)
    return SpeechReference(_identity(audio, transcript), audio, transcript)


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


def _publish_single(repository: Repository, reference: SpeechReference, raw: bytes) -> bool:
    path = _path(repository, reference.id)
    try:
        existing = _read_record(repository, reference.id, singles_only=True)
    except FileNotFoundError:
        def check() -> None:
            repository.safe(path)
            if path.exists():
                raise ValueError("Audio reference appeared during creation; retry")

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return FileUtils.atomic_write_bytes_if_changed(str(path), raw, before_replace=check)
    if not isinstance(existing, SpeechReference) or existing != reference:
        raise ValueError("Existing audio reference identity does not match")
    return False


def save_reference(project: str | Path, audio: bytes, transcript: str) -> SpeechReference:
    """Create or reuse the immutable single reference; never overwrite a corrupt record."""
    reference = prepare_reference(audio, transcript)
    raw = _single_record(reference)
    if len(raw) > _MAX_RECORD_BYTES:
        raise ValueError("Audio reference exceeds the supported size")
    repository = _repository(project)
    with repository.locked():
        _publish_single(repository, reference, raw)
    return reference


def _set_record(reference: SpeechReferenceSet) -> bytes:
    return _canonical_json({
        "schema_version": _SET_SCHEMA,
        "id": reference.id,
        "part_ids": [part.id for part in reference.parts],
        "source_sha256": reference.source_sha256,
        "settings_sha256": reference.settings_sha256,
        "probe_sha256": reference.probe_sha256,
        "language": reference.language,
        "terms": list(reference.terms),
        "fallback_part_index": reference.fallback_part_index,
        "probe": reference.probe,
    })


def _publish_set(repository: Repository, reference: SpeechReferenceSet, raw: bytes) -> None:
    path = _path(repository, reference.id)
    try:
        existing = _read_record(repository, reference.id, sets_only=True)
    except FileNotFoundError:
        def check() -> None:
            repository.safe(path)
            if path.exists():
                raise ValueError("Audio reference set appeared during creation; retry")

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        FileUtils.atomic_write_bytes_if_changed(str(path), raw, before_replace=check)
        return
    if existing != reference:
        raise ValueError("Existing audio reference set identity does not match")


def _all_set_part_ids(repository: Repository) -> set[str]:
    directory = repository.root / ".lixity" / "audio-references"
    if not directory.is_dir():
        return set()
    referenced: set[str] = set()
    for candidate in directory.glob("*.json"):
        if not _IDENTITY.fullmatch(candidate.stem):
            continue
        try:
            record = _read_object(repository, candidate.stem)
        except FileNotFoundError:
            continue
        if record["schema_version"] != _SET_SCHEMA:
            continue
        if set(record) != _SET_FIELDS or record["id"] != candidate.stem:
            raise ValueError("Invalid audio reference set record")
        referenced.update(_checked_part_ids(record["part_ids"]))
    return referenced


def _rollback_new_parts(
    repository: Repository, created: Sequence[tuple[SpeechReference, Path]],
) -> None:
    """Best-effort removal of only intact, newly-created, unreferenced parts."""
    try:
        referenced = _all_set_part_ids(repository)
    except (OSError, ValueError, KeyError):
        return
    for reference, path in created:
        if reference.id in referenced:
            continue
        try:
            if _read_record(repository, reference.id, singles_only=True) != reference:
                continue
            repository.safe(path).unlink(missing_ok=True)
        except (OSError, ValueError, KeyError):
            continue


def save_reference_set(
    project: str | Path,
    parts: Sequence[SpeechReference],
    *,
    source_sha256: str,
    settings_sha256: str,
    probe_sha256: str,
    language: str,
    terms: Sequence[str] = (),
    fallback_part_index: int = 1,
    probe: dict[str, Any] | None = None,
) -> SpeechReferenceSet:
    """Atomically publish ordered single parts and one immutable set under one lock.

    All snapshots, metadata, the complete probe and actual total duration are
    validated before any filesystem write. Existing corrupt records are never
    replaced. A failed publication removes only newly-created part files that
    no published set references, where the filesystem permits.
    """
    if not isinstance(parts, Sequence) or isinstance(parts, (str, bytes)):
        raise ValueError("A project voice probe requires three to six reference parts")
    if not _MIN_SET_PARTS <= len(parts) <= _MAX_SET_PARTS:
        raise ValueError("A project voice probe requires three to six reference parts")
    if any(not isinstance(part, SpeechReference) for part in parts):
        raise ValueError("Project voice probe parts must be single reference recordings")
    prepared = tuple(parts)
    part_ids = tuple(part.id for part in prepared)
    if len(set(part_ids)) != len(part_ids):
        raise ValueError("Project voice probe parts must be distinct")
    if not all(_valid_hash(value) for value in (source_sha256, settings_sha256, probe_sha256)):
        raise ValueError("Invalid audio reference set hash")
    checked_language = _checked_language(language)
    if isinstance(terms, (str, bytes)):
        raise ValueError("Invalid audio reference set terms")
    checked_terms = _checked_terms(terms)
    fallback = _checked_fallback(fallback_part_index, len(prepared))
    if not isinstance(probe, dict):
        raise ValueError("A complete voice probe script is required")
    _validate_probe(
        probe, language=checked_language, source_sha256=source_sha256,
        settings_sha256=settings_sha256, part_count=len(prepared), expected_sha256=probe_sha256,
    )
    reference_id = _set_identity(
        prepared, source_sha256=source_sha256, settings_sha256=settings_sha256,
        probe_sha256=probe_sha256, language=checked_language, terms=checked_terms,
        fallback_part_index=fallback, probe=probe,
    )
    reference = SpeechReferenceSet(
        reference_id, prepared, source_sha256, settings_sha256, probe_sha256,
        checked_language, checked_terms, fallback, probe,
    )
    validate_reference_set(reference)
    records = tuple((part, _single_record(part)) for part in prepared)
    if any(len(raw) > _MAX_RECORD_BYTES for _part, raw in records):
        raise ValueError("Audio reference exceeds the supported size")
    raw_set = _set_record(reference)
    if len(raw_set) > _MAX_SET_RECORD_BYTES:
        raise ValueError("Project voice probe metadata exceeds the supported size")

    repository = _repository(project)
    created: list[tuple[SpeechReference, Path]] = []
    with repository.locked():
        try:
            for part, raw in records:
                if _publish_single(repository, part, raw):
                    created.append((part, _path(repository, part.id)))
            _publish_set(repository, reference, raw_set)
        except BaseException:
            _rollback_new_parts(repository, created)
            raise
    return reference


def _configured_reference_ids(repository: Repository) -> set[str]:
    from .config import read_explicit_project_config
    from .speech_profiles import parse_audio_settings

    raw_audio = read_explicit_project_config(repository.root).get("audio")
    if raw_audio is None:
        return set()
    settings = parse_audio_settings(raw_audio)
    return {profile.reference_id for profile in settings.profiles.values() if profile.reference_id}


def delete_reference(
    project: str | Path, reference_id: str, *, before_delete: Callable[[], None] | None = None,
) -> None:
    """Remove one single recording only when no profile or reference set uses it."""
    repository = _repository(project)
    path = _path(repository, reference_id)
    with repository.locked():
        configured_ids = _configured_reference_ids(repository)
        try:
            reference = _read_record(repository, reference_id)
        except FileNotFoundError as exc:
            raise ValueError("Saved recording is unavailable") from exc
        if isinstance(reference, SpeechReferenceSet):
            raise ValueError("Audio reference identity belongs to a set; use delete_reference_set")
        if reference_id in configured_ids:
            raise VoiceReferenceInUse("A saved voice profile uses this recording")
        if reference_id in _all_set_part_ids(repository):
            raise VoiceReferenceInUse("An audio reference set uses this recording")
        if before_delete is not None:
            before_delete()
        repository.safe(path).unlink()


def delete_reference_set(
    project: str | Path, reference_id: str, *, before_delete: Callable[[], None] | None = None,
) -> None:
    """Remove only a set manifest and retain every member recording.

    Deletion is blocked while a saved profile uses the set or any member ID.
    Retaining parts avoids a destructive cascade and permits later explicit
    deletion of each single recording after all set and profile references end.
    """
    repository = _repository(project)
    path = _path(repository, reference_id)
    with repository.locked():
        configured_ids = _configured_reference_ids(repository)
        try:
            reference = _read_record(repository, reference_id, sets_only=True)
        except FileNotFoundError as exc:
            raise ValueError("Saved recording set is unavailable") from exc
        if not isinstance(reference, SpeechReferenceSet):
            raise ValueError("Audio reference identity belongs to a single recording, not a set")
        member_ids = {part.id for part in reference.parts}
        if reference_id in configured_ids or member_ids.intersection(configured_ids):
            raise VoiceReferenceInUse("A saved voice profile uses this recording set or one of its parts")
        if before_delete is not None:
            before_delete()
        repository.safe(path).unlink()


CALIBRATION_TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "phonetic": (
            "Einst stritten sich Nordwind und Sonne, wer von ihnen beiden wohl der Stärkere wäre, "
            "als ein Wanderer, der in einen warmen Mantel gehüllt war, des Weges daherkam. "
            "Sie wurden einig, dass derjenige für den Stärkeren gelten sollte, der den Wanderer zwingen würde, "
            "seinen Mantel abzulegen. Der Nordwind blies mit aller Macht, aber je mehr er blies, desto fester "
            "hüllte sich der Wanderer in seinen Mantel ein. Endlich gab der Nordwind den Kampf auf. "
            "Da erwärmte die Sonne die Luft mit ihren freundlichen Strahlen, und schon nach wenigen Augenblicken "
            "zog der Wanderer seinen Mantel aus."
        ),
        "short": (
            "Zwölf Boxkämpfer jagen Viktor quer über den großen Sylter Deich. "
            "Ein kluger Richter prüft jede Aussage gewissenhaft und ruhig."
        ),
    },
    "en": {
        "phonetic": (
            "The North Wind and the Sun were disputing which was the stronger, "
            "when a traveler came along wrapped in a warm cloak. "
            "They agreed that the one who first succeeded in making the traveler take his cloak off "
            "should be considered stronger than the other. Then the North Wind blew as hard as he could, "
            "but the more he blew the more closely did the traveler fold his cloak around him; "
            "and at last the North Wind gave up the attempt. Then the Sun shone out warmly, "
            "and immediately the traveler took off his cloak."
        ),
        "short": (
            "The quick brown fox jumps over the lazy dog while sphinx of black quartz judges my vow. "
            "Every voice needs careful listening review."
        ),
    },
}


def get_calibration_text(language: str = "de", variant: str = "phonetic") -> str:
    """Return a standard phonetically balanced calibration text for voice references."""
    lang_map = CALIBRATION_TEXTS.get(language, CALIBRATION_TEXTS["de"])
    return lang_map.get(variant, lang_map["phonetic"])


def _record_paths(repository: Repository) -> list[Path]:
    directory = repository.root / ".lixity" / "audio-references"
    try:
        repository.safe(directory)
        if not directory.is_dir():
            return []
        return sorted(directory.glob("*.json"), key=lambda path: path.lstat().st_mtime, reverse=True)
    except (OSError, ValueError):
        return []


def _duration_and_rate(parts: Sequence[SpeechReference]) -> tuple[float, int]:
    frames = sum(len(read_pcm_wav(part.audio)[1]) for part in parts)
    params = read_pcm_wav(parts[0].audio)[0]
    channels, width, rate = params
    return frames / (rate * width * channels), rate


def list_references(project: str | Path) -> list[dict[str, Any]]:
    """List only single /1 recordings, including parts that belong to sets."""
    try:
        repo = _repository(project)
    except (ValueError, OSError):
        return []
    entries: list[dict[str, Any]] = []
    for path in _record_paths(repo):
        if not _IDENTITY.fullmatch(path.stem):
            continue
        try:
            reference = _read_record(repo, path.stem, singles_only=True)
            if not isinstance(reference, SpeechReference):
                continue
            duration, rate = _duration_and_rate((reference,))
        except (ValueError, OSError, KeyError):
            continue
        entries.append({
            "id": reference.id,
            "transcript": reference.transcript,
            "duration_seconds": round(duration, 2),
            "sample_rate": rate,
            "part_count": 1,
            "kind": "reference",
        })
    return entries


def list_reference_sets(project: str | Path) -> list[dict[str, Any]]:
    """Summarize only set manifests; never label a set with a member transcript."""
    try:
        repo = _repository(project)
    except (ValueError, OSError):
        return []
    entries: list[dict[str, Any]] = []
    for path in _record_paths(repo):
        if not _IDENTITY.fullmatch(path.stem):
            continue
        try:
            reference = _read_record(repo, path.stem, sets_only=True)
            if not isinstance(reference, SpeechReferenceSet):
                continue
            duration, rate = _duration_and_rate(reference.parts)
        except (ValueError, OSError, KeyError):
            continue
        entries.append({
            "id": reference.id,
            "kind": "set",
            "part_count": len(reference.parts),
            "part_ids": [part.id for part in reference.parts],
            "duration_seconds": round(duration, 2),
            "sample_rate": rate,
            "language": reference.language,
            "source_sha256": reference.source_sha256,
            "settings_sha256": reference.settings_sha256,
            "probe_sha256": reference.probe_sha256,
            "fallback_part_index": reference.fallback_part_index,
            "terms": list(reference.terms),
        })
    return entries


def generate_reference(
    project: str | Path,
    *,
    text: str | None = None,
    language: str = "de",
    voice_description: str | None = None,
    target: str = "local",
    opener: Any = None,
) -> SpeechReference:
    """Generate a synthetic voice reference from a calibration text and store it."""
    from .speech_profiles import AudioProfile
    from .speech_qwen import synthesize_qwen

    spoken_text = text.strip() if text and text.strip() else get_calibration_text(language)
    description = voice_description.strip() if voice_description and voice_description.strip() else (
        "A clear, natural German narrator voice with calm pacing and warmth." if language == "de"
        else "A clear, natural English narrator voice with calm pacing and warmth."
    )
    profile = AudioProfile(
        engine="qwen3-design",
        voice="design",
        language=language,
        voice_description=description,
    )
    audio = synthesize_qwen(spoken_text, profile, target=target, opener=opener)
    return save_reference(project, audio, spoken_text)
