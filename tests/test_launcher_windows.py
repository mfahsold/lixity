"""Exercise PowerShell delegation with a real packaged, synthetic Windows server."""

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.portability,
    pytest.mark.skipif(sys.platform != "win32", reason="Native Windows PowerShell lifecycle"),
]


def test_powershell_wrapper_preserves_project_spaces_unicode_and_language(tmp_path):
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        pytest.fail("Windows lifecycle validation requires its native PowerShell")
    project = tmp_path / "A book – Grüße"
    project.mkdir()
    source = project / "manuscript.md"
    source.write_text("# Synthetic book\n\n## Opening\n\nEin Vogel fliegt über den Garten.\n", encoding="utf-8")
    before = source.read_bytes()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src"), "PYTHONUTF8": "1",
           "LIXITY_SERVICE_STATE_DIR": str(tmp_path / "state"),
           "LIXITY_SERVICE_RUNTIME_DIR": str(tmp_path / "runtime")}
    script = root / "scripts" / "lixity-start.ps1"

    def invoke(action, *arguments):
        return subprocess.run(  # noqa: S603 - explicit native shell and repository wrapper
            [powershell, "-NoProfile", "-NonInteractive", "-File", str(script), action,
             "-Port", str(port), *arguments], cwd=tmp_path, env=env,
            capture_output=True, text=True, timeout=45, check=False,
        )

    try:
        result = invoke("start", "-Language", "de", "-Dir", str(project))
        assert result.returncode == 0, result.stdout + result.stderr
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api", timeout=10) as response:
            info = json.load(response)
        assert info["project"]["manuscript_loaded"] and info["project"]["language"] == "de"
        result = invoke("status")
        assert result.returncode == 0, result.stdout + result.stderr
        assert source.read_bytes() == before
    finally:
        result = invoke("stop")
        assert result.returncode == 0, result.stdout + result.stderr
