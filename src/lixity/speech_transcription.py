"""Explicit transcription through a local MLX-Audio-compatible service."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import secrets
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .speech_providers import REQUEST_TIMEOUT_SECONDS, speech_endpoint

SCHEMA = "lixity-audio-transcription/1"
DEFAULT_MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
MAX_AUDIO_BYTES = 200 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str,
    ) -> None:
        return None


def transcription_endpoint(base_url: str) -> str:
    """Derive the OpenAI-compatible transcription endpoint from a speech base URL."""
    return speech_endpoint(base_url).replace("/audio/speech", "/audio/transcriptions")


def _read_audio(path: str | Path) -> tuple[Path, bytes, str]:
    requested = Path(path).expanduser()
    if requested.is_symlink():
        raise ValueError("Audio transcription input must not be a symlink")
    source = requested.resolve(strict=True)
    info = source.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > MAX_AUDIO_BYTES:
        raise ValueError("Audio transcription requires a nonempty regular file within the size limit")
    data = source.read_bytes()
    if len(data) != info.st_size or len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Audio changed while it was being read")
    return source, data, hashlib.sha256(data).hexdigest()


def _multipart(audio: Path, data: bytes, *, model: str, language: str | None) -> tuple[bytes, str]:
    boundary = "----lixity-" + secrets.token_hex(16)
    fields = {
        "model": model,
        "response_format": "verbose_json",
        "word_timestamps": "true",
    }
    if language:
        fields["language"] = language
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend((
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ))
    content_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
    suffix = audio.suffix.lower()
    filename = "audio" + (suffix if 1 < len(suffix) <= 10 and suffix[1:].isalnum() else ".bin")
    chunks.extend((
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        data,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ))
    return b"".join(chunks), boundary


def _word_timestamps(result: dict[str, Any]) -> list[dict[str, Any]]:
    words = result.get("words")
    if isinstance(words, list):
        return [dict(word) for word in words if isinstance(word, dict)]
    timestamps: list[dict[str, Any]] = []
    segments = result.get("segments")
    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(segment.get("words"), list):
                continue
            timestamps.extend(dict(word) for word in segment["words"] if isinstance(word, dict))
    if timestamps:
        return timestamps
    sentences = result.get("sentences")
    if isinstance(sentences, list):
        for sentence in sentences:
            if not isinstance(sentence, dict) or not isinstance(sentence.get("tokens"), list):
                continue
            for token in sentence["tokens"]:
                if not isinstance(token, dict):
                    continue
                timestamps.append({"word": token.get("text"), "start": token.get("start"),
                                   "end": token.get("end")})
    return timestamps


def transcribe_audio(
    audio_path: str | Path,
    *,
    model: str = DEFAULT_MODEL,
    language: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    opener: Any = None,
) -> dict[str, Any]:
    """Send one explicit multipart request and return validated transcript JSON."""
    if not model.strip() or model != model.strip() or len(model) > 200 or any(
        ord(character) < 32 for character in model
    ):
        raise ValueError("Transcription model must be bounded text without control characters")
    if language is not None and (
        not language.strip() or language != language.strip() or len(language) > 32
        or any(ord(character) < 32 for character in language)
    ):
        raise ValueError("Transcription language must be a short bounded code")
    source, data, digest = _read_audio(audio_path)
    payload, boundary = _multipart(source, data, model=model, language=language)
    request = urllib.request.Request(  # noqa: S310 - explicit validated service URL
        transcription_endpoint(base_url),
        data=payload,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise ValueError("Unexpected transcription response")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise RuntimeError(
            f"Transcription provider rejected the request (HTTP {code}); no redirect or retry was attempted"
        ) from None
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise RuntimeError("Transcription provider request failed or returned an invalid response") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Transcription response exceeds the byte limit")
    try:
        result = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("Transcription provider returned malformed JSON") from None
    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise ValueError("Transcription provider returned an invalid transcript")
    detected_language = result.get("language")
    return {
        **result,
        "schema_version": SCHEMA,
        "audio_sha256": digest,
        "model": model,
        "language": language if language is not None else detected_language,
        "words": _word_timestamps(result),
    }
