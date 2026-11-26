#!/usr/bin/env python3
"""Synchronize release pins and check current-version claims in documentation.

The version comes from src/lixity/_version.py. Run with --check to report drift
without changing files. Rewriting handles known pins; the separate claim scan
also checks wording outside that list. Historical release notes and third-party
versions are not treated as current Lixity claims. Use --all to include the
generated documentation and localized metric references.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    from check_release import PENDING_RELEASE, RELEASE_HEADING, source_version
except ModuleNotFoundError:
    from scripts.check_release import PENDING_RELEASE, RELEASE_HEADING, source_version

ROOT = Path(__file__).resolve().parents[1]


def get_version() -> str:
    return source_version(ROOT)


_README_RELEASE_DIR = (
    r"(?:docs/releases/|https://lixity\.de/releases/|"
    r"https://mfahsold\.github\.io/lixity/releases/|"
    r"https://github\.com/mfahsold/lixity/blob/main/docs/releases/)"
)


def check_or_sync_files(
    version: str, *, check_only: bool = False, root: Path | None = None
) -> list[str]:
    """Check or update version references across documentation files."""
    base = ROOT if root is None else root
    drift_files: list[str] = []

    install_pin = (
        r"git\+https://github\.com/mfahsold/lixity\.git@v\d+\.\d+\.\d+",
        f"git+https://github.com/mfahsold/lixity.git@v{version}",
    )
    wheel_pin = (
        r"https://github\.com/mfahsold/lixity/releases/download/v\d+\.\d+\.\d+/lixity-\d+\.\d+\.\d+-py3-none-any\.whl",
        f"https://github.com/mfahsold/lixity/releases/download/v{version}/lixity-{version}-py3-none-any.whl",
    )
    source_pin = (
        r"The documentation source version is \*\*v\d+\.\d+\.\d+\*\*",
        f"The documentation source version is **v{version}**",
    )
    version_line_pin = (
        r"this documentation describes source \*\*v\d+\.\d+\.\d+\*\*",
        f"this documentation describes source **v{version}**",
    )
    # Rules: (file_path, list of (pattern, replacement))
    rules: list[tuple[Path, list[tuple[str, str]]]] = [
        (
            base / "README.md",
            [
                install_pin,
                source_pin,
                (r"fixed snapshot of \d+\.\d+\.\d+",
                 f"fixed snapshot of {version}"),
                (r"This installs \*\*v\d+\.\d+\.\d+\*\*",
                 f"This installs **v{version}**"),
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
                (rf"\[v\d+\.\d+\.\d+ release notes\]\(({_README_RELEASE_DIR})v\d+\.\d+\.\d+\.md\)",
                 rf"[v{version} release notes](\g<1>v{version}.md)"),
                (rf"(\[(?:[Rr]elease notes|development notes)\]\({_README_RELEASE_DIR})v\d+\.\d+\.\d+\.md\)",
                 rf"\g<1>v{version}.md)"),
            ],
        ),
        (
            base / "docs" / "INSTALLATION.md",
            [
                install_pin,
                (r"lixity==\d+\.\d+\.\d+", f"lixity=={version}"),
                (r"(the )\d+\.\d+\.\d+(\s+package still declares Python 3\.10\+)",
                 rf"\g<1>{version}\g<2>"),
                (r"this source documentation describes the prepared \*\*v\d+\.\d+\.\d+\*\*",
                 f"this source documentation describes the prepared **v{version}**"),
                (r"this documentation describes \*\*v\d+\.\d+\.\d+\*\*",
                 f"this documentation describes **v{version}**"),
                (r"The current release is \*\*v\d+\.\d+\.\d+\*\*",
                 f"The current release is **v{version}**"),
                (r"(\[(?:release notes|development notes)\]\(releases/)v\d+\.\d+\.\d+\.md\)",
                 rf"\g<1>v{version}.md)"),
            ],
        ),
        (
            base / "docs" / "USAGE.md",
            [
                install_pin,
                (r"`v\d+\.\d+\.\d+` is the release pin",
                 f"`v{version}` is the release pin"),
            ],
        ),
        (
            base / "docs" / "PRODUCT.md",
            [version_line_pin],
        ),
        (
            base / "docs" / "METHODS.md",
            [version_line_pin],
        ),
        (
            base / "docs" / "STABILITY.md",
            [version_line_pin],
        ),
        (
            base / "docs" / "AGENTS.md",
            [version_line_pin],
        ),
        (
            base / "docs" / "ARCHITECTURE.md",
            [version_line_pin],
        ),
        (
            base / "docs" / "llms.txt",
            [
                install_pin,
                (r"replace `@v\d+\.\d+\.\d+` with `@main`",
                 f"replace `@v{version}` with `@main`"),
                (r"Current release: \d+\.\d+\.\d+; release tag: v\d+\.\d+\.\d+",
                 f"Current release: {version}; release tag: v{version}"),
                (r"Documentation source version: \d+\.\d+\.\d+",
                 f"Documentation source version: {version}"),
                (r"release history \(current: \d+\.\d+\.\d+\)",
                 f"release history (current: {version})"),
                (r"\[Release notes\]\(https://(?:mfahsold\.github\.io/lixity|lixity\.de)/releases/v\d+\.\d+\.\d+\.md\)",
                 f"[Release notes](https://lixity.de/releases/v{version}.md)"),
            ],
        ),
        (
            base / "docs" / "index.html",
            [
                (r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/)?releases/v\d+\.\d+\.\d+\.md" id="current-release"([^>]*)>v\d+\.\d+\.\d+ release notes</a>',
                 rf'<a href="https://github.com/mfahsold/lixity/blob/main/docs/releases/v{version}.md" id="current-release"\g<1>>v{version} release notes</a>'),
            ],
        ),
    ]

    citation = base / "CITATION.cff"
    citation_version = r'(?m)^version: "[^"\n]+"$'
    citation_date = r"(?m)^date-released:[^\n]*(?:\n|$)"
    citation_pins = [(citation_version, f'version: "{version}"')]
    changelog = base / "CHANGELOG.md"
    if changelog.is_file() and citation.is_file():
        status = next((heading[2] for heading in RELEASE_HEADING.finditer(
            changelog.read_text(encoding="utf-8")) if heading[1] == version), None)
        if status == PENDING_RELEASE:
            citation_pins.append((citation_date, ""))
        elif status is not None:
            entry = f'date-released: "{status}"'
            if re.search(citation_date, citation.read_text(encoding="utf-8")):
                citation_pins.append((r"(?m)^date-released:[^\n]*$", entry))
            else:
                citation_pins.append((citation_version, rf"\g<0>\n{entry}"))
    rules.append((citation, citation_pins))

    # Static guides share the release-install convention with the main docs.
    for guide in sorted((base / "docs" / "guides").glob("*.html")):
        pins = [install_pin]
        if guide.name == "installation.html":
            pins.append((r'This source guide describes <strong>v\d+\.\d+\.\d+(?: development)?</strong>',
                         f'This source guide describes <strong>v{version}</strong>'))
            pins.append((r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/|\.\./)releases/v\d+\.\d+\.\d+\.md">\d+\.\d+\.\d+ development notes</a>',
                         f'<a href="https://github.com/mfahsold/lixity/blob/main/docs/releases/v{version}.md">{version} development notes</a>'))
            pins.append((r'The current release is <strong>v\d+\.\d+\.\d+</strong>',
                         f'The current release is <strong>v{version}</strong>'))
            pins.append((r'This installs the current release, <strong>v\d+\.\d+\.\d+</strong>',
                         f'This installs the current release, <strong>v{version}</strong>'))
            pins.append((r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/|\.\./)releases/v\d+\.\d+\.\d+\.md">release notes</a>',
                         f'<a href="https://github.com/mfahsold/lixity/blob/main/docs/releases/v{version}.md">release notes</a>'))
            pins.append((r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/|\.\./)releases/v\d+\.\d+\.\d+\.md">\d+\.\d+\.\d+ release notes</a>',
                         f'<a href="https://github.com/mfahsold/lixity/blob/main/docs/releases/v{version}.md">{version} release notes</a>'))
        rules.append((guide, pins))

    for file_path, replacements in rules:
        if not file_path.is_file():
            continue
        original = file_path.read_text(encoding="utf-8")
        updated = original
        for pattern, repl in [*replacements, wheel_pin]:
            updated = re.sub(pattern, repl, updated)

        if updated != original:
            rel_name = str(file_path.relative_to(base))
            drift_files.append(rel_name)
            if not check_only:
                file_path.write_text(updated, encoding="utf-8")

    return drift_files


# Files that describe the present release. docs/releases/ is excluded: past
# release notes exist precisely to name old versions.
def current_doc_files(root: Path | None = None) -> list[Path]:
    base = ROOT if root is None else root
    files = [base / "README.md", base / "CITATION.cff"]
    files += sorted((base / "docs").rglob("*.md"))
    files += sorted((base / "docs").rglob("*.html"))
    files += sorted((base / "docs").rglob("*.txt"))
    return [
        f for f in files
        if f.is_file() and "releases" not in f.relative_to(base).parts
    ]


# Match claims about the current Lixity release, not every version-shaped token.
# Broad matching would also catch 127.0.0.1 and third-party package versions.
# Historical wording such as "since v1.20.0" remains valid.
CURRENT_CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Markdown documentation source version",
     re.compile(r"(?:The documentation source version is|this source documentation describes the prepared|this documentation describes source) \*\*v(\d+\.\d+\.\d+)\*\*")),
    ("HTML documentation source version",
     re.compile(r'This source guide describes <strong>v(\d+\.\d+\.\d+)(?: development)?</strong>')),
    ("documentation source version",
     re.compile(r"Documentation source version:\s*(\d+\.\d+\.\d+)", re.I)),
    ("current release statement",
     re.compile(r"current release(?:\s+is)?[\s:*>]*\**v?(\d+\.\d+\.\d+)", re.I)),
    ("current HTML install statement",
     re.compile(r"This installs the current release, <strong>v(\d+\.\d+\.\d+)</strong>")),
    ("current HTML version notice",
     re.compile(r"The current release is <strong>v(\d+\.\d+\.\d+)</strong>")),
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
    ("manuals describe release",
     re.compile(r"(?:These manuals|This reference|The workflows below) describe(?:s| the)? \*{0,2}v?(\d+\.\d+\.\d+)\*{0,2}", re.I)),
    ("availability update release",
     re.compile(r"availability updated for (\d+\.\d+\.\d+)\b", re.I)),
    ("pip install pin",
     re.compile(r"lixity\.git@v(\d+\.\d+\.\d+)")),
    ("wheel release tag pin",
     re.compile(r"lixity/releases/download/v(\d+\.\d+\.\d+)/lixity-")),
    ("wheel artifact version pin",
     re.compile(r"lixity/releases/download/v\d+\.\d+\.\d+/lixity-(\d+\.\d+\.\d+)-py3-none-any\.whl")),
    ("demo snapshot version",
     re.compile(r"fixed snapshot of (\d+\.\d+\.\d+)")),
    ("package minimum-python claim",
     re.compile(r"the (\d+\.\d+\.\d+)\s+package still declares Python 3\.10\+")),
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
         re.compile(rf"\[v(\d+\.\d+\.\d+) release notes\]\({_README_RELEASE_DIR}v\d+\.\d+\.\d+\.md\)")),
        ("current release-note target",
         re.compile(rf"\[(?:v\d+\.\d+\.\d+ release notes|[Rr]elease notes|development notes)\]\({_README_RELEASE_DIR}v(\d+\.\d+\.\d+)\.md\)")),
    ),
    Path("docs/index.html"): (
        ("current release-note target",
         re.compile(r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/)?releases/v(\d+\.\d+\.\d+)\.md" id="current-release"')),
        ("current release-note label",
         re.compile(r'id="current-release"[^>]*>v(\d+\.\d+\.\d+) release notes</a>')),
    ),
    Path("docs/INSTALLATION.md"): (
        ("worker package install pin", re.compile(r"lixity==(\d+\.\d+\.\d+)")),
        ("current release-note target",
         re.compile(r"\[(?:release notes|development notes)\]\(releases/v(\d+\.\d+\.\d+)\.md\)")),
    ),
    Path("docs/llms.txt"): (
        ("current release-note target",
         re.compile(r"\[Release notes\]\(https://(?:mfahsold\.github\.io/lixity|lixity\.de)/releases/v(\d+\.\d+\.\d+)\.md\)")),
    ),
    Path("docs/guides/installation.html"): (
        ("current release-note target",
         re.compile(r'<a href="(?:https://github\.com/mfahsold/lixity/blob/main/docs/|\.\./)releases/v(\d+\.\d+\.\d+)\.md">(?:release notes|\d+\.\d+\.\d+ (?:development|release) notes)</a>')),
    ),
}


def find_version_drift(version: str, *, root: Path | None = None) -> list[str]:
    """Report current-version claims that do not match the SSOT version."""
    base = ROOT if root is None else root
    findings: list[str] = []
    for file_path in current_doc_files(base):
        text = file_path.read_text(encoding="utf-8", errors="replace")
        rel = file_path.relative_to(base)
        patterns = CURRENT_CLAIMS + CURRENT_NOTE_CLAIMS.get(rel, ())
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in patterns:
                findings.extend(
                    f"{rel}:{lineno}: {label} names v{match.group(1)}, "
                    f"but the current release is v{version}"
                    for match in pattern.finditer(line) if match.group(1) != version
                )
    return findings


def check_or_sync_generated(version: str, *, check_only: bool, root: Path) -> list[str]:
    """Run the same document generators for local work, releases and Pages."""
    from build_blog_feed import build as build_feed
    from build_guide_markdown import build as build_guides
    from build_llms_full import build as build_llms
    from build_metric_reference import build as build_metrics
    from build_public_site import build as build_site

    changed = check_or_sync_files(version, check_only=check_only, root=root)
    for build in (build_feed, build_site, build_llms, build_guides, build_metrics):
        changed.extend(build(check_only=check_only, root=root))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check for drift without writing changes")
    parser.add_argument("--all", action="store_true", help="Include generated files (requires Lixity dependencies)")
    args = parser.parse_args()

    version = get_version()
    sync = check_or_sync_generated if args.all else check_or_sync_files
    drift = sync(version, check_only=args.check, root=ROOT)

    if args.check:
        # The invariant is independent of the rewrite list: a file can need no
        # rewriting and still be making a stale current-version claim.
        stale = find_version_drift(version)
        if drift or stale:
            print(f"Documentation drift detected for version {version}:", file=sys.stderr)
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
            command = "make docs-sync" if args.all else "python scripts/sync_docs.py"
            print(f"Run '{command}' to synchronize documentation.", file=sys.stderr)
            return 1
        print(f"Documentation is synchronized with v{version}.")
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
