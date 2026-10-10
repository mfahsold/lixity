"""Tests for scripts/lixity-start.sh lifecycle launcher."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestLauncher(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = Path(__file__).resolve().parent.parent / "scripts" / "lixity-start.sh"
        bash_bin = shutil.which("bash")
        if not cls.script.exists() or not bash_bin:
            raise unittest.SkipTest("bash or scripts/lixity-start.sh not available")
        cls.bash = bash_bin

    def test_help_command(self) -> None:
        res = subprocess.run(  # noqa: S603
            [self.bash, str(self.script), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Usage:", res.stdout)

    def test_status_when_not_running(self) -> None:
        res = subprocess.run(  # noqa: S603
            [self.bash, str(self.script), "status", "--port", "59999"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("Lixity is not running", res.stdout)

    def test_restart_of_stopped_service_attempts_start_and_reports_launch_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            runtime.mkdir()
            executable = root / ".venv" / "bin" / "lixity"
            executable.parent.mkdir(parents=True)
            executable.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$@" > "$LIXITY_LAUNCHER_TEST_MARKER"\nexit 17\n',
                encoding="utf-8",
            )
            executable.chmod(0o755)
            marker = root / "attempt.txt"
            res = subprocess.run(  # noqa: S603 - repository launcher and synthetic executable
                [self.bash, str(self.script), "restart", "--port", "59997"],
                cwd=root,
                env={**os.environ, "XDG_RUNTIME_DIR": str(runtime),
                     "LIXITY_LAUNCHER_TEST_MARKER": str(marker)},
                capture_output=True, text=True, check=False, timeout=10,
            )
            self.assertTrue(marker.exists(), "Restart must attempt a start even without a live PID")
            self.assertEqual(marker.read_text().splitlines(),
                             ["serve", "--host", "127.0.0.1", "--port", "59997"])
            self.assertNotEqual(res.returncode, 0, "A failed launch cannot be reported as success")
            self.assertIn("exited during startup", res.stderr)

    def test_stale_pid_cleanup_by_status(self) -> None:
        xdg = os.environ.get("XDG_RUNTIME_DIR", "")
        if xdg and os.path.isdir(xdg) and os.access(xdg, os.W_OK):
            runtime_dir = Path(xdg)
        else:
            home_share = Path.home() / ".local" / "share" / "lixity"
            if home_share.is_dir() and os.access(home_share, os.W_OK):
                runtime_dir = home_share
            else:
                runtime_dir = Path(tempfile.gettempdir()) / f"lixity-{os.geteuid()}"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        fake_pid_file = runtime_dir / "lixity-59998.pid"
        fake_pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
        self.assertTrue(fake_pid_file.exists())

        res = subprocess.run(  # noqa: S603
            [self.bash, str(self.script), "status", "--port", "59998"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 1)
        self.assertFalse(
            fake_pid_file.exists(),
            "Stale/recycled PID file must be cleaned up when process is not listening on port",
        )
