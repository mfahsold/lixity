"""lixity.dialogue – dialogue and interaction structure of a manuscript.

Beyond the plain dialogue share (see ``CorpusMetrics.dialog_ratio``) this
module describes the *turn structure*: how often speech starts, how long the
turns are, how dialogue is distributed across chapters and paragraphs.

Deliberately heuristic and offline: quoted speech is detected with the
language profile's dialogue pattern (curated per language); there is no
speaker attribution – a "turn" is one quoted segment, not a named speaker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from .language import (
    compile_pattern,
    compile_word_pattern,
    quotation_capture_group,
    quotation_texts,
    resolve_language,
)
from .markdown_parser import prose_paragraphs, split_chapters  # shared segmentation (re-export)
from .models import CorpusConfig
from .sentences import split_prose_sentences

# A paragraph counts as dialogue paragraph when at least this share of its
# words sits inside quotation marks.
DIALOGUE_PARAGRAPH_SHARE = 0.5

# Turn-length cadence thresholds (words per recognized quoted span):
# rapid back-and-forth exchange (stichomythia proxy) vs. extended speech/monologue.
SHORT_TURN_MAX_WORDS = 12
LONG_TURN_MIN_WORDS = 80


@dataclass(frozen=True)
class DialogueChapter:
    """Turn structure of one chapter."""

    chapter_num: int
    title: str
    turns: int
    turn_words: int
    dialogue_words: int
    words: int
    dialogue_pct: float
    avg_turn_words: float
    longest_turn_words: int
    dialogue_paragraphs: int
    paragraphs: int
    short_turns: int = 0
    short_turn_pct: float = 0.0
    long_turns: int = 0
    dialogue_asl: float = 0.0
    narration_asl: float = 0.0
    asl_contrast: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "turns": self.turns,
            "turn_words": self.turn_words,
            "dialogue_words": self.dialogue_words,
            "words": self.words,
            "dialogue_pct": round(self.dialogue_pct, 2),
            "avg_turn_words": round(self.avg_turn_words, 2),
            "longest_turn_words": self.longest_turn_words,
            "dialogue_paragraphs": self.dialogue_paragraphs,
            "paragraphs": self.paragraphs,
            "short_turns": self.short_turns,
            "short_turn_pct": round(self.short_turn_pct, 2),
            "long_turns": self.long_turns,
            "dialogue_asl": round(self.dialogue_asl, 2),
            "narration_asl": round(self.narration_asl, 2),
            "asl_contrast": (
                round(self.asl_contrast, 2) if self.asl_contrast is not None else None
            ),
        }


@dataclass(frozen=True)
class DialogueReport:
    """Corpus-level dialogue structure with per-chapter detail."""

    language: str
    turns: int
    turn_words: int
    dialogue_words: int
    words: int
    dialogue_pct: float
    avg_turn_words: float
    median_turn_words: float
    longest_turn_words: int
    turns_per_1000: float
    dialogue_paragraph_pct: float
    chapters: list[DialogueChapter] = field(default_factory=list)
    short_turns: int = 0
    short_turn_pct: float = 0.0
    long_turns: int = 0
    dialogue_asl: float = 0.0
    narration_asl: float = 0.0
    asl_contrast: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "turns": self.turns,
            "turn_words": self.turn_words,
            "dialogue_words": self.dialogue_words,
            "words": self.words,
            "dialogue_pct": round(self.dialogue_pct, 2),
            "avg_turn_words": round(self.avg_turn_words, 2),
            "median_turn_words": round(self.median_turn_words, 2),
            "longest_turn_words": self.longest_turn_words,
            "turns_per_1000": round(self.turns_per_1000, 2),
            "dialogue_paragraph_pct": round(self.dialogue_paragraph_pct, 2),
            "short_turns": self.short_turns,
            "short_turn_pct": round(self.short_turn_pct, 2),
            "long_turns": self.long_turns,
            "dialogue_asl": round(self.dialogue_asl, 2),
            "narration_asl": round(self.narration_asl, 2),
            "asl_contrast": (
                round(self.asl_contrast, 2) if self.asl_contrast is not None else None
            ),
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


def _turn_stats(
    body: str,
    dialogue_re: re.Pattern[str],
    word_re: re.Pattern[str],
    language_key: str = "en",
) -> tuple[list[int], int, int, int, int, int, int, int]:
    """(turn word counts, dialogue words, words, dialogue paragraphs, paragraphs, dialogue sentences, narration words, narration sentences)."""
    paragraphs = prose_paragraphs(body, _front_matter=False)
    clean = "\n\n".join(paragraphs)
    matches = list(quotation_texts(dialogue_re, clean))
    turn_word_counts = [len(word_re.findall(m)) for m in matches]
    dialogue_words = sum(turn_word_counts)
    words = len(word_re.findall(clean))
    dialogue_sentences = 0
    for match_text, count in zip(matches, turn_word_counts, strict=True):
        if count > 0:
            sents = [
                s
                for s in split_prose_sentences(match_text, language_key)
                if word_re.search(s)
            ]
            dialogue_sentences += max(1, len(sents))

    # A recognized quoted span may continue across paragraph boundaries.
    # Reuse the same chapter-wide matches for paragraph shares instead of
    # requiring both quote delimiters to occur inside each paragraph.
    capture = quotation_capture_group(dialogue_re)
    spans = sorted(match.span(capture) for match in dialogue_re.finditer(clean)
                   if match.start(capture) >= 0 and match.end(capture) > match.start(capture))
    quoted_spans: list[tuple[int, int]] = []
    for start, end in spans:
        if quoted_spans and start <= quoted_spans[-1][1]:
            quoted_spans[-1] = (quoted_spans[-1][0], max(end, quoted_spans[-1][1]))
        else:
            quoted_spans.append((start, end))

    narration_parts: list[str] = []
    cursor = 0
    for start, end in quoted_spans:
        narration_parts.append(clean[cursor:start])
        cursor = end
    narration_parts.append(clean[cursor:])
    narration_text = " ".join(narration_parts)
    narration_words = len(word_re.findall(narration_text))
    nar_sents = [
        s
        for s in split_prose_sentences(narration_text, language_key)
        if word_re.search(s)
    ]
    narration_sentences = max(1, len(nar_sents)) if narration_words > 0 else 0

    dialogue_paragraphs = 0
    paragraph_start = 0
    first_span = 0
    for paragraph in paragraphs:
        paragraph_end = paragraph_start + len(paragraph)
        while first_span < len(quoted_spans) and quoted_spans[first_span][1] <= paragraph_start:
            first_span += 1
        paragraph_words = len(word_re.findall(paragraph))
        if paragraph_words:
            quoted = 0
            index = first_span
            while index < len(quoted_spans) and quoted_spans[index][0] < paragraph_end:
                start, end = quoted_spans[index]
                fragment = paragraph[max(0, start - paragraph_start):min(len(paragraph), end - paragraph_start)]
                quoted += len(word_re.findall(fragment))
                index += 1
            if quoted / paragraph_words >= DIALOGUE_PARAGRAPH_SHARE:
                dialogue_paragraphs += 1
        paragraph_start = paragraph_end + 2  # separator inserted in clean

    return (
        turn_word_counts,
        dialogue_words,
        words,
        dialogue_paragraphs,
        len(paragraphs),
        dialogue_sentences,
        narration_words,
        narration_sentences,
    )


def dialogue_report(text: str, config: CorpusConfig | None = None) -> DialogueReport:
    """Dialogue turn structure of a manuscript (deterministic, heuristic)."""
    config = config or CorpusConfig()
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)

    chapters: list[DialogueChapter] = []
    all_turn_lengths: list[int] = []
    all_dialogue_words = 0
    all_words = 0
    all_paragraphs = 0
    all_dialogue_paragraphs = 0
    all_dialogue_sentences = 0
    all_narration_words = 0
    all_narration_sentences = 0

    for number, title, body in split_chapters(text, config):
        (
            turn_lengths,
            dialogue_words,
            words,
            dialogue_paragraphs,
            paragraphs,
            dialogue_sentences,
            narration_words,
            narration_sentences,
        ) = _turn_stats(body, dialogue_re, word_re, resolved.key)
        if not words:
            continue
        turns = len(turn_lengths)
        short_turns = sum(1 for w in turn_lengths if 1 <= w <= SHORT_TURN_MAX_WORDS)
        long_turns = sum(1 for w in turn_lengths if w >= LONG_TURN_MIN_WORDS)
        dialogue_asl = (dialogue_words / dialogue_sentences) if dialogue_sentences else 0.0
        narration_asl = (narration_words / narration_sentences) if narration_sentences else 0.0
        asl_contrast = (
            (dialogue_asl - narration_asl)
            if (dialogue_sentences > 0 and narration_sentences > 0)
            else None
        )
        chapters.append(
            DialogueChapter(
                chapter_num=number,
                title=title,
                turns=turns,
                turn_words=dialogue_words,
                dialogue_words=dialogue_words,
                words=words,
                dialogue_pct=(dialogue_words / words * 100.0) if words else 0.0,
                avg_turn_words=(dialogue_words / turns) if turns else 0.0,
                longest_turn_words=max(turn_lengths, default=0),
                dialogue_paragraphs=dialogue_paragraphs,
                paragraphs=paragraphs,
                short_turns=short_turns,
                short_turn_pct=(short_turns / turns * 100.0) if turns else 0.0,
                long_turns=long_turns,
                dialogue_asl=dialogue_asl,
                narration_asl=narration_asl,
                asl_contrast=asl_contrast,
            )
        )
        all_turn_lengths.extend(turn_lengths)
        all_dialogue_words += dialogue_words
        all_words += words
        all_paragraphs += paragraphs
        all_dialogue_paragraphs += chapters[-1].dialogue_paragraphs
        all_dialogue_sentences += dialogue_sentences
        all_narration_words += narration_words
        all_narration_sentences += narration_sentences

    turns = len(all_turn_lengths)
    short_turns = sum(1 for w in all_turn_lengths if 1 <= w <= SHORT_TURN_MAX_WORDS)
    long_turns = sum(1 for w in all_turn_lengths if w >= LONG_TURN_MIN_WORDS)
    corpus_dialogue_asl = (
        (all_dialogue_words / all_dialogue_sentences) if all_dialogue_sentences else 0.0
    )
    corpus_narration_asl = (
        (all_narration_words / all_narration_sentences) if all_narration_sentences else 0.0
    )
    corpus_asl_contrast = (
        (corpus_dialogue_asl - corpus_narration_asl)
        if (all_dialogue_sentences > 0 and all_narration_sentences > 0)
        else None
    )
    return DialogueReport(
        language=resolved.key,
        turns=turns,
        turn_words=all_dialogue_words,
        dialogue_words=all_dialogue_words,
        words=all_words,
        dialogue_pct=(all_dialogue_words / all_words * 100.0) if all_words else 0.0,
        avg_turn_words=(all_dialogue_words / turns) if turns else 0.0,
        median_turn_words=median(all_turn_lengths) if all_turn_lengths else 0.0,
        longest_turn_words=max(all_turn_lengths, default=0),
        turns_per_1000=(turns / all_words * 1000.0) if all_words else 0.0,
        dialogue_paragraph_pct=(
            all_dialogue_paragraphs / all_paragraphs * 100.0 if all_paragraphs else 0.0
        ),
        chapters=chapters,
        short_turns=short_turns,
        short_turn_pct=(short_turns / turns * 100.0) if turns else 0.0,
        long_turns=long_turns,
        dialogue_asl=corpus_dialogue_asl,
        narration_asl=corpus_narration_asl,
        asl_contrast=corpus_asl_contrast,
    )
