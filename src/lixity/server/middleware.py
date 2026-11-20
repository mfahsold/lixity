"""Shared server middleware helpers for config loading, request validation and context guards."""

from __future__ import annotations

import contextlib
import os
import warnings
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from ..config import load_project_config, read_explicit_project_config
from ..manuscript_editing import ManuscriptStore
from ..style_fingerprint import FingerprintThresholds

ANALYSIS_OVERRIDE_KEYS: frozenset[str] = frozenset({"tense_model", "tense_scope"})


@dataclass(frozen=True)
class SelectedManuscriptContext:
    """Snapshot of the selected workspace/manuscript identity captured under lock."""

    source: str
    root: str | Path
    language: str
    title: str | None
    thresholds: FingerprintThresholds
    info: dict[str, Any]
    token: str
    analysis_overrides: dict[str, Any]


def analysis_open_overrides(overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract only analysis-scoped open overrides (tense model/scope)."""
    if not overrides:
        return {}
    return {
        key: value
        for key, value in overrides.items()
        if key in ANALYSIS_OVERRIDE_KEYS
    }


def load_selected_project_config(
    source_input: str | None,
    *,
    project_root: str | Path | None = None,
    strict_warnings: bool = False,
    overrides: Mapping[str, Any] | None = None,
    explicit_loader: Callable[..., dict[str, Any]] = read_explicit_project_config,
    implicit_loader: Callable[..., dict[str, Any]] = load_project_config,
) -> dict[str, Any]:
    """Load explicit project configuration (or selected-source config) deterministically."""
    guard = warnings.catch_warnings() if strict_warnings else contextlib.nullcontext()
    with guard:
        if strict_warnings:
            warnings.filterwarnings("error", category=UserWarning, module=r"lixity\.config")
        if project_root is not None:
            settings = dict(explicit_loader(project_root))
        elif source_input and os.path.isfile(source_input):
            settings = dict(implicit_loader(source_input))
        else:
            settings = {}
    extra = analysis_open_overrides(overrides)
    if extra:
        settings.update(extra)
    return settings


def build_manuscript_store(
    workspace_root: str | Path,
    source_input: str | None,
    *,
    language: str = "en",
    project_root: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    explicit_loader: Callable[..., dict[str, Any]] = read_explicit_project_config,
) -> ManuscriptStore:
    """Construct a project-bound ManuscriptStore with explicit project configuration."""
    if not source_input:
        raise ValueError("No manuscript selected")
    effective_root = project_root or Path(workspace_root)
    settings = load_selected_project_config(
        source_input,
        project_root=effective_root,
        overrides=overrides,
        explicit_loader=explicit_loader,
    )
    return ManuscriptStore(
        Path(workspace_root),
        Path(source_input),
        language=language or "en",
        project_config=settings,
    )


def format_validation_error(exc: ValidationError) -> str:
    """Format Pydantic validation errors cleanly for HTTP 400 responses."""
    return "; ".join(
        str(error["msg"]).removeprefix("Value error, ")
        for error in exc.errors(include_url=False, include_input=False)
    )


def parse_single_query_params(
    raw_path: str,
    *,
    required: Collection[str] = (),
    optional: Collection[str] = (),
    non_empty: Collection[str] = (),
    error_message: str | None = None,
) -> dict[str, str]:
    """Parse URL query parameters enforcing allowed keys, single values and non-empty constraints."""
    query = parse_qs(urlparse(raw_path).query, keep_blank_values=True)
    required_set = set(required)
    allowed = required_set | set(optional)
    non_empty_set = set(non_empty)
    if (
        (set(query) - allowed)
        or not required_set.issubset(query)
        or any(len(values) != 1 for values in query.values())
        or any(key in non_empty_set and not query[key][0] for key in query)
    ):
        raise ValueError(error_message or "Invalid query parameters")
    return {key: values[0] for key, values in query.items()}
