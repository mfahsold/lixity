"""Configured quote patterns use consistent capture semantics across reports."""

import pytest

from lixity.dialogue import dialogue_report
from lixity.models import CorpusConfig
from lixity.pacing import pacing_report
from lixity.pipeline import analyze_document
from lixity.scenes import scene_report
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


def test_reports_count_only_existing_scope_words_in_quotes():
    text = '## One\n\nShe said, "Come." He said, "Rest."\n'
    config = CorpusConfig(language="en", word_regex=r"^(\w+)")
    report = dialogue_report(text, config)
    chapter = pacing_report(text, config).chapter_list[0]
    scene = scene_report(text, config)["items"][0]
    assert report.turns == 2
    assert report.words == 1
    assert report.dialogue_words == 0
    assert report.dialogue_pct == chapter.dialogue_pct == chapter.scene_list[0].dialogue_pct == 0.0
    assert scene["features"]["dialog_pct"] == 0.0


def test_reports_project_line_initial_spanish_dialogue_after_a_soft_wrap():
    text = "## Uno\n\nMara duerme.\n—Hola.\n—Adiós.\n"
    config = CorpusConfig(language="es")
    report = dialogue_report(text, config)
    chapter = pacing_report(text, config).chapter_list[0]
    scene = scene_report(text, config)["items"][0]
    assert report.turns == 2
    assert report.dialogue_words == 2
    assert report.dialogue_pct == chapter.dialogue_pct == chapter.scene_list[0].dialogue_pct == 50.0
    assert scene["features"]["dialog_pct"] == 50.0
    assert scene["exit_hook_type"] == "dialogue"


def test_scene_halves_reuse_quotes_that_cross_sentences():
    narration = "The blue lamp by the window cast the same long shadow every night. " * 6
    speech = "Tomorrow we will travel to the coast before the warm sun goes down. " * 6
    text = f"## One\n\n{narration.strip()}\n\n“{speech.strip()}”\n"
    config = CorpusConfig(language="en")
    scene = scene_report(text, config)["items"][0]
    assert scene["dialogue_shift"] == 100.0
    assert scene["scene_dynamic"] == "dialogue_surge"


def test_incomplete_quote_is_an_unknown_hook_and_excluded_from_voice_separation():
    text = "## One\n\n“Come here.”\n\n“Wait until morning.\n"
    config = CorpusConfig(language="en")
    report = dialogue_report(text, config)
    chapter = pacing_report(text, config).chapter_list[0]
    scene = scene_report(text, config)["items"][0]
    assert report.dialogue_words == 2
    assert report.words == 5
    assert report.voice_separation.narrative_words == 0
    assert not report.voice_separation.available
    assert scene["exit_hook_type"] == chapter.scene_list[0].exit_hook_type == "unknown"
