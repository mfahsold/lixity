"""Ordered chapter diagnostics must not imply exchangeability or fill gaps."""

from itertools import pairwise
from types import SimpleNamespace

import pytest

from lixity.style_fingerprint import StyleFingerprint


def fingerprint(columns):
    chapters = sorted({chapter for values in columns.values() for chapter in values})
    return StyleFingerprint(
        n_chapters=len(chapters),
        values=columns,
    )


def test_empty_input_is_not_exchangeability_evidence():
    fp = StyleFingerprint.from_metrics(SimpleNamespace(chapters=[]))
    diagnostics = fp.passport()["baseline_diagnostics"]
    assert diagnostics["features"] == {}
    assert diagnostics["measured_features"] == 0
    assert "exchangeable" not in diagnostics
    assert "mean_lag1_rho" not in diagnostics
    assert "Exchangeability: ✓" not in fp.passport_text()


def test_opposite_autocorrelations_do_not_cancel():
    fp = fingerprint({
        "asl": dict(enumerate([0, 1, 0, 1, 0, 1, 0], 1)),
        "dialog_pct": dict(enumerate([0, 1, 2, 3, 4, 5, 6], 1)),
    })
    diag = fp._derive_baseline_diagnostics()
    assert set(diag["lag1_flagged"]) == {"asl", "dialog_pct"}
    assert diag["features"]["asl"]["lag1_rho"] < 0
    assert diag["features"]["dialog_pct"]["lag1_rho"] > 0
    assert diag["features"]["asl"]["lag1_critical"] == round(1 / 7**0.5, 4)


def test_missing_chapter_is_not_interpreted_as_adjacent():
    fp = fingerprint({"asl": {1: 0.0, 2: None, 3: 1.0, 4: 2.0},
                      "dialog_pct": {1: 0.0, 2: 1.0, 3: 2.0, 4: 3.0}})
    diag = fp._derive_baseline_diagnostics()
    assert diag["features"]["asl"]["missing_chapters"] == [2]
    assert diag["features"]["asl"]["lag1_rho"] is None
    assert diag["features"]["asl"]["runs_z"] is None
    assert diag["features"]["dialog_pct"]["lag1_rho"] is not None
    assert diag["features"]["dialog_pct"]["lag1_critical"] == 0.5


def test_constant_and_short_series_are_unavailable_not_zero():
    fp = fingerprint({"asl": {1: 5.0, 2: 5.0, 3: 5.0},
                      "dialog_pct": {1: 0.0, 2: 1.0, 3: None}})
    diag = fp._derive_baseline_diagnostics()
    assert diag["features"]["asl"]["lag1_rho"] is None
    assert diag["features"]["dialog_pct"]["lag1_rho"] is None
    assert diag["measured_features"] == 0


@pytest.mark.parametrize("size,missing_chapter", [
    (size, gap) for size in range(3, 10) for gap in range(size + 1)
])
def test_order_coverage_across_chapter_counts_and_gaps(size, missing_chapter):
    """Check real passport output against independently constructed coverage."""
    values = [float((number * number + 3 * number) % 11) for number in range(1, size + 1)]
    chapters = [
        SimpleNamespace(num=number, words=3 if number == missing_chapter else 100,
                        sentences=5, asl=value, style_se={})
        for number, value in enumerate(values, 1)
    ]
    diag = StyleFingerprint.from_metrics(SimpleNamespace(chapters=chapters)).passport()[
        "baseline_diagnostics"
    ]
    feature = diag["features"]["asl"]
    assert feature["observed_chapters"] == [n for n in range(1, size + 1) if n != missing_chapter]
    assert feature["missing_chapters"] == ([missing_chapter] if missing_chapter else [])
    if missing_chapter:
        assert feature["lag1_rho"] is None
        assert feature["runs_z"] is None
    else:
        mean = sum(values) / size
        centered = [value - mean for value in values]
        expected = sum(a * b for a, b in pairwise(centered)) / sum(
            value * value for value in centered
        )
        assert feature["lag1_rho"] == pytest.approx(round(expected, 4), abs=1e-4)
