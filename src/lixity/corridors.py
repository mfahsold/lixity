"""lixity.corridors – optional non-prescriptive genre reference corridors.

Provides descriptive orientation bands (ASL, dialogue share, staccato share,
average scene length) for broad fiction categories. Corridors are strictly
heuristic orientation aids for human review — never quality scores, grades,
or prescriptions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

CORRIDOR_SCOPE = (
    "Heuristic genre orientation corridor for editorial orientation only; "
    "not a quality score, grade, or prescription."
)


@dataclass(frozen=True)
class GenreCorridor:
    """Descriptive metric orientation ranges for one broad fiction category."""

    key: str
    label: str
    asl: tuple[float, float]
    dialogue_pct: tuple[float, float]
    staccato_pct: tuple[float, float]
    avg_scene_words: tuple[float, float]

    def bounds_dict(self) -> dict[str, list[float]]:
        return {
            "asl": [self.asl[0], self.asl[1]],
            "dialogue_pct": [self.dialogue_pct[0], self.dialogue_pct[1]],
            "staccato_pct": [self.staccato_pct[0], self.staccato_pct[1]],
            "avg_scene_words": [self.avg_scene_words[0], self.avg_scene_words[1]],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "non_prescriptive": True,
            "bounds": self.bounds_dict(),
        }


GENRE_CORRIDORS: dict[str, GenreCorridor] = {
    "crime_thriller": GenreCorridor(
        key="crime_thriller",
        label="Crime / Thriller",
        asl=(10.0, 16.0),
        dialogue_pct=(25.0, 50.0),
        staccato_pct=(15.0, 35.0),
        avg_scene_words=(800.0, 2200.0),
    ),
    "literary": GenreCorridor(
        key="literary",
        label="Literary Fiction",
        asl=(14.0, 24.0),
        dialogue_pct=(15.0, 40.0),
        staccato_pct=(8.0, 25.0),
        avg_scene_words=(1200.0, 3500.0),
    ),
    "romance": GenreCorridor(
        key="romance",
        label="Romance",
        asl=(11.0, 18.0),
        dialogue_pct=(30.0, 55.0),
        staccato_pct=(12.0, 30.0),
        avg_scene_words=(1000.0, 2800.0),
    ),
    "speculative": GenreCorridor(
        key="speculative",
        label="Speculative / Sci-Fi / Fantasy",
        asl=(13.0, 20.0),
        dialogue_pct=(20.0, 45.0),
        staccato_pct=(10.0, 28.0),
        avg_scene_words=(1200.0, 3200.0),
    ),
}

GENRE_CORRIDOR_KEYS: tuple[str, ...] = tuple(GENRE_CORRIDORS)


def resolve_genre_corridor(genre: str) -> GenreCorridor:
    """Resolve a genre key case-insensitively, raising ValueError if unknown."""
    if not isinstance(genre, str) or not genre.strip():
        raise ValueError(
            f"Genre corridor must be one of: {', '.join(GENRE_CORRIDOR_KEYS)}"
        )
    key = genre.strip().lower().replace("-", "_")
    if key not in GENRE_CORRIDORS:
        raise ValueError(
            f"Unknown genre corridor {genre!r}; choose from: {', '.join(GENRE_CORRIDOR_KEYS)}"
        )
    return GENRE_CORRIDORS[key]


def list_genre_corridors() -> list[dict[str, Any]]:
    """Return all available non-prescriptive genre corridors as JSON-safe dicts."""
    return [corridor.to_dict() for corridor in GENRE_CORRIDORS.values()]


def _position(value: float | None, low: float, high: float) -> str:
    if value is None:
        return "unavailable"
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "within"


def evaluate_genre_corridor(
    genre: str,
    observed: Mapping[str, float | None],
) -> dict[str, Any]:
    """Compare observed corpus/pacing metrics against a non-prescriptive corridor.

    Never computes a quality score or pass/fail grade; reports only whether each
    observed metric sits below, within, or above the reference band.
    """
    corridor = resolve_genre_corridor(genre)
    metrics: dict[str, dict[str, Any]] = {}
    for field_name, (low, high) in corridor.bounds_dict().items():
        val = observed.get(field_name)
        num_val = float(val) if val is not None else None
        metrics[field_name] = {
            "observed": round(num_val, 2) if num_val is not None else None,
            "low": low,
            "high": high,
            "position": _position(num_val, low, high),
        }
    return {
        "genre": corridor.key,
        "label": corridor.label,
        "non_prescriptive": True,
        "scope": CORRIDOR_SCOPE,
        "metrics": metrics,
    }


def pacing_corridor_observation(report: Any) -> dict[str, float | None]:
    """Derive chapter-weighted ASL, dialogue%, staccato%, and avg scene length from a PacingReport."""
    chapters = report.chapter_list
    total_words = sum(ch.words for ch in chapters)
    if not total_words:
        return {"asl": None, "dialogue_pct": None, "staccato_pct": None, "avg_scene_words": None}
    return {
        "asl": sum(ch.asl * ch.words for ch in chapters) / total_words,
        "dialogue_pct": sum(ch.dialogue_pct * ch.words for ch in chapters) / total_words,
        "staccato_pct": sum(ch.staccato_pct * ch.words for ch in chapters) / total_words,
        "avg_scene_words": report.avg_scene_words if report.scenes else None,
    }
