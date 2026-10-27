"""Synthetic async speech jobs keep outputs bound to their immutable source."""

import threading
import time
from pathlib import Path

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_jobs import SpeechJobs, prepare_speech_source
from lixity.speech_profiles import AudioProfile

TEXT = "## First\n\nA bird crosses the garden.\n\n## Second\n\nAnother passage waits here.\n"


def wait_for(jobs, identifier):
    for _ in range(200):
        result = jobs.status(identifier, "context")
        if result["state"] not in ("pending", "running"):
            return result
        time.sleep(0.005)
    pytest.fail("Synthetic speech job did not settle")


def test_scope_never_accepts_stale_paragraphs_or_invalid_chapters():
    text, info = prepare_speech_source(TEXT, language="en", mode="preview", chapter=1)
    assert "bird crosses" in text and "Another passage" not in text
    assert info["mode"] == "preview" and info["chapter"] == 1
    with pytest.raises(ValueError):
        prepare_speech_source(TEXT, language="en", mode="preview", chapter=99)
    with pytest.raises(ValueError):
        prepare_speech_source(
            TEXT,
            language="en",
            mode="preview",
            chapter=1,
            paragraph={"start_line": 3, "end_line": 3, "paragraph_sha256": "0" * 64},
        )


def test_success_returns_only_owned_audio_and_keeps_source_immutable(tmp_path):
    observed = []

    def render(source, output, **kwargs):
        from lixity.speech_jobs import MAX_AUDIO_BYTES

        assert kwargs["max_audio_bytes"] == MAX_AUDIO_BYTES
        observed.append(Path(source).read_text())
        kwargs["progress"](1, 2)
        Path(output).write_bytes(generate_silence_wav(0.01))
        kwargs["progress"](2, 2)
        return Path(output)

    jobs = SpeechJobs(renderer=render)
    try:
        value = jobs.start("context", TEXT, AudioProfile(), {"mode": "preview"}, lambda: True)
        final = wait_for(jobs, value["id"])
        assert final["state"] == "ready" and final["done"] == final["total"] == 2
        assert jobs.audio(value["id"], "context").startswith(b"RIFF")
        assert observed == [TEXT]
        with pytest.raises(ValueError):
            jobs.audio(value["id"], "other context")
        with pytest.raises(ValueError):
            jobs.status("../outside", "context")
    finally:
        jobs.close()


def test_cancel_and_changed_context_never_publish_completed_audio():
    release = threading.Event()
    entered = threading.Event()

    def render(source, output, **kwargs):
        entered.set()
        release.wait(2)
        Path(output).write_bytes(generate_silence_wav(0.01))
        return Path(output)

    jobs = SpeechJobs(renderer=render)
    try:
        value = jobs.start("context", TEXT, AudioProfile(), {}, lambda: True)
        assert entered.wait(1)
        with pytest.raises(RuntimeError, match="active"):
            jobs.start("context", TEXT, AudioProfile(), {}, lambda: True)
        jobs.cancel(value["id"], "context")
        release.set()
        assert wait_for(jobs, value["id"])["state"] == "cancelled"
        with pytest.raises(ValueError):
            jobs.audio(value["id"], "context")
    finally:
        release.set()
        jobs.close()
    jobs = SpeechJobs(
        renderer=lambda source, output, **kw: Path(output).write_bytes(generate_silence_wav(0.01))
    )
    try:
        value = jobs.start("context", TEXT, AudioProfile(), {}, lambda: False)
        assert wait_for(jobs, value["id"])["state"] == "stale"
        with pytest.raises(ValueError):
            jobs.audio(value["id"], "context")
    finally:
        jobs.close()


def test_failed_job_is_explicit_and_cleans_temporary_source():
    paths = []

    def render(source, output, **kwargs):
        paths.append(Path(source))
        raise RuntimeError("Synthetic backend unavailable")

    jobs = SpeechJobs(renderer=render)
    try:
        value = jobs.start("context", TEXT, AudioProfile(), {}, lambda: True)
        final = wait_for(jobs, value["id"])
        assert final["state"] == "error" and "unavailable" in final["message"]
        assert not paths[0].exists()
        with pytest.raises(ValueError):
            jobs.audio(value["id"], "context")
    finally:
        jobs.close()


def test_observed_staleness_cannot_be_undone_by_restoring_source():
    valid = [True]
    entered = threading.Event()
    release = threading.Event()

    def render(source, output, **kwargs):
        entered.set()
        release.wait(2)
        Path(output).write_bytes(generate_silence_wav(0.01))

    jobs = SpeechJobs(renderer=render)
    try:
        job = jobs.start("context", TEXT, AudioProfile(), {}, lambda: valid[0])
        assert entered.wait(1)
        valid[0] = False
        jobs.cancel_stale()
        valid[0] = True
        release.set()
        assert wait_for(jobs, job["id"])["state"] == "cancelled"
    finally:
        release.set()
        jobs.close()


def test_long_running_success_gets_its_full_result_retention_window(monkeypatch):
    import lixity.speech_jobs as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    original_job = module._Job
    monkeypatch.setattr(
        module, "_Job", lambda *args, **kwargs: original_job(*args, **kwargs, created=clock[0])
    )

    def render(source, output, **kwargs):
        clock[0] = module.JOB_TTL_SECONDS + 20
        Path(output).write_bytes(generate_silence_wav(0.01))

    jobs = SpeechJobs(renderer=render)
    try:
        job = jobs.start("context", TEXT, AudioProfile(), {}, lambda: True)
        assert wait_for(jobs, job["id"])["state"] == "ready"
        assert jobs.audio(job["id"], "context").startswith(b"RIFF")
    finally:
        jobs.close()


@pytest.mark.parametrize("target", ["local", "jetson"])
def test_job_dispatch_keeps_execution_target_outside_portable_profile(target):
    observed = []
    profile = AudioProfile(engine="qwen3", voice="Ryan")
    original = profile.model_dump()

    def render(source, output, **kwargs):
        observed.append((kwargs["target"], kwargs["profile"].model_dump()))
        Path(output).write_bytes(generate_silence_wav(0.01))

    jobs = SpeechJobs(renderer=render)
    try:
        job = jobs.start("context", TEXT, profile, {"mode": "preview"}, lambda: True,
                         target=target)
        assert wait_for(jobs, job["id"])["state"] == "ready"
        assert jobs.audio(job["id"], "context").startswith(b"RIFF")
        assert observed == [(target, original)]
        assert profile.model_dump() == original and "target" not in original
    finally:
        jobs.close()


def test_different_project_jobs_queue_without_overlapping_and_pending_cancel_never_renders():
    entered = threading.Event()
    release = threading.Event()
    rendered = []

    def render(source, output, **kwargs):
        rendered.append(Path(source).read_text())
        entered.set()
        release.wait(2)
        Path(output).write_bytes(generate_silence_wav(0.01))

    jobs = SpeechJobs(renderer=render)
    try:
        first = jobs.start('context', 'First project.', AudioProfile(), {}, lambda: True)
        assert entered.wait(1)
        second = jobs.start('other', 'Second project.', AudioProfile(), {}, lambda: True)
        assert jobs.status(second['id'], 'other')['queue_position'] == 1
        third = jobs.start('third', 'Cancelled project.', AudioProfile(), {}, lambda: True)
        jobs.cancel(third['id'], 'third')
        assert rendered == ['First project.']
        release.set()
        assert wait_for(jobs, first['id'])['state'] == 'ready'
        for _ in range(200):
            if jobs.status(second['id'], 'other')['state'] == 'ready':
                break
            time.sleep(0.005)
        assert rendered == ['First project.', 'Second project.']
        assert jobs.status(third['id'], 'third')['state'] == 'cancelled'
    finally:
        release.set()
        jobs.close()


def test_queue_is_bounded_and_stale_pending_sources_never_reach_renderer():
    from lixity.speech_jobs import MAX_PENDING_JOBS

    entered, release = threading.Event(), threading.Event()
    valid = [True]
    rendered = []
    def render(source, output, **kwargs):
        rendered.append(Path(source).read_text())
        entered.set()
        release.wait(2)
        Path(output).write_bytes(generate_silence_wav(0.01))
    jobs = SpeechJobs(renderer=render)
    try:
        first = jobs.start('context', 'First', AudioProfile(), {}, lambda: True)
        assert entered.wait(1)
        pending = jobs.start('stale', 'Stale', AudioProfile(), {}, lambda: valid[0])
        for index in range(MAX_PENDING_JOBS - 1):
            jobs.start(str(index), 'Other', AudioProfile(), {}, lambda: True)
        with pytest.raises(RuntimeError, match='queue is full'):
            jobs.start('overflow', 'Never stored', AudioProfile(), {}, lambda: True)
        valid[0] = False
        jobs.cancel_stale()
        release.set()
        assert wait_for(jobs, first['id'])['state'] == 'ready'
        for _ in range(200):
            if jobs.status(pending['id'], 'stale')['state'] == 'cancelled':
                break
            time.sleep(0.005)
        assert 'Stale' not in rendered and 'Never stored' not in rendered
    finally:
        release.set()
        jobs.close()


def test_source_cleanup_failure_does_not_block_the_queue(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    unlink = Path.unlink
    failed = []
    def failing_unlink(path, *args, **kwargs):
        if path.name == 'source.md' and not failed:
            failed.append(True)
            raise PermissionError('Synthetic cleanup failure')
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', failing_unlink)
    def render(source, output, **kwargs):
        entered.set()
        release.wait(2)
        Path(output).write_bytes(generate_silence_wav(0.01))
    jobs = SpeechJobs(renderer=render)
    try:
        first = jobs.start('context', 'First', AudioProfile(), {}, lambda: True)
        assert entered.wait(1)
        second = jobs.start('second', 'Second', AudioProfile(), {}, lambda: True)
        release.set()
        for _ in range(200):
            if jobs.status(second['id'], 'second')['state'] == 'ready':
                break
            time.sleep(0.005)
        assert jobs.status(second['id'], 'second')['state'] == 'ready'
        assert jobs.status(first['id'], 'context')['state'] == 'error'
    finally:
        release.set()
        jobs.close()
