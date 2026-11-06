"""Bounded, fixed-loopback transport shared by optional native speech workers."""
from __future__ import annotations

import base64
import json
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

from .log import get_logger, speech_diagnostic_id
from .speech_engines import QWEN_MODEL, engine_for_model, native_engine
from .speech_profiles import AudioProfile, audio_capabilities

if TYPE_CHECKING:
    from .speech_references import SpeechReference

MAX_REQUEST_BYTES = 32768
MAX_REFERENCE_BYTES = 2 * 1024 * 1024
MAX_BASE_REQUEST_BYTES = MAX_REQUEST_BYTES + 4 * ((MAX_REFERENCE_BYTES + 2) // 3)
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
SAMPLE_RATE = 24000
SYNTHESIS_TIMEOUT_SECONDS = 3600
_RENDER_ID_HEADER = "X-Lixity-Render-Id"


def _valid_render_id(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{16}", value) else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def worker_health(target: str, *, engine: str = "qwen3", opener: Any = None,
                  endpoints: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Probe the actual allowlisted model worker, never merely an open tunnel."""
    spec = native_engine(engine)
    if target not in spec.endpoints:
        raise ValueError("Unknown native speech execution target")
    endpoints = spec.endpoints if endpoints is None else endpoints
    request = urllib.request.Request(endpoints[target].replace("/v1/audio/speech", "/health"))  # noqa: S310 - fixed loopback allowlist
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    model_id = None
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
        state = "ready" if value["ready"] else "starting"
    except (OSError, ValueError, urllib.error.URLError):
        state = "unavailable"
    return {"target": target, "state": state, "transport": "loopback" if target == "local" else "ssh", "model": model_id}


def synthesize_native(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                    reference: SpeechReference | None = None,
                      endpoints: Mapping[str, str] | None = None, diagnostic_id: str | None = None) -> bytes:
    """Request bounded PCM WAV through a fixed loopback target, without fallback."""
    from .speech import MAX_SEGMENT_CHARS, _read_pcm

    profile = AudioProfile.model_validate(profile.model_dump())
    spec = native_engine(profile.engine)
    if target not in spec.endpoints:
        raise ValueError("Unknown native speech execution target")
    if not text.strip() or len(text) > MAX_SEGMENT_CHARS:
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
        request_data["phonemes"] = profile.phonemes
        request_data["prosody"] = profile.prosody.model_dump()
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(payload) > (MAX_BASE_REQUEST_BYTES if spec.reference_required else MAX_REQUEST_BYTES):
        raise ValueError("Qwen synthesis request is too large")
    headers = {"Content-Type": "application/json"}
    render_id = _valid_render_id(diagnostic_id if diagnostic_id is not None else speech_diagnostic_id())
    if render_id is not None:
        headers[_RENDER_ID_HEADER] = render_id
    request = urllib.request.Request(endpoints[target], data=payload,  # noqa: S310 - fixed loopback allowlist
                                     headers=headers)
    # Ignore proxy environment variables, even for localhost.
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=SYNTHESIS_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise RuntimeError(f"{worker_name} worker rejected the synthesis request")
            if (response.headers.get("X-Lixity-Model") != model_id or
                    response.headers.get("X-Lixity-Voice") != profile.voice):
                raise ValueError(f"{worker_name} worker model or voice mismatch")
            if response.headers.get_content_type() != "audio/wav":
                raise ValueError(f"{worker_name} worker returned an unexpected audio format")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # HTTPError owns a response stream even though open() raised before
        # entering the response context manager.
        actual_model = exc.headers.get("X-Lixity-Model") if exc.headers else None
        exc.close()
        if actual_model is not None and actual_model != model_id:
            model_kind = "Qwen model" if worker_name == "Qwen" else "model"
            raise RuntimeError(f"{worker_name} worker ({target}) is running a different {model_kind}; select the matching worker variant") from exc
        if exc.code == 400:
            raise RuntimeError(f"{worker_name} worker ({target}) rejected the synthesis request (HTTP 400); check the selected profile and model") from exc
        if exc.code == 500:
            raise RuntimeError(f"{worker_name} worker ({target}) reported synthesis failed (HTTP 500); check the worker runtime and resources") from exc
        if exc.code == 503:
            raise RuntimeError(f"{worker_name} worker ({target}) is busy (HTTP 503); retry after the current request finishes") from exc
        raise RuntimeError(f"{worker_name} worker ({target}) is unavailable or failed") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"{worker_name} worker ({target}) is unavailable or failed") from exc
    if not isinstance(data, bytes):
        raise ValueError("Qwen worker returned invalid audio bytes")
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Qwen worker response exceeds the audio limit")
    params, _frames = _read_pcm(data)
    if params != (1, 2, SAMPLE_RATE):
        raise ValueError("Unexpected Qwen audio format")
    return data


def _decode_reference(encoded: object, transcript: object) -> tuple[bytes, bytes]:
    """Validate a bounded in-memory PCM reference and exact transcript."""
    from .speech import _read_pcm

    if (not isinstance(encoded, str) or not encoded or
            len(encoded) > 4 * ((MAX_REFERENCE_BYTES + 2) // 3)):
        raise ValueError("Invalid reference audio size")
    if (not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 2000 or
            any(ord(char) < 32 and char not in "\n\r\t" for char in transcript)):
        raise ValueError("A bounded reference transcript is required")
    transcript.encode("utf-8")  # Reject lone surrogates before inference.
    data = base64.b64decode(encoded, validate=True)
    if len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("Reference audio is too large")
    params, frames = _read_pcm(data)
    if params != (1, 2, SAMPLE_RATE) or not SAMPLE_RATE * 2 <= len(frames) <= SAMPLE_RATE * 2 * 30:
        raise ValueError("Reference must be 1 to 30 seconds of 24 kHz mono 16-bit PCM WAV")
    return data, frames


def worker_server(synthesize: Callable[[dict[str, Any]], bytes], *, port: int = 8769,
                  runtime_info: Any = None, model: str = QWEN_MODEL,
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
                    logger.warning("event=worker_transport status=failed category=transport")
                else:
                    logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=failed category=transport",
                                   request_id, render_id, engine)
                return False
            return True

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send_reply(200, json.dumps({"ready": True, "model": model,
                                                 **({"runtime": asdict(runtime_info)} if runtime_info is not None else {})}).encode())
            elif self.path == "/capabilities":
                self._send_reply(200, json.dumps(audio_capabilities()[engine]).encode())
            else:
                self._send_reply(404, b'{"error":"Not found"}')

        def do_POST(self) -> None:
            from .speech import MAX_SEGMENT_CHARS, _read_pcm

            if self.path != "/v1/audio/speech":
                self._send_reply(404, b'{"error":"Not found"}')
                return
            request_id = token_hex(8)
            render_id = _valid_render_id(self.headers.get(_RENDER_ID_HEADER)) or "unknown"
            started = time.monotonic()
            # Browser pages cannot use this machine resource as a cross-origin API.
            if self.headers.get("Origin") or self.headers.get("Transfer-Encoding"):
                logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=rejected category=forbidden", request_id, render_id, engine)
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
                expected_fields = {"model", "input", "voice", "language", "instructions", "response_format"}
                if engine == "qwen3-design":
                    expected_fields.add("voice_description")
                if spec.reference_required:
                    expected_fields.update(("reference_audio", "reference_text"))
                if engine == "ims-toucan":
                    expected_fields.update(("phonemes", "prosody"))
                if not isinstance(request, dict) or set(request) != expected_fields:
                    raise ValueError("Invalid request fields")
                if request["model"] != model or request["response_format"] != "wav":
                    raise ValueError("Unsupported model or format")
                text = request["input"]
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
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
                AudioProfile.model_validate(profile_fields)
            except OSError:
                logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=failed category=transport",
                               request_id, render_id, engine)
                return
            except (ValueError, TypeError):
                logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=rejected category=validation", request_id, render_id, engine)
                self._send_reply(400, b'{"error":"Invalid synthesis request"}', request_id=request_id, render_id=render_id)
                return
            if not lock.acquire(blocking=False):
                logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=rejected category=busy", request_id, render_id, engine)
                self._send_reply(503, b'{"error":"Worker is busy"}', request_id=request_id, render_id=render_id)
                return
            phase = "synthesis"
            try:
                logger.info("event=worker_synthesis id=%s render_id=%s engine=%s status=started", request_id, render_id, engine)
                data = synthesize(request)
                if len(data) > MAX_RESPONSE_BYTES or _read_pcm(data)[0] != (1, 2, SAMPLE_RATE):
                    raise ValueError("Unexpected generated audio format")
                phase = "response"
                if not self._send_reply(200, data, "audio/wav", request["voice"],
                                        request_id=request_id, render_id=render_id):
                    return
                logger.info("event=worker_synthesis id=%s render_id=%s engine=%s status=success duration_ms=%d",
                            request_id, render_id, engine, int((time.monotonic() - started) * 1000))
            except Exception:  # noqa: BLE001 - optional inference adapter failures are reported locally
                category = "transport" if phase == "response" else "execution"
                logger.warning("event=worker_synthesis id=%s render_id=%s engine=%s status=failed category=%s duration_ms=%d",
                               request_id, render_id, engine, category, int((time.monotonic() - started) * 1000))
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

