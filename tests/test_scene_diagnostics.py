"""Stale assignments report observed structure without accepting absent scenes."""

import json

import pytest

from lixity import api
from lixity.cli import main
from lixity.models import CorpusConfig
from lixity.scenes import scene_report_for_display


def assignment(identifier):
    return {"scene_analysis": {"assignments": {identifier: "voice"}, "groups": {"voice": {}}}}


def test_missing_scene_reports_actual_chapter_structure_and_recovery(tmp_path, capsys):
    text = "".join(f"## Chapter {number}\n\nA door opens.\n\n" for number in range(1, 12))
    text += "---\n\nA window closes.\n"
    path = tmp_path / "draft.md"
    path.write_text(text, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[scene_analysis.assignments]\n"11:3" = "voice"\n[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    assert main(["scenes", str(path), "--chapter", "11", "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Scene assignments no longer match this manuscript: 11:3" in captured.err
    assert "Chapter 11: 2 measured scenes (11:1, 11:2); 1 recognized scene divider." in captured.err
    assert "scene_analysis.assignments" in captured.err
    assert "scene_analysis.planned" in captured.err
    assert "standalone --- or * * *" in captured.err
    assert "Blank lines do not split scenes" in captured.err


@pytest.mark.parametrize("body,identifier,detail", [
    ("A door closes.\n\n---\n\nA window opens.", "1:3",
     "Chapter 1: 2 measured scenes (1:1, 1:2); 1 recognized scene divider."),
    ("A door closes.\n\n<!--\n---\n-->\n\n```text\n* * *\n```\n\nA window opens.", "1:2",
     "Chapter 1: 1 measured scene (1:1); 0 recognized scene dividers."),
    ("```text\nOnly code.\n```\n\n---\n\nA door closes.\n\n---\n\n```text\nTrailing code.\n```", "1:3",
     "Chapter 1: 1 measured scene (1:2); 2 recognized scene dividers."),
    ("---\n---\nA door closes.\n---\n---", "1:2",
     "Chapter 1: 1 measured scene (1:1); 4 recognized scene dividers."),
])
def test_diagnostic_counts_follow_shared_parser_and_only_measured_prose(body, identifier, detail):
    text = "## Not a scene count 99\n\n" + body
    settings = assignment(identifier)
    with pytest.raises(ValueError) as failure:
        api.scenes(text, project_config=settings)
    assert detail in str(failure.value)
    # The dashboard uses the exact same failure while retaining the reader.
    display = scene_report_for_display(text, CorpusConfig(), settings["scene_analysis"])
    assert display == {"error": str(failure.value)}
    page = api.dashboard(text, project_config=settings)
    assert detail in page
    assert 'id="ch-1"' in page


def test_absent_chapter_is_not_reported_as_an_observed_empty_chapter(tmp_path, capsys):
    path = tmp_path / "draft.md"
    path.write_text("## First\n\nA door closes.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[scene_analysis.assignments]\n"9:1" = "voice"\n[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    assert main(["scenes", str(path), "--chapter", "1", "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Chapter 9 is not present in this manuscript." in captured.err
    assert "Chapter 9: 0 measured scenes" not in captured.err


def test_explicit_plan_still_has_no_measurements_and_does_not_change_scene_ids(tmp_path, capsys):
    text = "## First\n\nA door closes.\n\n---\n\nA window opens.\n"
    path = tmp_path / "draft.md"
    path.write_text(text, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[scene_analysis]\nplanned = ["1:3"]\n'
        '[scene_analysis.assignments]\n"1:3" = "voice"\n[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    assert main(["scenes", str(path), "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    report = json.loads(captured.out)["scenes"]
    assert [item["id"] for item in report["items"]] == ["1:1", "1:2"]
    assert report["items"] == api.scenes(text)["scenes"]["items"]
    assert report["planned_items"] == [
        {"id": "1:3", "chapter": 1, "scene": 3, "group": "voice", "state": "planned"}]
