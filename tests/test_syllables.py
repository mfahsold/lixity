"""Regression cases for the language-specific readability syllable estimates."""

from unicodedata import normalize

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.models import CorpusConfig
from lixity.syllables import count_es, count_syllables


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("vivir", 2),
        ("dibujo", 3),
        ("susurro", 3),
        ("ciudad", 2),
        ("ruido", 2),
        ("cuidado", 3),
        ("tierra", 2),
        ("causa", 2),
        ("cambiáis", 2),
        ("buey", 1),
        ("teatro", 3),
        ("poeta", 3),
        ("país", 2),
        ("río", 2),
        ("chiita", 3),
        ("lingüística", 4),
        ("veintiún", 2),
        ("guitarra", 3),
        ("seguir", 2),
        ("queso", 2),
        ("pingüino", 3),
        ("prohibir", 2),
        ("prohíbe", 3),
        ("búho", 2),
        ("VIVIR", 2),
        ("¡dibujo!", 3),
        ("", 0),
        ("123", 0),
    ],
)
def test_spanish_counts_nuclei_with_orthographic_diphthongs(word, expected):
    """Closed vowels form nuclei; mergers follow the bounded Spanish rules."""
    assert count_es(word) == expected


def test_spanish_syllables_reach_readability_metrics():
    """The corpus uses the corrected estimate, rather than a separate counter."""
    metrics = CorpusAnalyzer(CorpusConfig(language="es")).analyze_text(
        "## Escena\n\nVivir. Dibujo. Ruido.\n"
    )
    assert metrics.clean_words == 3
    assert metrics.total_sentences == 3
    assert metrics.asw == pytest.approx(7 / 3)
    assert metrics.flesch_de == pytest.approx(206.835 - 1 - 62.35 * 7 / 3)


@pytest.mark.parametrize(
    ("language", "word", "expected"),
    [
        ("de", "heute", 2),
        ("en", "table", 2),
        ("fr", "maison", 2),
        ("it", "casa", 2),
        ("pt", "casa", 2),
        ("nl", "huizen", 2),
        ("generic", "river", 2),
    ],
)
def test_spanish_change_preserves_other_language_counters(language, word, expected):
    assert count_syllables(word, language) == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("país", 2),
        ("saída", 3),
        ("saúde", 3),
        ("baía", 3),
        ("ruído", 3),
        ("SAÚDE", 3),
        ("pai", 1),
        ("pão", 1),
        ("mãe", 1),
        ("céu", 1),
        ("muito", 2),
    ],
)
def test_portuguese_marked_hiatus_preserves_other_diphthongs(word, expected):
    """Priberam separates accented i/u: país, saída, saúde, baía and ruído."""
    assert count_syllables(word, "pt") == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("ideeën", 3),
        ("reëel", 2),
        ("creëren", 3),
        ("geëerd", 2),
        ("beïnvloeden", 4),
        ("reünie", 3),
        ("IDEEËN", 3),
        ("zee", 1),
        ("huizen", 2),
        ("ijs", 1),
    ],
)
def test_dutch_diaeresis_starts_a_new_nucleus(word, expected):
    """Taaladvies's trema convention marks the first vowel of a new syllable."""
    assert count_syllables(word, "nl") == expected


@pytest.mark.parametrize(
    ("language", "text", "expected_asw", "expected_readability"),
    [
        ("pt", "Saída. Saúde. País.", 8 / 3, 22.22),
        ("nl", "Ideeën. Reëel. Creëren.", 8 / 3, 0.7366666666666788),
    ],
)
def test_marked_hiatus_reaches_readability(language, text, expected_asw, expected_readability):
    metrics = CorpusAnalyzer(CorpusConfig(language=language)).analyze_text(
        "## Scene\n\n" + text
    )
    assert metrics.tokens == metrics.total_sentences == 3
    assert metrics.asw == pytest.approx(expected_asw)
    assert metrics.flesch_de == pytest.approx(expected_readability)


@pytest.mark.parametrize("form", ["NFC", "NFD"])
@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("bijen", 2),
        ("rijen", 2),
        ("vrijer", 2),
        ("bijeen", 2),
        ("geijkt", 2),
        ("BIJEEN", 2),
        ("bij", 1),
        ("ijs", 1),
        ("vrij", 1),
        ("rijbewijs", 3),
        ("ijsvrij", 2),
        ("zee", 1),
        ("huizen", 2),
        ("ideeën", 3),
        ("reünie", 3),
        ("", 0),
        ("123", 0),
    ],
)
def test_dutch_ij_preserves_adjacent_vowel_nuclei(word, expected, form):
    """ANW divides bij.en, rij.en, vrij.er and bij.een; no trema is needed.

    Sources: https://anw.ivdnt.org/article/bij, /rij, /vrijer and /bijeen;
    https://onzetaal.nl/taalloket/trema also lists e+ij in geijkt.
    """
    assert count_syllables(normalize(form, word), "nl") == expected


@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_dutch_ij_nuclei_reach_readability(form):
    text = "## Referentie\n\nBijen. Rijen. Vrijer. Bijeen. Geijkt. Ideeën.\n"
    metrics = CorpusAnalyzer(CorpusConfig(language="nl")).analyze_text(normalize(form, text))
    assert metrics.tokens == metrics.total_sentences == 6
    assert metrics.asw == pytest.approx(13 / 6)
    assert metrics.flesch_de == pytest.approx(39.23666666666668)
