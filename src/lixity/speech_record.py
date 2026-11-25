"""Offline microphone recording and calibration using standard OSS components.

Supports ALSA (arecord/amixer), PipeWire (pw-record) and FFmpeg to record voice
references and calibrate input levels for author proofing and speech cloning.
"""
from __future__ import annotations

import array
import io
import logging
import math
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

from .audio_audit import _wave_reader_is_integer_pcm
from .io import sanitized_subprocess_env
from .log import get_logger, log_event
from .speech_recording_settings import MAX_REFERENCE_SECONDS, MIN_REFERENCE_SECONDS
from .speech_references import SpeechReference, save_reference
from .speech_worker import SAMPLE_RATE

DEFAULT_DEVICE = "default"
DEFAULT_MIXER_CONTROL = "Mic"
DEFAULT_CALIBRATION_SECONDS = 8.0
DEFAULT_CALIBRATION_COUNTDOWN = 4.0
CALIBRATION_SAMPLE_RATE = 48_000
MAX_CALIBRATION_SECONDS = 30
MAX_CAPTURE_GAIN = 100
_CONTROL_TIMEOUT_SECONDS = 15.0
NO_SIGNAL_DBFS = -120.0
_log = get_logger("speech.capture")


def _audio_tool_env() -> dict[str, str]:
    """Allow only audio-device session variables, never ambient API secrets."""
    return sanitized_subprocess_env(
        extra_allow=("XDG_RUNTIME_DIR", "PULSE_SERVER", "ALSA_CONFIG_PATH"),
        overrides={"LC_ALL": "C"},
    )


def _run_audio_tool(
    cmd: list[str],
    *,
    timeout: float = _CONTROL_TIMEOUT_SECONDS,
    capture_output: bool = True,
    text: bool = False,
    allow_timeout_stdout: bool = False,
) -> subprocess.CompletedProcess[Any] | None:
    """Run an external audio CLI tool with sanitized env and bounded timeout."""
    kwargs: dict[str, Any] = {
        "env": _audio_tool_env(),
        "timeout": timeout,
    }
    if capture_output:
        kwargs["capture_output"] = True
        if text:
            kwargs["text"] = True
    else:
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL
    started = time.monotonic()
    result: subprocess.CompletedProcess[Any] | None = None
    try:
        result = subprocess.run(cmd, check=False, **kwargs)  # noqa: S603 - fixed command vector
        outcome = "ok" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired as exc:
        outcome = "timeout"
        if allow_timeout_stdout and exc.stdout is not None:
            result = subprocess.CompletedProcess(cmd, -1, stdout=exc.stdout, stderr=exc.stderr)
            outcome = "duration_limit"
    except OSError:
        outcome = "unavailable"
    log_event(
        _log, "capture_tool_finished", logging.DEBUG,
        tool=Path(cmd[0]).name, outcome=outcome,
        elapsed_ms=round((time.monotonic() - started) * 1000, 1),
        exit_code=result.returncode if result is not None and outcome != "duration_limit" else None,
    )
    return result


def _alsa_mixer_args(command: str, card: int | str | None, control: str | None) -> list[str]:
    return [*(["-c", str(card)] if card is not None else []), command, *([control] if control is not None else [])]


def set_alsa_gain(gain: int, card: int | str | None = None, control: str = DEFAULT_MIXER_CONTROL) -> bool:
    """Set ALSA hardware capture gain safely without shell execution."""
    if not 0 <= gain <= MAX_CAPTURE_GAIN:
        raise ValueError(f"Gain must be between 0 and {MAX_CAPTURE_GAIN}")
    amixer = shutil.which("amixer")
    if amixer is None:
        return False
    cmd = [amixer, *_alsa_mixer_args("sset", card, control), "capture", str(gain)]
    res = _run_audio_tool(cmd, capture_output=False)
    return res is not None and res.returncode == 0


def _read_alsa_mixer(card: int | str | None, control: str | None) -> str | None:
    """Read one explicit ALSA control or enumerate the card's simple controls."""
    amixer = shutil.which("amixer")
    if amixer is None:
        return None
    cmd = [amixer, *_alsa_mixer_args("sget" if control is not None else "scontents", card, control)]
    res = _run_audio_tool(cmd, text=True)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else (res.stdout or "")


def get_alsa_gain(card: int | str | None = None, control: str = DEFAULT_MIXER_CONTROL) -> int | None:
    """Read current ALSA capture volume if available."""
    gain, _ = _alsa_gain_readback(card, control)
    return gain


def list_capture_devices() -> list[dict[str, Any]]:
    """List hardware audio capture devices detected by ALSA."""
    arecord = shutil.which("arecord")
    fallback = [{"card": None, "card_id": DEFAULT_DEVICE, "card_name": "Standard Audio", "device": 0,
                 "alsa_id": DEFAULT_DEVICE, "label": "Standard-Aufnahmegerät (default)"}]
    if arecord is None:
        return fallback
    res = _run_audio_tool([arecord, "-l"], text=True)
    if res is None or res.returncode != 0:
        return fallback
    stdout = res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else (res.stdout or "")
    devices: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        m = re.match(r"card\s+(\d+):\s+(\w+)\s+\[(.*?)\],\s+device\s+(\d+):\s+(.*?)\s+\[(.*?)\]", line)
        if m:
            c_num, c_id, c_name, d_num, d_name, _ = m.groups()
            devices.append({
                "card": int(c_num),
                "card_id": c_id,
                "card_name": c_name.strip(),
                "device": int(d_num),
                "device_name": d_name.strip(),
                "alsa_id": f"plughw:CARD={c_id},DEV={d_num}",
                "label": f"{c_name.strip()} ({d_name.strip()})",
            })
    return devices if devices else fallback


def get_alsa_gain_info(card: int | str | None = None, control: str = DEFAULT_MIXER_CONTROL) -> dict[str, Any] | None:
    """Read detailed ALSA capture gain info (current, min, max, percent, dB)."""
    _, info = _alsa_gain_readback(card, control)
    return info


def _alsa_gain_readback(card: int | str | None, control: str) -> tuple[int | None, dict[str, Any] | None]:
    """Return the observed value and any verified bounds from one mixer query."""
    stdout = _read_alsa_mixer(card, control)
    if stdout is None:
        return None, None
    return _parse_alsa_gain(stdout, card, control)


_CAPTURE_LIMITS = re.compile(r"^[ \t]*Limits:[^\n]*?\bCapture[ \t]+(-?\d+)[ \t]*-[ \t]*(-?\d+)", re.MULTILINE)


def _parse_alsa_gain(stdout: str, card: int | str | None, control: str) -> tuple[int | None, dict[str, Any] | None]:
    m_val = re.search(r"Capture[ \t]+(-?\d+)[ \t]+\[(?:(\d+)%\])?(?:[ \t]+\[([+-]?\d+(?:\.\d+)?)dB\])?", stdout)
    if not m_val:
        return None, None
    gain_val = int(m_val.group(1))
    m_lim = _CAPTURE_LIMITS.search(stdout)
    if not m_val.group(2) or not m_lim:
        return gain_val, None
    percent = int(m_val.group(2))
    db = float(m_val.group(3)) if m_val.group(3) else None
    min_lim, max_lim = map(int, m_lim.groups())
    if not min_lim <= gain_val <= max_lim:
        return gain_val, None
    return gain_val, {
        "card": card,
        "control": control,
        "gain": gain_val,
        "percent": percent,
        "db": db,
        "min": min_lim,
        "max": max_lim,
        "writable": 0 <= min_lim < max_lim <= MAX_CAPTURE_GAIN,
    }


def _discover_alsa_capture_gain(card: str) -> tuple[int | None, dict[str, Any] | None]:
    """Attribute gain only when ALSA exposes one unambiguous capture control."""
    stdout = _read_alsa_mixer(card, None)
    if not stdout:
        return None, None
    blocks = re.split(r"^Simple mixer control '(.+)',([0-9]+)[ \t]*\n", stdout, flags=re.MULTILINE)
    candidates = []
    for name, index, body in zip(blocks[1::3], blocks[2::3], blocks[3::3], strict=True):
        caps = re.search(r"^[ \t]*Capabilities:([^\n]*)", body, re.MULTILINE)
        caps_names = caps[1].split() if caps else ()
        if _CAPTURE_LIMITS.search(body) or "cvolume" in caps_names or (
            "volume" in caps_names and re.search(r"^[ \t]*Capture channels:", body, re.MULTILINE)
        ):
            candidates.append((name, index, body))
    if len(candidates) != 1:
        return None, None
    name, index, body = candidates[0]
    if index != "0" or name[0] in "-'\"" or "," in name or name != name.strip():
        return None, None
    return _parse_alsa_gain(body, card, name)


def _listed_card(device: str, devices: list[dict[str, Any]]) -> str | None:
    card = next(
        (str(item["card_id"]) for item in devices if item["alsa_id"] == device and item["card"] is not None),
        None,
    )
    if card is None:
        return None
    # A card-level control cannot be attributed to one of several capture inputs.
    return card if sum(item["card_id"] == card for item in devices) == 1 else None


def get_microphone_status(
    *, card: int | str | None = None, control: str | None = None, device: str | None = None,
) -> dict[str, Any]:
    """List capture devices and read the gain from the specified ALSA control."""
    devices = list_capture_devices()
    gain_info = None
    current_gain = None
    if device and device != DEFAULT_DEVICE:
        # A requested input has no implicit association with the default mixer.
        card = _listed_card(device, devices)
        if card is not None:
            if control is None:
                current_gain, gain_info = _discover_alsa_capture_gain(card)
            else:
                current_gain, gain_info = _alsa_gain_readback(card, control)
    else:
        current_gain, gain_info = _alsa_gain_readback(card, DEFAULT_MIXER_CONTROL if control is None else control)
    return {
        "schema_version": "lixity-microphone-status/1",
        "current_gain": current_gain,
        "gain_info": gain_info,
        "default_device": DEFAULT_DEVICE,
        "devices": devices,
    }


def set_microphone_gain(gain: int, card: int | str | None = None, control: str = DEFAULT_MIXER_CONTROL) -> bool:
    """Set capture gain safely and return success."""
    return set_alsa_gain(gain, card=card, control=control)


def record_audio(
    duration: float = 10.0,
    *,
    rate: int = SAMPLE_RATE,
    device: str | None = None,
    gain: int | None = None,
    countdown: float = 0.0,
) -> bytes:
    """Record mono 16-bit PCM WAV from microphone using arecord, pw-record or ffmpeg."""
    if not MIN_REFERENCE_SECONDS <= duration <= MAX_REFERENCE_SECONDS:
        raise ValueError(f"Recording duration must be between {MIN_REFERENCE_SECONDS} and {MAX_REFERENCE_SECONDS} seconds")
    if rate <= 0:
        raise ValueError("Recording sample rate must be positive")
    if not math.isfinite(countdown) or countdown < 0:
        raise ValueError("Countdown must be a finite, non-negative duration")

    dev = device or DEFAULT_DEVICE
    if gain is not None:
        card = _listed_card(dev, list_capture_devices()) if dev != DEFAULT_DEVICE else None
        control = DEFAULT_MIXER_CONTROL
        if dev != DEFAULT_DEVICE:
            _, info = _discover_alsa_capture_gain(card) if card is not None else (None, None)
            if info is None or not info["writable"]:
                raise ValueError("The recording input does not expose a single adjustable ALSA capture gain")
            if not info["min"] <= gain <= info["max"]:
                raise ValueError("Gain is outside the selected input's ALSA range")
            control = info["control"]
        if not set_alsa_gain(gain, card=card, control=control):
            raise RuntimeError("Could not set the recording input gain")

    if countdown > 0:
        time.sleep(countdown)

    # ALSA tools always receive the same input. An explicitly selected hardware
    # input is never replaced by another device or by PipeWire's default source.
    arecord = shutil.which("arecord")
    if arecord is not None:
        cmd = [
            arecord,
            "-D", dev,
            "-f", "S16_LE",
            "-r", str(rate),
            "-c", "1",
            "-d", str(math.ceil(duration)),
            "-t", "wav",
            "-q",
        ]
        res = _run_audio_tool(cmd, timeout=duration + 5.0)
        if res is not None and res.returncode == 0 and isinstance(res.stdout, bytes) and res.stdout.startswith(b"RIFF"):
            return _trim_wav_duration(res.stdout, duration)

    # 2. Try ffmpeg with the same ALSA input.
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        cmd = [
            ffmpeg, "-y", "-f", "alsa", "-i", dev, "-t", str(duration), "-ac", "1",
            "-ar", str(rate), "-c:a", "pcm_s16le", "-f", "wav", "pipe:1",
        ]
        res = _run_audio_tool(cmd, timeout=duration + 5.0)
        if res is not None and res.returncode == 0 and isinstance(res.stdout, bytes) and res.stdout.startswith(b"RIFF"):
            return _trim_wav_duration(res.stdout, duration)

    # PipeWire streams raw PCM to stdout so an interrupted capture does not
    # depend on the tool updating a WAV header before it exits.
    pw_record = shutil.which("pw-record")
    if pw_record is not None and dev == DEFAULT_DEVICE and gain is None:
        cmd = [
            pw_record, "--raw",
            "--rate", str(rate),
            "--channels", "1",
            "--format", "s16",
            "-",
        ]
        res = _run_audio_tool(cmd, timeout=duration, allow_timeout_stdout=True)
        if res is not None and res.returncode in (0, -1) and isinstance(res.stdout, bytes):
            frames = min(len(res.stdout) // 2, int(duration * rate))
            if frames:
                pcm = res.stdout[:frames * 2]
                if sys.byteorder == "big":
                    samples = array.array("h")
                    samples.frombytes(pcm)
                    samples.byteswap()
                    pcm = samples.tobytes()
                wav = io.BytesIO()
                with wave.open(wav, "wb") as writer:
                    writer.setparams((1, 2, rate, 0, "NONE", "not compressed"))
                    writer.writeframes(pcm)
                return wav.getvalue()

    if dev != DEFAULT_DEVICE:
        raise RuntimeError("Could not record from the selected ALSA input. Check that it is connected and available")
    raise RuntimeError("No working audio capture tool found (install arecord, ffmpeg or pw-record)")


def _trim_wav_duration(wav_data: bytes, target_seconds: float) -> bytes:
    """Trim complete capture frames and write a finalized WAV header."""
    try:
        with wave.open(io.BytesIO(wav_data), "rb") as reader:
            if not _wave_reader_is_integer_pcm(reader):
                return wav_data
            channels = reader.getnchannels()
            sampwidth = reader.getsampwidth()
            framerate = reader.getframerate()
            nframes = reader.getnframes()
            frames_to_keep = min(nframes, int(target_seconds * framerate))
            frames = reader.readframes(frames_to_keep)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as writer:
            writer.setnchannels(channels)
            writer.setsampwidth(sampwidth)
            writer.setframerate(framerate)
            writer.writeframes(frames)
        return buf.getvalue()
    except (wave.Error, OSError):
        return wav_data


def dbfs(v: float) -> float:
    """Calculate dBFS relative to 16-bit full scale."""
    return NO_SIGNAL_DBFS if v == 0.0 else 20.0 * math.log10(max(v, 1.0) / 32768.0)


def analyze_signal(wav_bytes: bytes) -> dict[str, Any]:
    """Descriptive signal analysis matching calibration requirements."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            if not _wave_reader_is_integer_pcm(w) or w.getsampwidth() != 2:
                raise ValueError("Signal analysis requires 16-bit integer PCM WAV")
            rate = w.getframerate()
            n = w.getnframes()
            data = array.array("h")
            data.frombytes(w.readframes(n))
            if sys.byteorder == "big":
                data.byteswap()
    except Exception as exc:
        raise ValueError(f"Invalid WAV audio data: {exc}") from exc

    if not data:
        return {
            "duration_seconds": 0.0,
            "sample_rate": rate,
            "signal_present": False,
            "peak_dbfs": NO_SIGNAL_DBFS,
            "clipping_samples": 0,
            "noise_floor_dbfs": NO_SIGNAL_DBFS,
            "snr_db": 0.0,
            "segments": [],
            "verdict": "too_quiet",
            "verdict_label": "MEHR LUFT ALS NÖTIG",
            "recommended_gain": None,
        }

    peak_val = max(abs(x) for x in data)
    peak_db = dbfs(float(peak_val))
    clipping = sum(1 for x in data if abs(x) >= 32600)

    # Noise floor: quietest 0.5s RMS window
    floors: list[float] = []
    segments: list[dict[str, Any]] = []
    half_sec = max(1, rate // 2)

    for i in range(math.floor(n / half_sec)):
        chunk = data[i * half_sec : (i + 1) * half_sec]
        if not chunk:
            break
        cp = max(abs(x) for x in chunk)
        rms = math.sqrt(sum(x * x for x in chunk) / len(chunk))
        floors.append(rms)
        segments.append({
            "time_seconds": round(i * 0.5, 1),
            "peak_dbfs": round(dbfs(float(cp)), 1),
            "rms_dbfs": round(dbfs(rms), 1),
            "clipping": cp >= 32600,
        })

    floor_db = dbfs(min(floors)) if floors else NO_SIGNAL_DBFS
    snr_db = max(0.0, peak_db - floor_db)

    # Verdict according to calibration rubric:
    # Target: Burst-Peaks between -13.0 and -7.0 dBFS
    if -13.0 <= peak_db <= -7.0:
        verdict = "calibrated"
        verdict_label = "CALIBRIERT FÜR AUFNAHMEN!"
    elif peak_db > -7.0:
        verdict = "too_hot"
        verdict_label = "ZU HEISS"
    else:
        verdict = "too_quiet"
        verdict_label = "MEHR LUFT ALS NÖTIG"

    return {
        "duration_seconds": round(n / rate, 2),
        "sample_rate": rate,
        "signal_present": peak_val > 0,
        "peak_dbfs": round(peak_db, 1),
        "clipping_samples": clipping,
        "noise_floor_dbfs": round(floor_db, 1),
        "snr_db": round(snr_db, 1),
        "segments": segments,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "recommended_gain": None,
    }


def run_calibration(
    gain: int | None = None,
    duration: float = DEFAULT_CALIBRATION_SECONDS,
    countdown: float = DEFAULT_CALIBRATION_COUNTDOWN,
    device: str | None = None,
) -> dict[str, Any]:
    """Measure one test capture and suggest gain only for a verified control."""
    if not MIN_REFERENCE_SECONDS <= duration <= MAX_CALIBRATION_SECONDS:
        raise ValueError(f"Calibration duration must be between {MIN_REFERENCE_SECONDS} and {MAX_CALIBRATION_SECONDS} seconds")
    raw_wav = record_audio(duration, rate=CALIBRATION_SAMPLE_RATE, countdown=countdown, device=device, gain=gain)
    metrics = analyze_signal(raw_wav)
    current_gain = None
    mixer = None
    if device and device != DEFAULT_DEVICE:
        card = _listed_card(device, list_capture_devices())
        if card is not None:
            current_gain, info = _discover_alsa_capture_gain(card)
            if info:
                mixer = {"card": card, "control": info["control"]}
                if metrics["signal_present"] and info["writable"]:
                    delta = {"too_hot": -10, "too_quiet": 6, "calibrated": 0}[metrics["verdict"]]
                    metrics["recommended_gain"] = max(info["min"], min(info["max"], info["gain"] + delta))
    elif gain is not None:
        # An explicit gain request uses ALSA. The logical input still has no
        # stable association with a physical control.
        current_gain = get_alsa_gain()
    return {
        "schema_version": "lixity-audio-calibration/1",
        "current_gain": current_gain,
        "mixer": mixer,
        **metrics,
    }


def record_and_save_reference(
    project: str | Path,
    duration: float,
    transcript: str,
    *,
    gain: int | None = None,
    device: str | None = None,
) -> SpeechReference:
    """Record speech directly from microphone and store as immutable project reference."""
    audio = record_audio(duration, rate=SAMPLE_RATE, gain=gain, device=device)
    return save_reference(project, audio, transcript)
