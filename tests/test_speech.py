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
    assert dlg.speaker_id == 0  # Amused / dialogue speaker in emotional model

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
