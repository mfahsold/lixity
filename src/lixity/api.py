"""lixity.api – Programmatic API facade for AI agents and automation.

Provides deterministic, self-describing functions for corpus linguistics,
tense profiling, self-calibrated style references, work markers, and dashboards.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import __version__
from .analyzer import CorpusAnalyzer
from .config import resolve_thresholds
from .language import LANGUAGE_PROFILES, resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import SCHEMA_VERSION, CorpusConfig
from .status import SCHEMA_VERSION_STYLE
from .style_fingerprint import (
    FingerprintThresholds,
    StyleFingerprint,
    lexical_structural_diagnostics,
)
from .style_profile import ParagraphProfiler, ProfileThresholds
from .ui import render_dashboard

PROFILE_KEYS = tuple(LANGUAGE_PROFILES)


def _config_and_language(language: str, text: str, **overrides: Any) -> tuple[CorpusConfig, Any]:
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


def profile(
    text: str,
    language: str = "auto",
    flag_min_severity: int | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Paragraph-accurate tense and style profiles with line anchors
    (dominant tense, switch/mix severity, ASL, dialogue, function words,
    perception filters, modals, nominalisations, passive).

    ``flag_min_severity`` (1|2|3) floors the paragraph flag cut; ``None``
    resolves from project config / code default (same as the style passport).

    Returns a JSON-safe dict: ``{"meta": {...}, "chapters": [...], "paragraphs": [...]}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    fp_thresholds = resolve_thresholds(flag_min_severity=flag_min_severity)
    profile_thresholds = ProfileThresholds(flag_min_severity=fp_thresholds.flag_min_severity)
    paragraphs, chapters = ParagraphProfiler(config, thresholds=profile_thresholds).profile_blocks(
        parse_markdown_blocks(text)
    )
    return {
        "meta": _meta(resolved.key),
        "chapters": [c.__dict__ for c in chapters],
        "paragraphs": [{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
    }


def fingerprint(
    text: str,
    language: str = "auto",
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Self-calibrated style fingerprint (style reference): house-style bands
    (median ± 2 sigma) per feature, significance-adjusted deviations (z*),
    Benjamini-Hochberg/Yekutieli FDR set, expected false positives, effect
    sizes (Cliff's δ), baseline exchangeability diagnostics, self-calibrated
    style dimensions (Spearman correlation + Jacobi eigendecomposition) and
    redundant feature pairs.

    Thresholds (z_mild=2.5, z_strong=3.5, fdr_q=0.05, fdr_method='bh',
    dim_score_threshold=2.5) are injectable; ``None`` keeps the documented
    defaults. Returns the style reference dict (see docs/AGENTS.md).

    In addition to the metrics-derived structural block, the passport carries
    token-level ``structural_diagnostics.cooccurrence`` / ``.keyness`` computed
    from ``text`` (Dunning G² early vs late half, Goh–Barabási fitness).
    """
    config, _resolved = _config_and_language(language, text, **config_overrides)
    metrics = CorpusAnalyzer(config).analyze_text(text)
    thresholds = _thresholds(
        z_mild,
        z_strong,
        fdr_q,
        fdr_method=fdr_method,
        dim_score_threshold=dim_score_threshold,
        flag_min_severity=flag_min_severity,
    )
    fingerprint = StyleFingerprint.from_metrics(metrics, thresholds=thresholds)
    lexical = lexical_structural_diagnostics(text, config)
    if lexical:
        fingerprint.structural_diagnostics.update(lexical)
    return fingerprint.passport()


def _thresholds(
    z_mild: float | None,
    z_strong: float | None,
    fdr_q: float | None,
    *,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    min_chapters: int | None = None,
) -> FingerprintThresholds:
    """Shared builder: explicit kwargs > project config > code default."""
    return resolve_thresholds(
        z_mild=z_mild,
        z_strong=z_strong,
        fdr_q=fdr_q,
        fdr_method=fdr_method,
        dim_score_threshold=dim_score_threshold,
        flag_min_severity=flag_min_severity,
        min_chapters=min_chapters,
    )


def passport(
    text: str,
    language: str = "auto",
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Alias of :func:`fingerprint` – the style passport as structured data.
    """
    return fingerprint(
        text,
        language=language,
        z_mild=z_mild,
        z_strong=z_strong,
        fdr_q=fdr_q,
        **config_overrides,
    )


def dialogue(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Dialogue and interaction structure: turns (quoted segments), turn lengths
    (mean/median/longest), turns per 1,000 words, dialogue paragraph share and
    the per-chapter turn structure. Heuristic: quoted speech via the language
    profile, no speaker attribution.

    Returns ``{"meta": {...}, "dialogue": {...}}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    from .dialogue import dialogue_report

    return {
        "meta": _meta(resolved.key),
        "dialogue": dialogue_report(text, config).to_dict(),
    }


def characters(
    text: str,
    names: Mapping[str, str] | Sequence[str],
    language: str = "auto",
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Character presence across chapters for curated name patterns.

    ``names`` is a sequence of display names or a mapping
    ``pattern -> display name`` (aliases), e.g. ``{"Matthias|Matze": "Matthias"}``.
    Returns ``{"meta": {...}, "chapters": n, "figures": [...]}``.
    Raises ``ValueError`` when ``names`` is empty (no NER — names required).
    """
    if not names:
        raise ValueError(
            "characters requires at least one name or alias pattern "
            "(no NER — the caller supplies the names)"
        )
    config, resolved = _config_and_language(language, text, **config_overrides)
    from .characters import presence_report

    report = presence_report(text, names, config)
    return {"meta": _meta(resolved.key), **report}


def pacing(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Scene structure, pacing signals and chapter hooks: explicit scene breaks
    (``---``, ``* * *``), per-scene tempo proxies (ASL, staccato, dialogue),
    the closing sentence of each chapter and its documented 0–3 hook score.

    When the text has no explicit dividers, ``explicit_scene_breaks`` is 0 and
    ``scenes_are_chapters`` is true (each chapter is one scene).

    Returns ``{"meta": {...}, "pacing": {...}}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    from .pacing import pacing_report

    return {"meta": _meta(resolved.key), "pacing": pacing_report(text, config).to_dict()}


def motifs(
    text: str,
    motifs: Mapping[str, str] | None = None,
    language: str = "auto",
    phrase_size: int = 3,
    **config_overrides: Any,
) -> dict[str, Any]:
    r"""
    Motif tracking and repetition analysis: per-motif presence (mentions,
    density, chapter span, longest gap) plus generic repetition signals —
    the most frequent content words and repeated n-grams (default 3-grams,
    at least 3 occurrences) with their chapter spread.

    ``motifs`` maps a display name to a regular expression
    (``{"Wut": r"\b(Wut|wütend\w*)\b"}``). Returns ``{"meta", "motifs", "top_words",
    "repeated_phrases", "chapters"}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    from .motifs import motif_report

    report = motif_report(text, motifs, config, phrase_size=phrase_size)
    return {"meta": _meta(resolved.key), **report.to_dict()}


def showing(text: str, language: str = "auto", **config_overrides: Any) -> dict[str, Any]:
    """
    Showing vs. telling balance (heuristic, self-calibrating): robust z-scores
    of the telling signals (perception filters, modals, passive,
    nominalisations) and the showing signals (dialogue, staccato) against the
    manuscript's own chapter medians, plus the balance ``show_z − tell_z`` and
    the most telling/showing chapters.

    Returns ``{"meta": {...}, "showing": {...}}``.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    from .showing import showing_report

    return {"meta": _meta(resolved.key), "showing": showing_report(text, config).to_dict()}


def dashboard(
    text: str,
    language: str = "auto",
    title: str = "Manuscript",
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    **config_overrides: Any,
) -> str:
    """
    Renders the complete single-file HTML dashboard (self-contained, no CDN,
    deterministic). Returns the HTML document as a string.
    """
    config, resolved = _config_and_language(language, text, **config_overrides)
    metrics = CorpusAnalyzer(config).analyze_text(text)
    thresholds = _thresholds(
        z_mild,
        z_strong,
        fdr_q,
        fdr_method=fdr_method,
        dim_score_threshold=dim_score_threshold,
        flag_min_severity=flag_min_severity,
    )
    profile_thresholds = ProfileThresholds(flag_min_severity=thresholds.flag_min_severity)
    paragraphs, chapters = ParagraphProfiler(config, thresholds=profile_thresholds).profile_blocks(
        parse_markdown_blocks(text)
    )
    fingerprint = StyleFingerprint.from_metrics(metrics, thresholds=thresholds)
    lexical = lexical_structural_diagnostics(text, config)
    if lexical:
        fingerprint.structural_diagnostics.update(lexical)
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
        flag_min_severity=thresholds.flag_min_severity,
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
        "commands": [
            {
                "name": "analyze",
                "purpose": "corpus metrics and per-chapter style features",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "profile",
                "purpose": "paragraph-accurate tense and style profiles",
                "output": "json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "dialogue",
                "purpose": "dialogue turn structure (turns, lengths, per chapter)",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "characters",
                "purpose": "character presence per chapter (names or aliases)",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "pacing",
                "purpose": "scene structure, pacing signals, chapter hook score",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "motifs",
                "purpose": "motif presence and repetition (content words, n-grams)",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "showing",
                "purpose": "showing vs. telling balance (self-calibrating)",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "style",
                "purpose": (
                    "self-calibrating style reference (bands, z*, FDR, dimensions, "
                    "structural diagnostics incl. distribution shift, co-occurrence fitness, keyness)"
                ),
                "output": "text|json",
                "schema_version": SCHEMA_VERSION_STYLE,
            },
            {
                "name": "dashboard",
                "purpose": "single-file interactive HTML dashboard (all panels)",
                "output": "html",
            },
            {
                "name": "build",
                "purpose": "idempotent workspace build (exports/, archive, nda/)",
                "output": "files",
            },
            {
                "name": "about",
                "purpose": "this metadata (languages, features, thresholds, commands)",
                "output": "text|json",
            },
            {
                "name": "completion",
                "purpose": "shell completion script",
                "output": "script",
            },
        ],
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
