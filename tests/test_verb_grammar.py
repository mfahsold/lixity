"""Tests for German Konjunktiv I/II and analytical würde + Inf in verb_grammar."""

from lixity.linguistic_models import SyntaxToken
from lixity.verb_grammar import classify_german


def _tok(
    index: int,
    text: str,
    lemma: str,
    pos: str,
    form: str,
    mood: str,
    tense: str,
    head: int = 0,
    dep: str = "ROOT",
) -> SyntaxToken:
    return SyntaxToken(index, index * 10, index * 10 + len(text), text, lemma, pos, "", form, mood, tense, head, dep)


def test_german_konjunktiv_i_and_ii_are_separated():
    k1 = classify_german([_tok(0, "singe", "singen", "VERB", "Fin", "Sub", "Pres")])
    assert (k1.tense, k1.mood, k1.voice) == ("present", "subjunctive_i", "active")

    k1_perf = classify_german([
        _tok(0, "habe", "haben", "AUX", "Fin", "Sub", "Pres"),
        _tok(1, "gesungen", "singen", "VERB", "Part", "", "", 0, "oc"),
    ])
    assert (k1_perf.tense, k1_perf.mood, k1_perf.voice) == ("perfect", "subjunctive_i", "active")

    k2 = classify_german([_tok(0, "sänge", "singen", "VERB", "Fin", "Sub", "Past")])
    assert (k2.tense, k2.mood, k2.voice) == ("preterite", "subjunctive_ii", "active")

    k2_plup = classify_german([
        _tok(0, "hätte", "haben", "AUX", "Fin", "Sub", "Past"),
        _tok(1, "gesungen", "singen", "VERB", "Part", "", "", 0, "oc"),
    ])
    assert (k2_plup.tense, k2_plup.mood, k2_plup.voice) == ("pluperfect", "subjunctive_ii", "active")


def test_german_wuerde_infinitive_is_conditional_not_future():
    wuerde = classify_german([
        _tok(0, "würde", "werden", "AUX", "Fin", "Sub", "Past"),
        _tok(1, "singen", "singen", "VERB", "Inf", "", "", 0, "oc"),
    ])
    assert (wuerde.tense, wuerde.mood, wuerde.voice) == ("conditional", "subjunctive_ii", "active")

    wuerde_perf = classify_german([
        _tok(0, "würde", "werden", "AUX", "Fin", "Sub", "Past"),
        _tok(1, "gesungen", "singen", "VERB", "Part", "", "", 2, "oc"),
        _tok(2, "haben", "haben", "AUX", "Inf", "", "", 0, "oc"),
    ])
    assert (wuerde_perf.tense, wuerde_perf.mood, wuerde_perf.voice) == ("conditional_perfect", "subjunctive_ii", "active")

    future = classify_german([
        _tok(0, "wird", "werden", "AUX", "Fin", "Ind", "Pres"),
        _tok(1, "singen", "singen", "VERB", "Inf", "", "", 0, "oc"),
    ])
    assert (future.tense, future.mood, future.voice) == ("future", "indicative", "active")
