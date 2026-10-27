"""Independent high-precision regressions for finite statistical primitives."""

import math
from decimal import Decimal, localcontext
from itertools import pairwise

import pytest

from lixity.style_fingerprint import dunning_g2, lag1_autocorrelation


def decimal_lag1(values):
    """Direct NIST sample ACF definition, over the actual binary64 values."""
    with localcontext() as context:
        context.prec = 900
        sample = [Decimal.from_float(value) for value in values]
        centre = sum(sample) / len(sample)
        denominator = sum((value - centre) ** 2 for value in sample)
        if not denominator:
            return None
        return float(sum((a - centre) * (b - centre)
                         for a, b in pairwise(sample)) / denominator)


@pytest.mark.parametrize("scale", [1.0, -1.0, 1e200, -1e200, 1e-200, -1e-200,
                                  1e-160, -1e-160, math.ulp(0.0)])
def test_lag1_retains_correlation_when_finite_scale_changes(scale):
    sample = [scale, 2 * scale, 3 * scale, 4 * scale]
    assert lag1_autocorrelation(sample) == pytest.approx(decimal_lag1(sample), rel=1e-14)


@pytest.mark.parametrize("sample", [
    [-1e308, 1e308, -1e308, 1e308],
    [1e15 + step * math.ulp(1e15) for step in (0, 1, 3, 7)],
    [1e100 + step * math.ulp(1e100) for step in (0, 1, 3, 7)],
    [1e200 + step * math.ulp(1e200) for step in (0, 1, 3, 7)],
    [-1e-200 + step * math.ulp(1e-200) for step in (0, 1, 3, 7)],
])
def test_lag1_retains_representable_variation_at_finite_offsets(sample):
    assert lag1_autocorrelation(sample) == pytest.approx(decimal_lag1(sample), rel=1e-14)


@pytest.mark.parametrize("value", [0.0, 0.1, -0.3, 1.0, 1e308, -1e308, 1e-200])
@pytest.mark.parametrize("size", [3, 4, 7])
def test_lag1_constant_samples_stay_unavailable(value, size):
    assert lag1_autocorrelation([value] * size) is None


def decimal_g2(obs_a, obs_b, total_a, total_b):
    """Full four-cell likelihood ratio, with no centered/series shortcut."""
    with localcontext() as context:
        context.prec = 100
        a, b, na, nb = map(Decimal, (obs_a, obs_b, total_a, total_b))
        n = na + nb
        term = a + b
        cells = [(a, na * term / n), (b, nb * term / n),
                 (na - a, na * (n - term) / n), (nb - b, nb * (n - term) / n)]
        value = 2 * sum(observed * (observed / expected).ln()
                        for observed, expected in cells if observed)
        return float(-value if obs_a * total_b < obs_b * total_a else value)


@pytest.mark.parametrize("counts", [
    (100_000_001, 99_999_999, 200_000_000, 200_000_000),
    (1_000_001, 999_999, 2_000_000, 2_000_000),
    (10_000_000_001, 9_999_999_999, 20_000_000_000, 20_000_000_000),
    (10_001, 29_999, 20_000, 60_000),
    (110, 90, 200, 200),
    (111, 89, 200, 200),
    (12, 3, 20, 30),
    (50, 0, 50, 50),
    (5, 10, 10, 20),
])
def test_g2_preserves_near_null_divergence_and_direction(counts):
    a, b, na, nb = counts
    for arguments in (counts, (b, a, nb, na), (na - a, nb - b, na, nb)):
        assert dunning_g2(*arguments) == pytest.approx(decimal_g2(*arguments), rel=5e-14, abs=0.0)
