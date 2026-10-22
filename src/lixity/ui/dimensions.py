"""Reusable style-dimension panel and its canvas data contract."""

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..format import num as format_num
from ..format import pct as format_pct
from ..format import precise_num
from ..style_fingerprint import FEATURES, LAYER_FEATURES, StyleFingerprint, dimension_loading_poles
from ..style_profile import ChapterProfile
from .components import esc, help_term, label, loading_bars, toggle_button


def style_dimensions(
    chapters: Sequence[ChapterProfile],
    fingerprint: StyleFingerprint,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    def translated(key: str, **fields: Any) -> str:
        return esc(label(labels, key).format(**fields))

    def number(value: float, decimals: int = 2, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed=signed)

    parts = ['<section class="panel" id="dimensions">',
             f"<h2>{help_term(labels, 'dimensions', translated('style_dimensions'))}</h2>",
             f'<p class="dim-guide">{translated("dim_guide")}</p>']
    diagnostics = fingerprint.dimension_diagnostics
    field_labels = {f: label_key for f, label_key, _u in FEATURES}

    def feature_name(field: str) -> str:
        return label(labels, field_labels.get(field, field))

    dim_list = fingerprint.dimensions
    if not dim_list:
        status = diagnostics.get("status", "unavailable")
        parts.append(f'<p class="dim-unavailable" role="status">{translated("dim_" + status, chapters=diagnostics.get("min_chapters", 3), features=diagnostics.get("min_features", 3))}</p>')
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
        parts.append(f'<p class="dim-coverage">{translated("dim_coverage", scored=len(points_data), total=len(chapters), features=len(features))}</p>')
    if dim_list:
        retained = diagnostics.get("retained_variance", sum(dim["variance"] for dim in dim_list))
        parts.append(f'<p class="hint" id="dim-retained">{translated("dim_retained", variance=number(retained * 100, 1))}</p>')

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
        payload = {
            "points": points_data, "threshold": threshold, "threshold_label": threshold_label,
            "axes": axes_data,
            "language": language_key if language_key != "generic" else "en",
            "labels": {key: label(labels, value) for key, value in {
                "dimension": "style_dimensions", "flagged": "dim_flagged", "status_flagged": "flagged",
                "not_flagged": "dim_not_flagged", "zero_variance": "dim_zero_variance",
                "retained": "dim_retained",
            }.items()},
        }
        parts.append('<div class="dim-layout"><div class="dim-3d-box">')
        parts.append(f'<div class="dim-3d-header"><span class="dim-3d-title">{translated("dim_3d_title")}</span><div class="dim-3d-actions">')
        for control_id, key, pressed in (
            ("dim-ctl-traj", "dim_ctl_trajectory", True),
            ("dim-ctl-corr", "dim_ctl_corridor", True),
            ("dim-ctl-spin", "dim_ctl_spin", False),
        ):
            parts.append(toggle_button(label(labels, key), control_id, pressed, "ctl ctl-sm dim-ctl"))
        parts.append(f'<button type="button" class="ctl ctl-sm dim-ctl" id="dim-ctl-reset">{translated("dim_ctl_reset")}</button></div></div>')
        parts.append(f'<div class="dim-view-control"><label for="dim-projection">{translated("dim_projection")}</label><select class="ctl dim-ctl" id="dim-projection" disabled><option value="3d">{translated("dim_3d")}</option>')
        for a in range(len(axes_data)):
            parts.extend(f'<option value="d{a + 1}-d{b + 1}">D{axes_data[a]["idx"]} / D{axes_data[b]["idx"]}</option>'
                         for b in range(a + 1, len(axes_data)))
        parts.append('</select></div>')
        parts.append(f'<div class="dim-canvas-wrap"><canvas id="dim-3d-canvas" width="800" height="440" role="img" aria-label="{translated("dim_3d_title")}" aria-describedby="dim-scores-caption" data-dim3d="{esc(json.dumps(payload, ensure_ascii=False))}"></canvas><div id="dim-3d-tooltip" class="dim-tooltip" style="display:none;"></div></div>')
        parts.append(f'<div class="dim-3d-actions dim-navigation" role="group" aria-label="{translated("dim_ctl_navigation")}">')
        for control_id, key in (
            ("dim-ctl-left", "dim_ctl_left"), ("dim-ctl-right", "dim_ctl_right"),
            ("dim-ctl-up", "dim_ctl_up"), ("dim-ctl-down", "dim_ctl_down"),
            ("dim-ctl-zoom-in", "dim_ctl_zoom_in"), ("dim-ctl-zoom-out", "dim_ctl_zoom_out"),
        ):
            parts.append(f'<button type="button" class="ctl ctl-sm dim-ctl" id="{control_id}">{translated(key)}</button>')
        parts.append(f'</div><div class="dim-3d-footer"><span>{translated("dim_3d_hint")}</span><span>{len(points_data)} / {len(chapters)} {translated("chapters")}</span></div>')
        parts.append(f'<details class="dim-cutoff"><summary>{translated("dim_score_threshold")}: |score| ≥ {threshold_label}</summary><p>{translated("dim_cutoff", threshold=threshold_label)}</p></details>')
        parts.append('</div>')
        point = points_data[0]
        parts.append(f'<div class="dim-selection-panel"><label for="dim-chapter-select">{translated("dim_choose_chapter")}</label><select class="ctl dim-ctl" id="dim-chapter-select" disabled>')
        parts.extend(f'<option value="{option["ch"]}">{option["ch"]}. {esc(option["title"])}</option>'
                     for option in points_data)
        parts.append(f'</select><p class="hint">{translated("dim_selection_help")}</p><div id="dim-selection" aria-live="polite" aria-atomic="true" data-chapter="{point["ch"]}"><strong>{point["ch"]}. {esc(point["title"])}</strong><dl class="dim-selected-scores">')
        for axis, coordinate in zip(axes_data, ("x", "y", "z"), strict=False):
            score = cast(float, point[coordinate]) or 0.0
            meaning = " / ".join(("+ " if side == "pos" else "− ") + axis[side]
                                 for side in ("pos", "neg") if axis[side])
            parts.append(f'<div><dt>D{axis["idx"]}<span class="dim-axis-meaning">{esc(meaning)}</span></dt><dd>{number(score, signed=bool(score))}</dd></div>')
        parts.append(f'</dl><p>{translated("flagged" if point["flagged"] else "dim_not_flagged")}</p></div><p class="hint">{translated("dim_score_units")}</p><a class="ctl dim-ctl" id="dim-read-chapter" href="#ch-{point["ch"]}" data-jump="#ch-{point["ch"]}">{translated("dim_read_chapter")}</a></div>')
        parts.append('</div><div class="dim-cards-col">')
        feature_layers = {field: key for key, field in LAYER_FEATURES.items()}
        for dim in dim_list:
            positive, negative = dimension_loading_poles(dim["loadings"])
            entries = [(feature_name(name), float(value)) for name, value in positive + negative]
            chip_layers = {feature_name(name): feature_layers[name]
                           for name, _ in positive + negative if name in feature_layers}
            parts.append(f'<div class="dim-card"><div class="dim-header"><span class="dim-title">{translated("style_dimensions")} {dim["index"]}</span><span class="badge">{format_pct(dim["variance"] * 100, language_key, 0)} {translated("dim_variance")}</span></div>')
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
        parts.append('<div class="table-wrap dim-score-wrap" tabindex="0" role="region" aria-labelledby="dim-scores-caption"><table id="dim-scores">'
                     f'<caption id="dim-scores-caption">{translated("dim_scores")}</caption><thead><tr><th scope="col">{translated("chapter")}</th>')
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
    parts.append(f'<details id="dim-expert"><summary>{translated("dim_expert")}</summary><p>{translated("dim_method")}</p><p>{translated("dim_limits")}</p>')
    omitted = diagnostics.get("omitted_chapters", [])
    if omitted:
        parts.append(f'<h3>{translated("dim_omitted")}</h3><ul>')
        for item in omitted:
            missing = ", ".join(feature_name(name) for name in item["missing_features"])
            parts.append(f'<li>{translated("chapter")} {item["chapter"]}: {translated("dim_missing_features")} — {esc(missing)}</li>')
        parts.append('</ul>')
    for dim in dim_list:
        parts.append(f'<h3>D{dim["index"]}</h3><div class="table-wrap" tabindex="0" role="region" aria-label="D{dim["index"]}"><table><thead><tr><th scope="col">{translated("register_target")}</th><th scope="col">{translated("dim_loading")}</th></tr></thead><tbody>')
        for name, value in sorted(dim["loadings"].items(), key=lambda item: abs(item[1]), reverse=True):
            parts.append(f'<tr><th scope="row">{esc(feature_name(name))}</th><td class="num">{number(value, 3, bool(value))}</td></tr>')
        parts.append('</tbody></table></div>')
    parts.append('</details></section>')
    return "".join(parts)
