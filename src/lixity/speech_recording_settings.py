"""Project recording preferences and the shared reference duration limits."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

AUDIO_RECORDING_SETTINGS_KEY = "audio_recording"
MIN_REFERENCE_SECONDS = 1
MAX_REFERENCE_SECONDS = 60
DEFAULT_SHORT_REFERENCE_SECONDS = 15


class AudioRecordingSettings(BaseModel):
    """A duration override independent of any synthesis profile."""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    reference_seconds: int | None = Field(default=None, ge=MIN_REFERENCE_SECONDS, le=MAX_REFERENCE_SECONDS)

    def duration_seconds(self, *, full_phonetic: bool = True) -> int:
        """Resolve this project's override or the entry point's default."""
        if self.reference_seconds is not None:
            return self.reference_seconds
        return MAX_REFERENCE_SECONDS if full_phonetic else DEFAULT_SHORT_REFERENCE_SECONDS


def resolve_audio_recording_settings(config: Mapping[str, object]) -> AudioRecordingSettings:
    """Read a recording table from an explicitly selected project config."""
    return AudioRecordingSettings.model_validate(config.get(AUDIO_RECORDING_SETTINGS_KEY, {}))
