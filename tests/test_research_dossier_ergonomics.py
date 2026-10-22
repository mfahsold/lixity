"""Dossier terminal reads preserve useful text and exact selectors."""

import argparse
import json

import pytest

from lixity.research import api, cli
from tests.research_support import capture_research, revise_record


@pytest.fixture
def project(tmp_path):
    api.init(tmp_path, title="Synthetic dossier routines")
    return tmp_path


def read(project, *arguments):
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    result = capture_research(*arguments, "--project", str(project))
    assert {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()} == before
    return result


@pytest.mark.parametrize("kind,create", [
    ("dossier", lambda project: api.create_dossier(project, "Copyable dossier", "Body.")["dossier_id"]),
    ("claim", lambda project: api.create_claim(project, title="Copyable claim", statement="Statement.")["claim_id"]),
    ("decision", lambda project: api.record_decision(project, title="Copyable decision", rationale="Reason.")["decision_id"]),
])
def test_record_list_table_has_full_unwrapped_copyable_ids_at_narrow_terminal(project, monkeypatch, kind, create):
    identifier = create(project)
    monkeypatch.setenv("COLUMNS", "30")
    status, output, errors = read(project, kind, "list", "--format", "table")
    assert status == 0 and errors == ""
    line = next((line for line in output.splitlines() if identifier in line), "")
    assert line, "The displayed list must contain the complete stored identifier"
    assert line.split()[0] == identifier
    assert "…" not in line and "\x1b" not in output
    status, opened, errors = read(project, kind, line.split()[0])
    assert status == 0 and errors == ""
    assert json.loads(opened)["record"]["id"] == identifier


@pytest.mark.parametrize("selector", ["direct", "show", "inspect", "flag"])
def test_section_text_reads_include_only_selected_subtree(project, selector):
    identifier = api.create_dossier(project, "Synthetic dossier",
        "## Before\n\nBEFORE_ONLY.\n\n## Target\n\nTARGET_BODY.\n\n### Child\n\nCHILD_BODY.\n\n## After\n\nAFTER_ONLY.")["dossier_id"]
    selected = [identifier] if selector == "direct" else ["--dossier-id", identifier] if selector == "flag" else [selector, identifier]
    status, output, errors = read(project, "dossier", *selected, "--section", " target ", "--format", "text")
    assert status == 0 and errors == ""
    assert "TARGET_BODY." in output and "CHILD_BODY." in output
    assert "Target" in output and "Version 1" in output
    assert "BEFORE_ONLY" not in output and "AFTER_ONLY" not in output
    status, raw, errors = read(project, "dossier", *selected, "--section", "Target", "--json")
    assert status == 0 and errors == ""
    assert json.loads(raw)["content"] == "TARGET_BODY.\n\n### Child\n\nCHILD_BODY."


def test_empty_and_historical_sections_do_not_fall_back_to_other_body_text(project):
    identifier = api.create_dossier(project, "Versioned dossier",
        "## Empty\n\n## Target\n\nOLD_TARGET.\n\n## Other\n\nUNSELECTED.")["dossier_id"]
    revise_record(project, "dossier", identifier, {"body": "## Empty\n\n## Target\n\nNEW_TARGET.\n\n## Other\n\nUNSELECTED."})
    status, output, errors = read(project, "dossier", identifier, "--section", "Empty", "--format", "text")
    assert status == 0 and errors == ""
    assert "Empty" in output
    assert "TARGET" not in output and "UNSELECTED" not in output
    status, output, errors = read(project, "dossier", "show", identifier, "--revision", "1",
                                   "--section", "Target", "--format", "text")
    assert status == 0 and errors == ""
    assert "OLD_TARGET." in output and "NEW_TARGET" not in output and "UNSELECTED" not in output


def test_section_terminal_text_keeps_existing_control_escape_boundary(project):
    identifier = api.create_dossier(project, "Safe title", "## Target\n\nText \x1b]52;c;payload\x07 and \u202e.")["dossier_id"]
    status, output, errors = read(project, "dossier", identifier, "--section", "Target", "--format", "text")
    assert status == 0 and errors == ""
    assert "Text " in output and "payload" in output
    assert "\x1b" not in output and "\x07" not in output and "\u202e" not in output


@pytest.fixture
def tagged(project):
    entries = {}
    for title, tags in (("Both", ["red", "blue"]), ("Red", ["red"]), ("Prefix", ["reddish"]),
                        ("Case", ["Red"]), ("Comma", ["red,blue"]), ("Unicode", ["Küste"]),
                        ("Longest", ["x" * 50]), ("Untagged", [])):
        entries[title] = api.create_dossier(project, title, "Synthetic note.", tags=tags)["dossier_id"]
    return entries


@pytest.mark.parametrize("tags,titles", [
    (["red"], {"Red", "Both"}), (["red", "blue"], {"Both"}), (["red", "red"], {"Red", "Both"}),
    (["Red"], {"Case"}), (["red,blue"], {"Comma"}), (["Küste"], {"Unicode"}),
    (["missing"], set()), (["x" * 50], {"Longest"}),
])
def test_repeatable_tags_are_exact_all_tag_filters_on_list_envelope(project, tagged, tags, titles):
    arguments = [option for tag in tags for option in ("--tag", tag)]
    status, output, errors = read(project, "dossier", "list", *arguments)
    assert status == 0 and errors == ""
    result = json.loads(output)
    expected = api.list_dossiers(project)
    expected["dossiers"] = [item for item in expected["dossiers"] if item["title"] in titles]
    assert result == expected
    assert {item["id"] for item in result["dossiers"]} == {tagged[title] for title in titles}
    for format in ("text", "table"):
        status, output, errors = read(project, "dossiers", "--format", format, *arguments)
        assert status == 0 and errors == ""
        assert f"{len(titles)} dossier(s)." in output
        assert all((identifier in output) == (title in titles) for title, identifier in tagged.items())


def test_tag_filter_reads_current_tags_without_repinning_history(project, tagged):
    revise_record(project, "dossier", tagged["Both"], {"tags": ["blue"]})
    status, output, errors = read(project, "dossier", "--tag", "red")
    assert status == 0 and errors == ""
    assert [item["id"] for item in json.loads(output)["dossiers"]] == [tagged["Red"]]
    assert api.get_dossier(project, tagged["Both"], revision=1)["tags"] == ["red", "blue"]


@pytest.mark.parametrize("tag", ["", " \t", "x" * 51])
def test_tag_selectors_do_not_relax_stored_tag_bounds(project, tag):
    status, output, errors = read(project, "dossier", "list", "--tag", tag)
    assert status == 1 and output == ""
    assert "tag" in errors.lower()


@pytest.mark.parametrize("mode", ["direct", "show", "create", "update", "prepare", "history"])
def test_tag_filter_rejects_record_or_write_modes_before_side_effects(project, mode):
    identifier = api.create_dossier(project, "Selected", "Original.")["dossier_id"]
    modes = {"direct": [identifier], "show": ["show", identifier],
             "create": ["--title", "Created", "--body", "New."],
             "update": [identifier, "--update", "--latest", "--body", "New.", "--change-kind", "correction", "--reason", "Synthetic."],
             "prepare": [identifier, "--prepare", "--body", "New."], "history": [identifier, "--history"]}
    status, output, errors = read(project, "dossier", *modes[mode], "--tag", "red")
    assert status == 1 and output == ""
    assert "--tag" in errors and "list" in errors


def test_dossier_help_distinguishes_filter_tags_from_authored_tags():
    parser = argparse.ArgumentParser()
    cli.configure(parser)
    commands = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    help_text = " ".join(commands.choices["dossier"].format_help().split())
    assert "--tag " in help_text and "--tags " in help_text
    assert "exact" in help_text and "case-sensitive" in help_text and "all" in help_text
