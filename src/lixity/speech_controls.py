"""Model-neutral speech control semantics and explicit backend support.

These helpers do not interpret manuscript markup or promise that a model will
honour delivery instructions. A spoken-form substitution changes only the text
sent to the model; it is not a phonetic transcription.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer


class SpeechProsody(BaseModel):
    """Sparse model controls; omitted values inherit rather than reset a profile.

    Variance scales are dimensionless model parameters, not pitch in Hz, energy
    in dB, or guarantees about absolute audio duration.
    """

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, hide_input_in_errors=True)
    duration_scaling_factor: float | None = Field(default=None, ge=0.5, le=2.0)
    pitch_variance_scale: float | None = Field(default=None, ge=0.0, le=2.0)
    energy_variance_scale: float | None = Field(default=None, ge=0.0, le=2.0)
    pause_duration_scaling_factor: float | None = Field(default=None, ge=0.0, le=3.0)
    prosody_creativity: float | None = Field(default=None, ge=0.0, le=1.2)

    @model_serializer(mode="wrap")
    def serialize_controls(self, handler: SerializerFunctionWrapHandler) -> dict[str, float]:
        return {key: value for key, value in handler(self).items() if value is not None}


def prosody_capabilities() -> dict[str, dict[str, float | str]]:
    """Bounds and actual synthesis semantics shared by configuration and UI."""
    return {key: {"minimum": minimum, "maximum": maximum, "default": default,
                  "implementation": implementation} for key, minimum, maximum, default, implementation in (
        ("duration_scaling_factor", 0.5, 2.0, 1.0, "model-duration-scale"),
        ("pitch_variance_scale", 0.0, 2.0, 1.0, "model-pitch-variance"),
        ("energy_variance_scale", 0.0, 2.0, 1.0, "model-energy-variance"),
        ("pause_duration_scaling_factor", 0.0, 3.0, 1.0, "model-internal-pause-scale"),
        ("prosody_creativity", 0.0, 1.2, 0.1, "model-prosody-sampling"),
    )}


@dataclass(frozen=True)
class SpeechControlSupport:
    """Advertised implementation, separate from an author's desired effect."""

    pronunciation: Literal["text_substitution"]
    direction: Literal["model_interpreted", "unsupported"]
    pauses: Literal["explicit_silence"]
    phonemes: bool
    ssml: bool
    precise_rate: bool

    def as_dict(self) -> dict[str, object]:
        result: dict[str, object] = asdict(self)
        if self.phonemes:
            result["prosody"] = prosody_capabilities()
        return result


_QWEN_SUPPORT = SpeechControlSupport(
    pronunciation="text_substitution", direction="model_interpreted", pauses="explicit_silence",
    phonemes=False, ssml=False, precise_rate=False,
)
_QWEN_BASE_SUPPORT = SpeechControlSupport(
    pronunciation="text_substitution", direction="unsupported", pauses="explicit_silence",
    phonemes=False, ssml=False, precise_rate=False,
)
_TOUCAN_SUPPORT = SpeechControlSupport(
    pronunciation="text_substitution", direction="unsupported", pauses="explicit_silence",
    phonemes=True, ssml=False, precise_rate=False,
)


def speech_control_support(engine: str, *, supports_instructions: bool = False) -> SpeechControlSupport:
    """Describe the actual Lixity adapter, not the model's theoretical features."""
    if engine == "openai-compatible":
        return _QWEN_SUPPORT if supports_instructions else _QWEN_BASE_SUPPORT
    if engine == "ims-toucan":
        return _TOUCAN_SUPPORT
    if engine in ("qwen3-base", "coqui", "coqui-reference", "f5-tts"):
        return _QWEN_BASE_SUPPORT
    if engine not in ("qwen3", "qwen3-design"):
        raise ValueError("Unknown speech engine")
    return _QWEN_SUPPORT


def validate_pronunciation_keys(substitutions: Mapping[str, str], *, case_sensitive: bool = True) -> None:
    """Reject keys that Python's case-insensitive regex treats as equivalent."""
    if any(not key for key in substitutions):
        raise ValueError("Pronunciation terms must not be empty")
    if not case_sensitive:
        seen: list[str] = []
        for key in substitutions:
            if any(re.fullmatch(re.escape(other), key, re.IGNORECASE) for other in seen):
                raise ValueError("Case-insensitive pronunciation keys are ambiguous")
            seen.append(key)


@lru_cache(maxsize=64)
def _pronunciation_pattern(terms: tuple[str, ...], case_sensitive: bool,
                           whole_words: bool) -> tuple[list[str], re.Pattern[str]]:
    validate_pronunciation_keys(dict.fromkeys(terms, ""), case_sensitive=case_sensitive)
    keys = sorted(terms, key=len, reverse=True)
    alternatives = "|".join(f"(?P<term{idx}>{re.escape(key)})" for idx, key in enumerate(keys))
    expression = f"(?<!\\w)(?:{alternatives})(?!\\w)" if whole_words else alternatives
    pattern = re.compile(expression, 0 if case_sensitive else re.IGNORECASE)
    return keys, pattern


def pronunciation_spans(text: str, substitutions: Mapping[str, str], *,
                        case_sensitive: bool = True, whole_words: bool = False,
                        left_context: str = "", right_context: str = "") -> list[tuple[int, int, str]]:
    """Return actual longest-first matches in original text, including identity replacements."""
    if not substitutions:
        return []
    keys, pattern = _pronunciation_pattern(tuple(substitutions), case_sensitive, whole_words)
    result: list[tuple[int, int, str]] = []
    for match in pattern.finditer(text):
        if whole_words:
            before = text[match.start() - 1] if match.start() else left_context[-1:]
            after = text[match.end()] if match.end() < len(text) else right_context[:1]
            if any(char and (char.isalnum() or char == "_" or unicodedata.category(char).startswith("M"))
                   for char in (before, after)):
                continue
        group = match.lastgroup
        if group is None:  # All alternatives are named and exactly one must match.
            raise RuntimeError("Pronunciation match has no rule")
        result.append((match.start(), match.end(), substitutions[keys[int(group[4:])]]))
    return result


def apply_pronunciation(text: str, substitutions: Mapping[str, str], *,
                        case_sensitive: bool = True, whole_words: bool = False,
                        left_context: str = "", right_context: str = "") -> str:
    """Apply longest-first literal replacements without recursively matching replacements."""
    pieces: list[str] = []
    previous = 0
    for start, end, replacement in pronunciation_spans(text, substitutions, case_sensitive=case_sensitive,
            whole_words=whole_words, left_context=left_context, right_context=right_context):
        pieces.extend((text[previous:start], replacement))
        previous = end
    pieces.append(text[previous:])
    return "".join(pieces)


def phoneme_spans(text: str, overrides: Mapping[str, str]) -> list[tuple[int, int, str]]:
    """Exact whole-word IPA overrides on prepared text, with Unicode boundaries."""
    return pronunciation_spans(text, overrides, whole_words=True)


def phonetic_segments(text: str, overrides: Mapping[str, str], *, maximum: int) -> list[str]:
    """Split only at whitespace outside overrides; never truncate an IPA rule.

    Used only for profiles with actual phonetic rules. Plain text keeps the
    established sentence packing algorithm and unchanged cache identities.
    """
    protected = phoneme_spans(text, overrides)
    pieces: list[str] = []
    cursor = 0
    while cursor < len(text):
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor == len(text):
            break
        limit = min(len(text), cursor + maximum)
        if limit == len(text):
            pieces.append(text[cursor:].rstrip())
            break
        boundaries = [match.start() for match in re.finditer(r"\s+", text[cursor:limit + 1])]
        candidates = [cursor + index for index in boundaries
                      if index and not any(start < cursor + index < end for start, end, _ in protected)]
        if not candidates:
            raise ValueError("A word or phonetic override exceeds the speech segment limit; it was not split")
        end = candidates[-1]
        pieces.append(text[cursor:end].rstrip())
        cursor = end
    return pieces


def combine_delivery(profile_instruction: str, passage_instruction: str) -> str:
    """Combine explicit author instructions; the model decides their effect."""
    return " ".join(part for part in (profile_instruction, passage_instruction.strip()) if part)
