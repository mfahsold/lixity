"""Shared, accessible settings form with locale-independent HTML values."""

import json
from collections.abc import Mapping, Sequence
from typing import Any

from ..config import MAX_AUTHOR_NAME_CHARS, MAX_PROJECT_TITLE_CHARS
from ..publication import PUBLICATION_FIELDS
from ..site import docs_url
from ..style_fingerprint import FingerprintThresholds
from .components import esc, help_term, label


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
) -> str:
    def translated(key: str) -> str:
        return esc(label(labels, key))

    defaults = FingerprintThresholds()
    publication_values: dict[str, str | bool] = {"enabled": (publication or {}).get("enabled") is True}
    publication_values.update({field.key: value if isinstance(value, str) else ""
                              for field in PUBLICATION_FIELDS
                              for value in [(publication or {}).get(field.key, "")]})
    initial_publication = esc(json.dumps(publication_values, ensure_ascii=False, sort_keys=True))
    parts = [
        f'<form id="settings-form" class="settings-form ctl-group" novalidate '
        f'data-project-token="{esc(project_token)}" data-publication-initial="{initial_publication}" '
        f'data-publication-editable="{str(author_setting_enabled).lower()}" '
        f'data-title-initial="{esc(title)}" data-author-initial="{esc(project_author)}">',
        f'<h3>{translated("settings")}</h3>',
        f'<p class="panel-guide">{translated("settings_intro")}</p>',
        '<div class="settings-grid">',
        f'<div class="setting-field"><label for="set-language">{help_term(labels, "language", translated("language"))}</label>',
        '<select class="ctl" id="set-language">',
    ]
    for code, name in language_options:
        selected = " selected" if code == current_language else ""
        parts.append(f'<option value="{esc(code)}"{selected}>{esc(name)}</option>')
    parts.extend([
        '</select></div>',
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
    ])
    if identity_check is not None:
        parts.extend([
            '<section id="project-identity-check" aria-labelledby="project-identity-title">',
            f'<h4 id="project-identity-title">{translated("project_identity_title")}</h4>',
            f'<p class="ctl-note">{translated("project_identity_hint")}</p>',
            '<dl class="research-revision-readonly">',
        ])
        statuses = {"matched", "mismatch", "missing", "unsupported", "unavailable"}
        for key, title_key, project_value in (("title", "title", title),
                                              ("author_name", "project_author_name", project_author)):
            check = identity_check.get(key, {})
            if not isinstance(check, Mapping):
                check = {}
            status = check.get("status")
            if not isinstance(status, str) or status not in statuses:
                status = "unavailable"
            parts.extend([
                f'<dt>{translated(title_key)}</dt><dd>',
                f'<strong data-identity-status="{status}">{translated("project_identity_" + str(status))}</strong>',
                f'<div>{translated("project_identity_saved")}: {esc(project_value) if project_value else translated("project_identity_not_set")}</div>',
            ])
            if check.get("value") is not None:
                parts.append(f'<div>{translated("project_identity_manuscript")}: {esc(str(check["value"]))}</div>')
            source_key = {"front_matter": "project_identity_source_metadata",
                          "title_page": "project_identity_source_title_page"}.get(str(check.get("source")))
            if source_key:
                parts.append(f'<div class="ctl-note">{translated("project_identity_source")}: {translated(source_key)}</div>')
            parts.append('</dd>')
        parts.append('</dl></section>')
    disabled = "" if author_setting_enabled else " disabled"
    checked = " checked" if publication_values["enabled"] else ""
    parts.extend([
        '<details class="settings-advanced publication-settings" id="settings-publication">',
        f'<summary>{translated("publication_title")}</summary>',
        f'<p class="panel-guide">{translated("publication_hint" if author_setting_enabled else "publication_unavailable")}</p>',
        '<p class="ctl-note"><a href="' + docs_url("guides/research-pdf.html#publication") + '" '
        f'target="_blank" rel="noopener noreferrer">{translated("publication_guide")}</a></p>',
        f'<label class="research-check publication-enable"><input type="checkbox" id="set-publication-enabled" '
        f'data-publication-key="enabled"{checked}{disabled}/> {translated("publication_enabled")}</label>',
    ])
    if publication_error:
        parts.append('<p class="ctl-status err" id="publication-settings-error" role="alert">'
                     f'{translated("publication_invalid")}: {esc(publication_error)}</p>')
    parts.append('<div class="settings-grid">')
    for field in PUBLICATION_FIELDS:
        identifier = "set-publication-" + field.key
        value = esc(publication_values[field.key])
        attrs = (f'class="ctl" id="{identifier}" data-publication-key="{field.key}" '
                 f'maxlength="{field.max_chars}"{disabled}')
        parts.append(f'<div class="setting-field publication-field-{field.kind} publication-field-{field.key}">'
                     f'<label for="{identifier}">{translated("publication_" + field.key)}</label>')
        if field.kind == "multiline":
            parts.append(f'<textarea {attrs} rows="3">{value}</textarea>')
        else:
            parts.append(f'<input type="text" {attrs} value="{value}"/>')
        parts.append('</div>')
    parts.append('</div></details>')
    parts.extend([
        '<details class="settings-advanced settings-thresholds" id="settings-thresholds">',
        f'<summary>{translated("settings_advanced")}</summary>',
        f'<p class="panel-guide">{translated("settings_guidance")}</p>',
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
            f'data-default="{default!r}" aria-describedby="{control_id}-help"/>'
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
                f'aria-describedby="set-fdr-method-help">'
                f'<option value="bh"{" selected" if method == "bh" else ""}>Benjamini–Hochberg</option>'
                f'<option value="by"{" selected" if method == "by" else ""}>Benjamini–Yekutieli</option>'
                f'</select><p id="set-fdr-method-help">{esc(label(labels, "help_fdr"))} '
                f'<span class="ctl-note">{method_default}</span></p></div>'
            )
    parts.extend([
        '<div class="setting-field">',
        f'<label for="set-flag-min-sev">{translated("flag_min_severity")}</label>',
        '<select class="ctl" id="set-flag-min-sev" data-default="2" aria-describedby="flag-severity-help">',
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
        '</div></details><div class="settings-actions">',
        f'<button type="submit" class="ctl primary" data-action="settings" data-payload="settings">{translated("apply")}</button>',
        f'<button type="button" class="ctl" id="settings-reset">{translated("reset_thresholds")}</button>',
        f'<span class="ctl-note">{translated("settings_apply_hint")}</span>',
        f'<span hidden id="settings-order-error">{translated("threshold_order")}</span>',
        '</div></form>',
    ])
    return "".join(parts)
