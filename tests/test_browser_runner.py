"""Browser runs must leave an accurate aggregate result at the end of their logs."""

import json
import re
import shutil
import subprocess
import sys
import time
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

    def run(codes, jobs=1, extra_args=(), *, wait=True):
        for name, code in codes.items():
            (suites / name).write_text(
                (f"import sys\nprint('Suite body: {name}', flush=True)\nsys.exit({code})\n"
                 if isinstance(code, int) else code),
                encoding="utf-8",
            )
        command = [sys.executable, "-c", bootstrap, str(runner), "--jobs", str(jobs), *extra_args]
        if not wait:
            return subprocess.Popen(  # noqa: S603 - disposable script and fixed test arguments
                command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        return subprocess.run(  # noqa: S603 - disposable script and fixed test arguments
            command,
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
    assert "c.cjs" not in result.stdout


@pytest.mark.parametrize("jobs", [1, 3])
def test_success_summary_reports_all_completed_suites_and_elapsed_time(browser_runner, jobs):
    result = browser_runner({"a.cjs": 0, "b.cjs": 0, "c.cjs": 0}, jobs=jobs)
    assert result.returncode == 0, result.stderr
    assert "3/3 completed, 3 passed, 0 failed, 0 not run" in result.stdout
    assert "Failed suites:" not in result.stdout + result.stderr
    assert re.search(r"not run in \d+\.\ds\.\n$", result.stdout)
    duration_lines = re.findall(r"^  (\d+\.\d)s ([abc]\.cjs)$", result.stdout, re.MULTILINE)
    assert len(duration_lines) == 3
    assert [float(seconds) for seconds, _ in duration_lines] == sorted(
        (float(seconds) for seconds, _ in duration_lines), reverse=True
    )


@pytest.mark.parametrize("jobs", [1, 3])
@pytest.mark.parametrize("limit", [0, 1])
def test_duration_report_is_bounded_without_changing_selection(browser_runner, jobs, limit):
    result = browser_runner({"a.cjs": 0, "b.cjs": 0, "c.cjs": 0}, jobs=jobs,
                            extra_args=("--durations", str(limit)))
    assert result.returncode == 0, result.stderr
    assert "3/3 completed, 3 passed" in result.stdout
    assert len(re.findall(r"^  \d+\.\ds [abc]\.cjs$", result.stdout, re.MULTILINE)) == limit
    assert ("Slowest browser suites" in result.stdout) == bool(limit)


def test_negative_duration_limit_fails_before_starting_suites(browser_runner):
    result = browser_runner({"a.cjs": 0}, extra_args=("--durations", "-1"))
    assert result.returncode == 2
    assert "--durations must be nonnegative" in result.stderr
    assert "Suite body:" not in result.stdout


@pytest.mark.parametrize("jobs", [1, 3])
def test_diagnostics_preserve_failed_logs_and_distinguish_unrun_suites(browser_runner, tmp_path, jobs):
    bundle = tmp_path / "evidence"
    result = browser_runner({"a.cjs": 0, "b.cjs": 7, "c.cjs": 0}, jobs=jobs,
                            extra_args=("--diagnostics", str(bundle)))
    assert result.returncode == 7, result.stderr
    manifest = json.loads((bundle / "results.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["counts"] == {
        "selected": 3, "completed": 2 if jobs == 1 else 3,
        "passed": 1 if jobs == 1 else 2, "failed": 1, "active": 0,
        "not_run": 1 if jobs == 1 else 0,
    }
    suites = {item["name"]: item for item in manifest["suites"]}
    assert suites["b.cjs"]["status"] == "failed"
    assert suites["b.cjs"]["exit_code"] == 7
    assert suites["b.cjs"]["seconds"] >= 0
    assert suites["b.cjs"]["started_at"]
    assert suites["b.cjs"]["finished_at"]
    assert "Suite body: b.cjs" in (bundle / suites["b.cjs"]["log"]).read_text()
    assert suites["c.cjs"]["status"] == ("not_run" if jobs == 1 else "passed")
    assert manifest["seconds"] >= suites["b.cjs"]["seconds"]
    assert manifest["jobs"] == jobs
    assert str(tmp_path) not in (bundle / "results.json").read_text()
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Runner state: **failed**" in summary.stdout
    assert "`b.cjs` (exit 7)" in summary.stdout


def test_diagnostics_are_readable_while_a_suite_is_active(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    process = browser_runner({
        "a.cjs": "import time\nprint('Synthetic active suite', flush=True)\ntime.sleep(2)\n",
        "b.cjs": 0,
    }, extra_args=("--diagnostics", str(bundle)), wait=False)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if (bundle / "results.json").exists():
                manifest = json.loads((bundle / "results.json").read_text())
                if manifest["counts"]["active"]:
                    break
            time.sleep(0.02)
        else:
            pytest.fail("Runner never persisted active-suite evidence")
        assert manifest["status"] == "running"
        assert manifest["counts"] == {
            "selected": 2, "completed": 0, "passed": 0, "failed": 0, "active": 1, "not_run": 1,
        }
        assert manifest["suites"][0]["name"] == "a.cjs"
        assert manifest["suites"][0]["status"] == "active"
        assert manifest["suites"][0]["started_at"]
        assert manifest["suites"][1]["status"] == "not_run"
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stdout + stderr
        final = json.loads((bundle / "results.json").read_text())
        assert final["status"] == "passed"
        assert final["counts"]["completed"] == 2
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)


def test_diagnostics_bound_logs_and_collect_only_owned_png_captures(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    outside = tmp_path / "unrelated-private.png"
    outside.write_bytes(b"private bytes")
    body = rf"""
import os
from pathlib import Path
root = Path(os.environ['TMPDIR'])
for index in range(8):
    (root / ('capture-%s.png' % index)).write_bytes(b'\x89PNG\r\n\x1a\n' + b'synthetic')
(root / 'too-large.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'x' * (3 * 1024 * 1024))
(root / 'not-an-image.png').write_text('synthetic but not a PNG')
(root / 'synthetic-project.txt').write_text('do not retain source documents')
try:
    (root / 'linked.png').symlink_to({str(outside)!r})
except OSError:
    pass
print('ä' * (256 * 1024))
print('Tail retained')
raise SystemExit(5)
"""
    result = browser_runner({"a.cjs": body}, extra_args=("--diagnostics", str(bundle)))
    assert result.returncode == 5, result.stderr
    manifest = json.loads((bundle / "results.json").read_text())
    suite = manifest["suites"][0]
    log = bundle / suite["log"]
    assert log.stat().st_size <= 128 * 1024
    assert log.read_text().endswith("Tail retained\n")
    assert suite["log_truncated"] is True
    assert len(suite["captures"]) == 4
    assert suite["captures_truncated"] is True
    assert all((bundle / name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
               for name in suite["captures"])
    assert not any(path.suffix == '.txt' for path in bundle.rglob('*'))
    assert not any(path.is_symlink() for path in bundle.rglob('*'))
    assert sum(path.stat().st_size for path in bundle.rglob('*') if path.is_file()) < 256 * 1024
    assert outside.read_bytes() == b"private bytes"


@pytest.mark.parametrize(("first_code", "failed_count", "last_capture_count"), [(0, 1, 1), (1, 2, 0)])
def test_failed_capture_budget_survives_a_successful_screenshot_heavy_predecessor(
    tmp_path, monkeypatch, first_code, failed_count, last_capture_count,
):
    from scripts import run_browser_suites as runner

    suites = tmp_path / "suites"
    suites.mkdir()
    for name, code in (("a.cjs", first_code), ("b.cjs", 1)):
        (suites / name).write_text(
            "import os\nfrom pathlib import Path\n"
            "for index in range(4):\n"
            "    (Path(os.environ['TMPDIR']) / f'synthetic-{index}.png').write_bytes("
            "b'\\x89PNG\\r\\n\\x1a\\nsynthetic')\n"
            f"raise SystemExit({code})\n",
        )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "SUITE_DIR", suites)
    # Each capture is 17 bytes: one fits, two exceed the shared budget.
    monkeypatch.setattr(runner.BrowserEvidence, "TOTAL_CAPTURE_BYTES", 25)
    bundle = tmp_path / "evidence"
    evidence = runner.BrowserEvidence(bundle, ["a.cjs", "b.cjs"], 1)
    code = 2
    try:
        # Run in order so a successful predecessor gets the first opportunity
        # to consume the shared budget. A later failing suite still needs PNGs.
        evidence.run_suite(sys.executable, "a.cjs", True)
        _name, _seconds, code, _output = evidence.run_suite(sys.executable, "b.cjs", True)
    finally:
        evidence.finish(code)
    assert code == 1
    manifest = json.loads((bundle / "results.json").read_text())
    captures = [bundle / name for suite in manifest["suites"] for name in suite["captures"]]
    assert len(captures) == 1
    assert sum(path.stat().st_size for path in captures) == 17
    assert len(manifest["suites"][1]["captures"]) == last_capture_count
    assert manifest["counts"]["failed"] == failed_count
    if first_code == 0:
        assert manifest["suites"][0]["captures"] == []
        assert manifest["suites"][0]["captures_truncated"] is False


def test_harness_failure_retains_evidence_and_leaves_ui_suites_not_run(browser_runner, tmp_path):
    support = tmp_path / "tests/browser/support"
    support.mkdir(parents=True)
    (support / "preflight.test.cjs").write_text("synthetic preflight")
    bundle = tmp_path / "evidence"
    result = browser_runner({"a.cjs": 0}, extra_args=("--diagnostics", str(bundle)))
    assert result.returncode != 0
    manifest = json.loads((bundle / "results.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["preflight"]["status"] == "failed"
    assert manifest["preflight"]["exit_code"] != 0
    assert (bundle / manifest["preflight"]["log"]).read_text()
    assert manifest["suites"][0]["status"] == "not_run"
    assert manifest["counts"]["completed"] == 0


def test_terminated_runner_preserves_partial_state_without_claiming_a_pass(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    result = browser_runner({
        "a.cjs": "import os, signal\nos.kill(os.getppid(), signal.SIGTERM)\n",
        "b.cjs": 0,
    }, extra_args=("--diagnostics", str(bundle)))
    assert result.returncode != 0
    manifest = json.loads((bundle / "results.json").read_text())
    assert manifest["status"] == "running"
    assert manifest["finished_at"] is None
    assert manifest["counts"]["completed"] == 0
    assert manifest["counts"]["active"] == 1
    assert manifest["counts"]["not_run"] == 1
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Runner state: **running**" in summary.stdout
    assert "Active in last saved snapshot: `a.cjs`" in summary.stdout
    assert "Not run: `b.cjs`" in summary.stdout


def test_diagnostics_refuse_existing_output_without_exposing_its_contents(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    sentinel = bundle / "private.txt"
    sentinel.write_text("leave existing data alone")
    result = browser_runner({"a.cjs": 0}, extra_args=("--diagnostics", str(bundle)))
    assert result.returncode == 2
    assert "Cannot create new browser diagnostics directory" in result.stderr
    assert "Suite body:" not in result.stdout
    assert sentinel.read_text() == "leave existing data alone"
    assert not (bundle / "results.json").exists()


def test_ci_summary_reports_partial_failure_and_last_active_state(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    (bundle / "results.json").write_text(json.dumps({
        "schema_version": 1, "status": "running", "seconds": 12.5,
        "jobs": 2, "full_matrix": True,
        "preflight": {"status": "passed", "exit_code": 0, "seconds": 0.2},
        "counts": {"selected": 4, "completed": 2, "passed": 1, "failed": 1,
                   "active": 1, "not_run": 1},
        "suites": [{"name": "a.cjs", "status": "passed", "exit_code": 0, "seconds": 4.0},
                   {"name": "b.cjs", "status": "failed", "exit_code": 7, "seconds": 6.0},
                   {"name": "c.cjs", "status": "active"},
                   {"name": "d.cjs", "status": "not_run"}],
    }))
    result = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert result.returncode == 0, result.stderr
    assert "2/4 completed" in result.stdout
    assert "1 passed, 1 failed, 1 active, 1 not run" in result.stdout
    assert "2 workers" in result.stdout and "full locale matrix" in result.stdout
    assert "`b.cjs` (exit 7)" in result.stdout
    assert "Active in last saved snapshot: `c.cjs`" in result.stdout
    assert "Not run: `d.cjs`" in result.stdout
    assert "running" in result.stdout and "job conclusion" in result.stdout
    assert "6.0s `b.cjs`" in result.stdout
    assert "Suite body:" not in result.stdout


@pytest.fixture
def valid_summary_manifest():
    return {
        "schema_version": 1, "status": "passed", "seconds": 1.2, "jobs": 1,
        "full_matrix": True,
        "preflight": {"status": "passed", "exit_code": 0, "seconds": 0.2},
        "counts": {"selected": 1, "completed": 1, "passed": 1, "failed": 0,
                   "active": 0, "not_run": 0},
        "suites": [{"name": "synthetic.cjs", "status": "passed", "exit_code": 0,
                    "seconds": 1.0}],
    }


@pytest.mark.parametrize(("path", "value"), [
    (("schema_version",), 999),
    (("schema_version",), True),
    (("status",), "complete"),
    (("seconds",), -1),
    (("seconds",), float("nan")),
    (("seconds",), float("inf")),
    (("jobs",), 0),
    (("jobs",), True),
    (("full_matrix",), "true"),
    (("counts", "passed"), 0),
    (("counts", "passed"), True),
    (("preflight", "status"), "failed"),
    (("preflight", "status"), "active"),
    (("preflight", "status"), "not_run"),
    (("preflight", "status"), "unknown"),
    (("suites", 0, "status"), "skipped"),
    (("suites", 0, "exit_code"), 7),
    (("suites", 0, "seconds"), float("inf")),
    (("suites", 0), {"name": "synthetic.cjs", "status": "failed", "exit_code": 7,
                     "seconds": 1.0}),
])
def test_ci_summary_refuses_corrupt_or_contradictory_saved_results(
    browser_runner, tmp_path, valid_summary_manifest, path, value,
):
    target = valid_summary_manifest
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    (bundle / "results.json").write_text(json.dumps(valid_summary_manifest))
    result = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert result.returncode == 0, result.stderr
    assert "Results are unknown" in result.stdout
    assert "Runner state:" not in result.stdout
    assert "1 passed" not in result.stdout


def test_ci_summary_refuses_duplicate_suites_even_when_saved_counts_match(
    browser_runner, tmp_path, valid_summary_manifest,
):
    valid_summary_manifest["suites"] *= 2
    valid_summary_manifest["counts"].update(selected=2, completed=2, passed=2)
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    (bundle / "results.json").write_text(json.dumps(valid_summary_manifest))
    result = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Results are unknown" in result.stdout
    assert "2 passed" not in result.stdout


def test_passed_summary_requires_completed_suites_and_an_explicit_harness_result(
    browser_runner, tmp_path,
):
    bundle = tmp_path / "evidence"
    result = browser_runner({"a.cjs": 0}, extra_args=("--diagnostics", str(bundle)))
    assert result.returncode == 0, result.stderr
    manifest = json.loads((bundle / "results.json").read_text())
    assert manifest["preflight"] == {
        "status": "not_required", "reason": "No support harness tests found.",
    }
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Runner state: **passed**" in summary.stdout
    assert "1/1 completed, 1 passed" in summary.stdout
    assert "harness: not_required" in summary.stdout
    manifest["suites"][0] = {"name": "a.cjs", "status": "active"}
    manifest["counts"] = {"selected": 1, "completed": 0, "passed": 0, "failed": 0,
                          "active": 1, "not_run": 0}
    (bundle / "results.json").write_text(json.dumps(manifest))
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Results are unknown" in summary.stdout


def test_ci_summary_preserves_a_truthful_empty_selection(browser_runner, tmp_path):
    bundle = tmp_path / "evidence"
    result = browser_runner({"unrelated.cjs": 0}, extra_args=(
        "--diagnostics", str(bundle), "--area", "analysis",
    ))
    assert result.returncode == 0, result.stderr
    manifest = json.loads((bundle / "results.json").read_text())
    assert manifest["suites"] == [] and manifest["jobs"] == 0
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "0/0 completed, 0 passed, 0 failed, 0 active, 0 not run" in summary.stdout
    assert "0 workers" in summary.stdout


def test_ci_summary_preserves_failed_startup_without_claiming_any_completed_suite(
    browser_runner, tmp_path,
):
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    (bundle / "results.json").write_text(json.dumps({
        "schema_version": 1, "status": "failed", "seconds": 0.1, "jobs": 1,
        "full_matrix": False, "preflight": {"status": "not_run"},
        "counts": {"selected": 1, "completed": 0, "passed": 0, "failed": 0,
                   "active": 0, "not_run": 1},
        "suites": [{"name": "synthetic.cjs", "status": "not_run"}],
    }))
    summary = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert "Runner state: **failed**" in summary.stdout
    assert "0/1 completed, 0 passed, 0 failed, 0 active, 1 not run" in summary.stdout
    assert "Not run: `synthetic.cjs`" in summary.stdout


@pytest.mark.parametrize("malformed", [False, True])
def test_ci_summary_reports_unknown_results_when_manifest_is_missing_or_invalid(
    browser_runner, tmp_path, malformed,
):
    bundle = tmp_path / "evidence"
    bundle.mkdir()
    if malformed:
        (bundle / "results.json").write_text("incomplete JSON")
    result = browser_runner({}, extra_args=("--summary", str(bundle)))
    assert result.returncode == 0, result.stderr
    assert "unavailable" in result.stdout and "job logs" in result.stdout
    assert "0 failed" not in result.stdout
    assert "Suite body:" not in result.stdout


def test_shard_selection_balances_estimated_duration_instead_of_suite_count(monkeypatch):
    from scripts import run_browser_suites as runner

    weights = {"long.cjs": 10, "medium.cjs": 6, "short.cjs": 5}
    monkeypatch.setattr(runner, "_FULL_SUITE_SECONDS", weights)
    monkeypatch.setattr(runner, "_UNMEASURED_SUITE_SECONDS", 2)
    names = ["unknown-b.cjs", *weights, "unknown-a.cjs"]
    assert runner.select_shard(names, "1/3") == ["long.cjs"]
    assert runner.select_shard(names, "2/3") == ["medium.cjs", "unknown-b.cjs"]
    assert runner.select_shard(names, "3/3") == ["short.cjs", "unknown-a.cjs"]


def test_full_selection_has_balanced_disjoint_shards_and_stable_order():
    from scripts.run_browser_suites import estimate_suite_seconds, select_shard, suite_names

    all_names = suite_names()
    workloads = []
    selected = []
    for index in range(1, 5):
        spec = f"{index}/4"
        shard = select_shard(all_names, spec)
        assert shard == select_shard(list(reversed(all_names)), spec)
        selected.extend(shard)
        weights = [estimate_suite_seconds(name) for name in shard]
        assert weights == sorted(weights, reverse=True)
        workloads.append(sum(weights))
    assert sorted(selected) == sorted(all_names)
    assert max(workloads) - min(workloads) <= 0.02 * sum(workloads) / len(workloads)


def test_shard_selection_distributes_unmeasured_suites_and_allows_empty_shards(browser_runner):
    suites = {"beta.cjs": 0, "alpha.cjs": 0}
    for shard, expected in (("1/3", "alpha.cjs"), ("2/3", "beta.cjs"), ("3/3", "")):
        result = browser_runner(suites, extra_args=("--list", "--shard", shard))
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected


@pytest.mark.parametrize("bad_shard", ["0/4", "5/4", "abc", "1/0"])
def test_invalid_shard_spec_fails_before_starting_suites(browser_runner, bad_shard):
    result = browser_runner({"a.cjs": 0}, extra_args=("--shard", bad_shard))
    assert result.returncode == 2
    assert "--shard" in result.stderr
    assert "Suite body:" not in result.stdout


@pytest.mark.parametrize("configured, expected", [
    ("", "--max-old-space-size=2048"),
    ("--trace-warnings", "--trace-warnings --max-old-space-size=2048"),
    ("--max-old-space-size=1024", "--max-old-space-size=1024"),
    ("--max_old_space_size 3072", "--max_old_space_size 3072"),
])
def test_suite_heap_limit_preserves_explicit_caller_options(monkeypatch, configured, expected):
    from scripts.run_browser_suites import browser_environment

    monkeypatch.setenv("NODE_OPTIONS", configured)
    assert browser_environment()["NODE_OPTIONS"] == expected


@pytest.mark.parametrize("diagnostics", [False, True])
def test_heap_limit_reaches_each_suite_process(browser_runner, monkeypatch, tmp_path, diagnostics):
    monkeypatch.delenv("NODE_OPTIONS", raising=False)
    arguments = ("--diagnostics", str(tmp_path / "evidence")) if diagnostics else ()
    result = browser_runner(
        {"a.cjs": "import os\nprint('suite options: ' + os.environ.get('NODE_OPTIONS', 'missing'))\n"},
        extra_args=arguments,
    )
    assert result.returncode == 0
    assert "suite options: --max-old-space-size=2048" in result.stdout
