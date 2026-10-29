"""Audio diagnostics expose operational state without private content."""

import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from lixity import speech
from lixity.speech_direction import SpeechSegment
from lixity.speech_profiles import AudioProfile


@pytest.fixture
def records(monkeypatch):
    stream = io.StringIO()
    logger = logging.Logger("lixity.speech.test", logging.DEBUG)
    logger.addHandler(logging.StreamHandler(stream))
    monkeypatch.setattr(speech, "get_logger", lambda _: logger, raising=False)
    return stream


def test_speech_diagnostics_track_pcm_boundaries_cache_and_redact_private_data(tmp_path, monkeypatch, records, capsys):
    sentinel = "PRIVATE-MANUSCRIPT-INSTRUCTION-PATH"
    source = tmp_path / (sentinel + ".md")
    source.write_text(sentinel, encoding="utf-8")
    profile = AudioProfile(name=sentinel, instructions=sentinel, speed=1.0, language="de", voice="Ryan")
    second = AudioProfile(name=sentinel, instructions=sentinel + "2", speed=1.0, language="de", voice="Ryan")
    plan = [SpeechSegment(sentinel, profile, 0.1, 0.2), SpeechSegment(sentinel + "2", second, 0.05, 0.1)]
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    for n in range(2):
        speech.render_speech_audio(source, tmp_path / f"{sentinel}{n}.wav", profile=profile, plan=plan, cache_dir=tmp_path / "cache")
    log = records.getvalue()
    assert sentinel not in log and str(tmp_path) not in log
    assert "event=render_start" in log and "event=render_end" in log and "status=success" in log
    assert "requested_engine=qwen3" in log and "voice=Ryan" in log and "language=de" in log
    assert "tempo=1.0" in log
    assert "has_instruction=true" in log
    assert "instruction_changed=first" in log and "instruction_changed=true" in log
    assert "cache=miss" in log and "cache=hit" in log
    assert "pcm_start_ms=100" in log and "pcm_end_ms=110" in log
    assert "pcm_start_ms=360" in log and "pcm_end_ms=370" in log
    ids = re.findall(r"event=render_start id=([0-9a-f]{16})", log)
    assert len(ids) == 2 and len(set(ids)) == 2
    assert capsys.readouterr().out == ""


def test_speech_failure_logs_category_without_exception_text(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    def fail(*_args, **_kwargs):
        raise RuntimeError("SECRET-WORKER-ERROR")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", fail)
    with pytest.raises(RuntimeError, match="SECRET"):
        speech.render_speech_audio(source, tmp_path / "out.wav", profile=AudioProfile(speed=1.0),
                                   plan=[SpeechSegment("synthetic", AudioProfile(speed=1.0))])
    log = records.getvalue()
    assert "SECRET" not in log
    assert "event=segment_end" in log and "status=error" in log
    assert "event=render_end" in log and "error=runtime" in log


def test_cancelled_before_planning_is_logged_without_changing_exception(tmp_path, records):
    with pytest.raises(speech.SpeechCancelled):
        speech.render_speech_audio(tmp_path / "secret.md", tmp_path / "secret.wav", cancelled=lambda: True)
    log = records.getvalue()
    assert "event=render_end" in log and "status=cancelled" in log and "secret" not in log


def test_preflight_missing_path_never_leaks_path_to_logs(tmp_path, records):
    source = tmp_path / "sensitive-file-name.md"
    with pytest.raises(FileNotFoundError):
        speech.render_speech_audio(source, tmp_path / "out.wav")
    log = records.getvalue()
    assert "event=render_start" in log and "event=render_end" in log and "error=missing" in log
    assert "sensitive-file-name" not in log and str(tmp_path) not in log


def test_keyboard_interrupt_is_cancelled_and_propagated(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt("PRIVATE-INTERRUPT")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", interrupt)
    with pytest.raises(KeyboardInterrupt):
        speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile,
                                   plan=[SpeechSegment("synthetic", profile)])
    log = records.getvalue()
    assert "status=cancelled error=interrupted" in log
    assert "PRIVATE-INTERRUPT" not in log


def test_voice_design_description_never_appears_in_diagnostics(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(engine="qwen3-design", voice="design", voice_description="PRIVATE-DESCRIPTION", speed=1.0)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile,
                               plan=[SpeechSegment("synthetic", profile)])
    log = records.getvalue()
    assert "PRIVATE-DESCRIPTION" not in log
    assert "requested_engine=qwen3-design" in log and "voice=design" in log


@pytest.mark.parametrize("engine", ["qwen3-design", "qwen3-base"])
def test_voice_condition_changes_are_reported_without_disclosing_values(tmp_path, monkeypatch, records, engine):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    first_id, second_id = "a" * 64, "b" * 64
    if engine == "qwen3-design":
        first = AudioProfile(engine=engine, voice="design", voice_description="PRIVATE-DESCRIPTION-A")
        second = AudioProfile(engine=engine, voice="design", voice_description="PRIVATE-DESCRIPTION-B")
        references = None
        key = "description_changed"
    else:
        first = AudioProfile(engine=engine, voice="reference", reference_id=first_id)
        second = AudioProfile(engine=engine, voice="reference", reference_id=second_id)
        references = {first_id: SimpleNamespace(id=first_id), second_id: SimpleNamespace(id=second_id)}
        monkeypatch.setattr("lixity.speech_references.validate_reference", lambda _reference: None)
        key = "reference_changed"
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    plan = [SpeechSegment("one", first), SpeechSegment("two", first), SpeechSegment("three", second)]
    speech.render_speech_audio(source, tmp_path / "result.wav", profile=first, plan=plan, references=references)
    events = [line for line in records.getvalue().splitlines() if "event=segment_start" in line]
    assert len(events) == 3
    assert [re.search(rf"{key}=(first|true|false)", line).group(1) for line in events] == ["first", "false", "true"]
    assert "PRIVATE-DESCRIPTION" not in records.getvalue()
    assert first_id not in records.getvalue() and second_id not in records.getvalue()


def test_parallel_render_diagnostics_have_distinct_ids(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    def run(index):
        speech.render_speech_audio(source, tmp_path / f"{index}.wav", profile=profile,
                                   plan=[SpeechSegment("synthetic", profile)])
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, range(2)))
    ids = re.findall(r"event=render_start id=([0-9a-f]{16})", records.getvalue())
    assert len(ids) == 2 and len(set(ids)) == 2


def test_pcm_offsets_use_tempo_adjusted_audio_and_following_pause(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(speed=1.2)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.04))
    monkeypatch.setattr(speech.shutil, "which", lambda _name: "ffmpeg")
    def adjust(command):
        Path(command[-1]).write_bytes(speech.generate_silence_wav(0.02))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(speech, "_run_ffmpeg", adjust)
    plan = [SpeechSegment("one", profile, 0.1, 0.2), SpeechSegment("two", profile, 0.05, 0)]
    speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile, plan=plan)
    log = records.getvalue()
    assert "pcm_start_ms=100" in log and "pcm_end_ms=120" in log
    assert "pcm_start_ms=370" in log and "pcm_end_ms=390" in log
    assert "instruction_changed=false" in log and "cache=disabled" in log
    assert "tempo=1.2" in log


def test_nested_render_shares_only_internal_diagnostic_id(tmp_path, monkeypatch, records):
    from lixity.log import speech_diagnostic_id, speech_diagnostic_scope

    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    with speech_diagnostic_scope() as job_id:
        speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile,
                                   plan=[SpeechSegment("synthetic", profile)])
        assert speech_diagnostic_id() == job_id
    assert speech_diagnostic_id() is None
    assert f"event=render_start id={job_id}" in records.getvalue()
    assert f"event=segment_start id={job_id}" in records.getvalue()


def test_info_level_reports_render_summary_without_segment_events(tmp_path, monkeypatch, records):
    source = tmp_path / "source.md"
    source.write_text("synthetic", encoding="utf-8")
    profile = AudioProfile(speed=1.0)
    speech.get_logger("speech").setLevel(logging.INFO)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_a, **_kw: speech.generate_silence_wav(0.01))
    speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile,
                               plan=[SpeechSegment("synthetic", profile)])
    log = records.getvalue()
    assert "event=render_start" in log and "event=render_plan" in log and "event=render_end" in log
    assert "event=segment_start" not in log and "event=segment_end" not in log


def test_diagnostic_tempo_uses_shared_playback_limits(monkeypatch, records):
    # A changed product limit must also change what the diagnostic regards as valid.
    monkeypatch.setattr(speech, "MIN_PLAYBACK_SPEED", 1.0)
    profile = AudioProfile(speed=0.75)
    with speech._observe_speech_segment(1, 1, profile, 0, "first", "first", "first"):
        pass
    assert "tempo=unknown" in records.getvalue()
