"""lixity.style_profile – Paragraph-accurate style and narrative tense profiling.

Classifies narrative tense (present / past / mixed / neutral), detects tense friction
and switches between consecutive paragraphs, and tracks paragraph-level style densities.
"""

import re
from dataclasses import dataclass
from typing import Any

from .language import compile_pattern, resolve_language
from .markdown_parser import strip_inline_markup
from .models import CorpusConfig

TENSE_PRESENT = "Präsens"
TENSE_PAST = "Präteritum"
TENSE_MIXED = "Gemischt"
TENSE_NEUTRAL = "Neutral"

SEVERITY_LABELS = {
    0: "unauffällig",
    1: "beobachten",
    2: "auffällig",
    3: "starke Friktion",
}


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

    @property
    def line_label(self) -> str:
        """Compact line anchor for the UI (e.g. "l. 470–472")."""
        if self.start_line == self.end_line:
            return f"Z. {self.start_line}"
        return f"Z. {self.start_line}–{self.end_line}"

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, "unauffällig")


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


@dataclass(frozen=True)
class ProfileThresholds:
    """Thresholds of the style profile heuristic (injectable, documented, reproducible)."""

    neutral_max_hits: int = 1  # fewer than 2 tense markers: no statement
    mix_min_hits: int = 2  # at least 2 markers per tense
    mix_min_ratio: float = 0.25  # minority share from 25 % = mixed
    switch_min_hits: int = 2  # dominant tense requires >= 2 markers
    severe_mix_minority: int = 3  # mixed + >= 3 minority markers = level 2


class ParagraphProfiler:
    """Stateless engine for paragraph-accurate tense and style profiles."""

    def __init__(
        self,
        config: CorpusConfig | None = None,
        thresholds: ProfileThresholds | None = None,
    ):
        self.config = config or CorpusConfig()
        self.thresholds = thresholds or ProfileThresholds()
        self.lang = resolve_language(self.config)
        self._praes = compile_pattern(self.lang.praesens_regex)
        self._praet = compile_pattern(self.lang.praeteritum_regex)
        self._markers = re.compile(r"<!--\s*(PRÜFEN|SACHCHECK)\b")
        self._dialogue = re.compile(self.lang.dialogue_regex)
        self._word = re.compile(self.lang.word_regex)
        self._appendix_title = self.config.appendix_marker.replace("##", "").strip()
        # Style densities per paragraph (house-style overlay, per 1,000 words)
        self._filter = compile_pattern(self.lang.filter_verbs_regex)
        self._passive = compile_pattern(self.lang.passive_regex)
        self._nominal = compile_pattern(self.lang.nominal_regex)
        self._modals = frozenset(w.lower() for w in self.lang.lexicon.get("modals", ()))

    def _sentence_tense(self, sentence: str) -> str | None:
        """Classifies a single sentence as present-, past- or mixed-dominant."""
        pr = len(self._praes.findall(sentence))
        pt = len(self._praet.findall(sentence))
        if pr == 0 and pt == 0:
            return None
        if pr > pt:
            return TENSE_PRESENT
        if pt > pr:
            return TENSE_PAST
        return TENSE_MIXED

    def _dominant(self, present: int, past: int) -> str:
        total = present + past
        if total <= self.thresholds.neutral_max_hits:
            return TENSE_NEUTRAL
        ratio = present / (past + 0.001)
        if ratio > 1.5:
            return TENSE_PRESENT
        if ratio < 0.67:
            return TENSE_PAST
        return TENSE_MIXED

    def profile_blocks(
        self, blocks: list[dict[str, Any]]
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

        def close_chapter():
            if not chapter_title or not chapter_paragraphs:
                return  # do not list empty chapters (e.g. an acknowledgements section still open)
            present = sum(p.present_hits for p in chapter_paragraphs)
            past = sum(p.past_hits for p in chapter_paragraphs)
            total_words = sum(p.words for p in chapter_paragraphs)
            total_sentences = sum(p.sentences for p in chapter_paragraphs)

            def _weighted(attr: str) -> float:
                if not total_words:
                    return 0.0
                return sum(getattr(p, attr) * p.words for p in chapter_paragraphs) / total_words

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
                    flagged=sum(1 for p in chapter_paragraphs if p.severity >= 2),
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
                chapter_num += 1
                chapter_title = block.get("text", "").strip()
                chapter_start = block.get("start_line", 0)
                chapter_end = block.get("end_line", 0)
                chapter_paragraphs = []
                prev_dominant = None
                continue

            if in_appendix or chapter_num == 0:
                continue
            if btype not in ("p", "list_item"):
                continue

            raw_text = block.get("text", "")
            clean = strip_inline_markup(raw_text)
            if not clean:
                continue

            words = len(self._word.findall(clean))
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
            present = len(self._praes.findall(clean))
            past = len(self._praet.findall(clean))
            dominant = self._dominant(present, past)

            total = present + past
            minority_ratio = (min(present, past) / total) if total else 0.0
            mixed = (
                present >= self.thresholds.mix_min_hits
                and past >= self.thresholds.mix_min_hits
                and minority_ratio >= self.thresholds.mix_min_ratio
            )

            switch = (
                prev_dominant in (TENSE_PRESENT, TENSE_PAST)
                and dominant in (TENSE_PRESENT, TENSE_PAST)
                and dominant != prev_dominant
                and max(present, past) >= self.thresholds.switch_min_hits
            )

            minority = min(present, past)
            if switch and mixed and minority >= self.thresholds.severe_mix_minority:
                severity = 3
            elif (switch and minority >= self.thresholds.mix_min_hits) or (
                mixed and minority >= self.thresholds.severe_mix_minority
            ):
                severity = 2
            elif switch or mixed:
                severity = 1
            else:
                severity = 0

            dialogue_words = sum(len(m.split()) for m in self._dialogue.findall(clean))
            dialogue_pct = (dialogue_words / words * 100.0) if words else 0.0
            tokens = [t.lower() for t in self._word.findall(clean)]
            function_word_pct = (
                sum(1 for t in tokens if t in self.lang.function_words) / len(tokens) * 100.0
                if tokens
                else 0.0
            )

            def per_mille(matches: int, base_words: int = words) -> float:
                return (matches / base_words * 1000.0) if base_words else 0.0

            filter_density = per_mille(len(self._filter.findall(clean)))
            modal_density = per_mille(sum(1 for t in tokens if t in self._modals))
            nominal_density = per_mille(len(self._nominal.findall(clean)))
            passive_density = per_mille(len(self._passive.findall(clean)))

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
                text=clean,
            )
            paragraphs.append(profile)
            chapter_paragraphs.append(profile)
            chapter_end = block.get("end_line", chapter_end)
            prev_dominant = dominant

        close_chapter()
        return paragraphs, chapters
