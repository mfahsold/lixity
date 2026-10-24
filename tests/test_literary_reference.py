"""Hand-annotated public-domain prose checks counting, not literary quality.

These seven convenience excerpts are neither a representative reference corpus
nor an independent validation of linguistic cues or readability calibration.
The expected sentence text and orthographic tokens were transcribed manually;
literal cue coverage below checks internal consistency, not grammatical truth.
"""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from lixity.cli import main
from lixity.language import compile_word_pattern, resolve_language
from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document
from lixity.sentences import split_sentences
from lixity.style_fingerprint import FingerprintThresholds

REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures" / "literary_reference.json").read_text(encoding="utf-8")
)
CASES = REFERENCE["fixtures"]


def paragraph_text(paragraph):
    return " ".join(sentence["text"] for sentence in paragraph["sentences"])


def paragraph_words(paragraph):
    return sum(len(sentence["tokens"]) for sentence in paragraph["sentences"])


@pytest.fixture(params=CASES, ids=lambda case: case["language"])
def literary_analysis(request):
    case = request.param
    text = "## Reference\n\n" + "\n\n".join(map(paragraph_text, case["paragraphs"])) + "\n"
    config = CorpusConfig(language=case["language"])
    result = analyze_document(text, config, FingerprintThresholds(), include_evidence=True)
    return case, result


def test_reference_has_explicit_provenance_and_seven_original_languages():
    assert REFERENCE["schema_version"] == "literary-reference/1"
    assert {case["language"] for case in CASES} == {"de", "en", "fr", "es", "it", "pt", "nl"}
    assert len(CASES) == 7
    for case in CASES:
        for field in ("author", "title", "source_url", "catalog_url", "source_locator",
                      "public_domain_rationale", "checked_on", "normalization"):
            assert case[field]
        assert 30 <= sum(map(paragraph_words, case["paragraphs"])) <= 80


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["language"])
def test_literary_tokens_and_sentences_match_manual_annotations(case):
    pattern = compile_word_pattern(resolve_language(CorpusConfig(language=case["language"])).word_regex)
    for paragraph in case["paragraphs"]:
        sentences = paragraph["sentences"]
        assert split_sentences(paragraph_text(paragraph), case["language"]) == [
            sentence["text"] for sentence in sentences
        ]
        for sentence in sentences:
            assert pattern.findall(sentence["text"]) == sentence["tokens"]


def test_literary_counts_agree_with_manual_scope_annotations(literary_analysis):
    case, result = literary_analysis
    paragraphs = case["paragraphs"]
    words = sum(map(paragraph_words, paragraphs))
    sentences = sum(len(paragraph["sentences"]) for paragraph in paragraphs)
    # clean_words is a documented legacy whitespace count, not regex tokens.
    assert result.metrics.tokens == words
    assert result.metrics.total_sentences == sentences
    assert result.metrics.total_paragraphs == len(paragraphs)
    assert result.metrics.asl == pytest.approx(words / sentences, abs=0.01)
    assert len(result.metrics.chapters) == len(result.chapters) == 1
    chapter = result.metrics.chapters[0]
    assert (chapter.words, chapter.sentences) == (words, sentences)
    assert chapter.asl == pytest.approx(words / sentences, abs=0.01)
    assert (result.chapters[0].words, result.chapters[0].paragraphs) == (words, len(paragraphs))
    assert len(result.paragraphs) == len(paragraphs)
    for expected, actual in zip(paragraphs, result.paragraphs, strict=True):
        assert actual.text == paragraph_text(expected)
        assert actual.words == paragraph_words(expected)
        assert actual.sentences == len(expected["sentences"])


def test_literary_literal_evidence_preserves_sentences_and_count_coverage(literary_analysis):
    case, result = literary_analysis
    assert result.evidence is not None
    assert len(result.evidence) == len(case["paragraphs"])
    for index, expected in enumerate(case["paragraphs"]):
        text = paragraph_text(expected)
        evidence = result.evidence[index]
        assert evidence["paragraph_sha256"] == sha256(text.encode("utf-8")).hexdigest()
        assert evidence["offset_unit"] == "unicode_codepoint"
        spans = evidence["layers"]["asl"]["spans"]
        assert [text[span["start"]:span["end"]] for span in spans] == [
            sentence["text"] for sentence in expected["sentences"]
        ]
        assert [span["words"] for span in spans] == [
            len(sentence["tokens"]) for sentence in expected["sentences"]
        ]
        for layer in evidence["layers"].values():
            assert layer["status"] == "available"
            assert layer["count"] == layer["mapped_count"]
            assert layer["mapped_count"] == sum(span["count"] for span in layer["spans"])
            assert all(0 <= span["start"] < span["end"] <= len(text) for span in layer["spans"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["language"])
def test_cli_reports_the_manual_literary_counts_and_sentence_evidence(case, tmp_path, capsys):
    text = "## Reference\n\n" + "\n\n".join(map(paragraph_text, case["paragraphs"])) + "\n"
    path = tmp_path / "reference.md"
    path.write_text(text, encoding="utf-8")
    original = path.read_bytes()
    assert main(["analyze", str(path), "--language", case["language"], "--json"]) == 0
    output = capsys.readouterr()
    assert not output.err
    report = json.loads(output.out)
    expected_tokens = sum(map(paragraph_words, case["paragraphs"]))
    expected_sentences = sum(len(p["sentences"]) for p in case["paragraphs"])
    assert report["meta"]["language"] == case["language"]
    assert report["metrics"]["tokens"] == expected_tokens
    assert report["metrics"]["total_sentences"] == expected_sentences
    assert report["metrics"]["asl"] == pytest.approx(expected_tokens / expected_sentences, abs=0.01)
    assert main(["profile", str(path), "--language", case["language"], "--layer", "asl",
                 "--evidence", "--json"]) == 0
    output = capsys.readouterr()
    assert not output.err
    profile = json.loads(output.out)
    assert profile["unit"] == "words per sentence"
    for row, expected in zip(profile["paragraphs"], case["paragraphs"], strict=True):
        paragraph = paragraph_text(expected)
        assert row["value"] == pytest.approx(paragraph_words(expected) / len(expected["sentences"]), abs=0.1)
        spans = row["evidence"]["layers"]["asl"]["spans"]
        assert [paragraph[s["start"]:s["end"]] for s in spans] == [s["text"] for s in expected["sentences"]]
        assert [s["words"] for s in spans] == [len(s["tokens"]) for s in expected["sentences"]]
    assert path.read_bytes() == original
