"""Independent high-precision regressions for finite statistical primitives."""

import math
from decimal import Decimal, localcontext
from itertools import pairwise

import pytest

from lixity.math_core import (
    adjusted_boxplot_fences,
    binomial_se_percent,
    huber_location,
    poisson_se_per_mille,
    ratio_or_zero,
    robust_z,
    significance_z,
)
from lixity.style_fingerprint import dunning_g2, lag1_autocorrelation


@pytest.mark.parametrize(("numerator", "denominator", "scale"), [
    (1e-308, 1e308, 1e308),
    (1.0, 1e-320, 1e-20),
    (math.ulp(0.0), 2.0, 4.0),
    (-math.nextafter(math.inf, 0.0), 0.5, 0.5),
    (1.0, 10**500, 1e308),
], ids=["underflow", "overflow", "subnormal", "float-max", "long-denominator"])
def test_scaled_ratio_retains_representable_result(numerator, denominator, scale):
    with localcontext() as context:
        context.prec = 100
        expected = Decimal(numerator) * Decimal(scale) / Decimal(denominator)
    assert ratio_or_zero(numerator, denominator, scale=scale) == float(expected)


@pytest.mark.parametrize(("pct", "count"), [
    (0.0, 10**163),
    (100.0, 10**16),
    (100.0, 10**308),
    (100.0, 10**324),
    (50.0, 10**500),
    (math.ulp(0.0), 100),
    (math.nextafter(100.0, 0.0), 100),
], ids=["lower-tail", "upper-tail", "float-limit", "subnormal-tail", "long-count", "tiny-share", "near-one"])
def test_jeffreys_standard_error_preserves_small_positive_tails(pct, count):
    with localcontext() as context:
        context.prec = 600
        probability = Decimal.from_float(pct) / 100
        if pct == 0.0:
            probability = Decimal("0.5") / (count + 1)
        elif pct == 100.0:
            probability = (Decimal(count) + Decimal("0.5")) / (count + 1)
        expected = (probability * (1 - probability) / count).sqrt() * 100
    assert binomial_se_percent(pct, count) == pytest.approx(float(expected), rel=2e-15, abs=0)


def test_poisson_standard_error_preserves_representable_density_with_long_denominator():
    words = 10**320
    with localcontext() as context:
        context.prec = 100
        expected = Decimal("0.5").sqrt() * 1000 / words
    assert poisson_se_per_mille(0, words) == pytest.approx(float(expected), rel=1e-15, abs=0)


def test_standardized_scores_preserve_ratios_at_subnormal_scales():
    unit = math.ulp(0.0)
    with localcontext() as context:
        context.prec = 100
        spacing = Decimal.from_float(unit)
        expected_significance = spacing / (spacing**2 + spacing**2).sqrt()
        expected_robust = spacing / (Decimal("1.4826") * spacing)
    assert significance_z(unit, 0.0, unit, unit) == pytest.approx(float(expected_significance), rel=1e-15)
    assert robust_z(unit, 0.0, unit) == pytest.approx(float(expected_robust), rel=1e-15)


@pytest.mark.parametrize("direction", [1, -1])
def test_adjusted_boxplot_retains_finite_fence_when_iqr_overflows(direction):
    sample = sorted(direction * value * 1e307 for value in (-17, -17, -15, -7, -1, 4, 5, 10, 11, 11, 14))
    with localcontext() as context:
        context.prec = 100
        values = list(map(Decimal.from_float, sample))
        centre = values[5]
        q1 = (values[2] + values[3]) / 2
        q3 = (values[7] + values[8]) / 2
        kernels = sorted(
            (high + low - 2 * centre) / (high - low) if high != low else Decimal(0)
            for low in values[:6] for high in values[5:]
        )
        skew = (kernels[17] + kernels[18]) / 2
        adjustment = Decimal("1.5") * (-4 * abs(skew)).exp() * (q3 - q1)
        expected = q3 + adjustment if direction == 1 else q1 - adjustment
    lower, upper = adjusted_boxplot_fences(sample)
    assert (upper if direction == 1 else lower) == pytest.approx(float(expected), rel=2e-15, abs=0)


@pytest.mark.parametrize("sample", [
    [1e308, 1.1e308, 1.2e308],
    [8e307, 9e307, 1e308, 1.15e308, 1.65e308],
    [-1e308, -1e308, 1.1e308, 1.7e308],
])
def test_huber_location_matches_clipped_score_root_at_finite_extremes(sample):
    from statistics import median

    with localcontext() as context:
        context.prec = 100
        values = list(map(Decimal.from_float, sample))
        centre = median(values)
        cutoff = Decimal("1.345") * Decimal("1.4826") * median(abs(value - centre) for value in values)
        lo, hi = min(values), max(values)
        # Solve the Huber score equation, independently of reweighting.
        for _ in range(120):
            trial = (lo + hi) / 2
            score = sum(max(-cutoff, min(cutoff, value - trial)) for value in values)
            if score > 0:
                lo = trial
            else:
                hi = trial
        expected = (lo + hi) / 2
    assert huber_location(sample, tol=1e-12, max_iter=200) == pytest.approx(float(expected), rel=2e-12, abs=0)


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
