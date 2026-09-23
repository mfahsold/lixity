"""lixity.config – project and user configuration files ([tool.lixity] / lixity.toml).

Resolution order (first match wins per key):
  CLI flag / API kwarg  >  UI server session  >  project pyproject.toml
  >  ~/.config/lixity.toml  >  code defaults.

Only scalar keys and simple lists/maps are read; unknown keys are ignored so
forward-compatible configs stay loadable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Keys that may appear in [tool.lixity] (documented schema).
TOOL_KEYS = frozenset(
    {
        "language",
        "title",
        "z_mild",
        "z_strong",
        "fdr_q",
        "fdr_method",
        "dim_score_threshold",
        "flag_min_severity",
        "min_chapters",
        "names",
        "motifs",
        "phrases",
        "chapter_regex",
        "appendix_marker",
        "min_paragraph_length_for_oneliner",
    }
)


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        return {}
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError):
        return {}
    if path.name == "pyproject.toml":
        tool = data.get("tool") or {}
        section = tool.get("lixity") or {}
        return dict(section) if isinstance(section, dict) else {}
    return dict(data) if isinstance(data, dict) else {}


def _walk_up(start: Path, name: str) -> Path | None:
    for directory in [start, *start.parents]:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def load_project_config(start: str | Path | None = None) -> dict[str, Any]:
    """
    Merge user config under project config under nothing else.
    Returns only known scalar/list keys present in either file.
    """
    here = Path(start).resolve() if start else Path.cwd()
    if here.is_file():
        here = here.parent

    merged: dict[str, Any] = {}

    user = Path(os.path.expanduser("~/.config/lixity.toml"))
    if user.is_file():
        merged.update(_load_toml(user))

    project = _walk_up(here, "pyproject.toml")
    if project is not None:
        merged.update(_load_toml(project))

    local = _walk_up(here, "lixity.toml")
    if local is not None and local != project:
        merged.update(_load_toml(local))

    return {k: v for k, v in merged.items() if k in TOOL_KEYS}


def apply_config_to_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    """Extract threshold-related keys (for FingerprintThresholds builders)."""
    out: dict[str, Any] = {}
    for key in (
        "z_mild",
        "z_strong",
        "fdr_q",
        "fdr_method",
        "min_chapters",
        "dim_score_threshold",
        "flag_min_severity",
    ):
        if key in config:
            out[key] = config[key]
    return out
