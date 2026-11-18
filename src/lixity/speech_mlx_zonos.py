"""Standalone ZONOS3 worker for the isolated MLX-Audio runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def main() -> int:
    from mlx_audio.audio_io import write
    from mlx_audio.tts import load

    request: dict[str, Any] = json.loads(sys.stdin.read())
    output_path = Path(str(request.pop("output_path")))
    model = load(str(request.pop("model")))
    result = next(model.generate(str(request.pop("input")), **request))
    write(str(output_path), result.audio, result.sample_rate, format="wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
