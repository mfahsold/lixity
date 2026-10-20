"""A bounded lexical cue list is shared across German analysis surfaces."""

import pytest

from lixity import api
from lixity.analyzer import CorpusAnalyzer
from lixity.models import CorpusConfig
from lixity.pipeline import profile_document, resolve_document_config
from lixity.scenes import scene_report
from lixity.style_fingerprint import FingerprintThresholds


@pytest.mark.parametrize("form", [
    "höre", "hörst", "hört", "hören", "hörte", "hörtest", "hörtet", "hörten",
    "rieche", "riechst", "riecht", "riechen", "roch", "rochst", "rocht", "rochen",
])
def test_list_counts_documented_finite_hear_and_smell_forms(form):
    metrics = CorpusAnalyzer(CorpusConfig(language="de")).analyze_text(form + ".")
    assert metrics.filter_count == 1


def test_cues_agree_across_corpus_chapter_paragraph_and_scene():
    text = "## Garden\n\nIch höre leise Musik. Ich rieche frische Farbe."
    config, _ = resolve_document_config(text, "de")
    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    scene = scene_report(text, config)["items"][0]
    assert metrics.filter_count == 2
    assert metrics.filter_density == pytest.approx(2000 / metrics.tokens)
    assert metrics.chapters[0].filter_density == metrics.filter_density
    assert paragraphs[0].filter_density == round(metrics.filter_density, 1)
    assert scene["features"]["filter_density"] == metrics.filter_density
    assert paragraphs[0].text == "Ich höre leise Musik. Ich rieche frische Farbe."


def test_word_boundaries_do_not_expand_to_compounds_or_ambiguous_participles():
    text = "Das Gehör gehört dazu. Unerhört. Die Zuhörer und Riechstoffe bleiben. Mein Puls hämmert."
    assert CorpusAnalyzer(CorpusConfig(language="de")).analyze_text(text).filter_count == 0


def test_lexical_match_does_not_claim_a_narrative_filter_parse():
    text = "Der Raum riecht nach Farbe."
    assert CorpusAnalyzer(CorpusConfig(language="de")).analyze_text(text).filter_count == 1


def test_explicit_project_pattern_replaces_default_and_other_languages_stay_separate():
    text = "Ich höre Musik. Sie merkt etwas."
    assert api.analyze(text, language="de", filter_verbs_regex=r"\bmerkt\b")["metrics"]["filter_count"] == 1
    assert api.analyze(text, language="de", filter_verbs_regex="")["metrics"]["filter_count"] == 0
    assert api.analyze(text, language="en")["metrics"]["filter_count"] == 0
