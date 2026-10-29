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


@dataclass(frozen=True)
class SpeechControlSupport:
    """Advertised implementation, separate from an author's desired effect."""

    pronunciation: Literal["text_substitution"]
    direction: Literal["model_interpreted", "unsupported"]
    pauses: Literal["explicit_silence"]
    phonemes: bool
    ssml: bool
    precise_rate: bool

    def as_dict(self) -> dict[str, str | bool]:
        return asdict(self)


_QWEN_SUPPORT = SpeechControlSupport(
    pronunciation="text_substitution", direction="model_interpreted", pauses="explicit_silence",
    phonemes=False, ssml=False, precise_rate=False,
)
_QWEN_BASE_SUPPORT = SpeechControlSupport(
    pronunciation="text_substitution", direction="unsupported", pauses="explicit_silence",
    phonemes=False, ssml=False, precise_rate=False,
)


def speech_control_support(engine: str) -> SpeechControlSupport:
    """Describe the actual Lixity adapter, not the model's theoretical features."""
    if engine in ("qwen3-base", "coqui", "coqui-reference"):
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


def apply_pronunciation(text: str, substitutions: Mapping[str, str], *,
                        case_sensitive: bool = True, whole_words: bool = False,
                        left_context: str = "", right_context: str = "") -> str:
    """Apply longest-first literal replacements, with optional matching constraints."""
    if not substitutions:
        return text
    keys, pattern = _pronunciation_pattern(tuple(substitutions), case_sensitive, whole_words)

    def replace(match: re.Match[str]) -> str:
        if whole_words:
            before = text[match.start() - 1] if match.start() else left_context[-1:]
            after = text[match.end()] if match.end() < len(text) else right_context[:1]
            if any(char and (char.isalnum() or char == "_" or unicodedata.category(char).startswith("M"))
                   for char in (before, after)):
                return match[0]
        group = match.lastgroup
        if group is None:  # All alternatives are named and exactly one must match.
            raise RuntimeError("Pronunciation match has no rule")
        return substitutions[keys[int(group[4:])]]

    return pattern.sub(replace, text)


def combine_delivery(profile_instruction: str, passage_instruction: str) -> str:
    """Combine explicit author instructions; the model decides their effect."""
    return " ".join(part for part in (profile_instruction, passage_instruction.strip()) if part)
