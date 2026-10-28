"""Playback-rate processing retains raw speech and explicit pause timing."""

import json
import math
import shutil
import struct
import wave
from itertools import pairwise

import pytest

from lixity.speech import render_speech_audio
from lixity.speech_direction import SpeechSegment
from lixity.speech_profiles import AudioProfile, parse_audio_settings


def test_existing_audio_profiles_keep_their_speed_and_new_default_is_faster():
    old = {"selected": "narrator", "profiles": {"narrator": {
        "engine": "qwen3", "language": "de", "voice": "Ryan", "speed": 1.0}}}
    assert parse_audio_settings(old).profiles["narrator"].speed == 1.0
    assert parse_audio_settings(None, language="de").profiles["narrator"].speed == 1.2
    old["profiles"]["narrator"].pop("speed")
    assert parse_audio_settings(old).profiles["narrator"].speed == 1.0
    assert AudioProfile(speed=1.2).speed == 1.2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required for tempo postprocessing")
def test_speed_is_applied_to_speech_but_not_explicit_silence(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("A synthetic passage.")
    raw = tmp_path / "source.wav"
    with wave.open(str(raw), "wb") as writer:
        writer.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        writer.writeframes(b"".join(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 220 * n / 24000)))
                                    for n in range(48000)))
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: raw.read_bytes())
    profile = AudioProfile(speed=1.2)
    plan = [SpeechSegment("A synthetic passage.", profile, 0.4, 0.6)]
    output = render_speech_audio(source, tmp_path / "result.wav", profile=profile, plan=plan)
    with wave.open(str(output), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 24000)
        duration = audio.getnframes() / 24000
        assert duration == pytest.approx(1.0 + 2 / 1.2, abs=0.08)
        frames = audio.readframes(audio.getnframes())
        assert frames[:int(.4 * 24000) * 2] == bytes(int(.4 * 24000) * 2)
        assert frames[-int(.6 * 24000) * 2:] == bytes(int(.6 * 24000) * 2)
        speech = frames[int(.8 * 24000) * 2:int(1.3 * 24000) * 2]
        samples = [item[0] for item in struct.iter_unpack("<h", speech)]
        crossings = sum(a <= 0 < b for a, b in pairwise(samples))
        assert crossings / .5 == pytest.approx(220, abs=5)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required for tempo postprocessing")
def test_very_short_speech_remains_audible_when_atempo_cannot_produce_frames(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("A.")
    raw = tmp_path / "short.wav"
    original_frames = b"".join(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 220 * n / 24000)))
                               for n in range(240))
    with wave.open(str(raw), "wb") as writer:
        writer.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        writer.writeframes(original_frames)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: raw.read_bytes())
    profile = AudioProfile(speed=1.2)
    plan = [SpeechSegment("A.", profile, 0.0, 0.0)]
    output = render_speech_audio(source, tmp_path / "result.wav", profile=profile, plan=plan)
    with wave.open(str(output), "rb") as audio:
        assert audio.readframes(audio.getnframes()) == original_frames


def test_empty_tempo_output_for_normal_speech_is_an_error(tmp_path, monkeypatch):
    import io
    from pathlib import Path
    from subprocess import CompletedProcess

    from lixity.speech import generate_silence_wav

    source = tmp_path / "source.md"
    source.write_text("A synthetic passage.")
    output = tmp_path / "result.wav"
    output.write_bytes(b"prior")
    monkeypatch.setattr("lixity.speech.shutil.which", lambda _name: "/synthetic/ffmpeg")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: generate_silence_wav(1))
    def empty_output(command):
        data = io.BytesIO()
        with wave.open(data, "wb") as writer:
            writer.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        Path(command[-1]).write_bytes(data.getvalue())
        return CompletedProcess(command, 0, b"", b"")
    monkeypatch.setattr("lixity.speech._run_ffmpeg", empty_output)
    with pytest.raises(RuntimeError, match="empty tempo-adjusted audio"):
        render_speech_audio(source, output, profile=AudioProfile(speed=1.2))
    assert output.read_bytes() == b"prior"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is required for tempo postprocessing")
def test_raw_synthesis_cache_is_reused_across_speed_changes(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("A synthetic passage.")
    from lixity.speech import generate_silence_wav
    calls = []
    def synthesize(*_args, **_kwargs):
        calls.append(1)
        return generate_silence_wav(2.0)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    for speed in (1.0, 1.2):
        profile = AudioProfile(speed=speed)
        plan = [SpeechSegment("A synthetic passage.", profile, 0.0, 0.0)]
        render_speech_audio(source, tmp_path / f"out-{speed}.wav", profile=profile, plan=plan,
                            cache_dir=tmp_path / "cache")
    assert len(calls) == 1


def test_speed_requires_ffmpeg_before_synthesis_and_keeps_old_output(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("A synthetic passage.")
    output = tmp_path / "out.wav"
    output.write_bytes(b"prior")
    monkeypatch.setattr("lixity.speech.shutil.which", lambda _name: None)
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: calls.append(1))
    with pytest.raises(FileNotFoundError, match="FFmpeg"):
        render_speech_audio(source, output, profile=AudioProfile(speed=1.2))
    assert not calls
    assert output.read_bytes() == b"prior"


def test_tempo_filter_failure_keeps_existing_output(tmp_path, monkeypatch):
    from subprocess import CompletedProcess

    from lixity.speech import generate_silence_wav
    source = tmp_path / "source.md"
    source.write_text("A synthetic passage.")
    output = tmp_path / "out.wav"
    output.write_bytes(b"prior")
    monkeypatch.setattr("lixity.speech.shutil.which", lambda _name: "/synthetic/ffmpeg")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: generate_silence_wav(1))
    monkeypatch.setattr("lixity.speech._run_ffmpeg", lambda _command: CompletedProcess([], 1, b"", b"failure"))
    with pytest.raises(RuntimeError, match="FFmpeg failed to adjust"):
        render_speech_audio(source, output, profile=AudioProfile(speed=1.2))
    assert output.read_bytes() == b"prior"


def test_cli_speed_override_applies_to_directed_profiles_without_saving(tmp_path, capsys):
    from lixity.cli import main
    from lixity.config import prepare_project_settings
    from lixity.speech_direction import direction_state, save_direction

    source = tmp_path / "manuscript.md"
    source.write_text("## One\n\nA bird flies across the garden.\n")
    settings = {"selected": "narrator", "profiles": {
        "narrator": {"engine": "qwen3", "voice": "Ryan", "language": "en", "speed": 1.0},
        "other": {"engine": "qwen3", "voice": "Aiden", "language": "en", "speed": 0.9},
    }}
    prepare_project_settings(tmp_path, {"audio": settings}).commit()
    state = direction_state(tmp_path, source)
    save_direction(tmp_path, source, {"anchor": state["passages"][0]["anchor"],
                                    "profile_id": "other", "start": 0, "end": 6},
                   expected_source_sha256=state["source_sha256"],
                   expected_settings_sha256=state["settings_sha256"],
                   expected_direction_sha256=state["direction_sha256"])
    config_before = (tmp_path / "lixity.toml").read_bytes()
    assert main(["read-aloud", "--project", str(tmp_path), "--plan-only", "--speed", "1.35"]) == 0
    plan = json.loads(capsys.readouterr().out)["segments"]
    assert {row["profile"]["voice"] for row in plan if row["text"]} == {"Ryan", "Aiden"}
    assert all(row["profile"]["speed"] == 1.35 for row in plan if row["text"])
    assert (tmp_path / "lixity.toml").read_bytes() == config_before
