"""Offline Coqui Thorsten worker with optional OpenVoice reference conversion.

The optional inference stack is imported only by the worker. Model files must
already exist locally; no manuscript or reference is sent to a remote service.
"""
from __future__ import annotations

import argparse
import importlib
import io
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .speech_profiles import COQUI_MODEL, COQUI_REFERENCE_MODEL
from .speech_qwen import SAMPLE_RATE, _decode_reference, worker_server


def load_renderer(model_dir: Path, converter_dir: Path | None = None, *, threads: int = 4) -> Callable[[dict[str, Any]], bytes]:
    """Load local checkpoints and return a serialized-worker renderer."""
    if not 1 <= threads <= 64:
        raise ValueError("Threads must be between 1 and 64")
    model_dir = model_dir.expanduser().resolve(strict=True)
    model_file, config_file = model_dir / "model_file.pth", model_dir / "config.json"
    if not model_file.is_file() or not config_file.is_file():
        raise ValueError("Coqui model directory requires model_file.pth and config.json")
    if converter_dir is not None:
        converter_dir = converter_dir.expanduser().resolve(strict=True)
        if not (converter_dir / "checkpoint.pth").is_file() or not (converter_dir / "config.json").is_file():
            raise ValueError("OpenVoice converter directory requires checkpoint.pth and config.json")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    torch = importlib.import_module("torch")
    torch.set_num_threads(threads)
    soundfile = importlib.import_module("soundfile")
    librosa = importlib.import_module("librosa")
    numpy = importlib.import_module("numpy")
    tts = importlib.import_module("TTS.api").TTS(model_path=str(model_file), config_path=str(config_file))
    # Upstream tokenizer logs entire manuscript segments on unknown phonemes.
    logging.getLogger("TTS").setLevel(logging.WARNING)
    logging.getLogger("TTS.tts.utils.text.tokenizer").setLevel(logging.ERROR)
    converter: Any = None
    if converter_dir is not None:
        config = importlib.import_module("TTS.vc.configs.openvoice_config").OpenVoiceConfig()
        converter = importlib.import_module("TTS.vc.models.openvoice").OpenVoice(config)
        converter.load_checkpoint(config, converter_dir / "checkpoint.pth", eval=True)

    def render(request: dict[str, Any]) -> bytes:
        with torch.inference_mode():
            tokenizer = tts.synthesizer.tts_model.tokenizer
            missing_before = len(tokenizer.not_found_characters)
            audio = numpy.asarray(tts.tts(text=request["input"]), dtype=numpy.float32)
            if len(tokenizer.not_found_characters) > missing_before:
                logging.getLogger("lixity.speech.worker").warning("Coqui discarded unsupported phonetic characters")
            rate = int(tts.synthesizer.output_sample_rate)
            if converter is not None:
                reference, _ = _decode_reference(request["reference_audio"], request["reference_text"])
                with tempfile.TemporaryDirectory(prefix="lixity-coqui-") as directory:
                    source = Path(directory) / "source.wav"
                    target = Path(directory) / "reference.wav"
                    soundfile.write(str(source), audio, rate, subtype="PCM_16")
                    target.write_bytes(reference)
                    audio = converter.voice_conversion(str(source), [str(target)])
                    rate = int(converter.config.audio.output_sample_rate)
            if rate != SAMPLE_RATE:
                audio = librosa.resample(audio, orig_sr=rate, target_sr=SAMPLE_RATE)
            output = io.BytesIO()
            soundfile.write(output, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
            return output.getvalue()
    return render


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Local Thorsten VITS model directory")
    parser.add_argument("--converter", type=Path, help="Local OpenVoice V2 converter directory")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    renderer = load_renderer(args.model, args.converter, threads=args.threads)
    server = worker_server(renderer, model=COQUI_REFERENCE_MODEL if args.converter else COQUI_MODEL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
