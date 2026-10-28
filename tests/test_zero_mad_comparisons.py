"""A zero MAD cannot support a standardized chapter comparison."""

import re
from types import SimpleNamespace

import pytest

from lixity.style_fingerprint import FingerprintThresholds, StyleFingerprint


def build(values, se):
    chapters = [SimpleNamespace(num=i + 1, words=100, sentences=5,
                                asl=value, style_se={"asl": se})
                for i, value in enumerate(values)]
    return StyleFingerprint.from_metrics(SimpleNamespace(chapters=chapters))


@pytest.mark.parametrize("values,status", [
    ([1, 1, 1, 10], "zero_mad_varying"),
    ([1, 1, 1, 1], "zero_mad_constant"),
])
@pytest.mark.parametrize("se", [0.0, 0.5])
def test_zero_mad_is_unavailable_even_with_positive_standard_error(values, status, se):
    fp = build(values, se)
    assert fp.baseline["asl"]["comparison_status"] == status
    assert fp.measured_cells == 0
    assert all("asl" not in row for row in fp.z_scores.values())
    assert all("asl" not in row for row in fp.effect_sizes.values())
    assert not fp.fdr_flagged and not fp.deviations
    passport = fp.passport()
    feature = next(row for row in passport["features"] if row["feature"] == "asl")
    assert feature["comparison_status"] == status
    assert feature["band"] is None
    assert passport["measured_cells"] == 0
    assert "–" in fp.passport_text()


def test_zero_mad_varying_keeps_ordinal_and_structural_information():
    fp = build([1, 1, 1, 10], 0)
    assert fp.cliffs_delta[4]["asl"] == 1.0
    assert fp.passport()["cliffs_delta"]["4"]["asl"] == 1.0
    assert "asl" in fp.structural_diagnostics["robust_scales"]
    assert "asl" in fp.baseline_diagnostics["features"]


def test_negative_zero_mad_preserves_signed_ordinal_contrast():
    fp = build([-10, -1, -1, -1], 0.5)
    assert fp.baseline["asl"]["comparison_status"] == "zero_mad_varying"
    assert fp.cliffs_delta[1]["asl"] == -1.0
    assert fp.measured_cells == 0


def test_heatmap_missing_chapter_value_does_not_claim_zero_mad_caused_it():
    from lixity.ui.heatmap import render_heatmap_panel

    chapters = [SimpleNamespace(num=i, title=f"Chapter {i}", words=100, sentences=5,
                                asl=1.0, style_se={}) for i in range(1, 4)]
    chapters.append(SimpleNamespace(num=4, title="Short", words=3, sentences=1,
                                    asl=1.0, style_se={}))
    metrics = SimpleNamespace(chapters=chapters)
    fingerprint = StyleFingerprint.from_metrics(metrics)
    assert fingerprint.baseline["asl"]["comparison_status"] == "zero_mad_constant"
    assert fingerprint.values["asl"][4] is None
    html = render_heatmap_panel(fingerprint, metrics, {
        "baseline_zero_mad": "Zero MAD comparison",
        "project_identity_unavailable": "Measurement unavailable",
    })
    def cell(number):
        return re.search(r'<td class="z" data-chapter="' + str(number)
                         + r'"[^>]*data-metric-feature="asl"[^>]*>', html)[0]
    assert "Zero MAD comparison" in cell(1)
    assert "Measurement unavailable" in cell(4)
    assert "Zero MAD comparison" not in cell(4)


def test_unavailable_baseline_never_exports_a_fabricated_median():
    fp = build([10], 0)
    feature = next(row for row in fp.passport()["features"] if row["feature"] == "asl")
    assert feature["comparison_status"] == "insufficient_chapters"
    assert feature["median"] is None
    assert feature["sigma"] is None
    assert feature["band"] is None


def test_structural_diagnostics_respect_configured_minimum_chapters():
    chapters = [SimpleNamespace(num=i + 1, words=100, sentences=5,
                                asl=value, style_se={"asl": 0.0})
                for i, value in enumerate([1, 2, 3])]
    fp = StyleFingerprint.from_metrics(SimpleNamespace(chapters=chapters),
                                       thresholds=FingerprintThresholds(min_chapters=4))
    assert fp.baseline["asl"]["comparison_status"] == "insufficient_chapters"
    assert "asl" not in fp.structural_diagnostics["trends"]
    assert "asl" not in fp.dimension_diagnostics["candidate_features"]
