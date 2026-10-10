"""lixity.ui.dashboard – Minimalist, self-contained single-file HTML dashboard.

Renders an interactive stylometric report combining KPI cards, sentence rhythm bars,
diverging z-score heatmap, style passport, latent dimensions, chapter map,
and editor-visible work markers with floating tooltips.
"""

import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path as _Path
from typing import Any

from ..diversity import MIN_TOKENS_LD
from ..format import num as format_num
from ..format import pct as format_pct
from ..status import FLAG_MIN_SEVERITY
from ..style_fingerprint import (
    FEATURES,
    LAYER_FEATURES,
    Z_COLOR_LIMIT,
    FingerprintThresholds,
    layer_stats,
    z_color,
)
from ..style_profile import (
    ChapterProfile,
    ParagraphProfile,
    flagged_paragraphs,
)
from ..workspace_labels import WORKSPACE_LABELS
from .components import (
    artifact_href,
    help_term,
    kpi,
    label,
    line_label,
    panel_start,
    project_header,
    status_strip,
    tense_class,
    tense_label,
)
from .dimensions import style_dimensions
from .dossier_images import image_limits_attribute
from .heatmap import render_heatmap_panel, render_style_passport_panel
from .markers_panel import render_markers_panel
from .modals import render_project_modals
from .narration import (
    render_characters_panel,
    render_dialogue_panel,
    render_motifs_panel,
    render_pacing_panel,
    render_scenes_panel,
    render_sentence_dist_panel,
    render_showing_panel,
)
from .research_panel import render_research_panel
from .settings import settings_form
from .structural import style_structural

_ASSET_DIR = _Path(__file__).with_name("assets")
_CSS = "\n".join(
    (_ASSET_DIR / name).read_text(encoding="utf-8")
    for name in ("dashboard.css", "dossier-images.css")
)
_JS = "\n".join(
    (_ASSET_DIR / name).read_text(encoding="utf-8")
    for name in ("dashboard.js", "dossier-images.js", "style-space.js")
)


def render_dashboard(
    chapters: Sequence[ChapterProfile],
    paragraphs: Sequence[ParagraphProfile],
    metrics: Any | None = None,
    fingerprint: Any | None = None,
    markers: Sequence[Any] | None = None,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    status: Sequence[Mapping[str, Any]] | None = None,
    dialogue: Mapping[str, Any] | None = None,
    characters: Mapping[str, Any] | None = None,
    pacing: Mapping[str, Any] | None = None,
    motifs: Mapping[str, Any] | None = None,
    showing: Mapping[str, Any] | None = None,
    title: str = "Manuscript",
    labels: Mapping[str, str] | None = None,
    language_name: str = "",
    language_key: str = "en",
    tense_available: bool = True,
    engine_name: str = "Lixity",
    controls: bool = False,
    api_base: str = "/api",
    manuscript_name: str = "",
    current_language: str | None = None,
    language_options: Sequence[Any] | None = None,
    flag_min_severity: int | None = None,
    document_context: Mapping[str, Any] | None = None,
    enabled_actions: Sequence[str] | None = None,
    debug: bool = False,
    scenes: Mapping[str, Any] | None = None,
    nda_project_name: str = "",
    project_author: str = "",
    identity_check: Mapping[str, Any] | None = None,
    author_setting_enabled: bool = False,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the local control panel. ``enabled_actions`` limits
    optional actions to those implemented by the embedding server; ``None``
    preserves the other existing controls. NDA generation requires explicit
    ``nda-draft`` capability; ``nda_project_name`` supplies a real project name
    separately from a placeholder dashboard title.
    ``project_author`` and ``identity_check`` describe saved project identity and
    a read-only manuscript comparison. Author editing requires the explicit
    ``author_setting_enabled`` capability; its default supplies no personal name.
    ``dialogue``/``characters``/``pacing``/``motifs``/
    ``showing`` add the optional dialogue-structure, character-presence,
    pacing, motif/repetition and showing/telling panels (see the
    corresponding modules).

    ``flag_min_severity`` floors the paragraph flag cut; ``None`` takes the
    resolved value from ``fingerprint.thresholds`` (CLI/API/config aware).
    """
    esc = html.escape
    allowed_actions = set(enabled_actions) if enabled_actions is not None else None

    def action_enabled(action: str) -> bool:
        return allowed_actions is None or action in allowed_actions

    def L(key: str) -> str:
        return esc(label(labels, key))

    def N(value: float, decimals: int = 1, signed: bool = False) -> str:
        return format_num(value, language_key, decimals, signed)

    def P(value: float, decimals: int = 1) -> str:
        return format_pct(value, language_key, decimals)

    html_lang = language_key if language_key not in ("auto", "generic") else "en"
    workspace_labels_json = esc(
        json.dumps(
            {
                key: label(labels, key)
                for key in (
                    *WORKSPACE_LABELS["en"],
                    "marker_pruefen",
                    "marker_sachcheck",
                    "marker_todo",
                    "marker_achtung",
                    "marker_note",
                    "ctx_genre",
                    "ctx_created_period",
                    "ctx_depicted_period",
                    "ctx_place",
                    "ctx_perspective",
                    "ctx_original_language",
                    "ctx_is_translation",
                    "ctx_provenance_note",
                    "ctx_yes",
                    "ctx_no",
                )
            },
            ensure_ascii=False,
        ),
        quote=True,
    )
    if current_language is None:
        current_language = language_key
    if not language_options:
        language_options = [
            ("auto", "auto"),
            ("de", "Deutsch"),
            ("en", "English"),
            ("fr", "Français"),
            ("es", "Español"),
            ("it", "Italiano"),
            ("pt", "Português"),
            ("nl", "Nederlands"),
            ("generic", "generic"),
        ]

    total_words = sum(c.words for c in chapters)
    if flag_min_severity is None:
        flag_min_severity = (
            fingerprint.thresholds.flag_min_severity
            if fingerprint is not None
            else int(FLAG_MIN_SEVERITY)
        )
    if flag_min_severity not in (1, 2, 3):
        flag_min_severity = int(FLAG_MIN_SEVERITY)
    total_flagged = sum(1 for p in paragraphs if p.severity >= flag_min_severity)
    scale = max((p.words for p in paragraphs), default=1)
    feature_layers = {field: key for key, field in LAYER_FEATURES.items()}

    function_pct = (
        round(sum(p.function_word_pct for p in paragraphs) / len(paragraphs), 1)
        if paragraphs
        else 0.0
    )
    has_house_style = bool(
        fingerprint is not None
        and any(float(base.get("sigma") or 0.0) > 0.0 for base in fingerprint.baseline.values())
    )

    layer_data: dict[str, dict[int, tuple[float, float]]] = {
        layer_key: layer_stats(paragraphs, layer_key) for layer_key in LAYER_FEATURES
    }

    def _layer_text(key: str, value: float) -> str:
        if key == "asl":
            return f"ASL {N(value, 1)}"
        if key in ("dialogue", "function"):
            text_label = label(labels, "dialogue" if key == "dialogue" else "function_words")
            return f"{text_label} {P(value)}"
        return f"{label(labels, 'feat_' + key)} {N(value, 1)}"

    def _layer_range(key: str) -> tuple[float, float]:
        values = [value for value, _z in layer_data.get(key, {}).values()]
        return (min(values), max(values)) if values else (0.0, 1.0)

    def _layer_tip(key: str, value: float, z: float) -> str:
        direction = label(labels, "layer_above" if z > 0 else "layer_below")
        return f"{_layer_text(key, value)} · {direction}"

    parts = [
        "<!DOCTYPE html>",
        f'<html lang="{html_lang}">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<link rel="icon" href="data:,"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        *(('<meta name="lixity-debug" content="true"/>',) if debug else ()),
        f"<title>{esc(title)} – {L('app_suffix')}</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        f'<body id="top" data-api="{esc(api_base)}" data-ui-labels="{workspace_labels_json}" '
        f'data-image-limits="{image_limits_attribute()}" '
        f'data-dossier-image-capable="{str(controls and allowed_actions is not None and action_enabled("research-dossier-image")).lower()}">',
        '<div class="page">',
        project_header(title, labels, language_name, engine_name),
    ]

    has_chapters = bool(chapters) and total_words > 0
    default_view = "analysis" if has_chapters else "research"

    if controls:
        parts.append(f'<nav class="workspace-bar" aria-label="{L("workspace")}">')
        parts.append(f'<span class="ctl-label">{L("workspace")}</span>')
        parts.append('<div class="row">')
        parts.append(
            f'<button type="button" class="ctl primary" id="btn-modal-new-project">+ {L("new_project")}</button>'
        )
        parts.append(
            f'<button type="button" class="ctl" id="btn-modal-open-project">📂 {L("open_project")}</button>'
        )
        show_guidance_hidden = "" if chapters else " hidden"
        parts.append(
            f'<button type="button" class="ctl" id="welcome-show" aria-controls="welcome-hero" aria-expanded="false"{show_guidance_hidden}>{L("welcome_show")}</button>'
        )
        if manuscript_name:
            parts.append(
                f'<span class="ctl-note">{L("current_manuscript")}: <strong>{esc(manuscript_name)}</strong></span>'
            )
        parts.append("</div>")
        parts.append("</nav>")
        parts.append(
            '<nav class="view-navigation" role="tablist" aria-label="' + L("workspace") + '">'
            f'<button type="button" class="view-nav-tab{" active" if default_view == "research" else ""}" data-view="research" role="tab" id="tab-view-research" aria-controls="view-pane-research" aria-selected="{"true" if default_view == "research" else "false"}">'
            f'<span class="view-nav-icon" aria-hidden="true">📚</span> '
            f'<span class="view-nav-label">{L("workspace_research")}</span>'
            "</button>"
            f'<button type="button" class="view-nav-tab{" active" if default_view == "analysis" else ""}" data-view="analysis" role="tab" id="tab-view-analysis" aria-controls="view-pane-analysis" aria-selected="{"true" if default_view == "analysis" else "false"}">'
            f'<span class="view-nav-icon" aria-hidden="true">📊</span> '
            f'<span class="view-nav-label">{L("workspace_analysis")}</span>'
            "</button>"
            f'<button type="button" class="view-nav-tab" data-view="project" role="tab" id="tab-view-project" aria-controls="view-pane-project" aria-selected="false">'
            f'<span class="view-nav-icon" aria-hidden="true">⚙️</span> '
            f'<span class="view-nav-label">{L("workspace_project")}</span>'
            "</button>"
            "</nav>"
        )

    if status:
        parts.append(status_strip(labels, status))

    if document_context:
        parts.append(panel_start("document-context", labels, "source_context"))
        parts.append('<div class="table-wrap"><table><tbody>')
        if "source_version_id" in document_context:
            parts.append(
                f'<tr><th scope="row">{L("ctx_source_version")}</th>'
                f"<td><code>{esc(document_context['source_version_id'])}</code></td></tr>"
            )
        ctx_fields = (
            ("genre", "ctx_genre"),
            ("created_period", "ctx_created_period"),
            ("depicted_period", "ctx_depicted_period"),
            ("place", "ctx_place"),
            ("perspective", "ctx_perspective"),
            ("original_language", "ctx_original_language"),
            ("is_translation", "ctx_is_translation"),
            ("provenance_note", "ctx_provenance_note"),
        )
        for field_name, label_key in ctx_fields:
            val = document_context.get(field_name)
            if val is not None:
                if isinstance(val, bool):
                    val_str = L("ctx_yes") if val else L("ctx_no")
                else:
                    val_str = str(val)
                parts.append(f'<tr><th scope="row">{L(label_key)}</th><td>{esc(val_str)}</td></tr>')
        parts.append("</tbody></table></div></section>")

    if controls or not chapters:
        parts.append(
            '<section class="welcome-hero" id="welcome-hero"'
            + (" hidden" if chapters else "")
            + ">"
        )
        if controls:
            parts.append(
                f'  <button type="button" class="ctl welcome-dismiss" id="welcome-dismiss" aria-controls="welcome-hero">{L("welcome_dismiss")}</button>'
            )
        parts.append('  <div class="welcome-inner">')
        parts.append(f'    <div class="welcome-badge">Lixity {L("workspace")}</div>')
        parts.append(f'    <h2 class="welcome-title">{L("welcome_title")}</h2>')
        parts.append(f'    <p class="welcome-desc">{L("welcome_desc")}</p>')
        if controls:
            parts.append('    <div class="welcome-actions">')
            parts.append(
                f'      <button type="button" class="ctl primary welcome-btn" id="hero-btn-new-project">{L("welcome_import_action")}</button>'
            )
            parts.append(
                f'      <button type="button" class="ctl welcome-btn" id="hero-btn-open-project">📂 {L("open_project")}</button>'
            )
            parts.append(
                f'      <button type="button" class="ctl welcome-btn" id="hero-btn-browse-project">{L("wizard_choose_action")}</button>'
            )
            parts.append("    </div>")
            parts.append(
                '    <section id="welcome-project-recent" data-recent-projects hidden aria-labelledby="welcome-project-recent-heading">'
            )
            parts.append(
                f'      <h3 id="welcome-project-recent-heading">{L("recent_projects_heading")}</h3>'
            )
            parts.append(f'      <p class="ctl-note">{L("recent_projects_help")}</p>')
            parts.append(
                '      <ul id="welcome-project-recent-list" class="project-chooser-list" data-recent-project-list></ul>'
            )
            parts.append(
                f'      <button type="button" class="ctl" data-clear-recent-projects>{L("clear_recent_projects")}</button>'
            )
            parts.append(
                '      <p class="ctl-status" data-recent-project-status role="status" hidden></p>'
            )
            parts.append("    </section>")
        parts.append('    <div class="onboarding-guide">')
        parts.append(
            f'      <div class="og-header"><h3>{L("welcome_quickstart")}</h3><p>{L("welcome_local")}</p></div>'
        )
        parts.append('      <div class="og-steps">')
        for step, title_key, desc_key in (
            (1, "welcome_manuscript", "welcome_manuscript_desc"),
            (2, "welcome_config", "welcome_config_desc"),
            (3, "welcome_research", "welcome_research_desc"),
        ):
            parts.append(
                f'<div class="og-step"><div class="og-step-num">{step}</div>'
                f'<div class="og-step-body"><strong>{L(title_key)}</strong>'
                f"<p>{L(desc_key)}</p></div></div>"
            )
        parts.append("      </div>")
        parts.append("    </div>")
        parts.append(f'    <details class="welcome-more"><summary>{L("welcome_more")}</summary><div class="welcome-features">')
        for title_key, desc_key in (
            ("welcome_fdr", "welcome_fdr_desc"),
            ("welcome_style", "welcome_style_desc"),
            ("welcome_research_feature", "welcome_research_feature_desc"),
        ):
            parts.append(
                f'      <div class="wf-item"><strong>{L(title_key)}</strong><span>{L(desc_key)}</span></div>'
            )
        parts.append("    </div></details>")
        parts.append("  </div>")
        parts.append("</section>")

    if controls:
        # Project actions and optional guidance stay available in every view.
        parts.append(
            f'<div class="view-pane{" active" if default_view == "research" else ""}" id="view-pane-research" data-view-pane="research" role="tabpanel" aria-labelledby="tab-view-research">'
        )
        parts.append(render_research_panel(labels))
        parts.append("</div>")
        parts.append(
            '<div class="view-pane" id="view-pane-project" data-view-pane="project" role="tabpanel" aria-labelledby="tab-view-project">'
        )
        parts.append('<section class="panel controls" id="controls">')
        parts.append(f"<h2>{L('controls')}</h2>")

        parts.append('<div class="ctl-group">')
        parts.append(f'<span class="ctl-label">{L("manuscript")}</span>')
        file_input_id = "ms-file" if action_enabled("load") else "manuscript-import-file"
        parts.append(
            f'<input type="file" id="{file_input_id}" accept=".md,.markdown,.txt" hidden/>'
        )
        parts.append(
            f'<button type="button" class="file-dropzone dropzone-compact" id="manuscript-dropzone" aria-label="{L("wizard_drop_aria")}" aria-describedby="manuscript-drop-hint manuscript-file-name">'
        )
        parts.append(
            f'<strong>{L("dropzone_drop_here")} <span class="ctl-link">{L("dropzone_browse")}</span></strong>'
        )
        parts.append(
            f'<span class="ctl-note" id="manuscript-drop-hint">{L("dropzone_hint")}</span>'
        )
        parts.append("</button>")
        parts.append(
            '<p class="ctl-note manuscript-file-name" id="manuscript-file-name" role="status" aria-live="polite"></p>'
        )
        parts.append('<div class="row">')
        if action_enabled("load"):
            parts.append(
                f'<button type="button" class="ctl primary" data-action="load" data-payload="load" disabled>{L("dropzone_action")}</button>'
            )
        else:
            parts.append(
                f'<button type="button" class="ctl primary" id="manuscript-import-btn" disabled>{L("manuscript_import_action")}</button>'
            )
        parts.append("</div>")
        parts.append(
            f'<p class="ctl-note">{L("manuscript_load_hint") if action_enabled("load") else L("manuscript_import_hint")}</p>'
        )
        parts.append("</div>")

        parts.append(
            settings_form(
                labels,
                title,
                current_language,
                language_options,
                replace(
                    fingerprint.thresholds if fingerprint is not None else FingerprintThresholds(),
                    flag_min_severity=flag_min_severity,
                ),
                project_author=project_author,
                identity_check=identity_check,
                author_setting_enabled=author_setting_enabled,
            )
        )

        # Actions advertised by the embedding server.
        visible_actions = [
            action
            for action in ("analyze", "sync", "audit", "prune", "gdrive", "rebuild")
            if action_enabled(action)
        ]
        if action_enabled("export") or visible_actions:
            parts.append('<div class="ctl-group">')
            action_heading = (
                f"{L('export')} · {L('run_analysis')}"
                if action_enabled("export") and visible_actions
                else L("export")
                if action_enabled("export")
                else L("run_analysis")
            )
            parts.append(f'<span class="ctl-label">{action_heading}</span>')
            parts.append('<div class="row">')
            if action_enabled("export"):
                parts.append(
                    f'<select class="ctl" id="fmt" aria-label="{esc(L("export"))}" '
                    f'title="{esc(label(labels, "help_format"))}">'
                    f'<option value="all">{L("format_all")}</option>'
                    f'<option value="a4">A4</option>'
                    f'<option value="taschenbuch">{L("format_paperback")}</option>'
                    f'<option value="mobile">Mobile</option>'
                    f'<option value="epub">EPUB</option>'
                    "</select>"
                )
                parts.append(
                    f'<button class="ctl primary" data-action="export" data-payload="format">'
                    f"{help_term(labels, 'export', L('export'))}</button>"
                )
            if "analyze" in visible_actions:
                parts.append(
                    f'<button class="ctl" data-action="analyze">{help_term(labels, "rebuild", L("run_analysis"))}</button>'
                )
            parts.extend(
                f'<button class="ctl" data-action="{action}">{help_term(labels, action, L(action))}</button>'
                for action in visible_actions
                if action != "analyze"
            )
            parts.append("</div></div>")

        parts.append(
            f'<div class="ctl-status" id="ctl-status" role="status" aria-live="polite">{L("server_hint")}</div>'
        )
        parts.append("</section>")

        if allowed_actions is not None and "nda-draft" in allowed_actions:
            parts.append('<section class="panel controls" id="nda-draft">')
            parts.append(f"<h2>{L('nda_draft_title')}</h2>")
            parts.append(f'<p class="ctl-note">{L("nda_draft_hint")}</p>')
            parts.append(
                f'<form id="nda-draft-form" class="ctl-group" autocomplete="off" '
                f'method="post" action="{esc(api_base.rstrip("/") + "/nda-draft")}">'
                '<div class="settings-grid">'
            )
            for field, label_key, input_type in (
                ("name", "nda_draft_name", "text"),
                ("address", "nda_draft_address", "textarea"),
                ("project_name", "nda_draft_project", "text"),
                ("date", "nda_draft_date", "date"),
                ("place", "nda_draft_place", "text"),
            ):
                field_id = "nda-" + field.replace("_", "-")
                parts.append(
                    f'<div class="setting-field"><label for="{field_id}">{L(label_key)}</label>'
                )
                if input_type == "textarea":
                    parts.append(
                        f'<textarea class="ctl" id="{field_id}" name="{field}" rows="2"></textarea>'
                    )
                else:
                    value_attr = (
                        f' value="{esc(nda_project_name)}"' if field == "project_name" else ""
                    )
                    parts.append(
                        f'<input class="ctl" type="{input_type}" id="{field_id}" '
                        f'name="{field}"{value_attr} required/>'
                    )
                parts.append("</div>")
            parts.append('</div><div class="row">')
            parts.append(
                f'<button type="submit" class="ctl primary" id="nda-preview-btn" disabled>{L("nda_draft_preview")}</button>'
            )
            parts.append(
                f'<button type="button" class="ctl" id="nda-pdf-btn" disabled>{L("nda_draft_pdf")}</button>'
            )
            parts.append(
                f'<button type="button" class="ctl" id="nda-text-btn" disabled>{L("nda_draft_text")}</button>'
            )
            parts.append(
                '</div><div class="ctl-status" id="nda-draft-status" role="status" aria-live="polite"></div></form>'
            )
            parts.append(
                f'<noscript><p class="ctl-note">{L("nda_draft_javascript")}</p></noscript>'
            )
            parts.append(
                f'<div id="nda-preview-wrap" hidden><h3 class="section-heading" id="nda-preview-title">{L("nda_draft_preview")}</h3>'
                '<div id="nda-draft-preview" class="research-dossier-body-source" '
                'tabindex="0" role="region" aria-labelledby="nda-preview-title"></div></div></section>'
            )

        if artifacts:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{help_term(labels, 'artifacts', L('artifacts'))}</h2>")
            parts.append('<div class="artifacts">')
            for art in artifacts:
                name = esc(str(art.get("name", "")))
                meta_bits = []
                if art.get("size_kb") is not None:
                    meta_bits.append(f"{N(art['size_kb'], 0)} KB")
                if art.get("pages"):
                    meta_bits.append(f"{art['pages']} {label(labels, 'pages')}")
                meta = " · ".join(meta_bits)
                href = artifact_href(art.get("href"))
                link = (
                    f'<a href="{esc(str(href))}" target="_blank" rel="noopener">{L("open")}</a>'
                    if href
                    else ""
                )
                parts.append(
                    f'<div class="artifact"><span class="name">{name}</span>'
                    f'<span class="meta">{esc(meta)}</span>{link}</div>'
                )
            parts.append("</div></section>")

        parts.append("</div>")
        parts.append(render_project_modals(labels, language_key, language_options))

        # --- PANE 3: MANUSCRIPT & ANALYSIS ---
        parts.append(
            f'<div class="view-pane{" active" if default_view == "analysis" else ""}" id="view-pane-analysis" data-view-pane="analysis" role="tabpanel" aria-labelledby="tab-view-analysis">'
        )

    if not has_chapters:
        parts.append(
            '<div class="panel empty-analysis-state">'
            '<div class="empty-state-icon" aria-hidden="true">📖</div>'
            f"<h2>{L('analysis_empty_title')}</h2>"
            f'<p class="ctl-note" style="max-width:60ch;margin:0 auto 1.2rem;line-height:1.5;">{L("analysis_empty_desc")}</p>'
            '<div class="row" style="justify-content:center;gap:.6rem;">'
            f'<button type="button" class="ctl primary" id="analysis-empty-import">{L("welcome_import_action")}</button>'
            f'<button type="button" class="ctl" data-switch-view="project">{L("analysis_empty_to_project")}</button>'
            f'<button type="button" class="ctl" data-switch-view="research">{L("analysis_empty_to_research")}</button>'
            "</div>"
            "</div>"
        )
        parts.append('<div class="analysis-empty-metrics" hidden>')

    if has_chapters:
        parts.append(f'<section class="panel" id="analysis-review"><h2>{L("review_title")}</h2>')
        parts.append(f'<p class="panel-guide">{L("review_intro")}</p><div class="review-routes">')
        if paragraphs:
            candidates = flagged_paragraphs(list(paragraphs), min_severity=flag_min_severity)
            first = min(candidates, key=lambda paragraph: paragraph.start_line) if candidates else paragraphs[0]
            first_index = next(i for i, paragraph in enumerate(paragraphs) if paragraph is first)
            passage_hint = "review_passage_flagged" if candidates else "review_passage_unflagged"
            parts.append(
                f'<article class="review-route"><h3>{L("review_passage")}</h3>'
                f'<p>{L(passage_hint)}</p><a class="ctl primary" href="#p-{first_index}" '
                f'data-review-passage="1" data-line="{first.start_line}" data-target="p-{first_index}">'
                f'{L("review_passage_action")}</a></article>'
            )
        compare_target = "heatmap" if has_house_style and metrics is not None and metrics.chapters else "chapters"
        compare_hint = "review_compare_hint" if compare_target == "heatmap" else "review_compare_limited"
        review_routes = [
            ("review_compare", compare_hint, "review_compare_action", compare_target),
        ]
        if metrics is not None:
            review_routes.append(("review_rhythm", "review_rhythm_hint", "review_rhythm_action", "dist"))
        for title_key, hint_key, action_key, target in review_routes:
            parts.append(
                f'<article class="review-route"><h3>{L(title_key)}</h3><p>{L(hint_key)}</p>'
                f'<a class="ctl" href="#{target}" data-jump="#{target}">{L(action_key)}</a></article>'
            )
        parts.append('</div></section>')

    # --- Key metrics (grouped for scanability) ----------------------------
    scope_tiles = [
        kpi(N(total_words, 0), help_term(labels, "words", L("words_prose")), jump="#matrix"),
        kpi(str(len(chapters)), L("chapter"), jump="#matrix"),
        kpi(str(len(paragraphs)), L("paragraphs"), jump="#matrix"),
    ]
    rhythm_tiles: list[str] = []
    language_tiles: list[str] = []
    lexis_tiles: list[str] = []
    style_tiles: list[str] = []
    if metrics is not None:
        has_tokens = bool(metrics.tokens)
        scope_tiles.append(kpi(N(metrics.total_sentences, 0), L("sentences"), jump="#matrix"))
        rhythm_tiles.append(
            kpi(
                N(metrics.asl, 2) if has_tokens else "–",
                help_term(labels, "asl", "ASL"),
                jump="#dist",
            )
        )
        rhythm_tiles.append(
            kpi(
                P(metrics.staccato_pct) if has_tokens else "–",
                help_term(labels, "staccato", L("feat_staccato")),
                bar=metrics.staccato_pct if has_tokens else None,
                jump="#dist",
            )
        )
        language_tiles.append(
            kpi(
                P(metrics.dialog_ratio) if (has_tokens and metrics.clean_words) else "–",
                help_term(labels, "dialogue", L("dialogue")),
                bar=metrics.dialog_ratio if (has_tokens and metrics.clean_words) else None,
                jump="#chapters",
                layer="dialogue",
            )
        )
        language_tiles.append(
            kpi(
                N(metrics.flesch_de, 1) if has_tokens else "–",
                help_term(labels, "flesch", "Flesch"),
                jump="#bands",
            )
        )
        language_tiles.append(
            kpi(
                N(metrics.lix, 1) if has_tokens else "–",
                help_term(labels, "lix", "LIX"),
                jump="#bands",
            )
        )
        lexis_tiles.append(
            kpi(
                N(metrics.ttr, 4) if has_tokens else "–",
                help_term(labels, "ttr", "TTR"),
                jump="#bands",
            )
        )
        lexis_tiles.append(
            kpi(
                N(metrics.guiraud_r, 2) if has_tokens else "–",
                help_term(labels, "guiraud", "Guiraud R"),
                jump="#bands",
            )
        )
        lexis_tiles.append(
            kpi(
                N(metrics.yules_k, 1) if has_tokens else "–",
                help_term(labels, "yules", "Yule&#8217;s K"),
                jump="#bands",
            )
        )
        hd_d_value = (
            N(metrics.hd_d, 3)
            if (has_tokens and getattr(metrics, "hd_d", None) is not None)
            else "–"
        )
        lexis_tiles.append(kpi(hd_d_value, help_term(labels, "hd_d", "HD-D"), jump="#bands"))
        mtld_value = (
            N(metrics.mtld, 1)
            if (has_tokens and getattr(metrics, "mtld", None) is not None)
            else "–"
        )
        lexis_tiles.append(kpi(mtld_value, help_term(labels, "mtld", "MTLD"), jump="#bands"))
        mattr_value = (
            N(metrics.mattr, 3)
            if (has_tokens and getattr(metrics, "mattr", None) is not None)
            else "–"
        )
        lexis_tiles.append(kpi(mattr_value, help_term(labels, "mattr", "MATTR"), jump="#bands"))
        maas_value = (
            N(metrics.maas_a2, 3)
            if (has_tokens and getattr(metrics, "maas_a2", None) is not None)
            else "–"
        )
        lexis_tiles.append(kpi(maas_value, help_term(labels, "maas", "Maas a²"), jump="#bands"))
        language_tiles.append(
            kpi(
                P(metrics.first_person_start_rate) if has_tokens else "–",
                help_term(labels, "first_start", L("feat_ich_start")),
                bar=metrics.first_person_start_rate if has_tokens else None,
                jump="#heatmap",
            )
        )
    language_tiles.append(
        kpi(
            P(function_pct) if (metrics is not None and metrics.tokens) else "–",
            help_term(labels, "function_words", L("function_words")),
            bar=function_pct if (metrics is not None and metrics.tokens) else None,
            jump="#chapters",
            layer="function",
        )
    )
    if fingerprint is not None:
        style_tiles.append(
            kpi(
                P(fingerprint.consistency * 100, 0) if fingerprint.measured_cells else "–",
                help_term(labels, "consistency", L("consistency")),
                bar=fingerprint.consistency * 100 if fingerprint.measured_cells else None,
                jump="#heatmap",
            )
        )
        drifters = fingerprint.top_deviants(1)
        if drifters:
            num, mean_abs = drifters[0]
            devs = fingerprint.deviations.get(num, {})
            top_field = max(devs, key=lambda k: abs(devs[k])) if devs else None
            top_layer = feature_layers.get(top_field) if top_field else None
            top_chapter = next((c for c in chapters if c.num == num), None)
            top_title = top_chapter.title if top_chapter is not None else ""
            style_tiles.append(
                kpi(
                    f"Ø {N(mean_abs, 1)}",
                    help_term(
                        labels,
                        "fingerprint",
                        f"{L('deviation')} · {L('chapter')} {num}"
                        + (f" · {esc(top_title)}" if top_title else ""),
                    ),
                    jump=f"#ch-{num}",
                    layer=top_layer,
                    only=bool(devs),
                )
            )
    style_tiles.append(
        kpi(
            str(total_flagged),
            help_term(labels, "flagged", L("flagged")),
            jump="#flags",
            flags=True,
        )
    )

    parts.append('<section class="kpis">')
    if has_chapters and metrics is not None and metrics.tokens < MIN_TOKENS_LD:
        support = esc(label(labels, "scene_support").replace("{min_tokens}", str(MIN_TOKENS_LD)))
        parts.append(f'<p class="hint" role="note">{support}</p>')
    for caption_key, tiles in (
        ("group_scope", scope_tiles),
        ("group_rhythm", rhythm_tiles),
        ("group_language", language_tiles),
        ("group_lexis", lexis_tiles),
        ("group_style", style_tiles),
    ):
        if not tiles:
            continue
        parts.append('<div class="kpi-group">')
        parts.append(f'<div class="kpi-caption">{L(caption_key)}</div>')
        parts.append('<div class="kpi-row">')
        parts.extend(tiles)
        parts.append("</div></div>")
    parts.append("</section>")

    # --- Flagged passages (list → paragraph → marker) ----------------------
    flagged = flagged_paragraphs(list(paragraphs), min_severity=flag_min_severity)
    parts.append('<section class="panel" id="flags">')
    parts.append(f"<h2>{help_term(labels, 'flagged', label(labels, 'panel_flags'))}</h2>")
    if flagged:
        para_index = {id(p): i for i, p in enumerate(paragraphs)}
        parts.append('<div class="table-wrap flags-wrap">')
        parts.append("<table><thead><tr>")
        parts.append(
            f"<th>{label(labels, 'flags_stage')}</th>"
            f"<th>{L('chapter')}</th>"
            f'<th class="num">{L("line")}</th>'
            f"<th>{label(labels, 'flags_excerpt')}</th>"
        )
        if controls:
            parts.append("<th></th>")
        parts.append("</tr></thead><tbody>")
        for p in flagged:
            idx = para_index[id(p)]
            excerpt = " ".join(p.text.split())
            if len(excerpt) > 140:
                excerpt = excerpt[:137].rstrip() + "…"
            chapter_cell = (
                f"{L('chapter')} {p.chapter_num} · {esc(p.chapter_title)}"
                if p.chapter_title
                else f"{L('chapter')} {p.chapter_num}"
            )
            parts.append(
                f'<tr class="row-link flag-row" data-line="{p.start_line}" '
                f'data-target="p-{idx}" data-flags="1" role="button" tabindex="0" '
                f'title="{esc(label(labels, "click_hint_para"), quote=True)}">'
                f'<td><span class="badge sev-{p.severity}">'
                f"{esc(label(labels, f'severity_{p.severity}'))}</span></td>"
                f"<td>{chapter_cell}</td>"
                f'<td class="num">{esc(line_label(labels, p))}</td>'
                f'<td class="flag-excerpt">{esc(excerpt)}</td>'
            )
            if controls:
                parts.append(
                    f'<td class="flag-actions"><div class="row marker-row">'
                    f'<button class="ctl" data-marker-kind="todo" '
                    f'data-line="{p.start_line}">+ '
                    f"{esc(label(labels, 'marker_todo'))}</button>"
                    f'<span class="marker-note-slot" data-placeholder="'
                    f'{esc(label(labels, "marker_note"), quote=True)}"></span>'
                    f"</div></td>"
                )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
    else:
        parts.append(f'<p class="hint">{label(labels, "flags_empty")}</p>')
    parts.append("</section>")

    # --- Narrative panels (sentence distribution, dialogue, characters, pacing, motifs, showing) ---
    parts.append(render_sentence_dist_panel(metrics, labels, language_key))
    parts.append(render_dialogue_panel(dialogue, labels, language_key))
    parts.append(render_characters_panel(characters, chapters, labels))
    parts.append(render_pacing_panel(pacing, labels, language_key))
    parts.append(render_scenes_panel(scenes, labels, language_key))
    parts.append(render_motifs_panel(motifs, labels))
    parts.append(render_showing_panel(showing, labels, language_key))

    # --- Style heatmap & passport (self-calibrated house style) -----------
    if has_house_style and fingerprint is not None and metrics is not None and metrics.chapters:
        style_views = [
            ("heatmap", "style_fingerprint", render_heatmap_panel(fingerprint, metrics, labels, language_key)),
            ("bands", "style_passport", render_style_passport_panel(fingerprint, labels, language_key)),
            ("dimensions", "style_dimensions", style_dimensions(chapters, fingerprint, labels, language_key)),
            ("structural", "panel_structural", style_structural(chapters, fingerprint, labels, language_key)),
        ]
        parts.append(f'<section class="panel style-panel" id="style"><h2>{L("group_style")}</h2>')
        parts.append(f'<div class="style-tabs" id="style-tabs" role="tablist" aria-label="{L("group_style")}" hidden>')
        for view_id, label_key, content in style_views:
            if content:
                parts.append(
                    f'<button type="button" class="ctl" id="style-tab-{view_id}" role="tab" '
                    f'aria-controls="{view_id}" data-style-view="{view_id}">{L(label_key)}</button>'
                )
        parts.append('</div><div id="style-panels">')
        parts.extend(content for _, _, content in style_views if content)
        parts.append('</div></section>')

    # --- Work markers (editor-visible, set from the dashboard) -------
    parts.append(render_markers_panel(markers, chapters, labels, controls))

    # --- Toolbar ----------------------------------------------------------
    parts.append('<div class="toolbar">')
    parts.append('<span class="text-search-group">')
    parts.append(
        f'<input class="ctl" type="search" id="text-search" autocomplete="off" '
        f'placeholder="{L("text_search")}" aria-label="{L("text_search")}" '
        f'aria-controls="chapters"/>'
    )
    parts.append(
        f'<button type="button" class="ctl" id="text-search-prev" hidden '
        f'aria-label="{L("text_search_prev")}" title="{L("text_search_prev")}">↑</button>'
    )
    parts.append(
        f'<button type="button" class="ctl" id="text-search-next" hidden '
        f'aria-label="{L("text_search_next")}" title="{L("text_search_next")}">↓</button>'
    )
    parts.append(
        f'<button type="button" class="ctl" id="text-search-clear" hidden>'
        f"{L('text_search_clear')}</button>"
    )
    parts.append(
        '<span class="ctl-note" id="text-search-status" role="status" aria-live="polite"></span>'
    )
    parts.append("</span>")
    parts.append(f'<label><input type="checkbox" id="filter-flags"/> {L("filter_flags")}</label>')
    if paragraphs:
        parts.append(
            f'<button type="button" class="ctl" id="paragraph-filter-reset">{L("paragraph_filter_reset")}</button>'
        )
        parts.append("<label>")
        parts.append(f"{help_term(labels, 'layer', L('style_layer'))} ")
        parts.append('<select class="ctl" id="style-layer">')
        parts.append(f'<option value="">{L("layer_off")}</option>')
        for layer_key in LAYER_FEATURES:
            low, high = _layer_range(layer_key)
            parts.append(
                f'<option value="{layer_key}" '
                f'data-hint="{esc(label(labels, "layer_hint_" + layer_key), quote=True)}" '
                f'data-range="{esc(f"{_layer_text(layer_key, low)} – {_layer_text(layer_key, high)}", quote=True)}">'
                f"{esc(label(labels, 'layer_' + layer_key))}</option>"
            )
        parts.append("</select></label>")
    parts.append('<span class="legend">')
    for key, color in (
        ("present", "var(--present)"),
        ("past", "var(--past)"),
        ("mixed", "var(--mixed)"),
        ("neutral", "var(--neutral)"),
    ):
        parts.append(
            f'<span><span class="swatch" style="background:{color}"></span>{L(key)}</span>'
        )
    parts.append(
        f'<span><span class="swatch" style="background:var(--flag)"></span>'
        f"{L('severity_2')} / {L('severity_3')}</span>"
    )
    parts.append("</span>")
    parts.append(f'<a class="totop" href="#top">↑ {L("top")}</a>')
    parts.append("</div>")

    parts.append(
        f'<div class="layer-legend" id="layer-legend" hidden="hidden" '
        f'data-outliers="{esc(label(labels, "layer_outliers"), quote=True)}" '
        f'data-outliers-one="{esc(label(labels, "layer_outliers_one"), quote=True)}">'
    )
    parts.append('<span class="layer-title" id="layer-legend-title" tabindex="0"></span>')
    parts.append('<span class="z-gradient"></span>')
    parts.append(
        '<span class="layer-scale"><span id="layer-scale-low"></span>'
        '<span id="layer-scale-high"></span></span>'
    )
    parts.append('<span class="layer-count" id="layer-legend-count"></span>')
    parts.append(
        f'<label class="layer-only"><input type="checkbox" id="layer-only"/> '
        f"{esc(label(labels, 'layer_only'))}</label>"
    )
    parts.append(f'<button class="ctl" id="layer-next">{esc(label(labels, "layer_next"))}</button>')
    parts.append("</div>")

    if not tense_available:
        parts.append(f'<p class="hint">{L("no_tense")}</p>')

    parts.append(
        f'<p class="ctl-note" id="paragraph-metrics-note">{L("paragraph_metrics_note")}</p>'
    )

    # --- Chapter map ------------------------------------------------------
    by_chapter: dict[int, list[tuple[int, Any]]] = {}
    paragraph_content: dict[str, list[str]] = {}
    for idx, p in enumerate(paragraphs):
        by_chapter.setdefault(p.chapter_num, []).append((idx, p))

    parts.append('<main id="chapters">')
    for chapter in chapters:
        chapter_paras = by_chapter.get(chapter.num, [])
        has_flags = any(p.is_flagged for _, p in chapter_paras)
        classes = "chapter has-flags" if has_flags else "chapter"
        parts.append(
            f'<section class="{classes}" id="ch-{chapter.num}" '
            f'data-start="{chapter.start_line}" data-end="{chapter.end_line}">'
        )
        parts.append('<div class="chapter-head">')
        parts.append(f"<h2>{chapter.num}. {esc(chapter.title)}</h2>")
        parts.append(
            f'<span class="meta">{N(chapter.words, 0)} {L("words")} · '
            f"{chapter.paragraphs} {L('paragraphs')} · {esc(tense_label(labels, chapter.dominant))} · "
            f"{chapter.flagged} {L('flagged')} · {L('line')} {chapter.start_line}–{chapter.end_line}</span>"
        )
        parts.append("</div>")

        if chapter_paras:
            parts.append('<div class="strip">')
            for idx, p in chapter_paras:
                sev = f" sev-{p.severity}" if p.is_flagged else ""
                width = max(1.0, p.words / scale * 100.0)
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                tooltip = (
                    f"{line_label(labels, p)} · {dom_label} · "
                    f"{label(labels, 'present')} {p.present_hits} / "
                    f"{label(labels, 'past')} {p.past_hits} · {sev_label}"
                )
                layer_payload: dict[str, list[Any]] = {}
                for key in LAYER_FEATURES:
                    info = layer_data.get(key, {}).get(idx)
                    if info is not None:
                        value, z = info
                        low, high = _layer_range(key)
                        span = (high - low) or 1.0
                        position = (value - low) / span
                        colour = z_color((position * 2.0 - 1.0) * Z_COLOR_LIMIT)
                        layer_payload[key] = [colour, _layer_tip(key, value, z), round(z, 2)]
                layer_attr = (
                    f" data-layers='{esc(json.dumps(layer_payload, ensure_ascii=False), quote=True)}'"
                    if layer_payload
                    else ""
                )
                parts.append(
                    f'<button class="chip {tense_class(p.dominant)}{sev}" '
                    f'style="flex:{width:.2f} 0 auto" data-target="p-{idx}"{layer_attr} '
                    f'data-tip-base="{esc(tooltip, quote=True)}" '
                    f'title="{esc(tooltip)}" aria-label="{esc(tooltip)}" aria-expanded="false"></button>'
                )
            parts.append("</div>")

            for idx, p in chapter_paras:
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                parts.append(
                    f'<div class="ptext" id="p-{idx}" data-start="{p.start_line}" '
                    f'data-end="{p.end_line}" data-markers="{int(controls)}"><div class="ptext-inner">'
                )
                anchor = f"{line_label(labels, p)} · {dom_label} · {sev_label}"
                stats = (
                    f'{label(labels, "present")} {p.present_hits} · {label(labels, "past")} {p.past_hits} · '
                    f"ASL {N(p.asl, 1)} · {label(labels, 'dialogue')} {P(p.dialogue_pct)} · "
                    f"{label(labels, 'function_words')} {P(p.function_word_pct)} · "
                    f"{label(labels, 'feat_filter')} {N(p.filter_density, 1)} · {label(labels, 'feat_modal')} {N(p.modal_density, 1)} · "
                    f"{label(labels, 'feat_nominal')} {N(p.nominal_density, 1)} · {label(labels, 'feat_passive')} {N(p.passive_density, 1)} · "
                    f"{p.words} {label(labels, 'words')}"
                )
                paragraph_content[f"p-{idx}"] = [p.text, anchor, stats]
                # The fallback preserves the full offline report without JavaScript.
                # JavaScript removes the inert fallback before lazy rendering.
                parts.append(
                    f'<noscript><p>{esc(p.text)}</p><details class="paragraph-values">'
                    f'<summary>{L("paragraph_values")}</summary>'
                    f'<div class="anchor">{esc(anchor)}</div><div class="stats">{esc(stats)}</div></details>'
                )
                if controls:
                    buttons = " ".join(
                        f'<button class="ctl" data-marker-kind="{esc(kind, quote=True)}" '
                        f'data-line="{p.start_line}">+ {esc(label(labels, "marker_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(
                        f'<div class="row marker-row">{buttons}'
                        f'<span class="marker-note-slot" '
                        f'data-placeholder="{esc(label(labels, "marker_note"), quote=True)}"></span>'
                        f"</div>"
                    )
                parts.append("</noscript>")
                parts.append("</div></div>")
        parts.append("</section>")
    parts.append("</main>")
    content_json = json.dumps(paragraph_content, ensure_ascii=False, separators=(",", ":"))
    # Script raw text does not decode HTML entities. Escape angle brackets so
    # manuscript strings, including </script>, cannot end this inert JSON block.
    content_json = content_json.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    parts.append(f'<script type="application/json" id="paragraph-content">{content_json}</script>')

    # --- Chapter matrix ---------------------------------------------------
    if chapters:
        parts.append(panel_start("matrix", labels, "chapter_table"))
        parts.append('<div class="table-wrap">')
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th scope="col">{help_term(labels, "chapter_row", "#")}</th>'
            f'<th scope="col">{help_term(labels, "chapter_row", L("chapter"))}</th>'
            f'<th scope="col" class="num">{help_term(labels, "words", L("words"))}</th>'
            f'<th scope="col" class="num">{help_term(labels, "asl", "ASL")}</th>'
            f'<th scope="col" class="num">{help_term(labels, "dialogue", L("dialogue"))}</th>'
            f'<th scope="col" class="num">{help_term(labels, "function_words", L("function_words"))}</th>'
            f'<th scope="col">{help_term(labels, "chapter_tense", L("past") + "/" + L("present"))}</th>'
            f'<th scope="col" class="num">{help_term(labels, "chapter_flags", L("flagged"))}</th>'
        )
        if fingerprint is not None:
            parts.append(
                f'<th scope="col" class="num">{help_term(labels, "chapter_deviation", L("deviation"))}</th>'
            )
        parts.append("</tr></thead><tbody>")
        max_asl = max((c.asl for c in chapters), default=1.0) or 1.0
        max_dialog = max((c.dialog_pct for c in chapters), default=1.0) or 1.0
        for c in chapters:
            row_hint = ' data-flags="1"' if c.flagged else ""
            parts.append(
                f'<tr class="row-link" data-jump="#ch-{c.num}"{row_hint} role="button" tabindex="0">'
                f"<td>{c.num}</td><td>{esc(c.title)}</td>"
                f'<td class="num">{N(c.words, 0)}</td>'
                f'<td class="num bar-cell"><i style="--v:{c.asl / max_asl * 100:.0f}%"></i>'
                f"{N(c.asl, 1)}</td>"
                f'<td class="num bar-cell"><i style="--v:{c.dialog_pct / max_dialog * 100:.0f}%"></i>'
                f"{P(c.dialog_pct)}</td>"
                f'<td class="num">{P(c.function_word_pct)}</td>'
                f'<td>{esc(tense_label(labels, c.dominant))}</td><td class="num">{c.flagged}</td>'
            )
            if fingerprint is not None:
                dev = fingerprint.deviations.get(c.num, {})
                if dev:
                    named = ", ".join(
                        f"{label(labels, label_key)}: z* = {N(z, 1, signed=True)}"
                        for field_name, label_key, _unit in FEATURES
                        if (z := dev.get(field_name)) is not None
                    )
                    parts.append(
                        f'<td class="num" title="{esc(named, quote=True)}">{len(dev)}</td>'
                    )
                else:
                    parts.append('<td class="num">–</td>')
            parts.append("</tr>")
        parts.append("</tbody></table></div></section>")

    if not has_chapters:
        parts.append("</div>")

    if controls:
        parts.append("</div>")

    # --- Publications (for standalone non-interactive reports) ------------
    if not controls and artifacts:
        parts.append('<section class="panel">')
        parts.append(f"<h2>{help_term(labels, 'artifacts', L('artifacts'))}</h2>")
        parts.append('<div class="artifacts">')
        for art in artifacts:
            name = esc(str(art.get("name", "")))
            meta_bits = []
            if art.get("size_kb") is not None:
                meta_bits.append(f"{N(art['size_kb'], 0)} KB")
            if art.get("pages"):
                meta_bits.append(f"{art['pages']} {label(labels, 'pages')}")
            meta = " · ".join(meta_bits)
            href = artifact_href(art.get("href"))
            link = (
                f'<a href="{esc(str(href))}" target="_blank" rel="noopener">{L("open")}</a>'
                if href
                else ""
            )
            parts.append(
                f'<div class="artifact"><span class="name">{name}</span>'
                f'<span class="meta">{esc(meta)}</span>{link}</div>'
            )
        parts.append("</div></section>")

    parts.extend(
        [
            "</div>",
            f"<footer><span>{esc(engine_name)} · {L('app_suffix')}</span><span>{esc(title)}</span></footer>",
            f"<script>{_JS}</script>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts) + "\n"
