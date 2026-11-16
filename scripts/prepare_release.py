#!/usr/bin/env python3
"""Prepare a release: bump version, scaffold release notes and synchronize docs.

Usage:
    python3 scripts/prepare_release.py 0.8.1
    make release-prepare VERSION=0.8.1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate_version(version: str) -> tuple[int, int, int]:
    clean = version.lstrip("v")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", clean)
    if not match:
        raise ValueError(f"Version must be in semantic format X.Y.Z (e.g. 0.8.1), got: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def update_version_file(version: str) -> None:
    path = ROOT / "src/lixity/_version.py"
    content = f'__version__ = "{version}"\n'
    path.write_text(content, encoding="utf-8")
    print(f"[OK] Updated {path.relative_to(ROOT)} to {version}")


def scaffold_release_notes(version: str) -> Path:
    target = ROOT / "docs/releases" / f"v{version}.md"
    if target.exists():
        print(f"[NOTE] Release notes already exist at {target.relative_to(ROOT)}")
        return target
    template = f"""# Lixity v{version}

Pending release. Publication date and verification results have not been recorded.

## Highlights

- Pending maintainer review of the changes in this release.

## Changes

- Pending review. Describe the actual changes and any migration requirements.

## Verification (pending)

```bash
make release-check RELEASE_TAG=v{version}
```

Record completed command results, tested platforms and any skips after running the checks.

## Publication (pending)

Record the publication date and GitHub, PyPI and website checks after publication.
"""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(template, encoding="utf-8")
    print(f"[OK] Scaffolded release notes at {target.relative_to(ROOT)}")
    return target


def run_sync() -> None:
    from sync_docs import check_or_sync_files, get_version
    version = get_version()
    drift = check_or_sync_files(version, check_only=False)
    if drift:
        print(f"[OK] Synchronized version pins in {len(drift)} files: {', '.join(drift)}")
    else:
        print("[OK] Version pins already synchronized.")


def preparation_snapshot(version: str) -> dict[Path, bytes | None]:
    """Capture files preparation can change, including pins written before a sync failure."""
    paths = {ROOT / "src/lixity/_version.py", ROOT / "README.md", ROOT / "CITATION.cff",
             ROOT / "docs/releases" / f"v{version}.md"}
    for pattern in ("*.md", "*.html", "*.txt"):
        paths.update((ROOT / "docs").rglob(pattern))
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def report_partial_changes(before: dict[Path, bytes | None]) -> None:
    """Report retained edits without claiming that multi-file preparation is atomic."""
    changed = []
    unknown = []
    for path, contents in before.items():
        try:
            current = path.read_bytes() if path.is_file() else None
        except OSError:
            unknown.append(str(path.relative_to(ROOT)))
            continue
        if current != contents:
            changed.append(str(path.relative_to(ROOT)))
    if changed:
        print("[NOTE] Changes already made (not rolled back):", file=sys.stderr)
        for path in sorted(changed):
            print(f"  {path}", file=sys.stderr)
    if unknown:
        print("[NOTE] Could not inspect possible changes: " + ", ".join(sorted(unknown)),
              file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="New version in X.Y.Z format (e.g. 0.8.1)")
    args = parser.parse_args()

    before: dict[Path, bytes | None] = {}
    try:
        parts = validate_version(args.version)
        version_str = f"{parts[0]}.{parts[1]}.{parts[2]}"
        before = preparation_snapshot(version_str)
        print(f"--- Preparing Lixity release v{version_str} ---")
        update_version_file(version_str)
        scaffold_release_notes(version_str)
        # Import sync_docs from scripts dir
        sys.path.insert(0, str(ROOT / "scripts"))
        run_sync()
        print("\nNext steps:")
        print(f"  1. Review and refine docs/releases/v{version_str}.md")
        print("  2. If UI changed: make examples && make docs-sync")
        print(f"  3. Validate release: make release-check RELEASE_TAG=v{version_str}")
        print(f"  4. Commit and tag: git tag -a v{version_str} -m 'Release v{version_str}'")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary must report retained partial edits
        print(f"[ERROR] Release preparation failed: {exc}", file=sys.stderr)
        report_partial_changes(before)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
