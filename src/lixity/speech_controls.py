"""Model-neutral speech control semantics and explicit backend support.

These helpers do not interpret manuscript markup or promise that a model will
honour delivery instructions. A spoken-form substitution changes only the text
sent to the model; it is not a phonetic transcription.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
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
    if engine == "qwen3-base":
        return _QWEN_BASE_SUPPORT
    if engine not in ("qwen3", "qwen3-design"):
        raise ValueError("Unknown speech engine")
    return _QWEN_SUPPORT


def apply_pronunciation(text: str, substitutions: Mapping[str, str]) -> str:
    """Apply literal, case-sensitive, longest-first replacements in one pass."""
    if not substitutions:
        return text
    if any(not key for key in substitutions):
        raise ValueError("Pronunciation terms must not be empty")
    pattern = re.compile("|".join(re.escape(key) for key in sorted(substitutions, key=len, reverse=True)))
    return pattern.sub(lambda match: substitutions[match[0]], text)


def combine_delivery(profile_instruction: str, passage_instruction: str) -> str:
    """Combine explicit author instructions; the model decides their effect."""
    return " ".join(part for part in (profile_instruction, passage_instruction.strip()) if part)
