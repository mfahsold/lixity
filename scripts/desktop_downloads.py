"""Record qualified public desktop releases and render reviewed download links."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime
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
REPOSITORY = "https://github.com/mfahsold/lixity"
RELEASES = f"{REPOSITORY}/releases"
TEST_BUILDS = f"{REPOSITORY}/blob/main/desktop/README.md#download-a-test-build"
TEST_WORKFLOW = f"{REPOSITORY}/actions/workflows/desktop-release.yml"
CATALOG = Path("docs/desktop-downloads.json")
TEST_BUILD = Path("docs/desktop-test-build.json")
GUIDE = Path("docs/guides/installation.html")
SCHEMA = "lixity-desktop-downloads/1"
TEST_BUILD_SCHEMA = "lixity-desktop-test-build/1"
CHECKSUMS = DESKTOP_CHECKSUMS
TAG = PUBLIC_RELEASE_TAG
PREVIEW_RELEASE_TAG = re.compile(r"desktop-preview-v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9]+)?")
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
UTC_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
DOWNLOAD_BLOCK = re.compile(r"(<!-- desktop-downloads:start -->\n).*?(\n<!-- desktop-downloads:end -->)", re.S)

INSTALLER_LABELS = {
    ("aarch64-apple-darwin", "macos-dmg"): "Mac with Apple silicon",
    ("x86_64-apple-darwin", "macos-dmg"): "Mac with an Intel processor",
    ("x86_64-pc-windows-msvc", "windows-nsis"): "Windows Setup",
    ("x86_64-pc-windows-msvc", "windows-msi"): "Windows MSI",
    ("x86_64-unknown-linux-gnu", "linux-deb"): "Ubuntu and Debian",
    ("x86_64-unknown-linux-gnu", "linux-appimage"): "Linux AppImage",
}
TEST_TARGETS = {
    "aarch64-apple-darwin": ("Mac with Apple silicon", "macos", "DMG disk image"),
    "x86_64-apple-darwin": ("Mac with an Intel processor", "macos", "DMG disk image"),
    "x86_64-pc-windows-msvc": ("Windows Installer", "windows", "Setup EXE"),
    "x86_64-unknown-linux-gnu": ("Linux Installer", "linux", "DEB or AppImage"),
}
PLATFORMS = {
    "macos": ("Mac", "macOS 12 or later"),
    "windows": ("Windows", "64-bit Intel or AMD PCs"),
    "linux": ("Linux", "64-bit Intel or AMD PCs"),
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


def validate_test_build(test_build: dict[str, Any]) -> None:
    """Validate one reviewed Actions run separately from public installers."""
    required_keys = {"schema_version", "tag", "commit", "run_id", "expires_at", "artifacts", "installers"}
    optional_keys = {"preview_release_tag"}
    if (not isinstance(test_build, dict)
            or not required_keys <= test_build.keys()
            or not test_build.keys() <= (required_keys | optional_keys)
            or test_build["schema_version"] != TEST_BUILD_SCHEMA):
        raise ValueError("Invalid desktop test build record")
    tag, commit, run_id = test_build["tag"], test_build["commit"], test_build["run_id"]
    if (not isinstance(tag, str) or not TAG.fullmatch(tag)
            or not isinstance(commit, str) or not COMMIT_SHA.fullmatch(commit)
            or type(run_id) is not int or run_id <= 0):
        raise ValueError("Expected a reviewed test version, source commit and Actions run ID")
    preview_release_tag = test_build.get("preview_release_tag")
    if preview_release_tag is not None and (
        not isinstance(preview_release_tag, str)
        or not PREVIEW_RELEASE_TAG.fullmatch(preview_release_tag)
        or not (preview_release_tag == f"desktop-preview-{tag}"
                or preview_release_tag.startswith(f"desktop-preview-{tag}-"))
    ):
        raise ValueError("Expected a matching desktop-preview-vX.Y.Z prerelease tag")
    expires_at = test_build["expires_at"]
    try:
        expires = datetime.strptime(expires_at, UTC_TIMESTAMP)  # noqa: DTZ007 - compared as a UTC string
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected a UTC test archive expiration timestamp") from exc
    if expires.strftime(UTC_TIMESTAMP) != expires_at:
        raise ValueError("Expected a UTC test archive expiration timestamp")
    artifacts = test_build["artifacts"]
    if (not isinstance(artifacts, dict) or artifacts.keys() != TEST_TARGETS.keys()
            or any(type(artifact) is not int or artifact <= 0 for artifact in artifacts.values())
            or len(set(artifacts.values())) != len(TEST_TARGETS)):
        raise ValueError("Expected a unique test archive ID for each supported target")
    validate_catalog({"schema_version": SCHEMA, "tag": tag, "installers": test_build["installers"]})


def render_platforms(links: Iterable[tuple[str, str]]) -> str:
    by_platform: dict[str, list[str]] = {platform: [] for platform in PLATFORMS}
    for target, link in links:
        by_platform[TEST_TARGETS[target][1]].append(link)
    sections = []
    for platform, (name, requirement) in PLATFORMS.items():
        choices = by_platform[platform]
        actions = '<div class="desktop-download-actions">' + '\n'.join(choices) + '</div>' if choices else ''
        sections.append(f'<section class="desktop-download-card" aria-labelledby="{platform}">\n'
                        f'<h3 id="{platform}">{name}</h3>\n'
                        f'<p class="desktop-platform-requirement">{requirement}</p>\n{actions}\n'
                        f'<p><a href="#{platform}-setup">{name} setup steps</a></p>\n</section>')
    return '<div class="desktop-download-grid">\n' + '\n'.join(sections) + '\n</div>'


def render_verification(installers: list[dict[str, Any]]) -> str:
    digests = [{key: item[key] for key in ("filename", "bytes", "sha256")} for item in installers]
    return ('<section id="installer-check" class="notice-box" aria-labelledby="installer-check-heading" hidden>\n'
            '<h3 id="installer-check-heading">Check the installer</h3>\n'
            '<p>Choose the downloaded installer. If it came in a ZIP, extract it first. '
            'Your browser checks the file on this computer.</p>\n'
            '<label for="installer-check-file">Select the downloaded installer</label>\n'
            '<input id="installer-check-file" type="file" accept=".dmg,.exe,.msi,.deb,.appimage"/>\n'
            '<p id="installer-check-status" role="status"></p>\n'
            f'<script id="installer-check-digests" type="application/json">{json.dumps(digests)}</script>\n'
            '</section>')


def render(catalog: dict[str, Any], test_build: dict[str, Any] | None = None) -> str:
    validate_catalog(catalog)
    tag = catalog["tag"]
    if tag is None:
        if test_build is not None:
            validate_test_build(test_build)
            run = f'{REPOSITORY}/actions/runs/{test_build["run_id"]}'
            preview_tag = test_build.get("preview_release_tag")
            if preview_tag:
                installers = sorted(test_build["installers"], key=lambda asset: (
                    tuple(INSTALLER_LABELS).index((asset["target"], asset["kind"])), asset["filename"],
                ))
                links = []
                for asset in installers:
                    label = INSTALLER_LABELS[(asset["target"], asset["kind"])]
                    filename = asset["filename"]
                    if asset["kind"] == "windows-msi":
                        label += " (German)" if filename.endswith("_de-DE.msi") else " (English)"
                    size = asset["bytes"] / (1024 * 1024)
                    links.append((asset["target"],
                                  f'<a class="ctl primary" href="{RELEASES}/download/{preview_tag}/{filename}">'
                                  f'<strong>{label}</strong><span>Preview · {filename} · {size:.1f} MiB</span></a>'))
                return (f'<p id="desktop-test-downloads">These {test_build["tag"]} desktop preview builds are '
                        'available as direct downloads without a GitHub account. '
                        'macOS builds use ad hoc signing, and Windows builds are unsigned. '
                        'For a PyPI installation, use the '
                        '<a href="#install">published local browser app and CLI</a>.</p>\n'
                        f'{render_platforms(links)}\n'
                        f'{render_verification(installers)}\n'
                        f'<p><a href="{RELEASES}/tag/{preview_tag}">Preview release {preview_tag}</a> · '
                        f'<a href="{RELEASES}/download/{preview_tag}/{CHECKSUMS}">Check SHA-256 sums</a> · '
                        f'<a href="{REPOSITORY}/commit/{test_build["commit"]}">Source commit</a> · '
                        '<a href="#install">Published browser app and CLI</a>.</p>')
            links = []
            for target, (label, _, format_label) in TEST_TARGETS.items():
                artifact = test_build["artifacts"][target]
                links.append((target, f'<a class="ctl primary desktop-test-archive" href="{run}/artifacts/{artifact}">'
                                      f'<strong>{label}</strong><span>GitHub sign-in · ZIP with {format_label}</span></a>'))
            expires = test_build["expires_at"]
            login = f'https://github.com/login?return_to=%2Fmfahsold%2Flixity%2Factions%2Fruns%2F{test_build["run_id"]}'
            return ('<p class="notice-box"><strong>Want to start right away without a GitHub account?</strong> '
                    'Use the <a href="#install">published local browser app and CLI</a> below — '
                    'no sign-in and no expiry. The desktop test archives here are unsigned builds hosted on GitHub Actions.</p>\n'
                    f'<p id="desktop-test-downloads">The {test_build["tag"]} downloads are desktop test builds. '
                    f'<a href="{login}">Sign in to GitHub</a> before downloading. Signed-out visitors may see a GitHub 404. '
                    'Extract the archive and follow the setup steps for your system.</p>\n'
                    '<p id="desktop-test-expired" hidden>These test archives have expired. '
                    f'<a href="{TEST_WORKFLOW}">Find another test build</a>.</p>\n'
                    f'{render_platforms(links)}\n'
                    f'{render_verification(test_build["installers"])}\n'
                    '<p>The archive includes the SHA-256 checksums and the setup guide.</p>\n'
                    f'<p>Download by <time id="desktop-test-expiry" datetime="{expires}">'
                    f'{expires[:10]}, {expires[11:16]} UTC</time>. '
                    f'<a href="{run}#artifacts">GitHub Actions run</a> · '
                    f'<a href="{REPOSITORY}/commit/{test_build["commit"]}">Source commit</a> · '
                    f'<a href="{TEST_WORKFLOW}">Find another test build</a> · '
                    '<a href="#install">Alternative installation</a>.</p>')
        return ('<p class="notice-box">Desktop installers are currently available as test builds. '
                'To start with the published release, <a href="#install">install the local browser app and CLI</a>. '
                f'To test the desktop app, <a href="{TEST_BUILDS}">sign in to GitHub and find a test build</a>.</p>\n'
                + render_platforms([]))
    installers = sorted(catalog["installers"], key=lambda asset: (
        tuple(INSTALLER_LABELS).index((asset["target"], asset["kind"])), asset["filename"],
    ))
    links = []
    for asset in installers:
        label = INSTALLER_LABELS[(asset["target"], asset["kind"])]
        filename = asset["filename"]
        if asset["kind"] == "windows-msi":
            label += " (German)" if filename.endswith("_de-DE.msi") else " (English)"
        size = asset["bytes"] / (1024 * 1024)
        links.append((asset["target"], f'<a class="ctl" href="{RELEASES}/download/{tag}/{filename}">'
                                       f'<strong>{label}</strong><span>{filename} · {size:.1f} MiB</span></a>'))
    return ('<p>Choose the installer for your computer to run Lixity as a desktop app. '
            f'<a href="{RELEASES}/tag/{tag}">Release {tag}</a> · '
            f'<a href="{RELEASES}/download/{tag}/{CHECKSUMS}">Check SHA-256 sums</a>.</p>\n'
            f'{render_platforms(links)}\n{render_verification(installers)}')


def build(*, check_only: bool, root: Path) -> list[str]:
    guide = root / GUIDE
    content = guide.read_text(encoding="utf-8")
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    test_path = root / TEST_BUILD
    test_build = None
    if isinstance(catalog, dict) and catalog.get("tag") is None and test_path.is_file():
        test_build = json.loads(test_path.read_text(encoding="utf-8"))
    replacement = render(catalog, test_build)
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
