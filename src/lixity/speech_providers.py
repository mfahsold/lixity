"""Explicit OpenAI-compatible speech transport; no discovery or model loading.

Only synthesis reads credentials or sends text. Configuration and status checks
are local, and diagnostic errors never include URLs, secrets or response bodies.
"""
from __future__ import annotations

import atexit
import contextlib
import io
import ipaddress
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from string import Template
from typing import IO, TYPE_CHECKING, Any

from .audio_pcm import SPEECH_PCM_FORMAT, read_pcm_wav, wave_reader_is_integer_pcm
from .log import get_logger, log_event, speech_diagnostic_id

if TYPE_CHECKING:
    from .speech_profiles import AudioProfile
    from .speech_references import VoiceReference

ADAPTER_ID = "lixity-openai-speech/1"
MAX_REQUEST_BYTES = 32768
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 300
_LOCAL_NETWORKS = tuple(ipaddress.ip_network(network) for network in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",
))


def _validate_ip_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    scheme: str,
    allow_link_local: bool,
    error: str,
) -> None:
    unwrapped = getattr(address, "ipv4_mapped", None) or address
    if unwrapped.is_multicast or unwrapped.is_unspecified:
        raise ValueError(error)
    if unwrapped.is_link_local and not allow_link_local:
        raise ValueError(error)
    if scheme == "http" and not (
        unwrapped.is_loopback
        or any(unwrapped in network for network in _LOCAL_NETWORKS)
        or (allow_link_local and unwrapped.is_link_local)
    ):
        raise ValueError(error)


def speech_endpoint(base_url: str, *, allow_link_local: bool = False) -> str:
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
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if parsed.scheme == "http" and host.lower() != "localhost":
            raise ValueError(error) from None
    else:
        _validate_ip_address(
            address, scheme=parsed.scheme, allow_link_local=allow_link_local, error=error
        )
    path = parsed.path.rstrip("/")
    if not path.endswith("/audio/speech"):
        path += "/audio/speech" if path.endswith("/v1") else "/v1/audio/speech"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def validate_resolved_endpoint(endpoint: str, *, allow_link_local: bool = False) -> None:
    """Reject resolved IP addresses in link-local, multicast, or unspecified ranges."""
    error = "Speech endpoint resolved to a disallowed network address"
    parsed = urllib.parse.urlsplit(endpoint)
    host = parsed.hostname
    if not host:
        raise ValueError(error)
    address: ipaddress.IPv4Address | ipaddress.IPv6Address | None
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        _validate_ip_address(
            address, scheme=parsed.scheme, allow_link_local=allow_link_local, error=error
        )
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for *_prefix, sockaddr in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        raw_ip = str(sockaddr[0]).split("%", 1)[0]
        resolved = ipaddress.ip_address(raw_ip)
        unwrapped = getattr(resolved, "ipv4_mapped", None) or resolved
        if unwrapped.is_multicast or unwrapped.is_unspecified:
            raise ValueError(error)
        if unwrapped.is_link_local and not allow_link_local:
            raise ValueError(error)
        if parsed.scheme == "http" and host.lower() == "localhost" and not unwrapped.is_loopback:
            raise ValueError("Speech localhost endpoint must resolve to a loopback address")


def _zonos_worker_paths() -> tuple[Path, Path]:
    return (Path.home() / ".local/share/lixity/runtimes/mlx-audio/bin/python",
            Path(__file__).with_name("speech_mlx_zonos.py"))


def _zonos_worker_available(runtime: Path, worker_script: Path) -> bool:
    return runtime.is_file() and os.access(runtime, os.X_OK) and worker_script.is_file()


def _zonos_runtime_status(profile: AudioProfile | None) -> dict[str, Any]:
    from .speech_profiles import MLX_AUDIO_TTS_MODEL

    runtime, worker_script = _zonos_worker_paths()
    worker_env = _zonos_worker_env()
    # Use the cache precedence of huggingface_hub inside the isolated worker.
    xdg_cache = worker_env.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    hf_home = Template(os.path.expanduser(worker_env.get(
        "HF_HOME", os.path.join(xdg_cache, "huggingface")
    ))).safe_substitute(worker_env)
    hub_cache = Template(os.path.expanduser(worker_env.get(
        "HF_HUB_CACHE", os.path.join(hf_home, "hub")
    ))).safe_substitute(worker_env)
    model_directory = "models--" + MLX_AUDIO_TTS_MODEL.replace("/", "--")
    snapshots = Path(hub_cache) / model_directory / "snapshots"
    runtime_available = _zonos_worker_available(runtime, worker_script)
    model_cached = any(
        snapshot.joinpath("config.json").is_file()
        and (any(snapshot.rglob("*.safetensors")) or any(snapshot.rglob("*.gguf")))
        for snapshot in snapshots.glob("*/")
    )
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
    from .speech import _run_ffmpeg

    _validate_wav_container(data)
    try:
        params, _frames = read_pcm_wav(data)
    except ValueError:
        try:
            with wave.open(io.BytesIO(data), "rb") as reader:
                integer_pcm = wave_reader_is_integer_pcm(reader)
        except (wave.Error, EOFError):
            integer_pcm = False
        if integer_pcm:
            raise ValueError("Speech provider returned missing or truncated PCM audio") from None
        params = None  # Non-integer or unsupported WAV formats need the decoder.
    if params == SPEECH_PCM_FORMAT:
        return data
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("FFmpeg is required to normalize this provider WAV to mono 16-bit PCM at 24 kHz")
    with tempfile.TemporaryDirectory(prefix="lixity-provider-wav-") as directory:
        source, target = Path(directory) / "source.wav", Path(directory) / "normalized.wav"
        source.write_bytes(data)
        channels, _, rate = SPEECH_PCM_FORMAT
        result = _run_ffmpeg([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(source),
                              "-ac", str(channels), "-ar", str(rate), "-c:a", "pcm_s16le",
                              "-fs", str(MAX_RESPONSE_BYTES + 1), str(target)])
        if result.returncode or not target.is_file():
            raise ValueError("Speech provider WAV could not be decoded")
        if target.stat().st_size > MAX_RESPONSE_BYTES:
            raise ValueError("Normalized provider audio exceeds the byte limit")
        normalized = target.read_bytes()
        if read_pcm_wav(normalized)[0] != SPEECH_PCM_FORMAT:
            raise ValueError("Speech provider WAV could not be normalized")
        return normalized


def external_speech_request(text: str, profile: AudioProfile) -> dict[str, str | float]:
    """Build the adapter-specific speech JSON from one validated profile."""
    from .speech_direction import require_render_direction
    from .speech_profiles import MLX_AUDIO_TEMPERATURE, mlx_audio_uses_model_speed

    require_render_direction(profile, profile.instructions)
    request_data: dict[str, str | float] = {
        "model": profile.model, "input": text, "response_format": "wav",
    }
    if profile.engine == "mlx-audio":
        # ZONOS3 selects its speaker embedding from ``voice``; omitting the
        # preset would silently fall back to the adapter default ("jett").
        # Only reference cloning relies on ``ref_audio`` instead of ``voice``.
        if profile.voice != "reference":
            request_data["voice"] = profile.voice
        request_data["lang_code"] = profile.language
        if mlx_audio_uses_model_speed(profile):
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


def _zonos_worker_env() -> dict[str, str]:
    """Build a minimal offline environment so ambient secrets never reach MLX."""
    from .io import sanitized_subprocess_env

    return sanitized_subprocess_env(
        extra_allow=("HF_HOME", "HF_HUB_CACHE", "XDG_CACHE_HOME"),
        overrides={"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )


DEFAULT_ZONOS_IDLE_TIMEOUT_SECONDS = 300.0
DEFAULT_ZONOS_STARTUP_TIMEOUT_SECONDS = 120.0
DEFAULT_ZONOS_REQUEST_TIMEOUT_SECONDS = REQUEST_TIMEOUT_SECONDS


def _read_zonos_reply(pipe: IO[bytes], timeout_seconds: float, *, phase: str) -> bytes:
    """Read one bounded line without blocking the server thread indefinitely."""
    result: list[bytes | Exception] = []

    def _target() -> None:
        try:
            result.append(pipe.readline(4096))
        except Exception as exc:  # noqa: BLE001 - transport errors become bounded failures
            result.append(exc)

    reader = threading.Thread(target=_target, daemon=True)
    reader.start()
    reader.join(timeout_seconds)
    if reader.is_alive():
        from .speech import SpeechBackendTimeout

        raise SpeechBackendTimeout(f"Local ZONOS3 synthesis failed: worker {phase} timed out")
    if not result:
        return b""
    item = result[0]
    if isinstance(item, Exception):
        raise item
    return item


class _ZonosWorkerSession:
    """Keep the isolated ZONOS3 worker warm across segments and release on idle."""

    def __init__(
        self,
        *,
        idle_timeout_seconds: float = DEFAULT_ZONOS_IDLE_TIMEOUT_SECONDS,
        startup_timeout_seconds: float = DEFAULT_ZONOS_STARTUP_TIMEOUT_SECONDS,
        request_timeout_seconds: float = DEFAULT_ZONOS_REQUEST_TIMEOUT_SECONDS,
        popen_factory: Any = None,
    ) -> None:
        self._idle_timeout = idle_timeout_seconds
        self._startup_timeout = startup_timeout_seconds
        self._request_timeout = request_timeout_seconds
        self._popen_factory = popen_factory if popen_factory is not None else subprocess.Popen
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._runtime_key: tuple[str, str] | None = None
        self._timer: threading.Timer | None = None
        self._completed: float | None = None

    def _dispose(self) -> None:
        process = self._process
        self._process = None
        self._runtime_key = None
        if process is None:
            return
        try:
            if process.poll() is None:
                with contextlib.suppress(OSError):
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(OSError):
                        process.kill()
                    with contextlib.suppress(OSError):
                        process.wait()
        finally:
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()

    def _expire(self, completed: float) -> None:
        with self._lock:
            if self._completed == completed:
                self._dispose()

    def close(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._dispose()

    def synthesize(self, runtime: Path, worker_script: Path, worker_request: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(worker_request, ensure_ascii=False).encode("utf-8") + b"\n"
        key = (str(runtime), str(worker_script))
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if (self._process is not None
                    and (self._process.poll() is not None or self._runtime_key != key)):
                self._dispose()
            try:
                if self._process is None:
                    process = self._popen_factory(
                        [str(runtime), str(worker_script), "--persistent", str(os.getpid())],
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        env=_zonos_worker_env(),
                    )
                    self._process = process
                    self._runtime_key = key
                    if process.stdout is None:
                        raise RuntimeError("Local ZONOS3 worker failed to start")
                    banner_raw = _read_zonos_reply(process.stdout, self._startup_timeout, phase="startup")
                    banner = json.loads(banner_raw.decode("utf-8")) if banner_raw else {}
                    if (not isinstance(banner, dict) or banner.get("ready") is not True
                            or banner.get("model") != "mlx-community/ZONOS3-Mini"):
                        raise RuntimeError("Local ZONOS3 worker failed to start")
                process = self._process
                if process is None or process.stdin is None or process.stdout is None:
                    raise RuntimeError("Local ZONOS3 worker is unavailable")
                try:
                    process.stdin.write(payload)
                    process.stdin.flush()
                except (BrokenPipeError, OSError) as exc:
                    raise RuntimeError("Local ZONOS3 synthesis failed") from exc
                reply_raw = _read_zonos_reply(process.stdout, self._request_timeout, phase="response")
                reply = json.loads(reply_raw.decode("utf-8")) if reply_raw else {}
                if not isinstance(reply, dict) or reply.get("ok") is not True:
                    raise RuntimeError("Local ZONOS3 synthesis failed")
                token_count = reply.get("token_count")
                final_chunk = reply.get("is_final_chunk", True)
                if token_count is not None and (type(token_count) is not int or not 0 <= token_count <= 1_000_000):
                    raise RuntimeError("Local ZONOS3 worker returned invalid generation metadata")
                if type(final_chunk) is not bool:
                    raise RuntimeError("Local ZONOS3 worker returned invalid generation metadata")
                return {"token_count": token_count, "is_final_chunk": final_chunk}
            except Exception as exc:
                self._dispose()
                if isinstance(exc, RuntimeError):
                    raise
                raise RuntimeError("Local ZONOS3 synthesis failed") from exc
            finally:
                self._completed = time.monotonic()
                if self._process is not None and self._idle_timeout > 0:
                    self._timer = threading.Timer(self._idle_timeout, self._expire, args=(self._completed,))
                    self._timer.daemon = True
                    self._timer.start()


_ZONOS_SESSION = _ZonosWorkerSession()
atexit.register(_ZONOS_SESSION.close)


def close_zonos_worker() -> None:
    """Release any warm ZONOS3 subprocess owned by this process."""
    _ZONOS_SESSION.close()


def _synthesize_zonos_direct(text: str, profile: AudioProfile,
                             reference: VoiceReference | None) -> bytes:
    from .speech_references import SpeechReferenceSet
    from .speech_worker import validate_voice_reference

    runtime, worker_script = _zonos_worker_paths()
    if not _zonos_worker_available(runtime, worker_script):
        raise FileNotFoundError("ZONOS3 synthesis requires an executable local MLX-Audio runtime and worker script")
    validate_voice_reference(profile, reference)
    request_data = external_speech_request(text, profile)
    with tempfile.TemporaryDirectory(prefix="lixity-zonos-") as directory:
        os.chmod(directory, 0o700)
        output = Path(directory) / "speech.wav"
        worker_request: dict[str, Any] = dict(request_data)
        worker_request.pop("response_format", None)
        worker_request["output_path"] = str(output)
        if isinstance(reference, SpeechReferenceSet):
            reference_paths = []
            for index, part in enumerate(reference.parts, 1):
                reference_path = Path(directory) / f"reference-{index}.wav"
                reference_path.write_bytes(part.audio)
                reference_path.chmod(0o600)
                reference_paths.append(str(reference_path))
            worker_request["ref_audio_parts"] = reference_paths
        elif reference is not None:
            reference_path = Path(directory) / "reference.wav"
            reference_path.write_bytes(reference.audio)
            reference_path.chmod(0o600)
            worker_request["ref_audio"] = str(reference_path)
        metadata = _ZONOS_SESSION.synthesize(runtime, worker_script, worker_request)
        if output.is_symlink() or not output.is_file():
            raise RuntimeError("Local ZONOS3 synthesis failed")
        with output.open("rb") as stream:
            data = stream.read(MAX_RESPONSE_BYTES + 1)
    if not 44 < len(data) <= MAX_RESPONSE_BYTES:
        raise ValueError("Local ZONOS3 audio is empty or exceeds the byte limit")
    params, frames = read_pcm_wav(data)
    channels, width, rate = params
    duration = len(frames) / (channels * width * rate)
    token_count = metadata.get("token_count")
    log_event(get_logger("speech.transport"), "zonos_generation", logging.DEBUG,
              id=speech_diagnostic_id(), token_count=token_count,
              duration_seconds=round(duration, 3), final_chunk=metadata.get("is_final_chunk"))
    if metadata.get("is_final_chunk") is not True:
        raise RuntimeError("Local ZONOS3 synthesis returned an incomplete audio chunk")
    if token_count is not None and token_count >= 1990:
        raise RuntimeError("Local ZONOS3 synthesis reached its generation budget; text may be truncated")
    if not any(frames):
        raise RuntimeError("Local ZONOS3 synthesis returned silent audio")
    words = len(text.split())
    if (profile.language not in {"ja", "zh", "ko"} and words >= 3
            and duration < (words / (3.0 * profile.speed)) * 0.35):
        raise RuntimeError("Local ZONOS3 synthesis output is implausibly short; text may be truncated")
    return data


def synthesize_external(text: str, profile: AudioProfile, *, opener: Any = None,
                        reference: VoiceReference | None = None) -> bytes:
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
    try:
        validate_resolved_endpoint(endpoint)
    except OSError:
        if opener is None:
            raise RuntimeError("Speech provider request failed or returned an invalid response") from None
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
