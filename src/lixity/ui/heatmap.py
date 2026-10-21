"""Reusable style heatmap and reference-bands passport panels."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..format import num as format_num
from ..style_fingerprint import (
    FEATURES,
    LAYER_FEATURES,
    MIN_COMPARABLE_SENTENCES,
    MIN_COMPARABLE_WORDS,
    Z_COLOR_LIMIT,
    StyleFingerprint,
    z_color,
)
from .components import band_chart, checkbox_field, contrast_text, esc, help_term, label

FEATURE_HELP_KEYS: dict[str, str] = {
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


def render_register_targets(
    fingerprint: StyleFingerprint | None, metrics: Any | None,
    labels: Mapping[str, str] | None, language_key: str,
) -> str:
    """Author ranges are descriptive comparisons, independent of statistical z."""
    if fingerprint is None or not fingerprint.register_targets or metrics is None:
        return ""
    titles = {chapter.num: chapter.title for chapter in metrics.chapters}
    features = {name: label(labels, key) for name, key, _ in FEATURES}
    parts = ['<section class="panel" id="register-targets">',
             f'<h2>{esc(label(labels, "register_title"))}</h2>',
             f'<p class="panel-guide">{esc(label(labels, "register_hint"))}</p>',
             '<div class="table-wrap"><table><thead><tr>']
    parts.extend(f'<th scope="col">{esc(label(labels, key))}</th>' for key in (
        "chapter", "register_name", "register_target", "register_lower", "register_upper", "scene_value", "status"))
    parts.append('</tr></thead><tbody>')
    for number, targets in sorted(fingerprint.register_targets.items()):
        register = fingerprint.chapter_registers[number]
        for feature, comparison in targets.items():
            parts.append(f'<tr data-register="{esc(register)}">'
                         f'<th scope="row">{number}. {esc(titles.get(number, ""))}</th>'
                         f'<td>{esc(register)}</td><td>{esc(features.get(feature, feature))}</td>')
            for key in ("lower", "upper", "value"):
                value = comparison[key]
                parts.append(f'<td>{format_num(value, language_key, 2) if value is not None else "–"}</td>')
            parts.append(f'<td>{esc(label(labels, "scene_" + comparison["position"]))}</td></tr>')
    parts.append('</tbody></table></div></section>')
    return "".join(parts)


def render_heatmap_panel(
    fingerprint: StyleFingerprint | None,
    metrics: Any | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *, characters: Mapping[str, Any] | None = None,
) -> str:
    """Renders the diverging z-score heatmap matrix panel."""
    if fingerprint is None or metrics is None or not metrics.chapters:
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}
    z_mild = fingerprint.thresholds.z_mild
    chapter_numbers = {chapter.num for chapter in metrics.chapters if chapter.num in fingerprint.z_scores}
    register_names = sorted({name for number, name in fingerprint.chapter_registers.items()
                             if number in chapter_numbers})
    register_keys = {name: f"r-{index}" for index, name in enumerate(register_names)}
    pov_groups = []
    if characters and not characters.get("error"):
        for figure in characters.get("figures", []):
            members = {number for number in figure.get("declared_pov_chapters", [])
                       if type(number) is int and number in chapter_numbers}
            if members:
                pov_groups.append((figure["name"], members))
    pov_groups.sort(key=lambda group: group[0])

    parts: list[str] = ['<section class="panel" id="heatmap">']
    parts.append(
        "<h2>"
        + help_term(
            labels,
            "heatmap",
            L("style_fingerprint"),
            fields={
                "min_words": str(MIN_COMPARABLE_WORDS),
                "min_sentences": str(MIN_COMPARABLE_SENTENCES),
            },
        )
        + "</h2>"
    )
    parts.append(
        '<div class="z-legend">'
        + esc(label(labels, "zscore"))
        + f' <span class="z-gradient"></span> −{N(Z_COLOR_LIMIT, 1)} … +{N(Z_COLOR_LIMIT, 1)}'
        + "</div>"
    )
    reading = (
        label(labels, "matrix_reading")
        .replace("{min_words}", str(MIN_COMPARABLE_WORDS))
        .replace("{min_sentences}", str(MIN_COMPARABLE_SENTENCES))
    )
    parts.append(f'<p class="panel-guide">{esc(reading)}</p>')
    fdr_only = checkbox_field('<input type="checkbox" id="heatmap-fdr-only"/>', L("matrix_fdr_only"))
    parts.append(
        f'<div class="matrix-tools">{fdr_only}<span class="analysis-method">'
        f'{esc(fingerprint.thresholds.fdr_method.upper())} · q = {N(fingerprint.thresholds.fdr_q, 2)}'
        f' · |z*| ≥ {N(z_mild, 1)}</span></div>'
    )
    if register_names or pov_groups:
        parts.append(
            f'<div class="analysis-scope" id="analysis-scope" hidden '
            f'data-empty-label="{L("analysis_scope_empty")}"><div class="analysis-scope-controls">'
        )
        if register_names:
            parts.append(f'<label for="analysis-scope-register">{L("analysis_scope_register")}'
                         '<select class="ctl" id="analysis-scope-register">'
                         f'<option value="">{L("analysis_scope_all")}</option>')
            parts.extend(f'<option value="{register_keys[name]}">{esc(name)}</option>' for name in register_names)
            if any(number not in fingerprint.chapter_registers for number in chapter_numbers):
                parts.append(f'<option value="unassigned">{L("analysis_scope_unassigned")}</option>')
            parts.append('</select></label>')
        if pov_groups:
            parts.append(f'<label for="analysis-scope-pov">{L("analysis_scope_pov")}'
                         '<select class="ctl" id="analysis-scope-pov">'
                         f'<option value="">{L("analysis_scope_all")}</option>')
            for index, (name, _members) in enumerate(pov_groups):
                parts.append(f'<option value="p-{index}">{esc(name)}</option>')
            parts.append('</select></label>')
        parts.append(f'<button type="button" class="ctl" id="analysis-scope-reset">'
                     f'{L("analysis_scope_reset")}</button></div>')
        template = label(labels, "analysis_scope_status")
        initial = template.replace("{shown}", N(len(chapter_numbers), 0)).replace("{total}", N(len(chapter_numbers), 0))
        parts.append(f'<p class="ctl-note" id="analysis-scope-status" role="status" '
                     f'data-template="{esc(template)}">{esc(initial)}</p>'
                     f'<details><summary>{L("layer_guide")}</summary>'
                     f'<p class="ctl-note">{L("analysis_scope_hint")}</p>')
        if register_names:
            parts.append(f'<p class="ctl-note">{L("analysis_scope_exemption")}</p>')
        parts.append('</details></div>')
    parts.append(f'<p id="heatmap-empty" class="panel-guide" role="status" hidden>{L("matrix_empty")}</p>')
    parts.append('<div class="heatmap-wrap" tabindex="0" role="region" '
                 f'aria-label="{L("style_fingerprint")}"><table class="heatmap"><thead><tr>')
    parts.append('<th scope="col" class="ch" id="feat-chapter">' + L("chapter") + "</th>")
    for _field, label_key, _unit in FEATURES:
        parts.append(
            f'<th scope="col" id="feat-{_field}">'
            f"{help_term(labels, FEATURE_HELP_KEYS.get(_field, _field), esc(label(labels, label_key)))}"
            "</th>"
        )
    parts.append("</tr></thead><tbody>")
    for chapter in metrics.chapters:
        if chapter.num not in fingerprint.z_scores:
            continue
        confirmed = set(fingerprint.fdr_flagged.get(chapter.num, []))
        register = fingerprint.chapter_registers.get(chapter.num)
        register_badge = (
            f' <span class="badge badge-register" title="{esc(register)}">{esc(register)}</span>'
            if register else ""
        )
        pov_memberships = " ".join(f"p-{index}" for index, (_name, members) in enumerate(pov_groups)
                                   if chapter.num in members)
        parts.append(f'<tr id="heatmap-ch-{chapter.num}" data-chapter-num="{chapter.num}" '
                     f'data-scope-register="{register_keys.get(register, "unassigned") if register is not None else "unassigned"}" '
                     f'data-scope-pov="{pov_memberships}" '
                     f'data-fdr-count="{len(confirmed)}" data-register="{esc(register or "")}">'
                     f'<td class="ch">{chapter.num}. {esc(chapter.title)}{register_badge}</td>')
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
            cliff = fingerprint.cliffs_delta.get(chapter.num, {}).get(field_name)
            if cliff is not None:
                tooltip += f" · Cliff’s δ {N(cliff, 2, signed=True)}"
            marker = (
                f'<span class="fdr-marker" aria-label="{L("fdr_flagged")}">●</span>'
                if field_name in confirmed else ""
            )
            layer_key = feature_layers.get(field_name, "")
            cell_attrs = (
                f' data-chapter="{chapter.num}" data-layer="{layer_key}"'
                + (' data-only="1"' if layer_key and abs(z) >= z_mild else "")
                + ' tabindex="0" role="button"'
            )
            if abs(z) < 0.05:
                parts.append(
                    f'<td class="z zero"{cell_attrs} title="{esc(tooltip, quote=True)}">0{marker}</td>'
                )
            else:
                background = z_color(z)
                parts.append(
                    f'<td class="z" style="background:{background};'
                    f'color:{contrast_text(background)}"{cell_attrs} '
                    f'title="{esc(tooltip, quote=True)}">{N(z, 1, signed=True)}{marker}</td>'
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
    return "".join(parts)


def render_style_passport_panel(
    fingerprint: StyleFingerprint | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the self-calibrated style reference bands panel."""
    if fingerprint is None:
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}

    parts: list[str] = ['<section class="panel" id="bands">']
    parts.append(f"<h2>{help_term(labels, 'passport', L('style_passport'))}</h2>")
    parts.append(f'<p class="panel-guide">{L("reference_reading")}</p>')
    parts.append('<div class="bands">')
    for field_name, label_key, _unit in FEATURES:
        base = fingerprint.baseline.get(field_name, {})
        if int(base.get("n", 0)) < fingerprint.thresholds.min_chapters:
            continue
        centre = float(base["median"])
        sigma = float(base["sigma"])
        series = fingerprint.values.get(field_name, {})
        values = [float(v) for v in series.values() if v is not None]
        outlier_chapters = [
            int(ch) for ch, feats in fingerprint.deviations.items() if field_name in feats
        ]
        outliers = [float(val) for ch in outlier_chapters if (val := series.get(ch)) is not None]
        n_out = len(outliers)
        layer = feature_layers.get(field_name)
        click_hint = label(labels, "click_hint")
        title = (
            f"{label(labels, label_key)}: {L('median')} {N(centre, 2)} · "
            f"σ = {N(sigma, 2)} · n = {int(base['n'])} · "
            f"{L('band')} {N(centre - 2 * sigma, 2)} – {N(centre + 2 * sigma, 2)} · "
            f"{L('outliers')}: {n_out}" + (f" · {click_hint}" if n_out or layer else "")
        )
        row_attrs = [
            f'data-jump="#feat-{field_name}"',
            f'data-feature="{field_name}"',
            'role="button"',
            'tabindex="0"',
            f'title="{esc(title, quote=True)}"',
        ]
        if layer:
            row_attrs.append(f'data-layer="{layer}"')
            if n_out:
                row_attrs.append('data-only="1"')
        parts.append(f'<div class="band-row" {" ".join(row_attrs)}>')
        parts.append(
            f'<span class="band-label">{help_term(labels, FEATURE_HELP_KEYS.get(field_name, field_name), esc(label(labels, label_key)))}'
            f'<small class="band-summary">{L("median")} {N(centre, 2)} · n = {int(base["n"])}</small></span>'
        )
        parts.append(
            band_chart(
                title,
                centre - 2 * sigma,
                centre + 2 * sigma,
                centre,
                values,
                outliers,
            )
        )
        if n_out and outlier_chapters:
            strongest = max(
                outlier_chapters,
                key=lambda ch: abs(
                    float(fingerprint.deviations.get(ch, {}).get(field_name, 0.0))
                ),
            )
            title_text = (
                f"{label(labels, label_key)} · {L('chapter')} {strongest} · {click_hint}"
            )
            count_attrs = [
                f'data-jump="#ch-{strongest}"',
                'role="button"',
                'tabindex="0"',
                f'title="{esc(title_text, quote=True)}"',
            ]
            if layer:
                count_attrs.append(f'data-layer="{layer}"')
                count_attrs.append('data-only="1"')
            parts.append(
                f'<span class="band-count band-outlier" {" ".join(count_attrs)}>{n_out}</span>'
            )
        else:
            parts.append(f'<span class="band-count">{n_out if n_out else ""}</span>')
        parts.append("</div>")
    parts.append("</div></section>")
    return "".join(parts)
