"""Qwen command completions must not inherit unrelated analysis options."""
from __future__ import annotations

import re
import shlex
import shutil
import subprocess

import pytest

from lixity.cli import _completion_scripts

READ_FLAGS = {
    "--help", "--project", "-o", "--output", "--chapter", "--language", "--profile",
    "--plan-only", "--no-direction", "--engine", "--voice-description", "--reference-id", "--instructions", "--voice", "--speed", "--speech-target", "--no-audio-cache", "--fresh-audio", "--keep-markers", "--preview", "--preview-line", "--progress",
}
MIGRATION_FLAGS = {
    "--help", "--project", "--to-schema-3", "--replace", "--instructions", "--apply", "--backup", "--expected-snapshot",
}
LANGUAGES = {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"}
VOICES = {"Vivian", "Serena", "Uncle_Fu", "Dylan", "Eric", "Ryan", "Aiden", "Ono_Anna", "Sohee", "design", "reference", "thorsten"}


def bash_complete(tmp_path, *words):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable")
    probe = (f"\nCOMP_WORDS=({shlex.join(words)})\nCOMP_CWORD={len(words) - 1}\n"
             '_lixity_complete\nprintf "%s\\n" "${COMPREPLY[@]}"\n')
    result = subprocess.run(  # noqa: S603 - installed shell, emitted script and controlled synthetic words
        [bash, "--noprofile", "--norc"], input=_completion_scripts()[0] + probe,
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    assert not result.stderr
    return set(result.stdout.split())


@pytest.mark.parametrize(("command", "expected"), [("read-aloud", READ_FLAGS), ("audio-migrate", MIGRATION_FLAGS)])
def test_bash_audio_commands_offer_only_their_actual_options(tmp_path, command, expected):
    assert bash_complete(tmp_path, "lixity", command, "--") == {flag for flag in expected if flag.startswith("--")}


@pytest.mark.parametrize(("option", "expected"), [
    ("--language", LANGUAGES), ("--speech-target", {"local", "jetson"}), ("--voice", VOICES),
    ("--engine", {"qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference"}),
])
def test_bash_qwen_values_match_supported_model_controls(tmp_path, option, expected):
    assert bash_complete(tmp_path, "lixity", "read-aloud", option, "") == expected


def test_bash_migration_replacement_retains_explicit_profile_id(tmp_path):
    assert bash_complete(tmp_path, "lixity", "audio-migrate", "--replace", "narrator=R") == {"narrator=Ryan"}
    assert bash_complete(tmp_path, "lixity", "audio-migrate", "--replace", "") == set()


def test_direction_add_completion_exposes_new_action_and_options(tmp_path):
    assert "add" in bash_complete(tmp_path, "lixity", "audio-direction", "a")
    assert "--instruction" in bash_complete(tmp_path, "lixity", "audio-direction", "--inst")
    assert bash_complete(tmp_path, "lixity", "audio-direction", "--instruction", "") == set()
    arguments = zsh_arguments("audio-direction")
    assert "1:action:(inspect add save remove)" in arguments
    assert any(argument.startswith("--instruction[") for argument in arguments)


@pytest.mark.parametrize(("command", "option"), [
    ("read-aloud", "--profile"), ("read-aloud", "--instructions"), ("read-aloud", "--chapter"), ("read-aloud", "--speed"),
    ("audio-migrate", "--instructions"), ("audio-migrate", "--expected-snapshot"),
])
def test_bash_free_values_do_not_offer_analysis_flags_or_files(tmp_path, command, option):
    (tmp_path / "unrelated.md").touch()
    assert bash_complete(tmp_path, "lixity", command, option, "") == set()


@pytest.mark.parametrize("command", ["read-aloud", "audio-migrate"])
def test_bash_audio_project_completion_only_offers_directories(tmp_path, command):
    (tmp_path / "project").mkdir()
    (tmp_path / "prose.md").touch()
    assert bash_complete(tmp_path, "lixity", command, "--project", "pro") == {"project"}


@pytest.mark.parametrize(("command", "option"), [
    ("read-aloud", "-o"), ("read-aloud", "--output"), ("audio-migrate", "--backup"),
])
def test_bash_audio_output_paths_complete_existing_files(tmp_path, command, option):
    (tmp_path / "synthetic.wav").touch()
    assert bash_complete(tmp_path, "lixity", command, option, "syn") == {"synthetic.wav"}


def zsh_arguments(command):
    script = _completion_scripts()[1]
    branch = re.search(r"\n        " + re.escape(command) + r"\)\n(.*?)\n          ;;", script, re.S)
    assert branch is not None, f"Dedicated Zsh command branch missing: {command}"
    arguments = shlex.split(branch[1].replace("\\\n", " "))
    assert arguments.pop(0) == "_arguments"
    return arguments


@pytest.mark.parametrize(("command", "expected"), [("read-aloud", READ_FLAGS), ("audio-migrate", MIGRATION_FLAGS)])
def test_zsh_audio_argument_contract_matches_current_commands(command, expected):
    arguments = zsh_arguments(command)
    assert {argument.lstrip("*").split("[", 1)[0] for argument in arguments
            if argument.lstrip("*").startswith("-")} == expected
    if command == "read-aloud":
        choices = {argument.split("[", 1)[0]: set(argument.rsplit("(", 1)[1].removesuffix(")").split())
                   for argument in arguments if argument.endswith(")")}
        assert choices["--language"] == LANGUAGES
        assert choices["--voice"] == VOICES
        assert choices["--speech-target"] == {"local", "jetson"}
    else:
        assert any(argument.startswith("*--replace[") for argument in arguments)
        assert any(argument.startswith("*--instructions[") for argument in arguments)


@pytest.mark.parametrize(("shell", "index"), [("bash", 0), ("zsh", 1)])
def test_emitted_audio_completion_shell_syntax(shell, index):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is unavailable")
    result = subprocess.run(  # noqa: S603 - installed shell parses emitted completion without executing it
        [executable, "-n"], input=_completion_scripts()[index], text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("command", "expected"), [("read-aloud", READ_FLAGS), ("audio-migrate", MIGRATION_FLAGS)])
def test_native_zsh_dispatches_audio_argument_contract(command, expected):
    zsh = shutil.which("zsh")
    if zsh is None:
        pytest.skip("Zsh is unavailable; declaration contracts are checked separately")
    # Stub only Zsh's completion UI, keeping its own word-array dispatch intact.
    probe = ("\n_arguments() { if [[ $1 == -C ]]; then state=args; else printf '%s\\n' \"$@\"; fi; }\n"
             f"words=({shlex.quote(command)} '')\n_lixity\n")
    result = subprocess.run(  # noqa: S603 - installed shell and generated completion on controlled words
        [zsh, "-f"], input="compdef() { :; }\n" + _completion_scripts()[1] + probe,
        text=True, capture_output=True, check=True,
    )
    assert not result.stderr
    arguments = result.stdout.splitlines()
    assert {argument.lstrip("*").split("[", 1)[0] for argument in arguments
            if argument.lstrip("*").startswith("-")} == expected
