"""Checkout launchers delegate to the installed lifecycle implementation."""

import json
import os
import plistlib
import shlex
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


@pytest.mark.parametrize("use_uv", [False, True], ids=["on-path", "uv-bin-directory"])
def test_linux_desktop_launcher_delegates_browser_opening_for_selected_port(tmp_path, use_uv):
    bash = shutil.which("bash")
    if not bash or os.name == "nt":
        pytest.skip("Requires a native POSIX Bash")
    installed = tmp_path / "installed tools"
    installed.mkdir()
    executable = installed / "lixity"
    executable.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$LIXITY_PORT" "$@"\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)
    search = tmp_path / "tool commands" if use_uv else installed
    if use_uv:
        search.mkdir()
        uv = search / "uv"
        uv.write_text('#!/bin/sh\n[ "$*" = "tool dir --bin" ] || exit 1\nprintf "%s\\n" "$UV_TOOL_BIN_DIR"\n',
                      encoding="utf-8")
        uv.chmod(0o755)
    for name in ("update-desktop-database", "xdg-open"):
        stub = search / name
        stub.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        stub.chmod(0o755)
    data = tmp_path / "data"
    env = {**os.environ, "PATH": str(search) + os.pathsep + os.defpath, "HOME": str(tmp_path),
           "UV_TOOL_BIN_DIR": str(installed), "XDG_DATA_HOME": str(data), "LIXITY_PORT": "9000"}
    result = subprocess.run(  # noqa: S603 - local installer and synthetic executable
        [bash, str(SCRIPT.parent / "install-desktop-linux.sh")],
        env=env, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
    launcher = data / "applications" / "lixity.desktop"
    command = next(line.removeprefix("Exec=") for line in launcher.read_text().splitlines()
                   if line.startswith("Exec="))
    argv = shlex.split(command)
    assert argv == [str(executable), "service", "start", "--open"]
    result = subprocess.run(  # noqa: S603 - asserted synthetic executable and arguments
        argv, env=env, capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0 and result.stdout.splitlines() == ["9000", "service", "start", "--open"]


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
    environment = {**os.environ, "LIXITY_LAUNCHER_TEST_MARKER": str(marker)}
    # This is a fresh Make invocation. A parent `make test VPY=...` would
    # otherwise pass its interpreter override on to the launcher fixture.
    for name in ("MAKEFLAGS", "MAKEOVERRIDES", "MFLAGS", "GNUMAKEFLAGS", "MAKELEVEL", "MAKEFILES"):
        environment.pop(name, None)
    result = subprocess.run(  # noqa: S603 - explicit Makefile and synthetic interpreter
        [make, "-f", str(SCRIPT.parent.parent / "Makefile"), target, f"VENV={venv}", "LIXITY_PORT=59996"],
        cwd=tmp_path, env=environment,
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(marker.read_text()) == arguments
