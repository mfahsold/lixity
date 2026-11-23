#!/usr/bin/env python3
"""Render Homebrew Cask and WinGet release manifests from verified desktop checksums.

Reads `SHA256SUMS-desktop.txt` (or per-target `SHA256SUMS-*.txt` files) from a
desktop release bundle directory, injects verified SHA-256 digests into the
maintained templates under `desktop/packaging/`, verifies that zero `@...@`
placeholders remain, and writes LF-normalized manifests ready for tap/PR upload.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGING = ROOT / "desktop" / "packaging"
CHECKSUM_LINE = re.compile(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$")
PLACEHOLDER_RE = re.compile(r"@[A-Z0-9_]+@")


def load_checksums(artifacts_dir: Path) -> dict[str, str]:
    """Load filename -> lowercase sha256 map from SHA256SUMS files."""
    combined = artifacts_dir / "SHA256SUMS-desktop.txt"
    sources = [combined] if combined.is_file() else sorted(artifacts_dir.glob("SHA256SUMS-*.txt"))
    if not sources:
        raise FileNotFoundError(f"No SHA256SUMS files found in {artifacts_dir}")

    digests: dict[str, str] = {}
    for src in sources:
        for raw_line in src.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = CHECKSUM_LINE.match(line)
            if not match:
                raise ValueError(f"Malformed checksum line in {src.name}: {raw_line!r}")
            digest, filename = match.group(1).lower(), Path(match.group(2)).name
            if filename in digests and digests[filename] != digest:
                raise ValueError(f"Conflicting SHA-256 entries for {filename}")
            digests[filename] = digest
    return digests


def _assert_no_placeholders(rendered: str, label: str) -> None:
    leftover = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if leftover:
        raise ValueError(f"Unreplaced template placeholders in {label}: {', '.join(leftover)}")


def render_homebrew_cask(version: str, digests: dict[str, str], template_path: Path) -> str:
    arm_name = f"Lixity_{version}_aarch64.dmg"
    x64_name = f"Lixity_{version}_x64.dmg"
    arm_sha = digests.get(arm_name)
    x64_sha = digests.get(x64_name)
    if not arm_sha:
        raise ValueError(f"Missing required macOS ARM64 checksum for {arm_name}")

    template = template_path.read_text(encoding="utf-8")
    if x64_sha:
        rendered = (
            template.replace("@VERSION@", version)
            .replace("@SHA256_ARM64@", arm_sha)
            .replace("@SHA256_X64@", x64_sha)
        )
    else:
        # Clean ARM64-only cask when no Intel macOS DMG was built in this run.
        rendered = template.replace('  arch arm: "aarch64", intel: "x64"\n\n', "")
        rendered = rendered.replace(
            '  sha256 arm:   "@SHA256_ARM64@",\n         intel: "@SHA256_X64@"',
            f'  sha256 "{arm_sha}"',
        )
        rendered = rendered.replace("Lixity_#{version}_#{arch}.dmg", "Lixity_#{version}_aarch64.dmg")
        rendered = rendered.replace(
            '  depends_on macos: ">= :monterey"',
            '  depends_on arch: :arm64\n  depends_on macos: ">= :monterey"',
        )
        rendered = rendered.replace("@VERSION@", version)

    _assert_no_placeholders(rendered, "homebrew/lixity.rb")
    return rendered


def render_winget_manifests(
    version: str,
    digests: dict[str, str],
    winget_dir: Path,
) -> dict[str, str]:
    nsis_name = f"Lixity_{version}_x64-setup.exe"
    msi_name = f"Lixity_{version}_x64_en-US.msi"
    nsis_sha = digests.get(nsis_name)
    msi_sha = digests.get(msi_name)
    if not nsis_sha or not msi_sha:
        missing = [name for name, val in ((nsis_name, nsis_sha), (msi_name, msi_sha)) if not val]
        raise ValueError(f"Missing required Windows checksum(s): {', '.join(missing)}")

    replacements = {
        "@VERSION@": version,
        "@SHA256_NSIS_X64@": nsis_sha.upper(),
        "@SHA256_MSI_X64@": msi_sha.upper(),
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
    digests = load_checksums(artifacts_dir)
    written: list[str] = []

    hb_dir = out_dir / "homebrew"
    hb_dir.mkdir(parents=True, exist_ok=True)
    cask_text = render_homebrew_cask(version, digests, packaging_dir / "homebrew" / "lixity.rb.in")
    cask_out = hb_dir / "lixity.rb"
    cask_out.write_text(cask_text, encoding="utf-8", newline="\n")
    written.append(cask_out.relative_to(out_dir).as_posix())

    wg_dir = out_dir / "winget"
    wg_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in render_winget_manifests(version, digests, packaging_dir / "winget").items():
        target = wg_dir / filename
        target.write_text(content, encoding="utf-8", newline="\n")
        written.append(target.relative_to(out_dir).as_posix())

    return {
        "schema_version": "lixity-package-manifests/1",
        "version": version,
        "macos_intel_included": f"Lixity_{version}_x64.dmg" in digests,
        "files": written,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version in X.Y.Z format")
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        required=True,
        help="Directory containing SHA256SUMS-desktop.txt or SHA256SUMS-*.txt",
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

    summary = render_all(version, args.artifacts_dir.resolve(), args.out_dir.resolve())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
