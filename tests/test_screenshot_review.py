"""Capture review responses must describe the exact manuscript shown on screen."""

from hashlib import sha256

import pytest

from lixity.analysis_review import review_analysis
from lixity.markers import add_marker
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.style_fingerprint import FingerprintThresholds
from scripts import make_screenshots


@pytest.mark.parametrize("marked", [False, True])
def test_capture_review_fixture_uses_real_exact_source_state(tmp_path, marked):
    text = make_screenshots.DEMO_MANUSCRIPT.read_text(encoding="utf-8")
    if marked:
        text, _ = add_marker(text, kind="todo", note="Synthetic review note", target_line=10)
    thresholds = FingerprintThresholds()
    fixture = make_screenshots.build_analysis_review_fixture(
        tmp_path, text, manuscript_name="harbour-manuscript.md", language="en",
        title="Synthetic Warehouse", thresholds=thresholds,
    )
    response = fixture["response"]
    assert response == {"ok": True, **review_analysis(
        tmp_path, manuscript=tmp_path / "harbour-manuscript.md", language="en", thresholds=thresholds,
    )}
    assert response["source_sha256"] == sha256(text.encode()).hexdigest()
    assert response["total"] == len(response["observations"])
    assert any(item["chapter"] == 6 and item["mixed"] for item in response["observations"])
    assert all(item["status"] == "unreviewed" for item in response["observations"])
    assert response["completed"] == response["unmatched_decisions"] == 0
    assert fixture["token"] == manuscript_pdf_token(
        str(tmp_path / "harbour-manuscript.md"), project_root=tmp_path, language="en",
        title="Synthetic Warehouse", thresholds=thresholds,
    )
    assert not (tmp_path / ".lixity" / "analysis-review.json").exists()
