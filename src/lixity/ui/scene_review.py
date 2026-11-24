"""Presentation of scene evidence and the author's separate rehearsal workspace."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..analysis_intents import INTENT_KINDS, INTENT_TEXT_LIMIT, INTENT_VOICE_LIMIT
from .components import (
    badge,
    details_start,
    esc,
    form_field,
    label,
    panel_formatters,
    panel_guide,
    panel_label,
    select_control,
    status_banner,
)


def scene_claim(labels: Mapping[str, str] | None, level: int) -> str:
    return badge(
        f"L{level} · {label(labels, f'scene_claim_{level}')}",
        extra_attrs=f'data-claim-level="L{level}"',
    )


def scene_track(value: float | None, limit: float, text: str) -> str:
    """The accessible cell contains the actual value, independent of the scale."""
    if value is None:
        return text
    width = min(100.0, max(0.0, value / limit * 100))
    return (
        '<span class="scene-track">'
        f'<span class="scene-track-bar" aria-hidden="true"><i style="width:{width:.1f}%"></i></span>'
        f'<span>{text}</span></span>'
    )


def render_scene_evidence(
    item: Mapping[str, Any],
    report: Mapping[str, Any],
    labels: Mapping[str, str] | None,
    language: str,
) -> str:
    L, N, _ = panel_formatters(labels, language)

    def T(key: str, **fields: str) -> str:
        return esc(label(labels, key).format(**fields))

    blocks = item.get("quote_blocks")
    target = f'scene-evidence-{item["chapter"]}-{item["scene"]}'
    parts = [f'<div class="scene-evidence" id="{esc(target)}" tabindex="-1">']
    if isinstance(blocks, Mapping):
        sample = T("scene_quote_sample", quoted=N(blocks["words"], 0), words=N(item["words"], 0))
        parts.append(f'<p class="scene-sample">{scene_claim(labels, 0)} {sample}</p>')
    if isinstance(blocks, Mapping) and (limits := report.get("quote_block_limits")):
        short, long = limits["short_max_words"], limits["long_min_words"]
        medium = (
            f"{N(short + 1, 0)}–{N(long - 1, 0)}" if long - short > 2 else
            N(short + 1, 0) if long - short == 2 else ""
        )
        ranges = (f"≤ {N(short, 0)}", medium, f"≥ {N(long, 0)}")
        count = [
            f'{L("scene_block_" + key)} ({bound} {L("words")}) <strong>{N(blocks[key], 0)}</strong>'
            for key, bound in zip(("short", "medium", "long"), ranges, strict=True) if bound
        ]
        parts.append(
            f'<div><h3>{L("scene_quote_lengths")} {scene_claim(labels, 2)}</h3>'
            '<ul class="scene-block-counts">' + "".join(f"<li>{entry}</li>" for entry in count) + "</ul>"
            f'<p class="ctl-note">{L("scene_quote_lengths_help")}</p>'
        )
        if blocks["unresolved_ranges"]:
            parts.append(f'<p class="ctl-note">{L("scene_quote_unresolved")}</p>')
        parts.append("</div>")

    if (limits := report.get("within_scene_limits")) and "within_scene" in item:
        halves = item["within_scene"]
        parts.append(f'<div><h3>{L("scene_half_comparison")} {scene_claim(labels, 1)}</h3>')
        if halves:
            for key in ("asl", "dialogue"):
                delta = item.get(key + "_shift")
                if delta is not None:
                    parts.append(f'<p>{T("scene_half_" + key, delta=N(delta, 2, signed=True))}</p>')
            samples = {
                f"{side}_{unit}": N(halves[side][unit], 0)
                for side in ("first", "second") for unit in ("words", "sentences", "quote_words")
            }
            parts.append(f'<p class="ctl-note">{T("scene_half_samples", **samples)}</p>')
        floor = T("scene_half_rule", words=N(limits["min_words"], 0), sentences=N(limits["min_sentences"], 0))
        parts.append(f'<p class="ctl-note">{floor}</p></div>')
    if isinstance(blocks, Mapping):
        prompt = badge(f'L3 · {label(labels, "scene_voice_prompt")}', extra_attrs='data-claim-level="L3"')
        parts.append(f'<p class="scene-voice-prompt">{prompt} {L("scene_voice_question")}</p>')
    parts.append("</div>")
    return "".join(parts)


def render_rehearsal(
    items: Sequence[Mapping[str, Any]], labels: Mapping[str, str] | None,
    *, project_token: str,
) -> str:
    L = panel_label(labels)
    scene_options = "".join(
        f'<option value="{esc(item["id"])}">{esc(item["chapter_title"])} · '
        f'{L("scene_unit")} {item["scene"]}</option>'
        for item in items
    )
    beat_options = "".join(f'<option value="{kind}">{L("scene_intent_" + kind)}</option>' for kind in INTENT_KINDS)

    def field(name: str, input_html: str) -> str:
        return form_field("scene-intent-" + name, L("scene_intent_" + name), input_html)

    fields = [
        field("scene", select_control("scene-intent-scene",
                                      f'<option value="">{L("scene_intent_choose")}</option>' + scene_options,
                                      attributes={"name": "scene_id", "required": ""})),
        field("kind", select_control("scene-intent-kind", beat_options, attributes={"name": "kind"})),
        field("text", f'<textarea id="scene-intent-text" name="intent" rows="2" maxlength="{INTENT_TEXT_LIMIT}" required></textarea>'),
        field("voice", f'<input id="scene-intent-voice" name="voice" type="text" maxlength="{INTENT_VOICE_LIMIT}">'),
        field("hypothesis", f'<input id="scene-intent-hypothesis" name="hypothesis" type="text" maxlength="{INTENT_TEXT_LIMIT}">'),
    ]
    edit_card = (
        f'<button type="button" class="ctl ctl-sm" data-intent-action="edit">{L("scene_intent_edit")}</button>'
        if items else ""
    )
    return (
        details_start(f'{L("scene_rehearsal")} {scene_claim(labels, 3)}', element_id="scene-rehearsal")
        + f'<input type="hidden" id="scene-intents-token" value="{esc(project_token)}">'
        + panel_guide(L("scene_rehearsal_help" if items else "scene_intent_no_scene"))
        + status_banner("scene-rehearsal-status")
        + f'<button class="ctl" type="button" data-intent-action="load" hidden>{L("scene_intent_reload")}</button>'
        f'<p id="scene-rehearsal-empty" hidden>{L("scene_rehearsal_empty")}</p>'
        '<ol id="scene-intent-order"></ol>'
        '<div class="row" id="scene-rehearsal-order-actions" hidden>'
        f'<button type="button" class="ctl primary" data-intent-action="save_order">{L("scene_intent_save_order")}</button>'
        f'<button type="button" class="ctl" data-intent-action="reset_order">{L("scene_intent_reset_order")}</button></div>'
        + details_start(L("scene_intent_add"), element_id="scene-intent-editor",
                        extra_class="" if items else "scene-intent-editor-unavailable")
        + '<form id="scene-intent-form" autocomplete="off"><fieldset disabled><div class="scene-intent-fields">'
        + "".join(fields) + '</div><div class="row">'
        f'<button type="submit" class="ctl primary">{L("scene_intent_save")}</button>'
        f'<button type="button" class="ctl" data-intent-action="cancel">{L("modal_cancel")}</button>'
        '</div></fieldset></form></details>'
        '<template id="scene-intent-card"><li class="scene-intent-card">'
        '<p class="scene-intent-card-heading"><strong data-intent-field="kind"></strong> '
        '<span class="badge badge-neutral" data-intent-field="status"></span></p>'
        '<p data-intent-field="intent"></p><p data-intent-field="voice"></p>'
        '<p data-intent-field="hypothesis"></p>'
        '<p><span data-intent-field="scene"></span> '
        f'<a class="ctl-link" data-intent-field="scene-link">{L("scene_intent_open_scene")}</a></p>'
        f'<div class="row">{edit_card}'
        f'<button type="button" class="ctl ctl-sm" data-intent-action="up">{L("scene_intent_up")}</button>'
        f'<button type="button" class="ctl ctl-sm" data-intent-action="down">{L("scene_intent_down")}</button>'
        f'<button type="button" class="ctl ctl-sm" data-intent-action="delete">{L("scene_intent_delete")}</button>'
        '</div></li></template></details>'
    )
