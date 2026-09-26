"""Adapter connecting research repository sources and versions to the core analysis pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._version import __version__
from ..config import resolve_thresholds
from ..language import resolve_language
from ..models import SCHEMA_VERSION, CorpusConfig
from ..pipeline import analyze_document
from ..style_fingerprint import FEATURES, FingerprintThresholds
from ..ui import render_dashboard
from .models import Extraction, Passage, Reference, Source, SourceVersion, Tombstone
from .repository import Repository, ResearchError

_ALLOWED_THRESHOLDS = {
    "z_mild",
    "z_strong",
    "fdr_q",
    "fdr_method",
    "dim_score_threshold",
    "flag_min_severity",
    "min_chapters",
}


@dataclass(frozen=True)
class SourceAnalysisResult:
    """Deterministic analysis results for a verified archived source version."""

    report_data: dict[str, Any]
    dashboard_html: str

    def report(self) -> dict[str, Any]:
        return self.report_data

    def dashboard(self) -> str:
        return self.dashboard_html


def analyze(
    project: str | Path,
    source_id: str,
    *,
    version_id: str | None = None,
    thresholds: Mapping[str, Any] | None = None,
) -> SourceAnalysisResult:
    """Analyze verified archived text with explicit settings; never accept a claim."""
    if thresholds is not None:
        for key in thresholds:
            if key not in _ALLOWED_THRESHOLDS:
                raise ValueError(f"Unknown threshold: {key}")

    thresholds_dict = dict(thresholds) if thresholds is not None else {}
    try:
        resolved_thresholds: FingerprintThresholds = resolve_thresholds(
            project_config={}, **thresholds_dict
        )
    except TypeError as exc:
        raise ValueError(str(exc)) from exc

    repository = Repository(project)
    snapshot = repository.snapshot()

    source = snapshot.get(Reference(id=source_id), Source)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    if source.id in withdrawn_or_purged:
        raise ResearchError("Source has been withdrawn or purged; refusing analysis")

    if version_id is None:
        versions = [
            record
            for record in snapshot.records.values()
            if isinstance(record, SourceVersion) and record.source_ref.id == source.id
        ]
        if not versions:
            raise ResearchError("Source has no versions")
        version = max(versions, key=lambda rec: rec.sequence)
    else:
        version = snapshot.get(Reference(id=version_id), SourceVersion)
        if version.source_ref.id != source.id:
            raise ResearchError("Source version does not belong to the requested source")

    if version.id in withdrawn_or_purged:
        raise ResearchError("Source version has been withdrawn or purged; refusing analysis")

    raw_bytes = repository.read_blob(version.blob)
    text = raw_bytes.decode("utf-8")

    config = CorpusConfig(language=source.language)
    resolved = resolve_language(config, sample_text=text)
    config = config.model_copy(update={"language": resolved.key})

    analysis = analyze_document(text, config, resolved_thresholds)

    # Compute paragraph line offsets in the original text (1-indexed lines)
    raw_lines = text.splitlines(keepends=True)
    line_starts: list[int] = [0]
    line_ends: list[int] = [0]
    pos = 0
    for line in raw_lines:
        line_starts.append(pos)
        pos += len(line)
        line_ends.append(pos)

    # Locate passages belonging to this source version
    extraction_ids = {
        record.id
        for record in snapshot.records.values()
        if isinstance(record, Extraction) and record.source_version_ref.id == version.id
    }
    passages = [
        record
        for record in snapshot.records.values()
        if isinstance(record, Passage) and record.extraction_ref.id in extraction_ids
    ]
    passages.sort(key=lambda p: (p.start, p.end))

    paragraphs_data: list[dict[str, Any]] = []
    for p in analysis.paragraphs:
        start_idx = p.start_line if p.start_line < len(line_starts) else 0
        end_idx = p.end_line if p.end_line < len(line_ends) else len(line_ends) - 1
        p_start = line_starts[start_idx]
        p_end = line_ends[end_idx]

        matching_passages = [
            {"id": pass_rec.id, "revision": pass_rec.revision}
            for pass_rec in passages
            if pass_rec.start < p_end and pass_rec.end > p_start
        ]

        para_dict = {k: v for k, v in p.__dict__.items() if k != "text"}
        para_dict["evidence"] = {
            "start": p_start,
            "end": p_end,
            "offset_unit": "unicode_codepoint",
            "passage_refs": matching_passages,
        }
        paragraphs_data.append(para_dict)

    # Evaluation limitations and baseline coverage
    limitations: list[str] = []
    if len(analysis.chapters) < resolved_thresholds.min_chapters:
        limitations.append("insufficient_chapters")
    if version.context.is_translation is True:
        limitations.append("translation")
    if version.context.original_language:
        limitations.append("historical_language")

    estimable = sum(
        1
        for b in analysis.fingerprint.baseline.values()
        if b.get("n", 0) >= resolved_thresholds.min_chapters
    )
    baseline_coverage = {
        "total_features": len(FEATURES),
        "estimable_features": estimable,
    }

    report_dict: dict[str, Any] = {
        "meta": {
            "tool": "lixity",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "language": resolved.key,
        },
        "provenance": {
            "project_id": snapshot.project.id,
            "source_id": source.id,
            "source_title": source.title,
            "source_version_id": version.id,
            "source_sha256": version.blob.sha256,
            "snapshot": snapshot.digest,
            "context": version.context.model_dump(),
        },
        "interpretation": {
            "scope": "source_internal",
            "context_status": "user_supplied_unverified",
            "limitations": limitations,
            "baseline_coverage": baseline_coverage,
        },
        "metrics": analysis.metrics.model_dump(),
        "style": analysis.fingerprint.passport(),
        "chapters": [c.__dict__ for c in analysis.chapters],
        "paragraphs": paragraphs_data,
    }

    context_for_dashboard = dict(version.context.model_dump())
    context_for_dashboard["source_version_id"] = version.id
    context_for_dashboard["source_id"] = source.id

    dashboard_html = render_dashboard(
        analysis.chapters,
        analysis.paragraphs,
        metrics=analysis.metrics,
        fingerprint=analysis.fingerprint,
        title=source.title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        document_context=context_for_dashboard,
        flag_min_severity=resolved_thresholds.flag_min_severity,
        controls=False,
    )

    return SourceAnalysisResult(report_dict, dashboard_html)
