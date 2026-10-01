"""Reusable structural diagnostics panel (PELT changepoints, Mann-Kendall drift, distribution shift)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..format import num as format_num
from ..status import ContractKeys
from ..style_fingerprint import FEATURES, LAYER_FEATURES, StyleFingerprint
from ..style_profile import ChapterProfile
from .components import esc, help_term, label
from .heatmap import FEATURE_HELP_KEYS as _FEATURE_HELP


def style_structural(
    chapters: Sequence[ChapterProfile],
    fingerprint: StyleFingerprint,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the structural diagnostics & stylistic drift panel.

    Displays PELT changepoints (structural phase shifts between chapters),
    Mann-Kendall monotonic trend tests (gradual drift over the book), and
    half-split distribution shifts (first half vs. second half).
    """
    diag = getattr(fingerprint, "structural_diagnostics", None)
    if diag is None:
        return ""

    def translated(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 2, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    field_labels = {f: label_key for f, label_key, _u in FEATURES}
    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}

    parts: list[str] = ['<section class="panel" id="structural">']
    parts.append(f"<h2>{help_term(labels, 'structural', translated('panel_structural'))}</h2>")
    parts.append(f'<p class="panel-guide">{translated("structural_guide")}</p>')

    if len(chapters) < 3:
        parts.append(f'<p class="hint">{translated("structural_min_chapters")}</p>')
        parts.append("</section>")
        return "".join(parts)

    parts.append('<div class="structural-grid">')

    # --- Card 1: PELT changepoints (Stylistic Phase Shifts) ---
    changepoints = diag.get(ContractKeys.CHANGEPOINTS) or {}
    parts.append('<div class="structural-card">')
    parts.append(
        f'<h3><span>{help_term(labels, "changepoints", translated("structural_changepoints_title"))}</span>'
        f'<span class="badge">{len(changepoints)}</span></h3>'
    )

    if changepoints:
        parts.append('<div class="structural-list">')
        for field_name in sorted(changepoints.keys()):
            cps = changepoints[field_name]
            feat_label = label(labels, field_labels.get(field_name, field_name))
            help_k = _FEATURE_HELP.get(field_name, field_name)
            layer = feature_layers.get(field_name)

            sorted_chs = sorted(fingerprint.values.get(field_name, {}).keys())

            shift_links: list[str] = []
            for cp in cps:
                ch_num = sorted_chs[cp] if cp < len(sorted_chs) else (cp + 1)
                link_text = label(labels, "structural_shift_from").replace("{chapter}", str(ch_num))
                layer_attr = f' data-layer="{esc(layer)}"' if layer else ""
                shift_links.append(
                    f'<span class="badge badge-jump" data-jump="#ch-{ch_num}"{layer_attr} '
                    f'role="button" tabindex="0" title="{esc(feat_label)} · {esc(link_text)}">'
                    f'{esc(link_text)}</span>'
                )

            parts.append('<div class="structural-item">')
            parts.append(
                f'<span class="structural-feat">{help_term(labels, help_k, esc(feat_label))}</span>'
            )
            parts.append(f'<div class="structural-meta">{" ".join(shift_links)}</div>')
            parts.append('</div>')
        parts.append('</div>')
    else:
        parts.append(
            f'<div class="structural-empty"><span class="badge badge-success">✓</span> '
            f'<span>{translated("structural_no_changepoints")}</span></div>'
        )
    parts.append('</div>')

    # --- Card 2: Mann-Kendall Monotonic Drift (Trends) ---
    trends = diag.get(ContractKeys.TRENDS) or {}
    trending_set = set(diag.get(ContractKeys.TRENDING_FEATURES) or [])
    parts.append('<div class="structural-card">')
    parts.append(
        f'<h3><span>{help_term(labels, "trends", translated("structural_trends_title"))}</span>'
        f'<span class="badge">{len(trending_set)}</span></h3>'
    )

    sorted_trends = sorted(
        trends.items(),
        key=lambda kv: (0 if kv[0] in trending_set else 1, -abs(float(kv[1].get("tau", 0.0)))),
    )

    significant_or_salient = [
        (f, t) for f, t in sorted_trends if f in trending_set or abs(float(t.get("tau", 0.0))) >= 0.4
    ]

    if significant_or_salient:
        parts.append('<div class="structural-list">')
        for field_name, t_info in significant_or_salient:
            feat_label = label(labels, field_labels.get(field_name, field_name))
            help_k = _FEATURE_HELP.get(field_name, field_name)
            tau = float(t_info.get("tau", 0.0))
            p_val = float(t_info.get("p", 1.0))
            is_sig = field_name in trending_set

            direction_key = "structural_trend_up" if tau > 0 else "structural_trend_down"
            dir_text = label(labels, direction_key)
            status_badge = (
                f'<span class="badge badge-warn">{translated("structural_confirmed")}</span>'
                if is_sig
                else f'<span class="badge badge-neutral">{translated("structural_tendency")}</span>'
            )

            parts.append('<div class="structural-item">')
            parts.append(
                f'<span class="structural-feat">{help_term(labels, help_k, esc(feat_label))}</span>'
            )
            parts.append(
                f'<div class="structural-meta">'
                f'<span class="structural-trend {esc("trend-up" if tau > 0 else "trend-down")}">{esc(dir_text)}</span> '
                f'<span>τ={N(tau, 2, signed=True)}</span> '
                f'<span>p={N(p_val, 3)}</span> '
                f'{status_badge}'
                f'</div>'
            )
            parts.append('</div>')
        parts.append('</div>')
    else:
        parts.append(
            f'<div class="structural-empty"><span class="badge badge-success">✓</span> '
            f'<span>{translated("structural_no_trends")}</span></div>'
        )
    parts.append('</div>')

    # --- Card 3: Distribution Shift (First Half vs. Second Half) ---
    dist_shift = diag.get(ContractKeys.DISTRIBUTION_SHIFT) or {}
    shifted_set = set(diag.get(ContractKeys.SHIFTED_FEATURES) or [])
    parts.append('<div class="structural-card">')
    parts.append(
        f'<h3><span>{help_term(labels, "distribution_shift", translated("structural_distribution_title"))}</span>'
        f'<span class="badge">{len(shifted_set)}</span></h3>'
    )

    if shifted_set:
        parts.append('<div class="structural-list">')
        for field_name in sorted(shifted_set):
            info = dist_shift.get(field_name, {})
            feat_label = label(labels, field_labels.get(field_name, field_name))
            help_k = _FEATURE_HELP.get(field_name, field_name)
            w1 = float(info.get("wasserstein", 0.0))
            ks_p = float(info.get("ks_p", 1.0))

            parts.append('<div class="structural-item">')
            parts.append(
                f'<span class="structural-feat">{help_term(labels, help_k, esc(feat_label))}</span>'
            )
            parts.append(
                f'<div class="structural-meta">'
                f'<span>W₁={N(w1, 2)}</span> '
                f'<span>p={N(ks_p, 3)}</span> '
                f'<span class="badge badge-warn">{translated("structural_confirmed")}</span>'
                f'</div>'
            )
            parts.append('</div>')
        parts.append('</div>')
    else:
        parts.append(
            f'<div class="structural-empty"><span class="badge badge-success">✓</span> '
            f'<span>{translated("structural_no_shifts")}</span></div>'
        )
    parts.append('</div>')

    parts.append('</div>')  # .structural-grid
    parts.append('</section>')
    return "".join(parts)
