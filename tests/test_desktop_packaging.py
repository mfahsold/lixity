"""Verification tests for the cross-platform Rust/Tauri desktop packaging assets."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
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
    for rel_icon in tauri_conf["bundle"]["icon"]:
        assert (DESKTOP / "src-tauri" / rel_icon).is_file(), f"Missing icon: {rel_icon}"

    cargo_toml = (DESKTOP / "Cargo.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in cargo_toml

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
