"""Bounded, fixed-loopback transport shared by optional native speech workers."""
from __future__ import annotations

import base64
import errno
import http.client
import json
import logging
import math
import re
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from secrets import token_hex
from typing import TYPE_CHECKING, Any

from .audio_pcm import SPEECH_PCM_FORMAT, read_pcm_wav
from .log import get_logger, log_event, speech_diagnostic_id, speech_diagnostic_scope
from .speech_engines import QWEN_MODEL, engine_for_model, native_engine
from .speech_profiles import AudioProfile, audio_capabilities, speech_segment_limit
from .speech_providers import _NoRedirect as _NoRedirect
from .speech_providers import no_redirect_opener
from .speech_recording_settings import (
    MAX_REFERENCE_SECONDS as MAX_REFERENCE_SECONDS,
)
from .speech_recording_settings import (
    MIN_REFERENCE_SECONDS as MIN_REFERENCE_SECONDS,
)

if TYPE_CHECKING:
    from .speech_references import SpeechReference

MAX_REQUEST_BYTES = 32768
MAX_REFERENCE_BYTES = 3 * 1024 * 1024
MAX_BASE_REQUEST_BYTES = MAX_REQUEST_BYTES + 4 * ((MAX_REFERENCE_BYTES + 2) // 3)
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
SAMPLE_RATE = SPEECH_PCM_FORMAT[2]
REFERENCE_WAV_FORMAT = (1, 2, SAMPLE_RATE)
MAX_REFERENCE_TRANSCRIPT_CHARS = 2000
SYNTHESIS_TIMEOUT_SECONDS = 3600
_RENDER_ID_HEADER = "X-Lixity-Render-Id"


class SpeechRequestValidationError(ValueError):
    """A bounded, author-correctable synthesis request error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def reference_format() -> dict[str, int]:
    """Return the capture and validation contract for author references."""
    channels, width, rate = REFERENCE_WAV_FORMAT
    return {
        "channels": channels,
        "sample_rate_hz": rate,
        "sample_width_bits": width * 8,
        "min_seconds": MIN_REFERENCE_SECONDS,
        "max_seconds": MAX_REFERENCE_SECONDS,
        "max_bytes": MAX_REFERENCE_BYTES,
        "max_transcript_chars": MAX_REFERENCE_TRANSCRIPT_CHARS,
    }


def _valid_render_id(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{16}", value) else None


def _connection_failure(error: OSError | http.client.HTTPException) -> tuple[str, str | None]:
    """Classify transport exceptions without retaining their text or destination."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    code = reason.errno if isinstance(reason, OSError) else None
    os_error = errno.errorcode.get(code) if type(code) is int else None
    if isinstance(reason, http.client.RemoteDisconnected):
        return "remote_disconnected", os_error
    if isinstance(reason, http.client.IncompleteRead):
        return "incomplete_response", os_error
    if isinstance(reason, http.client.HTTPException):
        return "http_protocol_error", os_error
    # Socket failures can retain Winsock codes instead of their POSIX mappings.
    if isinstance(reason, ConnectionRefusedError) or code in (errno.ECONNREFUSED, 10061):
        return "connection_refused", os_error
    if isinstance(reason, ConnectionResetError) or code in (errno.ECONNRESET, 10054):
        return "connection_reset", os_error
    if isinstance(reason, ConnectionAbortedError) or code in (errno.ECONNABORTED, 10053):
        return "connection_aborted", os_error
    if isinstance(reason, BrokenPipeError) or code == errno.EPIPE:
        return "broken_pipe", os_error
    if isinstance(reason, TimeoutError) or code in (errno.ETIMEDOUT, 10060):
        return "timeout", os_error
    if code in (errno.ENETDOWN, errno.ENETUNREACH, errno.EHOSTUNREACH, 10050, 10051, 10065):
        return "unreachable", os_error
    if isinstance(reason, PermissionError) or code in (errno.EACCES, errno.EPERM, 10013):
        return "access_denied", os_error
    return "connection_error", os_error


def _reported_engine(model: object) -> str | None:
    if isinstance(model, str):
        try:
            return engine_for_model(model)
        except ValueError:
            pass
    return None


def worker_health(target: str, *, engine: str = "qwen3", opener: Any = None,
                  endpoints: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Probe the actual allowlisted model worker, never merely an open tunnel."""
    spec = native_engine(engine)
    if target not in spec.endpoints:
        raise ValueError("Unknown native speech execution target")
    endpoints = spec.endpoints if endpoints is None else endpoints
    request = urllib.request.Request(endpoints[target].replace("/v1/audio/speech", "/health"))  # noqa: S310 - fixed loopback allowlist
    client = no_redirect_opener(opener)
    model_id = None
    residency: dict[str, Any] = {}
    try:
        with client.open(request, timeout=1.5) as response:
            raw = response.read(4097)
        if len(raw) > 4096:
            raise ValueError("Oversized health response")
        value = json.loads(raw)
        if not isinstance(value, dict) or not isinstance(value.get("model"), str) or type(value.get("ready")) is not bool:
            raise ValueError("Unexpected worker identity")
        engine_for_model(value["model"])
        model_id = value["model"]
        if "model_state" in value:
            if value["model_state"] not in ("unloaded", "loading", "loaded", "failed") or type(value.get("active")) is not bool:
                raise ValueError("Unexpected model residency")
            residency = {"model_state": value["model_state"], "active": value["active"]}
            if "idle_timeout_seconds" in value:
                from .speech_lifecycle import MAX_IDLE_TIMEOUT_SECONDS
                timeout = value["idle_timeout_seconds"]
                if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= MAX_IDLE_TIMEOUT_SECONDS:
                    raise ValueError("Unexpected model idle timeout")
                residency["idle_timeout_seconds"] = timeout
        state = "ready" if value["ready"] else "starting"
    except (OSError, ValueError, http.client.HTTPException):
        state = "unavailable"
    return {"target": target, "state": state, "transport": "loopback" if target == "local" else "ssh", "model": model_id, **residency}


def synthesize_native(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                    reference: SpeechReference | None = None,
                      endpoints: Mapping[str, str] | None = None, diagnostic_id: str | None = None) -> bytes:
    """Request bounded PCM WAV through a fixed loopback target, without fallback."""
    profile = AudioProfile.model_validate(profile.model_dump())
    spec = native_engine(profile.engine)
    if target not in spec.endpoints:
        raise ValueError("Unknown native speech execution target")
    if not text.strip() or len(text) > speech_segment_limit(profile):
        raise ValueError("Invalid native synthesis request")
    model_id = spec.model
    worker_name = "Qwen" if profile.engine.startswith("qwen") else "Coqui" if profile.engine.startswith("coqui") else audio_capabilities()[profile.engine]["name"]
    endpoints = spec.endpoints if endpoints is None else endpoints
    request_data: dict[str, Any] = {"model": model_id, "input": text, "voice": profile.voice,
                          "language": profile.language, "instructions": profile.instructions,
                          "response_format": "wav"}
    if profile.engine == "qwen3-design":
        request_data["voice_description"] = profile.voice_description
    elif spec.reference_required:
        from .speech_references import validate_reference
        if reference is None or reference.id != profile.reference_id:
            raise ValueError(f"{worker_name} requires the matching verified reference")
        validate_reference(reference)
        request_data["reference_audio"] = base64.b64encode(reference.audio).decode("ascii")
        request_data["reference_text"] = reference.transcript
        if profile.engine == "qwen3-base" and len(text.strip().split()) <= 4:
            request_data["x_vector_only"] = True
    elif reference is not None:
        raise ValueError("This native model does not use a reference")
    if profile.engine == "ims-toucan":
        from .speech_controls import phoneme_spans

        request_data["phonemes"] = {
            text[start:end]: replacement
            for start, end, replacement in phoneme_spans(text, profile.phonemes)
        }
        request_data["prosody"] = profile.prosody.model_dump()
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(payload) > (MAX_BASE_REQUEST_BYTES if spec.reference_required else MAX_REQUEST_BYTES):
        raise ValueError(f"{worker_name} synthesis request is too large")
    headers = {"Content-Type": "application/json"}
    render_id = _valid_render_id(diagnostic_id if diagnostic_id is not None else speech_diagnostic_id())
    if render_id is not None:
        headers[_RENDER_ID_HEADER] = render_id

    def transport_failed(category: str, http_status: int | None = None, *,
                         observed_model: object = None, os_error: str | None = None) -> None:
        status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        log_event(get_logger("speech.transport"), "speech_transport", logging.WARNING,
                  id=render_id, engine=profile.engine, target=target, category=category,
                  http_status=status, observed_engine=_reported_engine(observed_model), os_error=os_error)

    request = urllib.request.Request(endpoints[target], data=payload,  # noqa: S310 - fixed loopback allowlist
                                     headers=headers)
    # Ignore proxy environment variables, even for localhost.
    client = no_redirect_opener(opener)
    response_started = False
    try:
        with client.open(request, timeout=SYNTHESIS_TIMEOUT_SECONDS) as response:
            response_started = True
            if response.status != 200:
                transport_failed("http_error", response.status)
                raise RuntimeError(f"{worker_name} worker rejected the synthesis request")
            actual_model = response.headers.get("X-Lixity-Model")
            model_mismatch = actual_model != model_id
            if (model_mismatch or
                    response.headers.get("X-Lixity-Voice") != profile.voice):
                transport_failed("model_mismatch" if model_mismatch else "voice_mismatch", 200,
                                 observed_model=actual_model)
                raise ValueError(f"{worker_name} worker model or voice mismatch")
            if response.headers.get_content_type() != "audio/wav":
                transport_failed("unexpected_content_type", 200)
                raise ValueError(f"{worker_name} worker returned an unexpected audio format")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # HTTPError owns a response stream even though open() raised before
        # entering the response context manager.
        actual_model = exc.headers.get("X-Lixity-Model") if exc.headers else None
        validation_code = None
        if exc.code == 400:
            try:
                detail = json.loads(exc.read(4096))
                candidate = detail.get("code") if isinstance(detail, dict) else None
                if isinstance(candidate, str) and re.fullmatch(r"[a-z0-9_]{1,64}", candidate):
                    validation_code = candidate
            except (OSError, ValueError, TypeError):
                pass
        exc.close()
        if actual_model is not None and actual_model != model_id:
            transport_failed("model_mismatch", exc.code, observed_model=actual_model)
            model_kind = "Qwen model" if worker_name == "Qwen" else "model"
            raise RuntimeError(f"{worker_name} worker ({target}) is running a different {model_kind}; select the matching worker variant") from exc
        transport_failed("http_error", exc.code)
        if exc.code == 400:
            if validation_code:
                raise ValueError(f"{worker_name} worker ({target}) rejected the synthesis request ({validation_code})") from exc
            raise RuntimeError(f"{worker_name} worker ({target}) rejected the synthesis request (HTTP 400); check the selected profile and model") from exc
        if exc.code == 500:
            raise RuntimeError(f"{worker_name} worker ({target}) reported synthesis failed (HTTP 500); check the worker runtime and resources") from exc
        if exc.code == 503:
            raise RuntimeError(f"{worker_name} worker ({target}) is busy (HTTP 503); retry after the current request finishes") from exc
        raise RuntimeError(f"{worker_name} worker ({target}) is unavailable or failed") from exc
    except (OSError, http.client.HTTPException) as exc:
        category, os_error = _connection_failure(exc)
        observed_model = None
        # A worker can close a large reference upload before urllib reads the
        # rejection headers. Check only its current identity and never replay the POST.
        if not response_started and category in {"connection_reset", "connection_aborted", "broken_pipe", "remote_disconnected"}:
            health = worker_health(target, engine=profile.engine, opener=client, endpoints=endpoints)
            if health["state"] in ("ready", "starting"):
                observed_model = health["model"]
        transport_failed(category, observed_model=observed_model, os_error=os_error)
        if observed_model is not None and observed_model != model_id:
            raise RuntimeError(f"{worker_name} worker ({target}) disconnected and now reports a different model; select the matching worker variant") from exc
        raise RuntimeError(f"{worker_name} worker ({target}) is unavailable or failed") from exc
    if not isinstance(data, bytes):
        transport_failed("invalid_audio", 200)
        raise ValueError(f"{worker_name} worker returned invalid audio bytes")
    if len(data) > MAX_RESPONSE_BYTES:
        transport_failed("response_too_large", 200)
        raise ValueError(f"{worker_name} worker response exceeds the audio limit")
    try:
        params, _frames = read_pcm_wav(data)
    except ValueError:
        transport_failed("invalid_audio", 200)
        raise
    if params != SPEECH_PCM_FORMAT:
        transport_failed("audio_format_mismatch", 200)
        raise ValueError(f"Unexpected {worker_name} audio format")
    return data


def _decode_reference(encoded: object, transcript: object) -> tuple[bytes, bytes]:
    """Validate a bounded in-memory PCM reference and exact transcript."""
    if (not isinstance(encoded, str) or not encoded or
            len(encoded) > 4 * ((MAX_REFERENCE_BYTES + 2) // 3)):
        raise ValueError("Invalid reference audio size")
    if (not isinstance(transcript, str) or not transcript.strip() or len(transcript) > MAX_REFERENCE_TRANSCRIPT_CHARS or
            any(ord(char) < 32 and char not in "\n\r\t" for char in transcript)):
        raise ValueError("A bounded reference transcript is required")
    transcript.encode("utf-8")  # Reject lone surrogates before inference.
    data = base64.b64decode(encoded, validate=True)
    if len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference audio is too large")
    params, frames = read_pcm_wav(data)
    channels, width, rate = REFERENCE_WAV_FORMAT
    bytes_per_second = channels * width * rate
    if params != REFERENCE_WAV_FORMAT or not (
        MIN_REFERENCE_SECONDS * bytes_per_second <= len(frames) <= MAX_REFERENCE_SECONDS * bytes_per_second
    ):
        raise ValueError(
            f"Reference must be {MIN_REFERENCE_SECONDS} to {MAX_REFERENCE_SECONDS} seconds of "
            "24 kHz mono 16-bit PCM WAV"
        )
    return data, frames


def worker_server(synthesize: Callable[[dict[str, Any]], bytes], *, port: int = 8769,
                  runtime_info: Any = None, model: str = QWEN_MODEL,
                  health_info: Callable[[], dict[str, Any]] | None = None,
                  server_class: type[ThreadingHTTPServer] = ThreadingHTTPServer) -> ThreadingHTTPServer:
    """Build a loopback-only worker with injectable serialized inference."""
    engine = engine_for_model(model)
    spec = native_engine(engine)
    logger = get_logger("speech.worker")
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: Any) -> None:
            # Do not log manuscript requests or synthesis instructions.
            pass

        def reply(self, status: int, data: bytes, content_type: str = "application/json",
                  voice: str | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Lixity-Model", model)
            if voice is not None:
                self.send_header("X-Lixity-Voice", voice)
            self.end_headers()
            self.wfile.write(data)

        def _send_reply(self, status: int, data: bytes, content_type: str = "application/json",
                        voice: str | None = None, *, request_id: str | None = None,
                        render_id: str = "unknown") -> bool:
            try:
                self.reply(status, data, content_type, voice)
            except OSError:
                if request_id is None:
                    log_event(logger, "worker_transport", logging.WARNING, status="failed", category="transport")
                else:
                    log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                              engine=engine, status="failed", category="transport")
                return False
            return True

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_reply(200, json.dumps({"ready": True, "model": model,
                                                 **({"runtime": asdict(runtime_info)} if runtime_info is not None else {}),
                                                 **(health_info() if health_info is not None else {})}).encode())
            elif self.path == "/capabilities":
                self._send_reply(200, json.dumps(audio_capabilities()[engine]).encode())
            else:
                self._send_reply(404, b'{"error":"Not found"}')

        def do_POST(self) -> None:
            if self.path != "/v1/audio/speech":
                self._send_reply(404, b'{"error":"Not found"}')
                return
            request_id = token_hex(8)
            render_id = _valid_render_id(self.headers.get(_RENDER_ID_HEADER)) or "unknown"
            started = time.monotonic()
            # Browser pages cannot use this machine resource as a cross-origin API.
            if self.headers.get("Origin") or self.headers.get("Transfer-Encoding"):
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="rejected", category="forbidden")
                self._send_reply(403, b'{"error":"Unsupported request"}', request_id=request_id, render_id=render_id)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= (MAX_BASE_REQUEST_BYTES if spec.reference_required else MAX_REQUEST_BYTES):
                    raise ValueError("Invalid request size")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected JSON")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Truncated request")
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError("Invalid request fields")
                expected_fields = {"model", "input", "voice", "language", "instructions", "response_format"}
                if engine == "qwen3-design":
                    expected_fields.add("voice_description")
                if spec.reference_required:
                    expected_fields.update(("reference_audio", "reference_text"))
                if engine == "qwen3-base" and "x_vector_only" in request:
                    if type(request["x_vector_only"]) is not bool:
                        raise ValueError("Invalid speaker-embedding flag")
                    expected_fields.add("x_vector_only")
                if engine == "ims-toucan":
                    expected_fields.update(("phonemes", "prosody"))
                if set(request) != expected_fields:
                    raise ValueError("Invalid request fields")
                if request["model"] != model or request["response_format"] != "wav":
                    raise ValueError("Unsupported model or format")
                text = request["input"]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Invalid synthesis text")
                profile_fields = {"name": "Worker", "engine": engine, "language": request["language"],
                                  "voice": request["voice"], "instructions": request["instructions"],
                                  "voice_description": request.get("voice_description", "")}
                if spec.reference_required:
                    _decode_reference(request["reference_audio"], request["reference_text"])
                    profile_fields["reference_id"] = "0" * 64
                if engine == "ims-toucan":
                    if request["instructions"]:
                        raise ValueError("IMS Toucan does not support free-text direction")
                    profile_fields.update(phonemes=request["phonemes"], prosody=request["prosody"])
                profile = AudioProfile.model_validate(profile_fields)
                if len(text) > speech_segment_limit(profile):
                    raise ValueError("Invalid synthesis text")
            except OSError:
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="failed", category="transport")
                return
            except (ValueError, TypeError):
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="rejected", category="validation")
                self._send_reply(400, b'{"error":"Invalid synthesis request"}', request_id=request_id, render_id=render_id)
                return
            if not lock.acquire(blocking=False):
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="rejected", category="busy")
                self._send_reply(503, b'{"error":"Worker is busy"}', request_id=request_id, render_id=render_id)
                return
            phase = "synthesis"
            try:
                log_event(logger, "worker_synthesis", id=request_id, render_id=render_id, engine=engine, status="started")
                with speech_diagnostic_scope(request_id):
                    data = synthesize(request)
                if len(data) > MAX_RESPONSE_BYTES or read_pcm_wav(data)[0] != SPEECH_PCM_FORMAT:
                    raise ValueError("Unexpected generated audio format")
                phase = "response"
                if not self._send_reply(200, data, "audio/wav", request["voice"],
                                        request_id=request_id, render_id=render_id):
                    return
                log_event(logger, "worker_synthesis", id=request_id, render_id=render_id, engine=engine, status="success",
                          duration_ms=int((time.monotonic() - started) * 1000))
            except SpeechRequestValidationError as exc:
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="rejected", category="validation", code=exc.code,
                          duration_ms=int((time.monotonic() - started) * 1000))
                self._send_reply(400, json.dumps({"error": "Invalid synthesis request", "code": exc.code}).encode(),
                                 request_id=request_id, render_id=render_id)
            except Exception:  # noqa: BLE001 - optional inference adapter failures are reported locally
                category = "transport" if phase == "response" else "execution"
                log_event(logger, "worker_synthesis", logging.WARNING, id=request_id, render_id=render_id,
                          engine=engine, status="failed", category=category,
                          duration_ms=int((time.monotonic() - started) * 1000))
                if phase != "response":
                    self._send_reply(500, b'{"error":"Local synthesis failed"}', request_id=request_id, render_id=render_id)
            finally:
                lock.release()

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(30)

    server = server_class(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

