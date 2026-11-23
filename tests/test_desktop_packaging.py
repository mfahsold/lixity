"""Verification tests for the cross-platform Rust/Tauri desktop packaging assets."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

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

    # Splash screen exists and has zero Tauri IPC capability access.
    assert (src_tauri / "placeholder-dist" / "splash.html").is_file()
    capability = json.loads((src_tauri / "capabilities" / "desktop-core.json").read_text(encoding="utf-8"))
    assert "splashscreen" not in capability["windows"]
    assert capability["windows"] == ["main", "project-*"]

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


def test_render_package_manifests_emits_homebrew_and_winget_without_placeholders(tmp_path):
    script = DESKTOP / "scripts" / "render_package_manifests.py"
    artifacts = tmp_path / "dist-desktop"
    artifacts.mkdir()
    arm_sha = "a" * 64
    x64_sha = "b" * 64
    nsis_sha = "c" * 64
    msi_sha = "d" * 64
    (artifacts / "SHA256SUMS-desktop.txt").write_text(
        f"{arm_sha}  Lixity_0.10.0_aarch64.dmg\n"
        f"{x64_sha}  Lixity_0.10.0_x64.dmg\n"
        f"{nsis_sha}  Lixity_0.10.0_x64-setup.exe\n"
        f"{msi_sha}  Lixity_0.10.0_x64_en-US.msi\n",
        encoding="utf-8",
    )

    out = tmp_path / "manifests"
    res = subprocess.run(  # noqa: S603 - fixed repository script
        [
            sys.executable,
            str(script),
            "--version",
            "0.10.0",
            "--artifacts-dir",
            str(artifacts),
            "--out-dir",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    summary = json.loads(res.stdout)
    assert summary["macos_intel_included"] is True
    assert len(summary["files"]) == 5

    cask = (out / "homebrew" / "lixity.rb").read_text(encoding="utf-8")
    assert 'version "0.10.0"' in cask
    assert arm_sha in cask and x64_sha in cask
    assert "@" not in cask

    wg_inst = (out / "winget" / "mfahsold.Lixity.installer.yaml").read_text(encoding="utf-8")
    assert "PackageVersion: 0.10.0" in wg_inst
    assert nsis_sha.upper() in wg_inst and msi_sha.upper() in wg_inst
    assert "@" not in wg_inst

    # Also verify clean ARM64-only fallback when Intel macOS DMG is absent.
    (artifacts / "SHA256SUMS-desktop.txt").write_text(
        f"{arm_sha}  Lixity_0.10.0_aarch64.dmg\n"
        f"{nsis_sha}  Lixity_0.10.0_x64-setup.exe\n"
        f"{msi_sha}  Lixity_0.10.0_x64_en-US.msi\n",
        encoding="utf-8",
    )
    out_arm = tmp_path / "manifests-arm"
    res_arm = subprocess.run(  # noqa: S603 - fixed repository script
        [
            sys.executable,
            str(script),
            "--version",
            "0.10.0",
            "--artifacts-dir",
            str(artifacts),
            "--out-dir",
            str(out_arm),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_arm.returncode == 0, res_arm.stdout + res_arm.stderr
    cask_arm = (out_arm / "homebrew" / "lixity.rb").read_text(encoding="utf-8")
    assert "depends_on arch: :arm64" in cask_arm
    assert arm_sha in cask_arm
    assert "@" not in cask_arm
