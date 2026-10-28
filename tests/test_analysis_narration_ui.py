"""Narration overviews preserve coverage and provide reversible measurement access."""

from xml.etree import ElementTree

import pytest

from lixity.dialogue import dialogue_report
from lixity.language import get_language_profile
from lixity.models import CorpusConfig
from lixity.pacing import pacing_report
from lixity.scenes import scene_report
from lixity.ui.narration import render_dialogue_panel, render_pacing_panel, render_scenes_panel
from tests.locales import LOCALES


def synthetic_scenes():
    text = "\n\n".join(
        f"## Synthetic chapter {chapter}\n\n"
        + "\n\n---\n\n".join("A quiet garden waits. " * 30 for _ in range(2 if chapter <= 5 else 1))
        for chapter in range(1, 15)
    )
    return scene_report(text, CorpusConfig(language="en"), {
        "assignments": {"1:1": "voice", "1:2": "voice", "15:1": "voice"},
        "groups": {"voice": {"targets": {"asl": [2, 8]}}}, "planned": ["15:1"],
    })


@pytest.mark.parametrize("locale", LOCALES)
def test_scene_overview_links_reach_all_measurements_inside_one_closed_disclosure(locale):
    labels = get_language_profile(locale).labels
    panel = ElementTree.fromstring(render_scenes_panel(synthetic_scenes(), labels, locale))  # noqa: S314
    measurements = panel.find("./details[@class='scene-measurements']")
    assert measurements is not None, "One disclosure keeps the repeated measurement catalogue out of the overview"
    assert "open" not in measurements.attrib
    assert measurements.findtext("summary") == labels["scene_measurements"] + " (19)"
    overview = panel.find("./div[@class='table-wrap scene-overview']/table/tbody")
    details = measurements.findall("./details[@class='scene-detail']")
    assert len(overview) == len(details) == 19
    for row, detail in zip(overview, details, strict=True):
        identifier = detail.attrib["data-scene"].replace(":", "-")
        link = row.find("th/a")
        target = f"scene-metrics-{identifier}"
        assert link.attrib["href"] == link.attrib["data-jump"] == "#" + target
        assert detail.find(f"./div[@id='{target}']/table") is not None
        assert "open" not in detail.attrib and "name" not in detail.attrib
        assert len(detail.findall(".//tbody/tr")) == 16
    # Plans stay outside the measured catalogue and never acquire fabricated values.
    planned = panel.find("./details[@class='scene-planned']")
    assert planned is not None and planned.find(".//table") is None
    assert "15:1" in "".join(planned.itertext())


@pytest.mark.parametrize("count", (16, 17))
def test_dialogue_keeps_every_chapter_in_manuscript_order_including_zero_turns(count):
    text = "\n\n".join(
        f"## Synthetic chapter {number}\n\n"
        + ('"Come here." ' * number if number < count else "The garden was silent.")
        for number in range(1, count + 1)
    )
    report = dialogue_report(text, CorpusConfig(language="en")).to_dict()
    panel = ElementTree.fromstring(render_dialogue_panel(report))  # noqa: S314
    chart = panel.find("./div[@class='dist scrollable']")
    assert chart is not None, "Complete chapter coverage uses the existing bounded chart"
    assert [row.attrib["data-jump"] for row in chart] == [f"#ch-{number}" for number in range(1, count + 1)]
    assert chart[0].findtext("./span[@class='val']").endswith(" · 1 Quoted span")
    assert chart[-1].findtext("./span[@class='val']") == "0.0% · 0 Quoted spans"


@pytest.mark.parametrize("locale", LOCALES)
def test_pacing_names_the_bar_measurement_and_explains_the_existing_hook_heuristic(locale):
    labels = get_language_profile(locale).labels
    report = pacing_report('## Synthetic chapter\n\nThe garden was still.\n\n"Why?"', CorpusConfig(language="en")).to_dict()
    assert report["chapter_list"][0]["hook_score"] == 3
    panel = ElementTree.fromstring(render_pacing_panel(report, labels, locale))  # noqa: S314
    help_texts = [span.attrib["data-help"] for span in panel.findall(".//span[@class='help']")]
    assert labels.get("help_pacing_hook") and labels["help_pacing_hook"].replace("{max_words}", "8") in help_texts
    guide = panel.find("./p[@class='panel-guide']")
    assert guide is not None and "ASL" in "".join(guide.itertext())
    assert labels["pacing_scale"] in "".join(guide.itertext())
    value = panel.find("./div[@class='dist scrollable']/div/span[@class='val']")
    assert "ASL" in "".join(value.itertext())
    assert "3" in "".join(value.itertext())
