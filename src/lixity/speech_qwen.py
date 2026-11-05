"""Fixed loopback Qwen CustomVoice adapter and optional offline worker.

Importing this module never imports the optional inference stack. The worker
requires a complete local model directory and disables Hugging Face networking.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import inspect
import io
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speech_references import SpeechReference

from .log import get_logger, speech_diagnostic_id
from .speech_engines import native_endpoint, native_engine
from .speech_profiles import (
    QWEN_BASE_MODEL,
    QWEN_DESIGN_MODEL,
    QWEN_LANGUAGES,
    QWEN_MODEL,
    QWEN_VOICES,
    AudioProfile,
)
from .speech_worker import (
    MAX_BASE_REQUEST_BYTES as MAX_BASE_REQUEST_BYTES,
)
from .speech_worker import (
    MAX_REFERENCE_BYTES as MAX_REFERENCE_BYTES,
)
from .speech_worker import (
    MAX_REQUEST_BYTES as MAX_REQUEST_BYTES,
)
from .speech_worker import (
    MAX_RESPONSE_BYTES as MAX_RESPONSE_BYTES,
)
from .speech_worker import (
    SAMPLE_RATE as SAMPLE_RATE,
)
from .speech_worker import (
    SYNTHESIS_TIMEOUT_SECONDS as SYNTHESIS_TIMEOUT_SECONDS,
)
from .speech_worker import (
    _decode_reference as _decode_reference,
)
from .speech_worker import (
    _NoRedirect as _NoRedirect,
)
from .speech_worker import (
    _valid_render_id as _valid_render_id,
)

ENDPOINT = native_endpoint("qwen3")
TARGET_ENDPOINTS = dict(native_engine("qwen3").endpoints)

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


def worker_health(target: str, *, engine: str = "qwen3", opener: Any = None) -> dict[str, Any]:
    """Probe one fixed target through the shared native transport."""
    from .speech_worker import worker_health as probe

    endpoints = TARGET_ENDPOINTS if engine in ("qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference") else None
    return probe(target, engine=engine, opener=opener, endpoints=endpoints)


def synthesize_qwen(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                    reference: SpeechReference | None = None) -> bytes:
    """Keep the established adapter entrypoint on the shared native transport."""
    from .speech_worker import synthesize_native

    if profile.engine not in ("qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference"):
        raise ValueError("Invalid Qwen synthesis request")
    if profile.engine.startswith("coqui") and target != "local":
        raise ValueError("Coqui supports only the local execution target")
    return synthesize_native(text, profile, target=target, opener=opener, reference=reference,
                             endpoints=TARGET_ENDPOINTS, diagnostic_id=speech_diagnostic_id())


def worker_server(synthesize: Callable[[dict[str, Any]], bytes], *, port: int = 8769,
                  runtime_info: WorkerRuntime | None = None, model: str = QWEN_MODEL) -> ThreadingHTTPServer:
    """Preserve the public factory while all HTTP validation has one owner."""
    from .speech_worker import worker_server as build_worker

    return build_worker(synthesize, port=port, runtime_info=runtime_info, model=model,
                        server_class=ThreadingHTTPServer)


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
    logger = get_logger("speech.worker")
    started = time.monotonic()
    logger.info("event=worker_model_load variant=%s device=%s status=started", args.variant, args.device)
    try:
        renderer = load_local_model(args.model, **options)
    except Exception:
        logger.warning("event=worker_model_load variant=%s device=%s status=failed duration_ms=%d",
                       args.variant, args.device, int((time.monotonic() - started) * 1000))
        raise
    logger.info("event=worker_model_load variant=%s device=%s status=ready duration_ms=%d",
                args.variant, args.device, int((time.monotonic() - started) * 1000))
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
