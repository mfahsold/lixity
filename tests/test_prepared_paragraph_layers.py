"""Prepared statistical paragraph layers retain chapter-local comparison semantics."""

from types import SimpleNamespace

from lixity import style_fingerprint
from lixity.models import CorpusConfig
from lixity.pipeline import analyze_document
from lixity.style_fingerprint import FingerprintThresholds


def test_prepared_cells_round_before_notability_and_keep_chapters_independent():
    paragraphs = [
        SimpleNamespace(words=5, chapter_num=chapter, filter_density=value + offset)
        for chapter, offset in [(1, 0), (2, 100)]
        for value in [0, 1, 2, 3, 4.22]
    ]
    cells = style_fingerprint.paragraph_layer_cells(paragraphs, "filter")
    assert (cells[0].value, cells[0].z, cells[0].notable) == (0, -1.35, False)
    assert (cells[2].value, cells[2].z, cells[2].notable) == (2, 0, False)
    # Raw robust z is about 1.497; the existing reader's rounded cutoff is 1.50.
    assert (cells[4].value, cells[4].z, cells[4].notable) == (4.22, 1.5, True)
    assert cells[4].raw_z < cells[4].z
    assert (cells[9].value, cells[9].z, cells[9].notable) == (104.22, 1.5, True)


def test_prepared_cells_keep_values_and_reasons_when_comparisons_are_unavailable():
    paragraphs = [
        SimpleNamespace(words=words, chapter_num=chapter, filter_density=value)
        for chapter, words, value in [
            (1, 5, 0), (1, 5, 1), (1, 5, 2), (1, 4, 10),
            (2, 5, 0), (2, 5, 0), (2, 5, 0),
            (3, 5, 0), (3, 5, 1), (3, 0, 0),
        ]
    ]
    cells = style_fingerprint.paragraph_layer_cells(paragraphs, "filter")
    assert set(cells) == {0, 1, 2}
    assert cells[0].value == 0
    assert cells[1].z == 0
    measurements = style_fingerprint.prepare_paragraph_layers(
        paragraphs, available_layers=frozenset({"filter"}),
    )["filter"]
    assert set(measurements) == set(range(9))
    assert (measurements[3].value, measurements[3].reason) == (10, "short_paragraph")
    assert (measurements[4].value, measurements[4].reason) == (0, "zero_spread")
    assert (measurements[7].value, measurements[7].reason) == (0, "too_few_paragraphs")
    assert measurements[4].chapter_median == 0
    assert measurements[3].chapter_median is None and measurements[7].chapter_median is None
    assert all(cell.z is None and cell.raw_z is None and not cell.notable
               for index, cell in measurements.items() if index >= 3)


def test_analysis_prepares_every_layer_and_keeps_zero_distinct_from_unavailable():
    text = (
        "## Main\n\nThe wooden door opens now.\n\n"
        "The heavy iron door closes slowly.\n\n"
        "A tall window opens quietly inside the room.\n\n`OnlyCode`\n"
    )
    analysis = analyze_document(text, CorpusConfig(language="en"), FingerprintThresholds())
    assert set(analysis.paragraph_layers) == set(style_fingerprint.LAYER_FEATURES)
    assert set(analysis.paragraph_layers["asl"]) == {0, 1, 2}
    assert analysis.paragraph_layers["asl"][1].z == 0
    assert analysis.paragraph_layers["asl"][1].notable is False
    dialogue = analysis.paragraph_layers["dialogue"]
    assert len(dialogue) == 3
    assert all(cell.value == 0 and cell.z is None and cell.reason == "zero_spread"
               for cell in dialogue.values())


def test_sparse_german_pattern_keeps_measured_hits_and_chapter_median():
    text = (
        "## Anfang\n\nDie Straße lag still und dunkel.\n\n"
        "Eine Lampe hing über der Straße.\n\n"
        "Die Tür fiel hinter dem Fahrer zu.\n\n"
        "Mara legte ihre Tasche vor dem Haus ab.\n\n"
        "Ich spüre die Müdigkeit. Ich merke den Morgen und ich fühle die Sonne.\n"
    )
    analysis = analyze_document(
        text, CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+"),
        FingerprintThresholds(), include_evidence=True,
    )
    cells = analysis.paragraph_layers["filter"]
    assert [cell.value for cell in cells.values()] == [0, 0, 0, 0, 230.8]
    assert all(cell.chapter_median == 0 and cell.z is None and cell.reason == "zero_spread"
               for cell in cells.values())
    assert analysis.evidence is not None
    assert analysis.evidence[4]["layers"]["filter"]["count"] == 3
    assert style_fingerprint.layer_stats(analysis.paragraphs, "filter") == {}


def test_rounded_cutoff_preserves_positive_and_negative_boundary_ties():
    # Median 10 and MAD 1 give raw endpoint scores just below +/-1.5.
    values = [7.783, 9, 10, 11, 12.217]
    paragraphs = [
        SimpleNamespace(
            asl=value, words=10, sentences=1, chapter_num=1,
            chapter_title="Main", start_line=index + 1, end_line=index + 1,
        )
        for index, value in enumerate(values)
    ]
    cells = style_fingerprint.paragraph_layer_cells(paragraphs, "asl")
    assert [cell.z for cell in cells.values()] == [-1.5, -0.67, 0.0, 0.67, 1.5]
    assert [cell.notable for cell in cells.values()] == [True, False, False, False, True]
    report = style_fingerprint.paragraph_layer_projection(paragraphs, "asl", only_notable=True)
    assert [(row["index"], row["z"], row["notable"]) for row in report["paragraphs"]] == [
        (0, -1.5, True), (4, 1.5, True),
    ]
