"""Reusable style heatmap and reference-bands passport panels."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..format import num as format_num
from ..models import ChapterMetrics
from ..style_fingerprint import (
    FEATURE_UNITS,
    FEATURES,
    LAYER_FEATURES,
    MIN_COMPARABLE_SENTENCES,
    MIN_COMPARABLE_WORDS,
    REFERENCE_BAND_SIGMA,
    Z_COLOR_LIMIT,
    StyleFingerprint,
    z_color,
)
from .components import (
    attr_json,
    badge,
    band_chart,
    chapter_link,
    checkbox_field,
    contrast_text,
    details_start,
    esc,
    help_term,
    label,
    modal_footer,
    modal_shell,
    panel_formatters,
    panel_guide,
    panel_start,
    table_wrap_start,
)

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
    "long_word_pct": "long_words",
    "start_entropy": "start_entropy",
    "first_person_start_rate": "first_start",
    "guiraud_r": "guiraud",
    "hd_d": "hd_d",
    "mtld": "mtld",
    "mattr": "mattr",
    "maas_a2": "maas",
}

_FEATURE_DISPLAY_KEYS = {
    "asl": "readability_asl",
    "staccato_pct": "measurement_short_sentences",
    "sentence_cv": "heatmap_sentence_variation",
}


def render_metric_context(
    fingerprint: StyleFingerprint,
    chapters: Sequence[ChapterMetrics],
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Project existing chapter measurements into one shared, read-only inspector."""
    layers = {field: key for key, field in LAYER_FEATURES.items()}
    units = FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])
    features = {}
    for field, key, unit in FEATURES:
        base = fingerprint.baseline.get(field, {})
        supported = int(base.get("n", 0)) >= fingerprint.thresholds.min_chapters
        features[field] = {
            "label": label(labels, _FEATURE_DISPLAY_KEYS.get(field, key)),
            "unit": units.get(field, unit),
            "help": label(labels, "help_" + FEATURE_HELP_KEYS.get(field, field)),
            "layer": layers.get(field, ""),
            "median": format_num(float(base["median"]), language_key, 2) if supported else "–",
            "n": int(base.get("n", 0)),
        }
    chapter_data = {}
    for chapter in chapters:
        chapter_data[str(chapter.num)] = {
            "title": f"{chapter.num}. {chapter.title}",
            "sample": f"{chapter.words} {label(labels, 'words')} · {chapter.sentences} {label(labels, 'sentences')}",
            "values": {
                field: {
                    "value": format_num(value, language_key, 2) if value is not None else "–",
                    "z": format_num(z, language_key, 2, signed=True) if z is not None else "–",
                    "reason": (label(labels, "baseline_zero_mad")
                               if z is None and value is not None and
                               fingerprint.baseline.get(field, {}).get("comparison_status")
                               in ("zero_mad_varying", "zero_mad_constant") else ""),
                }
                for field, _key, _unit in FEATURES
                for value in [fingerprint.values.get(field, {}).get(chapter.num)]
                for z in [fingerprint.z_scores.get(chapter.num, {}).get(field)]
            },
        }
    payload = attr_json(
        {
            "features": features,
            "chapters": chapter_data,
            "labels": {
                "loading": label(labels, "dim_loading"),
                "poles": label(labels, "dim_poles"),
                "unavailable": label(labels, "metric_context_missing"),
            },
        }
    )
    body = (
        '<div class="modal-body">'
        '<p id="metric-context-chapter"></p><p class="ctl-note" id="metric-context-sample"></p>'
        '<p id="metric-context-definition"></p>'
        '<dl class="metric-context-comparison">'
        f'<div><dt>{esc(label(labels, "metric_context_this_chapter"))}</dt><dd id="metric-context-value"></dd></div>'
        f'<div><dt>{esc(label(labels, "metric_context_typical"))}</dt><dd id="metric-context-typical"></dd></div>'
        '</dl>'
        '<p class="ctl-note" id="metric-context-origin" hidden></p>'
        '<p class="ctl-note" id="metric-context-no-layer" hidden>'
        f'{esc(label(labels, "metric_context_no_layer"))}</p>'
        + details_start(esc(label(labels, "metric_context_details")), element_id="metric-context-details")
        + f'<p class="ctl-note">{esc(label(labels, "metric_context_hint"))}</p>'
        + table_wrap_start(
            aria_labelledby="metric-context-caption",
            caption_html=f'<caption id="metric-context-caption">{esc(label(labels, "metric_context_title"))}</caption>',
        )
        + '<thead><tr>'
        f'<th scope="col">{esc(label(labels, "register_target"))}</th>'
        f'<th scope="col">{esc(label(labels, "scene_value"))}</th>'
        f'<th scope="col">{esc(label(labels, "metric_context_reference"))}</th>'
        '<th scope="col">z*</th></tr></thead><tbody id="metric-context-values"></tbody></table></div></details>'
        '</div>'
    )
    close_label = label(labels, "modal_close")
    footer = modal_footer(
        f'<button type="button" class="ctl" data-metric-close>{esc(close_label)}</button>'
        f'<a class="ctl primary" id="metric-context-read">{esc(label(labels, "dim_read_chapter"))}</a>'
    )
    return modal_shell(
        "analysis-metric-context", "metric-context-title", esc(label(labels, "metric_context_title")), body,
        close_label=close_label, footer_html=footer, extra_attrs=f'data-metric-context="{payload}"',
        title_tag="h2", focusable_title=True, close_attrs="data-metric-close",
    )


def render_register_targets(
    fingerprint: StyleFingerprint | None, metrics: Any | None,
    labels: Mapping[str, str] | None, language_key: str,
    *, settings_available: bool = False,
) -> str:
    """Author ranges are descriptive comparisons, independent of statistical z."""
    if fingerprint is None or not fingerprint.register_targets or metrics is None:
        return ""
    titles = {chapter.num: chapter.title for chapter in metrics.chapters}
    features = {name: label(labels, key) for name, key, _ in FEATURES}
    units = {name: FEATURE_UNITS.get(language_key, {}).get(name, unit) for name, _key, unit in FEATURES}
    parts = [panel_start("register-targets", labels, "register_title"),
             panel_guide(esc(label(labels, "register_hint"))),
             f'<p class="ctl-note">{esc(label(labels, "register_scope_hint"))}</p>']
    if settings_available:
        parts.append('<p><a class="ctl-link" href="#settings-registers-summary" data-register-settings>'
                     f'{esc(label(labels, "register_edit"))}</a></p>')
    parts.append(table_wrap_start(label(labels, "register_title")) + '<thead><tr>')
    parts.extend(f'<th scope="col">{esc(label(labels, key))}</th>' for key in (
        "chapter", "register_name", "register_target", "register_lower", "register_upper", "scene_value", "status"))
    parts.append('</tr></thead><tbody>')
    for number, targets in sorted(fingerprint.register_targets.items()):
        register = fingerprint.chapter_registers[number]
        for feature, comparison in targets.items():
            chapter_title = f"{number}. {esc(titles.get(number, ''))}"
            parts.append(f'<tr data-register="{esc(register)}">'
                         f'<th scope="row">{chapter_link(number, chapter_title)}</th>'
                         f'<td>{esc(register)}</td><td>{esc(features.get(feature, feature))} '
                         f'<small>{esc(units.get(feature, ""))}</small></td>')
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

    L, N, P = panel_formatters(labels, language_key)

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

    parts: list[str] = [
        panel_start(
            "heatmap",
            labels,
            "style_fingerprint",
            help_key="heatmap",
            help_fields={
                "min_words": str(MIN_COMPARABLE_WORDS),
                "min_sentences": str(MIN_COMPARABLE_SENTENCES),
            },
        ),
        panel_guide(L("heatmap_author_guide")),
    ]
    parts.append(
        '<div class="z-legend">'
        f'<span>{L("heatmap_lower")}</span><span class="z-gradient" aria-hidden="true"></span>'
        f'<span>{L("heatmap_higher")}</span></div>'
    )
    reading = (
        label(labels, "matrix_reading")
        .replace("{min_words}", str(MIN_COMPARABLE_WORDS))
        .replace("{min_sentences}", str(MIN_COMPARABLE_SENTENCES))
    )
    method = esc(fingerprint.thresholds.fdr_method.upper())
    consistency = (
        f'{P(fingerprint.consistency * 100, 0)}'
        f' · {N(round(fingerprint.consistency * fingerprint.measured_cells), 0)} / {N(fingerprint.measured_cells, 0)}'
        if fingerprint.measured_cells else '–'
    )
    fdr_total = sum(len(results) for results in fingerprint.fdr_flagged.values())
    parts.append(
        details_start(L("heatmap_method"), extra_class="heatmap-method")
        + panel_guide(esc(reading))
        + f'<p class="analysis-method">{method} · q = {N(fingerprint.thresholds.fdr_q, 2)}'
        f' · |z*| ≥ {N(z_mild, 1)} · {L("zscore")} ±{N(Z_COLOR_LIMIT, 1)}</p>'
        + panel_guide(f'{L("cockpit_cohesion_summary")} · {consistency}')
        + f'<p class="hint">{help_term(labels, "expected_false_positives", L("expected_false_positives"))}: '
        f'~{N(fingerprint.expected_false_positives, 1)} · {help_term(labels, "fdr", L("fdr_flagged"))}: {fdr_total}</p>'
        + '</details>'
    )
    fdr_only = checkbox_field('<input type="checkbox" id="heatmap-fdr-only" disabled/>', L("heatmap_marked_only"))
    parts.append(
        f'<div class="matrix-tools">{fdr_only}'
        f'<a href="#matrix" class="ctl cockpit-switch" data-jump="#matrix">{L("cockpit_switch_matrix")} →</a></div>'
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
        if register_names:
            reg_counts = {name: sum(1 for num in chapter_numbers if fingerprint.chapter_registers.get(num) == name)
                          for name in register_names}
            unassigned_count = sum(1 for num in chapter_numbers if num not in fingerprint.chapter_registers)
            parts.append(
                f'<div class="chip-row analysis-scope-pills" role="group" '
                f'aria-label="{L("analysis_scope_register")}" data-sync-select="analysis-scope-register">'
                f'<button type="button" class="ctl ctl-sm" data-value="" aria-pressed="true">'
                f'{L("analysis_scope_all")} {badge(N(len(chapter_numbers), 0), variant="")}</button>'
            )
            parts.extend(
                f'<button type="button" class="ctl ctl-sm" data-value="{register_keys[name]}" aria-pressed="false">'
                f'{esc(name)} {badge(N(reg_counts[name], 0), variant="")}</button>'
                for name in register_names
            )
            if unassigned_count:
                parts.append(
                    f'<button type="button" class="ctl ctl-sm" data-value="unassigned" aria-pressed="false">'
                    f'{L("analysis_scope_unassigned")} {badge(N(unassigned_count, 0), variant="")}</button>'
                )
            parts.append('</div>')
        if pov_groups:
            parts.append(
                f'<div class="chip-row analysis-scope-pills" role="group" '
                f'aria-label="{L("analysis_scope_pov")}" data-sync-select="analysis-scope-pov">'
                f'<button type="button" class="ctl ctl-sm" data-value="" aria-pressed="true">'
                f'{L("analysis_scope_all")} {badge(N(len(chapter_numbers), 0), variant="")}</button>'
            )
            for index, (name, members) in enumerate(pov_groups):
                pov_count = sum(1 for num in chapter_numbers if num in members)
                parts.append(
                    f'<button type="button" class="ctl ctl-sm" data-value="p-{index}" aria-pressed="false">'
                    f'{esc(name)} {badge(N(pov_count, 0), variant="")}</button>'
                )
            parts.append('</div>')
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
            f'{help_term(labels, FEATURE_HELP_KEYS.get(_field, _field), L(_FEATURE_DISPLAY_KEYS.get(_field, label_key)))}'
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
            feature_name = label(labels, _FEATURE_DISPLAY_KEYS.get(field_name, label_key))
            layer_key = feature_layers.get(field_name, "")
            cell_attrs = (
                f' data-chapter="{chapter.num}" data-layer="{layer_key}"'
                f' data-metric-feature="{field_name}"'
                + (' data-only="1"' if layer_key and z is not None and abs(z) >= z_mild else "")
                + ' tabindex="0" role="button"'
            )
            if z is None:
                status = fingerprint.baseline.get(field_name, {}).get("comparison_status")
                reason = (label(labels, "baseline_zero_mad")
                          if fingerprint.values.get(field_name, {}).get(chapter.num) is not None
                          and status in ("zero_mad_varying", "zero_mad_constant")
                          else label(labels, "project_identity_unavailable"))
                description = esc(
                    f"{feature_name} · {label(labels, 'chapter')} {chapter.num} · "
                    f"{reason}",
                    quote=True,
                )
                parts.append(f'<td class="z"{cell_attrs} aria-label="{description}">–</td>')
                continue
            raw = fingerprint.values[field_name].get(chapter.num)
            raw_text = N(raw, 2) if isinstance(raw, float) else str(raw)
            effect = fingerprint.effect_sizes[chapter.num].get(field_name, 0.0)
            tooltip = (
                f"{feature_name}: {raw_text} · "
                f"z* {N(z, 1, signed=True)} · "
                f"{label(labels, 'effect_size')} {N(effect, 1, signed=True)}\u03c3 · "
                f"{label(labels, 'click_hint')}"
            )
            cliff = fingerprint.cliffs_delta.get(chapter.num, {}).get(field_name)
            if cliff is not None:
                tooltip += f" · Cliff’s δ {N(cliff, 2, signed=True)}"
            marker = '<span class="fdr-marker" aria-hidden="true">●</span>' if field_name in confirmed else ""
            if chapter.num in fingerprint.chapter_registers:
                fdr_status = label(labels, "analysis_scope_exemption")
            else:
                selected = "research_value_yes" if field_name in confirmed else "research_value_no"
                fdr_status = f'{label(labels, "fdr_flagged")}: {label(labels, selected)}'
            cell_attrs += (
                f' aria-label="{esc(feature_name)} · '
                f'{L("chapter")} {chapter.num} · z* {N(z, 1, signed=True)} · {esc(fdr_status, quote=True)}"'
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
    coupled = _render_coupled_style_patterns(
        fingerprint, metrics.chapters, z_mild, labels, language_key
    )
    if coupled:
        parts.append(coupled)
    parts.append("</section>")
    return "".join(parts)


def _render_coupled_style_patterns(
    fingerprint: StyleFingerprint,
    chapters: Sequence[ChapterMetrics],
    z_mild: float,
    labels: Mapping[str, str] | None,
    language_key: str,
) -> str:
    """Render combined multi-metric chapter style patterns when two or more linked z-scores align."""
    L, _, _ = panel_formatters(labels, language_key)
    patterns: tuple[tuple[str, Any], ...] = (
        (
            "style_pattern_distancing",
            lambda z: (z.get("perception_verbs") or 0.0) >= z_mild
            and ((z.get("nominalizations") or 0.0) >= z_mild or (z.get("passive_patterns") or 0.0) >= z_mild),
        ),
        (
            "style_pattern_dense_narrative",
            lambda z: (z.get("asl") or 0.0) >= z_mild and (z.get("dialogue_ratio") or 0.0) <= -z_mild,
        ),
        (
            "style_pattern_fast_dialogue",
            lambda z: (z.get("asl") or 0.0) <= -z_mild and (z.get("dialogue_ratio") or 0.0) >= z_mild,
        ),
        (
            "style_pattern_expository",
            lambda z: (z.get("function_words") or 0.0) >= z_mild and (z.get("modal_verbs") or 0.0) >= z_mild,
        ),
    )
    items: list[str] = []
    for label_key, predicate in patterns:
        matched = [
            ch.num
            for ch in chapters
            if ch.num in fingerprint.z_scores and predicate(fingerprint.z_scores[ch.num])
        ]
        if not matched:
            continue
        links = " ".join(
            f'<a class="ctl ctl-sm" href="#ch-{num}" data-jump="#ch-{num}">{L("chapter")} {num}</a>'
            for num in matched
        )
        items.append(f"<li><strong>{esc(L(label_key))}:</strong> {links}</li>")
    if not items:
        return ""
    return (
        f'<div class="style-coupled-patterns">'
        f'<h3>{esc(L("style_coupled_patterns"))}</h3>'
        f'<ul>{"".join(items)}</ul></div>'
    )


def render_style_passport_panel(
    fingerprint: StyleFingerprint | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the self-calibrated style reference bands panel."""
    if fingerprint is None:
        return ""

    L, N, _ = panel_formatters(labels, language_key)

    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}

    parts: list[str] = [
        panel_start("bands", labels, "style_passport", help_key="passport"),
        panel_guide(L("reference_reading")),
    ]
    notes = fingerprint.interpretation_texts(labels, language_key)
    parts.append(f'<p class="hint">{esc(notes["selection_limits"])}</p>')
    if "small_sample" in notes:
        parts.append(f'<p class="hint" id="style-small-sample" role="status">{esc(notes["small_sample"])}</p>')
    if "rounding_sensitive" in notes:
        parts.append(f'<p class="hint" id="style-rounding-sensitive" role="status">{esc(notes["rounding_sensitive"])}</p>')
    parts.append(f'<details id="style-decision-legend"><summary>{esc(notes["decision_legend"])}</summary><ul>')
    parts.extend(f'<li>{esc(notes[key])}</li>' for key in (
        "decision_band", "decision_deviation", "decision_fdr", "decision_layer"
    ))
    if "register_exemptions" in notes:
        parts.append(f'<li>{esc(notes["register_exemptions"])}</li>')
    parts.append('</ul></details>')
    parts.append('<div class="bands">')
    for field_name, label_key, _unit in FEATURES:
        base = fingerprint.baseline.get(field_name, {})
        if int(base.get("n", 0)) < fingerprint.thresholds.min_chapters:
            continue
        centre = float(base["median"])
        sigma = float(base["sigma"])
        series = fingerprint.values.get(field_name, {})
        if sigma == 0.0:
            layer = feature_layers.get(field_name)
            layer_attr = f' data-layer="{esc(layer)}"' if layer else ""
            parts.append(f'<div class="band-row" data-jump="#feat-{field_name}" '
                         f'data-feature="{field_name}" role="button" tabindex="0"{layer_attr}>')
            parts.append(f'<span class="band-label">{esc(label(labels, label_key))}'
                         f'<small class="band-summary">{L("median")} {N(centre, 2)} · n = {int(base["n"])}</small></span>')
            parts.append(f'<span class="hint">{L("baseline_zero_mad")}</span></div>')
            continue
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
            f"{L('band')} {N(centre - REFERENCE_BAND_SIGMA * sigma, 2)} – {N(centre + REFERENCE_BAND_SIGMA * sigma, 2)} · "
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
                centre - REFERENCE_BAND_SIGMA * sigma,
                centre + REFERENCE_BAND_SIGMA * sigma,
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
                f'data-chapter="{strongest}"',
                f'data-metric-feature="{field_name}"',
                f'data-layer="{layer or ""}"',
                'role="button"',
                'tabindex="0"',
                f'title="{esc(title_text, quote=True)}"',
            ]
            if layer:
                count_attrs.append('data-only="1"')
            parts.append(
                f'<span class="band-count band-outlier" {" ".join(count_attrs)}>{n_out}</span>'
            )
        else:
            parts.append(f'<span class="band-count">{n_out if n_out else ""}</span>')
        parts.append("</div>")
    parts.append("</div></section>")
    return "".join(parts)
