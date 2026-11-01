"""Spanish have-perfect auxiliaries should not also count as present cues."""

import pytest

from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize("text", [
    "Ella ha llegado. Él ha comido.",
    "Yo he hablado. Tú has trabajado. Nosotros hemos vivido.",
    "ELLA HA LLEGADO. ÉL HA COMIDO.",
])
def test_spanish_haber_perfect_counts_once_as_past(text):
    config = CorpusConfig(language="es")
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(text) == (0, text.count("."))
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    assert not paragraphs[0].mixed
    assert paragraphs[0].present_hits == chapters[0].present_hits == 0
    assert paragraphs[0].past_hits == chapters[0].past_hits == text.count(".")


def test_spanish_independent_present_and_perfect_remain_distinct():
    config = CorpusConfig(language="es")
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count("Ella ha llegado. Él tiene tiempo.") == (1, 1)


@pytest.mark.parametrize(("language", "text"), [
    ("fr", "Il est arrivé."),
    ("it", "Lei è arrivata."),
    ("nl", "Hij is gekomen."),
    ("nl", "Hij heeft gebreken."),
])
def test_ambiguous_constructions_remain_unchanged(language, text):
    config = CorpusConfig(language=language)
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(text) == (1, 1)


@pytest.mark.parametrize("override", [
    {"praesens_regex": r"\bha\b"},
    {"praeteritum_regex": r"\bha llegado\b"},
])
def test_custom_patterns_retain_independent_counting(override):
    config = CorpusConfig(language="es", **override)
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count("Ella ha llegado.") == (1, 1)



@pytest.mark.parametrize("text", ["Ha de salir.", "Ha ya llegado.", "Ha, llegado."])
def test_nonadjacent_or_nonparticipial_haber_stays_present(text):
    config = CorpusConfig(language="es")
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(text) == (1, 0)


def test_paragraph_break_does_not_bind_spanish_perfect_auxiliary():
    config = CorpusConfig(language="es")
    matcher = TenseMatcher(config, resolve_language(config))
    present, _past = matcher.count("Ha\n\nllegado.")
    assert present == 1
