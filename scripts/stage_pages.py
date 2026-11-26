#!/usr/bin/env python3
"""Stage public product documentation without publishing the entire docs tree.

The output mirrors the published GitHub Pages layout: ``docs/<name>`` is
flattened to ``/<name>``. A relative link inside the published documentation
therefore resolves only if its target is also published, which is why nothing
outside ``docs/`` is staged except the canonical packaged design-token and
component stylesheets. Use absolute repository URLs for repository documents.
``tests/test_documentation.py`` enforces the result against the
staged tree rather than the checkout, because a link can be correct in the
checkout and still break on the site.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

try:
    import desktop_downloads
    from build_public_site import LANGUAGES, page_path
    from make_videos import PUBLIC_VIDEO_FILES
except ModuleNotFoundError:
    from scripts import desktop_downloads
    from scripts.build_public_site import LANGUAGES, page_path
    from scripts.make_videos import PUBLIC_VIDEO_FILES

LEGACY_PAGES_BASE_URL = "https://mfahsold.github.io/lixity/"
CUSTOM_PAGES_BASE_URL = "https://lixity.de/"
CANONICAL_PAGES_BASE_URL = CUSTOM_PAGES_BASE_URL
PAGES_BASE_URLS = frozenset({LEGACY_PAGES_BASE_URL, CUSTOM_PAGES_BASE_URL})
_LEGACY_SITE_LINK = re.compile(
    re.escape(LEGACY_PAGES_BASE_URL.rstrip("/")) + r"""(?:/|(?=$|[\s"'<>?#)\]`]))"""
)
_APEX_SITE_LINK = re.compile(
    re.escape(CUSTOM_PAGES_BASE_URL.rstrip("/")) + r"""(?:/|(?=$|[\s"'<>?#)\]`]))"""
)
_ANY_SITE_LINK = re.compile(
    r"(?:"
    + re.escape(LEGACY_PAGES_BASE_URL.rstrip("/"))
    + r"|"
    + re.escape(CUSTOM_PAGES_BASE_URL.rstrip("/"))
    + r""")(?:/|(?=$|[\s"'<>?#)\]`]))"""
)
_SITE_TEXT_SUFFIXES = frozenset({".html", ".md", ".txt", ".xml"})

#: Approved files inside ``docs/``, keyed by their path relative to it.
#:
#: The packaged design-token and component stylesheets come from outside ``docs/``.
#: Repository-root documents (README,
#: CONTRIBUTING, SECURITY, LICENSE, CHANGELOG) are written for browsing inside
#: the checkout, where ``docs/`` is a real subdirectory; flattening them onto the
#: site root would break every ``docs/...`` link they contain. The documentation
#: therefore references them by absolute repository URL instead, which resolves
#: correctly in both contexts.
DOCS_ROOT_FILES = {
    ".nojekyll",
    *(page_path(language) for language in LANGUAGES),
    "robots.txt",
    "sitemap.xml",
    "BingSiteAuth.xml",  # Public Bing ownership proof; preserve the downloaded bytes.
    "indexnow-key.txt",  # Public ownership proof, scoped by the deployed keyLocation.
    "favicon.ico",
    "manifest.webmanifest",
    "llms.txt",
    "llms-full.txt",
    desktop_downloads.CATALOG.name,
    "README.md",
    "WORKSPACE.md",
    "PRODUCT.md",
    "PROJECT_BACKUP.md",
    "AUDIO.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "MANUSCRIPT_EDITING_RFC.md",
    "RUST_EVALUATION_RFC.md",
    "INSTALLATION.md",
    "LICENSING.md",
    "FUNDING.md",
    "LOCALIZATION.md",
    "METHODS.md",
    "ONBOARDING.md",
    "STABILITY.md",
    "USAGE.md",
    # One project demo and its reviewed outputs; sibling build files stay unpublished.
    "demo/report.html",
    "sandbox/index.html",
    # The former research page is a compatibility entry, not a second project.
    "demo/research.html",
    "demo/warehouse-4-editor.pdf",
    "demo/warehouse-4-book.pdf",
    "demo/warehouse-4-sheet.pdf",
    "demo/warehouse-4-report.pdf",
    "demo/warehouse-4-document.pdf",
    "demo/warehouse-4-dossier.pdf",
    "assets/research/sources.json",
    "assets/analytics.json",
    "assets/research/hamburg-free-port-1900.jpg",
    "assets/research/hamburg-harbour-1890-1900.jpg",
    *("videos/" + name for name in PUBLIC_VIDEO_FILES),
}

#: Approved subtrees, keyed by their first path segment.
PUBLIC_TREES = {
    "assets": {".css", ".js", ".svg", ".png", ".webp", ".woff2"},
    "blog": {".html", ".xml"},
    "guides": {".html", ".md"},
    "screenshots": {".png", ".webp", ".md"},
    "releases": {".md"},
    "examples": {".html", ".pdf", ".md"},
    "research": {".md", ".json", ".txt"},
}
LOCAL_ONLY_DIRECTORIES = frozenset({"private", "confidential", "secrets"})
DEMO_READER_AUDIO_CHAPTERS = (1, 2)


def screenshot_manifest(source: Path) -> list[dict[str, str]]:
    """Read the single reviewed image inventory used by capture and publication."""
    if (source / "screenshots").is_symlink():
        raise ValueError("Symlink in screenshot directory")
    path = source / "screenshots/manifest.json"
    if not path.exists():
        if (source / "screenshots").exists():
            raise ValueError("Screenshots require a reviewed manifest")
        return []
    if path.is_symlink():
        raise ValueError("Symlink in screenshot manifest")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or set(data) != {"schema_version", "images"}
            or data["schema_version"] != "lixity-screenshot-catalog/1"
            or not isinstance(data["images"], list) or not data["images"]):
        raise ValueError("Invalid screenshot manifest")
    names = set()
    for item in data["images"]:
        if (not isinstance(item, dict)
                or set(item) != {"file", "role", "question", "alt", "caption", "destination"}
                or any(not isinstance(value, str) or not value.strip() for value in item.values())
                or not re.fullmatch(r"[a-z0-9-]+\.(?:png|webp)", item["file"])
                or item["file"] in names
                or item["role"] not in {"lead", "support", "guide", "reference"}
                or item["destination"].startswith(("/", "."))
                or ":" in item["destination"] or ".." in item["destination"].split("/")):
            raise ValueError("Invalid screenshot entry")
        image = path.parent / item["file"]
        if image.is_symlink() or not image.is_file():
            raise ValueError("Missing reviewed screenshot")
        names.add(item["file"])
    return data["images"]


def _demo_bundle_files(source: Path, *, directory: str = "demo", entrypoint: str = "report.html",
                       mode: str | None = None) -> set[str]:
    """Select the reviewed website inventory, never a whole demo subtree."""
    manifest = source / directory / "manifest.json"
    if (source / directory).is_symlink() or manifest.is_symlink():
        raise ValueError("Symlink in public demo bundle")
    if not manifest.exists():
        return set()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    version = data.get("schema_version") if isinstance(data, dict) else None
    approved_analysis = (mode == "reader" and version in {"lixity-read-only-site/2", "lixity-read-only-site/3"}
                         and isinstance(data.get("publication"), dict)
                         and data["publication"].get("analysis_sections") == ["chapters"])
    if (not isinstance(data, dict) or not (version == "lixity-read-only-site/1" or approved_analysis)
            or data.get("entrypoint") != entrypoint or not isinstance(data.get("files"), dict)
            or entrypoint not in data["files"]):
        raise ValueError("The public demo requires a reviewed website manifest")
    if approved_analysis and "analysis.html" not in data["files"]:
        raise ValueError("The reviewed reader analysis page is missing")
    audio_assets = set()
    if version == "lixity-read-only-site/3":
        audio = data.get("audio")
        if (not approved_analysis or not isinstance(audio, dict)
                or audio.get("schema_version") != "lixity-reader-audio/1"
                or audio.get("source_sha256") != data.get("manuscript", {}).get("source_sha256")
                or not isinstance(audio.get("tracks"), list)
                or len(audio["tracks"]) != len(DEMO_READER_AUDIO_CHAPTERS)):
            raise ValueError("The reader demo requires its reviewed chapter audio scope")
        for chapter, track in zip(DEMO_READER_AUDIO_CHAPTERS, audio["tracks"], strict=True):
            if (not isinstance(track, dict) or type(track.get("chapter")) is not int
                    or track["chapter"] != chapter or track.get("origin") != "imported"
                    or not isinstance(track.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", track["sha256"])
                    or track.get("file") != f"assets/audio/{track['sha256']}.wav"
                    or data["files"].get(track["file"]) != {"sha256": track["sha256"], "byte_length": track.get("byte_length")}):
                raise ValueError("The reader demo audio does not match its reviewed file inventory")
            audio_assets.add(track["file"])
    if mode is not None and (data.get("mode") != mode
            or not isinstance(data.get("capabilities"), dict)
            or data["capabilities"].get("analysis") is not approved_analysis
            or data["capabilities"].get("research") is not False
            or data["capabilities"].get("automatic_external_requests") is not False):
        raise ValueError("Reader examples require their reviewed publication mode and analysis scope")
    selected = {directory + "/manifest.json"}
    for name, metadata in data["files"].items():
        approved = isinstance(name, str) and (
            (directory == "demo" and "demo/" + name in DOCS_ROOT_FILES)
            or (mode is not None and name == "index.html")
            or (approved_analysis and name == "analysis.html")
            or name in audio_assets
            or re.fullmatch(r"assets/sources/[0-9a-f]{64}\.(?:jpg|png|txt|pdf|mp4)", name)
            or re.fullmatch(r"licenses/(?:Lixity-LICENSE|[A-Za-z0-9._-]+\.LICENSE)", name)
        )
        if not approved:
            raise ValueError("Unapproved public demo bundle member")
        path = source / directory / name
        if any(parent.is_symlink() for parent in (path, *path.parents)
               if parent != source and parent.is_relative_to(source)):
            raise ValueError("Symlink in public demo bundle")
        if (not isinstance(metadata, dict) or type(metadata.get("byte_length")) is not int
                or not isinstance(metadata.get("sha256"), str) or not path.is_file()):
            raise ValueError("Missing or invalid public demo bundle member")
        content = path.read_bytes()
        if len(content) != metadata["byte_length"] or hashlib.sha256(content).hexdigest() != metadata["sha256"]:
            raise ValueError("Public demo bundle member changed; regenerate its checksum inventory")
        selected.add(directory + "/" + name)
    return selected


def normalize_pages_base_url(base_url: str) -> str:
    """Accept either deployed HTTPS base, with or without a terminal slash."""
    normalized = base_url if base_url.endswith("/") else base_url + "/"
    if normalized not in PAGES_BASE_URLS:
        raise ValueError("Pages base URL must be a supported public site")
    return normalized


def _site_text(content: str, relative_path: Path, base_url: str) -> str:
    """Use the deployment base for public links and preserve Atom identifiers."""
    if relative_path.as_posix() == "blog/feed.xml":
        return "".join(
            line if line.lstrip().startswith("<id>") else _ANY_SITE_LINK.sub(base_url, line)
            for line in content.splitlines(keepends=True)
        )
    if relative_path.as_posix() == "robots.txt":
        content = "".join(line for line in content.splitlines(keepends=True)
                          if not line.startswith(("# Deployment note:", "# Only /robots.txt")))
    # Canonical source is apex; rewrite either known host to the deployment base
    # so legacy staging still verifies old deep links and apex staging is a copy.
    rewritten = _ANY_SITE_LINK.sub(base_url, content)
    return rewritten


def _demo_html_for_base(content: bytes, base_url: str) -> bytes:
    # Keep reviewed publication bodies, assets and citations byte-identical.
    head, closing_tag, body = content.partition(b"</head>")
    if not closing_tag:
        return content
    metadata = _ANY_SITE_LINK.sub(base_url, head.decode("utf-8"))
    return metadata.encode("utf-8") + closing_tag + body


def _update_demo_manifests(
    output: Path, demo_files: set[str], changes: dict[Path, dict[str, int | str]],
) -> None:
    """Record the exact staged bytes after changing reviewed HTML heads."""
    for relative in sorted(demo_files):
        manifest = output / relative
        if manifest.name != "manifest.json":
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        changed_members = {
            name: changes[manifest.parent / name]
            for name in data["files"] if manifest.parent / name in changes
        }
        if changed_members:
            data["files"].update(changed_members)
            manifest.write_bytes((json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def stage(source: Path, output: Path, *, base_url: str = CUSTOM_PAGES_BASE_URL) -> int:
    """Stage approved public paths and metadata for the selected deployment base."""
    base_url = normalize_pages_base_url(base_url)
    if not source.is_dir():
        raise ValueError("Documentation source directory is missing")
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("Pages output must be outside the documentation source")
    screenshots = screenshot_manifest(source)
    screenshot_paths = {"screenshots/" + item["file"] for item in screenshots}
    if screenshots:
        screenshot_paths.update({"screenshots/README.md", "screenshots/manifest.json"})
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
        # Local previews can see ignored files inside the public subtrees.
        parts = tuple(part.casefold() for part in relative.parts)
        name = parts[-1]
        if (LOCAL_ONLY_DIRECTORIES.intersection(parts)
                or any(part.startswith("credentials") for part in parts)
                or name == "client_secret.json"
                or (name.startswith("client_secret_") and name.endswith(".json"))):
            continue
        if relative.as_posix() in ("assets/design-tokens.css", "assets/components.css"):
            raise ValueError("Pages must use the packaged canonical design assets")
        if path.is_symlink():
            raise ValueError(f"Symlink in documentation source: {relative}")
        if not path.is_file():
            continue
        if relative.as_posix() == desktop_downloads.CATALOG.name:
            desktop_downloads.validate_catalog(json.loads(path.read_text(encoding="utf-8")))
        approved = relative.as_posix() in DOCS_ROOT_FILES or (
            len(relative.parts) > 1
            and not any(part.startswith(".") for part in relative.parts)
            and (path.suffix in PUBLIC_TREES.get(relative.parts[0], set())
                 or (relative.parts[0] == "blog" and path.name.endswith(".html.md")))
        )
        if relative.parts[0] == "screenshots":
            approved = relative.as_posix() in screenshot_paths
        if demo_files and relative.parts[0] == "demo":
            approved = relative.as_posix() in demo_files
        if approved:
            selected.append(path)
    output.mkdir(parents=True, exist_ok=False)
    demo_changes: dict[Path, dict[str, int | str]] = {}
    for path in selected:
        relative = path.relative_to(source)
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if (relative.as_posix() == "BingSiteAuth.xml"
                or path.suffix not in _SITE_TEXT_SUFFIXES):
            shutil.copyfile(path, target)
        elif relative.as_posix() not in demo_files:
            content = path.read_bytes().decode("utf-8")
            target.write_bytes(_site_text(content, relative, base_url).encode("utf-8"))
        elif path.suffix == ".html":
            original = path.read_bytes()
            revised = _demo_html_for_base(original, base_url)
            target.write_bytes(revised)
            if revised != original:
                demo_changes[target] = {"sha256": hashlib.sha256(revised).hexdigest(), "byte_length": len(revised)}
        else:
            shutil.copyfile(path, target)
    if demo_changes:
        _update_demo_manifests(output, demo_files, demo_changes)
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
    parser.add_argument("--base-url", default=CUSTOM_PAGES_BASE_URL,
                        help="Public HTTPS base for the staged site.")
    args = parser.parse_args()
    count = stage(Path(__file__).resolve().parents[1] / "docs", args.output, base_url=args.base_url)
    print(f"Staged {count} public documentation files in {args.output}")


if __name__ == "__main__":
    main()
