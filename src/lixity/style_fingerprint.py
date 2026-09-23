"""lixity.style_fingerprint – Self-calibrating style passport and latent style dimensions.

Derives the manuscript's reference house style using robust statistics (median/MAD),
computes significance-adjusted deviations (z* with standard errors), controls false
discoveries (Benjamini-Hochberg FDR), and extracts latent style dimensions via cyclic
Jacobi eigendecomposition.
"""

import math
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from .format import num as format_num

# Descriptive, register-neutral features: (model field, label key, unit).
# Every style – staccato or cascading, nominal or verbal – is a legal value;
# only the deviation from the text's own centre is measured.
FEATURES: tuple[tuple[str, str, str], ...] = (
    ("asl", "feat_asl", "words per sentence"),
    ("staccato_pct", "feat_staccato", "% of sentences"),
    ("kaskade_pct", "feat_kaskade", "% of sentences"),
    ("sentence_cv", "feat_cv", "coefficient"),
    ("dialog_pct", "feat_dialog", "% of words"),
    ("function_word_pct", "feat_function", "% of words"),
    ("filter_density", "feat_filter", "per 1,000 words"),
    ("modal_density", "feat_modal", "per 1,000 words"),
    ("passive_density", "feat_passive", "per 1,000 words"),
    ("nominalization_density", "feat_nominal", "per 1,000 words"),
    ("adjective_density", "feat_adjective", "per 1,000 words"),
    ("long_word_pct", "feat_long_words", "% of words"),
    ("start_entropy", "feat_start_entropy", "bit"),
    ("first_person_start_rate", "feat_ich_start", "% of sentences"),
    ("guiraud_r", "feat_guiraud", "index"),
    ("hd_d", "feat_hd_d", "index"),
)

# Localised unit strings (FEATURES carries the English defaults).
FEATURE_UNITS_DE: dict[str, str] = {
    "asl": "Wörter je Satz",
    "staccato_pct": "% der Sätze",
    "kaskade_pct": "% der Sätze",
    "sentence_cv": "Koeffizient",
    "dialog_pct": "% der Wörter",
    "function_word_pct": "% der Wörter",
    "filter_density": "je 1.000 Wörter",
    "modal_density": "je 1.000 Wörter",
    "passive_density": "je 1.000 Wörter",
    "nominalization_density": "je 1.000 Wörter",
    "adjective_density": "je 1.000 Wörter",
    "long_word_pct": "% der Wörter",
    "start_entropy": "bit",
    "first_person_start_rate": "% der Sätze",
    "guiraud_r": "Index",
    "hd_d": "Index",
}

FEATURE_FIELDS: tuple[str, ...] = tuple(f for f, _l, _u in FEATURES)

# Paragraph-level overlay layers for the chapter strips (chip bottom edge).
# Values are the fingerprint/chapter field names (FEATURES / deviations).
LAYER_FEATURES: dict[str, str] = {
    "asl": "asl",
    "function": "function_word_pct",
    "dialogue": "dialog_pct",
    "filter": "filter_density",
    "modal": "modal_density",
    "nominal": "nominalization_density",
    "passive": "passive_density",
}
# ParagraphProfile attribute per layer key (dialogue/nominal use shorter names).
LAYER_PARAGRAPH_ATTR: dict[str, str] = {
    "asl": "asl",
    "function": "function_word_pct",
    "dialogue": "dialogue_pct",
    "filter": "filter_density",
    "modal": "modal_density",
    "nominal": "nominal_density",
    "passive": "passive_density",
}

# Dimensions to extract from the feature correlation matrix.
N_DIMENSIONS = 3
DIM_SCORE_THRESHOLD = 2.5  # |chapter score| from here: strong position on a dimension
REDUNDANCY_RHO = 0.8  # |Spearman rho| from here: features measure (almost) the same


@dataclass(frozen=True)
class FingerprintThresholds:
    """Thresholds of the consistency heuristic (injectable, documented)."""

    z_mild: float = 2.5  # significance-adjusted z from here: noticeable deviation
    z_strong: float = 3.5  # significance-adjusted z from here: strong deviation
    fdr_q: float = 0.05  # Benjamini-Hochberg / Benjamini-Yekutieli false-discovery rate
    fdr_method: str = "bh"  # "bh" (default) or "by" (arbitrary dependence)
    min_chapters: int = 2  # below this chapter count no baseline is derived
    dim_score_threshold: float = 2.5  # |dimension score| from here: flagged on that axis
    flag_min_severity: int = 2  # paragraph severity floor for the flags panel (1|2|3)


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


def significance_z(value: float, centre: float, sigma: float, se: float) -> float:
    """Deviation tested against house-style spread AND estimation noise."""
    denom = math.sqrt(sigma**2 + se**2)
    return (value - centre) / denom if denom > 0.0 else 0.0


def normal_tail_probability(z: float) -> float:
    """Two-sided p-value via math.erf (stdlib, no scipy)."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def benjamini_hochberg(
    cells: list[tuple[int, str, float]], q: float = 0.05
) -> list[tuple[int, str]]:
    """
    Benjamini-Hochberg FDR control over (chapter, feature, p-value) cells.
    Returns the significant cell set at level q (deterministic ordering).
    """
    ordered = sorted(cells, key=lambda c: (c[2], c[0], c[1]))
    m = len(ordered)
    k_star = 0
    for k, (_ch, _f, p) in enumerate(ordered, start=1):
        if p <= q * k / m:
            k_star = k
    return [(ch, feat) for ch, feat, _p in ordered[:k_star]]


def benjamini_yekutieli(
    cells: list[tuple[int, str, float]], q: float = 0.05
) -> list[tuple[int, str]]:
    """
    Benjamini-Yekutieli FDR control: BH step-up with the harmonic factor
    c(m) = sum 1/i, valid under arbitrary dependence between tests
    (style features are strongly correlated).
    """
    if not cells:
        return []
    m = len(cells)
    harmonic = sum(1.0 / i for i in range(1, m + 1))
    return benjamini_hochberg(cells, q=q / harmonic)


def fdr_rejects(
    cells: list[tuple[int, str, float]], q: float = 0.05, method: str = "bh"
) -> list[tuple[int, str]]:
    """Dispatch BH (default) or BY multiplicity control."""
    if method.lower() in ("by", "benjamini-yekutieli", "benjamini_yekutieli"):
        return benjamini_yekutieli(cells, q=q)
    return benjamini_hochberg(cells, q=q)


def cliff_delta(x: list[float], y: list[float]) -> float:
    """
    Cliff's delta: P(X>Y) - P(X<Y) over all pairs (ties count 0).
    Ordinal effect size for one chapter vs. the rest of the house style.
    """
    if not x or not y:
        return 0.0
    wins = losses = 0
    for a in x:
        for b in y:
            if a > b:
                wins += 1
            elif a < b:
                losses += 1
    n = len(x) * len(y)
    return (wins - losses) / n if n else 0.0


def vargha_delaney_a(x: list[float], y: list[float]) -> float:
    """Vargha-Delaney A = P(X>Y) + 0.5·P(X=Y) = (δ + 1) / 2."""
    if not x or not y:
        return 0.5
    wins = ties = 0
    for a in x:
        for b in y:
            if a > b:
                wins += 1
            elif a == b:
                ties += 1
    n = len(x) * len(y)
    return (wins + 0.5 * ties) / n if n else 0.5


def effect_label(delta: float) -> str:
    """Romano et al. (2006) bands for |Cliff's delta|."""
    a = abs(delta)
    if a < 0.147:
        return "negligible"
    if a < 0.33:
        return "small"
    if a < 0.474:
        return "medium"
    return "large"


def lag1_autocorrelation(values: list[float]) -> float | None:
    """Lag-1 Pearson autocorrelation; None when n < 3 or zero variance."""
    n = len(values)
    if n < 3:
        return None
    mean = sum(values) / n
    denom = sum((v - mean) ** 2 for v in values)
    if denom == 0.0:
        return None
    num = sum((values[i] - mean) * (values[i + 1] - mean) for i in range(n - 1))
    return num / denom


def runs_above_median_z(values: list[float]) -> float | None:
    """
    Wald-Wolfowitz runs z for above/below-median signs (ties to the right).
    None when n < 8 or one side is empty (no power).
    """
    n = len(values)
    if n < 8:
        return None
    med = median(values)
    signs = [1 if v >= med else -1 for v in values]
    n_pos = sum(1 for s in signs if s > 0)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    runs = 1 + sum(1 for i in range(n - 1) if signs[i] != signs[i + 1])
    mu = (2.0 * n_pos * n_neg) / n + 1.0
    var = (2.0 * n_pos * n_neg * (2.0 * n_pos * n_neg - n)) / (n * n * (n - 1.0))
    if var <= 0.0:
        return None
    return (runs - mu) / math.sqrt(var)


def spearman_rho(x: list[float], y: list[float]) -> float:
    """Spearman rank correlation of two paired samples (average ranks on ties)."""
    n = len(x)
    if n < 3:
        return 0.0

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: (values[i], i))
        result = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                result[order[k]] = avg
            i = j + 1
        return result

    rx = ranks(x)
    ry = ranks(y)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return cov / (vx * vy)


def jacobi_eigh(
    matrix: list[list[float]], tol: float = 1e-12, max_sweeps: int = 200
) -> tuple[list[float], list[list[float]]]:
    """
    Eigenvalues and eigenvectors of a symmetric matrix via cyclic Jacobi
    rotations (pure stdlib, deterministic). Returns (eigenvalues, eigenvectors)
    where ``eigenvectors[i]`` is the unit eigenvector belonging to
    ``eigenvalues[i]``; pairs are sorted by eigenvalue descending.
    """
    n = len(matrix)
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(i + 1, n))
        if off <= tol * tol:
            break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(a[p][q]) <= 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = math.copysign(1.0, theta) / (abs(theta) + math.sqrt(theta**2 + 1.0))
                c = 1.0 / math.sqrt(t**2 + 1.0)
                s = t * c
                app = c * c * a[p][p] - 2.0 * s * c * a[p][q] + s * s * a[q][q]
                aqq = s * s * a[p][p] + 2.0 * s * c * a[p][q] + c * c * a[q][q]
                a[p][q] = a[q][p] = 0.0
                a[p][p] = app
                a[q][q] = aqq
                for k in range(n):
                    if k in (p, q):
                        continue
                    akp = a[k][p]
                    akq = a[k][q]
                    a[k][p] = a[p][k] = c * akp - s * akq
                    a[k][q] = a[q][k] = s * akp + c * akq
                for k in range(n):
                    vkp = v[k][p]
                    vkq = v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    eigen = [(a[i][i], [v[j][i] for j in range(n)]) for i in range(n)]
    eigen.sort(key=lambda pair: pair[0], reverse=True)
    return [e for e, _ in eigen], [vec for _, vec in eigen]


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


PASSPORT_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "style_passport": "STYLE REFERENCE",
        "house_style": "self-calibrated house style",
        "chapter": "chapter",
        "chapters": "chapters",
        "median": "median",
        "band": "band",
        "constant": "constant",
        "consistency": "Consistency",
        "cells_in_band": "of cells within the band",
        "multiplicity": "Multiplicity",
        "expected_hits": "statistically expected hits",
        "fdr_confirmed": "FDR-confirmed",
        "cells": "cells",
        "exchangeability": "Exchangeability",
        "mean_acf": "mean lag-1",
        "low_power": "low power (n < 8)",
        "dimension": "Dimension",
        "variance": "variance",
        "flagged": "flagged",
        "redundant": "Redundant features",
    },
    "de": {
        "style_passport": "STILREFERENZ",
        "house_style": "selbstkalibrierter Hausstil",
        "chapter": "Kapitel",
        "chapters": "Kapitel",
        "median": "Median",
        "band": "Korridor",
        "constant": "konstant",
        "consistency": "Konsistenz",
        "cells_in_band": "der Zellen im Korridor",
        "multiplicity": "Multiplizität",
        "expected_hits": "statistisch erwartete Zufallstreffer",
        "fdr_confirmed": "FDR-bestätigt",
        "cells": "Zellen",
        "exchangeability": "Austauschbarkeit",
        "mean_acf": "mittlere Verzögerung-1",
        "low_power": "geringe Kraft (n < 8)",
        "dimension": "Dimension",
        "variance": "Varianz",
        "flagged": "auffällig",
        "redundant": "Redundante Merkmale",
    },
}


@dataclass
class StyleFingerprint:
    """
    Self-calibrated style fingerprint of a corpus.

    - values:       feature -> {chapter_num: value} (None = not measurable)
    - baseline:     feature -> {"median", "mad", "sigma", "n"}
    - z_scores:     chapter -> {feature: z*}  (significance-adjusted)
    - effect_sizes: chapter -> {feature: z}   (deviation in house-style sigma)
    - deviations:   chapter -> {feature: z*}  (only |z*| >= z_mild)
    - fdr_flagged:  chapter -> [feature]      (Benjamini-Hochberg set, q=0.05)
    - consistency:  share of measurable cells inside the band [0, 1]
    - dimensions:   self-calibrated principal style dimensions (loadings/scores)
    - redundant_features: feature pairs with |Spearman rho| >= 0.8
    """

    values: dict[str, dict[int, float | None]] = field(default_factory=dict)
    baseline: dict[str, dict[str, float | int]] = field(default_factory=dict)
    z_scores: dict[int, dict[str, float]] = field(default_factory=dict)
    effect_sizes: dict[int, dict[str, float]] = field(default_factory=dict)
    cliffs_delta: dict[int, dict[str, float]] = field(default_factory=dict)
    deviations: dict[int, dict[str, float]] = field(default_factory=dict)
    fdr_flagged: dict[int, list[str]] = field(default_factory=dict)
    expected_false_positives: float = 0.0
    consistency: float = 1.0
    n_chapters: int = 0
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    redundant_features: list[dict[str, Any]] = field(default_factory=list)
    baseline_diagnostics: dict[str, Any] = field(default_factory=dict)
    thresholds: FingerprintThresholds = field(default_factory=FingerprintThresholds)

    @classmethod
    def from_metrics(
        cls, metrics: Any, thresholds: FingerprintThresholds | None = None
    ) -> "StyleFingerprint":
        """Derives the fingerprint from a CorpusMetrics object (self-calibration)."""
        thresholds = thresholds or FingerprintThresholds()
        chapters = getattr(metrics, "chapters", []) or []
        values: dict[str, dict[int, float | None]] = {}
        ses: dict[str, dict[int, float]] = {}
        for field_name, _label, _unit in FEATURES:
            col: dict[int, float | None] = {}
            se_col: dict[int, float] = {}
            for chapter in chapters:
                raw = getattr(chapter, field_name, None)
                col[chapter.num] = float(raw) if isinstance(raw, int | float) else None
                se_raw = getattr(chapter, "style_se", {}).get(field_name)
                se_col[chapter.num] = float(se_raw) if isinstance(se_raw, int | float) else 0.0
            values[field_name] = col
            ses[field_name] = se_col

        baseline: dict[str, dict[str, float | int]] = {}
        z_scores: dict[int, dict[str, float]] = {c.num: {} for c in chapters}
        effect_sizes: dict[int, dict[str, float]] = {c.num: {} for c in chapters}
        cliffs: dict[int, dict[str, float]] = {c.num: {} for c in chapters}
        measured_cells = 0
        in_band = 0
        p_cells: list[tuple[int, str, float]] = []
        for field_name, _label, _unit in FEATURES:
            obs = [v for v in values[field_name].values() if v is not None]
            if len(obs) < thresholds.min_chapters:
                baseline[field_name] = {"median": 0.0, "mad": 0.0, "sigma": 0.0, "n": len(obs)}
                continue
            centre = median(obs)
            spread = mad(obs, centre)
            sigma = 1.4826 * spread
            baseline[field_name] = {
                "median": centre,
                "mad": spread,
                "sigma": sigma,
                "n": len(obs),
            }
            for chapter in chapters:
                value = values[field_name].get(chapter.num)
                if value is None:
                    continue
                others = [
                    v for ch, v in values[field_name].items() if ch != chapter.num and v is not None
                ]
                z_raw = robust_z(value, centre, spread)
                z_sig = significance_z(value, centre, sigma, ses[field_name][chapter.num])
                z_scores[chapter.num][field_name] = z_sig
                effect_sizes[chapter.num][field_name] = z_raw
                cliffs[chapter.num][field_name] = cliff_delta([value], others)
                measured_cells += 1
                if abs(z_sig) < thresholds.z_mild:
                    in_band += 1
                p_cells.append((chapter.num, field_name, normal_tail_probability(z_sig)))

        deviations: dict[int, dict[str, float]] = {}
        for chapter in chapters:
            flagged = {
                feat: z
                for feat, z in z_scores.get(chapter.num, {}).items()
                if abs(z) >= thresholds.z_mild
            }
            if flagged:
                deviations[chapter.num] = flagged

        fdr_cells = fdr_rejects(p_cells, q=thresholds.fdr_q, method=thresholds.fdr_method)
        fdr_flagged: dict[int, list[str]] = {}
        for chapter_num, field_name in fdr_cells:
            fdr_flagged.setdefault(chapter_num, []).append(field_name)

        expected_fp = (
            measured_cells * normal_tail_probability(thresholds.z_mild) if measured_cells else 0.0
        )
        consistency = (in_band / measured_cells) if measured_cells else 1.0
        fingerprint = cls(
            values=values,
            baseline=baseline,
            z_scores=z_scores,
            effect_sizes=effect_sizes,
            cliffs_delta=cliffs,
            deviations=deviations,
            fdr_flagged=fdr_flagged,
            expected_false_positives=expected_fp,
            consistency=consistency,
            n_chapters=len(chapters),
            thresholds=thresholds,
        )
        fingerprint.dimensions = fingerprint._derive_dimensions()
        fingerprint.redundant_features = fingerprint._derive_redundancies()
        fingerprint.baseline_diagnostics = fingerprint._derive_baseline_diagnostics()
        return fingerprint

    def _derive_baseline_diagnostics(self) -> dict[str, Any]:
        """
        Exchangeability diagnostics: are chapters i.i.d. draws from one house
        style? Runs z (above/below median) and lag-1 autocorrelation per usable
        feature; low power when n < 8 (documented).
        """
        fields = self._usable_features()
        n = self.n_chapters
        runs_flagged: list[str] = []
        acf_values: list[float] = []
        for field_name in fields:
            series: list[float] = []
            for ch in sorted(self.values[field_name]):
                value = self.values[field_name].get(ch)
                if value is not None:
                    series.append(float(value))
            rz = runs_above_median_z(series)
            rho1 = lag1_autocorrelation(series)
            if rz is not None and abs(rz) >= 1.96:
                runs_flagged.append(field_name)
            if rho1 is not None:
                acf_values.append(rho1)
        mean_rho1 = sum(acf_values) / len(acf_values) if acf_values else 0.0
        acf_critical = 1.0 / math.sqrt(n) if n >= 3 else 1.0
        exchangeable = not runs_flagged and abs(mean_rho1) < acf_critical
        return {
            "n_chapters": n,
            "low_power": n < 8,
            "runs_flagged": sorted(runs_flagged),
            "mean_lag1_rho": round(mean_rho1, 4),
            "acf_critical": round(acf_critical, 4),
            "exchangeable": exchangeable,
        }

    def _usable_features(self) -> list[str]:
        return [
            field
            for field, _label, _unit in FEATURES
            if self.baseline.get(field, {}).get("n", 0) >= 2
            and float(self.baseline.get(field, {}).get("sigma", 0.0)) > 0.0
        ]

    def _correlation_matrix(self, fields: list[str]) -> list[list[float]]:
        """Spearman correlation matrix over the chapter values of the features."""
        n = len(fields)
        matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                common = [
                    ch
                    for ch in self.values[fields[i]]
                    if ch in self.values[fields[j]]
                    and self.values[fields[i]].get(ch) is not None
                    and self.values[fields[j]].get(ch) is not None
                ]
                rho = 0.0
                if len(common) >= 3:
                    xs = [v for ch in common if (v := self.values[fields[i]][ch]) is not None]
                    ys = [v for ch in common if (v := self.values[fields[j]][ch]) is not None]
                    rho = spearman_rho(xs, ys)
                matrix[i][j] = matrix[j][i] = rho
        return matrix

    def _derive_dimensions(self) -> list[dict[str, Any]]:
        """
        Principal style dimensions of the author's own text: eigendecomposition
        of the Spearman correlation matrix of the usable features (cyclic
        Jacobi rotations, deterministic sign convention).
        """
        fields = self._usable_features()
        if len(fields) < 3:
            return []
        matrix = self._correlation_matrix(fields)
        eigenvalues, eigenvectors = jacobi_eigh(matrix)
        dims: list[dict[str, Any]] = []
        for dim_index in range(min(N_DIMENSIONS, len(fields))):
            loading_vector = eigenvectors[dim_index]
            # Deterministic sign: the largest absolute loading points upward.
            anchor = max(range(len(loading_vector)), key=lambda k: abs(loading_vector[k]))
            if loading_vector[anchor] < 0.0:
                loading_vector = [-v for v in loading_vector]
            loadings = {fields[k]: round(loading_vector[k], 3) for k in range(len(fields))}
            scores: dict[int, float] = {}
            flagged: list[int] = []
            for chapter_num in sorted(self.z_scores):
                score = 0.0
                for k, field_name in enumerate(fields):
                    value = self.values[field_name].get(chapter_num)
                    if value is None:
                        continue  # mean imputation: z = 0 contribution
                    centre = float(self.baseline[field_name]["median"])
                    sigma = float(self.baseline[field_name]["sigma"])
                    z = (value - centre) / sigma
                    score += loading_vector[k] * z
                    scores[chapter_num] = round(score, 2)
                    if abs(score) >= self.thresholds.dim_score_threshold:
                        flagged.append(chapter_num)
            dims.append(
                {
                    "index": dim_index + 1,
                    "variance": round(eigenvalues[dim_index] / len(fields), 4),
                    "loadings": loadings,
                    "scores": scores,
                    "flagged": flagged,
                }
            )
        return dims

    def _derive_redundancies(self) -> list[dict[str, Any]]:
        """Feature pairs that measure (almost) the same thing: |rho| >= 0.8."""
        fields = self._usable_features()
        pairs: list[dict[str, Any]] = []
        for i in range(len(fields)):
            for j in range(i + 1, len(fields)):
                common = [
                    ch
                    for ch in self.values[fields[i]]
                    if ch in self.values[fields[j]]
                    and self.values[fields[i]][ch] is not None
                    and self.values[fields[j]][ch] is not None
                ]
                if len(common) < 3:
                    continue
                xs = [v for ch in common if (v := self.values[fields[i]][ch]) is not None]
                ys = [v for ch in common if (v := self.values[fields[j]][ch]) is not None]
                rho = spearman_rho(xs, ys)
                if abs(rho) >= REDUNDANCY_RHO:
                    pairs.append({"a": fields[i], "b": fields[j], "rho": round(rho, 3)})
        pairs.sort(key=lambda p: abs(float(p["rho"])), reverse=True)
        return pairs[:10]

    def top_deviants(self, n: int = 3) -> list[tuple[int, float]]:
        """Chapters with the highest mean absolute significance-adjusted z."""
        scored = []
        for chapter_num, cells in self.z_scores.items():
            if not cells:
                continue
            mean_abs = sum(abs(z) for z in cells.values()) / len(cells)
            scored.append((chapter_num, mean_abs))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:n]

    def passport(self) -> dict[str, Any]:
        """Structured style passport (JSON-serialisable constraint data)."""
        features = []
        for field_name, _label, unit in FEATURES:
            base = self.baseline.get(field_name, {})
            sigma = float(base.get("sigma", 0.0))
            centre = float(base.get("median", 0.0))
            features.append(
                {
                    "feature": field_name,
                    "unit": unit,
                    "median": round(centre, 4),
                    "sigma": round(sigma, 4),
                    "band": [round(centre - 2 * sigma, 4), round(centre + 2 * sigma, 4)],
                    "chapters_measured": int(base.get("n", 0)),
                }
            )
        # Cliff's δ / Vargha-Delaney A for FDR-confirmed cells (magnitude).
        effect_magnitudes: dict[str, dict[str, str]] = {}
        for chapter_num, fields in self.fdr_flagged.items():
            row: dict[str, str] = {}
            for field_name in fields:
                d = self.cliffs_delta.get(chapter_num, {}).get(field_name, 0.0)
                row[field_name] = effect_label(d)
            if row:
                effect_magnitudes[str(chapter_num)] = row
        return {
            "meta": {
                "tool": "lixity",
                "schema_version": 2,
                "n_chapters": self.n_chapters,
                "n_features": len(FEATURES),
                "z_mild": self.thresholds.z_mild,
                "z_strong": self.thresholds.z_strong,
                "fdr_q": self.thresholds.fdr_q,
                "fdr_method": self.thresholds.fdr_method,
                "dim_score_threshold": self.thresholds.dim_score_threshold,
                "expected_false_positives": round(self.expected_false_positives, 2),
            },
            "consistency": round(self.consistency, 4),
            "baseline_diagnostics": self.baseline_diagnostics,
            "features": features,
            "deviations": {
                str(chapter_num): {feat: round(z, 2) for feat, z in dev.items()}
                for chapter_num, dev in sorted(self.deviations.items())
            },
            "fdr_flagged": {
                str(chapter_num): fields for chapter_num, fields in sorted(self.fdr_flagged.items())
            },
            "effect_magnitudes": effect_magnitudes,
            "dimensions": self.dimensions,
            "redundant_features": self.redundant_features,
        }

    def passport_text(
        self, labels: Mapping[str, str] | None = None, language_key: str = "en"
    ) -> str:
        """Human-readable style reference (constraint block for author or LLM)."""
        labels = labels or {}
        pack = PASSPORT_TEXTS.get(language_key, PASSPORT_TEXTS["en"])

        def t(key: str, default: str = "") -> str:
            if labels and key in labels:
                return labels[key]
            return pack.get(key, default or key)

        lines = [
            f"{t('style_passport')} – "
            f"{t('house_style')} "
            f"({self.n_chapters} {t('chapters' if self.n_chapters != 1 else 'chapter')})",
            "=" * 72,
        ]
        for field_name, label_key, unit_default in FEATURES:
            unit = (
                FEATURE_UNITS_DE.get(field_name, unit_default)
                if language_key == "de"
                else unit_default
            )
            base = self.baseline.get(field_name, {})
            if not base.get("n"):
                continue
            centre = float(base["median"])
            sigma = float(base["sigma"])
            label = labels.get(label_key, field_name)
            if sigma > 0.0:
                lines.append(
                    f"{label:<22} {t('median')} {format_num(centre, language_key, 2):>9}   "
                    f"{t('band')} "
                    f"{format_num(centre - 2 * sigma, language_key, 2):>8} – "
                    f"{format_num(centre + 2 * sigma, language_key, 2):>7}   [{unit}]"
                )
            else:
                lines.append(
                    f"{label:<22} {t('median')} {format_num(centre, language_key, 2):>9}   "
                    f"({t('constant')})   [{unit}]"
                )
        lines.append("=" * 72)
        lines.append(
            f"{t('consistency')}: {format_num(self.consistency * 100, language_key, 1)} % "
            f"{t('cells_in_band')} (z*)"
        )
        lines.append(
            f"{t('multiplicity')}: {format_num(self.expected_false_positives, language_key, 1)} "
            f"{t('expected_hits')} |z*| >= {format_num(self.thresholds.z_mild, language_key, 1)}; "
            f"{t('fdr_confirmed')} "
            f"({'BY' if self.thresholds.fdr_method.lower().startswith('by') else 'BH'} "
            f"q={format_num(self.thresholds.fdr_q, language_key, 2)}): "
            f"{sum(len(v) for v in self.fdr_flagged.values())} {t('cells')}"
        )
        if self.baseline_diagnostics:
            diag = self.baseline_diagnostics
            rho = format_num(float(diag.get("mean_lag1_rho", 0.0)), language_key, 2, signed=True)
            flag = "✓" if diag.get("exchangeable") else "!"
            lines.append(
                f"{t('exchangeability')}: {flag} "
                f"{t('mean_acf')} ρ₁={rho}"
                + (f" · {t('low_power')}" if diag.get("low_power") else "")
            )
        if self.dimensions:
            lines.append("-" * 72)
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            for dim in self.dimensions:
                loadings = dim["loadings"]
                top_pos = sorted(loadings.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_neg = sorted(loadings.items(), key=lambda kv: kv[1])[:3]
                pos_text = ", ".join(
                    f"+{labels.get(field_labels.get(f) or f, f)}" for f, _v in top_pos
                )
                neg_text = ", ".join(
                    f"{labels.get(field_labels.get(f) or f, f)}" for f, _v in top_neg
                )
                flagged = dim.get("flagged", [])
                lines.append(
                    f"{t('dimension')} {dim['index']} "
                    f"({format_num(dim['variance'] * 100, language_key, 0)} % {t('variance')}): "
                    f"{pos_text}  ⇅  {neg_text}"
                )
                if flagged:
                    lines.append(
                        f"    {t('flagged')}: {t('chapter')} {', '.join(map(str, flagged))}"
                    )
        if self.redundant_features:
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            redundant = ", ".join(
                f"{labels.get(field_labels.get(p['a']) or p['a'], p['a'])}↔"
                f"{labels.get(field_labels.get(p['b']) or p['b'], p['b'])} "
                f"({format_num(p['rho'], language_key, 2, signed=True)})"
                for p in self.redundant_features[:4]
            )
            lines.append(f"{t('redundant')} (|\u03c1| >= 0.8): {redundant}")
        lines.append("=" * 72)
        field_labels = {f: label_key for f, label_key, _u in FEATURES}
        for chapter_num, mean_abs in self.top_deviants(5):
            dev = self.deviations.get(chapter_num, {})
            named = ", ".join(
                f"{labels.get(field_labels.get(k, k), k)} {format_num(z, language_key, 1, signed=True)}σ"
                for k, z in sorted(dev.items(), key=lambda kv: abs(kv[1]), reverse=True)[:4]
            )
            lines.append(
                f"{t('chapter')} {chapter_num:>2}: Ø|z*| {format_num(mean_abs, language_key, 2)} – {named}"
            )
        return "\n".join(lines)


def layer_stats(paragraphs: Sequence[Any], layer: str) -> dict[int, tuple[float, float]]:
    """Per-paragraph layer values with their within-chapter robust z-score.

    Each chapter is its own reference (median/MAD), so the colour shows
    deviation *within* the chapter, not against the whole manuscript.
    Returns {paragraph_index: (value, robust z)}; empty for unknown layers
    or chapters with fewer than three measurable paragraphs.
    """
    field_name = LAYER_PARAGRAPH_ATTR.get(layer, LAYER_FEATURES.get(layer))
    if field_name is None:
        return {}
    by_chapter: dict[int, list[tuple[int, float]]] = {}
    for idx, p in enumerate(paragraphs):
        value = getattr(p, field_name, None)
        if not isinstance(value, int | float):
            continue
        by_chapter.setdefault(p.chapter_num, []).append((idx, float(value)))
    stats: dict[int, tuple[float, float]] = {}
    for pairs in by_chapter.values():
        if len(pairs) < 3:
            continue
        obs = [v for _, v in pairs]
        centre = median(obs)
        spread = mad(obs, centre)
        if spread == 0.0:
            continue
        for idx, value in pairs:
            stats[idx] = (value, robust_z(value, centre, spread))
    return stats
