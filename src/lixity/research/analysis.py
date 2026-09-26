"""Adapter connecting research repository sources and versions to the core analysis pipeline."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._version import __version__
from ..analyzer import CorpusAnalyzer
from ..config import resolve_thresholds
from ..language import resolve_language
from ..markdown_parser import split_chapters, strip_inline_markup
from ..models import SCHEMA_VERSION, CorpusConfig
from ..pipeline import analyze_document
from ..style_fingerprint import FEATURES, FingerprintThresholds, dunning_g2
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


def compare_source_to_manuscript(
    project: str | Path,
    source_id: str,
    manuscript: str | Path,
    *,
    version_id: str | None = None,
    language: str | None = None,
    top_n: int = 20,
) -> dict[str, Any]:
    """Compare verified research source against manuscript text or file.

    Evaluates lexical overlap, Dunning's G² keyness differential, stylistic/register
    contrast, and per-chapter evidence grounding.
    """
    if top_n < 1 or top_n > 100:
        raise ValueError("top_n must be between 1 and 100")

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
    source_text = raw_bytes.decode("utf-8")

    # Load manuscript text
    ms_text: str
    ms_path = Path(manuscript) if isinstance(manuscript, (str, Path)) else None
    if ms_path and ms_path.is_file():
        ms_text = ms_path.read_text(encoding="utf-8")
    elif isinstance(manuscript, str):
        if "\n" not in manuscript and ("/" in manuscript or "\\" in manuscript or manuscript.endswith((".md", ".txt"))):
            raise ResearchError(f"Manuscript file not found: {manuscript}")
        ms_text = manuscript
    else:
        raise ResearchError("Manuscript must be a file path or valid text")

    # Configure languages
    source_config = CorpusConfig(language=source.language)
    source_resolved = resolve_language(source_config, sample_text=source_text)
    source_config = source_config.model_copy(update={"language": source_resolved.key})

    ms_config = CorpusConfig(language=language) if language else CorpusConfig()
    ms_resolved = resolve_language(ms_config, sample_text=ms_text)
    ms_config = ms_config.model_copy(update={"language": ms_resolved.key})

    # Core analysis for sentence / register statistics
    source_analyzer = CorpusAnalyzer(source_config)
    source_metrics = source_analyzer.analyze_text(source_text)

    ms_analyzer = CorpusAnalyzer(ms_config)
    ms_metrics = ms_analyzer.analyze_text(ms_text)

    # Word extraction & blacklist filtering
    source_word_re = re.compile(source_resolved.word_regex)
    source_blacklist = source_resolved.function_words | source_resolved.stopwords
    source_tokens = [w.lower() for w in source_word_re.findall(strip_inline_markup(source_text))]
    source_content = [w for w in source_tokens if len(w) > 1 and w not in source_blacklist]
    source_counter = Counter(source_content)

    ms_word_re = re.compile(ms_resolved.word_regex)
    ms_blacklist = ms_resolved.function_words | ms_resolved.stopwords
    ms_tokens = [w.lower() for w in ms_word_re.findall(strip_inline_markup(ms_text))]
    ms_content = [w for w in ms_tokens if len(w) > 1 and w not in ms_blacklist]
    ms_counter = Counter(ms_content)

    source_vocab = set(source_counter.keys())
    ms_vocab = set(ms_counter.keys())
    shared_vocab = source_vocab & ms_vocab
    source_exclusive = source_vocab - ms_vocab
    ms_exclusive = ms_vocab - source_vocab
    union_vocab = source_vocab | ms_vocab

    jaccard = (len(shared_vocab) / len(union_vocab)) if union_vocab else 0.0
    min_vocab_len = min(len(source_vocab), len(ms_vocab))
    overlap_coef = (len(shared_vocab) / min_vocab_len) if min_vocab_len > 0 else 0.0

    # Top shared and exclusive terms
    top_shared = [
        {
            "word": w,
            "source_count": source_counter[w],
            "manuscript_count": ms_counter[w],
            "total_count": source_counter[w] + ms_counter[w],
        }
        for w in sorted(shared_vocab, key=lambda w: (-(source_counter[w] + ms_counter[w]), w))[:top_n]
    ]

    top_source_exclusive = [
        {"word": w, "count": source_counter[w]}
        for w in sorted(source_exclusive, key=lambda w: (-source_counter[w], w))[:top_n]
    ]

    # Keyness Differential (Dunning G²)
    total_s = sum(source_counter.values())
    total_m = sum(ms_counter.values())
    source_key_terms: list[dict[str, Any]] = []
    ms_key_terms: list[dict[str, Any]] = []

    if total_s >= 10 and total_m >= 10:
        scored: list[tuple[str, float, int, int]] = []
        for word in union_vocab:
            g2 = dunning_g2(source_counter[word], ms_counter[word], total_s, total_m)
            if g2 != 0.0:
                scored.append((word, g2, source_counter[word], ms_counter[word]))

        # Sort by signed g2: positive = over-represented in source
        scored_pos = [item for item in scored if item[1] > 0]
        scored_pos.sort(key=lambda item: (-item[1], item[0]))
        source_key_terms = [
            {"word": w, "g2": round(g2, 3), "source_count": sc, "manuscript_count": mc}
            for w, g2, sc, mc in scored_pos[:top_n]
        ]

        scored_neg = [item for item in scored if item[1] < 0]
        scored_neg.sort(key=lambda item: (item[1], item[0]))
        ms_key_terms = [
            {"word": w, "g2": round(g2, 3), "source_count": sc, "manuscript_count": mc}
            for w, g2, sc, mc in scored_neg[:top_n]
        ]

    # Register & stylistic contrast
    register_contrast = {
        "asl": {
            "source": round(source_metrics.asl, 2),
            "manuscript": round(ms_metrics.asl, 2),
            "delta": round(ms_metrics.asl - source_metrics.asl, 2),
        },
        "dialogue_pct": {
            "source": round(source_metrics.dialog_ratio, 2),
            "manuscript": round(ms_metrics.dialog_ratio, 2),
            "delta": round(ms_metrics.dialog_ratio - source_metrics.dialog_ratio, 2),
        },
        "guiraud_r": {
            "source": round(source_metrics.guiraud_r, 2),
            "manuscript": round(ms_metrics.guiraud_r, 2),
            "delta": round(ms_metrics.guiraud_r - source_metrics.guiraud_r, 2),
        },
        "yules_k": {
            "source": round(source_metrics.yules_k, 2),
            "manuscript": round(ms_metrics.yules_k, 2),
            "delta": round(ms_metrics.yules_k - source_metrics.yules_k, 2),
        },
        "staccato_pct": {
            "source": round(source_metrics.staccato_pct, 2),
            "manuscript": round(ms_metrics.staccato_pct, 2),
            "delta": round(ms_metrics.staccato_pct - source_metrics.staccato_pct, 2),
        },
        "kaskade_pct": {
            "source": round(source_metrics.kaskade_pct, 2),
            "manuscript": round(ms_metrics.kaskade_pct, 2),
            "delta": round(ms_metrics.kaskade_pct - source_metrics.kaskade_pct, 2),
        },
    }

    # Chapter Grounding / Evidence Trace
    ms_chapters = split_chapters(ms_text, ms_config)
    if not ms_chapters:
        ms_chapters = [(1, "Document", ms_text)]

    source_key_set = {item["word"] for item in source_key_terms[:10]}
    chapter_grounding: list[dict[str, Any]] = []

    for ch_num, ch_title, ch_body in ms_chapters:
        clean_body = strip_inline_markup(ch_body)
        ch_tokens = [w.lower() for w in ms_word_re.findall(clean_body)]
        ch_content = [w for w in ch_tokens if len(w) > 1 and w not in ms_blacklist]
        ch_counter = Counter(ch_content)

        ch_overlap = {w: ch_counter[w] for w in ch_counter if w in source_vocab}
        overlap_tokens = sum(ch_overlap.values())
        overlap_types = len(ch_overlap)
        grounding_density = round((overlap_tokens / len(ch_tokens) * 1000.0), 2) if ch_tokens else 0.0

        top_ch_terms = [
            {"word": w, "count": ch_overlap[w]}
            for w in sorted(ch_overlap, key=lambda w: (-ch_overlap[w], w))[:5]
        ]
        present_keys = [w for w in sorted(ch_overlap, key=lambda w: (-ch_overlap[w], w)) if w in source_key_set]

        chapter_grounding.append(
            {
                "chapter": ch_num,
                "title": ch_title,
                "words": len(ch_tokens),
                "content_words": len(ch_content),
                "overlap_types": overlap_types,
                "overlap_tokens": overlap_tokens,
                "grounding_density": grounding_density,
                "top_terms": top_ch_terms,
                "key_terms_present": present_keys,
            }
        )

    return {
        "schema_version": "research-comparison-local/1",
        "meta": {
            "tool": "lixity",
            "version": __version__,
            "source_language": source_resolved.key,
            "manuscript_language": ms_resolved.key,
        },
        "provenance": {
            "project_id": snapshot.project.id,
            "source_id": source.id,
            "source_title": source.title,
            "source_version_id": version.id,
            "source_sha256": version.blob.sha256,
            "snapshot": snapshot.digest,
        },
        "summary": {
            "source_tokens": len(source_tokens),
            "source_content_words": len(source_content),
            "manuscript_tokens": len(ms_tokens),
            "manuscript_content_words": len(ms_content),
            "source_vocabulary_types": len(source_vocab),
            "manuscript_vocabulary_types": len(ms_vocab),
            "shared_types": len(shared_vocab),
            "source_exclusive_types": len(source_exclusive),
            "manuscript_exclusive_types": len(ms_exclusive),
            "jaccard_similarity": round(jaccard, 4),
            "overlap_coefficient": round(overlap_coef, 4),
        },
        "lexical_overlap": {
            "top_shared_terms": top_shared,
            "top_source_exclusive": top_source_exclusive,
        },
        "keyness": {
            "source_key_terms": source_key_terms,
            "manuscript_key_terms": ms_key_terms,
        },
        "register_contrast": register_contrast,
        "chapter_grounding": chapter_grounding,
    }
