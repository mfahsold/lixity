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
    """Deviation tested against house-style spread AND estimation noise."""
    denominator = math.hypot(sigma, se)
    if math.isinf(denominator) and math.isfinite(sigma) and math.isfinite(se):
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
    """Plug-in binomial standard error of a share in percentage points."""
    p = pct / 100.0
    return (math.sqrt(max(p * (1.0 - p), 0.0) / n) * 100.0) if n else 0.0


def poisson_se_per_mille(count: float, words: int) -> float:
    """Plug-in Poisson standard error of a count density (per 1,000 words)."""
    return (math.sqrt(count) * 1000.0 / words) if words else 0.0
