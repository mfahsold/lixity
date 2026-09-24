"""Reusable style-dimension panel and its canvas data contract."""

import json
from collections.abc import Mapping, Sequence

from ..format import pct as format_pct
from ..style_fingerprint import FEATURES, LAYER_FEATURES, StyleFingerprint
from ..style_profile import ChapterProfile
from .components import esc, help_term, label, loading_bars, toggle_button


def style_dimensions(
    chapters: Sequence[ChapterProfile],
    fingerprint: StyleFingerprint,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    if not fingerprint.dimensions:
        return ""

    def translated(key: str) -> str:
        return esc(label(labels, key))

    def percent(value: float, decimals: int) -> str:
        return format_pct(value, language_key, decimals)

    parts: list[str] = []
    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}
    parts.append('<section class="panel" id="dimensions">')
    parts.append(f"<h2>{help_term(labels, 'dimensions', translated('style_dimensions'))}</h2>")
    field_labels = {f: label_key for f, label_key, _u in FEATURES}

    dim_list = fingerprint.dimensions
    d1 = dim_list[0]
    d2 = dim_list[1] if len(dim_list) > 1 else None
    d3 = dim_list[2] if len(dim_list) > 2 else None

    flagged_set = set(d1.get("flagged", []))
    if d2:
        flagged_set.update(d2.get("flagged", []))
    if d3:
        flagged_set.update(d3.get("flagged", []))

    points_data = []
    for ch in chapters:
        sx = round(float(d1["scores"].get(ch.num, 0.0)), 2)
        sy = round(float(d2["scores"].get(ch.num, 0.0)), 2) if d2 else 0.0
        sz = round(float(d3["scores"].get(ch.num, 0.0)), 2) if d3 else 0.0
        points_data.append(
            {
                "ch": ch.num,
                "title": ch.title or f"{translated('chapter')} {ch.num}",
                "x": sx,
                "y": sy,
                "z": sz,
                "flagged": ch.num in flagged_set,
            }
        )

    axes_data = []
    for d in [d1, d2, d3]:
        if not d:
            continue
        loadings = d["loadings"]
        top_pos_f = max(loadings.items(), key=lambda kv: kv[1])[0]
        top_neg_f = min(loadings.items(), key=lambda kv: kv[1])[0]
        axes_data.append(
            {
                "idx": d["index"],
                "pos": label(labels, field_labels.get(top_pos_f, top_pos_f)),
                "neg": label(labels, field_labels.get(top_neg_f, top_neg_f)),
            }
        )

    dim_3d_payload = {
        "points": points_data,
        "threshold": float(fingerprint.thresholds.dim_score_threshold),
        "axes": axes_data,
        "language": language_key if language_key != "generic" else "en",
        "labels": {
            "dimension": label(labels, "style_dimensions"),
            "flagged": label(labels, "dim_flagged"),
        },
    }
    dim_3d_json = json.dumps(dim_3d_payload, ensure_ascii=False)

    parts.append('<div class="dim-layout">')
    parts.append('<div class="dim-3d-box">')
    parts.append(
        f'<div class="dim-3d-header">'
        f'<span class="dim-3d-title">{translated("dim_3d_title")}</span>'
        f'<div class="dim-3d-actions">'
    )
    for control_id, key, pressed in (
        ("dim-ctl-traj", "dim_ctl_trajectory", True),
        ("dim-ctl-corr", "dim_ctl_corridor", True),
        ("dim-ctl-spin", "dim_ctl_spin", False),
    ):
        parts.append(toggle_button(label(labels, key), control_id, pressed, "dim-ctl"))
    parts.append(
        f'<button type="button" class="dim-ctl" id="dim-ctl-reset" title="{translated("dim_ctl_reset")}">{translated("dim_ctl_reset")}</button>'
        f"</div></div>"
    )
    parts.append(
        f'<div class="dim-canvas-wrap">'
        f'<canvas id="dim-3d-canvas" width="800" height="440" '
        f'role="img" aria-label="{translated("dim_3d_title")}" '
        f'data-dim3d="{esc(dim_3d_json)}"></canvas>'
        f'<div id="dim-3d-tooltip" class="dim-tooltip" style="display:none;"></div>'
        f"</div>"
    )
    parts.append(f'<div class="dim-3d-footer"><span>{translated("dim_3d_hint")}</span></div>')
    parts.append("</div>")

    parts.append('<div class="dim-cards-col">')
    for dim in fingerprint.dimensions:
        dim_loadings = dim["loadings"]
        top_pos = sorted(
            ((field, value) for field, value in dim_loadings.items() if value > 0),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        top_neg = sorted(
            ((field, value) for field, value in dim_loadings.items() if value < 0),
            key=lambda item: item[1],
        )[:3]
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
            f'<div class="dim-header"><span class="dim-title">{translated("style_dimensions")} {dim["index"]}</span>'
            f'<span class="badge">{percent(dim["variance"] * 100, 0)} {translated("dim_variance")}</span></div>'
        )
        parts.append(loading_bars(entries, limit, layers=chip_layers))
        if flagged:
            ch_label = translated("chapter")
            if len(flagged) <= 8:
                flagged_str = ", ".join(f"{ch_label} {ch}" for ch in flagged)
            else:
                first_few = ", ".join(f"{ch_label} {ch}" for ch in flagged[:6])
                flagged_str = f"{first_few} (+{len(flagged) - 6})"
            parts.append(f'<div class="dim-meta">{translated("dim_flagged")}: {flagged_str}</div>')
        parts.append("</div>")
    parts.append("</div>")
    parts.append("</div>")
    parts.append("</section>")
    return "".join(parts)
