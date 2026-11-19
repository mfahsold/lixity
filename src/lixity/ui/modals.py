"""Reusable modal dialogs for the dashboard UI (project create, open, revision history)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ..language import LANGUAGE_CHOICES, LANGUAGE_PROFILES
from .components import checkbox_field, esc, help_term, label, modal_shell, panel_label, ui_icon


def _language_author_row(
    prefix: str,
    L: Callable[[str], str],
    labels: Mapping[str, str] | None,
    language_options_html: str,
) -> str:
    return (
        '<div class="form-row">'
        '<div class="grow">'
        f'<label for="{prefix}-proj-lang" class="form-label">{help_term(labels, "language", L("language"))}</label>'
        f'<select class="ctl full-width" id="{prefix}-proj-lang" required>'
        f'{language_options_html}'
        '</select>'
        f'<span class="ctl-note wizard-hint">{L("wizard_language_hint")}</span>'
        '</div>'
        '<div class="grow-2">'
        f'<label for="{prefix}-proj-author" class="form-label">{L("wizard_author")}</label>'
        f'<input class="ctl full-width" id="{prefix}-proj-author"/>'
        f'<span class="ctl-note wizard-hint">{L("wizard_author_hint")}</span>'
        '</div>'
        '</div>'
    )


def render_project_modals(
    labels: Mapping[str, str] | None = None,
    language_key: str = "generic",
    language_options: Sequence[Any] | None = None,
    *,
    current_language: str | None = None,
) -> str:
    """Renders the project wizard and research revision modal dialogs."""

    L = panel_label(labels)

    # Project creation cannot preserve `auto`: the server currently converts
    # it to English. Require an explicit supported choice instead of silently
    # selecting the first language when the current choice is unavailable.
    choices = language_options if language_options is not None else [
        (key, profile.name) for key, profile in LANGUAGE_PROFILES.items()
    ]
    project_languages = [(code, name) for code, name in choices if code in LANGUAGE_CHOICES and code != "auto"]
    configured = current_language if current_language is not None else language_key
    selected = configured if any(code == configured for code, _name in project_languages) else ""

    def project_language_options() -> str:
        placeholder = f'<option value="" disabled{" selected" if not selected else ""}>{L("wizard_choose_language")}</option>'
        return placeholder + "".join(
            f'<option value="{esc(code)}"{" selected" if code == selected else ""}>{esc(name)}</option>'
            for code, name in project_languages
        )

    close_lbl = label(labels, "modal_close")
    parts: list[str] = []
    parts.append(
        modal_shell(
            "modal-runtime",
            "runtime-title",
            L("runtime_title"),
            '<div class="modal-body"><p id="runtime-status" role="status" aria-live="polite"></p>'
            '<div id="runtime-content"></div>'
            f'<p class="ctl-note">{L("runtime_scope_note")}</p></div>',
            close_label=close_lbl,
            footer_html=(
                '<div class="modal-footer">'
                f'<button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_close")}</button>'
                f'<button type="button" class="ctl" id="runtime-refresh">{L("runtime_refresh")}</button>'
                '</div>'
            ),
        )
    )

    site_export_body: list[str] = [
        '<form id="site-export-form" class="modal-body" method="dialog">',
        f'<p class="ctl-note">{L("site_export_intro")}</p>',
        '<div class="form-group site-export-card">',
        f'<label class="form-label" for="site-export-mode">{L("publication_export_mode")}</label>',
        '<select class="ctl full-width" id="site-export-mode">',
        *(f'<option value="{mode}">{L("publication_export_" + mode)}</option>'
          for mode in ("review", "reader", "companion")),
        '</select>',
        '<p class="ctl-note" id="site-export-scope"></p>',
        '</div>',
        '<div id="site-export-publication-options" class="site-export-section site-export-card" hidden>',
        '<div class="form-group">',
        f'<label class="form-label" for="site-export-profile">{L("publication_export_profile")}</label>',
        '<div class="site-export-profile-row">',
        '<select class="ctl" id="site-export-profile" aria-describedby="site-export-profile-state"></select>',
        f'<button type="button" class="ctl" id="site-export-edit-profiles">{L("publication_export_edit_profiles")}</button>',
        '</div>',
        '<p class="ctl-note" id="site-export-profile-state" role="status" aria-live="polite"></p>',
        '<p class="ctl-note" id="site-export-profile-draft" hidden></p>',
        '</div>',
        '<div class="form-group">',
        f'<label class="form-label" for="site-export-max-chapter">{L("publication_export_cap")}</label>',
        '<select class="ctl full-width" id="site-export-max-chapter"></select>',
        f'<p class="ctl-note">{L("publication_export_cap_hint")}</p>',
        '</div>',
        f'<fieldset id="site-export-analysis-options" class="settings-section" hidden><legend>{L("publication_analysis_options")}</legend>',
        '<div class="site-export-analysis-choices">',
        *(checkbox_field(f'<input type="checkbox" id="site-export-analysis-{section}" value="{section}"/>',
                         L("publication_analysis_" + section))
          for section in ("chapters", "language", "full")),
        f'</div><p class="ctl-note">{L("publication_analysis_cap_note")}</p></fieldset>',
        '<div id="site-export-audio-option" hidden>',
        checkbox_field('<input type="checkbox" id="site-export-audio" aria-describedby="site-export-audio-help"/>', L("publication_audio_include")),
        f'<p class="ctl-note" id="site-export-audio-help">{L("publication_audio_export_help")}</p></div></div>',
        '<div class="site-export-includes site-export-card">',
        '<div id="site-export-research-option">',
        checkbox_field('<input type="checkbox" id="site-export-research"/>', L("site_export_research")),
        '</div>',
        checkbox_field('<input type="checkbox" id="site-export-sources" disabled/>', L("site_export_sources")),
        '</div>',
        '<div id="site-export-preflight" role="status" aria-live="polite" hidden></div>',
        '<p class="ctl-status" id="site-export-status" role="status" aria-live="polite"></p>',
        '</form>',
    ]
    parts.append(
        modal_shell(
            "modal-site-export",
            "site-export-title",
            L("site_export"),
            "".join(site_export_body),
            close_label=close_lbl,
            extra_attrs="data-requires-write",
            footer_html=(
                f'<div class="modal-footer"><button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_cancel")}</button>'
                f'<button type="submit" form="site-export-form" class="ctl" id="site-export-check">{L("site_export_check")}</button>'
                f'<button type="submit" form="site-export-form" class="ctl primary" id="site-export-download">{L("site_export_download")}</button></div>'
            ),
        )
    )

    # Modal: New Project (with Import & From-Scratch Tabs)
    lang_options_html = project_language_options()
    create_body = [
        '    <div class="modal-tabs" role="tablist" aria-labelledby="modal-create-title">',
        f'      <button type="button" class="modal-tab-btn active" role="tab" id="tab-btn-import" aria-controls="tab-pane-import" aria-selected="true" data-tab-target="tab-pane-import">{L("wizard_import_tab")}</button>',
        f'      <button type="button" class="modal-tab-btn" role="tab" id="tab-btn-scratch" aria-controls="tab-pane-scratch" aria-selected="false" data-tab-target="tab-pane-scratch">{L("wizard_scratch_tab")}</button>',
        '    </div>',
        f'    <p class="ctl-note modal-intro">{L("wizard_intro")}</p>',
        '    <div class="modal-tab-pane active" id="tab-pane-import" role="tabpanel" aria-labelledby="tab-btn-import">',
        '      <form id="form-project-import" class="modal-form" method="dialog">',
        '        <div class="modal-body">',
        '        <input type="file" id="import-file-input" accept=".md,.markdown,.txt,.docx" hidden />',
        f'        <button type="button" class="file-dropzone" id="import-dropzone" autofocus aria-label="{L("wizard_drop_aria")}">',
        f'          <span class="dropzone-icon">{ui_icon("file-up", size=34)}</span>',
        '          <span class="dropzone-text">',
        f'            <strong>{L("wizard_drop_main")}</strong>',
        f'            <span>{L("wizard_drop_sub")}</span>',
        '          </span>',
        '        </button>',
        '        <p class="ctl-status project-form-status" id="import-project-status" role="alert" aria-live="assertive" hidden></p>',
        '        <div class="file-preview-card" id="import-preview-box" hidden>',
        '          <div class="fpc-header">',
        f'            <span class="fpc-badge">{L("wizard_recognized")}</span>',
        '            <span class="fpc-filename" id="import-fpc-filename">manuscript.md</span>',
        '          </div>',
        '          <div class="fpc-meta">',
        f'            <div class="fpc-stat"><span class="fpc-label">{L("wizard_scope")}</span> <strong id="import-fpc-stats"></strong></div>',
        f'            <div class="fpc-stat"><span class="fpc-label">{L("wizard_analysis_language")}</span> <span id="import-fpc-lang"></span></div>',
        '          </div>',
        f'          <p class="ctl-note">{L("wizard_preview_estimate_hint")}</p>',
        '          <div class="fpc-loss" id="import-fpc-loss" hidden></div>',
        '        </div>',
        '        <div class="project-structure-hint">',
        f'          <span>{help_term(labels, "import_manuscript", L("wizard_import_layout"))}</span>',
        '        </div>',
        '        <div class="form-group">',
        f'          <label for="import-proj-title" class="form-label">{L("title")}</label>',
        f'          <input class="ctl full-width" id="import-proj-title" required placeholder="{L("wizard_import_title_hint")}"/>',
        '        </div>',
        _language_author_row("import", L, labels, lang_options_html),
        '<details class="research-details" id="import-project-options">',
        f'<summary>{L("optional_details")}</summary>',
        '          <div class="form-group">',
        f'            <label for="import-proj-path" class="form-label">{L("wizard_project_folder")}</label>',
        f'            <input class="ctl full-width" id="import-proj-path" placeholder="{L("wizard_auto_folder")}"/>',
        f'            <span class="ctl-note wizard-hint">{L("wizard_folder_note")}</span>',
        '          </div>',
        '        <div class="form-group">',
        checkbox_field('<input type="checkbox" id="import-proj-research"/>', f'<span>{L("wizard_enable_research")}</span>'),
        '        </div>',
        '</details>',
        '        </div>',
        '        <div class="modal-footer">',
        f'          <button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_cancel")}</button>',
        f'          <button type="submit" class="ctl primary" id="btn-submit-import-project" disabled>{L("wizard_import_action")}</button>',
        '        </div>',
        '      </form>',
        '    </div>',
        '    <div class="modal-tab-pane" id="tab-pane-scratch" role="tabpanel" aria-labelledby="tab-btn-scratch" hidden>',
        '      <form id="form-project-create" class="modal-form" method="dialog">',
        '        <div class="modal-body">',
        '        <div class="project-structure-hint">',
        f'          <span>{L("wizard_project_files")}</span>',
        '        </div>',
        '        <div class="form-group">',
        f'          <label for="new-proj-title" class="form-label">{L("title")}</label>',
        f'          <input class="ctl full-width" id="new-proj-title" required placeholder="{L("wizard_title_example")}"/>',
        '        </div>',
        _language_author_row("new", L, labels, lang_options_html),
        '        <div class="form-group">',
        f'          <span class="form-label">{L("wizard_template_heading")}</span>',
        '          <div class="template-grid">',
        '            <label class="template-card active">',
        '              <input type="radio" name="proj_template" value="minimal" checked/>',
        f'              <div class="tc-title">{L("wizard_minimal")}</div>',
        f'              <div class="tc-desc">{L("wizard_minimal_desc")}</div>',
        '            </label>',
        '            <label class="template-card">',
        '              <input type="radio" name="proj_template" value="three_act"/>',
        f'              <div class="tc-title">{L("wizard_three_act")}</div>',
        f'              <div class="tc-desc">{L("wizard_three_act_desc")}</div>',
        '            </label>',
        '            <label class="template-card">',
        '              <input type="radio" name="proj_template" value="research"/>',
        f'              <div class="tc-title">{L("wizard_research_template")}</div>',
        f'              <div class="tc-desc">{L("wizard_research_template_desc")}</div>',
        '            </label>',
        '          </div>',
        '        </div>',
        '        <div class="wizard-options-section">',
        '          <div class="form-group">',
        f'            <label for="new-proj-path" class="form-label">{L("wizard_target_folder")}</label>',
        f'            <input class="ctl full-width" id="new-proj-path" placeholder="{L("wizard_subfolder")}"/>',
        f'            <span class="ctl-note wizard-hint">{L("wizard_folder_note")}</span>',
        '          </div>',
        '          <div class="form-group">',
        checkbox_field('<input type="checkbox" id="new-proj-research"/>', f'<span>{L("wizard_enable_research")}</span>'),
        f'            <p class="ctl-note" id="new-proj-research-required" hidden>{L("wizard_research_required")}</p>',
        '          </div>',
        '        </div>',
        '        <p class="ctl-status project-form-status" id="new-project-status" role="alert" aria-live="assertive" hidden></p>',
        '        </div>',
        '        <div class="modal-footer">',
        f'          <button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_cancel")}</button>',
        f'          <button type="submit" class="ctl primary" id="btn-submit-create-project">{L("create_project")}</button>',
        '        </div>',
        '      </form>',
        '    </div>',
    ]
    parts.append(
        modal_shell(
            "modal-project-create",
            "modal-create-title",
            L("create_project"),
            "".join(create_body),
            close_label=close_lbl,
            extra_attrs="data-requires-write",
        )
    )

    # Modal: Open Project
    open_body = [
        '    <form id="form-project-open" class="modal-body" method="dialog">',
        '      <div class="form-group">',
        f'        <label for="open-proj-path" class="form-label">{L("wizard_open_path")}</label>',
        '        <div class="project-path-row">',
        f'          <button type="button" class="ctl" id="open-proj-choose" autofocus aria-controls="open-project-chooser" aria-expanded="false">{L("wizard_choose_action")}</button>',
        f'          <input class="ctl" id="open-proj-path" required placeholder="{L("wizard_open_placeholder")}"/>',
        '        </div>',
        f'        <p class="ctl-note">{L("wizard_open_note")}</p>',
        '      </div>',
        '      <div id="open-project-recent" class="recent-projects-panel" data-recent-projects hidden>',
        '        <div class="recent-projects-header">',
        f'          <span class="ctl-label recent-projects-heading">{L("recent_projects_heading")}</span>',
        f'          <button type="button" class="ctl-link recent-projects-clear" data-clear-recent-projects>{L("clear_recent_projects")}</button>',
        '        </div>',
        '        <ul class="recent-projects-list" id="open-project-recent-list" data-recent-project-list></ul>',
        '        <p class="ctl-status" data-recent-project-status role="status" hidden></p>',
        '      </div>',
        '      <div class="project-chooser" id="open-project-chooser" role="region" aria-labelledby="open-project-chooser-heading" hidden>',
        '        <div class="project-chooser-heading">',
        f'          <strong id="open-project-chooser-heading">{L("wizard_choose_heading")}</strong>',
        f'          <button type="button" class="ctl" id="open-project-chooser-close" aria-label="{L("modal_close")}">✕</button>',
        '        </div>',
        f'        <p class="ctl-note">{L("wizard_choose_location")}</p>',
        f'        <p class="ctl-note project-chooser-current">{L("wizard_choose_current")} <code id="open-project-chooser-path"></code></p>',
        f'        <p class="ctl-note project-chooser-project" id="open-project-chooser-project" data-empty="{esc(L("chooser_project_none"), quote=True)}" role="status"></p>',
        '        <div class="project-chooser-toolbar">',
        f'          <button type="button" class="ctl" id="open-project-chooser-home">{L("wizard_choose_home")}</button>',
        f'          <button type="button" class="ctl" id="open-project-chooser-parent" disabled>{L("wizard_choose_parent")}</button>',
        f'          <button type="button" class="ctl primary" id="open-project-chooser-select-folder" disabled>{L("wizard_choose_folder")}</button>',
        '        </div>',
        '        <p class="ctl-note" id="open-project-chooser-status" role="status" aria-live="polite"></p>',
        '        <ul class="project-chooser-list" id="open-project-chooser-list" aria-label="' + L("wizard_choose_entries") + '"></ul>',
        '      </div>',
        '      <div class="project-structure-hint mt-2">',
        f'        <span>{L("wizard_switch_prompt")} <button type="button" class="ctl-link" id="link-switch-to-import">{L("wizard_switch_action")}</button></span>',
        '      </div>',
        '      <p class="ctl-status project-form-status" id="open-project-status" role="alert" aria-live="assertive" hidden></p>',
        '    </form>',
    ]
    parts.append(
        modal_shell(
            "modal-project-open",
            "modal-open-title",
            help_term(labels, "open_existing", L("open_project")),
            "".join(open_body),
            close_label=close_lbl,
            extra_attrs="data-requires-write",
            footer_html=(
                '    <div class="modal-footer">'
                f'      <button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_cancel")}</button>'
                f'      <button type="submit" form="form-project-open" class="ctl primary" id="btn-submit-open-project">{L("open")}</button>'
                '    </div>'
            ),
        )
    )

    # One editor and history view for all authored research record kinds.
    revision_body = [
        '    <div class="modal-scroll">',
        '    <div class="modal-tabs" role="tablist" aria-labelledby="research-revision-title">',
        f'      <button type="button" class="modal-tab-btn active" role="tab" id="research-revision-history-tab" aria-controls="research-revision-history" aria-selected="true" tabindex="0">{L("research_revision_entry")}</button>',
        f'      <button type="button" class="modal-tab-btn" role="tab" id="research-revision-edit-tab" data-requires-write aria-controls="research-revision-form" aria-selected="false" tabindex="-1">{L("research_revision_edit")}</button>',
        '    </div>',
        '    <p class="ctl-note research-revision-meta" id="research-revision-kind"></p>',
        '    <div class="research-revision-updates" id="research-revision-source-updates" role="status" aria-live="polite" hidden></div>',
        '    <form id="research-revision-form" data-requires-write class="modal-body" method="dialog" role="tabpanel" aria-labelledby="research-revision-edit-tab" novalidate hidden>',
        '      <section id="research-revision-merge" class="form-group" aria-labelledby="research-revision-merge-title" hidden>',
        f'        <h4 id="research-revision-merge-title">{L("research_revision_merge_title")}</h4>',
        f'        <p class="ctl-note">{L("research_revision_merge_help")}</p>',
        '        <div id="research-revision-merge-fields"></div>',
        f'        <button type="button" class="ctl" id="research-revision-merge-apply">{L("research_revision_merge_apply")}</button>',
        '      </section>',
        '      <div id="research-revision-fields" class="research-revision-fields"></div>',
        f'      <p class="ctl-note">{L("research_revision_link_help")}</p>',
        '      <fieldset class="research-revision-choice">',
        f'        <legend class="form-label">{L("research_revision_type")}</legend>',
        f'        <label><input type="radio" name="research_revision_change_kind" value="correction" required/> <span><strong>{L("research_revision_correction")}</strong><small>{L("research_revision_correction_desc")}</small></span></label>',
        f'        <label><input type="radio" name="research_revision_change_kind" value="supersession"/> <span><strong>{L("research_revision_supersession")}</strong><small>{L("research_revision_supersession_desc")}</small></span></label>',
        '      </fieldset>',
        f'      <label for="research-revision-reason" class="form-label">{L("research_revision_reason")}</label>',
        '<textarea class="ctl" id="research-revision-reason" rows="2" maxlength="2000" required></textarea>',
        '      <details class="research-details" id="research-revision-citations-wrap" hidden>',
        f'        <summary>{L("research_citations")}</summary>',
        '        <div class="research-details-body" id="research-revision-citations"></div>',
        '      </details>',
        '    </form>',
        '    <p class="ctl-status" id="research-revision-status" role="alert" aria-live="assertive" hidden></p>',
        '    <div id="research-revision-history" class="modal-body research-revision-history" role="tabpanel" aria-labelledby="research-revision-history-tab">',
        '      <div id="research-revision-history-detail"></div>',
        '      <details class="research-details" id="research-revision-versions">',
        f'        <summary>{L("research_revision_history")}</summary>',
        '        <ol id="research-revision-history-list" class="research-revision-history-list"></ol>',
        '      </details>',
        '    </div>',
        '    </div>',
    ]
    parts.append(
        modal_shell(
            "modal-research-revision",
            "research-revision-title",
            L("research_revision_title"),
            "".join(revision_body),
            close_label=close_lbl,
            footer_html=(
                '      <div class="modal-footer" id="research-revision-actions">'
                f'        <button type="button" class="ctl" id="research-revision-reload" hidden>{L("research_revision_reload")}</button>'
                f'        <button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("modal_cancel")}</button>'
                f'        <button type="button" class="ctl" id="research-revision-batch-add">{L("research_revision_batch_add")}</button>'
                f'        <button type="submit" form="research-revision-form" class="ctl primary" id="research-revision-save">{L("research_revision_save")}</button>'
                '      </div>'
            ),
        )
    )

    parts.append(
        modal_shell(
            "modal-research-revision-batch",
            "research-revision-batch-title",
            L("research_revision_batch_title"),
            '    <div class="modal-body">'
            f'      <p class="ctl-note">{L("research_revision_batch_help")}</p>'
            '      <ol id="research-revision-batch-list"></ol>'
            '      <p class="ctl-status" id="research-revision-batch-status" role="status" aria-live="polite" hidden></p>'
            '    </div>',
            close_label=close_lbl,
            extra_attrs="data-requires-write",
            footer_html=(
                '    <div class="modal-footer">'
                f'      <button type="button" class="ctl" id="research-revision-batch-clear">{L("research_revision_batch_clear")}</button>'
                f'      <button type="button" class="ctl" data-close-modal aria-keyshortcuts="Escape">{L("research_revision_batch_close")}</button>'
                f'      <button type="button" class="ctl" id="research-revision-batch-check">{L("research_revision_batch_check")}</button>'
                f'      <button type="button" class="ctl primary" id="research-revision-batch-apply" disabled>{L("research_revision_batch_apply")}</button>'
                '    </div>'
            ),
        )
    )

    return "".join(parts)
