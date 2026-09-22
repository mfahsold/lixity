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

from .language import compile_pattern, resolve_language
from .models import CorpusConfig

# A paragraph counts as dialogue paragraph when at least this share of its
# words sits inside quotation marks.
DIALOGUE_PARAGRAPH_SHARE = 0.5


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

    def to_dict(self) -> dict:
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

    def to_dict(self) -> dict:
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
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


def split_chapters(text: str, config: CorpusConfig) -> list[tuple[int, str, str]]:
    """(chapter number, title, body) – same conventions as the analyzer.

    The scholarly appendix (``config.appendix_marker``) is cut off first and
    front matter is not a chapter, so chapter numbers match the metrics.
    """
    if config.appendix_marker and config.appendix_marker in text:
        text, _ = text.split(config.appendix_marker, 1)
    parts = re.split(config.chapter_regex, text)
    if parts:
        first = re.sub(r"<!--.*?-->", "", parts[0], flags=re.DOTALL).strip()
        if first.startswith("# ") or not first:
            parts = parts[1:]
    chapters: list[tuple[int, str, str]] = []
    number = 1
    for raw in parts:
        block = raw.strip()
        if not block:
            continue
        lines = block.split("\n")
        title = lines[0].strip().replace("# ", "")
        body = "\n".join(lines[1:]).strip()
        if not re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip():
            continue  # heading without content is not a chapter (matches the analyzer)
        chapters.append((number, title, body))
        number += 1
    return chapters


def _turn_stats(
    body: str, dialogue_re: re.Pattern[str], word_re: re.Pattern[str]
) -> tuple[list[int], int, int, int, int]:
    """(turn word counts, dialogue words, words, dialogue paragraphs, paragraphs)."""
    clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    matches = dialogue_re.findall(clean)
    turn_word_counts = [len(word_re.findall(m)) for m in matches]
    dialogue_words = sum(turn_word_counts)
    words = len(word_re.findall(clean))

    paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
    prose_paragraphs = [p for p in paragraphs if not p.startswith(("#", "|", "-", "*"))]
    dialogue_paragraphs = 0
    for paragraph in prose_paragraphs:
        paragraph_words = len(word_re.findall(paragraph))
        if not paragraph_words:
            continue
        quoted = sum(len(word_re.findall(m)) for m in dialogue_re.findall(paragraph))
        if quoted / paragraph_words >= DIALOGUE_PARAGRAPH_SHARE:
            dialogue_paragraphs += 1

    return (
        turn_word_counts,
        dialogue_words,
        words,
        dialogue_paragraphs,
        len(prose_paragraphs),
    )


def dialogue_report(text: str, config: CorpusConfig | None = None) -> DialogueReport:
    """Dialogue turn structure of a manuscript (deterministic, heuristic)."""
    config = config or CorpusConfig(language="auto")
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)

    chapters: list[DialogueChapter] = []
    all_turn_lengths: list[int] = []
    all_dialogue_words = 0
    all_words = 0
    all_paragraphs = 0
    all_dialogue_paragraphs = 0

    for number, title, body in split_chapters(text, config):
        turn_lengths, dialogue_words, words, dialogue_paragraphs, paragraphs = _turn_stats(
            body, dialogue_re, word_re
        )
        if not words:
            continue
        turns = len(turn_lengths)
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
            )
        )
        all_turn_lengths.extend(turn_lengths)
        all_dialogue_words += dialogue_words
        all_words += words
        all_paragraphs += paragraphs
        all_dialogue_paragraphs += chapters[-1].dialogue_paragraphs

    turns = len(all_turn_lengths)
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
    )
