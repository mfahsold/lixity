"""Regression cases for the language-specific readability syllable estimates."""

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
