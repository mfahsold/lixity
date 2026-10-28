"""Project-local author review decisions over exact tense-analysis observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field

from .config import read_explicit_project_config, resolve_thresholds
from .io import FileUtils
from .pipeline import paragraph_identity, profile_document, resolve_document_config
from .research.models import Digest, StrictModel
from .research.repository import Repository, ResearchConflictError
from .style_fingerprint import FingerprintThresholds
from .style_profile import flagged_paragraphs
from .workspace import resolve_manuscript_target

ReviewStatus = Literal["kept", "changed", "later"]
_MAX_STATE_BYTES = 4 * 1024 * 1024
# Marker semantics are part of the review context, even with unchanged settings.
_ANALYSIS_POLICY = "tense-review/6"
_GERMAN_LEXICAL_POLICY = "de-tense-cues/conservative-1"


class ReviewDecision(StrictModel):
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    observation_id: Digest
    source_sha256: Digest
    analysis_sha256: Digest
    status: ReviewStatus
    updated_at: str


class ReviewState(StrictModel):
    schema_version: Literal["lixity-analysis-review-state/1"] = "lixity-analysis-review-state/1"
    decisions: Annotated[list[ReviewDecision], Field(max_length=10000)] = Field(default_factory=list)


def _hash(value: Any) -> str:
    def encode(item: Any) -> str:
        if isinstance(item, (date, datetime, time)):
            return item.isoformat()
        raise TypeError(f"Unsupported analysis context type: {type(item).__name__}")

    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":"), default=encode).encode()).hexdigest()


def _read(repository: Repository) -> tuple[ReviewState, str]:
    path = repository.safe(repository.root / ".lixity" / "analysis-review.json")
    try:
        raw = repository.read(path, maximum=_MAX_STATE_BYTES)
    except FileNotFoundError:
        return ReviewState(), hashlib.sha256(b"").hexdigest()
    state = ReviewState.model_validate_json(raw)
    keys = [(item.source_path, item.observation_id) for item in state.decisions]
    if len(keys) != len(set(keys)):
        raise ValueError("Analysis review state repeats an observation identity")
    return state, hashlib.sha256(raw).hexdigest()


def review_analysis(project: str | Path, *, manuscript: str | Path | None = None,
                    language: str | None = None, thresholds: FingerprintThresholds | None = None,
                    tense_model: str | None = None, tense_scope: str | None = None) -> dict[str, Any]:
    """Read current observations and classify prior decisions without writing."""
    workspace = resolve_manuscript_target(str(manuscript) if manuscript is not None else None, project=project)
    root = Path(workspace.root).resolve()
    source = Path(workspace.manuscript).resolve()
    relative = source.relative_to(root).as_posix()
    repository = Repository(root)
    settings = read_explicit_project_config(root)
    text, source_hash = FileUtils.read_source_snapshot(str(source))
    overrides = {key: value for key, value in (("tense_model", tense_model), ("tense_scope", tense_scope))
                 if value is not None}
    config, resolved = resolve_document_config(text, language or settings.get("language", "en"),
                                              project_config=settings, **overrides)
    effective = thresholds or resolve_thresholds(project_config=settings)
    paragraphs, _chapters = profile_document(text, config, effective)
    linguistic_identity = None
    if config.tense_model is not None:
        from .grammatical_tense import model_identity

        linguistic_identity = model_identity(config.tense_model)
    analysis_context = {"policy": _ANALYSIS_POLICY, "config": config.model_dump(mode="json"),
                        "thresholds": asdict(effective), "linguistics": linguistic_identity}
    if (resolved.key == "de" and config.tense_model is None and _GERMAN_LEXICAL_POLICY is not None
            and (config.praesens_regex is None or config.praeteritum_regex is None)):
        analysis_context["lexical_policy"] = _GERMAN_LEXICAL_POLICY
    analysis_hash = _hash(analysis_context)
    state, state_hash = _read(repository)
    saved = {item.observation_id: item for item in state.decisions if item.source_path == relative}
    observations = []
    for paragraph in flagged_paragraphs(paragraphs, min_severity=effective.flag_min_severity):
        identity = paragraph_identity(paragraph)
        observation_id = _hash({"source_path": relative, **identity})
        previous = saved.get(observation_id)
        stale = bool(previous and (previous.source_sha256 != source_hash or previous.analysis_sha256 != analysis_hash))
        observations.append({"id": observation_id, **identity, "chapter": paragraph.chapter_num,
            "chapter_title": paragraph.chapter_title, "severity": paragraph.severity,
            "present_hits": paragraph.present_hits, "past_hits": paragraph.past_hits,
            "switch": paragraph.switch, "mixed": paragraph.mixed,
            "status": "stale" if stale else previous.status if previous else "unreviewed",
            "previous_status": previous.status if previous else None})
    current_ids = {row["id"] for row in observations}
    return {"schema_version": "lixity-analysis-review/1", "source_path": relative,
            "source_sha256": source_hash, "analysis_sha256": analysis_hash, "review_sha256": state_hash,
            "project_settings_sha256": _hash(settings),
            "language": resolved.key, "observations": observations,
            "unmatched_decisions": sum(key not in current_ids for key in saved),
            "completed": sum(row["status"] in ("kept", "changed") for row in observations),
            "total": len(observations)}


def record_analysis_review(project: str | Path, observation_id: str, status: ReviewStatus, *,
                           expected_source_sha256: str, expected_analysis_sha256: str,
                           expected_review_sha256: str, manuscript: str | Path | None = None,
                           language: str | None = None,
                           thresholds: FingerprintThresholds | None = None,
                           tense_model: str | None = None, tense_scope: str | None = None) -> dict[str, Any]:
    """Save an author assertion, not a verified manuscript edit, under explicit guards."""
    repository = Repository(project)
    with repository.locked():
        current = review_analysis(project, manuscript=manuscript, language=language, thresholds=thresholds,
                                  tense_model=tense_model, tense_scope=tense_scope)
        for name, expected in (("source_sha256", expected_source_sha256), ("analysis_sha256", expected_analysis_sha256),
                               ("review_sha256", expected_review_sha256)):
            if current[name] != expected:
                raise ResearchConflictError("Manuscript, analysis settings or review decisions changed; reload before saving")
        if not any(item["id"] == observation_id for item in current["observations"]):
            raise ValueError("Review requires an observation from the current tense analysis")
        previous, _digest = _read(repository)
        decision = ReviewDecision(source_path=current["source_path"], observation_id=observation_id,
            source_sha256=current["source_sha256"], analysis_sha256=current["analysis_sha256"],
            status=status, updated_at=datetime.now(timezone.utc).isoformat())
        state = ReviewState(decisions=[item for item in previous.decisions
            if (item.source_path, item.observation_id) != (decision.source_path, observation_id)] + [decision])
        raw = state.model_dump_json().encode("utf-8")
        if len(raw) > _MAX_STATE_BYTES:
            raise ValueError("Analysis review state exceeds the 4 MiB limit")
        target = repository.safe(repository.root / ".lixity" / "analysis-review.json")
        source = repository.safe(repository.root / current["source_path"])
        def check() -> None:
            if (FileUtils.read_source_snapshot(str(source))[1] != expected_source_sha256
                    or _hash(read_explicit_project_config(repository.root)) != current["project_settings_sha256"]
                    or _read(repository)[1] != expected_review_sha256):
                raise ResearchConflictError("Manuscript, analysis or review decisions changed before publication")

        FileUtils.atomic_write_bytes_if_changed(str(target), raw, before_replace=check)
    observations = [{**item, "status": status, "previous_status": status} if item["id"] == observation_id else item
                    for item in current["observations"]]
    return {**current, "review_sha256": hashlib.sha256(raw).hexdigest(), "observations": observations,
            "completed": sum(item["status"] in ("kept", "changed") for item in observations)}
