"""Scene CLI selection preserves manuscript measurements and comparison context."""

import json

import orjson
import pytest

from lixity import api
from lixity.cli import main

TEXT = (
    "## Chapter99\n\n```text\nUnmeasured code.\n```\n\n---\n\nShort words end.\n\n"
    "## Empty200\n\n```text\nOnly code.\n```\n\n"
    "## Chapter5\n\nA considerably longer synthetic sentence contains more words. "
    "Another sentence closes this final section.\n\n---\n\n```text\nTrailing code.\n```\n"
)
SETTINGS = {"scene_analysis": {
    "assignments": {"1:2": "voice", "2:1": "voice"}, "groups": {"voice": {}},
}}


@pytest.fixture
def manuscript(tmp_path):
    path = tmp_path / "draft.md"
    path.write_text(TEXT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[scene_analysis.assignments]\n"1:2" = "voice"\n"2:1" = "voice"\n'
        '[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    return path


def run(capsys, *arguments):
    try:
        status = main(["scenes", *map(str, arguments)])
    except SystemExit as error:
        status = error.code
    output = capsys.readouterr()
    return status, output.out, output.err


@pytest.mark.parametrize("arguments,identifiers", [
    (("--chapter", "1"), ["1:2"]),
    (("--scene", "1:2"), ["1:2"]),
    (("--chapter", "1", "--scene", "1:2"), ["1:2"]),
    (("--latest",), ["2:1"]),
    (("--chapter", "1", "--latest"), ["1:2"]),
])
def test_selected_items_keep_original_ids_and_full_manuscript_baselines(manuscript, capsys, arguments, identifiers):
    status, output, errors = run(capsys, manuscript, "--json", *arguments)
    assert status == 0, errors
    actual = json.loads(output)
    full = api.scenes(TEXT, project_config=SETTINGS)
    assert [item["id"] for item in actual["scenes"]["items"]] == identifiers
    assert actual["scenes"]["items"] == [item for item in full["scenes"]["items"] if item["id"] in identifiers]
    assert actual["scenes"]["baselines"]["voice"]["asl"] == {"n": 2, "median": 5.0, "mad": 2.0}
    assert {key: value for key, value in actual["scenes"].items() if key not in ("items", "selection")} == {
        key: value for key, value in full["scenes"].items() if key != "items"
    }
    assert actual["scenes"]["selection"] == {
        "chapter": int(arguments[arguments.index("--chapter") + 1]) if "--chapter" in arguments else None,
        "scene": arguments[arguments.index("--scene") + 1] if "--scene" in arguments else None,
        "latest": "--latest" in arguments, "selected_count": len(identifiers),
        "total_count": 2, "reference_scope": "full_manuscript",
    }
    assert actual["meta"] == full["meta"]


def test_unfiltered_json_remains_exact(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--json")
    assert status == 0, errors
    assert output.encode() == orjson.dumps(api.scenes(TEXT, project_config=SETTINGS), option=orjson.OPT_INDENT_2) + b"\n"


@pytest.mark.parametrize("arguments", [
    ("--chapter", "0"), ("--chapter", "-1"), ("--chapter", "text"),
    ("--scene", "1"), ("--scene", "0:1"), ("--scene", "1:0"),
    ("--scene", "01:2"), ("--scene", "1:2:3"),
    ("--scene", "1:2", "--latest"),
    ("--chapter", "2", "--scene", "1:2"),
    ("--chapter", "99"), ("--scene", "1:1"),
    ("--chapter", "99", "--latest"),
])
def test_invalid_or_unmeasured_selection_fails_without_success_output(manuscript, capsys, arguments):
    status, output, errors = run(capsys, manuscript, "--json", *arguments)
    assert status != 0
    assert output == ""
    assert errors.strip()


def test_filter_does_not_hide_invalid_assignment_in_another_chapter(manuscript, capsys):
    # An existing assignment to unwritten text remains an error before selection.
    (manuscript.parent / "lixity.toml").write_text(
        '[scene_analysis.assignments]\n"9:1" = "voice"\n[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    status, output, errors = run(capsys, manuscript, "--chapter", "1", "--json")
    assert status == 1 and output == ""
    assert "9:1" in errors and "assignments" in errors


@pytest.mark.parametrize("arguments", [(), ("--latest",), ("--chapter", "1"), ("--scene", "1:1")])
def test_empty_document_only_succeeds_without_selection(tmp_path, capsys, arguments):
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")
    status, output, errors = run(capsys, path, "--json", *arguments)
    if arguments:
        assert status != 0 and output == "" and errors
    else:
        assert status == 0, errors
        assert json.loads(output)["scenes"]["items"] == []


def test_omitted_manuscript_uses_workspace_discovery_before_loading_settings(manuscript, monkeypatch, capsys):
    monkeypatch.chdir(manuscript.parent)
    status, output, errors = run(capsys, "--latest", "--json")
    assert status == 0, errors
    report = json.loads(output)["scenes"]
    assert [item["id"] for item in report["items"]] == ["2:1"]
    assert report["baselines"]["voice"]["asl"]["n"] == 2


@pytest.mark.parametrize("count", [0, 2])
def test_omitted_manuscript_without_unique_selection_fails(tmp_path, monkeypatch, capsys, count):
    for index in range(count):
        (tmp_path / f"draft-{index}.md").write_text("Synthetic prose.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    status, output, errors = run(capsys, "--json")
    assert status == 1 and output == "" and errors


def test_explicit_file_wins_over_current_workspace(tmp_path, manuscript, monkeypatch, capsys):
    other = tmp_path / "other"
    other.mkdir()
    (other / "manuscript.md").write_text("Different workspace prose.", encoding="utf-8")
    monkeypatch.chdir(other)
    status, output, errors = run(capsys, manuscript, "--scene", "1:2", "--json")
    assert status == 0, errors
    assert json.loads(output)["scenes"]["items"][0]["chapter_title"] == "Chapter99"


def test_missing_explicit_file_never_falls_back_to_current_workspace(manuscript, monkeypatch, capsys):
    monkeypatch.chdir(manuscript.parent)
    status, output, errors = run(capsys, "missing.md", "--json")
    assert status == 1 and output == "" and "missing.md" in errors


def test_chapter_selection_keeps_every_measured_scene(tmp_path, capsys):
    path = tmp_path / "draft.md"
    path.write_text("## First\n\nA door closes.\n\n---\n\nA window opens.\n\n## Second\n\nRain falls.", encoding="utf-8")
    status, output, errors = run(capsys, path, "--chapter", "1", "--json")
    assert status == 0, errors
    report = json.loads(output)["scenes"]
    assert [item["id"] for item in report["items"]] == ["1:1", "1:2"]
    assert report["selection"]["selected_count"] == 2 and report["selection"]["total_count"] == 3


def test_human_output_only_lists_selected_scene(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--scene", "1:2", "--language", "de")
    assert status == 0, errors
    assert "1:2 · Chapter99" in output and "2:1 · Chapter5" not in output
    assert "3 Wörter" in output


@pytest.fixture
def planned_manuscript(manuscript):
    (manuscript.parent / "lixity.toml").write_text(
        '[scene_analysis]\nplanned = ["2:2", "3:1"]\n'
        '[scene_analysis.assignments]\n"1:2" = "voice"\n"2:1" = "voice"\n'
        '"2:2" = "voice"\n"3:1" = "voice"\n[scene_analysis.groups.voice]\n', encoding="utf-8",
    )
    return manuscript


@pytest.mark.parametrize("arguments,measured,planned", [
    (("--chapter", "2"), ["2:1"], ["2:2"]),
    (("--scene", "3:1"), [], ["3:1"]),
    (("--latest",), ["2:1"], []),
    (("--chapter", "1", "--latest"), ["1:2"], []),
])
def test_explicit_plans_can_be_selected_without_becoming_measurements(planned_manuscript, capsys, arguments, measured, planned):
    status, output, errors = run(capsys, planned_manuscript, "--json", *arguments)
    assert status == 0, errors
    report = json.loads(output)["scenes"]
    assert [item["id"] for item in report["items"]] == measured
    assert [item["id"] for item in report["planned_items"]] == planned
    assert report["selection"]["selected_count"] == len(measured)
    assert report["selection"]["selected_planned_count"] == len(planned)
    assert report["selection"]["total_count"] == 2
    assert report["selection"]["total_planned_count"] == 2
    assert report["baselines"]["voice"]["asl"] == {"n": 2, "median": 5.0, "mad": 2.0}
    for item in report["planned_items"]:
        assert item["state"] == "planned"
        assert not {"features", "words", "sentences", "standard_errors"} & item.keys()


def test_latest_in_only_planned_chapter_is_not_a_measurement(planned_manuscript, capsys):
    status, output, errors = run(capsys, planned_manuscript, "--chapter", "3", "--latest", "--json")
    assert status == 1 and output == ""
    assert "measured" in errors.lower()


def test_planned_human_output_names_state_without_zero_measurements(planned_manuscript, capsys):
    status, output, errors = run(capsys, planned_manuscript, "--scene", "3:1")
    assert status == 0, errors
    assert "3:1" in output and "planned" in output.lower()
    assert not any(line.strip().startswith("0 words") for line in output.splitlines())
    assert "words per sentence" not in output


def test_omitted_nested_manuscript_uses_selected_root_settings(tmp_path, monkeypatch, capsys):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "draft.md").write_text("## First\n\nEine Tür öffnet sich. Regen fällt.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        'manuscript = "drafts/draft.md"\nlanguage = "de"\n'
        '[scene_analysis.assignments]\n"1:1" = "root voice"\n'
        '[scene_analysis.groups."root voice"]\n', encoding="utf-8",
    )
    (drafts / "lixity.toml").write_text(
        'language = "fr"\n[scene_analysis.assignments]\n"9:1" = "child voice"\n'
        '[scene_analysis.groups."child voice"]\n', encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    status, output, errors = run(capsys, "--json")
    assert status == 0 and not errors
    result = json.loads(output)
    assert result["meta"]["language"] == "de"
    assert result["scenes"]["items"][0]["group"] == "root voice"
    explicit_status, _, explicit_errors = run(capsys, drafts / "draft.md", "--json")
    assert explicit_status == 1 and "9:1" in explicit_errors


def test_build_default_keeps_root_exports_and_metadata(tmp_path, monkeypatch, capsys):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    (drafts / "draft.md").write_text("## First\n\nEine Tür öffnet sich. Regen fällt.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        'manuscript = "drafts/draft.md"\nlanguage = "de"\ntitle = "Root project title"\n', encoding="utf-8",
    )
    (drafts / "lixity.toml").write_text('language = "fr"\ntitle = "Child title"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    output = capsys.readouterr()
    assert not output.err
    assert not (drafts / "exports").exists()
    metrics = json.loads((tmp_path / "exports" / "draft_metrics.json").read_text(encoding="utf-8"))
    assert metrics["meta"]["language"] == "de"
    assert "Root project title" in (tmp_path / "exports" / "draft_dashboard.html").read_text(encoding="utf-8")


def test_bash_completes_supported_scene_selectors(tmp_path):
    import shutil
    import subprocess

    from lixity.cli import _completion_scripts

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable")
    script = _completion_scripts()[0]
    probe = '\nCOMP_WORDS=(lixity scenes --); COMP_CWORD=2; _lixity_complete; printf "%s\\n" "${COMPREPLY[@]}"\n'
    completed = subprocess.run(  # noqa: S603 - resolved Bash, emitted completion and fixed synthetic words
        [bash, "--noprofile", "--norc"], input=script + probe, cwd=tmp_path,
        capture_output=True, text=True, check=True,
    )
    assert not completed.stderr
    assert {"--chapter", "--scene", "--latest", "--language", "--json", "--help"} == set(completed.stdout.split())
