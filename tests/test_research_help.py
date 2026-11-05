"""Research help stays usable without opening an archive or accepting source bytes."""

import argparse
import shlex
import socket
import subprocess

import pytest

from lixity import cli as main_cli
from lixity.research import cli
from lixity.research.repository import Repository


def research_parser():
    parser = argparse.ArgumentParser(prog="lixity research")
    cli.configure(parser)
    commands = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )
    return parser, commands.choices


RESEARCH_NAMES = tuple(
    name for canonical, _, _, aliases in cli.COMMAND_DEFINITIONS for name in (canonical, *aliases)
)


@pytest.mark.parametrize("name", RESEARCH_NAMES)
def test_research_command_and_alias_help_has_no_runtime_effects(
    name, tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LIXITY_LANG", "de")

    def forbidden(*args, **kwargs):
        pytest.fail("Help must not open an archive, dispatch a command or contact a service")

    monkeypatch.setattr(cli, "run", forbidden)
    monkeypatch.setattr(Repository, "__init__", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    with pytest.raises(SystemExit) as stopped:
        main_cli.main(["research", name, "--help"])
    assert stopped.value.code == 0
    result = capsys.readouterr()
    assert not result.err
    assert "Output:" in result.out
    assert "Examples" in result.out
    assert "https://mfahsold.github.io/lixity/research/USAGE.md" in result.out
    assert list(tmp_path.iterdir()) == []


def test_research_help_examples_parse_and_aliases_keep_the_same_grammar():
    parser, commands = research_parser()
    seen = set()
    # Parse actual displayed examples, including continued dossier commands and
    # stdout redirection, without opening paths or executing commands.
    for command in (parser, *dict.fromkeys(commands.values())):
        assert command.epilog
        for line in command.epilog.replace("\\\n", " ").splitlines():
            if not line.strip().startswith("lixity research "):
                continue
            tokens = shlex.split(line.strip())[2:]
            if ">" in tokens:
                tokens = tokens[: tokens.index(">")]
            args = parser.parse_args(tokens)
            seen.add(args.research_command)
            for alias in commands[tokens[0]].get_default("cli_aliases"):
                assert vars(parser.parse_args([alias, *tokens[1:]])) == vars(args)
    assert seen == {name for name, _, _, _ in cli.COMMAND_DEFINITIONS}


def test_research_help_options_and_output_choices_are_explained():
    _, commands = research_parser()
    for command in dict.fromkeys(commands.values()):
        for action in command._actions:
            assert action.help, (command.prog, action.dest)
        formats = command.get_default("cli_output_formats")
        default = command.get_default("cli_default_output")
        assert f"Output: {', '.join(formats)} (default: {default})." in command.epilog
        if "--format" in command._option_string_actions:
            action = command._option_string_actions["--format"]
            assert tuple(action.choices) == formats
            assert action.default == default


def test_storage_migration_appears_in_the_existing_archive_group():
    parser, commands = research_parser()
    groups = {
        commands[name].get_default("cli_group")
        for name in ("audit", "reindex", "migrate-storage", "export", "restore")
    }
    assert len(groups) == 1
    assert parser.format_help().count(groups.pop() + ":") == 1


@pytest.mark.parametrize(
    "arguments",
    [
        ["schema", "--json"],
        ["dashboard", "--format", "html"],
        ["search", "--query", "room", "--format", "text"],
        ["matrix", "--format", "text"],
        ["restore", "--from", "backup.tar.gz", "--project", "novel"],
        ["find-anchor", "draft.md", "--manuscript", "other.md", "--quote", "room"],
    ],
)
def test_research_help_does_not_imply_universal_output_or_path_options(arguments, capsys):
    parser, _ = research_parser()
    with pytest.raises(SystemExit) as stopped:
        parser.parse_args(arguments)
    assert stopped.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "error:" in output.err
