"""Reusable style-dimension panel and its canvas data contract."""

import math
from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..format import pct as format_pct
from ..format import precise_num
from ..status import FEATURE_LAYERS
from ..style_fingerprint import FEATURES, StyleFingerprint, dimension_loading_poles
from ..style_profile import ChapterProfile
from .components import (
    attr_json,
    badge,
    empty_state,
    esc,
    label,
    loading_bars,
    panel_formatters,
    panel_start,
    table_wrap_start,
    toggle_button,
)


def style_dimensions(
    chapters: Sequence[ChapterProfile],
    fingerprint: StyleFingerprint,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    _L, _N, _ = panel_formatters(labels, language_key)

    def translated(key: str, **fields: Any) -> str:
        return esc(label(labels, key).format(**fields)) if fields else _L(key)

    def number(value: float, decimals: int = 2, signed: bool = False) -> str:
        return _N(value, decimals, signed)

    parts = [panel_start("dimensions", labels, "style_dimensions", help_key="dimensions")]
    diagnostics = fingerprint.dimension_diagnostics
    field_labels = {f: label_key for f, label_key, _u in FEATURES}

    def feature_name(field: str) -> str:
        return label(labels, field_labels.get(field, field))

    dim_list = fingerprint.dimensions
    if not dim_list:
        status = diagnostics.get("status", "unavailable")
        parts.append(empty_state(translated("dim_" + status, chapters=diagnostics.get("min_chapters", 3), features=diagnostics.get("min_features", 3)), css_class="dim-unavailable", role="status"))
    points_data: list[dict[str, Any]] = []
    for ch in chapters:
        if not dim_list or any(ch.num not in dim["scores"] for dim in dim_list):
            continue
        coordinates = [round(float(dim["scores"][ch.num]), 2) for dim in dim_list[:3]]
        points_data.append({
            "ch": ch.num, "title": ch.title or f"{label(labels, 'chapter')} {ch.num}",
            "x": coordinates[0], "y": coordinates[1] if len(coordinates) > 1 else 0.0,
            "z": coordinates[2] if len(coordinates) > 2 else 0.0,
            "flagged": any(ch.num in dim.get("flagged", []) for dim in dim_list),
        })
    features = diagnostics.get("features", list(dim_list[0]["loadings"]) if dim_list else [])
    if diagnostics or points_data:
        strip = [
            '<div class="chip-row dim-summary-strip">',
            badge(label(labels, "dim_coverage").format(scored=len(points_data), total=len(chapters), features=len(features)), variant="", css_class="dim-coverage"),
        ]
        if dim_list:
            retained = diagnostics.get("retained_variance", sum(dim["variance"] for dim in dim_list))
            strip.append(badge(label(labels, "dim_retained").format(variance=number(retained * 100, 1)), variant="", extra_attrs='id="dim-retained"'))
        strip.append('</div>')
        parts.extend(strip)
        if dim_list and "shrinkage_lambda" in diagnostics:
            parts.append(f'<p class="hint" id="dim-regularization">'
                         f'{translated("dim_regularization", lam=number(diagnostics["shrinkage_lambda"], 4), chapters=len(points_data), features=len(features))}</p>')

    axes_data = []
    for dim in dim_list[:3]:
        positive, negative = dimension_loading_poles(dim["loadings"])
        axes_data.append({
            "idx": dim["index"],
            "pos": feature_name(positive[0][0]) if positive else "",
            "neg": feature_name(negative[0][0]) if negative else "",
            "variance": dim["variance"],
        })
    threshold = fingerprint.thresholds.dim_score_threshold
    threshold_label = precise_num(threshold, language_key)
    if points_data:
        point = points_data[0]
        payload = {
            "points": points_data, "threshold": threshold, "threshold_label": threshold_label,
            "axes": axes_data,
            "language": language_key if language_key != "generic" else "en",
            "labels": {key: label(labels, value) for key, value in {
                "dimension": "style_dimensions", "flagged": "dim_flagged", "status_flagged": "flagged", "invalid_threshold": "dim_invalid_threshold",
                "not_flagged": "dim_not_flagged", "zero_variance": "dim_zero_variance",
                "retained": "dim_retained",
            }.items()},
        }
        parts.append('<div class="dim-layout"><div class="dim-3d-box" id="dim-3d-view">')
        parts.append(f'<div class="dim-3d-header"><span class="dim-3d-title">{translated("dim_3d_title")}</span></div>')
        parts.append(f'<p class="dim-legend-note" id="dim-fallback">{translated("dim_nojs")}</p>')
        parts.append(f'<div class="dim-view-controls"><div class="dim-view-control"><label for="dim-projection">{translated("dim_projection")}</label><select class="ctl dim-ctl" id="dim-projection" disabled><option value="3d">{translated("dim_3d")}</option>')
        for a in range(len(axes_data)):
            parts.extend(f'<option value="d{a + 1}-d{b + 1}">D{axes_data[a]["idx"]} / D{axes_data[b]["idx"]}</option>'
                         for b in range(a + 1, len(axes_data)))
        parts.append(
            '</select></div><div class="dim-view-control">'
            f'<label for="dim-chapter-select">{translated("dim_choose_chapter")}</label>'
            '<div class="dim-chapter-actions">'
            f'<select class="ctl dim-ctl" id="dim-chapter-select" data-help="{translated("dim_selection_help")}" disabled>'
        )
        parts.extend(f'<option value="{option["ch"]}">{option["ch"]}. {esc(option["title"])}</option>'
                     for option in points_data)
        parts.append(
            '</select>'
            f'<a class="ctl dim-ctl" id="dim-read-chapter" href="#ch-{point["ch"]}" data-jump="#ch-{point["ch"]}">'
            f'{translated("dim_read_chapter")}</a></div></div></div>'
        )
        parts.append('<ul id="dim-legend" class="dim-legend">')
        for glyph, key in (("chapter", "dim_legend_chapter"), ("threshold", "dim_legend_threshold"),
                           ("selected", "dim_legend_selected")):
            parts.append(f'<li><span class="dim-legend-{glyph}" aria-hidden="true"></span>{translated(key)}</li>')
        parts.append('</ul>')
        flagged_count = sum(1 for item in points_data if item["flagged"])
        summary_key = "dim_threshold_summary_one" if flagged_count == 1 else "dim_threshold_summary"
        parts.append(f'<div class="dim-threshold-controls"><p class="dim-threshold-summary" id="dim-threshold-summary">{translated(summary_key, count=flagged_count, total=len(points_data))}</p>')
        parts.append(f'<button type="button" class="ctl dim-ctl" id="dim-next-threshold" aria-describedby="dim-threshold-summary" disabled hidden>{translated("dim_next_threshold")}</button></div>')
        if len(axes_data) < 3:
            incomplete_key = "dim_incomplete_axes_one" if len(axes_data) == 1 else "dim_incomplete_axes"
            parts.append(f'<p class="dim-legend-note" id="dim-incomplete-axes">{translated(incomplete_key, count=len(axes_data))}</p>')
        missing_axes_description = " dim-incomplete-axes" if len(axes_data) < 3 else ""
        parts.append(f'<div class="dim-canvas-wrap" id="dim-canvas"><canvas id="dim-3d-canvas" width="800" height="440" role="img" aria-label="{translated("dim_3d_title")}" aria-describedby="dim-legend dim-legend-note dim-scores-caption{missing_axes_description}" data-dim3d="{attr_json(payload)}"></canvas><div id="dim-3d-tooltip" class="dim-tooltip" style="display:none;"></div></div>')
        parts.append('<div class="dim-3d-actions dim-display-options">')
        for control_id, key, pressed in (
            ("dim-ctl-traj", "dim_ctl_trajectory", True),
            ("dim-ctl-corr", "dim_ctl_corridor", True),
            ("dim-ctl-spin", "dim_ctl_spin", False),
        ):
            parts.append(toggle_button(label(labels, key), control_id, pressed, "ctl ctl-sm dim-ctl", disabled=True))
        parts.append(f'<button type="button" class="ctl ctl-sm dim-ctl" id="dim-ctl-reset" disabled>{translated("dim_ctl_reset")}</button></div>')
        parts.append(f'<div class="dim-3d-actions dim-navigation" role="group" aria-label="{translated("dim_ctl_navigation")}">')
        for control_id, key in (
            ("dim-ctl-left", "dim_ctl_left"), ("dim-ctl-right", "dim_ctl_right"),
            ("dim-ctl-up", "dim_ctl_up"), ("dim-ctl-down", "dim_ctl_down"),
            ("dim-ctl-zoom-in", "dim_ctl_zoom_in"), ("dim-ctl-zoom-out", "dim_ctl_zoom_out"),
        ):
            parts.append(f'<button type="button" class="ctl ctl-sm dim-ctl" id="{control_id}" disabled>{translated(key)}</button>')
        parts.append('</div>')
        parts.append(f'<details class="dim-cutoff"><summary>{translated("dim_score_threshold")}: |score| ≥ {threshold_label}</summary><p>{translated("dim_cutoff", threshold=threshold_label)}</p></details>')
        parts.append('</div>')
        parts.append('<div class="dim-selection-panel">')
        parts.append(f'<div id="dim-selection" aria-live="polite" aria-atomic="true" data-chapter="{point["ch"]}"><strong>{point["ch"]}. {esc(point["title"])}</strong><dl class="dim-selected-scores">')
        for axis, coordinate in zip(axes_data, ("x", "y", "z"), strict=False):
            score = cast(float, point[coordinate]) or 0.0
            meaning = " / ".join(("+ " if side == "pos" else "− ") + axis[side]
                                 for side in ("pos", "neg") if axis[side])
            parts.append(f'<div><dt>D{axis["idx"]}<span class="dim-axis-meaning">{esc(meaning)}</span></dt><dd>{number(score, signed=bool(score))}</dd></div>')
        parts.append(f'</dl><p>{translated("flagged" if point["flagged"] else "dim_not_flagged")}</p></div><p class="hint">{translated("dim_score_units")}</p></div>')
        parts.append('</div><div class="dim-cards-col">')
        for dim in dim_list:
            positive, negative = dimension_loading_poles(dim["loadings"])
            entries = [(feature_name(name), float(value)) for name, value in positive + negative]
            chip_layers = {feature_name(name): FEATURE_LAYERS[name]
                           for name, _ in positive + negative if name in FEATURE_LAYERS}
            variance_badge = badge(
                f'{format_pct(dim["variance"] * 100, language_key, 0)} {label(labels, "dim_variance")}',
                variant="",
            )
            parts.append(f'<div class="dim-card"><div class="dim-header"><span class="dim-title">{translated("style_dimensions")} {dim["index"]}</span>{variance_badge}</div>')
            axis_index = int(dim["index"]) - 1
            if 0 <= axis_index < len(fingerprint.dimension_axis_scales):
                scale = fingerprint.dimension_axis_scales[axis_index]
                ratio = threshold / scale if scale else None
                if scale is not None and ratio is not None:
                    def scale_number(value: float) -> str:
                        if value and (value < 0.005 or value >= 1e6):
                            return precise_num(float(f"{value:.3g}"), language_key)
                        return number(value)

                    ratio_label = scale_number(ratio) if math.isfinite(ratio) else "> 1e308"
                    parts.append(f'<p class="dim-meta">{translated("dim_axis_scale", scale=scale_number(scale), cutoff=ratio_label)}</p>')
                else:
                    parts.append(f'<p class="dim-meta">{translated("dim_axis_scale_unknown")}</p>')
            chip_features = {feature_name(name): name for name, _ in positive + negative}
            parts.append(loading_bars(entries, max((abs(value) for _, value in entries), default=1),
                                      layers=chip_layers, features=chip_features, dimension=dim["index"]))
            for pole, absent in ((positive, "dim_no_positive"), (negative, "dim_no_negative")):
                if not pole:
                    parts.append(f'<p class="hint">{translated(absent)}</p>')
            if dim["variance"] == 0:
                parts.append(f'<p class="hint">{translated("dim_zero_variance")}</p>')
            if dim.get("flagged"):
                flagged = ", ".join(str(ch) for ch in dim["flagged"])
                parts.append(f'<div class="dim-meta">{translated("dim_flagged")}: {esc(flagged)}</div>')
            parts.append('</div>')
        parts.append(f'</div><p class="hint">{translated("dim_poles")}</p>')
        parts.append(
            table_wrap_start(
                extra_class="dim-score-wrap",
                aria_labelledby="dim-scores-caption",
                table_id="dim-scores",
                caption_html=f'<caption id="dim-scores-caption">{translated("dim_scores")}</caption>',
            )
            + f'<thead><tr><th scope="col">{translated("chapter")}</th>'
        )
        parts.extend(f'<th scope="col">D{axis["idx"]}</th>' for axis in axes_data)
        parts.append(f'<th scope="col">{translated("dim_flagged")}</th></tr></thead><tbody>')
        for point in points_data:
            parts.append(f'<tr><th scope="row"><a class="dim-ctl dim-chapter-jump" href="#ch-{point["ch"]}" data-jump="#ch-{point["ch"]}">{point["ch"]}. {esc(point["title"])}</a></th>')
            for coordinate in ("x", "y", "z")[:len(axes_data)]:
                score = cast(float, point[coordinate]) or 0.0
                parts.append(f'<td class="num">{number(score, signed=bool(score))}</td>')
            parts.append(f'<td>{translated("flagged" if point["flagged"] else "dim_not_flagged")}</td></tr>')
        parts.append('</tbody></table></div>')
    if not points_data:
        parts.append(f'<p class="hint dim-cutoff">{translated("dim_cutoff", threshold=threshold_label)}</p>')
    parts.append(f'<details id="dim-expert"><summary>{translated("dim_expert")}</summary><p class="dim-guide">{translated("dim_guide")}</p>')
    if points_data:
        parts.append(f'<p id="dim-legend-note" class="dim-legend-note">{translated("dim_legend_note")}</p>')
        parts.append(f'<p class="hint">{translated("dim_3d_hint")}</p>')
    parts.append(f'<p>{translated("dim_method")}</p><p>{translated("dim_limits")}</p>')
    omitted = diagnostics.get("omitted_chapters", [])
    if omitted:
        parts.append(f'<h3>{translated("dim_omitted")}</h3><ul>')
        for item in omitted:
            missing = ", ".join(feature_name(name) for name in item["missing_features"])
            parts.append(f'<li>{translated("chapter")} {item["chapter"]}: {translated("dim_missing_features")} — {esc(missing)}</li>')
        parts.append('</ul>')
    for dim in dim_list:
        parts.append(
            f'<h3>D{dim["index"]}</h3>'
            + table_wrap_start(f'D{dim["index"]}')
            + f'<thead><tr><th scope="col">{translated("register_target")}</th><th scope="col">{translated("dim_loading")}</th></tr></thead><tbody>'
        )
        for name, value in sorted(dim["loadings"].items(), key=lambda item: abs(item[1]), reverse=True):
            parts.append(f'<tr><th scope="row">{esc(feature_name(name))}</th><td class="num">{number(value, 3, bool(value))}</td></tr>')
        parts.append('</tbody></table></div>')
    parts.append('</details></section>')
    return "".join(parts)
