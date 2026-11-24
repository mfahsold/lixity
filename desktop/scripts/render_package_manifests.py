#!/usr/bin/env python3
"""Render release checksums and package-manager manifests from verified installers.

Reads the per-target artifact inventory and rechecks the installer files in the
combined CI bundle. Uses the verified names and digests in the maintained
Homebrew Cask and WinGet templates under `desktop/packaging/`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from verify_desktop_artifacts import (
    DESKTOP_CHECKSUMS,
    DesktopArtifact,
    desktop_checksums,
    load_verified_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "desktop" / "packaging"
PLACEHOLDER_RE = re.compile(r"@[A-Z0-9_]+@")
MACOS_ARM64 = "aarch64-apple-darwin"
MACOS_X64 = "x86_64-apple-darwin"
WINDOWS_X64 = "x86_64-pc-windows-msvc"


def _one(artifacts: list[DesktopArtifact], description: str) -> DesktopArtifact:
    if len(artifacts) != 1:
        raise ValueError(f"Expected one {description} installer, found {len(artifacts)}")
    return artifacts[0]


def _assert_no_placeholders(rendered: str, label: str) -> None:
    leftover = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if leftover:
        raise ValueError(f"Unreplaced template placeholders in {label}: {', '.join(leftover)}")


def render_homebrew_cask(
    version: str, arm: DesktopArtifact, intel: DesktopArtifact | None, template_path: Path,
) -> str:
    asset = quote(arm.filename)
    checksums = f'  sha256 "{arm.sha256}"'
    arch = ""
    arch_dependency = "  depends_on arch: :arm64\n"
    if intel is not None:
        arch = f'  arch arm: "{asset}", intel: "{quote(intel.filename)}"\n\n'
        asset = "#{arch}"
        checksums = f'  sha256 arm:   "{arm.sha256}",\n         intel: "{intel.sha256}"'
        arch_dependency = ""
    rendered = (
        template_path.read_text(encoding="utf-8")
        .replace("@VERSION@", version)
        .replace("@ARCH_DECLARATION@", arch)
        .replace("@CHECKSUMS@", checksums)
        .replace("@ASSET@", asset)
        .replace("@ARCH_DEPENDENCY@", arch_dependency)
    )
    _assert_no_placeholders(rendered, "homebrew/lixity.rb")
    return rendered


def render_winget_manifests(
    version: str,
    nsis: DesktopArtifact,
    msi: DesktopArtifact,
    winget_dir: Path,
) -> dict[str, str]:
    replacements = {
        "@VERSION@": version,
        "@ASSET_NSIS_X64@": quote(nsis.filename),
        "@ASSET_MSI_X64@": quote(msi.filename),
        "@SHA256_NSIS_X64@": nsis.sha256.upper(),
        "@SHA256_MSI_X64@": msi.sha256.upper(),
    }
    outputs: dict[str, str] = {}
    for tmpl in sorted(winget_dir.glob("*.yaml.in")):
        rendered = tmpl.read_text(encoding="utf-8")
        for token, value in replacements.items():
            rendered = rendered.replace(token, value)
        out_name = tmpl.name.removesuffix(".in")
        _assert_no_placeholders(rendered, f"winget/{out_name}")
        outputs[out_name] = rendered
    if len(outputs) != 4:
        raise ValueError(f"Expected 4 WinGet templates in {winget_dir}, found {len(outputs)}")
    return outputs


def render_all(
    version: str,
    artifacts_dir: Path,
    out_dir: Path,
    *,
    packaging_dir: Path = PACKAGING,
) -> dict[str, object]:
    artifacts = load_verified_artifacts(artifacts_dir)
    inventory: dict[tuple[str, str], list[DesktopArtifact]] = {}
    for artifact in artifacts:
        inventory.setdefault((artifact.target, artifact.kind), []).append(artifact)
    arm = _one(inventory.get((MACOS_ARM64, "macos-dmg"), []), "macOS ARM64")
    intel_choices = inventory.get((MACOS_X64, "macos-dmg"), [])
    intel = _one(intel_choices, "macOS Intel") if intel_choices else None
    nsis = _one(inventory.get((WINDOWS_X64, "windows-nsis"), []), "Windows x64 NSIS")
    # WiX builds include the locale suffix. WinGet uses the English installer.
    msi = _one([
        package for package in inventory.get((WINDOWS_X64, "windows-msi"), [])
        if package.filename.lower().endswith("_en-us.msi")
    ], "Windows x64 MSI en-US")
    cask_text = render_homebrew_cask(version, arm, intel, packaging_dir / "homebrew" / "lixity.rb.in")
    winget_files = render_winget_manifests(version, nsis, msi, packaging_dir / "winget")
    (artifacts_dir / DESKTOP_CHECKSUMS).write_bytes(desktop_checksums(artifacts))

    hb_dir = out_dir / "homebrew"
    hb_dir.mkdir(parents=True, exist_ok=True)
    cask_out = hb_dir / "lixity.rb"
    cask_out.write_text(cask_text, encoding="utf-8", newline="\n")
    written = [cask_out.relative_to(out_dir).as_posix()]

    wg_dir = out_dir / "winget"
    wg_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in winget_files.items():
        target = wg_dir / filename
        target.write_text(content, encoding="utf-8", newline="\n")
        written.append(target.relative_to(out_dir).as_posix())

    return {
        "schema_version": "lixity-package-manifests/1",
        "version": version,
        "macos_intel_included": intel is not None,
        "files": written,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version in X.Y.Z format")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        required=True,
        help="Directory containing flat installers and per-target manifests; receives SHA256SUMS-desktop.txt",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Destination directory for rendered homebrew/ and winget/ manifests",
    )
    args = parser.parse_args(argv)
    version = args.version.lstrip("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"Version must be X.Y.Z, got: {args.version!r}")

    try:
        summary = render_all(version, args.artifacts_dir.resolve(), args.out_dir.resolve())
    except (OSError, ValueError) as error:
        raise SystemExit(f"Could not render desktop release manifests: {error}") from None
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
