#!/usr/bin/env python3
"""Run the focused portability or full packaged research/lifecycle checks."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SCOPES = ("portability", "full")

# Include established test families and name workflows split across other files.
FULL_PATTERNS = (
    "test_research*.py",
    "test_dossier*.py",
    "test_server_research*.py",
    "test_service*.py",
    "test_launcher*.py",
)
FULL_FILES = (
    "test_export_source_guard.py",
    "test_manuscript_dossier_confirmation.py",
    "test_manuscript_dossier_drafts.py",
    "test_manuscript_import.py",
    "test_manuscript_terms.py",
    "test_project_settings_write.py",
    "test_server_project_author.py",
    "test_server_startup.py",
)


def full_native_tests(root: Path = ROOT) -> list[Path]:
    tests = root / "tests"
    candidates = {tests / filename for filename in FULL_FILES}
    missing = sorted(path.name for path in candidates if not path.is_file())
    for pattern in FULL_PATTERNS:
        members = {path for path in tests.glob(pattern) if path.is_file()}
        if not members:
            missing.append(pattern)
        candidates.update(members)
    if missing:
        raise ValueError("Missing native test scope entries: " + ", ".join(missing))
    return sorted(path.relative_to(root) for path in candidates)


def native_pytest_args(scope: str, root: Path = ROOT) -> list[str]:
    if scope == "portability":
        return ["tests", "-m", "portability"]
    if scope == "full":
        return [str(path) for path in full_native_tests(root)]
    raise ValueError(f"Unsupported native check scope: {scope}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=NATIVE_SCOPES, default=os.environ.get("NATIVE_SCOPE", "portability"))
    parser.add_argument("--collect-only", action="store_true", help="Show selected tests without executing them")
    args = parser.parse_args()
    try:
        selected = native_pytest_args(args.scope)
    except ValueError as exc:
        parser.error(str(exc))
    command = [sys.executable, "-m", "pytest", *selected, "-W", "error", "-q", "-rs", "-p", "no:asyncio"]
    if args.collect_only:
        command.append("--collect-only")
    # Invoking pytest from the repository finds its support tooling and imports
    # Lixity from the selected environment, as the packaged CI gate requires.
    return subprocess.run(command, cwd=ROOT, check=False).returncode  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
