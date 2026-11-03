"""Offline microphone recording and calibration using standard OSS components.

Supports ALSA (arecord/amixer), PipeWire (pw-record) and FFmpeg to record voice
references and calibrate input levels for author proofing and speech cloning.
"""
from __future__ import annotations

import array
import io
import math
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any

from .speech_qwen import SAMPLE_RATE
from .speech_references import SpeechReference, save_reference

DEFAULT_DEVICE = "plughw:CARD=I3000,DEV=0"
MAX_RECORD_SECONDS = 30.0
MIN_RECORD_SECONDS = 1.0


def set_alsa_gain(gain: int, card: int | str = 1, control: str = "Mic") -> bool:
    """Set ALSA hardware capture gain safely without shell execution."""
    if not 0 <= gain <= 100:
        raise ValueError("Gain must be between 0 and 100")
    amixer = shutil.which("amixer")
    if amixer is None:
        return False
    try:
        cmd = [amixer, "-c", str(card), "sset", str(control), str(gain)]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)  # noqa: S603 - fixed command vector
        return res.returncode == 0
    except OSError:
        return False


def get_alsa_gain(card: int | str = 1, control: str = "Mic") -> int | None:
    """Read current ALSA capture volume if available."""
    amixer = shutil.which("amixer")
    if amixer is None:
        return None
    try:
        cmd = [amixer, "-c", str(card), "sget", str(control)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603 - fixed command vector
        if res.returncode != 0:
            return None
        stdout = res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else (res.stdout or "")
        match = re.search(r"Capture\s+(\d+)\s+\[", stdout)
        return int(match.group(1)) if match else None
    except OSError:
        return None


def list_capture_devices() -> list[dict[str, Any]]:
    """List hardware audio capture devices detected by ALSA."""
    arecord = shutil.which("arecord")
    fallback = [{"card": None, "card_id": "default", "card_name": "Standard Audio", "device": 0, "alsa_id": "default", "label": "Standard-Aufnahmegerät (default)"}]
    if arecord is None:
        return fallback
    try:
        res = subprocess.run([arecord, "-l"], capture_output=True, text=True, check=False)  # noqa: S603
        if res.returncode != 0:
            return fallback
        devices: list[dict[str, Any]] = []
        for line in res.stdout.splitlines():
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
    except OSError:
        return fallback


def get_alsa_gain_info(card: int | str = 1, control: str = "Mic") -> dict[str, Any] | None:
    """Read detailed ALSA capture gain info (current, min, max, percent, dB)."""
    amixer = shutil.which("amixer")
    if amixer is None:
        return None
    try:
        cmd = [amixer, "-c", str(card), "sget", str(control)]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
        if res.returncode != 0:
            return None
        stdout = res.stdout.decode("utf-8", errors="replace") if isinstance(res.stdout, bytes) else (res.stdout or "")
        m_val = re.search(r"Capture\s+(\d+)\s+\[(\d+)%\](?:\s+\[([-\d\.]+)dB\])?", stdout)
        m_lim = re.search(r"Limits:\s*Capture\s+(\d+)\s*-\s*(\d+)", stdout)
        if not m_val:
            return None
        gain_val = int(m_val.group(1))
        percent = int(m_val.group(2))
        db = float(m_val.group(3)) if m_val.group(3) else None
        min_lim = int(m_lim.group(1)) if m_lim else 0
        max_lim = int(m_lim.group(2)) if m_lim else 50
        return {
            "card": card,
            "control": control,
            "gain": gain_val,
            "percent": percent,
            "db": db,
            "min": min_lim,
            "max": max_lim,
        }
    except OSError:
        return None


def get_microphone_status() -> dict[str, Any]:
    """Return a comprehensive snapshot of microphone hardware and settings."""
    devices = list_capture_devices()
    gain_info = get_alsa_gain_info()
    current_gain = gain_info["gain"] if gain_info else get_alsa_gain()
    return {
        "schema_version": "lixity-microphone-status/1",
        "current_gain": current_gain,
        "gain_info": gain_info,
        "default_device": DEFAULT_DEVICE,
        "devices": devices,
    }


def set_microphone_gain(gain: int, card: int | str = 1, control: str = "Mic") -> bool:
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
    if not MIN_RECORD_SECONDS <= duration <= MAX_RECORD_SECONDS:
        raise ValueError(f"Recording duration must be between {MIN_RECORD_SECONDS} and {MAX_RECORD_SECONDS} seconds")

    if gain is not None:
        set_alsa_gain(gain)

    if countdown > 0:
        time.sleep(countdown)

    # 1. Try arecord (preferred for direct ALSA device access)
    arecord = shutil.which("arecord")
    if arecord is not None:
        dev = device or DEFAULT_DEVICE
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
        try:
            res = subprocess.run(cmd, capture_output=True, check=False, timeout=duration + 5.0)  # noqa: S603 - fixed command vector
            if res.returncode == 0 and res.stdout.startswith(b"RIFF"):
                return _trim_wav_duration(res.stdout, duration, rate)
        except (subprocess.TimeoutExpired, OSError):
            pass

    # 2. Try ffmpeg (generic ALSA or Pulse fallback)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        for src_input in (device or "default", "hw:1,0", "default"):
            cmd = [
                ffmpeg,
                "-y",
                "-f", "alsa",
                "-i", src_input,
                "-t", str(duration),
                "-ac", "1",
                "-ar", str(rate),
                "-c:a", "pcm_s16le",
                "-f", "wav",
                "pipe:1",
            ]
            try:
                res = subprocess.run(cmd, capture_output=True, check=False, timeout=duration + 5.0)  # noqa: S603 - fixed command vector
                if res.returncode == 0 and res.stdout.startswith(b"RIFF"):
                    return res.stdout
            except (subprocess.TimeoutExpired, OSError):
                continue

    # 3. Try pw-record (PipeWire)
    pw_record = shutil.which("pw-record")
    if pw_record is not None:
        cmd = [
            pw_record,
            "--rate", str(rate),
            "--channels", "1",
            "--format", "s16",
        ]
        # PipeWire pw-record does not take a duration flag natively, run with timeout
        try:
            res = subprocess.run(cmd, capture_output=True, check=False, timeout=duration)  # noqa: S603 - fixed command vector
            if res.stdout.startswith(b"RIFF"):
                return _trim_wav_duration(res.stdout, duration, rate)
        except subprocess.TimeoutExpired as exc:
            if exc.stdout and exc.stdout.startswith(b"RIFF"):
                return _trim_wav_duration(exc.stdout, duration, rate)
        except OSError:
            pass

    raise RuntimeError("No working audio capture tool found (install arecord, ffmpeg or pw-record)")


def _trim_wav_duration(wav_data: bytes, target_seconds: float, expected_rate: int) -> bytes:
    """Ensure exact duration and rate format in WAV output."""
    try:
        with wave.open(io.BytesIO(wav_data), "rb") as reader:
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
    return 20.0 * math.log10(max(v, 1.0) / 32768.0)


def analyze_signal(wav_bytes: bytes) -> dict[str, Any]:
    """Descriptive signal analysis matching calibration requirements."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as w:
            rate = w.getframerate()
            n = w.getnframes()
            data = array.array("h")
            data.frombytes(w.readframes(n))
    except Exception as exc:
        raise ValueError(f"Invalid WAV audio data: {exc}") from exc

    if not data:
        return {
            "duration_seconds": 0.0,
            "sample_rate": rate,
            "peak_dbfs": -120.0,
            "clipping_samples": 0,
            "noise_floor_dbfs": -120.0,
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
    half_sec = rate // 2

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

    floor_db = dbfs(min(floors)) if floors else -120.0
    snr_db = max(0.0, peak_db - floor_db)

    # Verdict according to calibration rubric:
    # Target: Burst-Peaks between -13.0 and -7.0 dBFS
    current_gain = get_alsa_gain() or 35
    if -13.0 <= peak_db <= -7.0:
        verdict = "calibrated"
        verdict_label = "CALIBRIERT FÜR AUFNAHMEN!"
        recommended_gain = current_gain
    elif peak_db > -7.0:
        verdict = "too_hot"
        verdict_label = "ZU HEISS"
        recommended_gain = max(0, current_gain - 10)
    else:
        verdict = "too_quiet"
        verdict_label = "MEHR LUFT ALS NÖTIG"
        recommended_gain = min(50, current_gain + 6)

    return {
        "duration_seconds": round(n / rate, 2),
        "sample_rate": rate,
        "peak_dbfs": round(peak_db, 1),
        "clipping_samples": clipping,
        "noise_floor_dbfs": round(floor_db, 1),
        "snr_db": round(snr_db, 1),
        "segments": segments,
        "verdict": verdict,
        "verdict_label": verdict_label,
        "recommended_gain": recommended_gain,
    }


def run_calibration(
    gain: int | None = None,
    duration: float = 8.0,
    countdown: float = 4.0,
    device: str | None = None,
) -> dict[str, Any]:
    """Execute automated calibration loop."""
    if gain is not None:
        set_alsa_gain(gain)
    raw_wav = record_audio(duration, rate=48000, countdown=countdown, device=device)
    metrics = analyze_signal(raw_wav)
    return {
        "schema_version": "lixity-audio-calibration/1",
        "current_gain": get_alsa_gain(),
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
