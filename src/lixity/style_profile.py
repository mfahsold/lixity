"""
scripts/engine/style_profile.py
===============================
Absatzgenaue Stil- und Tempusprofile mit Zeilenankern.

Die Engine erkennt auf Basis semantischer Markdown-Blöcke (inkl. Zeilenanker
aus ``markdown_parser``):

- das dominante Tempus je Absatz (Präsens / Präteritum / Gemischt / Neutral),
- **Tempuswechsel** zwischen aufeinanderfolgenden Absätzen eines Kapitels
  (potenzielle Micro-Friktionen wie retro-spektive Einschübe),
- **tempusgemischte** Absätze (Minderheitenanteil über Schwellwert),
- Satzlängen-, Dialog- und Arbeitsmarker-Profil je Absatz.

Die Heuristik ist bewusst transparent und reproduzierbar: Sie zählt kuratierte
Hochfrequenz-Verbformen (``CorpusConfig.praesens_regex`` / ``praeteritum_regex``)
und leitet daraus Verhältnisse ab – keine Blackbox, keine externen NLP-Modelle.

Projektneutral: keine Buch-spezifischen Hardcodings; der Anhang wird über den
konfigurierten ``appendix_marker`` abgetrennt.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
    """Stilprofil eines einzelnen Fließtext-Absatzes mit Zeilenanker."""

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
    text: str

    @property
    def line_label(self) -> str:
        """Kompakter Zeilenanker für die UI (z. B. „Z. 470–472“)."""
        if self.start_line == self.end_line:
            return f"Z. {self.start_line}"
        return f"Z. {self.start_line}–{self.end_line}"

    @property
    def severity_label(self) -> str:
        return SEVERITY_LABELS.get(self.severity, "unauffällig")


@dataclass
class ChapterProfile:
    """Aggregiertes Tempusprofil eines Kapitels (für Navigation & Kennzahlen)."""

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
    """Schwellwerte der Stilprofil-Heuristik (injizierbar, dokumentiert, reproduzierbar)."""

    neutral_max_hits: int = 1  # unter 2 Tempusmarkern: keine Aussage
    mix_min_hits: int = 2  # je Tempus mindestens 2 Marker
    mix_min_ratio: float = 0.25  # Minderheitenanteil ab 25 % = gemischt
    switch_min_hits: int = 2  # dominantes Tempus braucht >= 2 Marker
    severe_mix_minority: int = 3  # gemischt + >= 3 Minderheitenmarker = Stufe 2


class ParagraphProfiler:
    """Zustandslose Engine für absatzgenaue Tempus- und Stilprofile."""

    def __init__(
        self,
        config: Optional[CorpusConfig] = None,
        thresholds: Optional[ProfileThresholds] = None,
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

    def _sentence_tense(self, sentence: str) -> Optional[str]:
        """Klassifiziert einen einzelnen Satz als Präsens-, Präteritum- oder gemischt-dominant."""
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
        self, blocks: List[Dict[str, Any]]
    ) -> Tuple[List[ParagraphProfile], List[ChapterProfile]]:
        """Erzeugt Absatz- und Kapitelprofile aus semantischen Blöcken (mit Zeilenankern)."""
        paragraphs: List[ParagraphProfile] = []
        chapters: List[ChapterProfile] = []

        chapter_num = 0
        chapter_title = ""
        chapter_start = 0
        chapter_end = 0
        chapter_paragraphs: List[ParagraphProfile] = []
        prev_dominant: Optional[str] = None
        in_appendix = False

        def close_chapter():
            if not chapter_title or not chapter_paragraphs:
                return  # leere Kapitel (z. B. noch offene Danksagung) nicht führen
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
                text=clean,
            )
            paragraphs.append(profile)
            chapter_paragraphs.append(profile)
            chapter_end = block.get("end_line", chapter_end)
            prev_dominant = dominant

        close_chapter()
        return paragraphs, chapters
