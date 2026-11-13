"""Curated character name mentions across manuscript chapters.

Matching is whole-word and case-insensitive on author-supplied patterns;
mentions do not establish a character's presence or point of view.

Deliberately deterministic and offline; the patterns are regular expressions,
so aliases can be combined ("Matthias|Matze").
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .markdown_parser import prose_text, split_chapters
from .models import CorpusConfig
from .publication import validate_metadata_text

Names = Mapping[str, str] | Sequence[str]
MAX_CHARACTER_NAME_CHARS = 100
MAX_CHARACTER_ALIAS_CHARS = 100


class CharacterProfile(BaseModel):
    """Explicit literal aliases and author-declared chapter perspective."""

    model_config = ConfigDict(extra="forbid", strict=True)
    aliases: list[Annotated[str, Field(min_length=1, max_length=MAX_CHARACTER_ALIAS_CHARS)]] = Field(
        default_factory=list, description="Literal name variants; the profile name is also matched.")
    pov_in_chapters: list[Annotated[int, Field(strict=True, ge=1)]] = Field(
        default_factory=list,
        description="Author-declared 1-based manuscript chapter numbers, never inferred from pronouns.")

    @field_validator("aliases")
    @classmethod
    def valid_aliases(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            name = validate_metadata_text(value, "Character alias", MAX_CHARACTER_ALIAS_CHARS)
            if not name:
                raise ValueError("Character aliases must not be empty")
            if name not in result:
                result.append(name)
        return result

    @field_validator("pov_in_chapters")
    @classmethod
    def unique_chapters(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("Declared POV chapter numbers must not repeat")
        return sorted(values)


@dataclass(frozen=True)
class ResolvedCharacters:
    """One explicit selection, keeping declared POV separate from measurements."""

    names: Names
    declared_pov: Mapping[str, tuple[int, ...]] = field(default_factory=dict)


def character_configuration_schema() -> dict[str, Any]:
    """Describe the same profile model used by the configuration resolver."""
    return {"type": "object", "propertyNames": {"minLength": 1, "maxLength": MAX_CHARACTER_NAME_CHARS},
            "additionalProperties": CharacterProfile.model_json_schema(),
            "description": "Project-local display names mapped to literal aliases and declared POV chapters."}


def resolve_character_settings(explicit: Names | None, settings: Mapping[str, Any]) -> ResolvedCharacters:
    """Explicit names win; an existing profiles key, even empty, replaces legacy names."""
    if explicit is None and "characters" in settings:
        profiles = settings["characters"]
        if not isinstance(profiles, Mapping):
            raise ValueError("characters must be a table of named profiles")
        patterns: dict[str, str] = {}
        declared: dict[str, tuple[int, ...]] = {}
        for label, values in profiles.items():
            name = validate_metadata_text(label, "Character name", MAX_CHARACTER_NAME_CHARS)
            if not name or name != label:
                raise ValueError("Character names must be nonempty and have no surrounding whitespace")
            profile = CharacterProfile.model_validate(values)
            aliases = sorted({name, *profile.aliases}, key=lambda value: (-len(value), value))
            pattern = "|".join(re.escape(alias) for alias in aliases)
            if pattern in patterns:
                raise ValueError("Character profiles have indistinguishable alias groups")
            patterns[pattern] = name
            declared[name] = tuple(profile.pov_in_chapters)
        return ResolvedCharacters(patterns, declared)
    names = explicit if explicit is not None else settings.get("names", [])
    if not isinstance(names, (Mapping, Sequence)) or isinstance(names, (str, bytes)):
        raise ValueError("Character names must be a list or a pattern-to-label mapping")
    entries = names.items() if isinstance(names, Mapping) else ((name, name) for name in names)
    for pattern, label in entries:
        if not isinstance(pattern, str) or not pattern.strip() or not isinstance(label, str) or not label.strip():
            raise ValueError("Character patterns and display names must be nonempty strings")
        try:
            _name_pattern(pattern)
        except re.error as exc:
            raise ValueError(f"Invalid character name pattern: {exc}") from exc
    return ResolvedCharacters(names)


@dataclass(frozen=True)
class CharacterPresence:
    """Name mentions, retaining the legacy presence-key JSON contract."""

    name: str
    mentions: int
    chapters_present: list[int]
    first_chapter: int | None
    last_chapter: int | None
    longest_gap: int
    per_chapter: dict[int, int] = field(default_factory=dict)

    def to_dict(self, total_chapters: int) -> dict[str, Any]:
        return {
            "name": self.name,
            "mentions": self.mentions,
            "chapters_present": self.chapters_present,
            "first_chapter": self.first_chapter,
            "last_chapter": self.last_chapter,
            "longest_gap": self.longest_gap,
            "presence_ratio": round(len(self.chapters_present) / total_chapters, 4)
            if total_chapters
            else 0.0,
            "per_chapter": {str(k): v for k, v in sorted(self.per_chapter.items())},
        }


def _name_pattern(name: str) -> re.Pattern[str]:
    """Whole-word, case-insensitive pattern for one name or alias group."""
    return re.compile(rf"(?<!\w)(?:{name})(?!\w)", re.IGNORECASE | re.UNICODE)


def character_presence(
    text: str,
    names: Mapping[str, str] | Sequence[str],
    config: CorpusConfig | None = None,
) -> list[CharacterPresence]:
    """Name mentions per chapter, sorted by count (descending).

    ``names`` is either a sequence of display names (used as pattern) or a
    mapping ``pattern -> display name`` for aliases, e.g.
    ``{"Matthias|Matze": "Matthias"}``.
    """
    config = config or CorpusConfig()
    names = resolve_character_settings(names, {}).names
    patterns: dict[str, list[re.Pattern[str]]] = {}
    entries = names.items() if isinstance(names, Mapping) else ((name, name) for name in names)
    for pattern, label in entries:
        patterns.setdefault(label, []).append(_name_pattern(pattern))
    if not patterns:
        raise ValueError(
            "characters requires at least one name or alias pattern "
            "(no NER — the caller supplies the names)"
        )

    chapters = split_chapters(text, config)

    results: list[CharacterPresence] = []
    chapter_prose = [(number, prose_text(body, _front_matter=False)) for number, _title, body in chapters]
    for label, aliases in patterns.items():
        per_chapter: dict[int, int] = {}
        for number, clean in chapter_prose:
            spans = sorted({match.span() for pattern in aliases for match in pattern.finditer(clean)})
            hits = 0
            right = -1
            for start, end in spans:
                if start >= right:
                    hits += 1
                right = max(right, end)
            if hits:
                per_chapter[number] = hits
        present = sorted(per_chapter)
        first = present[0] if present else None
        last = present[-1] if present else None
        longest_gap = 0
        if present:
            for left, right in pairwise(present):
                longest_gap = max(longest_gap, right - left - 1)
        results.append(
            CharacterPresence(
                name=label,
                mentions=sum(per_chapter.values()),
                chapters_present=present,
                first_chapter=first,
                last_chapter=last,
                longest_gap=longest_gap,
                per_chapter=per_chapter,
            )
        )
    results.sort(key=lambda item: (-item.mentions, item.name))
    return results


def _pov_gap_metrics(pov_chapters: list[int], total_chapters: int) -> dict[str, Any]:
    """Compute chapter-absence gaps for one character's declared POV chapters."""
    gaps: list[dict[str, Any]] = []
    for left, right in pairwise(pov_chapters):
        span = right - left - 1
        if span > 0:
            gaps.append({
                "from_chapter": left,
                "to_chapter": right,
                "gap_chapters": span,
                "missing_chapters": list(range(left + 1, right)),
            })
    return {
        "pov_gaps": gaps,
        "pov_longest_gap": max((g["gap_chapters"] for g in gaps), default=0),
        "pov_leading_gap": (pov_chapters[0] - 1) if pov_chapters else 0,
        "pov_trailing_gap": (total_chapters - pov_chapters[-1]) if (pov_chapters and total_chapters) else 0,
        "pov_share": round(len(pov_chapters) / total_chapters, 4) if total_chapters else 0.0,
    }


def pov_chapters_map(declared_pov: Mapping[str, Sequence[int]]) -> dict[int, list[str]]:
    """Invert character -> declared POV chapters into chapter -> sorted character names."""
    by_chapter: dict[int, list[str]] = {}
    for name in sorted(declared_pov):
        for chapter_num in declared_pov[name]:
            by_chapter.setdefault(chapter_num, []).append(name)
    return by_chapter


def presence_report(
    text: str,
    names: Mapping[str, str] | Sequence[str],
    config: CorpusConfig | None = None, *,
    declared_pov: Mapping[str, Sequence[int]] | None = None,
) -> dict[str, Any]:
    """Name-mention report preserving legacy presence keys and separate POV metadata.

    Raises ``ValueError`` when ``names`` is empty — there is no NER.
    """
    config = config or CorpusConfig()
    chapters = split_chapters(text, config)
    figures = character_presence(text, names, config)
    declared = declared_pov or {}
    if set(declared) - {figure.name for figure in figures}:
        raise ValueError("Declared POV must identify a selected character")
    numbers = {number for number, _title, _body in chapters}
    total_chapters = len(chapters)
    result = []
    covered_pov_chapters: set[int] = set()
    declared_figures = 0
    for figure in figures:
        item = figure.to_dict(total_chapters)
        if figure.name in declared:
            values = list(declared[figure.name])
            if any(type(number) is not int or number not in numbers for number in values):
                raise ValueError(f"Declared POV chapters no longer match this manuscript: {figure.name}")
            if len(values) != len(set(values)):
                raise ValueError("Declared POV chapter numbers must not repeat")
            sorted_pov = sorted(values)
            item["declared_pov_chapters"] = sorted_pov
            item.update(_pov_gap_metrics(sorted_pov, total_chapters))
            covered_pov_chapters.update(sorted_pov)
            declared_figures += 1
        result.append(item)
    return {
        "chapters": total_chapters,
        "figures": result,
        "pov_summary": {
            "declared_figures": declared_figures,
            "pov_coverage_chapters": sorted(covered_pov_chapters),
            "chapters_without_declared_pov": (
                sorted(numbers - covered_pov_chapters) if declared_figures > 0 else []
            ),
        },
    }
