"""
scripts/engine/style_fingerprint.py
====================================
Self-calibrating style fingerprint: register-neutral consistency analysis.

Instead of judging style against external norms, the engine derives the
author's own **house style** from the corpus itself: for each descriptive
feature, the robust centre (median) and spread (MAD) over the chapters.
A chapter or paragraph is flagged only when it deviates from its own house
style (robust z-score) – whether that deviation is intended (a register
scene) or drift is a decision the author makes, never the engine.

Mathematical core (dependency-free, deterministic, transparent):
- median / MAD: robust location and spread, insensitive to outliers.
- robust z = 0.6745 * (x - median) / MAD  (MAD scaled to N(0,1) consistency).
- Jensen-Shannon distance per chapter vs. the rest of the corpus with
  additive, interpretable per-word contributions (computed in analyzer.py).
- HD-D (McCarthy & Jarvis 2010) for length-robust lexical diversity.

The **style passport** exports the self-calibrated feature bands as
structured data (JSON) and as a human-readable constraint block – usable by
the author or an assisting LLM to keep new prose inside the house style.
"""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

# Descriptive, register-neutral features: (model field, label key).
# Every style – staccato or cascading, nominal or verbal – is a legal value;
# only the deviation from the text's own centre is measured.
FEATURES: tuple[tuple[str, str], ...] = (
    ("asl", "feat_asl"),
    ("staccato_pct", "feat_staccato"),
    ("kaskade_pct", "feat_kaskade"),
    ("sentence_cv", "feat_cv"),
    ("dialog_pct", "feat_dialog"),
    ("function_word_pct", "feat_function"),
    ("filter_density", "feat_filter"),
    ("modal_density", "feat_modal"),
    ("passive_density", "feat_passive"),
    ("nominalization_density", "feat_nominal"),
    ("adjective_density", "feat_adjective"),
    ("long_word_pct", "feat_long_words"),
    ("start_entropy", "feat_start_entropy"),
    ("first_person_start_rate", "feat_ich_start"),
    ("guiraud_r", "feat_guiraud"),
    ("hd_d", "feat_hd_d"),
)

# Paragraph-level overlay layers for the chapter strips (chip bottom edge).
LAYER_FEATURES: dict[str, str] = {
    "asl": "asl",
    "function": "function_word_pct",
    "dialogue": "dialogue_pct",
    "filter": "filter_density",
    "modal": "modal_density",
    "nominal": "nominalization_density",
    "passive": "passive_density",
}


@dataclass(frozen=True)
class FingerprintThresholds:
    """Thresholds of the consistency heuristic (injectable, documented)."""

    z_mild: float = 2.5  # robust z from here: noticeable deviation
    z_strong: float = 3.5  # robust z from here: strong deviation
    min_chapters: int = 2  # below this chapter count no baseline is derived


def median(values: list[float]) -> float:
    return statistics.median(values)


def mad(values: list[float], centre: float) -> float:
    """Median absolute deviation; 0.0 for fewer than two observations."""
    if len(values) < 2:
        return 0.0
    return statistics.median([abs(v - centre) for v in values])


def robust_z(value: float, centre: float, spread: float) -> float:
    """Robust z-score: 0.6745 scales MAD to normal-consistency sigma."""
    if spread == 0.0:
        return 0.0
    return 0.6745 * (value - centre) / spread


def z_color(z: float) -> str:
    """
    Deterministic diverging colour scale for robust z-scores
    (blue = below house mean, grey = on mean, orange = above).
    Clamped to [-2.5, +2.5]; no external colour libraries.
    """
    stops = (
        (-2.5, (43, 108, 176)),
        (-1.0, (123, 167, 208)),
        (0.0, (229, 231, 235)),
        (1.0, (232, 176, 122)),
        (2.5, (192, 86, 33)),
    )
    z = max(stops[0][0], min(stops[-1][0], z))
    for (z0, c0), (z1, c1) in pairwise(stops):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            rgb = tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return f"#{stops[-1][1][0]:02x}{stops[-1][1][1]:02x}{stops[-1][1][2]:02x}"


@dataclass
class StyleFingerprint:
    """
    Self-calibrated style fingerprint of a corpus.

    - values:       feature -> {chapter_num: value} (None = not measurable)
    - baseline:     feature -> {"median", "mad", "sigma", "n"}
    - z_scores:     chapter_num -> {feature: z}
    - deviations:   chapter_num -> {feature: z}  (only |z| >= z_mild)
    - consistency:  share of measurable cells inside the band [0, 1]
    """

    values: dict[str, dict[int, float | None]] = field(default_factory=dict)
    baseline: dict[str, dict[str, float | int]] = field(default_factory=dict)
    z_scores: dict[int, dict[str, float]] = field(default_factory=dict)
    deviations: dict[int, dict[str, float]] = field(default_factory=dict)
    consistency: float = 1.0
    n_chapters: int = 0

    @classmethod
    def from_metrics(
        cls, metrics: Any, thresholds: FingerprintThresholds | None = None
    ) -> "StyleFingerprint":
        """Derives the fingerprint from a CorpusMetrics object (self-calibration)."""
        thresholds = thresholds or FingerprintThresholds()
        chapters = getattr(metrics, "chapters", []) or []
        values: dict[str, dict[int, float | None]] = {}
        for field_name, _label in FEATURES:
            col: dict[int, float | None] = {}
            for chapter in chapters:
                raw = getattr(chapter, field_name, None)
                col[chapter.num] = float(raw) if isinstance(raw, int | float) else None
            values[field_name] = col

        baseline: dict[str, dict[str, float | int]] = {}
        z_scores: dict[int, dict[str, float]] = {c.num: {} for c in chapters}
        measured_cells = 0
        in_band = 0
        for field_name, _label in FEATURES:
            obs = [v for v in values[field_name].values() if v is not None]
            if len(obs) < thresholds.min_chapters:
                baseline[field_name] = {"median": 0.0, "mad": 0.0, "sigma": 0.0, "n": len(obs)}
                continue
            centre = median(obs)
            spread = mad(obs, centre)
            baseline[field_name] = {
                "median": centre,
                "mad": spread,
                "sigma": 1.4826 * spread,
                "n": len(obs),
            }
            for chapter in chapters:
                value = values[field_name].get(chapter.num)
                if value is None:
                    continue
                z = robust_z(value, centre, spread)
                z_scores[chapter.num][field_name] = z
                measured_cells += 1
                if abs(z) < thresholds.z_mild:
                    in_band += 1

        deviations: dict[int, dict[str, float]] = {}
        for chapter in chapters:
            flagged = {
                feat: z
                for feat, z in z_scores.get(chapter.num, {}).items()
                if abs(z) >= thresholds.z_mild
            }
            if flagged:
                deviations[chapter.num] = flagged

        consistency = (in_band / measured_cells) if measured_cells else 1.0
        return cls(
            values=values,
            baseline=baseline,
            z_scores=z_scores,
            deviations=deviations,
            consistency=consistency,
            n_chapters=len(chapters),
        )

    def top_deviants(self, n: int = 3) -> list[tuple[int, float]]:
        """Chapters with the highest mean absolute robust z (style drift ranking)."""
        scored = []
        for chapter_num, cells in self.z_scores.items():
            if not cells:
                continue
            mean_abs = sum(abs(z) for z in cells.values()) / len(cells)
            scored.append((chapter_num, mean_abs))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:n]

    def passport(self) -> dict:
        """Structured style passport (JSON-serialisable constraint data)."""
        features = []
        for field_name, _label in FEATURES:
            base = self.baseline.get(field_name, {})
            sigma = float(base.get("sigma", 0.0))
            centre = float(base.get("median", 0.0))
            features.append(
                {
                    "feature": field_name,
                    "median": round(centre, 4),
                    "sigma": round(sigma, 4),
                    "band": [round(centre - 2 * sigma, 4), round(centre + 2 * sigma, 4)],
                    "chapters_measured": int(base.get("n", 0)),
                }
            )
        return {
            "chapters": self.n_chapters,
            "consistency": round(self.consistency, 4),
            "features": features,
            "deviations": {
                str(chapter_num): {feat: round(z, 2) for feat, z in dev.items()}
                for chapter_num, dev in sorted(self.deviations.items())
            },
        }

    def passport_text(self, labels: Mapping[str, str] | None = None) -> str:
        """Human-readable style passport (constraint block for author or LLM)."""
        labels = labels or {}
        lines = [
            f"STILPASS – selbstkalibrierter Hausstil ({self.n_chapters} Kapitel)",
            "=" * 62,
        ]
        for field_name, label_key in FEATURES:
            base = self.baseline.get(field_name, {})
            if not base.get("n"):
                continue
            centre = float(base["median"])
            sigma = float(base["sigma"])
            label = labels.get(label_key, field_name)
            if sigma > 0.0:
                lines.append(
                    f"{label:<22} Median {centre:>9.2f}   Korridor "
                    f"{centre - 2 * sigma:>8.2f} – {centre + 2 * sigma:.2f}"
                )
            else:
                lines.append(f"{label:<22} Median {centre:>9.2f}   (konstant)")
        lines.append("=" * 62)
        lines.append(f"Konsistenz: {self.consistency * 100:.1f} % der Zellen im Korridor")
        field_labels = dict(FEATURES)
        for chapter_num, mean_abs in self.top_deviants(5):
            dev = self.deviations.get(chapter_num, {})
            named = ", ".join(
                f"{labels.get(field_labels.get(k, k), k)} {z:+.1f}\u03c3"
                for k, z in sorted(dev.items(), key=lambda kv: abs(kv[1]), reverse=True)[:4]
            )
            lines.append(f"Kapitel {chapter_num:>2}: Ø|z| {mean_abs:.2f} – {named}")
        return "\n".join(lines)


def layer_colors(
    paragraphs: Sequence[Any], layer: str, thresholds: FingerprintThresholds | None = None
) -> dict[int, str | None]:
    """
    Colours for the chapter-strip overlay: within-chapter robust z of the
    selected paragraph feature, mapped to the diverging colour scale.
    Returns {paragraph_index: css colour or None (not measurable)}.
    """
    field_name = LAYER_FEATURES.get(layer)
    if field_name is None:
        return {}
    by_chapter: dict[int, list[tuple[int, float]]] = {}
    for idx, p in enumerate(paragraphs):
        value = getattr(p, field_name, None)
        if not isinstance(value, int | float):
            continue
        by_chapter.setdefault(p.chapter_num, []).append((idx, float(value)))
    colours: dict[int, str | None] = {}
    for pairs in by_chapter.values():
        obs = [v for _, v in pairs]
        if len(obs) < 3:
            for idx, _ in pairs:
                colours[idx] = None
            continue
        centre = median(obs)
        spread = mad(obs, centre)
        if spread == 0.0:
            for idx, _ in pairs:
                colours[idx] = None
            continue
        for idx, value in pairs:
            colours[idx] = z_color(robust_z(value, centre, spread))
    return colours
