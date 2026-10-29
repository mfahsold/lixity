"""Validated project-local listening profiles and backend control capabilities."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from .speech_controls import speech_control_support, validate_pronunciation_keys

QWEN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
QWEN_DESIGN_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
QWEN_BASE_MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
COQUI_MODEL = "coqui/tts_models/de/thorsten/vits"
COQUI_REFERENCE_MODEL = "coqui/tts_models/de/thorsten/vits+openvoice-v2"
QWEN_LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "de": "German", "fr": "French", "ru": "Russian", "pt": "Portuguese",
    "es": "Spanish", "it": "Italian",
}
QWEN_VOICES = ("Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee")
DEFAULT_PLAYBACK_SPEED = 1.2
MIN_PLAYBACK_SPEED = 0.5
MAX_PLAYBACK_SPEED = 2.0
_PROFILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_REMOVED_ENGINE = ("Piper audio profiles are no longer supported. Make a backup and explicitly migrate "
                   "each profile to a Qwen preset voice; the old voice and precise speed are not equivalent. "
                   "Use audio-migrate --project PATH --replace PROFILE=VOICE to review the migration.")
PronunciationMap = dict[Annotated[str, Field(min_length=1, max_length=100)],
                        Annotated[str, Field(min_length=1, max_length=300)]]


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
    engine: Literal["qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference"] = "qwen3"
    language: str = "en"
    voice: str = Field(default="Ryan", min_length=1, max_length=100)
    voice_description: str = Field(default="", max_length=2000)
    reference_id: str = ""
    # Preserve older explicit and omitted profile values. Only a new implicit
    # profile uses DEFAULT_PLAYBACK_SPEED in parse_audio_settings below.
    speed: float = Field(default=1.0, ge=MIN_PLAYBACK_SPEED, le=MAX_PLAYBACK_SPEED)
    instructions: str = Field(default="", max_length=2000)
    paragraph_pause: float = Field(default=0.45, ge=0, le=10)
    scene_pause: float = Field(default=1.2, ge=0, le=10)
    pronunciations: PronunciationMap = Field(default_factory=dict, max_length=200)

    @model_serializer(mode="wrap")
    def serialize_profile(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if not self.voice_description:
            data.pop("voice_description", None)
        if not self.reference_id:
            data.pop("reference_id", None)
        return data

    @field_validator("name", "voice", "language")
    @classmethod
    def valid_text(cls, value: str) -> str:
        return _text(value)

    @field_validator("instructions")
    @classmethod
    def valid_instructions(cls, value: str) -> str:
        return _text(value.replace("\r\n", " ").replace("\n", " "), empty=True)

    @field_validator("voice_description")
    @classmethod
    def valid_voice_description(cls, value: str) -> str:
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
        if self.engine in ("coqui", "coqui-reference"):
            if self.language != "de" or self.instructions or self.voice_description:
                raise ValueError("Coqui supports German without delivery instructions or voice descriptions")
            if self.engine == "coqui-reference":
                if self.voice != "reference" or re.fullmatch(r"[0-9a-f]{64}", self.reference_id) is None:
                    raise ValueError("Coqui reference requires a saved reference identity")
            elif self.voice != "thorsten" or self.reference_id:
                raise ValueError("Coqui requires the Thorsten voice without a reference")
            return self
        if self.language not in QWEN_LANGUAGES:
            raise ValueError("Unsupported Qwen language")
        if self.engine == "qwen3-base":
            if self.voice != "reference" or re.fullmatch(r"[0-9a-f]{64}", self.reference_id) is None:
                raise ValueError("Qwen Base requires voice='reference' and a saved reference identity")
            if self.instructions or self.voice_description:
                raise ValueError("Qwen Base does not support delivery instructions or voice descriptions")
        elif self.reference_id:
            raise ValueError("Reference identities are only supported by Qwen Base")
        elif self.engine == "qwen3":
            if self.voice not in QWEN_VOICES:
                raise ValueError("Unsupported Qwen preset voice")
            if self.voice_description:
                raise ValueError("CustomVoice does not accept a voice description")
        elif self.voice != "design" or not self.voice_description:
            raise ValueError("VoiceDesign requires voice='design' and a voice description")
        return self


class PronunciationMatching(BaseModel):
    """Explicit project-wide matching policy for schema /2."""

    model_config = ConfigDict(extra="forbid", strict=True)
    case_sensitive: bool = True
    whole_words: bool = False


class AudioSettings(BaseModel):
    """Versioned project profile collection with one existing selected narrator."""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    schema_name: Literal["lixity-audio-settings/1", "lixity-audio-settings/2", "lixity-audio-settings/3"] = Field(default="lixity-audio-settings/1", alias="schema_version")
    selected: str
    profiles: dict[str, AudioProfile] = Field(min_length=1, max_length=32)
    pronunciations: PronunciationMap = Field(default_factory=dict, max_length=200)
    pronunciation_matching: PronunciationMatching = Field(default_factory=PronunciationMatching)

    @model_serializer(mode="wrap")
    def serialize_settings(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.schema_name == "lixity-audio-settings/1":
            data.pop("pronunciations", None)
            data.pop("pronunciation_matching", None)
        return data

    @field_validator("pronunciations")
    @classmethod
    def valid_pronunciations(cls, values: dict[str, str]) -> dict[str, str]:
        return AudioProfile.valid_pronunciations(values)

    @model_validator(mode="before")
    @classmethod
    def require_explicit_engine(cls, raw: Any) -> Any:
        if isinstance(raw, Mapping) and ("pronunciations" in raw or "pronunciation_matching" in raw) and raw.get("schema_version", "lixity-audio-settings/1") not in ("lixity-audio-settings/2", "lixity-audio-settings/3"):
            raise ValueError("Project pronunciations require audio schema lixity-audio-settings/2 or /3")
        if isinstance(raw, Mapping) and isinstance(raw.get("profiles"), Mapping):
            for profile in raw["profiles"].values():
                if isinstance(profile, Mapping) and "engine" not in profile:
                    raise ValueError("Saved audio profiles require an explicit Qwen engine; "
                                     "review the old profile before replacing it")
                if isinstance(profile, Mapping) and profile.get("engine") in ("coqui", "coqui-reference") and raw.get("schema_version") != "lixity-audio-settings/3":
                    raise ValueError("Coqui profiles require audio schema lixity-audio-settings/3")
        return raw

    @model_validator(mode="after")
    def valid_selection(self) -> AudioSettings:
        if any(not _PROFILE_ID.fullmatch(key) for key in self.profiles):
            raise ValueError("Audio profile IDs must be safe identifiers of at most 64 characters")
        if self.selected not in self.profiles:
            raise ValueError("Selected audio profile does not exist")
        if any(len(self.pronunciations.keys() | profile.pronunciations.keys()) > 200
               for profile in self.profiles.values()):
            raise ValueError("Combined project and profile pronunciations must not exceed 200 entries")
        if not self.pronunciation_matching.case_sensitive:
            for profile in self.profiles.values():
                validate_pronunciation_keys({**self.pronunciations, **profile.pronunciations}, case_sensitive=False)
        return self


def parse_audio_settings(raw: object | None, *, language: str = "en") -> AudioSettings:
    """Return an explicit default only for absent settings; reject malformed data."""
    if raw is None:
        return AudioSettings(selected="narrator", profiles={
            "narrator": AudioProfile(language=language, speed=DEFAULT_PLAYBACK_SPEED),
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
        **{engine: {
            "name": name, "targets": ["local"], "languages": ["de"],
            "voices": {voice: {"name": voice_name, "languages": ["de"]}},
            "reference_required": engine == "coqui-reference", "instructions": False,
            "control_support": speech_control_support(engine).as_dict(),
            "speed": {"supported": True, "minimum": MIN_PLAYBACK_SPEED, "maximum": MAX_PLAYBACK_SPEED,
                      "default": DEFAULT_PLAYBACK_SPEED, "implementation": "ffmpeg-atempo"},
            "model": model,
        } for engine, name, voice, voice_name, model in (
            ("coqui", "Coqui Thorsten VITS", "thorsten", "Thorsten", COQUI_MODEL),
            ("coqui-reference", "Coqui Thorsten + OpenVoice V2", "reference", "Reference", COQUI_REFERENCE_MODEL),
        )},
        "qwen3": {
            "name": "Qwen3-TTS 1.7B CustomVoice", "targets": ["local", "jetson"], "languages": list(QWEN_LANGUAGES),
            "voices": {voice: {"name": voice, "languages": list(QWEN_LANGUAGES)} for voice in QWEN_VOICES},
            "instructions": True,
            "control_support": speech_control_support("qwen3").as_dict(),
            "speed": {"supported": True, "minimum": MIN_PLAYBACK_SPEED, "maximum": MAX_PLAYBACK_SPEED,
                      "default": DEFAULT_PLAYBACK_SPEED, "implementation": "ffmpeg-atempo"},
            "model": QWEN_MODEL,
        },
        "qwen3-design": {
            "name": "Qwen3-TTS 1.7B VoiceDesign", "targets": ["local", "jetson"],
            "languages": list(QWEN_LANGUAGES), "voices": {}, "voice_design": True,
            "instructions": True,
            "control_support": speech_control_support("qwen3-design").as_dict(),
            "speed": {"supported": True, "minimum": MIN_PLAYBACK_SPEED, "maximum": MAX_PLAYBACK_SPEED,
                      "default": DEFAULT_PLAYBACK_SPEED, "implementation": "ffmpeg-atempo"},
            "model": QWEN_DESIGN_MODEL,
        },
        "qwen3-base": {
            "name": "Qwen3-TTS 1.7B Base", "targets": ["local", "jetson"],
            "languages": list(QWEN_LANGUAGES),
            "voices": {"reference": {"name": "Reference", "languages": list(QWEN_LANGUAGES)}},
            "reference_required": True, "instructions": False,
            "control_support": speech_control_support("qwen3-base").as_dict(),
            "speed": {"supported": True, "minimum": MIN_PLAYBACK_SPEED, "maximum": MAX_PLAYBACK_SPEED,
                      "default": DEFAULT_PLAYBACK_SPEED, "implementation": "ffmpeg-atempo"},
            "model": QWEN_BASE_MODEL,
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
