"""Reusable exploratory segmentation, trend and distribution-shift panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..models import ChapterMetrics
from ..status import FEATURE_LAYERS, ContractKeys
from ..style_fingerprint import FEATURES, MIN_COMPARABLE_WORDS, StyleFingerprint
from ..style_profile import ChapterProfile
from .components import (
    badge,
    details_start,
    empty_state,
    esc,
    help_term,
    label,
    panel_formatters,
    panel_guide,
    panel_start,
)
from .heatmap import FEATURE_HELP_KEYS as _FEATURE_HELP


def style_structural(
    chapters: Sequence[ChapterProfile],
    fingerprint: StyleFingerprint,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *,
    chapter_metrics: Sequence[ChapterMetrics] = (),
) -> str:
    """Renders the structural diagnostics & stylistic drift panel.

    Displays guarded-cost changepoints (candidate shifts between chapters),
    Mann-Kendall monotonic trend tests (gradual drift over the book), and
    half-split distribution shifts (first half vs. second half).
    """
    diag = getattr(fingerprint, "structural_diagnostics", None)
    if diag is None:
        return ""

    translated, _N, _ = panel_formatters(labels, language_key)

    def N(value: float, decimals: int = 2, signed: bool = False) -> str:
        return _N(value, decimals, signed)

    def count_summary(tested: int, selected: int) -> str:
        if not tested:
            return ""
        text = label(labels, "structural_selection_count").format(tested=N(tested, 0), selected=N(selected, 0))
        return f'<p class="ctl-note">{esc(text)}</p>'

    field_labels = {f: label_key for f, label_key, _u in FEATURES}

    parts: list[str] = [
        panel_start("structural", labels, "panel_structural", help_key="structural"),
        panel_guide(translated("structural_guide")),
    ]

    if len(chapters) < 3:
        parts.append(empty_state(translated("structural_min_chapters")))
        parts.append("</section>")
        return "".join(parts)

    parts.append('<div class="structural-grid">')

    # --- Card 1: Guarded-cost changepoints ---
    changepoints = diag.get(ContractKeys.CHANGEPOINTS) or {}
    segmentation_unavailable = diag.get(ContractKeys.SEGMENTATION_UNAVAILABLE) or []
    segmentation_measured = (set(fingerprint._usable_features()) - set(segmentation_unavailable)) | set(changepoints)
    chapter_ids = sorted({chapter for column in fingerprint.values.values() for chapter in column})
    gaps = [
        chapter for chapter in chapter_ids
        if any(fingerprint.values.get(name, {}).get(chapter) is None for name in segmentation_unavailable)
    ]
    parts.append('<div class="structural-card">')
    parts.append(f'<h3>{help_term(labels, "changepoints", translated("structural_changepoints_title"))}</h3>')
    parts.append(count_summary(len(segmentation_measured), len(changepoints)))

    if changepoints:
        parts.append('<div class="structural-list">')
        for field_name in sorted(changepoints.keys()):
            cps = changepoints[field_name]
            feat_label = label(labels, field_labels.get(field_name, field_name))
            help_k = _FEATURE_HELP.get(field_name, field_name)
            layer = FEATURE_LAYERS.get(field_name)

            sorted_chs = sorted(
                ch for ch, value in fingerprint.values.get(field_name, {}).items()
                if value is not None
            )

            shift_links: list[str] = []
            for cp in cps:
                if cp < 0 or cp >= len(sorted_chs):
                    continue
                ch_num = sorted_chs[cp]
                link_text = label(labels, "structural_shift_from").replace("{chapter}", str(ch_num))
                layer_attr = f' data-layer="{esc(layer)}"' if layer else ""
                shift_links.append(
                    badge(
                        link_text,
                        variant="jump",
                        extra_attrs=f'data-jump="#ch-{ch_num}"{layer_attr} role="button" tabindex="0" '
                        f'title="{esc(feat_label)} · {esc(link_text)}"',
                    )
                )

            parts.append('<div class="structural-item">')
            parts.append(
                f'<span class="structural-feat">{help_term(labels, help_k, esc(feat_label))}</span>'
            )
            parts.append(f'<div class="structural-meta">{" ".join(shift_links)}</div>')
            parts.append('</div>')
        parts.append('</div>')
    else:
        status = "structural_no_changepoints" if segmentation_measured else "structural_unavailable"
        if gaps and not segmentation_measured:
            status = "structural_boundary_gap"
        parts.append(
            empty_state(translated(status), css_class="structural-empty")
        )
    if gaps:
        summary = label(labels, "structural_gap_count").format(
            observed=N(len(chapter_ids) - len(gaps), 0), total=N(len(chapter_ids), 0),
        )
        parts.append(details_start(esc(summary), opened=not segmentation_measured and len(gaps) == 1))
        words_by_chapter = {chapter.num: chapter.words for chapter in chapter_metrics}
        parts.append('<ul class="structural-gaps">')
        for chapter in gaps:
            parts.append(f'<li><a href="#ch-{chapter}" data-jump="#ch-{chapter}">{translated("chapter")} {N(chapter, 0)}</a>')
            words = words_by_chapter.get(chapter)
            if words is not None and words < MIN_COMPARABLE_WORDS:
                reason = label(labels, "structural_gap_short").format(words=N(words, 0), minimum=N(MIN_COMPARABLE_WORDS, 0))
                parts.append(f' <span class="ctl-note">· {esc(reason)}</span>')
            parts.append("</li>")
        parts.append("</ul></details>")
    elif segmentation_unavailable and segmentation_measured:
        parts.append(f'<p class="hint">{translated("structural_partly_unavailable")}</p>')
    parts.append('</div>')

    # --- Card 2: Mann-Kendall Monotonic Drift (Trends) ---
    trends = diag.get(ContractKeys.TRENDS) or {}
    trending_set = set(diag.get(ContractKeys.TRENDING_FEATURES) or [])
    parts.append('<div class="structural-card">')
    parts.append(f'<h3>{help_term(labels, "trends", translated("structural_trends_title"))}</h3>')
    parts.append(count_summary(len(trends), len(trending_set)))

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
            status_badge = badge(
                label(labels, "structural_confirmed" if is_sig else "structural_tendency"),
                variant="warn" if is_sig else "neutral",
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
            empty_state(
                translated("structural_no_trends" if trends else "structural_unavailable"),
                css_class="structural-empty",
            )
        )
    if diag.get(ContractKeys.TREND_INCOMPLETE):
        parts.append(f'<p class="hint">{translated("structural_partial_trend")}</p>')
    parts.append('</div>')

    # --- Card 3: Distribution Shift (First Half vs. Second Half) ---
    dist_shift = diag.get(ContractKeys.DISTRIBUTION_SHIFT) or {}
    shifted_set = set(diag.get(ContractKeys.SHIFTED_FEATURES) or [])
    distribution_unavailable = diag.get(ContractKeys.DISTRIBUTION_UNAVAILABLE) or []
    parts.append('<div class="structural-card">')
    parts.append(f'<h3>{help_term(labels, "distribution_shift", translated("structural_distribution_title"))}</h3>')
    parts.append(count_summary(len(dist_shift), len(shifted_set)))

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
                f'{badge(label(labels, "structural_confirmed"), variant="warn")}'
                f'</div>'
            )
            parts.append('</div>')
        parts.append('</div>')
    else:
        parts.append(
            empty_state(
                translated("structural_no_shifts" if dist_shift else "structural_unavailable"),
                css_class="structural-empty",
            )
        )
    if distribution_unavailable and dist_shift:
        parts.append(f'<p class="hint">{translated("structural_partly_unavailable")}</p>')
    if diag.get(ContractKeys.DISTRIBUTION_INCOMPLETE):
        parts.append(f'<p class="hint">{translated("structural_partial_distribution")}</p>')
    parts.append('</div>')

    parts.append('</div>')  # .structural-grid
    parts.append('</section>')
    return "".join(parts)
