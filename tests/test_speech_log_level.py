"""The optional speech diagnostics must not enable general server debug logs."""

import io
import logging
from concurrent.futures import ThreadPoolExecutor

import pytest

from lixity import log


@pytest.fixture(autouse=True)
def reset_logger(monkeypatch):
    monkeypatch.delenv("LIXITY_SPEECH_LOG_LEVEL", raising=False)
    monkeypatch.delenv("LIXITY_DEBUG", raising=False)
    monkeypatch.delenv("LIXITY_LOG_LEVEL", raising=False)
    speech = logging.getLogger("lixity.speech")
    speech.setLevel(logging.NOTSET)
    yield
    monkeypatch.delenv("LIXITY_SPEECH_LOG_LEVEL", raising=False)
    log.configure(force=True)
    speech.setLevel(logging.NOTSET)


def test_speech_debug_does_not_enable_server_debug_and_works_in_threads(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "debug")
    log.configure(stream=stream, force=True)

    def emit():
        log.get_logger("speech.jobs").debug("synthetic speech")
        log.get_logger("server").debug("synthetic server")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: emit(), range(4)))
    assert stream.getvalue().count("synthetic speech") == 4
    assert "synthetic server" not in stream.getvalue()


def test_override_can_be_removed_and_normal_level_inheritance_resumes(monkeypatch):
    monkeypatch.setenv("LIXITY_LOG_LEVEL", "WARNING")
    speech = log.get_logger("speech")
    log.configure(force=True)
    assert speech.getEffectiveLevel() == logging.WARNING
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "DEBUG")
    log.configure()
    assert speech.getEffectiveLevel() == logging.DEBUG
    monkeypatch.delenv("LIXITY_SPEECH_LOG_LEVEL")
    log.configure()
    assert speech.level == logging.NOTSET
    assert speech.getEffectiveLevel() == logging.WARNING


def test_existing_speech_level_restored_and_invalid_value_ignored(monkeypatch):
    speech = log.get_logger("speech")
    speech.setLevel(logging.ERROR)
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "DEBUG")
    log.configure()
    assert speech.getEffectiveLevel() == logging.DEBUG
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "invalid")
    log.configure()
    assert speech.level == logging.ERROR


def test_force_still_replaces_handler_and_nonforce_keeps_it(monkeypatch):
    first, second = io.StringIO(), io.StringIO()
    monkeypatch.setenv("LIXITY_SPEECH_LOG_LEVEL", "DEBUG")
    root = log.configure(stream=first, force=True)
    handler = root.handlers[0]
    log.configure(stream=second)
    assert root.handlers[0] is handler
    log.get_logger("speech").debug("before")
    log.configure(stream=second, force=True)
    assert root.handlers[0] is not handler
    log.get_logger("speech").debug("after")
    assert "before" in first.getvalue()
    assert "after" in second.getvalue()
