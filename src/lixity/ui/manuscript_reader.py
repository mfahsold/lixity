"""Shared display controls for the canonical manuscript paragraph tree."""

from collections.abc import Mapping, Sequence
from html import escape

from ..style_profile import ChapterProfile
from .components import label
from .manuscript_document import ReaderBlock


def reading_controls(
    chapters: Sequence[ChapterProfile], labels: Mapping[str, str] | None,
    reader_document: Sequence[ReaderBlock] | None = None,
    *,
    companion_controls: str = "",
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
    return (
        '<div class="manuscript-reader-controls" id="manuscript-reader-controls" hidden>'
        f'<button class="ctl analysis-toggle" type="button" id="manuscript-analysis-toggle" '
        f'aria-label="{text("reading_analysis")}" aria-pressed="false" data-help="{text("reading_help_analysis")}">'
        '<span class="analysis-switch" aria-hidden="true"></span>'
        f'{text("reading_analysis")} <span class="analysis-state" aria-hidden="true">'
        f'<span class="analysis-state-measure">{text("reading_on")}</span>'
        f'<span class="analysis-state-measure">{text("reading_off")}</span>'
        f'<span id="manuscript-analysis-state">{text("reading_off")}</span></span></button>'
        f'<select id="manuscript-mode" hidden aria-hidden="true" tabindex="-1"><option value="read">{text("reading_read")}</option>'
        f'<option value="inspect">{text("reading_inspect")}</option></select>'
        f'<select class="ctl reader-chapter" id="reader-chapter" aria-label="{text("reading_chapter")}">'
        f'<option value="">{text("reading_chapter")}…</option>{options}</select>'
        '<details class="reader-settings" id="reader-settings">'
        f'<summary class="ctl">{text("reading_appearance")}</summary><div class="reader-settings-body">'
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
        f'<dt><kbd>Shift+F10</kbd></dt><dd>{text("reading_shortcut_actions")}</dd>'
        f'<dt><kbd>Enter</kbd></dt><dd>{text("reading_shortcut_search")}</dd>'
        f'<dt><kbd>Esc</kbd></dt><dd>{text("reading_shortcut_close")}</dd>'
        '</dl></div></div></details>'
        f'<button class="ctl" type="button" id="reader-focus" aria-pressed="false" '
        f'data-help="{text("reading_help_focus")}">{text("reading_focus")}</button>'
        f'<button class="ctl" type="button" id="workbench-overview-open" '
        f'data-help="{text("reading_help_overview")}">{text("reading_overview")}</button>'
        f'{companion_controls}'
        f'<strong class="workbench-surface-label" id="workbench-overview-label" hidden>{text("reading_overview")}</strong>'
        f'<button class="ctl" type="button" id="workbench-overview-back" hidden>{text("reading_back")}</button>'
        f'<button class="ctl" type="button" id="workbench-return" hidden '
        f'data-help="{text("reading_help_return")}">{text("reading_back")}</button>'
        '</div>'
        '<aside class="reader-inspector panel" id="reader-inspector" hidden '
        'aria-labelledby="reader-inspector-title"><div class="workspace-reader-head">'
        f'<h2 id="reader-inspector-title">{text("reading_passage_values")}</h2>'
        f'<button class="ctl" type="button" id="reader-inspector-close" aria-label="{text("modal_close")}">✕</button>'
        '</div><div id="reader-inspector-body"></div></aside>'
        f'<div class="manuscript-context-menu" id="manuscript-context-menu" role="menu" aria-label="{text("reading_actions")}" hidden></div>'
        f'<div class="manuscript-selection-tools" id="manuscript-selection-tools" role="toolbar" aria-label="{text("reading_actions")}" hidden></div>'
    )
