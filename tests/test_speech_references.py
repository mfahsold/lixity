"""Project-local audio references are private, bounded and immutable."""
# ruff: noqa: RUF001 -- IPA symbols in the synthetic probe are intentional.

import hashlib
import json
from dataclasses import FrozenInstanceError, fields, replace

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_references import (
    SpeechReference,
    SpeechReferenceSet,
    VoiceReferenceInUse,
    delete_reference,
    delete_reference_set,
    list_reference_sets,
    list_references,
    load_reference,
    load_reference_set,
    load_voice_reference,
    prepare_reference,
    references_for_plan,
    references_unchanged,
    save_reference,
    save_reference_set,
    validate_reference,
    validate_reference_set,
)
from lixity.speech_worker import MAX_BASE_REQUEST_BYTES


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
    with pytest.raises((ValueError, OSError)):
        delete_reference(tmp_path, saved.id)
    assert outside.read_bytes() == original


def test_delete_reference_failure_keeps_record_and_allows_retry(tmp_path, monkeypatch):
    audio = generate_silence_wav(1)
    saved = save_reference(tmp_path, audio, "Synthetic first recording.")
    other = save_reference(tmp_path, audio, "Synthetic second recording.")
    config = tmp_path / "lixity.toml"
    config.write_text('[audio]\nschema_version = "invalid"\n')
    with pytest.raises(ValueError, match="schema_version"):
        delete_reference(tmp_path, saved.id)
    assert load_reference(tmp_path, saved.id) == saved

    config.write_text('language = "en"\n')
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    unlink = type(record).unlink

    def unavailable(path, *args, **kwargs):
        if path == record:
            raise PermissionError("Synthetic removal denied")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(type(record), "unlink", unavailable)
        with pytest.raises(PermissionError, match="Synthetic removal denied"):
            delete_reference(tmp_path, saved.id)
    assert load_reference(tmp_path, saved.id) == saved

    delete_reference(tmp_path, saved.id)
    assert not record.exists()
    assert load_reference(tmp_path, other.id) == other
    assert config.read_text() == 'language = "en"\n'


def test_reference_rejects_oversized_stored_data(tmp_path):
    saved = save_reference(tmp_path, generate_silence_wav(1), "Synthetic words.")
    record = tmp_path / ".lixity" / "audio-references" / f"{saved.id}.json"
    record.write_bytes(b"x" * (MAX_BASE_REQUEST_BYTES + 1))
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


@pytest.mark.parametrize(("configured", "variant", "extra", "expected", "excerpt"), [
    (None, "short", [], 15, "Boxkämpfer"),
    (None, "phonetic", [], 60, "Nordwind"),
    (37, "short", [], 37, "Boxkämpfer"),
    (37, "phonetic", [], 37, "Nordwind"),
    (37, "phonetic", ["--duration", "15"], 15, "Nordwind"),
    (None, "phonetic", ["--transcript", "Synthetic custom text."], 15, "Synthetic custom text."),
    (37, "phonetic", ["--transcript", "Synthetic custom text."], 37, "Synthetic custom text."),
])
def test_cli_record_with_calibration_text(tmp_path, capsys, monkeypatch, configured, variant, extra, expected, excerpt):
    import lixity.speech_record
    from lixity.cli import main

    def record(duration, **options):
        assert duration == expected
        return generate_silence_wav(duration)

    monkeypatch.setattr(lixity.speech_record, "record_audio", record)
    if configured is not None:
        (tmp_path / "lixity.toml").write_text(f"[audio_recording]\nreference_seconds = {configured}\n")

    assert main([
        "audio-reference", "record",
        "--project", str(tmp_path),
        "--calibration-text",
        "--language", "de",
        "--variant", variant,
        *extra,
    ]) == 0
    captured = capsys.readouterr()
    assert "KALIBRIERUNGSTEXT (TELEPROMPTER)" in captured.err
    assert excerpt in captured.err
    res = json.loads(captured.out)
    assert res["schema_version"] == "lixity-audio-reference-created/1"
    assert "id" in res
    assert res["quality"]["duration_seconds"] == expected


def _prepared_parts(durations, *, prefix="Synthetic part"):
    return [
        prepare_reference(generate_silence_wav(duration), f"{prefix} {index}.")
        for index, duration in enumerate(durations, 1)
    ]


def _probe(part_count=3, *, language="de", source_sha256="b" * 64, settings_sha256="c" * 64):
    parts = []
    for index in range(1, part_count + 1):
        first = " ".join(["Private", "probe", "phrase", *(["synthetic"] * 21), str(index)])
        second = " ".join(["Retained", "manuscript", "span", *(["term"] * 21), str(index)])
        parts.append({
            "index": index,
            "text": first + " " + second,
            "words": 50,
            "estimated_seconds": 23,
            "terms": ["Mara"] if index == 1 else [],
            "substitutions": [{
                "start": 0, "end": 7, "source": "Private", "replacement": "Public",
                "kind": "substitution",
            }] if index == 1 else [],
            "phonemes": [{
                "start": 8, "end": 13, "source": "probe", "replacement": "pɹoʊb",
                "kind": "phoneme",
            }] if index == 1 else [],
            "sentences": [
                {
                    "text": first,
                    "words": 25,
                    "start_line": index,
                    "end_line": index,
                    "terms": ["Mara"] if index == 1 else [],
                    "dialogue": False,
                },
                {
                    "text": second,
                    "words": 25,
                    "start_line": index,
                    "end_line": index,
                    "terms": [],
                    "dialogue": False,
                },
            ],
        })
    probe = {
        "schema_version": "lixity-voice-probe-script/1",
        "status": "ready",
        "language": language,
        "target_seconds": 150,
        "estimated_seconds": 150,
        "duration_method": "word_count_at_130_wpm",
        "method_version": "lixity-voice-probe-method/1",
        "source_sha256": source_sha256,
        "settings_sha256": settings_sha256,
        "selected_terms": ["Mara"],
        "covered_terms": ["Mara"],
        "term_provenance": [{
            "term": "Mara", "kind": "lexicon", "count": 1,
            "ipa": "maːra", "respelling": "Mara",
        }],
        "warnings": [],
        "parts": parts,
    }
    probe["probe_sha256"] = _probe_hash(probe)
    return probe


def _probe_hash(probe):
    canonical = dict(probe)
    canonical.pop("probe_sha256", None)
    return hashlib.sha256(json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _save_set(project, parts, *, source_sha256="b" * 64, settings_sha256="c" * 64,
              terms=("Mara", "Travemünde"), fallback_part_index=1, probe=None):
    probe = _probe(
        len(parts), source_sha256=source_sha256, settings_sha256=settings_sha256,
    ) if probe is None else probe
    return save_reference_set(
        project, parts, source_sha256=source_sha256, settings_sha256=settings_sha256,
        probe_sha256=_probe_hash(probe), language="de", terms=terms,
        fallback_part_index=fallback_part_index, probe=probe,
    )


def _record_path(project, reference_id):
    return project / ".lixity" / "audio-references" / f"{reference_id}.json"


def test_prepare_reference_validates_without_writing(tmp_path):
    with pytest.raises(ValueError):
        prepare_reference(b"not audio", "Invalid.")
    assert not (tmp_path / ".lixity").exists()
    audio = generate_silence_wav(1)
    snapshot = prepare_reference(audio, "Prepared without a write.")
    assert isinstance(snapshot, SpeechReference)
    assert not (tmp_path / ".lixity").exists()
    assert snapshot == save_reference(tmp_path, audio, "Prepared without a write.")
    assert load_reference(tmp_path, snapshot.id) == snapshot


def test_reference_set_is_immutable_ordered_and_project_bound(tmp_path):
    assert [item.name for item in fields(SpeechReference)] == ["id", "audio", "transcript"]
    assert [item.name for item in fields(SpeechReferenceSet)] == [
        "id", "parts", "source_sha256", "settings_sha256", "probe_sha256",
        "language", "terms", "fallback_part_index", "probe",
    ]
    parts = _prepared_parts((40, 40, 40))
    probe = _probe()
    assert not (tmp_path / ".lixity" / "audio-references").exists()
    saved = _save_set(tmp_path, parts, probe=probe)
    loaded = load_reference_set(tmp_path, saved.id)
    assert loaded == saved == load_voice_reference(tmp_path, saved.id)
    assert loaded.parts == tuple(parts)
    assert loaded.source_sha256 == "b" * 64
    assert loaded.settings_sha256 == "c" * 64
    assert loaded.probe_sha256 == _probe_hash(probe)
    assert loaded.language == "de"
    assert loaded.terms == ("Mara", "Travemünde")
    assert loaded.fallback_part_index == 1
    assert loaded.probe == probe and loaded.probe is not probe
    validate_reference(loaded)
    validate_reference_set(loaded)
    with pytest.raises(FrozenInstanceError):
        loaded.fallback_part_index = 2
    assert "Private probe phrase" not in repr(loaded)
    assert parts[0].transcript not in repr(loaded)
    assert parts[0].id not in repr(loaded)
    assert "Travemünde" not in repr(loaded)
    with pytest.raises(ValueError, match="identity"):
        validate_reference(replace(loaded, source_sha256="d" * 64))
    with pytest.raises(ValueError, match=r"set|load_reference_set"):
        load_reference(tmp_path, saved.id)
    with pytest.raises(ValueError, match=r"single|not a set|supported size"):
        load_reference_set(tmp_path, parts[0].id)

    probe["parts"][0]["text"] = "Caller mutation."
    assert load_reference_set(tmp_path, saved.id).probe["parts"][0]["text"].startswith("Private probe phrase")
    record = _record_path(tmp_path, saved.id)
    manifest = json.loads(record.read_text(encoding="utf-8"))
    assert set(manifest) == {
        "schema_version", "id", "part_ids", "source_sha256", "settings_sha256",
        "probe_sha256", "language", "terms", "fallback_part_index", "probe",
    }
    assert manifest["schema_version"] == "lixity-audio-reference-set/1"
    assert manifest["part_ids"] == [part.id for part in parts]
    original = record.read_bytes()
    before = record.stat().st_mtime_ns
    part_record = _record_path(tmp_path, parts[0].id)
    part_before = part_record.stat().st_mtime_ns
    assert _save_set(tmp_path, parts, probe=_probe()) == saved
    assert record.read_bytes() == original and record.stat().st_mtime_ns == before
    assert part_record.stat().st_mtime_ns == part_before


@pytest.mark.parametrize(("durations", "accepted"), [
    ((40, 40, 40), True),
    ((40, 40, 39.999), False),
    ((30, 30, 30, 30, 30, 30), True),
    ((30, 30, 30, 30, 30, 30.001), False),
])
def test_reference_set_uses_actual_inclusive_total_duration(tmp_path, durations, accepted):
    parts = _prepared_parts(durations)
    if accepted:
        saved = _save_set(tmp_path, parts)
        assert load_reference_set(tmp_path, saved.id) == saved
    else:
        with pytest.raises(ValueError, match="total 120 to 180"):
            _save_set(tmp_path, parts)
        assert not (tmp_path / ".lixity" / "audio-references").exists()


def test_reference_set_rejects_too_few_too_many_or_duplicate_parts(tmp_path):
    two = _prepared_parts((60, 60))
    seven = _prepared_parts((20,) * 7)
    first, second, third = _prepared_parts((40, 40, 40))
    with pytest.raises(ValueError, match="three to six"):
        _save_set(tmp_path, two)
    with pytest.raises(ValueError, match="three to six"):
        _save_set(tmp_path, seven)
    with pytest.raises(ValueError, match="distinct"):
        _save_set(tmp_path, [first, first, third])
    assert second not in (first, third)
    assert not (tmp_path / ".lixity" / "audio-references").exists()


@pytest.mark.parametrize("fallback", [0, 4, -1, True, 1.0, "1"])
def test_reference_set_rejects_bad_fallback_before_writing(tmp_path, fallback):
    with pytest.raises(ValueError, match="fallback_part_index"):
        _save_set(tmp_path, _prepared_parts((40, 40, 40)), fallback_part_index=fallback)
    assert not (tmp_path / ".lixity" / "audio-references").exists()


def test_reference_set_rejects_malformed_probe_and_hash_mismatch(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    probe = _probe()
    probe["unexpected"] = "unknown"
    with pytest.raises(ValueError, match="Malformed voice probe"):
        _save_set(tmp_path, parts, probe=probe)
    probe = _probe()
    probe["schema_version"] = "lixity-voice-probe-script/0"
    with pytest.raises(ValueError, match=r"Unsupported|mismatched"):
        _save_set(tmp_path, parts, probe=probe)
    probe = _probe()
    probe["parts"] = probe["parts"][:2]
    with pytest.raises(ValueError, match="do not match"):
        _save_set(tmp_path, parts, probe=probe)
    probe = _probe()
    probe["warnings"] = ["old string warning"]
    with pytest.raises(ValueError, match="Malformed voice probe warning"):
        _save_set(tmp_path, parts, probe=probe)
    probe = _probe()
    probe["parts"][0]["phonemes"][0]["kind"] = "substitution"
    with pytest.raises(ValueError, match="pronunciation kind"):
        _save_set(tmp_path, parts, probe=probe)
    probe = _probe()
    probe["term_provenance"][0]["unexpected"] = True
    with pytest.raises(ValueError, match="term provenance"):
        _save_set(tmp_path, parts, probe=probe)
    with pytest.raises(ValueError, match="checksum"):
        save_reference_set(
            tmp_path, parts, source_sha256="b" * 64, settings_sha256="c" * 64,
            probe_sha256="d" * 64, language="de", probe=_probe(),
        )
    with pytest.raises(ValueError, match="complete voice probe"):
        save_reference_set(
            tmp_path, parts, source_sha256="b" * 64, settings_sha256="c" * 64,
            probe_sha256=_probe_hash(_probe()), language="de", probe=None,
        )
    assert not (tmp_path / ".lixity" / "audio-references").exists()


@pytest.mark.parametrize(("field", "message"), [
    ("source_sha256", "identity"),
    ("settings_sha256", "identity"),
    ("probe_sha256", "checksum"),
])
def test_reference_set_detects_manifest_hash_tampering(tmp_path, field, message):
    saved = _save_set(tmp_path, _prepared_parts((40, 40, 40)))
    record = _record_path(tmp_path, saved.id)
    manifest = json.loads(record.read_text(encoding="utf-8"))
    manifest[field] = "d" * 64
    record.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_reference_set(tmp_path, saved.id)


def test_reference_set_detects_probe_tampering(tmp_path):
    saved = _save_set(tmp_path, _prepared_parts((40, 40, 40)))
    record = _record_path(tmp_path, saved.id)
    manifest = json.loads(record.read_text(encoding="utf-8"))
    manifest["probe"]["parts"][0]["text"] = "Changed private phrase."
    record.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        load_reference_set(tmp_path, saved.id)


def test_reference_set_rejects_corrupt_or_missing_parts_without_overwriting(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    part_record = _record_path(tmp_path, parts[0].id)
    data = json.loads(part_record.read_text(encoding="utf-8"))
    data["transcript"] = "Tampered member."
    corrupt = json.dumps(data).encode("utf-8")
    part_record.write_bytes(corrupt)
    with pytest.raises(ValueError, match="identity"):
        load_reference_set(tmp_path, saved.id)
    with pytest.raises(ValueError, match="identity"):
        _save_set(tmp_path, parts)
    assert part_record.read_bytes() == corrupt

    part_record.unlink()
    with pytest.raises(FileNotFoundError):
        load_reference_set(tmp_path, saved.id)
    with pytest.raises(ValueError, match="load_reference_set"):
        load_reference(tmp_path, saved.id)


def test_reference_set_rejects_unknown_old_and_oversized_manifests(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    record = _record_path(tmp_path, saved.id)
    original = json.loads(record.read_text(encoding="utf-8"))
    unknown = {**original, "unexpected": True}
    record.write_text(json.dumps(unknown), encoding="utf-8")
    corrupt = record.read_bytes()
    with pytest.raises(ValueError, match="Invalid audio reference set"):
        load_reference_set(tmp_path, saved.id)
    with pytest.raises(ValueError, match="Invalid audio reference set"):
        _save_set(tmp_path, parts)
    assert record.read_bytes() == corrupt

    old = {**original, "schema_version": "lixity-audio-reference-set/0"}
    record.write_text(json.dumps(old), encoding="utf-8")
    with pytest.raises(ValueError, match=r"schema|fallback"):
        load_reference_set(tmp_path, saved.id)

    record.write_bytes(json.dumps(original).encode("utf-8") + b" " * (64 * 1024))
    with pytest.raises(ValueError, match=r"supported size|bounded"):
        load_voice_reference(tmp_path, saved.id)

    record.write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match=r"supported size|bounded"):
        load_reference_set(tmp_path, saved.id)


def test_reference_set_rejects_nested_sets(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    record = _record_path(tmp_path, saved.id)
    manifest = json.loads(record.read_text(encoding="utf-8"))
    manifest["part_ids"][0] = saved.id
    record.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="nested sets"):
        load_reference_set(tmp_path, saved.id)


def test_reference_set_rejects_manifest_and_member_symlinks(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    record = _record_path(tmp_path, saved.id)
    original = record.read_bytes()
    outside = tmp_path / "outside-set.json"
    outside.write_bytes(original)
    record.unlink()
    record.symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        load_reference_set(tmp_path, saved.id)
    with pytest.raises((ValueError, OSError)):
        _save_set(tmp_path, parts)
    with pytest.raises((ValueError, OSError)):
        delete_reference_set(tmp_path, saved.id)
    assert outside.read_bytes() == original

    record.unlink()
    record.write_bytes(original)
    part_record = _record_path(tmp_path, parts[0].id)
    part_original = part_record.read_bytes()
    outside_part = tmp_path / "outside-part.json"
    outside_part.write_bytes(part_original)
    part_record.unlink()
    part_record.symlink_to(outside_part)
    with pytest.raises((ValueError, OSError)):
        load_reference_set(tmp_path, saved.id)
    assert outside_part.read_bytes() == part_original


def test_failed_set_publication_cleans_only_new_unreferenced_parts(tmp_path, monkeypatch):
    from lixity.io import FileUtils

    original_write = FileUtils.atomic_write_bytes_if_changed

    def fail_manifest(filepath, content, **kwargs):
        if json.loads(content)["schema_version"] == "lixity-audio-reference-set/1":
            raise OSError("Synthetic manifest failure")
        return original_write(filepath, content, **kwargs)

    parts = _prepared_parts((40, 40, 40))
    with monkeypatch.context() as scoped:
        scoped.setattr(FileUtils, "atomic_write_bytes_if_changed", fail_manifest)
        with pytest.raises(OSError, match="Synthetic manifest failure"):
            _save_set(tmp_path, parts)
    assert list_references(tmp_path) == []
    assert list_reference_sets(tmp_path) == []
    assert all(not _record_path(tmp_path, part.id).exists() for part in parts)
    saved = _save_set(tmp_path, parts)
    assert load_reference_set(tmp_path, saved.id) == saved


def test_failed_set_publication_retains_preexisting_part(tmp_path, monkeypatch):
    from lixity.io import FileUtils

    original_write = FileUtils.atomic_write_bytes_if_changed

    def fail_manifest(filepath, content, **kwargs):
        if json.loads(content)["schema_version"] == "lixity-audio-reference-set/1":
            raise OSError("Synthetic manifest failure")
        return original_write(filepath, content, **kwargs)

    parts = _prepared_parts((40, 40, 40))
    existing = save_reference(tmp_path, parts[0].audio, parts[0].transcript)
    with monkeypatch.context() as scoped:
        scoped.setattr(FileUtils, "atomic_write_bytes_if_changed", fail_manifest)
        with pytest.raises(OSError, match="Synthetic manifest failure"):
            _save_set(tmp_path, parts)
    assert load_reference(tmp_path, existing.id) == existing
    assert all(not _record_path(tmp_path, part.id).exists() for part in parts[1:])

def test_reference_listings_separate_singles_and_sets(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    singles = list_references(tmp_path)
    assert {item["id"] for item in singles} == {part.id for part in parts}
    assert all(item["kind"] == "reference" and item["part_count"] == 1 for item in singles)
    assert {item["transcript"] for item in singles} == {part.transcript for part in parts}
    sets = list_reference_sets(tmp_path)
    assert len(sets) == 1
    summary = sets[0]
    assert summary == {
        "id": saved.id,
        "kind": "set",
        "part_count": 3,
        "part_ids": [part.id for part in parts],
        "duration_seconds": 120.0,
        "sample_rate": 24000,
        "language": "de",
        "source_sha256": "b" * 64,
        "settings_sha256": "c" * 64,
        "probe_sha256": saved.probe_sha256,
        "fallback_part_index": 1,
        "terms": ["Mara", "Travemünde"],
    }
    assert "transcript" not in summary


def test_delete_reference_is_blocked_by_set_and_set_delete_retains_parts(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    with pytest.raises(VoiceReferenceInUse, match="set uses"):
        delete_reference(tmp_path, parts[0].id)
    with pytest.raises(ValueError, match="delete_reference_set"):
        delete_reference(tmp_path, saved.id)
    assert load_reference_set(tmp_path, saved.id) == saved

    delete_reference_set(tmp_path, saved.id)
    assert list_reference_sets(tmp_path) == []
    assert len(list_references(tmp_path)) == 3
    for part in parts:
        assert load_reference(tmp_path, part.id) == part
        delete_reference(tmp_path, part.id)
    assert list_references(tmp_path) == []


@pytest.mark.parametrize("uses_member", [False, True])
def test_delete_reference_set_preserves_profile_in_use_checks(tmp_path, uses_member):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    reference_id = parts[0].id if uses_member else saved.id
    (tmp_path / "lixity.toml").write_text(
        '[audio]\nschema_version = "lixity-audio-settings/5"\nselected = "narrator"\n'
        '[audio.profiles.narrator]\nengine = "ims-toucan"\nlanguage = "de"\n'
        f'voice = "reference"\nreference_id = "{reference_id}"\n',
        encoding="utf-8",
    )
    with pytest.raises(VoiceReferenceInUse, match="profile"):
        delete_reference_set(tmp_path, saved.id)
    with pytest.raises(VoiceReferenceInUse):
        delete_reference(tmp_path, parts[0].id)
    assert load_reference_set(tmp_path, saved.id) == saved


def test_plan_reference_snapshots_include_sets(tmp_path):
    from lixity.speech_direction import SpeechSegment
    from lixity.speech_profiles import AudioProfile

    saved = _save_set(tmp_path, _prepared_parts((40, 40, 40)))
    profile = AudioProfile(
        engine="ims-toucan", language="de", voice="reference", reference_id=saved.id,
    )
    snapshots = references_for_plan(tmp_path, [SpeechSegment("Synthetic prose.", profile)])
    assert snapshots == {saved.id: saved}
    assert references_unchanged(tmp_path, snapshots)
    delete_reference_set(tmp_path, saved.id)
    assert not references_unchanged(tmp_path, snapshots)


def test_list_references(tmp_path):
    assert list_references(tmp_path) == []
    audio = generate_silence_wav(1)
    saved = save_reference(tmp_path, audio, "Erster Text.")
    refs = list_references(tmp_path)
    assert len(refs) == 1
    assert refs[0]["id"] == saved.id
    assert refs[0]["transcript"] == "Erster Text."
    assert refs[0]["duration_seconds"] == 1.0
    assert refs[0]["sample_rate"] == 24000
    assert refs[0]["part_count"] == 1
    assert refs[0]["kind"] == "reference"


def test_reference_set_rejects_altered_part_snapshot_before_writing(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    parts[0] = replace(parts[0], id="0" * 64)
    with pytest.raises(ValueError, match="identity"):
        _save_set(tmp_path, parts)
    assert not (tmp_path / ".lixity" / "audio-references").exists()


def test_reference_set_identity_separates_order_counts_and_metadata(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts, terms=("ab", "c"))
    variants = [
        _save_set(tmp_path, list(reversed(parts)), terms=("ab", "c")),
        _save_set(tmp_path, parts, terms=("a", "bc")),
        _save_set(tmp_path, parts, terms=("ab", "c"), fallback_part_index=2),
        _save_set(tmp_path, parts, terms=("ab", "c"), settings_sha256="d" * 64),
    ]
    assert len({saved.id, *(item.id for item in variants)}) == 5


def test_missing_other_member_does_not_bypass_set_delete_protection(tmp_path):
    parts = _prepared_parts((40, 40, 40))
    saved = _save_set(tmp_path, parts)
    _record_path(tmp_path, parts[1].id).unlink()
    with pytest.raises(VoiceReferenceInUse, match="set uses"):
        delete_reference(tmp_path, parts[0].id)
    assert load_reference(tmp_path, parts[0].id) == parts[0]
    assert _record_path(tmp_path, saved.id).exists()


def test_reference_set_accepts_current_generated_probe(tmp_path):
    from lixity.speech_probe import build_voice_probe_script

    lines = ["## Erstes Kapitel", ""]
    for index in range(1, 31):
        lines.extend([
            f"Mara besucht den alten Leuchtturm in Travemünde Nummer {index}.",
            f"Hansen prüft den Frachtbrief von Kowalski am Hafen von Lübeck Nummer {index}.",
            f"Die Latente Steuern belastet die Rechnung aus Rotterdam Nummer {index}.",
            "",
        ])
    script = build_voice_probe_script("\n".join(lines), language="de", target_seconds=150)
    assert script.status == "ready"
    parts = _prepared_parts((120 / len(script.parts),) * len(script.parts))
    saved = save_reference_set(
        tmp_path, parts, source_sha256=script.source_sha256,
        settings_sha256=script.settings_sha256, probe_sha256=script.probe_sha256,
        language=script.language, terms=script.selected_terms, probe=script.to_dict(),
    )
    assert load_reference_set(tmp_path, saved.id) == saved
