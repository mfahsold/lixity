"""Short weak stems and separable preverbs retain bounded tense ownership."""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize(("text", "expected"), [
    ("Ich habe geübt.", (0, 1)),
    ("Ich habe geölt.", (0, 1)),
    ("Ich hatte gestern geübt.", (0, 1)),
    ("Ich habe gestern geübt.", (0, 1)),
    ("Ich habe eingekauft.", (0, 1)),
    ("Ich habe aufgeräumt.", (0, 1)),
    ("Ich habe einen Koffer abgeholt.", (0, 1)),
    ("Ich habe eingeölt.", (0, 1)),
    ("Ich habe nachgedacht.", (0, 1)),
    ("Ich habe mitgearbeitet.", (0, 1)),
    ("Ich habe zurückgebracht.", (0, 1)),
    ("Ich habe abgegeben.", (0, 1)),
    ("Ich habe ausgegeben.", (0, 1)),
    ("Ich habe eingeübt.", (0, 1)),
    ("Ich bin zurückgekehrt.", (0, 1)),
    ("Das Zimmer ist aufgeräumt worden.", (0, 1)),
    ("Die Tür ist eingeölt worden.", (0, 1)),
    ("Das Paket ist abgeholt worden.", (0, 1)),
    ("Die Rolle ist eingeübt worden.", (0, 1)),
    ("Die Antenne ist ausgefahren worden.", (0, 1)),
    ("Das Paket ist abgeholt.", (1, 1)),
    ("Der Boden ist eingeölt.", (1, 1)),
    ("Ich bin eingekauft.", (1, 1)),
    ("Ich bin weggegangen.", (1, 1)),
    ("Die Antenne ist ausgefahren.", (1, 1)),
    ("Das Instrument ist geölt.", (1, 1)),
    ("Ich habe einen allgemeinen Überblick.", (1, 0)),
    ("Ich habe einen aufgeweckten Jungen.", (1, 0)),
    ("Ich habe einen abgehobenen Ton.", (1, 0)),
    ("Ich habe einen eingehenden Brief.", (1, 0)),
    ("Ich habe geschnittenes Brot.", (1, 0)),
    ("Ich habe eingeölte Türen.", (1, 0)),
    ("Ich habe Gehalt.", (1, 0)),
    ("Ich habe geübt, und gehe.", (1, 1)),
    ("Ich habe und sie haben aufgeräumt.", (1, 1)),
    ("Ich habe, eingekauft.", (1, 0)),
    ("Ich habe vorbereitet.", (1, 1)),
    ("Ich habe wiedergutgemacht.", (1, 1)),
])
def test_short_and_separable_forms_across_measured_scopes(text, expected):
    config = CorpusConfig(language="de")
    assert TenseMatcher(config, resolve_language(config)).count(text) == expected
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == expected
    assert (chapters[0].present_hits, chapters[0].past_hits) == expected
    measured = CorpusAnalyzer(config).measure_unit(text)
    assert measured is not None and measured.dominance == paragraphs[0].dominant


def test_separable_span_ownership_and_explicit_override():
    text = "🧭 Ich habe geübt. Die Tür ist eingeölt worden."
    config = CorpusConfig(language="de")
    matcher = TenseMatcher(config, resolve_language(config))
    assert [(text[start:end], licensed) for start, end, licensed in matcher._german_perfect_spans(text)] == [
        ("habe geübt", True), ("ist eingeölt worden", True),
    ]
    override = CorpusConfig(language="de", praesens_regex=r"\bhabe\b")
    assert TenseMatcher(override, resolve_language(override)).count("Ich habe eingekauft.") == (1, 1)
