"""Structural summaries must respect missing chapter positions."""

from lixity.style_fingerprint import (
    StyleFingerprint,
    ks_2sample,
    mann_kendall,
    qn_estimator,
    sn_estimator,
    wasserstein_1d,
)


def fingerprint(values):
    return StyleFingerprint(
        n_chapters=len(values),
        values={"asl": dict(enumerate(values, 1))},
        baseline={"asl": {"n": sum(value is not None for value in values), "sigma": 1.0}},
    )


def test_missing_chapter_does_not_produce_a_fabricated_boundary():
    diag = fingerprint([1.0, 1.0, None, 1.0, 10.0, 10.0, 10.0])._derive_structural_diagnostics()
    assert "asl" not in diag["changepoints"]
    assert diag["segmentation_unavailable"] == ["asl"]


def test_half_comparison_uses_original_chapter_midpoint():
    diag = fingerprint([None, None, 1.0, 2.0, 10.0, 11.0, 12.0, 13.0])._derive_structural_diagnostics()
    shift = diag["distribution_shift"]["asl"]
    early, late = [1.0, 2.0], [10.0, 11.0, 12.0, 13.0]
    d, p = ks_2sample(early, late)
    assert shift == {"wasserstein": round(wasserstein_1d(early, late), 6),
                     "ks_d": round(d, 4), "ks_p": round(p, 4)}
    assert "asl" not in diag["distribution_unavailable"]
    assert diag["distribution_incomplete"] == ["asl"]


def test_distribution_is_unavailable_when_original_half_has_too_few_observations():
    diag = fingerprint([None, None, None, 2.0, 10.0, 11.0, 12.0, 13.0])._derive_structural_diagnostics()
    assert "asl" not in diag["distribution_shift"]
    assert diag["distribution_unavailable"] == ["asl"]


def test_trend_and_order_independent_scales_use_available_observations():
    values = [1.0, None, 2.0, 4.0, 8.0, 16.0]
    diag = fingerprint(values)._derive_structural_diagnostics()
    observed = [value for value in values if value is not None]
    trend = mann_kendall(observed)
    assert trend is not None
    assert diag["trends"]["asl"] == {"tau": round(trend[0], 4), "S": round(trend[1], 1),
                                     "p": round(trend[2], 4)}
    assert diag["trend_incomplete"] == ["asl"]
    assert diag["robust_scales"]["asl"]["sn"] == round(sn_estimator(observed), 6)
    assert diag["robust_scales"]["asl"]["qn"] == round(qn_estimator(observed), 6)


def test_ui_reports_unavailable_and_partial_data_without_success_checks():
    from lixity.ui.structural import style_structural

    fp = fingerprint([None, None, None, 2.0, 10.0, 11.0, 12.0, 13.0])
    fp.structural_diagnostics = fp._derive_structural_diagnostics()
    html = style_structural([None] * fp.n_chapters, fp)  # type: ignore[list-item]
    assert html.count("Not enough comparable chapter measurements") == 2
    assert "badge-success" not in html
    assert "No candidate boundaries selected" not in html
    assert "No nominal distribution signals selected" not in html
    assert "Some trends use only chapters with measurements" in html

    full = {chapter: float(chapter) for chapter in range(1, 9)}
    fp.values["dialog_pct"] = full
    fp.baseline["dialog_pct"] = {"n": 8, "sigma": 1.0}
    fp.structural_diagnostics = fp._derive_structural_diagnostics()
    html = style_structural([None] * fp.n_chapters, fp)  # type: ignore[list-item]
    assert "Some features could not be calculated" in html
