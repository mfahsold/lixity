"""Editorial workflow entrypoints for the native analysis overview."""

from collections.abc import Mapping, Sequence
from html import escape

from .components import label, ui_icon

_WORKFLOW_SECTIONS = {
    "review": ("flags", "markers"),
    "compare": ("matrix", "style", "register-targets"),
    "explore": (
        "pacing",
        "scenes",
        "dialogue",
        "dist",
        "showing",
        "characters",
        "motifs",
    ),
}

_WORKFLOW_ICONS = {"review": "file-text", "compare": "git-compare", "explore": "search"}


def analysis_workflow_sections(
    active_sections: Sequence[tuple[str, str]],
    *,
    has_markers: bool = False,
    has_register_targets: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Project the available panels into the shared order for overview routes."""
    available = dict(active_sections)
    if has_markers:
        available["markers"] = "markers"
    if has_register_targets:
        available["register-targets"] = "register_title"
    return tuple(
        (section, available[section])
        for sections in _WORKFLOW_SECTIONS.values()
        for section in sections
        if section in available
    )


def render_analysis_workflows(
    active_sections: Sequence[tuple[str, str]],
    labels: Mapping[str, str] | None,
) -> str:
    """Render available routes without hiding any no-script report content."""
    available = dict(active_sections)
    groups = {
        key: [section for section in sections if section in available]
        for key, sections in _WORKFLOW_SECTIONS.items()
    }
    parts = [
        '<div class="analysis-workflows" id="analysis-workflows" data-analysis-workflows>',
        '<div class="analysis-workflow-entries" role="group" '
        f'aria-label="{escape(label(labels, "workflow_choose_section"))}">',
        '<button type="button" class="ctl analysis-workflow-entry" id="analysis-measurements-tab" '
        'aria-pressed="false" aria-controls="analysis-measurements">'
        f'{ui_icon("layout-grid")}<span>{escape(label(labels, "analysis_measurements"))}</span></button>',
    ]
    for workflow, sections in groups.items():
        if not sections:
            continue
        title = escape(label(labels, f"workflow_{workflow}"))
        hint = escape(label(labels, f"workflow_{workflow}_hint"))
        parts.append(
            f'<button type="button" class="ctl analysis-workflow-entry" '
            f'data-analysis-workflow="{workflow}" data-help="{hint}" aria-pressed="false" '
            f'aria-controls="analysis-workflow-sections manuscript-analysis-panels">'
            f'{ui_icon(_WORKFLOW_ICONS[workflow])}<span>{title}</span></button>'
        )
    parts.append(
        '</div><div class="analysis-workflow-sections" id="analysis-workflow-sections" role="group" '
        f'aria-label="{escape(label(labels, "workflow_sections"), quote=True)}">'
    )
    for workflow, sections in groups.items():
        parts.extend(
            f'<button type="button" class="ctl ctl-choice" data-analysis-section-target="{section}" '
            f'data-analysis-section-workflow="{workflow}" aria-pressed="false" '
            f'aria-controls="{section}">{escape(label(labels, available[section]))}</button>'
            for section in sections
        )
    parts.append("</div></div>")
    return "".join(parts)
