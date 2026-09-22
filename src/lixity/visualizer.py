"""lixity.visualizer – Minimalist, self-contained single-file HTML dashboard.

Renders an interactive stylometric report combining KPI cards, sentence rhythm bars,
diverging z-score heatmap, style passport, latent dimensions, chapter map,
and editor-visible work markers with floating tooltips.
"""

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path as _Path
from typing import Any

from .format import num as format_num
from .format import pct as format_pct
from .language_data import EN_LABELS, HELP_TEXTS, METRIC_LABELS
from .style_fingerprint import FEATURES, LAYER_FEATURES, layer_stats, z_color
from .style_profile import (
    TENSE_MIXED,
    TENSE_NEUTRAL,
    TENSE_PAST,
    TENSE_PRESENT,
    ChapterProfile,
    ParagraphProfile,
)

_ASSET_DIR = _Path(__file__).with_name("assets")
_CSS = (_ASSET_DIR / "dashboard.css").read_text(encoding="utf-8")
_JS = (_ASSET_DIR / "dashboard.js").read_text(encoding="utf-8")


_DEFAULT_LABELS = {**EN_LABELS, **METRIC_LABELS["en"], **HELP_TEXTS["en"]}


def _label(labels: Mapping[str, str] | None, key: str) -> str:
    source = labels if labels else _DEFAULT_LABELS
    return source.get(key, _DEFAULT_LABELS.get(key, key))


# Help-key mapping: model field name (FEATURES) -> tooltip key (help_*).
_FEATURE_HELP = {
    "asl": "asl",
    "staccato_pct": "staccato",
    "kaskade_pct": "kaskade",
    "sentence_cv": "cv",
    "dialog_pct": "dialogue",
    "function_word_pct": "function_words",
    "filter_density": "perception",
    "modal_density": "modal",
    "passive_density": "passive",
    "nominalization_density": "nominal",
    "adjective_density": "adjective",
    "long_word_pct": "lix",
    "start_entropy": "start_entropy",
    "first_person_start_rate": "first_start",
    "guiraud_r": "guiraud",
    "hd_d": "hd_d",
    "mtld": "mtld",
    "mattr": "mattr",
    "maas_a2": "maas",
}


def _tense_class(dominant: str) -> str:
    if dominant == TENSE_PRESENT:
        return "tense-present"
    if dominant == TENSE_PAST:
        return "tense-past"
    if dominant == TENSE_MIXED:
        return "tense-mixed"
    return "tense-neutral"


# Canonical tense values (style_profile.TENSE_*) -> label keys of the language profile.
_TENSE_LABEL_KEYS = {
    TENSE_PRESENT: "present",
    TENSE_PAST: "past",
    TENSE_MIXED: "mixed",
    TENSE_NEUTRAL: "neutral",
}


def _tense_label(labels: Mapping[str, str] | None, dominant: str) -> str:
    """Localised tense name (dominant holds canonical values, labels use keys)."""
    return _label(labels, _TENSE_LABEL_KEYS.get(dominant, dominant))


def _line_label(labels: Mapping[str, str] | None, p) -> str:
    """Localised line anchor, e.g. 'Z. 470–472' (de) / 'l. 470–472' (en)."""
    prefix = _label(labels, "line")
    if p.start_line == p.end_line:
        return f"{prefix} {p.start_line}"
    return f"{prefix} {p.start_line}–{p.end_line}"


def _help(labels: Mapping[str, str] | None, key: str, text: str) -> str:
    """Wraps a term with a tooltip (help text from the language profile)."""
    tip = _label(labels, f"help_{key}")
    if not tip or tip.startswith("help_"):
        tip = HELP_TEXTS["en"].get(f"help_{key}") or HELP_TEXTS["de"].get(f"help_{key}") or ""
    if not tip:
        return text
    return (
        f'<span class="help" data-help="{html.escape(tip, quote=True)}" tabindex="0">{text}</span>'
    )


def _kpi(value: str, label: str) -> str:
    return f'<div class="kpi"><b>{value}</b><span>{label}</span></div>'


def render_dashboard(
    chapters: Sequence[ChapterProfile],
    paragraphs: Sequence[ParagraphProfile],
    metrics: Any | None = None,
    fingerprint: Any | None = None,
    markers: Sequence[Any] | None = None,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    title: str = "Manuskript",
    labels: Mapping[str, str] | None = None,
    language_name: str = "",
    language_key: str = "generic",
    tense_available: bool = True,
    engine_name: str = "Lixity",
    controls: bool = False,
    api_base: str = "/api",
    manuscript_name: str = "",
    current_language: str = "auto",
    language_options: Sequence | None = None,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the local control panel (buttons/dropdown/NDA),
    which triggers the CLI functions via the UI server (``scripts/ui_server.py``).
    """
    esc = html.escape
    L = lambda key: esc(_label(labels, key))  # noqa: E731

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    def P(value: float, decimals: int = 1) -> str:
        return format_pct(value, language_key, decimals)

    html_lang = language_key if language_key not in ("auto", "generic") else "en"
    if not language_options:
        language_options = [
            ("auto", "auto"),
            ("de", "Deutsch"),
            ("en", "English"),
            ("fr", "Français"),
            ("es", "Español"),
            ("it", "Italiano"),
            ("pt", "Português"),
            ("nl", "Nederlands"),
            ("generic", "generic"),
        ]

    total_words = sum(c.words for c in chapters)
    total_flagged = sum(1 for p in paragraphs if p.severity >= 2)
    scale = max((p.words for p in paragraphs), default=1)
    function_pct = (
        round(sum(p.function_word_pct for p in paragraphs) / len(paragraphs), 1)
        if paragraphs
        else 0.0
    )
    has_house_style = bool(
        fingerprint is not None
        and any(float(base.get("sigma") or 0.0) > 0.0 for base in fingerprint.baseline.values())
    )

    parts = [
        "<!DOCTYPE html>",
        f'<html lang="{html_lang}">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        f"<title>{esc(title)} – {L('app_suffix')}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        f'<body id="top" data-api="{esc(api_base)}">',
        '<div class="page">',
        "<header>",
        f"<h1>{esc(title)}</h1>",
        f'<p class="sub">{L("app_suffix")}'
        + (f" · {esc(language_name)}" if language_name else "")
        + "</p>",
        f'<p class="hint">{L("hint")}</p>',
        "</header>",
    ]

    if controls:
        parts.append('<section class="panel controls" id="controls">')
        parts.append(f"<h2>{L('controls')}</h2>")

        # Load manuscript
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("manuscript")}</span>')
        parts.append('<div class="row">')
        parts.append('<input class="ctl" type="file" id="ms-file" accept=".md,.markdown,.txt"/>')
        parts.append(
            f'<button class="ctl" data-action="load" data-payload="load">{L("load")}</button>'
        )
        if manuscript_name:
            parts.append(
                f'<span class="ctl-note">{L("current_manuscript")}: {esc(manuscript_name)}</span>'
            )
        parts.append("</div>")
        parts.append(f'<p class="ctl-note">{L("load_hint")}</p>')
        parts.append("</div>")

        # Settings (language, title)
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("settings")}</span>')
        parts.append('<div class="row">')
        parts.append(
            f'<select class="ctl" id="set-language" aria-label="{L("language")}">'
            + "".join(
                f'<option value="{code}"{" selected" if code == current_language else ""}>{label}</option>'
                for code, label in language_options
            )
            + "</select>"
        )
        parts.append(
            f'<input class="ctl" id="set-title" value="{esc(title)}" placeholder="{L("title")}"/>'
        )
        parts.append(
            f'<button class="ctl" data-action="settings" data-payload="settings">{L("apply")}</button>'
        )
        parts.append("</div></div>")

        # Analyses & exports
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("export")} · {L("run_analysis")}</span>')
        parts.append('<div class="row">')
        parts.append(
            f'<select class="ctl" id="fmt" aria-label="{esc(_label(labels, "help_format"))}">'
            f'<option value="all">{L("format_all")}</option>'
            f'<option value="a4">A4</option>'
            f'<option value="taschenbuch">{L("format_paperback")}</option>'
            f'<option value="mobile">Mobile</option>'
            f'<option value="epub">EPUB</option>'
            "</select>"
        )
        parts.append(
            f'<button class="ctl primary" data-action="export" data-payload="format">'
            f"{_help(labels, 'export', L('export'))}</button>"
        )
        parts.append(
            f'<button class="ctl" data-action="analyze">{_help(labels, "rebuild", L("run_analysis"))}</button>'
        )
        for action in ("sync", "audit", "prune", "gdrive", "rebuild"):
            parts.append(
                f'<button class="ctl" data-action="{action}">{_help(labels, action, L(action))}</button>'
            )
        parts.append("</div></div>")

        # NDA
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{_help(labels, "nda", L("new_nda"))}</span>')
        parts.append('<div class="row">')
        parts.append(f'<input class="ctl" id="nda-name" placeholder="{L("name")}"/>')
        parts.append(f'<input class="ctl" id="nda-contact" placeholder="{L("contact")}"/>')
        parts.append(
            f'<button class="ctl" data-action="nda" data-payload="nda">{L("create")}</button>'
        )
        parts.append("</div></div>")

        parts.append(f'<div class="ctl-status" id="ctl-status">{L("server_hint")}</div>')
        parts.append("</section>")

        parts.append('<section class="panel controls" id="nda-manager">')
        parts.append(f"<h2>{L('nda_manager')}</h2>")
        parts.append(f'<p class="ctl-note" id="nda-hint">{L("locked_hint")}</p>')
        parts.append('<div class="row" id="nda-unlock-row">')
        parts.append(
            f'<input class="ctl" type="password" id="nda-passphrase" placeholder="{L("passphrase")}"/>'
        )
        parts.append(f'<button class="ctl" id="nda-unlock-btn">{L("unlock")}</button>')
        parts.append("</div>")
        parts.append('<div id="nda-table"></div>')
        parts.append('<div class="row" id="nda-add-row" hidden="hidden">')
        parts.append(f'<input class="ctl" id="nda-new-name" placeholder="{L("name")}"/>')
        parts.append(f'<input class="ctl" id="nda-new-contact" placeholder="{L("contact")}"/>')
        parts.append(f'<input class="ctl" id="nda-new-notes" placeholder="{L("notes")}"/>')
        parts.append(
            f'<button class="ctl primary" id="nda-add-btn">{L("create")} + {L("export_pdf")}</button>'
        )
        parts.append("</div>")
        parts.append('<div class="ctl-status" id="nda-status"></div>')
        parts.append("</section>")

    # --- Key metrics (grouped for scanability) ----------------------------
    scope_tiles = [
        _kpi(N(total_words, 0), _help(labels, "words", L("words_prose"))),
        _kpi(str(len(chapters)), L("chapter")),
        _kpi(str(len(paragraphs)), L("paragraphs")),
    ]
    rhythm_tiles: list[str] = []
    language_tiles: list[str] = []
    lexis_tiles: list[str] = []
    style_tiles: list[str] = []
    if metrics is not None:
        scope_tiles.append(_kpi(N(metrics.total_sentences, 0), L("sentences")))
        rhythm_tiles.append(_kpi(N(metrics.asl, 2), _help(labels, "asl", "ASL")))
        rhythm_tiles.append(
            _kpi(P(metrics.staccato_pct), _help(labels, "staccato", L("feat_staccato")))
        )
        language_tiles.append(
            _kpi(P(metrics.dialog_ratio), _help(labels, "dialogue", L("dialogue")))
        )
        language_tiles.append(_kpi(N(metrics.flesch_de, 1), _help(labels, "flesch", "Flesch")))
        language_tiles.append(_kpi(N(metrics.lix, 1), _help(labels, "lix", "LIX")))
        lexis_tiles.append(_kpi(N(metrics.ttr, 4), _help(labels, "ttr", "TTR")))
        lexis_tiles.append(_kpi(N(metrics.guiraud_r, 2), _help(labels, "guiraud", "Guiraud R")))
        lexis_tiles.append(_kpi(N(metrics.yules_k, 1), _help(labels, "yules", "Yule&#8217;s K")))
        hd_d_value = N(metrics.hd_d, 3) if getattr(metrics, "hd_d", None) is not None else "–"
        lexis_tiles.append(_kpi(hd_d_value, _help(labels, "hd_d", "HD-D")))
        mtld_value = N(metrics.mtld, 1) if getattr(metrics, "mtld", None) is not None else "–"
        lexis_tiles.append(_kpi(mtld_value, _help(labels, "mtld", "MTLD")))
        mattr_value = N(metrics.mattr, 3) if getattr(metrics, "mattr", None) is not None else "–"
        lexis_tiles.append(_kpi(mattr_value, _help(labels, "mattr", "MATTR")))
        maas_value = N(metrics.maas_a2, 3) if getattr(metrics, "maas_a2", None) is not None else "–"
        lexis_tiles.append(_kpi(maas_value, _help(labels, "maas", "Maas a²")))
        language_tiles.append(
            _kpi(
                P(metrics.first_person_start_rate),
                _help(labels, "first_start", L("feat_ich_start")),
            )
        )
    language_tiles.append(
        _kpi(P(function_pct), _help(labels, "function_words", L("function_words")))
    )
    if fingerprint is not None:
        style_tiles.append(
            _kpi(
                P(fingerprint.consistency * 100, 0),
                _help(labels, "consistency", L("consistency")),
            )
        )
        drifters = fingerprint.top_deviants(1)
        if drifters:
            num, mean_abs = drifters[0]
            style_tiles.append(
                _kpi(
                    f"Ø {N(mean_abs, 1)}",
                    _help(labels, "fingerprint", f"{L('deviation')} · {L('chapter')} {num}"),
                )
            )
    style_tiles.append(_kpi(str(total_flagged), _help(labels, "flagged", L("flagged"))))

    parts.append('<section class="kpis">')
    for caption_key, tiles in (
        ("group_scope", scope_tiles),
        ("group_rhythm", rhythm_tiles),
        ("group_language", language_tiles),
        ("group_lexis", lexis_tiles),
        ("group_style", style_tiles),
    ):
        if not tiles:
            continue
        parts.append('<div class="kpi-group">')
        parts.append(f'<div class="kpi-caption">{L(caption_key)}</div>')
        parts.append('<div class="kpi-row">')
        parts.extend(tiles)
        parts.append("</div></div>")
    parts.append("</section>")

    # --- Sentence-length architecture -------------------------------------
    if metrics is not None:
        d = metrics.sentence_dist
        rows = [
            ("≤ 6", d.short_count, d.short_pct),
            ("7–15", d.medium_count, d.medium_pct),
            ("16–25", d.long_count, d.long_pct),
            ("> 25", d.complex_count, d.complex_pct),
        ]
        parts.append('<section class="panel">')
        parts.append(f"<h2>{L('sentence_dist')}</h2>")
        parts.append('<div class="dist">')
        for criterion, count, pct in rows:
            parts.append(
                f'<div class="row"><span>{criterion}</span>'
                f'<span class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></span>'
                f'<span class="val">{N(count, 0)} · {P(pct)}</span></div>'
            )
        parts.append("</div></section>")

    # --- Style heatmap & passport (self-calibrated house style) -----------
    if has_house_style and fingerprint is not None and metrics is not None and metrics.chapters:
        feature_layers = {field: key for key, field in LAYER_FEATURES.items()}
        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'heatmap', L('style_fingerprint'))}</h2>")
        parts.append('<p class="hint">' + esc(_label(labels, "help_heatmap")) + "</p>")
        parts.append(
            '<div class="z-legend">'
            + esc(_label(labels, "zscore"))
            + f' <span class="z-gradient"></span> −{N(2.5, 1)} … +{N(2.5, 1)}'
            + f' <span class="z-click-hint">{esc(_label(labels, "heatmap_click"))}</span></div>'
        )
        parts.append('<div class="heatmap-wrap"><table class="heatmap"><thead><tr>')
        parts.append(f'<th class="ch">{L("chapter")}</th>')
        for _field, label_key, _unit in FEATURES:
            parts.append(
                f"<th>{_help(labels, _FEATURE_HELP.get(_field, _field), esc(_label(labels, label_key)))}</th>"
            )
        parts.append("</tr></thead><tbody>")
        for chapter in metrics.chapters:
            if chapter.num not in fingerprint.z_scores:
                continue
            parts.append(f'<tr><td class="ch">{chapter.num}. {esc(chapter.title)}</td>')
            for field_name, label_key, _unit in FEATURES:
                z = fingerprint.z_scores[chapter.num].get(field_name)
                if z is None:
                    parts.append('<td class="z">–</td>')
                    continue
                raw = fingerprint.values[field_name].get(chapter.num)
                raw_text = N(raw, 2) if isinstance(raw, float) else str(raw)
                effect = fingerprint.effect_sizes[chapter.num].get(field_name, 0.0)
                tooltip = (
                    f"{_label(labels, label_key)}: {raw_text} · "
                    f"z* {N(z, 1, signed=True)} · "
                    f"{_label(labels, 'effect_size')} {N(effect, 1, signed=True)}\u03c3"
                )
                layer_key = feature_layers.get(field_name, "")
                cell_attrs = (
                    f' data-chapter="{chapter.num}" data-layer="{layer_key}"'
                    f' tabindex="0" role="button"'
                )
                if abs(z) < 0.05:
                    parts.append(
                        f'<td class="z zero"{cell_attrs} title="{esc(tooltip, quote=True)}">0</td>'
                    )
                else:
                    parts.append(
                        f'<td class="z" style="background:{z_color(z)}"{cell_attrs} '
                        f'title="{esc(tooltip, quote=True)}">{N(z, 1, signed=True)}</td>'
                    )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
        fdr_total = sum(len(v) for v in fingerprint.fdr_flagged.values())
        parts.append(
            f'<p class="hint">{_help(labels, "expected_false_positives", L("expected_false_positives"))}: '
            f"~{N(fingerprint.expected_false_positives, 1)} · "
            f"{_help(labels, 'fdr', L('fdr_flagged'))}: {fdr_total}</p>"
        )
        parts.append("</section>")

        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'passport', L('style_passport'))}</h2>")
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th>{L("metrics")}</th><th class="num">{L("median")}</th>'
            f'<th class="num">{L("band")} (±2σ)</th><th class="num">{L("outliers")}</th>'
        )
        parts.append("</tr></thead><tbody>")
        for field_name, label_key, _unit in FEATURES:
            base = fingerprint.baseline.get(field_name, {})
            if not base.get("n"):
                continue
            centre = float(base["median"])
            sigma = float(base["sigma"])
            band_text = f"{N(centre - 2 * sigma, 2)} … {N(centre + 2 * sigma, 2)}"
            n_out = sum(1 for cells in fingerprint.deviations.values() if field_name in cells)
            outlier_text = str(n_out) if n_out else "–"
            parts.append(
                f"<tr><td>{_help(labels, _FEATURE_HELP.get(field_name, field_name), esc(_label(labels, label_key)))}</td>"
                f'<td class="num">{N(centre, 2)}</td>'
                f'<td class="num">{esc(band_text)}</td>'
                f'<td class="num">{outlier_text}</td></tr>'
            )
        parts.append("</tbody></table></section>")

        # --- Style dimensions (self-calibrated principal axes) -------------
        if fingerprint.dimensions:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{_help(labels, 'dimensions', L('style_dimensions'))}</h2>")
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            for dim in fingerprint.dimensions:
                loadings: dict[str, float] = dim["loadings"]
                top_pos = sorted(loadings.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_neg = sorted(loadings.items(), key=lambda kv: kv[1])[:3]
                pos_text = " · ".join(
                    f"{esc(_label(labels, field_labels.get(f, f)))} {N(v, 2, signed=True)}"
                    for f, v in top_pos
                )
                neg_text = " · ".join(
                    f"{esc(_label(labels, field_labels.get(f, f)))} {N(v, 2, signed=True)}"
                    for f, v in top_neg
                )
                flagged = dim.get("flagged", [])
                parts.append('<div class="dim-card">')
                parts.append(
                    f'<div class="dim-header"><span class="dim-title">{L("style_dimensions")} {dim["index"]}</span>'
                    f'<span class="badge">{P(dim["variance"] * 100, 0)} {L("dim_variance")}</span></div>'
                )
                parts.append(
                    f'<div class="dim-loadings"><b>{L("dim_loadings_pos")}:</b> {pos_text}<br/>'
                    f"<b>{L('dim_loadings_neg')}:</b> {neg_text}</div>"
                )
                if flagged:
                    ch_label = L("chapter")
                    flagged_str = ", ".join(f"{ch_label} {ch}" for ch in flagged)
                    parts.append(f'<div class="dim-meta">{L("dim_flagged")}: {flagged_str}</div>')
                parts.append("</div>")
            parts.append("</section>")

        # --- Work markers (editor-visible, set from the dashboard) -------
        if markers is not None:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{_help(labels, 'markers', L('markers'))}</h2>")
            if markers:
                parts.append("<table><thead><tr>")
                parts.append(
                    f'<th>{L("status")}</th><th class="num">{L("line")}</th><th>{L("notes")}</th>'
                )
                if controls:
                    parts.append("<th></th>")
                parts.append("</tr></thead><tbody>")
                for m in markers:
                    kind_label = _label(labels, "marker_" + m.kind)
                    note = esc(str(m.note or "")) or "–"
                    parts.append(
                        f'<tr><td><span class="badge marker-{m.kind}">{esc(kind_label)}</span></td>'
                        f'<td class="num">{L("line")} {m.line}</td><td>{note}</td>'
                    )
                    if controls:
                        parts.append(
                            f'<td><button class="ctl" data-marker-resolve="{esc(m.id, quote=True)}">'
                            f"{L('marker_resolve')}</button></td>"
                        )
                    parts.append("</tr>")
                parts.append("</tbody></table>")
            else:
                parts.append(f'<p class="hint">{L("markers_empty")}</p>')
            parts.append("</section>")

        # --- Toolbar ----------------------------------------------------------
    parts.append('<div class="toolbar">')
    parts.append(f'<label><input type="checkbox" id="filter-flags"/> {L("filter_flags")}</label>')
    if paragraphs:
        parts.append("<label>")
        parts.append(f"{_help(labels, 'layer', L('style_layer'))} ")
        parts.append('<select class="ctl" id="style-layer">')
        parts.append(f'<option value="">{L("layer_off")}</option>')
        for layer_key in LAYER_FEATURES:
            parts.append(
                f'<option value="{layer_key}" '
                f'data-hint="{esc(_label(labels, "layer_hint_" + layer_key), quote=True)}">'
                f"{esc(_label(labels, 'layer_' + layer_key))}</option>"
            )
        parts.append("</select></label>")
    parts.append('<span class="legend">')
    for key, color in (
        ("present", "var(--present)"),
        ("past", "var(--past)"),
        ("mixed", "var(--mixed)"),
        ("neutral", "var(--neutral)"),
    ):
        parts.append(
            f'<span><span class="swatch" style="background:{color}"></span>{L(key)}</span>'
        )
    parts.append(
        f'<span><span class="swatch" style="background:var(--flag)"></span>'
        f"{L('severity_2')} / {L('severity_3')}</span>"
    )
    parts.append("</span>")
    parts.append(f'<a class="totop" href="#top">↑ {L("top")}</a>')
    parts.append("</div>")

    parts.append('<div class="layer-legend" id="layer-legend" hidden="hidden">')
    parts.append('<span class="layer-title" id="layer-legend-title"></span>')
    parts.append('<span class="z-gradient"></span>')
    parts.append(
        f'<span class="layer-scale">{esc(_label(labels, "layer_below"))} · '
        f"{esc(_label(labels, 'layer_scale_mean'))} · "
        f"{esc(_label(labels, 'layer_above'))}</span>"
    )
    parts.append('<span class="layer-hint" id="layer-legend-hint"></span>')
    parts.append("</div>")

    if not tense_available:
        parts.append(f'<p class="hint">{L("no_tense")}</p>')

    # --- Chapter map ------------------------------------------------------
    by_chapter: dict = {}
    for idx, p in enumerate(paragraphs):
        by_chapter.setdefault(p.chapter_num, []).append((idx, p))

    layer_data: dict[str, dict[int, tuple[float, float]]] = {
        layer_key: layer_stats(paragraphs, layer_key) for layer_key in LAYER_FEATURES
    }

    def _layer_tip(key: str, value: float, z: float) -> str:
        if key == "asl":
            text = f"ASL {N(value, 1)}"
        elif key in ("dialogue", "function"):
            label = _label(labels, "dialogue" if key == "dialogue" else "function_words")
            text = f"{label} {P(value)}"
        else:
            text = f"{_label(labels, 'feat_' + key)} {N(value, 1)}"
        direction = _label(labels, "layer_above" if z > 0 else "layer_below")
        return f"{text} · {direction}"

    parts.append("<main>")
    for chapter in chapters:
        chapter_paras = by_chapter.get(chapter.num, [])
        has_flags = any(p.severity >= 2 for _, p in chapter_paras)
        classes = "chapter has-flags" if has_flags else "chapter"
        parts.append(f'<section class="{classes}" id="ch-{chapter.num}">')
        parts.append('<div class="chapter-head">')
        parts.append(f"<h2>{chapter.num}. {esc(chapter.title)}</h2>")
        parts.append(
            f'<span class="meta">{N(chapter.words, 0)} {L("words")} · '
            f"{chapter.paragraphs} {L('paragraphs')} · {esc(_tense_label(labels, chapter.dominant))} · "
            f"{chapter.flagged} {L('flagged')} · {L('line')} {chapter.start_line}–{chapter.end_line}</span>"
        )
        parts.append("</div>")

        if chapter_paras:
            parts.append('<div class="strip">')
            for idx, p in chapter_paras:
                sev = f" sev-{p.severity}" if p.severity >= 2 else ""
                width = max(1.0, p.words / scale * 100.0)
                dom_label = _tense_label(labels, p.dominant)
                sev_label = _label(labels, f"severity_{p.severity}")
                tooltip = (
                    f"{_line_label(labels, p)} · {dom_label} · "
                    f"{_label(labels, 'present')} {p.present_hits} / "
                    f"{_label(labels, 'past')} {p.past_hits} · {sev_label}"
                )
                layer_payload: dict[str, list[str]] = {}
                for key in LAYER_FEATURES:
                    info = layer_data.get(key, {}).get(idx)
                    if info is not None:
                        value, z = info
                        layer_payload[key] = [z_color(z), _layer_tip(key, value, z)]
                layer_attr = (
                    f" data-layers='{esc(json.dumps(layer_payload, ensure_ascii=False), quote=True)}'"
                    if layer_payload
                    else ""
                )
                parts.append(
                    f'<button class="chip {_tense_class(p.dominant)}{sev}" '
                    f'style="flex:{width:.2f} 0 auto" data-target="p-{idx}"{layer_attr} '
                    f'data-tip-base="{esc(tooltip, quote=True)}" '
                    f'title="{esc(tooltip)}" aria-label="{esc(tooltip)}" aria-expanded="false"></button>'
                )
            parts.append("</div>")

            for idx, p in chapter_paras:
                dom_label = _tense_label(labels, p.dominant)
                sev_label = _label(labels, f"severity_{p.severity}")
                parts.append(f'<div class="ptext" id="p-{idx}">')
                parts.append(
                    f'<div class="anchor">{_line_label(labels, p)} · '
                    f"{esc(dom_label)} · {esc(sev_label)}</div>"
                )
                parts.append(
                    f'<div class="stats">{L("present")} {p.present_hits} · {L("past")} {p.past_hits} · '
                    f"ASL {N(p.asl, 1)} · {L('dialogue')} {P(p.dialogue_pct)} · "
                    f"{L('function_words')} {P(p.function_word_pct)} · "
                    f"{L('feat_filter')} {N(p.filter_density, 1)} · {L('feat_modal')} {N(p.modal_density, 1)} · "
                    f"{L('feat_nominal')} {N(p.nominal_density, 1)} · {L('feat_passive')} {N(p.passive_density, 1)} · "
                    f"{p.words} {L('words')}</div>"
                )
                if controls:
                    buttons = " ".join(
                        f'<button class="ctl" data-marker-add="{esc(kind, quote=True)}" '
                        f'data-line="{p.start_line}">+ {esc(_label(labels, "marker_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(f'<div class="row">{buttons}</div>')
                parts.append(f"<p>{esc(p.text)}</p>")
                parts.append("</div>")
        parts.append("</section>")
    parts.append("</main>")

    # --- Chapter matrix ---------------------------------------------------
    if chapters:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{L('chapter_table')}</h2>")
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th>#</th><th>{L("chapter")}</th><th class="num">{L("words")}</th>'
            f'<th class="num">ASL</th><th class="num">{L("dialogue")}</th>'
            f'<th class="num">{L("function_words")}</th><th>{L("past")}/{L("present")}</th>'
            f'<th class="num">{L("flagged")}</th>'
        )
        if fingerprint is not None:
            parts.append(f'<th class="num">{L("deviation")}</th>')
        parts.append("</tr></thead><tbody>")
        for c in chapters:
            parts.append(
                f"<tr><td>{c.num}</td><td>{esc(c.title)}</td>"
                f'<td class="num">{N(c.words, 0)}</td><td class="num">{N(c.asl, 1)}</td>'
                f'<td class="num">{P(c.dialog_pct)}</td><td class="num">{P(c.function_word_pct)}</td>'
                f'<td>{esc(_tense_label(labels, c.dominant))}</td><td class="num">{c.flagged}</td>'
            )
            if fingerprint is not None:
                dev = fingerprint.deviations.get(c.num, {})
                if dev:
                    named = ", ".join(
                        f"{_label(labels, label_key)} {z:+.1f}σ"
                        for field_name, label_key, _unit in FEATURES
                        if (z := dev.get(field_name)) is not None
                    )
                    parts.append(
                        f'<td class="num" title="{esc(named, quote=True)}">{len(dev)}</td>'
                    )
                else:
                    parts.append('<td class="num">–</td>')
            parts.append("</tr>")
        parts.append("</tbody></table></section>")

    # --- Publications -----------------------------------------------------
    if artifacts:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{_help(labels, 'artifacts', L('artifacts'))}</h2>")
        parts.append('<div class="artifacts">')
        for art in artifacts:
            name = esc(str(art.get("name", "")))
            meta_bits = []
            if art.get("size_kb") is not None:
                meta_bits.append(f"{N(art['size_kb'], 0)} KB")
            if art.get("pages"):
                meta_bits.append(f"{art['pages']} {_label(labels, 'pages')}")
            meta = " · ".join(meta_bits)
            href = art.get("href")
            link = (
                f'<a href="{esc(str(href))}" target="_blank" rel="noopener">{L("open")}</a>'
                if href
                else ""
            )
            parts.append(
                f'<div class="artifact"><span class="name">{name}</span>'
                f'<span class="meta">{esc(meta)}</span>{link}</div>'
            )
        parts.append("</div></section>")

    parts.extend(
        [
            "</div>",
            f"<footer><span>{esc(engine_name)} · {L('app_suffix')}</span><span>{esc(title)}</span></footer>",
            f"<script>{_JS}</script>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts) + "\n"


# Backwards-compatible name (older calls/tests)
render_style_report = render_dashboard
