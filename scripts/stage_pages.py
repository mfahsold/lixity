#!/usr/bin/env python3
"""Stage public product documentation without publishing the entire docs tree."""

import argparse
import shutil
from pathlib import Path

ROOT_FILES = {
    ".nojekyll", "index.html", "robots.txt", "sitemap.xml", "llms.txt",
    "AGENT_PROFILE.md", "AGENTS.md", "ARCHITECTURE.md", "GROWTH_REVIEW.md", "INSTALLATION.md",
    "LICENSING.md", "LOCALIZATION.md", "METHODS.md", "ONBOARDING.md",
    "SECURITY_REVIEW.md", "STABILITY.md", "USAGE.md",
}
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
        approved = str(relative) in ROOT_FILES or (
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
