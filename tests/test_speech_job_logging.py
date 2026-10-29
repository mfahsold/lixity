"""Content-free diagnostics for concurrent and cancelled synthetic speech jobs."""

import logging
import re
import tempfile
import threading
import time
from pathlib import Path

import pytest

from lixity.log import get_logger, speech_diagnostic_id, speech_diagnostic_scope
from lixity.speech import SpeechCancelled
from lixity.speech_jobs import SpeechJobs
from lixity.speech_profiles import AudioProfile


@pytest.fixture
def events(monkeypatch):
    logger = get_logger("speech.jobs")
    records = []
    monkeypatch.setattr(logger, "info", lambda template, *args: records.append(template % args))
    monkeypatch.setattr(logger, "warning", lambda template, *args: records.append(template % args))
    monkeypatch.setattr(logger, "getEffectiveLevel", lambda: logging.INFO)
    return records


def wait_for(events, text):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if any(text in line for line in events):
            return
        time.sleep(.01)
    pytest.fail(f"Missing speech job diagnostic: {text}")


def test_job_logs_are_correlated_and_do_not_expose_private_material(events):
    def render(source, output, **kwargs):
        output.write_bytes(b"X" * 60)

    jobs = SpeechJobs(renderer=render)
    try:
        response = jobs.start("PRIVATE_CONTEXT", "PRIVATE_MANUSCRIPT", AudioProfile(),
                              {"mode": "preview", "title": "PRIVATE_TITLE"}, lambda: True)
        wait_for(events, "stage=finished")
        queued = next(line for line in events if "stage=queued" in line)
        running = next(line for line in events if "stage=running" in line)
        finished = next(line for line in events if "stage=finished" in line)
        ids = [re.search(r"\bid=([0-9a-f]{16})\b", line).group(1) for line in (queued, running, finished)]
        assert len(set(ids)) == 1
        assert ids[0] != response["id"]
        assert "status=ready" in finished and "duration_ms=" in finished
        assert all("PRIVATE_" not in line and response["id"] not in line for line in events)
    finally:
        jobs.close()


def test_cancelled_job_and_error_do_not_log_exception_content(events):
    def failing(source, output, **kwargs):
        raise RuntimeError("PRIVATE_EXCEPTION_AND_PATH")

    jobs = SpeechJobs(renderer=failing)
    try:
        jobs.start("a", "PRIVATE_MANUSCRIPT", AudioProfile(), {"mode": "chapter"}, lambda: True)
        wait_for(events, "status=error")
        assert all("PRIVATE_" not in line for line in events)
    finally:
        jobs.close()
    events.clear()
    started = threading.Event()
    release = threading.Event()

    def cancelling(source, output, **kwargs):
        started.set()
        release.wait(3)
        raise SpeechCancelled()

    jobs = SpeechJobs(renderer=cancelling)
    try:
        response = jobs.start("b", "PRIVATE_MANUSCRIPT", AudioProfile(), {"mode": "preview"}, lambda: True)
        assert started.wait(3)
        jobs.cancel(response["id"], "b")
        release.set()
        wait_for(events, "status=cancelled")
    finally:
        release.set()
        jobs.close()


def test_jobs_use_distinct_non_public_diagnostic_ids(events):
    def render(source, output, **kwargs):
        output.write_bytes(b"X" * 60)

    jobs = SpeechJobs(renderer=render)
    try:
        a = jobs.start("a", "one", AudioProfile(), {"mode": "preview"}, lambda: True)
        b = jobs.start("b", "two", AudioProfile(), {"mode": "chapter"}, lambda: True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and sum("stage=finished" in line for line in events) < 2:
            time.sleep(.01)
        queued = [line for line in events if "stage=queued" in line]
        assert len(queued) == 2
        ids = [re.search(r"\bid=([0-9a-f]{16})\b", line).group(1) for line in queued]
        assert len(set(ids)) == 2
        assert all(identifier not in {a["id"], b["id"]} for identifier in ids)
    finally:
        jobs.close()


def test_job_scope_matches_renderer_and_is_reset_in_the_caller(events):
    render_ids = []

    def render(source, output, **kwargs):
        render_ids.append(speech_diagnostic_id())
        with speech_diagnostic_scope() as nested:
            assert nested == render_ids[-1]
        output.write_bytes(b"X" * 60)

    assert speech_diagnostic_id() is None
    jobs = SpeechJobs(renderer=render)
    try:
        jobs.start("PRIVATE_CONTEXT", "PRIVATE_MANUSCRIPT", AudioProfile(), {"mode": "preview"}, lambda: True)
        wait_for(events, "stage=finished")
        queued = next(line for line in events if "stage=queued" in line)
        assert render_ids == [re.search(r"\bid=([0-9a-f]{16})\b", queued).group(1)]
        assert speech_diagnostic_id() is None
    finally:
        jobs.close()


def test_scope_restores_context_after_error():
    assert speech_diagnostic_id() is None
    with pytest.raises(RuntimeError), speech_diagnostic_scope() as diagnostic_id:
        assert speech_diagnostic_id() == diagnostic_id
        raise RuntimeError("failure")
    assert speech_diagnostic_id() is None


def test_stale_job_and_unknown_metadata_do_not_leak(events):
    jobs = SpeechJobs(renderer=lambda *args, **kwargs: None)
    valid = True

    def is_valid():
        return valid

    try:
        # Make the job stale as it waits behind another job without writing inputs to the log.
        gate = threading.Event()
        entered = threading.Event()

        def blocking(source, output, **kwargs):
            entered.set()
            gate.wait(3)
            output.write_bytes(b"X" * 60)

        jobs._render = blocking
        jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: True)
        assert entered.wait(3)
        jobs.start("b", "PRIVATE_TEXT", AudioProfile(), {"mode": "PRIVATE_MODE"}, is_valid, target="PRIVATE_TARGET")
        valid = False
        jobs.cancel_stale()
        wait_for(events, "stage=stale_requested")
        gate.set()
        wait_for(events, "status=cancelled")
        assert any("mode=unknown" in line and "target=unknown" in line for line in events)
        assert not any("PRIVATE_" in line for line in events)
    finally:
        gate.set()
        jobs.close()


def test_ready_jobs_report_later_invalidation(events):
    def render(source, output, **kwargs):
        output.write_bytes(b"X" * 60)

    jobs = SpeechJobs(renderer=render)
    try:
        response = jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: True)
        wait_for(events, "status=ready")
        jobs.cancel(response["id"], "a")
        assert any("stage=invalidated" in line and "status=cancelled" in line for line in events)
    finally:
        jobs.close()


def test_job_cleanup_failure_settles_and_logs_without_private_exception(events, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    thread_errors = []
    monkeypatch.setattr(threading, "excepthook", lambda args: thread_errors.append(args.exc_type))

    def render(source, output, **kwargs):
        entered.set()
        release.wait(3)
        raise SpeechCancelled()

    jobs = SpeechJobs(renderer=render)
    try:
        response = jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: True)
        assert entered.wait(3)
        storage = jobs._jobs[response["id"]].storage
        original_cleanup = storage.cleanup

        def fail_cleanup():
            raise OSError("PRIVATE_CLEANUP_PATH")

        monkeypatch.setattr(storage, "cleanup", fail_cleanup)
        release.set()
        wait_for(events, "stage=finished")
        assert thread_errors == []
        report = jobs.status(response["id"], "a")
        assert report["state"] == "error"
        assert "PRIVATE_" not in report["message"]
        assert any("stage=finished" in line and "status=error" in line and "category=cleanup" in line for line in events)
        assert not any("PRIVATE_" in line for line in events)
        monkeypatch.setattr(storage, "cleanup", original_cleanup)
    finally:
        release.set()
        if "storage" in locals():
            monkeypatch.setattr(storage, "cleanup", original_cleanup)
        jobs.close()


@pytest.mark.parametrize("invalidate", ["cancel", "stale", "close"])
def test_ready_job_cleanup_failure_is_reported_safely(events, monkeypatch, invalidate):
    jobs = SpeechJobs(renderer=lambda source, output, **kwargs: output.write_bytes(b"X" * 60))
    current = [True]
    try:
        response = jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: current[0])
        wait_for(events, "status=ready")
        storage = jobs._jobs[response["id"]].storage
        original_cleanup = storage.cleanup

        def fail_cleanup():
            raise OSError("PRIVATE_CLEANUP_PATH")

        monkeypatch.setattr(storage, "cleanup", fail_cleanup)
        if invalidate == "cancel":
            report = jobs.cancel(response["id"], "a")
        elif invalidate == "stale":
            current[0] = False
            jobs.cancel_stale()
            report = jobs.status(response["id"], "a")
        else:
            jobs.close()
            report = jobs.status(response["id"], "a")
        assert report["state"] == "error"
        assert "PRIVATE_" not in report["message"]
        assert any("stage=cleanup" in line and "status=failed" in line for line in events)
        assert not any("PRIVATE_" in line for line in events)
        monkeypatch.setattr(storage, "cleanup", original_cleanup)
    finally:
        if "storage" in locals():
            monkeypatch.setattr(storage, "cleanup", original_cleanup)
        jobs.close()


def test_expired_job_with_cleanup_error_is_retained_for_retry(events, monkeypatch):
    jobs = SpeechJobs(renderer=lambda source, output, **kwargs: output.write_bytes(b"X" * 60))
    try:
        response = jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: True)
        wait_for(events, "status=ready")
        job = jobs._jobs[response["id"]]
        original_cleanup = job.storage.cleanup

        def fail_cleanup():
            raise OSError("PRIVATE_PATH")

        monkeypatch.setattr(job.storage, "cleanup", fail_cleanup)
        job.finished = time.monotonic() - 100_000
        jobs.overview()
        assert job.identifier in jobs._jobs
        assert job.state == "error"
        assert any("stage=cleanup" in line and "status=failed" in line for line in events)
        assert not any("PRIVATE_" in line for line in events)
        monkeypatch.setattr(job.storage, "cleanup", original_cleanup)
        jobs.overview()
        assert job.identifier not in jobs._jobs
    finally:
        if "job" in locals():
            monkeypatch.setattr(job.storage, "cleanup", original_cleanup)
        jobs.close()


def test_source_write_and_cleanup_failure_leave_queue_usable(events, monkeypatch):
    original_write = Path.write_text
    original_cleanup = tempfile.TemporaryDirectory.cleanup

    def fail_write(path, *args, **kwargs):
        raise OSError("PRIVATE_SOURCE_PATH")

    def fail_cleanup(storage):
        raise OSError("PRIVATE_CLEANUP_PATH")

    jobs = SpeechJobs(renderer=lambda source, output, **kwargs: output.write_bytes(b"X" * 60))
    try:
        monkeypatch.setattr(Path, "write_text", fail_write)
        monkeypatch.setattr(tempfile.TemporaryDirectory, "cleanup", fail_cleanup)
        with pytest.raises(OSError, match="PRIVATE_SOURCE_PATH"):
            jobs.start("a", "PRIVATE_TEXT", AudioProfile(), {"mode": "preview"}, lambda: True)
        assert jobs._pending == []
        assert len(jobs._jobs) == 1
        retained = next(iter(jobs._jobs.values()))
        assert retained.state == "error" and retained.finished is not None
        assert "PRIVATE_" not in retained.message
        assert any("stage=cleanup" in line and "status=failed" in line for line in events)
        assert not any("PRIVATE_" in line for line in events)

        monkeypatch.setattr(Path, "write_text", original_write)
        monkeypatch.setattr(tempfile.TemporaryDirectory, "cleanup", original_cleanup)
        response = jobs.start("b", "synthetic", AudioProfile(), {"mode": "preview"}, lambda: True)
        wait_for(events, "status=ready")
        assert jobs.status(response["id"], "b")["state"] == "ready"
    finally:
        monkeypatch.setattr(tempfile.TemporaryDirectory, "cleanup", original_cleanup)
        jobs.close()
