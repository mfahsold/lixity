"""Editorial workflow entrypoints for the native analysis overview."""

from collections.abc import Mapping, Sequence
from html import escape

from .components import label, panel_guide

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
        "analysis-measurements",
    ),
}


def analysis_workflow_sections(
    active_sections: Sequence[tuple[str, str]],
    *,
    has_markers: bool = False,
    has_register_targets: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Project the available panels into the shared order for overview routes."""
    available = dict(active_sections)
    available["analysis-measurements"] = "analysis_measurements"
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
        panel_guide(escape(label(labels, "workflow_choose_hint"))),
        '<div class="analysis-workflow-entries">',
    ]
    for workflow, sections in groups.items():
        if not sections:
            continue
        title = escape(label(labels, f"workflow_{workflow}"))
        hint = escape(label(labels, f"workflow_{workflow}_hint"))
        preview_items = [escape(label(labels, available[section])) for section in sections]
        preview = f'<small class="analysis-workflow-preview" aria-hidden="true">{" · ".join(preview_items)}</small>'
        parts.append(
            f'<button type="button" class="ctl analysis-workflow-entry" '
            f'data-analysis-workflow="{workflow}" aria-pressed="false" '
            f'aria-controls="analysis-workflow-sections manuscript-analysis-panels">'
            f'<strong>{title}</strong><span>{hint}</span>{preview}</button>'
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
