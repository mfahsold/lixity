"""Shared, accessible settings form with locale-independent HTML values."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ..config import MAX_AUTHOR_NAME_CHARS, MAX_PROJECT_TITLE_CHARS
from ..publication import PUBLICATION_FIELDS
from ..site import docs_url
from ..style_fingerprint import FEATURE_UNITS, FEATURES, FingerprintThresholds
from .components import checkbox_field, esc, help_term, label


def settings_form(
    labels: Mapping[str, str] | None,
    title: str,
    current_language: str,
    language_options: Sequence[Any],
    thresholds: FingerprintThresholds,
    *,
    project_author: str = "",
    identity_check: Mapping[str, Any] | None = None,
    author_setting_enabled: bool = False,
    publication: Mapping[str, Any] | None = None,
    publication_error: str = "",
    project_token: str = "",
    register_settings: Mapping[str, Any] | None = None,
    site_publications: Mapping[str, Any] | None = None,
    site_publication_context_token: str = "",
    language_key: str | None = None,
) -> str:
    def translated(key: str) -> str:
        return esc(label(labels, key))

    defaults = FingerprintThresholds()
    publication_values: dict[str, str | bool] = {"enabled": (publication or {}).get("enabled") is True}
    publication_values.update({field.key: value if isinstance(value, str) else ""
                              for field in PUBLICATION_FIELDS
                              for value in [(publication or {}).get(field.key, "")]})
    initial_publication = esc(json.dumps(publication_values, ensure_ascii=False, sort_keys=True))
    project_save_hint = (f'<p class="ctl-note" id="settings-project-save-help">{translated("settings_project_save_hint")}</p>'
                         if author_setting_enabled else "")
    parts = [
        f'<form id="settings-form" class="settings-form ctl-group" novalidate '
        f'data-project-token="{esc(project_token)}" data-publication-initial="{initial_publication}" '
        f'data-publication-editable="{str(author_setting_enabled).lower()}" '
        f'data-title-initial="{esc(title)}" data-author-initial="{esc(project_author)}">',
        f'<h3>{translated("settings")}</h3>',
        f'<p class="panel-guide" id="settings-scope-help">{translated("settings_intro")}</p>',
        '<fieldset class="settings-section" id="settings-project-details">',
        f'<legend>{translated("settings_project_details")}</legend>',
        project_save_hint,
        '<div class="settings-grid">',
        f'<div class="setting-field"><label for="set-title">{translated("title")}</label>',
        f'<input class="ctl" id="set-title" maxlength="{MAX_PROJECT_TITLE_CHARS}" value="{esc(title)}" '
        f'aria-describedby="set-title-help"/>',
        f'<p id="set-title-help">{translated("settings_title_hint")}</p></div>',
        f'<div class="setting-field"><label for="set-author-name">{translated("project_author_name")}</label>',
        f'<input class="ctl" id="set-author-name" value="{esc(project_author)}" '
        f'maxlength="{MAX_AUTHOR_NAME_CHARS}" aria-describedby="set-author-name-help" '
        f'data-author-setting-enabled="{str(author_setting_enabled).lower()}"'
        f'{" disabled" if not author_setting_enabled else ""}/>',
        f'<p id="set-author-name-help">{translated("project_author_hint" if author_setting_enabled else "project_author_unavailable")}</p></div></div>',
    ]
    if identity_check is not None:
        parts.extend([
            '<details class="settings-advanced" id="settings-identity">',
            f'<summary id="project-identity-title">{translated("project_identity_title")}</summary>',
            '<section id="project-identity-check" aria-labelledby="project-identity-title">',
            f'<p class="ctl-note">{translated("project_identity_hint")}</p>',
            '<dl class="research-revision-readonly">',
        ])
        statuses = {"matched", "mismatch", "missing", "unsupported", "unavailable"}
        for key, title_key, project_value in (("title", "title", title),
                                              ("author_name", "project_author_name", project_author)):
            check = identity_check.get(key, {})
            if not isinstance(check, Mapping):
                check = {}
            raw_status = check.get("status")
            status = raw_status
            if not isinstance(status, str) or status not in statuses:
                status = "unavailable"
            manuscript_value = check.get("value")
            status_html = (f'<strong data-identity-status="{status}">'
                           f'{translated("project_identity_" + str(status))}</strong>')
            if manuscript_value is not None:
                manuscript_html = esc(str(manuscript_value))
            elif status == "missing":
                manuscript_html = status_html
            elif raw_status == "unavailable" and project_value:
                manuscript_html = translated("project_identity_text_unavailable")
            else:
                manuscript_html = translated("project_identity_value_unavailable")
            parts.extend([
                f'<dt>{translated(title_key)}</dt><dd>',
                f'<div>{translated("project_identity_saved")}: {esc(project_value) if project_value else translated("project_identity_not_set" if raw_status == "unavailable" else "project_identity_value_unavailable")}</div>',
                f'<div>{translated("project_identity_manuscript")}: {manuscript_html}</div>',
            ])
            if status != "missing" or manuscript_value is not None:
                parts.append(status_html)
            if raw_status == "unavailable" and not project_value:
                parts.append(f'<p class="ctl-note">{translated("project_identity_enter_" + key)}</p>')
            source_key = {"front_matter": "project_identity_source_metadata",
                          "title_page": "project_identity_source_title_page"}.get(str(check.get("source")))
            if source_key:
                parts.append(f'<div class="ctl-note">{translated("project_identity_source")}: {translated(source_key)}</div>')
            parts.append('</dd>')
        parts.append('</dl></section></details>')
    parts.extend([
        '</fieldset>',
        '<fieldset class="settings-section" id="settings-analysis">',
        f'<legend>{translated("settings_analysis")}</legend>',
        '<div class="settings-grid">',
        f'<div class="setting-field"><label for="set-language">{help_term(labels, "language", translated("language"))}</label>',
        '<select class="ctl" id="set-language" aria-describedby="set-language-help settings-scope-help">',
    ])
    for code, name in language_options:
        selected = " selected" if code == current_language else ""
        parts.append(f'<option value="{esc(code)}"{selected}>{esc(name)}</option>')
    parts.extend([
        '</select>',
        f'<p id="set-language-help">{translated("settings_language_hint")}</p></div></div>',
    ])
    disabled = "" if author_setting_enabled else " disabled"
    checked = " checked" if publication_values["enabled"] else ""
    publication_parts = [
        '<details class="settings-advanced publication-settings" id="settings-publication">',
        f'<summary>{translated("publication_title")}</summary>',
        f'<p class="panel-guide">{translated("publication_hint" if author_setting_enabled else "publication_unavailable")}</p>',
        '<p class="ctl-note"><a href="' + docs_url("guides/research-pdf.html#publication") + '" '
        f'target="_blank" rel="noopener noreferrer">{translated("publication_guide")}</a></p>',
        checkbox_field(
            f'<input type="checkbox" id="set-publication-enabled" '
            f'data-publication-key="enabled"{checked}{disabled}/>',
            translated("publication_enabled"),
        ),
    ]
    if publication_error:
        publication_parts.append('<p class="ctl-status err" id="publication-settings-error" role="alert">'
                     f'{translated("publication_invalid")}: {esc(publication_error)}</p>')
    publication_parts.append('<div class="settings-grid">')
    for field in PUBLICATION_FIELDS:
        identifier = "set-publication-" + field.key
        value = esc(publication_values[field.key])
        attrs = (f'class="ctl" id="{identifier}" data-publication-key="{field.key}" '
                 f'maxlength="{field.max_chars}"{disabled}')
        publication_parts.append(f'<div class="setting-field publication-field-{field.kind} publication-field-{field.key}">'
                     f'<label for="{identifier}">{translated("publication_" + field.key)}</label>')
        if field.kind == "multiline":
            publication_parts.append(f'<textarea {attrs} rows="3">{value}</textarea>')
        else:
            publication_parts.append(f'<input type="text" {attrs} value="{value}"/>')
        publication_parts.append('</div>')
    publication_parts.append('</div></details>')
    parts.extend([
        '<details class="settings-advanced settings-thresholds" id="settings-thresholds">',
        f'<summary>{translated("settings_thresholds_optional")}</summary>',
        f'<p class="panel-guide">{translated("settings_thresholds_hint")}</p>',
        '<div class="settings-grid">',
    ])
    fields = (
        ("z_mild", "set-z-mild"),
        ("z_strong", "set-z-strong"),
        ("fdr_q", "set-fdr-q"),
        ("dim_score_threshold", "set-dim-threshold"),
    )
    for key, control_id in fields:
        value = getattr(thresholds, key)
        default = getattr(defaults, key)
        policy = FingerprintThresholds.numeric_inputs[key]
        constraints = [f'min="{policy.minimum}"', 'step="any"']
        if policy.maximum is not None:
            constraints.append(f'max="{policy.maximum}"')
        if policy.minimum_exclusive:
            constraints.append('data-min-exclusive="true"')
        if policy.maximum_exclusive:
            constraints.append('data-max-exclusive="true"')
        help_text = label(labels, "help_" + key)
        if key == "fdr_q" and thresholds.fdr_method.lower() == "by":
            help_text = help_text.replace("Benjamini–Hochberg", "Benjamini–Yekutieli").replace(
                "Benjamini-Hochberg", "Benjamini–Yekutieli"
            )
        default_note = esc(label(labels, "settings_default")).replace("{value}", str(default))
        parts.append(
            f'<div class="setting-field"><label for="{control_id}">{translated(key)}</label>'
            f'<input class="ctl" type="number" id="{control_id}" value="{value!r}" '
            f'{" ".join(constraints)} required '
            f'data-default="{default!r}" aria-describedby="{control_id}-help settings-scope-help"/>'
            f'<p id="{control_id}-help">{esc(help_text)} <span class="ctl-note">{default_note}</span></p></div>'
        )
        if key == "fdr_q":
            method = thresholds.fdr_method.lower()
            default_method = defaults.fdr_method.lower()
            method_default = esc(label(labels, "settings_default")).replace(
                "{value}", "Benjamini–Hochberg" if default_method == "bh" else "Benjamini–Yekutieli")
            parts.append(
                f'<div class="setting-field"><label for="set-fdr-method">{translated("settings_fdr_method")}</label>'
                f'<select class="ctl" id="set-fdr-method" data-default="{default_method}" '
                f'aria-describedby="set-fdr-method-help settings-scope-help">'
                f'<option value="bh"{" selected" if method == "bh" else ""}>Benjamini–Hochberg</option>'
                f'<option value="by"{" selected" if method == "by" else ""}>Benjamini–Yekutieli</option>'
                f'</select><p id="set-fdr-method-help">{esc(label(labels, "help_fdr"))} '
                f'<span class="ctl-note">{method_default}</span></p></div>'
            )
    parts.extend([
        '<div class="setting-field">',
        f'<label for="set-flag-min-sev">{translated("flag_min_severity")}</label>',
        '<select class="ctl" id="set-flag-min-sev" data-default="2" '
        'aria-describedby="flag-severity-help settings-scope-help">',
    ])
    for severity in (1, 2, 3):
        selected = " selected" if severity == thresholds.flag_min_severity else ""
        marker = f' · {translated("settings_default_short")}' if severity == 2 else ""
        parts.append(
            f'<option value="{severity}"{selected}>{translated(f"severity_{severity}")} ≥ {severity}{marker}</option>'
        )
    parts.extend([
        '</select>',
        f'<p id="flag-severity-help">{translated("help_flag_min_severity")}</p></div>',
        '</div></details>',
        checkbox_field(
            '<input type="checkbox" id="set-save-analysis-defaults" '
            'aria-describedby="save-analysis-defaults-help"'
            f'{"" if author_setting_enabled and project_token else " disabled"}/>',
            translated("settings_save_analysis_defaults"),
        ),
        '<p class="ctl-note" id="save-analysis-defaults-help">'
        f'{translated("settings_save_analysis_hint" if author_setting_enabled and project_token else "settings_save_analysis_unavailable")}</p>',
        '</fieldset>',
        *publication_parts,
        register_editor(labels, register_settings or {}, editable=author_setting_enabled and bool(project_token),
                        language_key=language_key or current_language),
        site_publication_editor(labels, site_publications if site_publications is not None else {},
                                editable=author_setting_enabled and bool(project_token),
                                context_token=site_publication_context_token),
        '<div class="settings-actions">',
        f'<button type="submit" class="ctl primary" data-action="settings" data-payload="settings">{translated("apply")}</button>',
        f'<button type="button" class="ctl" id="settings-reset">{translated("reset_thresholds")}</button>',
        f'<span class="ctl-note">{translated("settings_apply_hint")}</span>',
        f'<span hidden id="settings-order-error">{translated("threshold_order")}</span>',
        '</div></form>',
    ])
    return "".join(parts)


def site_publication_editor(
    labels: Mapping[str, str] | None, profiles: Mapping[str, Any], *, editable: bool,
    context_token: str = "",
) -> str:
    """Keep curated publication drafts in the existing project settings save."""
    keys = ("title", "hint", "unavailable", "id", "id_hint", "name", "introduction", "add_profile", "profile",
            "entries", "entry", "add_entry", "dossier", "choose_dossier", "revision", "current",
            "version", "section", "whole_body", "after", "after_hint", "override", "citations", "geography",
            "scope", "missing", "loading", "load_error", "invalid", "raw_error", "raw", "recover",
            "move_up", "move_down")
    terms = {"publication_editor_" + key: label(labels, "publication_editor_" + key) for key in keys}
    terms["remove_recent_project"] = label(labels, "remove_recent_project")
    return (
        '<details class="settings-advanced" id="settings-site-publications">'
        f'<summary id="settings-site-publications-summary">{esc(terms["publication_editor_title"])}</summary>'
        f'<p class="panel-guide">{esc(terms["publication_editor_hint"])}</p>'
        + ("" if editable else f'<p class="ctl-note">{esc(terms["publication_editor_unavailable"])}</p>')
        + '<fieldset class="site-publication-editor" id="site-publication-editor" '
        f'data-initial="{esc(json.dumps(profiles, ensure_ascii=False))}" '
        f'data-labels="{esc(json.dumps(terms, ensure_ascii=False))}" data-context-token="{esc(context_token)}"'
        f'{"" if editable else " disabled"}>'
        f'<legend>{esc(terms["publication_editor_title"])}</legend>'
        '<p class="ctl-status" data-site-publication-status role="status" aria-live="polite"></p>'
        '<div data-site-publication-profiles></div>'
        f'<button type="button" class="ctl" data-site-publication-add-profile>{esc(terms["publication_editor_add_profile"])}</button>'
        '</fieldset></details>'
    )


def register_editor(
    labels: Mapping[str, str] | None, settings: Mapping[str, Any], *, editable: bool,
    language_key: str = "en",
) -> str:
    """Use the shared settings save for explicit chapter registers and ranges."""
    initial = {key: settings.get(key, {}) for key in ("register_profiles", "chapter_registers")}
    terms = {key: label(labels, key) for key in (
        "register_name", "register_target", "register_lower", "register_upper", "register_add_target",
        "register_selector", "register_invalid", "remove_recent_project")}
    units = FEATURE_UNITS.get(language_key, {})
    features = [(name, f"{label(labels, key)} · {units.get(name, unit)}") for name, key, unit in FEATURES]
    return (
        '<details class="settings-advanced" id="settings-registers">'
        f'<summary id="settings-registers-summary">{esc(label(labels, "register_title"))}</summary>'
        f'<p class="panel-guide">{esc(label(labels, "register_hint"))}</p>'
        f'<p class="ctl-note">{esc(label(labels, "register_scope_hint"))}</p>'
        + ("" if editable else f'<p class="ctl-note">{esc(label(labels, "register_unavailable"))}</p>')
        + f'<fieldset class="register-editor" id="register-editor" data-initial="{esc(json.dumps(initial, ensure_ascii=False))}" '
        f'data-labels="{esc(json.dumps(terms, ensure_ascii=False))}" data-features="{esc(json.dumps(features, ensure_ascii=False))}"'
        f'{"" if editable else " disabled"}>'
        f'<legend>{esc(label(labels, "register_title"))}</legend>'
        '<div data-register-profiles></div>'
        f'<button type="button" class="ctl" data-register-add-profile>{esc(label(labels, "register_add_profile"))}</button>'
        f'<h4>{esc(label(labels, "register_assignments"))}</h4>'
        f'<p class="ctl-note">{esc(label(labels, "register_selector_hint"))}</p>'
        '<div data-register-assignments></div>'
        f'<button type="button" class="ctl" data-register-add-assignment>{esc(label(labels, "register_add_assignment"))}</button>'
        '</fieldset></details>'
    )
