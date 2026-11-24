"""Record verified public desktop releases and render their Pages download links."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from desktop.scripts.verify_desktop_artifacts import DesktopArtifact

ROOT = Path(__file__).resolve().parents[1]
RELEASES = "https://github.com/mfahsold/lixity/releases"
CATALOG = Path("docs/desktop-downloads.json")
GUIDE = Path("docs/guides/installation.html")
SCHEMA = "lixity-desktop-downloads/1"
CHECKSUMS = "SHA256SUMS-desktop.txt"
TAG = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+")
SHA256 = re.compile(r"[0-9a-f]{64}")
FILENAME = re.compile(r"Lixity[_-][A-Za-z0-9_.-]+")
DOWNLOAD_BLOCK = re.compile(r"(<!-- desktop-downloads:start -->\n).*?(\n<!-- desktop-downloads:end -->)", re.S)

# The approved public formats. Runtime build targets can be broader.
INSTALLERS = {
    ("aarch64-apple-darwin", "macos-dmg"): ("macOS · Apple Silicon", ".dmg"),
    ("x86_64-apple-darwin", "macos-dmg"): ("macOS · Intel", ".dmg"),
    ("x86_64-pc-windows-msvc", "windows-nsis"): ("Windows · x64 · setup", ".exe"),
    ("x86_64-pc-windows-msvc", "windows-msi"): ("Windows · x64 · MSI", ".msi"),
    ("x86_64-unknown-linux-gnu", "linux-deb"): ("Linux · x64 · Debian package", ".deb"),
    ("x86_64-unknown-linux-gnu", "linux-appimage"): ("Linux · x64 · AppImage", ".AppImage"),
}


def validate_catalog(catalog: dict[str, Any]) -> None:
    if set(catalog) != {"schema_version", "tag", "installers"} or catalog["schema_version"] != SCHEMA:
        raise ValueError("Invalid desktop download catalog")
    tag, installers = catalog["tag"], catalog["installers"]
    if not isinstance(installers, list):
        raise ValueError("Expected an installer list")
    if tag is None and not installers:
        return
    if not isinstance(tag, str) or not TAG.fullmatch(tag):
        raise ValueError("Expected a stable desktop release tag")
    pairs: set[tuple[str, str]] = set()
    names: set[str] = set()
    for asset in installers:
        if (not isinstance(asset, dict) or set(asset) != {"target", "kind", "filename", "bytes", "sha256"}
                or any(not isinstance(asset[key], str) for key in ("target", "kind", "filename", "sha256"))):
            raise ValueError("Invalid desktop installer entry")
        pair = (asset["target"], asset["kind"])
        variant = INSTALLERS.get(pair)
        filename = asset["filename"]
        if (variant is None or not FILENAME.fullmatch(filename) or not filename.endswith(variant[1])
                or filename in names or type(asset["bytes"]) is not int or asset["bytes"] <= 0
                or not SHA256.fullmatch(asset["sha256"])):
            raise ValueError(f"Invalid or duplicate desktop installer: {filename}")
        pairs.add(pair)
        names.add(filename)
    if pairs != INSTALLERS.keys():
        raise ValueError("A public desktop catalog requires all qualified installer formats")


def record_catalog(
    release: dict[str, Any], artifacts: Iterable[DesktopArtifact], checksums: bytes,
) -> dict[str, Any]:
    """Approve exact installer bytes attached to the selected public GitHub release."""
    tag = release.get("tag_name")
    if (not isinstance(tag, str) or not TAG.fullmatch(tag)
            or release.get("html_url") != f"{RELEASES}/tag/{tag}"
            or release.get("draft") is not False or release.get("prerelease") is not False
            or not release.get("published_at")):
        raise ValueError("Expected a public stable Lixity GitHub release")
    public = {entry["name"]: entry for entry in release["assets"]}

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
    return catalog


def render(catalog: dict[str, Any]) -> str:
    validate_catalog(catalog)
    tag = catalog["tag"]
    if tag is None:
        return ('<p class="notice-box">Desktop installers are in testing. You can start today with the '
                '<a href="#install">published local browser app</a>.</p>')
    installers = sorted(catalog["installers"], key=lambda asset: (
        INSTALLERS[(asset["target"], asset["kind"])][0], asset["filename"],
    ))
    links = []
    for asset in installers:
        label = INSTALLERS[(asset["target"], asset["kind"])][0]
        filename = asset["filename"]
        size = asset["bytes"] / (1024 * 1024)
        links.append(f'<li><a href="{RELEASES}/download/{tag}/{filename}">{label} '
                     f'<code>{filename}</code></a> · {size:.1f} MiB</li>')
    return (f'<p>Published desktop installers for <a href="{RELEASES}/tag/{tag}">{tag}</a>. '
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
    from desktop.scripts.verify_desktop_artifacts import load_verified_artifacts

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-info", type=Path, required=True, help="GitHub REST release JSON")
    parser.add_argument("--artifacts-dir", type=Path, required=True, help="Verified flattened installer artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / CATALOG, help="Reviewed desktop download catalog")
    args = parser.parse_args()
    try:
        release = json.loads(args.release_info.read_text(encoding="utf-8"))
        catalog = record_catalog(release, load_verified_artifacts(args.artifacts_dir),
                                 (args.artifacts_dir / CHECKSUMS).read_bytes())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
