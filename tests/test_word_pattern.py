"""Configured token patterns fail clearly before tuple-valued tokens reach analysis."""

import re
from dataclasses import replace

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.language import compile_word_pattern, resolve_language
from lixity.models import CorpusConfig
from lixity.paragraph_evidence import ParagraphMatcher

MULTIPLE_CAPTURES = r"\b([A-Za-z]+)(s?)\b"
CAPTURE_ERROR = r"word_regex.*at most one capturing group.*noncapturing"


def test_word_compiler_rejects_tuple_valued_matches_with_actionable_error():
    with pytest.raises(ValueError, match=CAPTURE_ERROR):
        compile_word_pattern(MULTIPLE_CAPTURES)


def test_corpus_configuration_rejects_multiple_token_captures_early():
    with pytest.raises(ValueError, match=CAPTURE_ERROR):
        CorpusConfig(word_regex=MULTIPLE_CAPTURES)


@pytest.mark.parametrize("pattern", ["(", "[a-"])
def test_word_compiler_reports_malformed_syntax_as_configuration_error(pattern):
    with pytest.raises(ValueError, match=r"word_regex.*valid regular expression"):
        compile_word_pattern(pattern)


@pytest.mark.parametrize("pattern", ["(", "[a-"])
def test_corpus_configuration_reports_malformed_word_syntax_as_value_error(pattern):
    with pytest.raises(ValueError, match=r"word_regex.*valid regular expression"):
        CorpusConfig(word_regex=pattern)


def test_analyzer_guards_unvalidated_custom_token_patterns():
    config = CorpusConfig().model_copy(update={"word_regex": MULTIPLE_CAPTURES})
    with pytest.raises(ValueError, match=CAPTURE_ERROR):
        CorpusAnalyzer(config).analyze_text("## One\n\nI can see cats.")


def test_paragraph_matcher_guards_custom_language_token_patterns():
    config = CorpusConfig()
    language = replace(resolve_language(CorpusConfig()), word_regex=MULTIPLE_CAPTURES)
    with pytest.raises(ValueError, match=CAPTURE_ERROR):
        ParagraphMatcher(config, language).count("I can see cats.")


@pytest.mark.parametrize("pattern,expected", [
    (r"\b(?:x-)?(?:can|I)\b", ["x-can", "I"]),
    (r"\b(?:x-)?(can|I)\b", ["can", "I"]),
    (r"(?i)\b(?:x-)?(can|I)\b", ["can", "I", "CAN"]),
])
def test_supported_capture_and_explicit_flag_semantics_are_preserved(pattern, expected):
    compiled = compile_word_pattern(pattern)
    assert compiled.findall("x-can I CAN.") == expected
    assert bool(compiled.flags & re.IGNORECASE) == pattern.startswith("(?i)")
    config = CorpusConfig(language="en", word_regex=pattern)
    metrics = CorpusAnalyzer(config).analyze_text("## One\n\nx-can I CAN.")
    counts = ParagraphMatcher(config, resolve_language(config)).count("x-can I CAN.")
    assert metrics.tokens == metrics.chapters[0].words == counts.words == len(expected)
