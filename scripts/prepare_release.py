#!/usr/bin/env python3
"""Prepare a release: bump version, scaffold release notes and synchronize docs.

Usage:
    python3 scripts/prepare_release.py X.Y.Z
    make release-prepare VERSION=X.Y.Z
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

try:
    from check_release import PENDING_RELEASE, RELEASE_HEADING
except ModuleNotFoundError:
    from scripts.check_release import PENDING_RELEASE, RELEASE_HEADING

ROOT = Path(__file__).resolve().parents[1]
UNRELEASED_COMPARE = re.compile(
    r"(?m)^\[Unreleased\]: (https://github\.com/[^/]+/[^/]+/compare/)v\d+\.\d+\.\d+\.\.\.HEAD$"
)


def validate_version(version: str) -> tuple[int, int, int]:
    clean = version.lstrip("v")
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", clean)
    if not match:
        raise ValueError(f"Version must be in semantic format X.Y.Z, got: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def validate_release_date(value: str) -> str:
    try:
        date = datetime.date.fromisoformat(value)
    except ValueError:
        date = None
    if date is None or date.isoformat() != value:
        raise ValueError("release date must use YYYY-MM-DD")
    return value


def update_version_file(version: str) -> None:
    path = ROOT / "src/lixity/_version.py"
    content = f'__version__ = "{version}"\n'
    path.write_text(content, encoding="utf-8")
    print(f"[OK] Updated {path.relative_to(ROOT)} to {version}")


def update_desktop_manifests(version: str, *, release_date: str | None = None) -> None:
    """Keep desktop Rust/Tauri and Linux AppStream manifests aligned with __version__."""
    cargo_toml = ROOT / "desktop/Cargo.toml"
    if cargo_toml.is_file():
        text = cargo_toml.read_text(encoding="utf-8")
        updated, count = re.subn(
            r'(?m)^version = "\d+\.\d+\.\d+"$',
            f'version = "{version}"',
            text,
            count=1,
        )
        if count == 1 and updated != text:
            cargo_toml.write_text(updated, encoding="utf-8")
            print(f"[OK] Updated {cargo_toml.relative_to(ROOT)} to {version}")

    tauri_conf = ROOT / "desktop/src-tauri/tauri.conf.json"
    if tauri_conf.is_file():
        data = json.loads(tauri_conf.read_text(encoding="utf-8"))
        if data.get("version") != version:
            data["version"] = version
            tauri_conf.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"[OK] Updated {tauri_conf.relative_to(ROOT)} to {version}")

    metainfo = ROOT / "desktop/packaging/linux/io.github.mfahsold.Lixity.metainfo.xml"
    if metainfo.is_file():
        text = metainfo.read_text(encoding="utf-8")
        date_attr = f' date="{release_date}"' if release_date else ""
        entry = (
            f'    <release version="{version}"{date_attr}>\n'
            f'      <url type="details">https://github.com/mfahsold/lixity/releases/tag/v{version}</url>\n'
            f'    </release>'
        )
        existing = re.compile(
            rf'    <release version="{re.escape(version)}"[^>]*>\n.*?\n    </release>',
            re.DOTALL,
        )
        if existing.search(text):
            updated = existing.sub(lambda _: entry, text, count=1)
        elif "  <releases>\n" in text:
            updated = text.replace("  <releases>\n", f"  <releases>\n{entry}\n", 1)
        else:
            updated = text
        if updated != text:
            metainfo.write_text(updated, encoding="utf-8")
            print(f"[OK] Updated {metainfo.relative_to(ROOT)} for {version}")


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


def update_changelog(version: str, *, release_date: str | None = None) -> None:
    """Prepare a pending changelog section or record an explicit release date."""
    path = ROOT / "CHANGELOG.md"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    date = validate_release_date(release_date) if release_date is not None else None
    current = next((heading for heading in RELEASE_HEADING.finditer(text)
                    if heading[1] == version), None)
    if current is None:
        if "## [Unreleased]" not in text:
            return
        status = date or PENDING_RELEASE
        updated = text.replace("## [Unreleased]", f"## [Unreleased]\n\n## [{version}] - {status}", 1)
    else:
        status = current[2]
        if date is not None and status not in {PENDING_RELEASE, date}:
            raise ValueError(f"changelog already records {status} for v{version}")
        status = date or status
        updated = text[:current.start(2)] + status + text[current.end(2):]

    all_headings = list(RELEASE_HEADING.finditer(updated))
    latest_dated = next((heading[1] for heading in all_headings if heading[2] != PENDING_RELEASE), None)
    headings = iter(all_headings)
    current = next(heading for heading in headings if heading[1] == version)
    # Changelog order records the release line, including version-number resets.
    previous = next((heading[1] for heading in headings if heading[2] != PENDING_RELEASE), None)
    compare = UNRELEASED_COMPARE.search(updated)
    if compare is not None and latest_dated is not None:
        base = compare[1]
        unreleased_link = f"[Unreleased]: {base}v{latest_dated}...HEAD"
        if previous is not None:
            candidate_to = "HEAD" if current[2] == PENDING_RELEASE else f"v{version}"
            release_link = f"[{version}]: {base}v{previous}...{candidate_to}"
            version_link = re.compile(rf"(?m)^\[{re.escape(version)}\]: [^\n]*$")
            if version_link.search(updated) is None:
                unreleased_link += f"\n{release_link}"
            else:
                updated = version_link.sub(lambda _: release_link, updated, count=1)
        updated = UNRELEASED_COMPARE.sub(lambda _: unreleased_link, updated, count=1)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(f"[OK] Updated {path.relative_to(ROOT)} for {version}")


def run_sync() -> None:
    from check_release import source_version
    from sync_docs import check_or_sync_generated

    version = source_version(ROOT)
    updated = check_or_sync_generated(version, check_only=False, root=ROOT)
    if updated:
        print(f"[OK] Synchronized documentation in {len(updated)} files: {', '.join(updated)}")
    else:
        print("[OK] Documentation already synchronized.")

    remaining = check_or_sync_generated(version, check_only=True, root=ROOT)
    if remaining:
        raise RuntimeError(f"Generated documentation remains out of sync: {', '.join(remaining)}")


def preparation_snapshot(version: str) -> dict[Path, bytes | None]:
    """Capture files preparation can change, including pins written before a sync failure."""
    paths = {
        ROOT / "src/lixity/_version.py",
        ROOT / "README.md",
        ROOT / "CITATION.cff",
        ROOT / "CHANGELOG.md",
        ROOT / "docs/releases" / f"v{version}.md",
        ROOT / "desktop/Cargo.toml",
        ROOT / "desktop/src-tauri/tauri.conf.json",
        ROOT / "desktop/packaging/linux/io.github.mfahsold.Lixity.metainfo.xml",
    }
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
    parser.add_argument("version", help="New version in X.Y.Z format")
    parser.add_argument("--release-date", help="Reviewed release date in YYYY-MM-DD")
    args = parser.parse_args()

    before: dict[Path, bytes | None] = {}
    try:
        parts = validate_version(args.version)
        version_str = f"{parts[0]}.{parts[1]}.{parts[2]}"
        release_date = validate_release_date(args.release_date) if args.release_date is not None else None
        before = preparation_snapshot(version_str)
        print(f"--- Preparing Lixity release v{version_str} ---")
        update_version_file(version_str)
        update_desktop_manifests(version_str, release_date=release_date)
        update_changelog(version_str, release_date=release_date)
        scaffold_release_notes(version_str)
        # Import sync_docs from scripts dir
        sys.path.insert(0, str(ROOT / "scripts"))
        run_sync()
        print("\nNext steps:")
        print(f"  1. Review and refine docs/releases/v{version_str}.md")
        print("  2. Follow the documentation generation and preview procedure in CONTRIBUTING.md")
        print(f"  3. Validate release: make release-check RELEASE_TAG=v{version_str}")
        print("  4. Follow the release qualification and publication procedure in CONTRIBUTING.md")
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary must report retained partial edits
        print(f"[ERROR] Release preparation failed: {exc}", file=sys.stderr)
        report_partial_changes(before)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
