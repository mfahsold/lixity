"""Mathematical vocabulary shared by every Lixity heuristic.

The module is the single source for the primitives that the analysis core,
the style profile and the structure reports reuse. Conventions in one place:

- A statistic is a partial function of its sample. ``None`` denotes "not
  defined for this sample"; where a public payload requires a number, an
  undefined statistic totalizes to ``0.0`` and that value means *unavailable*,
  never certainty (see ``docs/METHODS.md``).
- Ratios, shares and densities totalize to ``0.0`` on an empty denominator.
- Robust scale follows the normal-consistent MAD with
  ``MAD_TO_SIGMA = 1.4826`` (Rousseeuw & Croux 1993); robust z-scores use the
  inverse factor ``0.6745``.
- Two-sided normal p-values come from ``math.erfc`` (stdlib only, no SciPy).
- Cliff's delta bands follow Romano et al. (2006): 0.147 / 0.33 / 0.474.
- Standard errors of shares and counts use the plug-in binomial and Poisson
  estimators documented in ``docs/METHODS.md`` §2.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

#: Normal-consistent MAD factor (Rousseeuw & Croux 1993).
MAD_TO_SIGMA = 1.4826

#: Robust z-score factor: the inverse of :data:`MAD_TO_SIGMA` (0.6745...).
MAD_TO_SIGMA_INVERSE = 1.0 / MAD_TO_SIGMA

#: Gaussian consistency factor of the Sn estimator.
SN_TO_SIGMA = 1.1926

#: Gaussian consistency factor of the Qn estimator.
QN_TO_SIGMA = 2.21914

#: Romano et al. (2006) thresholds for |Cliff's delta|: negligible / small /
#: medium below the bands, large at or above the last one.
CLIFF_BANDS = (0.147, 0.33, 0.474)


def median(values: Sequence[float]) -> float:
    """Sample median; avoid an overflowing sum of two finite central values."""
    ordered = sorted(values)
    size = len(ordered)
    if not size:
        raise statistics.StatisticsError("no median for empty data")
    middle = size // 2
    if size % 2:
        return ordered[middle]
    left, right = ordered[middle - 1:middle + 1]
    result = (left + right) / 2
    if (isinstance(result, float) and not math.isfinite(result)
            and all(isinstance(value, int) or math.isfinite(value) for value in ordered)):
        return statistics.mean((left, right))
    return result


def mad(values: Sequence[float], centre: float) -> float:
    """Median absolute deviation; 0.0 for fewer than two observations."""
    if len(values) < 2:
        return 0.0
    return median([abs(value - centre) for value in values])


def robust_scale(values: Sequence[float], centre: float | None = None) -> float:
    """Normal-consistent robust scale ``sigma = 1.4826 * MAD``."""
    if centre is None:
        centre = median(values)
    return MAD_TO_SIGMA * mad(values, centre)


def _standardized_difference(
    value: float, centre: float, denominator: float, factor: float = 1.0,
) -> float:
    """Divide before subtraction only when finite operands overflow their difference."""
    difference = value - centre
    if math.isinf(difference) and math.isfinite(value) and math.isfinite(centre):
        return factor * value / denominator - factor * centre / denominator
    return factor * difference / denominator


def robust_z(value: float, centre: float, spread: float) -> float:
    """Robust z-score: 0.6745 scales MAD to normal-consistency sigma."""
    if spread == 0.0:
        return 0.0
    return _standardized_difference(value, centre, spread, MAD_TO_SIGMA_INVERSE)


def significance_z(value: float, centre: float, sigma: float, se: float) -> float:
    """Standardize against finite reference spread and estimation noise."""
    if not all(math.isfinite(x) for x in (value, centre, sigma, se)) or sigma < 0.0 or se < 0.0:
        raise ValueError("Scoring requires finite values and nonnegative finite spreads")
    denominator = math.hypot(sigma, se)
    if math.isinf(denominator):
        scale = max(abs(sigma), abs(se))
        return _standardized_difference(value, centre, scale) / math.hypot(sigma / scale, se / scale)
    return _standardized_difference(value, centre, denominator) if denominator > 0.0 else 0.0


def normal_two_sided_p(z: float) -> float:
    """Two-sided normal p-value via ``math.erfc`` (stdlib, no SciPy)."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def ratio_or_zero(numerator: float, denominator: float, *, scale: float = 1.0) -> float:
    """Totalize a ratio: ``numerator / denominator * scale``, 0.0 on zero divisor."""
    return (numerator / denominator * scale) if denominator else 0.0


def percent(part: float, whole: float) -> float:
    """Share in percentage points; 0.0 on a zero whole."""
    return ratio_or_zero(part, whole, scale=100.0)


def per_mille(matches: float, words: float) -> float:
    """Occurrences per 1,000 tokens (shared density convention)."""
    return ratio_or_zero(matches, words, scale=1000.0)


def mean_or_zero(values: Sequence[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sample (unavailable, not zero evidence)."""
    if not values:
        return 0.0
    total = sum(values)
    if (isinstance(total, float) and not math.isfinite(total)
            and all(isinstance(value, int) or math.isfinite(value) for value in values)):
        # Exact-ratio accumulation retains cancellation and subnormal residuals;
        # scaling every observation first could lose those contributions.
        return statistics.mean(values)
    return total / len(values)


def binomial_se_percent(pct: float, n: int) -> float:
    """Continuity-adjusted binomial standard error of a share in percentage points.

    Uses the Jeffreys continuity adjustment ``(count + 0.5) / (n + 1.0)`` when
    ``pct <= 0.0`` or ``pct >= 100.0`` (for ``n > 0``), preventing ``SE = 0.0``
    collapse on zero-hit or 100%-hit chapters.
    """
    if n <= 0:
        return 0.0
    p = pct / 100.0
    if p <= 0.0:
        p = 0.5 / (n + 1.0)
    elif p >= 1.0:
        p = (n + 0.5) / (n + 1.0)
    return math.sqrt(max(p * (1.0 - p), 0.0) / n) * 100.0


def poisson_se_per_mille(count: float, words: int) -> float:
    """Continuity-adjusted Poisson standard error of a count density (per 1,000 words).

    Uses ``count + 0.5`` when ``count == 0`` and ``words > 0`` to avoid
    ``SE = 0.0`` collapse on zero-hit chapters.
    """
    if words <= 0:
        return 0.0
    effective = 0.5 if count == 0 else max(count, 0.0)
    return math.sqrt(effective) * 1000.0 / words


#: Small-sample MAD consistency factors b_n (Croux & Rousseeuw 1992).
_MAD_FINITE_SAMPLE_FACTORS: dict[int, float] = {
    2: 1.196,
    3: 1.495,
    4: 1.363,
    5: 1.206,
    6: 1.200,
    7: 1.140,
    8: 1.129,
    9: 1.107,
}


def mad_finite_sample_factor(n: int) -> float:
    """Small-sample MAD bias-correction factor ``b_n`` (Croux & Rousseeuw 1992)."""
    if n < 2:
        return 1.0
    if n in _MAD_FINITE_SAMPLE_FACTORS:
        return _MAD_FINITE_SAMPLE_FACTORS[n]
    return n / (n - 0.8)


def split_mad(values: Sequence[float], centre: float | None = None) -> tuple[float, float]:
    """Asymmetric lower and upper normal-consistent MAD around the median.

    Returns ``(lower_sigma, upper_sigma)``; ``(0.0, 0.0)`` for fewer than two
    observations.
    """
    if len(values) < 2:
        return 0.0, 0.0
    med = median(values) if centre is None else centre
    lower_diffs = [med - value for value in values if value <= med]
    upper_diffs = [value - med for value in values if value >= med]
    lower = MAD_TO_SIGMA * median(lower_diffs) if lower_diffs else 0.0
    upper = MAD_TO_SIGMA * median(upper_diffs) if upper_diffs else 0.0
    return lower, upper


def medcouple(values: Sequence[float]) -> float:
    """Medcouple non-parametric skewness in ``[-1.0, 1.0]`` (Brys et al. 2004)."""
    n = len(values)
    if n < 3:
        return 0.0
    ordered = sorted(values)
    med = median(ordered)
    lower = [value for value in ordered if value <= med][::-1]
    upper = [value for value in ordered if value >= med]
    k = sum(1 for value in ordered if value == med)

    kernels: list[float] = []
    for i, x_i in enumerate(lower):
        for j, x_j in enumerate(upper):
            if x_i < x_j:
                left, right = med - x_i, x_j - med
                if math.isinf(left + right):
                    # Halve before subtracting when the distance overflows.
                    left, right = med * 0.5 - x_i * 0.5, x_j * 0.5 - med * 0.5
                kernels.append((right - left) / (right + left))
            else:
                # Tied at the median: symmetric tie-breaking kernel (Brys et al. 2004).
                diff = i + j - (k - 1)
                kernels.append(-1.0 if diff < 0 else (1.0 if diff > 0 else 0.0))
    mc = median(kernels)
    return max(-1.0, min(1.0, mc))


def _linear_quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile on a non-empty sorted sequence."""
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    frac = pos - lo
    return float(sorted_values[lo]) * (1.0 - frac) + float(sorted_values[hi]) * frac


def adjusted_boxplot_fences(values: Sequence[float]) -> tuple[float, float]:
    """Medcouple-adjusted boxplot outlier fences (Hubert & Vandervieren 2008)."""
    if not values:
        raise statistics.StatisticsError("no fences for empty data")
    if len(values) == 1:
        only = float(values[0])
        return only, only
    ordered = sorted(values)
    q1 = _linear_quantile(ordered, 0.25)
    q3 = _linear_quantile(ordered, 0.75)
    iqr = q3 - q1
    mc = medcouple(ordered)
    if mc >= 0.0:
        lower = q1 - 1.5 * math.exp(-4.0 * mc) * iqr
        upper = q3 + 1.5 * math.exp(3.0 * mc) * iqr
    else:
        lower = q1 - 1.5 * math.exp(-3.0 * mc) * iqr
        upper = q3 + 1.5 * math.exp(4.0 * mc) * iqr
    return lower, upper


def huber_location(
    values: Sequence[float],
    *,
    k: float = 1.345,
    tol: float = 1e-6,
    max_iter: int = 50,
) -> float:
    """IRLS Huber M-estimator of location with MAD scale."""
    if not values:
        raise statistics.StatisticsError("no huber_location for empty data")
    if len(values) == 1:
        return float(values[0])
    mu = float(median(values))
    scale = robust_scale(values, mu)
    if scale == 0.0:
        return mu
    for _ in range(max_iter):
        weighted_sum = 0.0
        weight_total = 0.0
        for value in values:
            r = abs(value - mu) / scale
            weight = 1.0 if r <= k else k / r
            weighted_sum += weight * value
            weight_total += weight
        if weight_total == 0.0:
            break
        mu_new = weighted_sum / weight_total
        if abs(mu_new - mu) <= tol * max(1.0, abs(mu)):
            mu = mu_new
            break
        mu = mu_new
    return mu
