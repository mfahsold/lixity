"""lixity.api – Programmatic API facade for AI agents and automation.

Provides deterministic, self-describing functions for corpus linguistics,
tense profiling, self-calibrated style passports, work markers, and dashboards.
"""

from __future__ import annotations

from typing import Any

from . import __version__
from .analyzer import CorpusAnalyzer
from .language import LANGUAGE_PROFILES, resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import CorpusConfig
from .style_fingerprint import StyleFingerprint
from .style_profile import ParagraphProfiler
from .ui import render_dashboard

SCHEMA_VERSION = 1
PROFILE_KEYS = tuple(LANGUAGE_PROFILES)


def _config_and_language(language: str, text: str, **overrides: Any):
    """Resolves the language profile and builds the effective configuration."""
    config = CorpusConfig(language=language, **overrides)
    resolved = resolve_language(config, sample_text=text)
    return CorpusConfig(language=resolved.key, **overrides), resolved


def _meta(language_key: str) -> dict[str, Any]:
    return {
        "tool": "lixity",
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "language": language_key,
    }


def analyze(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Corpus analysis: words, sentences, ASL, TTR, Guiraud R, Yule's K, Flesch,
    LIX, dialogue, punctuation, sentence-length architecture, chapters and
    the self-calibrating style features per chapter (incl. standard errors).

    Returns a JSON-safe dict: ``{"meta": {...}, "metrics": {...}}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    metrics = CorpusAnalyzer(config).analyze_text(text)
    return {"meta": _meta(resolved.key), "metrics": metrics.model_dump()}


def profile(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Paragraph-accurate tense and style profiles with line anchors
    (dominant tense, switch/mix severity, ASL, dialogue, function words,
    perception filters, modals, nominalisations, passive).

    Returns a JSON-safe dict: ``{"meta": {...}, "chapters": [...], "paragraphs": [...]}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    return {
        "meta": _meta(resolved.key),
        "chapters": [c.__dict__ for c in chapters],
        "paragraphs": [{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
    }


def fingerprint(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Self-calibrated style fingerprint (style passport): house-style bands
    (median ± 2 sigma) per feature, significance-adjusted deviations (z*),
    Benjamini-Hochberg FDR set, expected false positives, self-calibrated
    style dimensions (Spearman correlation + Jacobi eigendecomposition) and
    redundant feature pairs.

    Returns the passport dict (see docs/AGENTS.md for the full schema).
    """
    config, _resolved = _config_and_language(language, text, **config_overrides)
    metrics = CorpusAnalyzer(config).analyze_text(text)
    return StyleFingerprint.from_metrics(metrics).passport()


def passport(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Alias of :func:`fingerprint` – the style passport as structured data.
    """
    return fingerprint(text, language=language, **config_overrides)


def dashboard(
    text: str,
    language: str = "auto",
    title: str = "Manuskript",
    **config_overrides: Any,
) -> str:
    """
    Renders the complete single-file HTML dashboard (self-contained, no CDN,
    deterministic). Returns the HTML document as a string.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    fingerprint = StyleFingerprint.from_metrics(metrics)
    from .markers import list_markers

    marker_items = list_markers(text)
    return render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        markers=marker_items if marker_items else None,
    )


def about() -> dict[str, Any]:
    """Tool metadata for agents: version, languages, features, thresholds."""
    from .style_fingerprint import (
        DIM_SCORE_THRESHOLD,
        FEATURES,
        N_DIMENSIONS,
        REDUNDANCY_RHO,
        FingerprintThresholds,
    )

    defaults = FingerprintThresholds()
    return {
        "meta": _meta("generic"),
        "languages": PROFILE_KEYS,
        "features": [
            {"field": f, "label_key": label_key, "unit": u} for f, label_key, u in FEATURES
        ],
        "heuristics": {
            "z_mild": defaults.z_mild,
            "z_strong": defaults.z_strong,
            "fdr_q": defaults.fdr_q,
            "min_chapters": defaults.min_chapters,
            "n_dimensions": N_DIMENSIONS,
            "dim_score_threshold": DIM_SCORE_THRESHOLD,
            "redundancy_rho": REDUNDANCY_RHO,
            "hd_d_samples": 42,
            "hd_d_sample_size": 35,
        },
        "license": "Lixity Non-Commercial License 1.0 (LNCL-1.0)",
    }


def markers(text: str) -> list[dict[str, Any]]:
    """
    Lists the work markers of the manuscript (inline HTML comments with
    stable IDs). Returns JSON-safe marker dicts with 1-based line anchors.
    """
    from .markers import list_markers

    return [
        {"id": m.id, "kind": m.kind, "note": m.note, "line": m.line} for m in list_markers(text)
    ]


def add_marker(text: str, kind: str, note: str, line: int) -> tuple[str, dict[str, Any]]:
    """
    Inserts a work marker line directly above ``line`` (1-based).
    Idempotent and deterministic (stable content-hash ID).
    Returns (updated text, marker dict).
    """
    from .markers import add_marker as engine_add_marker

    new_text, marker = engine_add_marker(text, kind, note, line)
    return new_text, {
        "id": marker.id,
        "kind": marker.kind,
        "note": marker.note,
        "line": marker.line,
    }


def resolve_marker(text: str, marker_id: str) -> str:
    """Removes every marker with the given id. Returns the updated text."""
    from .markers import resolve_marker as engine_resolve_marker

    return engine_resolve_marker(text, marker_id)
