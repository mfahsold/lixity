"""CLI adapters report invalid input encoding without publishing artifacts."""

import pytest

from lixity.cli import main


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
