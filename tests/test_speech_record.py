"""Unit tests for offline microphone recording, signal analysis and calibration."""
from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from lixity.speech_record import (
    analyze_signal,
    dbfs,
    get_alsa_gain,
    record_and_save_reference,
    record_audio,
    run_calibration,
    set_alsa_gain,
)
from lixity.speech_references import load_reference


def _generate_wav(duration: float = 1.0, rate: int = 24000, amplitude: int = 16384) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(duration * rate)
        # Create half speech, half silence
        samples = [amplitude if i < n // 2 else 0 for i in range(n)]
        w.writeframes(struct.pack(f"<{n}h", *samples))
    return buf.getvalue()


def test_dbfs_calculation():
    assert math.isclose(dbfs(32768.0), 0.0, abs_tol=0.01)
    assert math.isclose(dbfs(16384.0), -6.02, abs_tol=0.05)
    assert dbfs(0.0) <= -90.0


def test_set_and_get_alsa_gain(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(ValueError, match="Gain must be between 0 and 100"):
        set_alsa_gain(-1)
    with pytest.raises(ValueError, match="Gain must be between 0 and 100"):
        set_alsa_gain(101)

    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        if "sget" in cmd:
            return SimpleNamespace(returncode=0, stdout="Mono: Capture 35 [70%] [15.00dB] [on]\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)

    assert set_alsa_gain(35) is True
    assert calls[0] == ["/usr/bin/amixer", "-c", "1", "sset", "Mic", "35"]
    assert get_alsa_gain() == 35


def test_analyze_signal_evaluates_peaks_clipping_and_noise_floor():
    wav = _generate_wav(duration=2.0, rate=24000, amplitude=16384)
    res = analyze_signal(wav)
    assert res["duration_seconds"] == 2.0
    assert res["sample_rate"] == 24000
    assert math.isclose(res["peak_dbfs"], -6.0, abs_tol=0.5)
    assert res["clipping_samples"] == 0
    assert res["noise_floor_dbfs"] < -80.0
    assert res["snr_db"] > 60.0
    assert len(res["segments"]) == 4


@pytest.mark.parametrize("amplitude,expected_verdict,expected_label", [
    (10000, "calibrated", "CALIBRIERT FÜR AUFNAHMEN!"),  # ~ -10.3 dBFS
    (32700, "too_hot", "ZU HEISS"),                     # ~ -0.02 dBFS
    (1000, "too_quiet", "MEHR LUFT ALS NÖTIG"),          # ~ -30.3 dBFS
])
def test_calibration_verdicts(amplitude: int, expected_verdict: str, expected_label: str):
    wav = _generate_wav(duration=1.0, rate=48000, amplitude=amplitude)
    res = analyze_signal(wav)
    assert res["verdict"] == expected_verdict
    assert res["verdict_label"] == expected_label


def test_record_audio_duration_validation():
    with pytest.raises(ValueError, match="duration must be between"):
        record_audio(0.5)
    with pytest.raises(ValueError, match="duration must be between"):
        record_audio(35.0)


def test_record_audio_and_save_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    synthetic_wav = _generate_wav(duration=1.5, rate=24000, amplitude=8000)

    def mock_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout=synthetic_wav)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)

    ref = record_and_save_reference(tmp_path, duration=1.5, transcript="Test-Aufnahme.")
    assert ref.transcript == "Test-Aufnahme."
    assert ref.audio.startswith(b"RIFF")
    loaded = load_reference(tmp_path, ref.id)
    assert loaded.id == ref.id
    assert loaded.transcript == ref.transcript


def test_run_calibration_integration(monkeypatch: pytest.MonkeyPatch):
    synthetic_wav = _generate_wav(duration=2.0, rate=48000, amplitude=10000)

    def mock_run(cmd, **kwargs):
        if "sget" in cmd:
            return SimpleNamespace(returncode=0, stdout="Mono: Capture 35 [70%] [15.00dB] [on]\n")
        return SimpleNamespace(returncode=0, stdout=synthetic_wav)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("time.sleep", lambda s: None)

    calib = run_calibration(gain=35, duration=2.0, countdown=0.0)
    assert calib["schema_version"] == "lixity-audio-calibration/1"
    assert calib["verdict"] == "calibrated"
    assert calib["verdict_label"] == "CALIBRIERT FÜR AUFNAHMEN!"
