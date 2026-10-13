"""Reusable research manager panel (sources, search, dossiers, claims, decisions, grounding)."""

from __future__ import annotations

from collections.abc import Mapping

from .components import esc, help_term, label, loading_state


def render_research_panel(labels: Mapping[str, str] | None = None, *, research_context_token: str = "") -> str:
    """Renders the local research archive panel and its tab panes."""

    def L(key: str) -> str:
        return esc(label(labels, key))

    def form_field(identifier: str, key: str, control: str) -> str:
        return ('<div class="setting-field research-form-field">'
                f'<label class="form-label" for="{identifier}">{L(key)}</label>'
                + control + '</div>')

    parts: list[str] = [f'<section class="panel controls" id="research-manager" data-research-token="{esc(research_context_token)}">']
    parts.append(f"<h2>{L('research_panel')}</h2>")
    parts.append('<div class="row form-row-between m-0">')
    parts.append(f'<p class="ctl-note m-0" id="research-hint">{L("research_hint")}</p>')
    parts.append(f'<span class="ctl-status loading fw-medium" id="r-active-root">{L("research_loading")}</span>')
    parts.append('</div>')

    parts.append('<details class="settings-advanced" id="research-setup-guide">')
    parts.append(f'<summary>{L("setup_title")}</summary><div class="ctl-group">')
    parts.append(f'<p class="ctl-note">{L("setup_intro")}</p>')
    parts.append(f'<button type="button" class="ctl" id="research-setup-check">{L("setup_check")}</button>')
    parts.append(f'<p id="setup-ocr-reading" class="ctl-note" aria-live="polite">OCR: {L("setup_not_checked")}</p>')
    parts.append(f'<p id="setup-zotero-reading" class="ctl-note" aria-live="polite">Zotero: {L("setup_not_checked")}</p>')
    # The steps are grouped so a successful check can hide the guidance for the
    # component it just found working. Leaving it visible next to "reachable"
    # read as if the check had failed.
    parts.append('<div id="setup-zotero-steps">')
    parts.append(f'<h3 class="section-heading">Zotero</h3><p class="ctl-note">{L("setup_zotero_steps")}</p>')
    parts.append('<p><a class="ctl-link" href="https://www.zotero.org/support/" target="_blank" rel="noopener">Zotero</a></p>')
    parts.append("</div>")
    parts.append('<div id="setup-ocr-steps">')
    parts.append(f'<h3 class="section-heading">OCR</h3><p class="ctl-note">{L("setup_ocr_steps")}</p>')
    parts.append('<p><a class="ctl-link" href="https://tesseract-ocr.github.io/tessdoc/Installation.html" target="_blank" rel="noopener">Tesseract</a> · '
                 '<a class="ctl-link" href="https://mfahsold.github.io/lixity/INSTALLATION.md#server-environment-and-project-access" target="_blank" rel="noopener">Poppler</a></p>')
    parts.append("</div>")
    parts.append(f'<p class="ctl-note">{L("setup_language_example")}</p>')
    parts.append('<pre class="research-dossier-body-source">LIXITY_OCR_BACKEND=tesseract\nLIXITY_OCR_LANGUAGES=deu+eng</pre>')
    parts.append(f'<p class="ctl-note">{L("setup_restart")}</p>')
    parts.append(f'<p class="ctl-note">{L("setup_large_scans")}</p>')
    parts.append(f'<details><summary>{L("setup_advanced")}</summary><pre class="research-dossier-body-source" id="setup-diagnostics"></pre></details>')
    parts.append('</div></details>')

    parts.append(f'<button type="button" class="ctl" id="research-revision-batch-review" hidden>{L("research_revision_batch_review")}</button>')
    parts.append('<div class="row research-tabs" id="research-tabs" role="tablist">')
    parts.append(f'<button type="button" class="ctl active" data-rtab="sources" role="tab" aria-selected="true">{L("research_tab_sources")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="search" role="tab" aria-selected="false">{L("research_tab_search")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="dossiers" role="tab" aria-selected="false">{L("research_tab_dossiers")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="claims" role="tab" aria-selected="false">{L("research_tab_claims")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="timeline" role="tab" aria-selected="false">{L("research_claim_timeline")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="decisions" role="tab" aria-selected="false">{L("research_tab_decisions")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="review" role="tab" aria-selected="false">{L("research_tab_review")}</button>')
    parts.append(f'<button type="button" class="ctl" data-rtab="grounding" role="tab" aria-selected="false">{L("research_tab_grounding")}</button>')
    parts.append('</div>')

    parts.append('<div id="research-init-box" class="ctl-group" style="display:none;">')
    parts.append(f'<span class="ctl-label">{help_term(labels, "research_init", L("research_not_initialized"))}</span>')
    parts.append(f'<p class="ctl-note">{L("research_init_note")}</p>')
    parts.append('<div class="row">')
    parts.append(f'<input class="ctl" id="r-init-title" placeholder="{L("research_project_title")}"/>')
    parts.append(f'<button class="ctl primary" id="r-init-btn">{L("research_init_action")}</button>')
    parts.append('</div>')
    parts.append('</div>')

    parts.append('<div class="research-tab-pane" id="rtab-sources">')
    parts.append('<div id="r-local-import">')

    parts.append('<div class="ctl-group">')
    parts.append(f'<h3 class="section-heading">{help_term(labels, "research_ingest", L("research_ingest_heading"))}</h3>')
    parts.append('<div class="row mb-5">')
    parts.append('<input class="ctl" type="file" id="r-ingest-file" accept=".txt,.md,.text,.pdf"/>')
    parts.append('</div>')
    parts.append('<details class="research-details" id="r-ingest-options">')
    parts.append(f'<summary>{L("optional_details")}</summary><div class="row">')
    parts.append(f'<input class="ctl field-narrow" id="r-ingest-title" placeholder="{L("research_source_title")}"/>')
    parts.append(f'<input class="ctl field-narrow" id="r-ingest-tags" placeholder="{L("research_tags_example")}"/>')
    parts.append('</div>')
    parts.append(f'<label for="r-ingest-origin-url">{L("ctx_origin_url")}</label>')
    parts.append('<input class="ctl w-full my-3" type="url" id="r-ingest-origin-url" maxlength="2000" aria-describedby="r-ingest-origin-help" placeholder="https://example.org/source"/>')
    parts.append(f'<p class="ctl-note" id="r-ingest-origin-help">{L("research_origin_url_help")}</p>')
    parts.append('</details>')
    parts.append('<div class="row mb-5" id="r-ocr-diagnostic-box" style="display:none;"></div>')
    parts.append('<div class="row mb-5">')
    parts.append(f'<textarea class="ctl w-full" id="r-ingest-text" placeholder="{L("research_source_text")}" rows="3"></textarea>')
    parts.append('</div>')
    parts.append('<div class="row items-center">')
    parts.append(f'<label class="form-checkbox"><input type="checkbox" id="r-ingest-retention" data-help="{L("help_research_ingest")}"/> <span>{L("research_retention")}</span></label>')
    parts.append(f'<button class="ctl primary" id="r-ingest-btn">{L("research_ingest_action")}</button>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('<div class="ctl-group mt-10" id="zotero-box">')
    parts.append('<h3 class="section-heading">Zotero</h3>')
    parts.append(f'<p class="ctl-note">{L("zotero_intro")}</p>')
    parts.append('<div class="row">')
    parts.append(f'<label for="r-zotero-library">{L("zotero_library")}</label>')
    parts.append('<input class="ctl" id="r-zotero-library" value="users/0" placeholder="users/0"/>')
    parts.append(f'<button type="button" class="ctl" id="r-zotero-collections">{L("zotero_collections")}</button>')
    parts.append(f'<select class="ctl" id="r-zotero-collection" aria-label="{L("zotero_all")}"><option value="">{L("zotero_all")}</option></select>')
    parts.append('</div><div class="row">')
    parts.append(f'<input class="ctl grow" id="r-zotero-query" aria-label="{L("research_search_query")}" placeholder="{L("research_search_query")}"/>')
    parts.append(f'<button type="button" class="ctl primary" id="r-zotero-browse">{L("zotero_browse")}</button>')
    parts.append('</div>')
    parts.append(f'<label><input type="checkbox" id="r-zotero-retention"/> {L("research_retention_zotero")}</label>')
    parts.append('<div id="r-zotero-results" aria-live="polite"></div></div>')
    parts.append(f'<h3 class="section-heading">{L("zotero_retained")}</h3>')
    parts.append(f'<input class="ctl w-full mb-5" type="search" id="r-filter-sources" aria-label="{L("research_filter_sources")}" placeholder="{L("research_filter_sources")}"/>')
    parts.append('<p class="ctl-note" id="r-filter-sources-status" aria-live="polite" hidden></p>')
    parts.append(f'<div id="research-sources-list">{loading_state(label(labels, "research_loading"))}</div>')
    parts.append('</div>')

    parts.append('<div class="research-tab-pane" id="rtab-search" style="display:none;">')
    parts.append('<div class="ctl-group">')
    parts.append(f'<span class="ctl-label">{help_term(labels, "research_search", L("research_search_heading"))}</span>')
    parts.append('<div class="row">')
    parts.append(f'<input class="ctl" id="r-search-query" placeholder="{L("research_search_query")}"/>')
    parts.append(f'<select class="ctl" id="r-search-scope" aria-label="{L("research_search_scope")}">')
    for scope, scope_label in (("all", "research_search_all"), ("sources", "research_tab_sources"),
                         ("dossiers", "research_tab_dossiers"), ("claims", "research_tab_claims"),
                         ("decisions", "research_tab_decisions")):
        parts.append(f'<option value="{scope}">{L(scope_label)}</option>')
    parts.append('</select>')
    parts.append(f'<button class="ctl primary" id="r-search-btn">{L("research_search_action")}</button>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('<div id="research-search-results"></div>')
    parts.append('</div>')

    parts.append('<div class="research-tab-pane" id="rtab-dossiers" style="display:none;">')
    parts.append('<div class="ctl-group">')
    parts.append(f'<span class="ctl-label">{help_term(labels, "research_dossier", L("research_dossier_heading"))}</span>')
    parts.append('<div class="row mb-5">')
    parts.append(form_field("r-dos-title", "research_dossier_title",
                 f'<input class="ctl" id="r-dos-title" placeholder="{L("research_dossier_title")}"/>'))
    parts.append('</div>')
    parts.append('<details class="research-details" id="r-dos-options">')
    parts.append(f'<summary>{L("optional_details")}</summary><div class="row">')
    parts.append(form_field("r-dos-tags", "research_tags",
                 f'<input class="ctl" id="r-dos-tags" placeholder="{L("research_tags")}"/>'))
    parts.append(form_field("r-dos-eids", "research_evidence_ids",
                 f'<input class="ctl" id="r-dos-eids" data-help="{L("help_research_passage")}" placeholder="{L("research_evidence_ids")}"/>'))
    parts.append('</div></details>')
    parts.append('<div class="row mb-5">')
    parts.append(form_field("r-dos-body", "research_dossier_body",
                 f'<textarea class="ctl" id="r-dos-body" placeholder="{L("research_dossier_body")}" rows="4"></textarea>'))
    parts.append('</div>')
    parts.append('<div class="row">')
    parts.append(f'<button class="ctl primary" id="r-dos-create-btn">{L("research_dossier_action")}</button>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append(f'<input class="ctl w-full mb-5" type="search" id="r-filter-dossiers" aria-label="{L("research_filter_dossiers")}" placeholder="{L("research_filter_dossiers")}"/>')
    parts.append('<p class="ctl-note" id="r-filter-dossiers-status" aria-live="polite" hidden></p>')
    parts.append(f'<div id="research-dossiers-list">{loading_state(label(labels, "research_loading"))}</div>')
    parts.append('</div>')

    # Tab Pane: Claims & Evidence Links
    parts.append('<div class="research-tab-pane" id="rtab-claims" style="display:none;">')
    parts.append('  <div class="ctl-group">')
    parts.append(f'    <span class="ctl-label">{help_term(labels, "research_claim", L("research_claim_heading"))}</span>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-claim-title", "research_claim_title",
                 f'<input class="ctl" id="r-claim-title" placeholder="{L("research_claim_title")}"/>'))
    parts.append(form_field("r-claim-confidence", "research_confidence_field",
                 f'<select class="ctl" id="r-claim-confidence" aria-label="{L("research_confidence_field")}" data-help="{L("help_research_confidence")}">'
                 f'<option value="hypothetical">{L("research_confidence_hypothetical")}</option>'
                 f'<option value="evidenced">{L("research_confidence_evidenced")}</option>'
                 f'<option value="disputed">{L("research_confidence_disputed")}</option></select>'))
    parts.append('    </div>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-claim-statement", "research_claim_statement",
                 f'<textarea class="ctl" id="r-claim-statement" placeholder="{L("research_claim_statement")}" rows="3"></textarea>'))
    parts.append('    </div>')
    parts.append('<details class="research-details" id="r-claim-options">')
    parts.append(f'<summary>{L("optional_details")}</summary><div class="row">')
    parts.append(form_field("r-claim-tags", "research_tags",
                 f'<input class="ctl" id="r-claim-tags" placeholder="{L("research_tags")}"/>'))
    parts.append(form_field("r-claim-dossier-select", "research_dossier",
                 f'<select class="ctl" id="r-claim-dossier-select"><option value="">{L("research_no_dossier")}</option></select>'))
    parts.append('</div>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-claim-time", "research_claim_time",
                 f'<input class="ctl" id="r-claim-time" placeholder="{L("research_claim_time")}"/>'
                 f'<span class="ctl-note">{L("research_claim_time_hint")}</span>'))
    parts.append(form_field("r-claim-place", "research_claim_place",
                 f'<input class="ctl" id="r-claim-place" placeholder="{L("research_claim_place")}"/>'))
    parts.append(form_field("r-claim-actors", "research_claim_actors",
                 f'<input class="ctl" id="r-claim-actors" placeholder="{L("research_claim_actors")}"/>'))
    parts.append('    </div>')
    parts.append('</details>')
    parts.append('    <div class="row">')
    parts.append(f'      <button class="ctl primary" id="r-claim-create-btn">{L("research_claim_action")}</button>')
    parts.append(f'      <button type="button" class="ctl secondary" id="r-claim-matrix-btn">{L("research_export_matrix")}</button>')
    parts.append('    </div>')
    parts.append('  </div>')
    parts.append('  <div class="ctl-group mt-8">')
    parts.append(f'    <span class="ctl-label">{help_term(labels, "research_evidence", L("research_link_heading"))}</span>')
    parts.append(f'<button type="button" class="ctl" id="r-find-passage">{L("research_find_passage")}</button>')
    parts.append('    <div class="row mb-5">')
    parts.append(f'      <select class="ctl field-wide" id="r-link-claim-select" aria-label="{L("research_select_claim")}"><option value="">{L("research_select_claim")}</option></select>')
    parts.append(f'      <input class="ctl ctl-code field-wide" id="r-link-passage-id" aria-label="{L("research_passage_id")}" data-help="{L("help_research_passage")}" placeholder="{L("research_passage_id")}"/>')
    parts.append(f'      <select class="ctl" id="r-link-relation" aria-label="{L("research_relation_field")}" data-help="{L("help_research_relation")}">')
    parts.append(f'        <option value="supports">{L("research_relation_supports")}</option>')
    parts.append(f'        <option value="contradicts">{L("research_relation_contradicts")}</option>')
    parts.append(f'        <option value="qualifies">{L("research_relation_qualifies")}</option>')
    parts.append(f'        <option value="contextualizes">{L("research_relation_contextualizes")}</option>')
    parts.append('      </select>')
    parts.append('    </div>')
    parts.append('    <div class="row mb-5">')
    parts.append(f'      <input class="ctl form-col" id="r-link-rationale" placeholder="{L("research_link_rationale")}"/>')
    parts.append(f'      <button class="ctl primary" id="r-link-evidence-btn">{L("research_link_action")}</button>')
    parts.append('    </div>')
    parts.append('  </div>')
    parts.append('<div class="ctl-group research-timeline-entry">')
    parts.append('<p class="ctl-note" id="r-timeline-callout" hidden></p>')
    parts.append(f'<button type="button" class="ctl" id="r-open-timeline">{L("research_timeline_open")}</button>')
    parts.append('</div>')
    parts.append(f'  <div id="research-claims-list">{loading_state(label(labels, "research_loading"))}</div>')
    parts.append('<div class="ctl-group research-relation-section">')
    parts.append(f'<h3>{L("research_relation_heading")}</h3><p class="ctl-note">{L("research_relation_hint")}</p>')
    parts.append('<form id="r-relation-form">')
    parts.append('<div class="research-relation-fields">')
    for role in ("from", "to"):
        parts.append(f'<div><label for="r-relation-{role}">{L("research_relation_" + role)}</label>')
        parts.append(f'<select class="ctl" id="r-relation-{role}" required><option value="">{L("research_select_claim")}</option></select></div>')
    parts.append('</div>')
    parts.append(f'<label for="r-relation-rationale">{L("research_link_rationale")}</label>')
    parts.append('<textarea class="ctl" id="r-relation-rationale" rows="2"></textarea>')
    parts.append(f'<p class="ctl-note" id="r-relation-compatibility">{L("research_relation_compatibility")}</p>')
    parts.append(f'<button type="submit" class="ctl primary" id="r-relation-save" disabled>{L("research_relation_save")}</button>')
    parts.append('<p class="ctl-note" id="r-relation-status" role="status"></p></form>')
    parts.append(f'<label class="form-checkbox"><input type="checkbox" id="r-relation-retracted"/> {L("research_relation_show_retracted")}</label>')
    parts.append('<div id="research-claim-relations" aria-live="polite"></div></div>')
    parts.append('</div>')

    # Tab Pane: Timeline
    parts.append('<div class="research-tab-pane" id="rtab-timeline" style="display:none;">')
    parts.append(f'<div id="research-claims-timeline" aria-live="polite">{loading_state(label(labels, "research_loading"))}</div>')
    parts.append('</div>')

    # Tab Pane: Decisions
    parts.append('<div class="research-tab-pane" id="rtab-decisions" style="display:none;">')
    parts.append('  <div class="ctl-group">')
    parts.append(f'    <span class="ctl-label">{help_term(labels, "research_decision", L("research_decision_heading"))}</span>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-decision-title", "research_decision_title",
                 f'<input class="ctl" id="r-decision-title" placeholder="{L("research_decision_title")}"/>'))
    parts.append('    </div>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-decision-rationale", "research_decision_rationale",
                 f'<textarea class="ctl" id="r-decision-rationale" placeholder="{L("research_decision_rationale")}" rows="3"></textarea>'))
    parts.append('    </div>')
    parts.append('<details class="research-details" id="r-decision-options">')
    parts.append(f'<summary>{L("optional_details")}</summary><div class="row">')
    parts.append(form_field("r-decision-claim-select", "research_decision_claim",
                 f'<select class="ctl" id="r-decision-claim-select"><option value="">{L("research_no_claim_linked")}</option></select>'))
    parts.append(form_field("r-decision-dossier-select", "research_dossier",
                 f'<select class="ctl" id="r-decision-dossier-select"><option value="">{L("research_no_dossier")}</option></select>'))
    parts.append('</div>')
    parts.append('    <div class="row mb-5">')
    parts.append(form_field("r-decision-plot", "research_decision_plot",
                 f'<input class="ctl" id="r-decision-plot" placeholder="{L("research_decision_plot")}"/>'))
    parts.append('    </div>')
    parts.append('    <div class="row form-row-between">')
    parts.append('      <label class="form-checkbox">')
    parts.append('        <input type="checkbox" id="r-decision-deviation"/>')
    parts.append(f'        <span>{help_term(labels, "research_deviation", L("research_deviation_checkbox"))}</span>')
    parts.append('      </label>')
    parts.append('</div></details>')
    parts.append('<div class="row">')
    parts.append(f'      <button class="ctl primary" id="r-decision-create-btn">{L("research_decision_action")}</button>')
    parts.append('    </div>')
    parts.append('  </div>')
    parts.append(f'  <div id="research-decisions-list">{loading_state(label(labels, "research_loading"))}</div>')
    parts.append('</div>')

    parts.append('<div class="research-tab-pane" id="rtab-review" style="display:none;">')
    parts.append(f'<h3 class="section-heading">{L("research_editorial_heading")}</h3>')
    parts.append(f'<p class="ctl-note">{L("research_editorial_help")}</p>')
    parts.append(f'<button type="button" class="ctl" id="r-review-refresh">{L("research_editorial_refresh")}</button>')
    parts.append('<div id="research-editorial-review" aria-live="polite"></div>')
    parts.append('</div>')

    parts.append('<div class="research-tab-pane" id="rtab-grounding" style="display:none;">')
    parts.append('<div class="ctl-group">')
    parts.append(f'<span class="ctl-label">{help_term(labels, "research_comparison", L("research_ground_heading"))}</span>')
    parts.append('<div class="row">')
    parts.append(f'<select class="ctl field-wide" id="r-ground-source-select" aria-label="{L("research_select_source")}"><option value="">{L("research_select_source")}</option></select>')
    parts.append(f'<button class="ctl primary" id="r-ground-btn">{L("research_ground_action")}</button>')
    parts.append('</div>')
    parts.append('</div>')
    parts.append('<div id="research-grounding-results"></div>')
    parts.append('</div>')

    parts.append('<div class="ctl-status" id="research-status-bar" role="status" aria-live="polite"></div>')
    parts.append("</section>")

    return "".join(parts)
