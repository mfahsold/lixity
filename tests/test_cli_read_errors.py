"""CLI adapters reject invalid inputs and output modes without publishing artifacts."""

import pytest

from lixity.cli import main


@pytest.mark.parametrize("command,option,value,message", [
    ("style", "--fdr-q", "1", "less than 1"),
    ("build", "--fdr-q", "0", "greater than 0"),
    ("dashboard", "--z-mild", "-0.1", "at least 0"),
    ("serve", "--dim-threshold", "0", "greater than 0"),
    ("style", "--z-strong", "inf", "finite number"),
    ("build", "--fdr-q", "nan", "finite number"),
])
def test_invalid_threshold_is_usage_error_before_configuration_or_output(
    tmp_path, monkeypatch, capsys, command, option, value, message,
):
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "lixity.toml"
    original = 'title = "Unclosed synthetic configuration\n'
    config.write_text(original)
    with pytest.raises(SystemExit) as error:
        main([command, "missing-synthetic.md", option, value])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert option in captured.err and message in captured.err
    assert config.read_text() == original
    assert list(tmp_path.iterdir()) == [config]


@pytest.mark.parametrize("command", ["style", "build", "dashboard", "serve"])
def test_threshold_help_explains_numeric_domain(command, capsys):
    with pytest.raises(SystemExit) as error:
        main([command, "--help"])
    assert error.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "> 0 and < 1" in help_text
    assert "finite" in help_text and "default: 0.05" in help_text


def test_pdf_rejects_json_before_processing_or_replacing_output(tmp_path, capsys):
    source = tmp_path / "synthetic.md"
    source.write_text("## One\n\nA synthetic scene.\n", encoding="utf-8")
    output = tmp_path / "report.pdf"
    output.write_bytes(b"Previous synthetic PDF")
    with pytest.raises(SystemExit) as error:
        main(["pdf", str(source), "--json", "--output", str(output)])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "--json" in captured.err and "PDF" in captured.err
    assert output.read_bytes() == b"Previous synthetic PDF"


@pytest.mark.parametrize("command", ["pdf", "build", "analyze"])
def test_invalid_utf8_returns_error_without_traceback_or_outputs(tmp_path, capsys, command):
    source = tmp_path / "synthetic.md"
    original = b"# Invalid synthetic source\n\xff\n"
    source.write_bytes(original)
    failure = None
    result = None
    try:
        result = main([command, str(source)])
    except (OSError, UnicodeError) as exc:
        failure = type(exc).__name__
    assert failure is None, "An input error must be reported by the CLI, not escape the adapter"
    assert result == 1
    output = capsys.readouterr()
    assert output.err and "Traceback" not in output.err
    assert source.read_bytes() == original
    assert list(tmp_path.iterdir()) == [source]


@pytest.mark.parametrize("command", ["pdf", "build", "dashboard"])
def test_invalid_project_title_returns_error_before_any_output(tmp_path, capsys, command):
    source = tmp_path / "synthetic.md"
    source.write_text("# Synthetic\n\n## One\n\nA simple scene.\n")
    config = tmp_path / "lixity.toml"
    config.write_text("title = 42\n")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    failure = None
    result = None
    try:
        result = main([command, str(source)])
    except ValueError as exc:
        failure = type(exc).__name__
    assert failure is None, "Metadata validation belongs in the CLI error channel"
    assert result == 1
    output = capsys.readouterr()
    assert "Title" in output.err and "Traceback" not in output.err
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_dashboard_replacement_failure_reports_error_and_keeps_previous_output(tmp_path, capsys):
    from unittest.mock import patch
    source = tmp_path / "synthetic.md"
    source.write_text("# Synthetic\n\n## One\n\nA simple scene.\n")
    output = tmp_path / "dashboard.html"
    output.write_bytes(b"Previous synthetic output")
    failure = None
    result = None
    with patch("lixity.io.os.replace", side_effect=OSError("Synthetic replace failure")):
        try:
            result = main(["dashboard", str(source), "--output", str(output)])
        except OSError as exc:
            failure = type(exc).__name__
    assert failure is None
    assert result == 1
    assert "Synthetic replace failure" in capsys.readouterr().err
    assert output.read_bytes() == b"Previous synthetic output"
    assert set(tmp_path.iterdir()) == {source, output}
