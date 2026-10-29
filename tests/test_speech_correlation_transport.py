"""Synthetic checks for worker correlation and its privacy boundary."""
import io
import json
import re
import threading
import urllib.error
import urllib.request
from email.message import Message
from types import SimpleNamespace

import pytest

from lixity import log, speech_qwen
from lixity.speech import generate_silence_wav
from lixity.speech_profiles import QWEN_MODEL, AudioProfile


@pytest.fixture
def recorded():
    stream = io.StringIO()
    logger = log.get_logger()
    previous_handlers, previous_level = list(logger.handlers), logger.level
    log.configure(stream=stream, level="INFO", force=True)
    yield stream
    logger.handlers = previous_handlers
    logger.setLevel(previous_level)


def test_client_sends_correlation_only_with_render_scope():
    requests = []
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"

    class Response(io.BytesIO):
        status = 200

    def open_request(request, timeout):
        requests.append(request)
        response = Response(generate_silence_wav(.01))
        response.headers = headers
        return response

    opener = SimpleNamespace(open=open_request)
    profile = AudioProfile(engine="qwen3", voice="Ryan", language="en")
    speech_qwen.synthesize_qwen("Synthetic text.", profile, opener=opener)
    with log.speech_diagnostic_scope("0123456789abcdef"):
        speech_qwen.synthesize_qwen("Synthetic text.", profile, opener=opener)
    speech_qwen.synthesize_qwen("Synthetic text.", profile, opener=opener)
    assert [r.get_header("X-lixity-render-id") for r in requests] == [None, "0123456789abcdef", None]
    # The existing strict worker accepts exactly these fields.
    assert all(set(json.loads(r.data)) == {"model", "input", "voice", "language", "instructions", "response_format"} for r in requests)


@pytest.mark.parametrize("header, expected", [
    (None, "unknown"), ("0123456789abcdef", "0123456789abcdef"),
    ("PRIVATE_TOKEN", "unknown"), ("0123456789ABCDEF", "unknown"),
    ("0123456789abcdef\n", "unknown"), ("a" * 1000, "unknown"),
])
def test_worker_correlates_only_valid_header_without_affecting_result(recorded, monkeypatch, header, expected):
    handlers = []

    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)

    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    speech_qwen.worker_server(lambda _request: generate_silence_wav(.01), port=0)
    body = json.dumps({"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
                       "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}).encode()
    handler = object.__new__(handlers[0])
    handler.path = "/v1/audio/speech"
    handler.rfile = io.BytesIO(body)
    values = {"Content-Length": str(len(body)), "X-Lixity-Render-Id": header}
    handler.headers = SimpleNamespace(get=lambda name, default=None: values.get(name, default),
                                      get_content_type=lambda: "application/json")
    replies = []
    handler.reply = lambda status, data, *_a, **_kw: replies.append((status, data))
    handler.do_POST()
    assert replies[0][0] == 200
    lines = [line for line in recorded.getvalue().splitlines() if "event=worker_synthesis" in line]
    assert len(lines) == 2
    assert all(f"render_id={expected}" in line for line in lines)
    assert re.search(r"id=[0-9a-f]{16}", lines[0])
    for secret in ("PRIVATE_TOKEN", "PRIVATE_MANUSCRIPT", "PRIVATE_DIRECTION"):
        assert secret not in recorded.getvalue()


def test_invalid_context_is_never_sent(monkeypatch):
    requests = []
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"

    class Response(io.BytesIO):
        status = 200

    def open_request(request, timeout):
        requests.append(request)
        response = Response(generate_silence_wav(.01))
        response.headers = headers
        return response

    monkeypatch.setattr(speech_qwen, "speech_diagnostic_id", lambda: "PRIVATE_TOKEN")
    speech_qwen.synthesize_qwen("Synthetic text.", AudioProfile(engine="qwen3", voice="Ryan", language="en"),
                                opener=SimpleNamespace(open=open_request))
    assert requests[0].get_header("X-lixity-render-id") is None


def test_parallel_http_requests_keep_ids_separate_and_reject_busy_safely(recorded):
    entered = threading.Event()
    release = threading.Event()

    def synthesize(_request):
        entered.set()
        assert release.wait(5)
        return generate_silence_wav(.01)

    server = speech_qwen.worker_server(synthesize, port=0)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    url = f"http://127.0.0.1:{server.server_port}/v1/audio/speech"
    body = json.dumps({"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
                       "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}).encode()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    results = []

    def send(render_id):
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                                  "X-Lixity-Render-Id": render_id})
        try:
            with opener.open(request, timeout=5) as response:
                results.append((render_id, response.status))
        except urllib.error.HTTPError as exc:
            results.append((render_id, exc.code))
            assert render_id.encode() not in exc.read()
            exc.close()

    first = threading.Thread(target=send, args=("1111111111111111",))
    try:
        first.start()
        assert entered.wait(5)
        send("2222222222222222")
        release.set()
        first.join(timeout=5)
        assert not first.is_alive()
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    assert sorted(results) == [("1111111111111111", 200), ("2222222222222222", 503)]
    lines = [line for line in recorded.getvalue().splitlines() if "event=worker_synthesis" in line]
    first_ids = {re.search(r" id=([0-9a-f]{16}) ", line).group(1) for line in lines if "render_id=1111111111111111" in line}
    second_ids = {re.search(r" id=([0-9a-f]{16}) ", line).group(1) for line in lines if "render_id=2222222222222222" in line}
    assert len(first_ids) == len(second_ids) == 1 and first_ids.isdisjoint(second_ids)
    assert any("status=rejected category=busy" in line and "render_id=2222222222222222" in line for line in lines)
    assert "PRIVATE_MANUSCRIPT" not in recorded.getvalue() and "PRIVATE_DIRECTION" not in recorded.getvalue()


@pytest.mark.parametrize("synthesis_fails, expected_status", [(False, 200), (True, 500)])
def test_disconnect_does_not_retry_response_or_leak_errors(recorded, monkeypatch, synthesis_fails, expected_status):
    handlers = []

    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)

    def synthesize(_request):
        if synthesis_fails:
            raise RuntimeError("PRIVATE_INFERENCE_ERROR")
        return generate_silence_wav(.01)

    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    speech_qwen.worker_server(synthesize, port=0)
    body = json.dumps({"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
                       "instructions": "PRIVATE_DIRECTION", "response_format": "wav"}).encode()
    handler = object.__new__(handlers[0])
    handler.path = "/v1/audio/speech"
    handler.rfile = io.BytesIO(body)
    handler.headers = SimpleNamespace(get=lambda name, default=None: str(len(body)) if name == "Content-Length" else default,
                                      get_content_type=lambda: "application/json")
    attempts = []

    def reply(status, *_args, **_kwargs):
        attempts.append(status)
        raise BrokenPipeError("PRIVATE_SOCKET_ERROR")

    handler.reply = reply
    handler.do_POST()
    assert attempts == [expected_status]
    assert "category=transport" in recorded.getvalue()
    for secret in ("PRIVATE_INFERENCE_ERROR", "PRIVATE_SOCKET_ERROR", "PRIVATE_MANUSCRIPT", "PRIVATE_DIRECTION"):
        assert secret not in recorded.getvalue()


@pytest.mark.parametrize("method,path,origin,invalid,expected", [
    ("GET", "/health", False, False, 200),
    ("GET", "/capabilities", False, False, 200),
    ("GET", "/unknown", False, False, 404),
    ("POST", "/unknown", False, False, 404),
    ("POST", "/v1/audio/speech", True, False, 403),
    ("POST", "/v1/audio/speech", False, True, 400),
])
def test_disconnect_before_synthesis_does_not_retry_or_raise(recorded, monkeypatch, method, path, origin, invalid, expected):
    handlers = []

    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)

    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    speech_qwen.worker_server(lambda _request: pytest.fail("unexpected synthesis"), port=0)
    body = b'{}' if invalid else b'PRIVATE_MANUSCRIPT'
    handler = object.__new__(handlers[0])
    handler.path = path
    handler.rfile = io.BytesIO(body)
    values = {"Content-Length": str(len(body)), "Origin": "PRIVATE_ORIGIN" if origin else None,
              "X-Lixity-Render-Id": "0123456789abcdef"}
    handler.headers = SimpleNamespace(get=lambda name, default=None: values.get(name, default),
                                      get_content_type=lambda: "application/json")
    attempts = []

    def reply(status, *_args, **_kwargs):
        attempts.append(status)
        raise BrokenPipeError("PRIVATE_SOCKET_ERROR")

    handler.reply = reply
    (handler.do_GET if method == "GET" else handler.do_POST)()
    assert attempts == [expected]
    assert "category=transport" in recorded.getvalue()
    for secret in ("PRIVATE_SOCKET_ERROR", "PRIVATE_MANUSCRIPT", "PRIVATE_ORIGIN"):
        assert secret not in recorded.getvalue()


def test_busy_response_disconnect_is_handled(recorded, monkeypatch):
    handlers = []

    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)

    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    body = json.dumps({"model": QWEN_MODEL, "input": "PRIVATE_MANUSCRIPT", "voice": "Ryan", "language": "en",
                       "instructions": "", "response_format": "wav"}).encode()
    attempts = []

    def make_handler():
        handler = object.__new__(handlers[0])
        handler.path = "/v1/audio/speech"
        handler.rfile = io.BytesIO(body)
        handler.headers = SimpleNamespace(get=lambda name, default=None: str(len(body)) if name == "Content-Length" else default,
                                          get_content_type=lambda: "application/json")
        return handler

    def fail_reply(status, *_args, **_kwargs):
        attempts.append(status)
        raise BrokenPipeError("PRIVATE_SOCKET_ERROR")

    def synthesize(_request):
        nested = make_handler()
        nested.reply = fail_reply
        nested.do_POST()
        return generate_silence_wav(.01)

    speech_qwen.worker_server(synthesize, port=0)
    outer = make_handler()
    outer.reply = lambda status, *_args, **_kwargs: attempts.append(status)
    outer.do_POST()
    assert attempts == [503, 200]
    assert "status=rejected category=busy" in recorded.getvalue()
    assert "category=transport" in recorded.getvalue()
    assert "status=success" in recorded.getvalue()
    assert "PRIVATE_SOCKET_ERROR" not in recorded.getvalue()


def test_disconnect_while_reading_request_has_no_response_or_traceback(recorded, monkeypatch):
    handlers = []

    class FakeServer:
        def __init__(self, _address, handler):
            handlers.append(handler)

    class BrokenStream:
        def read(self, _size):
            raise ConnectionResetError("PRIVATE_READ_ERROR")

    monkeypatch.setattr(speech_qwen, "ThreadingHTTPServer", FakeServer)
    speech_qwen.worker_server(lambda _request: pytest.fail("unexpected synthesis"), port=0)
    handler = object.__new__(handlers[0])
    handler.path = "/v1/audio/speech"
    handler.rfile = BrokenStream()
    values = {"Content-Length": "100", "X-Lixity-Render-Id": "0123456789abcdef"}
    handler.headers = SimpleNamespace(get=lambda name, default=None: values.get(name, default),
                                      get_content_type=lambda: "application/json")
    attempts = []
    handler.reply = lambda status, *_args, **_kwargs: attempts.append(status)
    handler.do_POST()
    assert attempts == []
    assert "render_id=0123456789abcdef" in recorded.getvalue()
    assert "status=failed category=transport" in recorded.getvalue()
    assert "PRIVATE_READ_ERROR" not in recorded.getvalue()
