"""Read-only manuscript evidence for a saved character dossier."""

from __future__ import annotations

import json
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from itertools import pairwise
from typing import Any

from ..characters import _mention_spans, _name_pattern, resolve_character_settings
from ..dialogue import character_voice_profiles
from ..markdown_parser import (
    CountedChapterPassage,
    counted_chapter_passages,
    prose_paragraphs,
    split_chapters,
)
from ..pipeline import resolve_document_config
from ..scenes import _chapter_recurring_names
from ..sentences import split_prose_sentence_spans, split_sentence_spans

CHARACTER_EVIDENCE_SCHEMA = "dossier-character-local/1"
_MAX_AUTO_CHARACTERS = 12
_PASSAGES_PER_PAGE = 20
_PASSAGE_TEXT_BYTES_PER_PAGE = 64 * 1024
_MAX_CONTEXT_SENTENCES = 2


class CharacterEvidenceChanged(ValueError):
    """The source or rules changed between reads."""


def _auto_character_names(chapters: Sequence[tuple[int, str, str]]) -> list[str]:
    counts: Counter[str] = Counter()
    for _number, _title, body in chapters:
        paragraphs = prose_paragraphs(body, _front_matter=False)
        for name in _chapter_recurring_names(paragraphs):
            counts[name] += sum(1 for paragraph in paragraphs if name in paragraph)
    return [name for name, _count in counts.most_common(_MAX_AUTO_CHARACTERS)]


def _neighboring_prose(
    parts: Sequence[CountedChapterPassage], boundary: int, indices: range, needed: int,
    language: str,
) -> str:
    """Take nearest measured sentences while staying in the same region."""
    snippets: list[str] = []
    preceding = indices.step == -1
    for index in indices:
        part = parts[index]
        if needed <= 0 or part.region != parts[boundary].region:
            break
        spans = split_sentence_spans(part.text, language)
        chosen = spans[-needed:] if preceding else spans[:needed]
        if chosen:
            snippets.append(part.text[chosen[0][0]:chosen[-1][1]])
            needed -= len(chosen)
    return "\n\n".join(reversed(snippets) if preceding else snippets)


def _chapter_passages(
    body: str, patterns: list[re.Pattern[str]], *, context_language: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """Group the same name matches as character presence into readable passages."""
    parts = list(counted_chapter_passages(body))
    if not parts:
        return 0, []
    offsets: list[int] = []
    cursor = 0
    for part in parts:
        offsets.append(cursor)
        cursor += len(part.text) + 2
    prose = "\n\n".join(part.text for part in parts)
    matches = _mention_spans(prose, patterns)
    groups: list[tuple[int, int, list[tuple[int, int]]]] = []
    for start, end in matches:
        left = bisect_right(offsets, start) - 1
        right = bisect_left(offsets, max(start + 1, end)) - 1
        # A configured pattern can span paragraphs. Keep the entire range in
        # the same excerpt, and let repeated matches share it.
        if groups and left <= groups[-1][1]:
            previous_left, previous_right, spans = groups.pop()
            spans.append((start, end))
            groups.append((previous_left, max(previous_right, right), spans))
        else:
            groups.append((left, right, [(start, end)]))
    passages = []
    for index, (left, right, spans) in enumerate(groups):
        # Keep literal separators, even for a configured pattern that ends in
        # the whitespace between paragraphs.
        end = max(offsets[right] + len(parts[right].text), spans[-1][1])
        excerpt = prose[offsets[left]:end]
        passage = {
            "start_line": parts[left].start_line, "end_line": parts[right].end_line,
            "text": excerpt,
            "matches": [{"start": start - offsets[left], "end": end - offsets[left]} for start, end in spans],
        }
        if context_language is not None:
            excerpt_sentences = split_prose_sentence_spans(excerpt, context_language)
            first_hit, last_hit = spans[0][0] - offsets[left], spans[-1][1] - offsets[left]
            before = _MAX_CONTEXT_SENTENCES - sum(b <= first_hit for _, b in excerpt_sentences)
            after = _MAX_CONTEXT_SENTENCES - sum(a >= last_hit for a, _ in excerpt_sentences)
            previous_hit = groups[index - 1][1] if index else -1
            next_hit = groups[index + 1][0] if index + 1 < len(groups) else len(parts)
            passage["context_before"] = _neighboring_prose(
                parts, left, range(left - 1, previous_hit, -1), before, context_language,
            )
            passage["context_after"] = _neighboring_prose(
                parts, right, range(right + 1, next_hit), after, context_language,
            )
        passages.append(passage)
    return len(matches), passages


def character_evidence(
    text: str,
    source_sha256: str,
    *,
    character: str,
    language: str,
    settings: Mapping[str, Any],
    chapter: int | None = None,
    offset: int = 0,
    expected_analysis_sha256: str | None = None,
) -> dict[str, Any]:
    """Return chapter counts and a page of full matching prose for one character."""
    config, resolved_language = resolve_document_config(text, language, project_config=settings)
    resolved = resolve_character_settings(None, settings)
    chapters = split_chapters(text, config)
    names = resolved.names or _auto_character_names(chapters)
    patterns = dict(names.items()) if isinstance(names, Mapping) else {name: name for name in names}
    selected_patterns = [pattern for pattern, label in patterns.items() if label == character]
    if not selected_patterns:
        literal = re.escape(character)
        if literal not in patterns:
            patterns[literal] = character
        selected_patterns = [literal]
    known_chapters = {number for number, _, _ in chapters}
    declared = [number for number in resolved.declared_pov.get(character, ()) if number in known_chapters]
    profiles = settings.get("characters", {})
    aliases = list((profiles.get(character) or {}).get("aliases", ()))

    analysis_sha256 = sha256(json.dumps({
        "schema": CHARACTER_EVIDENCE_SCHEMA, "source": source_sha256,
        "config": config.model_dump(mode="json"), "patterns": patterns,
        "character": character, "declared": declared, "aliases": aliases,
        "context_sentences": _MAX_CONTEXT_SENTENCES,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    if expected_analysis_sha256 is not None and expected_analysis_sha256 != analysis_sha256:
        raise CharacterEvidenceChanged("Manuscript or character settings changed; reopen the evidence")
    if chapter is not None and chapter not in known_chapters:
        raise ValueError("Choose a chapter in the selected manuscript")

    compiled = [_name_pattern(pattern) for pattern in selected_patterns]
    chapter_rows: list[dict[str, Any]] = []
    ordered_chapters: list[int] = []
    selected_passages: list[dict[str, Any]] = []
    for number, title, body in chapters:
        mentions, passages = _chapter_passages(body, compiled, context_language=resolved_language.key)
        chapter_rows.append({"chapter": number, "chapter_title": title, "mentions": mentions,
                             "passage_count": len(passages)})
        if mentions:
            ordered_chapters.append(number)
        if chapter in (None, number):
            selected_passages.extend({"chapter": number, "chapter_title": title, **row} for row in passages)

    # The page limit bounds ordinary responses. A paragraph larger than that
    # budget still gets its own page so it can be read in full.
    page: list[dict[str, Any]] = []
    text_bytes = 0
    for row in selected_passages[offset:offset + _PASSAGES_PER_PAGE]:
        size = sum(len(row[key].encode("utf-8")) for key in ("text", "context_before", "context_after"))
        if page and text_bytes + size > _PASSAGE_TEXT_BYTES_PER_PAGE:
            break
        page.append(row)
        text_bytes += size
    end = offset + len(page)

    voices = character_voice_profiles(text, patterns, config)
    profile = next((entry for entry in voices["characters"] if entry["name"] == character), None)
    dialogue = None if profile is None else {
        "status": profile["status"], "turns": profile["turns"],
        "min_turns": profile["min_turns"], "words": profile["words"],
        "mean_sentence_words": profile["dialogue_asl"], "question_excl_pct": profile["question_excl_rate"],
    }
    return {
        "schema_version": CHARACTER_EVIDENCE_SCHEMA, "character": character, "aliases": aliases,
        "mentions": sum(row["mentions"] for row in chapter_rows),
        "chapters_with_mentions": len(ordered_chapters),
        "longest_gap": max((b - a - 1 for a, b in pairwise(ordered_chapters)), default=0),
        "declared_pov_chapters": declared, "dialogue": dialogue,
        "chapters": chapter_rows, "passages": page, "passage_count": len(selected_passages),
        "offset": offset, "next_offset": end if end < len(selected_passages) else None,
        "analysis_sha256": analysis_sha256, "source_sha256": source_sha256, "line_scope": "chapter_body",
    }
