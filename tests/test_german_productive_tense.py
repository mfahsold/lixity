"""Morphological perfect candidates need bounded auxiliary/head evidence."""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize(("text", "expected"), [
    ("Ich habe geschlafen. Ich habe getroffen. Ich habe gehabt.", (0, 3)),
    ("Ich habe gestern geschlafen.", (0, 1)),
    ("Ich habe ihn getroffen.", (0, 1)),
    ("Ich hatte vorher geschlafen.", (0, 1)),
    ("Ich habe geputzt.", (0, 1)),
    ("Ich habe gestaunt.", (0, 1)),
    ("Ich habe telefoniert.", (0, 1)),
    ("Ich habe renoviert.", (0, 1)),
    ("Ich habe fotografiert.", (0, 1)),
    ("Die Brücke ist gebaut worden.", (0, 1)),
    ("Die Brücke ist renoviert worden.", (0, 1)),
    ("Die Brücke war renoviert worden.", (0, 1)),
    ("Der Plan ist finanziert worden.", (0, 1)),
    ("Ich habe Bedenken.", (1, 0)),
    ("Die Tür ist geschlossen.", (1, 1)),
    ("Die Tür ist renoviert.", (1, 0)),
    ("Ich habe gewissen Mut.", (1, 1)),
    ("Ich habe geraden Rücken.", (1, 1)),
    ("Ich habe einen geraden Rücken.", (1, 0)),
    ("Ich habe einen getroffenen Zeugen.", (1, 0)),
    ("Ich habe geschnittenes Brot.", (1, 0)),
    ("Ich habe Gewalt.", (1, 0)),
    ("Ich habe geraden und gebundenen Stoff.", (1, 1)),
    ("Ich habe gegen die Regel gehandelt.", (0, 1)),
    ("Ich habe, geschlafen.", (1, 0)),
    ("Ich habe und sie haben geschlafen.", (1, 1)),
    ("Ich habe geschlafen, und gehe.", (1, 1)),
    ("geschlafen getroffen gehabt gebaut renoviert", (0, 0)),
    ("Ich habe ge123t.", (1, 1)),
    ("Ich habe gelben Stoff.", (1, 1)),
    ("Ich habe und er renoviert.", (1, 0)),
])
def test_productive_constructions_and_adversarial_controls(text, expected):
    config = CorpusConfig(language="de")
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(text) == expected
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == expected
    assert (chapters[0].present_hits, chapters[0].past_hits) == expected
    measured = CorpusAnalyzer(config).measure_unit(text)
    assert measured is not None and measured.dominance == paragraphs[0].dominant


def test_productive_span_ownership_stays_exact_in_original_counting_text():
    config = CorpusConfig(language="de")
    text = "🧭 Ich habe geschlafen. Die Brücke ist renoviert worden."
    spans = TenseMatcher(config, resolve_language(config))._german_perfect_spans(text)
    assert [(text[start:end], licensed) for start, end, licensed in spans] == [
        ("habe geschlafen", True), ("ist renoviert worden", True),
    ]


@pytest.mark.parametrize(("overrides", "expected"), [
    ({"praesens_regex": ""}, (0, 1)),
    ({"praeteritum_regex": ""}, (1, 0)),
    ({"praesens_regex": r"\bhabe\b"}, (1, 1)),
])
def test_explicit_overrides_keep_independent_raw_matching(overrides, expected):
    config = CorpusConfig(language="de", **overrides)
    assert TenseMatcher(config, resolve_language(config)).count("Ich habe geschlafen.") == expected
