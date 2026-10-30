"""Deterministic signal diagnostics for private voice references.

Cloning engines inherit the channel of their reference: a band-limited,
gated or clipped recording shapes every cloned segment. These measurements are
descriptive signal facts computed offline with the standard library. The
thresholds behind the notes are uncalibrated heuristics; they support a human
listening decision and are not a quality score or a validated limit.
"""
from __future__ import annotations

import array
import cmath
import math
import sys

from .speech import _read_pcm

SCHEMA = "lixity-audio-reference-quality/1"
_FRAME = 1024
_LEVEL_FRAME_MS = 20
_MAX_SPECTRUM_FRAMES = 64
_FLOOR_DBFS = -120.0
_CLIP_LEVEL = 32760
_BAND_HZ = 500
_BAND_FLOOR_RATIO = 1e-7  # 70 dB below the mean power under 1 kHz
# Uncalibrated heuristic thresholds behind the notes.
_NARROW_BANDWIDTH_SHARE = 0.8  # of the Nyquist frequency
_LOW_SPEECH_LEVEL_DBFS = -35.0
_MIN_SPEECH_TO_NOISE_DB = 30.0
_GATED_NOISE_FLOOR_DBFS = -90.0
_CLIPPED_RATIO_LIMIT = 0.001


def _fft(values: list[complex]) -> list[complex]:
    size = len(values)
    if size == 1:
        return values
    even = _fft(values[0::2])
    odd = _fft(values[1::2])
    result = [0j] * size
    half = size // 2
    for index in range(half):
        twiddle = cmath.exp(-2j * math.pi * index / size) * odd[index]
        result[index] = even[index] + twiddle
        result[index + half] = even[index] - twiddle
    return result


def _db(power: float) -> float:
    return max(_FLOOR_DBFS, 10.0 * math.log10(power)) if power > 0.0 else _FLOOR_DBFS


def _percentile(sorted_values: list[float], fraction: float) -> float:
    return sorted_values[min(len(sorted_values) - 1, int(fraction * len(sorted_values)))]


def _note(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _bandwidth(spectrum: list[float], rate: int) -> float | None:
    """Upper edge of the highest 500 Hz band that rises above the noise floor."""
    bin_hz = rate / _FRAME
    low = [spectrum[index] for index in range(1, len(spectrum)) if index * bin_hz < 1000.0]
    if not low or sum(low) <= 0.0:
        return None
    floor_power = sum(low) / len(low) * _BAND_FLOOR_RATIO
    bandwidth = 0.0
    for lower in range(0, rate // 2, _BAND_HZ):
        members = [spectrum[index] for index in range(1, len(spectrum)) if lower <= index * bin_hz < lower + _BAND_HZ]
        if members and sum(members) / len(members) >= floor_power:
            bandwidth = float(lower + _BAND_HZ)
    return bandwidth


def assess_reference(audio: bytes) -> dict[str, object]:
    """Measure a PCM WAV reference; undeterminable values are ``None`` with a note."""
    (channels, width, rate), frames = _read_pcm(audio)
    if width != 2 or channels != 1:
        raise ValueError("Reference diagnostics require mono 16-bit PCM")
    samples = array.array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    notes: list[dict[str, str]] = []
    result: dict[str, object] = {
        "schema_version": SCHEMA, "method": "heuristic-uncalibrated", "sample_rate": rate,
        "duration_seconds": round(len(samples) / rate, 2), "peak_dbfs": None, "clipped_sample_ratio": None,
        "speech_level_dbfs": None, "noise_floor_dbfs": None, "bandwidth_hz": None, "notes": notes,
    }
    peak = max((abs(value) for value in samples), default=0)
    if peak == 0:
        notes.append(_note("silent", "The reference contains no signal; nothing can be measured."))
        return result
    clipped = sum(1 for value in samples if abs(value) >= _CLIP_LEVEL) / len(samples)
    result["peak_dbfs"] = round(20.0 * math.log10(peak / 32768.0), 1)
    result["clipped_sample_ratio"] = round(clipped, 5)

    step = rate * _LEVEL_FRAME_MS // 1000
    powers = [sum(value * value for value in samples[start:start + step]) / (step * 32768.0 ** 2)
              for start in range(0, len(samples) - step + 1, step)]
    level = floor = None
    if powers:
        ordered = sorted(powers)
        active = [power for power in powers if power >= _percentile(ordered, 0.5)]
        level = round(_db(sum(active) / len(active)), 1)
        floor = round(_db(_percentile(ordered, 0.05)), 1)
        result["speech_level_dbfs"], result["noise_floor_dbfs"] = level, floor

    window = [0.5 - 0.5 * math.cos(2.0 * math.pi * index / _FRAME) for index in range(_FRAME)]
    starts = list(range(0, len(samples) - _FRAME + 1, _FRAME // 2))
    energies = [sum(value * value for value in samples[start:start + _FRAME]) for start in starts]
    bandwidth = None
    if energies:
        threshold = sorted(energies)[len(energies) // 2]
        loud = [start for start, energy in zip(starts, energies, strict=True) if energy >= threshold and energy > 0]
        stride = max(1, math.ceil(len(loud) / _MAX_SPECTRUM_FRAMES))
        spectrum = [0.0] * (_FRAME // 2)
        for start in loud[::stride]:
            frame = [complex(samples[start + index] * window[index]) for index in range(_FRAME)]
            for index, value in enumerate(_fft(frame)[:_FRAME // 2]):
                spectrum[index] += value.real * value.real + value.imag * value.imag
        bandwidth = _bandwidth(spectrum, rate)
        result["bandwidth_hz"] = bandwidth

    if clipped > _CLIPPED_RATIO_LIMIT:
        notes.append(_note("clipping", "Samples reach full scale; clipped speech shapes every cloned segment."))
    if level is not None and level < _LOW_SPEECH_LEVEL_DBFS:
        notes.append(_note("low_level", "The speech level is low; background noise weighs more in the voice estimate."))
    if level is not None and floor is not None:
        if floor <= _GATED_NOISE_FLOOR_DBFS:
            notes.append(_note("digitally_silent_pauses", "Pauses are digitally silent, which suggests a noise gate or "
                                                          "aggressive noise removal; breath and room character may be missing."))
        elif level - floor < _MIN_SPEECH_TO_NOISE_DB:
            notes.append(_note("high_noise", "The gap between speech and pauses is small; background noise is likely audible."))
    if bandwidth is not None and bandwidth < _NARROW_BANDWIDTH_SHARE * rate / 2:
        notes.append(_note("band_limited", f"No signal above about {bandwidth:.0f} Hz although the file allows "
                                           f"{rate / 2:.0f} Hz; the OpenVoice converter reproduces such a limit, "
                                           "so the cloned voice sounds duller than a wideband recording."))
    return result
