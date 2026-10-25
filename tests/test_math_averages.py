"""Finite average/midpoint results survive overflowing intermediate sums."""

import math
import random
import statistics
import sys
from decimal import Decimal, localcontext

import pytest

from lixity.math_core import MAD_TO_SIGMA, mad, mean_or_zero, median, robust_scale


def decimal_mean(values):
    # Binary64's complete exponent span, including subnormal residuals, fits
    # comfortably within this precision before conversion back to binary64.
    with localcontext() as context:
        context.prec = 800
        return float(sum(map(Decimal.from_float, values), Decimal(0)) / len(values))


@pytest.mark.parametrize("values", [
    [1e308, 1e308],
    [-1e308, -1e308],
    [sys.float_info.max, sys.float_info.max],
    [-sys.float_info.max, -sys.float_info.max],
    [1e308, 1e308, -1e308],
    [1e308, 1e308, -1e308, -1e308],
    [1e308, 1e308, -1e308, -1e308, 1e200],
    [1e308, 1e308, -1e308, -1e308, 32 * math.ulp(0.0)],
])
def test_mean_retains_finite_results_and_cancellation_residuals(values):
    expected = decimal_mean(values)
    assert math.isfinite(expected)
    assert mean_or_zero(values) == expected


@pytest.mark.parametrize("values", [
    [1e308, 1e308],
    [-1e308, -1e308],
    [sys.float_info.max, sys.float_info.max],
    [-sys.float_info.max, -sys.float_info.max],
    [0.0, 9e307, 1.1e308, sys.float_info.max],
    [-sys.float_info.max, -1.1e308, -9e307, 0.0],
])
def test_even_median_midpoint_remains_inside_finite_observation_range(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    expected = decimal_mean(ordered[middle - 1:middle + 1])
    assert median(values) == expected
    assert min(values) <= median(values) <= max(values)


def test_mad_and_robust_scale_reuse_the_stable_midpoint():
    assert mad([-1e308, 1e308], 0.0) == 1e308
    assert robust_scale([-1e308, 1e308], 0.0) == MAD_TO_SIGMA * 1e308


def test_empty_and_nonfinite_conventions_remain_unchanged():
    assert mean_or_zero([]) == 0.0
    with pytest.raises(statistics.StatisticsError):
        median([])
    for values in ([math.inf, 1.0], [-math.inf, -1.0], [math.inf, -math.inf], [math.nan, 1.0],
                   [-math.inf, 1e308, 1e308, math.inf]):
        for operation, original in ((median, statistics.median), (mean_or_zero, lambda x: sum(x) / len(x))):
            expected = original(values)
            actual = operation(values)
            assert math.isnan(actual) if math.isnan(expected) else actual == expected


def test_finite_integer_inputs_do_not_need_a_float_conversion_for_validation():
    # A cancelled large Python integer must not make the overflow guard itself
    # raise while the final mathematical mean remains representable.
    huge = 10**400
    assert mean_or_zero([huge, -huge, 1e308, 1e308]) == 5e307
    assert median([huge]) == huge


def test_ordinary_paths_preserve_existing_rounding_and_signed_zero():
    rng = random.Random(20261025)
    cases = [[-0.0], [-0.0, -0.0], [math.ulp(0.0), 2 * math.ulp(0.0)]]
    cases += [[rng.uniform(-1e5, 1e5) for _ in range(size)] for size in range(1, 101)]
    for values in cases:
        assert mean_or_zero(values).hex() == (sum(values) / len(values)).hex()
        assert median(values).hex() == statistics.median(values).hex()
