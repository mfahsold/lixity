"""Unit tests for offline microphone recording, signal analysis and calibration."""
from __future__ import annotations

import io
import math
import struct
import subprocess
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
    assert dbfs(0.0) == -120.0


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
    assert get_alsa_gain() == 35
    assert set_alsa_gain(40, card="USB", control="Capture") is True
    assert calls == [
        ["/usr/bin/amixer", "sset", "Mic", "capture", "35"],
        ["/usr/bin/amixer", "sget", "Mic"],
        ["/usr/bin/amixer", "-c", "USB", "sset", "Capture", "capture", "40"],
    ]


def test_analyze_signal_evaluates_peaks_clipping_and_noise_floor():
    wav = _generate_wav(duration=2.0, rate=24000, amplitude=16384)
    res = analyze_signal(wav)
    assert res["duration_seconds"] == 2.0
    assert res["sample_rate"] == 24000
    assert res["signal_present"] is True
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
        record_audio(60.01)
    with pytest.raises(ValueError, match="Calibration duration must be between"):
        run_calibration(duration=35.0)
    with pytest.raises(ValueError, match="Countdown must be a finite"):
        record_audio(1.0, countdown=math.inf)


def test_named_capture_never_falls_back_to_another_input(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def mock_run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout=b"")

    device = "plughw:CARD=USB,DEV=0"
    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)
    with pytest.raises(RuntimeError, match="selected ALSA input"):
        record_audio(1.0, device=device)
    assert [(call[0], call[call.index(option) + 1]) for call, option in zip(calls, ("-D", "-i"), strict=True)] == [
        ("/usr/bin/arecord", device), ("/usr/bin/ffmpeg", device),
    ]


def test_pipewire_default_wraps_partial_raw_capture_in_a_wav(monkeypatch: pytest.MonkeyPatch):
    pcm = struct.pack("<hh", 500, -500)

    def mock_run(cmd, *, timeout, **kwargs):
        assert cmd == ["/usr/bin/pw-record", "--raw", "--rate", "24000", "--channels", "1", "--format", "s16", "-"]
        raise subprocess.TimeoutExpired(cmd, timeout, output=pcm + b"\x00")

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pw-record" if name == "pw-record" else None)
    monkeypatch.setattr("subprocess.run", mock_run)
    with wave.open(io.BytesIO(record_audio(1.0)), "rb") as reader:
        assert reader.getparams()[:4] == (1, 2, 24000, 2)
        assert reader.readframes(2) == pcm


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
    assert calib["current_gain"] == 35
    assert calib["mixer"] is None
    assert calib["recommended_gain"] is None
    assert run_calibration(duration=2.0, countdown=0.0)["current_gain"] is None


@pytest.mark.parametrize("amplitude,limits,expected", [
    (1000, "Limits: Capture 0 - 5\n", 5),
    (1000, "Limits: Playback 0 - 120 Capture 0 - 5\n", 5),
    (0, "Limits: Capture 0 - 5\n", None),
    (1000, "Limits: Capture -5 - 5\n", None),
    (1000, "Limits: Capture 0 - 120\n", None),
    (1000, "", None),
])
def test_calibration_uses_selected_card_readback_and_bounds(monkeypatch, amplitude, limits, expected):
    device = "plughw:CARD=USB,DEV=0"
    synthetic_wav = _generate_wav(rate=48000, amplitude=amplitude)
    calls = []

    def mock_run(cmd, **kwargs):
        if "-l" in cmd:
            return SimpleNamespace(returncode=0, stdout="card 4: USB [USB], device 0: Capture [Capture]")
        calls.append(cmd)
        if "scontents" in cmd:
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    "Simple mixer control 'Master',0\n"
                    "  Capabilities: pvolume\n"
                    "  Limits: Playback 0 - 100\n"
                    "  Mono: Playback 80 [80%]\n"
                    "Simple mixer control 'Capture',0\n"
                    "  Capabilities: cvolume\n  " + limits + "  Mono: Capture 0 [0%]\n"
                ),
            )
        return SimpleNamespace(returncode=0, stdout=synthetic_wav)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)
    gain = 0 if expected else None
    calib = run_calibration(gain=gain, duration=1.0, countdown=0.0, device=device)
    discovery = ["/usr/bin/amixer", "-c", "USB", "scontents"]
    if gain is not None:
        assert calls[:2] == [discovery, ["/usr/bin/amixer", "-c", "USB", "sset", "Capture", "capture", "0"]]
    assert calls[-2][:3] == ["/usr/bin/arecord", "-D", device]
    assert calls[-1] == discovery
    assert calib["current_gain"] == 0
    assert calib["signal_present"] is (amplitude != 0)
    assert calib["recommended_gain"] == expected
    assert calib["mixer"] == ({"card": "USB", "control": "Capture"} if limits else None)
    if amplitude == 0:
        assert calib["peak_dbfs"] == -120.0


@pytest.mark.parametrize("controls", [
    (("Capture", 0), ("Mic", 0)),
    (("Capture", 0), ("Capture", 1)),
    (("Capture", 1),),
])
def test_named_input_with_ambiguous_control_has_no_automatic_mixer(monkeypatch, controls):
    from lixity.speech_record import get_microphone_status

    device = "plughw:CARD=USB,DEV=0"

    def mock_run(cmd, **kwargs):
        if "-l" in cmd:
            return SimpleNamespace(returncode=0, stdout="card 4: USB [USB], device 0: Capture [Capture]")
        if "scontents" in cmd:
            return SimpleNamespace(
                returncode=0,
                stdout="".join(
                    f"Simple mixer control '{name}',{index}\n"
                    "  Capabilities: cvolume\n  Limits: Capture 0 - 5\n  Mono: Capture 1 [20%]\n"
                    for name, index in controls
                ),
            )
        if "sget" in cmd:
            assert cmd[-1] == "Explicit"
            return SimpleNamespace(returncode=0, stdout="Limits: Capture 0 - 5\nMono: Capture 1 [20%]\n")
        if "-D" in cmd:
            return SimpleNamespace(returncode=0, stdout=_generate_wav(rate=48000, amplitude=1000))
        raise AssertionError("A capture gain write occurred unexpectedly")

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)
    assert get_microphone_status(device=device)["gain_info"] is None
    assert get_microphone_status(device=device, control="Explicit")["gain_info"]["control"] == "Explicit"
    calibration = run_calibration(device=device, duration=1.0, countdown=0.0)
    assert calibration["signal_present"] is True
    assert calibration["mixer"] is None
    assert calibration["recommended_gain"] is None
    with pytest.raises(ValueError, match="single adjustable ALSA capture gain"):
        record_audio(duration=1.0, device=device, gain=1)


def test_list_capture_devices_and_status(monkeypatch: pytest.MonkeyPatch):
    from lixity.speech_record import (
        get_alsa_gain_info,
        get_microphone_status,
        list_capture_devices,
        set_microphone_gain,
    )

    arecord_out = (
        "card 0: X1E80100LENOVOT [X1E80100-LENOVO-Thinkpad-T14s], device 2: MultiMedia3 Capture (*) []\n"
        "card 1: I3000 [ISY IMI 3000], device 0: USB Audio [USB Audio]\n"
    )
    amixer_out = (
        "Simple mixer control 'Mic',0\n"
        "  Limits: Capture 0 - 50\n"
        "  Mono: Capture 35 [70%] [13.50dB] [on]\n"
    )

    def mock_run(cmd, **kwargs):
        if "arecord" in cmd[0]:
            return SimpleNamespace(returncode=0, stdout=arecord_out)
        if "sget" in cmd:
            return SimpleNamespace(returncode=0, stdout=amixer_out)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)

    devices = list_capture_devices()
    assert len(devices) == 2
    assert devices[0]["card_id"] == "X1E80100LENOVOT"
    assert devices[1]["alsa_id"] == "plughw:CARD=I3000,DEV=0"

    info = get_alsa_gain_info()
    assert info is not None
    assert info["gain"] == 35
    assert info["percent"] == 70
    assert info["db"] == 13.5
    assert info["min"] == 0
    assert info["max"] == 50
    assert info["writable"] is True

    status = get_microphone_status()
    assert status["schema_version"] == "lixity-microphone-status/1"
    assert status["current_gain"] == 35
    assert status["gain_info"]["card"] is None
    assert status["default_device"] == "default"
    assert len(status["devices"]) == 2

    assert set_microphone_gain(38) is True

    ambiguous = arecord_out + "\ncard 1: I3000 [ISY IMI 3000], device 1: Other Input [Other Input]"
    arecord_out = ambiguous
    status = get_microphone_status(device=devices[1]["alsa_id"])
    assert status["current_gain"] is None
    assert status["gain_info"] is None


def test_cli_audio_microphone(capsys, monkeypatch: pytest.MonkeyPatch):
    import json

    from lixity.cli import main

    arecord_out = "card 1: I3000 [ISY IMI 3000], device 0: USB Audio [USB Audio]\n"
    amixer_out = (
        "Simple mixer control 'Mic',0\n"
        "  Limits: Capture 0 - 50\n"
        "  Mono: Capture 35 [70%] [13.50dB] [on]\n"
    )

    def mock_run(cmd, **kwargs):
        if "arecord" in cmd[0]:
            return SimpleNamespace(returncode=0, stdout=arecord_out)
        if "sget" in cmd:
            return SimpleNamespace(returncode=0, stdout=amixer_out)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)

    # 1. status
    assert main(["audio-microphone", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == "lixity-microphone-status/1"
    assert data["current_gain"] == 35
    assert main(["audio-microphone", "status", "--card", "USB", "--control", "Capture", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["gain_info"]["card"] == "USB"
    assert data["gain_info"]["control"] == "Capture"

    # 2. devices
    assert main(["audio-microphone", "devices", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["devices"]) == 1

    # 3. set
    assert main(["audio-microphone", "set", "--gain", "35", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "updated"
    assert data["gain"] == 35
    assert data["current_gain"] == 35


def test_sanitized_subprocess_env_and_audio_tool_env_strip_ambient_secrets(
    monkeypatch: pytest.MonkeyPatch,
):
    from lixity.io import sanitized_subprocess_env
    from lixity.speech_record import _audio_tool_env

    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("HF_TOKEN", "hf_secret")
    monkeypatch.setenv("GH_TOKEN", "ghp_secret")
    monkeypatch.setenv("PULSE_SERVER", "unix:/tmp/pulse-test")

    base = sanitized_subprocess_env()
    for secret in ("OPENAI_API_KEY", "HF_TOKEN", "GH_TOKEN"):
        assert secret not in base
    assert "PULSE_SERVER" not in base

    audio_env = _audio_tool_env()
    for secret in ("OPENAI_API_KEY", "HF_TOKEN", "GH_TOKEN"):
        assert secret not in audio_env
    assert audio_env["PULSE_SERVER"] == "unix:/tmp/pulse-test"
    assert audio_env["LC_ALL"] == "C"


def test_alsa_controls_pass_sanitized_env_and_handle_timeout(monkeypatch: pytest.MonkeyPatch, caplog):
    from lixity.speech_record import get_alsa_gain_info, list_capture_devices

    seen_kwargs: list[dict[str, object]] = []

    def mock_run(cmd, **kwargs):
        seen_kwargs.append(kwargs)
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=15.0)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setattr("shutil.which", lambda bin_name: f"/usr/bin/{bin_name}")
    monkeypatch.setattr("subprocess.run", mock_run)

    with caplog.at_level("DEBUG", logger="lixity.speech.capture"):
        assert set_alsa_gain(35, card="private-device") is False
        assert get_alsa_gain() is None
        assert get_alsa_gain_info() is None
        devices = list_capture_devices()
    assert len(devices) == 1 and devices[0]["alsa_id"] == "default"
    assert len(seen_kwargs) == 4
    for kw in seen_kwargs:
        assert kw.get("timeout") is not None
        env = kw.get("env")
        assert isinstance(env, dict)
        assert "OPENAI_API_KEY" not in env
        assert env.get("LC_ALL") == "C"
    messages = [record.message for record in caplog.records if record.name == "lixity.speech.capture"]
    assert len(messages) == 4
    assert all("event=capture_tool_finished" in message and "outcome=timeout" in message for message in messages)
    assert "tool=amixer" in messages[0]
    assert all("private-device" not in message and "/usr/bin" not in message for message in messages)

