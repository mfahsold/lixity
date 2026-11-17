"""Synthetic regressions for coordinate coherence and interpretation contracts."""

import math
from types import SimpleNamespace

import pytest

from lixity.language_data import LABELS, METRIC_LABELS
from lixity.models import CorpusConfig
from lixity.style_fingerprint import (
    MAD_TO_SIGMA,
    PARAGRAPH_LAYER_Z_CUTOFF,
    FingerprintThresholds,
    StyleFingerprint,
)
from lixity.ui.dimensions import style_dimensions
from lixity.ui.heatmap import render_style_passport_panel

FIELDS = ("asl", "staccato_pct", "kaskade_pct", "dialog_pct", "hd_d")


def metrics(values: list[float], *, se: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(chapters=[
        SimpleNamespace(num=i, title=f"Synthetic {i}", words=1000, sentences=100,
                        style_se=dict.fromkeys(FIELDS, se),
                        **dict.fromkeys(FIELDS, value))
        for i, value in enumerate(values, 1)
    ])


def test_production_mahalanobis_matches_independent_rank_space_solution() -> None:
    fp = StyleFingerprint.from_metrics(metrics([10.0, 12.0, 14.0, 30.0]))
    assert all(set(FIELDS) <= set(cells) for cells in fp.z_scores.values())
    # Five identical standardized rank columns: R = 11', eigenvalue p.
    # Ridge changes the leading eigenvalue to (1-lambda)*p + lambda.
    lam = fp.dimension_diagnostics["shrinkage_lambda"]
    # Diagnostics round lambda; the algorithm uses its full precision.
    assert lam == round(2 / 9, 4)
    leading = (1 - 2 / 9) * 5 + 2 / 9
    for chapter, rank_delta in enumerate([-1.5, -0.5, 0.5, 1.5], 1):
        rank = rank_delta / math.sqrt(5 / 3)
        expected = math.sqrt(5 * rank * rank / leading)
        assert fp.mahalanobis_distances[chapter] == pytest.approx(expected, abs=5e-5)
    assert fp.dimension_diagnostics["mahalanobis_space"] == "standardized_midranks"


@pytest.mark.parametrize("values", [[1.0, 1.0, 3.0, 7.0], [1.0, 2.0, 3.0, 9.0]])
def test_rank_distance_does_not_depend_on_optional_z_scores(values: list[float]) -> None:
    fp = StyleFingerprint.from_metrics(metrics(values))
    before = dict(fp.mahalanobis_distances)
    fp.z_scores = {}
    fp._derive_dimensions()
    assert fp.mahalanobis_distances == before
    fp.z_scores = {1: {"asl": 1e6}}  # Partial cells must not switch coordinates either.
    fp._derive_dimensions()
    assert fp.mahalanobis_distances == before


def test_rank_distance_omits_incomplete_chapters() -> None:
    data = metrics([1.0, 2.0, 3.0, 9.0])
    data.chapters[3].hd_d = None
    fp = StyleFingerprint.from_metrics(data)
    assert set(fp.mahalanobis_distances) == {1, 2, 3}


def test_noncollinear_rank_distance_matches_direct_linear_solve() -> None:
    columns = {"asl": [1., 2., 3., 4., 5., 20.],
               "dialog_pct": [4., 6., 2., 5., 3., 1.],
               "hd_d": [1., 3., 1., 2., 5., 4.]}
    data = SimpleNamespace(chapters=[
        SimpleNamespace(num=i + 1, words=1000, sentences=100, style_se={},
                        **{key: col[i] for key, col in columns.items()}) for i in range(6)
    ])
    fp = StyleFingerprint.from_metrics(data)
    assert fp.dimension_diagnostics["shrinkage_lambda"] == 0
    standardized = []
    for values in columns.values():
        ranks = [sum(other < value for other in values)
                 + (sum(other == value for other in values) + 1) / 2 for value in values]
        mean = sum(ranks) / 6
        sd = math.sqrt(sum((rank - mean) ** 2 for rank in ranks) / 5)
        standardized.append([(rank - mean) / sd for rank in ranks])
    covariance = [[sum(a * b for a, b in zip(x, y, strict=True)) / 5
                   for y in standardized] for x in standardized]
    for chapter, row in enumerate(zip(*standardized, strict=True), 1):
        # Independently solve C*y=row with pivoted elimination, not PCA/eigenvectors.
        augmented = [[*values, value] for values, value in zip(covariance, row, strict=True)]
        for col in range(3):
            pivot = max(range(col, 3), key=lambda index: abs(augmented[index][col]))
            augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
            factor = augmented[col][col]
            augmented[col] = [value / factor for value in augmented[col]]
            for index in range(3):
                if index != col:
                    factor = augmented[index][col]
                    augmented[index] = [a - factor * b for a, b in
                                        zip(augmented[index], augmented[col], strict=True)]
        expected = math.sqrt(sum(value * augmented[i][-1] for i, value in enumerate(row)))
        assert fp.mahalanobis_distances[chapter] == pytest.approx(expected, abs=5e-5)


def test_two_chapter_contract_reports_unreachable_flags_without_hiding_scores() -> None:
    fp = StyleFingerprint.from_metrics(metrics([10.0, 20.0], se=2.0))
    info = fp.interpretation()
    assert info["schema_version"] == "style-interpretation/1"
    assert info["normal_tail_calibration"] == "not_established"
    assert info["fdr_guarantee"] == "not_established"
    assert set(info["two_chapter_features"]) == set(FIELDS)
    assert set(info["unreachable_deviation_features"]) == set(FIELDS)
    assert info["two_chapter_abs_z_star_upper_bound"] == 1 / MAD_TO_SIGMA
    assert all(0 < abs(cells["asl"]) < 1 / MAD_TO_SIGMA for cells in fp.z_scores.values())
    assert not fp.deviations
    assert fp.passport()["meta"]["interpretation"] == info


def test_attainability_uses_each_features_support_and_configured_threshold() -> None:
    data = metrics([0.0, 1.0, 100.0])
    data.chapters[2].hd_d = None
    fp = StyleFingerprint.from_metrics(data)
    assert fp.interpretation()["unreachable_deviation_features"] == ["hd_d"]
    assert fp.z_scores[3]["asl"] > 60  # No invented n=3 MAD ceiling.
    fp = StyleFingerprint.from_metrics(data, FingerprintThresholds(z_mild=0.5))
    assert fp.interpretation()["two_chapter_features"] == ["hd_d"]
    assert not fp.interpretation()["unreachable_deviation_features"]


def test_unavailable_features_do_not_receive_attainability_claims() -> None:
    fp = StyleFingerprint.from_metrics(metrics([1.0, 1.0]))
    assert fp.interpretation()["two_chapter_features"] == []
    assert fp.measured_cells == 0
    assert fp.passport()["consistency"] == 1.0  # Preserve documented sentinel.


def test_float_midpoint_rounding_cannot_make_an_actual_flag_unreachable() -> None:
    data = metrics([1.0, math.nextafter(1.0, 2.0)])
    fp = StyleFingerprint.from_metrics(data, FingerprintThresholds(z_mild=1.0))
    assert fp.deviations  # Median rounds to one endpoint of this adjacent pair.
    info = fp.interpretation()
    assert not info["unreachable_deviation_features"]
    assert set(info["two_chapter_rounding_sensitive_features"]) == set(FIELDS)
    assert info["two_chapter_abs_z_star_upper_bounds"]["asl"] > 1.0
    assert "rounding_sensitive" in fp.interpretation_texts(language_key="en")
    warning = METRIC_LABELS["en"]["selection_pair_rounding"]
    assert warning in fp.passport_text(language_key="en")
    assert warning in render_style_passport_panel(fp, METRIC_LABELS["en"], "en")


def test_register_metadata_distinguishes_flag_eligibility_from_reference_population() -> None:
    data = metrics([1.0, 2.0, 100.0])
    plain = StyleFingerprint.from_metrics(data)
    registered = StyleFingerprint.from_metrics(data, config=CorpusConfig(
        chapter_registers={"3": "letter"}, register_profiles={"letter": {"asl": [1.0, 100.0]}},
    ))
    assert 3 in plain.deviations and 3 not in registered.deviations
    assert registered.z_scores == plain.z_scores
    assert registered.measured_cells == plain.measured_cells
    assert registered.interpretation()["register_excluded_chapters"] == [3]
    assert "register_exemptions" in registered.interpretation_texts(language_key="en")


def test_legend_contract_keeps_distinct_thresholds_and_reference_populations() -> None:
    fp = StyleFingerprint.from_metrics(metrics([1.0, 2.0, 3.0]),
                                       FingerprintThresholds(z_mild=3.0, fdr_method="by"))
    info = fp.interpretation()
    assert info["band"] == {"sigma_multiplier": 2.0, "includes_se": False}
    assert info["deviation"] == {"absolute_z_star_min": 3.0, "includes_se": True}
    assert info["fdr"]["method"] == "by"
    assert info["paragraph_layer"]["absolute_z_min"] == PARAGRAPH_LAYER_Z_CUTOFF
    assert info["paragraph_layer"]["reference_scope"] == "all_measurable_paragraphs_within_each_chapter"
    assert info["paragraph_layer"]["z_decimals"] == 2
    assert info["paragraph_layer"]["cutoff_applied_to"] == "rounded_z"


@pytest.mark.parametrize("language", ["de", "en", "fr", "es", "it", "pt", "nl"])
def test_reference_panel_explains_selection_and_two_chapter_limit(language: str) -> None:
    fp = StyleFingerprint.from_metrics(metrics([10.0, 20.0]))
    labels = {**LABELS[language], **METRIC_LABELS[language]}
    rendered = render_style_passport_panel(fp, labels, language)
    assert 'id="style-decision-legend"' in rendered
    assert 'id="style-small-sample"' in rendered
    assert METRIC_LABELS[language]["selection_limits"] in rendered


def test_projection_surfaces_regularization_and_text_export_keeps_interpretation() -> None:
    data = metrics([10.0, 12.0, 14.0, 30.0])
    for chapter in data.chapters:
        chapter.title = f"Synthetic {chapter.num}"
    fp = StyleFingerprint.from_metrics(data)
    rendered = style_dimensions(data.chapters, fp, METRIC_LABELS["en"], "en")
    assert 'id="dim-regularization"' in rendered
    assert "0.2222" in rendered
    assert "regulariz" in rendered.lower()
    text = fp.passport_text(language_key="en")
    assert METRIC_LABELS["en"]["selection_limits"] in text
    assert "0.2222" in text
