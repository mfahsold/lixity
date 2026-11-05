"""Unit tests for the Lucide icon library asset in Lixity UI."""

import re
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parents[1] / "src/lixity/ui/assets"


def test_icons_asset_exists_and_contains_standard_lucide_set():
    icons_js = (ASSET_DIR / "icons.js").read_text(encoding="utf-8")
    assert "window.LixityIcons" in icons_js
    assert "lucide.dev" in icons_js

    # Check essential icon names are present in the catalog
    required_icons = [
        "book-open", "archive", "settings", "search",
        "info", "lightbulb", "alert-circle", "triangle-alert", "shield-alert",
        "bold", "italic", "heading", "link", "code", "list", "sigma",
        "mic", "mic-off", "play", "pause", "square", "volume-2",
        "check", "x", "chevron-right", "download"
    ]
    for name in required_icons:
        assert f'"{name}":' in icons_js, f"Icon '{name}' must be present in icons.js"


def test_icons_asset_path_definitions_are_safe_svg_strings():
    icons_js = (ASSET_DIR / "icons.js").read_text(encoding="utf-8")
    paths = re.findall(r'"([a-z0-9-]+)":\s*\'([^\']+)\'', icons_js)
    assert len(paths) >= 30, "Expected at least 30 icons in the curated Lucide subset"
    for _name, content in paths:
        assert "<script" not in content.lower()
        assert "javascript:" not in content.lower()
        assert ("<path" in content or "<line" in content or "<circle" in content
                or "<rect" in content or "<polyline" in content or "<polygon" in content)
