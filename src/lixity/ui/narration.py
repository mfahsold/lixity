"""Reusable narration panels (sentence distribution, dialogue, characters, pacing, motifs, showing)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from itertools import pairwise
from typing import Any

from ..dialogue import LONG_TURN_MIN_WORDS, SHORT_TURN_MAX_WORDS
from ..diversity import MIN_TOKENS_LD
from ..format import num as format_num
from ..format import pct as format_pct
from ..models import CorpusMetrics
from ..motifs import MAX_DISPLAY_OCCURRENCES
from ..pacing import HOOK_SHORT_SENTENCE, sentence_group_intervals
from ..showing import MIN_COMPARISON_CHAPTERS
from ..style_fingerprint import FEATURE_UNITS, FEATURES, MIN_COMPARABLE_WORDS
from ..style_profile import ChapterProfile
from .components import (
    action_strip,
    attr_json,
    badge,
    chapter_link,
    checkbox_field,
    details_start,
    dist_row,
    esc,
    help_term,
    kpi,
    kpi_row,
    label,
    panel_formatters,
    panel_guide,
    panel_label,
    panel_start,
    status_banner,
    table_wrap_start,
)


def render_scenes_panel(
    scenes: Mapping[str, Any] | None, labels: Mapping[str, str] | None,
    language_key: str = "en",
) -> str:
    """Show scene observations, sample support and author-defined comparisons."""
    if not scenes:
        return ""
    if scenes.get("error"):
        return (panel_start("scenes", labels, "panel_scenes") +
                f'<p role="status">{esc(label(labels, "scene_error_summary"))}</p>'
                f'<details><summary>{esc(label(labels, "scene_error_details"))}</summary>'
                f'<p>{esc(scenes["error"])}</p></details></section>')
    items = scenes.get("items")
    if items is None:
        return ""
    if not items and not scenes.get("planned_items"):
        return (panel_start("scenes", labels, "panel_scenes")
                + panel_guide(esc(label(labels, "scene_no_measurements"))) + "</section>")

    _L, _N, _ = panel_formatters(labels, language_key)

    def L(key: str) -> str:
        return esc(label(labels, key).replace("{min_tokens}", str(MIN_TOKENS_LD))) if key == "scene_support" else _L(key)

    def N(value: Any) -> str:
        return "—" if value is None else _N(value, 2)

    parts = [panel_start("scenes", labels, "panel_scenes"),
             f'<p class="hint">{L("scene_guidance")}</p>',
             f'<p class="hint">{L("scene_support")}</p>']
    # Keep comparisons visible, with one reversible catalogue for the detailed
    # tables rather than a second full list of scene summaries in the overview.
    asl_unit = esc(FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])["asl"])
    dialog_key = next(label_key for field, label_key, _unit in FEATURES if field == "dialog_pct")
    has_hooks = any("entry_hook_type" in item or "exit_hook_type" in item for item in scenes["items"])

    def _hook_text(hook_type: Any) -> str:
        key = f"hook_type_{hook_type}" if hook_type in {"dialogue", "action", "reflection", "question", "unknown"} else "hook_type_unknown"
        return label(labels, key)

    def _hook_label(hook_type: Any) -> str:
        return esc(_hook_text(hook_type))

    hook_dist = scenes.get("hook_distribution")
    if isinstance(hook_dist, Mapping) and (hook_dist.get("entry") or hook_dist.get("exit")):
        entry_parts = [f"{_hook_label(k)}: {int(v)}" for k, v in (hook_dist.get("entry") or {}).items() if v]
        exit_parts = [f"{_hook_label(k)}: {int(v)}" for k, v in (hook_dist.get("exit") or {}).items() if v]
        summary_bits: list[str] = []
        if entry_parts:
            summary_bits.append(f'{L("scene_entry_hook")}: {", ".join(entry_parts)}')
        if exit_parts:
            summary_bits.append(f'{L("scene_exit_hook")}: {", ".join(exit_parts)}')
        if summary_bits:
            parts.append(f'<p class="hint">{" · ".join(summary_bits)}</p>')

    plateaus = scenes.get("pacing_plateaus") or []
    if plateaus:
        plateau_bits = []
        for plateau in plateaus:
            reason_raw = str(plateau.get("reason", "flat_pacing"))
            reason_key = f"scene_plateau_{reason_raw}" if reason_raw in {"low_exit_hooks", "flat_pacing"} else "scene_plateau_flat_pacing"
            plateau_bits.append(
                f'{esc(str(plateau.get("start_id", "")))}–{esc(str(plateau.get("end_id", "")))} '
                f'({int(plateau.get("scene_count", 0))}, {N(plateau.get("mean_asl"))} {asl_unit}, {L(reason_key)})'
            )
        parts.append(
            f'<p class="hint scene-plateaus-warning" role="status">'
            f'<strong>{L("scene_pacing_plateaus")}:</strong> {" · ".join(plateau_bits)}</p>'
        )

    has_dynamics = any("scene_dynamic" in item for item in scenes["items"])
    has_showing_rates = any(
        "filter_per_1000" in item or "sensory_per_1000" in item
        for item in scenes["items"]
    )

    if scenes["items"]:
        hook_headers = (
            f'<th scope="col">{L("scene_entry_hook")}</th>'
            f'<th scope="col">{L("scene_exit_hook")}</th>'
            if has_hooks
            else ""
        )
        dynamic_header = f'<th scope="col">{L("scene_dynamic")}</th>' if has_dynamics else ""
        showing_headers = (
            f'<th scope="col" class="num">{L("scene_filter_per_1000")}</th>'
            f'<th scope="col" class="num">{L("scene_sensory_per_1000")}</th>'
            if has_showing_rates
            else ""
        )
        parts.append(
            table_wrap_start(label(labels, "panel_scenes"), extra_class="scene-overview")
            + '<thead><tr>'
            f'<th scope="col">{L("panel_scenes")}</th><th scope="col" class="num">{L("words")}</th>'
            f'<th scope="col" class="num">{L("sentences")}</th>'
            f'<th scope="col" class="num">{asl_unit}</th><th scope="col" class="num">{L(dialog_key)}</th>'
            f'{hook_headers}{dynamic_header}{showing_headers}</tr></thead><tbody>'
        )
    for item in scenes["items"]:
        group_raw = item["group"] or label(labels, "scene_unassigned")
        group_badge = badge(group_raw, variant="register" if item["group"] else "neutral")
        pov_chars = item.get("pov_characters") or []
        pov_badge = (
            " " + badge(f'{label(labels, "scene_pov")}: {", ".join(str(c) for c in pov_chars)}')
            if pov_chars
            else ""
        )
        dialog = item["features"].get("dialog_pct")
        dialog_text = "—" if dialog is None else f"{format_num(dialog, language_key, 1)} %"
        target = f'scene-metrics-{item["chapter"]}-{item["scene"]}'
        hook_cells = ""
        if has_hooks:
            entry_t = item.get("entry_hook_type")
            exit_t = item.get("exit_hook_type")
            exit_score = item.get("exit_hook_score")
            entry_cell = badge(_hook_text(entry_t)) if entry_t else "—"
            if exit_t:
                score_txt = f" · {int(exit_score)}/3" if exit_score is not None else ""
                exit_cell = badge(f"{_hook_text(exit_t)}{score_txt}")
            else:
                exit_cell = "—"
            hook_cells = f"<td>{entry_cell}</td><td>{exit_cell}</td>"
        dynamic_cell = ""
        if has_dynamics:
            dyn_raw = item.get("scene_dynamic")
            if dyn_raw in {"accelerating", "decelerating", "dialogue_surge", "steady", "insufficient_length"}:
                dynamic_cell = f'<td>{badge(label(labels, "scene_dynamic_" + dyn_raw))}</td>'
            else:
                dynamic_cell = "<td>—</td>"
        showing_cells = ""
        if has_showing_rates:
            showing_cells = (
                f'<td class="num">{N(item.get("filter_per_1000"))}</td>'
                f'<td class="num">{N(item.get("sensory_per_1000"))}</td>'
            )
        parts.append(
            f'<tr><th><a href="#{esc(target)}" data-jump="#{esc(target)}">'
            f'{esc(item["chapter_title"])} · {L("scene_unit")} {item["scene"]}'
            f'</a> {group_badge}{pov_badge}</th>'
            f'<td>{item["words"]}</td><td>{item["sentences"]}</td>'
            f'<td>{N(item["features"].get("asl"))}</td><td>{dialog_text}</td>{hook_cells}{dynamic_cell}{showing_cells}</tr>'
        )
    if scenes["items"]:
        parts.append('</tbody></table></div>')
        parts.append(details_start(f'{L("scene_measurements")} ({len(scenes["items"])})',
                                   extra_class="scene-measurements"))
    # Comparison columns only appear when the project actually defines targets
    # or register medians; otherwise every cell would repeat a dash.
    has_targets = any(
        item["targets"].get(field)
        for item in scenes["items"]
        for field, _label_key, _unit in FEATURES
    )
    has_baseline = any(scenes["baselines"].get(item["group"]) for item in scenes["items"])
    for item in scenes["items"]:
        group = esc(item["group"]) if item["group"] else L("scene_unassigned")
        parts.append(f'<details class="scene-detail" data-scene="{esc(item["id"])}"><summary>'
                     f'{esc(item["chapter_title"])} · {L("scene_unit")} {item["scene"]} · {group}'
                     f' · {L("words")}: {item["words"]} · {L("sentences")}: {item["sentences"]}'
                     '</summary>')
        parts.append(f'<p><a class="ctl-link" href="#ch-{item["chapter"]}" data-jump="#ch-{item["chapter"]}">'
                     f'{L("scene_containing_chapter")}: {esc(item["chapter_title"])}→</a></p>')
        header = (f'<th>{L("panel_scenes")}</th><th>{L("scene_value")}</th>'
                  f'<th>{L("scene_se")}</th>')
        if has_targets:
            header += f'<th>{L("scene_range")}</th>'
        if has_baseline:
            header += f'<th>{L("scene_baseline")}</th>'
        target = f'scene-metrics-{item["chapter"]}-{item["scene"]}'
        parts.append(
            table_wrap_start(
                f'{label(labels, "scene_measurements")} · {item["id"]}',
                wrap_id=target,
            )
            + f'<thead><tr>{header}</tr></thead><tbody>'
        )
        baseline = scenes["baselines"].get(item["group"], {})
        for field, label_key, unit in FEATURES:
            units = FEATURE_UNITS.get(language_key, {}).get(field, unit)
            row = (f'<tr><th>{L(label_key)} <small>{esc(units)}</small></th>'
                   f'<td>{N(item["features"][field])}</td>'
                   f'<td>{N(item["standard_errors"].get(field))}</td>')
            if has_targets:
                target = item["targets"].get(field)
                comparison = "—"
                if target:
                    lower = "…" if target["lower"] is None else N(target["lower"])
                    upper = "…" if target["upper"] is None else N(target["upper"])
                    comparison = f'{lower} – {upper} · {L("scene_" + target["position"])}'
                row += f'<td>{comparison}</td>'
            if has_baseline:
                reference = baseline.get(field, {})
                row += f'<td>{N(reference.get("median"))} <small class="text-muted">(n={reference.get("n", 0)})</small></td>'
            parts.append(row + "</tr>")
        parts.append('</tbody></table></div></details>')
    if scenes["items"]:
        parts.append('</details>')
    if scenes.get("planned_items"):
        parts.append(f'<details class="scene-planned"><summary>{L("scene_planned")} '
                     f'({len(scenes["planned_items"])})</summary><p>{L("scene_planned_note")}</p><ul>')
        parts.extend(f'<li>{esc(item["id"])} · {esc(item["group"])}</li>' for item in scenes["planned_items"])
        parts.append('</ul></details>')
    implicit_breaks = scenes.get("implicit_breaks") or []
    if implicit_breaks:
        def _cue_label(cue_raw: Any) -> str:
            cues = [c.strip() for c in str(cue_raw or "").split("+") if c.strip()]
            translated = [
                L(f"scene_cue_{c}") if c in {"time", "place", "character", "cohesion_drop"} else esc(c)
                for c in cues
            ]
            return " + ".join(translated) if translated else "–"

        parts.append(
            f'<details class="scene-implicit-breaks"><summary>{L("scene_implicit_breaks")} '
            f'({len(implicit_breaks)})</summary>'
            f'<p class="hint">{L("scene_implicit_breaks_hint")}</p><ul>'
        )
        for brk in implicit_breaks[:30]:
            ch_num = int(brk.get("chapter", 0))
            scene_num = int(brk.get("scene", 0))
            para_idx = int(brk.get("paragraph_index", 0))
            cue_text = _cue_label(brk.get("cue_type"))
            sim = brk.get("cohesion_similarity")
            sim_badge = (
                f' <span class="badge badge-neutral">{L("scene_cohesion_similarity")} {N(float(sim))}</span>'
                if sim is not None
                else ""
            )
            snippet = esc(str(brk.get("snippet", "")))
            ch_label = f'{L("chapter")} {ch_num} · {L("scene_unit")} {scene_num}'
            ch_html = chapter_link(ch_num, ch_label) if ch_num > 0 else esc(ch_label)
            parts.append(
                f'<li>{ch_html} '
                f'<span class="badge badge-neutral">{L("scene_paragraph")} {para_idx} · {cue_text}</span>'
                f'{sim_badge} '
                f'<span class="text-muted">{snippet}</span></li>'
            )
        parts.append("</ul></details>")
    parts.append('</section>')
    return "".join(parts)


def _sentence_group_attrs(
    interval: tuple[int, int | None] | None,
    *,
    label_text: str,
    count_positive: bool,
    group_key: str = "",
) -> str:
    if interval is None or not count_positive:
        return ""
    min_w, max_w = interval
    max_attr = f' data-rhythm-max-words="{max_w}"' if max_w is not None else ""
    group_attr = f' data-rhythm-group="{esc(group_key, quote=True)}"' if group_key else ""
    return (
        f' data-rhythm-min-words="{min_w}"{max_attr}{group_attr}'
        f' data-rhythm-label="{esc(label_text, quote=True)}"'
    )


def _sentence_group_labels(
    keys: Sequence[str], bounds: Sequence[int] | None,
    L: Callable[[str], str], N: Callable[..., str],
) -> list[str]:
    names = [L("sentence_group_" + key) for key in keys]
    if bounds is None:
        return names
    words = L("words")
    first_unit = L("words_one") if bounds[0] == 1 else words
    ranges = [f"≤ {N(bounds[0], 0)} {first_unit}"]
    ranges.extend(
        f"{N(left + 1, 0)}–{N(right, 0)} {words}" if left < right else L("sentence_group_empty")
        for left, right in pairwise(bounds)
    )
    ranges.append(f"> {N(max(bounds), 0)} {words}")
    return [f"{name} ({length})" for name, length in zip(names, ranges, strict=True)]


def render_sentence_dist_panel(
    metrics: CorpusMetrics | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *,
    embedded: bool = False,
) -> str:
    """Renders the sentence-length distribution panel (standalone or embedded in rhythm)."""
    if metrics is None:
        return ""

    L, N, P = panel_formatters(labels, language_key)

    d = metrics.sentence_dist
    dist_keys = ("short", "medium", "long", "very_long")
    groups = _sentence_group_labels(dist_keys, d._word_bounds, L, N)
    intervals = sentence_group_intervals(d._word_bounds) or [None] * len(groups)
    values = [(d.short_count, d.short_pct), (d.medium_count, d.medium_pct),
              (d.long_count, d.long_pct), (d.complex_count, d.complex_pct)]
    parts = (
        [f'<div class="rhythm-sentence-dist" id="dist"><h3>{L("sentence_dist")}</h3>']
        if embedded
        else [panel_start("dist", labels, "sentence_dist")]
    )
    parts.append(panel_guide(L("analysis_sentence_dist_guide")))
    if d._word_bounds is None:
        parts.append(f'<p class="ctl-note">{L("sentence_group_bounds_unavailable")}</p>')
    parts.append('<div class="dist">')
    jump_label = L("rhythm_open_sentences")
    for group_key, group, interval, (count, pct) in zip(dist_keys, groups, intervals, values, strict=True):
        attrs = _sentence_group_attrs(
            interval,
            label_text=group,
            count_positive=count > 0,
            group_key=group_key,
        )
        jump_btn = (
            f'<button type="button" class="ctl ctl-sm rhythm-jump-btn"{attrs} hidden="hidden">{jump_label}</button>'
            if attrs
            else ""
        )
        parts.append(
            f'<div class="row"{attrs}><span class="label">{group}</span>'
            f'<span class="bar" aria-hidden="true"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></span>'
            f'<span class="val">{N(count, 0)} · {P(pct)}</span>{jump_btn}</div>'
        )
    parts.append("</div>")
    verb_mattr = getattr(metrics, "verb_mattr", None)
    desc_mattr = getattr(metrics, "desc_mattr", None)
    if verb_mattr is not None or desc_mattr is not None:
        tiles = []
        if verb_mattr is not None:
            tiles.append(kpi(N(verb_mattr, 3), help_term(labels, "lex_action", L("lex_action_mattr"))))
        if desc_mattr is not None:
            tiles.append(kpi(N(desc_mattr, 3), help_term(labels, "lex_desc", L("lex_desc_mattr"))))
        parts.extend((details_start(L("analysis_sentence_dist_vocabulary")), kpi_row(tiles), "</details>"))
    parts.append("</div>" if embedded else "</section>")
    return "".join(parts)


def render_dialogue_panel(
    dialogue: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *,
    counted_text_available: bool = False,
) -> str:
    """Render recognized quoted spans and their manuscript word shares."""
    if not dialogue:
        return ""

    L, N, P = panel_formatters(labels, language_key)

    parts = [
        panel_start("dialogue", labels, "panel_dialogue"),
        panel_guide(L("analysis_dialogue_guide")),
        kpi_row([
            kpi(N(dialogue.get("turns", 0), 0), L("dlg_turns")),
            kpi(P(dialogue.get("dialogue_pct", 0.0)),
                help_term(labels, "dialogue", L("analysis_dialogue_share"))),
        ]),
    ]
    tiles = [
        kpi(N(dialogue.get("avg_turn_words", 0.0), 1), L("dlg_avg_turn"), jump="#chapters"),
        kpi(N(dialogue.get("turns_per_1000", 0.0), 1), L("dlg_turns_per_1000"), jump="#chapters"),
    ]
    if "short_turn_pct" in dialogue:
        short_label = esc(
            label(labels, "dlg_short_turns").replace("{max_words}", str(SHORT_TURN_MAX_WORDS))
        )
        tiles.append(
            kpi(
                P(float(dialogue.get("short_turn_pct", 0.0))),
                help_term(
                    labels,
                    "dlg_short_turns",
                    short_label,
                    fields={"max_words": str(SHORT_TURN_MAX_WORDS)},
                ),
            )
        )
    if "long_turns" in dialogue:
        long_label = esc(
            label(labels, "dlg_long_turns").replace("{min_words}", str(LONG_TURN_MIN_WORDS))
        )
        tiles.append(
            kpi(
                N(int(dialogue.get("long_turns", 0)), 0),
                help_term(
                    labels,
                    "dlg_long_turns",
                    long_label,
                    fields={"min_words": str(LONG_TURN_MIN_WORDS)},
                ),
            )
        )
    if "asl_contrast" in dialogue or "dialogue_asl" in dialogue:
        contrast_raw = dialogue.get("asl_contrast")
        contrast_val = (
            N(float(contrast_raw), 1, signed=True) if contrast_raw is not None else "–"
        )
        tiles.append(
            kpi(
                contrast_val,
                help_term(labels, "dlg_voice_contrast", L("dlg_voice_contrast")),
            )
        )
    if dialogue.get("dialogue_tag_available"):
        tiles.append(
            kpi(
                N(float(dialogue.get("dialogue_tags_per_1000", 0.0)), 1),
                L("dlg_tags_per_1000"),
            )
        )
        tiles.append(
            kpi(
                f'{N(int(dialogue.get("dialogue_tags", 0)), 0)} ({P(float(dialogue.get("dialogue_tag_pct", 0.0)))})',
                L("dlg_tags"),
            )
        )
    if dialogue.get("adverbial_tag_available"):
        tiles.append(
            kpi(
                f'{N(int(dialogue.get("adverbial_tags", 0)), 0)} ({P(float(dialogue.get("adverbial_tag_pct", 0.0)))})',
                L("dlg_adverbial_tags"),
            )
        )
    if dialogue.get("indirect_speech_available"):
        tiles.append(
            kpi(
                N(int(dialogue.get("indirect_speech", 0)), 0),
                L("dlg_indirect_speech"),
            )
        )
        tiles.append(
            kpi(
                N(float(dialogue.get("indirect_speech_per_1000", 0.0)), 1),
                L("dlg_indirect_speech_per_1000"),
            )
        )
    voice_sep = dialogue.get("voice_separation")
    if isinstance(voice_sep, Mapping) and voice_sep.get("available"):
        sep_raw = str(voice_sep.get("separation_label", "unavailable"))
        sep_key = f"dlg_voice_sep_{sep_raw}" if sep_raw in {"distinct", "moderate", "blended", "unavailable"} else "dlg_voice_sep_unavailable"
        tiles.append(
            kpi(
                L(sep_key),
                L("dlg_voice_separation"),
            )
        )
    dialogue_chapters = dialogue.get("chapters", [])
    if dialogue_chapters:
        reading_guide = label(labels, "analysis_dialogue_reading_guide")
        if counted_text_available:
            reading_guide += " " + label(labels, "analysis_dialogue_counted_guide").format(
                counted_text=label(labels, "legend_counted_text"),
            )
        parts.append(panel_guide(esc(reading_guide)))
        parts.append('<div class="dist scrollable">')
        for chapter in dialogue_chapters:
            num = int(chapter.get("chapter_num", 0))
            turns = int(chapter.get("turns", 0))
            turns_label = L("dlg_turns_one" if turns == 1 else "dlg_turns")
            share = float(chapter.get("dialogue_pct", 0.0))
            chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
            parts.append(
                dist_row(
                    num,
                    chapter_label,
                    min(100.0, share),
                    f"{P(share)} · {turns} {turns_label}",
                    layer="dialogue",
                    title_text=chapter.get("title", ""),
                )
            )
        parts.append("</div>")
        if any("short_turn_pct" in ch or "dialogue_asl" in ch for ch in dialogue_chapters):
            has_ch_tags = any("dialogue_tags_per_1000" in ch for ch in dialogue_chapters)
            has_ch_indirect = any("indirect_speech_per_1000" in ch for ch in dialogue_chapters)
            short_col = esc(
                label(labels, "dlg_short_turns").replace("{max_words}", str(SHORT_TURN_MAX_WORDS))
            )
            long_col = esc(
                label(labels, "dlg_long_turns").replace("{min_words}", str(LONG_TURN_MIN_WORDS))
            )
            tags_th = f'<th scope="col" class="num">{L("dlg_tags_per_1000")}</th>' if has_ch_tags else ""
            indirect_th = f'<th scope="col" class="num">{L("dlg_indirect_speech_per_1000")}</th>' if has_ch_indirect else ""
            parts.append(details_start(f'{L("dlg_chapter_details")} ({len(dialogue_chapters)})',
                                       extra_class="dialogue-measurements"))
            parts.append(
                table_wrap_start(label(labels, "dlg_chapter_details"))
                + "<thead><tr>"
                f'<th scope="col">{L("chapter")}</th>'
                f'<th scope="col" class="num">{L("dlg_turns")}</th>'
                f'<th scope="col" class="num">{short_col}</th>'
                f'<th scope="col" class="num">{long_col}</th>'
                f'<th scope="col" class="num">{L("dlg_dialogue_asl")}</th>'
                f'<th scope="col" class="num">{L("dlg_narration_asl")}</th>'
                f'<th scope="col" class="num">{L("dlg_voice_contrast")}</th>'
                f"{tags_th}{indirect_th}"
                "</tr></thead><tbody>"
            )
            for chapter in dialogue_chapters:
                num = int(chapter.get("chapter_num", 0))
                turns = int(chapter.get("turns", 0))
                short_turns = int(chapter.get("short_turns", 0))
                short_pct = float(chapter.get("short_turn_pct", 0.0))
                long_turns = int(chapter.get("long_turns", 0))
                dlg_asl = float(chapter.get("dialogue_asl", 0.0))
                nar_asl = float(chapter.get("narration_asl", 0.0))
                ch_contrast = chapter.get("asl_contrast")
                chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
                if ch_contrast is not None:
                    cval = float(ch_contrast)
                    cls = "val-positive" if cval > 0 else ("val-negative" if cval < 0 else "")
                    contrast_cell = f'<span class="{cls}">{N(cval, 1, signed=True)}</span>'
                else:
                    contrast_cell = '<span class="text-muted">–</span>'
                tags_cell = (
                    f'<td class="num">{N(float(chapter["dialogue_tags_per_1000"]), 1) if chapter.get("dialogue_tags_per_1000") is not None else "–"}</td>'
                    if has_ch_tags
                    else ""
                )
                indirect_cell = (
                    f'<td class="num">{N(float(chapter["indirect_speech_per_1000"]), 1) if chapter.get("indirect_speech_per_1000") is not None else "–"}</td>'
                    if has_ch_indirect
                    else ""
                )
                parts.append(
                    f"<tr>"
                    f'<th scope="row">{chapter_link(num, chapter_label, layer="dialogue")}</th>'
                    f'<td class="num">{N(turns, 0)}</td>'
                    f'<td class="num">{N(short_turns, 0)} ({P(short_pct)})</td>'
                    f'<td class="num">{N(long_turns, 0)}</td>'
                    f'<td class="num">{N(dlg_asl, 1) if turns > 0 else "–"}</td>'
                    f'<td class="num">{N(nar_asl, 1) if nar_asl > 0 else "–"}</td>'
                    f'<td class="num">{contrast_cell}</td>'
                    f"{tags_cell}{indirect_cell}"
                    f"</tr>"
                )
            parts.append("</tbody></table></div></details>")
    parts.extend((
        details_start(L("analysis_dialogue_corpus_details"), element_id="dialogue-corpus-details"),
        kpi_row(tiles),
    ))
    if isinstance(voice_sep, Mapping) and voice_sep.get("available"):
        sep_raw = str(voice_sep.get("separation_label", "unavailable"))
        sep_key = f"dlg_voice_sep_{sep_raw}" if sep_raw in {"distinct", "moderate", "blended", "unavailable"} else "dlg_voice_sep_unavailable"
        dlg_asl_v = voice_sep.get("dialogue_asl")
        nar_asl_v = voice_sep.get("narrative_asl")
        delta_v = voice_sep.get("asl_delta")
        cos_v = voice_sep.get("cosine_similarity")
        dlg_asl_s = N(float(dlg_asl_v), 1) if dlg_asl_v is not None else "–"
        nar_asl_s = N(float(nar_asl_v), 1) if nar_asl_v is not None else "–"
        delta_s = N(float(delta_v), 1, signed=True) if delta_v is not None else "–"
        cos_s = N(float(cos_v), 2) if cos_v is not None else "–"
        parts.append(
            f'<p class="hint dialogue-voice-separation">'
            f'<strong>{L("dlg_voice_separation")}:</strong> {L(sep_key)} · '
            f'{L("dlg_dialogue_asl")} {dlg_asl_s} vs. {L("dlg_narration_asl")} {nar_asl_s} ({delta_s}) · '
            f'{L("dlg_cosine_similarity")} {cos_s}</p>'
        )
    parts.append("</details></section>")
    return "".join(parts)


def render_characters_panel(
    characters: Mapping[str, Any] | None,
    chapters: Sequence[ChapterProfile],
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Render measured name mentions separately from author-declared POV."""
    if characters and characters.get("error"):
        return (panel_start("characters", labels, "panel_characters")
                + f'<p role="status">{esc(characters["error"])}</p></section>')
    if not (characters and characters.get("figures")):
        return ""

    L, N, P = panel_formatters(labels, language_key)

    parts: list[str] = [panel_start("characters", labels, "panel_characters")]
    parts.append(f'<p class="hint">{L("chr_hint")}</p>')
    total = int(characters.get("chapters", 0))
    pov_summary = characters.get("pov_summary")
    if isinstance(pov_summary, Mapping) and int(pov_summary.get("declared_figures", 0)) > 0:
        cov_raw = pov_summary.get("pov_coverage_chapters", 0)
        cov = len(cov_raw) if isinstance(cov_raw, list | tuple | set | frozenset) else int(cov_raw or 0)
        missing = pov_summary.get("chapters_without_declared_pov") or []
        missing_txt = (
            f' · {L("chr_pov_missing")}: {", ".join(str(int(c)) for c in missing)}'
            if missing
            else ""
        )
        parts.append(f'<p class="hint">{L("chr_pov_coverage")}: {cov} / {total}{missing_txt}</p>')
    has_pov = any("declared_pov_chapters" in figure for figure in characters["figures"])
    has_pov_gaps = has_pov and any("pov_longest_gap" in figure for figure in characters["figures"])
    parts.append(table_wrap_start(label(labels, "panel_characters")) + "<thead><tr>")
    for key in (
        "chr_name",
        "chr_mentions",
        "chr_chapters",
        "chr_span",
        "chr_gap",
        "chr_share",
    ):
        num_cls = ' class="num"' if key != "chr_name" else ""
        th_content = help_term(labels, key, L(key)) if key in {"chr_span", "chr_gap", "chr_share"} else L(key)
        parts.append(f'<th scope="col"{num_cls}>{th_content}</th>')
    if has_pov:
        parts.append(f'<th scope="col">{L("chr_pov")}</th>')
    if has_pov_gaps:
        parts.append(f'<th scope="col" class="num">{L("chr_pov_gap")}</th>')
    parts.append("</tr></thead><tbody>")
    for figure in characters["figures"]:
        first = figure.get("first_chapter")
        jump = f' data-jump="#ch-{int(first)}"' if first else ""
        row_class = ' class="row-link"' if first else ""
        name = figure.get("name", "")
        name_link = chapter_link(int(first), name) if first else esc(name)
        share = float(figure.get("presence_ratio", 0.0)) * 100.0
        chapter_span = f"{first}–{figure.get('last_chapter')}" if first else "–"
        first_chapter = next((c for c in chapters if c.num == first), None)
        span_title = (
            f"{L('chapter')} {first} · {esc(first_chapter.title)}"
            if first_chapter is not None
            else ""
        )
        parts.append(
            f'<tr{row_class}{jump}>'
            f'<td class="name">{name_link}</td>'
            f'<td class="num">{int(figure.get("mentions", 0))}</td>'
            f'<td class="num">{len(figure.get("chapters_present", []))} / {total}</td>'
            f'<td class="num" title="{span_title}">{esc(chapter_span)}</td>'
            f'<td class="num">{int(figure.get("longest_gap", 0))}</td>'
            f'<td class="num bar-cell"><i style="--v:{min(100.0, share):.1f}%"></i>{share:.0f} %</td>'
        )
        if has_pov:
            declared = ", ".join(str(int(number)) for number in figure.get("declared_pov_chapters", [])) or "–"
            pov_share = figure.get("pov_share")
            share_suffix = f" ({float(pov_share) * 100.0:.0f} %)" if pov_share is not None and figure.get("declared_pov_chapters") else ""
            parts.append(f'<td>{esc(declared)}{esc(share_suffix)}</td>')
        if has_pov_gaps:
            pov_gap = figure.get("pov_longest_gap")
            gap_list = figure.get("pov_gaps") or []
            gap_tip = "; ".join(
                f'{int(g["from_chapter"])}→{int(g["to_chapter"])} ({int(g["gap_chapters"])})'
                for g in gap_list
            )
            gap_text = str(int(pov_gap)) if pov_gap is not None and figure.get("declared_pov_chapters") else "–"
            parts.append(f'<td class="num" title="{esc(gap_tip)}">{gap_text}</td>')
        parts.append("</tr>")
    parts.append("</tbody></table></div>")
    voices = characters.get("character_voices")
    if isinstance(voices, Mapping) and (voices.get("characters") or voices.get("narrator")):
        parts.append(
            f'<details class="character-voices" open=""><summary>{L("chr_voices_title")}</summary>'
            f'<p class="hint">{L("chr_voices_hint")}</p>'
        )
        narrator = voices.get("narrator")
        if isinstance(narrator, Mapping) and narrator.get("words"):
            nar_asl = N(float(narrator["asl"]), 1) if narrator.get("asl") is not None else "–"
            nar_q = P(float(narrator["question_excl_rate"])) if narrator.get("question_excl_rate") is not None else "–"
            nar_fw = P(float(narrator["function_word_share"])) if narrator.get("function_word_share") is not None else "–"
            parts.append(
                f'<p class="hint"><strong>{L("chr_voice_narrator")}:</strong> '
                f'{L("chr_voice_asl")} {nar_asl} · {L("chr_voice_qexcl")} {nar_q} · {L("chr_voice_func")} {nar_fw}</p>'
            )
        char_rows = voices.get("characters") or []
        if char_rows:
            parts.append(
                table_wrap_start(label(labels, "chr_voices_title"))
                + "<thead><tr>"
                f'<th scope="col">{L("chr_name")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_turns")}</th>'
                f'<th scope="col" class="num">{L("words")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_asl")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_delta")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_qexcl")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_func")}</th>'
                "</tr></thead><tbody>"
            )
            for ch_voice in char_rows:
                v_name = esc(str(ch_voice.get("name", "")))
                v_turns = N(int(ch_voice.get("turns", 0)), 0)
                v_words = N(int(ch_voice.get("words", 0)), 0)
                if ch_voice.get("status") != "available":
                    parts.append(
                        f'<tr><th scope="row">{v_name}</th>'
                        f'<td class="num">{v_turns}</td><td class="num">{v_words}</td>'
                        f'<td colspan="4" class="num">{badge(label(labels, "chr_voice_insufficient"))}</td></tr>'
                    )
                    continue
                v_asl = N(float(ch_voice["dialogue_asl"]), 1) if ch_voice.get("dialogue_asl") is not None else "–"
                v_delta = N(float(ch_voice["narrator_asl_delta"]), 1, signed=True) if ch_voice.get("narrator_asl_delta") is not None else "–"
                v_q = P(float(ch_voice["question_excl_rate"])) if ch_voice.get("question_excl_rate") is not None else "–"
                v_fw = P(float(ch_voice["function_word_share"])) if ch_voice.get("function_word_share") is not None else "–"
                parts.append(
                    f'<tr><th scope="row">{v_name}</th>'
                    f'<td class="num">{v_turns}</td>'
                    f'<td class="num">{v_words}</td>'
                    f'<td class="num">{v_asl}</td>'
                    f'<td class="num">{v_delta}</td>'
                    f'<td class="num">{v_q}</td>'
                    f'<td class="num">{v_fw}</td></tr>'
                )
            parts.append("</tbody></table></div>")
        parts.append("</details>")
    interactions = characters.get("character_interactions")
    if not isinstance(interactions, Mapping) and isinstance(voices, Mapping):
        interactions = voices.get("character_interactions")
    if isinstance(interactions, Mapping) and (interactions.get("pairs") or interactions.get("turn_dominance")):
        parts.append(
            f'<details class="character-interactions" open=""><summary>{L("chr_interactions_title")}</summary>'
            f'<p class="hint">{L("chr_interactions_hint")}</p>'
        )
        pairs = interactions.get("pairs") or []
        if pairs:
            parts.append(
                table_wrap_start(label(labels, "chr_interactions_title"))
                + "<thead><tr>"
                f'<th scope="col">{L("chr_interaction_pair")}</th>'
                f'<th scope="col" class="num">{L("chr_turn_exchanges")}</th>'
                f'<th scope="col" class="num">{L("chr_co_chapters")}</th>'
                "</tr></thead><tbody>"
            )
            for pair in pairs[:20]:
                a_name = esc(str(pair.get("a", "")))
                b_name = esc(str(pair.get("b", "")))
                exchanges = N(int(pair.get("turn_exchanges", 0)), 0)
                co_ch = N(int(pair.get("co_chapters", 0)), 0)
                parts.append(
                    f'<tr><th scope="row">{a_name} ↔ {b_name}</th>'
                    f'<td class="num">{exchanges}</td>'
                    f'<td class="num">{co_ch}</td></tr>'
                )
            parts.append("</tbody></table></div>")
        dominance = interactions.get("turn_dominance") or []
        if dominance:
            parts.append(
                table_wrap_start(label(labels, "chr_turn_dominance"))
                + "<thead><tr>"
                f'<th scope="col">{L("chr_name")}</th>'
                f'<th scope="col" class="num">{L("chr_voice_turns")}</th>'
                f'<th scope="col" class="num">{L("words")}</th>'
                f'<th scope="col" class="num">{L("chr_turn_share")}</th>'
                f'<th scope="col" class="num">{L("chr_word_share")}</th>'
                "</tr></thead><tbody>"
            )
            for row in dominance[:20]:
                d_name = esc(str(row.get("name", "")))
                d_turns = N(int(row.get("turns", 0)), 0)
                d_words = N(int(row.get("words", 0)), 0)
                t_share = float(row.get("turn_share", 0.0))
                w_share = float(row.get("word_share", 0.0))
                parts.append(
                    f'<tr><th scope="row">{d_name}</th>'
                    f'<td class="num">{d_turns}</td>'
                    f'<td class="num">{d_words}</td>'
                    f'<td class="num bar-cell"><i style="--v:{min(100.0, t_share):.1f}%"></i>{N(t_share, 1)} %</td>'
                    f'<td class="num bar-cell"><i style="--v:{min(100.0, w_share):.1f}%"></i>{N(w_share, 1)} %</td></tr>'
                )
            parts.append("</tbody></table></div>")
        parts.append("</details>")
    parts.append("</section>")
    return "".join(parts)


def _evidence_chapter_select(
    chapters: Sequence[Mapping[str, Any]], L: Callable[[str], str],
) -> str:
    options = [f'<option value="">{L("analysis_scope_all")}</option>']
    for chapter in chapters:
        number = int(chapter.get("chapter_num") or 0)
        if number <= 0:
            continue
        name = f'{L("chapter")} {number} · {esc(chapter.get("title", ""))}'
        options.append(f'<option value="{number}">{name}</option>')
    return (
        f'<label class="evidence-chapter-label">{L("evidence_examples_chapter")}'
        f'<select class="ctl" data-evidence-chapter="1">{"".join(options)}</select></label>'
    )


def render_pacing_panel(
    pacing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *,
    metrics: CorpusMetrics | None = None,
) -> str:
    """Renders the unified pacing, rhythm and sentence-length panel."""
    if not (pacing and pacing.get("chapter_list")):
        return ""

    L, N, P = panel_formatters(labels, language_key)

    sg_matches = pacing.get("sentence_group_matches")
    pacing_attrs = (
        f'data-sentence-group-matches="{attr_json(sg_matches)}"'
        if isinstance(sg_matches, Mapping)
        else ""
    )
    parts = [panel_start("pacing", labels, "panel_pacing", extra_attrs=pacing_attrs), panel_guide(L("pacing_scale"))]
    if pacing.get("scenes_are_chapters", False):
        parts.append(f'<p class="ctl-note">{L("pacing_units_note")}</p>')
    units = esc(FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])["asl"])
    chapters_pacing = pacing["chapter_list"]
    max_asl = max((float(c.get("asl", 0.0)) for c in chapters_pacing), default=0.0) or 1.0
    parts.append('<div class="dist scrollable">')
    for chapter in chapters_pacing:
        num = int(chapter.get("chapter_num", 0))
        asl = float(chapter.get("asl", 0.0))
        chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
        parts.append(
            dist_row(
                num,
                chapter_label,
                min(100.0, asl / max_asl * 100.0),
                f"{N(asl, 1)} {units}",
                layer="asl",
                title_text=chapter.get("title", ""),
            )
        )
    parts.append("</div>")
    parts.append(action_strip(
        f'<p class="ctl-note">{L("evidence_examples_note")}</p>'
        f'<div class="row">{_evidence_chapter_select(chapters_pacing, L)}'
        f'<button type="button" class="ctl ctl-sm" data-pattern-jump="1" data-layer="asl">'
        f'{L("rhythm_open_sentences")}</button></div>',
        css_class="chapter-evidence-actions",
        hidden=True,
    ))
    if metrics is not None:
        parts.append(render_sentence_dist_panel(metrics, labels, language_key, embedded=True))

    parts.append(details_start(L("pac_chapter_details"), extra_class="pacing-measurements"))
    tiles: list[str] = []
    tiles.append(kpi(N(pacing.get("scenes", 0), 0), L("pac_scenes")))
    tiles.append(kpi(N(pacing.get("avg_scene_words", 0.0), 0), L("pac_avg_scene")))
    tiles.append(kpi(N(pacing.get("hook_score_mean", 0.0), 2),
                     help_term(labels, "pacing_hook", L("pac_hook_mean"),
                               fields={"max_words": str(HOOK_SHORT_SENTENCE)})))
    if "sentence_overlap_pct" in pacing:
        tiles.append(kpi(P(float(pacing.get("sentence_overlap_pct", 0.0))), L("pac_cohesion")))
    if "repeated_start_runs" in pacing:
        tiles.append(kpi(N(int(pacing.get("repeated_start_runs", 0)), 0), L("pac_monotony")))
    if pacing.get("sticky_available"):
        sticky_pct_val = float(pacing.get("sticky_sentence_pct", 0.0))
        sticky_jump = "#pacing-sticky-items" if pacing.get("sticky_items") else None
        tiles.append(kpi(P(sticky_pct_val), L("pac_sticky_pct"), jump=sticky_jump))
        tiles.append(kpi(P(float(pacing.get("mean_glue_pct", 0.0))), L("pac_glue_mean")))
    rhythm = pacing.get("rhythm_profile")
    if isinstance(rhythm, Mapping) and rhythm.get("available"):
        if rhythm.get("asl_cv") is not None:
            tiles.append(kpi(N(float(rhythm["asl_cv"]), 2), L("pac_asl_cv")))
        if rhythm.get("asl_iqr") is not None:
            tiles.append(kpi(N(float(rhythm["asl_iqr"]), 1), L("pac_asl_iqr")))
        if rhythm.get("length_entropy") is not None:
            tiles.append(kpi(N(float(rhythm["length_entropy"]), 2), L("pac_length_entropy")))
    parts.append(kpi_row(tiles))
    if isinstance(rhythm, Mapping) and rhythm.get("available"):
        parts.append(
            f'<p class="hint pacing-rhythm-profile"><strong>{L("pac_rhythm_profile")}</strong> '
            f'{L("pac_rhythm_hint")}</p>'
        )
        buckets = rhythm.get("bucket_shares")
        if isinstance(buckets, Mapping):
            keys = ("short", "medium", "long")
            bounds = pacing.get("rhythm_word_bounds")
            if (not isinstance(bounds, (tuple, list)) or len(bounds) != 2
                    or any(type(bound) is not int or bound < 1 for bound in bounds)):
                bounds = None
                parts.append(f'<p class="ctl-note">{L("sentence_group_bounds_unavailable")}</p>')
            groups = _sentence_group_labels(keys, bounds, L, N)
            intervals = sentence_group_intervals(bounds) or [None] * len(groups)
            values_by_group = [buckets.get(key) for key in keys]
            scale = 100.0 if sum(float(value) for value in values_by_group if value is not None) <= 1.5 else 1.0
            parts.append(f'<p class="ctl-note">{L("pacing_sentence_groups")}</p>')
            parts.append(kpi_row([
                kpi(
                    P(float(value) * scale) if value is not None else "–",
                    group,
                    extra_attrs=_sentence_group_attrs(
                        interval,
                        label_text=group,
                        count_positive=value is not None and float(value) > 0.0,
                        group_key=group_key,
                    ),
                )
                for group_key, group, interval, value in zip(keys, groups, intervals, values_by_group, strict=True)
            ], row_id="pacing-rhythm-buckets"))
    if any(field in ch for ch in chapters_pacing for field in (
        "hook_score", "sentence_overlap_pct", "repeated_start_runs", "pacing_sparkline", "sticky_sentence_pct",
    )):
        has_sticky_ch = pacing.get("sticky_available", True) and any("sticky_sentence_pct" in ch for ch in chapters_pacing)
        sticky_th = f'<th scope="col" class="num">{L("pac_sticky_pct")}</th>' if has_sticky_ch else ""
        parts.append(
            table_wrap_start(label(labels, "pac_chapter_details"))
            + "<thead><tr>"
            f'<th scope="col">{L("chapter")}</th>'
            f'<th scope="col" class="num">{help_term(labels, "asl", units)}</th>'
            f'<th scope="col" class="spark">{help_term(labels, "pacing_sparkline", L("pac_sparkline"))}</th>'
            f'<th scope="col" class="num">{L("pac_hook")}</th>'
            f'<th scope="col" class="num">{help_term(labels, "pacing_cohesion", L("pac_cohesion"))}</th>'
            f'<th scope="col" class="num">{help_term(labels, "pacing_monotony", L("pac_monotony"))}</th>'
            f"{sticky_th}"
            "</tr></thead><tbody>"
        )
        for chapter in chapters_pacing:
            num = int(chapter.get("chapter_num", 0))
            asl = float(chapter.get("asl", 0.0))
            hook = chapter.get("hook_score")
            sparkline = chapter.get("pacing_sparkline") or ""
            overlap = chapter.get("sentence_overlap_pct")
            monotony = chapter.get("repeated_start_runs")
            chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
            sticky_cell = (
                f'<td class="num">{P(float(chapter["sticky_sentence_pct"])) if chapter.get("sticky_sentence_pct") is not None else "–"}</td>'
                if has_sticky_ch
                else ""
            )
            parts.append(
                f"<tr>"
                f'<th scope="row">{chapter_link(num, chapter_label)}</th>'
                f'<td class="num">{N(asl, 1)}</td>'
                f'<td class="spark" style="text-align:center"><span class="sparkline" style="font-family:monospace;font-size:var(--text-micro);letter-spacing:.05em;color:var(--accent)">{esc(sparkline)}</span></td>'
                f'<td class="num">{N(int(hook), 0) if hook is not None else "–"}</td>'
                f'<td class="num">{P(float(overlap)) if overlap is not None else "–"}</td>'
                f'<td class="num">{N(int(monotony), 0) if monotony is not None else "–"}</td>'
                f"{sticky_cell}"
                f"</tr>"
            )
        parts.append("</tbody></table></div>")
    parts.append("</details>")
    sticky_items = pacing.get("sticky_items") or []
    if pacing.get("sticky_available") or sticky_items:
        total = int(pacing.get("sticky_sentences", len(sticky_items)))
        shown = sticky_items[:20]
        parts.append(
            details_start(
                f'{L("pac_sticky_items")} ({N(total, 0)})',
                element_id="pacing-sticky-items",
                extra_class="pacing-sticky-items",
            )
        )
        parts.append(f'<p class="ctl-note">{L("pac_sticky_read")}</p>')
        rule = pacing.get("sticky_rule")
        if isinstance(rule, Mapping) and rule.get("min_words") is not None and rule.get("min_pct") is not None:
            thresholds = label(labels, "pac_sticky_rule").format(
                min_words=N(int(rule["min_words"]), 0),
                min_pct=format_pct(float(rule["min_pct"]), language_key, decimals=2, precise=True),
            )
            parts.append(f'<p class="ctl-note">{esc(thresholds)}</p>')
        else:
            parts.append(f'<p class="ctl-note">{L("pac_sticky_rule_missing")}</p>')
        if len(shown) < total:
            count = label(labels, "pac_sticky_shown").format(shown=N(len(shown), 0), total=N(total, 0))
            parts.append(f'<p class="ctl-note">{esc(count)}</p>')
        if shown:
            parts.append("<ul>")
        for item in shown:
            ch_num = int(item.get("chapter_num", 0))
            glue_pct = P(float(item["glue_pct"]), 2) if item.get("glue_pct") is not None else "–"
            words = N(int(item["words"]), 0) if item.get("words") is not None else "–"
            glue_words = item.get("glue_words")
            if glue_words is None:
                evidence = f'{glue_pct} {L("function_words")} · {words} {L("words")}'
            else:
                evidence = esc(label(labels, "pac_sticky_evidence").format(
                    function_words=N(int(glue_words), 0), words=words, percent=glue_pct,
                ))
            preview = esc(str(item.get("preview", "")))
            ch_label = f'{label(labels, "chapter")} {ch_num}'
            p_id = item.get("paragraph_id")
            jump_html = ""
            if p_id:
                jump_html = (
                    f' <button type="button" class="ctl ctl-sm sticky-jump-btn" '
                    f'data-sticky-jump="1" data-target="{esc(str(p_id), quote=True)}" '
                    f'data-line="{int(item.get("start_line", 0))}" '
                    f'data-span-index="{int(item.get("span_index", 0))}">'
                    f'{L("rhythm_open_sentence")}</button>'
                )
            parts.append(
                f'<li><p>{preview}</p><p class="ctl-note">{evidence} · '
                f'{chapter_link(ch_num, ch_label, layer="sticky")}{jump_html}</p></li>'
            )
        if shown:
            parts.append("</ul>")
        parts.append("</details>")
    corridor = pacing.get("genre_corridor")
    if isinstance(corridor, Mapping) and corridor.get("metrics"):
        genre_label = esc(str(corridor.get("label") or corridor.get("genre") or ""))
        corridor_metric_labels = {
            "asl": L("feat_asl"),
            "dialogue_pct": L("dialogue"),
            "staccato_pct": L("feat_staccato"),
            "avg_scene_words": L("pac_avg_scene"),
        }
        parts.append(
            f'<details class="genre-corridor" open><summary>{L("genre_corridor_title")}: {genre_label}</summary>'
            f'<p class="hint">{L("genre_corridor_note")}</p>'
            + table_wrap_start(label(labels, "genre_corridor_title"))
            + "<thead><tr>"
            f'<th scope="col">{L("genre_corridor_title")}</th>'
            f'<th scope="col" class="num">{L("genre_corridor_observed")}</th>'
            f'<th scope="col" class="num">{L("genre_corridor_range")}</th>'
            f'<th scope="col">{L("genre_corridor_position")}</th>'
            "</tr></thead><tbody>"
        )
        for m_key, m_val in corridor["metrics"].items():
            if not isinstance(m_val, Mapping):
                continue
            m_name = corridor_metric_labels.get(m_key, esc(str(m_key)))
            obs = m_val.get("observed")
            low = m_val.get("low")
            high = m_val.get("high")
            pos = str(m_val.get("position") or "")
            pos_key = f"scene_{pos}" if pos in {"below", "within", "above", "unavailable"} else ""
            pos_raw = label(labels, pos_key) if pos_key else (pos or "–")
            parts.append(
                f"<tr>"
                f'<th scope="row">{m_name}</th>'
                f'<td class="num">{N(obs, 1) if obs is not None else "–"}</td>'
                f'<td class="num">{N(low, 1) if low is not None else "…"} – {N(high, 1) if high is not None else "…"}</td>'
                f'<td>{badge(pos_raw)}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div></details>")
    parts.append("</section>")
    return "".join(parts)


_MOTIF_PREVIEW_LIMIT = 30


def _render_motif_occurrences(
    items: Sequence[Mapping[str, Any]],
    *,
    group_type: str,
    label_field: str,
    count_field: str,
    L: Callable[[str], str],
    labels: Mapping[str, str] | None,
) -> str:
    """Render exact match locations and shared-highlight selectors for motifs/phrases."""
    groups: list[str] = []
    for index, item in enumerate(items):
        occs = item.get("occurrences")
        counted = int(item.get(count_field, 0))
        mapped = item.get("mapped_occurrence_count")
        if not isinstance(occs, list) or not isinstance(mapped, int) or not counted:
            continue
        title = str(item.get(label_field, ""))
        occ_payload = attr_json([
            {
                "paragraph_id": str(occ["paragraph_id"]),
                "start_line": int(occ["start_line"]),
                "start": int(occ["start"]),
                "end": int(occ["end"]),
                "offset_unit": str(occ["offset_unit"]),
                "quote": str(occ["quote"]),
                **({"quotation_context": str(occ["quotation_context"])} if occ.get("quotation_context") else {}),
            }
            for occ in occs
        ])
        notes = []
        if mapped < counted:
            coverage = "mot_locations_partial_one" if counted == 1 else "mot_locations_partial"
            notes.append(L(coverage).format(mapped=mapped, count=counted))
        if len(occs) < mapped:
            notes.append(L("mot_locations_limit").format(shown=len(occs), mapped=mapped))
        if len(occs) > _MOTIF_PREVIEW_LIMIT:
            notes.append(L("mot_locations_preview").format(preview=_MOTIF_PREVIEW_LIMIT))
        rows = []
        for idx, occ in enumerate(occs[:_MOTIF_PREVIEW_LIMIT]):
            loc = f'{label(labels, "chapter")} {int(occ["chapter"])} · {label(labels, "line")} {int(occ["start_line"])}'
            excerpt = esc(str(occ.get("excerpt", "")))
            context = occ.get("quotation_context")
            quote_badge = (f'<span class="badge badge-neutral">{L(f"evidence_quote_{context}")}</span> '
                           if context else "")
            rows.append(
                f'<li><span class="ctl-note">{esc(loc)}</span> {quote_badge}'
                f'<span class="motif-occ-excerpt">{excerpt}</span> '
                f'<a class="ctl ctl-sm motif-jump-btn" href="#{esc(occ["paragraph_id"])}" '
                f'data-motif-jump="1" data-occurrence-index="{idx}">{L("mot_open_occurrence")}</a></li>'
            )
        actions = (
            '<div class="motif-occurrence-actions">'
            f'<button type="button" class="ctl ctl-sm motif-select-btn" aria-pressed="false" '
            f'data-motif-select="1">{L("mot_highlight_all")}</button></div>'
            f'<ul class="motif-occurrence-list">{"".join(rows)}</ul>'
        ) if rows else ""
        groups.append(
            details_start(f'{esc(title)} ({counted})', extra_class="motif-occurrence-group")
            + f'<div data-motif-group="{group_type}-{index}" data-motif-label="{esc(title)}" '
            + f'data-motif-occurrences=\'{occ_payload}\'>'
            + "".join(f'<p class="ctl-note">{note}</p>' for note in notes)
            + '<p class="ctl-status" data-motif-status="" role="status"></p>'
            + actions + '</div></details>'
        )
    if not groups:
        return ""
    return f'<div class="motif-occurrence-groups">{"".join(groups)}</div>'


def _render_motif_custom_search(L: Callable[[str], str]) -> str:
    """Render the custom phrase/pattern search form inside #motifs (no table)."""
    regex_field = checkbox_field('<input type="checkbox" id="motif-pattern-regex"/>', L("mot_custom_regex"),
                                 extra_class="motif-custom-regex")
    return (
        '<div class="motif-custom-block">'
        f'<h3>{L("mot_custom_heading")}</h3>'
        f'<p class="ctl-note">{L("mot_custom_hint")}</p>'
        '<form class="motif-custom-search" id="motif-custom-search" '
        f'data-location-limit="{MAX_DISPLAY_OCCURRENCES}" data-preview-limit="{_MOTIF_PREVIEW_LIMIT}">'
        f'<label class="motif-custom-field"><span>{L("mot_custom_label")}</span>'
        f'<input type="search" class="ctl" id="motif-pattern-input" '
        f'placeholder="{L("mot_custom_placeholder")}" autocomplete="off"/></label>'
        f'{regex_field}'
        f'<button type="submit" class="ctl primary" id="motif-pattern-submit">{L("mot_custom_submit")}</button>'
        f'<button type="button" class="ctl" id="motif-pattern-clear" hidden="hidden">{L("mot_custom_clear")}</button>'
        '</form>'
        + status_banner("motif-pattern-status")
        + '<div id="motif-custom-results"></div>'
        '</div>'
    )


def render_motifs_panel(
    motifs: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    *,
    custom_search: bool = False,
) -> str:
    """Render motifs, manuscript phrase totals, local echoes and custom search patterns."""
    if not motifs:
        return ""

    L = panel_label(labels)
    findings = (motifs.get("motifs"), motifs.get("repeated_phrases"), motifs.get("echoes"))
    if not any(findings):
        if None in findings or not motifs.get("chapters"):
            return ""
        return (
            panel_start("motifs", labels, "panel_motifs")
            + panel_guide(L("motifs_no_findings"))
            + (_render_motif_custom_search(L) if custom_search else "")
            + "</section>"
        )

    parts: list[str] = [panel_start("motifs", labels, "panel_motifs")]
    if motifs.get("motifs"):
        parts.append(table_wrap_start(label(labels, "panel_motifs")) + "<thead><tr>")
        parts.extend(
            (f'<th scope="col">{L(key)}</th>' if key == "mot_name" else f'<th scope="col" class="num">{L(key)}</th>')
            for key in ("mot_name", "mot_count", "mot_chapters", "chr_gap")
        )
        parts.append("</tr></thead><tbody>")
        for motif in motifs["motifs"]:
            first = motif.get("first_chapter")
            jump = f' data-jump="#ch-{int(first)}"' if first else ""
            row_class = ' class="row-link"' if first else ""
            name = motif.get("name", "")
            name_link = chapter_link(int(first), name) if first else esc(name)
            motif_span = f"{first}–{motif.get('last_chapter')}" if first else "–"
            parts.append(
                f'<tr{row_class}{jump}>'
                f'<td class="name">{name_link}</td>'
                f'<td class="num">{int(motif.get("mentions", 0))}</td>'
                f'<td class="num">{esc(motif_span)}</td>'
                f'<td class="num">{int(motif.get("longest_gap", 0))}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")
        parts.append(_render_motif_occurrences(motifs["motifs"], group_type="motif", label_field="name",
                                               count_field="mentions", L=L, labels=labels))

    if motifs.get("repeated_phrases"):
        parts.append(table_wrap_start(label(labels, "mot_phrase"), extra_class="motif-phrases") + "<thead><tr>")
        parts.extend(
            (f'<th scope="col">{L(key)}</th>' if key == "mot_phrase" else f'<th scope="col" class="num">{L(key)}</th>')
            for key in ("mot_phrase", "mot_global_count", "mot_chapters")
        )
        parts.append("</tr></thead><tbody>")
        for phrase in motifs["repeated_phrases"]:
            chapter_list_text = ", ".join(str(c) for c in phrase.get("chapters", []))
            first = phrase.get("chapters", [None])[0]
            jump = f' data-jump="#ch-{int(first)}"' if first else ""
            row_class = ' class="row-link"' if first else ""
            text = phrase.get("phrase", "")
            phrase_link = chapter_link(int(first), text) if first else esc(text)
            parts.append(
                f'<tr{row_class}{jump}>'
                f'<td class="name">{phrase_link}</td>'
                f'<td class="num">{int(phrase.get("count", 0))}</td>'
                f'<td class="num">{esc(chapter_list_text)}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")
        parts.append(_render_motif_occurrences(motifs["repeated_phrases"], group_type="phrase", label_field="phrase",
                                               count_field="count", L=L, labels=labels))

    if motifs.get("echoes"):
        parts.extend((f'<h3>{L("mot_echoes")}</h3>', panel_guide(L("mot_echo_note"))))
        parts.append(table_wrap_start(label(labels, "mot_echoes"), extra_class="motif-echoes") + "<thead><tr>")
        parts.extend(
            (f'<th scope="col">{L(key)}</th>' if key == "mot_phrase" else f'<th scope="col" class="num">{L(key)}</th>')
            for key in ("mot_phrase", "mot_echo_chapter", "mot_echo_count", "mot_echo_words")
        )
        parts.append("</tr></thead><tbody>")
        for echo in motifs["echoes"]:
            chapter = int(echo["chapter"])
            parts.append(
                f'<tr><td class="name">{esc(echo["term"])}</td>'
                f'<td class="num"><a href="#ch-{chapter}" data-jump="#ch-{chapter}">{chapter}</a></td>'
                f'<td class="num">{int(echo["count"])}</td>'
                f'<td class="num">{int(echo["first_word"])}–{int(echo["last_word"])}</td></tr>'
            )
        parts.append('</tbody></table></div>')
        parts.append(_render_motif_occurrences(motifs["echoes"], group_type="echo", label_field="term",
                                               count_field="count", L=L, labels=labels))
        parts.append(details_start(L("mot_echo_method"), extra_class="motif-echo-method")
                     + f'<p>{L("mot_echo_limits")}</p></details>')

    if custom_search:
        parts.append(_render_motif_custom_search(L))
    parts.append("</section>")
    return "".join(parts)


def render_showing_panel(
    showing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    *,
    short_sentence_max: int | None = None,
) -> str:
    """Render the manuscript-relative signal groups without a narrative verdict."""
    if not (showing and showing.get("chapter_list")):
        return ""

    L, N, _ = panel_formatters(labels, language_key)

    showing_chapters = showing["chapter_list"]
    comparable_chapters = [chapter for chapter in showing_chapters if chapter.get("comparable", True)]
    comparable = len(comparable_chapters) >= MIN_COMPARISON_CHAPTERS and any(
        float(chapter.get("tell_z") or 0.0) != 0.0
        or float(chapter.get("show_z") or 0.0) != 0.0
        for chapter in comparable_chapters
    )
    parts: list[str] = [panel_start("showing", labels, "panel_showing")]
    brief_note = esc(
        label(labels, "showing_brief_note").replace("{min_words}", str(MIN_COMPARABLE_WORDS))
    )
    context_note = esc(
        label(labels, "showing_context_note").replace("{min_words}", str(MIN_COMPARABLE_WORDS))
    )
    parts.append(f'<p class="ctl-note">{brief_note}</p>')
    parts.append(details_start(L("showing_method"), extra_class="signal-method"))
    parts.append(f'<p class="ctl-note">{context_note}</p></details>')
    pattern_layers = (
        ("filter", "layer_filter"),
        ("modal", "layer_modal"),
        ("passive", "layer_passive"),
        ("nominal", "layer_nominal"),
        ("sensory", "layer_sensory"),
        ("dialogue", "layer_dialogue"),
    )
    pattern_buttons = "".join(
        f'<button type="button" class="ctl ctl-sm showing-pattern-jump" '
        f'data-pattern-jump="1" data-layer="{layer_key}">{L(label_key)}</button>'
        for layer_key, label_key in pattern_layers
    )
    if short_sentence_max is not None:
        pattern_buttons += (
            '<button type="button" class="ctl ctl-sm rhythm-jump-btn" '
            f'data-rhythm-min-words="1" data-rhythm-max-words="{short_sentence_max}" '
            f'data-rhythm-label="{L("rhythm_open_short_sentences")}" hidden="hidden">'
            f'{L("rhythm_open_short_sentences")}</button>'
        )
    parts.append(
        action_strip(
            f'<p class="ctl-note">{L("showing_open_patterns")} {L("evidence_examples_note")}</p>'
            f'<div class="row">{_evidence_chapter_select(showing_chapters, L)}{pattern_buttons}</div>',
            css_class="chapter-evidence-actions showing-pattern-actions",
            hidden=True,
        )
    )
    if not comparable:
        note = L("showing_unavailable_note").replace("{min_chapters}", str(MIN_COMPARISON_CHAPTERS))
        parts.append(f'<p class="ctl-note">{note}</p></section>')
        return "".join(parts)
    parts.append(kpi_row([
        kpi(N(float(showing.get("tell_z_mean") or 0.0), 2, signed=True), L("show_tell")),
        kpi(N(float(showing.get("show_z_mean") or 0.0), 2, signed=True), L("show_show")),
        kpi(N(float(showing.get("balance_mean") or 0.0), 2, signed=True), L("show_balance")),
    ]))
    if showing.get("sensory_density_mean") is not None or showing.get("immersion_ratio_mean") is not None:
        pills: list[str] = []
        if showing.get("sensory_density_mean") is not None:
            sens_term = help_term(labels, "sensory", L("show_sensory"))
            pills.append(
                f'<span class="immersion-pill"><b>{N(float(showing["sensory_density_mean"]), 1)}</b> {sens_term}</span>'
            )
        if showing.get("immersion_ratio_mean") is not None:
            imm_term = help_term(labels, "immersion", L("show_immersion"))
            pills.append(
                f'<span class="immersion-pill"><b>{N(float(showing["immersion_ratio_mean"]), 2)}</b> {imm_term}</span>'
            )
        parts.append(f'<p class="ctl-note">{" · ".join(pills)}</p>')
    parts.append(f'<p class="signal-scale">{L("showing_axis_note")} '
                 '<span class="signal-scale-key" aria-hidden="true"><span>−</span><span>0</span><span>+</span></span></p>')

    max_abs = (
        max((abs(float(c.get("balance") or 0.0)) for c in comparable_chapters), default=0.0) or 1.0
    )
    parts.append('<div class="dist scrollable">')
    for chapter in showing_chapters:
        num = int(chapter.get("chapter_num", 0))
        title_raw = chapter.get("title", "")
        label_text = f'{label(labels, "chapter")} {num} · {title_raw}'
        if not chapter.get("comparable", True):
            parts.append(
                dist_row(
                    num,
                    label_text,
                    0.0,
                    "–",
                    bar_class="bar",
                    title_text=title_raw,
                    unavailable=True,
                )
            )
            continue
        balance = float(chapter.get("balance") or 0.0)
        width = min(50.0, abs(balance) / max_abs * 50.0)
        sign = "signal-negative" if balance < 0 else "signal-positive"
        parts.append(
            dist_row(
                num,
                label_text,
                width,
                N(balance, 2, signed=True),
                bar_class="bar signal-bar",
                bar_inner_class=sign,
                title_text=title_raw,
            )
        )
    parts.append("</div></section>")
    return "".join(parts)
