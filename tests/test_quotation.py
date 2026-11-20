"""Quotation profiles share offsets and word membership across analysis scopes."""

import re

import pytest

from lixity.language import compile_pattern, compile_word_pattern
from lixity.quotation import (
    QuotationAnalysis,
    count_quoted_words,
    partition_quoted_words,
    quoted_word_counts,
    scan_quotations,
)


def sections(text, result):
    return [(text[span.start:span.end], span.kind) for span in result.spans]


@pytest.mark.parametrize(("language", "left", "right"), [
    ("de", "\u201e", "\u201c"),
    ("de", "»", "«"),
    ("de", "«", "»"),
    ("en", "\u201c", "\u201d"),
    ("en", "\u2018", "’"),
    ("en", '"', '"'),
    ("fr", "«", "»"),
    ("es", "«", "»"),
    ("it", "«", "»"),
    ("it", "\u201c", "\u201d"),
    ("pt", "«", "»"),
    ("pt", "\u201c", "\u201d"),
    ("nl", "\u201c", "\u201d"),
    ("nl", "\u2018", "’"),
    ("nl", "\u201e", "\u201d"),
])
def test_approved_pairs_span_physical_paragraph_boundaries(language, left, right):
    content = "First paragraph.\r\n\r\nSecond paragraph."
    text = f"Before {left}{content}{right} after."
    analysis = scan_quotations(text, language)
    assert sections(text, analysis) == [(content, "quotation")]
    assert analysis.quote_ranges == ((8, 8 + len(content)),)
    assert analysis.spans[0].marker == f"{left}…{right}"
    assert not analysis.unclear


@pytest.mark.parametrize(("language", "left", "continuation", "right"), [
    ("en", "\u201c", "\u201c", "\u201d"),
    ("en", '"', '"', '"'),
    ("fr", "«", "«", "»"),
    ("fr", "«", "»", "»"),
    ("es", "«", "»", "»"),
    ("nl", "\u2018", "\u2018", "’"),
])
def test_paragraph_initial_continuation_completes_one_passage(language, left, continuation, right):
    content = f"First paragraph.\n\n{continuation}Second paragraph."
    text = f"{left}{content}{right}"
    analysis = scan_quotations(text, language)
    assert sections(text, analysis) == [(content, "quotation")]
    assert not analysis.unclear


def test_nested_de_and_en_count_each_measured_token_once():
    for language, text in [
        ("de", "Vorher \u201eSie rief \u201aHalt!\u2018 und wartete.\u201c Nachher."),
        ("en", "Before \u201cShe said \u2018Stop!’ and waited.\u201d After."),
    ]:
        analysis = scan_quotations(text, language)
        pattern = compile_word_pattern(r"\w+")
        assert len(analysis.spans) == 2
        assert len(analysis.quote_ranges) == 1
        assert count_quoted_words(text, pattern, analysis.spans) == 5
        assert quoted_word_counts(text, pattern, analysis.spans) == (5,)
        quoted, outside = partition_quoted_words(text, pattern, analysis.spans)
        assert len(quoted[0]) == 5
        assert len(outside) == 2


@pytest.mark.parametrize(("language", "text", "expected"), [
    ("en", "“first draft\" then “recovered correctly”.", ("recovered correctly",)),
    ("de", "\u201efalsches Paar« dann »richtiges Paar«.", ("richtiges Paar",)),
    ("en", "“unfinished paragraph\n\nStill open.", ()),
    ("en", "“unclosed nesting \u2018inside\u201d", ()),
])
def test_mismatched_pairs_are_unknown_and_later_valid_pairs_can_recover(language, text, expected):
    analysis = scan_quotations(text, language)
    assert tuple(content for content, _ in sections(text, analysis)) == expected
    assert analysis.unclear[0][0] == 0
    for start, end in analysis.unclear:
        assert 0 <= start < end <= len(text)


@pytest.mark.parametrize("text", ["Es war gut.\u201c\n\nSie übt.", "\u201c\n\nSie übt."])
def test_dual_use_orphan_delimiter_does_not_swallow_the_next_paragraph(text):
    analysis = scan_quotations(text, "de")
    assert not analysis.spans
    assert analysis.unclear == ((text.index("\u201c"), text.index("\u201c") + 1),)


def test_escaped_ascii_marks_do_not_open_or_close_quotes():
    text = r'Before \"literal\" then "an escaped \" in discourse".'
    analysis = scan_quotations(text, "en")
    assert sections(text, analysis) == [(r'an escaped \" in discourse', "quotation")]
    assert not analysis.unclear


@pytest.mark.parametrize(("language", "text", "content"), [
    ("en", "The 12\" pipe. \u2018I can’t go. ’Twas late.’", "I can’t go. ’Twas late."),
    ("en", "It’s 1988. In ’90s style. 'I can\'t go.'", "I can't go."),
    ("fr", "Aujourd’hui, l’objectif est « l’approche ». ", " l’approche "),
    ("it", "L’autore scrisse «l’ultimo giorno».", "l’ultimo giorno"),
    ("nl", "'s Morgens 'k zeg \u2018Ik kom ’t halen.’", "Ik kom ’t halen."),
])
def test_word_apostrophes_and_dimensions_are_not_quote_boundaries(language, text, content):
    analysis = scan_quotations(text, language)
    assert sections(text, analysis) == [(content, "quotation")]
    assert not analysis.unclear


@pytest.mark.parametrize("language", ["fr", "es", "it", "pt"])
def test_physical_line_starts_and_long_dash_narrator_interruption(language):
    text = "Narration.\n— Prima — interjection. — Fin.\n— Seconde.\n- Liste."
    if language == "es":
        text = text.replace("— Prima", "—Prima").replace("— interjection. — Fin.", "—interjection—. Fin.")
    analysis = scan_quotations(text, language)
    assert sections(text, analysis) == [
        ("Prima", "marked_speech"),
        ("Fin.", "marked_speech"),
        ("Seconde.", "marked_speech"),
    ]
    assert [span.marker for span in analysis.spans] == ["—", "—", "—"]
    assert not analysis.unclear


def test_ambiguous_extra_dash_limited_to_one_line_and_later_replies_recover():
    text = "— Bonjour — adieu.\nNarration.\n— Cela continue."
    analysis = scan_quotations(text, "fr")
    assert sections(text, analysis) == [("Bonjour", "marked_speech"), ("Cela continue.", "marked_speech")]
    assert tuple(text[start:end] for start, end in analysis.unclear) == ("— adieu.",)


def test_spanish_raya_and_quoted_continuation_are_bound_to_a_marked_reply():
    text = "\u2015Hola.\n\n»Sigo.\n\nNarración.\n\n»Sin comienzo."
    analysis = scan_quotations(text, "es")
    assert sections(text, analysis) == [("Hola.", "marked_speech"), ("Sigo.", "marked_speech")]
    assert len(analysis.unclear) == 1
    assert text[slice(*analysis.unclear[0])] == "»"


def test_non_speech_dashes_and_mixed_quoted_conversation():
    text = "- Liste\n\n———\n\n1930 – 1940\n\n« Début.\n— Suite.\nFin. »"
    analysis = scan_quotations(text, "fr")
    assert sections(text, analysis) == [(" Début.\n— Suite.\nFin. ", "quotation")]
    assert scan_quotations("— Sie sah weg.", "de") == QuotationAnalysis()


def test_custom_pattern_overrides_all_default_delimiters_and_retains_capture_contract():
    text = '“Default”\n— Extra\n{known} and [optional]'
    pattern = compile_pattern(r"\{([^}]+)\}|\[([^\]]+)\]")
    analysis = scan_quotations(text, "es", pattern=pattern)
    assert sections(text, analysis) == [("known", "custom")]
    assert analysis.empty_matches == (text.index("["),)
    assert scan_quotations(text, "es", pattern=compile_pattern("")) == QuotationAnalysis()
    full = scan_quotations(text, "es", pattern=compile_pattern(r"known"))
    assert sections(text, full) == [("known", "custom")]


def test_word_membership_uses_effective_capture_and_original_scope():
    text = 'She said, "Come." He said, "Rest."'
    analysis = scan_quotations(text, "en")
    assert count_quoted_words(text, compile_word_pattern(r"^(\w+)"), analysis.spans) == 0
    assert quoted_word_counts(text, compile_word_pattern(r"\w+"), analysis.spans) == (1, 1)
    # The match can sit outside while its capture sits inside the quote.
    text = '"word"X'
    analysis = scan_quotations(text, "en")
    assert count_quoted_words(text, compile_word_pattern(r'(?<=(word)")X'), analysis.spans) == 1
    # The delimiter straddles the token and cannot supply quote words.
    assert count_quoted_words(text, compile_word_pattern(r'.word.'), analysis.spans) == 0


def test_empty_word_matches_remain_in_the_configured_denominator():
    text = '"word" X'
    analysis = scan_quotations(text, "en")
    pattern = re.compile(r"(word)|X")
    quoted, outside = partition_quoted_words(text, pattern, analysis.spans)
    assert quoted == [["word"]]
    assert outside == [""]
    assert len(quoted[0]) + len(outside) == len(pattern.findall(text))
