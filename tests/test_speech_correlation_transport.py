"""Synthetic checks for worker correlation and its privacy boundary."""
import errno
import http.client
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
from lixity.speech_profiles import COQUI_MODEL, QWEN_MODEL, AudioProfile
from lixity.speech_references import save_reference
from lixity.speech_worker import MAX_REQUEST_BYTES, synthesize_native


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


@pytest.mark.parametrize("engine, error, category", [
    ("coqui-reference", urllib.error.URLError(ConnectionRefusedError(errno.ECONNREFUSED, "PRIVATE_EXCEPTION")),
     "connection_refused"),
    ("qwen3-base", urllib.error.URLError(OSError(10061, "PRIVATE_EXCEPTION")), "connection_refused"),
    ("qwen3-base", TimeoutError("PRIVATE_EXCEPTION"), "timeout"),
    ("coqui-reference", urllib.error.URLError(OSError(errno.EHOSTUNREACH, "PRIVATE_EXCEPTION")),
     "unreachable"),
    ("qwen3-base", PermissionError(errno.EACCES, "PRIVATE_EXCEPTION"), "access_denied"),
    ("qwen3-base", http.client.BadStatusLine("PRIVATE_EXCEPTION"), "http_protocol_error"),
    ("qwen3-base", http.client.IncompleteRead(b"PRIVATE_EXCEPTION", 10), "incomplete_response"),
    ("qwen3-base", urllib.error.URLError("PRIVATE_EXCEPTION"), "connection_error"),
])
def test_native_reference_transport_classifies_connection_errors(
        recorded, tmp_path, engine, error, category):
    log.configure(stream=recorded, level="INFO", force=True, json_format=True)
    reference = save_reference(tmp_path, generate_silence_wav(1), "PRIVATE_TRANSCRIPT")
    profile = AudioProfile(engine=engine, voice="reference", language="de", reference_id=reference.id)

    def open_request(request, timeout):
        assert request.get_header("X-lixity-render-id") == "0123456789abcdef"
        assert json.loads(request.data)["reference_text"] == "PRIVATE_TRANSCRIPT"
        raise error

    with log.speech_diagnostic_scope("0123456789abcdef"), pytest.raises(RuntimeError, match="unavailable or failed") as failure:
        synthesize_native("PRIVATE_MANUSCRIPT", profile, reference=reference,
                          opener=SimpleNamespace(open=open_request),
                          endpoints={"local": "http://127.0.0.1:8769/PRIVATE_ENDPOINT"})
    event = json.loads(recorded.getvalue())
    assert (event["event"], event["level"], event["id"], event["engine"], event["target"],
            event["category"]) == ("speech_transport", "WARNING", "0123456789abcdef", engine,
                                    "local", category)
    assert "http_status" not in event
    assert "PRIVATE_" not in recorded.getvalue() + str(failure.value)
    assert reference.id not in recorded.getvalue()


@pytest.mark.parametrize("socket_failure, category, os_error, declared_model, observed_engine", [
    (BrokenPipeError(errno.EPIPE, "PRIVATE_SOCKET_ERROR"), "broken_pipe", "EPIPE", QWEN_MODEL, "qwen3"),
    (ConnectionResetError(errno.ECONNRESET, "PRIVATE_SOCKET_ERROR"), "connection_reset", "ECONNRESET",
     "PRIVATE_MODEL", None),
    (http.client.RemoteDisconnected("PRIVATE_SOCKET_ERROR"), "remote_disconnected", None, None, None),
])
def test_abrupt_reference_upload_checks_worker_identity_without_replaying_synthesis(
        recorded, tmp_path, socket_failure, category, os_error, declared_model, observed_engine):
    log.configure(stream=recorded, level="INFO", force=True, json_format=True)
    reference = save_reference(tmp_path, generate_silence_wav(1), "PRIVATE_TRANSCRIPT")
    profile = AudioProfile(engine="coqui-reference", voice="reference", language="de", reference_id=reference.id)
    requests = []

    def open_request(request, timeout):
        requests.append(request.get_method())
        if request.get_method() == "POST":
            assert len(request.data) > MAX_REQUEST_BYTES
            raise urllib.error.URLError(socket_failure)
        assert timeout == 1.5
        assert request.full_url.endswith("/health")
        assert request.data is None
        assert not request.header_items()
        if declared_model is None:
            raise http.client.BadStatusLine("PRIVATE_HEALTH_RESPONSE")
        return io.BytesIO(json.dumps({"ready": True, "model": declared_model}).encode())

    message = "now reports a different model" if observed_engine is not None else "unavailable or failed"
    with pytest.raises(RuntimeError, match=message) as failure:
        synthesize_native("PRIVATE_MANUSCRIPT", profile, reference=reference,
                          opener=SimpleNamespace(open=open_request), diagnostic_id="0123456789abcdef")
    assert requests == ["POST", "GET"]
    event = json.loads(recorded.getvalue())
    assert (event["engine"], event["category"]) == ("coqui-reference", category)
    assert event.get("observed_engine") == observed_engine
    assert event.get("os_error") == os_error
    assert "http_status" not in event
    assert "PRIVATE_" not in recorded.getvalue() + str(failure.value)
    assert reference.id not in recorded.getvalue()


@pytest.mark.parametrize("status, header, category, raises, message", [
    (503, None, "http_error", RuntimeError, "busy"),
    (400, "X-Lixity-Model", "model_mismatch", RuntimeError, "different Qwen model"),
    (200, "X-Lixity-Model", "model_mismatch", ValueError, "model or voice mismatch"),
    (200, "X-Lixity-Voice", "voice_mismatch", ValueError, "model or voice mismatch"),
])
def test_native_transport_logs_http_status_and_identity_mismatch_without_response_data(
        recorded, status, header, category, raises, message):
    log.configure(stream=recorded, level="INFO", force=True, json_format=True)
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"
    if header is not None:
        headers.replace_header(header, "PRIVATE_RESPONSE_HEADER")

    class Response(io.BytesIO):
        pass

    response = Response(b"PRIVATE_RESPONSE_BODY")
    response.headers = headers
    response.status = status

    def open_request(request, timeout):
        if status != 200:
            raise urllib.error.HTTPError(request.full_url, status, "PRIVATE_REASON", headers, response)
        return response

    profile = AudioProfile(engine="qwen3", voice="Ryan", language="en", instructions="PRIVATE_DIRECTION")
    with pytest.raises(raises, match=message) as failure:
        synthesize_native("PRIVATE_MANUSCRIPT", profile, target="jetson",
                          opener=SimpleNamespace(open=open_request), diagnostic_id="fedcba9876543210")
    assert response.closed
    event = json.loads(recorded.getvalue())
    assert (event["event"], event["level"], event["id"], event["engine"], event["target"],
            event["category"], event["http_status"]) == (
                "speech_transport", "WARNING", "fedcba9876543210", "qwen3", "jetson", category, status,
            )
    assert all(secret not in recorded.getvalue() + str(failure.value)
               for secret in ("PRIVATE_", QWEN_MODEL, "Ryan", "127.0.0.1", "8770"))


@pytest.mark.parametrize("content_type, body, limit, category, message", [
    ("application/private_response_type", b"PRIVATE_RESPONSE_BODY", None, "unexpected_content_type",
     "Coqui worker returned an unexpected audio format"),
    ("audio/wav", b"PRIVATE_RESPONSE_BODY", None, "invalid_audio", "Invalid WAV audio segment"),
    ("audio/wav", generate_silence_wav(.01), 128, "response_too_large", "Coqui worker response exceeds the audio limit"),
    ("audio/wav", generate_silence_wav(.01, sample_rate=22050), None, "audio_format_mismatch",
     "Unexpected Coqui audio format"),
    ("audio/wav", generate_silence_wav(.01), None, None, None),
])
def test_native_transport_correlates_bad_audio_replies_without_payload_details(
        recorded, monkeypatch, content_type, body, limit, category, message):
    log.configure(stream=recorded, level="INFO", force=True, json_format=True)
    if limit is not None:
        monkeypatch.setattr("lixity.speech_worker.MAX_RESPONSE_BYTES", limit)
    response = io.BytesIO(body)
    response.status = 200
    response.headers = Message()
    response.headers["Content-Type"] = content_type
    response.headers["X-Lixity-Model"] = COQUI_MODEL
    response.headers["X-Lixity-Voice"] = "thorsten"
    profile = AudioProfile(engine="coqui", voice="thorsten", language="de")
    calls = []

    def open_request(request, timeout):
        calls.append(request.get_method())
        return response

    def synthesize():
        return synthesize_native("PRIVATE_MANUSCRIPT", profile, opener=SimpleNamespace(open=open_request),
                                 diagnostic_id="0123456789abcdef")

    if category is None:
        assert synthesize() == body
        assert recorded.getvalue() == ""
    else:
        with pytest.raises(ValueError, match=message) as failure:
            synthesize()
        event = json.loads(recorded.getvalue())  # A second event would not decode as a single object.
        assert (event["event"], event["level"], event["id"], event["engine"], event["target"],
                event["category"], event["http_status"]) == (
                    "speech_transport", "WARNING", "0123456789abcdef", "coqui", "local", category, 200,
                )
        diagnostic = recorded.getvalue() + str(failure.value)
        assert all(secret not in diagnostic
                   for secret in ("PRIVATE_", "private_response_type", COQUI_MODEL, "thorsten", "127.0.0.1"))
    assert calls == ["POST"]
    assert response.closed


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
    assert any(all(field in line for field in ("status=rejected", "category=busy", "render_id=2222222222222222"))
               for line in lines)
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
    assert any("status=rejected" in line and "category=busy" in line
               for line in recorded.getvalue().splitlines())
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
    assert any("status=failed" in line and "category=transport" in line
               for line in recorded.getvalue().splitlines())
    assert "PRIVATE_READ_ERROR" not in recorded.getvalue()
