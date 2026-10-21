"""Shared, deterministic orchestration for API, CLI and workspace analysis."""

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from .analyzer import CorpusAnalyzer
from .language import ResolvedLanguage, resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import CorpusConfig, CorpusMetrics
from .paragraph_evidence import ParagraphEvidence
from .style_fingerprint import (
    FingerprintThresholds,
    StyleFingerprint,
    lexical_structural_diagnostics,
)
from .style_profile import ChapterProfile, ParagraphProfile, ParagraphProfiler, ProfileThresholds


@dataclass(frozen=True)
class DocumentAnalysis:
    metrics: CorpusMetrics
    paragraphs: list[ParagraphProfile]
    chapters: list[ChapterProfile]
    fingerprint: StyleFingerprint
    evidence: dict[int, ParagraphEvidence] | None = None


def paragraph_identity(paragraph: ParagraphProfile) -> dict[str, Any]:
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
    config = CorpusConfig(language=language, **(settings | overrides))
    resolved = resolve_language(config, sample_text=text)
    return config.model_copy(update={"language": resolved.key}), resolved


def profile_document(
    text: str, config: CorpusConfig, thresholds: FingerprintThresholds, *,
    evidence: dict[int, ParagraphEvidence] | None = None,
) -> tuple[list[ParagraphProfile], list[ChapterProfile]]:
    profile_thresholds = ProfileThresholds(flag_min_severity=thresholds.flag_min_severity)
    return ParagraphProfiler(config, thresholds=profile_thresholds, sample_text=text).profile_blocks(
        parse_markdown_blocks(text, config), evidence=evidence,
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


def analyze_document(
    text: str, config: CorpusConfig, thresholds: FingerprintThresholds, *,
    include_evidence: bool = False,
) -> DocumentAnalysis:
    metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
    evidence: dict[int, ParagraphEvidence] | None = {} if include_evidence else None
    paragraphs, chapters = profile_document(text, config, thresholds, evidence=evidence)
    fingerprint = fingerprint_document(text, config, thresholds, metrics)
    return DocumentAnalysis(metrics, paragraphs, chapters, fingerprint, evidence)
