"""Record verified public desktop releases and render their Pages download links."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop.scripts.qualify_desktop_release import QUALIFICATION_FILE, load_qualified_artifacts
from desktop.scripts.verify_desktop_artifacts import (
    DESKTOP_CHECKSUMS,
    PUBLIC_RELEASE_TAG,
    public_installer_inventory,
)

if TYPE_CHECKING:
    from desktop.scripts.verify_desktop_artifacts import DesktopArtifact

ROOT = Path(__file__).resolve().parents[1]
RELEASES = "https://github.com/mfahsold/lixity/releases"
TEST_BUILDS = "https://github.com/mfahsold/lixity/blob/main/desktop/README.md#download-a-test-build"
CATALOG = Path("docs/desktop-downloads.json")
GUIDE = Path("docs/guides/installation.html")
SCHEMA = "lixity-desktop-downloads/1"
CHECKSUMS = DESKTOP_CHECKSUMS
TAG = PUBLIC_RELEASE_TAG
SHA256 = re.compile(r"[0-9a-f]{64}")
DOWNLOAD_BLOCK = re.compile(r"(<!-- desktop-downloads:start -->\n).*?(\n<!-- desktop-downloads:end -->)", re.S)

INSTALLER_LABELS = {
    ("aarch64-apple-darwin", "macos-dmg"): "macOS · Apple Silicon",
    ("x86_64-apple-darwin", "macos-dmg"): "macOS · Intel",
    ("x86_64-pc-windows-msvc", "windows-nsis"): "Windows · x64 · setup",
    ("x86_64-pc-windows-msvc", "windows-msi"): "Windows · x64 · MSI",
    ("x86_64-unknown-linux-gnu", "linux-deb"): "Linux · x64 · Debian package",
    ("x86_64-unknown-linux-gnu", "linux-appimage"): "Linux · x64 · AppImage",
}


def validate_catalog(catalog: dict[str, Any]) -> None:
    if (not isinstance(catalog, dict) or set(catalog) != {"schema_version", "tag", "installers"}
            or catalog["schema_version"] != SCHEMA):
        raise ValueError("Invalid desktop download catalog")
    tag, installers = catalog["tag"], catalog["installers"]
    if not isinstance(installers, list):
        raise ValueError("Expected an installer list")
    if tag is None and not installers:
        return
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise ValueError("Expected a stable desktop release tag")
    expected = public_installer_inventory(tag)
    names: set[str] = set()
    for asset in installers:
        if (not isinstance(asset, dict) or set(asset) != {"target", "kind", "filename", "bytes", "sha256"}
                or any(not isinstance(asset[key], str) for key in ("target", "kind", "filename", "sha256"))):
            raise ValueError("Invalid desktop installer entry")
        pair = (asset["target"], asset["kind"])
        filename = asset["filename"]
        if (expected.get(filename) != pair or filename in names
                or type(asset["bytes"]) is not int or asset["bytes"] <= 0
                or not SHA256.fullmatch(asset["sha256"])):
            raise ValueError(f"Invalid or duplicate desktop installer: {filename}")
        names.add(filename)
    if names != expected.keys():
        raise ValueError("A public desktop catalog requires all qualified installer variants")


def record_catalog(
    release: dict[str, Any], artifacts: Iterable[DesktopArtifact], checksums: bytes, qualification: bytes,
) -> dict[str, Any]:
    """Approve exact installer bytes attached to the selected public GitHub release."""
    tag = release.get("tag_name")
    if (not isinstance(tag, str) or not TAG.fullmatch(tag)
            or release.get("html_url") != f"{RELEASES}/tag/{tag}"
            or release.get("draft") is not False or release.get("prerelease") is not False
            or release.get("immutable") is not True
            or not release.get("published_at")):
        raise ValueError("Expected a public stable Lixity GitHub release")
    entries = release.get("assets")
    if not isinstance(entries, list):
        raise ValueError("Expected a public release asset list")
    public = {}
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or name in public:
            raise ValueError("Invalid or duplicate public release asset")
        public[name] = entry

    def verify_asset(name: str, size: int, digest: str) -> None:
        asset = public.get(name, {})
        if (asset.get("browser_download_url") != f"{RELEASES}/download/{tag}/{name}"
                or asset.get("state") != "uploaded" or asset.get("digest") != f"sha256:{digest}"
                or asset.get("size") != size):
            raise ValueError(f"Public release asset differs from verified file: {name}")

    installers = []
    for artifact in artifacts:
        verify_asset(artifact.filename, artifact.size, artifact.sha256)
        installers.append({"target": artifact.target, "kind": artifact.kind, "filename": artifact.filename,
                           "bytes": artifact.size, "sha256": artifact.sha256})
    catalog = {"schema_version": SCHEMA, "tag": tag, "installers": installers}
    validate_catalog(catalog)
    expected_lines = {f'{asset["sha256"]}  {asset["filename"]}' for asset in installers}
    lines = checksums.decode("ascii").splitlines()
    if len(lines) != len(expected_lines) or set(lines) != expected_lines:
        raise ValueError("The published checksum list must describe the verified desktop installers")
    verify_asset(CHECKSUMS, len(checksums), hashlib.sha256(checksums).hexdigest())
    verify_asset(QUALIFICATION_FILE, len(qualification), hashlib.sha256(qualification).hexdigest())
    return catalog


def write_catalog(catalog: dict[str, Any], output: Path) -> None:
    validate_catalog(catalog)
    with tempfile.TemporaryDirectory(prefix=".lixity-desktop-catalog-", dir=output.parent) as scratch:
        staged = Path(scratch) / CATALOG.name
        staged.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        staged.replace(output)


def render(catalog: dict[str, Any]) -> str:
    validate_catalog(catalog)
    tag = catalog["tag"]
    if tag is None:
        return ('<p class="notice-box">Desktop installers are currently available as test builds. '
                'To start with the published release, <a href="#install">install the local browser app and CLI</a>. '
                f'To test the desktop app, <a href="{TEST_BUILDS}">sign in to GitHub and find a test build</a>.</p>')
    installers = sorted(catalog["installers"], key=lambda asset: (
        INSTALLER_LABELS[(asset["target"], asset["kind"])], asset["filename"],
    ))
    links = []
    for asset in installers:
        label = INSTALLER_LABELS[(asset["target"], asset["kind"])]
        filename = asset["filename"]
        size = asset["bytes"] / (1024 * 1024)
        links.append(f'<li><a href="{RELEASES}/download/{tag}/{filename}">{label} '
                     f'<code>{filename}</code></a> · {size:.1f} MiB</li>')
    return ('<p>Choose the installer for your computer to run Lixity as a desktop app. '
            f'<a href="{RELEASES}/tag/{tag}">Release {tag}</a> · '
            f'<a href="{RELEASES}/download/{tag}/{CHECKSUMS}">Check SHA-256 sums</a>.</p>\n'
            '<ul>\n' + '\n'.join(links) + '\n</ul>')


def build(*, check_only: bool, root: Path) -> list[str]:
    guide = root / GUIDE
    content = guide.read_text(encoding="utf-8")
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    replacement = render(catalog)
    updated, count = DOWNLOAD_BLOCK.subn(lambda match: match[1] + replacement + match[2], content)
    if count != 1:
        raise ValueError("Installation guide must contain one desktop download block")
    if updated == content:
        return []
    if not check_only:
        guide.write_text(updated, encoding="utf-8")
    return [str(GUIDE)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-info", type=Path, required=True, help="GitHub REST release JSON")
    parser.add_argument("--artifacts-dir", type=Path, required=True, help="Verified flattened installer artifacts")
    parser.add_argument("--source-sha", required=True, help="Commit verified for the immutable release")
    parser.add_argument("--output", type=Path, default=ROOT / CATALOG, help="Reviewed desktop download catalog")
    args = parser.parse_args()
    try:
        release = json.loads(args.release_info.read_text(encoding="utf-8"))
        qualification = args.artifacts_dir / QUALIFICATION_FILE
        artifacts = load_qualified_artifacts(args.artifacts_dir, qualification, tag=release["tag_name"],
                                             source_sha=args.source_sha)
        catalog = record_catalog(release, artifacts, (args.artifacts_dir / CHECKSUMS).read_bytes(),
                                 qualification.read_bytes())
        write_catalog(catalog, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
