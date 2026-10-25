"""Textual report destinations share atomic writing and manuscript guards."""

import json

import pytest

from lixity.cli import main
from lixity.io import FileUtils


@pytest.fixture
def manuscript(tmp_path):
    path = tmp_path / "story.md"
    path.write_text("## Garden\n\n" + "The quiet garden waits for rain. " * 30, encoding="utf-8")
    return path


@pytest.mark.parametrize("command", ["analyze", "profile", "style", "dialogue", "pacing", "showing"])
@pytest.mark.parametrize("json_output", [False, True])
def test_report_destination_matches_stdout_without_duplicate_data(manuscript, tmp_path, capsys, command, json_output):
    options = ["--json"] if json_output else []
    if command == "profile" and not json_output:
        options += ["--layer", "asl"]
    arguments = [command, str(manuscript), "--language", "en", *options]
    assert main(arguments) == 0
    expected = capsys.readouterr()
    destination = tmp_path / "results" / "report.txt"
    assert main([*arguments, "-o", str(destination)]) == 0
    actual = capsys.readouterr()
    assert destination.read_text(encoding="utf-8") == expected.out
    assert actual.out == ""
    assert actual.err == expected.err
    if json_output:
        json.loads(destination.read_text(encoding="utf-8"))


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_report_must_not_overwrite_manuscript_alias(manuscript, tmp_path, capsys, alias):
    original = manuscript.read_bytes()
    destination = manuscript if alias == "same" else tmp_path / "alias.md"
    if alias == "symlink":
        destination.symlink_to(manuscript)
    elif alias == "hardlink":
        destination.hardlink_to(manuscript)
    assert main(["analyze", str(manuscript), "--json", "-o", str(destination)]) == 1
    output = capsys.readouterr()
    assert not output.out and "alias" in output.err
    assert manuscript.read_bytes() == original


def test_failed_read_keeps_existing_output(tmp_path, capsys):
    destination = tmp_path / "report.json"
    destination.write_text("keep", encoding="utf-8")
    assert main(["analyze", str(tmp_path / "missing.md"), "--json", "-o", str(destination)]) == 1
    assert destination.read_text() == "keep"
    assert not capsys.readouterr().out


def test_directory_output_fails_without_stdout_data(manuscript, tmp_path, capsys):
    assert main(["style", str(manuscript), "-o", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert not output.out and output.err


def test_failed_atomic_write_keeps_existing_output(manuscript, tmp_path, monkeypatch, capsys):
    destination = tmp_path / "report.json"
    destination.write_text("keep", encoding="utf-8")

    def fail(*args, **kwargs):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(FileUtils, "atomic_write_if_changed", fail)
    assert main(["analyze", str(manuscript), "--json", "-o", str(destination)]) == 1
    assert destination.read_text() == "keep"
    output = capsys.readouterr()
    assert not output.out and "synthetic write failure" in output.err


def test_failed_renderer_discards_partial_data(manuscript, tmp_path, monkeypatch, capsys):
    from lixity import cli

    destination = tmp_path / "report.json"
    destination.write_text("keep", encoding="utf-8")

    def fail(args):
        print("incomplete report")
        return 1

    monkeypatch.setattr(cli, "_cmd_dialogue", fail)
    assert main(["dialogue", str(manuscript), "-o", str(destination)]) == 1
    assert destination.read_text() == "keep"
    assert not capsys.readouterr().out


def test_guard_is_rechecked_immediately_before_replacement(manuscript, tmp_path, monkeypatch, capsys):
    destination = tmp_path / "report.json"
    original = manuscript.read_bytes()
    atomic_write = FileUtils.atomic_write_if_changed

    def swap(filepath, content, *, before_replace):
        destination.symlink_to(manuscript)
        return atomic_write(filepath, content, before_replace=before_replace)

    monkeypatch.setattr(FileUtils, "atomic_write_if_changed", swap)
    assert main(["analyze", str(manuscript), "--json", "-o", str(destination)]) == 1
    assert manuscript.read_bytes() == original
    assert destination.is_symlink()
    assert not list(tmp_path.glob("sync_tmp_*"))
    assert not capsys.readouterr().out
