#!/usr/bin/env python3
"""Maintain and synchronize version references and links across documentation files.

Ensures Single-Source-of-Truth (SSOT) consistency based on src/lixity/_version.py.
Usage:
    python scripts/sync_docs.py          # Synchronize documentation files
    python scripts/sync_docs.py --check  # Check for version drift without writing (exit 1 on drift)

Two separate things happen here, and they answer different questions.

1. Synchronisation rewrites a known list of pinned strings (install URLs, version
   badges, "the current release is"). This is convenience, not verification.

2. The drift check is the actual invariant: across every current-documentation
   file, each version token must either equal the SSOT version or sit in a
   context that marks it as talking about the past. Anything else is drift.

The distinction matters because the rewrite list is necessarily incomplete: it
can only cover phrasings somebody thought to enumerate. A check built only on
"is there anything left for my own list to rewrite" is a tautology that reports
success after its first run and can never notice a stale claim in wording it
does not know, which is exactly how the site came to advertise a two-releases-
old version while every check stayed green.
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

    # Static guides share the release-install convention with the main docs.
    rules.extend((guide, [
        (r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
         f"git+https://github.com/mfahsold/lixity.git@v{version}"),
    ]) for guide in sorted((ROOT / "docs" / "guides").glob("*.html")))

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


# Files that describe the present release. docs/releases/ is excluded: past
# release notes exist precisely to name old versions.
def current_doc_files() -> list[Path]:
    files = [ROOT / "README.md"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    files += sorted((ROOT / "docs").rglob("*.html"))
    files += sorted((ROOT / "docs").rglob("*.txt"))
    return [
        f for f in files
        if f.is_file() and "releases" not in f.relative_to(ROOT).parts
    ]


# Phrases that assert, by construction, which version is current. Each must
# name the SSOT version; a mismatch means the documentation is describing a
# release that is no longer current.
#
# The list is deliberately narrow. A wider sweep over every version-shaped token
# is not usable here: it matches 127.0.0 inside 127.0.0.1, and it flags every
# third-party version (pdfjs, tesseract, pypdf) as if it were a stale Lixity
# pin. Retrospective prose such as "Release v1.20.0 adds ..." is legitimate and
# is intentionally not matched. What is matched is the class of wording that is
# wrong whenever it drifts.
CURRENT_CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("current release statement",
     re.compile(r"current release(?:\s+is)?[\s:*>]*\**v?(\d+\.\d+\.\d+)", re.I)),
    ("release tag pin",
     re.compile(r"release tag:\s*v(\d+\.\d+\.\d+)", re.I)),
    ("release history pin",
     re.compile(r"release history\s*\(current:\s*(\d+\.\d+\.\d+)\)", re.I)),
    ("what's-new heading",
     re.compile(r"New in v(\d+\.\d+\.\d+)")),
    ("screenshot currency claim",
     re.compile(r"current main and release v(\d+\.\d+\.\d+)", re.I)),
    ("install statement",
     re.compile(r"This installs \*\*v(\d+\.\d+\.\d+)\*\*")),
    ("pip install pin",
     re.compile(r"lixity\.git@v(\d+\.\d+\.\d+)")),
    ("JSON-LD softwareVersion",
     re.compile(r'"softwareVersion":\s*"(\d+\.\d+\.\d+)"')),
    ("header version badge",
     re.compile(r'class="brand-badge">v(\d+\.\d+\.\d+)<')),
    ("hero version badge",
     re.compile(r"<span>v(\d+\.\d+\.\d+)\s*(?:&middot;|·)", re.I)),
    ("meta description version",
     re.compile(r'content="[^"]*?\bv(\d+\.\d+\.\d+)', re.I)),
)


def find_version_drift(version: str) -> list[str]:
    """Report current-version claims that do not match the SSOT version."""
    findings: list[str] = []
    for file_path in current_doc_files():
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in CURRENT_CLAIMS:
                for match in pattern.finditer(line):
                    if match.group(1) != version:
                        rel = file_path.relative_to(ROOT)
                        findings.append(
                            f"{rel}:{lineno}: {label} names v{match.group(1)}, "
                            f"but the current release is v{version}"
                        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check for version drift without writing changes")
    args = parser.parse_args()

    version = get_version()
    drift = check_or_sync_files(version, check_only=args.check)

    if args.check:
        # The invariant is independent of the rewrite list: a file can need no
        # rewriting and still be making a stale current-version claim.
        stale = find_version_drift(version)
        if drift or stale:
            print(f"Documentation version drift detected for version {version}:", file=sys.stderr)
            for f in drift:
                print(f"  - needs sync: {f}", file=sys.stderr)
            for f in stale:
                print(f"  - {f}", file=sys.stderr)
            if stale:
                print(
                    "These statements name the release the documentation claims is\n"
                    "  current. Update them, or if the sentence is genuinely about the\n"
                    "  past, reword it as history ('since v1.20.0', 'Release v1.20.0\n"
                    "  adds ...') so it is no longer a currency claim.",
                    file=sys.stderr,
                )
            print("Run 'python scripts/sync_docs.py' to update pinned documentation files.", file=sys.stderr)
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
