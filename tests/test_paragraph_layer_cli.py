"""Opt-in paragraph layers preserve profile contracts and chapter references."""

import json
import shutil
import subprocess
from dataclasses import replace

import orjson
import pytest

from lixity import api, style_fingerprint
from lixity.cli import main
from lixity.style_profile import ParagraphProfile

TEXT = (
    "## Étude 🧭\n\n"
    "Mara waits.\n\n"
    "Mara reads the map.\n\n"
    "Mara opens the gate then waits.\n\n"
    "Mara carries twenty silver keys across the quiet courtyard while a distant "
    "clock marks the final hour before the dark storm.\n\n"
    "## Equal\n\nMara waits.\n\nMara waits.\n\nMara waits.\n\n"
    "## Short\n\nMara waits here.\n\nMara opens the gate then waits.\n"
)


@pytest.fixture
def manuscript(tmp_path):
    path = tmp_path / "étude 🧭.md"
    path.write_text(TEXT, encoding="utf-8")
    return path


def run(capsys, *arguments):
    try:
        status = main(["profile", *map(str, arguments)])
    except SystemExit as error:
        status = error.code
    output = capsys.readouterr()
    return status, output.out, output.err


def test_help_offers_a_read_count_compare_path_without_changing_defaults(capsys):
    status, output, errors = run(capsys, "--help")
    assert status == 0 and not errors
    assert "--language en --layer asl --only-notable" in output
    assert "Then inspect the counted text:" in output
    assert "ASL means words per sentence" in output
    assert "same chapter, not the manuscript-wide chapter baseline" in output
    assert "Unavailable comparison is not a measured zero" in output


@pytest.mark.parametrize("arguments", [(), ("--json",)])
def test_default_profile_stays_byte_identical_to_v2_api(manuscript, capsys, arguments):
    status, output, errors = run(capsys, manuscript, *arguments)
    assert status == 0, errors
    expected = orjson.dumps(api.profile(TEXT, project_config={}), option=orjson.OPT_INDENT_2)
    assert output.encode() == expected + b"\n"
    assert json.loads(output)["meta"]["schema_version"] == 2


def test_layer_json_reports_full_reference_and_unknown_comparisons(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--layer", "asl", "--json")
    assert status == 0, errors
    report = json.loads(output)
    assert report["meta"]["schema_version"] == "paragraph-layer/1"
    assert report["meta"]["language"] == "en"
    assert report["layer"] == "asl"
    assert report["feature"] == "asl"
    assert report["unit"] == "words per sentence"
    assert report["comparison"] == {
        "reference_scope": "all_measurable_paragraphs_within_each_chapter",
        "method": "median_mad_robust_z", "minimum_paragraphs": 3,
        "requires_nonzero_mad": True, "z_decimals": 2, "notable_abs_z": 1.5,
    }
    assert report["selection"] == {
        "only_notable": False, "total_count": 9, "comparable_count": 4,
        "notable_count": 1, "selected_count": 9,
    }
    rows = report["paragraphs"]
    assert [row["value"] for row in rows] == [2, 4, 6, 21, 2, 2, 2, 3, 6]
    assert [row["z"] for row in rows[:4]] == [-1.01, -0.34, 0.34, 5.4]
    assert rows[3]["notable"] is True
    assert rows[0]["notable"] is False
    assert rows[0]["chapter_title"] == "Étude 🧭"
    assert (rows[3]["index"], rows[3]["start_line"], rows[3]["end_line"]) == (3, 9, 9)
    for row in rows[4:]:
        assert row["comparable"] is False
        assert row["z"] is None and row["notable"] is None
    assert all("text" not in row for row in rows)


def test_only_notable_filters_after_comparing_the_full_chapter(manuscript, capsys):
    status, output, errors = run(
        capsys, manuscript, "--layer", "asl", "--only-notable", "--json",
    )
    assert status == 0, errors
    report = json.loads(output)
    assert report["selection"] == {
        "only_notable": True, "total_count": 9, "comparable_count": 4,
        "notable_count": 1, "selected_count": 1,
    }
    assert [(row["index"], row["z"]) for row in report["paragraphs"]] == [(3, 5.4)]


@pytest.mark.parametrize("layer,feature,unit", [
    ("asl", "asl", "words per sentence"),
    ("function", "function_word_pct", "% of words"),
    ("dialogue", "dialog_pct", "% of words"),
    ("filter", "filter_density", "per 1,000 words"),
    ("modal", "modal_density", "per 1,000 words"),
    ("nominal", "nominalization_density", "per 1,000 words"),
    ("passive", "passive_density", "per 1,000 words"),
])
def test_every_layer_uses_its_canonical_feature_and_unit(manuscript, capsys, layer, feature, unit):
    status, output, errors = run(capsys, manuscript, "--layer", layer, "--json")
    assert status == 0, errors
    report = json.loads(output)
    assert (report["layer"], report["feature"], report["unit"]) == (layer, feature, unit)
    assert report["selection"]["total_count"] == 9
    assert report["paragraphs"][0]["value"] is not None


def test_zero_density_remains_measured_when_local_comparison_is_unavailable(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--layer", "dialogue", "--json")
    assert status == 0, errors
    report = json.loads(output)
    assert report["selection"]["comparable_count"] == 0
    assert all(row["value"] == 0 for row in report["paragraphs"])
    assert all(row["z"] is None and row["notable"] is None for row in report["paragraphs"])
    status, output, errors = run(
        capsys, manuscript, "--layer", "dialogue", "--only-notable", "--json",
    )
    assert status == 0, errors
    assert json.loads(output)["paragraphs"] == []


def test_human_layer_lists_source_values_and_local_comparison_without_prose(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--layer", "asl", "--only-notable")
    assert status == 0, errors
    assert "Étude 🧭" in output and f"{manuscript}:9-9" in output
    assert "21.00 words per sentence" in output
    assert "z +5.40" in output and "notable" in output
    assert "9 total" in output and "4 comparable" in output and "1 shown" in output
    assert "within each chapter" in output and "MAD" in output
    assert "Mara carries" not in output


def test_human_zero_density_explains_unavailable_comparison(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--layer", "modal")
    assert status == 0, errors
    assert "0.00 per 1,000 words" in output
    assert "comparison unavailable" in output
    assert "at least 3 measurable paragraphs" in output and "nonzero MAD" in output


def test_german_layer_explanations_follow_analysis_language(manuscript, capsys):
    status, output, errors = run(capsys, manuscript, "--language", "de", "--layer", "asl")
    assert status == 0, errors
    assert "Referenz:" in output and "Vergleich nicht verfügbar" in output
    assert "vergleichbar" in output and "angezeigt" in output
    assert "Reference:" not in output and "comparison unavailable" not in output


def test_empty_selection_explains_actual_chapter_limits_and_quotes_command(manuscript, capsys):
    import shlex

    status, output, errors = run(
        capsys, manuscript, "--language", "de", "--layer", "modal", "--only-notable",
    )
    assert status == 0, errors
    assert "weniger als 3 messbaren Absätzen: 1" in output
    assert "MAD = 0: 2" in output
    command = output.split("Vollständige Belege: ")[1].strip()
    arguments = shlex.split(command)
    assert arguments[:3] == ["lixity", "profile", str(manuscript)]
    assert "--only-notable" not in arguments
    assert "--evidence" in arguments and "--json" in arguments


@pytest.mark.parametrize("arguments,message", [
    (("--only-notable",), "requires --layer"),
    (("--only-notable", "--json"), "requires --layer"),
    (("--layer", "unknown"), "invalid choice"),
    (("--layer",), "expected one argument"),
])
def test_invalid_layer_options_fail_before_loading_input(tmp_path, monkeypatch, capsys, arguments, message):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "lixity.toml"
    config.write_text('title = "Unclosed synthetic config\n', encoding="utf-8")
    status, output, errors = run(capsys, "missing.md", *arguments)
    assert status == 2 and output == ""
    assert message in errors
    assert list(tmp_path.iterdir()) == [config]


def test_configured_project_input_and_language_are_used(tmp_path, monkeypatch, capsys):
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    source = drafts / "étude.md"
    source.write_text("## Étude\n\nSie wartet.\n", encoding="utf-8")
    original = source.read_bytes()
    (tmp_path / "lixity.toml").write_text(
        'manuscript = "drafts/étude.md"\nlanguage = "de"\n', encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    status, output, errors = run(capsys, "--layer", "asl", "--json")
    assert status == 0, errors
    report = json.loads(output)
    assert report["meta"]["language"] == "de"
    assert report["unit"] == "words per sentence"
    assert report["paragraphs"][0]["value"] == 2
    assert source.read_bytes() == original
    status, output, errors = run(capsys, "--layer", "asl")
    assert status == 0, errors
    assert "Wörter je Satz" in output


def test_explicit_missing_input_does_not_fall_back_to_configured_manuscript(tmp_path, monkeypatch, capsys):
    (tmp_path / "draft.md").write_text(TEXT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    status, output, errors = run(capsys, "missing.md", "--layer", "asl", "--json")
    assert status == 1 and output == ""
    assert "missing.md" in errors


def test_empty_layer_result_keeps_zero_counts(tmp_path, capsys):
    source = tmp_path / "empty.md"
    source.write_text("", encoding="utf-8")
    status, output, errors = run(capsys, source, "--layer", "filter", "--only-notable", "--json")
    assert status == 0, errors
    report = json.loads(output)
    assert report["paragraphs"] == []
    assert report["selection"] == {
        "only_notable": True, "total_count": 0, "comparable_count": 0,
        "notable_count": 0, "selected_count": 0,
    }


def test_shared_projection_rounds_z_before_applying_notability_cutoff():
    base = ParagraphProfile(
        chapter_num=1, chapter_title="Synthetic", start_line=1, end_line=1,
        words=10, sentences=1, present_hits=0, past_hits=0, dominant="neutral",
        minority_ratio=0, mixed=False, switch=False, severity=0,
        asl=0, dialogue_pct=0, function_word_pct=0,
    )
    # Median 10, MAD 1. The outer raw scores are +/-1.496, rounded to +/-1.50.
    paragraphs = [replace(base, asl=value) for value in (7.782, 9, 10, 11, 12.218)]
    report = style_fingerprint.paragraph_layer_projection(paragraphs, "asl")
    row = report["paragraphs"][-1]
    assert row["z"] == 1.5 and row["notable"] is True
    assert report["paragraphs"][0]["z"] == -1.5
    assert report["paragraphs"][0]["notable"] is True
    assert report["paragraphs"][2]["z"] == 0
    assert report["paragraphs"][2]["notable"] is False


@pytest.mark.parametrize("prefix,expected", [
    ("--", {"--layer", "--only-notable"}),
    ("--layer ", {"asl", "function", "dialogue", "filter", "modal", "nominal", "passive"}),
])
def test_bash_completion_offers_profile_layers(tmp_path, prefix, expected):
    from lixity.cli import _completion_scripts

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable")
    words = "lixity profile --" if prefix == "--" else 'lixity profile --layer ""'
    word_index = 2 if prefix == "--" else 3
    probe = (
        f"\nCOMP_WORDS=({words}); COMP_CWORD={word_index}; _lixity_complete; "
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    completed = subprocess.run(  # noqa: S603 - resolved Bash, emitted completion, fixed words
        [bash, "--noprofile", "--norc"], input=_completion_scripts()[0] + probe,
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert completed.stderr == ""
    assert expected <= set(completed.stdout.split())
