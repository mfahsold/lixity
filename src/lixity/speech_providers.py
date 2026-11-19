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
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speech_profiles import AudioProfile
    from .speech_references import SpeechReference

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


def _zonos_runtime_status(profile: AudioProfile | None) -> dict[str, Any]:
    from .speech_profiles import MLX_AUDIO_TTS_MODEL

    runtime = Path.home() / ".local/share/lixity/runtimes/mlx-audio/bin/python"
    snapshots = Path.home() / ".cache/huggingface/hub/models--mlx-community--ZONOS3-Mini/snapshots"
    runtime_available = (runtime.is_file() and os.access(runtime, os.X_OK)
                         and Path(__file__).with_name("speech_mlx_zonos.py").is_file())
    model_cached = any(snapshot.joinpath("config.json").is_file()
                       and any(snapshot.glob("*.safetensors")) for snapshot in snapshots.glob("*/"))
    ready = runtime_available and model_cached
    return {
        "target": "local", "state": "ready" if ready else "unavailable", "transport": "isolated-process",
        "configured": profile is not None, "model": MLX_AUDIO_TTS_MODEL, "model_matches": True,
        "runtime_available": runtime_available, "model_cached": model_cached,
        "reason": "zonos_worker_ready" if ready else "zonos_worker_or_model_missing",
    }


def external_provider_status(profile: AudioProfile | None, *, engine: str | None = None) -> dict[str, Any]:
    """Describe provider configuration or inspect the fixed local ZONOS3 worker."""
    if ((profile is not None and _uses_zonos_direct_worker(profile))
            or (profile is None and engine == "mlx-audio")):
        return _zonos_runtime_status(profile)
    return {"target": "provider", "state": "unknown", "transport": "http",
            "configured": profile is not None, "model": profile.model if profile else None,
            "model_matches": None, "reason": "Provider readiness is unknown until an explicit render"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


def no_redirect_opener(opener: Any = None) -> Any:
    """Return an explicit opener or a direct no-proxy, no-redirect client."""
    return opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


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


def external_speech_request(text: str, profile: AudioProfile) -> dict[str, str | float]:
    """Build the adapter-specific speech JSON from one validated profile."""
    from .speech_profiles import MLX_AUDIO_DEFAULT_VOICE, MLX_AUDIO_TEMPERATURE

    request_data: dict[str, str | float] = {
        "model": profile.model, "input": text, "response_format": "wav",
    }
    if profile.engine == "mlx-audio":
        if profile.voice not in (MLX_AUDIO_DEFAULT_VOICE, "reference"):
            request_data["voice"] = profile.voice
        request_data["lang_code"] = profile.language
        request_data["speed"] = profile.speed
        request_data["temperature"] = MLX_AUDIO_TEMPERATURE
        return request_data
    request_data["voice"] = profile.voice
    if profile.instructions:
        request_data["instructions"] = profile.instructions
    return request_data


def _uses_zonos_direct_worker(profile: AudioProfile) -> bool:
    from .speech_profiles import MLX_AUDIO_BASE_URL, MLX_AUDIO_TTS_MODEL

    return (profile.engine == "mlx-audio" and profile.model == MLX_AUDIO_TTS_MODEL
            and speech_endpoint(profile.base_url) == speech_endpoint(MLX_AUDIO_BASE_URL))


_ZONOS_ALLOWED_ENV = (
    "HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "HF_HOME", "HF_HUB_CACHE", "XDG_CACHE_HOME",
)


def _zonos_worker_env() -> dict[str, str]:
    """Build a minimal offline environment so ambient secrets never reach MLX."""
    env = {key: os.environ[key] for key in _ZONOS_ALLOWED_ENV if key in os.environ}
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    return env


def _synthesize_zonos_direct(text: str, profile: AudioProfile,
                             reference: SpeechReference | None) -> bytes:
    from .speech_references import validate_reference

    runtime = Path.home() / ".local/share/lixity/runtimes/mlx-audio/bin/python"
    if not runtime.is_file():
        raise FileNotFoundError("The local MLX-Audio runtime is required for ZONOS3")
    if profile.voice == "reference":
        if reference is None or reference.id != profile.reference_id:
            raise ValueError("A verified reference is required for the selected ZONOS3 voice")
        validate_reference(reference)
    elif reference is not None:
        raise ValueError("A preset ZONOS3 voice cannot use a local reference")
    request_data = external_speech_request(text, profile)
    with tempfile.TemporaryDirectory(prefix="lixity-zonos-") as directory:
        os.chmod(directory, 0o700)
        output = Path(directory) / "speech.wav"
        worker_request = dict(request_data)
        worker_request.pop("response_format", None)
        worker_request["output_path"] = str(output)
        if reference is not None:
            reference_path = Path(directory) / "reference.wav"
            reference_path.write_bytes(reference.audio)
            worker_request["ref_audio"] = str(reference_path)
        result = subprocess.run(  # noqa: S603 - fixed isolated runtime and package worker
            [str(runtime), str(Path(__file__).with_name("speech_mlx_zonos.py"))],
            input=json.dumps(worker_request, ensure_ascii=False).encode("utf-8"),
            env=_zonos_worker_env(),
            capture_output=True, timeout=REQUEST_TIMEOUT_SECONDS, check=False,
        )
        if result.returncode != 0 or output.is_symlink() or not output.is_file():
            raise RuntimeError("Local ZONOS3 synthesis failed")
        with output.open("rb") as stream:
            data = stream.read(MAX_RESPONSE_BYTES + 1)
    if not 44 < len(data) <= MAX_RESPONSE_BYTES:
        raise ValueError("Local ZONOS3 audio is empty or exceeds the byte limit")
    return data


def synthesize_external(text: str, profile: AudioProfile, *, opener: Any = None,
                        reference: SpeechReference | None = None) -> bytes:
    """Send one explicit bounded request and return normalized PCM, without fallback."""
    from .speech import MAX_SEGMENT_CHARS
    from .speech_profiles import EXTERNAL_ENGINES, AudioProfile

    profile = AudioProfile.model_validate(profile.model_dump())
    if profile.engine not in EXTERNAL_ENGINES or not text.strip() or len(text) > MAX_SEGMENT_CHARS:
        raise ValueError("Invalid external speech synthesis request")
    if _uses_zonos_direct_worker(profile):
        return _normalize_wav(_synthesize_zonos_direct(text, profile, reference))
    if profile.engine == "mlx-audio" and profile.voice == "reference":
        raise ValueError("ZONOS3 reference voices require the default local MLX worker binding")
    endpoint = speech_endpoint(profile.base_url)
    request_data = external_speech_request(text, profile)
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
    client = no_redirect_opener(opener)
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
