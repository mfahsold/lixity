"""Nominal ending cues include the listed noun's regular plural form."""

import pytest

from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds


@pytest.mark.parametrize(
    ("language", "singular", "plural"),
    [
        ("de", "Die Entscheidung", "Die Entscheidungen"),
        ("en", "A decision", "Some decisions"),
        ("fr", "La décision", "Les décisions"),
        ("es", "La decisión", "Las decisiones"),
        ("it", "La decisione", "Le decisioni"),
        ("pt", "A decisão", "As decisões"),
        ("nl", "De beslissing", "De beslissingen"),
    ],
)
def test_plural_nominal_cues_reach_metrics_and_exact_evidence(language, singular, plural):
    text = f"## Reference\n\n{singular}.\n\n{plural}.\n"
    analysis = analyze_document(
        text, CorpusConfig(language=language), FingerprintThresholds(), include_evidence=True,
    )
    assert analysis.metrics.nominalization_density == 500
    assert analysis.metrics.chapters[0].nominalization_density == 500
    assert analysis.evidence is not None
    for paragraph, evidence, phrase in zip(
        analysis.paragraphs, analysis.evidence.values(), (singular, plural), strict=True,
    ):
        assert paragraph.nominal_density == 500
        nominal = evidence["layers"]["nominal"]
        assert nominal["count"] == nominal["mapped_count"] == 1
        assert [paragraph.text[s["start"]:s["end"]] for s in nominal["spans"]] == [phrase.split()[1]]
