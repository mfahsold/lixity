#!/usr/bin/env python3
"""Build the public copies of the app's localized metric reference."""

import argparse
from pathlib import Path

from lixity.status import LANGUAGE_CODES
from lixity.ui.metric_reference import METRIC_REFERENCE_PATH, metric_reference_document

ROOT = Path(__file__).resolve().parents[1]


def build(check_only: bool = False, *, root: Path = ROOT) -> list[str]:
    """Write or check the seven HTML copies, returning the changed file names."""
    directory = root / "docs" / METRIC_REFERENCE_PATH.strip("/")
    if not check_only:
        directory.mkdir(parents=True, exist_ok=True)
    changed = []
    for language in LANGUAGE_CODES:
        if language == "generic":
            continue
        path = directory / f"{language}.html"
        rendered = metric_reference_document(language).encode("utf-8")
        if not path.is_file() or path.read_bytes() != rendered:
            changed.append(path.relative_to(root).as_posix())
            if not check_only:
                path.write_bytes(rendered)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check without writing files")
    args = parser.parse_args()
    changed = build(check_only=args.check)
    if args.check:
        if changed:
            print("Stale metric reference pages; run make docs-sync: " + ", ".join(changed))
        return int(bool(changed))
    print(f"Updated {len(changed)} metric reference page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
