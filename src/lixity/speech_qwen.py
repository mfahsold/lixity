"""Fixed loopback Qwen CustomVoice adapter and optional offline worker.

Importing this module never imports the optional inference stack. The worker
requires a complete local model directory and disables Hugging Face networking.
"""
from __future__ import annotations

import argparse
import importlib
import io
import json
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .speech_profiles import (
    QWEN_LANGUAGES,
    QWEN_MODEL,
    QWEN_VOICES,
    AudioProfile,
    audio_capabilities,
)

ENDPOINT = "http://127.0.0.1:8769/v1/audio/speech"
MAX_REQUEST_BYTES = 16384
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
SAMPLE_RATE = 24000
# CPU synthesis can take substantially longer than the resulting audio.
SYNTHESIS_TIMEOUT_SECONDS = 3600


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def synthesize_qwen(text: str, profile: AudioProfile, *, opener: Any = None) -> bytes:
    """Request bounded PCM WAV from the fixed local worker, without fallback."""
    from .speech import MAX_SEGMENT_CHARS, _read_pcm

    profile = AudioProfile.model_validate(profile.model_dump())
    if profile.engine != "qwen3" or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
        raise ValueError("Invalid Qwen synthesis request")
    payload = json.dumps({"model": QWEN_MODEL, "input": text, "voice": profile.voice,
                          "language": profile.language, "instructions": profile.instructions,
                          "response_format": "wav"}).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Qwen synthesis request is too large")
    request = urllib.request.Request(ENDPOINT, data=payload,
                                     headers={"Content-Type": "application/json"})
    # Ignore proxy environment variables, even for localhost.
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=SYNTHESIS_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise RuntimeError("Qwen worker rejected the synthesis request")
            if (response.headers.get("X-Lixity-Model") != QWEN_MODEL or
                    response.headers.get("X-Lixity-Voice") != profile.voice):
                raise ValueError("Qwen worker model or voice mismatch")
            if response.headers.get_content_type() != "audio/wav":
                raise ValueError("Qwen worker returned an unexpected audio format")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # HTTPError owns a response stream even though open() raised before
        # entering the response context manager.
        exc.close()
        raise RuntimeError("Local Qwen worker is unavailable or failed") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Local Qwen worker is unavailable or failed") from exc
    if not isinstance(data, bytes):
        raise ValueError("Qwen worker returned invalid audio bytes")
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Qwen worker response exceeds the audio limit")
    params, _frames = _read_pcm(data)
    if params != (1, 2, SAMPLE_RATE):
        raise ValueError("Unexpected Qwen audio format")
    return data


def worker_server(synthesize: Callable[[dict[str, Any]], bytes], *, port: int = 8769) -> ThreadingHTTPServer:
    """Build a loopback-only worker with injectable serialized inference."""
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
            self.send_header("X-Lixity-Model", QWEN_MODEL)
            if voice is not None:
                self.send_header("X-Lixity-Voice", voice)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path == "/health":
                self.reply(200, json.dumps({"ready": True, "model": QWEN_MODEL}).encode())
            elif self.path == "/capabilities":
                self.reply(200, json.dumps(audio_capabilities()["qwen3"]).encode())
            else:
                self.reply(404, b'{"error":"Not found"}')

        def do_POST(self) -> None:
            from .speech import MAX_SEGMENT_CHARS, _read_pcm

            if self.path != "/v1/audio/speech":
                self.reply(404, b'{"error":"Not found"}')
                return
            # Browser pages cannot use this machine resource as a cross-origin API.
            if self.headers.get("Origin") or self.headers.get("Transfer-Encoding"):
                self.reply(403, b'{"error":"Unsupported request"}')
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_REQUEST_BYTES:
                    raise ValueError("Invalid request size")
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected JSON")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Truncated request")
                request = json.loads(raw)
                if not isinstance(request, dict) or set(request) != {
                    "model", "input", "voice", "language", "instructions", "response_format"
                }:
                    raise ValueError("Invalid request fields")
                if request["model"] != QWEN_MODEL or request["response_format"] != "wav":
                    raise ValueError("Unsupported model or format")
                text = request["input"]
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
                    raise ValueError("Invalid synthesis text")
                AudioProfile.model_validate({"name": "Worker", "engine": "qwen3", "language": request["language"],
                                             "voice": request["voice"], "instructions": request["instructions"]})
            except (ValueError, TypeError):
                self.reply(400, b'{"error":"Invalid synthesis request"}')
                return
            if not lock.acquire(blocking=False):
                self.reply(503, b'{"error":"Worker is busy"}')
                return
            try:
                data = synthesize(request)
                if len(data) > MAX_RESPONSE_BYTES or _read_pcm(data)[0] != (1, 2, SAMPLE_RATE):
                    raise ValueError("Unexpected generated audio format")
                self.reply(200, data, "audio/wav", request["voice"])
            except Exception:  # noqa: BLE001 - optional inference adapter failures are reported locally
                self.reply(500, b'{"error":"Local synthesis failed"}')
            finally:
                lock.release()

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(30)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def load_local_model(
    model_path: Path, *, device: str = "cpu", threads: int = 4,
) -> Callable[[dict[str, Any]], bytes]:
    """Load only the pinned CustomVoice architecture from local files, once."""
    if device not in ("cpu", "cuda"):
        raise ValueError("Qwen device must be cpu or cuda")
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError("Qwen threads must be an integer between 1 and 64")
    model_path = model_path.expanduser().resolve()
    config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
    if (config.get("tts_model_type") != "custom_voice" or
            config.get("tts_model_size") != "1b7" or config.get("tokenizer_type") != "qwen3_tts_tokenizer_12hz"):
        raise ValueError("A local Qwen3-TTS-12Hz-1.7B-CustomVoice model is required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch = importlib.import_module("torch")
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable; select cpu explicitly")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
        device_map, attention = "cuda:0", "sdpa"
    else:
        dtype, device_map, attention = torch.float32, "cpu", "eager"
    torch.set_num_threads(threads)
    qwen_tts = importlib.import_module("qwen_tts")

    model = qwen_tts.Qwen3TTSModel.from_pretrained(str(model_path), device_map=device_map, dtype=dtype,
                                                 attn_implementation=attention, local_files_only=True)
    speakers = {value.lower() for value in model.get_supported_speakers()}
    languages = {value.lower() for value in model.get_supported_languages()}
    if (not {value.lower() for value in QWEN_VOICES}.issubset(speakers) or
            not {value.lower() for value in QWEN_LANGUAGES.values()}.issubset(languages)):
        raise ValueError("Local Qwen model does not support the required presets and languages")

    def synthesize(request: dict[str, Any]) -> bytes:
        soundfile = importlib.import_module("soundfile")

        wavs, rate = model.generate_custom_voice(text=request["input"],
                                                language=QWEN_LANGUAGES[request["language"]],
                                                speaker=request["voice"], instruct=request["instructions"],
                                                max_new_tokens=2048)
        if rate != SAMPLE_RATE or len(wavs) != 1:
            raise ValueError("Unexpected Qwen output")
        output = io.BytesIO()
        soundfile.write(output, wavs[0], rate, format="WAV", subtype="PCM_16")
        return output.getvalue()

    return synthesize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Complete local CustomVoice model directory")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu",
                        help="Explicit inference device; unavailable CUDA fails without fallback")
    parser.add_argument("--threads", type=int, default=4, choices=range(1, 65), metavar="N",
                        help="Torch CPU threads (1..64; default 4)")
    parser.add_argument("--port", type=int, default=8769, choices=[8769])
    args = parser.parse_args()
    server = worker_server(load_local_model(args.model, device=args.device, threads=args.threads), port=args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
