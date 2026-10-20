"""Browser runs must leave an accurate aggregate result at the end of their logs."""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_browser_suites.py"


@pytest.fixture
def browser_runner(tmp_path):
    """Run the real CLI with disposable suites and a small Node stand-in."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    runner = scripts / SCRIPT.name
    shutil.copyfile(SCRIPT, runner)
    suites = tmp_path / "tests/browser"
    suites.mkdir(parents=True)
    # Override only executable discovery in the child, so the real CLI runs
    # Python fixtures as its subprocess suites on every supported platform.
    bootstrap = """
import runpy
import shutil
import sys
original_which = shutil.which
shutil.which = lambda name: sys.executable if name == 'node' else original_which(name)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name='__main__')
"""

    def run(codes, jobs=1):
        for name, code in codes.items():
            (suites / name).write_text(
                f"import sys\nprint('Suite body: {name}', flush=True)\nsys.exit({code})\n",
                encoding="utf-8",
            )
        return subprocess.run(  # noqa: S603 - disposable script and fixed test arguments
            [sys.executable, "-c", bootstrap, str(runner), "--jobs", str(jobs)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    return run


def test_parallel_failure_summary_lists_every_failure_after_suite_output(browser_runner):
    result = browser_runner({"a.cjs": 4, "b.cjs": 0, "c.cjs": 4}, jobs=3)
    assert result.returncode == 4
    assert "Suite body: b.cjs" in result.stdout
    assert "3/3 completed, 1 passed, 2 failed, 0 not run" in result.stderr
    assert result.stderr.index("Browser suite summary:") > result.stderr.index("Failed: c.cjs")
    assert "Failed suites:\n  a.cjs (exit 4)\n  c.cjs (exit 4)" in result.stderr
    assert "All 3 browser suites passed" not in result.stdout


def test_sequential_failure_summary_distinguishes_unrun_suites(browser_runner):
    result = browser_runner({"a.cjs": 0, "b.cjs": 7, "c.cjs": 0})
    assert result.returncode == 7
    assert "Suite body: a.cjs" in result.stdout
    assert "Suite body: c.cjs" not in result.stdout
    assert "2/3 completed, 1 passed, 1 failed, 1 not run" in result.stderr
    assert "Failed suites:\n  b.cjs (exit 7)" in result.stderr
    assert "--start b.cjs" in result.stderr


@pytest.mark.parametrize("jobs", [1, 3])
def test_success_summary_reports_all_completed_suites_and_elapsed_time(browser_runner, jobs):
    result = browser_runner({"a.cjs": 0, "b.cjs": 0, "c.cjs": 0}, jobs=jobs)
    assert result.returncode == 0, result.stderr
    assert "3/3 completed, 3 passed, 0 failed, 0 not run" in result.stdout
    assert "Failed suites:" not in result.stdout + result.stderr
    assert re.search(r"not run in \d+\.\ds\.\n$", result.stdout)
