"""Help is complete, readable and safe without a project or running services."""
from __future__ import annotations

import socket
import subprocess

import pytest

from lixity.cli import _COMMANDS, main


def test_top_level_help_groups_every_registered_command(capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["--help"])
    assert stopped.value.code == 0
    result = capsys.readouterr()
    assert not result.err
    for heading in ("Projects and local app", "Manuscript analysis", "Reports and sharing", "Audio", "Setup and automation"):
        assert heading + ":" in result.out
    for command, _ in _COMMANDS:
        assert command in result.out
    assert "COMMAND --help" in result.out
    assert "README.md" in result.out


@pytest.mark.parametrize("command", [name for name, _ in _COMMANDS])
def test_command_help_needs_no_project_network_or_process(command, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIXITY_DIR", str(tmp_path / "missing-project"))
    monkeypatch.setenv("LIXITY_PORT", "invalid")

    def forbidden(*args, **kwargs):
        raise AssertionError("Help must not start a process or contact a service")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    with pytest.raises(SystemExit) as stopped:
        main([command, "--help"])
    assert stopped.value.code == 0
    result = capsys.readouterr()
    assert not result.err
    assert "usage: lixity " + command in result.out
    assert "https://mfahsold.github.io/lixity/" in result.out
    assert list(tmp_path.iterdir()) == []


def test_every_published_example_parses_without_dispatch():
    import shlex

    from lixity.cli import _build_parser
    from lixity.cli_help import COMMAND_HELP

    parser = _build_parser()
    assert set(COMMAND_HELP) == {name for name, _ in _COMMANDS}
    for _, _, examples in COMMAND_HELP.values():
        for example in examples:
            arguments = shlex.split(example)
            assert arguments.pop(0) == "lixity"
            parser.parse_args(arguments)


def test_help_presentation_preserves_exclusive_audio_exports(capsys):
    from lixity.cli import _build_parser

    with pytest.raises(SystemExit) as stopped:
        _build_parser().parse_args(["read-aloud", "--ssml", "--timeline"])
    assert stopped.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
