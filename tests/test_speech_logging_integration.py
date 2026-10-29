"""Exercise speech diagnostics across job, renderer and CLI boundaries."""

import io
import json
import logging
import os
import re
import subprocess
import sys
import time

import pytest

from lixity import log
from lixity.speech import generate_silence_wav
from lixity.speech_direction import SpeechSegment
from lixity.speech_jobs import SpeechJobs
from lixity.speech_profiles import AudioProfile

pytestmark = pytest.mark.portability


def test_job_and_renderer_share_private_content_free_diagnostics(monkeypatch):
    stream = io.StringIO()
    root = logging.getLogger("lixity")
    speech_logger = logging.getLogger("lixity.speech")
    original_handlers, original_level = list(root.handlers), root.level
    original_speech_level = speech_logger.level
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "DEBUG")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: generate_silence_wav(0.01))
    log.configure(level="INFO", stream=stream, force=True)
    sentinel = "SYNTHETIC_PRIVATE_MANUSCRIPT_AND_DIRECTION"
    profile = AudioProfile(instructions=sentinel, speed=1.0)
    jobs = SpeechJobs()
    try:
        report = jobs.start(
            "synthetic-private-context", sentinel, profile,
            {"mode": "chapter", "title": sentinel}, lambda: True,
            plan=[SpeechSegment(sentinel, profile)],
        )
        deadline = time.monotonic() + 5
        while "stage=finished" not in stream.getvalue() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert jobs.status(report["id"], "synthetic-private-context")["state"] == "ready"
        assert len(jobs.audio(report["id"], "synthetic-private-context")) > 44
        lines = stream.getvalue().splitlines()
        queued = next(line for line in lines if "stage=queued" in line)
        identifier = re.search(r"\bid=([0-9a-f]{16})\b", queued).group(1)
        for event in ("stage=running", "event=render_start", "event=render_plan",
                      "event=segment_start", "event=segment_end", "event=render_end", "stage=finished"):
            assert any(event in line and f"id={identifier}" in line for line in lines), event
        assert "status=ready" in lines[-1]
        assert sentinel not in stream.getvalue()
        assert "synthetic-private-context" not in stream.getvalue()
        assert report["id"] not in stream.getvalue()
    finally:
        jobs.close()
        monkeypatch.delenv("LIXITY_SPEECH_LOG_LEVEL", raising=False)
        log.configure(force=True)
        root.handlers = original_handlers
        root.setLevel(original_level)
        speech_logger.setLevel(original_speech_level)


def test_cli_json_stdout_survives_speech_debug_logging(tmp_path):
    (tmp_path / "lixity.toml").write_text('language="de"\nmanuscript="draft.md"\n', encoding="utf-8")
    (tmp_path / "draft.md").write_text("## Eins\n\nEin synthetischer Absatz.\n", encoding="utf-8")
    # The plan command does not synthesize speech, so emit one representative
    # speech diagnostic in the same process before invoking the real CLI.
    script = (
        'import sys; from lixity.log import get_logger; '
        'get_logger("speech").debug("event=synthetic_cli_probe"); '
        'from lixity.cli import main; raise SystemExit(main(sys.argv[1:]))'
    )
    command = [sys.executable, "-c", script, "read-aloud", "--project", str(tmp_path), "--plan-only"]
    environment = os.environ.copy()
    environment.pop("LIXITY_LOG_LEVEL", None)
    environment.pop("LIXITY_DEBUG", None)
    environment.pop("LIXITY_SPEECH_LOG_LEVEL", None)
    baseline = subprocess.run(command, env=environment, capture_output=True, text=True, check=True)  # noqa: S603 - fixed interpreter and synthetic project
    environment["LIXITY_SPEECH_LOG_LEVEL"] = "DEBUG"
    debug = subprocess.run(command, env=environment, capture_output=True, text=True, check=True)  # noqa: S603 - fixed interpreter and synthetic project
    assert json.loads(debug.stdout) == json.loads(baseline.stdout)
    assert "event=synthetic_cli_probe" in debug.stderr
    assert "event=synthetic_cli_probe" not in baseline.stderr
    assert "event=synthetic_cli_probe" not in debug.stdout
