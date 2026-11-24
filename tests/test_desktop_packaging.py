"""Verification tests for the cross-platform Rust/Tauri desktop packaging assets."""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from lixity import __version__
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.server.views import build_server_dashboard
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import DashboardOptions, render_analysis

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"


def test_desktop_menu_locales_are_synchronized_across_all_seven_languages():
    res = subprocess.run(  # noqa: S603 - fixed repository verification script
        [sys.executable, str(DESKTOP / "scripts" / "generate_menu_locales.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    generated = json.loads(
        (DESKTOP / "src-tauri" / "generated" / "menu-locales.json").read_text(encoding="utf-8")
    )
    assert set(generated.keys()) == {"de", "en", "fr", "es", "it", "pt", "nl"}
    expected_keys = set(generated["en"].keys())
    assert {"item_recent_projects", "item_recent_empty"}.issubset(expected_keys)
    for lang, catalog in generated.items():
        assert set(catalog.keys()) == expected_keys, f"Key mismatch in {lang}"
        assert all(isinstance(v, str) and v.strip() for v in catalog.values())


def test_desktop_icons_are_synchronized_and_valid_containers():
    res = subprocess.run(  # noqa: S603 - fixed repository verification script
        [sys.executable, str(DESKTOP / "scripts" / "generate_desktop_icons.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr

    icons_dir = DESKTOP / "src-tauri" / "icons"
    for png_name in ("32x32.png", "128x128.png", "128x128@2x.png", "icon.png"):
        data = (icons_dir / png_name).read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n")

    ico = (icons_dir / "icon.ico").read_bytes()
    assert ico[:4] == b"\x00\x00\x01\x00"

    icns = (icons_dir / "icon.icns").read_bytes()
    assert icns[:4] == b"icns"
    (declared_len,) = struct.unpack(">I", icns[4:8])
    assert declared_len == len(icns)


def test_desktop_metadata_versions_and_targets_align_with_package():
    tauri_conf = json.loads((DESKTOP / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    assert tauri_conf["version"] == __version__
    cargo = (DESKTOP / "Cargo.toml").read_text(encoding="utf-8")
    assert f'[workspace.package]\nversion = "{__version__}"\n' in cargo
    lock = (DESKTOP / "Cargo.lock").read_text(encoding="utf-8")
    assert f'[[package]]\nname = "lixity-desktop"\nversion = "{__version__}"\n' in lock
    for rel_icon in tauri_conf["bundle"]["icon"]:
        assert (DESKTOP / "src-tauri" / rel_icon).is_file(), f"Missing icon: {rel_icon}"

    # Referenced relative packaging paths in tauri.conf.json must exist on disk.
    src_tauri = DESKTOP / "src-tauri"
    assert (src_tauri / tauri_conf["bundle"]["macOS"]["entitlements"]).is_file()
    assert (src_tauri / tauri_conf["bundle"]["windows"]["nsis"]["installerHooks"]).is_file()
    assert (src_tauri / tauri_conf["bundle"]["linux"]["deb"]["desktopTemplate"]).is_file()
    assert (src_tauri / tauri_conf["bundle"]["linux"]["rpm"]["desktopTemplate"]).is_file()
    for rel_src in tauri_conf["bundle"]["linux"]["deb"]["files"].values():
        assert (src_tauri / rel_src).is_file()

    # macOS Info.plist stays synchronized between src-tauri/ and packaging/macos/.
    plist_src = (src_tauri / "Info.plist").read_text(encoding="utf-8")
    plist_pkg = (DESKTOP / "packaging" / "macos" / "Info.plist").read_text(encoding="utf-8")
    assert plist_src == plist_pkg
    assert "NSMicrophoneUsageDescription" in plist_src

    # Linux AppStream MetaInfo is valid XML with matching ID, license and release version.
    metainfo_path = DESKTOP / "packaging" / "linux" / "io.github.mfahsold.Lixity.metainfo.xml"
    tree = ET.parse(metainfo_path)  # noqa: S314 - repository-owned static XML file
    root = tree.getroot()
    assert root.findtext("id") == "io.github.mfahsold.Lixity"
    assert root.findtext("project_license") == "AGPL-3.0-or-later"
    release_versions = [el.attrib.get("version") for el in root.findall("./releases/release")]
    assert __version__ in release_versions

    # Homebrew Cask and WinGet manifest templates exist and use clean version placeholders.
    cask = (DESKTOP / "packaging" / "homebrew" / "lixity.rb.in").read_text(encoding="utf-8")
    assert '@VERSION@' in cask and 'cask "lixity"' in cask
    for winget_name in (
        "mfahsold.Lixity.yaml.in",
        "mfahsold.Lixity.installer.yaml.in",
        "mfahsold.Lixity.locale.en-US.yaml.in",
        "mfahsold.Lixity.locale.de-DE.yaml.in",
    ):
        content = (DESKTOP / "packaging" / "winget" / winget_name).read_text(encoding="utf-8")
        assert "PackageIdentifier: mfahsold.Lixity" in content
        assert "@VERSION@" in content

    cargo_toml = (DESKTOP / "Cargo.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in cargo_toml

    # Splash screen is bundled with the host.
    assert (src_tauri / "placeholder-dist" / "splash.html").is_file()

    # macOS DMG packager script exists.
    assert (DESKTOP / "scripts" / "package_macos_dmg.sh").is_file()

    manifest = json.loads((DESKTOP / "runtime-manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "lixity-desktop-runtime-manifest/1"
    assert manifest["python_series"] == "3.12"
    assert set(manifest["targets"].keys()) == {
        "aarch64-apple-darwin",
        "x86_64-apple-darwin",
        "x86_64-pc-windows-msvc",
        "aarch64-pc-windows-msvc",
        "x86_64-unknown-linux-gnu",
        "aarch64-unknown-linux-gnu",
    }


def test_loopback_workspace_capability_covers_only_the_registered_bridge():
    host = DESKTOP / "src-tauri"
    capability = json.loads((host / "capabilities" / "desktop-core.json").read_text(encoding="utf-8"))
    assert capability["windows"] == ["main", "project-*"]
    assert capability["local"] is False
    assert capability["remote"]["urls"] == ["http://127.0.0.1:*"]

    permission, = tomllib.loads((host / "permissions" / "workspace.toml").read_text(encoding="utf-8"))["permission"]
    assert capability["permissions"] == [
        permission["identifier"], "core:event:default", "core:window:allow-close",
    ]
    bridge = (host / "src" / "security.rs").read_text(encoding="utf-8")
    frontend = set(re.findall(r'\binvoke\("([a-z_]+)"', bridge))
    rust = (host / "src" / "lib.rs").read_text(encoding="utf-8")
    handler = rust.split("tauri::generate_handler![", 1)[1].split("])", 1)[0]
    registered = {entry.strip().removeprefix("commands::") for entry in handler.split(",") if entry.strip()}
    assert set(permission["commands"]["allow"]) == frontend == registered


def test_desktop_runtime_smoke_rejects_python_outside_the_bundle(tmp_path):
    bundle = tmp_path / "runtime"
    bundle.mkdir()
    (bundle / "runtime-bundle-manifest.json").write_text(
        json.dumps({"python_relpath": sys.executable}), encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603 - fixed repository verification script
        [sys.executable, str(DESKTOP / "scripts" / "smoke_desktop_runtime.py"), str(bundle)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Bundled Python executable resolves outside the runtime directory" in result.stderr


def test_macos_signing_preflight_rejects_each_missing_credential_before_writing(tmp_path):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("macOS signing preflight needs Bash")
    credentials = dict.fromkeys((
        "APPLE_DEVELOPER_ID_P12_BASE64", "APPLE_DEVELOPER_ID_P12_PASSWORD",
        "APPLE_NOTARY_KEY_P8_BASE64", "APPLE_NOTARY_KEY_ID", "APPLE_NOTARY_ISSUER_ID",
    ), "synthetic-fixture")
    output = tmp_path / "output"
    script = DESKTOP / "scripts" / "prepare_macos_signing.sh"
    for missing in credentials:
        env = {**os.environ, **credentials, "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(output)}
        env.pop(missing)
        result = subprocess.run(  # noqa: S603 - fixed repository verification script
            [bash, str(script)], env=env, capture_output=True, text=True, check=False, timeout=5,
        )
        assert result.returncode == 1
        assert f"Missing GitHub secret {missing}" in result.stderr
        assert "synthetic-fixture" not in result.stdout + result.stderr
        assert not list(tmp_path.iterdir())


def test_verify_desktop_artifacts_validates_installers_and_rejects_corrupt_files(tmp_path):
    script = DESKTOP / "scripts" / "verify_desktop_artifacts.py"
    bundle = tmp_path / "bundle"
    out = tmp_path / "out"
    (bundle / "dmg").mkdir(parents=True)
    (bundle / "nsis").mkdir(parents=True)
    (bundle / "msi").mkdir(parents=True)
    (bundle / "deb").mkdir(parents=True)
    (bundle / "appimage").mkdir(parents=True)

    (bundle / "dmg" / "Lixity_0.9.1_aarch64.dmg").write_bytes(b"\x00" * 1024 + b"koly" + b"\x00" * 508)
    (bundle / "nsis" / "Lixity_0.9.1_x64-setup.exe").write_bytes(b"MZ" + b"\x00" * 1024)
    (bundle / "msi" / "Lixity_0.9.1_x64_en-US.msi").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1024)
    (bundle / "deb" / "Lixity_0.9.1_amd64.deb").write_bytes(b"!<arch>\n" + b"\x00" * 1024)
    (bundle / "appimage" / "Lixity_0.9.1_amd64.AppImage").write_bytes(b"\x7fELF" + b"\x00" * 1024)

    # Nested runtime files inside unpacked .app / .AppDir trees must NEVER be
    # collected or copied as installers.
    stray_macos = bundle / "macos" / "Lixity.app" / "Contents" / "Resources" / "t64.exe"
    stray_macos.parent.mkdir(parents=True)
    stray_macos.write_bytes(b"MZ" + b"\x00" * 1024)
    stray_appdir = bundle / "appimage" / "Lixity.AppDir" / "usr" / "lib" / "w64.exe"
    stray_appdir.parent.mkdir(parents=True)
    stray_appdir.write_bytes(b"MZ" + b"\x00" * 1024)

    copied = tmp_path / "copied"
    ok = subprocess.run(  # noqa: S603 - fixed repository verification script
        [
            sys.executable,
            str(script),
            str(bundle),
            "--target",
            "x86_64-test",
            "--expect-kind",
            "macos-dmg",
            "--expect-kind",
            "windows-nsis",
            "--expect-kind",
            "windows-msi",
            "--expect-kind",
            "linux-deb",
            "--expect-kind",
            "linux-appimage",
            "--out-dir",
            str(out),
            "--copy-to",
            str(copied),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    manifest = json.loads((out / "desktop-artifacts-x86_64-test.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "lixity-desktop-artifacts/1"
    assert len(manifest["artifacts"]) == 5
    filenames = {item["filename"] for item in manifest["artifacts"]}
    assert "t64.exe" not in filenames and "w64.exe" not in filenames
    assert {p.name for p in copied.iterdir()} == filenames
    checksums = (out / "SHA256SUMS-x86_64-test.txt").read_text(encoding="utf-8").splitlines()
    assert len(checksums) == 5

    # Corrupt PE header must fail verification cleanly.
    (bundle / "nsis" / "Lixity_0.9.1_x64-setup.exe").write_bytes(b"NOPE" + b"\x00" * 1024)
    bad = subprocess.run(  # noqa: S603 - fixed repository verification script
        [sys.executable, str(script), str(bundle), "--target", "x86_64-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode != 0


def test_package_manifests_use_verified_installer_names_and_bytes(tmp_path):
    scripts = DESKTOP / "scripts"
    release_bundle = tmp_path / "release-bundle"
    output = tmp_path / "manifests"
    dmg = b"\x00" * 1024 + b"koly" + b"\x00" * 508
    msi = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 1024
    installers = {
        "aarch64-apple-darwin": {"dmg/Apple Silicon.dmg": dmg},
        "x86_64-apple-darwin": {"dmg/Intel Mac.dmg": b"\x01" + dmg[1:]},
        "x86_64-pc-windows-msvc": {
            "nsis/Windows User.exe": b"MZ" + b"\x00" * 1024,
            "msi/Windows Installer_en-US.msi": msi,
            "msi/Windows Installer_de-DE.msi": msi,
        },
        "x86_64-unknown-linux-gnu": {"deb/Ubuntu-amd64.deb": b"!<arch>\n" + b"\x00" * 1024},
    }
    metadata = []
    for target, files in installers.items():
        bundle = tmp_path / target
        for relative_path, content in files.items():
            installer = bundle / relative_path
            installer.parent.mkdir(parents=True, exist_ok=True)
            installer.write_bytes(content)
        staged = subprocess.run(  # noqa: S603 - fixed repository verification script
            [sys.executable, str(scripts / "verify_desktop_artifacts.py"), str(bundle), "--target", target,
             "--out-dir", str(release_bundle), "--copy-to", str(release_bundle)],
            check=True, capture_output=True, text=True,
        )
        metadata.extend(json.loads(staged.stdout)["artifacts"])

    render_command = [sys.executable, str(scripts / "render_package_manifests.py"), "--version", __version__,
                      "--artifacts-dir", str(release_bundle), "--out-dir", str(output)]
    rendered = subprocess.run(render_command, check=True, capture_output=True, text=True)  # noqa: S603
    summary = json.loads(rendered.stdout)
    assert summary["macos_intel_included"] is True
    assert len(summary["files"]) == 5
    for filename in summary["files"]:
        assert re.search(r"@[A-Z0-9_]+@", (output / filename).read_text(encoding="utf-8")) is None
    digests = {entry["filename"]: entry["sha256"] for entry in metadata}
    cask = (output / "homebrew" / "lixity.rb").read_text(encoding="utf-8")
    assert f'version "{__version__}"' in cask
    assert 'arch arm: "Apple%20Silicon.dmg", intel: "Intel%20Mac.dmg"' in cask
    assert '/releases/download/v#{version}/#{arch}"' in cask
    assert digests["Apple Silicon.dmg"] in cask and digests["Intel Mac.dmg"] in cask
    windows = (output / "winget" / "mfahsold.Lixity.installer.yaml").read_text(encoding="utf-8")
    assert f"/releases/download/v{__version__}/Windows%20User.exe" in windows
    assert f"/releases/download/v{__version__}/Windows%20Installer_en-US.msi" in windows
    assert digests["Windows User.exe"].upper() in windows
    assert digests["Windows Installer_en-US.msi"].upper() in windows
    assert "de-DE.msi" not in windows
    checksums = release_bundle / "SHA256SUMS-desktop.txt"
    expected = "".join(f"{entry['sha256']}  {entry['filename']}\n"
                       for entry in sorted(metadata, key=lambda item: item["filename"]))
    assert checksums.read_bytes() == expected.encode()

    # Preserve size and magic bytes while changing the copied installer's digest.
    (release_bundle / "Windows User.exe").write_bytes(b"MZ" + b"\x01" * 1024)
    rejected = subprocess.run(render_command, check=False, capture_output=True, text=True)  # noqa: S603
    assert rejected.returncode != 0
    assert "Size or SHA-256 differs for Windows User.exe" in rejected.stderr
    assert checksums.read_bytes() == expected.encode()

    (release_bundle / "Windows User.exe").write_bytes(installers["x86_64-pc-windows-msvc"]["nsis/Windows User.exe"])
    (release_bundle / "desktop-artifacts-x86_64-apple-darwin.json").unlink()
    (release_bundle / "Intel Mac.dmg").unlink()
    arm_only = subprocess.run(render_command, check=True, capture_output=True, text=True)  # noqa: S603
    assert json.loads(arm_only.stdout)["macos_intel_included"] is False
    cask_arm = (output / "homebrew" / "lixity.rb").read_text(encoding="utf-8")
    assert 'depends_on arch: :arm64' in cask_arm
    assert '/releases/download/v#{version}/Apple%20Silicon.dmg"' in cask_arm
    assert digests["Apple Silicon.dmg"] in cask_arm


def test_desktop_bridge_is_native_only_and_excluded_from_read_only_exports(tmp_path):
    manuscript = tmp_path / "draft.md"
    manuscript.write_text("# Chapter 1\n\nA short test sentence.\n", encoding="utf-8")

    native_html, _ = build_server_dashboard(str(manuscript), language="en", controls=True)
    empty_native_html, _ = build_server_dashboard(None, language="en", controls=True)
    readonly_report_html, _ = build_server_dashboard(str(manuscript), language="en", controls=False)
    text = manuscript.read_text(encoding="utf-8")
    config, resolved = resolve_document_config(text, "en")
    analysis = analyze_document(text, config, FingerprintThresholds())
    readonly_site_html = render_analysis(
        analysis,
        resolved,
        title="Draft",
        flag_min_severity=2,
        options=DashboardOptions(controls=True, read_only=True),
    )

    marker = "window.LixityDesktopBridge = Object.freeze("
    assert marker in native_html
    assert marker in empty_native_html
    assert marker not in readonly_report_html
    assert marker not in readonly_site_html
    assert marker not in (ROOT / "docs" / "demo" / "report.html").read_text(encoding="utf-8")


def test_strip_runtime_bloat_preserves_windows_stdlib_and_removes_pip(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_runtime_bundle",
        DESKTOP / "scripts" / "build_runtime_bundle.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Synthetic Windows layout: ensure case-insensitive Lib/threading.py survives
    # while pip, distlib .exe stubs and Tcl/Tk assets are removed.
    win_py = tmp_path / "win-python"
    (win_py / "Lib" / "site-packages" / "pip" / "_vendor" / "distlib").mkdir(parents=True)
    (win_py / "Lib" / "site-packages" / "pip-25.0.dist-info").mkdir(parents=True)
    (win_py / "Lib" / "site-packages" / "lixity").mkdir(parents=True)
    (win_py / "Scripts").mkdir(parents=True)
    (win_py / "DLLs").mkdir(parents=True)
    (win_py / "tcl").mkdir(parents=True)

    (win_py / "python.exe").write_bytes(b"MZ")
    (win_py / "Lib" / "threading.py").write_text("# stdlib threading\n", encoding="utf-8")
    (win_py / "Lib" / "site-packages" / "lixity" / "__init__.py").write_text("", encoding="utf-8")
    (win_py / "Lib" / "site-packages" / "pip" / "_vendor" / "distlib" / "t64.exe").write_bytes(b"MZ")
    (win_py / "Scripts" / "pip.exe").write_bytes(b"MZ")
    (win_py / "DLLs" / "tcl86t.dll").write_bytes(b"MZ")
    (win_py / "DLLs" / "python3.dll").write_bytes(b"MZ")

    mod.strip_runtime_bloat(win_py, keep_exe_name="python.exe")

    assert (win_py / "python.exe").is_file()
    assert (win_py / "Lib" / "threading.py").is_file()
    assert (win_py / "Lib" / "site-packages" / "lixity" / "__init__.py").is_file()
    assert (win_py / "DLLs" / "python3.dll").is_file()
    assert not (win_py / "Lib" / "site-packages" / "pip").exists()
    assert not (win_py / "Lib" / "site-packages" / "pip-25.0.dist-info").exists()
    assert not (win_py / "Scripts" / "pip.exe").exists()
    assert not (win_py / "DLLs" / "tcl86t.dll").exists()
    assert not (win_py / "tcl").exists()
