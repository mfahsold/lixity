#!/usr/bin/env python3
"""Synchronize release pins and check current-version claims in documentation.

The version comes from src/lixity/_version.py. Run with --check to report drift
without changing files. Rewriting handles known pins; the separate claim scan
also checks wording outside that list. Historical release notes and third-party
versions are not treated as current Lixity claims.
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

    install_pin = (
        r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
        f"git+https://github.com/mfahsold/lixity.git@v{version}",
    )
    # Rules: (file_path, list of (pattern, replacement))
    rules: list[tuple[Path, list[tuple[str, str]]]] = [
        (
            ROOT / "README.md",
            [
                install_pin,
                (r"This installs \*\*v\d+\.\d+\.\d+\*\*",
                 f"This installs **v{version}**"),
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
                (r"\[v\d+\.\d+\.\d+ release notes\]\(docs/releases/v\d+\.\d+\.\d+\.md\)",
                 f"[v{version} release notes](docs/releases/v{version}.md)"),
                (r"\[Release notes\]\(docs/releases/v\d+\.\d+\.\d+\.md\)",
                 f"[Release notes](docs/releases/v{version}.md)"),
            ],
        ),
        (
            ROOT / "docs" / "INSTALLATION.md",
            [
                install_pin,
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
                (r"\[release notes\]\(releases/v\d+\.\d+\.\d+\.md\)",
                 f"[release notes](releases/v{version}.md)"),
            ],
        ),
        (
            ROOT / "docs" / "USAGE.md",
            [
                install_pin,
                (r"`v\d+\.\d+\.\d+` is the release pin",
                 f"`v{version}` is the release pin"),
            ],
        ),
        (
            ROOT / "docs" / "llms.txt",
            [
                install_pin,
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
                (r'Current release: <a href="releases/v\d+\.\d+\.\d+\.md">v\d+\.\d+\.\d+</a>',
                 f'Current release: <a href="releases/v{version}.md">v{version}</a>'),
                install_pin,
            ],
        ),
    ]

    citation_pins = [(r'(?m)^version: "[^"\n]+"$', f'version: "{version}"')]
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        released = re.search(
            rf"(?m)^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})$",
            changelog.read_text(encoding="utf-8"),
        )
        if released:
            citation_pins.append((r'(?m)^date-released: "[^"\n]+"$',
                                  f'date-released: "{released[1]}"'))
    rules.append((ROOT / "CITATION.cff", citation_pins))

    # Static guides share the release-install convention with the main docs.
    for guide in sorted((ROOT / "docs" / "guides").glob("*.html")):
        pins = [install_pin]
        if guide.name == "installation.html":
            pins.append((r'<a href="\.\./releases/v\d+\.\d+\.\d+\.md">release notes</a>',
                         f'<a href="../releases/v{version}.md">release notes</a>'))
        rules.append((guide, pins))

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
    files = [ROOT / "README.md", ROOT / "CITATION.cff"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    files += sorted((ROOT / "docs").rglob("*.html"))
    files += sorted((ROOT / "docs").rglob("*.txt"))
    return [
        f for f in files
        if f.is_file() and "releases" not in f.relative_to(ROOT).parts
    ]


# Match claims about the current Lixity release, not every version-shaped token.
# Broad matching would also catch 127.0.0.1 and third-party package versions.
# Historical wording such as "since v1.20.0" remains valid.
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

# These entrypoint links describe the current release. Other release-note links
# may be historical, so do not scan them throughout the documentation tree.
CURRENT_NOTE_CLAIMS: dict[Path, tuple[tuple[str, re.Pattern[str]], ...]] = {
    Path("CITATION.cff"): (
        ("citation version", re.compile(r'^version: "(\d+\.\d+\.\d+)"$')),
    ),
    Path("README.md"): (
        ("current release-note label",
         re.compile(r"\[v(\d+\.\d+\.\d+) release notes\]\(docs/releases/v\d+\.\d+\.\d+\.md\)")),
        ("current release-note target",
         re.compile(r"\[(?:v\d+\.\d+\.\d+ release notes|Release notes)\]\(docs/releases/v(\d+\.\d+\.\d+)\.md\)")),
    ),
    Path("docs/index.html"): (
        ("current release-note label",
         re.compile(r'Current release:\s*<a href="releases/v\d+\.\d+\.\d+\.md">v(\d+\.\d+\.\d+)</a>')),
        ("current release-note target",
         re.compile(r'Current release:\s*<a href="releases/v(\d+\.\d+\.\d+)\.md">')),
    ),
    Path("docs/INSTALLATION.md"): (
        ("current release-note target",
         re.compile(r"\[release notes\]\(releases/v(\d+\.\d+\.\d+)\.md\)")),
    ),
    Path("docs/guides/installation.html"): (
        ("current release-note target",
         re.compile(r'<a href="\.\./releases/v(\d+\.\d+\.\d+)\.md">release notes</a>')),
    ),
}


def find_version_drift(version: str) -> list[str]:
    """Report current-version claims that do not match the SSOT version."""
    findings: list[str] = []
    for file_path in current_doc_files():
        text = file_path.read_text(encoding="utf-8", errors="replace")
        rel = file_path.relative_to(ROOT)
        patterns = CURRENT_CLAIMS + CURRENT_NOTE_CLAIMS.get(rel, ())
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in patterns:
                findings.extend(
                    f"{rel}:{lineno}: {label} names v{match.group(1)}, "
                    f"but the current release is v{version}"
                    for match in pattern.finditer(line) if match.group(1) != version
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
