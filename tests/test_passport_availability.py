"""Text passports distinguish unavailable references from zero robust spread."""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.models import CorpusConfig
from lixity.style_fingerprint import FingerprintThresholds, StyleFingerprint


def manuscript(lengths):
    return "\n\n".join(
        f"## Chapter {index}\n\n" + ((" ".join(["garden"] * length) + ". ") * 25)
        for index, length in enumerate(lengths, start=1)
    )


def fingerprint(lengths, minimum=2):
    metrics = CorpusAnalyzer(CorpusConfig(language="en")).analyze_text(manuscript(lengths))
    return StyleFingerprint.from_metrics(metrics, FingerprintThresholds(min_chapters=minimum))


def asl_line(result, language):
    return next(line for line in result.passport_text(
        labels={"feat_asl": "ASL"}, language_key=language
    ).splitlines() if line.startswith("ASL "))


@pytest.mark.parametrize(("lengths", "minimum"), [([6], 2), ([6, 12], 3)])
@pytest.mark.parametrize("language", ["en", "de"])
def test_unsupported_reference_does_not_print_a_zero_median(lengths, minimum, language):
    result = fingerprint(lengths, minimum)
    original = result.passport()
    assert result.baseline["asl"]["n"] == len(lengths)
    row = asl_line(result, language)
    assert "–" in row
    assert f"{len(lengths)}/{minimum}" in row
    assert "reference unavailable" in row if language == "en" else "Referenz nicht verfügbar" in row
    assert "median" not in row.lower()
    assert "constant" not in row and "konstant" not in row
    assert result.passport() == original


@pytest.mark.parametrize("language", ["en", "de"])
def test_tied_zero_mad_does_not_claim_constant_chapter_values(language):
    result = fingerprint([6, 6, 6, 12])
    original = result.passport()
    assert result.baseline["asl"] == {"median": 6.0, "mad": 0.0, "sigma": 0.0, "n": 4,
                                      "comparison_status": "zero_mad_varying"}
    row = asl_line(result, language)
    assert "MAD" in row
    assert "constant" not in row and "konstant" not in row
    assert "values vary" in row if language == "en" else "unterscheiden sich" in row
    assert result.passport() == original


@pytest.mark.parametrize("language", ["en", "de"])
def test_equal_observations_remain_described_as_constant(language):
    result = fingerprint([6, 6, 6, 6])
    row = asl_line(result, language)
    assert "(constant)" in row if language == "en" else "(konstant)" in row


@pytest.mark.parametrize("language", ["en", "de"])
def test_nonzero_spread_keeps_the_existing_band(language):
    result = fingerprint([6, 8, 10, 12])
    row = asl_line(result, language)
    assert "band" in row if language == "en" else "Korridor" in row
    assert "unavailable" not in row and "nicht verfügbar" not in row


def test_real_cli_does_not_present_an_unsupported_baseline_as_constant(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "manuscript.md"
    source.write_text(manuscript([6]), encoding="utf-8")
    assert main(["style", str(source), "--language", "en"]) == 0
    output = capsys.readouterr().out
    assert "reference unavailable: 1/2" in output
    assert "(constant)" not in output
