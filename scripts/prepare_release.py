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
from datetime import datetime, timezone
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
    today = datetime.now(timezone.utc).date().isoformat()
    template = f"""# Lixity v{version}

Released on {today}.

## Highlights

- Continuous manuscript reader with responsive single-row controls and unified search.
- Native manuscript analysis, localized diagnostics and offline deterministic stats.
- Privacy-first reading website exports and research dossiers.

## Changes

### User Interface & Experience
- Seamlessly docked search toolbar with glassmorphism styling and quick keyboard shortcuts (`Ctrl+F`, `/`).
- Enriched DevTools console logging with styled badges and transparent performance tracking.

### Reliability & Verification
- Full offline test suite passing under `-W error`.
- Synchronized documentation version claims and verified example artifacts.

## Verification

```bash
make release-check RELEASE_TAG=v{version}
```
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="New version in X.Y.Z format (e.g. 0.8.1)")
    args = parser.parse_args()

    try:
        parts = validate_version(args.version)
        version_str = f"{parts[0]}.{parts[1]}.{parts[2]}"
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
    except (ValueError, OSError) as exc:
        print(f"[ERROR] Release preparation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
