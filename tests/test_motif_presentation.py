"""Local echoes keep their own counts and chapter-prose locations in human views."""

import json
import re
from xml.etree import ElementTree

import pytest

from lixity.cli import main
from lixity.language import get_language_profile
from lixity.models import CorpusConfig
from lixity.motifs import motif_report
from lixity.ui.narration import render_motifs_panel

LOCALES = ("en", "de", "fr", "es", "it", "pt", "nl")
LOCAL = "## First chapter\n\nsilver lantern shines. blue river flows. silver lantern shines.\n"
GLOBAL = LOCAL + "\n## Second chapter\n\nsilver lantern shines.\n"


@pytest.mark.parametrize("locale", LOCALES)
def test_echo_only_panel_keeps_local_count_inclusive_bounds_and_chapter_navigation(locale):
    labels = get_language_profile(locale).labels
    report = motif_report(LOCAL, config=CorpusConfig(language="en")).to_dict()
    assert report["repeated_phrases"] == []
    rendered = render_motifs_panel(report, labels)
    assert rendered, "Two local hits must stay visible below the global three-hit threshold"
    panel = ElementTree.fromstring(rendered)  # noqa: S314
    table = panel.find("./div[@class='table-wrap motif-echoes']/table")
    assert table is not None
    rows = [["".join(cell.itertext()) for cell in row] for row in table.findall("./tbody/tr")]
    assert rows == [["silver lantern shines", "1", "2", "1–9"]]
    assert labels["mot_echo_count"] in "".join(table.itertext())
    assert labels["mot_echo_words"] in "".join(table.itertext())
    assert "300" in "".join(panel.itertext())
    link = table.find("./tbody/tr/td/a")
    assert link.attrib["href"] == link.attrib["data-jump"] == "#ch-1"
    assert not any("data-line" in element.attrib or "data-start" in element.attrib for element in panel.iter())


def test_global_phrase_total_and_local_cluster_count_remain_separate():
    report = motif_report(GLOBAL, config=CorpusConfig(language="en")).to_dict()
    panel = ElementTree.fromstring(render_motifs_panel(report))  # noqa: S314
    global_table = panel.find("./div[@class='table-wrap motif-phrases']/table")
    local_table = panel.find("./div[@class='table-wrap motif-echoes']/table")
    assert global_table is not None and local_table is not None
    assert [cell.text for cell in global_table.findall("./tbody/tr/td")] == ["silver lantern shines", "3", "1, 2"]
    assert ["".join(cell.itertext()) for cell in local_table.findall("./tbody/tr/td")] == ["silver lantern shines", "1", "2", "1–9"]
    assert "Manuscript count" in "".join(global_table.itertext())
    assert "Local count" in "".join(local_table.itertext())


@pytest.mark.parametrize("locale", ("en", "de"))
def test_cli_exposes_the_existing_local_echo_below_global_threshold(tmp_path, monkeypatch, capsys, locale):
    monkeypatch.setenv("LIXITY_LANG", locale)
    monkeypatch.setenv("COLUMNS", "160")
    path = tmp_path / "synthetic.md"
    path.write_text(LOCAL, encoding="utf-8")
    assert main(["motifs", str(path), "--language", "en"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert re.search(r"silver lantern shines\s+1\s+2\s+1–9", output.out)
    labels = get_language_profile(locale).labels
    assert labels["mot_echoes"] in output.out
    assert labels["mot_echo_count"] in output.out
    assert labels["mot_echo_words"] in output.out
    assert "300" in output.out


def test_cli_distinguishes_global_three_from_local_two_and_keeps_echo_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LIXITY_LANG", "en")
    monkeypatch.setenv("COLUMNS", "160")
    path = tmp_path / "synthetic.md"
    path.write_text(GLOBAL, encoding="utf-8")
    assert main(["motifs", str(path)]) == 0
    output = capsys.readouterr()
    assert "Manuscript count" in output.out and "Local count" in output.out
    assert re.search(r"silver lantern shines\s+3\s+1, 2", output.out)
    assert re.search(r"silver lantern shines\s+1\s+2\s+1–9", output.out)
    assert main(["motifs", str(path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"meta", "language", "chapters", "motifs", "top_words", "repeated_phrases", "echoes"}
    assert data["echoes"] == [{"term": "silver lantern shines", "chapter": 1, "count": 2, "first_word": 1, "last_word": 9}]


@pytest.mark.parametrize("text", ("", "## One\n\nsilver lantern shines.\n\n## Two\n\nsilver lantern shines."))
def test_absent_local_echoes_do_not_invent_a_zero_result(tmp_path, monkeypatch, capsys, text):
    monkeypatch.setenv("LIXITY_LANG", "en")
    path = tmp_path / "synthetic.md"
    path.write_text(text, encoding="utf-8")
    report = motif_report(text, config=CorpusConfig(language="en")).to_dict()
    assert render_motifs_panel(report) == ""
    assert main(["motifs", str(path)]) == 0
    assert "Local phrase echoes" not in capsys.readouterr().out
