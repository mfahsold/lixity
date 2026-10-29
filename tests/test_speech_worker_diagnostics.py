"""Worker diagnostics exclude request content and use independent IDs."""
import io
import json
import re
from types import SimpleNamespace

import pytest

from lixity import log, speech_qwen
from lixity.speech import generate_silence_wav
from lixity.speech_profiles import QWEN_MODEL


@pytest.fixture
def recorded():
    stream = io.StringIO()
    logger = log.get_logger()
    previous_handlers, previous_level = list(logger.handlers), logger.level
    log.configure(stream=stream, level="INFO", force=True)
    yield stream
    logger.handlers = previous_handlers
    logger.setLevel(previous_level)


def test_worker_main_logs_load_failure_without_untrusted_model_path(recorded, monkeypatch):
    monkeypatch.setattr("sys.argv", ["worker", "--model", "/private/MODEL_SECRET"])
    def fail(*_a, **_kw):
        raise RuntimeError("EXCEPTION_SECRET")
    monkeypatch.setattr(speech_qwen, "load_local_model", fail)
    with pytest.raises(RuntimeError):
        speech_qwen.main()
    text = recorded.getvalue()
    assert "event=worker_model_load" in text and "status=failed" in text
    assert "MODEL_SECRET" not in text and "EXCEPTION_SECRET" not in text


def test_worker_request_events_are_safe_for_success_and_failure(recorded, monkeypatch):
    handlers = []
    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)
    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    responses = []
    should_fail = [False]
    def synthesize(_request):
        if should_fail[0]:
            raise RuntimeError("EXCEPTION_SECRET")
        return generate_silence_wav(.01)
    speech_qwen.worker_server(synthesize, port=0)
    request = {"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
               "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}
    body = json.dumps(request).encode()
    for fail in (False, True):
        should_fail[0] = fail
        handler = object.__new__(handlers[0])
        handler.path = "/v1/audio/speech"
        handler.rfile = io.BytesIO(body)
        handler.headers = SimpleNamespace(get=lambda name, default=None: str(len(body)) if name == "Content-Length" else default,
                                          get_content_type=lambda: "application/json")
        handler.reply = lambda status, *_a, **_kw: responses.append(status)
        handler.do_POST()
    assert responses == [200, 500]
    text = recorded.getvalue()
    assert "event=worker_synthesis" in text and "status=success" in text and "status=failed" in text
    assert "PRIVATE_MANUSCRIPT" not in text and "PRIVATE_DIRECTION" not in text and "EXCEPTION_SECRET" not in text
    ids = re.findall(r"event=worker_synthesis id=([0-9a-f]{16}) .*status=started", text)
    assert len(ids) == 2 and ids[0] != ids[1]


def test_worker_rejects_invalid_and_busy_requests_without_logging_payload(recorded, monkeypatch):
    handlers = []
    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)
    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    responses = []
    request = {"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
               "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}

    def send(payload):
        body = json.dumps(payload).encode()
        handler = object.__new__(handlers[0])
        handler.path = "/v1/audio/speech"
        handler.rfile = io.BytesIO(body)
        handler.headers = SimpleNamespace(get=lambda name, default=None: str(len(body)) if name == "Content-Length" else default,
                                          get_content_type=lambda: "application/json")
        handler.reply = lambda status, *_a, **_kw: responses.append(status)
        handler.do_POST()

    def synthesize(_request):
        send(request)  # The nested request sees the worker lock as busy.
        return generate_silence_wav(.01)

    speech_qwen.worker_server(synthesize, port=0)
    send({**request, "model": "PRIVATE_MODEL"})
    send(request)
    assert responses == [400, 503, 200]
    text = recorded.getvalue()
    assert "category=validation" in text and "category=busy" in text
    for private in ("PRIVATE_MANUSCRIPT", "PRIVATE_DIRECTION", "PRIVATE_MODEL"):
        assert private not in text


def test_worker_logs_client_disconnect_as_transport_not_synthesis_failure(recorded, monkeypatch):
    handlers = []
    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)
    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    speech_qwen.worker_server(lambda _request: generate_silence_wav(.01), port=0)
    request = {"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
               "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}
    body = json.dumps(request).encode()
    handler = object.__new__(handlers[0])
    handler.path = "/v1/audio/speech"
    handler.rfile = io.BytesIO(body)
    handler.headers = SimpleNamespace(get=lambda name, default=None: str(len(body)) if name == "Content-Length" else default,
                                      get_content_type=lambda: "application/json")
    replies = []
    def reply(status, *_a, **_kw):
        replies.append(status)
        if status == 200:
            raise BrokenPipeError("PRIVATE_PATH")
    handler.reply = reply
    handler.do_POST()
    assert replies == [200]  # A partially sent response cannot be replaced with a second response.
    text = recorded.getvalue()
    assert "status=failed category=transport" in text
    assert "PRIVATE_MANUSCRIPT" not in text and "PRIVATE_PATH" not in text
