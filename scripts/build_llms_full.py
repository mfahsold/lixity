"""Build the agent-facing full-text bundle ``docs/llms-full.txt``.

The bundle concatenates current operational references in reading order for
AI agents and offline readers. ``llms.txt`` indexes the complete documentation;
setup, architecture, storage internals and history stay linked rather than
duplicated here. Keep full reference text so contracts and caveats remain intact.

Run this script after changing any bundled document; ``make docs-check`` and
``tests/test_documentation.py`` fail while the committed bundle is outdated.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "llms-full.txt"

#: Task index, operational guides, interpretation and coverage, then contracts.
SOURCES: tuple[Path, ...] = (
    Path("docs/llms.txt"),
    Path("docs/USAGE.md"),
    Path("docs/research/USAGE.md"),
    Path("docs/METHODS.md"),
    Path("docs/STABILITY.md"),
    Path("docs/LOCALIZATION.md"),
    Path("docs/AGENTS.md"),
)

SEPARATOR = "\n" + "=" * 79 + "\n"


def get_version() -> str:
    """Read the product version from its single source of truth."""
    version_file = ROOT / "src" / "lixity" / "_version.py"
    match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Cannot find __version__ in src/lixity/_version.py")
    return match.group(1)


def build_bundle() -> str:
    """Return the deterministic bundle text for the current source tree."""
    header = (
        "# Lixity - operational reference bundle\n"
        "\n"
        "> Generated file for AI agents and offline reading. Do not edit it by hand:\n"
        "> run `python scripts/build_llms_full.py` after changing a bundled document.\n"
        f"> The individually published files remain authoritative. Product version {get_version()}.\n"
        "\n"
        "Lixity is open source under AGPL-3.0-or-later; writing for any purpose is\n"
        "covered. A separate written commercial license exists only for closed-source\n"
        "integrations that cannot meet the AGPL.\n"
        "\n"
        "Scope: current usage, research, automation contracts, methods, stability and\n"
        "localization. See the llms.txt index for setup, architecture, storage internals\n"
        "and design history. These linked references are not bundled here.\n"
        "\n"
        "Links inside a section are relative to that file's directory in the repository;\n"
        "use the source URL printed above each section to resolve them.\n"
    )
    sections: list[str] = []
    for relative in SOURCES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8").rstrip("\n")
        source_url = f"https://github.com/mfahsold/lixity/blob/main/{relative.as_posix()}"
        sections.append(f"## {relative.as_posix()}\n\nSource: {source_url}\n\n{text}\n")
    return header + SEPARATOR.join(["", *sections])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check the committed bundle without writing"
    )
    args = parser.parse_args()

    expected = build_bundle()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
        if current != expected:
            print(
                f"{OUTPUT.relative_to(ROOT)} is outdated; run 'python scripts/build_llms_full.py'",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is up to date.")
        return 0

    OUTPUT.write_text(expected, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(expected):,} characters).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
