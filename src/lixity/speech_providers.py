"""Explicit OpenAI-compatible speech transport; no discovery or model loading.

Only synthesis reads credentials or sends text. Configuration and status checks
are local, and diagnostic errors never include URLs, secrets or response bodies.
"""
from __future__ import annotations

import io
import ipaddress
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speech_profiles import AudioProfile

ADAPTER_ID = "lixity-openai-speech/1"
MAX_REQUEST_BYTES = 32768
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 300
_LOCAL_NETWORKS = tuple(ipaddress.ip_network(network) for network in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "fc00::/7", "fe80::/10",
))


def speech_endpoint(base_url: str) -> str:
    """Validate an explicit base URL and derive its standard speech endpoint."""
    error = "Speech base URL requires HTTPS or a local HTTP address, without credentials, query or fragment"
    if not base_url or any(char.isspace() or ord(char) < 32 for char in base_url) or "\\" in base_url:
        raise ValueError(error)
    try:
        parsed = urllib.parse.urlsplit(base_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError(error) from None
    if (parsed.scheme not in ("http", "https") or not host or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment or "?" in base_url
            or "#" in base_url or (port is not None and not 1 <= port <= 65535)):
        raise ValueError(error)
    if parsed.scheme == "http" and host.lower() != "localhost":
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(error) from None
        if not (address.is_loopback or any(address in network for network in _LOCAL_NETWORKS)):
            raise ValueError(error)
    path = parsed.path.rstrip("/")
    if not path.endswith("/audio/speech"):
        path += "/audio/speech" if path.endswith("/v1") else "/v1/audio/speech"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def external_provider_status(profile: AudioProfile | None) -> dict[str, Any]:
    """Describe configuration without probing a provider or reading its key."""
    return {"target": "provider", "state": "unknown", "transport": "http",
            "configured": profile is not None, "model": profile.model if profile else None,
            "model_matches": None, "reason": "Provider readiness is unknown until an explicit render"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def _validate_wav_container(data: bytes) -> None:
    """Reject incomplete RIFF/chunks before a decoder can salvage partial audio."""
    if len(data) < 12 or not (data[:4] == b"RIFF" and data[8:12] == b"WAVE"):
        raise ValueError("Speech provider did not return a WAV file")
    error = "Speech provider returned an incomplete or truncated WAV container"
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        raise ValueError(error)
    position = 12
    while position < len(data):
        if len(data) - position < 8:
            raise ValueError(error)
        size = int.from_bytes(data[position + 4:position + 8], "little")
        end = position + 8 + size
        if end > len(data):
            raise ValueError(error)
        # Some PCM writers omit the final odd-byte pad. The declared sample
        # bytes must still be complete; intermediate chunks require padding.
        position = end + (size % 2 if end < len(data) else 0)


def _normalize_wav(data: bytes) -> bytes:
    from .speech import _read_pcm, _run_ffmpeg

    _validate_wav_container(data)
    try:
        params, _frames = _read_pcm(data)
    except ValueError:
        try:
            with wave.open(io.BytesIO(data), "rb"):
                pass
        except (wave.Error, EOFError):
            params = None  # Float/extended WAV formats require an explicit decoder.
        else:
            raise ValueError("Speech provider returned missing or truncated PCM audio") from None
    if params == (1, 2, 24000):
        return data
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("FFmpeg is required to normalize this provider WAV to mono 16-bit PCM at 24 kHz")
    with tempfile.TemporaryDirectory(prefix="lixity-provider-wav-") as directory:
        source, target = Path(directory) / "source.wav", Path(directory) / "normalized.wav"
        source.write_bytes(data)
        result = _run_ffmpeg([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(source),
                              "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le",
                              "-fs", str(MAX_RESPONSE_BYTES + 1), str(target)])
        if result.returncode or not target.is_file():
            raise ValueError("Speech provider WAV could not be decoded")
        if target.stat().st_size > MAX_RESPONSE_BYTES:
            raise ValueError("Normalized provider audio exceeds the byte limit")
        normalized = target.read_bytes()
        if _read_pcm(normalized)[0] != (1, 2, 24000):
            raise ValueError("Speech provider WAV could not be normalized")
        return normalized


def synthesize_external(text: str, profile: AudioProfile, *, opener: Any = None) -> bytes:
    """Send one explicit bounded request and return normalized PCM, without fallback."""
    from .speech import MAX_SEGMENT_CHARS
    from .speech_profiles import AudioProfile

    profile = AudioProfile.model_validate(profile.model_dump())
    if profile.engine != "openai-compatible" or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
        raise ValueError("Invalid external speech synthesis request")
    endpoint = speech_endpoint(profile.base_url)
    request_data = {"model": profile.model, "input": text, "voice": profile.voice, "response_format": "wav"}
    if profile.instructions:
        request_data["instructions"] = profile.instructions
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("External speech request exceeds the byte limit")
    headers = {"Content-Type": "application/json", "Accept": "audio/wav"}
    if profile.api_key_env is not None:
        key = os.environ.get(profile.api_key_env)
        if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise ValueError("Speech API key environment variable is missing or invalid")
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(endpoint, data=payload, headers=headers)  # noqa: S310 - explicit validated provider configuration
    client = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with client.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise ValueError("Unexpected status")
            if response.headers.get_content_type() not in ("audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"):
                raise ValueError("Unexpected response type")
            size = response.headers.get("Content-Length")
            if size is not None and not 0 < int(size) <= MAX_RESPONSE_BYTES:
                raise ValueError("Unexpected response size")
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise RuntimeError(f"Speech provider rejected the request (HTTP {code}); no redirect or retry was attempted") from None
    except Exception:  # noqa: BLE001 - transport adapters must not expose private request or response data
        raise RuntimeError("Speech provider request failed or returned an invalid response") from None
    if not isinstance(data, bytes) or not 44 < len(data) <= MAX_RESPONSE_BYTES:
        raise ValueError("Speech provider audio is empty or exceeds the byte limit")
    return _normalize_wav(data)
