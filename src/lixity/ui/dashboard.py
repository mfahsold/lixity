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

from ..format import num as format_num
from ..format import pct as format_pct
from ..style_fingerprint import FEATURES, LAYER_FEATURES, layer_stats, z_color
from ..style_profile import (
    ChapterProfile,
    ParagraphProfile,
)
from .components import (
    band_chart,
    help_term,
    kpi,
    label,
    line_label,
    loading_bars,
    tense_class,
    tense_label,
)

_ASSET_DIR = _Path(__file__).with_name("assets")
_CSS = (_ASSET_DIR / "dashboard.css").read_text(encoding="utf-8")
_JS = (_ASSET_DIR / "dashboard.js").read_text(encoding="utf-8")


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
    L = lambda key: esc(label(labels, key))  # noqa: E731

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
        f'<p class="microhint" id="microhint">{L("hint")}</p>',
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
            f'<select class="ctl" id="fmt" aria-label="{esc(label(labels, "help_format"))}">'
            f'<option value="all">{L("format_all")}</option>'
            f'<option value="a4">A4</option>'
            f'<option value="taschenbuch">{L("format_paperback")}</option>'
            f'<option value="mobile">Mobile</option>'
            f'<option value="epub">EPUB</option>'
            "</select>"
        )
        parts.append(
            f'<button class="ctl primary" data-action="export" data-payload="format">'
            f"{help_term(labels, 'export', L('export'))}</button>"
        )
        parts.append(
            f'<button class="ctl" data-action="analyze">{help_term(labels, "rebuild", L("run_analysis"))}</button>'
        )
        for action in ("sync", "audit", "prune", "gdrive", "rebuild"):
            parts.append(
                f'<button class="ctl" data-action="{action}">{help_term(labels, action, L(action))}</button>'
            )
        parts.append("</div></div>")

        # NDA
        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{help_term(labels, "nda", L("new_nda"))}</span>')
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
        kpi(N(total_words, 0), help_term(labels, "words", L("words_prose"))),
        kpi(str(len(chapters)), L("chapter")),
        kpi(str(len(paragraphs)), L("paragraphs")),
    ]
    rhythm_tiles: list[str] = []
    language_tiles: list[str] = []
    lexis_tiles: list[str] = []
    style_tiles: list[str] = []
    if metrics is not None:
        scope_tiles.append(kpi(N(metrics.total_sentences, 0), L("sentences")))
        rhythm_tiles.append(kpi(N(metrics.asl, 2), help_term(labels, "asl", "ASL")))
        rhythm_tiles.append(
            kpi(
                P(metrics.staccato_pct),
                help_term(labels, "staccato", L("feat_staccato")),
                bar=metrics.staccato_pct,
            )
        )
        language_tiles.append(
            kpi(
                P(metrics.dialog_ratio),
                help_term(labels, "dialogue", L("dialogue")),
                bar=metrics.dialog_ratio,
            )
        )
        language_tiles.append(kpi(N(metrics.flesch_de, 1), help_term(labels, "flesch", "Flesch")))
        language_tiles.append(kpi(N(metrics.lix, 1), help_term(labels, "lix", "LIX")))
        lexis_tiles.append(kpi(N(metrics.ttr, 4), help_term(labels, "ttr", "TTR")))
        lexis_tiles.append(kpi(N(metrics.guiraud_r, 2), help_term(labels, "guiraud", "Guiraud R")))
        lexis_tiles.append(kpi(N(metrics.yules_k, 1), help_term(labels, "yules", "Yule&#8217;s K")))
        hd_d_value = N(metrics.hd_d, 3) if getattr(metrics, "hd_d", None) is not None else "–"
        lexis_tiles.append(kpi(hd_d_value, help_term(labels, "hd_d", "HD-D")))
        mtld_value = N(metrics.mtld, 1) if getattr(metrics, "mtld", None) is not None else "–"
        lexis_tiles.append(kpi(mtld_value, help_term(labels, "mtld", "MTLD")))
        mattr_value = N(metrics.mattr, 3) if getattr(metrics, "mattr", None) is not None else "–"
        lexis_tiles.append(kpi(mattr_value, help_term(labels, "mattr", "MATTR")))
        maas_value = N(metrics.maas_a2, 3) if getattr(metrics, "maas_a2", None) is not None else "–"
        lexis_tiles.append(kpi(maas_value, help_term(labels, "maas", "Maas a²")))
        language_tiles.append(
            kpi(
                P(metrics.first_person_start_rate),
                help_term(labels, "first_start", L("feat_ich_start")),
                bar=metrics.first_person_start_rate,
            )
        )
    language_tiles.append(
        kpi(
            P(function_pct),
            help_term(labels, "function_words", L("function_words")),
            bar=function_pct,
        )
    )
    if fingerprint is not None:
        style_tiles.append(
            kpi(
                P(fingerprint.consistency * 100, 0),
                help_term(labels, "consistency", L("consistency")),
                bar=fingerprint.consistency * 100,
            )
        )
        drifters = fingerprint.top_deviants(1)
        if drifters:
            num, mean_abs = drifters[0]
            style_tiles.append(
                kpi(
                    f"Ø {N(mean_abs, 1)}",
                    help_term(labels, "fingerprint", f"{L('deviation')} · {L('chapter')} {num}"),
                )
            )
    style_tiles.append(kpi(str(total_flagged), help_term(labels, "flagged", L("flagged"))))

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
        parts.append(f"<h2>{help_term(labels, 'heatmap', L('style_fingerprint'))}</h2>")
        parts.append(
            '<div class="z-legend">'
            + esc(label(labels, "zscore"))
            + f' <span class="z-gradient"></span> −{N(2.5, 1)} … +{N(2.5, 1)}'
            + "</div>"
        )
        parts.append('<div class="heatmap-wrap"><table class="heatmap"><thead><tr>')
        parts.append(f'<th class="ch">{L("chapter")}</th>')
        for _field, label_key, _unit in FEATURES:
            parts.append(
                f"<th>{help_term(labels, _FEATURE_HELP.get(_field, _field), esc(label(labels, label_key)))}</th>"
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
                    f"{label(labels, label_key)}: {raw_text} · "
                    f"z* {N(z, 1, signed=True)} · "
                    f"{label(labels, 'effect_size')} {N(effect, 1, signed=True)}\u03c3 · "
                    f"{label(labels, 'click_hint')}"
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
            f'<p class="hint">{help_term(labels, "expected_false_positives", L("expected_false_positives"))}: '
            f"~{N(fingerprint.expected_false_positives, 1)} · "
            f"{help_term(labels, 'fdr', L('fdr_flagged'))}: {fdr_total}</p>"
        )
        parts.append("</section>")

        parts.append('<section class="panel">')
        parts.append(f"<h2>{help_term(labels, 'passport', L('style_passport'))}</h2>")
        parts.append('<div class="bands">')
        for field_name, label_key, _unit in FEATURES:
            base = fingerprint.baseline.get(field_name, {})
            if not base.get("n"):
                continue
            centre = float(base["median"])
            sigma = float(base["sigma"])
            series = fingerprint.values.get(field_name, {})
            values = [float(v) for v in series.values() if v is not None]
            outliers = [
                float(v)
                for ch, v in series.items()
                if v is not None and field_name in fingerprint.deviations.get(ch, {})
            ]
            n_out = len(outliers)
            title = (
                f"{label(labels, label_key)}: {L('median')} {N(centre, 2)} · "
                f"{L('band')} {N(centre - 2 * sigma, 2)} – {N(centre + 2 * sigma, 2)} · "
                f"{L('outliers')}: {n_out}"
            )
            parts.append('<div class="band-row">')
            parts.append(
                f'<span class="band-label">{help_term(labels, _FEATURE_HELP.get(field_name, field_name), esc(label(labels, label_key)))}</span>'
            )
            parts.append(
                band_chart(title, centre - 2 * sigma, centre + 2 * sigma, centre, values, outliers)
            )
            parts.append(f'<span class="band-count">{n_out if n_out else ""}</span>')
            parts.append("</div>")
        parts.append("</div></section>")

        # --- Style dimensions (self-calibrated principal axes) -------------
        if fingerprint.dimensions:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{help_term(labels, 'dimensions', L('style_dimensions'))}</h2>")
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            for dim in fingerprint.dimensions:
                loadings: dict[str, float] = dim["loadings"]
                top_pos = sorted(loadings.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_neg = sorted(loadings.items(), key=lambda kv: kv[1])[:3]
                entries = [
                    (label(labels, field_labels.get(f, f)), float(v)) for f, v in top_pos + top_neg
                ]
                limit = max((abs(v) for _f, v in entries), default=1.0)
                flagged = dim.get("flagged", [])
                parts.append('<div class="dim-card">')
                parts.append(
                    f'<div class="dim-header"><span class="dim-title">{L("style_dimensions")} {dim["index"]}</span>'
                    f'<span class="badge">{P(dim["variance"] * 100, 0)} {L("dim_variance")}</span></div>'
                )
                parts.append(loading_bars(entries, limit))
                if flagged:
                    ch_label = L("chapter")
                    flagged_str = ", ".join(f"{ch_label} {ch}" for ch in flagged)
                    parts.append(f'<div class="dim-meta">{L("dim_flagged")}: {flagged_str}</div>')
                parts.append("</div>")
            parts.append("</section>")

        # --- Work markers (editor-visible, set from the dashboard) -------
        if markers is not None:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{help_term(labels, 'markers', L('markers'))}</h2>")
            if markers:
                parts.append("<table><thead><tr>")
                parts.append(
                    f'<th>{L("status")}</th><th class="num">{L("line")}</th><th>{L("notes")}</th>'
                )
                if controls:
                    parts.append("<th></th>")
                parts.append("</tr></thead><tbody>")
                for m in markers:
                    kind_label = label(labels, "marker_" + m.kind)
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
        parts.append(f"{help_term(labels, 'layer', L('style_layer'))} ")
        parts.append('<select class="ctl" id="style-layer">')
        parts.append(f'<option value="">{L("layer_off")}</option>')
        for layer_key in LAYER_FEATURES:
            parts.append(
                f'<option value="{layer_key}" '
                f'data-hint="{esc(label(labels, "layer_hint_" + layer_key), quote=True)}">'
                f"{esc(label(labels, 'layer_' + layer_key))}</option>"
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
        f'<span class="layer-scale">{esc(label(labels, "layer_below"))} · '
        f"{esc(label(labels, 'layer_scale_mean'))} · "
        f"{esc(label(labels, 'layer_above'))}</span>"
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
            text_label = label(labels, "dialogue" if key == "dialogue" else "function_words")
            text = f"{text_label} {P(value)}"
        else:
            text = f"{label(labels, 'feat_' + key)} {N(value, 1)}"
        direction = label(labels, "layer_above" if z > 0 else "layer_below")
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
            f"{chapter.paragraphs} {L('paragraphs')} · {esc(tense_label(labels, chapter.dominant))} · "
            f"{chapter.flagged} {L('flagged')} · {L('line')} {chapter.start_line}–{chapter.end_line}</span>"
        )
        parts.append("</div>")

        if chapter_paras:
            parts.append('<div class="strip">')
            for idx, p in chapter_paras:
                sev = f" sev-{p.severity}" if p.severity >= 2 else ""
                width = max(1.0, p.words / scale * 100.0)
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                tooltip = (
                    f"{line_label(labels, p)} · {dom_label} · "
                    f"{label(labels, 'present')} {p.present_hits} / "
                    f"{label(labels, 'past')} {p.past_hits} · {sev_label}"
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
                    f'<button class="chip {tense_class(p.dominant)}{sev}" '
                    f'style="flex:{width:.2f} 0 auto" data-target="p-{idx}"{layer_attr} '
                    f'data-tip-base="{esc(tooltip, quote=True)}" '
                    f'title="{esc(tooltip)}" aria-label="{esc(tooltip)}" aria-expanded="false"></button>'
                )
            parts.append("</div>")

            for idx, p in chapter_paras:
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                parts.append(f'<div class="ptext" id="p-{idx}"><div class="ptext-inner">')
                parts.append(
                    f'<div class="anchor">{line_label(labels, p)} · '
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
                        f'data-line="{p.start_line}">+ {esc(label(labels, "marker_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(f'<div class="row">{buttons}</div>')
                parts.append(f"<p>{esc(p.text)}</p>")
                parts.append("</div></div>")
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
        max_asl = max((c.asl for c in chapters), default=1.0) or 1.0
        max_dialog = max((c.dialog_pct for c in chapters), default=1.0) or 1.0
        for c in chapters:
            parts.append(
                f"<tr><td>{c.num}</td><td>{esc(c.title)}</td>"
                f'<td class="num">{N(c.words, 0)}</td>'
                f'<td class="num bar-cell"><i style="--v:{c.asl / max_asl * 100:.0f}%"></i>'
                f"{N(c.asl, 1)}</td>"
                f'<td class="num bar-cell"><i style="--v:{c.dialog_pct / max_dialog * 100:.0f}%"></i>'
                f"{P(c.dialog_pct)}</td>"
                f'<td class="num">{P(c.function_word_pct)}</td>'
                f'<td>{esc(tense_label(labels, c.dominant))}</td><td class="num">{c.flagged}</td>'
            )
            if fingerprint is not None:
                dev = fingerprint.deviations.get(c.num, {})
                if dev:
                    named = ", ".join(
                        f"{label(labels, label_key)} {z:+.1f}σ"
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
        parts.append(f"<h2>{help_term(labels, 'artifacts', L('artifacts'))}</h2>")
        parts.append('<div class="artifacts">')
        for art in artifacts:
            name = esc(str(art.get("name", "")))
            meta_bits = []
            if art.get("size_kb") is not None:
                meta_bits.append(f"{N(art['size_kb'], 0)} KB")
            if art.get("pages"):
                meta_bits.append(f"{art['pages']} {label(labels, 'pages')}")
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
