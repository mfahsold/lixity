"""lixity.ui.dashboard – Minimalist, self-contained single-file HTML dashboard.

Renders an interactive stylometric report combining KPI cards, sentence rhythm bars,
diverging z-score heatmap, style passport, latent dimensions, chapter map,
and editor-visible work markers with floating tooltips.
"""

import html
import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import lru_cache
from pathlib import Path as _Path
from typing import Any

from ..diversity import MIN_TOKENS_LD
from ..format import num as format_num
from ..format import pct as format_pct
from ..language import ResolvedLanguage
from ..pipeline import DocumentAnalysis, paragraph_identity
from ..site import docs_url
from ..status import FLAG_MIN_SEVERITY
from ..style_fingerprint import (
    FEATURE_UNITS,
    FEATURES,
    LAYER_FEATURES,
    LAYER_PARAGRAPH_ATTR,
    MIN_COMPARABLE_WORDS,
    PARAGRAPH_LAYER_Z_CUTOFF,
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
    ANALYSIS_SECTIONS,
    analysis_outline_nav,
    artifact_href,
    checkbox_field,
    help_term,
    kpi,
    label,
    license_terms,
    line_label,
    manuscript_pdf_controls,
    panel_start,
    product_details,
    project_header,
    section_nav,
    status_strip,
    tense_class,
    tense_label,
)
from .dimensions import style_dimensions
from .dossier_images import image_limits_attribute
from .heatmap import (
    render_heatmap_panel,
    render_metric_context,
    render_register_targets,
    render_style_passport_panel,
)
from .manuscript_document import ReaderBlock, reader_block_html
from .manuscript_reader import reading_controls
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
from .project_overview import project_overview
from .research_panel import render_research_panel
from .settings import settings_form
from .structural import style_structural

_ASSET_DIR = _Path(__file__).with_name("assets")
_CSS_FILES = (
    "design-tokens.css",
    "components.css",
    "dashboard.css",
    "vendor/photoswipe-5.4.4.css",
    "research-media.css",
    "research-navigation.css",
    "dossier-images.css",
    "vendor/leaflet-1.9.4.css",
    "dossier-geography.css",
    "workspace-reader.css",
    "manuscript-links.css",
    "manuscript-reader.css",
    "decision-review.css",
    "analysis-scope.css",
    "section-navigation.css",
    "analysis-evidence.css",
    "reader-publication.css",
    "project-overview.css",
)
_JS_FILES = (
    "read-only-site.js",
    "vendor/preact-10.29.8.min.js",
    "vendor/htm-3.1.1.umd.js",
    "vendor/leaflet-1.9.4.min.js",
    "vendor/photoswipe-5.4.4.umd.min.js",
    "research-media.js",
    "component-layer.js",
    "tooltips.js",
    "interactions.js",
    "section-navigation.js",
    "register-settings.js",
    "site-publication-settings.js",
    "dashboard.js",
    "analysis-scope.js",
    "zotero-results.js",
    "research-cards.js",
    "research-core.js",
    "research-content.js",
    "research-evidence.js",
    "research-lists.js",
    "research-review.js",
    "research-workspace.js",
    "research-revisions.js",
    "workspace-state.js",
    "workspace-motion.js",
    "project-ui.js",
    "project-overview.js",
    "dossier-images.js",
    "dossier-geography.js",
    "style-space.js",
    "metric-context.js",
    "workspace-reader.js",
    "manuscript-links.js",
    "manuscript-reader.js",
    "analysis-evidence.js",
    "analysis-review.js",
    "reader-publication.js",
)


@lru_cache(maxsize=2)
def _bundle(files: tuple[str, ...]) -> str:
    """Join packaged assets on first use; importing the module does no I/O."""
    return "\n".join((_ASSET_DIR / name).read_text(encoding="utf-8") for name in files)


def _script_json(value: Any) -> str:
    """Keep JSON data inside an inert HTML script's raw-text boundary."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def render_analysis(
    analysis: DocumentAnalysis,
    resolved: ResolvedLanguage,
    *,
    title: str,
    flag_min_severity: int,
    **options: Any,
) -> str:
    """Render one ``analyze_document`` result through the shared wiring.

    Centralises the chapters/paragraphs/metrics/fingerprint/labels/identity
    arguments every dashboard surface passes; surface-specific options stay in
    ``options``.
    """
    return render_dashboard(
        analysis.chapters,
        analysis.paragraphs,
        metrics=analysis.metrics,
        fingerprint=analysis.fingerprint,
        paragraph_evidence=analysis.evidence,
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        flag_min_severity=flag_min_severity,
        **options,
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
    read_only: bool = False,
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
    manuscript_pdf_token: str = "",
    research_context_token: str = "",
    publication: Mapping[str, Any] | None = None,
    publication_error: str = "",
    project_token: str = "",
    manuscript_source_sha256: str = "",
    register_settings: Mapping[str, Any] | None = None,
    site_publications: Mapping[str, Any] | None = None,
    site_publication_context_token: str = "",
    reader_document: Sequence[ReaderBlock] | None = None,
    paragraph_evidence: Mapping[int, Mapping[str, Any]] | None = None,
    project_overview_enabled: bool = False,
) -> str:
    """Renders the complete, deterministic single-file dashboard.

    ``controls=True`` adds the native workspace. ``read_only=True`` preserves
    its reading surfaces while removing local administration and writes.
    ``enabled_actions`` limits
    optional actions to those implemented by the embedding server; ``None``
    preserves the other existing controls. NDA generation requires explicit
    ``nda-draft`` capability; ``nda_project_name`` supplies a real project name
    separately from a placeholder dashboard title.
    ``research-manuscript-review`` enables saved-anchor inspection without
    editing; ``research-manuscript-link`` also enables association writes.
    Manuscript PDF generation requires explicit ``manuscript-pdf`` capability
    and an opaque ``manuscript_pdf_token`` for the selected server context.
    ``research_context_token`` binds native research controls to their selected
    research root; standalone renderers supply no guessed context.
    ``project_overview_enabled`` enables explicit local project inspection;
    embedding and read-only exports omit that surface by default.
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
    can_edit = controls and not read_only
    show_project_overview = can_edit and project_overview_enabled

    def action_enabled(action: str) -> bool:
        return not read_only and (allowed_actions is None or action in allowed_actions)

    reader_enabled = (
        controls and allowed_actions is not None and "research-reader" in allowed_actions
    )
    manuscript_links_mode = (
        "1" if not read_only and allowed_actions is not None and "research-manuscript-link" in allowed_actions
        else "read" if allowed_actions is not None and
        {"research-manuscript-review", "research-manuscript-link"}.intersection(allowed_actions)
        else "0"
    )

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
                    "words",
                    "words_one",
                    "layer_below",
                    "layer_above",
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

    total_words = metrics.tokens if metrics is not None else sum(c.words for c in chapters)
    if flag_min_severity is None:
        flag_min_severity = (
            fingerprint.thresholds.flag_min_severity
            if fingerprint is not None
            else int(FLAG_MIN_SEVERITY)
        )
    if flag_min_severity not in (1, 2, 3):
        flag_min_severity = int(FLAG_MIN_SEVERITY)
    total_flagged = sum(1 for p in paragraphs if p.severity >= flag_min_severity)
    scale = max(1, max((p.words for p in paragraphs), default=1))
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
        field = LAYER_FEATURES[key]
        units = FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])
        return f"{label(labels, 'layer_' + key)}: {N(value, 1)} {units[field]}"

    def _layer_tip(key: str, value: float, z: float) -> str:
        direction = label(labels, "layer_above" if z > 0 else "layer_below" if z < 0 else "layer_at")
        return f"{_layer_text(key, value)} · {direction} · z = {N(z, 2, True)}"

    meta_bits: list[str] = []
    if chapters and total_words > 0:
        chapter_key = "chapter" if len(chapters) == 1 else "chapters"
        meta_bits.append(f"{len(chapters)} {label(labels, chapter_key)}")
        meta_bits.append(f"{N(total_words, 0)} {label(labels, 'words')}")
    if manuscript_name:
        meta_bits.append(manuscript_name)
    project_meta = " · ".join(meta_bits)

    has_chapters = bool(chapters) and total_words > 0
    has_reading = has_chapters or bool(reader_document)
    default_view = "analysis" if has_reading or (read_only and not research_context_token) else "research"
    body_class = "lixity-workspace" if controls else "lixity-report"
    if controls and has_reading:
        body_class += " has-reading"
    if (controls and reader_document and reader_document[0].kind == "heading"
            and reader_document[0].level == 1 and reader_document[0].text == title):
        body_class += " has-source-title"

    parts = [
        "<!DOCTYPE html>",
        f'<html lang="{html_lang}">',
        "<head>",
        '<meta charset="utf-8"/>',
        '<link rel="icon" href="data:,"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        *(('<meta name="lixity-debug" content="true"/>',) if debug else ()),
        f"<title>{esc(title)} – {esc(engine_name)}</title>",
        f"<style>{_bundle(_CSS_FILES)}</style>",
        "</head>",
        f'<body id="top" class="{body_class}" data-api="{esc(api_base)}" data-ui-labels="{workspace_labels_json}" '
        f'data-read-only="{str(read_only).lower()}" '
        f'data-manuscript-source-sha256="{esc(manuscript_source_sha256)}" '
        f'data-manuscript-project-token="{esc(manuscript_pdf_token)}" '
        f'data-manuscript-links="{manuscript_links_mode}" '
        f'data-image-limits="{image_limits_attribute()}" '
        f'data-dossier-media-capable="{str(controls and allowed_actions is not None and action_enabled("research-dossier-media")).lower()}" '
        f'data-dossier-image-capable="{str(controls and allowed_actions is not None and action_enabled("research-dossier-image")).lower()}">',
        f'<a class="skip-link" href="#chapters">{L("skip_main")}</a>',
        *((f'<p class="site-read-only-notice" role="note">{L("site_read_only")}</p>',) if read_only else ()),
        '<div class="page">',
        *(('<div class="workspace-shell"><div class="workspace-shell-header">',
           f'<button type="button" class="ctl workspace-navigation-toggle" id="workspace-navigation-toggle" '
           f'aria-label="{L("navigation_collapse")}" aria-controls="workspace-navigation-content" aria-expanded="true" '
           f'title="{L("navigation_collapse")}">'
           '<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" '
           'stroke-width="1.5" aria-hidden="true" focusable="false">'
           '<rect x="2.5" y="3.5" width="15" height="13" rx="2"/><path d="M7.5 3.5v13"/></svg></button>',
           f'<span class="product-name">{esc(engine_name)}</span></div>') if controls else ()),
    ]

    if not controls:
        parts.append(project_header(title, labels, language_name, engine_name, meta=project_meta))

    if controls:
        parts.append(
            '<nav class="view-navigation" role="tablist" aria-label="' + L("workspace") + '">'
            f'<button type="button" class="view-nav-tab{" active" if default_view == "analysis" else ""}" data-view="analysis" role="tab" id="tab-view-analysis" aria-controls="view-pane-analysis" aria-selected="{"true" if default_view == "analysis" else "false"}">'
            f"<span>{L('workspace_analysis')}</span>"
            "</button>"
            f'<button type="button" class="view-nav-tab{" active" if default_view == "research" else ""}" data-view="research" role="tab" id="tab-view-research" {"data-requires-live " if read_only and not research_context_token else ""}aria-controls="view-pane-research" aria-selected="{"true" if default_view == "research" else "false"}">'
            f"<span>{L('workspace_research')}</span>"
            "</button>"
            f'<button type="button" class="view-nav-tab" data-view="project" role="tab" id="tab-view-project" data-requires-write aria-controls="view-pane-project" aria-selected="false">'
            f"<span>{L('workspace_project')}</span>"
            "</button>"
            "</nav>"
        )
        parts.append('<div id="workspace-navigation-content">')
        parts.append(project_header(title, labels, language_name, engine_name, compact=True, meta=project_meta))
        parts.append(
            '<details class="workspace-actions" id="project-actions" data-requires-write'
            + ("" if has_reading else " open") + ">"
        )
        parts.append(f'<summary>{L("project_actions")}</summary>')
        parts.append(
            f'<nav class="workspace-bar" id="project-controls" aria-label="{L("controls")}">'
        )
        parts.append('<div class="row">')
        parts.append(
            f'<button type="button" class="ctl{"" if has_chapters else " primary"}" id="btn-modal-new-project">{L("new_project")}</button>'
        )
        parts.append(
            f'<button type="button" class="ctl" id="btn-modal-open-project">{L("open_project")}</button>'
        )
        if allowed_actions is not None and action_enabled("site-export"):
            parts.append(
                '<button type="button" class="ctl" id="btn-site-export"'
                + ("" if manuscript_pdf_token else " disabled")
                + f'>{L("site_export")}</button>'
            )
        show_guidance_hidden = "" if chapters else " hidden"
        parts.append(
            f'<button type="button" class="ctl" id="welcome-show" aria-controls="welcome-hero" aria-expanded="false"{show_guidance_hidden}>{L("welcome_show")}</button>'
        )
        parts.append("</div>")
        if allowed_actions is not None and "manuscript-pdf" in allowed_actions:
            parts.append(
                manuscript_pdf_controls(
                    labels,
                    api_base=api_base,
                    project_token=manuscript_pdf_token,
                    available=has_chapters and bool(paragraphs) and bool(manuscript_pdf_token),
                )
            )
        parts.append("</nav></details>")
        parts.append('<p class="workspace-product-details">' + product_details(labels) + '</p>')
        parts.append("</div></div>")

    if status:
        parts.append(status_strip(labels, status))
    parts.append("<!--dashboard-freshness-->")

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
            + " data-requires-write>"
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
                f'      <button type="button" class="ctl welcome-btn" id="hero-btn-open-project">{L("open_project")}</button>'
            )
            parts.append(
                f'      <button type="button" class="ctl welcome-btn" id="hero-btn-browse-project">{L("wizard_choose_action")}</button>'
            )
            parts.append("    </div>")
            # Every entry point follows the same synthetic project across views.
            parts.append(
                '    <p class="welcome-example"><a href='
                f'"{docs_url("demo/report.html")}" target="_blank" rel="noopener">'
                f"{L('welcome_example')} ↗</a></p>"
            )
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
        parts.append(
            f'    <details class="welcome-more"><summary>{L("welcome_more")}</summary><div class="welcome-features">'
        )
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
        parts.append(render_research_panel(labels, research_context_token=research_context_token, read_only=read_only))
        parts.append("</div>")
        parts.append(
            '<div class="view-pane" id="view-pane-project" data-view-pane="project" data-requires-write role="tabpanel" aria-labelledby="tab-view-project">'
        )
        parts.append('<section class="panel controls" id="controls">')
        parts.append(f"<h2>{L('workspace_project')}</h2>")
        if show_project_overview:
            parts.append(project_overview(labels, research_navigation=bool(
                research_context_token and research_context_token == site_publication_context_token)))

        # Hosts that advertise `load` get their upload control here. The native
        # app imports through the single project dialog instead, so this view
        # does not duplicate that flow.
        if action_enabled("load"):
            parts.append('<div class="ctl-group">')
            parts.append(f'<span class="ctl-label">{L("manuscript")}</span>')
            parts.append('<input type="file" id="ms-file" accept=".md,.markdown,.txt" hidden/>')
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
            parts.append(
                f'<button type="button" class="ctl primary" data-action="load" data-payload="load" disabled>{L("dropzone_action")}</button>'
            )
            parts.append("</div>")
            parts.append(f'<p class="ctl-note">{L("manuscript_load_hint")}</p>')
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
                publication=publication,
                publication_error=publication_error,
                project_token=project_token,
                register_settings=register_settings,
                site_publications=site_publications,
                site_publication_context_token=site_publication_context_token,
                language_key=language_key,
            )
        )

        # Actions advertised by the embedding server.
        visible_actions = [
            action
            for action in ("analyze", "sync", "audit", "prune", "gdrive", "rebuild")
            if action_enabled(action)
        ]
        if action_enabled("export") or visible_actions:
            # The heading belongs to the results group. Keeping both in one
            # element preserves the separator rule between adjacent groups.
            parts.append('<div class="ctl-group">')
            parts.append(f'<h3 class="section-heading">{L("settings_results")}</h3>')
            action_heading = (
                f"{L('export')} · {L('run_analysis')}"
                if action_enabled("export") and visible_actions
                else L("export")
                if action_enabled("export")
                else L("run_analysis")
            )
            if action_enabled("export") or len(visible_actions) > 1:
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
        # Generated files belong to the Results step, directly under the actions.
        if artifacts and not show_project_overview:
            parts.append('<section class="panel">')
            parts.append(f"<h2>{help_term(labels, 'artifacts', L('generated_files'))}</h2>")
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

        parts.append("</div>")
        parts.append(render_project_modals(labels, language_key, language_options))

        # --- PANE 3: MANUSCRIPT & ANALYSIS ---
        parts.append(
            f'<div class="view-pane{" active" if default_view == "analysis" else ""}" id="view-pane-analysis" data-view-pane="analysis" role="tabpanel" aria-labelledby="tab-view-analysis">'
        )

    reader_controls = ""
    if controls and has_reading:
        reader_controls = (
            '<div class="reader-controls">'
            '<button type="button" class="ctl reader-compact-control" id="workspace-reader-toggle" '
            f'aria-label="{L("reader_toggle")}" title="{L("reader_toggle")}" '
            f'data-help="{L("reader_hint")}" '
            'aria-expanded="false" aria-controls="workspace-reader-panel" disabled>'
            '<span class="reader-control-icon" aria-hidden="true">▤</span>'
            f'<span class="reader-control-label">{L("reader_toggle")}</span></button><p class="ctl-note">'
            f"{L('reader_hint') if manuscript_pdf_token else L('reader_unavailable')}</p></div>"
        ) if reader_enabled else ""
        parts.append(
            '<section id="workspace-reader" '
            f'data-project-token="{esc(manuscript_pdf_token)}">'
            '<div class="workspace-reader-layout" id="workspace-reader-layout">'
            '<div id="workspace-context-panel" class="workspace-context-panel" hidden>'
            '<div class="context-tool-tabs" role="group">'
            f'<button type="button" class="ctl" data-context-tool="analysis" aria-pressed="false">{L("reading_passage_context")}</button>'
            f'<button type="button" class="ctl" data-context-tool="dossier" aria-pressed="false" {"" if reader_enabled else "hidden"}>{L("reader_title")}</button></div>'
            '<aside class="panel workspace-reader-panel" id="workspace-reader-panel" '
            'aria-labelledby="workspace-reader-title" hidden>'
            '<div class="workspace-reader-head">'
            f'<h2 id="workspace-reader-title">{L("reader_title")}</h2>'
            f'<button type="button" class="ctl" id="workspace-reader-close" aria-label="{esc(L("modal_close"), quote=True)}">✕</button>'
            "</div>"
            '<div class="row workspace-reader-controls" id="workspace-reader-collection-field" hidden>'
            '<div class="setting-field grow">'
            f'<label for="workspace-reader-collection">{L("research_dossier_collection")}</label>'
            f'<select class="ctl" id="workspace-reader-collection"><option value="all">{L("research_dossier_collection_all")}</option></select></div></div>'
            '<div class="row workspace-reader-controls">'
            '<div class="setting-field grow">'
            f'<label for="workspace-reader-dossier">{L("reader_choose")}</label>'
            f'<select class="ctl" id="workspace-reader-dossier"><option value="">{L("reader_choose")}</option></select></div>'
            f'<button type="button" class="ctl" id="workspace-reader-refresh">{L("reader_refresh")}</button></div>'
            '<p class="ctl-status" id="workspace-reader-status" role="status" aria-live="polite"></p>'
            '<div id="workspace-reader-body"></div></aside></div>'
            '<div id="workspace-reader-divider" class="workspace-reader-divider" role="separator" '
            'tabindex="0" aria-orientation="vertical" aria-valuemin="35" aria-valuemax="75" '
            f'aria-valuenow="62" aria-label="{L("reading_split")}" '
            'aria-controls="workspace-analysis-body workspace-context-panel" hidden></div>'
            '<div id="workspace-analysis-body">'
        )

    if not has_reading:
        parts.append(
            '<div class="panel empty-analysis-state">'
            '<div class="empty-state-icon" aria-hidden="true">📖</div>'
            f"<h2>{L('analysis_empty_title')}</h2>"
            f'<p class="ctl-note empty-state-note">{L("analysis_empty_desc")}</p>'
            '<div class="row empty-actions">'
            f'<button type="button" class="ctl primary" id="analysis-empty-import">{L("welcome_import_action")}</button>'
            f'<button type="button" class="ctl" data-switch-view="project">{L("analysis_empty_to_project")}</button>'
            f'<button type="button" class="ctl" data-switch-view="research">{L("analysis_empty_to_research")}</button>'
            "</div>"
            "</div>"
        )
        parts.append("<div hidden>")

    metric_control = ""
    layer_navigation = (
        f'<div class="reader-outlier-navigation" role="group" aria-label="{L("legend_paragraph_comparison")}">'
        f'<button class="ctl" type="button" id="layer-prev" disabled '
        f'aria-label="{L("layer_previous")}" title="{L("layer_previous")}">↑</button>'
        f'<output id="layer-position" aria-live="polite" aria-atomic="true" '
        f'aria-label="{esc(label(labels, "layer_position").format(current=0, total=0), quote=True)}">0 / 0</output>'
        f'<button class="ctl" type="button" id="layer-next" disabled '
        f'aria-label="{L("layer_next")}" title="{L("layer_next")}">↓</button></div>'
    )
    if paragraphs:
        layer_groups = (
            ("layer_group_rhythm", ("asl", "function")),
            ("layer_group_voice", ("dialogue", "filter")),
            ("layer_group_grammar", ("passive", "modal", "nominal")),
        )
        grouped_members = {m for _, members in layer_groups for m in members}
        grouped_layer_options = []
        for group_label_key, members in layer_groups:
            options_html = "".join(
                f'<option value="{layer_key}" '
                f'data-hint="{esc(label(labels, "layer_hint_" + layer_key), quote=True)}" '
                f'data-unit="{esc(FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])[LAYER_FEATURES[layer_key]], quote=True)}" '
                f'data-comparable="{len(layer_data.get(layer_key, {}))}">'
                f"{esc(label(labels, 'layer_' + layer_key))}</option>"
                for layer_key in members
                if layer_key in LAYER_FEATURES
            )
            if options_html:
                grouped_layer_options.append(f'<optgroup label="{L(group_label_key)}">{options_html}</optgroup>')

        remaining_options = "".join(
            f'<option value="{layer_key}" '
            f'data-hint="{esc(label(labels, "layer_hint_" + layer_key), quote=True)}" '
            f'data-unit="{esc(FEATURE_UNITS.get(language_key, FEATURE_UNITS["en"])[LAYER_FEATURES[layer_key]], quote=True)}" '
            f'data-comparable="{len(layer_data.get(layer_key, {}))}">'
            f"{esc(label(labels, 'layer_' + layer_key))}</option>"
            for layer_key in LAYER_FEATURES
            if layer_key not in grouped_members
        )
        if remaining_options:
            grouped_layer_options.append(remaining_options)

        metric_control = (
            '<label class="metric-layer-control">'
            f'<span>{L("analysis_measure") if controls else help_term(labels, "layer", L("style_layer"))}</span> '
            '<select class="ctl" id="style-layer">'
            f'<option value="">{L("layer_off")}</option>'
            + "".join(grouped_layer_options)
            + "</select></label>"
        )
    # Use one navigation in the measured reader header when available, with
    # the same registry-backed anchors in static reports without reader controls.
    available = {"flags"} if has_chapters else set()
    if metrics is not None:
        available.add("dist")
    if scenes:
        available.add("scenes")
    if motifs:
        available.add("motifs")
    if has_house_style or (fingerprint is not None and metrics is not None and metrics.chapters):
        available.add("style")
    if chapters:
        available.add("matrix")
    active_sections = [entry for entry in ANALYSIS_SECTIONS if entry[0] in available]
    overview_navigation = section_nav(active_sections, labels)
    outline_sections = ([("analysis-review", "review_title")] if has_chapters else []) + active_sections
    analysis_outline = analysis_outline_nav(outline_sections, labels)

    if has_reading and controls:
        analysis_controls = (
            f'<div class="reader-analysis-controls" id="reader-analysis-settings" role="group" '
            f'aria-label="{L("reading_text_analysis")}">'
            f'{metric_control}'
            f'{layer_navigation}'
            '<div class="reader-analysis-switches">'
            f'<label class="reader-evidence-toggle"><input type="checkbox" id="analysis-evidence-enabled" checked/> '
            f'<span class="analysis-evidence-key">{L("legend_counted_text")}</span></label>'
            f'<label class="reader-comparison-toggle"><input type="checkbox" id="analysis-comparison-enabled" checked/> '
            f'<span class="analysis-comparison-key">{L("legend_paragraph_comparison")}</span></label>'
            '</div></div>'
        ) if paragraphs else ""
        parts.append(reading_controls(chapters, labels, reader_document, companion_controls=reader_controls,
                                      analysis_controls=analysis_controls, overview_navigation=overview_navigation))
    else:
        parts.append(overview_navigation)

    parts.append('<div class="analysis-outline-folder">')
    parts.append('<div class="analysis-outline-layout">')
    parts.append('<div class="analysis-outline-document" id="analysis-outline-document">')

    if has_chapters:
        parts.append(f'<section class="panel" id="analysis-review"><h2>{L("review_title")}</h2>')
        parts.append(f'<p class="panel-guide">{L("review_intro")}</p><div class="review-routes">')
        if paragraphs:
            candidates = flagged_paragraphs(list(paragraphs), min_severity=flag_min_severity)
            first = (
                min(candidates, key=lambda paragraph: paragraph.start_line)
                if candidates
                else paragraphs[0]
            )
            first_index = next(i for i, paragraph in enumerate(paragraphs) if paragraph is first)
            passage_hint = "review_passage_flagged" if candidates else "review_passage_unflagged"
            parts.append(
                f'<article class="review-route"><a class="ctl primary" href="#p-{first_index}" '
                f'data-help="{L(passage_hint)}" '
                'aria-describedby="review-passage-reason" '
                f'data-review-passage="1" data-line="{first.start_line}" data-target="p-{first_index}">'
                f"{L('review_passage_action')}</a>"
                f'<p class="ctl-note" id="review-passage-reason">{L(passage_hint)}</p></article>'
            )
        compare_target = (
            "heatmap"
            if has_house_style and metrics is not None and metrics.chapters
            else "chapters"
        )
        compare_hint = (
            "review_compare_hint" if compare_target == "heatmap" else "review_compare_limited"
        )
        review_routes = [
            ("review_compare", compare_hint, "review_compare_action", compare_target),
        ]
        if metrics is not None:
            review_routes.append(
                ("review_rhythm", "review_rhythm_hint", "review_rhythm_action", "dist")
            )
        for _title_key, hint_key, action_key, target in review_routes:
            parts.append(
                f'<article class="review-route"><a class="ctl" href="#{target}" '
                f'data-help="{L(hint_key)}" data-jump="#{target}">{L(action_key)}</a></article>'
            )
        parts.append("</div></section>")

    # --- Toolbar ----------------------------------------------------------
    parts.append('<div class="toolbar">')
    parts.append('<span class="text-search-group">')
    parts.append(
        f'<input class="ctl" type="search" id="text-search" autocomplete="off" '
        f'placeholder="{L("text_search")}" aria-label="{L("text_search")}" '
        f'aria-controls="chapters" data-help="{L("reading_help_search")}" '
        'aria-keyshortcuts="Enter Shift+Enter Escape"/>'
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
    parts.append(checkbox_field('<input type="checkbox" id="filter-flags"/>', L("filter_flags")))
    if paragraphs:
        parts.append(
            f'<button type="button" class="ctl" id="paragraph-filter-reset">{L("paragraph_filter_reset")}</button>'
        )
        if not controls:
            parts.append(metric_control)
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
    parts.append(
        f'<p class="ctl-note toolbar-note" id="paragraph-metrics-note">{L("paragraph_metrics_note")}</p>'
    )
    parts.append("</div>")

    parts.append(
        f'<div class="layer-legend" id="layer-legend" hidden="hidden" '
        f'data-cutoff="{PARAGRAPH_LAYER_Z_CUTOFF}" '
        f'data-profiled="{len(paragraphs)}" '
        f'data-outliers="{esc(label(labels, "layer_outliers"), quote=True)}" '
        f'data-outliers-one="{esc(label(labels, "layer_outliers_one"), quote=True)}">'
    )
    parts.append('<div class="layer-legend-group" id="layer-evidence-legend">'
                 f'<strong class="analysis-evidence-swatch">{L("legend_counted_text")}</strong>'
                 '<p class="ctl-note" id="analysis-evidence-status" role="status" aria-live="polite"></p></div>')
    parts.append('<div class="layer-legend-group" id="layer-comparison-legend">'
                 f'<strong>{L("legend_paragraph_comparison")}</strong>')
    parts.append('<span class="layer-title" id="layer-legend-title" tabindex="0"></span>')
    parts.append(
        f'<span class="layer-scale"><span id="layer-scale-low" '
        f'style="--layer-direction-color:{z_color(-PARAGRAPH_LAYER_Z_CUTOFF)}">↓ {L("layer_below")}</span>'
        f'<span id="layer-scale-high" style="--layer-direction-color:{z_color(PARAGRAPH_LAYER_Z_CUTOFF)}">'
        f'↑ {L("layer_above")}</span></span>'
    )
    parts.append('<span class="layer-count" id="layer-legend-count" role="status" aria-live="polite"></span>')
    parts.append(
        f'<label class="layer-only"><input type="checkbox" id="layer-only"/> '
        f"{esc(label(labels, 'layer_only'))}</label>"
    )
    if not (has_reading and controls and paragraphs):
        parts.append(layer_navigation)
    parts.append('</div>')
    parts.append(f'<details class="layer-comparison-note"><summary>{L("analysis_marks_help")}</summary>'
                 '<p id="layer-comparison-hint"></p><p id="layer-evidence-hint"></p>'
                 f'<p class="ctl-note">{L("layer_comparison_help")}</p>'
                 f'<button class="ctl" id="layer-clear" type="button">{L("layer_clear")}</button></details>')
    parts.append("</div>")

    if not tense_available:
        parts.append(f'<p class="hint">{L("no_tense")}</p>')

    # --- Chapter map ------------------------------------------------------
    by_chapter: dict[int, list[tuple[int, Any]]] = {}
    paragraph_content: dict[str, list[Any]] = {}
    for idx, p in enumerate(paragraphs):
        by_chapter.setdefault(p.chapter_num, []).append((idx, p))

    main_start = len(parts)
    profile_markup: dict[int, str] = {}
    chapter_markup: dict[int, str] = {}
    parts.append('<main id="chapters" role="main" tabindex="-1">')
    for chapter in chapters:
        chapter_start = len(parts)
        chapter_paras = by_chapter.get(chapter.num, [])
        has_flags = any(p.is_flagged for _, p in chapter_paras)
        classes = "chapter has-flags" if has_flags else "chapter"
        parts.append(
            f'<section class="{classes}" id="ch-{chapter.num}" '
            f'data-start="{chapter.start_line}" data-end="{chapter.end_line}">'
        )
        parts.append('<div class="chapter-head">')
        parts.append(
            f'<h2><button class="chapter-toggle" type="button" data-chapter-toggle '
            f'aria-expanded="true" title="{esc(L("chapter_fold"), quote=True)}" '
            f'aria-label="{esc(L("chapter_fold"), quote=True)}"></button>'
            f"{chapter.num}. {esc(chapter.title)}</h2>"
        )
        words_unit = L("words_one") if chapter.words == 1 else L("words")
        paragraphs_unit = L("paragraphs_one") if chapter.paragraphs == 1 else L("paragraphs")
        flags_unit = L("flags_one") if chapter.flagged == 1 else L("flags")
        parts.append(
            f'<span class="meta">{N(chapter.words, 0)} {words_unit} · '
            f"{chapter.paragraphs} {paragraphs_unit} · {esc(tense_label(labels, chapter.dominant))} · "
            f"{chapter.flagged} {flags_unit} · {L('line')} {chapter.start_line}–{chapter.end_line}</span>"
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
                        colour = z_color(z)
                        layer_payload[key] = [colour, f"{line_label(labels, p)} · {_layer_tip(key, value, z)}",
                                              round(z, 2), N(value, 1)]
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

            chapter_markup[chapter.start_line] = "".join(parts[chapter_start:])
            for idx, p in chapter_paras:
                paragraph_start = len(parts)
                dom_label = tense_label(labels, p.dominant)
                sev_label = label(labels, f"severity_{p.severity}")
                parts.append(
                    f'<div class="ptext" id="p-{idx}" data-start="{p.start_line}" '
                    f'data-end="{p.end_line}" data-paragraph-sha256="{paragraph_identity(p)["paragraph_sha256"]}" '
                    f'data-markers="{int(can_edit)}">'
                )
                anchor = f"{line_label(labels, p)} · {dom_label} · {sev_label}"
                stats = (
                    f"{label(labels, 'present')} {p.present_hits} · {label(labels, 'past')} {p.past_hits} · "
                    f"ASL {N(p.asl, 1)} · {label(labels, 'dialogue')} {P(p.dialogue_pct)} · "
                    f"{label(labels, 'function_words')} {P(p.function_word_pct)} · "
                    f"{label(labels, 'feat_filter')} {N(p.filter_density, 1)} · {label(labels, 'feat_modal')} {N(p.modal_density, 1)} · "
                    f"{label(labels, 'feat_nominal')} {N(p.nominal_density, 1)} · {label(labels, 'feat_passive')} {N(p.passive_density, 1)} · "
                    f"{p.words} {label(labels, 'words')}"
                )
                paragraph_content[f"p-{idx}"] = [p.text, anchor, stats]
                if paragraph_evidence is not None and idx in paragraph_evidence:
                    paragraph_content[f"p-{idx}"].append(paragraph_evidence[idx])
                    paragraph_content[f"p-{idx}"].append({
                        key: _layer_text(key, getattr(p, attribute)) if p.words > 0 else None
                        for key, attribute in LAYER_PARAGRAPH_ATTR.items()
                    })
                # The fallback preserves the full offline report without JavaScript.
                # JavaScript removes the inert fallback before lazy rendering.
                parts.append(
                    f'<noscript><div class="ptext-inner"><p>{esc(p.text)}</p><details class="paragraph-values">'
                    f"<summary>{L('paragraph_values')}</summary>"
                    f'<div class="anchor">{esc(anchor)}</div><div class="stats">{esc(stats)}</div></details>'
                )
                if can_edit:
                    buttons = " ".join(
                        f'<button class="ctl" data-marker-kind="{esc(kind, quote=True)}" '
                        f'data-line="{p.start_line}">{esc(label(labels, "marker_action_" + kind))}</button>'
                        for kind in ("pruefen", "sachcheck", "todo", "achtung")
                    )
                    parts.append(
                        f'<div class="row marker-row">{buttons}'
                        f'<span class="marker-note-slot" '
                        f'data-placeholder="{esc(label(labels, "marker_note"), quote=True)}"></span>'
                        f"</div>"
                    )
                parts.append("</div></noscript></div>")
                profile_markup[idx] = "".join(parts[paragraph_start:])
        parts.append("</section>")
    if reader_document is not None:
        parts[main_start:] = ['<main id="chapters" role="main" tabindex="-1">']
        section_open = False
        for block in reader_document:
            if block.is_chapter:
                if section_open:
                    parts.append("</section>")
                header = chapter_markup.get(block.start_line)
                if header:
                    parts.append(header)
                else:
                    parts.append(f'<section class="chapter" id="source-{block.start_line}" data-start="{block.start_line}" data-end="{block.end_line}">'
                                 f'<div class="chapter-head"><h2>{esc(block.text)}</h2></div>')
                section_open = True
                continue
            if not section_open:
                implicit = chapters[0] if chapters and not any(item.is_chapter for item in reader_document) else None
                if implicit:
                    parts.append(f'<section class="chapter reader-preface" id="ch-{implicit.num}" data-start="{implicit.start_line}" data-end="{implicit.end_line}">'
                                 '<span id="reader-preface"></span>')
                else:
                    parts.append('<section class="chapter reader-preface" id="reader-preface">')
                section_open = True
            if block.profile_index is not None:
                parts.append(profile_markup[block.profile_index])
            else:
                parts.append(reader_block_html(block))
                if block.kind in {"paragraph", "quote", "code", "note", "list_item"}:
                    parts.append(f'<p class="reader-coverage">{L("reading_coverage")}</p>')
        if section_open:
            parts.append("</section>")
    parts.append("</main>")
    content_json = _script_json(paragraph_content)
    parts.append(f'<script type="application/json" id="paragraph-content">{content_json}</script>')
    parts.append('<div id="manuscript-analysis-panels">')

    # --- Key metrics (grouped for scanability) ----------------------------
    scope_tiles = [
        kpi(N(total_words, 0), help_term(labels, "corpus_words" if metrics is not None else "words", L("words_prose")), jump="#matrix"),
        kpi(str(len(chapters)), L("chapter"), jump="#matrix"),
        kpi(str(len(paragraphs)), L("paragraphs"), jump="#matrix"),
    ]
    rhythm_tiles: list[str] = []
    language_tiles: list[str] = []
    lexis_tiles: list[str] = []
    lexis_secondary_tiles: list[str] = []
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
                help_term(labels, "flesch", esc(metrics.flesch_variant or "Flesch")),
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
        mtld_value = (
            N(metrics.mtld, 1)
            if (has_tokens and getattr(metrics, "mtld", None) is not None)
            else "–"
        )
        lexis_tiles.append(kpi(mtld_value, help_term(labels, "mtld", "MTLD"), jump="#bands"))
        lexis_tiles.append(
            kpi(
                N(metrics.guiraud_r, 2) if has_tokens else "–",
                help_term(labels, "guiraud", "Guiraud R"),
                jump="#bands",
            )
        )
        lexis_secondary_tiles.append(
            kpi(
                N(metrics.ttr, 4) if has_tokens else "–",
                help_term(labels, "ttr", "TTR"),
                jump="#bands",
            )
        )
        lexis_secondary_tiles.append(
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
        lexis_secondary_tiles.append(kpi(hd_d_value, help_term(labels, "hd_d", "HD-D"), jump="#bands"))
        mattr_value = (
            N(metrics.mattr, 3)
            if (has_tokens and getattr(metrics, "mattr", None) is not None)
            else "–"
        )
        lexis_secondary_tiles.append(kpi(mattr_value, help_term(labels, "mattr", "MATTR"), jump="#bands"))
        maas_value = (
            N(metrics.maas_a2, 3)
            if (has_tokens and getattr(metrics, "maas_a2", None) is not None)
            else "–"
        )
        lexis_secondary_tiles.append(kpi(maas_value, help_term(labels, "maas", "Maas a²"), jump="#bands"))
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

    p_unit = L("paragraphs_one") if len(paragraphs) == 1 else L("paragraphs")
    scope_narrative = f"{N(total_words, 0)} {L('words_prose')} · {len(chapters)} {L('chapter')} · {len(paragraphs)} {p_unit}"
    rhythm_narrative = (
        f"Ø {N(metrics.asl, 1) if getattr(metrics, 'asl', None) is not None else '–'} {L('words')}/{L('sentence')} · {P(metrics.staccato_pct) if getattr(metrics, 'staccato_pct', None) is not None else '–'} {L('feat_staccato')}"
        if (metrics is not None and metrics.tokens)
        else ""
    )
    language_narrative = (
        f"{P(metrics.dialog_ratio) if getattr(metrics, 'dialog_ratio', None) is not None else '–'} {L('dialogue')} · {esc(metrics.flesch_variant or 'Flesch')} {N(metrics.flesch_de, 1) if getattr(metrics, 'flesch_de', None) is not None else '–'} · LIX {N(metrics.lix, 1) if getattr(metrics, 'lix', None) is not None else '–'}"
        if (metrics is not None and metrics.tokens)
        else ""
    )
    lexis_narrative = (
        f"MTLD {N(metrics.mtld, 1) if getattr(metrics, 'mtld', None) is not None else '–'} · Guiraud {N(metrics.guiraud_r, 2) if getattr(metrics, 'guiraud_r', None) is not None else '–'}"
        if (metrics is not None and metrics.tokens)
        else ""
    )
    style_narrative = (
        f"{L('consistency')} {P(fingerprint.consistency * 100, 0)} · {total_flagged} {L('flagged')}"
        if (fingerprint is not None and fingerprint.measured_cells)
        else (f"{total_flagged} {L('flagged')}" if total_flagged else "")
    )

    measurements_open = "" if controls else " open"
    parts.append(f'<details id="analysis-measurements"{measurements_open}>')
    parts.append(f'<summary>{L("analysis_measurements")}</summary>')
    parts.append('<section class="kpis">')
    if has_chapters and metrics is not None and metrics.tokens < MIN_TOKENS_LD:
        support = esc(label(labels, "scene_support").replace("{min_tokens}", str(MIN_TOKENS_LD)))
        parts.append(f'<p class="hint" role="note">{support}</p>')
    for caption_key, tiles, narrative, *extra in (
        ("group_scope", scope_tiles, scope_narrative),
        ("group_rhythm", rhythm_tiles, rhythm_narrative),
        ("group_language", language_tiles, language_narrative),
        ("group_lexis", lexis_tiles, lexis_narrative, lexis_secondary_tiles),
        ("group_style", style_tiles, style_narrative),
    ):
        if not tiles:
            continue
        parts.append('<div class="kpi-group">')
        parts.append(
            f'<div class="kpi-header"><span class="kpi-caption">{L(caption_key)}</span>'
            + (f'<span class="kpi-narrative">{narrative}</span>' if narrative else '')
            + '</div>'
        )
        parts.append('<div class="kpi-row">')
        parts.extend(tiles)
        parts.append("</div>")
        if extra and extra[0]:
            parts.append(
                f'<div class="kpi-drawer" id="kpi-lexis-drawer">'
                f'<button type="button" class="kpi-drawer-btn" data-kpi-toggle="kpi-lexis-secondary" aria-expanded="false">{L("kpi_lexis_more")}</button>'
                '<div class="kpi-row kpi-drawer-row" id="kpi-lexis-secondary" hidden>'
            )
            parts.extend(extra[0])
            parts.append("</div></div>")
        parts.append("</div>")
    parts.append("</section></details>")

    # --- Flagged passages (list → paragraph → marker) ----------------------
    flagged = flagged_paragraphs(list(paragraphs), min_severity=flag_min_severity)
    review_capable = bool(controls and not read_only and allowed_actions is not None and action_enabled("analysis-review"))
    parts.append(f'<section class="panel" id="flags" data-review-capable="{str(review_capable).lower()}">')
    parts.append(f"<h2>{help_term(labels, 'flagged', label(labels, 'panel_flags'))} "
                 f'<span class="badge">{N(len(flagged), 0)}</span></h2>')
    parts.append(f'<p class="panel-guide">{L("triage_intro")}</p>')
    if flagged:
        parts.append('<div class="row triage-controls">')
        parts.append(f'<label>{L("chapter")} <select class="ctl" id="triage-chapter">'
                     f'<option value="">{L("triage_all")}</option>')
        flagged_chapters = {p.chapter_num for p in flagged}
        parts.extend(f'<option value="{chapter.num}">{chapter.num}. {esc(chapter.title)}</option>'
                     for chapter in chapters if chapter.num in flagged_chapters)
        parts.append('</select></label>')
        parts.append(f'<label>{L("flags_stage")} <select class="ctl" id="triage-severity">'
                     f'<option value="">{L("triage_all")}</option>')
        parts.extend(f'<option value="{severity}">{L(f"severity_{severity}")}</option>'
                     for severity in sorted({p.severity for p in flagged}))
        parts.append('</select></label>')
        if review_capable:
            parts.append(f'<label>{L("triage_status")} <select class="ctl" id="triage-status-filter">'
                         f'<option value="">{L("triage_all")}</option>')
            parts.extend(f'<option value="{status}">{L("triage_" + status)}</option>'
                         for status in ("unreviewed", "stale", "later", "kept", "changed"))
            parts.append('</select></label>')
        parts.append(f'<button type="button" class="ctl" id="triage-next">{L("triage_next")}</button></div>')
        parts.append('<p class="ctl-note" id="triage-progress" role="status" aria-live="polite"></p>')
        if review_capable:
            parts.append(f'<p class="ctl-note">{L("triage_storage")}</p>')
            parts.append('<p class="ctl-status" id="triage-save-status" role="status" aria-live="polite"></p>')
            parts.append(f'<button type="button" class="ctl" id="triage-reload" hidden>{L("triage_reload")}</button>')
        para_index = {id(p): i for i, p in enumerate(paragraphs)}
        parts.append('<div class="table-wrap flags-wrap" tabindex="0" role="region" '
                     f'aria-label="{L("panel_flags")}">')
        parts.append("<table><thead><tr>")
        parts.append(
            f'<th scope="col">{label(labels, "flags_stage")}</th>'
            f'<th scope="col">{L("chapter")}</th>'
            f'<th scope="col" class="num">{L("line")}</th>'
            f'<th scope="col">{label(labels, "flags_excerpt")}</th>'
        )
        parts.append(f'<th scope="col">{L("triage_read")}</th>')
        if review_capable:
            parts.append(f'<th scope="col">{L("triage_status")}</th>')
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
                f'data-target="p-{idx}" data-flags="1" '
                f'data-triage-chapter="{p.chapter_num}" data-triage-severity="{p.severity}" '
                f'data-review-sha="{paragraph_identity(p)["paragraph_sha256"]}" '
                f'title="{esc(label(labels, "click_hint_para"), quote=True)}">'
                f'<td><span class="badge sev-{p.severity}">'
                f"{esc(label(labels, f'severity_{p.severity}'))}</span></td>"
                f"<td>{chapter_cell}</td>"
                f'<td class="num">{esc(line_label(labels, p))}</td>'
                f'<td class="flag-excerpt">{esc(excerpt)}'
                f'<details class="triage-reason"><summary>{L("triage_why")}</summary>'
                f'<p>{esc(label(labels, "triage_reason").format(present=p.present_hits, past=p.past_hits, mixed=L("research_value_yes" if p.mixed else "research_value_no"), switch=L("research_value_yes" if p.switch else "research_value_no")))}</p>'
                '</details></td>'
            )
            parts.append(f'<td class="triage-read-cell"><button type="button" class="ctl" data-line="{p.start_line}" '
                         f'data-target="p-{idx}" data-flags="1">{L("triage_read")}</button></td>')
            if review_capable:
                parts.append(
                    f'<td class="triage-decision-cell"><span class="ctl-note triage-saved-state">{L("triage_loading")}</span>'
                    f'<select class="ctl triage-choice" disabled aria-label="{L("triage_status")}">'
                    f'<option value="">{L("triage_choose")}</option>'
                    + "".join(f'<option value="{status}">{L("triage_" + status)}</option>'
                              for status in ("kept", "changed", "later"))
                    + f'</select><button type="button" class="ctl" data-triage-save disabled>{L("triage_save")}</button></td>'
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
            (
                "heatmap",
                "style_fingerprint",
                render_heatmap_panel(fingerprint, metrics, labels, language_key, characters=characters),
            ),
            (
                "bands",
                "style_passport",
                render_style_passport_panel(fingerprint, labels, language_key),
            ),
            (
                "dimensions",
                "style_dimensions",
                style_dimensions(chapters, fingerprint, labels, language_key),
            ),
            (
                "structural",
                "panel_structural",
                style_structural(chapters, fingerprint, labels, language_key),
            ),
        ]
        parts.append(
            f'<section class="panel style-panel" id="style">'
            f'<div class="style-header"><h2>{L("group_style")}</h2>'
            f'<div class="cohesion-summary-badge">'
            f'<span>{L("cockpit_cohesion_summary")}: <strong>{P(fingerprint.consistency * 100, 0)}</strong></span>'
            f'</div></div>'
        )
        parts.append(
            f'<div class="style-tabs" id="style-tabs" role="tablist" aria-label="{L("group_style")}" hidden>'
        )
        for view_id, label_key, content in style_views:
            if content:
                parts.append(
                    f'<button type="button" class="ctl" id="style-tab-{view_id}" role="tab" '
                    f'aria-controls="{view_id}" data-style-view="{view_id}">{L(label_key)}</button>'
                )
        parts.append('</div><div id="style-panels">')
        parts.extend(content for _, _, content in style_views if content)
        parts.append("</div></section>")
        parts.append(render_metric_context(fingerprint, metrics.chapters, labels, language_key))
    elif fingerprint is not None and metrics is not None and metrics.chapters:
        # Chapters exist, but none reaches the comparability floor: explain the
        # minimum instead of presenting an empty or misleading style reference.
        min_chapters = fingerprint.thresholds.min_chapters
        parts.append(f'<section class="panel" id="style"><h2>{L("group_style")}</h2>')
        parts.append(
            '<p class="ctl-note">'
            + L("style_unavailable_note")
            .replace("{min_chapters}", str(min_chapters))
            .replace("{min_words}", str(MIN_COMPARABLE_WORDS))
            + "</p>"
            + style_dimensions(chapters, fingerprint, labels, language_key)
            + "</section>"
        )

    # --- Work markers (editor-visible, set from the dashboard) -------
    parts.append(render_register_targets(fingerprint, metrics, labels, language_key, settings_available=can_edit))
    parts.append(render_markers_panel(markers, chapters, labels, can_edit))

    # --- Chapter matrix ---------------------------------------------------
    if chapters:
        parts.append(panel_start("matrix", labels, "chapter_table"))
        if has_house_style and fingerprint is not None and metrics is not None and metrics.chapters:
            parts.append(
                f'<div class="cockpit-toolbar">'
                f'<a href="#heatmap" class="ctl cockpit-switch" data-jump="#heatmap" '
                f'title="{L("cockpit_switch_heatmap")}">{L("cockpit_switch_heatmap")} →</a>'
                '</div>'
            )
        parts.append('<details class="analysis-coverage">'
                     f'<summary>{L("analysis_coverage")}</summary>'
                     f'<p>{L("analysis_chapter_coverage")}</p></details>')
        parts.append('<div class="table-wrap" tabindex="0" role="region" '
                     f'aria-label="{L("chapter_table")}">')
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
                elif any(z is not None for z in fingerprint.z_scores.get(c.num, {}).values()):
                    parts.append('<td class="num">0</td>')
                else:
                    parts.append('<td class="num">–</td>')
            parts.append("</tr>")
        parts.append("</tbody></table></div></section>")

    parts.append("</div>")  # closes manuscript-analysis-panels
    parts.append("</div>")  # closes analysis-outline-document
    parts.append(analysis_outline)
    parts.append("</div></div>")  # closes analysis-outline-layout and analysis-outline-folder
    if not has_reading:
        parts.append("</div>")

    if controls:
        if controls and has_reading:
            parts.append("</div></div></section>")
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

    if controls:
        parts.append(license_terms(labels))
    parts.extend(
        [
            "</div>",
            ("<footer></footer>" if controls else
             f"<footer><span>{esc(engine_name)}</span> · <span>{esc(title)}</span></footer>"),
            ('<script type="application/json" id="research-diagram-library">'
             + _script_json(_bundle(("vendor/mermaid-tiny-12.2.0.min.js",))) + "</script>" if controls else ""),
            f"<script>{_bundle(_JS_FILES)}</script>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts) + "\n"
