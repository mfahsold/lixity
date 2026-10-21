"""lixity.style_profile – Paragraph-accurate style and narrative tense profiling.

Classifies narrative tense (present / past / mixed / neutral), detects tense friction
and switches between consecutive paragraphs, and tracks paragraph-level style densities.
"""

from dataclasses import dataclass
from typing import Any

from .language import compile_pattern, resolve_language
from .markdown_parser import counting_inline_text, strip_inline_markup
from .math_core import per_mille
from .models import CorpusConfig
from .paragraph_evidence import ParagraphEvidence, ParagraphMatcher
from .status import (
    FLAG_MIN_SEVERITY,
    TENSE_MIXED,
    TENSE_NEUTRAL,
    TENSE_PAST,
    TENSE_PRESENT,
)

__all__ = [
    "FLAG_MIN_SEVERITY",
    "TENSE_MIXED",
    "TENSE_NEUTRAL",
    "TENSE_PAST",
    "TENSE_PRESENT",
    "ChapterProfile",
    "ParagraphProfile",
    "ParagraphProfiler",
    "ProfileThresholds",
    "classify_severity",
    "dominance_from_hits",
    "flagged_paragraphs",
]

# Re-exported from lixity.status (single source of truth).


#: Ratio-band convention of the dominance classification.
DOMINANCE_EPSILON = 0.001
DOMINANCE_PRESENT_ABOVE = 1.5
DOMINANCE_PAST_BELOW = 0.67


def dominance_from_hits(present: int, past: int, neutral_max_hits: int = 1) -> str:
    """Dominant tense from marker counts – shared by chapter and paragraph analysis."""
    if present + past <= neutral_max_hits:
        return TENSE_NEUTRAL
    ratio = present / (past + DOMINANCE_EPSILON)
    if ratio > DOMINANCE_PRESENT_ABOVE:
        return TENSE_PRESENT
    if ratio < DOMINANCE_PAST_BELOW:
        return TENSE_PAST
    return TENSE_MIXED


@dataclass(frozen=True)
class ProfileThresholds:
    """Thresholds of the style profile heuristic (injectable, documented, reproducible)."""

    neutral_max_hits: int = 1  # fewer than 2 tense markers: no statement
    mix_min_hits: int = 2  # at least 2 markers per tense
    mix_min_ratio: float = 0.25  # minority share from 25 % = mixed
    switch_min_hits: int = 2  # dominant tense requires >= 2 markers
    severe_mix_minority: int = 3  # mixed + >= 3 minority markers = level 2
    flag_min_severity: int = FLAG_MIN_SEVERITY  # editorial cut for the flags panel


def classify_severity(
    switch: bool,
    mixed: bool,
    minority: int,
    thresholds: ProfileThresholds | None = None,
) -> int:
    """Tense-friction severity of one paragraph (0–3).

    Truth table (t = thresholds):

    ================================  ========
    condition                         severity
    ================================  ========
    switch AND mixed AND minority >= severe   3
    (switch AND minority >= mix_min)
        OR (mixed AND minority >= severe)    2
    switch OR mixed                          1
    otherwise                                0
    ================================  ========

    severe = t.severe_mix_minority, mix_min = t.mix_min_hits.
    """
    t = thresholds or ProfileThresholds()
    conditions = (
        (3, switch and mixed and minority >= t.severe_mix_minority),
        (2, (switch and minority >= t.mix_min_hits)
            or (mixed and minority >= t.severe_mix_minority)),
        (1, switch or mixed),
    )
    return next((severity for severity, holds in conditions if holds), 0)


def mixed_tense(
    present: int, past: int, thresholds: ProfileThresholds
) -> tuple[bool, float]:
    """Mixed-tense definition: both marker counts at the floor and a minority share.

    Returns ``(mixed, minority_ratio)``; the ratio is 0.0 without markers.
    """
    total = present + past
    minority_ratio = (min(present, past) / total) if total else 0.0
    mixed = (
        present >= thresholds.mix_min_hits
        and past >= thresholds.mix_min_hits
        and minority_ratio >= thresholds.mix_min_ratio
    )
    return mixed, minority_ratio


@dataclass
class ParagraphProfile:
    """Style profile of a single body-text paragraph with line anchor."""

    chapter_num: int
    chapter_title: str
    start_line: int
    end_line: int
    words: int
    sentences: int
    present_hits: int
    past_hits: int
    dominant: str
    minority_ratio: float
    mixed: bool
    switch: bool
    severity: int
    asl: float
    dialogue_pct: float
    function_word_pct: float
    filter_density: float = 0.0
    modal_density: float = 0.0
    nominal_density: float = 0.0
    passive_density: float = 0.0
    text: str = ""
    flag_min: int = FLAG_MIN_SEVERITY

    @property
    def is_flagged(self) -> bool:
        """True when severity reaches this paragraph's flag cut (default FLAG_MIN_SEVERITY)."""
        return self.severity >= self.flag_min


def flagged_paragraphs(
    paragraphs: list[ParagraphProfile], min_severity: int | None = None
) -> list[ParagraphProfile]:
    """Actionable paragraphs, sorted by severity (desc) then line (asc).

    ``min_severity`` overrides each paragraph's own cut when given (UI/CLI).
    """
    cut = FLAG_MIN_SEVERITY if min_severity is None else min_severity
    return sorted(
        (p for p in paragraphs if p.severity >= (cut if min_severity is not None else p.flag_min)),
        key=lambda p: (-p.severity, p.start_line),
    )


@dataclass
class ChapterProfile:
    """Aggregated tense profile of a chapter (for navigation & metrics)."""

    num: int
    title: str
    start_line: int
    end_line: int
    words: int
    paragraphs: int
    present_hits: int
    past_hits: int
    dominant: str
    flagged: int
    asl: float
    dialog_pct: float
    function_word_pct: float


class ParagraphProfiler:
    """Stateless engine for paragraph-accurate tense and style profiles."""

    def __init__(
        self,
        config: CorpusConfig | None = None,
        thresholds: ProfileThresholds | None = None,
        *,
        sample_text: str | None = None,
    ):
        self.config = config or CorpusConfig()
        self.thresholds = thresholds or ProfileThresholds()
        self.lang = resolve_language(self.config, sample_text=sample_text)
        self._praes = compile_pattern(self.lang.praesens_regex)
        self._praet = compile_pattern(self.lang.praeteritum_regex)
        self._matcher = ParagraphMatcher(self.config, self.lang)
        self._appendix_title = self.config.appendix_marker.replace("##", "").strip()

    def _dominant(self, present: int, past: int) -> str:
        return dominance_from_hits(present, past, self.thresholds.neutral_max_hits)

    def profile_blocks(
        self, blocks: list[dict[str, Any]], *, evidence: dict[int, ParagraphEvidence] | None = None,
    ) -> tuple[list[ParagraphProfile], list[ChapterProfile]]:
        """Builds paragraph and chapter profiles from semantic blocks (with line anchors)."""
        paragraphs: list[ParagraphProfile] = []
        chapters: list[ChapterProfile] = []

        chapter_num = 0
        chapter_title = ""
        chapter_start = 0
        chapter_end = 0
        chapter_paragraphs: list[ParagraphProfile] = []
        prev_dominant: str | None = None
        in_appendix = False

        def close_chapter() -> None:
            if chapter_num == 0 or not chapter_paragraphs:
                return  # do not list empty chapters (e.g. an acknowledgements section still open)
            present = sum(p.present_hits for p in chapter_paragraphs)
            past = sum(p.past_hits for p in chapter_paragraphs)
            total_words = sum(p.words for p in chapter_paragraphs)
            total_sentences = sum(p.sentences for p in chapter_paragraphs)

            def _weighted(attr: str) -> float:
                if not total_words:
                    return 0.0
                weighted = sum(getattr(p, attr) * p.words for p in chapter_paragraphs) / total_words
                return float(weighted)

            chapters.append(
                ChapterProfile(
                    num=chapter_num,
                    title=chapter_title,
                    start_line=chapter_start,
                    end_line=chapter_end,
                    words=total_words,
                    paragraphs=len(chapter_paragraphs),
                    present_hits=present,
                    past_hits=past,
                    dominant=self._dominant(present, past),
                    flagged=sum(1 for p in chapter_paragraphs if p.is_flagged),
                    asl=round(total_words / total_sentences, 2) if total_sentences else 0.0,
                    dialog_pct=round(_weighted("dialogue_pct"), 1),
                    function_word_pct=round(_weighted("function_word_pct"), 1),
                )
            )

        for block in blocks:
            btype = block.get("type")
            if btype == "h2":
                if block.get("text", "").strip() == self._appendix_title:
                    in_appendix = True
                    break
                close_chapter()
                chapter_num = block.get("chapter_num", chapter_num + 1)
                chapter_title = block.get("text", "").strip()
                chapter_start = block.get("start_line", 0)
                chapter_end = block.get("end_line", 0)
                chapter_paragraphs = []
                prev_dominant = None
                continue

            if chapter_num == 0 and block.get("chapter_num"):
                chapter_num = block["chapter_num"]
                chapter_title = block.get("chapter_title", "")
                chapter_start = block.get("start_line", 0)
                chapter_end = block.get("end_line", 0)

            if in_appendix or chapter_num == 0:
                continue
            if btype not in ("p", "list_item"):
                continue

            raw_text = block.get("text", "")
            display_text = strip_inline_markup(raw_text)
            if not display_text:
                continue

            clean = counting_inline_text(raw_text)

            counts = self._matcher.count(clean)
            words = counts.words
            # Mirror the chapter metric: a fragment without word tokens is
            # not a sentence, and a resolved auto language picks its own
            # abbreviation table.
            sentences = counts.sentences
            present = len(self._praes.findall(clean))
            past = len(self._praet.findall(clean))
            dominant = self._dominant(present, past)

            mixed, minority_ratio = mixed_tense(present, past, self.thresholds)

            switch = (
                prev_dominant in (TENSE_PRESENT, TENSE_PAST)
                and dominant in (TENSE_PRESENT, TENSE_PAST)
                and dominant != prev_dominant
                and max(present, past) >= self.thresholds.switch_min_hits
            )

            severity = classify_severity(switch, mixed, min(present, past), self.thresholds)

            dialogue_words = counts.dialogue
            dialogue_pct = (dialogue_words / words * 100.0) if words else 0.0
            function_word_pct = (
                counts.function / words * 100.0
                if words
                else 0.0
            )

            filter_density = per_mille(counts.filter, words)
            modal_density = per_mille(counts.modal, words)
            nominal_density = per_mille(counts.nominal, words)
            passive_density = per_mille(counts.passive, words)

            profile = ParagraphProfile(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                start_line=block.get("start_line", 0),
                end_line=block.get("end_line", 0),
                words=words,
                sentences=len(sentences),
                present_hits=present,
                past_hits=past,
                dominant=dominant,
                minority_ratio=round(minority_ratio, 3),
                mixed=mixed,
                switch=switch,
                severity=severity,
                asl=round(words / len(sentences), 2) if sentences else 0.0,
                dialogue_pct=round(dialogue_pct, 1),
                function_word_pct=round(function_word_pct, 1),
                filter_density=round(filter_density, 1),
                modal_density=round(modal_density, 1),
                nominal_density=round(nominal_density, 1),
                passive_density=round(passive_density, 1),
                text=display_text,
                flag_min=self.thresholds.flag_min_severity,
            )
            if evidence is not None:
                evidence[len(paragraphs)] = self._matcher.evidence(clean, display_text, counts)
            paragraphs.append(profile)
            chapter_paragraphs.append(profile)
            chapter_end = block.get("end_line", chapter_end)
            prev_dominant = dominant

        close_chapter()
        return paragraphs, chapters
