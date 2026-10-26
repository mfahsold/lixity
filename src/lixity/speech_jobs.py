"""Bounded native speech jobs with immutable source and explicit cancellation."""

from __future__ import annotations

import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_hex
from typing import Any

from .markdown_parser import split_chapters
from .pipeline import document_paragraph_texts, paragraph_identity, resolve_document_config
from .speech import SpeechCancelled, extract_audio_cues, render_speech_audio
from .speech_profiles import AudioProfile

MAX_AUDIO_BYTES = 200 * 1024 * 1024
MAX_RETAINED_JOBS = 4
JOB_TTL_SECONDS = 1800


def prepare_speech_source(
    text: str,
    *,
    language: str,
    mode: str,
    chapter: int,
    paragraph: Mapping[str, Any] | None = None,
    project_config: Mapping[str, Any] | None = None,
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
        if len(body) > 250000:
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
    state: str = "pending"
    done: int = 0
    total: int = 0
    message: str = ""
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


class SpeechJobs:
    """One active render per server; completed temporary files expire on access."""

    def __init__(self, *, renderer: Callable[..., Any] | None = None) -> None:
        self._render = renderer or render_speech_audio
        self._lock = threading.RLock()
        self._jobs: dict[str, _Job] = {}
        self._closed = False

    def _prune(self) -> None:
        completed = [job for job in self._jobs.values() if job.state not in ("pending", "running")]
        for job in completed:
            if (
                job.finished is not None and time.monotonic() - job.finished > JOB_TTL_SECONDS
            ) or len(self._jobs) >= MAX_RETAINED_JOBS:
                self._jobs.pop(job.identifier)
                job.storage.cleanup()

    def start(
        self,
        context_key: str,
        text: str,
        profile: AudioProfile,
        context: dict[str, Any],
        valid: Callable[[], bool],
    ) -> dict[str, Any]:
        profile = AudioProfile.model_validate(profile.model_dump())
        self.cancel_stale()
        with self._lock:
            if self._closed:
                raise RuntimeError("Speech service is closed")
            if any(job.state in ("pending", "running") for job in self._jobs.values()):
                if any(
                    job.cancel.is_set() and job.state in ("pending", "running")
                    for job in self._jobs.values()
                ):
                    raise RuntimeError(
                        "A cancelled speech segment is still finishing; wait before starting another"
                    )
                raise RuntimeError("A speech job is already active; cancel it or wait")
            self._prune()
            storage = tempfile.TemporaryDirectory(prefix="lixity-speech-job-")
            job = _Job(token_hex(16), context_key, dict(context), storage, valid)
            self._jobs[job.identifier] = job
            source = Path(storage.name) / "source.md"
            try:
                source.write_text(text, encoding="utf-8")
            except OSError:
                self._jobs.pop(job.identifier)
                storage.cleanup()
                raise
            threading.Thread(target=self._run, args=(job, source, profile), daemon=True).start()
            return self._report(job)

    def _run(self, job: _Job, source: Path, profile: AudioProfile) -> None:
        output = Path(job.storage.name) / "reading.wav"

        def progress(done: int, total: int) -> None:
            with self._lock:
                job.done, job.total = done, total

        try:
            with self._lock:
                job.state = "running"
            if not job.valid():
                with self._lock:
                    job.state = "stale"
                return
            self._render(
                source,
                output,
                profile=profile,
                progress=progress,
                cancelled=job.cancel.is_set,
                max_audio_bytes=MAX_AUDIO_BYTES,
            )
            if not output.is_file() or not 44 < output.stat().st_size <= MAX_AUDIO_BYTES:
                raise ValueError("Generated audio is missing or exceeds the download limit")
            current = job.valid()
            with self._lock:
                job.state = "cancelled" if job.cancel.is_set() else "ready" if current else "stale"
        except SpeechCancelled:
            with self._lock:
                job.state = "cancelled"
        except Exception as exc:  # noqa: BLE001 - asynchronous adapter failures must settle the job
            with self._lock:
                job.state = "cancelled" if job.cancel.is_set() else "error"
                job.message = str(exc)[:500]
        finally:
            source.unlink(missing_ok=True)
            with self._lock:
                job.finished = time.monotonic()
                if job.state != "ready" or self._closed:
                    job.storage.cleanup()

    def _find(self, identifier: str, context_key: str) -> _Job:
        self._prune()
        job = self._jobs.get(identifier)
        if job is None or job.context_key != context_key:
            raise ValueError("Speech job is unavailable in the selected context")
        return job

    @staticmethod
    def _report(job: _Job) -> dict[str, Any]:
        return {
            "id": job.identifier,
            "state": job.state,
            "done": job.done,
            "total": job.total,
            "message": job.message,
            "context": dict(job.context),
        }

    def status(self, identifier: str, context_key: str) -> dict[str, Any]:
        with self._lock:
            return self._report(self._find(identifier, context_key))

    def cancel(self, identifier: str, context_key: str) -> dict[str, Any]:
        with self._lock:
            job = self._find(identifier, context_key)
            job.cancel.set()
            if job.state == "ready":
                job.state = "cancelled"
                job.storage.cleanup()
            return self._report(job)

    def cancel_stale(self) -> None:
        with self._lock:
            candidates = list(self._jobs.values())
        for job in candidates:
            if not job.valid():
                with self._lock:
                    job.cancel.set()
                    if job.state not in ("pending", "running"):
                        job.state = "stale"
                        job.storage.cleanup()

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
            for job in self._jobs.values():
                job.cancel.set()
                if job.state not in ("pending", "running"):
                    job.storage.cleanup()
