"""Bounded native speech jobs with immutable source and explicit cancellation."""

from __future__ import annotations

import logging
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_hex
from typing import TYPE_CHECKING, Any, Literal

from .log import (
    get_logger,
    log_event,
    new_speech_diagnostic_id,
    speech_diagnostic_id,
    speech_diagnostic_scope,
)
from .markdown_parser import split_chapters
from .pipeline import document_paragraph_texts, paragraph_identity, resolve_document_config
from .speech import SpeechCancelled, extract_audio_cues, render_speech_audio
from .speech_direction import SpeechSegment
from .speech_profiles import AudioProfile

if TYPE_CHECKING:
    from .speech_references import SpeechReference

MAX_AUDIO_BYTES = 200 * 1024 * 1024
MAX_RETAINED_JOBS = 4
MAX_PENDING_JOBS = 3
JOB_TTL_SECONDS = 1800
SpeechStaleReason = Literal["context", "workspace_closed", "settings_changed", "direction_changed",
                            "reference_changed", "source_changed", "workspace_refreshed", "context_unavailable"]


def prepare_speech_source(
    text: str,
    *,
    language: str,
    mode: str,
    chapter: int,
    paragraph: Mapping[str, Any] | None = None,
    project_config: Mapping[str, Any] | None = None,
    for_export: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Select actual manuscript prose, verifying a requested displayed anchor."""
    if mode not in ("preview", "chapter") or type(chapter) is not int or chapter < 1:
        raise ValueError("Choose a valid speech mode and chapter")
    config, _resolved = resolve_document_config(text, language, project_config=project_config)
    chapters = split_chapters(text, config) or [(1, "", text)]
    selected = next((row for row in chapters if row[0] == chapter), None)
    if selected is None:
        raise ValueError("Choose an existing chapter")
    number, title, body = selected
    context: dict[str, Any] = {"mode": mode, "chapter": number, "title": title}
    if mode == "chapter":
        if paragraph is not None:
            raise ValueError("A paragraph selection is only valid for previews")
        if not for_export and len(body) > 250000:
            raise ValueError("Chapter exceeds the native audio limit; use the CLI")
        return f"## {title}\n\n{body}" if title else body, context
    if paragraph is not None:
        keys = {"start_line", "end_line", "paragraph_sha256"}
        if set(paragraph) != keys:
            raise ValueError("Supply one exact displayed paragraph identity")
        matches = [
            item
            for item in document_paragraph_texts(text, config)
            if paragraph_identity(item) == dict(paragraph)
        ]
        if len(matches) != 1:
            raise ValueError("The selected paragraph changed; choose it again")
        item = matches[0]
        if item.chapter_num not in (0, chapter):
            raise ValueError("The selected paragraph belongs to another chapter")
        body = item.text
        context.update(paragraph_identity(item))
    cues = [
        cue
        for cue in extract_audio_cues(body, language=config.language)
        if cue.text and cue.kind not in ("heading", "scene_break")
    ]
    if not cues:
        raise ValueError("The selected passage has no supported spoken prose")
    context.update(excerpt=cues[0].text, truncated=len(cues) > 1)
    return cues[0].text, context


@dataclass
class _Job:
    identifier: str
    context_key: str
    context: dict[str, Any]
    storage: tempfile.TemporaryDirectory[str]
    valid: Callable[[], bool]
    diagnostic_id: str
    cache_dir: Path | None = None
    fresh_audio: bool = False
    target: str = "local"
    plan: list[SpeechSegment] | None = None
    references: dict[str, SpeechReference] = field(default_factory=dict, repr=False)
    state: str = "pending"
    done: int = 0
    total: int = 0
    message: str = ""
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None
    last_reported_terminal_state: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    retain: Callable[[Path, Callable[[], bool]], None] | None = field(default=None, repr=False)
    stale_reason: Callable[[], SpeechStaleReason | None] | None = field(default=None, repr=False)

    def invalid_reason(self) -> SpeechStaleReason | None:
        if self.stale_reason is not None:
            return self.stale_reason()
        return None if self.valid() else "context"


class SpeechJobs:
    """One bounded FIFO per app; projects share a single active renderer."""

    def __init__(self, *, renderer: Callable[..., Any] | None = None) -> None:
        self._render = renderer or render_speech_audio
        self._lock = threading.RLock()
        self._jobs: dict[str, _Job] = {}
        self._condition = threading.Condition(self._lock)
        self._pending: list[str] = []
        self._active: str | None = None
        self._closed = False
        self._log = get_logger("speech.jobs")

    def _prune(self) -> None:
        completed = [job for job in self._jobs.values() if job.state not in ("pending", "running")]
        excess = max(0, len(completed) - MAX_RETAINED_JOBS)
        for index, job in enumerate(completed):
            expired = (
                job.finished is not None and time.monotonic() - job.finished > JOB_TTL_SECONDS
            )
            if (expired or index < excess) and self._cleanup(job):
                self._jobs.pop(job.identifier)

    def _cleanup(self, job: _Job) -> bool:
        """Remove temporary files without exposing filesystem errors to diagnostics."""
        try:
            job.storage.cleanup()
        except OSError:
            job.state = "error"
            job.message = "Could not remove temporary speech files"
            log_event(self._log, "audio_job", logging.WARNING, id=job.diagnostic_id,
                      stage="cleanup", status="failed", category="io")
            return False
        return True

    def start(
        self,
        context_key: str,
        text: str,
        profile: AudioProfile,
        context: dict[str, Any],
        valid: Callable[[], bool],
        *,
        cache_dir: Path | None = None,
        fresh_audio: bool = False,
        target: str = "local",
        plan: list[SpeechSegment] | None = None,
        references: Mapping[str, SpeechReference] | None = None,
        retain: Callable[[Path, Callable[[], bool]], None] | None = None,
        stale_reason: Callable[[], SpeechStaleReason | None] | None = None,
    ) -> dict[str, Any]:
        profile = AudioProfile.model_validate(profile.model_dump())
        self.cancel_stale()
        with self._lock:
            if self._closed:
                raise RuntimeError("Speech service is closed")
            active = [job for job in self._jobs.values() if job.state in ("pending", "running")]
            if any(job.context_key == context_key for job in active):
                raise RuntimeError("A speech job is already active for this project; cancel it or wait")
            if len(active) >= MAX_PENDING_JOBS + 1:
                raise RuntimeError("The audio queue is full; wait before submitting another job")
            self._prune()
            storage = tempfile.TemporaryDirectory(prefix="lixity-speech-job-")
            job = _Job(
                token_hex(16), context_key, dict(context), storage, valid,
                diagnostic_id=speech_diagnostic_id() or new_speech_diagnostic_id(),
                cache_dir=cache_dir, fresh_audio=fresh_audio, target=target,
                stale_reason=stale_reason,
            )
            job.plan = [SpeechSegment(p.text, AudioProfile.model_validate(p.profile.model_dump()), p.pause_before, p.pause_after, dict(p.anchor) if p.anchor else None) for p in plan] if plan is not None else None
            job.references = dict(references or {})
            job.retain = retain
            self._jobs[job.identifier] = job
            source = Path(storage.name) / "source.md"
            try:
                source.write_text(text, encoding="utf-8")
            except OSError:
                job.finished = time.monotonic()
                if self._cleanup(job):
                    self._jobs.pop(job.identifier)
                raise
            self._pending.append(job.identifier)
            mode = job.context.get("mode")
            safe_mode = mode if isinstance(mode, str) and mode in ("preview", "chapter") else "unknown"
            safe_target = job.target if job.target in ("local", "jetson") else "unknown"
            log_event(self._log, "audio_job", id=job.diagnostic_id, stage="queued", mode=safe_mode, target=safe_target)
            threading.Thread(target=self._run, args=(job, source, profile), daemon=True).start()
            return self._report(job)

    def _run(self, job: _Job, source: Path, profile: AudioProfile) -> None:
        with speech_diagnostic_scope(job.diagnostic_id):
            self._run_scoped(job, source, profile)

    def _run_scoped(self, job: _Job, source: Path, profile: AudioProfile) -> None:
        output = Path(job.storage.name) / "reading.wav"
        category = "none"
        invalid_reason: SpeechStaleReason | None = None
        retained = False
        terminal_state = "error"
        terminal_message = ""

        def progress(done: int, total: int) -> None:
            with self._lock:
                job.done, job.total = done, total

        try:
            with self._condition:
                self._condition.wait_for(lambda: job.cancel.is_set() or self._closed or
                                         (self._active is None and self._pending[0] == job.identifier))
                if job.cancel.is_set() or self._closed:
                    raise SpeechCancelled()
                self._pending.remove(job.identifier)
                self._active = job.identifier
                job.state = "running"
                log_event(self._log, "audio_job", stage="running")
            if not job.valid():
                terminal_state = "stale"
                return
            options: dict[str, Any] = {
                "profile": profile, "progress": progress, "cancelled": job.cancel.is_set,
                "max_audio_bytes": MAX_AUDIO_BYTES, "target": job.target,
            }
            if job.plan is not None:
                options["plan"] = job.plan
            if job.references:
                options["references"] = job.references
            if job.cache_dir is not None:
                options["cache_dir"] = job.cache_dir
                options["fresh_audio"] = job.fresh_audio
            self._render(source, output, **options)
            if not output.is_file() or not 44 < output.stat().st_size <= MAX_AUDIO_BYTES:
                raise ValueError("Generated audio is missing or exceeds the download limit")
            invalid_reason = job.invalid_reason()
            if invalid_reason is None and not job.cancel.is_set() and job.context.get("mode") == "chapter" and job.retain is not None:
                job.retain(output, lambda: not job.cancel.is_set() and job.valid())
                retained = True
                invalid_reason = job.invalid_reason()
            terminal_state = "cancelled" if job.cancel.is_set() else "ready" if invalid_reason is None else "stale"
        except SpeechCancelled:
            category = "cancelled"
            terminal_state = "cancelled"
        except Exception as exc:  # noqa: BLE001 - asynchronous adapter failures must settle the job
            category = ("io" if isinstance(exc, OSError) else "validation" if isinstance(exc, ValueError)
                        else "runtime" if isinstance(exc, RuntimeError) else "unexpected")
            terminal_state = "cancelled" if job.cancel.is_set() else "error"
            terminal_message = str(exc)[:500]
        finally:
            try:
                source.unlink(missing_ok=True)
            except OSError:
                category = "cleanup"
                terminal_state = "error"
                terminal_message = "Could not remove the temporary speech source"
            with self._lock:
                # A terminal report also settles temporary source ownership.
                # Cancellation may arrive while the source cleanup is in flight.
                job.state = "cancelled" if terminal_state == "ready" and job.cancel.is_set() else terminal_state
                job.message = terminal_message
                if job.identifier in self._pending:
                    self._pending.remove(job.identifier)
                if self._active == job.identifier:
                    self._active = None
                self._condition.notify_all()
                if (job.state != "ready" or self._closed) and not self._cleanup(job):
                    category = "cleanup"
                job.finished = time.monotonic()
                log_event(self._log, "audio_job", stage="finished", status=job.state, category=category,
                          retained=retained, reason=invalid_reason,
                          duration_ms=int((job.finished - job.created) * 1000))

    def _find(self, identifier: str, context_key: str) -> _Job:
        self._prune()
        job = self._jobs.get(identifier)
        if job is None or job.context_key != context_key:
            raise ValueError("Speech job is unavailable in the selected context")
        return job

    def _report(self, job: _Job) -> dict[str, Any]:
        return {
            "id": job.identifier,
            "queue_position": self._pending.index(job.identifier) + 1 if job.identifier in self._pending else 0,
            "state": job.state,
            "done": job.done,
            "total": job.total,
            "message": job.message,
            "context": dict(job.context),
        }

    def status(self, identifier: str, context_key: str) -> dict[str, Any]:
        with self._lock:
            job = self._find(identifier, context_key)
            if job.state not in ("pending", "running") and job.state != job.last_reported_terminal_state:
                job.last_reported_terminal_state = job.state
                log_event(self._log, "audio_job", id=job.diagnostic_id, stage="status_read", status=job.state)
            return self._report(job)

    def cancel(self, identifier: str, context_key: str) -> dict[str, Any]:
        with self._lock:
            job = self._find(identifier, context_key)
            job.cancel.set()
            self._condition.notify_all()
            log_event(self._log, "audio_job", id=job.diagnostic_id, stage="cancel_requested")
            if job.state == "ready":
                job.state = "cancelled"
                self._cleanup(job)
                log_event(self._log, "audio_job", id=job.diagnostic_id, stage="invalidated",
                          status=job.state, reason="cancel")
            return self._report(job)

    def cancel_stale(self) -> None:
        with self._lock:
            candidates = list(self._jobs.values())
        for job in candidates:
            reason = job.invalid_reason()
            if reason is not None:
                with self._lock:
                    was_cancelled = job.cancel.is_set()
                    job.cancel.set()
                    self._condition.notify_all()
                    if not was_cancelled:
                        log_event(self._log, "audio_job", id=job.diagnostic_id, stage="stale_requested", reason=reason)
                    if job.state not in ("pending", "running"):
                        was_stale = job.state == "stale"
                        job.state = "stale"
                        self._cleanup(job)
                        if not was_stale:
                            log_event(self._log, "audio_job", id=job.diagnostic_id, stage="invalidated",
                                      status=job.state, reason=reason)

    def audio(self, identifier: str, context_key: str) -> bytes:
        with self._lock:
            job = self._find(identifier, context_key)
        current = job.valid()
        with self._lock:
            if job.state != "ready" or not current:
                raise ValueError("Speech audio is not ready or its source/settings changed")
            path = Path(job.storage.name) / "reading.wav"
            if path.stat().st_size > MAX_AUDIO_BYTES:
                raise ValueError("Speech audio exceeds the download limit")
            return path.read_bytes()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._condition.notify_all()
            for job in self._jobs.values():
                job.cancel.set()
                if job.state not in ("pending", "running"):
                    self._cleanup(job)

    def overview(self) -> list[dict[str, Any]]:
        """Content-free operational observations, never manuscript/job bindings."""
        with self._lock:
            self._prune()
            return [{"state": job.state, "target": job.target,
                     "done": job.done, "total": job.total,
                     "queue_position": self._report(job)["queue_position"]}
                    for job in self._jobs.values()]
