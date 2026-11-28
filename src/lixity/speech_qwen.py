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
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speech_references import VoiceReference

from .log import speech_diagnostic_id
from .speech_engines import native_endpoint, native_engine
from .speech_lifecycle import set_offline_hf_env, validate_worker_compute
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
        validate_worker_compute(self.device, self.threads, prefix="Qwen")
        if (self.dtype not in ("float32", "float16", "bfloat16")
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
                    reference: VoiceReference | None = None) -> bytes:
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


def _require_local_asset(path: Path) -> None:
    try:
        if path.is_file():
            with path.open("rb") as source:
                if source.read(1):
                    return
    except OSError as exc:
        raise ValueError(f"Unreadable local Qwen asset: {path.name}") from exc
    raise ValueError(f"Missing or empty local Qwen asset: {path.name}")


def _validate_local_weights(directory: Path) -> None:
    """Check supported local checkpoint layouts without reading tensor data."""
    for name in ("model.safetensors", "pytorch_model.bin"):
        if (directory / name).is_file():
            _require_local_asset(directory / name)
            return
    for name in ("model.safetensors.index.json", "pytorch_model.bin.index.json"):
        index = directory / name
        if not index.is_file():
            continue
        _require_local_asset(index)
        if index.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("Oversized local Qwen checkpoint index")
        metadata = json.loads(index.read_text(encoding="utf-8"))
        mapping = metadata.get("weight_map") if isinstance(metadata, dict) else None
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("Invalid local Qwen checkpoint index")
        shards: set[str] = set()
        for shard in mapping.values():
            if not isinstance(shard, str) or not shard or Path(shard).is_absolute() or ".." in Path(shard).parts:
                raise ValueError("Invalid local Qwen checkpoint shard")
            shards.add(shard)
        for shard in shards:
            _require_local_asset(directory / shard)
        return
    raise ValueError("Missing local Qwen checkpoint weights")


def validate_local_model(
    model_path: Path, *, device: str = "cpu", threads: int = 4, codec_device: str = "model",
    attention: str = "auto", codec_chunk_frames: int = 300, variant: str = "custom-voice",
) -> Path:
    """Validate local assets and options without importing inference dependencies."""
    if variant not in ("custom-voice", "voice-design", "base"):
        raise ValueError("Unknown Qwen model variant")
    validate_worker_compute(device, threads, prefix="Qwen")
    if codec_device not in ("cpu", "model"):
        raise ValueError("Qwen codec device must be cpu or model")
    if attention not in ("auto", "eager", "sdpa"):
        raise ValueError("Qwen attention must be auto, eager or sdpa")
    if type(codec_chunk_frames) is not int or not 16 <= codec_chunk_frames <= 300:
        raise ValueError("Qwen codec chunk frames must be an integer between 16 and 300")
    model_path = model_path.expanduser().resolve()
    config = json.loads((model_path / "config.json").read_text(encoding="utf-8"))
    expected_type = {"voice-design": "voice_design", "custom-voice": "custom_voice", "base": "base"}[variant]
    if (not isinstance(config, dict) or config.get("tts_model_type") != expected_type or
            config.get("tts_model_size") != "1b7" or config.get("tokenizer_type") != "qwen3_tts_tokenizer_12hz"):
        raise ValueError(f"A local Qwen3-TTS-12Hz-1.7B {variant} model is required")
    for name in ("generation_config.json", "tokenizer_config.json", "vocab.json", "merges.txt",
                 "speech_tokenizer/config.json", "speech_tokenizer/preprocessor_config.json"):
        _require_local_asset(model_path / name)
    _validate_local_weights(model_path)
    _validate_local_weights(model_path / "speech_tokenizer")
    return model_path


def load_local_model(
    model_path: Path, *, device: str = "cpu", threads: int = 4, codec_device: str = "model",
    attention: str = "auto", codec_chunk_frames: int = 300,
    variant: str = "custom-voice",
) -> LoadedRenderer:
    """Load an explicitly selected pinned Qwen architecture from local files."""
    model_path = validate_local_model(model_path, device=device, threads=threads, codec_device=codec_device,
                                      attention=attention, codec_chunk_frames=codec_chunk_frames, variant=variant)
    set_offline_hf_env()
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

    reference_key: tuple[str, str, bool] | None = None
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
                xvec_only = bool(request.get("x_vector_only", False))
                key = (
                    hashlib.sha256(data).hexdigest(),
                    hashlib.sha256(request["reference_text"].encode("utf-8")).hexdigest(),
                    xvec_only,
                )
                if key != reference_key:
                    np = importlib.import_module("numpy")
                    waveform = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
                    reference_prompt = model.create_voice_clone_prompt(
                        ref_audio=(waveform, SAMPLE_RATE),
                        ref_text=request["reference_text"],
                        x_vector_only_mode=xvec_only,
                    )
                    reference_key = key
                wavs, rate = model.generate_voice_clone(
                    text=request["input"],
                    language=QWEN_LANGUAGES[request["language"]],
                    voice_clone_prompt=reference_prompt,
                    x_vector_only_mode=xvec_only,
                    max_new_tokens=2048,
                )
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
    from .speech_lifecycle import add_lifecycle_arguments, serve_worker

    add_lifecycle_arguments(parser)
    args = parser.parse_args()
    options = {"device": args.device, "threads": args.threads, "codec_device": args.codec_device,
               "attention": args.attention, "codec_chunk_frames": args.codec_chunk_frames}
    if args.variant != "custom-voice":
        options["variant"] = args.variant
    path = validate_local_model(args.model, **options)
    model = {"custom-voice": QWEN_MODEL, "voice-design": QWEN_DESIGN_MODEL, "base": QWEN_BASE_MODEL}[args.variant]
    serve_worker(partial(load_local_model, path, **options), model=model, port=args.port,
                 idle_timeout_seconds=args.idle_timeout_seconds)


if __name__ == "__main__":
    main()
