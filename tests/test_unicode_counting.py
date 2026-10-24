"""Canonical-equivalent prose keeps measurements and original-source spans."""

from dataclasses import asdict
from hashlib import sha256
from unicodedata import normalize

import pytest

from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds
from lixity.syllables import count_syllables

CASES = [
    ("de", "Die schöne Tür öffnet sich zur Untersuchung.", 7),
    ("en", "The café serves naïve guests.", 5),
    ("fr", "Une école célèbre prépare une décision.", 6),
    ("es", "El niño salió después de la decisión.", 7),
    ("it", "La città è vicina all'università.", 5),
    ("pt", "A saúde melhora após a decisão.", 6),
    ("nl", "De reünie beïnvloedt de beslissing.", 5),
]


@pytest.mark.parametrize(("language", "sentence", "words"), CASES)
def test_equivalent_unicode_counts_match_without_rewriting_source(language, sentence, words):
    originals = [normalize(form, "## Reference\n\n🧭 " + sentence + "\n") for form in ("NFC", "NFD")]
    analyses = [analyze_document(text, CorpusConfig(language=language), FingerprintThresholds(),
                                include_evidence=True) for text in originals]
    for result, original in zip(analyses, originals, strict=True):
        assert result.metrics.tokens == words
        assert result.metrics.total_sentences == 1
        assert result.metrics.raw_chars == len(original)
        assert result.paragraphs[0].text == original.split("\n\n", 1)[1].strip()
    # Raw source character counts intentionally retain the supplied encoding.
    excluded = {"raw_chars", "clean_chars"}
    assert analyses[0].metrics.model_dump(exclude=excluded) == analyses[1].metrics.model_dump(exclude=excluded)
    for result in analyses:
        assert result.evidence is not None
        paragraph = result.paragraphs[0]
        evidence = result.evidence[0]
        assert evidence["paragraph_sha256"] == sha256(paragraph.text.encode()).hexdigest()
        assert evidence["layers"]["asl"]["spans"][0]["words"] == words
        assert all(layer["status"] == "available" for layer in evidence["layers"].values())
    left, right = analyses
    assert {k:v for k,v in asdict(left.paragraphs[0]).items() if k != "text"} == {
        k:v for k,v in asdict(right.paragraphs[0]).items() if k != "text"}
    for key in left.evidence[0]["layers"]:
        expected = [left.paragraphs[0].text[s["start"]:s["end"]]
                    for s in left.evidence[0]["layers"][key]["spans"]]
        actual = [normalize("NFC", right.paragraphs[0].text[s["start"]:s["end"]])
                  for s in right.evidence[0]["layers"][key]["spans"]]
        assert actual == expected


@pytest.mark.parametrize(("language", "word"), [
    ("de", "schöne"), ("en", "café"), ("fr", "célèbre"), ("es", "niño"),
    ("it", "città"), ("pt", "saúde"), ("nl", "reünie"),
])
def test_syllable_dispatch_is_canonically_equivalent(language, word):
    assert count_syllables(word, language) == count_syllables(normalize("NFD", word), language)


def test_configured_patterns_keep_flags_and_map_to_original_canonical_clusters():
    source = "## Reference\n\ncafe\u0301 CAFE\u0301.\n"
    result = analyze_document(source, CorpusConfig(language="fr", word_regex=r"\bCAFÉ\b",
                                                 nominal_regex="é"),
                              FingerprintThresholds(), include_evidence=True)
    assert result.metrics.tokens == result.paragraphs[0].words == 1
    assert result.evidence is not None
    nominal = result.evidence[0]["layers"]["nominal"]
    assert nominal["count"] == nominal["mapped_count"] == 2
    assert [result.paragraphs[0].text[s["start"]:s["end"]] for s in nominal["spans"]] == ["e\u0301", "E\u0301"]


def test_ambiguous_inner_cluster_match_preserves_count_without_a_guessed_range():
    result = analyze_document("## Reference\n\na\u0308\u0301.\n",
                              CorpusConfig(language="de", nominal_regex="ä"),
                              FingerprintThresholds(), include_evidence=True)
    assert result.metrics.nominalization_density == 1000
    assert result.evidence is not None
    nominal = result.evidence[0]["layers"]["nominal"]
    assert nominal == {"status": "unavailable", "kind": "pattern", "count": 1,
                       "mapped_count": 0, "spans": [], "reason": "unicode_mapping_unavailable"}
