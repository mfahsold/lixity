"""Explicit future scene assignments must not fabricate observations."""

import copy

import pytest

from lixity import api
from lixity.language import get_language_profile
from lixity.ui.narration import render_scenes_panel

TEXT = "## First\n\nA door opens. Rain falls.\n\n## Second\n\nThe quiet garden holds its breath."
BASE = {"assignments": {"1:1": "voice", "2:1": "voice"}, "groups": {"voice": {}}}


def report(text=TEXT, settings=None):
    return api.scenes(text, project_config={"scene_analysis": BASE if settings is None else settings})["scenes"]


def test_explicit_plans_preserve_measured_rows_and_references():
    expected = report()
    settings = copy.deepcopy(BASE)
    settings["assignments"].update({"10:2": "voice", "3:1": "voice"})
    settings["planned"] = ["10:2", "3:1"]
    before = copy.deepcopy(settings)
    actual = report(settings=settings)
    assert actual["items"] == expected["items"]
    assert actual["baselines"] == expected["baselines"]
    assert actual["baselines"]["voice"]["asl"]["n"] == 2
    assert actual["planned_items"] == [
        {"id": "3:1", "chapter": 3, "scene": 1, "group": "voice", "state": "planned"},
        {"id": "10:2", "chapter": 10, "scene": 2, "group": "voice", "state": "planned"},
    ]
    assert settings == before
    assert "planned_items" not in expected


def test_unlisted_missing_assignment_still_fails_with_plans_present():
    settings = copy.deepcopy(BASE)
    settings["assignments"].update({"3:1": "voice", "4:1": "voice"})
    settings["planned"] = ["3:1"]
    with pytest.raises(ValueError, match="4:1"):
        report(settings=settings)


def test_a_plan_becomes_measured_only_when_text_is_available():
    settings = copy.deepcopy(BASE)
    settings["assignments"]["3:1"] = "voice"
    settings["planned"] = ["3:1"]
    before = report(settings=settings)
    after = report(TEXT + "\n\n## Third\n\nA window opens. Day begins.", settings)
    assert [item["id"] for item in before["planned_items"]] == ["3:1"]
    assert after["planned_items"] == []
    assert after["items"][-1]["id"] == "3:1"
    assert after["baselines"]["voice"]["asl"]["n"] == 3
    assert "state" not in after["items"][-1]


@pytest.mark.parametrize("planned", [None, True, "3:1", {}, ["0:1"], ["3:01"], [1],
                                     ["3:1", "3:1"], ["4:1"]])
def test_malformed_or_unassigned_plan_is_rejected(planned):
    settings = copy.deepcopy(BASE)
    settings["assignments"]["3:1"] = "voice"
    settings["planned"] = planned
    with pytest.raises(ValueError, match=r"[Pp]lanned"):
        report(settings=settings)


def test_empty_plan_preserves_ordinary_response():
    settings = {**BASE, "planned": []}
    assert report(settings=settings) == report()


@pytest.mark.parametrize("locale", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_pending_only_panel_is_localized_reversible_and_has_no_fake_measurements(locale):
    group = '<img src=x onerror="bad()">'
    settings = {"assignments": {"1:1": group}, "groups": {group: {}}, "planned": ["1:1"]}
    scenes = report("", settings)
    assert scenes["items"] == []
    assert all(value["n"] == 0 and value["median"] is None
               for value in scenes["baselines"][group].values())
    labels = get_language_profile(locale).labels
    html = render_scenes_panel(scenes, labels, locale)
    assert '<details class="scene-planned">' in html
    assert "<summary>" in html and "1:1" in html
    assert labels["scene_planned"] in html
    assert labels["scene_planned_note"] in html
    assert "&lt;img" in html and "<img" not in html
    assert "<table" not in html
    assert 'href="#ch-1"' not in html
    assert "scene_planned" not in html


@pytest.mark.parametrize("identifier", ["1:1٢", "1٢:1", "01:1", "1:01", "0:1", "1:0"])
def test_planning_cannot_introduce_noncanonical_scene_ids(identifier):
    settings = {"assignments": {identifier: "voice"}, "groups": {"voice": {}}, "planned": [identifier]}
    with pytest.raises(ValueError, match="Scene assignment keys"):
        report(settings=settings)
