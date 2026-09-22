"""lixity.ui.dashboard – Minimalist, self-contained single-file HTML dashboard.

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
    flagged_paragraphs,
)
from .components import (
    band_chart,
    help_term,
    kpi,
    label,
    line_label,
    loading_bars,
    status_strip,
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
    status: Sequence[Mapping[str, Any]] | None = None,
    dialogue: Mapping[str, Any] | None = None,
    characters: Mapping[str, Any] | None = None,
    pacing: Mapping[str, Any] | None = None,
    motifs: Mapping[str, Any] | None = None,
    showing: Mapping[str, Any] | None = None,
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
    language_options: Sequence[Any] | None = None,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the local control panel (buttons/dropdown/NDA),
    which triggers the CLI functions via the UI server (``scripts/ui_server.py``).
    ``dialogue``/``characters``/``pacing``/``motifs``/``showing`` add the
    optional dialogue-structure, character-presence, pacing, motif/repetition
    and showing/telling panels (see the corresponding modules).
    """
    esc = html.escape

    def L(key: str) -> str:
        return esc(label(labels, key))

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
    total_flagged = sum(1 for p in paragraphs if p.is_flagged)
    scale = max((p.words for p in paragraphs), default=1)
    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}

    function_pct = (
        round(sum(p.function_word_pct for p in paragraphs) / len(paragraphs), 1)
        if paragraphs
        else 0.0
    )
    has_house_style = bool(
        fingerprint is not None
        and any(float(base.get("sigma") or 0.0) > 0.0 for base in fingerprint.baseline.values())
    )

    layer_data: dict[str, dict[int, tuple[float, float]]] = {
        layer_key: layer_stats(paragraphs, layer_key) for layer_key in LAYER_FEATURES
    }

    def _layer_text(key: str, value: float) -> str:
        if key == "asl":
            return f"ASL {N(value, 1)}"
        if key in ("dialogue", "function"):
            text_label = label(labels, "dialogue" if key == "dialogue" else "function_words")
            return f"{text_label} {P(value)}"
        return f"{label(labels, 'feat_' + key)} {N(value, 1)}"

    def _layer_range(key: str) -> tuple[float, float]:
        values = [value for value, _z in layer_data.get(key, {}).values()]
        return (min(values), max(values)) if values else (0.0, 1.0)

    def _layer_tip(key: str, value: float, z: float) -> str:
        direction = label(labels, "layer_above" if z > 0 else "layer_below")
        return f"{_layer_text(key, value)} · {direction}"

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

    if status:
        parts.append(status_strip(labels, status))

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
        parts.extend(
            f'<button class="ctl" data-action="{action}">{help_term(labels, action, L(action))}</button>'
            for action in ("sync", "audit", "prune", "gdrive", "rebuild")
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
        kpi(N(total_words, 0), help_term(labels, "words", L("words_prose")), jump="#matrix"),
        kpi(str(len(chapters)), L("chapter"), jump="#matrix"),
        kpi(str(len(paragraphs)), L("paragraphs"), jump="#matrix"),
    ]
    rhythm_tiles: list[str] = []
    language_tiles: list[str] = []
    lexis_tiles: list[str] = []
    style_tiles: list[str] = []
    if metrics is not None:
        scope_tiles.append(kpi(N(metrics.total_sentences, 0), L("sentences"), jump="#matrix"))
        rhythm_tiles.append(kpi(N(metrics.asl, 2), help_term(labels, "asl", "ASL"), jump="#dist"))
        rhythm_tiles.append(
            kpi(
                P(metrics.staccato_pct),
                help_term(labels, "staccato", L("feat_staccato")),
                bar=metrics.staccato_pct,
                jump="#dist",
            )
        )
        language_tiles.append(
            kpi(
                P(metrics.dialog_ratio),
                help_term(labels, "dialogue", L("dialogue")),
                bar=metrics.dialog_ratio,
                jump="#chapters",
                layer="dialogue",
            )
        )
        language_tiles.append(
            kpi(N(metrics.flesch_de, 1), help_term(labels, "flesch", "Flesch"), jump="#bands")
        )
        language_tiles.append(
            kpi(N(metrics.lix, 1), help_term(labels, "lix", "LIX"), jump="#bands")
        )
        lexis_tiles.append(kpi(N(metrics.ttr, 4), help_term(labels, "ttr", "TTR"), jump="#bands"))
        lexis_tiles.append(
            kpi(N(metrics.guiraud_r, 2), help_term(labels, "guiraud", "Guiraud R"), jump="#bands")
        )
        lexis_tiles.append(
            kpi(N(metrics.yules_k, 1), help_term(labels, "yules", "Yule&#8217;s K"), jump="#bands")
        )
        hd_d_value = N(metrics.hd_d, 3) if getattr(metrics, "hd_d", None) is not None else "–"
        lexis_tiles.append(kpi(hd_d_value, help_term(labels, "hd_d", "HD-D"), jump="#bands"))
        mtld_value = N(metrics.mtld, 1) if getattr(metrics, "mtld", None) is not None else "–"
        lexis_tiles.append(kpi(mtld_value, help_term(labels, "mtld", "MTLD"), jump="#bands"))
        mattr_value = N(metrics.mattr, 3) if getattr(metrics, "mattr", None) is not None else "–"
        lexis_tiles.append(kpi(mattr_value, help_term(labels, "mattr", "MATTR"), jump="#bands"))
        maas_value = N(metrics.maas_a2, 3) if getattr(metrics, "maas_a2", None) is not None else "–"
        lexis_tiles.append(kpi(maas_value, help_term(labels, "maas", "Maas a²"), jump="#bands"))
        language_tiles.append(
            kpi(
                P(metrics.first_person_start_rate),
                help_term(labels, "first_start", L("feat_ich_start")),
                bar=metrics.first_person_start_rate,
                jump="#heatmap",
            )
        )
    language_tiles.append(
        kpi(
            P(function_pct),
            help_term(labels, "function_words", L("function_words")),
            bar=function_pct,
            jump="#chapters",
            layer="function",
        )
    )
    if fingerprint is not None:
        style_tiles.append(
            kpi(
                P(fingerprint.consistency * 100, 0),
                help_term(labels, "consistency", L("consistency")),
                bar=fingerprint.consistency * 100,
                jump="#heatmap",
            )
        )
        drifters = fingerprint.top_deviants(1)
        if drifters:
            num, mean_abs = drifters[0]
            devs = fingerprint.deviations.get(num, {})
            top_field = max(devs, key=lambda k: abs(devs[k])) if devs else None
            top_layer = feature_layers.get(top_field) if top_field else None
            top_chapter = next((c for c in chapters if c.num == num), None)
            top_title = top_chapter.title if top_chapter is not None else ""
            style_tiles.append(
                kpi(
                    f"Ø {N(mean_abs, 1)}",
                    help_term(
                        labels,
                        "fingerprint",
                        f"{L('deviation')} · {L('chapter')} {num}"
                        + (f" · {esc(top_title)}" if top_title else ""),
                    ),
                    jump=f"#ch-{num}",
                    layer=top_layer,
                    only=bool(devs),
                )
            )
    style_tiles.append(
        kpi(
            str(total_flagged),
            help_term(labels, "flagged", L("flagged")),
            jump="#flags",
            flags=True,
        )
    )

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

    # --- Flagged passages (list → paragraph → marker) ----------------------
    flagged = flagged_paragraphs(list(paragraphs))
    parts.append('<section class="panel" id="flags">')
    parts.append(f"<h2>{help_term(labels, 'flagged', label(labels, 'panel_flags'))}</h2>")
    if flagged:
        para_index = {id(p): i for i, p in enumerate(paragraphs)}
        parts.append('<div class="table-wrap flags-wrap">')
        parts.append("<table><thead><tr>")
        parts.append(
            f"<th>{label(labels, 'flags_stage')}</th>"
            f"<th>{L('chapter')}</th>"
            f'<th class="num">{L("line")}</th>'
            f"<th>{label(labels, 'flags_excerpt')}</th>"
        )
        if controls:
            parts.append("<th></th>")
        parts.append("</tr></thead><tbody>")
        for p in flagged:
            idx = para_index[id(p)]
            excerpt = " ".join(p.text.split())
            if len(excerpt) > 140:
                excerpt = excerpt[:137].rstrip() + "…"
            chapter_cell = (
                f"{L('chapter')} {p.chapter_num} · {esc(p.chapter_title)}"
                if p.chapter_title
                else f"{L('chapter')} {p.chapter_num}"
            )
            parts.append(
                f'<tr class="row-link flag-row" data-line="{p.start_line}" '
                f'data-target="p-{idx}" data-flags="1" role="button" tabindex="0" '
                f'title="{esc(label(labels, "click_hint_para"), quote=True)}">'
                f'<td><span class="badge sev-{p.severity}">'
                f"{esc(label(labels, f'severity_{p.severity}'))}</span></td>"
                f"<td>{chapter_cell}</td>"
                f'<td class="num">{esc(line_label(labels, p))}</td>'
                f'<td class="flag-excerpt">{esc(excerpt)}</td>'
            )
            if controls:
                parts.append(
                    f'<td class="flag-actions"><div class="row marker-row">'
                    f'<button class="ctl" data-marker-kind="todo" '
                    f'data-line="{p.start_line}">+ '
                    f"{esc(label(labels, 'marker_todo'))}</button>"
                    f'<span class="marker-note-slot" data-placeholder="'
                    f'{esc(label(labels, "marker_note"), quote=True)}"></span>'
                    f"</div></td>"
                )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
    else:
        parts.append(f'<p class="hint">{label(labels, "flags_empty")}</p>')
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
        parts.append('<section class="panel" id="dist">')
        parts.append(f"<h2>{L('sentence_dist')}</h2>")
        parts.append('<div class="dist">')
        for criterion, count, pct in rows:
            parts.append(
                f'<div class="row"><span>{criterion}</span>'
                f'<span class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></span>'
                f'<span class="val">{N(count, 0)} · {P(pct)}</span></div>'
            )
        parts.append("</div></section>")

    # --- Dialogue structure (turns, per chapter) ---------------------------
    if dialogue:
        parts.append('<section class="panel" id="dialogue">')
        parts.append(f"<h2>{L('panel_dialogue')}</h2>")
        parts.append('<div class="kpi-row">')
        parts.append(
            kpi(N(dialogue.get("turns", 0), 0), help_term(labels, "dialogue", L("dlg_turns")))
        )
        parts.append(kpi(P(dialogue.get("dialogue_pct", 0.0)), L("dialogue")))
        parts.append(
            kpi(N(dialogue.get("avg_turn_words", 0.0), 1), L("dlg_avg_turn"), jump="#chapters")
        )
        parts.append(
            kpi(
                N(dialogue.get("turns_per_1000", 0.0), 1), L("dlg_turns_per_1000"), jump="#chapters"
            )
        )
        parts.append("</div>")
        dialogue_chapters = [c for c in dialogue.get("chapters", []) if c.get("turns")]
        if dialogue_chapters:
            top = sorted(dialogue_chapters, key=lambda c: c.get("turns", 0), reverse=True)[:8]
            parts.append('<div class="dist">')
            for chapter in top:
                num = int(chapter.get("chapter_num", 0))
                share = float(chapter.get("dialogue_pct", 0.0))
                parts.append(
                    f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
                    f'title="{esc(chapter.get("title", ""), quote=True)}">'
                    f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
                    f'<span class="bar"><i style="width:{min(100.0, share):.1f}%"></i></span>'
                    f'<span class="val">{P(share)} · {int(chapter.get("turns", 0))} {esc(label(labels, "dlg_turns"))}</span>'
                    f"</div>"
                )
            parts.append("</div>")
        parts.append("</section>")

    # --- Character presence ------------------------------------------------
    if characters and characters.get("figures"):
        parts.append('<section class="panel" id="characters">')
        parts.append(f"<h2>{L('panel_characters')}</h2>")
        parts.append("<table><thead><tr>")
        parts.extend(
            f"<th>{L(key)}</th>"
            for key in (
                "chr_name",
                "chr_mentions",
                "chr_chapters",
                "chr_span",
                "chr_gap",
                "chr_share",
            )
        )
        parts.append("</tr></thead><tbody>")
        total = int(characters.get("chapters", 0))
        for figure in characters["figures"]:
            first = figure.get("first_chapter")
            jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
            share = float(figure.get("presence_ratio", 0.0)) * 100.0
            chapter_span = f"{first}–{figure.get('last_chapter')}" if first else "–"
            first_chapter = next((c for c in chapters if c.num == first), None)
            span_title = (
                f"{L('chapter')} {first} · {esc(first_chapter.title)}"
                if first_chapter is not None
                else ""
            )
            parts.append(
                f'<tr class="row-link"{jump}>'
                f'<td class="name">{esc(figure.get("name", ""))}</td>'
                f'<td class="num">{int(figure.get("mentions", 0))}</td>'
                f'<td class="num">{len(figure.get("chapters_present", []))} / {total}</td>'
                f'<td class="num" title="{span_title}">{esc(chapter_span)}</td>'
                f'<td class="num">{int(figure.get("longest_gap", 0))}</td>'
                f'<td class="num bar-cell"><i style="--v:{min(100.0, share):.1f}%"></i>{share:.0f} %</td>'
                f"</tr>"
            )
        parts.append("</tbody></table>")
        parts.append("</section>")

    # --- Pacing curve (scene structure & hooks) ----------------------------
    if pacing and pacing.get("chapter_list"):
        parts.append('<section class="panel" id="pacing">')
        parts.append(f"<h2>{L('panel_pacing')}</h2>")
        parts.append('<div class="kpi-row">')
        parts.append(kpi(N(pacing.get("scenes", 0), 0), L("pac_scenes")))
        parts.append(kpi(N(pacing.get("avg_scene_words", 0.0), 0), L("pac_avg_scene")))
        parts.append(kpi(N(pacing.get("hook_score_mean", 0.0), 2), L("pac_hook_mean")))
        parts.append("</div>")
        chapters_pacing = pacing["chapter_list"]
        max_asl = max((float(c.get("asl", 0.0)) for c in chapters_pacing), default=0.0) or 1.0
        parts.append('<div class="dist scrollable">')
        for chapter in chapters_pacing:
            num = int(chapter.get("chapter_num", 0))
            asl = float(chapter.get("asl", 0.0))
            hook = int(chapter.get("hook_score", 0))
            parts.append(
                f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
                f'title="{esc(chapter.get("title", ""), quote=True)}">'
                f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
                f'<span class="bar"><i style="width:{min(100.0, asl / max_asl * 100.0):.1f}%"></i></span>'
                f'<span class="val">{N(asl, 1)} · {esc(label(labels, "pac_hook"))} {hook}</span>'
                f"</div>"
            )
        parts.append("</div>")
        parts.append("</section>")

    # --- Motifs & repetition ------------------------------------------------
    if motifs and (motifs.get("motifs") or motifs.get("repeated_phrases")):
        parts.append('<section class="panel" id="motifs">')
        parts.append(f"<h2>{L('panel_motifs')}</h2>")
        if motifs.get("motifs"):
            parts.append("<table><thead><tr>")
            parts.extend(
                f"<th>{L(key)}</th>" for key in ("mot_name", "mot_count", "mot_chapters", "chr_gap")
            )
            parts.append("</tr></thead><tbody>")
            for motif in motifs["motifs"]:
                first = motif.get("first_chapter")
                jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
                motif_span = f"{first}–{motif.get('last_chapter')}" if first else "–"
                parts.append(
                    f'<tr class="row-link"{jump}>'
                    f'<td class="name">{esc(motif.get("name", ""))}</td>'
                    f'<td class="num">{int(motif.get("mentions", 0))}</td>'
                    f'<td class="num">{esc(motif_span)}</td>'
                    f'<td class="num">{int(motif.get("longest_gap", 0))}</td>'
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        if motifs.get("repeated_phrases"):
            parts.append("<table><thead><tr>")
            parts.extend(
                f"<th>{L(key)}</th>" for key in ("mot_phrase", "mot_count", "mot_chapters")
            )
            parts.append("</tr></thead><tbody>")
            for phrase in motifs["repeated_phrases"]:
                chapter_list_text = ", ".join(str(c) for c in phrase.get("chapters", []))
                first = phrase.get("chapters", [None])[0]
                jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
                parts.append(
                    f'<tr class="row-link"{jump}>'
                    f'<td class="name">{esc(phrase.get("phrase", ""))}</td>'
                    f'<td class="num">{int(phrase.get("count", 0))}</td>'
                    f'<td class="num">{esc(chapter_list_text)}</td>'
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        parts.append("</section>")

    # --- Showing vs. telling (narrative distance) ---------------------------
    if showing and showing.get("chapter_list"):
        parts.append('<section class="panel" id="showing">')
        parts.append(f"<h2>{L('panel_showing')}</h2>")
        parts.append('<div class="kpi-row">')
        parts.append(kpi(N(showing.get("tell_z_mean", 0.0), 2, signed=True), L("show_tell")))
        parts.append(kpi(N(showing.get("show_z_mean", 0.0), 2, signed=True), L("show_show")))
        parts.append(kpi(N(showing.get("balance_mean", 0.0), 2, signed=True), L("show_balance")))
        parts.append("</div>")
        showing_chapters = showing["chapter_list"]
        max_abs = (
            max((abs(float(c.get("balance", 0.0))) for c in showing_chapters), default=0.0) or 1.0
        )
        parts.append('<div class="dist scrollable">')
        for chapter in showing_chapters:
            num = int(chapter.get("chapter_num", 0))
            balance = float(chapter.get("balance", 0.0))
            width = min(100.0, abs(balance) / max_abs * 100.0)
            parts.append(
                f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
                f'title="{esc(chapter.get("title", ""), quote=True)}">'
                f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
                f'<span class="bar"><i style="width:{width:.1f}%"></i></span>'
                f'<span class="val">{N(balance, 2, signed=True)}</span>'
                f"</div>"
            )
        parts.append("</div>")
        parts.append("</section>")

    # --- Style heatmap & passport (self-calibrated house style) -----------
    if has_house_style and fingerprint is not None and metrics is not None and metrics.chapters:
        parts.append('<section class="panel" id="heatmap">')
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
                    + (' data-only="1"' if layer_key and abs(z) >= 2.5 else "")
                    + ' tabindex="0" role="button"'
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

        parts.append('<section class="panel" id="bands">')
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
                band_chart(
                    title,
                    centre - 2 * sigma,
                    centre + 2 * sigma,
                    centre,
                    values,
                    outliers,
                    layer=feature_layers.get(field_name),
                )
            )
            parts.append(f'<span class="band-count">{n_out if n_out else ""}</span>')
            parts.append("</div>")
        parts.append("</div></section>")

        # --- Style dimensions (self-calibrated principal axes) -------------
        if fingerprint.dimensions:
            parts.append('<section class="panel" id="dimensions">')
            parts.append(f"<h2>{help_term(labels, 'dimensions', L('style_dimensions'))}</h2>")
            field_labels = {f: label_key for f, label_key, _u in FEATURES}
            for dim in fingerprint.dimensions:
                loadings: dict[str, float] = dim["loadings"]
                top_pos = sorted(loadings.items(), key=lambda kv: kv[1], reverse=True)[:3]
                top_neg = sorted(loadings.items(), key=lambda kv: kv[1])[:3]
                entries = [
                    (label(labels, field_labels.get(f, f)), float(v)) for f, v in top_pos + top_neg
                ]
                chip_layers = {
                    label(labels, field_labels.get(f, f)): feature_layers[f]
                    for f, _v in top_pos + top_neg
                    if f in feature_layers
                }
                limit = max((abs(v) for _f, v in entries), default=1.0)
                flagged = dim.get("flagged", [])
                parts.append('<div class="dim-card">')
                parts.append(
                    f'<div class="dim-header"><span class="dim-title">{L("style_dimensions")} {dim["index"]}</span>'
                    f'<span class="badge">{P(dim["variance"] * 100, 0)} {L("dim_variance")}</span></div>'
                )
                parts.append(loading_bars(entries, limit, layers=chip_layers))
                if flagged:
                    ch_label = L("chapter")
                    flagged_str = ", ".join(f"{ch_label} {ch}" for ch in flagged)
                    parts.append(f'<div class="dim-meta">{L("dim_flagged")}: {flagged_str}</div>')
                parts.append("</div>")
            parts.append("</section>")

        # --- Work markers (editor-visible, set from the dashboard) -------
        if markers is not None:
            parts.append('<section class="panel" id="markers">')
            parts.append(f"<h2>{help_term(labels, 'markers', L('markers'))}</h2>")
            if markers:
                parts.append('<div class="table-wrap">')
                parts.append("<table><thead><tr>")
                parts.append(
                    f"<th>{L('status')}</th><th>{L('chapter')}</th>"
                    f'<th class="num">{L("line")}</th><th>{L("notes")}</th>'
                )
                if controls:
                    parts.append("<th></th>")
                parts.append("</tr></thead><tbody>")
                for m in markers:
                    kind_label = label(labels, "marker_" + m.kind)
                    note = esc(str(m.note or "")) or "–"
                    marker_chapter = next(
                        (c for c in chapters if c.start_line <= m.line <= c.end_line), None
                    )
                    chapter_cell = (
                        f"{L('chapter')} {marker_chapter.num} · {esc(marker_chapter.title)}"
                        if marker_chapter is not None
                        else "–"
                    )
                    parts.append(
                        f'<tr class="row-link" data-line="{m.line}" role="button" tabindex="0">'
                        f'<td><span class="badge marker-{m.kind}">{esc(kind_label)}</span></td>'
                        f"<td>{chapter_cell}</td>"
                        f'<td class="num">{L("line")} {m.line}</td><td>{note}</td>'
                    )
                    if controls:
                        parts.append(
                            f'<td><button class="ctl" data-marker-resolve="{esc(m.id, quote=True)}">'
                            f"{L('marker_resolve')}</button></td>"
                        )
                    parts.append("</tr>")
                parts.append("</tbody></table></div>")
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
            low, high = _layer_range(layer_key)
            parts.append(
                f'<option value="{layer_key}" '
                f'data-hint="{esc(label(labels, "layer_hint_" + layer_key), quote=True)}" '
                f'data-range="{esc(f"{_layer_text(layer_key, low)} – {_layer_text(layer_key, high)}", quote=True)}">'
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

    parts.append(
        f'<div class="layer-legend" id="layer-legend" hidden="hidden" '
        f'data-outliers="{esc(label(labels, "layer_outliers"), quote=True)}" '
        f'data-outliers-one="{esc(label(labels, "layer_outliers_one"), quote=True)}">'
    )
    parts.append('<span class="layer-title" id="layer-legend-title" tabindex="0"></span>')
    parts.append('<span class="z-gradient"></span>')
    parts.append(
        '<span class="layer-scale"><span id="layer-scale-low"></span>'
        '<span id="layer-scale-high"></span></span>'
    )
    parts.append('<span class="layer-count" id="layer-legend-count"></span>')
    parts.append(
        f'<label class="layer-only"><input type="checkbox" id="layer-only"/> '
        f"{esc(label(labels, 'layer_only'))}</label>"
    )
    parts.append(f'<button class="ctl" id="layer-next">{esc(label(labels, "layer_next"))}</button>')
    parts.append("</div>")

    if not tense_available:
        parts.append(f'<p class="hint">{L("no_tense")}</p>')

    # --- Chapter map ------------------------------------------------------
    by_chapter: dict[int, list[tuple[int, Any]]] = {}
    for idx, p in enumerate(paragraphs):
        by_chapter.setdefault(p.chapter_num, []).append((idx, p))

    parts.append('<main id="chapters">')
    for chapter in chapters:
        chapter_paras = by_chapter.get(chapter.num, [])
        has_flags = any(p.is_flagged for _, p in chapter_paras)
        classes = "chapter has-flags" if has_flags else "chapter"
        parts.append(
            f'<section class="{classes}" id="ch-{chapter.num}" '
            f'data-start="{chapter.start_line}" data-end="{chapter.end_line}">'
        )
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
                sev = f" sev-{p.severity}" if p.is_flagged else ""
                width = max(1.0, p.words / scale * 100.0)
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                tooltip = (
                    f"{line_label(labels, p)} · {dom_label} · "
                    f"{label(labels, 'present')} {p.present_hits} / "
                    f"{label(labels, 'past')} {p.past_hits} · {sev_label}"
                )
                layer_payload: dict[str, list[Any]] = {}
                for key in LAYER_FEATURES:
                    info = layer_data.get(key, {}).get(idx)
                    if info is not None:
                        value, z = info
                        low, high = _layer_range(key)
                        span = (high - low) or 1.0
                        position = (value - low) / span
                        colour = z_color((position * 2.0 - 1.0) * 2.5)
                        layer_payload[key] = [colour, _layer_tip(key, value, z), round(z, 2)]
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
                parts.append(
                    f'<div class="ptext" id="p-{idx}" data-start="{p.start_line}" '
                    f'data-end="{p.end_line}"><div class="ptext-inner">'
                )
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
                        f'<button class="ctl" data-marker-kind="{esc(kind, quote=True)}" '
                        f'data-line="{p.start_line}">+ {esc(label(labels, "marker_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(
                        f'<div class="row marker-row">{buttons}'
                        f'<span class="marker-note-slot" '
                        f'data-placeholder="{esc(label(labels, "marker_note"), quote=True)}"></span>'
                        f"</div>"
                    )
                parts.append(f"<p>{esc(p.text)}</p>")
                parts.append("</div></div>")
        parts.append("</section>")
    parts.append("</main>")

    # --- Chapter matrix ---------------------------------------------------
    if chapters:
        parts.append('<section class="panel" id="matrix">')
        parts.append(f"<h2>{L('chapter_table')}</h2>")
        parts.append('<div class="table-wrap">')
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
            row_hint = ' data-flags="1"' if c.flagged else ""
            parts.append(
                f'<tr class="row-link" data-jump="#ch-{c.num}"{row_hint} role="button" tabindex="0">'
                f"<td>{c.num}</td><td>{esc(c.title)}</td>"
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
        parts.append("</tbody></table></div></section>")

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

