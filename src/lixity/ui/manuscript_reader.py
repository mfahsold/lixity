"""Shared display controls for the canonical manuscript paragraph tree."""

from collections.abc import Mapping, Sequence
from html import escape

from ..style_profile import ChapterProfile
from .components import label


def reading_controls(chapters: Sequence[ChapterProfile], labels: Mapping[str, str] | None) -> str:
    """Render progressive-enhancement controls; no second manuscript copy."""
    def text(key: str) -> str:
        return escape(label(labels, key), quote=True)

    options = "".join(
        f'<option value="ch-{chapter.num}">{chapter.num}. {escape(chapter.title)}</option>'
        for chapter in chapters
    )
    return (
        '<div class="manuscript-reader-controls" id="manuscript-reader-controls" hidden>'
        f'<label class="reader-mode-label" for="manuscript-mode">{text("reading_view")}</label>'
        f'<select class="ctl" id="manuscript-mode"><option value="read">{text("reading_read")}</option>'
        f'<option value="inspect">{text("reading_inspect")}</option></select>'
        f'<select class="ctl reader-chapter" id="reader-chapter" aria-label="{text("reading_chapter")}">'
        f'<option value="">{text("reading_chapter")}…</option>{options}</select>'
        f'<div class="reader-size-controls" role="group" aria-label="{text("reading_size")}">'
        f'<button class="ctl" type="button" id="reader-text-smaller" aria-label="{text("reading_smaller")}">A−</button>'
        '<output id="reader-size-value" aria-live="polite">18</output>'
        f'<button class="ctl" type="button" id="reader-text-larger" aria-label="{text("reading_larger")}">A+</button></div>'
        '<details class="reader-settings" id="reader-settings">'
        f'<summary class="ctl">{text("reading_appearance")}</summary><div class="reader-settings-body">'
        f'<label for="reader-width">{text("reading_width")}</label><select class="ctl" id="reader-width">'
        f'<option value="narrow">{text("reading_narrow")}</option><option value="standard" selected>{text("reading_standard")}</option>'
        f'<option value="wide">{text("reading_wide")}</option></select>'
        f'<label for="reader-spacing">{text("reading_spacing")}</label><select class="ctl" id="reader-spacing">'
        f'<option value="compact">{text("reading_compact")}</option><option value="standard" selected>{text("reading_standard")}</option>'
        f'<option value="relaxed">{text("reading_relaxed")}</option></select></div></details>'
        f'<button class="ctl" type="button" id="reader-focus" aria-pressed="false">{text("reading_focus")}</button>'
        '</div>'
        '<aside class="reader-inspector panel" id="reader-inspector" hidden '
        'aria-labelledby="reader-inspector-title"><div class="workspace-reader-head">'
        f'<h2 id="reader-inspector-title">{text("paragraph_values")}</h2>'
        f'<button class="ctl" type="button" id="reader-inspector-close" aria-label="{text("modal_close")}">✕</button>'
        '</div><div id="reader-inspector-body"></div></aside>'
        f'<div class="manuscript-context-menu" id="manuscript-context-menu" role="menu" aria-label="{text("reading_actions")}" hidden></div>'
        f'<div class="manuscript-selection-tools" id="manuscript-selection-tools" role="toolbar" aria-label="{text("reading_actions")}" hidden></div>'
    )
