"""Shared display controls for the canonical manuscript paragraph tree."""

from collections.abc import Callable, Mapping, Sequence
from html import escape

from ..style_fingerprint import FEATURE_UNITS, LAYER_FEATURES, ParagraphLayerData
from ..style_profile import ChapterProfile
from .components import (
    close_button,
    compact_control,
    help_term,
    label,
    metric_reference_link,
    panel_label,
    select_control,
    ui_icon,
)
from .manuscript_document import ReaderBlock

# Quotation evidence in the reader identifies marked text. The share still
# belongs to the chapter and manuscript reports, which have a useful scope.
PARAGRAPH_COMPARISON_LAYERS = tuple(key for key in LAYER_FEATURES if key != "dialogue")

_LAYER_GROUPS = (
    ("layer_group_rhythm", ("asl", "function", "sticky")),
    ("layer_group_voice", ("dialogue", "dialogue_tag", "indirect_speech", "filter", "sensory", "echo")),
    ("layer_group_grammar", ("passive", "modal", "nominal")),
)
_READER_WIDTHS = (("narrow", "54ch"), ("standard", "68ch"), ("wide", "78ch"))
_READER_SPACING = (("compact", "1.5"), ("standard", "1.8"), ("relaxed", "2.1"))
_READER_SIZE_DEFAULT = 18
_READER_SIZE_MIN = 16
_READER_SIZE_MAX = 28
_READER_SIZE_STEP = 2


def _appearance_choices(
    text: Callable[[str], str], key: str, css_property: str, choices: Sequence[tuple[str, str]],
) -> str:
    """Supply one set of choices to the visible controls and their select."""
    buttons = []
    options = []
    for value, css_value in choices:
        title = text(f"reading_{value}")
        selected = value == "standard"
        pressed = "true" if selected else "false"
        selected_attr = " selected" if selected else ""
        buttons.append(
            f'<button type="button" class="ctl ctl-sm" data-reader-choice="{value}" '
            f'aria-pressed="{pressed}">{title}</button>'
        )
        options.append(f'<option value="{value}" data-css-value="{css_value}"{selected_attr}>{title}</option>')
    control_id = f"reader-{key}"
    return (
        '<div class="reader-setting-field">'
        f'<span class="reader-setting-label" id="{control_id}-label">{text(f"reading_{key}")}</span>'
        f'<div class="reader-segmented" role="group" aria-labelledby="{control_id}-label">'
        f'{"".join(buttons)}<select class="ctl reader-segmented-native" id="{control_id}" '
        f'data-reader-setting="{key}" data-css-property="{css_property}" aria-hidden="true" tabindex="-1">'
        f'{"".join(options)}</select></div></div>'
    )


def reading_metric_control(
    labels: Mapping[str, str] | None, language: str, comparisons: ParagraphLayerData, *,
    available: frozenset[str] | None = None, include_evidence: bool, report: bool,
) -> str:
    """Render the shared metric selector from the prepared analysis."""
    text = panel_label(labels)
    units = FEATURE_UNITS.get(language, FEATURE_UNITS["en"])

    def option(key: str) -> str:
        inline = key not in PARAGRAPH_COMPARISON_LAYERS
        if inline and not include_evidence:
            return ""
        has_metric_labels = key in LAYER_FEATURES
        title = text(("layer_" if has_metric_labels else "evidence_layer_") + key)
        unavailable = available is not None and key not in available
        if unavailable:
            title = f'{text("metric_context_missing")} · {title}'
        hint = text(("layer_hint_" if has_metric_labels else "reading_help_evidence_") + key)
        unit = "" if inline else escape(units[LAYER_FEATURES[key]])
        capability = ' data-available="0"' if unavailable else ""
        inline_attr = ' data-inline-evidence="1"' if inline else ""
        comparable = 0 if inline else len(comparisons.get(key, {}))
        return (f'<option value="{key}" data-hint="{hint}" data-unit="{unit}" '
                f'data-comparable="{comparable}" data-reference="measure-{key}"'
                f'{capability}{inline_attr}>{title}</option>')

    groups = "".join(f'<optgroup label="{text(group)}">{"".join(map(option, keys))}</optgroup>'
                     for group, keys in _LAYER_GROUPS)
    additional = "".join(option(key) for key in LAYER_FEATURES
                         if not any(key in keys for _, keys in _LAYER_GROUPS))
    title = help_term(labels, "layer", text("style_layer")) if report else text("analysis_measure")
    options = f'<option value="">{text("layer_off")}</option>{groups}{additional}'
    picker = select_control(
        "style-layer", options, accessible_name=label(labels, "analysis_measure"),
        help_text=label(labels, "reading_help_measure"),
    )
    return (
        f'<label class="metric-layer-control"><span class="metric-layer-label">{title}</span> {picker}</label>'
    )


def reading_controls(
    chapters: Sequence[ChapterProfile], labels: Mapping[str, str] | None,
    reader_document: Sequence[ReaderBlock] | None = None,
    *,
    companion_controls: str = "",
    analysis_controls: str = "",
    overview_navigation: str = "",
) -> str:
    """Render progressive-enhancement controls; no second manuscript copy."""
    text = panel_label(labels)

    def chapter_option(target: str, title: str, number: int | None) -> str:
        metadata = f' data-chapter-number="{number}"' if number is not None else ""
        return f'<option value="{escape(target)}"{metadata}>{escape(title)}</option>'

    options = "".join(
        chapter_option(f"ch-{chapter.num}", f"{chapter.num}. {chapter.title}", chapter.num)
        for chapter in chapters
    )
    if reader_document:
        source_chapters = [block for block in reader_document if block.is_chapter]
        if source_chapters:
            profiled = {chapter.start_line: chapter for chapter in chapters}
            choices = []
            for block in source_chapters:
                chapter = profiled.get(block.start_line)
                number = chapter.num if chapter else block.chapter_num
                target = f"ch-{number}" if number is not None else f"source-{block.start_line}"
                title = chapter.title if chapter else block.text
                numbered_title = f"{number}. {title}" if number is not None else title
                choices.append(chapter_option(target, numbered_title, number))
            options = "".join(choices)
        if not reader_document[0].is_chapter and source_chapters:
            number = chapters[0].num if chapters and chapters[0].start_line < source_chapters[0].start_line else None
            target = f"ch-{number}" if number is not None else "reader-preface"
            options = chapter_option(target, label(labels, "reading_view"), number) + options
    chapter_picker = select_control(
        "reader-chapter", f'<option value="">{text("reading_chapter")}…</option>{options}',
        accessible_name=label(labels, "reading_chapter"), css_class="reader-chapter",
    )
    width_choices = _appearance_choices(text, "width", "--reader-measure", _READER_WIDTHS)
    spacing_choices = _appearance_choices(text, "spacing", "--reader-leading", _READER_SPACING)
    help_icon = ui_icon("help-circle")
    appearance_summary = compact_control(
        label(labels, "reading_appearance"), "type", tag="summary",
    )
    focus_btn = compact_control(
        label(labels, "reading_focus"), "maximize-2", control_id="reader-focus",
        help_text=label(labels, "reading_help_focus"), pressed=False,
    )
    teleprompter_btn = compact_control(
        label(labels, "reading_teleprompter"), "teleprompter", control_id="reader-teleprompter",
        help_text=label(labels, "reading_help_teleprompter"), pressed=False, keyshortcuts="P",
    )
    direct_speech_btn = compact_control(
        label(labels, "reading_direct_speech"), "message-square", control_id="reader-direct-speech",
        help_text=label(labels, "reading_help_direct_speech"), pressed=False, keyshortcuts="D",
    )
    overview_btn = compact_control(
        label(labels, "reading_overview"), "layout-grid", control_id="workbench-overview-open",
        css_class="ctl reader-compact-control reader-overview-control",
        help_text=label(labels, "reading_help_overview"),
    )
    inspector_close_btn = close_button(
        label(labels, "modal_close"), control_id="reader-inspector-close",
    )
    return (
        '<div class="manuscript-reader-controls" id="manuscript-reader-controls" hidden>'
        f'{chapter_picker}'
        '<details class="reader-settings" id="reader-settings" name="reader-settings">'
        f'{appearance_summary}<div class="reader-settings-body">'
        f'<div class="reader-size-controls" role="group" aria-label="{text("reading_size")}">'
        f'<button class="ctl" type="button" id="reader-text-smaller" aria-label="{text("reading_smaller")}">A−</button>'
        f'<output id="reader-size-value" aria-live="polite" data-min="{_READER_SIZE_MIN}" '
        f'data-max="{_READER_SIZE_MAX}" data-step="{_READER_SIZE_STEP}">{_READER_SIZE_DEFAULT}</output>'
        f'<button class="ctl" type="button" id="reader-text-larger" aria-label="{text("reading_larger")}">A+</button></div>'
        f'{width_choices}{spacing_choices}'
        f'<div class="reader-shortcuts"><strong>{text("reading_shortcuts")}</strong><dl>'
        f'<dt><kbd>P</kbd></dt><dd>{text("reading_teleprompter")}</dd>'
        f'<dt><kbd>D</kbd></dt><dd>{text("reading_direct_speech")}</dd>'
        f'<dt><kbd>Shift+F10</kbd></dt><dd>{text("reading_shortcut_actions")}</dd>'
        f'<dt><kbd>Enter</kbd></dt><dd>{text("reading_shortcut_search")}</dd>'
        f'<dt><kbd>Esc</kbd></dt><dd>{text("reading_shortcut_close")}</dd>'
        '</dl></div></div></details>'
        f'{focus_btn}{teleprompter_btn}{direct_speech_btn}'
        '<div class="reader-analysis-toggle-controls">'
        f'<button class="ctl analysis-toggle" type="button" id="manuscript-analysis-toggle" '
        f'aria-label="{text("reading_analysis")}" title="{text("reading_analysis")}" aria-pressed="false" data-help="{text("reading_help_analysis")}">'
        '<span class="analysis-switch" aria-hidden="true"></span>'
        f'{text("reading_analysis")} <span class="analysis-state" aria-hidden="true">'
        f'<span class="analysis-state-measure">{text("reading_on")}</span>'
        f'<span class="analysis-state-measure">{text("reading_off")}</span>'
        f'<span id="manuscript-analysis-state">{text("reading_off")}</span></span></button>'
        '<details class="reader-settings reader-analysis-guide" id="reader-analysis-guide" name="reader-settings" hidden>'
        f'<summary class="ctl" aria-label="{text("analysis_guide_title")}" title="{text("analysis_guide_title")}" data-help="{text("analysis_guide_intro")}">'
        f'<span class="reader-control-icon" aria-hidden="true">{help_icon}</span>'
        f'<span class="reader-control-label" aria-hidden="true">{text("analysis_guide_title")}</span></summary>'
        '<div class="reader-settings-body">'
        '<p class="ctl-note ctl-guidance" id="reader-analysis-guide-state" role="status"></p>'
        '<p class="ctl-note" id="reader-metric-definition" hidden></p>'
        '<div class="reader-guide-actions">'
        f'<button type="button" class="ctl" data-analysis-guide-action="example" hidden>{text("analysis_guide_count")}</button>'
        f'<button type="button" class="ctl primary" data-analysis-guide-action="choose">{text("analysis_guide_enable")}</button>'
        f'<button type="button" class="ctl" data-analysis-guide-action="explore" hidden>{text("reading_explore_passage")}</button></div>'
        f'<p class="ctl-note" id="reader-guide-counted" hidden><strong class="analysis-evidence-swatch">{text("legend_counted_text")}</strong> '
        f'{text("reading_help_counted")}</p>'
        f'<p class="ctl-note" id="reader-guide-comparison" hidden>{text("analysis_guide_compare")}</p>'
        f'<p class="ctl-note">{metric_reference_link(labels, "measurements", element_id="reader-metric-reference")}</p>'
        '</div></details></div>'
        f'{overview_btn}'
        f'{companion_controls}'
        '<div class="workbench-overview-toolbar" id="workbench-overview-toolbar" hidden>'
        f'<strong class="workbench-surface-label">{text("reading_overview")}</strong>'
        '<div class="workbench-overview-actions">'
        f'<a class="ctl" id="workbench-overview-sections" href="#analysis-workflows" '
        f'aria-controls="analysis-workflows">{text("workflow_choose_section")}</a>'
        f'<button class="ctl" type="button" id="workbench-overview-back" '
        f'data-help="{text("reading_help_return")}">{text("reading_back")}</button></div></div>'
        f'{analysis_controls}'
        f'{overview_navigation}'
        '</div><div class="reader-secondary-controls">'
        f'<button class="ctl" type="button" id="workbench-return" hidden '
        f'data-help="{text("reading_help_return")}">{text("reading_back")}</button>'
        '</div>'
        '<aside class="reader-inspector panel" id="reader-inspector" hidden '
        'aria-labelledby="reader-inspector-title"><div class="workspace-reader-head">'
        f'<h2 id="reader-inspector-title">{text("reading_explore_passage")}</h2>'
        f'{inspector_close_btn}'
        '</div><div id="reader-inspector-body"></div></aside>'
        f'<div class="manuscript-context-menu" id="manuscript-context-menu" role="menu" aria-label="{text("reading_actions")}" hidden></div>'
        f'<div class="manuscript-selection-tools" id="manuscript-selection-tools" role="toolbar" aria-label="{text("reading_actions")}" hidden></div>'
    )
