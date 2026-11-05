"""Chapter import binds user-selected PCM audio to a reviewed manuscript hash."""

import hashlib
import json
from pathlib import Path

import pytest

from lixity.cli import main
from lixity.speech import generate_silence_wav
from lixity.speech_artifacts import list_project_audio, read_project_audio, retain_chapter_audio


def inputs(tmp_path):
    source = tmp_path / "draft.md"
    source.write_text("## One\n\nA synthetic sentence.\n\n## Two\n\nAnother sentence.\n")
    (tmp_path / "lixity.toml").write_text('language = "en"\nmanuscript = "draft.md"\n')
    audio = tmp_path / "chapter.wav"
    audio.write_bytes(generate_silence_wav(.1))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return source, audio, digest


def test_import_retains_explicit_chapter_without_claiming_transcript_verification(tmp_path, capsys):
    source, audio, digest = inputs(tmp_path)
    before = source.read_bytes()
    assert main(["audio-import", "--project", str(tmp_path), "--audio", str(audio),
                 "--chapter", "2", "--source-sha256", digest]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "lixity-chapter-audio/1"
    assert result["origin"] == "imported" and result["chapter"] == 2
    assert "transcript" not in result
    entries = list_project_audio(tmp_path, source_sha256=digest, max_chapter=2)
    assert len(entries) == 1 and read_project_audio(tmp_path, entries[0]) == audio.read_bytes()
    assert source.read_bytes() == before


def test_stale_hash_or_missing_chapter_import_does_not_create_retained_audio(tmp_path, capsys):
    _source, audio, digest = inputs(tmp_path)
    for chapter, expected in (("1", "0" * 64), ("99", digest)):
        assert main(["audio-import", "--project", str(tmp_path), "--audio", str(audio),
                     "--chapter", chapter, "--source-sha256", expected]) != 0
        capsys.readouterr()
        assert not (tmp_path / ".lixity/audio/exports").exists()


def test_read_aloud_retains_completed_explicit_chapter_with_full_source_hash(tmp_path, monkeypatch):
    source, _, digest = inputs(tmp_path)
    before = source.read_bytes()
    output = tmp_path / "spoken.wav"
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: generate_silence_wav(.02))
    assert main(["read-aloud", "--project", str(tmp_path), "--chapter", "2", "--speed", "1.0",
                 "--no-audio-cache", "-o", str(output)]) == 0
    entries = list_project_audio(tmp_path, source_sha256=digest, max_chapter=2)
    assert len(entries) == 1
    assert entries[0].origin == "generated" and entries[0].chapter == 2
    assert entries[0].source_sha256 == digest
    assert read_project_audio(tmp_path, entries[0]) == output.read_bytes()
    assert source.read_bytes() == before


@pytest.mark.parametrize("scope", ["preview", "preview-line", "manuscript", "implicit-project", "mp3", "plan-only"])
def test_read_aloud_retains_only_explicit_complete_wav_chapters(tmp_path, monkeypatch, scope):
    source, _, _ = inputs(tmp_path)
    output = tmp_path / ("spoken.mp3" if scope == "mp3" else "spoken.wav")

    def render(**options):
        assert scope != "plan-only"
        path = Path(options["output_path"])
        path.write_bytes(generate_silence_wav(.02))
        return path

    monkeypatch.setattr("lixity.speech.render_speech_audio", render)
    command = ["read-aloud", "--speed", "1.0", "--no-audio-cache", "-o", str(output)]
    command += [str(source)] if scope == "implicit-project" else ["--project", str(tmp_path)]
    if scope != "manuscript":
        command += ["--chapter", "1"]
    if scope in ("preview", "plan-only"):
        command += [f"--{scope}"]
    elif scope == "preview-line":
        command += ["--preview-line", "3"]
    assert main(command) == 0
    assert not (tmp_path / ".lixity/audio/exports").exists()


@pytest.mark.parametrize("changed", ["source", "settings", "direction"])
def test_read_aloud_checks_context_again_before_retention_and_preserves_output(tmp_path, monkeypatch, capsys, changed):
    source, initial_audio, digest = inputs(tmp_path)
    previous = retain_chapter_audio(tmp_path, initial_audio.read_bytes(), source_sha256=digest, chapter=1, origin="imported")
    pointer = tmp_path / ".lixity/audio/exports/chapter-1.json"
    before = pointer.read_bytes()
    output = tmp_path / "spoken.wav"
    rendered = generate_silence_wav(.2)

    def render(**_options):
        output.write_bytes(rendered)
        if changed == "source":
            source.write_text("## One\n\nChanged after synthesis.\n")
        elif changed == "settings":
            (tmp_path / "lixity.toml").write_text('language = "de"\nmanuscript = "draft.md"\n')
        else:
            (tmp_path / ".lixity/audio-directions.json").write_text(json.dumps({"schema_version":"lixity-audio-directions/1","entries":[]}))
        return output

    monkeypatch.setattr("lixity.speech.render_speech_audio", render)
    assert main(["read-aloud", "--project", str(tmp_path), "--chapter", "1", "-o", str(output)]) == 1
    error = capsys.readouterr().err
    assert "written" in error and "retention" in error and "changed" in error
    assert output.read_bytes() == rendered
    assert pointer.read_bytes() == before
    assert read_project_audio(tmp_path, previous) == initial_audio.read_bytes()


def test_read_aloud_reports_retention_failure_without_removing_rendered_output(tmp_path, monkeypatch, capsys):
    inputs(tmp_path)
    output = tmp_path / "spoken.wav"
    rendered = generate_silence_wav(.2)

    def render(**_options):
        output.write_bytes(rendered)
        return output

    def fail_retention(*_args, **_kwargs):
        raise OSError("Synthetic retention failure")

    monkeypatch.setattr("lixity.speech.render_speech_audio", render)
    monkeypatch.setattr("lixity.speech_artifacts.retain_chapter_audio", fail_retention)
    assert main(["read-aloud", "--project", str(tmp_path), "--chapter", "1", "-o", str(output)]) == 1
    error = capsys.readouterr().err
    assert "written" in error and "retention failure" in error
    assert output.read_bytes() == rendered
    assert not (tmp_path / ".lixity/audio/exports").exists()
