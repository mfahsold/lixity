"""Reusable narration panels (sentence distribution, dialogue, characters, pacing, motifs, showing)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..dialogue import LONG_TURN_MIN_WORDS, SHORT_TURN_MAX_WORDS
from ..diversity import MIN_TOKENS_LD
from ..format import num as format_num
from ..pacing import HOOK_SHORT_SENTENCE
from ..showing import MIN_COMPARISON_CHAPTERS
from ..style_fingerprint import FEATURE_UNITS, FEATURES, MIN_COMPARABLE_WORDS
from ..style_profile import ChapterProfile
from .components import (
    chapter_link,
    esc,
    help_term,
    kpi,
    label,
    panel_formatters,
    panel_label,
    panel_start,
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
    if not scenes.get("items") and not scenes.get("planned_items"):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key).replace("{min_tokens}", str(MIN_TOKENS_LD)))

    def N(value: Any) -> str:
        return "—" if value is None else format_num(value, language_key, 2)

    parts = [panel_start("scenes", labels, "panel_scenes"),
             f'<p class="hint">{L("scene_guidance")}</p>',
             f'<p class="hint">{L("scene_support")}</p>']
    # Keep comparisons visible, with one reversible catalogue for the detailed
    # tables rather than a second full list of scene summaries in the overview.
    asl_key = next(label_key for field, label_key, _unit in FEATURES if field == "asl")
    dialog_key = next(label_key for field, label_key, _unit in FEATURES if field == "dialog_pct")
    has_hooks = any("entry_hook_type" in item or "exit_hook_type" in item for item in scenes["items"])

    def _hook_label(hook_type: Any) -> str:
        key = f"hook_type_{hook_type}" if hook_type in {"dialogue", "action", "reflection", "question", "unknown"} else "hook_type_unknown"
        return L(key)

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
                f'({int(plateau.get("scene_count", 0))}, ASL {N(plateau.get("mean_asl"))}, {L(reason_key)})'
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
        parts.append('<div class="table-wrap scene-overview" tabindex="0" role="region" '
                     f'aria-label="{L("panel_scenes")}"><table><thead><tr>'
                     f'<th scope="col">{L("panel_scenes")}</th><th scope="col" class="num">{L("words")}</th>'
                     f'<th scope="col" class="num">{L("sentences")}</th>'
                     f'<th scope="col" class="num">{L(asl_key)}</th><th scope="col" class="num">{L(dialog_key)}</th>'
                     f'{hook_headers}{dynamic_header}{showing_headers}</tr></thead><tbody>')
    for item in scenes["items"]:
        group = esc(item["group"]) if item["group"] else L("scene_unassigned")
        group_badge = f'<span class="badge badge-register">{group}</span>' if item["group"] else f'<span class="badge badge-neutral">{group}</span>'
        pov_chars = item.get("pov_characters") or []
        pov_badge = (
            f' <span class="badge badge-neutral">{L("scene_pov")}: {esc(", ".join(str(c) for c in pov_chars))}</span>'
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
            entry_cell = f'<span class="badge badge-neutral">{_hook_label(entry_t)}</span>' if entry_t else "—"
            if exit_t:
                score_txt = f" · {int(exit_score)}/3" if exit_score is not None else ""
                exit_cell = f'<span class="badge badge-neutral">{_hook_label(exit_t)}{score_txt}</span>'
            else:
                exit_cell = "—"
            hook_cells = f"<td>{entry_cell}</td><td>{exit_cell}</td>"
        dynamic_cell = ""
        if has_dynamics:
            dyn_raw = item.get("scene_dynamic")
            if dyn_raw in {"accelerating", "decelerating", "dialogue_surge", "steady", "insufficient_length"}:
                dynamic_cell = f'<td><span class="badge badge-neutral">{L("scene_dynamic_" + dyn_raw)}</span></td>'
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
        parts.append(f'<details class="scene-measurements"><summary>{L("scene_measurements")} '
                     f'({len(scenes["items"])})</summary>')
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
        parts.append(f'<div class="table-wrap" id="{esc(target)}" tabindex="0" role="region" '
                     f'aria-label="{L("scene_measurements")} · {esc(item["id"])}">'
                     f'<table><thead><tr>{header}</tr></thead><tbody>')
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
                L(f"scene_cue_{c}") if c in {"time", "place", "character"} else esc(c)
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
            snippet = esc(str(brk.get("snippet", "")))
            ch_label = f'{L("chapter")} {ch_num} · {L("scene_unit")} {scene_num}'
            ch_html = chapter_link(ch_num, ch_label) if ch_num > 0 else esc(ch_label)
            parts.append(
                f'<li>{ch_html} '
                f'<span class="badge badge-neutral">{L("scene_paragraph")} {para_idx} · {cue_text}</span> '
                f'<span class="text-muted">{snippet}</span></li>'
            )
        parts.append("</ul></details>")
    parts.append('</section>')
    return "".join(parts)


def render_sentence_dist_panel(
    metrics: Any | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the sentence-length distribution panel."""
    if metrics is None:
        return ""

    L, N, P = panel_formatters(labels, language_key)

    d = metrics.sentence_dist
    rows = [
        ("≤ 6", d.short_count, d.short_pct),
        ("7–15", d.medium_count, d.medium_pct),
        ("16–25", d.long_count, d.long_pct),
        ("> 25", d.complex_count, d.complex_pct),
    ]
    parts: list[str] = [panel_start("dist", labels, "sentence_dist")]
    verb_mattr = getattr(metrics, "verb_mattr", None)
    desc_mattr = getattr(metrics, "desc_mattr", None)
    if verb_mattr is not None or desc_mattr is not None:
        parts.append('<div class="kpi-row">')
        if verb_mattr is not None:
            parts.append(kpi(N(verb_mattr, 3), help_term(labels, "lex_action", L("lex_action_mattr"))))
        if desc_mattr is not None:
            parts.append(kpi(N(desc_mattr, 3), help_term(labels, "lex_desc", L("lex_desc_mattr"))))
        parts.append("</div>")
    parts.append('<div class="dist">')
    for criterion, count, pct in rows:
        parts.append(
            f'<div class="row"><span>{criterion}</span>'
            f'<span class="bar"><i style="width:{max(0.0, min(100.0, pct)):.1f}%"></i></span>'
            f'<span class="val">{N(count, 0)} · {P(pct)}</span></div>'
        )
    parts.append("</div></section>")
    return "".join(parts)


def render_dialogue_panel(
    dialogue: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Render recognized quoted spans and their manuscript word shares."""
    if not dialogue:
        return ""

    L, N, P = panel_formatters(labels, language_key)

    parts: list[str] = [panel_start("dialogue", labels, "panel_dialogue")]
    parts.append('<div class="kpi-row">')
    parts.append(kpi(N(dialogue.get("turns", 0), 0), help_term(labels, "dialogue", L("dlg_turns"))))
    parts.append(kpi(P(dialogue.get("dialogue_pct", 0.0)), L("dialogue")))
    parts.append(kpi(N(dialogue.get("avg_turn_words", 0.0), 1), L("dlg_avg_turn"), jump="#chapters"))
    parts.append(kpi(N(dialogue.get("turns_per_1000", 0.0), 1), L("dlg_turns_per_1000"), jump="#chapters"))
    if "short_turn_pct" in dialogue:
        short_label = esc(
            label(labels, "dlg_short_turns").replace("{max_words}", str(SHORT_TURN_MAX_WORDS))
        )
        parts.append(
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
        parts.append(
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
        parts.append(
            kpi(
                contrast_val,
                help_term(labels, "dlg_voice_contrast", L("dlg_voice_contrast")),
            )
        )
    if dialogue.get("dialogue_tag_available"):
        parts.append(
            kpi(
                N(float(dialogue.get("dialogue_tags_per_1000", 0.0)), 1),
                L("dlg_tags_per_1000"),
            )
        )
        parts.append(
            kpi(
                f'{N(int(dialogue.get("dialogue_tags", 0)), 0)} ({P(float(dialogue.get("dialogue_tag_pct", 0.0)))})',
                L("dlg_tags"),
            )
        )
    if dialogue.get("adverbial_tag_available"):
        parts.append(
            kpi(
                f'{N(int(dialogue.get("adverbial_tags", 0)), 0)} ({P(float(dialogue.get("adverbial_tag_pct", 0.0)))})',
                L("dlg_adverbial_tags"),
            )
        )
    if dialogue.get("indirect_speech_available"):
        parts.append(
            kpi(
                N(int(dialogue.get("indirect_speech", 0)), 0),
                L("dlg_indirect_speech"),
            )
        )
        parts.append(
            kpi(
                N(float(dialogue.get("indirect_speech_per_1000", 0.0)), 1),
                L("dlg_indirect_speech_per_1000"),
            )
        )
    voice_sep = dialogue.get("voice_separation")
    if isinstance(voice_sep, Mapping) and voice_sep.get("available"):
        sep_raw = str(voice_sep.get("separation_label", "unavailable"))
        sep_key = f"dlg_voice_sep_{sep_raw}" if sep_raw in {"distinct", "moderate", "blended", "unavailable"} else "dlg_voice_sep_unavailable"
        parts.append(
            kpi(
                L(sep_key),
                L("dlg_voice_separation"),
            )
        )
    parts.append("</div>")

    dialogue_chapters = dialogue.get("chapters", [])
    if dialogue_chapters:
        parts.append('<div class="dist scrollable">')
        for chapter in dialogue_chapters:
            num = int(chapter.get("chapter_num", 0))
            turns = int(chapter.get("turns", 0))
            turns_label = L("dlg_turns_one" if turns == 1 else "dlg_turns")
            share = float(chapter.get("dialogue_pct", 0.0))
            title_attr = esc(chapter.get("title", ""))
            chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
            parts.append(
                f'<div class="row" data-jump="#ch-{num}" '
                f'title="{title_attr}">'
                f'{chapter_link(num, chapter_label, css_class="label")}'
                f'<span class="bar"><i style="width:{min(100.0, share):.1f}%"></i></span>'
                f'<span class="val">{P(share)} · {turns} {turns_label}</span>'
                f"</div>"
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
            parts.append(
                f'<details class="dialogue-measurements"><summary>{L("dlg_chapter_details")} '
                f"({len(dialogue_chapters)})</summary>"
                f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("dlg_chapter_details")}">'
                "<table><thead><tr>"
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
                    f'<th scope="row">{chapter_link(num, chapter_label)}</th>'
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
    parts.append("</section>")
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
    parts.append(f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("panel_characters")}"><table><thead><tr>')
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
                f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("chr_voices_title")}">'
                "<table><thead><tr>"
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
                        f'<td colspan="4" class="num"><span class="badge badge-neutral">{L("chr_voice_insufficient")}</span></td></tr>'
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
    parts.append("</section>")
    return "".join(parts)


def render_pacing_panel(
    pacing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the pacing curve and scene structure panel."""
    if not (pacing and pacing.get("chapter_list")):
        return ""

    L, N, P = panel_formatters(labels, language_key)

    parts: list[str] = [panel_start("pacing", labels, "panel_pacing")]
    if pacing.get("scenes_are_chapters", False):
        parts.append(f'<p class="ctl-note">{L("pacing_units_note")}</p>')
    parts.append('<div class="kpi-row">')
    parts.append(kpi(N(pacing.get("scenes", 0), 0), L("pac_scenes")))
    parts.append(kpi(N(pacing.get("avg_scene_words", 0.0), 0), L("pac_avg_scene")))
    parts.append(kpi(N(pacing.get("hook_score_mean", 0.0), 2),
                     help_term(labels, "pacing_hook", L("pac_hook_mean"),
                               fields={"max_words": str(HOOK_SHORT_SENTENCE)})))
    if "sentence_overlap_pct" in pacing:
        parts.append(kpi(P(float(pacing.get("sentence_overlap_pct", 0.0))), L("pac_cohesion")))
    if "repeated_start_runs" in pacing:
        parts.append(kpi(N(int(pacing.get("repeated_start_runs", 0)), 0), L("pac_monotony")))
    if pacing.get("sticky_available"):
        parts.append(kpi(P(float(pacing.get("sticky_sentence_pct", 0.0))), L("pac_sticky_pct")))
        parts.append(kpi(P(float(pacing.get("mean_glue_pct", 0.0))), L("pac_glue_mean")))
    rhythm = pacing.get("rhythm_profile")
    if isinstance(rhythm, Mapping) and rhythm.get("available"):
        if rhythm.get("asl_cv") is not None:
            parts.append(kpi(N(float(rhythm["asl_cv"]), 2), L("pac_asl_cv")))
        if rhythm.get("asl_iqr") is not None:
            parts.append(kpi(N(float(rhythm["asl_iqr"]), 1), L("pac_asl_iqr")))
        if rhythm.get("length_entropy") is not None:
            parts.append(kpi(N(float(rhythm["length_entropy"]), 2), L("pac_length_entropy")))
    parts.append("</div>")
    if isinstance(rhythm, Mapping) and rhythm.get("available"):
        buckets = rhythm.get("bucket_shares")
        bucket_txt = ""
        if isinstance(buckets, Mapping):
            s_val = float(buckets.get("short", 0.0))
            m_val = float(buckets.get("medium", 0.0))
            l_val = float(buckets.get("long", 0.0))
            scale = 100.0 if (s_val + m_val + l_val) <= 1.5 else 1.0
            bucket_txt = f' · {L("pac_rhythm_buckets")}: {P(s_val * scale)} / {P(m_val * scale)} / {P(l_val * scale)}'
        parts.append(
            f'<p class="hint pacing-rhythm-profile"><strong>{L("pac_rhythm_profile")}:</strong> '
            f'{L("pac_rhythm_hint")}{bucket_txt}</p>'
        )
    units = FEATURE_UNITS.get(language_key, {}).get("asl", "words per sentence")
    parts.append(f'<p class="panel-guide">{help_term(labels, "asl", L("feat_asl"))} '
                 f'· {esc(units)}. {L("pacing_scale")}</p>')

    chapters_pacing = pacing["chapter_list"]
    max_asl = max((float(c.get("asl", 0.0)) for c in chapters_pacing), default=0.0) or 1.0
    parts.append('<div class="dist scrollable">')
    for chapter in chapters_pacing:
        num = int(chapter.get("chapter_num", 0))
        asl = float(chapter.get("asl", 0.0))
        hook = int(chapter.get("hook_score", 0))
        sparkline = chapter.get("pacing_sparkline") or ""
        spark_html = (
            f'<span class="sparkline" style="font-family:monospace;font-size:var(--text-micro);letter-spacing:.05em;color:var(--accent)" '
            f'title="{L("pac_sparkline")}">{esc(sparkline)}</span> · '
            if sparkline
            else ""
        )
        title_attr = esc(chapter.get("title", ""))
        chapter_label = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
        parts.append(
            f'<div class="row" data-jump="#ch-{num}" '
            f'title="{title_attr}">'
            f'{chapter_link(num, chapter_label, css_class="label")}'
            f'<span class="bar"><i style="width:{min(100.0, asl / max_asl * 100.0):.1f}%"></i></span>'
            f'<span class="val">{spark_html}{L("feat_asl")} {N(asl, 1)} · {L("pac_hook")} {hook}</span>'
            f"</div>"
        )
    parts.append("</div>")
    if any("sentence_overlap_pct" in ch or "repeated_start_runs" in ch or "pacing_sparkline" in ch for ch in chapters_pacing):
        has_sticky_ch = any("sticky_sentence_pct" in ch for ch in chapters_pacing)
        sticky_th = f'<th scope="col" class="num">{L("pac_sticky_pct")}</th>' if has_sticky_ch else ""
        parts.append(
            f'<details class="pacing-measurements"><summary>{L("pac_chapter_details")} '
            f"({len(chapters_pacing)})</summary>"
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("pac_chapter_details")}">'
            "<table><thead><tr>"
            f'<th scope="col">{L("chapter")}</th>'
            f'<th scope="col" class="num">{L("feat_asl")}</th>'
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
            hook = int(chapter.get("hook_score", 0))
            sparkline = chapter.get("pacing_sparkline") or ""
            overlap = float(chapter.get("sentence_overlap_pct", 0.0))
            monotony = int(chapter.get("repeated_start_runs", 0))
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
                f'<td class="num">{N(hook, 0)}</td>'
                f'<td class="num">{P(overlap)}</td>'
                f'<td class="num">{N(monotony, 0)}</td>'
                f"{sticky_cell}"
                f"</tr>"
            )
        parts.append("</tbody></table></div></details>")
    sticky_items = pacing.get("sticky_items") or []
    if sticky_items:
        parts.append(
            f'<details class="pacing-sticky-items"><summary>{L("pac_sticky_items")} ({len(sticky_items)})</summary><ul>'
        )
        for item in sticky_items[:20]:
            ch_num = int(item.get("chapter_num", 0))
            glue_pct = float(item.get("glue_pct", 0.0))
            words_n = int(item.get("words", 0))
            preview = esc(str(item.get("preview", "")))
            ch_label = f'{label(labels, "chapter")} {ch_num}'
            parts.append(
                f'<li>{chapter_link(ch_num, ch_label)} '
                f'<span class="badge badge-neutral">{P(glue_pct)} · {words_n} {L("words")}</span> '
                f'<span class="text-muted">{preview}</span></li>'
            )
        parts.append("</ul></details>")
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
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("genre_corridor_title")}">'
            "<table><thead><tr>"
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
            pos_label = L(pos_key) if pos_key else esc(pos or "–")
            parts.append(
                f"<tr>"
                f'<th scope="row">{m_name}</th>'
                f'<td class="num">{N(obs, 1) if obs is not None else "–"}</td>'
                f'<td class="num">{N(low, 1) if low is not None else "…"} – {N(high, 1) if high is not None else "…"}</td>'
                f'<td><span class="badge badge-neutral">{pos_label}</span></td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div></details>")
    parts.append("</section>")
    return "".join(parts)


def render_motifs_panel(
    motifs: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
) -> str:
    """Render motifs, manuscript phrase totals and local chapter-prose echoes."""
    if not (motifs and (motifs.get("motifs") or motifs.get("repeated_phrases") or motifs.get("echoes"))):
        return ""

    L = panel_label(labels)

    parts: list[str] = [panel_start("motifs", labels, "panel_motifs")]
    if motifs.get("motifs"):
        parts.append(f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("panel_motifs")}"><table><thead><tr>')
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

    if motifs.get("repeated_phrases"):
        parts.append('<div class="table-wrap motif-phrases" tabindex="0" role="region" '
                     f'aria-label="{L("mot_phrase")}"><table><thead><tr>')
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

    if motifs.get("echoes"):
        parts.append(f'<h3>{L("mot_echoes")}</h3><p class="panel-guide">{L("mot_echo_note")}</p>')
        parts.append('<div class="table-wrap motif-echoes" tabindex="0" role="region" '
                     f'aria-label="{L("mot_echoes")}"><table><thead><tr>')
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
        parts.append(f'<details><summary>{L("mot_echo_method")}</summary><p>{L("mot_echo_limits")}</p></details>')

    parts.append("</section>")
    return "".join(parts)


def render_showing_panel(
    showing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
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
    parts.append(f'<p class="ctl-note">{brief_note}</p>'
                 f'<details class="signal-method"><summary>{L("showing_method")}</summary>'
                 f'<p class="ctl-note">{context_note}</p></details>')
    if not comparable:
        note = L("showing_unavailable_note").replace("{min_chapters}", str(MIN_COMPARISON_CHAPTERS))
        parts.append(f'<p class="ctl-note">{note}</p></section>')
        return "".join(parts)
    parts.append('<div class="kpi-row">')
    parts.append(kpi(
        N(float(showing.get("tell_z_mean") or 0.0), 2, signed=True), L("show_tell")
    ))
    parts.append(kpi(
        N(float(showing.get("show_z_mean") or 0.0), 2, signed=True), L("show_show")
    ))
    parts.append(kpi(
        N(float(showing.get("balance_mean") or 0.0), 2, signed=True), L("show_balance")
    ))
    parts.append("</div>")
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
        title_attr = esc(chapter.get("title", ""))
        label_text = f'{label(labels, "chapter")} {num} · {chapter.get("title", "")}'
        if not chapter.get("comparable", True):
            parts.append(
                f'<div class="row unavailable" title="{title_attr}">'
                f'<span class="label">{esc(label_text)}</span>'
                f'<span class="bar"></span>'
                f'<span class="val">–</span>'
                f"</div>"
            )
            continue
        balance = float(chapter.get("balance") or 0.0)
        width = min(50.0, abs(balance) / max_abs * 50.0)
        sign = "signal-negative" if balance < 0 else "signal-positive"
        bar = f'<i class="{sign}" style="width:{width:.1f}%"></i>'
        value = N(balance, 2, signed=True)
        parts.append(
            f'<div class="row" data-jump="#ch-{num}" '
            f'title="{title_attr}">'
            f'{chapter_link(num, label_text, css_class="label")}'
            f'<span class="bar signal-bar" aria-hidden="true">{bar}</span>'
            f'<span class="val">{value}</span>'
            f"</div>"
        )
    parts.append("</div></section>")
    return "".join(parts)
