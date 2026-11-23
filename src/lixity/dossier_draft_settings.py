"""Validated author settings for manuscript dossier suggestions and excerpts."""

from collections.abc import Mapping, Sequence
from typing import Any
from unicodedata import normalize

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .publication import validate_metadata_text

DEFAULT_INFERRED_DOSSIER_LIMIT = 12
DEFAULT_CHARACTER_CONTEXT_SENTENCES = 2
_MAX_INFERRED_DOSSIER_LIMIT = 50
_MAX_CHARACTER_CONTEXT_SENTENCES = 5
DOSSIER_DRAFT_SETTINGS_KEY = "dossier_drafts"
AUTOMATIC_LOCATION_NAMES = "auto"
MAX_LOCATION_NAME_CHARS = 100


class DossierInferenceSettings(BaseModel):
    """Limits for automatically inferred suggestions, after ranking candidates."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    inferred_character_limit: int = Field(
        DEFAULT_INFERRED_DOSSIER_LIMIT, ge=0, le=_MAX_INFERRED_DOSSIER_LIMIT,
        description="Maximum inferred character suggestions. Zero disables inference. Configured names take precedence.",
    )
    inferred_location_limit: int = Field(
        DEFAULT_INFERRED_DOSSIER_LIMIT, ge=0, le=_MAX_INFERRED_DOSSIER_LIMIT,
        description="Maximum inferred place suggestions. Zero disables inference. Configured places take precedence.",
    )


class DossierDraftSettings(DossierInferenceSettings):
    """Project-local options for draft suggestions and full character dossiers."""

    character_context_sentences: int = Field(
        DEFAULT_CHARACTER_CONTEXT_SENTENCES, ge=0, le=_MAX_CHARACTER_CONTEXT_SENTENCES,
        description="Nearby sentences to include per side of full matching paragraphs in character dossiers.",
    )
    character_report_passages: bool = Field(
        True, description="Include manuscript excerpts in saved generated character dossiers. Live evidence stays available.",
    )


def resolve_dossier_draft_settings(settings: Mapping[str, Any]) -> DossierDraftSettings:
    """Read the explicit settings table, rejecting invalid values and unknown keys."""
    try:
        return DossierDraftSettings.model_validate(settings.get(DOSSIER_DRAFT_SETTINGS_KEY, {}))
    except ValidationError as exc:
        raise ValueError(f"Invalid [{DOSSIER_DRAFT_SETTINGS_KEY}] configuration: {exc}") from exc


def parse_location_names(value: object) -> list[str] | None:
    """Resolve automatic, explicitly named or disabled place suggestions."""
    if value == AUTOMATIC_LOCATION_NAMES:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("locations must be a list of names or 'auto'")
    names: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Each configured location must be a nonempty name")
        name = validate_metadata_text(item, "Location name", MAX_LOCATION_NAME_CHARS)
        if not name:
            raise ValueError("Each configured location must be a nonempty name")
        names.setdefault(normalize("NFC", name.casefold()), name)
    return list(names.values())
