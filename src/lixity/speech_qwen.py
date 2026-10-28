"""Fixed loopback Qwen CustomVoice adapter and optional offline worker.

Importing this module never imports the optional inference stack. The worker
requires a complete local model directory and disables Hugging Face networking.
"""
from __future__ import annotations

import argparse
import base64
import gc
import hashlib
import importlib
import inspect
import io
import json
import os
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speech_references import SpeechReference

from .speech_profiles import (
    QWEN_BASE_MODEL,
    QWEN_DESIGN_MODEL,
    QWEN_LANGUAGES,
    QWEN_MODEL,
    QWEN_VOICES,
    AudioProfile,
    audio_capabilities,
)

ENDPOINT = "http://127.0.0.1:8769/v1/audio/speech"
TARGET_ENDPOINTS = {"local": ENDPOINT, "jetson": "http://127.0.0.1:8770/v1/audio/speech"}
MAX_REQUEST_BYTES = 32768
MAX_REFERENCE_BYTES = 2 * 1024 * 1024
MAX_BASE_REQUEST_BYTES = MAX_REQUEST_BYTES + 4 * ((MAX_REFERENCE_BYTES + 2) // 3)
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
SAMPLE_RATE = 24000
# CPU synthesis can take substantially longer than the resulting audio.
SYNTHESIS_TIMEOUT_SECONDS = 3600


@dataclass(frozen=True)
class WorkerRuntime:
    """Bounded resolved loading settings, not a checkpoint or hardware digest."""

    device: str
    dtype: str
    threads: int
    attention: str
    codec_device: str
    codec_chunk_frames: int = 300

    def __post_init__(self) -> None:
        if (self.device not in ("cpu", "cuda")
                or self.dtype not in ("float32", "float16", "bfloat16")
                or type(self.threads) is not int or not 1 <= self.threads <= 64
                or self.attention not in ("eager", "sdpa")
                or self.codec_device not in ("cpu", "cuda")
                or type(self.codec_chunk_frames) is not int or not 16 <= self.codec_chunk_frames <= 300):
            raise ValueError("Invalid Qwen worker runtime settings")


@dataclass(frozen=True)
class LoadedRenderer:
    """One loaded renderer with its explicit, non-sensitive runtime settings."""

    render: Callable[[dict[str, Any]], bytes]
    runtime_info: WorkerRuntime

    def __call__(self, request: dict[str, Any]) -> bytes:
        return self.render(request)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def worker_health(target: str, *, opener: Any = None) -> dict[str, Any]:
    """Probe the actual allowlisted model worker, never merely an open tunnel."""
    if target not in TARGET_ENDPOINTS:
        raise ValueError("Unknown Qwen execution target")
    request = urllib.request.Request(TARGET_ENDPOINTS[target].replace("/v1/audio/speech", "/health"))  # noqa: S310 - fixed loopback allowlist
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    model_id = None
    try:
        with client.open(request, timeout=1.5) as response:
            raw = response.read(4097)
        if len(raw) > 4096:
            raise ValueError("Oversized health response")
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("model") not in (QWEN_MODEL, QWEN_DESIGN_MODEL, QWEN_BASE_MODEL) or type(value.get("ready")) is not bool:
            raise ValueError("Unexpected worker identity")
        model_id = value["model"]
        state = "ready" if value["ready"] else "starting"
    except (OSError, ValueError, urllib.error.URLError):
        state = "unavailable"
    return {"target": target, "state": state, "transport": "loopback" if target == "local" else "ssh", "model": model_id}


def synthesize_qwen(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                    reference: SpeechReference | None = None) -> bytes:
    """Request bounded PCM WAV through a fixed loopback target, without fallback."""
    from .speech import MAX_SEGMENT_CHARS, _read_pcm

    profile = AudioProfile.model_validate(profile.model_dump())
    if target not in TARGET_ENDPOINTS:
        raise ValueError("Unknown Qwen execution target")
    if profile.engine not in ("qwen3", "qwen3-design", "qwen3-base") or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
        raise ValueError("Invalid Qwen synthesis request")
    model_id = QWEN_BASE_MODEL if profile.engine == "qwen3-base" else QWEN_DESIGN_MODEL if profile.engine == "qwen3-design" else QWEN_MODEL
    request_data = {"model": model_id, "input": text, "voice": profile.voice,
                          "language": profile.language, "instructions": profile.instructions,
                          "response_format": "wav"}
    if profile.engine == "qwen3-design":
        request_data["voice_description"] = profile.voice_description
    elif profile.engine == "qwen3-base":
        from .speech_references import validate_reference
        if reference is None or reference.id != profile.reference_id:
            raise ValueError("Qwen Base requires the matching verified reference")
        validate_reference(reference)
        request_data["reference_audio"] = base64.b64encode(reference.audio).decode("ascii")
        request_data["reference_text"] = reference.transcript
    elif reference is not None:
        raise ValueError("This Qwen model does not use a reference")
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(payload) > (MAX_BASE_REQUEST_BYTES if profile.engine == "qwen3-base" else MAX_REQUEST_BYTES):
        raise ValueError("Qwen synthesis request is too large")
    request = urllib.request.Request(TARGET_ENDPOINTS[target], data=payload,  # noqa: S310 - fixed loopback allowlist
                                     headers={"Content-Type": "application/json"})
    # Ignore proxy environment variables, even for localhost.
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=SYNTHESIS_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise RuntimeError("Qwen worker rejected the synthesis request")
            if (response.headers.get("X-Lixity-Model") != model_id or
                    response.headers.get("X-Lixity-Voice") != profile.voice):
                raise ValueError("Qwen worker model or voice mismatch")
            if response.headers.get_content_type() != "audio/wav":
                raise ValueError("Qwen worker returned an unexpected audio format")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # HTTPError owns a response stream even though open() raised before
        # entering the response context manager.
        actual_model = exc.headers.get("X-Lixity-Model") if exc.headers else None
        exc.close()
        if actual_model in (QWEN_MODEL, QWEN_DESIGN_MODEL, QWEN_BASE_MODEL) and actual_model != model_id:
            raise RuntimeError(f"Qwen worker ({target}) is running a different Qwen model; select the matching worker variant") from exc
        if exc.code == 400:
            raise RuntimeError(f"Qwen worker ({target}) rejected the synthesis request (HTTP 400); check the selected profile and model") from exc
        if exc.code == 500:
            raise RuntimeError(f"Qwen worker ({target}) reported synthesis failed (HTTP 500); check the worker runtime and resources") from exc
        if exc.code == 503:
            raise RuntimeError(f"Qwen worker ({target}) is busy (HTTP 503); retry after the current request finishes") from exc
        raise RuntimeError(f"Qwen worker ({target}) is unavailable or failed") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Qwen worker ({target}) is unavailable or failed") from exc
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
                  runtime_info: WorkerRuntime | None = None, model: str = QWEN_MODEL) -> ThreadingHTTPServer:
    """Build a loopback-only worker with injectable serialized inference."""
    if model not in (QWEN_MODEL, QWEN_DESIGN_MODEL, QWEN_BASE_MODEL):
        raise ValueError("Unsupported worker model")
    engine = "qwen3-base" if model == QWEN_BASE_MODEL else "qwen3-design" if model == QWEN_DESIGN_MODEL else "qwen3"
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

        def do_GET(self) -> None:
            if self.path == "/health":
                self.reply(200, json.dumps({"ready": True, "model": model,
                                           **({"runtime": asdict(runtime_info)} if runtime_info is not None else {})}).encode())
            elif self.path == "/capabilities":
                self.reply(200, json.dumps(audio_capabilities()[engine]).encode())
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
                if not 0 < size <= (MAX_BASE_REQUEST_BYTES if engine == "qwen3-base" else MAX_REQUEST_BYTES):
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
                if engine == "qwen3-base":
                    expected_fields.update(("reference_audio", "reference_text"))
                if not isinstance(request, dict) or set(request) != expected_fields:
                    raise ValueError("Invalid request fields")
                if request["model"] != model or request["response_format"] != "wav":
                    raise ValueError("Unsupported model or format")
                text = request["input"]
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
                    raise ValueError("Invalid synthesis text")
                if engine == "qwen3-base":
                    if (request["voice"] != "reference" or request["instructions"] != "" or
                            request["language"] not in QWEN_LANGUAGES):
                        raise ValueError("Unsupported reference voice controls")
                    _decode_reference(request["reference_audio"], request["reference_text"])
                else:
                    AudioProfile.model_validate({"name": "Worker", "engine": engine, "language": request["language"],
                                                 "voice": request["voice"], "instructions": request["instructions"],
                                                 "voice_description": request.get("voice_description", "")})
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
    model_path: Path, *, device: str = "cpu", threads: int = 4, codec_device: str = "model",
    attention: str = "auto", codec_chunk_frames: int = 300,
    variant: str = "custom-voice",
) -> LoadedRenderer:
    """Load an explicitly selected pinned Qwen architecture from local files."""
    if variant not in ("custom-voice", "voice-design", "base"):
        raise ValueError("Unknown Qwen model variant")
    if device not in ("cpu", "cuda"):
        raise ValueError("Qwen device must be cpu or cuda")
    if codec_device not in ("cpu", "model"):
        raise ValueError("Qwen codec device must be cpu or model")
    if attention not in ("auto", "eager", "sdpa"):
        raise ValueError("Qwen attention must be auto, eager or sdpa")
    if type(codec_chunk_frames) is not int or not 16 <= codec_chunk_frames <= 300:
        raise ValueError("Qwen codec chunk frames must be an integer between 16 and 300")
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError("Qwen threads must be an integer between 1 and 64")
    model_path = model_path.expanduser().resolve()
    config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
    expected_type = {"voice-design": "voice_design", "custom-voice": "custom_voice", "base": "base"}[variant]
    if (config.get("tts_model_type") != expected_type or
            config.get("tts_model_size") != "1b7" or config.get("tokenizer_type") != "qwen3_tts_tokenizer_12hz"):
        raise ValueError(f"A local Qwen3-TTS-12Hz-1.7B {variant} model is required")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch = importlib.import_module("torch")
    if device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is unavailable; select cpu explicitly")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported(including_emulation=False) else torch.float16
        device_map, default_attention = "cuda:0", "sdpa"
    else:
        dtype, device_map, default_attention = torch.float32, "cpu", "eager"
    attention = default_attention if attention == "auto" else attention
    torch.set_num_threads(threads)
    qwen_tts = importlib.import_module("qwen_tts")

    model = qwen_tts.Qwen3TTSModel.from_pretrained(str(model_path), device_map=device_map, dtype=dtype,
                                                 attn_implementation=attention, local_files_only=True)
    if codec_chunk_frames != 300:
        # The upstream public tokenizer decode API exposes no chunk setting.
        # Bind only this loaded decoder's existing overlap-and-trim algorithm;
        # keep its 25-frame left context and leave the default path untouched.
        try:
            decoder = model.model.speech_tokenizer.model.decoder
            chunked_decode = decoder.chunked_decode
            signature = inspect.signature(chunked_decode)
            for name in ("chunk_size", "left_context_size"):
                if signature.parameters[name].kind not in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY,
                ):
                    raise ValueError("Codec chunk settings must accept keyword arguments")
            signature.bind(object(), chunk_size=codec_chunk_frames, left_context_size=25)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("Local Qwen codec does not support explicit chunk settings") from exc
        decoder.chunked_decode = partial(chunked_decode, chunk_size=codec_chunk_frames, left_context_size=25)
    if device == "cuda" and codec_device == "cpu":
        # Keep the talker on CUDA while moving only audio decoding to CPU.
        codec = model.model.speech_tokenizer
        codec.model.to(device="cpu", dtype=torch.float32)
        codec.device = torch.device("cpu")
        gc.collect()
        torch.cuda.empty_cache()
    speakers = {value.lower() for value in model.get_supported_speakers()} if variant == "custom-voice" else set()
    languages = {value.lower() for value in model.get_supported_languages()}
    if ((variant == "custom-voice" and not {value.lower() for value in QWEN_VOICES}.issubset(speakers)) or
            not {value.lower() for value in QWEN_LANGUAGES.values()}.issubset(languages)):
        raise ValueError("Local Qwen model does not support the required presets and languages")

    reference_key: tuple[str, str] | None = None
    reference_prompt: Any = None

    def synthesize(request: dict[str, Any]) -> bytes:
        nonlocal reference_key, reference_prompt
        soundfile = importlib.import_module("soundfile")

        # CustomVoice includes codec decoding; its upstream no_grad guard does
        # not disable view tracking and version-counter overhead as this does.
        with torch.inference_mode():
            if variant == "base":
                if request.get("instructions", ""):
                    raise ValueError("Qwen Base does not support delivery instructions")
                data, frames = _decode_reference(request["reference_audio"], request["reference_text"])
                key = (hashlib.sha256(data).hexdigest(), hashlib.sha256(request["reference_text"].encode("utf-8")).hexdigest())
                if key != reference_key:
                    np = importlib.import_module("numpy")
                    waveform = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
                    reference_prompt = model.create_voice_clone_prompt(
                        ref_audio=(waveform, SAMPLE_RATE), ref_text=request["reference_text"], x_vector_only_mode=False)
                    reference_key = key
                wavs, rate = model.generate_voice_clone(text=request["input"],
                    language=QWEN_LANGUAGES[request["language"]], voice_clone_prompt=reference_prompt, max_new_tokens=2048)
            elif variant == "voice-design":
                instruction = " ".join(part for part in (request["voice_description"], request["instructions"]) if part)
                wavs, rate = model.generate_voice_design(text=request["input"],
                                                        language=QWEN_LANGUAGES[request["language"]],
                                                        instruct=instruction, max_new_tokens=2048)
            else:
                wavs, rate = model.generate_custom_voice(text=request["input"],
                                                        language=QWEN_LANGUAGES[request["language"]],
                                                        speaker=request["voice"], instruct=request["instructions"],
                                                        max_new_tokens=2048)
        if rate != SAMPLE_RATE or len(wavs) != 1:
            raise ValueError("Unexpected Qwen output")
        output = io.BytesIO()
        soundfile.write(output, wavs[0], rate, format="WAV", subtype="PCM_16")
        return output.getvalue()

    return LoadedRenderer(synthesize, WorkerRuntime(
        device=device, dtype=str(dtype).removeprefix("torch."), threads=threads,
        attention=attention, codec_device="cpu" if device == "cpu" or codec_device == "cpu" else "cuda",
        codec_chunk_frames=codec_chunk_frames))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Complete local model directory")
    parser.add_argument("--variant", choices=["custom-voice", "voice-design", "base"], default="custom-voice")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu",
                        help="Explicit inference device; unavailable CUDA fails without fallback")
    parser.add_argument("--codec-device", choices=["cpu", "model"], default="model",
                        help="Audio decoder placement; model follows --device (default)")
    parser.add_argument("--attention", choices=["auto", "eager", "sdpa"], default="auto",
                        help="Attention backend; auto preserves eager on CPU and SDPA on CUDA")
    parser.add_argument("--codec-chunk-frames", type=int, default=300, choices=range(16, 301), metavar="N",
                        help="Codec frames per decode chunk (16..300; upstream default 300); retains 25-frame context")
    parser.add_argument("--threads", type=int, default=4, choices=range(1, 65), metavar="N",
                        help="Torch CPU threads (1..64; default 4)")
    parser.add_argument("--port", type=int, default=8769, choices=[8769])
    args = parser.parse_args()
    options = {"device": args.device, "threads": args.threads, "codec_device": args.codec_device,
               "attention": args.attention, "codec_chunk_frames": args.codec_chunk_frames}
    if args.variant != "custom-voice":
        options["variant"] = args.variant
    renderer = load_local_model(args.model, **options)
    server_options: dict[str, Any] = {"port": args.port, "runtime_info": renderer.runtime_info}
    if args.variant == "voice-design":
        server_options["model"] = QWEN_DESIGN_MODEL
    elif args.variant == "base":
        server_options["model"] = QWEN_BASE_MODEL
    server = worker_server(renderer, **server_options)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
