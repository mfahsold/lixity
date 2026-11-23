#!/usr/bin/env python3
"""Verify built native desktop installers and emit SHA256SUMS + artifact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ARTIFACT_SCHEMA = "lixity-desktop-artifacts/1"
# Map Tauri's top-level bundle output subdirectories to (suffix, artifact kind).
# Scanning only depth-1 entries under these known directories avoids descending
# into unpacked app trees (e.g. macos/Lixity.app or appimage/Lixity.AppDir).
INSTALLER_SUBDIRS: dict[str, tuple[str, str]] = {
    "dmg": (".dmg", "macos-dmg"),
    "nsis": (".exe", "windows-nsis"),
    "msi": (".msi", "windows-msi"),
    "deb": (".deb", "linux-deb"),
    "rpm": (".rpm", "linux-rpm"),
    "appimage": (".AppImage", "linux-appimage"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_container_magic(path: Path, kind: str) -> None:
    size = path.stat().st_size
    if size < 512:
        raise ValueError(f"{path.name} is unexpectedly small ({size} bytes)")
    with path.open("rb") as handle:
        head = handle.read(64)
        handle.seek(max(0, size - 512))
        tail = handle.read(512)

    if kind == "windows-nsis":
        if not head.startswith(b"MZ"):
            raise ValueError(f"{path.name}: missing PE/MZ header")
    elif kind == "windows-msi":
        if not head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise ValueError(f"{path.name}: missing OLE/MSI compound-file header")
    elif kind == "linux-deb":
        if not head.startswith(b"!<arch>\n"):
            raise ValueError(f"{path.name}: missing Debian ar archive header")
    elif kind == "linux-rpm":
        if not head.startswith(b"\xed\xab\xee\xdb"):
            raise ValueError(f"{path.name}: missing RPM lead magic")
    elif kind == "linux-appimage":
        if not head.startswith(b"\x7fELF"):
            raise ValueError(f"{path.name}: missing ELF executable header")
    elif kind == "macos-dmg" and (b"koly" not in tail and not head.startswith((b"x\x01", b"x\x9c", b"BZh"))):
        raise ValueError(f"{path.name}: missing UDIF koly trailer or compressed DMG header")


def collect_artifacts(bundle_dir: Path) -> list[dict[str, Any]]:
    if not bundle_dir.is_dir():
        raise FileNotFoundError(f"Bundle directory does not exist: {bundle_dir}")

    found: list[dict[str, Any]] = []
    for subdir_name, (suffix, kind) in sorted(INSTALLER_SUBDIRS.items()):
        subdir = bundle_dir / subdir_name
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            if not path.name.endswith(suffix):
                continue
            verify_container_magic(path, kind)
            found.append(
                {
                    "filename": path.name,
                    "relative_path": path.relative_to(bundle_dir).as_posix(),
                    "kind": kind,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle_dir",
        type=Path,
        help="Path to Tauri release bundle directory (e.g. desktop/target/release/bundle)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target triple (e.g. aarch64-apple-darwin, x86_64-pc-windows-msvc, x86_64-unknown-linux-gnu)",
    )
    parser.add_argument(
        "--expect-kind",
        action="append",
        default=[],
        help="Require at least one verified artifact of this kind (repeatable)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Optional output directory for SHA256SUMS and manifest JSON (defaults to bundle_dir)",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        default=None,
        help="Optional destination directory to copy ONLY the verified top-level installer files",
    )
    args = parser.parse_args(argv)

    bundle_dir = args.bundle_dir.resolve()
    artifacts = collect_artifacts(bundle_dir)
    if not artifacts:
        raise SystemExit(f"No native installer artifacts found under {bundle_dir}")

    present_kinds = {item["kind"] for item in artifacts}
    missing_kinds = [k for k in args.expect_kind if k not in present_kinds]
    if missing_kinds:
        raise SystemExit(
            f"Missing expected installer kinds {missing_kinds} (found: {sorted(present_kinds)})"
        )

    out_dir = (args.out_dir or bundle_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.copy_to is not None:
        copy_dir = args.copy_to.resolve()
        copy_dir.mkdir(parents=True, exist_ok=True)
        for item in artifacts:
            src = bundle_dir / item["relative_path"]
            dst = copy_dir / item["filename"]
            if src != dst:
                shutil.copy2(src, dst)

    checksum_lines = [f"{item['sha256']}  {item['filename']}\n" for item in artifacts]
    (out_dir / f"SHA256SUMS-{args.target}.txt").write_text("".join(checksum_lines), encoding="utf-8")

    manifest = {
        "schema_version": ARTIFACT_SCHEMA,
        "target": args.target,
        "artifacts": artifacts,
    }
    (out_dir / f"desktop-artifacts-{args.target}.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
