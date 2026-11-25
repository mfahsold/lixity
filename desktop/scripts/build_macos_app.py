#!/usr/bin/env python3
"""Build and verify a local macOS development app from this checkout."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from build_runtime_bundle import host_target_triple
from macos_app_update import update_installed_app
from smoke_desktop_runtime import verify_bundle
from verify_desktop_artifacts import (
    DesktopArtifact,
    desktop_checksums,
    sha256_file,
    verify_container_magic,
)

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "desktop"
OUTPUT_ROOT = DESKTOP / "build" / "macos-local"
sys.path.insert(0, str(ROOT))

from scripts.check_release import validate  # noqa: E402


def _run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)  # noqa: S603 - fixed local build tools


def _clean_revision() -> str:
    git = shutil.which("git")
    if not git:
        raise ValueError("Git is required when updating the installed app")
    if subprocess.check_output([git, "status", "--porcelain"], cwd=ROOT):  # noqa: S603 - fixed Git query
        raise ValueError("Commit the checkout before updating the installed app")
    return subprocess.check_output([git, "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()  # noqa: S603


def _verify_app(app: Path, prepared_runtime: Path, identifier: str, version: str) -> dict[str, Any]:
    contents = app / "Contents"
    with (contents / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    if (
        info.get("CFBundleIdentifier") != identifier
        or info.get("CFBundleShortVersionString") != version
    ):
        raise ValueError("The macOS bundle identity or version differs from the checkout")
    runtime = contents / "Resources" / "runtime"
    name = "runtime-bundle-manifest.json"
    if (runtime / name).read_bytes() != (prepared_runtime / name).read_bytes():
        raise ValueError("The macOS bundle contains a different runtime manifest")
    smoke = verify_bundle(runtime)
    if smoke["version"] != f"lixity {version}":
        raise ValueError("The bundled interpreter loaded a different Lixity version")
    return smoke


def build(*, offline: bool, dmg: bool, revision: str | None = None) -> dict[str, Any]:
    if sys.platform != "darwin":
        raise ValueError("Local .app builds require macOS")
    required_tools = ("uv", "npx", "cargo", "codesign")
    if dmg:
        required_tools += ("diskutil", "ditto")
    for tool in required_tools:
        if shutil.which(tool) is None:
            raise ValueError(f"Required build tool is unavailable: {tool}")
    import fcntl

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="build-", dir=OUTPUT_ROOT))
    print(f"Building in {output}", flush=True)
    target = host_target_triple()
    config_file = DESKTOP / "src-tauri" / "tauri.conf.json"
    config = json.loads(config_file.read_text(encoding="utf-8"))
    artifacts = output / "packages"
    network = ["--offline"] if offline else []
    _run(
        [
            "uv",
            "build",
            *network,
            "--quiet",
            "--no-create-gitignore",
            "--python",
            sys.executable,
            "--out-dir",
            str(artifacts),
        ]
    )
    version = validate(ROOT, artifacts)
    if config["version"] != version:
        raise ValueError("Tauri version differs from the verified Python package")
    for script in ("generate_menu_locales.py", "generate_desktop_icons.py"):
        _run([sys.executable, str(DESKTOP / "scripts" / script), "--check"])
    runtime = output / "runtime"
    (wheel,) = artifacts.glob("*.whl")
    _run(
        [
            sys.executable,
            str(DESKTOP / "scripts" / "build_runtime_bundle.py"),
            *network,
            "--target",
            target,
            "--auto-uv",
            "--wheel",
            str(wheel),
            "--output",
            str(runtime),
        ]
    )

    # Tauri merges resource maps. Clear inherited sources before adding this build's runtime.
    runtime_destination = "runtime/"
    resources: dict[str, str | None] = {
        source: None
        for source, destination in config["bundle"]["resources"].items()
        if destination == runtime_destination
    }
    resources[Path(os.path.relpath(runtime, config_file.parent)).as_posix() + "/"] = (
        runtime_destination
    )
    override = output / "tauri-local.json"
    override.write_text(json.dumps({"bundle": {"resources": resources}}), encoding="utf-8")
    target_dir = os.environ.get("CARGO_TARGET_DIR")
    cache = (DESKTOP / Path(target_dir).expanduser()).resolve() if target_dir else OUTPUT_ROOT / "target"
    cache.mkdir(parents=True, exist_ok=True)
    name = f"{config['productName']}.app"
    app = output / name
    with (cache / ".lixity-app-build.lock").open("a") as build_lock:
        # Tauri assembles the app in the Cargo target tree. Copy it while holding
        # the lock so simultaneous local builds have distinct verified output.
        fcntl.flock(build_lock, fcntl.LOCK_EX)
        _run(
            [
                "npx",
                *network,
                "--yes",
                "@tauri-apps/cli@2",
                "build",
                "--debug",
                "--ci",
                "--target",
                target,
                "--bundles",
                "app",
                "--no-sign",
                "--config",
                str(override),
                "--",
                "--locked",
                *network,
            ],
            cwd=DESKTOP,
            env={**os.environ, "CARGO_TARGET_DIR": str(cache), "LIXITY_DESKTOP_BUILD_REVISION": revision or ""},
        )
        shutil.copytree(cache / target / "debug" / "bundle" / "macos" / name, app, symlinks=True)
    _run(["bash", str(DESKTOP / "scripts" / "sign_macos_bundle.sh"), "--adhoc", str(app)])
    smoke = _verify_app(app, runtime, config["identifier"], version)
    _run(["codesign", "--verify", "--deep", "--strict", str(app)])
    report: dict[str, Any] = {"app": str(app), "runtime_smoke": smoke}
    if dmg:
        chip = "Apple-Silicon" if target == "aarch64-apple-darwin" else "Intel"
        image = output / f"{app.stem}-{version}-macOS-{chip}.dmg"
        env = dict(os.environ)
        for key in ("APPLE_SIGNING_IDENTITY", "APPLE_NOTARY_PROFILE"):
            env.pop(key, None)
        _run(
            [
                "bash",
                str(DESKTOP / "scripts" / "package_macos_dmg.sh"),
                str(app),
                str(image),
                sys.executable,
            ],
            env=env,
        )
        verify_container_magic(image, "macos-dmg")
        artifact = DesktopArtifact(target, "macos-dmg", image.name, image.stat().st_size, sha256_file(image))
        checksums = output / f"SHA256SUMS-{target}.txt"
        checksums.write_bytes(desktop_checksums((artifact,)))
        report["disk_image"] = {
            "path": str(image),
            "sha256": artifact.sha256,
            "checksums": str(checksums),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline", action="store_true", help="Use cached build tools and dependencies"
    )
    parser.add_argument("--dmg", action="store_true", help="Build and verify a local disk image")
    parser.add_argument("--update-installed", action="store_true", help="Update the closed local app in /Applications")
    args = parser.parse_args()
    try:
        revision = _clean_revision() if args.update_installed else None
        report = build(offline=args.offline, dmg=args.dmg, revision=revision)
        if revision is not None:
            if _clean_revision() != revision:
                raise ValueError("The checkout changed during the build")
            report["local_update"] = update_installed_app(Path(report["app"]), revision)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"macOS app build failed: {exc}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
