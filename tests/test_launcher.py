"""Checkout launchers delegate to the installed lifecycle implementation."""

import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lixity-start.sh"


@pytest.fixture
def launcher(tmp_path):
    bash = shutil.which("bash")
    if not bash or os.name == "nt":
        pytest.skip("Requires a native POSIX Bash")
    installed = tmp_path / "installed"
    installed.mkdir()
    marker = tmp_path / "arguments.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    executable = installed / "lixity"
    executable.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['LIXITY_LAUNCHER_TEST_MARKER']).write_text(json.dumps(sys.argv[1:]))\n"
        "print('Synthetic lifecycle result')\nsys.exit(int(os.environ.get('LIXITY_LAUNCHER_TEST_STATUS', '0')))\n"
    )
    executable.chmod(0o755)
    local = tmp_path / ".venv" / "bin" / "lixity"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\nexit 99\n")
    local.chmod(0o755)
    environment = {**os.environ, "PATH": str(installed) + os.pathsep + os.environ.get("PATH", ""),
                   "LIXITY_LAUNCHER_TEST_MARKER": str(marker), "XDG_RUNTIME_DIR": str(runtime),
                   "XDG_STATE_HOME": str(tmp_path / "state")}

    def invoke(*args, status=0):
        result = subprocess.run(  # noqa: S603 - local wrapper and synthetic installed executable
            [bash, str(SCRIPT), *args], cwd=tmp_path,
            env={**environment, "LIXITY_LAUNCHER_TEST_STATUS": str(status)},
            capture_output=True, text=True, timeout=10, check=False,
        )
        return result, json.loads(marker.read_text()) if marker.exists() else None

    return invoke


@pytest.mark.parametrize("action", ["start", "stop", "restart", "status"])
def test_wrapper_delegates_action_to_installed_cli_instead_of_cwd_venv(launcher, action):
    result, arguments = launcher(action, "--port", "59997")
    assert result.returncode == 0
    assert arguments == ["service", action, "--port", "59997"]


def test_wrapper_preserves_language_and_space_unicode_arguments(launcher):
    project = "/synthetic/A book – Grüße"
    result, arguments = launcher("start", "--language", "de", "--open", project)
    assert result.returncode == 0
    assert arguments == ["service", "start", "--language", "de", "--open", project]


def test_wrapper_defaults_to_start_and_preserves_controller_exit_status(launcher):
    result, arguments = launcher(status=17)
    assert result.returncode == 17
    assert arguments == ["service", "start"]


def test_wrapper_forwards_help_to_the_packaged_interface(launcher):
    result, arguments = launcher("--help")
    assert result.returncode == 0
    assert arguments == ["service", "--help"]


def test_macos_template_is_valid_and_has_explicit_neutral_startup():
    template = plistlib.loads((SCRIPT.parent / "lixity.plist").read_bytes())
    assert "--no-project" in template["ProgramArguments"]
    assert template["Label"] == "com.lixity.serve"


@pytest.mark.parametrize("target,arguments", [
    ("run", ["-m", "lixity", "serve", "--no-project", "--port", "59996"]),
    ("start", ["-m", "lixity", "service", "start", "--port", "59996"]),
    ("serve", ["-m", "lixity", "service", "start", "--port", "59996"]),
    ("stop", ["-m", "lixity", "service", "stop", "--port", "59996"]),
    ("restart", ["-m", "lixity", "service", "restart", "--port", "59996"]),
    ("status", ["-m", "lixity", "service", "status", "--port", "59996"]),
])
def test_make_uses_explicit_interpreter_with_space_containing_venv(tmp_path, target, arguments):
    make = shutil.which("make")
    if not make or os.name == "nt":
        pytest.skip("Requires native POSIX Make")
    venv = tmp_path / "A developer environment – Grüße"
    executable = venv / "bin" / "python"
    executable.parent.mkdir(parents=True)
    marker = tmp_path / "make-arguments.json"
    executable.write_text(
        f"#!{sys.executable}\nimport json,os,sys\nfrom pathlib import Path\n"
        "Path(os.environ['LIXITY_LAUNCHER_TEST_MARKER']).write_text(json.dumps(sys.argv[1:]))\n"
    )
    executable.chmod(0o755)
    result = subprocess.run(  # noqa: S603 - explicit Makefile and synthetic interpreter
        [make, "-f", str(SCRIPT.parent.parent / "Makefile"), target, f"VENV={venv}", "LIXITY_PORT=59996"],
        cwd=tmp_path, env={**os.environ, "LIXITY_LAUNCHER_TEST_MARKER": str(marker)},
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(marker.read_text()) == arguments
