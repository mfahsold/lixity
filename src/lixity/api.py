"""lixity.api – Programmatic API facade for scripts, agents and integrations.

Provides deterministic functions for corpus linguistics, tense profiling,
self-calibrated style references, work markers and dashboards. Every call
accepts explicit language and threshold settings; pass project settings when
several projects are involved. JSON payloads carry their schema version in
``meta``. Interface contracts live in ``docs/AGENTS.md``; interpretation
limits in ``docs/METHODS.md``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import __version__
from .analyzer import CorpusAnalyzer
from .config import configuration_metadata, resolve_thresholds
from .language import LANGUAGE_PROFILES
from .models import SCHEMA_VERSION
from .pipeline import (
    analyze_document,
    fingerprint_document,
    profile_document,
    resolve_document_config,
)
from .status import SCHEMA_VERSION_STYLE
from .style_fingerprint import FingerprintThresholds as FingerprintThresholds
from .ui import render_analysis
from .ui.manuscript_document import reader_blocks

PROFILE_KEYS = tuple(LANGUAGE_PROFILES)


def _meta(language_key: str) -> dict[str, Any]:
    return {
        "tool": "lixity",
        "version": __version__,
        "schema_version": SCHEMA_VERSION,
        "language": language_key,
    }


def analyze(text: str, language: str = "en", **config_overrides: Any) -> dict[str, Any]:
    """
    Corpus analysis: words, sentences, ASL, TTR, Guiraud R, Yule's K, Flesch,
    LIX, dialogue, punctuation, sentence-length architecture, chapters and
    the self-calibrating style features per chapter (incl. standard errors).

    Returns a JSON-safe dict: ``{"meta": {...}, "metrics": {...}}``.
    """
    config, resolved = resolve_document_config(text, language, **config_overrides)
    metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
    return {"meta": _meta(resolved.key), "metrics": metrics.model_dump()}


def profile(
    text: str,
    language: str = "en",
    flag_min_severity: int | None = None,
    project_config: Mapping[str, Any] | None = None,
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
    config, resolved = resolve_document_config(text, language, project_config=project_config, **config_overrides)
    fp_thresholds = resolve_thresholds(flag_min_severity=flag_min_severity, project_config=project_config)
    paragraphs, chapters = profile_document(text, config, fp_thresholds)
    return {
        "meta": _meta(resolved.key),
        "chapters": [c.__dict__ for c in chapters],
        "paragraphs": [{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
    }


def fingerprint(
    text: str,
    language: str = "en",
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    min_chapters: int | None = None,
    project_config: Mapping[str, Any] | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Self-calibrated style fingerprint (style reference): house-style bands
    (median ± 2 sigma) per feature, noise-adjusted deviations (z*), nominal
    Benjamini-Hochberg/Yekutieli selections, normal-reference expected hits,
    effect bands (Cliff's δ), baseline dependence diagnostics, exploratory
    style dimensions (standardized midrank PCA on complete chapters), their
    ``dimension_diagnostics`` support/availability metadata and redundant
    feature pairs.

    Thresholds (z_mild=2.5, z_strong=3.5, fdr_q=0.05, fdr_method='bh',
    dim_score_threshold=2.5, min_chapters=2) are injectable. ``None`` resolves
    from project settings, then code defaults. ``project_config={}`` disables
    implicit threshold discovery; a mapping supplies thresholds and known corpus settings.
    Language and corpus options remain explicit arguments. Returns the style
    reference dict (see docs/AGENTS.md).

    In addition to the metrics-derived structural block, the passport carries
    token-level ``structural_diagnostics.cooccurrence`` / ``.keyness`` computed
    from ``text`` (Dunning G² early vs late half, approximate degree-tail fit).
    """
    config, _resolved = resolve_document_config(text, language, project_config=project_config, **config_overrides)
    thresholds = resolve_thresholds(
        z_mild,
        z_strong,
        fdr_q,
        fdr_method=fdr_method,
        dim_score_threshold=dim_score_threshold,
        flag_min_severity=flag_min_severity,
        min_chapters=min_chapters,
        project_config=project_config,
    )
    return fingerprint_document(text, config, thresholds).passport()


def passport(
    text: str,
    language: str = "en",
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


def dialogue(text: str, language: str = "en", **config_overrides: Any) -> dict[str, Any]:
    """
    Dialogue and interaction structure: turns (quoted segments), turn lengths
    (mean/median/longest), turns per 1,000 words, dialogue paragraph share and
    the per-chapter turn structure. Heuristic: quoted speech via the language
    profile, no speaker attribution.

    Returns ``{"meta": {...}, "dialogue": {...}}``.
    """
    config, resolved = resolve_document_config(text, language, **config_overrides)
    from .dialogue import dialogue_report

    return {
        "meta": _meta(resolved.key),
        "dialogue": dialogue_report(text, config).to_dict(),
    }


def characters(
    text: str,
    names: Mapping[str, str] | Sequence[str] | None = None,
    language: str = "en",
    *, project_config: Mapping[str, Any] | None = None,
    **config_overrides: Any,
) -> dict[str, Any]:
    """
    Curated name mentions, with separately declared POV from explicit project settings.

    ``names`` is a sequence of display names or a mapping
    ``pattern -> display name`` (aliases), e.g. ``{"Matthias|Matze": "Matthias"}``.
    Omitted names use only explicit ``project_config`` profiles or legacy names;
    an explicit empty selection still raises. Name matches do not infer scene presence.
    Returns ``{"meta": {...}, "chapters": n, "figures": [...]}``.
    Raises ``ValueError`` when ``names`` is empty (no NER — names required).
    """
    from .characters import presence_report, resolve_character_settings

    selection = resolve_character_settings(names, project_config or {})
    if not selection.names:
        raise ValueError(
            "characters requires at least one name or alias pattern "
            "(no NER — the caller supplies the names)"
        )
    config, resolved = resolve_document_config(text, language, project_config=project_config, **config_overrides)

    report = presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
    return {"meta": _meta(resolved.key), **report}


def pacing(text: str, language: str = "en", **config_overrides: Any) -> dict[str, Any]:
    """
    Scene structure, pacing signals and chapter hooks: explicit scene breaks
    (``---``, ``* * *``), per-scene tempo proxies (ASL, staccato, dialogue),
    the closing sentence of each chapter and its documented 0–3 hook score.

    When the text has no explicit dividers, ``explicit_scene_breaks`` is 0 and
    ``scenes_are_chapters`` is true (each chapter is one scene).

    Returns ``{"meta": {...}, "pacing": {...}}``.
    """
    config, resolved = resolve_document_config(text, language, **config_overrides)
    from .pacing import pacing_report

    return {"meta": _meta(resolved.key), "pacing": pacing_report(text, config).to_dict()}


def scenes(
    text: str, language: str = "en", *,
    project_config: Mapping[str, Any] | None = None, **config_overrides: Any,
) -> dict[str, Any]:
    """Scene features, author targets and explicit manuscript-only registers.

    Settings are explicit; omitted project_config does not discover a project.
    This additive scene envelope has schema version 1; existing analyze/profile
    and style passports retain their contracts.
    """
    from .scenes import scene_report

    config, resolved = resolve_document_config(text, language, project_config=project_config, **config_overrides)
    return {"meta": {**_meta(resolved.key), "schema_version": 1},
            "scenes": scene_report(text, config, (project_config or {}).get("scene_analysis"))}


def motifs(
    text: str,
    motifs: Mapping[str, str] | None = None,
    language: str = "en",
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
    "repeated_phrases", "echoes", "chapters"}``. Echoes use the default local
    window; configurable echo controls belong to ``motifs.motif_report``.
    """
    config, resolved = resolve_document_config(text, language, **config_overrides)
    from .motifs import motif_report

    report = motif_report(text, motifs, config, phrase_size=phrase_size)
    return {"meta": _meta(resolved.key), **report.to_dict()}


def showing(text: str, language: str = "en", **config_overrides: Any) -> dict[str, Any]:
    """
    Showing vs. telling balance (heuristic, self-calibrating): robust z-scores
    of the telling signals (perception filters, modals, passive,
    nominalisations) and the showing signals (dialogue, staccato) against the
    manuscript's own chapter medians, plus the balance ``show_z − tell_z`` and
    the most telling/showing chapters.

    Returns ``{"meta": {...}, "showing": {...}}``.
    """
    config, resolved = resolve_document_config(text, language, **config_overrides)
    from .showing import showing_report

    return {"meta": _meta(resolved.key), "showing": showing_report(text, config).to_dict()}


def dashboard(
    text: str,
    language: str = "en",
    title: str = "Manuscript",
    z_mild: float | None = None,
    z_strong: float | None = None,
    fdr_q: float | None = None,
    fdr_method: str | None = None,
    dim_score_threshold: float | None = None,
    flag_min_severity: int | None = None,
    min_chapters: int | None = None,
    project_config: Mapping[str, Any] | None = None,
    names: Mapping[str, str] | Sequence[str] | None = None,
    **config_overrides: Any,
) -> str:
    """
    Renders the complete single-file HTML dashboard (self-contained, no CDN,
    deterministic). Returns the HTML document as a string.

    ``project_config`` supplies thresholds, known corpus settings, character profiles and scene registers; ``{}`` uses code
    defaults without reading the current directory. Other optional structure
    panels and server controls require the lower-level renderer and an adapter.
    """
    config, resolved = resolve_document_config(text, language, project_config=project_config, **config_overrides)
    thresholds = resolve_thresholds(
        z_mild,
        z_strong,
        fdr_q,
        fdr_method=fdr_method,
        dim_score_threshold=dim_score_threshold,
        flag_min_severity=flag_min_severity,
        min_chapters=min_chapters,
        project_config=project_config,
    )
    analysis = analyze_document(text, config, thresholds)
    from .markers import list_markers

    marker_items = list_markers(text)
    from .characters import presence_report, resolve_character_settings
    from .scenes import scene_report_for_display

    selection = resolve_character_settings(names, project_config or {})
    return render_analysis(
        analysis,
        resolved,
        reader_document=reader_blocks(text, config, analysis.paragraphs),
        title=title,
        flag_min_severity=thresholds.flag_min_severity,
        scenes=scene_report_for_display(text, config, (project_config or {}).get("scene_analysis"),
                                        premeasured_chapters=analysis.metrics.chapters),
        markers=marker_items if marker_items else None,
        characters=(presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
                    if selection.names else None),
    )


def about() -> dict[str, Any]:
    """Installed metadata and configuration schemas, without project values."""
    from .diversity import HD_D_DRAW_SIZE, MIN_TOKENS_LD
    from .research.cli import command_metadata
    from .research.models import ENTITY, Manifest
    from .style_fingerprint import (
        FEATURES,
        MIN_COMPARABLE_SENTENCES,
        MIN_COMPARABLE_WORDS,
        N_DIMENSIONS,
        REDUNDANCY_RHO,
    )

    defaults = FingerprintThresholds()
    record_versions: set[str] = set()
    for definition in ENTITY.json_schema().get("$defs", {}).values():
        version = definition.get("properties", {}).get("schema_version", {})
        record_versions.update(version.get("enum", []))
        if "const" in version:
            record_versions.add(version["const"])
    return {
        "meta": _meta("generic"),
        "languages": PROFILE_KEYS,
        "configuration": configuration_metadata(),
        "features": [
            {"field": f, "label_key": label_key, "unit": u} for f, label_key, u in FEATURES
        ],
        "heuristics": {
            "z_mild": defaults.z_mild,
            "z_strong": defaults.z_strong,
            "fdr_q": defaults.fdr_q,
            "fdr_method": defaults.fdr_method,
            "flag_min_severity": defaults.flag_min_severity,
            "min_chapters": defaults.min_chapters,
            "n_dimensions": N_DIMENSIONS,
            "dim_score_threshold": defaults.dim_score_threshold,
            "redundancy_rho": REDUNDANCY_RHO,
            "hd_d_samples": 0,
            "hd_d_sample_size": HD_D_DRAW_SIZE,
            "hd_d_method": "hypergeometric_expected_ttr",
            "hd_d_min_tokens": MIN_TOKENS_LD,
            "min_comparable_words": MIN_COMPARABLE_WORDS,
            "min_comparable_sentences": MIN_COMPARABLE_SENTENCES,
        },
        "commands": [
            {
                "name": "scenes", "purpose": "scene features, explicit register references and author targets",
                "output": "text|json", "schema_version": 1,
            },
            {
                "name": "analyze",
                "purpose": "corpus metrics and per-chapter style features",
                "output": "text|json",
                "schema_version": SCHEMA_VERSION,
            },
            {
                "name": "profile",
                "purpose": "paragraph tense/style estimates for supported body/list blocks",
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
                "purpose": "curated name mentions per chapter and separate author-declared POV",
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
                "purpose": "motif presence, repetition and local phrase echoes (content words, n-grams)",
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
                "purpose": "single-file HTML dashboard; optional panels depend on supplied analyses",
                "output": "html",
            },
            {
                "name": "pdf",
                "purpose": "composed PDF analysis report, A5 book layout or 30x60 submission sheet",
                "output": "pdf",
            },
            {
                "name": "serve",
                "purpose": "local HTTP development server and interactive dashboard (127.0.0.1)",
                "output": "server",
                "discovery": "/api",
            },
            {
                "name": "service",
                "purpose": "start, stop, restart or inspect an explicitly owned local dashboard process",
                "output": "text|json",
                "schema_version": "lixity-service-local/1",
            },
            {
                "name": "build",
                "purpose": "idempotent workspace build (exports/ and archive)",
                "output": "files",
            },
            {
                "name": "about",
                "purpose": "installed metadata (languages, features, thresholds, commands, configuration)",
                "output": "text|json",
            },
            {
                "name": "completion",
                "purpose": "shell completion script",
                "output": "script",
            },
            {
                "name": "research",
                "purpose": "experimental explicit-project archive: retained evidence, authored dossiers/claims/decisions and guarded revision workflows",
                "output": "command-dependent",
                "subcommands": command_metadata(),
                "status": "experimental",
                "schema_version": "research-local/1",
                "record_schema_versions": sorted(record_versions),
                "manifest_schema_versions": Manifest.model_json_schema()["properties"]["schema_version"]["enum"],
            },
        ],
        "license": "AGPL-3.0-or-later",
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
