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
_PROFILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_REMOVED_ENGINE = ("Piper audio profiles are no longer supported. Make a backup and explicitly migrate "
                   "each profile to a Qwen preset voice; the old voice and precise speed are not equivalent. "
                   "Use audio-migrate --project PATH --replace PROFILE=VOICE to review the migration.")


def _text(value: str, *, empty: bool = False) -> str:
    if (not empty and not value.strip()) or value != value.strip():
        raise ValueError("Audio text must be nonempty and have no surrounding whitespace")
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Audio text must not contain control characters")
    return value


class AudioProfile(BaseModel):
    """One narrator's explicit synthesis controls; no executable or remote paths."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False, hide_input_in_errors=True)
    name: str = Field(default="Narrator", min_length=1, max_length=100)
    engine: Literal["qwen3"] = "qwen3"
    language: str = "en"
    voice: str = Field(default="Ryan", min_length=1, max_length=100)
    speed: float = Field(default=1.0, ge=1.0, le=1.0)
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
        return _text(value.replace("\r\n", " ").replace("\n", " "), empty=True)

    @field_validator("pronunciations")
    @classmethod
    def valid_pronunciations(cls, values: dict[str, str]) -> dict[str, str]:
        for source, replacement in values.items():
            _text(source)
            _text(replacement)
        return values

    @model_validator(mode="before")
    @classmethod
    def reject_removed_engine(cls, raw: Any) -> Any:
        if isinstance(raw, Mapping) and raw.get("engine") == "piper":
            raise ValueError(_REMOVED_ENGINE)
        return raw

    @model_validator(mode="after")
    def supported_controls(self) -> AudioProfile:
        if self.language not in QWEN_LANGUAGES:
            raise ValueError("Unsupported Qwen language")
        if self.voice not in QWEN_VOICES:
            raise ValueError("Unsupported Qwen preset voice")
        if self.speed != 1.0:
            raise ValueError("Qwen does not support precise speed; speed must be 1.0")
        return self


class AudioSettings(BaseModel):
    """Versioned project profile collection with one existing selected narrator."""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    schema_name: Literal["lixity-audio-settings/1"] = Field(default="lixity-audio-settings/1", alias="schema_version")
    selected: str
    profiles: dict[str, AudioProfile] = Field(min_length=1, max_length=32)

    @model_validator(mode="before")
    @classmethod
    def require_explicit_engine(cls, raw: Any) -> Any:
        if isinstance(raw, Mapping) and isinstance(raw.get("profiles"), Mapping):
            for profile in raw["profiles"].values():
                if isinstance(profile, Mapping) and "engine" not in profile:
                    raise ValueError("Saved audio profiles require an explicit Qwen engine; "
                                     "review the old profile before replacing it")
        return raw

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
        return AudioSettings(selected="narrator", profiles={
            "narrator": AudioProfile(language=language),
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

    Qwen timbres are multilingual; native-language quality requires auditioning.
    """
    return {
        "qwen3": {
            "name": "Qwen3-TTS 1.7B CustomVoice", "targets": ["local", "jetson"], "languages": list(QWEN_LANGUAGES),
            "voices": {voice: {"name": voice, "languages": list(QWEN_LANGUAGES)} for voice in QWEN_VOICES},
            "instructions": True,
            "speed": {"supported": False, "minimum": 1.0, "maximum": 1.0, "default": 1.0},
            "model": QWEN_MODEL,
        },
    }


def requires_audio_migration(raw: object) -> bool:
    """Identify retained removed-engine profiles without interpreting their data."""
    if not isinstance(raw, Mapping) or not isinstance(raw.get("profiles"), Mapping):
        return False
    return any(isinstance(profile, Mapping) and profile.get("engine") == "piper"
               for profile in raw["profiles"].values())


def migrate_audio_settings(
    raw: object, *, replacements: Mapping[str, str], instructions: Mapping[str, str] | None = None,
) -> AudioSettings:
    """Build an explicit migration candidate without mutating input or writing files.

    Every removed engine profile needs a chosen Qwen preset. Original identity,
    language, structural pauses and pronunciation replacements are retained.
    Exact old speed and timbre have no equivalent: speed becomes 1.0 and style
    instructions require a separate explicit choice. Persist only after backup
    and review through the project settings transaction.
    """
    if not isinstance(raw, Mapping) or not isinstance(raw.get("profiles"), Mapping):
        raise ValueError("Migration requires existing versioned audio settings")
    profiles = raw["profiles"]
    legacy_ids = {key for key, profile in profiles.items()
                  if isinstance(profile, Mapping) and profile.get("engine") == "piper"}
    if set(replacements) != legacy_ids:
        raise ValueError("Provide exactly one explicit Qwen preset replacement for every removed Piper profile")
    styles = instructions if instructions is not None else {}
    if not set(styles).issubset(legacy_ids):
        raise ValueError("Migration instructions must name a replaced profile")
    candidates: dict[str, Any] = dict(profiles)
    for key in legacy_ids:
        original = profiles[key]
        candidate = {**original, "engine": "qwen3", "voice": replacements[key],
                     "speed": 1.0, "instructions": styles.get(key, "")}
        candidates[key] = AudioProfile.model_validate(candidate).model_dump()
    return AudioSettings.model_validate({**raw, "profiles": candidates})
