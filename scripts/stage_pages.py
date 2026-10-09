#!/usr/bin/env python3
"""Stage public product documentation without publishing the entire docs tree.

The output mirrors the published GitHub Pages layout: ``docs/<name>`` is
flattened to ``/<name>``. A relative link inside the published documentation
therefore resolves only if its target is also published, which is why nothing
outside ``docs/`` is staged -- those files are referenced by absolute repository
URL instead. ``tests/test_documentation.py`` enforces the result against the
staged tree rather than the checkout, because a link can be correct in the
checkout and still break on the site.
"""

import argparse
import shutil
from pathlib import Path

#: Approved files inside ``docs/``, keyed by their path relative to it.
#:
#: Nothing outside ``docs/`` is published. Repository-root documents (README,
#: CONTRIBUTING, SECURITY, LICENSE, CHANGELOG) are written for browsing inside
#: the checkout, where ``docs/`` is a real subdirectory; flattening them onto the
#: site root would break every ``docs/...`` link they contain. The documentation
#: therefore references them by absolute repository URL instead, which resolves
#: correctly in both contexts.
DOCS_ROOT_FILES = {
    ".nojekyll",
    "index.html",
    "robots.txt",
    "sitemap.xml",
    "llms.txt",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "INSTALLATION.md",
    "LICENSING.md",
    "LOCALIZATION.md",
    "METHODS.md",
    "ONBOARDING.md",
    "STABILITY.md",
    "USAGE.md",
    # One reviewed, generated example; sibling inputs/build files stay private to the repo.
    "demo/report.html",
}

#: Approved subtrees, keyed by their first path segment.
PUBLIC_TREES = {
    "assets": {".css", ".js", ".svg", ".png", ".woff2"},
    "guides": {".html"},
    "screenshots": {".png", ".webp", ".md"},
    "releases": {".md"},
    "research": {".md", ".json", ".txt"},
}


def stage(source: Path, output: Path) -> int:
    """Copy approved public paths to a new directory; never overwrite output."""
    if not source.is_dir():
        raise ValueError("Documentation source directory is missing")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Pages output must be outside the documentation source")
    selected: list[Path] = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_symlink():
            raise ValueError(f"Symlink in documentation source: {relative}")
        if not path.is_file():
            continue
        approved = str(relative) in DOCS_ROOT_FILES or (
            len(relative.parts) > 1
            and not any(part.startswith(".") for part in relative.parts)
            and path.suffix in PUBLIC_TREES.get(relative.parts[0], set())
        )
        if approved:
            selected.append(path)
    output.mkdir(parents=True, exist_ok=False)
    for path in selected:
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    count = stage(Path(__file__).resolve().parents[1] / "docs", args.output)
    print(f"Staged {count} public documentation files in {args.output}")


if __name__ == "__main__":
    main()
