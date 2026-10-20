"""lixity.showing – showing vs. telling signals (narrative distance).

A **heuristic composite**, documented and self-calibrating like the style
reference: the manuscript's own chapter medians are the reference, so the
report says "this chapter tells more than this book usually does", not "this
chapter is bad".

Telling signals (per 1,000 words): perception filters (see/hear/feel/notice/
think), modals (hedging), passive constructions, nominalisations.
Showing signals (shares in %): dialogue, staccato sentences.

For each chapter the report computes robust z-scores (median/MAD, scaled) for
the mean of the telling and showing signals and the balance
``show_z − tell_z``. Positive balance = more showing than telling *relative to
this manuscript*; negative = more telling. Deliberate telling is a stylistic
device — the report ranks and locates, it does not judge.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .analyzer import CorpusAnalyzer
from .language import resolve_language
from .math_core import mad, median, robust_z
from .models import CorpusConfig
from .style_fingerprint import MIN_COMPARABLE_WORDS

TELL_FEATURES = ("filter_density", "modal_density", "passive_density", "nominalization_density")
SHOW_FEATURES = ("dialog_pct", "staccato_pct")
MIN_COMPARISON_CHAPTERS = 3


@dataclass(frozen=True)
class ChapterBalance:
    """Telling/showing balance of one chapter (robust z, self-calibrated).

    ``comparable`` is False below the manuscript-level word floor: the raw
    densities stay visible, but no z-scores or rankings are derived from them.
    """

    chapter_num: int
    title: str
    tell_z: float | None
    show_z: float | None
    balance: float | None
    filter_density: float
    modal_density: float
    passive_density: float
    nominalization_density: float
    dialog_pct: float
    staccato_pct: float
    comparable: bool = True

    def to_dict(self) -> dict[str, Any]:
        def rounded(value: float | None) -> float | None:
            return None if value is None else round(value, 2)

        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "comparable": self.comparable,
            "tell_z": rounded(self.tell_z),
            "show_z": rounded(self.show_z),
            "balance": rounded(self.balance),
            "filter_density": round(self.filter_density, 2),
            "modal_density": round(self.modal_density, 2),
            "passive_density": round(self.passive_density, 2),
            "nominalization_density": round(self.nominalization_density, 2),
            "dialog_pct": round(self.dialog_pct, 2),
            "staccato_pct": round(self.staccato_pct, 2),
        }


@dataclass(frozen=True)
class ShowingReport:
    """Corpus-level showing/telling balance with per-chapter detail."""

    language: str
    chapters: int
    tell_z_mean: float | None
    show_z_mean: float | None
    balance_mean: float | None
    comparable_chapters: int = 0
    most_telling: list[int] = field(default_factory=list)
    most_showing: list[int] = field(default_factory=list)
    chapter_list: list[ChapterBalance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def rounded(value: float | None) -> float | None:
            return None if value is None else round(value, 2)

        return {
            "language": self.language,
            "chapters": self.chapters,
            "comparable_chapters": self.comparable_chapters,
            "tell_z_mean": rounded(self.tell_z_mean),
            "show_z_mean": rounded(self.show_z_mean),
            "balance_mean": rounded(self.balance_mean),
            "most_telling": self.most_telling,
            "most_showing": self.most_showing,
            "chapter_list": [chapter.to_dict() for chapter in self.chapter_list],
        }


def _z_map(values: dict[int, float]) -> dict[int, float]:
    """Robust z per chapter against the manuscript's own median/MAD.

    Fallback: when the median absolute deviation is zero (the majority of
    chapters share the median — common for share features such as dialogue),
    the standard deviation is used instead so the signal is not lost.
    """
    if len(values) < MIN_COMPARISON_CHAPTERS:
        return dict.fromkeys(values, 0.0)
    data = list(values.values())
    centre = median(data)
    spread = mad(data, centre)
    if spread > 0.0:
        return {num: robust_z(value, centre, spread) for num, value in values.items()}
    deviation = statistics.pstdev(data)
    if deviation == 0.0:
        return dict.fromkeys(values, 0.0)
    return {num: (value - centre) / deviation for num, value in values.items()}


def showing_report(
    text: str,
    config: CorpusConfig | None = None,
    metrics: Any | None = None,
) -> ShowingReport:
    """Showing/telling balance per chapter (heuristic, self-calibrating).

    ``metrics`` allows callers that already analysed the text (CLI dashboard,
    book adapter) to reuse the result instead of re-running the analyzer.
    """
    config = config or CorpusConfig()
    language = resolve_language(config, sample_text=text).key
    resolved_metrics = (metrics if metrics is not None
                        else CorpusAnalyzer(config, sample_text=text).analyze_text(text))
    chapters = resolved_metrics.chapters
    if not chapters:
        return ShowingReport(
            language=language, chapters=0, tell_z_mean=None, show_z_mean=None, balance_mean=None
        )

    # Comparability floor: chapters below MIN_COMPARABLE_WORDS keep their raw
    # densities but stay out of every z-score, mean and ranking.
    comparable_nums = {chapter.num for chapter in chapters if chapter.words >= MIN_COMPARABLE_WORDS}
    tell_z: dict[int, float] = {}
    show_z: dict[int, float] = {}
    for field_name in TELL_FEATURES:
        values = {
            chapter.num: float(getattr(chapter, field_name))
            for chapter in chapters if chapter.num in comparable_nums
        }
        for num, z in _z_map(values).items():
            tell_z[num] = tell_z.get(num, 0.0) + z / len(TELL_FEATURES)
    for field_name in SHOW_FEATURES:
        values = {
            chapter.num: float(getattr(chapter, field_name))
            for chapter in chapters if chapter.num in comparable_nums
        }
        for num, z in _z_map(values).items():
            show_z[num] = show_z.get(num, 0.0) + z / len(SHOW_FEATURES)

    chapter_list = []
    for chapter in chapters:
        is_comparable = chapter.num in comparable_nums
        tell_value: float | None = None
        show_value: float | None = None
        balance: float | None = None
        if is_comparable:
            tell_value = tell_z.get(chapter.num, 0.0)
            show_value = show_z.get(chapter.num, 0.0)
            balance = show_value - tell_value
        chapter_list.append(ChapterBalance(
            chapter_num=chapter.num,
            title=chapter.title,
            tell_z=tell_value,
            show_z=show_value,
            balance=balance,
            filter_density=chapter.filter_density,
            modal_density=chapter.modal_density,
            passive_density=chapter.passive_density,
            nominalization_density=chapter.nominalization_density,
            dialog_pct=chapter.dialog_pct,
            staccato_pct=chapter.staccato_pct,
            comparable=is_comparable,
        ))

    comparable_list = [chapter for chapter in chapter_list if chapter.comparable]

    def mean(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    tell_values = [c.tell_z for c in comparable_list if c.tell_z is not None]
    show_values = [c.show_z for c in comparable_list if c.show_z is not None]
    balance_values = [c.balance for c in comparable_list if c.balance is not None]

    ranked = sorted(comparable_list, key=lambda item: item.balance or 0.0)
    # Unmeasurable or identical balances do not support a chapter ranking.
    if balance_values and min(balance_values) == max(balance_values):
        ranked = []
    return ShowingReport(
        language=language,
        chapters=len(chapter_list),
        tell_z_mean=mean(tell_values),
        show_z_mean=mean(show_values),
        balance_mean=mean(balance_values),
        comparable_chapters=len(comparable_list),
        most_telling=[c.chapter_num for c in ranked[:3]],
        most_showing=[c.chapter_num for c in reversed(ranked[-3:])],
        chapter_list=chapter_list,
    )
