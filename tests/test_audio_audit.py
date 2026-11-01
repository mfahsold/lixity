"""Read-only chapter audio diagnostics use synthetic PCM and external timestamps."""

import hashlib
import io
import json
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from lixity.audio_audit import inspect_audio, load_audit_json


def _wav(path: Path, samples: list[int], *, channels: int = 1, rate: int = 1000) -> Path:
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return path


def _plan(*segments: dict) -> dict:
    return {"schema_version": "lixity-audio-timeline/1", "segments": list(segments)}


def _transcript(path: Path, words: list[tuple[str, float, float]], **extra: object) -> dict:
    return {"schema_version": "lixity-audio-transcript/1",
            "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "words": [{"text": text, "start": start, "end": end}
                      for text, start, end in words], **extra}


def test_pcm_measurements_preserve_stereo_without_cancellation(tmp_path: Path) -> None:
    path = _wav(tmp_path / "stereo.wav", [16384, -16384] * 1000, channels=2)
    original = path.read_bytes()
    result = inspect_audio(path)
    assert result["schema_version"] == "lixity-audio-audit/1"
    assert result["audio"]["duration_seconds"] == 1.0
    assert result["audio"]["channels"] == 2
    assert result["audio"]["sample_rate_hz"] == 1000
    assert result["signal"]["rms_dbfs"] == pytest.approx(-6.0206, abs=0.0001)
    assert result["signal"]["channel_metrics"][0]["dc_offset"] == 0.5
    assert result["signal"]["channel_metrics"][1]["dc_offset"] == -0.5
    assert result["signal"]["silences"] == []
    assert result["alignment"]["status"] == "unknown"
    assert result["alignment"]["reason"]
    assert result["signal"]["noise_floor_dbfs"] is None
    assert result["signal"]["bandwidth_hz"] is None
    assert inspect_audio(path) == result
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    json.dumps(result, allow_nan=False)


def test_long_chapter_silence_is_measured_without_reference_length_limit(tmp_path: Path) -> None:
    path = _wav(tmp_path / "chapter.wav", [0] * 61_000)
    result = inspect_audio(path)
    assert result["audio"]["duration_seconds"] == 61
    assert result["signal"]["peak_dbfs"] is None
    assert result["signal"]["rms_dbfs"] is None
    assert result["signal"]["silences"] == [{"start": 0.0, "end": 61.0, "duration": 61.0}]
    assert result["signal"]["silence_seconds"] == 61
    assert result["signal"]["clipped_samples"] == 0
    assert result["alignment"]["coverage"] is None


def test_full_scale_counts_and_silence_times_are_absolute(tmp_path: Path) -> None:
    path = _wav(tmp_path / "level.wav", [32767, -32768] * 250 + [0] * 500)
    signal = inspect_audio(path)["signal"]
    assert signal["peak_dbfs"] == 0
    assert signal["clipped_samples"] == 500
    assert signal["clipped_sample_fraction"] == 0.5
    assert signal["silences"] == [{"start": 0.5, "end": 1.0, "duration": 0.5}]


def test_truncated_pcm_fails_instead_of_reporting_shorter_audio(tmp_path: Path) -> None:
    path = _wav(tmp_path / "truncated.wav", [100] * 1000)
    path.write_bytes(path.read_bytes()[:-50])
    with pytest.raises(ValueError, match=r"[Tt]runcat"):
        inspect_audio(path)


def test_empty_and_unsupported_audio_are_rejected(tmp_path: Path) -> None:
    path = _wav(tmp_path / "empty.wav", [])
    with pytest.raises(ValueError, match=r"empty|frames"):
        inspect_audio(path)
    other = tmp_path / "not-audio.txt"
    other.write_text("synthetic text")
    with pytest.raises(ValueError, match=r"WAV|FLAC|MP3"):
        inspect_audio(other)


def test_missing_word_has_no_invented_timestamp_or_pause_anchor(tmp_path: Path) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 3000)
    plan = _plan({"text": "Hello brave world.", "pause_after": 0.5}, {"text": "Good day."})
    transcript = _transcript(path, [("HELLO", 0.1, 0.3), ("world!", 0.4, 0.6),
                                    ("Good", 1.2, 1.4), ("day", 1.5, 1.8)])
    result = inspect_audio(path, expected_plan=plan, transcript=transcript)
    alignment = result["alignment"]
    assert alignment["status"] == "compared"
    assert alignment["coverage"] == 0.8
    assert alignment["matched_words"] == 4
    assert [word["text"] for word in alignment["missing_words"]] == ["brave"]
    assert alignment["missing_words"][0]["start"] is None
    assert alignment["missing_words"][0]["end"] is None
    assert alignment["missing_words"][0]["after_seconds"] == 0.3
    assert alignment["missing_words"][0]["before_seconds"] == 0.4
    assert alignment["transcript_model"]["status"] == "unknown"
    assert result["pauses"]["status"] == "unknown"
    assert result["pauses"]["comparisons"] == []


def test_extra_and_replaced_words_keep_external_audio_times(tmp_path: Path) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 3000)
    result = inspect_audio(path, expected_plan=_plan({"text": "A red bird sings."}),
                           transcript=_transcript(path, [("A", 0.1, 0.2), ("blue", 0.3, 0.4),
                                                       ("bird", 0.5, 0.6), ("sings", 0.7, 0.8),
                                                       ("today", 0.9, 1.0)], model="external-test"))
    alignment = result["alignment"]
    assert alignment["coverage"] == 0.75
    assert alignment["missing_words"] == []
    assert alignment["replacements"][0]["expected_words"] == ["red"]
    assert alignment["replacements"][0]["transcript_words"] == ["blue"]
    assert alignment["replacements"][0]["start"] == 0.3
    assert alignment["replacements"][0]["end"] == 0.4
    assert alignment["extra_words"][0]["text"] == "today"
    assert alignment["extra_words"][0]["start"] == 0.9
    assert alignment["transcript_model"]["name"] == "external-test"


def test_fully_matching_segments_anchor_planned_pause_and_pcm_silence(tmp_path: Path) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 3000)
    result = inspect_audio(path, expected_plan=_plan(
        {"text": "Hello world.", "pause_after": 0.3},
        {"text": "", "pause_before": 0.1, "pause_after": 0.2},
        {"text": "Good day.", "pause_before": 0.1}),
        transcript=_transcript(path, [("Hello", 0.1, 0.3), ("world", 0.4, 0.6),
                                     ("Good", 1.5, 1.7), ("day", 1.8, 2.0)]))
    comparison = result["pauses"]["comparisons"][0]
    assert result["alignment"]["coverage"] == 1
    assert result["pauses"]["status"] == "compared"
    assert comparison["start"] == 0.6
    assert comparison["end"] == 1.5
    assert comparison["planned_seconds"] == pytest.approx(0.7)
    assert comparison["observed_seconds"] == pytest.approx(0.9)
    assert comparison["difference_seconds"] == pytest.approx(0.2)
    assert comparison["detected_silence_seconds"] == pytest.approx(0.9)


def test_extra_word_between_segments_prevents_pause_comparison(tmp_path: Path) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 2000)
    result = inspect_audio(path, expected_plan=_plan({"text": "Hello"}, {"text": "world"}),
                           transcript=_transcript(path, [("Hello", 0.1, 0.2),
                                                       ("um", 0.3, 0.4), ("world", 0.5, 0.6)]))
    assert result["pauses"]["comparisons"] == []
    assert result["pauses"]["status"] == "unknown"


@pytest.mark.parametrize("change", [
    {"audio_sha256": "0" * 64},
    {"schema_version": "unrecognized/1"},
    {"words": [{"text": "one", "start": 0.2, "end": 0.1}]},
    {"words": [{"text": "one", "start": -0.1, "end": 0.2}]},
    {"words": [{"text": "one", "start": 0.1, "end": 1.1}]},
    {"words": [{"text": "one", "start": math.nan, "end": 0.5}]},
    {"words": [{"text": "one", "start": 0.1, "end": math.inf}]},
    {"words": [{"text": "one", "start": True, "end": 0.5}]},
    {"words": [{"text": "two words", "start": 0.1, "end": 0.5}]},
    {"words": [{"text": "one", "start": 0.1, "end": 0.5},
               {"text": "two", "start": 0.4, "end": 0.7}]},
])
def test_invalid_transcripts_are_rejected_not_treated_as_unknown(tmp_path: Path, change: dict) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    transcript = _transcript(path, [("one", 0.1, 0.2)])
    transcript.update(change)
    with pytest.raises(ValueError):
        inspect_audio(path, expected_plan=_plan({"text": "one"}), transcript=transcript)


def test_german_unicode_normalization_uses_explicit_language(tmp_path: Path) -> None:
    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    result = inspect_audio(path, language="de", expected_plan=_plan({"text": "Äpfel, süß-sauer!"}),
                           transcript=_transcript(path, [("A\u0308PFEL", 0.1, 0.3),
                                                       ("SÜSS-SAUER", 0.4, 0.6)]))
    # Lowercasing preserves ß versus ss; this is token matching, not pronunciation inference.
    assert result["alignment"]["coverage"] == 0.5
    assert result["alignment"]["language"] == "de"
    with pytest.raises(ValueError, match="language"):
        inspect_audio(path, language="not-a-language")


def test_alignment_budget_rejects_huge_unmatched_sequences(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    monkeypatch.setattr(audit, "MAX_ALIGNMENT_CELLS", 4)
    with pytest.raises(ValueError, match="budget"):
        inspect_audio(path, expected_plan=_plan({"text": "one two three"}),
                      transcript=_transcript(path, [("four", 0.1, 0.2), ("five", 0.3, 0.4),
                                                  ("six", 0.5, 0.6)]))


def test_json_reader_rejects_duplicate_keys_and_non_objects(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_text('{"words": [], "words": [1]}')
    with pytest.raises(ValueError, match=r"[Dd]uplicate"):
        load_audit_json(path)
    path.write_text("[]")
    with pytest.raises(ValueError, match="object"):
        load_audit_json(path)


@pytest.mark.parametrize("width,values,expected_dc", [
    (1, bytes([192]) * 1000, 0.5),
    (3, (4194304).to_bytes(3, "little", signed=True) * 1000, 0.5),
    (4, struct.pack("<i", 1073741824) * 1000, 0.5),
])
def test_other_integer_pcm_widths_keep_full_scale_normalization(
    tmp_path: Path, width: int, values: bytes, expected_dc: float,
) -> None:
    path = tmp_path / "width.wav"
    with wave.open(str(path), "wb") as output:
        output.setparams((1, width, 1000, 0, "NONE", "not compressed"))
        output.writeframes(values)
    result = inspect_audio(path)
    assert result["audio"]["sample_width_bits"] == width * 8
    assert result["signal"]["dc_offset"] == expected_dc
    assert result["signal"]["rms_dbfs"] == pytest.approx(-6.0206, abs=0.0001)


def test_silence_requires_every_channel_and_retains_complete_totals(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = _wav(tmp_path / "channel.wav", [0, 4000] * 200 + [0, 0] * 200
                + [0, 4000] * 200 + [0, 0] * 200, channels=2)
    monkeypatch.setattr(audit, "MAX_SILENCES", 1)
    signal = inspect_audio(path)["signal"]
    assert signal["silences"] == [{"start": 0.2, "end": 0.4, "duration": 0.2}]
    assert signal["silence_count"] == 2
    assert signal["silence_seconds"] == 0.4
    assert signal["silences_truncated"] is True


def test_missing_decoder_is_explicit_and_creates_no_project_files(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = tmp_path / "audio.flac"
    path.write_bytes(b"synthetic unsupported encoded audio")
    monkeypatch.setattr(audit.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match="FFmpeg"):
        inspect_audio(path)
    assert list(tmp_path.iterdir()) == [path]


def test_pcm_sample_budget_rejects_before_partial_measurement(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    monkeypatch.setattr(audit, "MAX_PCM_SAMPLES", 999)
    with pytest.raises(ValueError, match="budget"):
        inspect_audio(path)


def test_identical_long_text_avoids_quadratic_comparison_budget(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    monkeypatch.setattr(audit, "MAX_ALIGNMENT_CELLS", 1)
    result = inspect_audio(path, expected_plan=_plan({"text": "one two three"}),
                           transcript=_transcript(path, [("one", 0.1, 0.2), ("two", 0.3, 0.4),
                                                       ("three", 0.5, 0.6)]))
    assert result["alignment"]["coverage"] == 1


def test_audit_accepts_effective_segments_without_loading_voice_reference(tmp_path: Path) -> None:
    from lixity.speech_direction import SpeechSegment
    from lixity.speech_profiles import AudioProfile

    path = _wav(tmp_path / "audio.wav", [0] * 1000)
    reference_profile = AudioProfile(engine="qwen3-base", voice="reference", language="en",
                                     reference_id="a" * 64)
    result = inspect_audio(path, expected_plan=[SpeechSegment("One.", reference_profile)],
                           transcript=_transcript(path, [("one", 0.1, 0.2)]))
    assert result["alignment"]["coverage"] == 1
    assert list(tmp_path.iterdir()) == [path]


def test_json_budget_and_nonfinite_values_fail_without_partial_input(tmp_path: Path, monkeypatch) -> None:
    import lixity.audio_audit as audit

    path = tmp_path / "input.json"
    path.write_text('{"value": NaN}')
    with pytest.raises(ValueError, match="finite"):
        load_audit_json(path)
    monkeypatch.setattr(audit, "MAX_JSON_BYTES", 4)
    path.write_text('{"value": 1}')
    with pytest.raises(ValueError, match="bounded"):
        load_audit_json(path)


@pytest.mark.parametrize("extension", ["flac", "mp3"])
def test_available_ffmpeg_decodes_external_formats(tmp_path: Path, extension: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is unavailable for compressed chapter audio")
    source = _wav(tmp_path / "source.wav", [8000, -8000] * 8000, rate=16000)
    audio = tmp_path / f"chapter.{extension}"
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source), str(audio)],  # noqa: S603 -- synthetic local fixture
                   check=True, timeout=15, capture_output=True)
    before = audio.read_bytes()
    result = inspect_audio(audio)
    assert result["audio"]["format"] == extension
    assert result["audio"]["duration_seconds"] == pytest.approx(1, abs=0.15)
    assert result["audio"]["sample_rate_hz"] == 16000
    assert result["signal"]["rms_dbfs"] is not None
    assert audio.read_bytes() == before


def _float_wav(path: Path) -> Path:
    samples = struct.pack("<ff", 0.5000000596046448, -0.25) * 1600
    fmt = struct.pack("<HHIIHH", 3, 2, 16000, 128000, 8, 32)
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(samples)) + samples
    path.write_bytes(b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks)
    return path


@pytest.mark.parametrize("extension", ["flac", "mp3", "float.wav"])
def test_ffmpeg_pcm32_is_portable_to_wave_without_extensible_support(
    tmp_path: Path, monkeypatch, extension: str,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is unavailable for compressed chapter audio")
    audio = _float_wav(tmp_path / "float.wav")
    if extension != "float.wav":
        source = audio
        audio = tmp_path / f"chapter.{extension}"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(source), str(audio)],  # noqa: S603 -- synthetic local fixture
                       check=True, timeout=15, capture_output=True)
    original = audio.read_bytes()
    real_open = wave.open

    def pre312_open(file, mode="rb"):
        # Python 3.10/3.11 rejects WAVE_FORMAT_EXTENSIBLE before examining its
        # PCM subtype. Exercise that boundary even on newer development Python.
        if mode == "rb":
            if isinstance(file, (str, Path)):
                with Path(file).open("rb") as handle:
                    header = handle.read(4096)
            else:
                position = file.tell()
                header = file.read(4096)
                file.seek(position)
            cursor = 12
            while cursor + 10 <= len(header):
                length = struct.unpack_from("<I", header, cursor + 4)[0]
                if header[cursor:cursor + 4] == b"fmt ":
                    if struct.unpack_from("<H", header, cursor + 8)[0] == 0xFFFE:
                        raise wave.Error("unknown format: 65534")
                    break
                cursor += 8 + length + length % 2
        return real_open(file, mode)

    monkeypatch.setattr(wave, "open", pre312_open)
    result = inspect_audio(audio)
    assert result["audio"]["channels"] == 2
    assert result["audio"]["sample_rate_hz"] == 16000
    assert result["audio"]["sample_width_bits"] == 32
    if extension == "float.wav":
        assert result["signal"]["channel_metrics"][0]["dc_offset"] == 0.5000000596046448
        assert result["signal"]["channel_metrics"][1]["dc_offset"] == -0.25
    assert audio.read_bytes() == original


@pytest.mark.parametrize("repair_riff_size", [False, True])
def test_truncated_float_wav_fails_before_optional_conversion(
    tmp_path: Path, monkeypatch, repair_riff_size: bool,
) -> None:
    import lixity.audio_audit as audit

    audio = _float_wav(tmp_path / "float.wav")
    truncated = bytearray(audio.read_bytes()[:-8])
    if repair_riff_size:
        # A correct outer size must not hide an incomplete declared data chunk.
        struct.pack_into("<I", truncated, 4, len(truncated) - 8)
    audio.write_bytes(truncated)
    # Validation must detect missing declared source data even without FFmpeg.
    monkeypatch.setattr(audit.shutil, "which", lambda _name: None)
    with pytest.raises(ValueError, match=r"[Tt]runcat"):
        inspect_audio(audio)


def test_classic_pcm_odd_sized_data_remains_readable(tmp_path: Path) -> None:
    audio = tmp_path / "odd.wav"
    data = io.BytesIO()
    with wave.open(data, "wb") as output:
        output.setparams((1, 1, 1000, 0, "NONE", "not compressed"))
        output.writeframes(bytes([128, 192, 128]))
    audio.write_bytes(data.getvalue())
    assert inspect_audio(audio)["audio"]["frames"] == 3
