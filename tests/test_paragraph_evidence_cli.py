"""Opt-in literal CLI evidence leaves existing profile envelopes unchanged."""

import json

from lixity.cli import main


def run(capsys, *arguments):
    try:
        status = main(["profile", *map(str, arguments)])
    except SystemExit as error:
        status = error.code
    result = capsys.readouterr()
    return status, result.out, result.err


def test_evidence_json_is_opt_in_and_reuses_the_original_layer_reference(tmp_path, capsys):
    path = tmp_path / "synthetic.md"
    path.write_text('## Example\n\nI wait.\n\nI can wait.\n\nI think I can wait.\n\n'
                    'I think I can wait here while the station closes and the guards leave.\n')
    status, before, _ = run(capsys, path, "--layer", "asl", "--json")
    assert status == 0
    status, output, errors = run(capsys, path, "--layer", "asl", "--evidence", "--json")
    assert status == 0, errors
    base, report = json.loads(before), json.loads(output)
    assert report["meta"]["schema_version"] == "paragraph-layer-evidence/1"
    assert report["selection"] == base["selection"] and report["comparison"] == base["comparison"]
    for original, row in zip(base["paragraphs"], report["paragraphs"], strict=True):
        assert {key: row[key] for key in original} == original
        assert row["evidence"]["schema_version"] == "paragraph-evidence/1"
        assert "text" not in row and "text" not in row["evidence"]
    status, selected, errors = run(capsys, path, "--layer", "asl", "--only-notable", "--evidence", "--json")
    assert status == 0, errors
    assert json.loads(selected)["selection"]["total_count"] == 4
    assert [row["index"] for row in json.loads(selected)["paragraphs"]] == [3]
    status, after, errors = run(capsys, path, "--layer", "asl", "--json")
    assert status == 0, errors
    assert before == after


def test_evidence_requires_layer_before_reading_source(capsys):
    status, _, errors = run(capsys, "does-not-exist.md", "--evidence")
    assert status == 2
    assert "--evidence requires --layer" in errors


def test_human_evidence_prints_bounded_safe_verbatim_and_source_anchors(tmp_path, capsys):
    path = tmp_path / "synthetic.md"
    path.write_text('## Example\n\nI think\x1b[31m I think.\n')
    status, output, errors = run(capsys, path, "--layer", "filter", "--evidence")
    assert status == 0, errors
    assert f"{path}:3-3" in output and "think" in output
    assert "2/2" in output and "[2:7]" in output
    assert "\x1b" not in output


def test_human_evidence_bounds_long_snippets_and_span_lists(tmp_path, capsys):
    path = tmp_path / "synthetic.md"
    path.write_text("## Example\n\nI " + "quiet " * 200 + "UNPRINTEDEND.\n")
    status, output, errors = run(capsys, path, "--layer", "asl", "--evidence")
    assert status == 0, errors
    assert "202 words" in output and "UNPRINTEDEND" not in output
    assert len(output) < 2000
    path.write_text("## Example\n\n" + "I think. " * 12 + "\n")
    status, output, errors = run(capsys, path, "--layer", "filter", "--evidence")
    assert status == 0, errors
    assert "12/12" in output and "4 further spans" in output
    assert output.count("x1 think") == 8
