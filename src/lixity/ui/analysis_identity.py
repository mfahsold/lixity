"""Visible source-analysis boundaries, including static/no-JavaScript reports."""

from collections.abc import Mapping
from html import escape

from .components import details_start, panel_guide, panel_label
from .render_contracts import AnalysisIdentity


def render_analysis_identity(identity: AnalysisIdentity, labels: Mapping[str, str] | None) -> str:
    if identity.scope != "source_internal":
        return ""

    text = panel_label(labels)

    return (
        '<aside class="panel analysis-identity" id="analysis-identity" role="note" '
        'data-analysis-scope="source_internal" data-context-status="user_supplied_unverified" '
        'aria-labelledby="analysis-identity-title">'
        f'<h2 id="analysis-identity-title">{text("analysis_source_title")}</h2>'
        f"<p>{text('analysis_source_scope')}</p>"
        + panel_guide(text("analysis_source_context"))
        + details_start(text("analysis_source_provenance"))
        + f"<p>{text('analysis_source_id')}: <code>{escape(identity.source_id)}</code></p>"
        f"<p>{text('analysis_source_version')}: <code>{escape(identity.source_version_id)}</code></p>"
        "</details></aside>"
    )
