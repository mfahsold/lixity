"""Tests for speech synthesis module and read-aloud CLI command."""

from __future__ import annotations

import io
import wave
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lixity.cli import main
from lixity.speech import (
    concatenate_wavs,
    extract_audio_cues,
    generate_silence_wav,
)

SAMPLE_MANUSCRIPT = """# Buch

## Kapitel 1: Der Anfang

Mara ging durch den herbstlichen Wald. Der Wind blies kalt durch die Zweige.

„Wir müssen weitergehen“, flüsterte Mara leise.

---

[TODO: Weitere Details zur Burg einfügen]
Am Horizont tauchten die finsteren Türme der alten Bergfeste auf.

## Kapitel 2: Die Ankunft

Die Zugbrücke war heruntergelassen. Mara zögerte keinen Moment.
"""


def test_extract_audio_cues_structure():
    cues = extract_audio_cues(
        SAMPLE_MANUSCRIPT,
        language="de",
        has_emotional_voice=True,
        skip_editorial_markers=True,
    )

    kinds = [c.kind for c in cues]
    assert "heading" in kinds
    assert "narrative" in kinds
    assert "dialogue" in kinds
    assert "scene_break" in kinds

    # Verify editorial marker [TODO: ...] was stripped
    texts = [c.text for c in cues]
    assert not any("TODO" in t for t in texts)

    # Dialogue cue checks
    dlg = next(c for c in cues if c.kind == "dialogue")
    assert "Wir müssen weitergehen" in dlg.text
    assert dlg.speaker_id == 4  # Dialogue keeps the neutral delivery used for narration.

    # Heading cue checks
    heading = next(c for c in cues if c.kind == "heading")
    assert "Kapitel 1" in heading.text
    assert heading.pause_after >= 1.0


def test_extract_audio_cues_chapter_filter():
    cues_ch1 = extract_audio_cues(SAMPLE_MANUSCRIPT, language="de", chapter_filter=1)
    for c in cues_ch1:
        assert c.chapter_num == 1
    assert any("Kapitel 1" in c.text for c in cues_ch1)
    assert not any("Kapitel 2" in c.text for c in cues_ch1)

    cues_ch2 = extract_audio_cues(SAMPLE_MANUSCRIPT, language="de", chapter_filter=2)
    for c in cues_ch2:
        assert c.chapter_num == 2
    assert any("Kapitel 2" in c.text for c in cues_ch2)
    assert not any("Kapitel 1" in c.text for c in cues_ch2)


def test_extract_audio_cues_keep_markers():
    cues = extract_audio_cues(
        SAMPLE_MANUSCRIPT,
        language="de",
        skip_editorial_markers=False,
    )
    texts = " ".join(c.text for c in cues)
    assert "TODO" in texts


def test_generate_silence_and_concatenate():
    silence = generate_silence_wav(0.1, sample_rate=16000, channels=1, sample_width=2)
    with wave.open(io.BytesIO(silence), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 1600

    combined = concatenate_wavs([silence, silence])
    with wave.open(io.BytesIO(combined), "rb") as wf:
        assert wf.getnframes() == 3200


def test_cli_read_aloud_help():
    buf = io.StringIO()
    with redirect_stdout(buf):
        try:
            main(["read-aloud", "--help"])
        except SystemExit as exc:
            assert exc.code == 0
    help_text = buf.getvalue()
    assert "--output" in help_text
    assert "--chapter" in help_text
    assert "--voice" in help_text
    assert "--speed" in help_text
    assert "--keep-markers" in help_text


def test_cli_read_aloud_dispatch(tmp_path: Path):
    doc = tmp_path / "manuscript.md"
    doc.write_text(SAMPLE_MANUSCRIPT, encoding="utf-8")
    out_wav = tmp_path / "output.wav"

    with patch("lixity.speech.render_speech_audio", return_value=out_wav) as mock_render:
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main([
                "read-aloud",
                str(doc),
                "-o", str(out_wav),
                "--chapter", "1",
                "--speed", "1.1",
                "--language", "de",
            ])
        assert ret == 0
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args.kwargs
        assert call_kwargs["chapter"] == 1
        assert call_kwargs["base_speed"] == 1.1
        assert call_kwargs["language"] == "de"
        assert "output.wav" in buf.getvalue()


# These cases exercise audible policy rather than infer intention from prose.
def test_letters_and_emotion_words_keep_one_neutral_voice_and_speed():
    text = '''# Example

## Brief 1

Die Lampe leuchtete leise. Er war müde.

„Nein!“, schrie sie wütend.

Ein Satz. Noch einer. Dies ist ein deutlich längerer Satz, der keine neue Sprechgeschwindigkeit auslösen soll.
'''
    cues = extract_audio_cues(text, language="de", has_emotional_voice=True, base_speed=1.2)
    spoken = [cue for cue in cues if cue.text]
    assert {cue.speaker_id for cue in spoken} == {4}
    assert all(abs(cue.length_scale - 1 / 1.2) < 1e-9 for cue in spoken)
    assert len({cue.sentence_silence for cue in spoken}) == 1


def test_unknown_chapter_never_falls_back_to_the_whole_manuscript():
    import pytest

    for value in (0, -1, 99, "missing chapter"):
        with pytest.raises(ValueError, match=r"chapter|Chapter"):
            extract_audio_cues(SAMPLE_MANUSCRIPT, language="de", chapter_filter=value)


def test_invalid_speed_is_rejected_instead_of_silently_clamped():
    import pytest

    for speed in (0, -1, float("nan"), float("inf"), 4):
        with pytest.raises(ValueError, match=r"speed|Speed"):
            extract_audio_cues(SAMPLE_MANUSCRIPT, base_speed=speed)


def test_concatenation_rejects_missing_truncated_and_mismatched_audio():
    import pytest

    valid = generate_silence_wav(.1, sample_rate=16000)
    for segments in ([], [b""], [b"not wav"], [valid[:-2]],
                     [valid, generate_silence_wav(.1, sample_rate=22050)],
                     [valid, generate_silence_wav(.1, sample_rate=16000, channels=2)]):
        with pytest.raises(ValueError, match=r"audio|WAV|format|PCM"):
            concatenate_wavs(segments)


def test_external_piper_failure_is_not_a_missing_passage(tmp_path):
    import subprocess

    import pytest

    from lixity.speech import AudioCue, synthesize_cue_subprocess

    with patch("lixity.speech.subprocess.run", return_value=subprocess.CompletedProcess([], 1, b"", b"failed")), pytest.raises(RuntimeError, match=r"Piper"):
        synthesize_cue_subprocess(AudioCue("Synthetic passage", "narrative"), "piper", tmp_path/"voice.onnx", tmp_path/"voice.json")


def _fake_renderer(tmp_path, monkeypatch):
    import json
    import sys
    from types import SimpleNamespace

    import lixity.speech as speech

    voice_dir = tmp_path / "voices" / "synthetic"
    voice_dir.mkdir(parents=True)
    (voice_dir / "synthetic.onnx").write_bytes(b"model")
    (voice_dir / "synthetic.onnx.json").write_text(json.dumps({
        "audio": {"sample_rate": 16000}, "num_speakers": 8,
        "speaker_id_map": {"neutral": 3, "whisper": 7},
    }))
    calls = []

    class Voice:
        config = SimpleNamespace(sample_rate=16000)

        @staticmethod
        def load(*_args, **_kwargs):
            return Voice()

        def synthesize(self, text, config):
            calls.append((text, config))
            yield SimpleNamespace(audio_int16_bytes=b"\x01\x00" * 160,
                                  sample_rate=16000, sample_width=2, sample_channels=1)

    monkeypatch.setattr(speech, "DEFAULT_VOICE_DIR", voice_dir.parent)
    monkeypatch.setitem(sys.modules, "piper.config", SimpleNamespace(SynthesisConfig=SimpleNamespace))
    monkeypatch.setitem(sys.modules, "piper.voice", SimpleNamespace(PiperVoice=Voice))
    monkeypatch.setattr(speech.shutil, "which", lambda _name: None)
    source = tmp_path / "source.md"
    source.write_text("# Synthetic\n\n## First\n\nA short passage.\n\nAnother passage.")
    return speech, source, calls, Voice


def test_render_uses_model_neutral_mapping_and_sample_rate(tmp_path, monkeypatch):
    speech, source, calls, _voice = _fake_renderer(tmp_path, monkeypatch)
    output = speech.render_speech_audio(source, tmp_path/"result.wav", voice_name="synthetic")
    assert calls and all(config.speaker_id == 3 for _text, config in calls)
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 16000
        assert audio.getnframes() > 0


def test_failed_or_empty_synthesis_preserves_existing_output(tmp_path, monkeypatch):
    import pytest

    speech, source, _calls, voice = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "result.wav"
    output.write_bytes(b"previous output")
    monkeypatch.setattr(voice, "synthesize", lambda *_args: iter(()))
    with pytest.raises((ValueError, RuntimeError), match=r"audio|Piper|segment"):
        speech.render_speech_audio(source, output, voice_name="synthetic")
    assert output.read_bytes() == b"previous output"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.wav", "source.md", "voices"]


def test_mp3_requires_ffmpeg_and_failed_conversion_is_atomic(tmp_path, monkeypatch):
    import subprocess

    import pytest

    speech, source, calls, _voice = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "result.mp3"
    output.write_bytes(b"previous output")
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError), match=r"FFmpeg|ffmpeg"):
        speech.render_speech_audio(source, output, voice_name="synthetic")
    assert not calls and output.read_bytes() == b"previous output"
    monkeypatch.setattr(speech.shutil, "which", lambda _name: "/synthetic/ffmpeg")
    monkeypatch.setattr(speech.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 1, b"", b"conversion failed"))
    with pytest.raises(RuntimeError, match=r"FFmpeg|ffmpeg"):
        speech.render_speech_audio(source, output, voice_name="synthetic")
    assert output.read_bytes() == b"previous output"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.mp3", "source.md", "voices"]


def test_quoted_and_list_prose_are_read_without_markdown_destinations():
    text = '''## First

> A **quoted** passage with [a label](https://example.invalid/private-path).
>
> Another quoted paragraph.

- A list entry.
'''
    spoken = " ".join(cue.text for cue in extract_audio_cues(text, language="en"))
    assert "A quoted passage with a label." in spoken
    assert "Another quoted paragraph." in spoken
    assert "A list entry." in spoken
    assert "**" not in spoken and "https://" not in spoken


def test_long_paragraphs_remain_complete_with_only_one_paragraph_pause():
    body = " ".join(f"Sentence {i} keeps its own words." for i in range(80))
    cues = [cue for cue in extract_audio_cues("## First\n\n" + body, language="en")
            if cue.kind == "narrative"]
    assert len(cues) > 1
    assert " ".join(cue.text for cue in cues) == body
    assert all(len(cue.text) <= 600 for cue in cues)
    assert sum(cue.pause_after > 0 for cue in cues) == 1


def test_unbounded_word_is_rejected_without_changing_its_spelling():
    import pytest

    with pytest.raises(ValueError, match="word"):
        extract_audio_cues("## First\n\n" + "x" * 601, language="en")


def test_piper_profile_owns_speed_voice_and_pronunciations(tmp_path, monkeypatch):
    from lixity.speech_profiles import AudioProfile

    speech, source, calls, _voice = _fake_renderer(tmp_path, monkeypatch)
    old = tmp_path / "voices" / "synthetic"
    selected = "en_US-lessac-medium"
    directory = old.with_name(selected)
    old.rename(directory)
    (directory / "synthetic.onnx").rename(directory / f"{selected}.onnx")
    (directory / "synthetic.onnx.json").rename(directory / f"{selected}.onnx.json")
    profile = AudioProfile(voice=selected, language="en", speed=1.4,
                           pronunciations={"passage": "reading"})
    speech.render_speech_audio(source, tmp_path / "result.wav", language="de", base_speed=.7,
                               voice_name="invalid", profile=profile)
    assert calls and all(config.length_scale == 1 / 1.4 for _text, config in calls)
    assert "reading" in " ".join(text for text, _config in calls)
    assert "passage" in source.read_text()


def test_cli_uses_saved_profile_without_replacing_its_language_with_project_default(tmp_path):
    from lixity.config import prepare_project_settings
    project = tmp_path / 'project'
    project.mkdir()
    source = project / 'manuscript.md'
    source.write_text('## One\n\nA small passage.')
    (project / 'lixity.toml').write_text('language = "en"\nmanuscript = "manuscript.md"\n')
    prepare_project_settings(project, {'audio': {'selected':'reader','profiles':{'reader':{
        'name':'Reader','engine':'qwen3','language':'de','voice':'Ryan','instructions':'Ruhig vorlesen.'
    }}}}).commit()
    with patch('lixity.speech.render_speech_audio', return_value=tmp_path/'result.wav') as render:
        assert main(['read-aloud','--project',str(project),'--profile','reader','-o',str(tmp_path/'result.wav')]) == 0
        assert render.call_args.kwargs['profile'].language == 'de'
        assert render.call_args.kwargs['profile'].instructions == 'Ruhig vorlesen.'


def test_cli_rejects_unsupported_qwen_speed_before_rendering(tmp_path):
    from lixity.config import prepare_project_settings
    project = tmp_path/'project'
    project.mkdir()
    source=project/'manuscript.md'
    source.write_text('## One\n\nA small passage.')
    (project/'lixity.toml').write_text('language="en"\nmanuscript="manuscript.md"\n')
    prepare_project_settings(project, {'audio': {'selected':'reader','profiles':{'reader':{
        'name':'Reader','engine':'qwen3','language':'en','voice':'Ryan'
    }}}}).commit()
    with patch('lixity.speech.render_speech_audio') as render:
        assert main(['read-aloud','--project',str(project),'--speed','1.2','-o',str(tmp_path/'result.wav')]) == 1
        render.assert_not_called()


def test_audio_byte_limit_counts_structural_silence_and_preserves_output(tmp_path, monkeypatch):
    import pytest

    speech, source, calls, _voice = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "limited.wav"
    output.write_bytes(b"previous audio")
    # The first PCM chunk (320 bytes) fits; its one-second heading pause does not.
    with pytest.raises(ValueError, match="byte limit"):
        speech.render_speech_audio(source, output, voice_name="synthetic", max_audio_bytes=500)
    assert len(calls) == 1
    assert output.read_bytes() == b"previous audio"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["limited.wav", "source.md", "voices"]


def test_audio_byte_limit_rejects_invalid_bounds_before_loading(tmp_path):
    import pytest

    from lixity.speech import render_speech_audio

    for limit in (0, 43, -1, True, 100.5):
        with pytest.raises(ValueError, match="byte limit"):
            render_speech_audio(tmp_path / "missing.md", tmp_path / "out.wav", max_audio_bytes=limit)
