"""Offline F5-TTS Flow-Matching speech adapter and optional local worker.

The optional inference stack is imported only by the worker. Model files must
already exist locally; no manuscript or reference is sent to a remote service.
"""
from __future__ import annotations

import argparse
import base64
import importlib
import io
import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .log import speech_diagnostic_id
from .speech_profiles import AudioProfile
from .speech_qwen import (
    MAX_BASE_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    SAMPLE_RATE,
    SYNTHESIS_TIMEOUT_SECONDS,
    _decode_reference,
    _NoRedirect,
    _valid_render_id,
    worker_server,
)
from .speech_references import SpeechReference

F5_MODEL = "SWivid/F5-TTS"
ENDPOINT = "http://127.0.0.1:8771/v1/audio/speech"
TARGET_ENDPOINTS = {"local": ENDPOINT}
_RENDER_ID_HEADER = "X-Lixity-Render-Id"


def synthesize_f5(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                  reference: SpeechReference | None = None) -> bytes:
    """Request bounded PCM WAV through a local F5-TTS worker target, without fallback."""
    from .speech import MAX_SEGMENT_CHARS, _read_pcm

    profile = AudioProfile.model_validate(profile.model_dump())
    if target not in TARGET_ENDPOINTS:
        raise ValueError("Unknown F5-TTS execution target")
    if profile.engine != "f5-tts" or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
        raise ValueError("Invalid F5-TTS synthesis request")
    from .speech_references import validate_reference
    if reference is None or reference.id != profile.reference_id:
        raise ValueError("F5-TTS requires the matching verified reference")
    validate_reference(reference)
    request_data = {
        "model": F5_MODEL,
        "input": text,
        "voice": profile.voice,
        "language": profile.language,
        "instructions": profile.instructions,
        "response_format": "wav",
        "reference_audio": base64.b64encode(reference.audio).decode("ascii"),
        "reference_text": reference.transcript,
    }
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_BASE_REQUEST_BYTES:
        raise ValueError("F5-TTS synthesis request is too large")
    headers = {"Content-Type": "application/json"}
    render_id = _valid_render_id(speech_diagnostic_id())
    if render_id is not None:
        headers[_RENDER_ID_HEADER] = render_id
    request = urllib.request.Request(TARGET_ENDPOINTS[target], data=payload, headers=headers)  # noqa: S310 - fixed loopback target
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=SYNTHESIS_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise RuntimeError("F5-TTS worker rejected the synthesis request")
            if (response.headers.get("X-Lixity-Model") != F5_MODEL or
                    response.headers.get("X-Lixity-Voice") != profile.voice):
                raise ValueError("F5-TTS worker model or voice mismatch")
            if response.headers.get_content_type() != "audio/wav":
                raise ValueError("F5-TTS worker returned an unexpected audio format")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        actual_model = exc.headers.get("X-Lixity-Model") if exc.headers else None
        exc.close()
        if actual_model is not None and actual_model != F5_MODEL:
            raise RuntimeError(f"F5-TTS worker ({target}) is running a different model; select the matching worker") from exc
        if exc.code == 400:
            raise RuntimeError(f"F5-TTS worker ({target}) rejected the synthesis request (HTTP 400); check the selected profile and model") from exc
        if exc.code == 500:
            raise RuntimeError(f"F5-TTS worker ({target}) reported synthesis failed (HTTP 500); check the worker runtime and resources") from exc
        if exc.code == 503:
            raise RuntimeError(f"F5-TTS worker ({target}) is busy (HTTP 503); retry after the current request finishes") from exc
        raise RuntimeError(f"F5-TTS worker ({target}) is unavailable or failed") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"F5-TTS worker ({target}) is unavailable or failed") from exc
    if not isinstance(data, bytes):
        raise ValueError("F5-TTS worker returned invalid audio bytes")
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("F5-TTS worker response exceeds the audio limit")
    params, _frames = _read_pcm(data)
    if params != (1, 2, SAMPLE_RATE):
        raise ValueError("Unexpected F5-TTS audio format")
    return data


def load_renderer(model_dir: Path, *, device: str = "cpu", threads: int = 4) -> Callable[[dict[str, Any]], bytes]:
    """Load local F5-TTS checkpoint and return a serialized renderer."""
    if not 1 <= threads <= 64:
        raise ValueError("Threads must be between 1 and 64")
    if device not in ("cpu", "cuda"):
        raise ValueError("Device must be cpu or cuda")
    model_dir = model_dir.expanduser().resolve(strict=True)
    checkpoint = model_dir / "model_1200000.safetensors"
    if not checkpoint.is_file():
        candidates = list(model_dir.glob("*.safetensors")) + list(model_dir.glob("*.pt"))
        if not candidates:
            raise ValueError("F5-TTS model directory requires a .safetensors or .pt checkpoint file")
        checkpoint = candidates[0]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    torch = importlib.import_module("torch")
    torch.set_num_threads(threads)
    soundfile = importlib.import_module("soundfile")
    f5_module = importlib.import_module("f5_tts.model")
    # Load model architecture and load weights safely
    model = f5_module.CFM(
        transformer=f5_module.DiT(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
        mel_spec_kwargs={
            "n_fft": 1024,
            "hop_length": 256,
            "win_length": 1024,
            "n_mel_channels": 100,
            "target_sample_rate": SAMPLE_RATE,
        },
        odeint_kwargs={"method": "euler"},
        vocab_char_map=f5_module.utils_infer.get_tokenizer(model_dir, "custom"),
    )
    checkpoint_data = torch.load(checkpoint, map_location=device, weights_only=True)
    if "ema_model_state_dict" in checkpoint_data:
        model.load_state_dict(checkpoint_data["ema_model_state_dict"])
    elif "model_state_dict" in checkpoint_data:
        model.load_state_dict(checkpoint_data["model_state_dict"])
    else:
        model.load_state_dict(checkpoint_data)
    model.to(device=device)
    model.eval()

    def render(request: dict[str, Any]) -> bytes:
        data, _frames = _decode_reference(request["reference_audio"], request["reference_text"])
        ref_file = io.BytesIO(data)
        ref_audio, _ref_sr = soundfile.read(ref_file)
        with torch.inference_mode():
            wav, _sr, _spectrogram = f5_module.utils_infer.infer_process(
                ref_audio, request["reference_text"], request["input"], model,
                target_sample_rate=SAMPLE_RATE, device=device
            )
        output = io.BytesIO()
        soundfile.write(output, wav, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        return output.getvalue()

    return render


def main() -> None:
    parser = argparse.ArgumentParser(description="Lixity F5-TTS Flow-Matching offline worker")
    parser.add_argument("--model", type=Path, required=True, help="Path to local F5-TTS checkpoint directory")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="Compute device (default: cpu)")
    parser.add_argument("--threads", type=int, default=4, help="Torch CPU threads (default: 4)")
    parser.add_argument("--port", type=int, default=8771, choices=[8771], help="Worker port (default: 8771)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s UTC %(levelname)s lixity.speech.f5 %(message)s")
    logging.info("event=worker_load engine=f5-tts model=%s device=%s", args.model, args.device)
    renderer = load_renderer(args.model, device=args.device, threads=args.threads)
    logging.info("event=worker_ready engine=f5-tts port=%d", args.port)
    server = worker_server(renderer, port=args.port, model=F5_MODEL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
