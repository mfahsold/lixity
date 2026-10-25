"""Bounded German constructions own their auxiliary and participle cues."""

import json

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.tense import TenseMatcher


@pytest.mark.parametrize(("text", "present", "past"), [
    ("Ich habe gearbeitet. Ich bin gegangen. Ich habe gegessen.", 0, 3),
    ("Ich habe gestern gearbeitet. Ich bin nach Hause gegangen. Ich habe gegessen.", 0, 3),
    ("Ich hatte gearbeitet. Ich war nach Hause gegangen.", 0, 2),
    ("Ich arbeite. Ich gehe. Ich esse.", 3, 0),
    ("Wir arbeiten. Ihr arbeitet. Du arbeitest.", 3, 0),
    ("Ich habe Bedenken. Wir haben Geschichten.", 2, 0),
    ("Ich habe gestern Bedenken. Wir haben oft Geschichten.", 2, 0),
    ("Die Tür ist geöffnet. Wir sind gewarnt.", 2, 2),
    ("Ich habe erzählt. Ich habe sie gewarnt.", 0, 2),
    ("Ich habe gearbeitet und ich gehe.", 1, 1),
    ("Ich habe eine Arbeit. Gegessen wurde später.", 1, 1),
    ("Ich habe, sie haben gearbeitet.", 1, 1),
    ("Ich habe und sie gearbeitet.", 1, 0),
    ("Ich habe. Gestern gearbeitet.", 1, 0),
    ("Ich habe\n\ngestern gearbeitet.", 1, 0),
    ("Ich habe sie gehen sehen.", 3, 0),
    ("Arbeitete er gestern?", 0, 1),
    ("ICH HABE GEARBEITET. ICH BIN GEGANGEN.", 0, 2),
    ("Ich habe geheiratet.", 1, 1),
    ("Wir sind gewarnt worden. Die Tür ist geöffnet worden.", 0, 2),
    ("Uns ist gestern erzählt worden.", 0, 1),
    ("Wir waren gewarnt worden.", 0, 1),
    ("Wir sind gewarnt, worden ist er nicht.", 2, 1),
    ("Ich bin nach Berlin gezogen.", 1, 1),
    ("Der Stuhl ist gekippt.", 1, 1),
    ("Ich bin dort gestanden.", 1, 1),
    ("Ich bin dort gesessen.", 1, 1),
    ("Ich bin dort gelegen.", 1, 1),
    ("Ich habe die Strecke geflogen.", 1, 1),
    ("Ich habe das Rennen gelaufen.", 1, 1),
    ("Ich habe einen Salto gesprungen.", 1, 1),
    ("Ich habe es geschlossen gehalten.", 0, 1),
    ("Die Tür ist geschlossen gehalten worden.", 0, 1),
    ("Die Tür ist geschlossen gehalten worden. Die Tür ist geschlossen gehalten worden.", 0, 2),
    ("Ich habe es geschlossen gehalten, dachte er.", 0, 2),
    ("Ich habe es geschlossen und gehe.", 1, 1),
])
def test_construction_counts_across_default_scopes(text, present, past):
    config = CorpusConfig(language="de")
    assert TenseMatcher(config, resolve_language(config)).count(text) == (present, past)
    if "\n\n" in text:
        return
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks("## Reference\n\n" + text)
    )
    assert (paragraphs[0].present_hits, paragraphs[0].past_hits) == (present, past)
    assert (chapters[0].present_hits, chapters[0].past_hits) == (present, past)
    measured = CorpusAnalyzer(config).measure_unit(text)
    assert measured is not None and measured.dominance == paragraphs[0].dominant


@pytest.mark.parametrize("override", [{"praesens_regex": ""}, {"praeteritum_regex": ""}])
def test_explicit_override_bypasses_default_construction_resolution(override):
    config = CorpusConfig(language="de", **override)
    language = resolve_language(config)
    text = "Ich habe gearbeitet."
    assert TenseMatcher(config, language).count(text) == (
        0 if "praesens_regex" in override else 1,
        0 if "praeteritum_regex" in override else 1,
    )


def test_perfect_and_preterite_share_past_without_a_spurious_mixed_flag():
    text = (
        "## Reference\n\n"
        "Ich habe gearbeitet. Ich bin gegangen. Ich habe gegessen.\n\n"
        "Ich habe gestern gearbeitet. Ich bin nach Hause gegangen. Ich habe gegessen.\n\n"
        "Ich arbeitete. Ich ging. Ich aß.\n\n"
        "Ich arbeite. Ich gehe. Ich esse."
    )
    paragraphs, _ = ParagraphProfiler(CorpusConfig(language="de")).profile_blocks(
        parse_markdown_blocks(text)
    )
    assert [(p.present_hits, p.past_hits, p.dominant, p.mixed) for p in paragraphs] == [
        (0, 3, "past", False), (0, 3, "past", False),
        (0, 3, "past", False), (3, 0, "present", False),
    ]
    assert [p.severity for p in paragraphs[:3]] == [0, 0, 0]
    # The actual shift from past to present remains visible.
    assert paragraphs[3].switch and paragraphs[3].severity == 1


def test_cli_reports_single_construction_counts_and_real_tense_change(tmp_path, capsys):
    source = tmp_path / "synthetic.md"
    source.write_text(
        "## Reference\n\n"
        "Ich habe gearbeitet. Ich bin gegangen. Ich habe gegessen.\n\n"
        "Ich habe gestern gearbeitet. Ich bin nach Hause gegangen. Ich habe gegessen.\n\n"
        "Ich arbeitete. Ich ging. Ich aß.\n\n"
        "Ich arbeite. Ich gehe. Ich esse."
    )
    assert main(["profile", str(source), "--language", "de", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [(p["present_hits"], p["past_hits"], p["dominant"], p["mixed"])
            for p in report["paragraphs"]] == [
        (0, 3, "past", False), (0, 3, "past", False),
        (0, 3, "past", False), (3, 0, "present", False),
    ]
    assert [p["severity"] for p in report["paragraphs"]] == [0, 0, 0, 1]


def test_german_past_label_includes_compound_tenses():
    config = CorpusConfig(language="de")
    labels = resolve_language(config).labels
    assert labels["past"] == "Vergangenheit"
    assert "Perfekt" in labels["help_past"]
