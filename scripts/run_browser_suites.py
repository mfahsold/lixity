#!/usr/bin/env python3
"""Run the local browser regression suites in one Chromium at a time.

Every ``tests/browser/*.cjs`` file is an independent suite. ``--group fast``
runs the everyday core surfaces; ``--group full`` (the default) runs every
suite and belongs before a release. ``--jobs N`` runs N independent suites in
parallel and keeps the machine reasonably busy; the suites do not share state.
Playwright and Chromium are optional developer tools; ``tests/browser/README.md``
documents installation and environment overrides. The same script backs the
manual ``browser`` workflow dispatch, so local and CI runs stay aligned.
"""

import argparse
import concurrent.futures
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "tests" / "browser"

# Everyday coverage for UI work; run every suite before a release.
GROUPS: dict[str, tuple[str, ...]] = {
    "fast": (
        "layout.cjs",
        "minimal-workflows.cjs",
        "project-controls.cjs",
        "research.cjs",
        "scenes.cjs",
        "settings.cjs",
        "ui-usability.cjs",
        "visual-consistency.cjs",
    ),
}


def suite_names() -> list[str]:
    """Return every registered browser suite in deterministic order."""
    return [path.name for path in sorted(SUITE_DIR.glob("*.cjs"))]


def run_suite(node: str, name: str, capture: bool) -> tuple[str, float, int, str]:
    """Run one suite; capture its output when suites share the terminal."""
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 - fixed node binary, local reviewed suites
        [node, str(SUITE_DIR / name)],
        cwd=ROOT,
        check=False,
        capture_output=capture,
        text=True,
    )
    output = ((result.stdout or "") + (result.stderr or "")) if capture else ""
    return name, time.monotonic() - started, result.returncode, output


def run_parallel(node: str, names: list[str], jobs: int) -> int:
    """Run independent suites in parallel and report atomically per suite."""
    print(f"Running {len(names)} suites with {jobs} parallel workers.", flush=True)
    started = time.monotonic()
    failures: list[tuple[str, int]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_suite, node, name, True) for name in names]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            name, seconds, code, output = future.result()
            print(f"[{index}/{len(names)}] {name} ({seconds:.1f}s)", flush=True)
            if output.strip():
                print(output.rstrip(), flush=True)
            if code:
                failures.append((name, code))
                print(f"Failed: {name} (exit {code})", file=sys.stderr, flush=True)
    if failures:
        name, code = failures[0]
        print(f"Resume after the fix with: --start {name}", file=sys.stderr, flush=True)
        return code
    print(f"All {len(names)} browser suites passed in {time.monotonic() - started:.1f}s.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List suite filenames and exit")
    parser.add_argument("--only", nargs="+", metavar="SUITE", help="Run only these suites")
    parser.add_argument("--group", choices=("fast", "full"), default="full",
                        help="Run the everyday fast group or every suite (default: full)")
    parser.add_argument("--jobs", type=int, default=1, metavar="N",
                        help="Run N independent suites in parallel (default: 1)")
    parser.add_argument("--start", metavar="SUITE", help="Resume at this suite after a failure")
    arguments = parser.parse_args()

    names = suite_names()
    if not names:
        print("No browser suites found under tests/browser/.", file=sys.stderr)
        return 2

    def normalize(value: str) -> str:
        return value if value.endswith(".cjs") else value + ".cjs"

    if arguments.only:
        requested = {normalize(value) for value in arguments.only}
        unknown = sorted(requested - set(names))
        if unknown:
            parser.error("Unknown suites: " + ", ".join(unknown))
        names = [name for name in names if name in requested]
    else:
        if arguments.group == "fast":
            fast = set(GROUPS["fast"])
            unknown = sorted(fast - set(names))
            if unknown:
                parser.error("Unknown suites in group fast: " + ", ".join(unknown))
            names = [name for name in names if name in fast]
        if arguments.start:
            start = normalize(arguments.start)
            if start not in names:
                parser.error(f"Unknown suite: {start}")
            names = names[names.index(start) :]

    if arguments.list:
        print("\n".join(names))
        return 0

    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the browser suites.", file=sys.stderr)
        return 2

    if arguments.jobs > 1:
        if arguments.jobs > len(names):
            parser.error("--jobs cannot exceed the number of selected suites")
        return run_parallel(node, names, arguments.jobs)

    started = time.monotonic()
    for index, name in enumerate(names, start=1):
        print(f"[{index}/{len(names)}] {name}", flush=True)
        _name, seconds, code, _output = run_suite(node, name, False)
        if code:
            print(f"Failed: {name} (exit {code}, {seconds:.1f}s)", file=sys.stderr)
            print(f"Resume after the fix with: --start {name}", file=sys.stderr)
            return code
        print(f"Passed: {name} ({seconds:.1f}s)", flush=True)
    print(f"All {len(names)} browser suites passed in {time.monotonic() - started:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
