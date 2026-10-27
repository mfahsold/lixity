"""Curated finite forms take precedence over contradictory suffix guesses.

These fixtures test lexical cue consistency, not grammatical tense tagging.
Unlisted compound auxiliary overlap and genuine homographs remain unresolved.
"""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize("text", [
    "Ich halte das Seil. Wir haben gesprochen. Ich halte das Seil.",
    "Wir sind gewarnt. Sie ist verhaftet worden. Wir haben geschlossen gehalten.",
    "Er war hier. Er ist hier. Sie gingen und sie gehen.",
])
def test_cue_spans_preserve_effective_counting_and_original_occurrences(text):
    config = CorpusConfig(language="de")
    matcher = TenseMatcher(config, resolve_language(config))
    present, past = matcher.spans(text)
    assert (len(present), len(past)) == matcher.count(text)
    for start, end in present + past:
        assert 0 <= start < end <= len(text)
    if "haben gesprochen" in text:
        assert "haben gesprochen" in [text[start:end] for start, end in past]
        assert "haben" not in [text[start:end] for start, end in present]
        assert sum(text[start:end] == "halte" for start, end in present) == 2


def test_custom_capture_and_zero_width_cues_keep_counts_without_fake_ranges():
    config = CorpusConfig(language="en", praesens_regex=r"(?=think)|(think)", praeteritum_regex=r"(was) (here)")
    matcher = TenseMatcher(config, resolve_language(config))
    text = "think was here think"
    present, past = matcher.spans(text)
    assert (len(present), len(past)) == matcher.count(text) == (4, 1)
    assert [text[start:end] for start, end in past] == ["was here"]
    assert sum(start == end for start, end in present) == 2


@pytest.mark.parametrize(("language", "sentence"), [
    ("de", "Ich halte das Seil."),
    ("de", "Wir halten Wache."),
    ("de", "WIR HALTEN WACHE."),
    ("fr", "Je connais ce livre."),
    ("nl", "Wij moeten vertrekken."),
    ("nl", "Wij vinden muziek."),
    ("nl", "Wij zitten buiten."),
    ("nl", "Wij praten zacht."),
    ("nl", "Wij rijden langzaam."),
    ("nl", "Wij worden ouder."),
])
def test_known_present_only_forms_are_not_also_productive_past(language, sentence):
    text = sentence + " " + sentence
    config = CorpusConfig(language=language)
    markdown = "## Reference\n\n" + text
    metrics = CorpusAnalyzer(config).analyze_text(markdown)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(markdown))
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (2, 0)
    assert (chapters[0].present_hits, chapters[0].past_hits) == (2, 0)
    assert paragraphs[0].dominant == chapters[0].dominant == "present"
    assert not paragraphs[0].mixed
    assert metrics.chapters[0].dominance == "present"
    # Scene analysis uses measure_unit, which must apply the same matching policy.
    measured = CorpusAnalyzer(config).measure_unit(text)
    assert measured is not None and measured.dominance == "present"


@pytest.mark.parametrize(("language", "sentence", "present", "past"), [
    ("de", "Wir hielten Wache.", 0, 2),
    ("de", "Wir tasteten vorsichtig.", 0, 2),
    ("fr", "Je connaissais ce livre.", 0, 2),
    ("nl", "Wij moesten vertrekken.", 0, 2),
    ("nl", "Wij praatten zacht.", 0, 2),
    ("de", "Wir haben gesprochen.", 0, 2),
    ("fr", "Nous avons parlé.", 2, 2),
    ("it", "Noi abbiamo parlato.", 2, 2),
    ("es", "Nosotros hemos hablado.", 2, 2),
    ("nl", "Wij hebben gesproken.", 2, 2),
    ("en", "We have worked.", 2, 2),
    ("pt", "Nós falamos.", 2, 2),
    ("de", "Wir sind gewarnt.", 2, 2),
])
def test_past_forms_compounds_and_ambiguous_forms_keep_their_cues(language, sentence, present, past):
    markdown = "## Reference\n\n" + sentence + " " + sentence
    paragraphs, _ = ParagraphProfiler(CorpusConfig(language=language)).profile_blocks(
        parse_markdown_blocks(markdown)
    )
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (present, past)


@pytest.mark.parametrize(("overrides", "expected"), [
    ({"praesens_regex": r"\bhalten\b"}, (2, 2)),
    ({"praesens_regex": ""}, (0, 2)),
    ({"praeteritum_regex": ""}, (2, 0)),
    ({"praeteritum_regex": r"\b(halten)\b"}, (2, 2)),
    ({"praeteritum_regex": r"\b(hal)(ten)\b"}, (2, 2)),
    ({"praeteritum_regex": r"(?=halten)"}, (2, 2)),
])
def test_explicit_tense_pattern_overrides_keep_independent_matching(overrides, expected):
    config = CorpusConfig(language="de", **overrides)
    markdown = "## Reference\n\nWir halten Wache. Wir halten Wache."
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(markdown))
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == expected
    assert (chapters[0].present_hits, chapters[0].past_hits) == expected
    measured = CorpusAnalyzer(config).measure_unit("Wir halten Wache. Wir halten Wache.")
    assert measured is not None and measured.dominance == paragraphs[0].dominant


def test_distinct_present_and_past_evidence_still_marks_a_mixed_paragraph():
    text = "Wir halten Wache. Wir hielten Wache. " * 2
    config = CorpusConfig(language="de")
    paragraphs, _ = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    paragraph = paragraphs[0]
    assert (paragraph.present_hits, paragraph.past_hits) == (2, 2)
    assert paragraph.dominant == "mixed" and paragraph.mixed
    measured = CorpusAnalyzer(config).measure_unit(text)
    assert measured is not None and measured.dominance == "mixed"


def test_explicit_auto_resolution_uses_the_resolved_curated_forms():
    text = "Wir halten die Wache und ich halte das Seil."
    config = CorpusConfig(language="auto")
    profiler = ParagraphProfiler(config, sample_text=text)
    analyzer = CorpusAnalyzer(config, sample_text=text)
    assert profiler.lang.key == analyzer.lang.key == "de"
    paragraphs, _ = profiler.profile_blocks(parse_markdown_blocks("## Reference\n\n" + text))
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (2, 0)
    measured = analyzer.measure_unit(text)
    assert measured is not None and measured.dominance == "present"


def test_generic_profile_remains_without_tense_cues():
    config = CorpusConfig(language="generic")
    paragraphs, _ = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\nWir halten Wache. Wir hielten Wache.")
    )
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (0, 0)
    assert paragraphs[0].dominant == "neutral"


@pytest.mark.parametrize(("language", "text"), [
    ("de", "Wir haben erzählt."),
    ("fr", "Elle a écrit une lettre."),
    ("it", "Le ragazze sono andate a casa."),
    ("it", "Le ho sentite cantare."),
])
def test_auxiliary_compounds_keep_present_homograph_participles(language, text):
    config = CorpusConfig(language=language)
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(text)[1] == 1
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    assert paragraphs[0].past_hits == chapters[0].past_hits == 1


@pytest.mark.parametrize("token", ["2halten", "x_halten"])
def test_word_character_prefixes_do_not_invent_a_present_only_final_word(token):
    # Default suffix patterns use Unicode word characters, including digits and
    # underscores. The veto must assess that complete candidate, not a substring.
    config = CorpusConfig(language="de")
    assert TenseMatcher(config, resolve_language(config)).count(token) == (0, 1)
