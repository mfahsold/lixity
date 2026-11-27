"""Regression tests for level changes in rendered speech."""

from __future__ import annotations

import io
import logging
import math
import struct
import wave
from pathlib import Path

import pytest

from lixity import speech
from lixity.speech_cache import SpeechSegmentCache
from lixity.speech_direction import SpeechSegment
from lixity.speech_leveling import level_speech_pcm
from lixity.speech_profiles import AudioProfile

RATE = 24_000
TONE_FRAMES = RATE
PASSAGE = {"start_line": 1, "end_line": 1, "paragraph_sha256": "a" * 64}


def _tone(peak: int) -> tuple[int, ...]:
    cycle = tuple(round(peak * math.sin(math.tau * index / 120)) for index in range(120))
    return cycle * (TONE_FRAMES // len(cycle))


def _wav(samples: tuple[int, ...]) -> bytes:
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return stream.getvalue()


def _read_samples(path: Path) -> tuple[int, ...]:
    with wave.open(str(path), "rb") as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, RATE)
        count = audio.getnframes()
        return struct.unpack(f"<{count}h", audio.readframes(count))


def _level_difference_db(first: tuple[int, ...], second: tuple[int, ...]) -> float:
    def mean_square(samples: tuple[int, ...]) -> float:
        return sum(sample * sample for sample in samples) / len(samples)

    return abs(10 * math.log10(mean_square(first) / mean_square(second)))


def _render_one_segment(tmp_path, monkeypatch, samples: tuple[int, ...]) -> tuple[int, ...]:
    text = "A synthetic sentence."
    source = tmp_path / "synthetic.md"
    source.write_text(text, encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    data = _wav(samples)
    monkeypatch.setattr(speech, "_synthesize_segment", lambda *_args, **_kwargs: data)
    output = speech.render_speech_audio(
        source, tmp_path / "chapter.wav", profile=profile, plan=[SpeechSegment(text, profile, anchor=PASSAGE)]
    )
    return _read_samples(output)


def test_render_reduces_gain_jump_within_a_passage_and_preserves_pauses_and_cache(tmp_path, monkeypatch):
    source = tmp_path / "synthetic.md"
    source.write_text("A first sentence. A second sentence.", encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    loud, quiet = _tone(15_000), _tone(950)
    raw = {"A first sentence.": _wav(loud), "A second sentence.": _wav(quiet)}
    requests = []

    def synthesize(text, *_args, **_kwargs):
        requests.append(text)
        return raw[text]

    monkeypatch.setattr(speech, "_synthesize_segment", synthesize)
    monkeypatch.setattr(speech.shutil, "which", lambda _name: None)
    plan = [
        SpeechSegment("A first sentence.", profile, pause_before=0.125, anchor=PASSAGE),
        SpeechSegment("A second sentence.", profile, pause_after=0.25, anchor=PASSAGE),
    ]
    cache = tmp_path / "cache"
    path = speech.render_speech_audio(source, tmp_path / "chapter.wav", profile=profile, plan=plan, cache_dir=cache)
    rendered = _read_samples(path)
    first_start = RATE // 8
    second_start = first_start + TONE_FRAMES
    second_end = second_start + TONE_FRAMES
    assert len(rendered) == second_end + RATE // 4
    assert rendered[:first_start] == (0,) * first_start
    assert rendered[second_end:] == (0,) * (RATE // 4)

    quarter = TONE_FRAMES // 4
    first_middle = rendered[first_start + quarter : second_start - quarter]
    second_middle = rendered[second_start + quarter : second_end - quarter]
    input_jump = _level_difference_db(loud, quiet)
    assert _level_difference_db(first_middle, second_middle) <= input_jump - 3
    assert _level_difference_db(loud, first_middle) <= 6.01
    assert _level_difference_db(quiet, second_middle) <= 6.01
    assert max(abs(sample) for sample in rendered) < 32_767

    cache_reader = SpeechSegmentCache(cache)
    for text, data in raw.items():
        assert cache_reader.get(text, profile) == data
    repeated = speech.render_speech_audio(source, tmp_path / "cached.wav", profile=profile, plan=plan, cache_dir=cache)
    assert _read_samples(repeated) == rendered
    assert requests == list(raw)


def test_render_keeps_relative_levels_within_one_synthesized_segment(tmp_path, monkeypatch):
    louder, softer = _tone(14_000), _tone(4_000)
    silence = (0,) * (RATE // 8)
    raw = louder + silence + softer
    rendered = _render_one_segment(tmp_path, monkeypatch, raw)

    assert len(rendered) == len(raw)
    assert rendered[TONE_FRAMES : TONE_FRAMES + len(silence)] == silence
    assert max(abs(sample) for sample in rendered) < max(louder)
    assert _level_difference_db(rendered[:TONE_FRAMES], rendered[-TONE_FRAMES:]) == pytest.approx(
        _level_difference_db(louder, softer), abs=0.02
    )


def test_render_preserves_explicit_delivery_levels_and_logs_numeric_diagnostics(tmp_path, monkeypatch):
    neutral_text = "Synthetic neutral sentence."
    directed_text = "Synthetic directed sentence."
    instruction = "Use the narrator's quiet aside."
    source = tmp_path / "synthetic.md"
    source.write_text(neutral_text + " " + directed_text, encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    directed = AudioProfile(speed=1.0, instructions=instruction)
    plan = [
        SpeechSegment(neutral_text, profile, anchor=PASSAGE),
        SpeechSegment(directed_text, directed, anchor=PASSAGE),
    ]
    quiet = _tone(500)
    data = _wav(quiet)
    monkeypatch.setattr(speech, "_synthesize_segment", lambda *_args, **_kwargs: data)
    records = io.StringIO()
    logger = logging.Logger("lixity.speech.test.level", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(records))
    monkeypatch.setattr(speech, "get_logger", lambda _suffix: logger)

    path = speech.render_speech_audio(source, tmp_path / "chapter.wav", profile=profile, plan=plan)
    rendered = _read_samples(path)
    quarter = TONE_FRAMES // 4
    neutral_middle = rendered[quarter : TONE_FRAMES - quarter]
    directed_middle = rendered[TONE_FRAMES + quarter : -quarter]
    assert directed_middle == quiet[quarter : -quarter]
    assert max(neutral_middle) > max(directed_middle)

    log = records.getvalue()
    assert all(value not in log for value in (neutral_text, directed_text, instruction, str(tmp_path)))
    segments = [
        dict(field.split("=", 1) for field in line.split())
        for line in log.splitlines()
        if "event=segment_end" in line
    ]
    neutral_record, directed_record = segments
    assert 3 <= float(neutral_record["level_gain_db"]) <= 6
    assert float(directed_record["level_gain_db"]) == 0
    for record in segments:
        assert -48 < float(record["level_active_rms_dbfs"]) < -30
        assert -48 < float(record["level_sample_peak_dbfs"]) <= -2


@pytest.mark.parametrize(
    "samples",
    [_tone(950)[: RATE // 5], _tone(65), (0,) * RATE],
    ids=["short", "below-the-gate", "silent"],
)
def test_render_leaves_short_and_weak_audio_unboosted(tmp_path, monkeypatch, samples):
    assert _render_one_segment(tmp_path, monkeypatch, samples) == samples


def test_render_caps_negative_pcm_peak_with_uniform_gain_even_for_short_segments(tmp_path, monkeypatch):
    raw = (-32_768, -16_384, 0, 8_192, 16_384)
    rendered = _render_one_segment(tmp_path, monkeypatch, raw)

    assert len(rendered) == len(raw)
    assert -rendered[0] == pytest.approx(32_768 * 10 ** (-2 / 20), abs=1)
    assert rendered[1] == pytest.approx(rendered[0] / 2, abs=1)
    assert rendered[2] == 0
    assert rendered[3] == pytest.approx(-rendered[0] / 4, abs=1)
    assert rendered[4] == -rendered[1]


def test_level_reports_peak_limiting_and_quiet_boost():
    spike = _tone(500)
    spike_list = list(spike)
    spike_list[len(spike_list) // 2] = 32_000
    transient_frames = struct.pack(f"<{len(spike_list)}h", *spike_list)
    leveled_spike = level_speech_pcm(transient_frames, RATE)
    assert leveled_spike.peak_limited is True
    assert leveled_spike.sample_peak_dbfs == pytest.approx(-2.0, abs=0.1)

    quiet_frames = struct.pack(f"<{TONE_FRAMES}h", *_tone(950))
    leveled_quiet = level_speech_pcm(quiet_frames, RATE)
    assert leveled_quiet.peak_limited is False
    assert 0 < leveled_quiet.gain_db <= 6.01


def test_render_logs_summary_with_gain_cache_and_delivery_counts(tmp_path, monkeypatch):
    text = "A synthetic sentence."
    source = tmp_path / "synthetic.md"
    source.write_text(text, encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    directed = AudioProfile(speed=1.0, instructions="Use a quiet aside.")
    plan = [
        SpeechSegment(text, profile, anchor=PASSAGE),
        SpeechSegment(text, directed, anchor=PASSAGE),
    ]
    monkeypatch.setattr(speech, "_synthesize_segment", lambda *_args, **_kwargs: _wav(_tone(950)))
    records = io.StringIO()
    logger = logging.Logger("lixity.speech.test.summary", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(records))
    monkeypatch.setattr(speech, "get_logger", lambda _suffix: logger)

    speech.render_speech_audio(
        source, tmp_path / "chapter.wav", profile=profile, plan=plan, cache_dir=tmp_path / "cache"
    )

    summaries = [
        dict(field.split("=", 1) for field in line.split())
        for line in records.getvalue().splitlines()
        if "event=render_summary" in line
    ]
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["segments"] == "2"
    assert summary["cache_misses"] == "2"
    assert float(summary["max_gain_db"]) > 0
    assert summary["unleveled_segments"] == "1"
    assert text not in records.getvalue()
    segment_ends = [
        dict(field.split("=", 1) for field in line.split())
        for line in records.getvalue().splitlines()
        if "event=segment_end" in line
    ]
    assert [record["delivery_preserved"] for record in segment_ends] == ["false", "true"]
