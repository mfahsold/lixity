"""Spacing and typography stay out of inline styles in markup and assets.

Layout uses the shared utility classes in ``dashboard.css``. Inline ``style``
remains reserved for measured or dynamic values (bar widths, positions,
heatmap colours, data-driven alignments) and the functional ``display:none``
toggle. This test fails when a converted pattern reappears.
"""

from __future__ import annotations

import re
from pathlib import Path

from lixity.language import LANGUAGE_PROFILES
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.ui.dashboard import render_dashboard

ROOT = Path(__file__).resolve().parents[1]
ASSETS = sorted((ROOT / "src/lixity/ui/assets").glob("*.js"))
STYLE = re.compile(r'style="([^"]*)"')
FORBIDDEN = re.compile(
    r"(margin|padding|font-size|text-align|min-width|max-width|gap|"
    r"justify-content|align-items|user-select)\s*:",
    re.IGNORECASE,
)
ALLOWED_VALUE = re.compile(
    r"^(display:\s*none;?|"
    r"(left|width|--v|--w|height):[^;]*;?|"
    r"flex:\s*[\d.]+ 0 auto|"
    r"background:.+|border-color:.+)$",
    re.IGNORECASE,
)
DYNAMIC = ("' +", "{")
SCRIPT = re.compile(r"<script.*?</script>", re.DOTALL | re.IGNORECASE)


def _violations(markup: str) -> list[str]:
    # Embedded assets are checked in their own test; script bodies contain the
    # dynamic concatenations, not rendered inline styles.
    rendered = SCRIPT.sub("", markup)
    return [value for value in STYLE.findall(rendered)
            if FORBIDDEN.search(value) and not ALLOWED_VALUE.match(value.strip())]


def test_rendered_dashboards_use_no_spacing_inline_styles() -> None:
    labels = LANGUAGE_PROFILES["de"].labels
    empty = render_dashboard([], [], controls=True, labels=labels, language_key="de")
    paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="de")).profile_blocks(
        parse_markdown_blocks("## Kapitel\n\nEin Satz mit genug Wörtern für die Analyse.\n")
    )
    context_marker = "opaque-context"
    loaded = render_dashboard(chapters, paragraphs, controls=True, labels=labels,
                              language_key="de", research_context_token=context_marker)
    for name, markup in (("empty", empty), ("loaded", loaded)):
        assert not _violations(markup), f"{name} dashboard: {_violations(markup)}"


def test_assets_contain_only_measured_or_dynamic_inline_styles() -> None:
    offenders: list[str] = []
    for asset in ASSETS:
        for value in STYLE.findall(asset.read_text(encoding="utf-8")):
            if any(token in value for token in DYNAMIC):
                continue
            if FORBIDDEN.search(value) and not ALLOWED_VALUE.match(value.strip()):
                offenders.append(f"{asset.name}: {value}")
    assert offenders == [], f"Assets must use utility classes instead: {offenders}"

STYLESHEET = ROOT / "src/lixity/ui/assets/dashboard.css"
RETIRED_UTILITIES = (
    "items-center", "mb-3", "mb-5", "mt-5", "mt-6", "mt-8", "mt-10", "my-3",
    "my-4", "ml-3", "ml-4", "ml-5", "w-full", "gap-sm", "form-col",
    "form-col-wide", "form-row-between",
)


RETIRED_MARKUP_CLASSES = (
    "analysis-empty-metrics", "banner-warning", "flag-actions",
    "recent-projects-wrap", "view-nav-label",
)


def test_retired_classes_stay_removed() -> None:
    """Decile utilities and dead markup classes must not come back."""
    sources = sorted((ROOT / "src/lixity/ui").glob("*.py")) + ASSETS + [STYLESHEET]
    offenders: list[str] = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        offenders.extend(
            f"{source.name}: {name}"
            for name in (*RETIRED_UTILITIES, *RETIRED_MARKUP_CLASSES)
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text)
        )
    assert offenders == [], f"Retired classes: {offenders}"
