#!/usr/bin/env python3
"""Maintain and synchronize version references and links across documentation files.

Ensures Single-Source-of-Truth (SSOT) consistency based on src/lixity/_version.py.
Usage:
    python scripts/sync_docs.py          # Synchronize documentation files
    python scripts/sync_docs.py --check  # Check for version drift without writing (exit 1 on drift)
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_version() -> str:
    version_file = ROOT / "src" / "lixity" / "_version.py"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Cannot find __version__ in src/lixity/_version.py")
    return match.group(1)


def check_or_sync_files(version: str, *, check_only: bool = False) -> list[str]:
    """Check or update version references across documentation files."""
    drift_files: list[str] = []

    # Rules: (file_path, list of (pattern, replacement))
    rules: list[tuple[Path, list[tuple[str, str]]]] = [
        (
            ROOT / "README.md",
            [
                (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
                 f"git+https://github.com/mfahsold/lixity.git@v{version}"),
                (r"This installs \*\*v\d+\.\d+\.\d+\*\*",
                 f"This installs **v{version}**"),
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
            ],
        ),
        (
            ROOT / "docs" / "INSTALLATION.md",
            [
                (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
                 f"git+https://github.com/mfahsold/lixity.git@v{version}"),
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
            ],
        ),
        (
            ROOT / "docs" / "USAGE.md",
            [
                (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
                 f"git+https://github.com/mfahsold/lixity.git@v{version}"),
                (r"`v\d+\.\d+\.\d+` is the release pin",
                 f"`v{version}` is the release pin"),
            ],
        ),
        (
            ROOT / "docs" / "llms.txt",
            [
                (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
                 f"git+https://github.com/mfahsold/lixity.git@v{version}"),
                (r"replace `@v\d+\.\d+\.\d+` with `@main`",
                 f"replace `@v{version}` with `@main`"),
                (r"Current release: \d+\.\d+\.\d+; release tag: v\d+\.\d+\.\d+",
                 f"Current release: {version}; release tag: v{version}"),
                (r"release history \(current: \d+\.\d+\.\d+\)",
                 f"release history (current: {version})"),
            ],
        ),
        (
            ROOT / "docs" / "index.html",
            [
                (r'"softwareVersion": "\d+\.\d+\.\d+"',
                 f'"softwareVersion": "{version}"'),
                (r'<span class="brand-badge">v\d+\.\d+\.\d+</span>',
                 f'<span class="brand-badge">v{version}</span>'),
                (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
                 f"git+https://github.com/mfahsold/lixity.git@v{version}"),
            ],
        ),
    ]

    for file_path, replacements in rules:
        if not file_path.is_file():
            continue
        original = file_path.read_text(encoding="utf-8")
        updated = original
        for pattern, repl in replacements:
            updated = re.sub(pattern, repl, updated)

        if updated != original:
            rel_name = str(file_path.relative_to(ROOT))
            drift_files.append(rel_name)
            if not check_only:
                file_path.write_text(updated, encoding="utf-8")

    return drift_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check for version drift without writing changes")
    args = parser.parse_args()

    version = get_version()
    drift = check_or_sync_files(version, check_only=args.check)

    if args.check:
        if drift:
            print(f"Documentation version drift detected for version {version}:", file=sys.stderr)
            for f in drift:
                print(f"  - {f}", file=sys.stderr)
            print("Run 'python scripts/sync_docs.py' to update documentation files.", file=sys.stderr)
            return 1
        print(f"Documentation versions are synchronized with v{version}.")
        return 0

    if drift:
        print(f"Synchronized documentation files to v{version}:")
        for f in drift:
            print(f"  - {f}")
    else:
        print(f"Documentation files are already synchronized with v{version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
