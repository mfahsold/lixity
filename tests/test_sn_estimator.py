"""Exact Sn order statistics with bounded work and legacy direct-input behavior."""

import itertools
import json
import math
import struct
from types import SimpleNamespace

from lixity import style_fingerprint
from lixity.models import ChapterMetrics
from lixity.style_fingerprint import FEATURES, StyleFingerprint, sn_estimator


def exhaustive_sn(values):
    n = len(values)
    if n < 2:
        return 0.0
    inner = [sorted(abs(a - b) for b in values)[n // 2] for a in values]
    return 1.1926 * sorted(inner)[(n - 1) // 2]


def test_sn_matches_exhaustive_high_inner_low_outer_medians_exactly():
    choices = (-1e308, -1.0, -0.0, 0.0, 1.0, 1e308)
    for n in range(9):
        for sample in itertools.combinations_with_replacement(choices, n):
            values = list(sample)
            expected = exhaustive_sn(values)
            assert sn_estimator(values).hex() == expected.hex(), sample
            values.reverse()
            assert sn_estimator(values).hex() == expected.hex(), sample
    for sample in (
        [1e16, 1e16 + 2, 1e16 + 4, 1e16 + 8, 1e16 + 32],
        [math.nextafter(1e308, 0.0), 1e308, math.nextafter(1e308, math.inf), -1e308],
        [0.0, math.nextafter(0.0, 1.0), math.nextafter(0.0, -1.0), 1.0],
    ):
        assert sn_estimator(sample).hex() == exhaustive_sn(sample).hex()


def test_sn_preserves_nonfinite_and_large_integer_direct_inputs_without_mutation():
    choices = (math.nan, math.inf, -math.inf, 0.0, 1.0)
    for n in range(2, 5):
        for sample in itertools.product(choices, repeat=n):
            values = list(sample)
            before = [struct.pack("!d", value) for value in values]
            expected = exhaustive_sn(values)
            actual = sn_estimator(values)
            assert math.isnan(actual) if math.isnan(expected) else actual.hex() == expected.hex()
            assert [struct.pack("!d", value) for value in values] == before
    huge = 1 << 2048
    for values in ([huge, huge], [huge + 1, huge + 2, huge + 3]):
        before = values[:]
        assert sn_estimator(values).hex() == exhaustive_sn(values).hex()
        assert values == before


def test_sn_does_not_mutate_finite_values_or_signed_zero():
    values = [4.0, -0.0, 1.0, 0.0, -2.0]
    before = [struct.pack("!d", value) for value in values]
    assert sn_estimator(values).hex() == exhaustive_sn(values).hex()
    assert [struct.pack("!d", value) for value in values] == before
    assert sn_estimator([-0.0, 0.0]).hex() == "0x0.0p+0"


def test_sn_uses_subquadratic_distance_evaluations():
    class CountedFloat(float):
        differences = 0

        def __sub__(self, other):
            type(self).differences += 1
            return super().__sub__(other)

    n = 256
    values = [CountedFloat((i * 47) % 113) for i in range(n)]
    expected = exhaustive_sn([float(value) for value in values])
    assert sn_estimator(values).hex() == expected.hex()
    assert CountedFloat.differences < 8 * n * math.ceil(math.log2(n))


def test_sn_optimization_preserves_complete_style_passport(monkeypatch):
    chapters = []
    for i in range(15):
        chapter = ChapterMetrics(num=i + 1, title=f"Synthetic chapter {i + 1}",
                                 words=200 + i, sentences=8, asl=10.0, dialog_pct=0.0, ttr=0.5)
        for j, (name, _label, _unit) in enumerate(FEATURES):
            value = ((i * (j + 3) * 47) % 113) / 113.0 + 0.01
            setattr(chapter, name, value if name == "hd_d" else value * 50)
        chapter.style_se = {name: 0.1 for name, _label, _unit in FEATURES}
        chapters.append(chapter)
    chapters[-1].words = 99
    chapters[-2].sentences = 2
    metrics = SimpleNamespace(chapters=chapters)
    with monkeypatch.context() as context:
        context.setattr(style_fingerprint, "sn_estimator", exhaustive_sn)
        expected = StyleFingerprint.from_metrics(metrics)
    actual = StyleFingerprint.from_metrics(metrics)
    assert actual == expected
    assert json.dumps(actual.passport(), sort_keys=True) == json.dumps(expected.passport(), sort_keys=True)
