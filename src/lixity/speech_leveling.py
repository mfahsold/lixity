"""Bound level differences between independent mono PCM16 synthesis segments."""

from __future__ import annotations

import math
import sys
from array import array
from dataclasses import dataclass
from statistics import median

_FULL_SCALE = 32768
_TARGET_DBFS = -30.0
_DEADBAND_DB = 2.0
_MAX_CORRECTION_DB = 6.0
_ACTIVE_FLOOR_POWER = 10 ** (-48 / 10)
_PEAK_LIMIT = int(_FULL_SCALE * 10 ** (-2 / 20))


@dataclass(frozen=True)
class LeveledSpeech:
    frames: bytes
    active_rms_dbfs: float | None
    gain_db: float
    sample_peak_dbfs: float | None


def level_speech_pcm(frames: bytes, rate: int, *, preserve_delivery: bool = False) -> LeveledSpeech:
    """Apply one gain to the entire segment, keeping its timing and dynamics."""
    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder == "big":
        samples.byteswap()
    peak = max(abs(min(samples, default=0)), abs(max(samples, default=0)))
    if not peak:
        return LeveledSpeech(frames, None, 0.0, None)

    width = max(1, rate // 10)
    scale = width * _FULL_SCALE**2
    powers = sorted(power for start in range(0, len(samples) - width + 1, width)
                    if (power := sum(s * s for s in samples[start:start + width]) / scale) >= _ACTIVE_FLOOR_POWER)
    level = None
    correction = 0.0
    if len(powers) >= 3:
        # Use an upper percentile rather than the loudest block to gate quiet
        # tails and pauses without letting a single click gate out the speech.
        floor = powers[4 * (len(powers) - 1) // 5] / 100
        active = [power for power in powers if power >= floor]
        if len(active) >= 3:
            level = 10 * math.log10(median(active))
            if not preserve_delivery:
                delta = _TARGET_DBFS - level
                correction = math.copysign(min(_MAX_CORRECTION_DB, max(0.0, abs(delta) - _DEADBAND_DB)), delta)

    # Use the measured sample peak to restrict the one gain for the entire
    # segment. A flat clamp would distort the waveform at each peak.
    gain = min(10 ** (correction / 20), _PEAK_LIMIT / peak)
    if gain != 1.0:
        adjusted = array("h", (round(s * gain) for s in samples))
        if sys.byteorder == "big":
            adjusted.byteswap()
        frames = adjusted.tobytes()
    return LeveledSpeech(frames, level, 20 * math.log10(gain),
                         20 * math.log10(round(gain * peak) / _FULL_SCALE))
