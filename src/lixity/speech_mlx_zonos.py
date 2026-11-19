"""Standalone ZONOS3 worker for the isolated MLX-Audio runtime.

Security boundaries:
- Forces offline Hugging Face / Transformers resolution before loading weights.
- Accepts only the pinned local ``mlx-community/ZONOS3-Mini`` checkpoint.
- Restricts generation keyword arguments to a fixed allowlist and bounds stdin.
- Refuses symlinked output or reference paths.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ALLOWED_MODEL = "mlx-community/ZONOS3-Mini"
MAX_STDIN_BYTES = 65536
_ALLOWED_KWARGS = frozenset({"lang_code", "speed", "temperature", "voice", "ref_audio"})


def _parse_request(raw: str) -> tuple[str, Path, dict[str, Any]]:
    if len(raw.encode("utf-8")) > MAX_STDIN_BYTES:
        raise ValueError("ZONOS3 worker request exceeds byte limit")
    payload: Any = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("ZONOS3 worker request must be a JSON object")
    model = payload.pop("model", None)
    if model != ALLOWED_MODEL:
        raise ValueError("ZONOS3 worker only accepts the pinned local ZONOS3-Mini model")
    text = payload.pop("input", None)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ZONOS3 worker requires non-empty input text")
    raw_output = payload.pop("output_path", None)
    if not isinstance(raw_output, str) or not raw_output:
        raise ValueError("ZONOS3 worker requires an output_path")
    output_path = Path(raw_output)
    if output_path.is_symlink() or not output_path.parent.is_dir():
        raise ValueError("ZONOS3 worker output_path must be a non-symlink file in an existing directory")
    unexpected = set(payload) - _ALLOWED_KWARGS
    if unexpected:
        raise ValueError(f"Unsupported ZONOS3 worker parameters: {sorted(unexpected)}")
    if "ref_audio" in payload:
        ref_value = payload["ref_audio"]
        if not isinstance(ref_value, str) or not ref_value:
            raise ValueError("ZONOS3 ref_audio must be a non-empty path")
        ref_path = Path(ref_value)
        if ref_path.is_symlink() or not ref_path.is_file():
            raise ValueError("ZONOS3 ref_audio must be an existing regular file")
    return text, output_path, payload


def main() -> int:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    raw = sys.stdin.read(MAX_STDIN_BYTES + 1)
    text, output_path, kwargs = _parse_request(raw)

    from mlx_audio.audio_io import write
    from mlx_audio.tts import load

    model = load(ALLOWED_MODEL)
    result = next(model.generate(text, **kwargs))
    write(str(output_path), result.audio, result.sample_rate, format="wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
