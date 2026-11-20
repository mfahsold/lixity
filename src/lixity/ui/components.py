"""lixity.ui.components – Small, reusable dashboard building blocks.

Centralises every piece of markup the dashboard reuses: labels and tooltips,
KPI tiles with optional micro-bars, the style-passport band chart, dimension
loading bars and the chapter-matrix micro-bars. All builders are pure
functions returning HTML strings – no state, no dependencies beyond the
standard library.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Callable, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .._version import __version__
from ..format import num as format_num
from ..format import pct as format_pct
from ..language_data import (
    EN_LABELS,
    GROUP_LABELS,
    GUIDANCE_LABELS,
    HELP_TEXTS,
    IDENTITY_LABELS,
    LAYER_LABELS,
    METRIC_LABELS,
    SCENE_LABELS,
    UI_LABELS,
)
from ..status import TENSE_MIXED, TENSE_NEUTRAL, TENSE_PAST, TENSE_PRESENT, Status
from ..workspace_labels import workspace_labels_for

_DEFAULT_LABELS = {
    **GUIDANCE_LABELS["en"],
    **SCENE_LABELS["en"],
    **IDENTITY_LABELS["en"],
    **EN_LABELS,
    **METRIC_LABELS["en"],
    **HELP_TEXTS["en"],
    **GROUP_LABELS["en"],
    **LAYER_LABELS["en"],
    **UI_LABELS["en"],
    **workspace_labels_for("en"),
}


def label(labels: Mapping[str, str] | None, key: str) -> str:
    """Localised label with English fallback (never raises)."""
    source = labels if labels else _DEFAULT_LABELS
    return source.get(key, _DEFAULT_LABELS.get(key, key))


def esc(value: object, quote: bool = True) -> str:
    """HTML-escapes any value (single helper for the whole UI)."""
    return html.escape(str(value), quote=quote)


FAVICON_DATA_URI = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+"
    "PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzI5NDljYyIvPjxyZWN0IHg9IjcuOCIgeT0iNi41IiB3aWR0aD0i"
    "NC42IiBoZWlnaHQ9IjE5IiByeD0iMS41IiBmaWxsPSIjZmZmIi8+PHJlY3QgeD0iNy44IiB5PSIyMS4yIiB3aWR0aD0iMTMuMiIgaGVpZ2h0"
    "PSI0LjMiIHJ4PSIxLjUiIGZpbGw9IiNmZmYiLz48cmVjdCB4PSIxNS4zIiB5PSI4LjIiIHdpZHRoPSI4LjYiIGhlaWdodD0iMi4zIiByeD0i"
    "MS4xNSIgZmlsbD0iI2M5ZDRmZiIvPjxyZWN0IHg9IjE1LjMiIHk9IjEyLjUiIHdpZHRoPSI2LjMiIGhlaWdodD0iMi4zIiByeD0iMS4xNSIg"
    "ZmlsbD0iI2M5ZDRmZiIvPjxyZWN0IHg9IjE1LjMiIHk9IjE2LjgiIHdpZHRoPSI0LjIiIGhlaWdodD0iMi4zIiByeD0iMS4xNSIgZmlsbD0i"
    "I2M5ZDRmZiIvPjwvc3ZnPg=="
)


def script_json(value: Any, *, ensure_ascii: bool = False) -> str:
    """Keep JSON data inside an inert HTML script's raw-text boundary."""
    return (
        json.dumps(value, ensure_ascii=ensure_ascii, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def attr_json(value: Any, *, sort_keys: bool = False) -> str:
    """Encode JSON safely for an HTML attribute value."""
    return esc(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys), quote=True)


def help_badge(help_text: str, aria_label: str) -> str:
    """Render an accessible inline ? help badge."""
    return (
        f'<span class="help" data-help="{esc(help_text, quote=True)}" '
        f'tabindex="0" aria-label="{esc(aria_label, quote=True)}">?</span>'
    )


def close_button(
    close_label: str,
    *,
    control_id: str = "",
    css_class: str = "ctl",
    help_text: str = "",
    extra_attrs: str = "",
) -> str:
    """Render a standardized accessible close button with Escape key shortcut."""
    esc_label = esc(close_label)
    id_attr = f' id="{esc(control_id, quote=True)}"' if control_id else ""
    help_attr = f' data-help="{esc(help_text, quote=True)}"' if help_text else ""
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    return (
        f'<button type="button" class="{esc(css_class, quote=True)}"{id_attr}{attrs} '
        f'aria-label="{esc_label}" title="{esc_label}"{help_attr} '
        'aria-keyshortcuts="Escape">✕</button>'
    )


def modal_footer(buttons_html: str, *, footer_id: str = "") -> str:
    """Render a standardized modal footer action strip."""
    id_attr = f' id="{esc(footer_id, quote=True)}"' if footer_id else ""
    return f'<div class="modal-footer"{id_attr}>{buttons_html}</div>'


def modal_shell(
    modal_id: str,
    title_id: str,
    title_html: str,
    body_html: str,
    *,
    close_label: str,
    footer_html: str = "",
    extra_attrs: str = "",
    title_tag: str = "h3",
    focusable_title: bool = False,
    close_attrs: str = "data-close-modal",
) -> str:
    """Render the shared <dialog class="lixity-modal"> shell."""
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    title_focus = ' tabindex="-1"' if focusable_title else ""
    close_btn = close_button(close_label, css_class="modal-close", extra_attrs=close_attrs)
    return (
        f'<dialog class="lixity-modal" id="{esc(modal_id, quote=True)}"{attrs} '
        f'closedby="any" aria-labelledby="{esc(title_id, quote=True)}">'
        '<div class="modal-card"><div class="modal-header">'
        f'<{title_tag} id="{esc(title_id, quote=True)}"{title_focus}>{title_html}</{title_tag}>'
        f'{close_btn}'
        f'</div>{body_html}{footer_html}</div></dialog>'
    )


def artifacts_panel(
    artifacts: Sequence[Mapping[str, Any]],
    labels: Mapping[str, str] | None,
    language_key: str,
    *,
    title_key: str = "artifacts",
) -> str:
    """Render the generated output / publication artifact list panel."""
    L, N, _ = panel_formatters(labels, language_key)
    rows: list[str] = []
    for art in artifacts:
        name = esc(str(art.get("name", "")))
        meta_bits: list[str] = []
        if art.get("size_kb") is not None:
            meta_bits.append(f"{N(art['size_kb'], 0)} KB")
        if art.get("pages"):
            meta_bits.append(f"{art['pages']} {label(labels, 'pages')}")
        meta = " · ".join(meta_bits)
        href = artifact_href(art.get("href"))
        link = (
            f'<a href="{esc(str(href))}" target="_blank" rel="noopener">{L("open")}</a>'
            if href
            else ""
        )
        rows.append(
            f'<div class="artifact"><span class="name">{name}</span>'
            f'<span class="meta">{esc(meta)}</span>{link}</div>'
        )
    return (
        '<section class="panel">'
        f'<h2>{help_term(labels, "artifacts", L(title_key))}</h2>'
        f'<div class="artifacts">{"".join(rows)}</div></section>'
    )


@lru_cache(maxsize=1)
def _icon_paths() -> dict[str, str]:
    """Read the one icon registry, ``assets/icons.js`` (Lucide subset), not a copy."""
    source = (Path(__file__).parent / "assets" / "icons.js").read_text(encoding="utf-8")
    return dict(re.findall(r'^\s*"([a-z0-9-]+)":\s*\'((?:[^\'\\]|\\.)*)\'', source, re.MULTILINE))


def ui_icon(name: str, *, size: int = 16, css_class: str = "", label_text: str = "") -> str:
    """Server-render a registry icon with the markup ``LixityIcons.svg`` produces.

    Unknown names raise: a typo must not silently show a generic info icon.
    """
    inner = _icon_paths()[name]
    cls = "lixity-icon" + (f" {esc(css_class)}" if css_class else "")
    aria = f'role="img" aria-label="{esc(label_text)}"' if label_text else 'aria-hidden="true"'
    return (
        f'<svg class="{cls}" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
        f'stroke-linejoin="round" {aria}>{inner}</svg>'
    )


def pane_ribbon(
    labels: Mapping[str, str] | None, aria_key: str,
    items: Sequence[tuple[str, str, str] | tuple[str, str, str, str]],
    *, css_class: str = "", start_target: str = "#controls",
) -> str:
    """Sticky, auto-hiding jump ribbon shared by the Project view (``items``:
    target element id, label key, icon name[, help key]). Research builds the same shape in JS."""
    start_label = esc(label(labels, "research_panel_start"))
    start = (
        f'<button type="button" class="ctl ctl-icon" data-ribbon-target="{esc(start_target)}" '
        f'title="{start_label}" aria-label="{start_label}" data-help="{start_label}">'
        f'{ui_icon("arrow-up", size=15)}</button>'
    ) if start_target else ""
    button_parts: list[str] = []
    for item in items:
        target, key, icon = item[0], item[1], item[2]
        help_key = item[3] if len(item) > 3 else f"{key}_help"
        text = esc(label(labels, key))
        help_text = esc(label(labels, help_key)) if labels and help_key in labels else text
        button_parts.append(
            f'<button type="button" class="ctl ctl-sm" data-ribbon-target="#{esc(target)}" '
            f'aria-controls="{esc(target)}" title="{text}" aria-label="{text}" data-help="{help_text}">'
            f'{ui_icon(icon, size=15)}<span class="pane-ribbon-label">{text}</span></button>'
        )
    buttons = "".join(button_parts)
    return (
        f'<nav class="pane-ribbon{(" " + esc(css_class)) if css_class else ""}" '
        f'aria-label="{esc(label(labels, aria_key))}">{start}{buttons}</nav>'
    ) if items else ""


def chapter_link(
    chapter: int, text: object, *, flags: bool = False, css_class: str = "", layer: str = "",
) -> str:
    """Link to a chapter with optional reader flag or measurement context."""
    target = f"#ch-{int(chapter)}"
    classes = f' class="chapter-link{(" " + esc(css_class)) if css_class else ""}"'
    context = ' data-flags="1"' if flags else ""
    if layer:
        context += f' data-layer="{esc(layer)}"'
    return f'<a{classes} href="{target}" data-jump="{target}"{context}>{esc(text)}</a>'


def panel_label(
    labels: Mapping[str, str] | None,
) -> Callable[[str], str]:
    """Bind the shared L helper for surfaces that resolve labels only."""

    def L(key: str) -> str:
        return esc(label(labels, key))

    return L


def panel_formatters(
    labels: Mapping[str, str] | None,
    language_key: str,
) -> tuple[Callable[[str], str], Callable[..., str], Callable[..., str]]:
    """Bind the shared L/N/P helpers for one rendered measurement panel.

    Every measurement surface used to re-declare the localized label, number
    and percent closures locally; binding them here keeps one
    implementation for localization, rounding and percent formatting across
    the dashboard, narrated panels and the chapter heatmap.
    """

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    def P(value: float, decimals: int = 1) -> str:
        return format_pct(value, language_key, decimals)

    return L, N, P


def contrast_text(background: str) -> str:
    """Choose black or white by WCAG sRGB luminance for an opaque #RRGGBB fill."""
    channels = [int(background[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
              for v in channels]
    luminance = sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))
    black_ratio = (luminance + 0.05) / 0.05
    white_ratio = 1.05 / (luminance + 0.05)
    return "#000000" if black_ratio >= white_ratio else "#ffffff"


def product_details(labels: Mapping[str, str] | None = None) -> str:
    """Keep version and licensing links separate from workspace navigation."""
    return (
        f'<span class="version-badge">{esc(label(labels, "version"))} {esc(__version__)}</span>'
        f'<a class="license-badge" href="#license-terms">{esc(label(labels, "license_notice"))}</a>'
    )


def project_header(
    title: str, labels: Mapping[str, str] | None = None,
    language_name: str = "", engine_name: str = "Lixity",
    *, compact: bool = False, meta: str = "",
) -> str:
    subtitle = language_name if compact else label(labels, "app_suffix")
    if language_name and not compact:
        subtitle += " · " + language_name
    return (
        '<header class="project-header">'
        + ("" if compact else '<div class="product-meta">'
        f'<span class="product-name">{esc(engine_name)}</span>'
        + product_details(labels) + '</div>')
        + ("" if compact else f'<span class="project-label">{esc(label(labels, "project_name"))}</span>')
        +
        f'<h1>{esc(title)}</h1>'
        + (f'<p class="sub">{esc(subtitle)}</p>' if subtitle else "")
        + (f'<p class="project-meta">{esc(meta)}</p>' if meta else "")
        + ("" if compact else f'<p class="microhint" id="microhint">{esc(label(labels, "hint"))}</p>'
           + license_terms(labels))
        + '</header>'
    )


def license_terms(labels: Mapping[str, str] | None) -> str:
    """Preserve one notice and target regardless of the workspace layout."""
    return (
        '<aside class="license-terms" id="license-terms" aria-labelledby="license-heading">'
        f'<strong id="license-heading">{esc(label(labels, "license_terms"))}</strong>'
        f'<p>{esc(label(labels, "license_sales_notice"))}</p>'
        '<div class="license-links">'
        '<a href="https://github.com/mfahsold/lixity/blob/main/LICENSE" '
        f'target="_blank" rel="noopener noreferrer">{esc(label(labels, "license_terms"))}</a>'
        '<a href="mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20License">'
        f'{esc(label(labels, "license_contact"))}</a>'
        '</div></aside>'
    )


def panel_start(
    panel_id: str,
    labels: Mapping[str, str] | None,
    title_key: str,
    *,
    extra_class: str = "",
    help_key: str | None = None,
    help_fields: Mapping[str, str] | None = None,
    badge_html: str = "",
    heading_id: str = "",
    extra_attrs: str = "",
) -> str:
    """Open a canonical ``<section class="panel">`` with localized heading."""
    classes = f"panel {extra_class.strip()}" if extra_class.strip() else "panel"
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    title = esc(label(labels, title_key))
    heading_inner = help_term(labels, help_key, title, fields=help_fields) if help_key else title
    if badge_html:
        heading_inner = f"{heading_inner} {badge_html}"
    h_id = f' id="{esc(heading_id, quote=True)}"' if heading_id else ""
    return (
        f'<section class="{esc(classes, quote=True)}" id="{esc(panel_id, quote=True)}"{attrs}>'
        f'<h2{h_id}>{heading_inner}</h2>'
    )


def badge(
    text: object,
    *,
    variant: str = "neutral",
    css_class: str = "",
    extra_attrs: str = "",
) -> str:
    """Render a standardized inline badge/chip."""
    classes = ["badge"]
    if variant:
        classes.append(f"badge-{variant}")
    if css_class:
        classes.append(css_class)
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    return f'<span class="{esc(" ".join(classes), quote=True)}"{attrs}>{esc(text)}</span>'


def table_wrap_start(
    aria_label: str = "",
    *,
    extra_class: str = "",
    wrap_id: str = "",
    aria_labelledby: str = "",
    table_id: str = "",
    caption_html: str = "",
) -> str:
    """Open a scrollable, keyboard-focusable table region."""
    classes = f"table-wrap {extra_class.strip()}" if extra_class.strip() else "table-wrap"
    id_attr = f' id="{esc(wrap_id, quote=True)}"' if wrap_id else ""
    if aria_labelledby:
        label_attr = f' aria-labelledby="{esc(aria_labelledby, quote=True)}"'
    elif aria_label:
        label_attr = f' aria-label="{esc(aria_label, quote=True)}"'
    else:
        label_attr = ""
    region_attrs = ' tabindex="0" role="region"' if (aria_label or aria_labelledby) else ""
    tbl_id = f' id="{esc(table_id, quote=True)}"' if table_id else ""
    return f'<div class="{esc(classes, quote=True)}"{id_attr}{region_attrs}{label_attr}><table{tbl_id}>{caption_html}'


def status_banner(
    element_id: str = "",
    text_html: str = "",
    *,
    css_class: str = "ctl-status",
    tag: str = "p",
    role: str = "status",
    aria_live: str = "polite",
    hidden: bool = False,
    extra_attrs: str = "",
) -> str:
    """Render an accessible live status or error banner."""
    cls_attr = f' class="{esc(css_class, quote=True)}"' if css_class else ""
    id_attr = f' id="{esc(element_id, quote=True)}"' if element_id else ""
    role_attr = f' role="{esc(role, quote=True)}"' if role else ""
    live_attr = f' aria-live="{esc(aria_live, quote=True)}"' if aria_live else ""
    hidden_attr = ' hidden="hidden"' if hidden else ""
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    return (
        f'<{tag}{cls_attr}{id_attr}{role_attr}{live_attr}{hidden_attr}{attrs}>'
        f"{text_html}</{tag}>"
    )


def empty_state(
    text_html: str,
    *,
    css_class: str = "hint",
    badge_text: str = "",
    role: str = "",
) -> str:
    """Render a consistent empty or unavailable state notice."""
    role_attr = f' role="{esc(role, quote=True)}"' if role else ""
    if badge_text:
        return (
            f'<div class="{esc(css_class, quote=True)}"{role_attr}>'
            f'{badge(badge_text, variant="neutral")} <span>{text_html}</span></div>'
        )
    return f'<p class="{esc(css_class, quote=True)}"{role_attr}>{text_html}</p>'


def compact_control(
    label_text: str,
    icon_name: str,
    *,
    control_id: str = "",
    tag: str = "button",
    icon_size: int = 16,
    css_class: str = "ctl reader-compact-control",
    help_text: str = "",
    pressed: bool | None = None,
    expanded: bool | None = None,
    controls_id: str = "",
    keyshortcuts: str = "",
    label_sr_only: bool = False,
    disabled: bool = False,
    extra_attrs: str = "",
) -> str:
    """Render an icon + label compact control (button or details summary)."""
    esc_label = esc(label_text)
    id_attr = f' id="{esc(control_id, quote=True)}"' if control_id else ""
    type_attr = ' type="button"' if tag == "button" else ""
    pressed_attr = f' aria-pressed="{str(pressed).lower()}"' if pressed is not None else ""
    expanded_attr = f' aria-expanded="{str(expanded).lower()}"' if expanded is not None else ""
    controls_attr = f' aria-controls="{esc(controls_id, quote=True)}"' if controls_id else ""
    shortcuts_attr = f' aria-keyshortcuts="{esc(keyshortcuts, quote=True)}"' if keyshortcuts else ""
    help_attr = f' data-help="{esc(help_text, quote=True)}"' if help_text else ""
    disabled_attr = " disabled" if disabled else ""
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    label_cls = "reader-control-label sr-only" if label_sr_only else "reader-control-label"
    icon_html = ui_icon(icon_name, size=icon_size)
    return (
        f'<{tag} class="{esc(css_class, quote=True)}"{type_attr}{id_attr}'
        f'{pressed_attr}{expanded_attr}{controls_attr}{shortcuts_attr}'
        f' aria-label="{esc_label}" title="{esc_label}"{help_attr}{disabled_attr}{attrs}>'
        f'<span class="reader-control-icon" aria-hidden="true">{icon_html}</span>'
        f'<span class="{label_cls}">{esc_label}</span></{tag}>'
    )


def form_field(
    control_id: str,
    label_html: str,
    control_html: str,
    *,
    extra_class: str = "",
    label_class: str = "form-label",
    note_html: str = "",
) -> str:
    """Render a labeled field wrapper using the shared ``setting-field`` layout."""
    classes = f"setting-field {extra_class.strip()}" if extra_class.strip() else "setting-field"
    lbl_cls = f' class="{esc(label_class, quote=True)}"' if label_class else ""
    return (
        f'<div class="{esc(classes, quote=True)}">'
        f'<label{lbl_cls} for="{esc(control_id, quote=True)}">{label_html}</label>'
        f'{control_html}{note_html}</div>'
    )


def dist_row(
    chapter_num: int,
    label_text: str,
    bar_pct: float,
    value_text: str,
    *,
    layer: str = "",
    bar_class: str = "bar",
    bar_inner_class: str = "",
    title_text: str = "",
    unavailable: bool = False,
) -> str:
    """Render one chapter distribution bar row shared by narration panels."""
    if unavailable:
        return (
            f'<div class="row unavailable" title="{esc(title_text, quote=True)}">'
            f'<span class="label">{esc(label_text)}</span>'
            f'<span class="{esc(bar_class, quote=True)}"></span>'
            f'<span class="val">{esc(value_text)}</span>'
            "</div>"
        )
    layer_attr = f' data-layer="{esc(layer, quote=True)}"' if layer else ""
    inner_cls = f' class="{esc(bar_inner_class, quote=True)}"' if bar_inner_class else ""
    aria = ' aria-hidden="true"' if "signal-bar" in bar_class else ""
    return (
        f'<div class="row" data-jump="#ch-{int(chapter_num)}"{layer_attr} '
        f'title="{esc(title_text, quote=True)}">'
        f'{chapter_link(chapter_num, label_text, css_class="label", layer=layer)}'
        f'<span class="{esc(bar_class, quote=True)}"{aria}>'
        f'<i{inner_cls} style="width:{max(0.0, min(100.0, bar_pct)):.1f}%"></i></span>'
        f'<span class="val">{value_text}</span>'
        "</div>"
    )


def action_strip(
    items_html: str,
    *,
    css_class: str = "row",
    strip_id: str = "",
    aria_label: str = "",
    role: str = "",
    hidden: bool = False,
    extra_attrs: str = "",
) -> str:
    """Render a standardized action/filter strip container."""
    id_attr = f' id="{esc(strip_id, quote=True)}"' if strip_id else ""
    role_attr = f' role="{esc(role, quote=True)}"' if role else ""
    label_attr = f' aria-label="{esc(aria_label, quote=True)}"' if aria_label else ""
    hidden_attr = ' hidden="hidden"' if hidden else ""
    attrs = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    return f'<div class="{esc(css_class, quote=True)}"{id_attr}{role_attr}{label_attr}{hidden_attr}{attrs}>{items_html}</div>'


def panel_guide(text_html: str, *, element_id: str = "") -> str:
    """Render a panel's visible reading guidance with trusted inline HTML."""
    identifier = f' id="{esc(element_id)}"' if element_id else ""
    return f'<p class="panel-guide"{identifier}>{text_html}</p>'


def details_start(title_html: str, *, element_id: str = "", extra_class: str = "", opened: bool = False) -> str:
    """Open a native panel disclosure with trusted inline summary HTML."""
    identifier = f' id="{esc(element_id)}"' if element_id else ""
    classes = f"panel-disclosure {extra_class}" if extra_class else "panel-disclosure"
    state = " open" if opened else ""
    return f'<details class="{esc(classes)}"{identifier}{state}><summary>{title_html}</summary>'


def manuscript_pdf_controls(
    labels: Mapping[str, str] | None, *, api_base: str, project_token: str, available: bool,
) -> str:
    """The single native PDF form, placed with the global project commands."""
    L = panel_label(labels)
    from ..pdf_export import PDF_LAYOUTS

    disabled = "" if available else " disabled"
    choices = "".join(f'<option value="{layout}">{L("manuscript_pdf_" + layout)}</option>'
                      for layout in PDF_LAYOUTS)
    layout_field = form_field(
        "manuscript-pdf-layout",
        L("manuscript_pdf_layout"),
        f'<select class="ctl" id="manuscript-pdf-layout" name="layout"{disabled}>{choices}</select>',
        label_class="",
    )
    status_html = status_banner(
        "manuscript-pdf-status",
        "" if available else L("manuscript_pdf_unavailable"),
    )
    return (
        '<details class="manuscript-pdf" id="manuscript-pdf">'
        f'<summary class="ctl" id="manuscript-pdf-title">{L("manuscript_pdf_title")}</summary>'
        f'<form id="manuscript-pdf-form" method="post" '
        f'action="{esc(api_base.rstrip("/") + "/manuscript-pdf")}" '
        f'data-project-token="{esc(project_token)}" data-available="{str(available).lower()}" '
        'aria-describedby="manuscript-pdf-hint">'
        f'<div class="manuscript-pdf-actions">{layout_field}'
        '<button type="submit" class="ctl primary" id="manuscript-pdf-download" disabled>'
        f'{L("manuscript_pdf_download")}</button></div>'
        '<p class="ctl-note" id="manuscript-pdf-layout-desc" aria-live="polite"></p>'
        f'{status_html}</form>'
        f'<p class="ctl-note" id="manuscript-pdf-hint">{L("manuscript_pdf_hint")}</p>'
        f'<noscript><p class="ctl-note">{L("manuscript_pdf_javascript")}</p></noscript></details>'
    )


def toggle_button(text: str, control_id: str, pressed: bool, css_class: str = "ctl", *, disabled: bool = False) -> str:
    classes = f"{css_class} active" if pressed else css_class
    return (
        f'<button type="button" class="{esc(classes)}" id="{esc(control_id)}" '
        f'aria-pressed="{str(pressed).lower()}" title="{esc(text)}"'
        f'{" disabled" if disabled else ""}>{esc(text)}</button>'
    )


def artifact_href(value: Any) -> str:
    """Allow relative artifact paths and HTTP(S), never executable URL schemes."""
    if not isinstance(value, str) or any(ord(character) < 32 for character in value):
        return ""
    candidate: str = value.strip()
    if "\\" in candidate or candidate.startswith("//"):
        return ""
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme and (parsed.scheme.lower() not in ("http", "https") or not parsed.netloc):
        return ""
    return candidate


def help_term(
    labels: Mapping[str, str] | None,
    key: str,
    text: str,
    fields: Mapping[str, str] | None = None,
) -> str:
    """Wraps a term with a tooltip (help text from the language profile).

    ``fields`` substitute ``{name}`` placeholders with live thresholds; label
    packs keep the wording, the caller owns the numbers.
    """
    tip = label(labels, f"help_{key}")
    if not tip or tip.startswith("help_"):
        tip = HELP_TEXTS["en"].get(f"help_{key}") or HELP_TEXTS["de"].get(f"help_{key}") or ""
    if fields:
        for name, value in fields.items():
            tip = tip.replace("{" + name + "}", value)
    if not tip:
        return text
    return (
        f'<span class="help" data-help="{html.escape(tip, quote=True)}" tabindex="0">{text}</span>'
    )


# Central registry: analysis section id -> label key, in display order (sorted
# by editorial workflow relevance for authors, Lektoren and editors: immediate
# flagged passages -> dramaturgy/pacing/scenes -> voice/dialogue/sentence
# craft -> character & echo continuity -> corpus style & chapter matrix).
ANALYSIS_SECTIONS: tuple[tuple[str, str], ...] = (
    ("flags", "panel_flags"),
    ("pacing", "analysis_nav_pacing"),
    ("scenes", "panel_scenes"),
    ("dialogue", "analysis_nav_dialogue"),
    ("dist", "sentence_dist"),
    ("showing", "analysis_nav_showing"),
    ("characters", "analysis_nav_characters"),
    ("motifs", "panel_motifs"),
    ("style", "group_style"),
    ("matrix", "chapter_table"),
)


def _section_help_attr(target: str, labels: Mapping[str, str] | None) -> str:
    help_key = "analysis_nav_help_" + target
    tip = label(labels, help_key)
    return f' data-help="{esc(tip)}"' if tip and tip != help_key else ""


def section_nav(links: Sequence[tuple[str, str]], labels: Mapping[str, str] | None) -> str:
    """Analysis section navigation for the given ``(panel id, label key)`` pairs."""
    if not links:
        return ""
    parts = [
        f'<nav class="toolbar-sections section-navigation" id="analysis-sections" data-section-nav="analysis" '
        f'aria-label="{esc(label(labels, "sections"))}">'
    ]
    for target, label_key in links:
        help_attr = _section_help_attr(target, labels)
        parts.append(
            f'<a href="#{esc(target)}" data-jump="#{esc(target)}" '
            f'data-section-link="{esc(target)}"{help_attr}>{esc(label(labels, label_key))}</a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def analysis_outline_nav(links: Sequence[tuple[str, str]], labels: Mapping[str, str] | None) -> str:
    """Right-hand vertical outline navigation with the growing scroll indicator."""
    if not links:
        return ""
    sections_label = esc(label(labels, "sections"))
    parts = [
        '<details class="analysis-outline-contents" data-section-contents="" open>',
        f'<summary id="analysis-outline-summary">{sections_label}</summary>',
        f'<nav class="section-navigation" id="analysis-outline-nav" data-section-nav="analysis-outline" '
        f'aria-label="{sections_label}">',
        "<ul>",
    ]
    for target, label_key in links:
        parts.append(
            f'<li><a href="#{esc(target)}" data-jump="#{esc(target)}" '
            f'data-section-link="{esc(target)}"{_section_help_attr(target, labels)}>'
            f'{esc(label(labels, label_key))}</a></li>'
        )
    parts.append("</ul></nav></details>")
    return "".join(parts)


def checkbox_field(input_html: str, text_html: str, *, extra_class: str = "") -> str:
    """One checkbox row of the shared ``form-checkbox`` component.

    ``input_html`` and ``text_html`` are caller-built markup: pass escaped
    values or helpers such as :func:`help_term`.
    """
    classes = f"form-checkbox {extra_class}".strip()
    return f'<label class="{classes}">{input_html} {text_html}</label>'


# Canonical tense values (status.TENSE_*) are the label keys themselves.
_TENSE_CLASSES = {TENSE_PRESENT, TENSE_PAST, TENSE_MIXED, TENSE_NEUTRAL}


def tense_class(dominant: str) -> str:
    return f"tense-{dominant}" if dominant in _TENSE_CLASSES else "tense-neutral"


def tense_label(labels: Mapping[str, str] | None, dominant: str) -> str:
    """Localised tense name (dominant holds the canonical neutral value)."""
    return label(labels, dominant)


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
    extra_attrs: str = "",
) -> str:
    """KPI tile; ``bar`` adds a proportion bar, ``jump``/``layer`` make it a link.

    ``only``/``flags`` preselect the matching filter on the way down (drill-down).
    """
    bar_html = (
        f'<i class="kpi-bar" style="--v:{max(0.0, min(100.0, bar)):.1f}%"></i>'
        if bar is not None
        else ""
    )
    extra = f" {extra_attrs.strip()}" if extra_attrs.strip() else ""
    if jump or layer:
        attrs = (
            f' class="kpi kpi-link" data-jump="{html.escape(jump or "#chapters", quote=True)}"'
            + (f' data-layer="{html.escape(layer, quote=True)}"' if layer else "")
            + (' data-only="1"' if only else "")
            + (' data-flags="1"' if flags else "")
            + extra
            + ' role="button" tabindex="0"'
        )
    elif extra:
        attrs = f' class="kpi kpi-link"{extra} role="button" tabindex="0"'
    else:
        attrs = ' class="kpi"'
    return f"<div{attrs}><b>{value}</b><span>{label_text}</span>{bar_html}</div>"


def kpi_row(tiles: Sequence[str], *, row_id: str = "") -> str:
    """Lay out pre-rendered measurement tiles on the shared responsive grid."""
    attrs = f' id="{esc(row_id)}"' if row_id else ""
    return f'<div class="kpi-row"{attrs}>{"".join(tiles)}</div>'


def kpi_group(tiles: Sequence[str], caption: str, *, hint: str = "", footer: str = "") -> str:
    """Group measurement tiles under escaped display copy and optional rendered content."""
    if not tiles:
        return ""
    note = panel_guide(esc(hint)) if hint else ""
    return (
        f'<div class="kpi-group"><div class="kpi-caption">{esc(caption)}</div>'
        f'{note}{kpi_row(tiles)}{footer}</div>'
    )


def band_chart(
    title: str,
    band_lo: float,
    band_hi: float,
    median: float,
    values: list[float],
    outliers: list[float],
) -> str:
    """One style-passport row: data range, ±2σ band, median tick, outlier dots.

    Everything visible encodes data (Tufte); exact numbers live in the tooltip.
    Interaction (jump/layer) lives on the parent ``.band-row``.
    """
    lo = min([*values, band_lo]) if values else band_lo
    hi = max([*values, band_hi]) if values else band_hi
    span = (hi - lo) or 1.0

    def pos(value: float) -> float:
        return max(0.0, min(100.0, (value - lo) / span * 100.0))

    band_left = pos(band_lo)
    band_width = max(0.5, pos(band_hi) - band_left)
    dots = "".join(f'<b style="left:{pos(v):.2f}%"></b>' for v in outliers)
    return (
        f'<div class="band" title="{html.escape(title, quote=True)}">'
        f'<i class="band-range" style="left:{band_left:.2f}%;width:{band_width:.2f}%"></i>'
        f'<i class="band-median" style="left:{pos(median):.2f}%"></i>'
        f"{dots}</div>"
    )


def loading_bars(
    entries: list[tuple[str, float]],
    limit: float,
    layers: Mapping[str, str] | None = None,
    features: Mapping[str, str] | None = None,
    dimension: int | None = None,
) -> str:
    """Mini-bars with explicit signs for dimension loadings.

    ``features`` identifies chapter measurements; ``layers`` supplies applicable
    paragraph layers for the existing reading action.
    """
    scale = max(limit, 1e-9)
    bars = []
    for name, value in entries:
        width = min(100.0, abs(value) / scale * 100.0)
        sign = "pos" if value >= 0 else "neg"
        layer = (layers or {}).get(name)
        feature = (features or {}).get(name)
        attrs = ""
        if feature:
            attrs = (
                f' data-metric-feature="{esc(feature)}" data-dimension-loading="1"'
                f' data-dimension-index="{dimension}" data-loading="{value}"'
                f' data-layer="{esc(layer or "")}" data-jump="#chapters"'
                ' role="button" tabindex="0"'
            )
        elif layer:
            attrs = (
                f' data-layer="{esc(layer)}" data-jump="#chapters" data-dimension-loading="1"'
                ' role="button" tabindex="0"'
            )
        bars.append(
            f'<span class="load {sign}" style="--w:{width:.1f}%" title="{esc(name)}"{attrs}>'
            f'<span class="load-track"><i></i></span><span class="load-sign">{"+" if value >= 0 else "−"}</span>'
            f'<b>{esc(name)}</b></span>'
        )
    return '<div class="loadings">' + "".join(bars) + "</div>"


def status_strip(
    labels: Mapping[str, str] | None, items: Sequence[Mapping[str, Any]] | None
) -> str:
    """Central component status line: one dot + label + detail per component.

    ``items`` is a sequence of mappings with ``key``, ``state`` (a
    :class:`lixity.status.Status` value: ``ok``/``warn``/``error``/``unknown``)
    and ``detail``. Labels are resolved from the language profile
    (``status_<key>``); the strip is deterministic (counts and names only,
    no timestamps).
    """
    entries = []
    for item in items or ():
        key = str(item.get("key", ""))
        raw_state = str(item.get("state", Status.UNKNOWN.value))
        try:
            state = Status(raw_state).value
        except ValueError:
            state = Status.UNKNOWN.value
        detail = esc(item.get("detail", ""))
        name = label(labels, f"status_{key}")
        entries.append(
            f'<span class="status-item {esc(state)}" title="{detail}">'
            f'<i class="status-dot"></i><b>{esc(name)}</b>'
            f'<span class="status-detail">{detail}</span></span>'
        )
    return '<div class="status-strip">' + "".join(entries) + "</div>"


def loading_state(text: str, element_id: str | None = None, role: str = "status") -> str:
    """Centralised accessible loading indicator with animated spinner."""
    id_attr = f' id="{esc(element_id, quote=True)}"' if element_id else ""
    return (
        f'<div class="loading-state"{id_attr} role="{esc(role)}" aria-busy="true" aria-live="polite">'
        f'<span class="loading-spinner" aria-hidden="true"></span>'
        f'<span class="loading-text">{esc(text)}</span>'
        f"</div>"
    )


def template_preset_bar(
    bar_id: str,
    label_text: str,
    target_textarea_id: str,
    presets: Sequence[tuple[str, str, str]],
    *,
    tag_input_id: str | None = None,
) -> str:
    """Render a reusable preset-button bar that populates a textarea and optional tag input.

    Each entry in ``presets`` is ``(button_label, tag_value, markdown_body)``.
    """
    tag_attr = (
        f' data-template-tag-target="{esc(tag_input_id, quote=True)}"'
        if tag_input_id
        else ""
    )
    buttons = "".join(
        f'<button type="button" class="ctl ctl-sm" '
        f'data-template-target="{esc(target_textarea_id, quote=True)}"'
        f'{tag_attr} '
        f'data-template-tag="{esc(tag_val, quote=True)}" '
        f'data-template-body="{esc(body_text, quote=True)}">'
        f"{esc(btn_label)}</button>"
        for btn_label, tag_val, body_text in presets
    )
    return (
        f'<div class="row mb-2 chip-row template-preset-bar" id="{esc(bar_id, quote=True)}">'
        f'<span class="ctl-note">{esc(label_text)}:</span>{buttons}</div>'
    )


def tag_input_with_suggestions(
    input_id: str,
    placeholder: str,
    suggestions_id: str,
    *,
    extra_input_attrs: str = "",
) -> str:
    """Render a comma-separated input paired with a clickable suggestion chip container."""
    attrs = f" {extra_input_attrs.strip()}" if extra_input_attrs.strip() else ""
    return (
        f'<input class="ctl" id="{esc(input_id, quote=True)}" '
        f'placeholder="{esc(placeholder, quote=True)}" data-tag-input="true"{attrs}/>'
        f'<div class="chip-row mt-1 tag-suggestions" id="{esc(suggestions_id, quote=True)}" '
        f'data-tag-suggestions-for="{esc(input_id, quote=True)}" hidden></div>'
    )


def empty_aware_multiselect(
    select_id: str,
    empty_hint_id: str,
    empty_hint_text: str,
    *,
    help_text: str = "",
    size: int = 3,
) -> str:
    """Render a multi-select paired with a declarative empty-state note."""
    help_attr = f' data-help="{esc(help_text, quote=True)}"' if help_text else ""
    return (
        f'<select class="ctl" id="{esc(select_id, quote=True)}" multiple size="{int(size)}" '
        f'data-empty-hint="{esc(empty_hint_id, quote=True)}"{help_attr}></select>'
        f'<p class="ctl-note" id="{esc(empty_hint_id, quote=True)}" hidden>{esc(empty_hint_text)}</p>'
    )
