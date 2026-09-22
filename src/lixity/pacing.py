"""lixity.pacing – scene structure, pacing signals and chapter hooks.

Deterministic, offline proxies for the questions an editor asks about
structure and tempo:

- **Scenes**: scene breaks are explicit dividers in Markdown
  (``---``, ``* * *``, ``***`` …). Scenes per chapter = breaks + 1.
- **Pacing signals**: per chapter and scene, the observable tempo proxies —
  average sentence length, staccato share, dialogue share and scene length.
  Short sentences, staccato and dialogue read as faster; the report provides
  the signals, not a verdict.
- **Chapter hooks**: the closing sentence of each chapter with a documented
  0–3 heuristic score (short closing sentence, terminal question/exclamation/
  ellipsis, closing dialogue).

No semantic scene detection, no sentiment: the module measures what is
explicitly in the text and marks its heuristics as such.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .dialogue import split_chapters
from .language import compile_pattern, resolve_language
from .models import CorpusConfig
from .sentences import split_sentences

# Explicit scene-break markers (Markdown dividers and common typographic forms).
SCENE_BREAK_RE = re.compile(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,}|•{3,}|#\s*#\s*#|\*\s+\*\s+\*)\s*$")

# Hook heuristic: a closing sentence counts as punchy up to this length.
HOOK_SHORT_SENTENCE = 8


@dataclass(frozen=True)
class SceneStats:
    """One scene inside a chapter."""

    index: int
    words: int
    sentences: int
    asl: float
    dialogue_pct: float
    staccato_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "words": self.words,
            "sentences": self.sentences,
            "asl": round(self.asl, 2),
            "dialogue_pct": round(self.dialogue_pct, 2),
            "staccato_pct": round(self.staccato_pct, 2),
        }


@dataclass(frozen=True)
class ChapterPacing:
    """Scene structure, pacing signals and the closing hook of one chapter."""

    chapter_num: int
    title: str
    words: int
    scenes: int
    avg_scene_words: float
    asl: float
    dialogue_pct: float
    staccato_pct: float
    closing_sentence_words: int
    closing_terminal: str
    closing_is_dialogue: bool
    hook_score: int
    scene_list: list[SceneStats] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "words": self.words,
            "scenes": self.scenes,
            "avg_scene_words": round(self.avg_scene_words, 2),
            "asl": round(self.asl, 2),
            "dialogue_pct": round(self.dialogue_pct, 2),
            "staccato_pct": round(self.staccato_pct, 2),
            "closing_sentence_words": self.closing_sentence_words,
            "closing_terminal": self.closing_terminal,
            "closing_is_dialogue": self.closing_is_dialogue,
            "hook_score": self.hook_score,
            "scene_list": [scene.to_dict() for scene in self.scene_list],
        }


@dataclass(frozen=True)
class PacingReport:
    """Corpus-level scene structure and pacing with per-chapter detail."""

    language: str
    chapters: int
    scenes: int
    avg_scene_words: float
    avg_chapter_scenes: float
    hook_score_mean: float
    fastest_chapter: int | None
    slowest_chapter: int | None
    chapter_list: list[ChapterPacing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "chapters": self.chapters,
            "scenes": self.scenes,
            "avg_scene_words": round(self.avg_scene_words, 2),
            "avg_chapter_scenes": round(self.avg_chapter_scenes, 2),
            "hook_score_mean": round(self.hook_score_mean, 2),
            "fastest_chapter": self.fastest_chapter,
            "slowest_chapter": self.slowest_chapter,
            "chapter_list": [chapter.to_dict() for chapter in self.chapter_list],
        }


def _scene_stats(
    scene_text: str,
    index: int,
    word_re: re.Pattern[str],
    dialogue_re: re.Pattern[str],
    language_key: str,
) -> SceneStats | None:
    words = len(word_re.findall(scene_text))
    if not words:
        return None
    sentences = [s for s in split_sentences(scene_text, language_key) if word_re.findall(s)]
    sentence_lengths = [len(word_re.findall(s)) for s in sentences]
    dialogue_words = sum(len(word_re.findall(m)) for m in dialogue_re.findall(scene_text))
    short = sum(1 for length in sentence_lengths if length <= 6)
    return SceneStats(
        index=index,
        words=words,
        sentences=len(sentences),
        asl=(sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0,
        dialogue_pct=(dialogue_words / words * 100.0) if words else 0.0,
        staccato_pct=(short / len(sentence_lengths) * 100.0) if sentence_lengths else 0.0,
    )


def _closing_sentence(body: str, language_key: str) -> str:
    sentences = split_sentences(body, language_key)
    for sentence in reversed(sentences):
        if sentence.strip():
            return sentence.strip()
    return ""


def _hook_score(
    closing: str, is_dialogue: bool, word_re: re.Pattern[str]
) -> tuple[int, int, str]:
    """(score, closing sentence words, terminal character) – documented heuristic."""
    words = len(word_re.findall(closing))
    terminal = closing.rstrip("\"'»«“”\u2018\u2019)]")[-1:] if closing else ""
    score = 0
    if words and words <= HOOK_SHORT_SENTENCE:
        score += 1
    if terminal in {"?", "!", "…"}:
        score += 1
    if is_dialogue:
        score += 1
    return score, words, terminal


def pacing_report(text: str, config: CorpusConfig | None = None) -> PacingReport:
    """Scene structure, pacing signals and chapter hooks (deterministic)."""
    config = config or CorpusConfig(language="auto")
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)

    chapter_list: list[ChapterPacing] = []
    total_scenes = 0
    total_scene_words = 0
    hook_scores: list[int] = []
    pace: dict[int, float] = {}

    for number, title, body in split_chapters(text, config):
        clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        words = len(word_re.findall(clean))
        if not words:
            continue
        raw_scenes = [part for part in SCENE_BREAK_RE.split(clean) if part.strip()]
        scenes: list[SceneStats] = []
        for index, scene_text in enumerate(raw_scenes, start=1):
            stats = _scene_stats(scene_text, index, word_re, dialogue_re, resolved.key)
            if stats is not None:
                scenes.append(stats)
        scene_words = sum(scene.words for scene in scenes)
        scene_sentences = sum(scene.sentences for scene in scenes)
        asl = (
            sum(scene.asl * scene.sentences for scene in scenes) / scene_sentences
            if scene_sentences
            else 0.0
        )
        dialogue_words = sum(scene.dialogue_pct * scene.words for scene in scenes) / 100.0
        staccato = (
            sum(scene.staccato_pct * scene.sentences for scene in scenes) / scene_sentences
            if scene_sentences
            else 0.0
        )

        closing = _closing_sentence(clean, resolved.key)
        closing_is_dialogue = bool(dialogue_re.search(closing))
        hook, closing_words, terminal = _hook_score(closing, closing_is_dialogue, word_re)

        chapter_list.append(
            ChapterPacing(
                chapter_num=number,
                title=title,
                words=words,
                scenes=len(scenes),
                avg_scene_words=(scene_words / len(scenes)) if scenes else 0.0,
                asl=asl,
                dialogue_pct=(dialogue_words / words * 100.0) if words else 0.0,
                staccato_pct=staccato,
                closing_sentence_words=closing_words,
                closing_terminal=terminal,
                closing_is_dialogue=closing_is_dialogue,
                hook_score=hook,
                scene_list=scenes,
            )
        )
        total_scenes += len(scenes)
        total_scene_words += scene_words
        hook_scores.append(hook)
        pace[number] = asl

    fastest = min(pace, key=lambda key: pace[key]) if pace else None
    slowest = max(pace, key=lambda key: pace[key]) if pace else None
    return PacingReport(
        language=resolved.key,
        chapters=len(chapter_list),
        scenes=total_scenes,
        avg_scene_words=(total_scene_words / total_scenes) if total_scenes else 0.0,
        avg_chapter_scenes=(total_scenes / len(chapter_list)) if chapter_list else 0.0,
        hook_score_mean=(sum(hook_scores) / len(hook_scores)) if hook_scores else 0.0,
        fastest_chapter=fastest,
        slowest_chapter=slowest,
        chapter_list=chapter_list,
    )
