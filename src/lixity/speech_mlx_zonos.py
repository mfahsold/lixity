"""Standalone ZONOS3 worker for the isolated MLX-Audio runtime.

Security boundaries:
- Forces offline Hugging Face / Transformers resolution before loading weights.
- Accepts only the pinned local ``mlx-community/ZONOS3-Mini`` checkpoint.
- Restricts generation keyword arguments to a fixed allowlist and bounds stdin.
- Refuses symlinked output or reference paths.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, TextIO

ALLOWED_MODEL = "mlx-community/ZONOS3-Mini"
MAX_STDIN_BYTES = 65536
_MAX_REFERENCE_BYTES = 3 * 1024 * 1024  # Matches the validated project WAV limit.
_MIN_REFERENCE_SET_PARTS = 3
_MAX_REFERENCE_SET_PARTS = 6
# Keep this standalone worker's method version aligned with speech_engines.
REFERENCE_SET_AGGREGATION_VERSION = "1"
_ALLOWED_KWARGS = frozenset({"lang_code", "speed", "temperature", "voice", "ref_audio", "ref_audio_parts"})


def _exit_with_parent(parent_pid: int) -> None:
    while os.getppid() == parent_pid:
        time.sleep(0.5)
    os._exit(1)


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
    if "ref_audio" in payload and "ref_audio_parts" in payload:
        raise ValueError("ZONOS3 ref_audio and ref_audio_parts are mutually exclusive")
    if "ref_audio_parts" in payload:
        ref_values = payload["ref_audio_parts"]
        if (not isinstance(ref_values, list)
                or not _MIN_REFERENCE_SET_PARTS <= len(ref_values) <= _MAX_REFERENCE_SET_PARTS):
            raise ValueError("ZONOS3 ref_audio_parts must contain three to six paths")
        for ref_value in ref_values:
            if not isinstance(ref_value, str) or not ref_value:
                raise ValueError("ZONOS3 ref_audio_parts entries must be non-empty paths")
            ref_path = Path(ref_value)
            if ref_path.is_symlink() or not ref_path.is_file():
                raise ValueError("ZONOS3 ref_audio_parts entries must be existing regular files")
    if "ref_audio" in payload:
        ref_value = payload["ref_audio"]
        if not isinstance(ref_value, str) or not ref_value:
            raise ValueError("ZONOS3 ref_audio must be a non-empty path")
        ref_path = Path(ref_value)
        if ref_path.is_symlink() or not ref_path.is_file():
            raise ValueError("ZONOS3 ref_audio must be an existing regular file")
    return text, output_path, payload


def _drain_truncated_line(first_chunk: str) -> None:
    """Discard the remainder of an overlong stdin line so the next read starts clean."""
    if first_chunk.endswith("\n") or first_chunk == "":
        return
    while True:
        chunk = sys.stdin.readline(MAX_STDIN_BYTES + 2)
        if not chunk or chunk.endswith("\n"):
            return


def _normalized_set_embedding(model: Any, references: list[str]) -> Any:
    """Normalize each finite speaker vector, average in order, then normalize."""
    import numpy as np

    embeddings = []
    for reference in references:
        embedding = np.asarray(model.extract_speaker_embedding(reference), dtype=np.float32)
        norm = float(np.linalg.norm(embedding))
        if not np.isfinite(embedding).all() or not math.isfinite(norm) or norm <= 0.0:
            raise ValueError("ZONOS3 returned an invalid speaker embedding")
        embeddings.append(embedding)
    shape = embeddings[0].shape
    if any(embedding.shape != shape for embedding in embeddings):
        raise ValueError("ZONOS3 returned mismatched speaker embedding shapes")
    normalized = [embedding / float(np.linalg.norm(embedding)) for embedding in embeddings]
    mean = np.mean(normalized, axis=0)
    norm = float(np.linalg.norm(mean))
    if not np.isfinite(mean).all() or not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("ZONOS3 returned an invalid combined speaker embedding")
    return mean / norm


def _reuse_speaker_embedding(
    model: Any,
    kwargs: dict[str, Any],
    cache: dict[bytes | tuple[str, tuple[bytes, ...]], Any],
) -> None:
    """Reuse single embeddings unchanged and version ordered set aggregation."""
    references = kwargs.get("ref_audio_parts")
    key: bytes | tuple[str, tuple[bytes, ...]]
    if references is None:
        reference = kwargs.get("ref_audio")
        if reference is None:
            return
        # Preserve the established single-reference byte key and raw embedding.
        with Path(reference).open("rb") as stream:
            audio = stream.read(_MAX_REFERENCE_BYTES + 1)
        if len(audio) > _MAX_REFERENCE_BYTES:
            raise ValueError("ZONOS3 reference exceeds the project WAV size limit")
        key = hashlib.sha256(audio).digest()
        if key not in cache:
            embedding = model.extract_speaker_embedding(reference)
            cache.clear()
            cache[key] = embedding
        kwargs["speaker_embedding"] = cache[key]
        del kwargs["ref_audio"]
        return
    if "ref_audio" in kwargs:
        raise ValueError("ZONOS3 ref_audio and ref_audio_parts are mutually exclusive")
    if (not isinstance(references, list)
            or not _MIN_REFERENCE_SET_PARTS <= len(references) <= _MAX_REFERENCE_SET_PARTS):
        raise ValueError("ZONOS3 ref_audio_parts must contain three to six paths")
    audio_parts = []
    for reference in references:
        # The caller uses private temporary paths per part. Match immutable bytes
        # and let the process lifetime scope the cache to the materialized model.
        with Path(reference).open("rb") as stream:
            audio = stream.read(_MAX_REFERENCE_BYTES + 1)
        if len(audio) > _MAX_REFERENCE_BYTES:
            raise ValueError("ZONOS3 reference exceeds the project WAV size limit")
        audio_parts.append(audio)
    hashes = tuple(hashlib.sha256(audio).digest() for audio in audio_parts)
    key = (REFERENCE_SET_AGGREGATION_VERSION, hashes)
    if key not in cache:
        cache.clear()
        cache[key] = _normalized_set_embedding(model, references)
    kwargs["speaker_embedding"] = cache[key]
    kwargs.pop("ref_audio_parts", None)


def _serve_persistent(protocol: TextIO, parent_pid: int) -> int:
    threading.Thread(target=_exit_with_parent, args=(parent_pid,), daemon=True).start()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    from mlx_audio.audio_io import write
    from mlx_audio.tts import load

    model = load(ALLOWED_MODEL)
    embeddings: dict[bytes | tuple[str, tuple[bytes, ...]], Any] = {}
    protocol.write(json.dumps({"ready": True, "model": ALLOWED_MODEL}) + "\n")
    protocol.flush()
    while True:
        raw = sys.stdin.readline(MAX_STDIN_BYTES + 2)
        if not raw:
            return 0
        if not raw.endswith("\n"):
            # Overlong line: the remainder would otherwise be parsed as a
            # separate request and fail every subsequent segment.
            _drain_truncated_line(raw)
            protocol.write('{"ok":false}\n')
            protocol.flush()
            continue
        try:
            text, output_path, kwargs = _parse_request(raw)
            _reuse_speaker_embedding(model, kwargs, embeddings)
            result = next(model.generate(text, **kwargs))
            write(str(output_path), result.audio, result.sample_rate, format="wav")
            protocol.write(json.dumps({
                "ok": True,
                "token_count": getattr(result, "token_count", None),
                "is_final_chunk": getattr(result, "is_final_chunk", True),
            }) + "\n")
        except Exception:  # noqa: BLE001 - report bounded status without echoing private text
            protocol.write('{"ok":false}\n')
        protocol.flush()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--persistent":
        # Keep Python and native dependency output off the JSON response pipe.
        with os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8") as protocol:
            sys.stdout.flush()
            os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
            return _serve_persistent(protocol, int(args[1]))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    raw = sys.stdin.read(MAX_STDIN_BYTES + 1)
    text, output_path, kwargs = _parse_request(raw)

    from mlx_audio.audio_io import write
    from mlx_audio.tts import load

    model = load(ALLOWED_MODEL)
    if "ref_audio_parts" in kwargs:
        _reuse_speaker_embedding(model, kwargs, {})
    result = next(model.generate(text, **kwargs))
    write(str(output_path), result.audio, result.sample_rate, format="wav")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
