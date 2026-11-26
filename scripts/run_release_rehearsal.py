#!/usr/bin/env python3
"""Run local release journeys and retain comparable evidence for development."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .benchmark_pipeline import DEFAULT_CORPUS
    from .check_release import promote_artifacts, source_version
    from .run_browser_suites import diagnostic_counts
else:
    from benchmark_pipeline import DEFAULT_CORPUS
    from check_release import promote_artifacts, source_version
    from run_browser_suites import diagnostic_counts

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lixity-release-rehearsal/1"
JOURNEYS = ("warehouse-author.cjs", "linguistic-reference.cjs", "home-tour.cjs")
STAGES = ("browser", "corpus", "wheel")


def source_state() -> dict:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to record the rehearsal source")
    revision = subprocess.check_output(  # noqa: S603 - fixed Git command and checkout
        [git, "rev-parse", "--verify", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    changes = subprocess.check_output(  # noqa: S603 - fixed Git command and checkout
        [git, "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT,
    )
    if not changes:
        return {"commit": revision, "dirty": False}
    tracked_diff = subprocess.check_output(  # noqa: S603 - fixed Git command, no diff plugins
        [git, "diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--"], cwd=ROOT,
    )
    return {"commit": revision, "dirty": True,
            "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
            "status_sha256": hashlib.sha256(changes).hexdigest()}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_receipt(directory: Path, receipt: dict) -> None:
    pending = directory / "results.json.tmp"
    pending.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    pending.replace(directory / "results.json")


def run_stage(directory: Path, receipt: dict, name: str, command: list[str], *,
              json_output: Path | None = None) -> bool:
    stage = receipt["stages"][name]
    stage["status"] = "running"
    write_receipt(directory, receipt)
    print(f"Running {name} checks", flush=True)
    started = time.monotonic()
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHON_BIN": sys.executable}
    env.pop("LIXITY_BROWSER_FULL", None)
    try:
        outcome = subprocess.run(  # noqa: S603 - fixed checked-in tools, no shell
            [sys.executable, *command], cwd=ROOT, env=env, check=False,
            text=True, stdout=subprocess.PIPE if json_output else None,
        )
        stage.update(status="passed" if not outcome.returncode else "failed",
                     exit_code=outcome.returncode)
        if json_output is not None and not outcome.returncode:
            data = json.loads(outcome.stdout)
            if [(item["file"], item["language"]) for item in data["results"]] != list(DEFAULT_CORPUS):
                raise ValueError("The benchmark did not measure every reviewed manuscript")
            json_output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            stage["evidence"] = json_output.name
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"{name}: {exc}", file=sys.stderr)
        stage["status"] = "failed"
    finally:
        stage["seconds"] = round(time.monotonic() - started, 3)
        write_receipt(directory, receipt)
    return stage["status"] == "passed"


def rehearse(*, jobs: int, tag: str | None, dist: Path | None, skip_wheel: bool,
             expected_commit: str | None = None) -> int:
    before = source_state()
    if expected_commit is not None and before["commit"] != expected_commit:
        raise ValueError("HEAD changed after the release checks began")
    version = source_version(ROOT, tag)
    parent = ROOT / ".artifacts" / "release-rehearsal"
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    receipt = {
        "schema_version": SCHEMA, "status": "running", "started_at": utc_now(),
        "version": version, "source": before,
        "fixtures": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                     for name in ("samples/first-look.md", "scripts/example_project.py",
                                  "tests/fixtures/literary_reference.json")},
        "stages": {name: {"status": "not_run"} for name in STAGES},
    }
    browser = receipt["stages"]["browser"]
    browser["evidence"] = "browser/results.json"
    wheel = receipt["stages"]["wheel"]
    target = directory / "dist"
    write_receipt(directory, receipt)
    print(f"Rehearsal evidence: {directory.relative_to(ROOT)}", flush=True)
    try:
        ui_ok = run_stage(directory, receipt, "browser", [
            "scripts/run_browser_suites.py", "--only", *JOURNEYS, "--jobs", str(jobs),
            "--diagnostics", str(directory / "browser"),
        ])
        corpus_ok = run_stage(directory, receipt, "corpus", [
            "scripts/benchmark_pipeline.py", "--workspace", "--json",
            "--iterations", "3", "--synthetic-chapters", "0",
        ], json_output=directory / "corpus.json")
        same_state = source_state() == before
        wheel_ok = skip_wheel
        if skip_wheel:
            wheel.update(status="skipped", reason="development run requested without a build")
        elif not (ui_ok and corpus_ok and same_state):
            wheel["reason"] = "browser, corpus or source check did not pass"
        else:
            command = ["scripts/check_release.py", "--build", "--smoke", "--dist", str(target)]
            if tag:
                command.extend(("--tag", tag))
            wheel_ok = run_stage(directory, receipt, "wheel", command)
            if wheel_ok:
                lines = (target / "SHA256SUMS").read_text(encoding="ascii").splitlines()
                receipt["wheel_checksums"] = {filename: digest for digest, filename in map(str.split, lines)}
        after = source_state()
        receipt["source_after"] = after
        ok = ui_ok and corpus_ok and wheel_ok and same_state and before == after
        if dist is not None:
            receipt["promotion"] = "not_run"
            if ok:
                try:
                    promote_artifacts(ROOT, target, dist.absolute(), tag)
                except (OSError, ValueError) as exc:
                    print(f"Artifact promotion failed: {exc}", file=sys.stderr)
                    receipt["promotion"] = "failed"
                    ok = False
                else:
                    receipt["promotion"] = "passed"
        receipt["reviewed_commit"] = before["commit"] if ok and not before["dirty"] else None
        receipt["status"] = "passed" if ok else "failed"
        return 0 if ok else 1
    finally:
        if receipt["status"] == "running":
            receipt["status"] = "incomplete"
        receipt["finished_at"] = utc_now()
        write_receipt(directory, receipt)
        print(f"Rehearsal {receipt['status']}: {directory.relative_to(ROOT)}/results.json")


def read_receipt(directory: Path) -> dict:
    data = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    if data["schema_version"] != SCHEMA:
        raise ValueError("Unsupported rehearsal result schema")
    return data


def browser_outcomes(directory: Path) -> dict[str, str]:
    path = directory / "browser" / "results.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    diagnostic_counts(data)
    return {suite["name"]: suite["status"] for suite in data["suites"]}


def compare(previous: Path, current: Path) -> None:
    before, after = (read_receipt(directory) for directory in (previous, current))
    for label, data in (("Previous", before), ("Current", after)):
        source = data["source"]
        identity = "reviewed commit" if data.get("reviewed_commit") else "working or unverified tree"
        print(f"{label}: {source['commit'][:12]} ({identity}), Lixity {data['version']}")
    for name in STAGES:
        print(f"{name}: {before['stages'][name]['status']} -> {after['stages'][name]['status']}")
    earlier, later = browser_outcomes(previous), browser_outcomes(current)
    for name in sorted(earlier.keys() | later.keys()):
        old_state, new_state = earlier.get(name, "unavailable"), later.get(name, "unavailable")
        if old_state != new_state or new_state != "passed":
            print(f"  {name}: {old_state} -> {new_state}")
    for fixture in sorted(before["fixtures"].keys() | after["fixtures"].keys()):
        if before["fixtures"].get(fixture) != after["fixtures"].get(fixture):
            print(f"Fixture changed: {fixture}")
    if any(data["stages"]["corpus"]["status"] != "passed" for data in (before, after)):
        print("Corpus comparison unavailable: both runs need a completed corpus check.")
        return
    old, new = (json.loads((directory / "corpus.json").read_text(encoding="utf-8"))
                for directory in (previous, current))
    compatible = all(old.get(key) == new.get(key) for key in
                     ("python", "machine", "platform", "mode", "iterations"))
    if not compatible:
        print("Timing comparison unavailable: benchmark environments or settings differ.")
    else:
        print("Use timing deltas from the same machine and comparable load.")
    old_cases = {(item["file"], item["language"]): item for item in old["results"]}
    for item in new["results"]:
        key = (item["file"], item["language"])
        baseline = old_cases.get(key)
        label = f"{key[0]} ({key[1]})"
        if baseline is None or item["source_sha256"] != baseline["source_sha256"]:
            print(f"{label}: input changed or has no baseline.")
            continue
        print(f"{label}: result digest {'unchanged' if item['digests'] == baseline['digests'] else 'changed'}")
        if compatible:
            for stage, value in item["median_ms"].items():
                if stage in baseline["median_ms"]:
                    previous_ms = baseline["median_ms"][stage]
                    print(f"  {stage}: {previous_ms:.2f} -> {value:.2f} ms ({value - previous_ms:+.2f} ms)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=2, help="Browser workers")
    parser.add_argument("--tag", help="Version tag when rehearsing a prepared release")
    parser.add_argument("--expected-commit", help="Commit recorded before the full source checks")
    parser.add_argument("--dist", type=Path, help="Promote checksummed artifacts to this directory")
    parser.add_argument("--skip-wheel", action="store_true", help="Run the source journeys and corpus only")
    parser.add_argument("--compare", nargs=2, metavar=("PREVIOUS", "CURRENT"), type=Path,
                        help="Compare two recorded runs without starting checks")
    args = parser.parse_args()
    if args.jobs < 1 or (args.skip_wheel and args.dist is not None):
        parser.error("Use a positive worker count and request a build when specifying --dist")
    try:
        if args.compare:
            compare(*args.compare)
            return 0
        return rehearse(jobs=args.jobs, tag=args.tag, dist=args.dist, skip_wheel=args.skip_wheel,
                        expected_commit=args.expected_commit)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError) as exc:
        print(f"Release rehearsal failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
