"""Shared, accessible settings form with locale-independent HTML values."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..style_fingerprint import FingerprintThresholds
from .components import esc, help_term, label


def settings_form(
    labels: Mapping[str, str] | None,
    title: str,
    current_language: str,
    language_options: Sequence[Any],
    thresholds: FingerprintThresholds,
) -> str:
    def translated(key: str) -> str:
        return esc(label(labels, key))

    defaults = FingerprintThresholds()
    parts = [
        '<form id="settings-form" class="settings-form ctl-group" novalidate>',
        f'<h3>{translated("settings")}</h3>',
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
        f'<input class="ctl" id="set-title" value="{esc(title)}"/></div></div>',
        '<details class="settings-advanced">',
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
        parts.append(
            f'<div class="setting-field"><label for="{control_id}">{translated(key)}</label>'
            f'<input class="ctl" type="number" id="{control_id}" value="{value!r}" '
            f'{" ".join(constraints)} required '
            f'data-default="{default!r}" aria-describedby="{control_id}-help"/>'
            f'<p id="{control_id}-help">{esc(help_text)}</p></div>'
        )
    parts.extend([
        '<div class="setting-field">',
        f'<label for="set-flag-min-sev">{translated("flag_min_severity")}</label>',
        '<select class="ctl" id="set-flag-min-sev" data-default="2" aria-describedby="flag-severity-help">',
    ])
    for severity in (1, 2, 3):
        selected = " selected" if severity == thresholds.flag_min_severity else ""
        parts.append(f'<option value="{severity}"{selected}>{translated(f"severity_{severity}")} ≥ {severity}</option>')
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
