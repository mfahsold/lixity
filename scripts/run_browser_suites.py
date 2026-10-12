#!/usr/bin/env python3
"""Run the local browser regression suites in one Chromium at a time.

Every ``tests/browser/*.cjs`` file is an independent suite. Playwright and
Chromium are optional developer tools; ``tests/browser/README.md`` documents
installation and environment overrides. The same script backs the manual
``browser`` workflow dispatch, so local and CI runs stay aligned.
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "tests" / "browser"


def suite_names() -> list[str]:
    """Return every registered browser suite in deterministic order."""
    return [path.name for path in sorted(SUITE_DIR.glob("*.cjs"))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List suite filenames and exit")
    parser.add_argument("--only", nargs="+", metavar="SUITE", help="Run only these suites")
    parser.add_argument("--start", metavar="SUITE", help="Resume at this suite after a failure")
    arguments = parser.parse_args()

    names = suite_names()
    if arguments.list:
        print("\n".join(names))
        return 0
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
    elif arguments.start:
        start = normalize(arguments.start)
        if start not in names:
            parser.error(f"Unknown suite: {start}")
        names = names[names.index(start) :]

    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the browser suites.", file=sys.stderr)
        return 2

    started = time.monotonic()
    for index, name in enumerate(names, start=1):
        print(f"[{index}/{len(names)}] {name}", flush=True)
        suite_started = time.monotonic()
        result = subprocess.run(  # noqa: S603 - fixed node binary, local reviewed suites
            [node, str(SUITE_DIR / name)],
            cwd=ROOT,
            check=False,
        )
        seconds = time.monotonic() - suite_started
        if result.returncode:
            print(f"Failed: {name} (exit {result.returncode}, {seconds:.1f}s)", file=sys.stderr)
            print(f"Resume after the fix with: --start {name}", file=sys.stderr)
            return result.returncode
        print(f"Passed: {name} ({seconds:.1f}s)", flush=True)
    print(f"All {len(names)} browser suites passed in {time.monotonic() - started:.1f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
