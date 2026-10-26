"""Validated project-local listening profiles and backend control capabilities."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
QWEN_LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "de": "German", "fr": "French", "ru": "Russian", "pt": "Portuguese",
    "es": "Spanish", "it": "Italian",
}
QWEN_VOICES = ("Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee")
PIPER_DEFAULT_VOICES = {"en": "en_US-lessac-medium", "de": "de_DE-thorsten-medium"}
_PROFILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_PIPER_VOICE = re.compile(r"(en|de)_[A-Z]{2}-[A-Za-z0-9_]+-(?:x_low|low|medium|high)\Z")


def _text(value: str, *, empty: bool = False) -> str:
    if (not empty and not value.strip()) or value != value.strip():
        raise ValueError("Audio text must be nonempty and have no surrounding whitespace")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Audio text must not contain control characters")
    return value


class AudioProfile(BaseModel):
    """One narrator's explicit synthesis controls; no executable or remote paths."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    name: str = Field(default="Narrator", min_length=1, max_length=100)
    engine: Literal["piper", "qwen3"] = "piper"
    language: str = "en"
    voice: str = Field(default="en_US-lessac-medium", min_length=1, max_length=100)
    speed: float = Field(default=1.0, ge=0.2, le=3.0)
    instructions: str = Field(default="", max_length=2000)
    paragraph_pause: float = Field(default=0.45, ge=0, le=10)
    scene_pause: float = Field(default=1.2, ge=0, le=10)
    pronunciations: dict[Annotated[str, Field(min_length=1, max_length=100)],
                         Annotated[str, Field(min_length=1, max_length=300)]] = Field(default_factory=dict, max_length=200)

    @field_validator("name", "voice", "language")
    @classmethod
    def valid_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("instructions")
    @classmethod
    def valid_instructions(cls, value: str) -> str:
        return _text(value, empty=True)

    @field_validator("pronunciations")
    @classmethod
    def valid_pronunciations(cls, values: dict[str, str]) -> dict[str, str]:
        for source, replacement in values.items():
            _text(source)
            _text(replacement)
        return values

    @model_validator(mode="after")
    def supported_controls(self) -> AudioProfile:
        if self.engine == "piper":
            if self.language not in PIPER_DEFAULT_VOICES:
                raise ValueError("Piper profiles support only en and de")
            match = _PIPER_VOICE.fullmatch(self.voice)
            if not match or match[1] != self.language:
                raise ValueError("Piper voice must be a safe cached model name matching the profile language")
            if self.instructions:
                raise ValueError("Piper does not support instructions")
        else:
            if self.language not in QWEN_LANGUAGES:
                raise ValueError("Unsupported Qwen language")
            if self.voice not in QWEN_VOICES:
                raise ValueError("Unsupported Qwen preset voice")
            if self.speed != 1.0:
                raise ValueError("Qwen does not support precise speed; speed must be 1.0")
        return self


class AudioSettings(BaseModel):
    """Versioned project profile collection with one existing selected narrator."""

    model_config = ConfigDict(extra="forbid", strict=True)
    schema_name: Literal["lixity-audio-settings/1"] = Field(default="lixity-audio-settings/1", alias="schema_version")
    selected: str
    profiles: dict[str, AudioProfile] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def valid_selection(self) -> AudioSettings:
        if any(not _PROFILE_ID.fullmatch(key) for key in self.profiles):
            raise ValueError("Audio profile IDs must be safe identifiers of at most 64 characters")
        if self.selected not in self.profiles:
            raise ValueError("Selected audio profile does not exist")
        return self


def parse_audio_settings(raw: object | None, *, language: str = "en") -> AudioSettings:
    """Return an explicit default only for absent settings; reject malformed data."""
    if raw is None:
        voice = PIPER_DEFAULT_VOICES.get(language)
        if voice is None:
            raise ValueError("No default Piper voice for this language; configure an explicit audio profile")
        return AudioSettings(selected="narrator", profiles={
            "narrator": AudioProfile(language=language, voice=voice),
        })
    return AudioSettings.model_validate(raw)


def resolve_audio_profile(
    config: Mapping[str, Any] | None, profile_id: str | None = None, *, language: str = "en",
) -> AudioProfile:
    """Resolve an explicit or saved selection without backend fallback."""
    settings = parse_audio_settings(config.get("audio") if config is not None else None, language=language)
    selected = profile_id if profile_id is not None else settings.selected
    if selected not in settings.profiles:
        raise ValueError(f"Unknown audio profile: {selected}")
    return settings.profiles[selected]


def audio_capabilities() -> dict[str, Any]:
    """Describe supported controls independently of optional runtime readiness.

    Piper accepts additional safe en/de cached model names at render time.
    Qwen timbres are multilingual; native-language quality requires auditioning.
    """
    return {
        "piper": {
            "name": "Piper", "languages": list(PIPER_DEFAULT_VOICES),
            "voices": {
                **{voice: {"name": voice, "languages": [language]}
                   for language, voice in PIPER_DEFAULT_VOICES.items()},
                "de_DE-thorsten_emotional-medium": {
                    "name": "Thorsten emotional (neutral delivery)", "languages": ["de"],
                },
            },
            "instructions": False,
            "speed": {"supported": True, "minimum": 0.2, "maximum": 3.0, "default": 1.0},
        },
        "qwen3": {
            "name": "Qwen3-TTS 1.7B CustomVoice", "languages": list(QWEN_LANGUAGES),
            "voices": {voice: {"name": voice, "languages": list(QWEN_LANGUAGES)} for voice in QWEN_VOICES},
            "instructions": True,
            "speed": {"supported": False, "minimum": 1.0, "maximum": 1.0, "default": 1.0},
            "model": QWEN_MODEL,
        },
    }
