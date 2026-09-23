"""lixity.characters – character presence across chapters.

Answers the structural questions an editor asks about a cast: which figures
appear where, how present they are, and how long the manuscript goes without
them. Matching is whole-word and case-insensitive on curated name patterns
(project-specific); there is no entity recognition – the caller supplies the
names, the engine measures their distribution.

Deliberately deterministic and offline; the patterns are regular expressions,
so aliases can be combined ("Matthias|Matze").
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from .markdown_parser import split_chapters  # shared chapter segmentation
from .models import CorpusConfig


@dataclass(frozen=True)
class CharacterPresence:
    """Where and how often one figure appears."""

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
    """Presence of each figure per chapter, sorted by mentions (descending).

    ``names`` is either a sequence of display names (used as pattern) or a
    mapping ``pattern -> display name`` for aliases, e.g.
    ``{"Matthias|Matze": "Matthias"}``.
    """
    config = config or CorpusConfig(language="auto")
    if isinstance(names, Mapping):
        patterns = {label: _name_pattern(pattern) for pattern, label in names.items()}
    else:
        patterns = {name: _name_pattern(name) for name in names}
    if not patterns:
        raise ValueError(
            "characters requires at least one name or alias pattern "
            "(no NER — the caller supplies the names)"
        )

    chapters = split_chapters(text, config)

    results: list[CharacterPresence] = []
    for label, pattern in patterns.items():
        per_chapter: dict[int, int] = {}
        for number, _title, body in chapters:
            clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
            hits = len(pattern.findall(clean))
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


def presence_report(
    text: str,
    names: Mapping[str, str] | Sequence[str],
    config: CorpusConfig | None = None,
) -> dict[str, Any]:
    """JSON-ready character presence report (total chapters + per figure).

    Raises ``ValueError`` when ``names`` is empty — there is no NER.
    """
    config = config or CorpusConfig(language="auto")
    chapters = split_chapters(text, config)
    figures = character_presence(text, names, config)
    return {
        "chapters": len(chapters),
        "figures": [figure.to_dict(len(chapters)) for figure in figures],
    }
