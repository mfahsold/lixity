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
import sys
from pathlib import Path

try:
    from check_release import source_version
except ModuleNotFoundError:
    from scripts.check_release import source_version

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "llms-full.txt"

#: Task index, operational guides, interpretation and coverage, then contracts.
SOURCES: tuple[Path, ...] = (
    Path("docs/llms.txt"),
    Path("docs/README.md"),
    Path("docs/USAGE.md"),
    Path("docs/WORKSPACE.md"),
    Path("docs/AUDIO.md"),
    Path("docs/research/USAGE.md"),
    Path("docs/METHODS.md"),
    Path("docs/STABILITY.md"),
    Path("docs/LOCALIZATION.md"),
    Path("docs/AGENTS.md"),
)

SEPARATOR = "\n" + "=" * 79 + "\n"


def get_version(root: Path | None = None) -> str:
    """Read the product version from its single source of truth."""
    return source_version(ROOT if root is None else root)


def build_bundle(root: Path | None = None) -> str:
    """Return the deterministic bundle text for the current source tree."""
    base = ROOT if root is None else root
    header = (
        "# Lixity - operational reference bundle\n"
        "\n"
        "> Generated file for AI agents and offline reading. Do not edit it by hand:\n"
        "> run `python scripts/build_llms_full.py` after changing a bundled document.\n"
        f"> The individually published files remain authoritative. Product version {get_version(base)}.\n"
        "\n"
        "Lixity is open source under AGPL-3.0-or-later; writing for any purpose is\n"
        "covered. A separate written commercial license exists only for closed-source\n"
        "integrations that cannot meet the AGPL.\n"
        "\n"
        "Scope: CLI, workspace, audio, research, automation contracts, methods, stability and\n"
        "localization. See the llms.txt index for setup, architecture, storage internals\n"
        "and design history. These linked references are not bundled here.\n"
        "\n"
        "Links inside a section are relative to that file's directory in the repository;\n"
        "use the source URL printed above each section to resolve them.\n"
    )
    sections: list[str] = []
    for relative in SOURCES:
        path = base / relative
        text = path.read_text(encoding="utf-8").rstrip("\n")
        source_url = f"https://github.com/mfahsold/lixity/blob/main/{relative.as_posix()}"
        sections.append(f"## {relative.as_posix()}\n\nSource: {source_url}\n\n{text}\n")
    return header + SEPARATOR.join(["", *sections])


def build(*, check_only: bool = False, root: Path | None = None) -> list[str]:
    """Generate ``docs/llms-full.txt``; return changed or outdated relative paths."""
    base = ROOT if root is None else root
    output = OUTPUT if root is None else base / "docs" / "llms-full.txt"
    expected = build_bundle(base)
    current = output.read_text(encoding="utf-8") if output.is_file() else ""
    if current == expected:
        return []
    rel = str(output.relative_to(base))
    if not check_only:
        output.write_text(expected, encoding="utf-8")
    return [rel]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check the committed bundle without writing"
    )
    args = parser.parse_args()

    outdated = build(check_only=args.check)
    if args.check:
        if outdated:
            print(
                f"{OUTPUT.relative_to(ROOT)} is outdated; run 'python scripts/build_llms_full.py'",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is up to date.")
        return 0

    expected_len = len(OUTPUT.read_text(encoding="utf-8"))
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({expected_len:,} characters).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
