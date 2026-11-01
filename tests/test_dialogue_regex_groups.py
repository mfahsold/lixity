"""Configured quote patterns use consistent capture semantics across reports."""

import pytest

from lixity.dialogue import dialogue_report
from lixity.models import CorpusConfig
from lixity.pacing import pacing_report
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds


@pytest.mark.parametrize("pattern", [
    r"„[^“]+“",
    r"„([^“]+)“",
    r"„((Alpha) beta)“",
])
def test_quote_word_counts_agree_across_analysis_with_zero_one_or_multiple_groups(pattern):
    text = "## One\n\n„Alpha beta“ gamma delta.\n"
    config = CorpusConfig(language="de", dialogue_regex=pattern)
    analysis = analyze_document(text, config, FingerprintThresholds(), include_evidence=True)
    assert analysis.metrics.dialog_words == 2
    assert analysis.metrics.dialog_ratio == 50.0
    assert analysis.metrics.chapters[0].dialog_pct == 50.0
    assert analysis.paragraphs[0].dialogue_pct == 50.0
    assert analysis.evidence is not None
    assert analysis.evidence[0]["layers"]["dialogue"]["count"] == 2
    assert analysis.evidence[0]["layers"]["dialogue"]["mapped_count"] == 2
    assert dialogue_report(text, config).dialogue_words == 2
    assert pacing_report(text, config).chapter_list[0].scene_list[0].dialogue_pct == 50.0


def test_optional_first_capture_contributes_no_words_across_reports():
    text = "## One\n\n„Alpha beta“ «gamma delta».\n"
    config = CorpusConfig(language="de", dialogue_regex=r"„((Alpha) beta)“|«([^»]+)»")
    analysis = analyze_document(text, config, FingerprintThresholds(), include_evidence=True)
    assert analysis.metrics.dialog_words == 2
    assert analysis.metrics.chapters[0].dialog_pct == 50.0
    assert analysis.paragraphs[0].dialogue_pct == 50.0
    assert analysis.evidence is not None
    assert analysis.evidence[0]["layers"]["dialogue"]["mapped_count"] == 2
    report = dialogue_report(text, config)
    assert report.turns == 2 and report.dialogue_words == 2
    assert pacing_report(text, config).chapter_list[0].scene_list[0].dialogue_pct == 50.0
