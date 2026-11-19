"""Localized labels for the project workspace and local research controls.

Locale catalogs live in ``src/lixity/locales/<lang>.json`` for ``en``, ``de``,
``fr``, ``es``, ``it``, ``pt`` and ``nl``. Markers such as ``research/`` and
``{count}`` are interface data, not translated. Callers should prefer
:func:`workspace_labels_for` so runtime paths load only the active locale;
``WORKSPACE_LABELS`` remains lazily available for full-matrix inspection and
tests.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

_LANGUAGES = ("en", "de", "fr", "es", "it", "pt", "nl")
_LOCALES_DIR = Path(__file__).resolve().with_name("locales")

PROJECT_STRUCTURE_ROLE_LABELS = {
    role: "project_structure_role_" + role
    for role in ("manuscript", "research", "outputs", "output_archive", "submissions")
}
PROJECT_STRUCTURE_STATE_LABELS = {
    state: "project_structure_state_" + state
    for state in (
        "available",
        "missing",
        "unassigned",
        "invalid",
        "ambiguous",
        "unreadable",
        "unsafe",
        "unknown",
    )
}
PROJECT_STRUCTURE_ISSUE_LABELS = {
    "invalid-config": "project_structure_issue_config",
    "unsafe-config": "project_structure_issue_unsafe",
    "config-unreadable": "project_structure_issue_unreadable",
    "config-too-large": "project_structure_issue_limited",
    "manuscript-missing": "project_structure_issue_missing",
    "manuscript-unassigned": "project_structure_issue_unassigned",
    "manuscript-ambiguous": "project_structure_issue_ambiguous",
    "manuscript-invalid": "project_structure_issue_file",
    "manuscript-unreadable": "project_structure_issue_unreadable",
    "manuscript-unsafe": "project_structure_issue_unsafe",
    "manuscript-selection-mismatch": "project_structure_issue_selection",
    "manuscript-in-outputs": "project_structure_issue_source_output",
    "role-not-directory": "project_structure_issue_directory",
    "role-symlink": "project_structure_issue_unsafe",
    "role-unreadable": "project_structure_issue_unreadable",
    "artifact-symlink-broken": "project_structure_issue_broken",
    "artifact-path-escape": "project_structure_issue_unsafe",
    "artifact-not-file": "project_structure_issue_file",
    "artifact-unreadable": "project_structure_issue_unreadable",
    "artifact-name-invalid": "project_structure_issue_file",
    "output-source-alias": "project_structure_issue_source_output",
    "output-config-alias": "project_structure_issue_source_output",
    "inventory-truncated": "project_structure_issue_limited",
    "discovery-truncated": "project_structure_issue_limited",
}


@lru_cache(maxsize=len(_LANGUAGES))
def _load_locale(language: str) -> dict[str, str]:
    if language not in _LANGUAGES:
        raise KeyError(language)
    data = orjson.loads((_LOCALES_DIR / f"{language}.json").read_bytes())
    if not isinstance(data, dict):
        raise ValueError(f"Workspace locale catalog {language!r} must be a JSON object")
    return data


def workspace_labels_for(language: str) -> dict[str, str]:
    """Return the cached label table for one locale, falling back to English."""
    return _load_locale(language if language in _LANGUAGES else "en")


if TYPE_CHECKING:
    WORKSPACE_LABELS: dict[str, dict[str, str]]


def __getattr__(name: str) -> Any:
    if name == "WORKSPACE_LABELS":
        tables = {language: _load_locale(language) for language in _LANGUAGES}
        expected = set(tables["en"])
        if any(set(labels) != expected for labels in tables.values()):
            raise ValueError("Workspace label catalogs must share the exact same key set")
        globals()["WORKSPACE_LABELS"] = tables
        return tables
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted({*globals(), "WORKSPACE_LABELS"})
