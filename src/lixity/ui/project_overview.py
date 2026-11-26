"""Native-only shell for explicit, read-only project structure inspection."""

from collections.abc import Mapping

from ..workspace_labels import (
    PROJECT_STRUCTURE_ISSUE_LABELS,
    PROJECT_STRUCTURE_ROLE_LABELS,
    PROJECT_STRUCTURE_STATE_LABELS,
)
from .components import esc, label, script_json, status_banner, ui_icon


def project_overview(labels: Mapping[str, str] | None = None, *, research_navigation: bool = False) -> str:
    """Render an empty overview; project paths are requested only on activation."""
    keys = {"roles": PROJECT_STRUCTURE_ROLE_LABELS, "states": PROJECT_STRUCTURE_STATE_LABELS,
            "issues": PROJECT_STRUCTURE_ISSUE_LABELS}
    payload = script_json(keys, ensure_ascii=True)
    refresh = esc(label(labels, "project_structure_refresh"))
    return (
        '<section class="project-overview" id="project-overview" aria-labelledby="project-overview-title" '
        f'data-research-navigation="{str(research_navigation).lower()}">'
        '<div class="project-overview-heading">'
        f'<h3 id="project-overview-title">{esc(label(labels, "project_structure_title"))}</h3>'
        '<button type="button" class="ctl ctl-sm" id="project-overview-refresh" aria-controls="project-overview-body" '
        f'data-help="{esc(label(labels, "project_structure_refresh_help"))}" title="{refresh}">'
        f'{ui_icon("rotate-cw", size=15)}<span>{refresh}</span></button></div>'
        f'<p class="ctl-note">{esc(label(labels, "project_structure_scope"))}</p>'
        + status_banner("project-overview-status", esc(label(labels, "project_structure_not_checked")))
        + '<div id="project-overview-body" hidden></div></section>'
        f'<script type="application/json" id="project-overview-label-keys">{payload}</script>'
    )
