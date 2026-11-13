"""lixity.pacing – scene structure, pacing signals and chapter hooks.

Deterministic, offline proxies for the questions an editor asks about
structure and tempo:

- **Scenes**: scene breaks are explicit dividers in Markdown
  (``---``, ``* * *``, ``***`` …). Scenes per chapter = breaks + 1.
  When the text has **no** explicit dividers, ``explicit_scene_breaks`` is 0
  and ``scenes_are_chapters`` is true — each chapter is one scene; scene
  structure is then uninformative, not "well paced".
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

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from .language import compile_pattern, compile_word_pattern, quotation_texts, resolve_language
from .markdown_parser import SCENE_BREAK_RE as SCENE_BREAK_RE
from .markdown_parser import prose_paragraphs, prose_text, split_chapters, split_scenes
from .models import (
    DEFAULT_HOOK_SHORT_SENTENCE,
    DEFAULT_MONOTONY_MIN_RUN,
    DEFAULT_STICKY_GLUE_PCT,
    DEFAULT_STICKY_MIN_WORDS,
    CorpusConfig,
)
from .sentences import SHORT_SENTENCE_MAX, split_prose_sentences

# Hook heuristic: a closing sentence counts as punchy up to this length.
HOOK_SHORT_SENTENCE = DEFAULT_HOOK_SHORT_SENTENCE

# Rhythm monotony heuristic: consecutive sentences in one paragraph starting
# with the identical lowercased word token.
MONOTONY_MIN_RUN = DEFAULT_MONOTONY_MIN_RUN

# Fallback content-word length floor when a language profile has no function-word
# lexicon (e.g. "generic").
COHESION_FALLBACK_MIN_LEN = 4

SPARKLINE_BARS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")
HOOK_TYPES: tuple[str, ...] = ("dialogue", "action", "reflection", "question", "unknown")
MAX_STICKY_ITEMS = 50

_REFLECTION_CUE_RE = re.compile(
    r"\b(?:wonder(?:ed|s|ing)?|realized?|remember(?:ed|s)?|knew|know|believe[ds]?|"
    r"seemed?|recalled?|thought|think|felt|feel|dachte|fühlte|wusste|schien|"
    r"erinnerte|ahnte|glaubte|pensait|savait|sentait|pensaba|sabía|sentía|"
    r"pensava|sapeva|sentiva|dacht|voelde|wist)\b",
    re.IGNORECASE | re.UNICODE,
)


def classify_scene_hook(
    sentence: str,
    *,
    dialogue_re: re.Pattern[str],
    filter_verbs_re: re.Pattern[str],
) -> str:
    """Classify a scene entry or exit sentence into a heuristic hook category.

    Categories: ``dialogue``, ``question``, ``reflection``, ``action``, or
    ``unknown`` when empty. Deliberately deterministic and offline.
    """
    stripped = sentence.strip()
    if not stripped:
        return "unknown"
    if dialogue_re.search(stripped) or stripped.startswith(('"', "»", "«", "„", "“", "—", "–")):
        return "dialogue"
    if stripped.rstrip("\"'»«“”\u2018\u2019)] \t").endswith("?"):
        return "question"
    if filter_verbs_re.search(stripped) or _REFLECTION_CUE_RE.search(stripped):
        return "reflection"
    return "action"


def compute_rolling_asl(sentence_lengths: list[int], window: int = 15) -> list[float]:
    """Calculate rolling average sentence length across sliding window of sentences."""
    if not sentence_lengths:
        return []
    n = len(sentence_lengths)
    if n <= window:
        return [round(sum(sentence_lengths) / n, 1)]
    current_sum = sum(sentence_lengths[:window])
    results = [round(current_sum / window, 1)]
    for i in range(window, n):
        current_sum += sentence_lengths[i] - sentence_lengths[i - window]
        results.append(round(current_sum / window, 1))
    return results


def condense_timeline(values: Sequence[float], target_points: int = 12) -> list[float]:
    """Sample or bin timeline to target_points for compact presentation."""
    if not values:
        return []
    if len(values) <= target_points:
        return [round(v, 1) for v in values]
    step = len(values) / target_points
    condensed: list[float] = []
    for i in range(target_points):
        start = int(i * step)
        end = int((i + 1) * step)
        chunk = values[start:max(start + 1, end)]
        condensed.append(round(sum(chunk) / len(chunk), 1))
    return condensed


def compute_sparkline(values: Sequence[float]) -> str:
    """Render a sequence of floats as an 8-level Unicode sparkline."""
    if not values:
        return ""
    v_min = min(values)
    v_max = max(values)
    if v_max == v_min:
        return SPARKLINE_BARS[3] * len(values)
    span = v_max - v_min
    bars: list[str] = []
    for val in values:
        idx = int((val - v_min) / span * 7.0)
        idx = max(0, min(7, idx))
        bars.append(SPARKLINE_BARS[idx])
    return "".join(bars)


@dataclass(frozen=True)
class SceneStats:
    """One scene inside a chapter."""

    index: int
    words: int
    sentences: int
    asl: float
    dialogue_pct: float
    staccato_pct: float
    sticky_sentences: int = 0
    sticky_sentence_pct: float = 0.0
    entry_hook_type: str = "unknown"
    exit_hook_type: str = "unknown"
    exit_hook_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "words": self.words,
            "sentences": self.sentences,
            "asl": round(self.asl, 2),
            "dialogue_pct": round(self.dialogue_pct, 2),
            "staccato_pct": round(self.staccato_pct, 2),
            "sticky_sentences": self.sticky_sentences,
            "sticky_sentence_pct": round(self.sticky_sentence_pct, 2),
            "entry_hook_type": self.entry_hook_type,
            "exit_hook_type": self.exit_hook_type,
            "exit_hook_score": self.exit_hook_score,
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
    repeated_start_runs: int = 0
    adjacent_sentence_pairs: int = 0
    sentence_overlap_pct: float = 0.0
    sentence_cv: float = 0.0
    pacing_sparkline: str = ""
    pacing_curve: list[float] = field(default_factory=list)
    sticky_sentences: int = 0
    sticky_sentence_pct: float = 0.0
    mean_glue_pct: float = 0.0

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
            "repeated_start_runs": self.repeated_start_runs,
            "adjacent_sentence_pairs": self.adjacent_sentence_pairs,
            "sentence_overlap_pct": round(self.sentence_overlap_pct, 2),
            "sentence_cv": round(self.sentence_cv, 2),
            "pacing_sparkline": self.pacing_sparkline,
            "pacing_curve": self.pacing_curve,
            "sticky_sentences": self.sticky_sentences,
            "sticky_sentence_pct": round(self.sticky_sentence_pct, 2),
            "mean_glue_pct": round(self.mean_glue_pct, 2),
            "scene_list": [scene.to_dict() for scene in self.scene_list],
        }


@dataclass(frozen=True)
class PacingReport:
    """Corpus-level scene structure and pacing with per-chapter detail."""

    language: str
    chapters: int
    scenes: int
    explicit_scene_breaks: int
    avg_scene_words: float
    avg_chapter_scenes: float
    hook_score_mean: float
    fastest_chapter: int | None
    slowest_chapter: int | None
    chapter_list: list[ChapterPacing] = field(default_factory=list)
    repeated_start_runs: int = 0
    adjacent_sentence_pairs: int = 0
    sentence_overlap_pct: float = 0.0
    sticky_sentences: int = 0
    sticky_sentence_pct: float = 0.0
    mean_glue_pct: float = 0.0
    sticky_available: bool = True
    sticky_items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def scenes_are_chapters(self) -> bool:
        """True when no explicit dividers were found (scenes ≡ chapters)."""
        return self.explicit_scene_breaks == 0 and self.chapters > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "chapters": self.chapters,
            "scenes": self.scenes,
            "explicit_scene_breaks": self.explicit_scene_breaks,
            "scenes_are_chapters": self.scenes_are_chapters,
            "avg_scene_words": round(self.avg_scene_words, 2),
            "avg_chapter_scenes": round(self.avg_chapter_scenes, 2),
            "hook_score_mean": round(self.hook_score_mean, 2),
            "repeated_start_runs": self.repeated_start_runs,
            "adjacent_sentence_pairs": self.adjacent_sentence_pairs,
            "sentence_overlap_pct": round(self.sentence_overlap_pct, 2),
            "sticky_sentences": self.sticky_sentences,
            "sticky_sentence_pct": round(self.sticky_sentence_pct, 2),
            "mean_glue_pct": round(self.mean_glue_pct, 2),
            "sticky_available": self.sticky_available,
            "sticky_items": self.sticky_items,
            "fastest_chapter": self.fastest_chapter,
            "slowest_chapter": self.slowest_chapter,
            "chapter_list": [chapter.to_dict() for chapter in self.chapter_list],
        }


def _scene_stats(
    scene_text: str,
    index: int,
    chapter_num: int,
    word_re: re.Pattern[str],
    dialogue_re: re.Pattern[str],
    filter_verbs_re: re.Pattern[str],
    language_key: str,
    function_words: frozenset[str],
    *,
    short_sentence_max: int = SHORT_SENTENCE_MAX,
    hook_short_sentence: int = HOOK_SHORT_SENTENCE,
    sticky_glue_pct: float = DEFAULT_STICKY_GLUE_PCT,
    sticky_min_words: int = DEFAULT_STICKY_MIN_WORDS,
) -> tuple[SceneStats, list[float], list[dict[str, Any]]] | None:
    scene_text = prose_text(scene_text, _front_matter=False)
    words = len(word_re.findall(scene_text))
    if not words:
        return None
    sentences = [s for s in split_prose_sentences(scene_text, language_key) if word_re.findall(s)]
    sentence_tokens = [[w.lower() for w in word_re.findall(s)] for s in sentences]
    sentence_lengths = [len(tokens) for tokens in sentence_tokens]
    dialogue_words = sum(len(word_re.findall(m)) for m in quotation_texts(dialogue_re, scene_text))
    short = sum(1 for length in sentence_lengths if length <= short_sentence_max)

    glue_pcts: list[float] = []
    sticky_count = 0
    sticky_items: list[dict[str, Any]] = []
    if function_words:
        for sentence, tokens in zip(sentences, sentence_tokens, strict=True):
            n_words = len(tokens)
            if not n_words:
                continue
            glue_words = sum(1 for tok in tokens if tok in function_words)
            glue_pct = glue_words / n_words * 100.0
            glue_pcts.append(glue_pct)
            if n_words >= sticky_min_words and glue_pct >= sticky_glue_pct:
                sticky_count += 1
                sticky_items.append({
                    "chapter_num": chapter_num,
                    "scene_index": index,
                    "words": n_words,
                    "glue_words": glue_words,
                    "glue_pct": round(glue_pct, 2),
                    "preview": sentence.strip()[:80],
                })

    entry_sentence = sentences[0] if sentences else ""
    exit_sentence = sentences[-1] if sentences else ""
    entry_hook_type = classify_scene_hook(
        entry_sentence, dialogue_re=dialogue_re, filter_verbs_re=filter_verbs_re
    )
    exit_hook_type = classify_scene_hook(
        exit_sentence, dialogue_re=dialogue_re, filter_verbs_re=filter_verbs_re
    )
    exit_is_dialogue = bool(dialogue_re.search(exit_sentence)) if exit_sentence else False
    exit_hook_score, _, _ = _hook_score(
        exit_sentence,
        exit_is_dialogue,
        word_re,
        hook_short_sentence=hook_short_sentence,
    )

    stats = SceneStats(
        index=index,
        words=words,
        sentences=len(sentences),
        asl=(sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0,
        dialogue_pct=(dialogue_words / words * 100.0) if words else 0.0,
        staccato_pct=(short / len(sentence_lengths) * 100.0) if sentence_lengths else 0.0,
        sticky_sentences=sticky_count,
        sticky_sentence_pct=(sticky_count / len(sentences) * 100.0) if (sentences and function_words) else 0.0,
        entry_hook_type=entry_hook_type,
        exit_hook_type=exit_hook_type,
        exit_hook_score=exit_hook_score,
    )
    return stats, glue_pcts, sticky_items


def _closing_sentence(body: str, language_key: str) -> str:
    sentences = split_prose_sentences(body, language_key)
    for sentence in reversed(sentences):
        if sentence.strip():
            return sentence.strip()
    return ""


def _hook_score(
    closing: str,
    is_dialogue: bool,
    word_re: re.Pattern[str],
    *,
    hook_short_sentence: int = HOOK_SHORT_SENTENCE,
) -> tuple[int, int, str]:
    """(score, closing sentence words, terminal character) – documented heuristic."""
    words = len(word_re.findall(closing))
    terminal = closing.rstrip("\"'»«“”\u2018\u2019)]")[-1:] if closing else ""
    score = 0
    if words and words <= hook_short_sentence:
        score += 1
    if terminal in {"?", "!", "…"}:
        score += 1
    if is_dialogue:
        score += 1
    return score, words, terminal


def _chapter_flow_stats(
    body: str,
    word_re: re.Pattern[str],
    language_key: str,
    function_words: frozenset[str],
    *,
    monotony_min_run: int = MONOTONY_MIN_RUN,
) -> tuple[int, int, int]:
    """(repeated sentence-start runs, adjacent sentence pairs, linked sentence pairs)."""
    repeated_runs = 0
    adjacent_pairs = 0
    linked_pairs = 0
    has_function_lexicon = bool(function_words)
    for paragraph in prose_paragraphs(body, _front_matter=False):
        sentences = [
            s
            for s in split_prose_sentences(paragraph, language_key)
            if word_re.search(s)
        ]
        if len(sentences) < 2:
            continue
        starts: list[str] = []
        content_sets: list[set[str]] = []
        for sentence in sentences:
            tokens = [w.lower() for w in word_re.findall(sentence)]
            if not tokens:
                continue
            starts.append(tokens[0])
            if has_function_lexicon:
                content = {
                    t for t in tokens if len(t) >= 2 and t not in function_words
                }
            else:
                content = {
                    t for t in tokens if len(t) >= COHESION_FALLBACK_MIN_LEN
                }
            content_sets.append(content)
        run_len = 1
        for prev_start, curr_start in pairwise(starts):
            if curr_start == prev_start:
                run_len += 1
            else:
                if run_len >= monotony_min_run:
                    repeated_runs += 1
                run_len = 1
        if run_len >= monotony_min_run:
            repeated_runs += 1
        for prev_set, curr_set in pairwise(content_sets):
            if prev_set and curr_set:
                adjacent_pairs += 1
                if prev_set & curr_set:
                    linked_pairs += 1
    return repeated_runs, adjacent_pairs, linked_pairs


def pacing_report(text: str, config: CorpusConfig | None = None) -> PacingReport:
    """Scene structure, pacing signals and chapter hooks (deterministic)."""
    config = config or CorpusConfig()
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)
    filter_verbs_re = compile_pattern(resolved.filter_verbs_regex)
    sticky_available = bool(resolved.function_words)

    chapter_list: list[ChapterPacing] = []
    total_scenes = 0
    total_scene_words = 0
    explicit_breaks = 0
    hook_scores: list[int] = []
    pace: dict[int, float] = {}
    total_repeated_runs = 0
    total_adjacent_pairs = 0
    total_linked_pairs = 0
    total_sticky_sentences = 0
    total_sentences = 0
    all_glue_pcts: list[float] = []
    all_sticky_items: list[dict[str, Any]] = []

    for number, title, body in split_chapters(text, config):
        clean = prose_text(body, _front_matter=False)
        words = len(word_re.findall(clean))
        if not words:
            continue
        raw_scenes, scene_breaks = split_scenes(body)
        explicit_breaks += scene_breaks
        scenes: list[SceneStats] = []
        chapter_glue_pcts: list[float] = []
        for index, scene_text in enumerate(raw_scenes, start=1):
            scene_result = _scene_stats(
                scene_text,
                index,
                number,
                word_re,
                dialogue_re,
                filter_verbs_re,
                resolved.key,
                resolved.function_words,
                short_sentence_max=config.short_sentence_max,
                hook_short_sentence=config.hook_short_sentence,
                sticky_glue_pct=config.sticky_glue_pct,
                sticky_min_words=config.sticky_min_words,
            )
            if scene_result is not None:
                stats, scene_glue_pcts, scene_sticky_items = scene_result
                scenes.append(stats)
                chapter_glue_pcts.extend(scene_glue_pcts)
                all_sticky_items.extend(scene_sticky_items)
        scene_words = sum(scene.words for scene in scenes)
        scene_sentences = sum(scene.sentences for scene in scenes)
        chapter_sticky = sum(scene.sticky_sentences for scene in scenes)
        chapter_sticky_pct = (
            (chapter_sticky / scene_sentences * 100.0)
            if (scene_sentences and sticky_available)
            else 0.0
        )
        chapter_mean_glue = (
            (sum(chapter_glue_pcts) / len(chapter_glue_pcts))
            if chapter_glue_pcts
            else 0.0
        )
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
        hook, closing_words, terminal = _hook_score(
            closing,
            closing_is_dialogue,
            word_re,
            hook_short_sentence=config.hook_short_sentence,
        )
        repeated_runs, adjacent_pairs, linked_pairs = _chapter_flow_stats(
            body,
            word_re,
            resolved.key,
            resolved.function_words,
            monotony_min_run=config.monotony_min_run,
        )
        overlap_pct = (linked_pairs / adjacent_pairs * 100.0) if adjacent_pairs else 0.0

        all_sentences = [
            s for s in split_prose_sentences(clean, resolved.key)
            if word_re.search(s)
        ]
        sentence_lengths = [len(word_re.findall(s)) for s in all_sentences]
        if sentence_lengths:
            m = sum(sentence_lengths) / len(sentence_lengths)
            var = sum((sl - m) ** 2 for sl in sentence_lengths) / len(sentence_lengths)
            cv = (math.sqrt(var) / m) if m > 0.0 else 0.0
            window = min(15, max(3, len(sentence_lengths) // 3)) if len(sentence_lengths) >= 6 else len(sentence_lengths)
            rolling = compute_rolling_asl(sentence_lengths, window=window)
            pacing_curve = condense_timeline(rolling, target_points=12)
            sparkline = compute_sparkline(pacing_curve)
        else:
            cv = 0.0
            pacing_curve = []
            sparkline = ""

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
                repeated_start_runs=repeated_runs,
                adjacent_sentence_pairs=adjacent_pairs,
                sentence_overlap_pct=overlap_pct,
                sentence_cv=cv,
                pacing_sparkline=sparkline,
                pacing_curve=pacing_curve,
                sticky_sentences=chapter_sticky,
                sticky_sentence_pct=chapter_sticky_pct,
                mean_glue_pct=chapter_mean_glue,
            )
        )
        total_scenes += len(scenes)
        total_scene_words += scene_words
        hook_scores.append(hook)
        pace[number] = asl
        total_repeated_runs += repeated_runs
        total_adjacent_pairs += adjacent_pairs
        total_linked_pairs += linked_pairs
        total_sticky_sentences += chapter_sticky
        total_sentences += scene_sentences
        all_glue_pcts.extend(chapter_glue_pcts)

    fastest = min(pace, key=lambda key: pace[key]) if pace else None
    slowest = max(pace, key=lambda key: pace[key]) if pace else None
    all_sticky_items.sort(
        key=lambda item: (-item["glue_pct"], -item["words"], item["chapter_num"], item["scene_index"])
    )
    return PacingReport(
        language=resolved.key,
        chapters=len(chapter_list),
        scenes=total_scenes,
        explicit_scene_breaks=explicit_breaks,
        avg_scene_words=(total_scene_words / total_scenes) if total_scenes else 0.0,
        avg_chapter_scenes=(total_scenes / len(chapter_list)) if chapter_list else 0.0,
        hook_score_mean=(sum(hook_scores) / len(hook_scores)) if hook_scores else 0.0,
        fastest_chapter=fastest,
        slowest_chapter=slowest,
        chapter_list=chapter_list,
        repeated_start_runs=total_repeated_runs,
        adjacent_sentence_pairs=total_adjacent_pairs,
        sentence_overlap_pct=(
            (total_linked_pairs / total_adjacent_pairs * 100.0)
            if total_adjacent_pairs
            else 0.0
        ),
        sticky_sentences=total_sticky_sentences,
        sticky_sentence_pct=(
            (total_sticky_sentences / total_sentences * 100.0)
            if (total_sentences and sticky_available)
            else 0.0
        ),
        mean_glue_pct=(sum(all_glue_pcts) / len(all_glue_pcts)) if all_glue_pcts else 0.0,
        sticky_available=sticky_available,
        sticky_items=all_sticky_items[:MAX_STICKY_ITEMS],
    )
