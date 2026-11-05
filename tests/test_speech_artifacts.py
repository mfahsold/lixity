"""Retained chapter audio uses exact source bindings and verified PCM files."""

import hashlib
import json
from dataclasses import replace

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_artifacts import (
    list_project_audio,
    read_project_audio,
    retain_chapter_audio,
)

SOURCE = hashlib.sha256(b"Synthetic manuscript").hexdigest()
OTHER = hashlib.sha256(b"Changed manuscript").hexdigest()


def retain(root, audio=None, **kwargs):
    return retain_chapter_audio(root, audio or generate_silence_wav(.05),
                                source_sha256=SOURCE, chapter=1, origin="generated", **kwargs)


def test_retain_roundtrip_and_exact_source_chapter_filter(tmp_path):
    audio = generate_silence_wav(.05)
    entry = retain(tmp_path, audio)
    assert entry.chapter == 1 and entry.byte_length == len(audio)
    assert entry.duration_seconds == pytest.approx(.05)
    assert entry.audio_sha256 == hashlib.sha256(audio).hexdigest()
    assert entry.origin == "generated"
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == [entry]
    assert list_project_audio(tmp_path, source_sha256=OTHER, max_chapter=1) == []
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=0) == []
    assert read_project_audio(tmp_path, entry) == audio


def test_latest_success_replaces_pointer_and_old_audio(tmp_path):
    previous = retain(tmp_path)
    current = retain_chapter_audio(tmp_path, generate_silence_wav(.1),
                                  source_sha256=OTHER, chapter=1, origin="imported")
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == []
    assert list_project_audio(tmp_path, source_sha256=OTHER, max_chapter=1) == [current]
    assert len(list((tmp_path / ".lixity/audio/exports").glob("*.wav"))) == 1
    with pytest.raises((ValueError, FileNotFoundError)):
        read_project_audio(tmp_path, previous)


def test_invalid_or_cancelled_replacement_keeps_existing_record(tmp_path):
    original = retain(tmp_path)
    with pytest.raises(ValueError, match=r"WAV|PCM"):
        retain(tmp_path, b"not audio")
    with pytest.raises(ValueError, match=r"context|changed"):
        retain(tmp_path, generate_silence_wav(.1), valid=lambda: False)
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == [original]
    assert read_project_audio(tmp_path, original)


def test_commit_guard_rechecks_after_staging(tmp_path):
    original = retain(tmp_path)
    calls = []

    def valid():
        calls.append(True)
        return len(calls) < 3

    with pytest.raises(ValueError, match=r"context|changed"):
        retain(tmp_path, generate_silence_wav(.1), valid=valid)
    assert len(calls) >= 3
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == [original]


@pytest.mark.parametrize("change", ["hash", "size", "duration", "symlink", "truncated"])
def test_corrupt_current_audio_fails_instead_of_disappearing(tmp_path, change):
    entry = retain(tmp_path)
    folder = tmp_path / ".lixity/audio/exports"
    path = next(folder.glob("*.wav"))
    if change == "symlink":
        outside = tmp_path / "outside.wav"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    elif change == "truncated":
        path.write_bytes(path.read_bytes()[:-2])
    elif change == "hash":
        data = bytearray(path.read_bytes())
        data[-1] = 1
        path.write_bytes(data)
    else:
        pointer = folder / "chapter-1.json"
        obj = json.loads(pointer.read_text())
        obj["byte_length" if change == "size" else "duration_seconds"] += 1
        pointer.write_text(json.dumps(obj))
    with pytest.raises((OSError, ValueError)):
        list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1)
    with pytest.raises((OSError, ValueError)):
        read_project_audio(tmp_path, entry)


def test_later_chapter_metadata_is_not_opened_or_interpreted(tmp_path):
    entry = retain(tmp_path)
    later = tmp_path / ".lixity/audio/exports/chapter-2.json"
    later.write_text("not JSON and outside selected cap")
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == [entry]
    with pytest.raises(ValueError):
        list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=2)


def test_valid_stale_metadata_does_not_open_old_audio(tmp_path):
    retain(tmp_path)
    next((tmp_path / ".lixity/audio/exports").glob("*.wav")).unlink()
    assert list_project_audio(tmp_path, source_sha256=OTHER, max_chapter=1) == []


def test_forged_entry_and_symlinked_store_are_rejected(tmp_path):
    entry = retain(tmp_path)
    with pytest.raises((ValueError, FileNotFoundError)):
        read_project_audio(tmp_path, replace(entry, chapter=2))
    project = tmp_path / "other"
    project.mkdir()
    (project / ".lixity").symlink_to(tmp_path / ".lixity", target_is_directory=True)
    with pytest.raises(ValueError):
        list_project_audio(project, source_sha256=SOURCE, max_chapter=1)


@pytest.mark.parametrize("key,value", [("chapter", 0), ("chapter", True),
                                      ("source_sha256", "../escape"), ("origin", "reference")])
def test_invalid_binding_cannot_create_artifacts(tmp_path, key, value):
    options = {"chapter": 1, "source_sha256": SOURCE, "origin": "generated"}
    options[key] = value
    with pytest.raises(ValueError):
        retain_chapter_audio(tmp_path, generate_silence_wav(.05), **options)
    assert not (tmp_path / ".lixity/audio/exports").exists()


def test_malformed_trailing_chunk_and_partial_pcm_frame_are_rejected(tmp_path):
    audio = bytearray(generate_silence_wav(.05))
    audio.extend(b"JUNK")
    audio[4:8] = (len(audio) - 8).to_bytes(4, "little")
    with pytest.raises(ValueError, match="chunk"):
        retain(tmp_path, bytes(audio))
    audio = bytearray(generate_silence_wav(.05))
    audio.append(0)
    audio[4:8] = (len(audio) - 8).to_bytes(4, "little")
    audio[40:44] = (len(audio) - 44).to_bytes(4, "little")
    with pytest.raises(ValueError, match="PCM"):
        retain(tmp_path, bytes(audio))


def test_combined_budget_is_checked_before_audio_reads(tmp_path, monkeypatch):
    import lixity.speech_artifacts as artifacts

    first = retain(tmp_path)
    retain_chapter_audio(tmp_path, generate_silence_wav(.05), source_sha256=SOURCE, chapter=2, origin="generated")
    monkeypatch.setattr(artifacts, "MAX_CHAPTER_AUDIO_BYTES", first.byte_length)
    monkeypatch.setattr(artifacts, "read_project_audio", lambda *args: pytest.fail("Audio opened before combined budget validation"))
    with pytest.raises(ValueError, match="budget"):
        list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=2)


def test_cleanup_failure_does_not_claim_committed_replacement_failed(tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    previous = retain(tmp_path)
    original_unlink = Path.unlink
    logged = []
    monkeypatch.setattr("lixity.speech_artifacts.get_logger", lambda _name: SimpleNamespace(warning=logged.append))

    def fail_previous(path, *args, **kwargs):
        if previous.audio_sha256 in path.name:
            raise PermissionError("Synthetic old-file cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_previous)
    current = retain(tmp_path, generate_silence_wav(.1))
    assert list_project_audio(tmp_path, source_sha256=SOURCE, max_chapter=1) == [current]
    assert logged == ["chapter_audio stage=cleanup status=failed"]


def test_old_symlink_is_rejected_before_replacement_commit(tmp_path):
    original = retain(tmp_path)
    folder = tmp_path / ".lixity/audio/exports"
    pointer_before = (folder / "chapter-1.json").read_bytes()
    path = next(folder.glob("*.wav"))
    outside = tmp_path / "outside.wav"
    outside.write_bytes(generate_silence_wav(.05))
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(ValueError):
        retain(tmp_path, generate_silence_wav(.1))
    assert (folder / "chapter-1.json").read_bytes() == pointer_before
    assert original.audio_sha256 in path.name
