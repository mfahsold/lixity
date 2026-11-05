"""Retained F5 transport; the unverified bundled inference loader is unavailable.

Saved profiles, references and plan exports remain readable. This module never
substitutes a different model or sends content to a different service.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .speech_engines import F5_MODEL as F5_MODEL
from .speech_engines import native_endpoint, native_engine
from .speech_profiles import AudioProfile
from .speech_references import SpeechReference

ENDPOINT = native_endpoint("f5-tts")
TARGET_ENDPOINTS = dict(native_engine("f5-tts").endpoints)
_RUNTIME_UNAVAILABLE = (
    "F5-TTS runtime integration is unavailable: the bundled checkpoint, vocabulary and vocoder loader "
    "was not compatible with upstream F5-TTS. Configure IMS-Toucan or an explicit external speech provider "
    "in a separate profile; existing F5 profiles and references are preserved."
)


def synthesize_f5(text: str, profile: AudioProfile, *, target: str = "local", opener: Any = None,
                  reference: SpeechReference | None = None) -> bytes:
    """Use the shared bounded transport for the fixed local F5 worker."""
    from .speech_worker import synthesize_native

    if profile.engine != "f5-tts":
        raise ValueError("Invalid F5-TTS synthesis request")
    return synthesize_native(text, profile, target=target, opener=opener, reference=reference,
                             endpoints=TARGET_ENDPOINTS)


def load_renderer(model_dir: Path, *, device: str = "cpu", threads: int = 4) -> Callable[[dict[str, Any]], bytes]:
    """Reject the retired loader explicitly, before any optional import or download."""
    if type(threads) is not int or not 1 <= threads <= 64:
        raise ValueError("Threads must be between 1 and 64")
    if device not in ("cpu", "cuda"):
        raise ValueError("Device must be cpu or cuda")
    model_dir = model_dir.expanduser().resolve(strict=True)
    if not any(path.is_file() for suffix in ("*.safetensors", "*.pt") for path in model_dir.glob(suffix)):
        raise ValueError("F5-TTS model directory requires a .safetensors or .pt checkpoint file")
    raise ValueError(_RUNTIME_UNAVAILABLE)


def main() -> None:
    parser = argparse.ArgumentParser(description=_RUNTIME_UNAVAILABLE)
    parser.add_argument("--model", type=Path, required=True, help="Path to local F5-TTS checkpoint directory")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="Compute device (default: cpu)")
    parser.add_argument("--threads", type=int, default=4, help="Torch CPU threads (default: 4)")
    parser.add_argument("--port", type=int, default=8771, choices=[8771], help="Worker port (default: 8771)")
    args = parser.parse_args()
    try:
        load_renderer(args.model, device=args.device, threads=args.threads)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
