"""Adapter connecting research repository sources and versions to the core analysis pipeline."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .._version import __version__
from ..analyzer import CorpusAnalyzer
from ..config import THRESHOLD_KEYS, resolve_thresholds
from ..language import compile_word_pattern, resolve_language
from ..markdown_parser import before_appendix, chapter_heading_spans, prose_text, split_chapters
from ..models import SCHEMA_VERSION, CorpusConfig
from ..pipeline import analyze_document
from ..style_fingerprint import FEATURES, FingerprintThresholds, dunning_g2
from ..ui import render_analysis
from ..ui.manuscript_document import reader_blocks
from ..ui.render_contracts import AnalysisIdentity, DashboardContent, DashboardOptions
from .models import Extraction, Passage, Reference, Source, SourceVersion, Tombstone
from .repository import Repository, ResearchError, Snapshot

_ALLOWED_THRESHOLDS = frozenset(THRESHOLD_KEYS)


def _source_text(repository: Repository, snapshot: Snapshot, version: SourceVersion) -> str:
    if version.blob.media_type not in ("text/plain", "application/pdf"):
        raise ResearchError("Image/video sources are unavailable to textual analysis or comparison")
    content = repository.read_blob(version.blob)
    if version.blob.media_type == "application/pdf":
        extraction = next((record for record in snapshot.records.values()
                           if isinstance(record, Extraction) and record.source_version_ref.id == version.id), None)
        if extraction is None:
            raise ResearchError("Retained PDF has no extracted text; ingest with extraction before textual analysis")
        content = repository.read_blob(extraction.text_blob)
    return content.decode("utf-8")


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

    text = _source_text(repository, snapshot, version)

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
        limitations.append("original_language_supplied")

    estimable = sum(
        1
        for b in analysis.fingerprint.baseline.values()
        if b.get("comparison_status") == "available"
    )
    baseline_coverage = {
        "total_features": len(FEATURES),
        "estimable_features": estimable,
    }

    identity = AnalysisIdentity(
        scope="source_internal", context_status="user_supplied_unverified",
        source_id=source.id, source_version_id=version.id,
    )
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
            "scope": identity.scope,
            "context_status": identity.context_status,
            "limitations": limitations,
            "baseline_coverage": baseline_coverage,
        },
        "metrics": analysis.metrics.model_dump(),
        "style": analysis.fingerprint.passport(),
        "chapters": [c.__dict__ for c in analysis.chapters],
        "paragraphs": paragraphs_data,
    }

    context_for_dashboard = dict(version.context.model_dump())

    dashboard_html = render_analysis(
        analysis,
        resolved,
        title=source.title,
        flag_min_severity=resolved_thresholds.flag_min_severity,
        content=DashboardContent(
            reader_document=reader_blocks(text, config, analysis.paragraphs),
            document_context=context_for_dashboard,
            identity=identity,
        ),
        options=DashboardOptions(
            controls=False,
        ),
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
    contrast, and per-chapter evidence grounding. Returns the plain result
    dictionary; use `format_compare_markdown` to render it.
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

    source_text = _source_text(repository, snapshot, version)

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

    # The comparison uses chapter prose where chapters exist. This is the same
    # body segmentation used for the chapter trace, so titles, front matter,
    # and the configured scholarly appendix cannot inflate lexical overlap.
    def comparison_prose(text: str, config: CorpusConfig) -> tuple[list[tuple[int, str, str]], str]:
        main_text = before_appendix(text, config)
        headings = chapter_heading_spans(main_text, config)
        chapters = split_chapters(main_text[headings[0][0]:], config) if headings else []
        bodies = [body for _, _, body in chapters] if chapters else [main_text]
        prose = "\n\n".join(prose_text(body, _front_matter=not chapters) for body in bodies)
        return chapters, prose

    _, source_prose = comparison_prose(source_text, source_config)
    ms_chapters, ms_prose = comparison_prose(ms_text, ms_config)

    # Core analysis for sentence / register statistics
    source_analyzer = CorpusAnalyzer(source_config)
    source_metrics = source_analyzer.analyze_text(source_prose)

    ms_analyzer = CorpusAnalyzer(ms_config)
    ms_metrics = ms_analyzer.analyze_text(ms_prose)

    # Word extraction & blacklist filtering
    source_word_re = compile_word_pattern(source_resolved.word_regex)
    source_blacklist = source_resolved.function_words | source_resolved.stopwords
    source_tokens = [w.lower() for w in source_word_re.findall(source_prose)]
    source_content = [w for w in source_tokens if len(w) > 1 and w not in source_blacklist]
    source_counter = Counter(source_content)

    ms_word_re = compile_word_pattern(ms_resolved.word_regex)
    ms_blacklist = ms_resolved.function_words | ms_resolved.stopwords
    ms_tokens = [w.lower() for w in ms_word_re.findall(ms_prose)]
    ms_content = [w for w in ms_tokens if len(w) > 1 and w not in ms_blacklist]
    ms_counter = Counter(ms_content)

    source_vocab = set(source_counter.keys())
    ms_vocab = set(ms_counter.keys())
    comparable = source_resolved.key == ms_resolved.key

    shared_vocab = (source_vocab & ms_vocab) if comparable else set()
    source_exclusive = (source_vocab - ms_vocab) if comparable else set()
    ms_exclusive = (ms_vocab - source_vocab) if comparable else set()
    union_vocab = (source_vocab | ms_vocab) if comparable else set()

    jaccard: float | None = None
    overlap_coef: float | None = None
    top_shared: list[dict[str, Any]] = []
    top_source_exclusive: list[dict[str, Any]] = []
    source_key_terms: list[dict[str, Any]] = []
    ms_key_terms: list[dict[str, Any]] = []

    if comparable:
        jaccard = round((len(shared_vocab) / len(union_vocab)) if union_vocab else 0.0, 4)
        min_vocab_len = min(len(source_vocab), len(ms_vocab))
        overlap_coef = round((len(shared_vocab) / min_vocab_len) if min_vocab_len > 0 else 0.0, 4)

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

    def _register_entry(source_val: float, ms_val: float) -> dict[str, float | None]:
        return {
            "source": round(source_val, 2),
            "manuscript": round(ms_val, 2),
            "delta": round(ms_val - source_val, 2) if comparable else None,
        }

    # Register & stylistic contrast
    register_contrast = {
        "asl": _register_entry(source_metrics.asl, ms_metrics.asl),
        "dialogue_pct": _register_entry(source_metrics.dialog_ratio, ms_metrics.dialog_ratio),
        "guiraud_r": _register_entry(source_metrics.guiraud_r, ms_metrics.guiraud_r),
        "yules_k": _register_entry(source_metrics.yules_k, ms_metrics.yules_k),
        "staccato_pct": _register_entry(source_metrics.staccato_pct, ms_metrics.staccato_pct),
        "kaskade_pct": _register_entry(source_metrics.kaskade_pct, ms_metrics.kaskade_pct),
    }

    # Chapter Grounding / Evidence Trace
    if not ms_chapters:
        ms_chapters = [(1, "Document", ms_prose)]

    source_key_set = {item["word"] for item in source_key_terms[:10]}
    chapter_grounding: list[dict[str, Any]] = []

    for ch_num, ch_title, ch_body in ms_chapters:
        clean_body = prose_text(ch_body, _front_matter=False)
        ch_tokens = [w.lower() for w in ms_word_re.findall(clean_body)]
        ch_content = [w for w in ch_tokens if len(w) > 1 and w not in ms_blacklist]
        if comparable:
            ch_counter = Counter(ch_content)
            ch_overlap = {w: ch_counter[w] for w in ch_counter if w in source_vocab}
            overlap_tokens_count = sum(ch_overlap.values())
            overlap_tokens: int | None = overlap_tokens_count
            overlap_types: int | None = len(ch_overlap)
            grounding_density: float | None = (
                round((overlap_tokens_count / len(ch_tokens) * 1000.0), 2) if ch_tokens else 0.0
            )
            top_ch_terms = [
                {"word": w, "count": ch_overlap[w]}
                for w in sorted(ch_overlap, key=lambda w: (-ch_overlap[w], w))[:5]
            ]
            present_keys = [
                w for w in sorted(ch_overlap, key=lambda w: (-ch_overlap[w], w)) if w in source_key_set
            ]
        else:
            overlap_types = None
            overlap_tokens = None
            grounding_density = None
            top_ch_terms = []
            present_keys = []

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

    result: dict[str, Any] = {
        "schema_version": "research-comparison-local/2",
        "meta": {
            "tool": "lixity",
            "version": __version__,
            "source_language": source_resolved.key,
            "manuscript_language": ms_resolved.key,
            "lexical_comparable": comparable,
        },
        "comparison_limits": (
            [] if comparable else ["cross_language_lexical_comparison"]
        ),
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
            "shared_types": len(shared_vocab) if comparable else None,
            "source_exclusive_types": len(source_exclusive) if comparable else None,
            "manuscript_exclusive_types": len(ms_exclusive) if comparable else None,
            "jaccard_similarity": jaccard,
            "overlap_coefficient": overlap_coef,
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

    return result


def format_compare_markdown(data: dict[str, Any]) -> str:
    """Format cross-corpus comparison dictionary as Markdown."""
    prov = data.get("provenance", {})
    summary = data.get("summary", {})
    meta = data.get("meta", {})
    source_title = prov.get("source_title", "Research Source")
    source_id = prov.get("source_id", "")

    lines = [
        f"# Cross-Corpus Grounding Report: {source_title} vs Manuscript",
        "",
        f"- **Source ID:** `{source_id}` (version `{prov.get('source_version_id', '')}`)",
        f"- **Source Language:** `{meta.get('source_language', '')}` · **Manuscript Language:** `{meta.get('manuscript_language', '')}`",
        f"- **Lexically Comparable:** `{'Yes' if meta.get('lexical_comparable') else 'No (cross-language)'}`",
    ]
    if data.get("comparison_limits"):
        lines.append(f"- **Limitations:** {', '.join(data['comparison_limits'])}")
    lines.append("")

    shared_types = summary.get("shared_types")
    shared_str = f"{shared_types:,} shared" if shared_types is not None else "–"
    jaccard_val = summary.get("jaccard_similarity")
    jaccard_str = f"{jaccard_val:.4f}" if jaccard_val is not None else "–"
    overlap_val = summary.get("overlap_coefficient")
    overlap_str = f"{overlap_val:.4f}" if overlap_val is not None else "–"

    lines.extend([
        "## Summary Metrics",
        "",
        "| Metric | Source | Manuscript | Overlap / Similarity |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Total Tokens** | {summary.get('source_tokens', 0):,} | {summary.get('manuscript_tokens', 0):,} | – |",
        f"| **Content Words** | {summary.get('source_content_words', 0):,} | {summary.get('manuscript_content_words', 0):,} | – |",
        f"| **Vocabulary Types** | {summary.get('source_vocabulary_types', 0):,} | {summary.get('manuscript_vocabulary_types', 0):,} | {shared_str} |",
        f"| **Jaccard Similarity** | – | – | {jaccard_str} |",
        f"| **Overlap Coefficient** | – | – | {overlap_str} |",
        "",
    ])

    reg = data.get("register_contrast", {})
    if reg:
        lines.extend([
            "## Register & Stylistic Contrast",
            "",
            "| Feature | Source | Manuscript | Delta (MS - Source) |",
            "| :--- | :--- | :--- | :--- |",
        ])
        labels = {
            "asl": "Average Sentence Length (ASL)",
            "dialogue_pct": "Dialogue Ratio",
            "guiraud_r": "Guiraud R (Richness)",
            "yules_k": "Yule's K (Concentration)",
            "staccato_pct": "Staccato Sentences (%)",
            "kaskade_pct": "Cascade Sentences (%)",
        }
        for k, lbl in labels.items():
            if k in reg:
                item = reg[k]
                src_v = item.get("source")
                ms_v = item.get("manuscript")
                delta_v = item.get("delta")
                src_s = "–" if src_v is None else str(src_v)
                ms_s = "–" if ms_v is None else str(ms_v)
                delta_s = "–" if delta_v is None else f"{delta_v:+g}"
                lines.append(f"| **{lbl}** | {src_s} | {ms_s} | {delta_s} |")
        lines.append("")

    keyness = data.get("keyness", {})
    source_keys = keyness.get("source_key_terms", [])
    ms_keys = keyness.get("manuscript_key_terms", [])
    if source_keys or ms_keys:
        lines.extend([
            "## Distinctive Key Terms (Dunning G²)",
            "",
            "### Over-represented in Research Source",
            "",
            "| Term | G² Score | Source Count | Manuscript Count |",
            "| :--- | :--- | :--- | :--- |",
        ])
        if not source_keys:
            lines.append("| *(none)* | – | – | – |")
        else:
            lines.extend(
                f"| **{item['word']}** | {item['g2']} | {item['source_count']} | {item['manuscript_count']} |"
                for item in source_keys[:10]
            )
        lines.append("")

        lines.extend([
            "### Over-represented in Manuscript",
            "",
            "| Term | G² Score | Manuscript Count | Source Count |",
            "| :--- | :--- | :--- | :--- |",
        ])
        if not ms_keys:
            lines.append("| *(none)* | – | – | – |")
        else:
            lines.extend(
                f"| **{item['word']}** | {item['g2']} | {item['manuscript_count']} | {item['source_count']} |"
                for item in ms_keys[:10]
            )
        lines.append("")

    chapters = data.get("chapter_grounding", [])
    if chapters:
        lines.extend([
            "## Chapter Grounding Trace",
            "",
            "| Chapter | Title | Words | Overlap Types | Density (‰) | Key Terms Grounded |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for ch in chapters:
            key_terms = ", ".join(ch.get("key_terms_present") or []) or "–"
            ov_types = ch.get("overlap_types")
            ov_tokens = ch.get("overlap_tokens")
            overlap_str = (
                f"{ov_types} ({ov_tokens} tok)"
                if ov_types is not None and ov_tokens is not None
                else "–"
            )
            density = ch.get("grounding_density")
            density_str = f"{density:.1f}‰" if density is not None else "–"
            lines.append(
                f"| {ch.get('chapter', 1)} | {ch.get('title', 'Chapter')} | {ch.get('words', 0):,} | "
                f"{overlap_str} | {density_str} | {key_terms} |"
            )
        lines.append("")

    return "\n".join(lines) + "\n"
