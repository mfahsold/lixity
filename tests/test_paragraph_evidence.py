"""Literal paragraph evidence uses the same configured counters and exact text."""

import importlib
import importlib.util
from dataclasses import replace
from hashlib import sha256

import pytest

from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document, profile_document
from lixity.style_fingerprint import FingerprintThresholds


def build(text, **settings):
    config = CorpusConfig(language="en", **settings)
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    spec = importlib.util.find_spec("lixity.paragraph_evidence")
    assert spec is not None, "Shared literal evidence builder is missing"
    module = importlib.import_module("lixity.paragraph_evidence")
    return paragraphs, module.paragraph_evidence(text, config, paragraphs)


def slices(paragraph, layer):
    return [(paragraph.text[span["start"]:span["end"]], span["count"])
            for span in layer["spans"]]


def test_repeated_unicode_tokens_and_sentences_keep_their_exact_occurrences():
    paragraphs, evidence = build('## Example\n\n🧭 I think I can. I think I can.\n')
    paragraph, result = paragraphs[0], evidence[0]
    assert result["schema_version"] == "paragraph-evidence/1"
    assert result["offset_unit"] == "unicode_codepoint"
    assert result["paragraph_sha256"] == sha256(paragraph.text.encode()).hexdigest()
    layers = result["layers"]
    assert set(layers) == {"asl", "function", "dialogue", "filter", "modal", "nominal", "passive"}
    assert slices(paragraph, layers["asl"]) == [("🧭 I think I can.", 1), ("I think I can.", 1)]
    assert [span["words"] for span in layers["asl"]["spans"]] == [4, 4]
    assert slices(paragraph, layers["filter"]) == [("think", 1), ("think", 1)]
    assert [s["start"] for s in layers["filter"]["spans"]] == [4, 19]
    assert slices(paragraph, layers["modal"]) == [("can", 1), ("can", 1)]
    assert layers["dialogue"] == {
        "status": "available", "kind": "dialogue", "count": 0, "mapped_count": 0, "spans": [],
    }


def test_capturing_custom_patterns_keep_full_matches_and_nominal_exclusions():
    paragraphs, evidence = build(
        '## Example\n\nI THINK I was seen. "You can go."\n',
        filter_verbs_regex=r"\b(think)\b", passive_regex=r"\b(was) seen\b",
        nominal_regex=r"\b(I)\b",
    )
    paragraph, layers = paragraphs[0], evidence[0]["layers"]
    assert slices(paragraph, layers["filter"]) == [("THINK", 1)]
    assert slices(paragraph, layers["passive"]) == [("was seen", 1)]
    assert slices(paragraph, layers["nominal"]) == [("I", 1), ("I", 1)]
    assert slices(paragraph, layers["dialogue"]) == [("You can go.", 3)]
    assert layers["dialogue"]["count"] == 3
    assert layers["dialogue"]["kind"] == "dialogue"


def test_inline_code_and_link_destinations_are_not_silently_counted_or_guessed():
    paragraphs, evidence = build('## Example\n\nI think `think` [think](https://think.example).\n')
    layer = evidence[0]["layers"]["filter"]
    assert paragraphs[0].filter_density == 666.7
    assert layer == {"status": "unavailable", "kind": "pattern", "count": 2,
                     "mapped_count": 0, "spans": [], "reason": "inline_mapping_unavailable"}
    assert evidence[0]["layers"]["passive"]["status"] == "available"
    assert evidence[0]["layers"]["passive"]["count"] == 0


def test_zero_width_matches_preserve_counts_but_never_invent_highlights():
    paragraphs, evidence = build('## Example\n\nI think twice.\n',
                                filter_verbs_regex=r"(?=think)|twice")
    layer = evidence[0]["layers"]["filter"]
    assert layer["status"] == "partial" and layer["reason"] == "zero_width_matches"
    assert (layer["count"], layer["mapped_count"]) == (2, 1)
    assert slices(paragraphs[0], layer) == [("twice", 1)]


def test_default_nominal_function_word_exclusions_and_empty_patterns():
    paragraphs, evidence = build('## Example\n\nThis station can wait.\n',
                                filter_verbs_regex="", passive_regex="")
    layers = evidence[0]["layers"]
    assert slices(paragraphs[0], layers["nominal"]) == [("station", 1)]
    assert layers["filter"]["status"] == "available" and layers["filter"]["count"] == 0
    assert layers["passive"]["status"] == "available" and layers["passive"]["count"] == 0


def test_counted_word_capture_uses_the_capture_range_not_its_prefix():
    paragraphs, evidence = build('## Example\n\nx-can I x-can.\n',
                                word_regex=r"\b(?:x-)?(can|I)\b")
    assert paragraphs[0].words == 3
    assert slices(paragraphs[0], evidence[0]["layers"]["modal"]) == [("can", 1), ("can", 1)]
    assert [span["start"] for span in evidence[0]["layers"]["modal"]["spans"]] == [2, 10]
    assert evidence[0]["layers"]["asl"]["spans"][0]["words"] == 3


def test_default_nominal_exclusions_apply_to_literal_spans_too():
    text = '## Beispiel\n\nNUR, nur. Kultur, Entscheidung.\n'
    config = CorpusConfig(language="de")
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    module = importlib.import_module("lixity.paragraph_evidence")
    evidence = module.paragraph_evidence(text, config, paragraphs)
    assert slices(paragraphs[0], evidence[0]["layers"]["nominal"]) == [
        ("Kultur", 1), ("Entscheidung", 1),
    ]


def test_all_zero_width_pattern_matches_are_unavailable_not_measured_zero():
    _, evidence = build('## Example\n\nI think twice.\n', filter_verbs_regex=r"(?=think)")
    assert evidence[0]["layers"]["filter"] == {
        "status": "unavailable", "kind": "pattern", "count": 1,
        "mapped_count": 0, "spans": [], "reason": "zero_width_matches",
    }


def test_multiple_captures_count_whole_pattern_occurrences_without_tuple_offsets():
    paragraphs, evidence = build('## Example\n\nI think I felt movement.\n',
                                filter_verbs_regex=r"(think)|(felt)",
                                nominal_regex=r"(think)|(movement)")
    assert slices(paragraphs[0], evidence[0]["layers"]["filter"]) == [("think", 1), ("felt", 1)]
    assert slices(paragraphs[0], evidence[0]["layers"]["nominal"]) == [
        ("think", 1), ("movement", 1),
    ]


def test_sentence_splitter_keeps_abbreviations_and_quoted_closers():
    paragraphs, evidence = build('## Example\n\nDr. May said "Go!" Then I left.\n')
    assert slices(paragraphs[0], evidence[0]["layers"]["asl"]) == [
        ('Dr. May said "Go!"', 1), ("Then I left.", 1),
    ]


def test_stale_source_profiles_are_unavailable_instead_of_relocated():
    text = '## Example\n\nI think twice.\n'
    paragraphs, _ = build(text)
    module = importlib.import_module("lixity.paragraph_evidence")
    changed = [replace(paragraphs[0], text="Other source.")]
    evidence = module.paragraph_evidence(text, CorpusConfig(language="en"), changed)[0]
    assert evidence["paragraph_sha256"] == sha256(b"Other source.").hexdigest()
    assert all(layer["status"] == "unavailable" and layer["reason"] == "source_mismatch"
               and layer["spans"] == [] and layer["count"] is None
               for layer in evidence["layers"].values())


def test_pipeline_collects_evidence_only_when_requested_from_the_profile_pass():
    text = '## Example\n\nI think twice.\n'
    config = CorpusConfig(language="en", filter_verbs_regex=r"twice")
    thresholds = FingerprintThresholds()
    ordinary = analyze_document(text, config, thresholds)
    assert ordinary.evidence is None
    result = analyze_document(text, config, thresholds, include_evidence=True)
    assert result.evidence is not None
    assert slices(result.paragraphs[0], result.evidence[0]["layers"]["filter"]) == [("twice", 1)]
    assert ordinary.paragraphs == result.paragraphs
    assert "text" not in result.evidence[0]


@pytest.mark.parametrize("language", ["de", "fr", "es", "it", "pt", "nl", "generic"])
def test_all_resolved_languages_keep_count_coverage_invariants(language):
    text = '## Example\n\n"The station can wait." I think the door was opened.\n'
    config = CorpusConfig(language=language)
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    module = importlib.import_module("lixity.paragraph_evidence")
    evidence = module.paragraph_evidence(text, config, paragraphs)[0]
    for layer in evidence["layers"].values():
        assert layer["mapped_count"] == sum(span["count"] for span in layer["spans"])
        assert layer["status"] == "available" and layer["mapped_count"] == layer["count"]
        assert all(0 <= span["start"] < span["end"] <= len(paragraphs[0].text)
                   for span in layer["spans"])
