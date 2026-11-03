"""Project-local audio references are private, bounded and immutable."""

import json

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_references import load_reference, save_reference


def test_reference_round_trip_is_content_addressed_and_idempotent(tmp_path):
    audio = generate_silence_wav(1)
    transcript = "Ähre und Meer.\nWeiter."
    saved = save_reference(tmp_path, audio, transcript)
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    original = record.read_bytes()
    before = record.stat().st_mtime_ns
    again = save_reference(tmp_path, audio, transcript)
    assert again == saved == load_reference(tmp_path, saved.id)
    assert record.read_bytes() == original and record.stat().st_mtime_ns == before
    assert saved.audio == audio and saved.transcript == transcript
    assert transcript not in repr(saved) and repr(audio) not in repr(saved)
    assert save_reference(tmp_path, generate_silence_wav(1.1), transcript).id != saved.id
    assert save_reference(tmp_path, audio, transcript + "!").id != saved.id


@pytest.mark.parametrize("audio,transcript", [
    (b"not audio", "words"), (generate_silence_wav(.1), "words"),
    (generate_silence_wav(1, 16000), "words"),
    (generate_silence_wav(1), ""), (generate_silence_wav(1), "x\x00"),
    (generate_silence_wav(1), "x" * 2001),
])
def test_invalid_reference_never_creates_a_record(tmp_path, audio, transcript):
    with pytest.raises(ValueError):
        save_reference(tmp_path, audio, transcript)
    assert not (tmp_path / ".lixity" / "audio-references").exists()


def test_tampering_is_detected_and_is_not_overwritten(tmp_path):
    audio = generate_silence_wav(1)
    saved = save_reference(tmp_path, audio, "Synthetic words.")
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    data = json.loads(record.read_text())
    data["transcript"] = "Something different."
    tampered = json.dumps(data).encode()
    record.write_bytes(tampered)
    with pytest.raises(ValueError, match=r"identity|checksum"):
        load_reference(tmp_path, saved.id)
    with pytest.raises(ValueError):
        save_reference(tmp_path, audio, "Synthetic words.")
    assert record.read_bytes() == tampered


def test_references_reject_wrong_ids_missing_files_and_symlinks(tmp_path):
    with pytest.raises(ValueError):
        load_reference(tmp_path, "../outside")
    with pytest.raises(FileNotFoundError):
        load_reference(tmp_path, "0" * 64)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".lixity").mkdir()
    (tmp_path / ".lixity" / "audio-references").symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        save_reference(tmp_path, generate_silence_wav(1), "Synthetic words.")
    assert list(outside.iterdir()) == []


def test_reference_rejects_final_symlink_without_rewriting_target(tmp_path):
    audio = generate_silence_wav(1)
    saved = save_reference(tmp_path, audio, "Synthetic words.")
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    original = record.read_bytes()
    record.unlink()
    outside = tmp_path / "outside.json"
    outside.write_bytes(original)
    record.symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        load_reference(tmp_path, saved.id)
    with pytest.raises((ValueError, OSError)):
        save_reference(tmp_path, audio, "Synthetic words.")
    assert outside.read_bytes() == original


def test_reference_rejects_oversized_stored_data(tmp_path):
    saved = save_reference(tmp_path, generate_silence_wav(1), "Synthetic words.")
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    record.write_bytes(b"x" * (3 * 1024 * 1024))
    with pytest.raises(ValueError, match="bounded"):
        load_reference(tmp_path, saved.id)


def test_calibration_texts_and_retrieval():
    from lixity.speech_references import CALIBRATION_TEXTS, get_calibration_text

    assert "Nordwind" in CALIBRATION_TEXTS["de"]["phonetic"]
    assert "Boxkämpfer" in CALIBRATION_TEXTS["de"]["short"]
    assert "North Wind" in CALIBRATION_TEXTS["en"]["phonetic"]
    assert "quick brown fox" in CALIBRATION_TEXTS["en"]["short"]

    assert get_calibration_text("de", "phonetic") == CALIBRATION_TEXTS["de"]["phonetic"]
    assert get_calibration_text("de", "short") == CALIBRATION_TEXTS["de"]["short"]
    assert get_calibration_text("en", "phonetic") == CALIBRATION_TEXTS["en"]["phonetic"]
    assert get_calibration_text("unknown", "invalid") == CALIBRATION_TEXTS["de"]["phonetic"]


def test_generate_reference(tmp_path, monkeypatch):
    import lixity.speech_qwen
    from lixity.speech_references import generate_reference

    dummy_audio = generate_silence_wav(2)
    monkeypatch.setattr(lixity.speech_qwen, "synthesize_qwen", lambda text, profile, **kw: dummy_audio)

    ref = generate_reference(tmp_path, language="de")
    assert ref.audio == dummy_audio
    assert "Nordwind" in ref.transcript
    loaded = load_reference(tmp_path, ref.id)
    assert loaded == ref


def test_cli_calibration_text_and_generate(tmp_path, capsys, monkeypatch):
    import lixity.speech_qwen
    from lixity.cli import main

    # 1. calibration-text command doesn't need --project
    assert main(["audio-reference", "calibration-text", "--language", "de", "--variant", "phonetic"]) == 0
    out = capsys.readouterr().out
    assert "Nordwind" in out

    assert main(["audio-reference", "calibration-text", "--language", "en", "--variant", "short"]) == 0
    out = capsys.readouterr().out
    assert "quick brown fox" in out

    # 2. generate command
    dummy_audio = generate_silence_wav(2)
    monkeypatch.setattr(lixity.speech_qwen, "synthesize_qwen", lambda text, profile, **kw: dummy_audio)

    assert main([
        "audio-reference", "generate",
        "--project", str(tmp_path),
        "--language", "de",
        "--voice-description", "Warm narrative voice",
    ]) == 0
    out = capsys.readouterr().out
    res = json.loads(out)
    assert res["schema_version"] == "lixity-audio-reference-created/1"
    assert "id" in res


def test_cli_record_with_calibration_text(tmp_path, capsys, monkeypatch):
    import lixity.speech_record
    from lixity.cli import main

    dummy_audio = generate_silence_wav(2)
    monkeypatch.setattr(lixity.speech_record, "record_audio", lambda duration, **kw: dummy_audio)

    assert main([
        "audio-reference", "record",
        "--project", str(tmp_path),
        "--calibration-text",
        "--language", "de",
        "--variant", "short",
    ]) == 0
    captured = capsys.readouterr()
    assert "KALIBRIERUNGSTEXT (TELEPROMPTER)" in captured.err
    assert "Boxkämpfer" in captured.err
    res = json.loads(captured.out)
    assert res["schema_version"] == "lixity-audio-reference-created/1"
    assert "id" in res

