"""lixity.motifs – motif tracking and repetition analysis.

Two complementary views for macro editing:

- **Motifs** (project-specific): where a curated motif appears across the
  chapters — mentions, density, first/last chapter, longest gap. Patterns are
  regular expressions, so a motif can cover a word field ("Wut|wütend").
- **Repetition** (generic, no configuration): the most frequent content words
  (function words and stop words excluded) and repeated n-grams (default
  3-grams) with their chapter spread. Deterministic, offline, no embeddings.

Repetition is a *signal*, not a verdict: deliberate repetition is a stylistic
device. The report provides counts and locations so the editor can decide.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from .language import compile_pattern, compile_word_pattern, resolve_language
from .markdown_parser import prose_text, split_chapters
from .models import CorpusConfig

MIN_PHRASE_COUNT = 3  # a repeated n-gram must occur at least this often


def resolve_motif_settings(
    explicit: Mapping[str, str] | None, settings: Mapping[str, Any],
) -> dict[str, str]:
    """Resolve explicit patterns or compatible canonical/legacy project tables.

    An explicit mapping replaces project patterns, including an empty mapping.
    Project tables combine distinct names; conflicting duplicate names fail
    instead of silently changing which pattern a named motif measures.
    """
    tables = (("motifs", explicit),) if explicit is not None else (
        (key, settings[key]) for key in ("motif_regexes", "motifs") if key in settings
    )
    patterns: dict[str, str] = {}
    for key, table in tables:
        if not isinstance(table, Mapping):
            raise ValueError(f"{key} must be a table of motif names and regular expressions")
        for name, pattern in table.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(pattern, str):
                raise ValueError(f"{key} must map nonblank motif names to regular-expression strings")
            try:
                compile_pattern(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid {key} pattern for {name}: {exc}") from exc
            if name in patterns and patterns[name] != pattern:
                raise ValueError(f"Conflicting motif {name} in motif_regexes and motifs")
            patterns[name] = pattern
    return patterns


@dataclass(frozen=True)
class MotifPresence:
    """Where one curated motif appears across the chapters."""

    name: str
    mentions: int
    density_per_1000: float
    chapters_present: list[int]
    first_chapter: int | None
    last_chapter: int | None
    longest_gap: int
    per_chapter: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mentions": self.mentions,
            "density_per_1000": round(self.density_per_1000, 3),
            "chapters_present": self.chapters_present,
            "first_chapter": self.first_chapter,
            "last_chapter": self.last_chapter,
            "longest_gap": self.longest_gap,
            "per_chapter": {str(k): v for k, v in sorted(self.per_chapter.items())},
        }


@dataclass(frozen=True)
class RepeatedPhrase:
    """One repeated n-gram with its chapter spread."""

    phrase: str
    count: int
    chapters: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"phrase": self.phrase, "count": self.count, "chapters": self.chapters}


@dataclass(frozen=True)
class Echo:
    """An n-gram's densest local cluster, with 1-based inclusive word bounds."""

    term: str
    chapter: int
    count: int
    first_word: int
    last_word: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "chapter": self.chapter,
            "count": self.count,
            "first_word": self.first_word,
            "last_word": self.last_word,
        }


@dataclass(frozen=True)
class MotifReport:
    """Motif tracking plus generic repetition signals."""

    language: str
    chapters: int
    motifs: list[MotifPresence] = field(default_factory=list)
    top_words: list[tuple[str, int]] = field(default_factory=list)
    repeated_phrases: list[RepeatedPhrase] = field(default_factory=list)
    echoes: list[Echo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "chapters": self.chapters,
            "motifs": [motif.to_dict() for motif in self.motifs],
            "top_words": [{"word": word, "count": count} for word, count in self.top_words],
            "repeated_phrases": [phrase.to_dict() for phrase in self.repeated_phrases],
            "echoes": [echo.to_dict() for echo in self.echoes],
        }


def _gaps(present: list[int]) -> int:
    longest = 0
    for left, right in pairwise(present):
        longest = max(longest, right - left - 1)
    return longest


def motif_report(
    text: str,
    motifs: Mapping[str, str] | None = None,
    config: CorpusConfig | None = None,
    phrase_size: int = 3,
    top_words: int = 15,
    top_phrases: int = 10,
    echo_window: int = 300,
    echo_min_count: int = 2,
    top_echoes: int = 20,
) -> MotifReport:
    """Motif presence and repetition signals (deterministic, offline).

    Omitted patterns inherit ``config.motif_regexes``; an explicit mapping,
    including ``{}``, replaces those configured patterns.
    """
    config = config or CorpusConfig()
    patterns = resolve_motif_settings(motifs, {"motif_regexes": config.motif_regexes})
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    content_blacklist = resolved.function_words | resolved.stopwords

    chapters = split_chapters(text, config)
    chapter_bodies = {
        number: prose_text(body, _front_matter=False)
        for number, _title, body in chapters
    }
    total_words = sum(len(word_re.findall(body)) for body in chapter_bodies.values())

    motif_items: list[MotifPresence] = []
    for name, pattern in patterns.items():
        compiled = compile_pattern(pattern)
        per_chapter: dict[int, int] = {}
        for number, body in chapter_bodies.items():
            hits = len(compiled.findall(body))
            if hits:
                per_chapter[number] = hits
        present = sorted(per_chapter)
        mentions = sum(per_chapter.values())
        motif_items.append(
            MotifPresence(
                name=name,
                mentions=mentions,
                density_per_1000=(mentions / total_words * 1000.0) if total_words else 0.0,
                chapters_present=present,
                first_chapter=present[0] if present else None,
                last_chapter=present[-1] if present else None,
                longest_gap=_gaps(present),
                per_chapter=per_chapter,
            )
        )
    motif_items.sort(key=lambda item: (-item.mentions, item.name))

    # Generic repetition: content words and n-grams across the whole manuscript.
    word_counts: Counter[str] = Counter()
    phrase_chapters: dict[str, set[int]] = {}
    phrase_counts: Counter[str] = Counter()
    for number, body in chapter_bodies.items():
        tokens = [token.lower() for token in word_re.findall(body)]
        word_counts.update(token for token in tokens if token not in content_blacklist)
        for index in range(len(tokens) - phrase_size + 1):
            gram = tokens[index : index + phrase_size]
            if all(token in content_blacklist for token in gram):
                continue  # pure function-word phrase: not a repetition signal
            phrase = " ".join(gram)
            phrase_counts[phrase] += 1
            phrase_chapters.setdefault(phrase, set()).add(number)

    repeated = [
        RepeatedPhrase(phrase=phrase, count=count, chapters=sorted(phrase_chapters[phrase]))
        for phrase, count in phrase_counts.most_common(top_phrases)
        if count >= MIN_PHRASE_COUNT
    ]

    # Echo counts and locations refer to one bounded local cluster, not to
    # unrelated occurrences elsewhere in the chapter. Equal counts use the
    # earliest cluster; the complete final n-gram must fit inside the window.
    echo_items: list[Echo] = []
    local_positions: dict[tuple[str, int], list[int]] = {}
    for number, body in chapter_bodies.items():
        tokens = [token.lower() for token in word_re.findall(body)]
        if len(tokens) < phrase_size:
            continue
        # Collect all n-gram occurrences.
        occurrences: dict[str, list[int]] = {}
        for index in range(len(tokens) - phrase_size + 1):
            gram = tokens[index : index + phrase_size]
            if all(token in content_blacklist for token in gram):
                continue
            phrase = " ".join(gram)
            occurrences.setdefault(phrase, []).append(index)
        for phrase, positions in occurrences.items():
            if len(positions) < echo_min_count:
                continue
            left = 0
            best_start = 0
            best_end = 0
            for right, position in enumerate(positions):
                while left <= right and position - positions[left] + phrase_size > echo_window:
                    left += 1
                if right - left + 1 > best_end - best_start:
                    best_start, best_end = left, right + 1
            cluster = positions[best_start:best_end]
            if len(cluster) < max(2, echo_min_count):
                continue
            local_positions[(phrase, number)] = cluster
            echo_items.append(
                Echo(
                    term=phrase,
                    chapter=number,
                    count=len(cluster),
                    first_word=cluster[0] + 1,
                    last_word=cluster[-1] + phrase_size,
                )
            )

    # Deduplicate shifted n-grams only when their actual occurrences overlap
    # in the same repeated passage. Shared vocabulary alone is insufficient:
    # "red wooden door" and "red metal door" are independent echo candidates.
    echo_items.sort(key=lambda e: (-e.count, e.chapter, e.first_word, e.term))
    deduped: list[Echo] = []
    kept_positions: dict[tuple[int, int], Echo] = {}
    for echo in echo_items:
        words = echo.term.split()
        positions = local_positions[(echo.term, echo.chapter)]
        duplicate = False
        for shift in range(1, phrase_size - 1):
            for offset in (shift, -shift):
                existing = kept_positions.get((echo.chapter, positions[0] + offset))
                if existing is None:
                    continue
                existing_words = existing.term.split()
                overlap = (words[offset:] == existing_words[:-offset] if offset > 0 else
                           words[:offset] == existing_words[-offset:])
                if overlap and all(
                    kept_positions.get((echo.chapter, position + offset)) == existing
                    for position in positions
                ):
                    duplicate = True
                    break
            if duplicate:
                break
        if not duplicate:
            deduped.append(echo)
            for position in positions:
                kept_positions[(echo.chapter, position)] = echo
    echo_items = deduped

    # Keep the most frequent echoes, capped.
    echo_items.sort(key=lambda e: (-e.count, e.chapter, e.term))
    echo_items = echo_items[:top_echoes]

    return MotifReport(
        language=resolved.key,
        chapters=len(chapters),
        motifs=motif_items,
        top_words=word_counts.most_common(top_words),
        repeated_phrases=repeated,
        echoes=echo_items,
    )
