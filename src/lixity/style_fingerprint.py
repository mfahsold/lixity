"""lixity.style_fingerprint – Self-calibrating style passport and latent style dimensions.

Derives the manuscript's reference house style using robust statistics (median/MAD),
computes significance-adjusted deviations (z* with standard errors), controls false
discoveries (Benjamini-Hochberg FDR), extracts latent style dimensions via cyclic
Jacobi eigendecomposition, and provides structural diagnostics: changepoint segmentation
(PELT), monotonic trend tests (Mann-Kendall), distribution distances (Wasserstein/KS),
keyness (Dunning G²), tail behaviour (Hill estimator), robust scale estimators (Sn/Qn),
and degree-distribution fitness (Goh-Barabási).
"""

import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from .format import num as format_num
from .language import resolve_language
from .markdown_parser import split_chapters, strip_inline_markup
from .models import CorpusConfig
from .status import (
    PASSPORT_LABEL_SEGMENTED,
    PASSPORT_LABEL_SHIFTED,
    PASSPORT_LABEL_STRUCTURAL,
    PASSPORT_LABEL_TRENDING,
    SCHEMA_VERSION_STYLE,
    STRUCTURAL_DIAGNOSTICS_KEY,
    ContractKeys,
)

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

# Localised unit strings per language (FEATURES carries the English defaults).
# Keys are language codes matching resolve_language().key; missing keys fall
# back to the English unit in FEATURES.
FEATURE_UNITS: dict[str, dict[str, str]] = {
    "en": {
        "asl": "words per sentence",
        "staccato_pct": "% of sentences",
        "kaskade_pct": "% of sentences",
        "sentence_cv": "coefficient",
        "dialog_pct": "% of words",
        "function_word_pct": "% of words",
        "filter_density": "per 1,000 words",
        "modal_density": "per 1,000 words",
        "passive_density": "per 1,000 words",
        "nominalization_density": "per 1,000 words",
        "adjective_density": "per 1,000 words",
        "long_word_pct": "% of words",
        "start_entropy": "bit",
        "first_person_start_rate": "% of sentences",
        "guiraud_r": "index",
        "hd_d": "index",
    },
    "de": {
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
    },
    "fr": {
        "asl": "mots par phrase",
        "staccato_pct": "% des phrases",
        "kaskade_pct": "% des phrases",
        "sentence_cv": "coefficient",
        "dialog_pct": "% des mots",
        "function_word_pct": "% des mots",
        "filter_density": "pour 1 000 mots",
        "modal_density": "pour 1 000 mots",
        "passive_density": "pour 1 000 mots",
        "nominalization_density": "pour 1 000 mots",
        "adjective_density": "pour 1 000 mots",
        "long_word_pct": "% des mots",
        "start_entropy": "bit",
        "first_person_start_rate": "% des phrases",
        "guiraud_r": "indice",
        "hd_d": "indice",
    },
    "es": {
        "asl": "palabras por frase",
        "staccato_pct": "% de frases",
        "kaskade_pct": "% de frases",
        "sentence_cv": "coeficiente",
        "dialog_pct": "% de palabras",
        "function_word_pct": "% de palabras",
        "filter_density": "por 1.000 palabras",
        "modal_density": "por 1.000 palabras",
        "passive_density": "por 1.000 palabras",
        "nominalization_density": "por 1.000 palabras",
        "adjective_density": "por 1.000 palabras",
        "long_word_pct": "% de palabras",
        "start_entropy": "bit",
        "first_person_start_rate": "% de frases",
        "guiraud_r": "índice",
        "hd_d": "índice",
    },
    "it": {
        "asl": "parole per frase",
        "staccato_pct": "% delle frasi",
        "kaskade_pct": "% delle frasi",
        "sentence_cv": "coefficiente",
        "dialog_pct": "% delle parole",
        "function_word_pct": "% delle parole",
        "filter_density": "ogni 1.000 parole",
        "modal_density": "ogni 1.000 parole",
        "passive_density": "ogni 1.000 parole",
        "nominalization_density": "ogni 1.000 parole",
        "adjective_density": "ogni 1.000 parole",
        "long_word_pct": "% delle parole",
        "start_entropy": "bit",
        "first_person_start_rate": "% delle frasi",
        "guiraud_r": "indice",
        "hd_d": "indice",
    },
    "pt": {
        "asl": "palavras por frase",
        "staccato_pct": "% de frases",
        "kaskade_pct": "% de frases",
        "sentence_cv": "coeficiente",
        "dialog_pct": "% de palavras",
        "function_word_pct": "% de palavras",
        "filter_density": "por 1.000 palavras",
        "modal_density": "por 1.000 palavras",
        "passive_density": "por 1.000 palavras",
        "nominalization_density": "por 1.000 palavras",
        "adjective_density": "por 1.000 palavras",
        "long_word_pct": "% de palavras",
        "start_entropy": "bit",
        "first_person_start_rate": "% de frases",
        "guiraud_r": "índice",
        "hd_d": "índice",
    },
    "nl": {
        "asl": "woorden per zin",
        "staccato_pct": "% van zinnen",
        "kaskade_pct": "% van zinnen",
        "sentence_cv": "coëfficiënt",
        "dialog_pct": "% van woorden",
        "function_word_pct": "% van woorden",
        "filter_density": "per 1.000 woorden",
        "modal_density": "per 1.000 woorden",
        "passive_density": "per 1.000 woorden",
        "nominalization_density": "per 1.000 woorden",
        "adjective_density": "per 1.000 woorden",
        "long_word_pct": "% van woorden",
        "start_entropy": "bit",
        "first_person_start_rate": "% van zinnen",
        "guiraud_r": "index",
        "hd_d": "index",
    },
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

    def __post_init__(self) -> None:
        for name in ("z_mild", "z_strong", "fdr_q", "dim_score_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not 0 <= self.z_mild <= self.z_strong:
            raise ValueError("Deviation thresholds must satisfy 0 <= z_mild <= z_strong")
        if not 0 < self.fdr_q < 1 or self.fdr_method not in ("bh", "by"):
            raise ValueError("FDR requires 0 < fdr_q < 1 and method bh or by")
        if self.dim_score_threshold <= 0:
            raise ValueError("dim_score_threshold must be positive")
        if isinstance(self.min_chapters, bool) or not isinstance(self.min_chapters, int) or self.min_chapters < 2:
            raise ValueError("min_chapters must be an integer of at least 2")
        if isinstance(self.flag_min_severity, bool) or not isinstance(self.flag_min_severity, int) or self.flag_min_severity not in (1, 2, 3):
            raise ValueError("flag_min_severity must be 1, 2 or 3")


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


# ---------------------------------------------------------------------------
#  Structural statistical functions (pure stdlib, no numpy/scipy)
# ---------------------------------------------------------------------------


def _segment_cost(values: list[float], start: int, end: int) -> float:
    """Gaussian negative-log-likelihood cost of a segment (BIC-compatible).

    Cost = n·ln(variance) with variance = (1/n)·Σ(xi − x̄)². Returns 0.0 for
    segments of length ≤ 1 (no variance to measure).
    """
    n = end - start
    if n <= 1:
        return 0.0
    seg = values[start:end]
    mean = sum(seg) / n
    var = sum((x - mean) ** 2 for x in seg) / n
    if var <= 0.0:
        return 0.0
    return n * math.log(var)


def pelt_changepoints(values: list[float], penalty: float | None = None) -> list[int]:
    """PELT (Pruned Exact Linear Time) changepoint segmentation.

    Detects structural breaks (phase shifts) in a chapter-level metric series
    using a Gaussian cost model with BIC penalty.  Returns the 0-based indices
    of the *first element after* each changepoint, sorted ascending.

    Edge cases:
    - ``n < 3``  → ``[]``  (too short to split)
    - Constant series → ``[]``  (zero variance everywhere)
    - ``penalty=None`` → BIC default ``2·ln(n)``
    """
    n = len(values)
    if n < 3:
        return []

    if penalty is None:
        penalty = 2.0 * math.log(n)

    # opt[j] = minimum cost of segmenting values[0:j]
    opt = [0.0] * (n + 1)
    # last_cp[j] = the last changepoint index for opt[j]
    last_cp = [0] * (n + 1)
    # Candidate set (PELT pruning)
    candidates: list[int] = [0]

    for j in range(1, n + 1):
        best_cost = math.inf
        best_t = 0
        for t in candidates:
            cost = opt[t] + _segment_cost(values, t, j) + penalty
            if cost < best_cost:
                best_cost = cost
                best_t = t
        opt[j] = best_cost
        last_cp[j] = best_t
        # Prune: keep only candidates whose opt + cost ≤ opt[j]
        candidates = [t for t in candidates if opt[t] + _segment_cost(values, t, j) <= opt[j]]
        candidates.append(j)

    # Back-trace
    cps: list[int] = []
    idx = n
    while idx > 0:
        cp = last_cp[idx]
        if cp > 0:
            cps.append(cp)
        idx = cp
    cps.sort()
    return cps


def mann_kendall(
    values: list[float],
) -> tuple[float, float, float] | None:
    """Mann-Kendall monotonic trend test (non-parametric).

    Returns ``(tau, S, p_value)`` or ``None`` when ``n < 3``.

    - ``tau``: Kendall's tau-b (concordance – discordance, normalised)
    - ``S``:   the raw Mann-Kendall statistic
    - ``p_value``: two-sided normal approximation (tie-corrected variance)

    Edge cases:
    - ``n < 3``  → ``None``
    - Constant   → ``(0.0, 0.0, 1.0)``
    """
    n = len(values)
    if n < 3:
        return None

    s = 0.0
    for i in range(n - 1):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            if diff > 0.0:
                s += 1.0
            elif diff < 0.0:
                s -= 1.0

    # Tie groups
    tie_counts = Counter(values)
    tie_groups = [c for c in tie_counts.values() if c > 1]

    n0 = n * (n - 1) / 2.0
    tau = s / n0 if n0 > 0.0 else 0.0

    # Variance under H0 (tie-corrected)
    var_s = n * (n - 1.0) * (2.0 * n + 5.0) / 18.0
    for t in tie_groups:
        var_s -= t * (t - 1.0) * (2.0 * t + 5.0) / 18.0

    if var_s <= 0.0:
        return (0.0, 0.0, 1.0)

    # Continuity correction
    if s > 0:
        z = (s - 1.0) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1.0) / math.sqrt(var_s)
    else:
        z = 0.0

    p = math.erfc(abs(z) / math.sqrt(2.0))
    return (tau, s, p)


def wasserstein_1d(x: list[float], y: list[float]) -> float:
    """1-D Wasserstein (earth mover's) distance between two empirical distributions.

    Computed as the L¹ integral of the quantile functions: sort both samples,
    linearly interpolate to the same size, then sum absolute differences.
    Returns 0.0 when either sample is empty.
    """
    if not x or not y:
        return 0.0
    sx = sorted(x)
    sy = sorted(y)
    na, nb = len(sx), len(sy)
    # Merge-based exact computation (equivalent to the integral form)
    total = 0.0
    all_cdf_points = sorted(
        set([(i / na) for i in range(1, na + 1)] + [(j / nb) for j in range(1, nb + 1)])
    )
    prev_q = 0.0
    for q in all_cdf_points:
        ia = min(int(q * na), na - 1)
        ib = min(int(q * nb), nb - 1)
        total += abs(sx[ia] - sy[ib]) * (q - prev_q)
        prev_q = q
    return total


def ks_2sample(x: list[float], y: list[float]) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov test (approximate p via asymptotic formula).

    Returns ``(D, p_value)`` where D is the maximum absolute CDF difference.
    Returns ``(0.0, 1.0)`` when either sample is empty.
    """
    if not x or not y:
        return (0.0, 1.0)
    na, nb = len(x), len(y)
    combined = sorted(set(x) | set(y))
    sx = sorted(x)
    sy = sorted(y)

    d_max = 0.0
    for val in combined:
        # CDF of x at val
        cdf_x = sum(1 for v in sx if v <= val) / na
        cdf_y = sum(1 for v in sy if v <= val) / nb
        d_max = max(d_max, abs(cdf_x - cdf_y))

    # Asymptotic p-value (Kolmogorov distribution approximation)
    en = math.sqrt(na * nb / (na + nb))
    lam = (en + 0.12 + 0.11 / en) * d_max
    # Kolmogorov survival function (truncated series)
    p = 0.0
    if lam > 0.0:
        p = 2.0 * sum(
            ((-1.0) ** (k - 1)) * math.exp(-2.0 * k * k * lam * lam) for k in range(1, 101)
        )
    p = max(0.0, min(1.0, p))
    return (d_max, p)


def dunning_g2(obs_a: int, obs_b: int, total_a: int, total_b: int) -> float:
    """Dunning's G² (log-likelihood ratio) for keyness of a term.

    Compares observed frequency in sub-corpus A vs. sub-corpus B.
    Returns a signed G² value: positive = over-represented in A,
    negative = under-represented.  Returns 0.0 when totals are zero
    or the term is absent from both corpora.
    """
    if total_a <= 0 or total_b <= 0:
        return 0.0
    c = obs_a + obs_b
    if c == 0:
        return 0.0
    n = total_a + total_b
    e_a = total_a * c / n
    e_b = total_b * c / n

    g2 = 0.0
    if obs_a > 0 and e_a > 0.0:
        g2 += 2.0 * obs_a * math.log(obs_a / e_a)
    if obs_b > 0 and e_b > 0.0:
        g2 += 2.0 * obs_b * math.log(obs_b / e_b)

    # Sign: positive when A is over-represented
    if e_a > 0.0 and obs_a / e_a < 1.0:
        g2 = -g2
    return g2


def hill_estimator(values: list[float], k: int | None = None) -> float | None:
    """Hill estimator for the tail index (power-law exponent) alpha-hat.

    Uses the *k* largest observations.  ``k=None`` defaults to ``floor(sqrt(n))``.
    Returns ``None`` when fewer than 5 observations or ``k < 2``, or when
    the k-th order statistic is non-positive (log undefined).

    The Hill estimator is alpha = [1/k * sum ln(x_(n-i+1) / x_(n-k))]^-1
    where x_(.) are order statistics.
    """
    n = len(values)
    if n < 5:
        return None
    if k is None:
        k = max(2, int(math.sqrt(n)))
    if k < 2 or k >= n:
        return None

    sorted_vals = sorted(values)
    # x_{(n-k)} is the threshold
    threshold = sorted_vals[n - k - 1]
    if threshold <= 0.0:
        return None

    log_sum = 0.0
    for i in range(n - k, n):
        if sorted_vals[i] <= 0.0:
            return None
        log_sum += math.log(sorted_vals[i] / threshold)

    if log_sum <= 0.0:
        return None
    return k / log_sum


def goh_barabasi_fitness(degrees: list[int]) -> dict[str, float] | None:
    """Goh–Barabási degree-sequence fitness (discrete power-law / scale-free fit).

    Estimates the power-law exponent with the Goh–Barabási maximum-likelihood
    form ``alpha = 1 + n / sum ln(k_i / (k_min - 0.5))`` over positive degrees, then
    reports the Kolmogorov–Smirnov distance between the empirical and fitted
    CDFs (continuous approximation) with an asymptotic p-value.

    Returns ``{"exponent", "ks_distance", "p_value"}`` or ``None`` when the
    sequence is empty, shorter than 5, all-zero, or constant (no fit).

    Edge cases:
    - empty / only zeros → ``None``
    - ``n < 5`` → ``None``
    - all equal positive degrees → ``None`` (degenerate fit)
    """
    pos = [d for d in degrees if d > 0]
    n = len(pos)
    if n < 5:
        return None
    k_min = min(pos)
    k_max = max(pos)
    if k_min == k_max:
        return None

    denom = sum(math.log(k / (k_min - 0.5)) for k in pos)
    if denom <= 0.0:
        return None
    alpha = 1.0 + n / denom
    if alpha <= 1.0:
        return None

    sorted_pos = sorted(pos)
    # Continuous power-law CDF truncated to [k_min, k_max] for KS comparison.
    trunc = 1.0 - (k_max / k_min) ** (1.0 - alpha)

    def cdf_theory(k: float) -> float:
        if trunc <= 0.0:
            return 1.0
        value = (1.0 - (k / float(k_min)) ** (1.0 - alpha)) / trunc
        return float(max(0.0, min(1.0, value)))

    d_max = 0.0
    for i, k in enumerate(sorted_pos):
        theo = cdf_theory(float(k))
        d_max = max(d_max, abs((i + 1) / n - theo), abs(i / n - theo))

    en = math.sqrt(n)
    lam = (en + 0.12 + 0.11 / en) * d_max
    p = 0.0
    if lam > 0.0:
        p = 2.0 * sum(
            ((-1.0) ** (t - 1)) * math.exp(-2.0 * t * t * lam * lam) for t in range(1, 101)
        )
    p = max(0.0, min(1.0, p))
    return {
        "exponent": round(alpha, 4),
        "ks_distance": round(d_max, 4),
        "p_value": round(p, 4),
    }


def cooccurrence_degrees(tokens: Sequence[str], window: int = 2) -> list[int]:
    """Degree sequence of the undirected word co-occurrence graph.

    Nodes are token types; an undirected edge joins every pair within
    ``window`` positions (excluding self-loops). Returns one degree per
    distinct token (isolates included as 0); empty for empty input.
    """
    if not tokens or window < 1:
        return []
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for i, a in enumerate(tokens):
        nodes.add(a)
        for j in range(i + 1, min(i + 1 + window, len(tokens))):
            b = tokens[j]
            if a != b:
                edges.add((a, b) if a < b else (b, a))
    deg: dict[str, int] = dict.fromkeys(nodes, 0)
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    return list(deg.values())


def sn_estimator(values: list[float]) -> float:
    """Sn robust scale estimator (Rousseeuw & Croux 1993).

    Sn = cn · median_i { median_j |xi − xj| } where cn is a finite-sample
    correction factor.  Returns 0.0 for fewer than 2 observations.
    """
    n = len(values)
    if n < 2:
        return 0.0

    inner_medians: list[float] = []
    for i in range(n):
        diffs = sorted(abs(values[i] - values[j]) for j in range(n))
        inner_medians.append(statistics.median(diffs))

    raw = statistics.median(inner_medians)
    # Asymptotic consistency factor for Gaussian: 1.1926
    cn = 1.1926
    return cn * raw


def qn_estimator(values: list[float]) -> float:
    """Qn robust scale estimator (Rousseeuw & Croux 1993).

    Qn = dn · {|xi − xj|; i < j}_(h) where h = ⌊n/2⌋·(⌊n/2⌋+1)/2 ≈ first
    quartile of all pairwise distances.  Returns 0.0 for fewer than 2 observations.
    """
    n = len(values)
    if n < 2:
        return 0.0

    # All pairwise absolute differences
    diffs = sorted(abs(values[i] - values[j]) for i in range(n) for j in range(i + 1, n))

    # h = binomial(floor(n/2)+1, 2) ≈ first quartile index
    h_n = n // 2 + 1
    h = h_n * (h_n - 1) // 2
    h = max(1, min(h, len(diffs)))

    raw = diffs[h - 1]  # 1-based → 0-based
    # Asymptotic consistency factor for Gaussian: 2.2219
    dn = 2.2219
    return dn * raw


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


Z_COLOR_LIMIT = 2.5


def z_color(z: float) -> str:
    """
    Deterministic diverging colour scale for robust z-scores
    (blue = below house mean, grey = on mean, orange = above).
    Clamped to [-2.5, +2.5]; no external colour libraries.
    """
    stops = (
        (-Z_COLOR_LIMIT, (43, 108, 176)),
        (-1.0, (123, 167, 208)),
        (0.0, (229, 231, 235)),
        (1.0, (232, 176, 122)),
        (Z_COLOR_LIMIT, (192, 86, 33)),
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
        PASSPORT_LABEL_STRUCTURAL: "Structural diagnostics",
        PASSPORT_LABEL_SEGMENTED: "segmented features",
        PASSPORT_LABEL_TRENDING: "trending features",
        PASSPORT_LABEL_SHIFTED: "shifted features",
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
        PASSPORT_LABEL_STRUCTURAL: "Strukturelle Diagnostik",
        PASSPORT_LABEL_SEGMENTED: "segmentierte Merkmale",
        PASSPORT_LABEL_TRENDING: "trendende Merkmale",
        PASSPORT_LABEL_SHIFTED: "verschobene Merkmale",
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
    structural_diagnostics: dict[str, Any] = field(default_factory=dict)
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
        fingerprint.structural_diagnostics = fingerprint._derive_structural_diagnostics()
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

    def _derive_structural_diagnostics(self) -> dict[str, Any]:
        """Structural diagnostics per usable feature: changepoints, trends, robust scales.

        - **changepoints**: PELT changepoint indices (0-based) per feature
        - **trends**: Mann-Kendall (tau, S, p) per feature
        - **robust_scales**: Sn and Qn estimators per feature, compared to 1.4826·MAD
        - **tail_index**: Hill tail exponent (alpha-hat) per feature (n >= 5)
        - **distribution_shift**: Wasserstein-1D + two-sample KS, first half of
          chapters vs second half (n >= 4 with both halves >= 2)
        """
        fields = self._usable_features()
        changepoints: dict[str, list[int]] = {}
        trends: dict[str, dict[str, float]] = {}
        robust_scales: dict[str, dict[str, float]] = {}
        tail_index: dict[str, float] = {}
        distribution_shift: dict[str, dict[str, float]] = {}

        for field_name in fields:
            series: list[float] = []
            for ch in sorted(self.values[field_name]):
                value = self.values[field_name].get(ch)
                if value is not None:
                    series.append(float(value))

            if len(series) >= 3:
                cps = pelt_changepoints(series)
                if cps:
                    changepoints[field_name] = cps

                mk = mann_kendall(series)
                if mk is not None:
                    tau, s_val, p_val = mk
                    trends[field_name] = {
                        "tau": round(tau, 4),
                        "S": round(s_val, 1),
                        "p": round(p_val, 4),
                    }

            if len(series) >= 2:
                sn = sn_estimator(series)
                qn = qn_estimator(series)
                sigma_mad = float(self.baseline.get(field_name, {}).get("sigma", 0.0))
                robust_scales[field_name] = {
                    "sn": round(sn, 6),
                    "qn": round(qn, 6),
                    "sigma_mad": round(sigma_mad, 6),
                }

            if len(series) >= 5:
                alpha = hill_estimator(series)
                if alpha is not None:
                    tail_index[field_name] = round(alpha, 4)

            if len(series) >= 4:
                mid = len(series) // 2
                first, second = series[:mid], series[mid:]
                if len(first) >= 2 and len(second) >= 2:
                    w1 = wasserstein_1d(first, second)
                    ks_d, ks_p = ks_2sample(first, second)
                    distribution_shift[field_name] = {
                        "wasserstein": round(w1, 6),
                        "ks_d": round(ks_d, 4),
                        "ks_p": round(ks_p, 4),
                    }

        # Summary: features with significant trends (p < 0.05)
        trending = [f for f, t in trends.items() if t["p"] < 0.05]
        # Summary: features with changepoints
        segmented = list(changepoints.keys())
        # Summary: features whose early/late chapter halves differ (KS p < 0.05)
        shifted = [f for f, s in distribution_shift.items() if s["ks_p"] < 0.05]

        return {
            "changepoints": changepoints,
            "trends": trends,
            "robust_scales": robust_scales,
            "tail_index": tail_index,
            "distribution_shift": distribution_shift,
            "trending_features": sorted(trending),
            "segmented_features": sorted(segmented),
            "shifted_features": sorted(shifted),
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
                "schema_version": SCHEMA_VERSION_STYLE,
                "n_chapters": self.n_chapters,
                "n_features": len(FEATURES),
                "z_mild": self.thresholds.z_mild,
                "z_strong": self.thresholds.z_strong,
                "fdr_q": self.thresholds.fdr_q,
                "fdr_method": self.thresholds.fdr_method,
                "dim_score_threshold": self.thresholds.dim_score_threshold,
                "min_chapters": self.thresholds.min_chapters,
                "flag_min_severity": self.thresholds.flag_min_severity,
                "expected_false_positives": round(self.expected_false_positives, 2),
            },
            "consistency": round(self.consistency, 4),
            "baseline_diagnostics": self.baseline_diagnostics,
            STRUCTURAL_DIAGNOSTICS_KEY: self.structural_diagnostics,
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
            unit_pack = FEATURE_UNITS.get(language_key) or FEATURE_UNITS["en"]
            unit = unit_pack.get(field_name, unit_default)
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
        if self.structural_diagnostics:
            w2 = self.structural_diagnostics
            seg = w2.get(ContractKeys.SEGMENTED_FEATURES) or []
            trend = w2.get(ContractKeys.TRENDING_FEATURES) or []
            shift = w2.get(ContractKeys.SHIFTED_FEATURES) or []
            bits: list[str] = []
            if seg:
                bits.append(f"{len(seg)} {t(PASSPORT_LABEL_SEGMENTED)}")
            if trend:
                bits.append(f"{len(trend)} {t(PASSPORT_LABEL_TRENDING)}")
            if shift:
                bits.append(f"{len(shift)} {t(PASSPORT_LABEL_SHIFTED)}")
            if bits:
                lines.append(f"{t(PASSPORT_LABEL_STRUCTURAL)}: {' · '.join(bits)}")
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


def lexical_structural_diagnostics(
    text: str, config: CorpusConfig | None = None, *, window: int = 2, top_n: int = 10
) -> dict[str, Any]:
    """Token-level structural diagnostics: co-occurrence fitness and early/late keyness.

    Returns a JSON-safe fragment for ``structural_diagnostics``:

    - ``cooccurrence``: undirected content-word graph (sliding ``window``) with
      mean degree and Goh–Barabási degree-sequence fitness when estimable.
    - ``keyness``: Dunning $G^2$ of the first half of chapters vs the second
      half (content words only); ``early_over`` / ``late_over`` list the
      strongest over-represented words per half (deterministic order).

    Empty or too-short input yields ``{}``. Guards: co-occurrence needs at
    least 50 content tokens; keyness needs both halves with ≥ 20 tokens each.
    """
    import re

    config = config or CorpusConfig()
    resolved = resolve_language(config, sample_text=text)
    word_re = re.compile(resolved.word_regex)
    blacklist = resolved.function_words | resolved.stopwords
    chapters = split_chapters(text, config)
    if not chapters:
        return {}

    chapter_tokens: list[list[str]] = []
    for _num, _title, body in chapters:
        clean = strip_inline_markup(body)
        chapter_tokens.append([w.lower() for w in word_re.findall(clean)])

    n = len(chapter_tokens)
    all_tokens = [t for toks in chapter_tokens for t in toks]
    content_tokens = [t for t in all_tokens if len(t) > 1 and t not in blacklist]
    result: dict[str, Any] = {}

    if len(content_tokens) >= 50:
        degrees = cooccurrence_degrees(content_tokens, window=window)
        fitness = goh_barabasi_fitness(degrees)
        cooc: dict[str, Any] = {
            "window": window,
            "n_tokens": len(content_tokens),
            "n_types": len(set(content_tokens)),
            "mean_degree": round(sum(degrees) / len(degrees), 3) if degrees else 0.0,
        }
        if fitness is not None:
            cooc["fitness"] = fitness
        result[ContractKeys.COOCCURRENCE] = cooc

    mid = n // 2
    if mid >= 1 and n - mid >= 1:
        early = Counter(
            t for toks in chapter_tokens[:mid] for t in toks if len(t) > 1 and t not in blacklist
        )
        late = Counter(
            t for toks in chapter_tokens[mid:] for t in toks if len(t) > 1 and t not in blacklist
        )
        total_a = sum(early.values())
        total_b = sum(late.values())
        if total_a >= 20 and total_b >= 20:
            scored: list[tuple[str, float]] = []
            for word in sorted(set(early) | set(late)):
                g2 = dunning_g2(early[word], late[word], total_a, total_b)
                if g2 != 0.0:
                    scored.append((word, round(g2, 3)))
            scored.sort(key=lambda kv: (-abs(kv[1]), kv[0]))
            early_over = [{"word": w, "g2": g2} for w, g2 in scored if g2 > 0][:top_n]
            late_pairs = sorted(
                ((w, g2) for w, g2 in scored if g2 < 0),
                key=lambda kv: (kv[1], kv[0]),
            )[:top_n]
            late_over = [{"word": w, "g2": g2} for w, g2 in late_pairs]
            result[ContractKeys.KEYNESS] = {
                "split": "first_half_vs_second_half",
                "n_early_chapters": mid,
                "n_late_chapters": n - mid,
                "early_over": early_over,
                "late_over": late_over,
            }

    return result


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
