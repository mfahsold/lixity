#!/usr/bin/env python3
"""Stage public product documentation without publishing the entire docs tree.

The output mirrors the published GitHub Pages layout: ``docs/<name>`` is
flattened to ``/<name>``. A relative link inside the published documentation
therefore resolves only if its target is also published, which is why nothing
outside ``docs/`` is staged except the canonical packaged design-token stylesheet;
repository documents are referenced by absolute URL instead.
``tests/test_documentation.py`` enforces the result against the
staged tree rather than the checkout, because a link can be correct in the
checkout and still break on the site.
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

#: Approved files inside ``docs/``, keyed by their path relative to it.
#:
#: Only the explicitly selected design-token asset comes from outside ``docs/``.
#: Repository-root documents (README,
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
    "llms-full.txt",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "INSTALLATION.md",
    "LICENSING.md",
    "LOCALIZATION.md",
    "METHODS.md",
    "ONBOARDING.md",
    "STABILITY.md",
    "USAGE.md",
    # One project demo and its reviewed outputs; sibling build files stay unpublished.
    "demo/report.html",
    # The former research page is a compatibility entry, not a second project.
    "demo/research.html",
    "demo/warehouse-4-editor.pdf",
    "demo/warehouse-4-book.pdf",
    "demo/warehouse-4-sheet.pdf",
    "demo/warehouse-4-report.pdf",
    "demo/warehouse-4-document.pdf",
    "assets/research/sources.json",
    "assets/analytics.json",
    "assets/research/hamburg-free-port-1900.jpg",
    "assets/research/hamburg-harbour-1890-1900.jpg",
}

#: Approved subtrees, keyed by their first path segment.
PUBLIC_TREES = {
    "assets": {".css", ".js", ".svg", ".png", ".woff2"},
    "blog": {".html"},
    "guides": {".html", ".md"},
    "screenshots": {".png", ".webp", ".md"},
    "releases": {".md"},
    "videos": {".mp4", ".webm", ".gif", ".png", ".md"},
    "examples": {".html", ".pdf", ".md"},
    "research": {".md", ".json", ".txt"},
}


def _demo_bundle_files(source: Path, *, directory: str = "demo", entrypoint: str = "report.html",
                       mode: str | None = None) -> set[str]:
    """Select the reviewed website inventory, never a whole demo subtree."""
    manifest = source / directory / "manifest.json"
    if (source / directory).is_symlink() or manifest.is_symlink():
        raise ValueError("Symlink in public demo bundle")
    if not manifest.exists():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != "lixity-read-only-site/1"
            or data.get("entrypoint") != entrypoint or not isinstance(data.get("files"), dict)
            or entrypoint not in data["files"]):
        raise ValueError("The public demo requires a reviewed website manifest")
    if mode is not None and (data.get("mode") != mode
            or not isinstance(data.get("capabilities"), dict)
            or data["capabilities"].get("analysis") is not False
            or data["capabilities"].get("research") is not False
            or data["capabilities"].get("automatic_external_requests") is not False):
        raise ValueError("Reader examples require their explicit publication mode without archive analysis or analytics")
    selected = {directory + "/manifest.json"}
    for name, metadata in data["files"].items():
        approved = isinstance(name, str) and (
            (directory == "demo" and "demo/" + name in DOCS_ROOT_FILES)
            or (mode is not None and name == "index.html")
            or re.fullmatch(r"assets/sources/[0-9a-f]{64}\.(?:jpg|png|txt|pdf)", name)
            or re.fullmatch(r"licenses/(?:Lixity-LICENSE|[A-Za-z0-9._-]+\.LICENSE)", name)
        )
        if not approved:
            raise ValueError("Unapproved public demo bundle member")
        path = source / directory / name
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != source.parent):
            raise ValueError("Symlink in public demo bundle")
        if (not isinstance(metadata, dict) or type(metadata.get("byte_length")) is not int
                or not isinstance(metadata.get("sha256"), str) or not path.is_file()):
            raise ValueError("Missing or invalid public demo bundle member")
        content = path.read_bytes()
        if len(content) != metadata["byte_length"] or hashlib.sha256(content).hexdigest() != metadata["sha256"]:
            raise ValueError("Public demo bundle member changed; regenerate its checksum inventory")
        selected.add(directory + "/" + name)
    return selected


def stage(source: Path, output: Path) -> int:
    """Copy approved public paths to a new directory; never overwrite output."""
    if not source.is_dir():
        raise ValueError("Documentation source directory is missing")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Pages output must be outside the documentation source")
    demo_files = _demo_bundle_files(source)
    # Only these two deliberately reviewed publication directories are added;
    # a sibling folder or even its own manifest never grants publication.
    for mode in ("reader", "companion"):
        demo_files.update(_demo_bundle_files(source, directory="demo/" + mode,
                                            entrypoint="index.html", mode=mode))
    selected: list[Path] = []
    assets = Path(__file__).resolve().parents[1] / "src/lixity/ui/assets"
    tokens = assets / "design-tokens.css"
    components = assets / "components.css"
    for canonical in (tokens, components):
        if canonical.is_symlink() or not canonical.is_file():
            raise ValueError("Canonical design assets must be regular packaged files")
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if relative.as_posix() in ("assets/design-tokens.css", "assets/components.css"):
            raise ValueError("Pages must use the packaged canonical design assets")
        if path.is_symlink():
            raise ValueError(f"Symlink in documentation source: {relative}")
        if not path.is_file():
            continue
        approved = relative.as_posix() in DOCS_ROOT_FILES or (
            len(relative.parts) > 1
            and not any(part.startswith(".") for part in relative.parts)
            and (path.suffix in PUBLIC_TREES.get(relative.parts[0], set())
                 or (relative.parts[0] == "blog" and path.name.endswith(".html.md")))
        )
        if demo_files and relative.parts[0] == "demo":
            approved = relative.as_posix() in demo_files
        if approved:
            selected.append(path)
    output.mkdir(parents=True, exist_ok=False)
    for path in selected:
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for canonical in (tokens, components):
        target = output / "assets" / canonical.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(canonical, target)
    extra = 2
    # Byte-identical fallback for a Search Console entry whose canonical path
    # stays stuck on a fetch failure; generated here so it cannot drift.
    sitemap = output / "sitemap.xml"
    if sitemap.is_file():
        shutil.copyfile(sitemap, output / "sitemap-alt.xml")
        extra += 1
    return len(selected) + extra


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    count = stage(Path(__file__).resolve().parents[1] / "docs", args.output)
    print(f"Staged {count} public documentation files in {args.output}")


if __name__ == "__main__":
    main()
