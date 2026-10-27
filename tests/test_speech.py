"""Tests for speech synthesis module and read-aloud CLI command."""

from __future__ import annotations

import io
import wave
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest

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


def test_default_render_uses_qwen_without_voice_files(tmp_path, monkeypatch):
    from lixity.speech import render_speech_audio

    source = tmp_path / "synthetic.md"
    source.write_text("One synthetic listening sentence.")
    calls = []

    def synthesize(text, profile, **kwargs):
        calls.append((text, profile.engine, profile.voice, profile.language, kwargs["target"]))
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    output = render_speech_audio(source, tmp_path / "out.wav", language="en", target="jetson")
    assert calls == [("One synthetic listening sentence.", "qwen3", "Ryan", "en", "jetson")]
    with wave.open(str(output)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 24000)
    assert source.read_text() == "One synthetic listening sentence."


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
    assert "--speech-target" in help_text
    assert "--keep-markers" in help_text


def test_read_aloud_script_forwards_to_the_shared_cli(monkeypatch):
    import runpy
    import sys

    calls = []
    monkeypatch.setattr("lixity.cli.main", lambda args: calls.append(args) or 7)
    monkeypatch.setattr(sys, "argv", ["read_aloud.py", "synthetic.md", "--speech-target", "jetson"])
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "read_aloud.py"))
    assert module["main"]() == 7
    assert calls == [["read-aloud", "synthetic.md", "--speech-target", "jetson"]]


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
                "--language", "de",
            ])
        assert ret == 0
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args.kwargs
        assert call_kwargs["chapter"] == 1
        assert call_kwargs["profile"].engine == "qwen3"
        assert call_kwargs["language"] == "de"
        assert "output.wav" in buf.getvalue()


# These cases exercise audible policy rather than infer intention from prose.


def test_unknown_chapter_never_falls_back_to_the_whole_manuscript():
    import pytest

    for value in (0, -1, 99, "missing chapter"):
        with pytest.raises(ValueError, match=r"chapter|Chapter"):
            extract_audio_cues(SAMPLE_MANUSCRIPT, language="de", chapter_filter=value)




def test_concatenation_rejects_missing_truncated_and_mismatched_audio():
    import pytest

    valid = generate_silence_wav(.1, sample_rate=16000)
    for segments in ([], [b""], [b"not wav"], [valid[:-2]],
                     [valid, generate_silence_wav(.1, sample_rate=22050)],
                     [valid, generate_silence_wav(.1, sample_rate=16000, channels=2)]):
        with pytest.raises(ValueError, match=r"audio|WAV|format|PCM"):
            concatenate_wavs(segments)




def _fake_renderer(tmp_path, monkeypatch):
    import lixity.speech as speech

    calls = []

    def synthesize(text, profile, **_kwargs):
        calls.append((text, profile))
        return generate_silence_wav(.005, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    monkeypatch.setattr(speech.shutil, "which", lambda _name: None)
    source = tmp_path / "source.md"
    source.write_text("# Synthetic\n\n## First\n\nA short passage.\n\nAnother passage.")
    return speech, source, calls


def test_render_uses_one_selected_qwen_profile_and_sample_rate(tmp_path, monkeypatch):
    from lixity.speech_profiles import AudioProfile

    speech, source, calls = _fake_renderer(tmp_path, monkeypatch)
    profile = AudioProfile(voice="Ryan", language="en", instructions="Read calmly.")
    output = speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile)
    assert calls and all(selected == profile for _text, selected in calls)
    with wave.open(str(output), "rb") as audio:
        assert audio.getframerate() == 24000
        assert audio.getnframes() > 0


@pytest.mark.parametrize("data", [b"", b"not a WAV", generate_silence_wav(.01, 24000)[:-2],
                                  generate_silence_wav(.01, 16000)])
def test_invalid_synthesis_preserves_existing_output(tmp_path, monkeypatch, data):
    speech, source, _calls = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "result.wav"
    output.write_bytes(b"previous output")
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda *_args, **_kwargs: data)
    with pytest.raises(ValueError, match=r"audio|WAV|PCM"):
        speech.render_speech_audio(source, output)
    assert output.read_bytes() == b"previous output"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.wav", "source.md"]


def test_mp3_requires_ffmpeg_and_failed_conversion_is_atomic(tmp_path, monkeypatch):
    import subprocess

    import pytest

    speech, source, calls = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "result.mp3"
    output.write_bytes(b"previous output")
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError), match=r"FFmpeg|ffmpeg"):
        speech.render_speech_audio(source, output)
    assert not calls and output.read_bytes() == b"previous output"
    monkeypatch.setattr(speech.shutil, "which", lambda _name: "/synthetic/ffmpeg")
    monkeypatch.setattr(speech.subprocess, "run", lambda *_args, **_kw: subprocess.CompletedProcess([], 1, b"", b"conversion failed"))
    with pytest.raises(RuntimeError, match=r"FFmpeg|ffmpeg"):
        speech.render_speech_audio(source, output)
    assert output.read_bytes() == b"previous output"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["result.mp3", "source.md"]


def test_ffmpeg_timeout_terminates_child_and_preserves_output(tmp_path, monkeypatch):
    import sys

    speech, source, _calls = _fake_renderer(tmp_path, monkeypatch)
    executable = tmp_path / "synthetic-audio.py"
    finished = tmp_path / "finished"
    segment_path = tmp_path / "segment-path"
    executable.write_text(
        "import sys, time\n"
        "from pathlib import Path\n"
        "target = Path(sys.argv[-1])\n"
        f"Path({str(segment_path)!r}).write_text(str(target))\n"
        "target.write_bytes(b'partial synthetic audio')\n"
        "time.sleep(2)\n"
        f"Path({str(finished)!r}).write_text('child was not terminated')\n"
    )
    # Use the Python interpreter explicitly on every platform, including Windows.
    real_run, real_popen = speech.subprocess.run, speech.subprocess.Popen
    children = []

    def start_child(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def run_python_child(command, **kwargs):
        return real_run([sys.executable, str(executable), *command[1:]], **kwargs)

    monkeypatch.setattr(speech.subprocess, "Popen", start_child)
    monkeypatch.setattr(speech.subprocess, "run", run_python_child)
    monkeypatch.setattr(speech, "SUBPROCESS_TIMEOUT_SECONDS", .5)
    output = tmp_path / "result.mp3"
    output.write_bytes(b"previous complete audio")
    monkeypatch.setattr(speech.shutil, "which", lambda _name: str(executable))
    with pytest.raises(RuntimeError, match="FFmpeg timed out"):
        speech.render_speech_audio(source, output)
    assert output.read_bytes() == b"previous complete audio"
    assert not finished.exists(), "the timed-out child must not continue running"
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].returncode != 0, "the timed-out child is terminated and reaped"
    assert not Path(segment_path.read_text()).parent.exists(), "temporary partial audio is removed"
    assert not list(tmp_path.glob(".lixity-speech-*"))


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


@pytest.mark.parametrize("pronunciations", [{}, {"river": "quiet river"}])
def test_profile_render_preserves_complete_sentence_boundaries(tmp_path, monkeypatch, pronunciations):
    import lixity.speech as speech
    from lixity.speech_profiles import AudioProfile

    body = ("A calm synthetic sentence about the river and the bridge. " * 30).strip()
    source = tmp_path / "source.md"
    source.write_text(body)
    spoken = []

    def synthesize(text, _profile, **_kwargs):
        spoken.append(text)
        return speech.generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    profile = AudioProfile(engine="qwen3", voice="Ryan", language="en", pronunciations=pronunciations)
    output = speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile)
    expected = body.replace("river", "quiet river") if pronunciations else body
    assert len(spoken) > 1
    assert all(text.endswith(".") and len(text) <= 600 for text in spoken)
    assert " ".join(spoken) == expected
    assert source.read_text() == body
    with wave.open(str(output)) as audio:
        # Only the completed paragraph receives the default .45-second pause.
        assert audio.getnframes() == len(spoken) * 240 + 10800


def test_profile_render_splits_long_single_sentence_at_words(tmp_path, monkeypatch):
    import lixity.speech as speech
    from lixity.speech_profiles import AudioProfile

    body = " ".join(f"word{index}" for index in range(200)) + "."
    source = tmp_path / "source.md"
    source.write_text(body)
    spoken = []

    def synthesize(text, _profile, **_kwargs):
        spoken.append(text)
        return speech.generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    profile = AudioProfile(engine="qwen3", voice="Ryan", language="en")
    speech.render_speech_audio(source, tmp_path / "result.wav", profile=profile)
    assert len(spoken) > 1
    assert all(len(text) <= 600 for text in spoken)
    assert " ".join(spoken) == body


def test_qwen_profile_owns_language_voice_and_pronunciations(tmp_path, monkeypatch):
    from lixity.speech_profiles import AudioProfile

    speech, source, calls = _fake_renderer(tmp_path, monkeypatch)
    profile = AudioProfile(voice="Aiden", language="en", pronunciations={"passage": "reading"})
    speech.render_speech_audio(source, tmp_path / "result.wav", language="de", profile=profile)
    assert calls and all(selected == profile for _text, selected in calls)
    assert "reading" in " ".join(text for text, _profile in calls)
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


def test_cli_rejects_removed_speed_option_before_rendering(tmp_path):
    source = tmp_path / "synthetic.md"
    source.write_text("A synthetic listening passage.")
    with patch("lixity.speech.render_speech_audio") as render:
        with pytest.raises(SystemExit) as error:
            main(["read-aloud", str(source), "--speed", "1.2"])
        assert error.value.code == 2
        render.assert_not_called()
    assert source.read_text() == "A synthetic listening passage."


def test_audio_byte_limit_counts_structural_silence_and_preserves_output(tmp_path, monkeypatch):
    import pytest

    speech, source, calls = _fake_renderer(tmp_path, monkeypatch)
    output = tmp_path / "limited.wav"
    output.write_bytes(b"previous audio")
    # The first PCM chunk (240 bytes) fits; its one-second heading pause does not.
    with pytest.raises(ValueError, match="byte limit"):
        speech.render_speech_audio(source, output, max_audio_bytes=500)
    assert len(calls) == 1
    assert output.read_bytes() == b"previous audio"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["limited.wav", "source.md"]


def test_audio_byte_limit_rejects_invalid_bounds_before_loading(tmp_path):
    import pytest

    from lixity.speech import render_speech_audio

    for limit in (0, 43, -1, True, 100.5):
        with pytest.raises(ValueError, match="byte limit"):
            render_speech_audio(tmp_path / "missing.md", tmp_path / "out.wav", max_audio_bytes=limit)
