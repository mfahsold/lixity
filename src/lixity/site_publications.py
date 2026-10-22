"""Author-curated reader publication profiles, separate from research records.

Profiles choose literal dossier versions or sections for a reading website.
They do not store source redistribution consent or recipient permissions.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from .publication import validate_metadata_text
from .research.models import Identifier

ProfileKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class SitePublicationEntry(BaseModel):
    """One explicit, indivisible publication selection and chapter release gate."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    dossier_id: Identifier
    revision: Annotated[int, Field(ge=1)] | None = None
    section: str | None = None
    reveal_after_chapter: Annotated[int, Field(ge=0)] = 0
    title: str | None = None
    include_citations: bool = False
    include_geography: bool = False

    @field_validator("section", "title")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = validate_metadata_text(value, "Publication entry text", 500)
        if not text:
            raise ValueError("Publication section and title must be nonblank when supplied")
        return text


class SitePublicationProfile(BaseModel):
    """Public introduction and selected dossier content; no automatic graph joins."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    title: str
    introduction: str = ""
    entries: Annotated[list[SitePublicationEntry], Field(max_length=500)] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def profile_title(cls, value: str) -> str:
        text = validate_metadata_text(value, "Publication title", 500)
        if not text:
            raise ValueError("Publication title must be nonblank")
        return text

    @field_validator("introduction")
    @classmethod
    def profile_introduction(cls, value: str) -> str:
        return validate_metadata_text(value, "Publication introduction", 10000, multiline=True)


_PROFILES = TypeAdapter(Annotated[dict[ProfileKey, SitePublicationProfile], Field(max_length=50)],
                        config=ConfigDict(strict=True))


def parse_site_publications(value: object) -> dict[str, SitePublicationProfile]:
    """Validate profiles without reading any project or research store."""
    return _PROFILES.validate_python(value)


def validate_site_publications(value: object) -> dict[str, Any]:
    """Return normalized JSON settings, including explicit optional defaults."""
    return {key: profile.model_dump() for key, profile in parse_site_publications(value).items()}


def site_publications_schema() -> dict[str, Any]:
    """Describe curation syntax; dossier/chapter existence is checked at export."""
    return _PROFILES.json_schema()


def resolve_site_publication(value: object, name: str, *, chapter_count: int,
                             max_chapter: int | None) -> tuple[SitePublicationProfile, int]:
    """Select one profile and validate gates against canonical parsed chapters."""
    profiles = parse_site_publications(value)
    if name not in profiles:
        raise ValueError(f"Unknown publication profile: {name}")
    cap = chapter_count if max_chapter is None else max_chapter
    if type(cap) is not int or not 0 <= cap <= chapter_count:
        raise ValueError(f"Publication chapter cap must be between 0 and {chapter_count}")
    profile = profiles[name]
    if any(entry.reveal_after_chapter > chapter_count for entry in profile.entries):
        raise ValueError(f"Publication release gates must use canonical chapters 0 through {chapter_count}")
    return profile, cap
