"""Reusable narration panels (sentence distribution, dialogue, characters, pacing, motifs, showing)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..diversity import MIN_TOKENS_LD
from ..format import num as format_num
from ..format import pct as format_pct
from ..style_fingerprint import FEATURE_UNITS, FEATURES
from ..style_profile import ChapterProfile
from .components import esc, help_term, kpi, label, panel_start


def render_scenes_panel(
    scenes: Mapping[str, Any] | None, labels: Mapping[str, str] | None,
    language_key: str = "en",
) -> str:
    """Show scene observations, sample support and author-defined comparisons."""
    if not scenes:
        return ""
    if scenes.get("error"):
        return (panel_start("scenes", labels, "panel_scenes") +
                f'<p role="status">{esc(scenes["error"])}</p></section>')
    if not scenes.get("items"):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key).replace("{min_tokens}", str(MIN_TOKENS_LD)))

    def N(value: Any) -> str:
        return "—" if value is None else format_num(value, language_key, 2)

    parts = [panel_start("scenes", labels, "panel_scenes"),
             f'<p class="hint">{L("scene_guidance")}</p>',
             f'<p class="hint">{L("scene_support")}</p>']
    for item in scenes["items"]:
        group = esc(item["group"]) if item["group"] else L("scene_unassigned")
        parts.append(f'<details class="scene-detail" data-scene="{esc(item["id"])}"><summary>'
                     f'{esc(item["chapter_title"])} · {L("scene_unit")} {item["scene"]} · {group}'
                     f' · {L("words")}: {item["words"]} · {L("sentences")}: {item["sentences"]}'
                     '</summary>')
        parts.append(f'<p><a class="ctl-link" href="#ch-{item["chapter"]}" data-jump="#ch-{item["chapter"]}">'
                     f'{L("scene_containing_chapter")}: {esc(item["chapter_title"])}→</a></p>')
        parts.append(f'<div class="table-wrap" tabindex="0" role="region" aria-label="{L("panel_scenes")}">'
                     '<table><thead><tr>'
                     f'<th>{L("panel_scenes")}</th><th>{L("scene_value")}</th>'
                     f'<th>{L("scene_se")}</th><th>{L("scene_range")}</th>'
                     f'<th>{L("scene_baseline")}</th></tr></thead><tbody>')
        baseline = scenes["baselines"].get(item["group"], {})
        for field, label_key, unit in FEATURES:
            units = FEATURE_UNITS.get(language_key, {}).get(field, unit)
            target = item["targets"].get(field)
            comparison = "—"
            if target:
                lower = "…" if target["lower"] is None else N(target["lower"])
                upper = "…" if target["upper"] is None else N(target["upper"])
                comparison = f'{lower} – {upper} · {L("scene_" + target["position"])}'
            reference = baseline.get(field, {})
            median = N(reference.get("median"))
            count = reference.get("n", 0)
            parts.append(f'<tr><th>{L(label_key)} <small>{esc(units)}</small></th>'
                         f'<td>{N(item["features"][field])}</td>'
                         f'<td>{N(item["standard_errors"].get(field))}</td><td>{comparison}</td>'
                         f'<td>{median} (n={count})</td></tr>')
        parts.append('</tbody></table></div></details>')
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

    def N(value: float, decimals: int = 1) -> str:
        return format_num(value, language_key, decimals)

    def P(value: float, decimals: int = 1) -> str:
        return format_pct(value, language_key, decimals)

    d = metrics.sentence_dist
    rows = [
        ("≤ 6", d.short_count, d.short_pct),
        ("7–15", d.medium_count, d.medium_pct),
        ("16–25", d.long_count, d.long_pct),
        ("> 25", d.complex_count, d.complex_pct),
    ]
    parts: list[str] = [panel_start("dist", labels, "sentence_dist")]
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
    """Renders the dialogue turns and scenic ratio panel."""
    if not dialogue:
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1) -> str:
        return format_num(value, language_key, decimals)

    def P(value: float, decimals: int = 1) -> str:
        return format_pct(value, language_key, decimals)

    parts: list[str] = [panel_start("dialogue", labels, "panel_dialogue")]
    parts.append('<div class="kpi-row">')
    parts.append(kpi(N(dialogue.get("turns", 0), 0), help_term(labels, "dialogue", L("dlg_turns"))))
    parts.append(kpi(P(dialogue.get("dialogue_pct", 0.0)), L("dialogue")))
    parts.append(kpi(N(dialogue.get("avg_turn_words", 0.0), 1), L("dlg_avg_turn"), jump="#chapters"))
    parts.append(kpi(N(dialogue.get("turns_per_1000", 0.0), 1), L("dlg_turns_per_1000"), jump="#chapters"))
    parts.append("</div>")

    dialogue_chapters = [c for c in dialogue.get("chapters", []) if c.get("turns")]
    if dialogue_chapters:
        top = sorted(dialogue_chapters, key=lambda c: c.get("turns", 0), reverse=True)[:8]
        parts.append('<div class="dist">')
        for chapter in top:
            num = int(chapter.get("chapter_num", 0))
            share = float(chapter.get("dialogue_pct", 0.0))
            title_attr = esc(chapter.get("title", ""))
            parts.append(
                f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
                f'title="{title_attr}">'
                f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
                f'<span class="bar"><i style="width:{min(100.0, share):.1f}%"></i></span>'
                f'<span class="val">{P(share)} · {int(chapter.get("turns", 0))} {esc(label(labels, "dlg_turns"))}</span>'
                f"</div>"
            )
        parts.append("</div>")
    parts.append("</section>")
    return "".join(parts)


def render_characters_panel(
    characters: Mapping[str, Any] | None,
    chapters: Sequence[ChapterProfile],
    labels: Mapping[str, str] | None = None,
) -> str:
    """Renders the character presence panel."""
    if not (characters and characters.get("figures")):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    parts: list[str] = [panel_start("characters", labels, "panel_characters")]
    parts.append('<div class="table-wrap"><table><thead><tr>')
    parts.extend(
        f"<th>{L(key)}</th>"
        for key in (
            "chr_name",
            "chr_mentions",
            "chr_chapters",
            "chr_span",
            "chr_gap",
            "chr_share",
        )
    )
    parts.append("</tr></thead><tbody>")
    total = int(characters.get("chapters", 0))
    for figure in characters["figures"]:
        first = figure.get("first_chapter")
        jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
        share = float(figure.get("presence_ratio", 0.0)) * 100.0
        chapter_span = f"{first}–{figure.get('last_chapter')}" if first else "–"
        first_chapter = next((c for c in chapters if c.num == first), None)
        span_title = (
            f"{L('chapter')} {first} · {esc(first_chapter.title)}"
            if first_chapter is not None
            else ""
        )
        parts.append(
            f'<tr class="row-link"{jump}>'
            f'<td class="name">{esc(figure.get("name", ""))}</td>'
            f'<td class="num">{int(figure.get("mentions", 0))}</td>'
            f'<td class="num">{len(figure.get("chapters_present", []))} / {total}</td>'
            f'<td class="num" title="{span_title}">{esc(chapter_span)}</td>'
            f'<td class="num">{int(figure.get("longest_gap", 0))}</td>'
            f'<td class="num bar-cell"><i style="--v:{min(100.0, share):.1f}%"></i>{share:.0f} %</td>'
            f"</tr>"
        )
    parts.append("</tbody></table></div></section>")
    return "".join(parts)


def render_pacing_panel(
    pacing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the pacing curve and scene structure panel."""
    if not (pacing and pacing.get("chapter_list")):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1) -> str:
        return format_num(value, language_key, decimals)

    parts: list[str] = [panel_start("pacing", labels, "panel_pacing")]
    if pacing.get("scenes_are_chapters", False):
        parts.append(f'<p class="ctl-note">{L("pacing_units_note")}</p>')
    parts.append('<div class="kpi-row">')
    parts.append(kpi(N(pacing.get("scenes", 0), 0), L("pac_scenes")))
    parts.append(kpi(N(pacing.get("avg_scene_words", 0.0), 0), L("pac_avg_scene")))
    parts.append(kpi(N(pacing.get("hook_score_mean", 0.0), 2), L("pac_hook_mean")))
    parts.append("</div>")

    chapters_pacing = pacing["chapter_list"]
    max_asl = max((float(c.get("asl", 0.0)) for c in chapters_pacing), default=0.0) or 1.0
    parts.append('<div class="dist scrollable">')
    for chapter in chapters_pacing:
        num = int(chapter.get("chapter_num", 0))
        asl = float(chapter.get("asl", 0.0))
        hook = int(chapter.get("hook_score", 0))
        title_attr = esc(chapter.get("title", ""))
        parts.append(
            f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
            f'title="{title_attr}">'
            f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
            f'<span class="bar"><i style="width:{min(100.0, asl / max_asl * 100.0):.1f}%"></i></span>'
            f'<span class="val">{N(asl, 1)} · {esc(label(labels, "pac_hook"))} {hook}</span>'
            f"</div>"
        )
    parts.append("</div></section>")
    return "".join(parts)


def render_motifs_panel(
    motifs: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
) -> str:
    """Renders the motifs and repeated phrases panel."""
    if not (motifs and (motifs.get("motifs") or motifs.get("repeated_phrases"))):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    parts: list[str] = [panel_start("motifs", labels, "panel_motifs")]
    if motifs.get("motifs"):
        parts.append('<div class="table-wrap"><table><thead><tr>')
        parts.extend(
            f"<th>{L(key)}</th>" for key in ("mot_name", "mot_count", "mot_chapters", "chr_gap")
        )
        parts.append("</tr></thead><tbody>")
        for motif in motifs["motifs"]:
            first = motif.get("first_chapter")
            jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
            motif_span = f"{first}–{motif.get('last_chapter')}" if first else "–"
            parts.append(
                f'<tr class="row-link"{jump}>'
                f'<td class="name">{esc(motif.get("name", ""))}</td>'
                f'<td class="num">{int(motif.get("mentions", 0))}</td>'
                f'<td class="num">{esc(motif_span)}</td>'
                f'<td class="num">{int(motif.get("longest_gap", 0))}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")

    if motifs.get("repeated_phrases"):
        parts.append('<div class="table-wrap"><table><thead><tr>')
        parts.extend(
            f"<th>{L(key)}</th>" for key in ("mot_phrase", "mot_count", "mot_chapters")
        )
        parts.append("</tr></thead><tbody>")
        for phrase in motifs["repeated_phrases"]:
            chapter_list_text = ", ".join(str(c) for c in phrase.get("chapters", []))
            first = phrase.get("chapters", [None])[0]
            jump = f' data-jump="#ch-{int(first)}" role="button" tabindex="0"' if first else ""
            parts.append(
                f'<tr class="row-link"{jump}>'
                f'<td class="name">{esc(phrase.get("phrase", ""))}</td>'
                f'<td class="num">{int(phrase.get("count", 0))}</td>'
                f'<td class="num">{esc(chapter_list_text)}</td>'
                f"</tr>"
            )
        parts.append("</tbody></table></div>")

    parts.append("</section>")
    return "".join(parts)


def render_showing_panel(
    showing: Mapping[str, Any] | None,
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
) -> str:
    """Renders the showing vs. telling panel."""
    if not (showing and showing.get("chapter_list")):
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    showing_chapters = showing["chapter_list"]
    comparable = len(showing_chapters) >= 3 and any(
        float(chapter.get("tell_z", 0.0) or 0.0) != 0.0
        or float(chapter.get("show_z", 0.0) or 0.0) != 0.0
        for chapter in showing_chapters
    )
    parts: list[str] = [panel_start("showing", labels, "panel_showing")]
    parts.append(f'<p class="ctl-note">{L("showing_context_note")}</p>')
    if not comparable:
        parts.append(f'<p class="ctl-note">{L("showing_unavailable_note")}</p>')
    parts.append('<div class="kpi-row">')
    parts.append(kpi(
        N(showing.get("tell_z_mean", 0.0), 2, signed=True) if comparable else "–", L("show_tell")
    ))
    parts.append(kpi(
        N(showing.get("show_z_mean", 0.0), 2, signed=True) if comparable else "–", L("show_show")
    ))
    parts.append(kpi(
        N(showing.get("balance_mean", 0.0), 2, signed=True) if comparable else "–", L("show_balance")
    ))
    parts.append("</div>")

    max_abs = (
        max((abs(float(c.get("balance", 0.0))) for c in showing_chapters), default=0.0) or 1.0
    )
    parts.append('<div class="dist scrollable">')
    for chapter in showing_chapters:
        num = int(chapter.get("chapter_num", 0))
        balance = float(chapter.get("balance", 0.0))
        width = min(100.0, abs(balance) / max_abs * 100.0)
        bar = f'<i style="width:{width:.1f}%"></i>' if comparable else ""
        value = N(balance, 2, signed=True) if comparable else "–"
        title_attr = esc(chapter.get("title", ""))
        parts.append(
            f'<div class="row" data-jump="#ch-{num}" role="button" tabindex="0" '
            f'title="{title_attr}">'
            f'<span class="label">{L("chapter")} {num} · {esc(chapter.get("title", ""))}</span>'
            f'<span class="bar">{bar}</span>'
            f'<span class="val">{value}</span>'
            f"</div>"
        )
    parts.append("</div></section>")
    return "".join(parts)
