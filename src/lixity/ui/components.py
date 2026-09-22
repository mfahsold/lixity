"""lixity.ui.components – Small, reusable dashboard building blocks.

Centralises every piece of markup the dashboard reuses: labels and tooltips,
KPI tiles with optional micro-bars, the style-passport band chart, dimension
loading bars and the chapter-matrix micro-bars. All builders are pure
functions returning HTML strings – no state, no dependencies beyond the
standard library.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any

from ..language_data import (
    EN_LABELS,
    GROUP_LABELS,
    HELP_TEXTS,
    LAYER_LABELS,
    METRIC_LABELS,
    UI_LABELS,
)
from ..style_profile import TENSE_MIXED, TENSE_NEUTRAL, TENSE_PAST, TENSE_PRESENT

_DEFAULT_LABELS = {
    **EN_LABELS,
    **METRIC_LABELS["en"],
    **HELP_TEXTS["en"],
    **GROUP_LABELS["en"],
    **LAYER_LABELS["en"],
    **UI_LABELS["en"],
}


def label(labels: Mapping[str, str] | None, key: str) -> str:
    """Localised label with English fallback (never raises)."""
    source = labels if labels else _DEFAULT_LABELS
    return source.get(key, _DEFAULT_LABELS.get(key, key))


def esc(value: object) -> str:
    """HTML-escapes any value (single helper for the whole UI)."""
    return html.escape(str(value))


def help_term(labels: Mapping[str, str] | None, key: str, text: str) -> str:
    """Wraps a term with a tooltip (help text from the language profile)."""
    tip = label(labels, f"help_{key}")
    if not tip or tip.startswith("help_"):
        tip = HELP_TEXTS["en"].get(f"help_{key}") or HELP_TEXTS["de"].get(f"help_{key}") or ""
    if not tip:
        return text
    return (
        f'<span class="help" data-help="{html.escape(tip, quote=True)}" tabindex="0">{text}</span>'
    )


# Canonical tense values (style_profile.TENSE_*) -> label keys.
_TENSE_LABEL_KEYS = {
    TENSE_PRESENT: "present",
    TENSE_PAST: "past",
    TENSE_MIXED: "mixed",
    TENSE_NEUTRAL: "neutral",
}


def tense_class(dominant: str) -> str:
    if dominant == TENSE_PRESENT:
        return "tense-present"
    if dominant == TENSE_PAST:
        return "tense-past"
    if dominant == TENSE_MIXED:
        return "tense-mixed"
    return "tense-neutral"


def tense_label(labels: Mapping[str, str] | None, dominant: str) -> str:
    """Localised tense name (dominant holds canonical values, labels use keys)."""
    return label(labels, _TENSE_LABEL_KEYS.get(dominant, dominant))


def line_label(labels: Mapping[str, str] | None, profile: Any) -> str:
    """Localised line anchor, e.g. 'Z. 470–472' (de) / 'l. 470–472' (en)."""
    prefix = label(labels, "line")
    start = int(profile.start_line)
    end = int(profile.end_line)
    return f"{prefix} {start}" if start == end else f"{prefix} {start}–{end}"


def kpi(
    value: str,
    label_text: str,
    bar: float | None = None,
    jump: str | None = None,
    layer: str | None = None,
    only: bool = False,
    flags: bool = False,
) -> str:
    """KPI tile; ``bar`` adds a proportion bar, ``jump``/``layer`` make it a link.

    ``only``/``flags`` preselect the matching filter on the way down (drill-down).
    """
    bar_html = (
        f'<i class="kpi-bar" style="--v:{max(0.0, min(100.0, bar)):.1f}%"></i>'
        if bar is not None
        else ""
    )
    if jump or layer:
        attrs = (
            f' class="kpi kpi-link" data-jump="{html.escape(jump or "#chapters", quote=True)}"'
            + (f' data-layer="{html.escape(layer, quote=True)}"' if layer else "")
            + (' data-only="1"' if only else "")
            + (' data-flags="1"' if flags else "")
            + ' role="button" tabindex="0"'
        )
    else:
        attrs = ' class="kpi"'
    return f"<div{attrs}><b>{value}</b><span>{label_text}</span>{bar_html}</div>"


def band_chart(
    title: str,
    band_lo: float,
    band_hi: float,
    median: float,
    values: list[float],
    outliers: list[float],
    layer: str | None = None,
) -> str:
    """One style-passport row: data range, ±2σ band, median tick, outlier dots.

    Everything visible encodes data (Tufte); exact numbers live in the tooltip.
    """
    lo = min([*values, band_lo]) if values else band_lo
    hi = max([*values, band_hi]) if values else band_hi
    span = (hi - lo) or 1.0

    def pos(value: float) -> float:
        return max(0.0, min(100.0, (value - lo) / span * 100.0))

    band_left = pos(band_lo)
    band_width = max(0.5, pos(band_hi) - band_left)
    dots = "".join(f'<b style="left:{pos(v):.2f}%"></b>' for v in outliers)
    attrs = f' data-layer="{html.escape(layer, quote=True)}"' if layer else ""
    if layer and outliers:
        attrs += ' data-only="1"'  # drill-down: show the marked passages right away
    return (
        f'<div class="band" title="{html.escape(title, quote=True)}"{attrs}>'
        f'<i class="band-range" style="left:{band_left:.2f}%;width:{band_width:.2f}%"></i>'
        f'<i class="band-median" style="left:{pos(median):.2f}%"></i>'
        f"{dots}</div>"
    )


def loading_bars(
    entries: list[tuple[str, float]],
    limit: float,
    layers: Mapping[str, str] | None = None,
) -> str:
    """Diverging mini-bars for dimension loadings (positive accent, negative blue).

    ``layers`` maps a label to a style-layer key; matching chips become links
    that activate that layer.
    """
    scale = max(limit, 1e-9)
    bars = []
    for name, value in entries:
        width = min(100.0, abs(value) / scale * 100.0)
        sign = "pos" if value >= 0 else "neg"
        layer = (layers or {}).get(name)
        attrs = (
            f' data-layer="{html.escape(layer, quote=True)}" data-jump="#chapters"'
            f' role="button" tabindex="0"'
            if layer
            else ""
        )
        bars.append(
            f'<span class="load {sign}" style="--w:{width:.1f}%"{attrs}><i></i>{esc(name)}</span>'
        )
    return '<div class="loadings">' + "".join(bars) + "</div>"


def status_strip(
    labels: Mapping[str, str] | None, items: Sequence[Mapping[str, Any]] | None
) -> str:
    """Central component status line: one dot + label + detail per component.

    ``items`` is a sequence of mappings with ``key``, ``state``
    (``ok``/``warn``/``error``/``unknown``) and ``detail``. Labels are resolved
    from the language profile (``status_<key>``); the strip is deterministic
    (counts and names only, no timestamps).
    """
    entries = []
    for item in items or ():
        key = str(item.get("key", ""))
        state = str(item.get("state", "unknown"))
        detail = esc(item.get("detail", ""))
        name = label(labels, f"status_{key}")
        entries.append(
            f'<span class="status-item {esc(state)}" title="{detail}">'
            f'<i class="status-dot"></i><b>{esc(name)}</b>'
            f'<span class="status-detail">{detail}</span></span>'
        )
    return '<div class="status-strip">' + "".join(entries) + "</div>"
