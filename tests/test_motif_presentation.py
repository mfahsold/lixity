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
from tests.locales import LOCALES

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
    assert ["".join(cell.itertext()) for cell in global_table.findall("./tbody/tr/td")] == ["silver lantern shines", "3", "1, 2"]
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
def test_absent_local_echoes_do_not_invent_echo_rows(tmp_path, monkeypatch, capsys, text):
    monkeypatch.setenv("LIXITY_LANG", "en")
    path = tmp_path / "synthetic.md"
    path.write_text(text, encoding="utf-8")
    report = motif_report(text, config=CorpusConfig(language="en")).to_dict()
    rendered = render_motifs_panel(report)
    if text:
        assert get_language_profile("en").labels["motifs_no_findings"] in rendered
        assert '<table' not in rendered
    else:
        assert rendered == ""
    assert main(["motifs", str(path)]) == 0
    assert "Local phrase echoes" not in capsys.readouterr().out


def test_motifs_output_flag_writes_file(tmp_path):
    path = tmp_path / "synthetic.md"
    out = tmp_path / "motifs.json"
    path.write_text("## One\n\nsilver lantern shines.\n", encoding="utf-8")
    assert main(["motifs", str(path), "--json", "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "top_words" in data


def test_motif_locations_and_panel_custom_search():
    from lixity.config import resolve_thresholds
    from lixity.pipeline import analyze_document

    text = (
        "## One\n\n"
        "Es ist so, dass der Nebel steigt und der kalte Brunnen glänzt. "
        "Es ist so, dass der kalte Brunnen ruft.\n\n"
        "## Two\n\n"
        "Am Fenster stand es ist so, dass der kalte Brunnen schimmerte.\n"
    )
    cfg = CorpusConfig(language="de", motif_regexes={"Nebel": r"\bNebel\b"})
    analysis = analyze_document(text, cfg, resolve_thresholds(project_config={}), include_evidence=False)
    enriched = motif_report(text, config=cfg, _paragraphs=analysis.paragraphs).to_display_dict()
    motif_rows = enriched["motifs"]
    assert len(motif_rows) == 1
    occs = motif_rows[0]["occurrences"]
    assert len(occs) == 1
    assert occs[0]["paragraph_id"] == "p-0"
    assert analysis.paragraphs[0].text[occs[0]["start"] : occs[0]["end"]].casefold() == "nebel"
    assert occs[0]["quote"] == "Nebel"
    phrase_rows = enriched["repeated_phrases"]
    assert len(phrase_rows) >= 1 and phrase_rows[0]["occurrences"]
    first_phrase_occ = phrase_rows[0]["occurrences"][0]
    p_idx = int(first_phrase_occ["paragraph_id"].split("-")[1])
    assert analysis.paragraphs[p_idx].text[first_phrase_occ["start"] : first_phrase_occ["end"]] == first_phrase_occ["quote"]
    assert 'id="motif-custom-search"' not in render_motifs_panel(enriched)
    rendered = render_motifs_panel(enriched, get_language_profile("de").labels, custom_search=True)
    panel = ElementTree.fromstring(rendered)  # noqa: S314
    assert panel.find(".//form[@id='motif-custom-search']") is not None
    assert panel.find(".//button[@data-motif-select='1']") is not None
    assert panel.find(".//a[@data-motif-jump='1']") is not None


def test_exact_locations_keep_counted_regex_scope_tokens_and_echo_cluster():
    from lixity.pipeline import document_paragraph_texts

    text = (
        "## One\n\n🌿 Silver, Cafe\u0301 gleams.\n\n"
        "> Silver Café gleams.\n\nSilver\n\nCafé gleams.\n\nsilver Café gleams.\n"
    )
    config = CorpusConfig(language="en", motif_regexes={
        "Start of a chapter": r"\ASilver",
        "Crosses a paragraph": r"Silver\n\nCafé",
        "Case-sensitive Silver": r"(?-i:Silver)",
    })
    paragraphs = document_paragraph_texts(text, config)
    public = motif_report(text, config=config, echo_window=6).to_dict()
    report = motif_report(text, config=config, echo_window=6, _paragraphs=paragraphs)
    assert report.to_dict() == public
    display = report.to_display_dict()
    motifs = {row["name"]: row for row in display["motifs"]}
    assert motifs["Start of a chapter"]["mentions"] == 0
    assert motifs["Start of a chapter"]["occurrences"] == []
    assert motifs["Crosses a paragraph"]["mentions"] == 1
    assert motifs["Crosses a paragraph"]["occurrences"] == []
    exact = motifs["Case-sensitive Silver"]
    assert (exact["mentions"], exact["mapped_occurrence_count"]) == (3, 2)
    assert [hit["paragraph_id"] for hit in exact["occurrences"]] == ["p-0", "p-1"]
    assert exact["occurrences"][0]["start"] == 2  # Unicode code points include the astral leaf.
    phrase = next(row for row in display["repeated_phrases"] if row["phrase"] == "silver café gleams")
    assert (phrase["count"], phrase["mapped_occurrence_count"]) == (4, 2)
    assert [hit["quote"] for hit in phrase["occurrences"]] == ["Silver, Cafe\u0301 gleams", "silver Café gleams"]
    echo = next(row for row in display["echoes"] if row["term"] == phrase["phrase"])
    assert (echo["count"], echo["mapped_occurrence_count"]) == (2, 1)
    assert echo["occurrences"] == phrase["occurrences"][:1]
    panel = ElementTree.fromstring(render_motifs_panel(display))  # noqa: S314
    phrase_group = panel.find(".//div[@data-motif-group='phrase-0']")
    assert phrase_group is not None and len(json.loads(phrase_group.attrib["data-motif-occurrences"])) == 2
    assert "Exact text locations are available for 2 of 4 counted matches." in "".join(phrase_group.itertext())


def test_location_cap_keeps_full_verified_count(monkeypatch):
    from lixity.pipeline import document_paragraph_texts

    monkeypatch.setattr("lixity.motifs.MAX_DISPLAY_OCCURRENCES", 2)
    text = "## One\n\nRain falls. Rain stops. Rain starts again."
    config = CorpusConfig(language="en", motif_regexes={"Rain": r"\bRain\b"})
    report = motif_report(text, config=config, _paragraphs=document_paragraph_texts(text, config)).to_display_dict()
    motif = report["motifs"][0]
    assert (motif["mentions"], motif["mapped_occurrence_count"], len(motif["occurrences"])) == (3, 3, 2)
    assert "The reader can open the first 2 of 3 matched locations." in render_motifs_panel(report)

