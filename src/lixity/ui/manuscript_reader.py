"""Shared display controls for the canonical manuscript paragraph tree."""

from collections.abc import Mapping, Sequence
from html import escape

from ..style_profile import ChapterProfile
from .components import label
from .manuscript_document import ReaderBlock

INLINE_EVIDENCE_LAYERS = ("sticky", "dialogue_tag", "echo")


def inline_evidence_controls(labels: Mapping[str, str] | None) -> str:
    """Render inline evidence layer toggle chips for the reader analysis bar."""
    def text(key: str) -> str:
        return escape(label(labels, key), quote=True)

    chips = "".join(
        f'<button type="button" class="ctl reader-evidence-chip" '
        f'data-evidence-layer="{layer_key}" aria-pressed="false" '
        f'data-help="{text("reading_help_evidence_" + layer_key)}">'
        f'<span class="evidence-chip-swatch evidence-chip-swatch-{layer_key}" aria-hidden="true"></span>'
        f'<span>{text("evidence_layer_" + layer_key)}</span></button>'
        for layer_key in INLINE_EVIDENCE_LAYERS
    )
    return (
        f'<div class="reader-inline-evidence-layers" id="reader-inline-evidence-layers" '
        f'role="group" aria-label="{text("reading_inline_evidence")}">{chips}</div>'
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
    def text(key: str) -> str:
        return escape(label(labels, key), quote=True)

    options = "".join(
        f'<option value="ch-{chapter.num}">{chapter.num}. {escape(chapter.title)}</option>'
        for chapter in chapters
    )
    if reader_document:
        source_chapters = [block for block in reader_document if block.is_chapter]
        if source_chapters:
            profiled = {chapter.start_line: chapter for chapter in chapters}
            choices = []
            for block in source_chapters:
                chapter = profiled.get(block.start_line)
                target = f"ch-{chapter.num}" if chapter else f"source-{block.start_line}"
                title = f"{chapter.num}. {chapter.title}" if chapter else block.text
                choices.append(f'<option value="{target}">{escape(title)}</option>')
            options = "".join(choices)
        if not reader_document[0].is_chapter and source_chapters:
            options = f'<option value="reader-preface">{text("reading_view")}</option>' + options
    focus_icon = (
        '<svg class="lixity-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
        '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>'
    )
    teleprompter_icon = (
        '<svg class="lixity-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect width="16" height="18" x="4" y="3" rx="2"/><path d="M8 8h8"/>'
        '<path d="m8 12 2 1.5L8 15"/><path d="M12 13.5h4"/></svg>'
    )
    overview_icon = (
        '<svg class="lixity-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/>'
        '<rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/></svg>'
    )
    direct_speech_icon = (
        '<svg class="lixity-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" '
        'stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
    )
    return (
        '<div class="manuscript-reader-controls" id="manuscript-reader-controls" hidden>'
        f'<select id="manuscript-mode" hidden aria-hidden="true" tabindex="-1"><option value="read">{text("reading_read")}</option>'
        f'<option value="inspect">{text("reading_inspect")}</option></select>'
        f'<select class="ctl reader-chapter" id="reader-chapter" aria-label="{text("reading_chapter")}">'
        f'<option value="">{text("reading_chapter")}…</option>{options}</select>'
        '<details class="reader-settings" id="reader-settings" name="reader-settings">'
        f'<summary class="ctl reader-compact-control" aria-label="{text("reading_appearance")}">'
        '<span class="reader-control-icon" aria-hidden="true">Aa</span>'
        f'<span class="reader-control-label">{text("reading_appearance")}</span></summary><div class="reader-settings-body">'
        f'<div class="reader-size-controls" role="group" aria-label="{text("reading_size")}">'
        f'<button class="ctl" type="button" id="reader-text-smaller" aria-label="{text("reading_smaller")}">A−</button>'
        '<output id="reader-size-value" aria-live="polite">18</output>'
        f'<button class="ctl" type="button" id="reader-text-larger" aria-label="{text("reading_larger")}">A+</button></div>'
        f'<label for="reader-width">{text("reading_width")}</label><select class="ctl" id="reader-width">'
        f'<option value="narrow">{text("reading_narrow")}</option><option value="standard" selected>{text("reading_standard")}</option>'
        f'<option value="wide">{text("reading_wide")}</option></select>'
        f'<label for="reader-spacing">{text("reading_spacing")}</label><select class="ctl" id="reader-spacing">'
        f'<option value="compact">{text("reading_compact")}</option><option value="standard" selected>{text("reading_standard")}</option>'
        f'<option value="relaxed">{text("reading_relaxed")}</option></select>'
        f'<div class="reader-shortcuts"><strong>{text("reading_shortcuts")}</strong><dl>'
        f'<dt><kbd>P</kbd></dt><dd>{text("reading_teleprompter")}</dd>'
        f'<dt><kbd>D</kbd></dt><dd>{text("reading_direct_speech")}</dd>'
        f'<dt><kbd>Shift+F10</kbd></dt><dd>{text("reading_shortcut_actions")}</dd>'
        f'<dt><kbd>Enter</kbd></dt><dd>{text("reading_shortcut_search")}</dd>'
        f'<dt><kbd>Esc</kbd></dt><dd>{text("reading_shortcut_close")}</dd>'
        '</dl></div></div></details>'
        f'<button class="ctl reader-compact-control" type="button" id="reader-focus" aria-pressed="false" '
        f'aria-label="{text("reading_focus")}" title="{text("reading_focus")}" '
        f'data-help="{text("reading_help_focus")}"><span class="reader-control-icon" aria-hidden="true">{focus_icon}</span>'
        f'<span class="reader-control-label">{text("reading_focus")}</span></button>'
        f'<button class="ctl reader-compact-control" type="button" id="reader-teleprompter" aria-pressed="false" '
        f'aria-label="{text("reading_teleprompter")}" title="{text("reading_teleprompter")}" aria-keyshortcuts="P" '
        f'data-help="{text("reading_help_teleprompter")}"><span class="reader-control-icon" aria-hidden="true">{teleprompter_icon}</span>'
        f'<span class="reader-control-label">{text("reading_teleprompter")}</span></button>'
        f'<button class="ctl reader-compact-control" type="button" id="reader-direct-speech" aria-pressed="false" '
        f'aria-label="{text("reading_direct_speech")}" title="{text("reading_direct_speech")}" aria-keyshortcuts="D" '
        f'data-help="{text("reading_help_direct_speech")}"><span class="reader-control-icon" aria-hidden="true">{direct_speech_icon}</span>'
        f'<span class="reader-control-label">{text("reading_direct_speech")}</span></button>'
        '<div class="reader-analysis-toggle-controls">'
        f'<button class="ctl analysis-toggle" type="button" id="manuscript-analysis-toggle" '
        f'aria-label="{text("reading_analysis")}" aria-pressed="false" data-help="{text("reading_help_analysis")}">'
        '<span class="analysis-switch" aria-hidden="true"></span>'
        f'{text("reading_analysis")} <span class="analysis-state" aria-hidden="true">'
        f'<span class="analysis-state-measure">{text("reading_on")}</span>'
        f'<span class="analysis-state-measure">{text("reading_off")}</span>'
        f'<span id="manuscript-analysis-state">{text("reading_off")}</span></span></button>'
        '<details class="reader-settings reader-analysis-guide" id="reader-analysis-guide" name="reader-settings" hidden>'
        f'<summary class="ctl" aria-label="{text("analysis_guide_title")}">?</summary>'
        '<div class="reader-settings-body">'
        f'<strong>{text("analysis_guide_title")}</strong>'
        f'<p>{text("analysis_guide_intro")}</p>'
        '<p class="ctl-note" id="reader-analysis-guide-state" role="status" aria-live="polite"></p>'
        f'<ol><li><button type="button" class="ctl" data-analysis-guide-action="choose">{text("analysis_guide_choose")}</button></li>'
        f'<li><button type="button" class="ctl" data-analysis-guide-action="example" disabled>{text("analysis_guide_count")}</button></li>'
        f'<li><button type="button" class="ctl" data-analysis-guide-action="explore">{text("reading_explore_passage")}</button></li></ol>'
        f'<p class="ctl-note">{text("analysis_guide_compare")}</p>'
        '</div></details></div>'
        f'<button class="ctl reader-compact-control" type="button" id="workbench-overview-open" '
        f'aria-label="{text("reading_overview")}" title="{text("reading_overview")}" '
        f'data-help="{text("reading_help_overview")}"><span class="reader-control-icon" aria-hidden="true">{overview_icon}</span>'
        f'<span class="reader-control-label">{text("reading_overview")}</span></button>'
        f'{companion_controls}'
        f'<strong class="workbench-surface-label" id="workbench-overview-label" hidden>{text("reading_overview")}</strong>'
        f'<button class="ctl" type="button" id="workbench-overview-back" hidden '
        f'data-help="{text("reading_help_return")}">{text("reading_back")}</button>'
        f'{analysis_controls}'
        f'{overview_navigation}'
        '</div><div class="reader-secondary-controls">'
        f'<button class="ctl" type="button" id="workbench-return" hidden '
        f'data-help="{text("reading_help_return")}">{text("reading_back")}</button>'
        '</div>'
        '<aside class="reader-inspector panel" id="reader-inspector" hidden '
        'aria-labelledby="reader-inspector-title"><div class="workspace-reader-head">'
        f'<h2 id="reader-inspector-title">{text("reading_explore_passage")}</h2>'
        f'<button class="ctl" type="button" id="reader-inspector-close" aria-label="{text("modal_close")}" title="{text("modal_close")}" aria-keyshortcuts="Escape">✕</button>'
        '</div><div id="reader-inspector-body"></div></aside>'
        f'<div class="manuscript-context-menu" id="manuscript-context-menu" role="menu" aria-label="{text("reading_actions")}" hidden></div>'
        f'<div class="manuscript-selection-tools" id="manuscript-selection-tools" role="toolbar" aria-label="{text("reading_actions")}" hidden></div>'
    )
