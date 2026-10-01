"""Reusable style heatmap and reference-bands passport panels."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..format import num as format_num
from ..style_fingerprint import (
    FEATURES,
    LAYER_FEATURES,
    Z_COLOR_LIMIT,
    StyleFingerprint,
    z_color,
)
from .components import band_chart, contrast_text, esc, help_term, label

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


def render_heatmap_panel(
    fingerprint: StyleFingerprint | None,
    metrics: Any | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
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

    parts: list[str] = ['<section class="panel" id="heatmap">']
    parts.append(f"<h2>{help_term(labels, 'heatmap', L('style_fingerprint'))}</h2>")
    parts.append(
        '<div class="z-legend">'
        + esc(label(labels, "zscore"))
        + f' <span class="z-gradient"></span> −{N(Z_COLOR_LIMIT, 1)} … +{N(Z_COLOR_LIMIT, 1)}'
        + "</div>"
    )
    parts.append(f'<p class="panel-guide">{L("matrix_reading")}</p>')
    parts.append(
        f'<div class="matrix-tools"><label><input type="checkbox" id="heatmap-fdr-only"/> '
        f'{L("matrix_fdr_only")}</label><span class="analysis-method">'
        f'{esc(fingerprint.thresholds.fdr_method.upper())} · q = {N(fingerprint.thresholds.fdr_q, 2)}'
        f' · |z*| ≥ {N(z_mild, 1)}</span></div>'
    )
    parts.append(f'<p id="heatmap-empty" class="panel-guide" role="status" hidden>{L("matrix_empty")}</p>')
    parts.append('<div class="heatmap-wrap"><table class="heatmap"><thead><tr>')
    parts.append('<th class="ch" id="feat-chapter">' + L("chapter") + "</th>")
    for _field, label_key, _unit in FEATURES:
        parts.append(
            f'<th id="feat-{_field}">'
            f"{help_term(labels, FEATURE_HELP_KEYS.get(_field, _field), esc(label(labels, label_key)))}"
            "</th>"
        )
    parts.append("</tr></thead><tbody>")
    for chapter in metrics.chapters:
        if chapter.num not in fingerprint.z_scores:
            continue
        confirmed = set(fingerprint.fdr_flagged.get(chapter.num, []))
        parts.append(f'<tr data-fdr-count="{len(confirmed)}"><td class="ch">{chapter.num}. {esc(chapter.title)}</td>')
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
