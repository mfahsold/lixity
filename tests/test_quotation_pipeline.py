"""Quotation recognition agrees across manuscript views and retained revisions."""

import pytest

from lixity.dialogue import dialogue_report
from lixity.manuscript_editing import analyze_manuscript_snapshot
from lixity.markdown_parser import prose_text
from lixity.models import CorpusConfig
from lixity.motifs import search_manuscript
from lixity.pipeline import analyze_document, supplementary_reports
from lixity.quotation_projection import quoted_prose
from lixity.style_fingerprint import FingerprintThresholds


@pytest.mark.parametrize(("language", "left", "right"), [
    ("de", "„", "“"), ("en", "\u2018", "’"), ("fr", "«", "»"), ("es", "«", "»"),
    ("it", "«", "»"), ("nl", "“", "”"), ("pt", "“", "”"),
])
def test_multiline_quote_uses_the_original_passages_in_all_seven_profiles(language, left, right):
    source = f"## Chapter\n\nNora waits.\n\n{left}Un deux.\n\nTrois quatre.{right}\n"
    config = CorpusConfig(language=language, filter_verbs_regex="quatre")
    analysis = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    assert analysis.metrics.dialog_words == 4
    assert [paragraph.dialogue_pct for paragraph in analysis.paragraphs] == [0, 100, 100]
    for index, quote in ((1, "Un deux."), (2, "Trois quatre.")):
        layer = analysis.evidence[index]["layers"]["dialogue"]
        assert layer["denominator"] == layer["count"] == 2
        span = layer["spans"][0]
        assert span["quotation_marker"] == f"{left}…{right}"
        assert analysis.paragraphs[index].text[span["start"]:span["end"]] == quote
    assert analysis.evidence[2]["layers"]["filter"]["spans"][0]["quotation_context"] == "in_quotation"
    reports = supplementary_reports(source, config, analysis)
    assert reports["dialogue"]["dialogue_words"] == 4
    assert reports["pacing"]["chapter_list"][0]["dialogue_pct"] == pytest.approx(66.67)
    assert analyze_manuscript_snapshot(source, config=config)["dialogue_ratio"] == 66.667
    occurrences = search_manuscript(source, "quatre", config=config)["occurrences"]
    assert occurrences[0]["quotation_context"] == "in_quotation"


def test_spanish_dash_keeps_its_physical_line_start_after_inline_cleanup():
    source = "## Llegada\r\n\r\nEntra **al salón.\r\n—Hola**.\r\n\r\n`—Código`\r\n"
    config = CorpusConfig(language="es")
    projection = quoted_prose(source, config)
    assert projection.text == prose_text(source, config) == "Entra al salón. —Hola."
    assert [projection.text[span.start:span.end] for span in projection.analysis.spans] == ["Hola."]
    assert dialogue_report(source, config).dialogue_words == 1


def test_word_share_never_retokenizes_a_quote_substring():
    source = '## Chapter\n\nShe said, "Come." He said, "Rest."\n'
    config = CorpusConfig(language="en", word_regex=r"^(\w+)")
    result = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    assert result.metrics.tokens == 1
    assert result.metrics.dialog_ratio == result.paragraphs[0].dialogue_pct == 0
    layer = result.evidence[0]["layers"]["dialogue"]
    assert layer["count"] == 0 and layer["denominator"] == 1
    assert len(layer["quotation_ranges"]) == 2
    assert dialogue_report(source, config).dialogue_words == 0
    assert analyze_manuscript_snapshot(source, config=config)["dialogue_ratio"] == 0


def test_a_scene_break_cannot_complete_an_open_quote():
    source = '## Chapter\n\n"Join us.\n\n---\n\nWe waited there."\n'
    config = CorpusConfig(language="en")
    analysis = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    assert analysis.metrics.dialog_words == 0
    assert analysis.evidence[0]["layers"]["dialogue"]["reason"] == "quotation_context_unresolved"
    assert "quotation_context" not in analysis.evidence[0]["layers"]["asl"]["spans"][0]
