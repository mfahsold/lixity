#!/usr/bin/env python3
"""Build a relocatable, offline-capable Python 3.12 core runtime bundle for Lixity Desktop.

The core bundle contains only:
  - A relocatable python-build-standalone CPython 3.12 runtime
  - The verified Lixity wheel and its 3 runtime dependencies (pydantic, rich, orjson)

Optional OCR, linguistics (spaCy/Stanza) and speech-synthesis workers stay outside
the desktop core bundle in explicit user-managed runtimes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "desktop" / "runtime-manifest.json"
STRIP_STDLIB_DIRS = (
    "test",
    "tests",
    "idlelib",
    "tkinter",
    "turtledemo",
    "ensurepip",
    "lib2to3",
)


def host_target_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if sys.platform.startswith("linux"):
        return f"{arch}-unknown-linux-gnu"
    if os.name == "nt":
        return f"{arch}-pc-windows-msvc"
    raise RuntimeError(f"Unsupported desktop host platform: {sys.platform} ({machine})")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_uv_python(series: str) -> Path:
    """Locate an already-installed uv managed python-build-standalone root."""
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        raise RuntimeError("uv is not on PATH; pass --python-dir or --python-archive explicitly")
    res = subprocess.run(  # noqa: S603 - explicit uv command
        [uv_bin, "python", "find", "--managed-python", series],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(
            f"No uv-managed Python {series} found; run `uv python install {series}` "
            "or pass --python-dir / --python-archive"
        )
    exe = Path(res.stdout.strip()).resolve()
    # Unix: <root>/bin/python3.12 -> <root>; Windows: <root>/python.exe -> <root>
    return exe.parent.parent if exe.parent.name == "bin" else exe.parent


def extract_verified_archive(archive: Path, dest: Path, expected_sha256: str | None) -> None:
    if expected_sha256:
        actual = sha256_file(archive)
        if actual.lower() != expected_sha256.lower():
            raise ValueError(
                f"SHA-256 mismatch for {archive.name}: expected {expected_sha256}, got {actual}"
            )
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            member_path = (dest / member.name).resolve()
            if not str(member_path).startswith(str(dest.resolve())):
                raise ValueError(f"Unsafe archive member path: {member.name}")
        tf.extractall(dest, filter="data")


def copy_python_tree(source_root: Path, dest_python: Path) -> None:
    if dest_python.exists():
        shutil.rmtree(dest_python)
    shutil.copytree(source_root, dest_python, symlinks=True)


def strip_runtime_bloat(python_root: Path) -> None:
    lib_candidates = [*python_root.glob("lib/python3.*"), python_root / "Lib"]
    for lib_dir in lib_candidates:
        if not lib_dir.is_dir():
            continue
        for name in STRIP_STDLIB_DIRS:
            target = lib_dir / name
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
        for cache_dir in list(lib_dir.rglob("__pycache__")):
            if cache_dir.is_dir() and not cache_dir.is_symlink():
                shutil.rmtree(cache_dir)
    # Remove unused static libraries and C headers not needed at runtime.
    for extra in ("include", "share"):
        target = python_root / extra
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)


def bundled_python_exe(bundle_root: Path, relpath: str) -> Path:
    candidate = bundle_root / relpath
    if candidate.exists():
        return candidate
    for fallback in (
        bundle_root / "python" / "bin" / "python3",
        bundle_root / "python" / "bin" / "python",
        bundle_root / "python" / "python.exe",
    ):
        if fallback.exists():
            return fallback
    raise FileNotFoundError(f"Could not locate bundled Python executable under {bundle_root}")


def install_lixity_into_bundle(
    python_exe: Path,
    wheel: Path,
    *,
    find_links: Path | None,
    offline: bool,
) -> None:
    uv_bin = shutil.which("uv")
    if uv_bin is not None:
        cmd = [
            uv_bin,
            "pip",
            "install",
            "--python",
            str(python_exe),
            "--break-system-packages",
            "--reinstall-package",
            "lixity",
        ]
        if offline:
            cmd.append("--offline")
        if find_links is not None:
            cmd.extend(["--find-links", str(find_links)])
        cmd.append(str(wheel))
    else:
        cmd = [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "--break-system-packages",
            "--no-warn-script-location",
            "--force-reinstall",
        ]
        if offline:
            cmd.append("--no-index")
        if find_links is not None:
            cmd.extend(["--find-links", str(find_links)])
        cmd.append(str(wheel))
    subprocess.run(cmd, check=True)  # noqa: S603 - explicit installer invocation


def directory_size_bytes(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file() and not item.is_symlink():
            total += item.stat().st_size
    return total


def find_default_wheel() -> Path:
    wheels = sorted((ROOT / "dist").glob("lixity-*-py3-none-any.whl"))
    if not wheels:
        raise FileNotFoundError("No wheel found in dist/; run `make build` first or pass --wheel")
    return wheels[-1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=host_target_triple(), help="Target triple (default: current host)")
    parser.add_argument("--wheel", type=Path, default=None, help="Path to lixity wheel (default: latest in dist/)")
    parser.add_argument("--output", type=Path, default=None, help="Destination bundle directory")
    parser.add_argument("--python-dir", type=Path, default=None, help="Existing standalone Python root directory")
    parser.add_argument("--python-archive", type=Path, default=None, help="Standalone Python tar archive")
    parser.add_argument("--expected-sha256", default=None, help="Expected SHA-256 for --python-archive")
    parser.add_argument("--auto-uv", action="store_true", help="Copy uv's managed Python 3.12 standalone runtime")
    parser.add_argument("--find-links", type=Path, default=None, help="Optional local wheelhouse for offline installs")
    parser.add_argument("--offline", action="store_true", help="Forbid network access while installing dependencies")
    parser.add_argument("--no-strip", action="store_true", help="Keep stdlib tests/headers (larger bundle)")
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    targets: dict[str, Any] = manifest["targets"]
    if args.target not in targets:
        raise SystemExit(f"Unsupported target triple: {args.target} (known: {', '.join(sorted(targets))})")
    target_spec = targets[args.target]

    wheel = (args.wheel or find_default_wheel()).resolve()
    if not wheel.is_file():
        raise SystemExit(f"Wheel not found: {wheel}")

    output = (args.output or (ROOT / "desktop" / "build" / "runtime" / args.target)).resolve()
    python_dest = output / "python"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    if args.python_archive is not None:
        expected = args.expected_sha256 or target_spec.get("archive_sha256")
        extract_verified_archive(args.python_archive.resolve(), output, expected)
    elif args.python_dir is not None:
        copy_python_tree(args.python_dir.resolve(), python_dest)
    elif args.auto_uv:
        source_root = discover_uv_python(manifest["python_series"])
        copy_python_tree(source_root, python_dest)
    else:
        raise SystemExit("Specify one of --python-archive, --python-dir, or --auto-uv")

    python_exe = bundled_python_exe(output, target_spec["python_relpath"])
    install_lixity_into_bundle(
        python_exe,
        wheel,
        find_links=args.find_links.resolve() if args.find_links else None,
        offline=args.offline,
    )
    if not args.no_strip:
        strip_runtime_bloat(output / "python")

    # Record installed package versions and bundle metadata.
    inspect_cmd = [
        str(python_exe),
        "-I",
        "-c",
        (
            "import importlib.metadata as m, json, platform, sys; "
            "pkgs = sorted((d.metadata['Name'], d.version) for d in m.distributions()); "
            "print(json.dumps({'python': platform.python_version(), 'packages': dict(pkgs)}))"
        ),
    ]
    meta_proc = subprocess.run(inspect_cmd, capture_output=True, text=True, check=True)  # noqa: S603
    runtime_meta = json.loads(meta_proc.stdout)
    size_bytes = directory_size_bytes(output)
    bundle_manifest = {
        "schema_version": "lixity-runtime-bundle/1",
        "target": args.target,
        "python_relpath": python_exe.relative_to(output).as_posix(),
        "python_version": runtime_meta["python"],
        "wheel": wheel.name,
        "wheel_sha256": sha256_file(wheel),
        "packages": runtime_meta["packages"],
        "uncompressed_bytes": size_bytes,
    }
    (output / "runtime-bundle-manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"[OK] Built Lixity runtime bundle for {args.target} at {output} "
        f"({size_bytes / (1024 * 1024):.1f} MiB uncompressed, Python {runtime_meta['python']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
