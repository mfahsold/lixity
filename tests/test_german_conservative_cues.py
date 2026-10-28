"""German default cues must not promote arbitrary inflectional endings to past."""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize('sentence', [
    'Sie wühlt in der feuchten Erde.',
    'Mit geschlossenen Augen setzt sie zu ihrem kunstvollsten Lied an.',
    'Die bunten Blätter liegen auf den alten Steinen.',
    'Die schnellste Route führt zu den geplanten Schulen.',
    'Heute stehen die nächsten Termine im Kalender.',
    'Die müden Menschen fanden ruhige Orte.',
])
def test_attributive_endings_are_not_automatic_past_cues(sentence):
    config = CorpusConfig(language='de')
    matcher = TenseMatcher(config, resolve_language(config))
    _, past = matcher.spans(sentence)
    forbidden = {'feuchten', 'kunstvollsten', 'bunten', 'alten', 'schnellste', 'geplanten',
                 'heute', 'nächsten', 'müden', 'ruhige'}
    assert not any(sentence[start:end].lower() in forbidden for start, end in past)


def test_cues_and_evidence_agree_across_project_scopes():
    sentence = 'Die Nachtigall übt und übt. Sie sang und fand die feuchten Blätter.'
    config = CorpusConfig(language='de')
    matcher = TenseMatcher(config, resolve_language(config))
    present, past = matcher.spans(sentence)
    assert [sentence[start:end] for start, end in present] == ['übt', 'übt']
    assert [sentence[start:end] for start, end in past] == ['sang', 'fand']
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks('## Chapter\n\n' + sentence))
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (2, 2)
    assert (chapters[0].present_hits, chapters[0].past_hits) == (2, 2)
    assert CorpusAnalyzer(config).measure_unit(sentence).dominance == paragraphs[0].dominant


def test_unknown_weak_past_is_not_guessed_without_context():
    config = CorpusConfig(language='de')
    sentence = 'Die Vögel flatterten.'
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count(sentence) == (0, 0)


def test_explicit_user_patterns_remain_author_controlled():
    config = CorpusConfig(language='de', praeteritum_regex=r'\bflatterten\b')
    matcher = TenseMatcher(config, resolve_language(config))
    assert matcher.count('Die Vögel flatterten.') == (0, 1)
