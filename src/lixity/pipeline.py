"""Shared, deterministic orchestration for API, CLI and workspace analysis."""

import logging
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from .analyzer import CorpusAnalyzer
from .corridors import evaluate_genre_corridor, pacing_corridor_observation
from .dialogue import dialogue_report
from .language import ResolvedLanguage, resolve_language
from .log import get_logger, log_event
from .markdown_parser import parse_markdown_blocks
from .models import CorpusConfig, CorpusMetrics
from .motifs import motif_report, resolve_motif_settings
from .pacing import MEDIUM_SENTENCE_MAX as PACING_MEDIUM_SENTENCE_MAX
from .pacing import pacing_report, sentence_group_intervals
from .paragraph_evidence import ParagraphEvidence
from .scenes import scene_report_for_display
from .showing import showing_report
from .style_fingerprint import (
    FingerprintThresholds,
    ParagraphLayerData,
    StyleFingerprint,
    lexical_structural_diagnostics,
    prepare_paragraph_layers,
)
from .style_profile import (
    ChapterProfile,
    ParagraphProfile,
    ParagraphProfiler,
    ParagraphText,
    ProfileThresholds,
)


@dataclass(frozen=True)
class DocumentAnalysis:
    metrics: CorpusMetrics
    paragraphs: list[ParagraphProfile]
    chapters: list[ChapterProfile]
    fingerprint: StyleFingerprint
    evidence: dict[int, ParagraphEvidence] | None = None
    paragraph_layers: ParagraphLayerData = field(default_factory=dict)


def paragraph_identity(paragraph: ParagraphProfile | ParagraphText) -> dict[str, Any]:
    """Identify the exact displayed profile text, without retaining that text."""
    return {"start_line": paragraph.start_line, "end_line": paragraph.end_line,
            "paragraph_sha256": sha256(paragraph.text.encode("utf-8")).hexdigest()}


def resolve_document_config(
    text: str, language: str = "en", *,
    project_config: Mapping[str, Any] | None = None, **overrides: Any,
) -> tuple[CorpusConfig, ResolvedLanguage]:
    """Resolve known corpus settings once; explicit language/overrides win."""
    settings = {key: value for key, value in (project_config or {}).items()
                if key in CorpusConfig.model_fields and key != "language"}
    motif_settings = ({"motif_regexes": overrides["motif_regexes"]} if "motif_regexes" in overrides
                      else project_config or {})
    settings["motif_regexes"] = resolve_motif_settings(None, motif_settings)
    config = CorpusConfig(language=language, **(settings | overrides))
    resolved = resolve_language(config, sample_text=text)
    return config.model_copy(update={"language": resolved.key}), resolved


def document_paragraph_texts(text: str, config: CorpusConfig) -> list[ParagraphText]:
    """Reuse the profile's exact displayed-text projection without style analysis."""
    return ParagraphProfiler(config, sample_text=text).text_blocks(parse_markdown_blocks(text, config))


def profile_document(
    text: str, config: CorpusConfig, thresholds: FingerprintThresholds, *,
    evidence: dict[int, ParagraphEvidence] | None = None,
    include_reader_details: bool = False,
) -> tuple[list[ParagraphProfile], list[ChapterProfile]]:
    profile_thresholds = ProfileThresholds(flag_min_severity=thresholds.flag_min_severity)
    return ParagraphProfiler(config, thresholds=profile_thresholds, sample_text=text).profile_blocks(
        parse_markdown_blocks(text, config), evidence=evidence, include_reader_details=include_reader_details,
    )


def fingerprint_document(
    text: str,
    config: CorpusConfig,
    thresholds: FingerprintThresholds,
    metrics: CorpusMetrics | None = None,
) -> StyleFingerprint:
    if metrics is None:
        metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
    fingerprint = StyleFingerprint.from_metrics(metrics, thresholds=thresholds, config=config)
    fingerprint.structural_diagnostics.update(lexical_structural_diagnostics(text, config))
    return fingerprint


logger = get_logger("pipeline")


def analyze_document(
    text: str, config: CorpusConfig, thresholds: FingerprintThresholds, *,
    include_evidence: bool = False,
) -> DocumentAnalysis:
    started = time.monotonic()
    log_event(logger, "pipeline_analyze", level=logging.DEBUG, stage="start", language=config.language, chars=len(text))
    try:
        metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
        evidence: dict[int, ParagraphEvidence] | None = {} if include_evidence else None
        paragraphs, chapters = profile_document(
            text, config, thresholds, evidence=evidence, include_reader_details=include_evidence,
        )
        fingerprint = fingerprint_document(text, config, thresholds, metrics)
        paragraph_layers = prepare_paragraph_layers(paragraphs)
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event(
            logger, "pipeline_analyze", level=logging.DEBUG, stage="completed",
            chapters=len(chapters), paragraphs=len(paragraphs),
            words=metrics.raw_words, duration_ms=duration_ms,
        )
        return DocumentAnalysis(metrics, paragraphs, chapters, fingerprint, evidence, paragraph_layers)
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_event(logger, "pipeline_analyze", stage="failed", error=type(exc).__name__, duration_ms=duration_ms)
        raise


def _attach_sticky_locations(
    pacing_dict: dict[str, Any], sentence_keys: Sequence[str | None], analysis: DocumentAnalysis,
) -> None:
    """Link unique full sentences when both measured scopes agree."""
    if analysis.evidence is None or not sentence_keys:
        return
    candidates: dict[tuple[int, str, int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for idx, paragraph in enumerate(analysis.paragraphs):
        ev = analysis.evidence.get(idx)
        sticky_layer = ev["layers"].get("sticky") if ev else None
        if not sticky_layer:
            continue
        for span_idx, span in enumerate(sticky_layer.get("spans", [])):
            words = span.get("words")
            function_words = span.get("function_words")
            if words is None or function_words is None:
                continue
            quote = paragraph.text[span["start"]:span["end"]].strip()
            digest = sha256(quote.encode("utf-8")).hexdigest()
            identity = (paragraph.chapter_num, digest, words, function_words)
            candidates[identity].append((idx, paragraph.start_line, span_idx))
    sticky_items = [dict(item) for item in pacing_dict["sticky_items"]]
    for item, key in zip(sticky_items, sentence_keys, strict=True):
        if key is None:
            continue
        matches = candidates.get((item["chapter_num"], key, item["words"], item["glue_words"]), [])
        if len(matches) == 1:
            idx, start_line, span_idx = matches[0]
            item.update(paragraph_id=f"p-{idx}", start_line=start_line, span_index=span_idx)
    pacing_dict["sticky_items"] = sticky_items


def _collect_sentence_group_matches(
    analysis: DocumentAnalysis,
    keys: Sequence[str],
    bounds: Sequence[int] | None,
) -> dict[str, list[dict[str, Any]]]:
    if analysis.evidence is None:
        return {}
    intervals = sentence_group_intervals(bounds)
    if len(intervals) != len(keys):
        return {key: [] for key in keys}
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    for idx in range(len(analysis.paragraphs)):
        ev = analysis.evidence.get(idx)
        asl_layer = ev["layers"].get("asl") if ev else None
        if not asl_layer:
            continue
        p_id = f"p-{idx}"
        for span_idx, span in enumerate(asl_layer.get("spans", [])):
            words = span.get("words")
            if not isinstance(words, int):
                continue
            for key, interval in zip(keys, intervals, strict=True):
                if interval is None:
                    continue
                min_w, max_w = interval
                if words >= min_w and (max_w is None or words <= max_w):
                    buckets[key].append({"paragraph_id": p_id, "span_index": span_idx})
                    break
    return buckets


def _attach_sentence_group_locations(
    pacing_dict: dict[str, Any],
    config: CorpusConfig,
    analysis: DocumentAnalysis,
) -> None:
    """Precompute sentence-length jump targets when paragraph evidence is present."""
    if analysis.evidence is None:
        return
    rhythm_bounds = (config.short_sentence_max, PACING_MEDIUM_SENTENCE_MAX)
    dist_bounds = getattr(analysis.metrics.sentence_dist, "_word_bounds", None)
    if dist_bounds is None:
        dist_bounds = (
            config.short_sentence_max,
            config.medium_sentence_max,
            config.long_sentence_max,
        )
    pacing_dict["sentence_group_matches"] = {
        "rhythm": _collect_sentence_group_matches(
            analysis, ("short", "medium", "long"), rhythm_bounds
        ),
        "distribution": _collect_sentence_group_matches(
            analysis, ("short", "medium", "long", "very_long"), dist_bounds
        ),
    }


def supplementary_reports(
    text: str, config: CorpusConfig, analysis: DocumentAnalysis, *,
    scene_settings: Any = None,
    genre_corridor: str | None = None,
    pov_by_chapter: Mapping[int, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Prepare the full workspace's optional reports from the same manuscript.

    Reuse measurements from exactly this text/config; explicitly split scenes
    still require their own measurements. Character error policies and reader
    document construction remain with the caller. No project settings are read.
    """
    pacing_obj = pacing_report(text, config, _include_sticky_identity=analysis.evidence is not None)
    pacing_dict = pacing_obj.to_dict()
    pacing_dict["rhythm_word_bounds"] = (config.short_sentence_max, PACING_MEDIUM_SENTENCE_MAX)
    pacing_dict["sticky_rule"] = {
        "min_words": config.sticky_min_words,
        "min_pct": config.sticky_glue_pct,
    }
    _attach_sticky_locations(pacing_dict, pacing_obj._sticky_sentence_keys, analysis)
    _attach_sentence_group_locations(pacing_dict, config, analysis)
    motifs_dict = motif_report(
        text, config=config, _paragraphs=analysis.paragraphs if analysis.evidence is not None else None,
    ).to_display_dict()
    reports: dict[str, Any] = {
        "dialogue": dialogue_report(text, config).to_dict(),
        "pacing": pacing_dict,
        "motifs": motifs_dict,
        "showing": showing_report(text, config, metrics=analysis.metrics).to_dict(),
        "scenes": scene_report_for_display(
            text, config, scene_settings,
            premeasured_chapters=analysis.metrics.chapters,
            pov_by_chapter=pov_by_chapter,
        ),
    }
    effective_genre = genre_corridor or config.genre_corridor
    if effective_genre:
        reports["genre_corridor"] = evaluate_genre_corridor(
            effective_genre, pacing_corridor_observation(pacing_obj)
        )
    return reports
