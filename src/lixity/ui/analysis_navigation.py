"""Editorial workflow entrypoints for the native analysis overview."""

import json
from collections.abc import Mapping, Sequence
from html import escape

from .components import label

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
    payload = escape(json.dumps(groups, separators=(",", ":")), quote=True)
    parts = [
        f'<div class="analysis-workflows" data-analysis-workflows="{payload}">',
        '<div class="analysis-workflow-entries">',
    ]
    for workflow in groups:
        title = escape(label(labels, f"workflow_{workflow}"))
        hint = escape(label(labels, f"workflow_{workflow}_hint"))
        parts.append(
            f'<button type="button" class="ctl analysis-workflow-entry" '
            f'data-analysis-workflow="{workflow}" aria-pressed="false" '
            f'aria-controls="manuscript-analysis-panels">'
            f"<strong>{title}</strong><span>{hint}</span></button>"
        )
    parts.append(
        '</div><div class="analysis-workflow-sections" role="group" '
        f'aria-label="{escape(label(labels, "workflow_sections"), quote=True)}">'
    )
    for workflow, sections in groups.items():
        parts.extend(
            f'<button type="button" class="ctl" data-analysis-section-target="{section}" '
            f'data-analysis-section-workflow="{workflow}" aria-pressed="false" '
            f'aria-controls="{section}">{escape(label(labels, available[section]))}</button>'
            for section in sections
        )
    parts.append("</div></div>")
    return "".join(parts)
