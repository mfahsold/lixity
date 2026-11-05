"""Unit tests for the Obsidian-style Command Palette component."""

from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[1] / "src/lixity/ui/assets"


def test_command_palette_asset_exists_and_exposes_api():
    palette_js = (ASSET_DIR / "command-palette.js").read_text(encoding="utf-8")
    assert "window.LixityCommandPalette" in palette_js
    assert "command-palette-dialog" in palette_js
    assert "command-palette-search" in palette_js
    assert "getCommands" in palette_js


def test_command_palette_supports_essential_shortcuts():
    palette_js = (ASSET_DIR / "command-palette.js").read_text(encoding="utf-8")
    # Ctrl/Cmd + P and Ctrl/Cmd + K
    assert 'key === "p"' in palette_js
    assert 'key === "k"' in palette_js
    assert "e.ctrlKey || e.metaKey" in palette_js
    # Escape
    assert 'e.key === "Escape"' in palette_js
    # Focus mode shortcut F
    assert 'key === "f"' in palette_js


def test_command_palette_includes_core_categories():
    palette_js = (ASSET_DIR / "command-palette.js").read_text(encoding="utf-8")
    for cat in ["Analyse", "Recherche", "Audio", "Ansicht", "Export"]:
        assert cat in palette_js
