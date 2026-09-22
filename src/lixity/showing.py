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
from .models import CorpusConfig
from .style_fingerprint import mad, median, robust_z

TELL_FEATURES = ("filter_density", "modal_density", "passive_density", "nominalization_density")
SHOW_FEATURES = ("dialog_pct", "staccato_pct")


@dataclass(frozen=True)
class ChapterBalance:
    """Telling/showing balance of one chapter (robust z, self-calibrated)."""

    chapter_num: int
    title: str
    tell_z: float
    show_z: float
    balance: float
    filter_density: float
    modal_density: float
    passive_density: float
    nominalization_density: float
    dialog_pct: float
    staccato_pct: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "tell_z": round(self.tell_z, 2),
            "show_z": round(self.show_z, 2),
            "balance": round(self.balance, 2),
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
    tell_z_mean: float
    show_z_mean: float
    balance_mean: float
    most_telling: list[int] = field(default_factory=list)
    most_showing: list[int] = field(default_factory=list)
    chapter_list: list[ChapterBalance] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "chapters": self.chapters,
            "tell_z_mean": round(self.tell_z_mean, 2),
            "show_z_mean": round(self.show_z_mean, 2),
            "balance_mean": round(self.balance_mean, 2),
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
    if len(values) < 3:
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
    config = config or CorpusConfig(language="auto")
    resolved_metrics = metrics if metrics is not None else CorpusAnalyzer(config).analyze_text(text)
    chapters = resolved_metrics.chapters
    if not chapters:
        return ShowingReport(
            language=config.language, chapters=0, tell_z_mean=0.0, show_z_mean=0.0, balance_mean=0.0
        )

    tell_z: dict[int, float] = {}
    show_z: dict[int, float] = {}
    for field_name in TELL_FEATURES:
        values = {chapter.num: float(getattr(chapter, field_name)) for chapter in chapters}
        for num, z in _z_map(values).items():
            tell_z[num] = tell_z.get(num, 0.0) + z / len(TELL_FEATURES)
    for field_name in SHOW_FEATURES:
        values = {chapter.num: float(getattr(chapter, field_name)) for chapter in chapters}
        for num, z in _z_map(values).items():
            show_z[num] = show_z.get(num, 0.0) + z / len(SHOW_FEATURES)

    chapter_list = [
        ChapterBalance(
            chapter_num=chapter.num,
            title=chapter.title,
            tell_z=tell_z.get(chapter.num, 0.0),
            show_z=show_z.get(chapter.num, 0.0),
            balance=show_z.get(chapter.num, 0.0) - tell_z.get(chapter.num, 0.0),
            filter_density=chapter.filter_density,
            modal_density=chapter.modal_density,
            passive_density=chapter.passive_density,
            nominalization_density=chapter.nominalization_density,
            dialog_pct=chapter.dialog_pct,
            staccato_pct=chapter.staccato_pct,
        )
        for chapter in chapters
    ]

    ranked = sorted(chapter_list, key=lambda item: item.balance)
    return ShowingReport(
        language=config.language,
        chapters=len(chapter_list),
        tell_z_mean=sum(c.tell_z for c in chapter_list) / len(chapter_list),
        show_z_mean=sum(c.show_z for c in chapter_list) / len(chapter_list),
        balance_mean=sum(c.balance for c in chapter_list) / len(chapter_list),
        most_telling=[c.chapter_num for c in ranked[:3]],
        most_showing=[c.chapter_num for c in reversed(ranked[-3:])],
        chapter_list=chapter_list,
    )
