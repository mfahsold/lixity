"""Canonical counting views preserve exact source ranges without guessed offsets."""

import unicodedata

import pytest

from lixity.text_normalization import counting_view


@pytest.mark.parametrize("word", ["schön", "café", "niño", "città", "ação", "één", "naïve"])
def test_decomposed_words_map_complete_matches_to_original_range(word):
    source = unicodedata.normalize("NFD", word)
    view = counting_view(source)
    assert view.text == word
    assert view.source_span(0, len(word)) == (0, len(source))


def test_identity_keeps_whitespace_astral_characters_and_all_offsets():
    source = " \t😀 café\n"
    view = counting_view(source)
    assert view.text is source
    for start in range(len(source) + 1):
        assert view.source_span(start, start) == (start, start)
    assert view.source_span(2, 4) == (2, 4)


def test_repeated_matches_use_their_own_occurrences():
    source = "cafe\u0301 😀 cafe\u0301"
    view = counting_view(source)
    assert view.text == "café 😀 café"
    assert view.source_span(0, 4) == (0, 5)
    assert view.source_span(7, 11) == (8, 13)
    assert view.source_span(4, 7) == (5, 8)


def test_composed_and_reordered_clusters_reject_ambiguous_inner_cuts():
    source = "x a\u0301\u0323 y"
    view = counting_view(source)
    assert view.text == "x ạ\u0301 y"
    assert view.source_span(2, 4) == (2, 5)
    assert view.source_span(2, 3) is None
    assert view.source_span(3, 4) is None
    assert view.source_span(3, 3) is None
    assert view.source_span(4, 6) == (5, 7)


def test_leading_reordered_marks_and_hangul_join_fail_closed_inside_clusters():
    source = "\u0301\u0323 \u1100\u1161\u11a8"
    view = counting_view(source)
    assert view.text == "\u0323\u0301 각"
    assert view.source_span(0, 2) == (0, 2)
    assert view.source_span(0, 1) is None
    assert view.source_span(3, 4) == (3, 6)


@pytest.mark.parametrize("source", ["", "cafe\u0301"])
def test_empty_and_invalid_ranges(source):
    view = counting_view(source)
    assert view.source_span(0, 0) == (0, 0)
    for start, end in [(-1, 0), (0, len(view.text) + 1), (1, 0), (0.0, 0), (False, 0)]:
        assert view.source_span(start, end) is None
