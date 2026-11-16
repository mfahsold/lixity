"""Tests for dialogue tag clamping, Romance dialogue dashes, DE indirect speech, and FR -ment exclusions."""

from __future__ import annotations

import pytest

from lixity.dialogue import (
    _count_adverbial_tags,
    dialogue_report,
    dialogue_tag_pattern,
    find_dialogue_tag_spans,
    find_indirect_speech_spans,
)
from lixity.models import CorpusConfig


def test_find_dialogue_tag_spans_clamps_at_sentence_terminators_and_quotes() -> None:
    tag_re = dialogue_tag_pattern("en")
    assert tag_re is not None

    # Sentence terminator in after-window prevents bleeding into next sentence.
    text_after = '"Hello." He walked away. She said nothing.'
    spans_after = find_dialogue_tag_spans(text_after, [(0, 8)], tag_re)
    assert spans_after == []

    # Sentence terminator in before-window prevents bleeding from previous sentence.
    text_before = 'He said nothing. "Hello."'
    spans_before = find_dialogue_tag_spans(text_before, [(18, 26)], tag_re)
    assert spans_before == []

    # Same-sentence tag still matches.
    text_valid = '"Hello," she said.'
    spans_valid = find_dialogue_tag_spans(text_valid, [(0, 8)], tag_re)
    assert len(spans_valid) == 1
    assert text_valid[spans_valid[0][0]:spans_valid[0][1]] == "said"

    # Adjacent quoted span clamps window so verb inside next quote is not attributed.
    text_adj = '"First" "Second said"'
    spans_adj = find_dialogue_tag_spans(text_adj, [(0, 7), (8, 21)], tag_re)
    assert spans_adj == []


@pytest.mark.parametrize(
    ("lang", "dash_text", "parenthetical_text"),
    [
        ("fr", "## Un\n\n— Bonjour, dit-il.\n\n– Salut !\n", "## Un\n\nIl partit — sans un mot — vers la porte.\n"),
        ("es", "## Uno\n\n— Hola, dijo ella.\n\n– ¿Qué tal?\n", "## Uno\n\nElla salió — sin mirar atrás — de la casa.\n"),
        ("it", "## Uno\n\n— Ciao, disse lui.\n\n– Come stai?\n", "## Uno\n\nLui uscì — senza parole — dalla stanza.\n"),
        ("pt", "## Um\n\n— Olá, disse ele.\n\n– Tudo bem?\n", "## Um\n\nEle saiu — sem dizer nada — da sala.\n"),
    ],
)
def test_romance_line_initial_dialogue_dash_and_parenthetical_exclusion(
    lang: str,
    dash_text: str,
    parenthetical_text: str,
) -> None:
    config = CorpusConfig(language=lang)
    dash_report = dialogue_report(dash_text, config)
    assert dash_report.turns == 2
    assert dash_report.dialogue_words > 0

    paren_report = dialogue_report(parenthetical_text, config)
    assert paren_report.turns == 0
    assert paren_report.dialogue_words == 0


def test_german_indirect_speech_konjunktiv_ii_vs_konjunktiv_i() -> None:
    # Counterfactual Konjunktiv II without reporting verb must not trigger.
    counterfactual = "Wenn er Zeit hätte, würde er kommen. Es wäre schön, und man könnte lachen."
    assert find_indirect_speech_spans(counterfactual, [], "de") == []

    # Konjunktiv I stays high-recall.
    konj_i = "Er sagte nichts. Sie sei müde, und er habe keine Zeit."
    spans_i = find_indirect_speech_spans(konj_i, [], "de")
    assert len(spans_i) == 2

    # Konjunktiv II with reporting verb + subordinator or comma+pronoun still matches.
    reported_ii = "Er sagte, dass er kommen würde. Sie meinte, er hätte recht."
    spans_ii = find_indirect_speech_spans(reported_ii, [], "de")
    assert len(spans_ii) == 2


def test_french_ment_nouns_excluded_from_adverbial_tags() -> None:
    clean_nouns = "« Bonjour », dit-il avec sentiment, un moment après le mouvement du gouvernement."
    # Find the tag span for "dit"
    tag_re = dialogue_tag_pattern("fr")
    assert tag_re is not None
    quoted = [(0, 11)]
    tag_spans = find_dialogue_tag_spans(clean_nouns, quoted, tag_re)
    assert len(tag_spans) == 1
    assert _count_adverbial_tags(clean_nouns, tag_spans, quoted, "fr") == 0

    clean_adverb = "« Bonjour », dit-il doucement."
    tag_spans_adv = find_dialogue_tag_spans(clean_adverb, [(0, 11)], tag_re)
    assert _count_adverbial_tags(clean_adverb, tag_spans_adv, [(0, 11)], "fr") == 1
