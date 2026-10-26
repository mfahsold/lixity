"""Synthesize manuscript audio using local TTS (Piper) enriched with Lixity stylometric cues.

Extracts manuscript structure, dialog segments, pacing, and chapter boundaries,
modulating speech parameters (tempo, pauses, speaker emotion) based on Lixity
paragraph analytics.
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler

DEFAULT_VOICE_DIR = Path.home() / ".cache" / "piper-voices"

# Thorsten Emotional speaker mapping
# 0: amused, 1: angry, 2: disgusted, 3: drunk, 4: neutral, 5: sleepy, 6: surprised, 7: whisper
SPEAKER_EMOTIONS = {
    "amused": 0,
    "angry": 1,
    "disgusted": 2,
    "drunk": 3,
    "neutral": 4,
    "sleepy": 5,
    "surprised": 6,
    "whisper": 7,
}


@dataclass
class AudioCue:
    text: str
    kind: str  # "heading", "narrative", "dialogue", "scene_break"
    length_scale: float = 1.0  # speed: <1.0 = faster, >1.0 = slower
    sentence_silence: float = 0.2  # seconds of pause between sentences
    pause_after: float = 0.3  # silence after segment in seconds
    speaker_id: int | None = None


def extract_audio_cues(
    text: str,
    language: str = "de",
    has_emotional_voice: bool = False,
    skip_editorial_markers: bool = True,
) -> list[AudioCue]:
    """Analyze manuscript blocks and generate prosody-enriched audio cues."""
    blocks = parse_markdown_blocks(text)
    profiler = ParagraphProfiler(CorpusConfig(language=language))
    paragraphs, _chapters = profiler.profile_blocks(blocks)

    cues: list[AudioCue] = []
    p_idx = 0

    for block in blocks:
        b_type = block.get("type", "")
        b_text = block.get("text", "") or ""

        if b_type.startswith("h"):
            clean_text = b_text.strip()
            if clean_text:
                cues.append(
                    AudioCue(
                        text=clean_text,
                        kind="heading",
                        length_scale=1.12,  # slightly slower, authoritative
                        pause_after=1.2,  # noticeable pause after chapter title
                        speaker_id=4 if has_emotional_voice else None,
                    )
                )
        elif b_type in ("divider", "thematic_break"):
            # Scene break: empty text with a longer pause
            cues.append(
                AudioCue(
                    text="",
                    kind="scene_break",
                    pause_after=1.6,
                )
            )
        elif b_type in ("p", "quote", "paragraph"):
            raw_text = b_text.strip()
            if not raw_text:
                continue

            # Skip editorial notes or markers if requested
            if skip_editorial_markers:
                # remove [TODO: ...], [PRÜFEN: ...], etc.
                raw_text = re.sub(r"\[(TODO|PRÜFEN|ACHTUNG|SACHCHECK)[^\]]*\]", "", raw_text, flags=re.IGNORECASE)
                raw_text = raw_text.strip()
                if not raw_text:
                    continue

            # Retrieve profile metrics if available for this paragraph
            metrics = paragraphs[p_idx] if p_idx < len(paragraphs) else None
            p_idx += 1

            # Pacing modulation based on Lixity sentence metrics:
            # Baseline length_scale = 1.0
            # Shorter avg sentence length (< 12 words) indicates high action/tempo -> 0.94 (brisk)
            # Longer avg sentence length (> 24 words) indicates descriptive/reflective -> 1.08 (measured)
            length_scale = 1.0
            sentence_silence = 0.22
            if metrics and metrics.sentences:
                avg_sl = metrics.words / max(1, metrics.sentences)
                if avg_sl < 11:
                    length_scale = 0.93
                    sentence_silence = 0.15
                elif avg_sl > 22:
                    length_scale = 1.07
                    sentence_silence = 0.32

            # Check for dialogue vs narrative:
            # German/English dialogue quotes: „...“, »...«, "..."
            is_predominantly_dialogue = bool(
                re.search(r"^[„»\"\'].*[“«\"\']$", raw_text) or raw_text.count("„") >= 2 or raw_text.count("»") >= 2
            )

            speaker_id = (0 if is_predominantly_dialogue else 4) if has_emotional_voice else None

            cues.append(
                AudioCue(
                    text=raw_text,
                    kind="dialogue" if is_predominantly_dialogue else "narrative",
                    length_scale=length_scale,
                    sentence_silence=sentence_silence,
                    pause_after=0.45,
                    speaker_id=speaker_id,
                )
            )

    return cues


def generate_silence_wav(duration_seconds: float, sample_rate: int = 22050, channels: int = 1, sample_width: int = 2) -> bytes:
    """Generate pure PCM silence bytes as a WAV."""
    num_samples = int(sample_rate * duration_seconds)
    silence_frames = b"\x00" * (num_samples * channels * sample_width)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(silence_frames)
    return buf.getvalue()


def _safe_read_frames(wb: bytes) -> bytes:
    try:
        with wave.open(io.BytesIO(wb), "rb") as in_wf:
            return in_wf.readframes(in_wf.getnframes())
    except (wave.Error, OSError):
        return b""


def concatenate_wavs(wav_bytes_list: list[bytes]) -> bytes:
    """Concatenate multiple PCM WAV audio streams into a single clean WAV stream."""
    valid_wavs = [b for b in wav_bytes_list if len(b) > 44]
    if not valid_wavs:
        return b""
    if len(valid_wavs) == 1:
        return valid_wavs[0]

    with wave.open(io.BytesIO(valid_wavs[0]), "rb") as first_reader:
        nchannels = first_reader.getnchannels()
        sampwidth = first_reader.getsampwidth()
        framerate = first_reader.getframerate()

    output_buf = io.BytesIO()
    with wave.open(output_buf, "wb") as out_wf:
        out_wf.setnchannels(nchannels)
        out_wf.setsampwidth(sampwidth)
        out_wf.setframerate(framerate)
        for wb in valid_wavs:
            frames = _safe_read_frames(wb)
            if frames:
                out_wf.writeframes(frames)

    return output_buf.getvalue()


def synthesize_cue(cue: AudioCue, piper_bin: str, model_path: Path, config_path: Path) -> bytes:
    """Invoke Piper to synthesize a single cue to WAV bytes."""
    if not cue.text.strip():
        return b""

    cmd = [
        piper_bin,
        "-m", str(model_path),
        "-c", str(config_path),
        "--length-scale", str(cue.length_scale),
        "--sentence-silence", str(cue.sentence_silence),
        "-f", "-",  # output to stdout
    ]
    if cue.speaker_id is not None:
        cmd.extend(["-s", str(cue.speaker_id)])

    proc = subprocess.run(  # noqa: S603
        cmd,
        input=cue.text.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"Piper error: {proc.stderr.decode('utf-8', errors='replace')}\n")
        return b""
    return proc.stdout


def render_manuscript_audio(
    manuscript_path: str | Path,
    output_path: str | Path,
    voice_name: str = "de_DE-thorsten_emotional-medium",
    language: str = "de",
    piper_bin: str | None = None,
) -> Path:
    """Synthesize full manuscript audio with Lixity-guided prosody."""
    src = Path(manuscript_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    text = src.read_text(encoding="utf-8")

    piper_exe = piper_bin or shutil.which("piper") or str(Path(sys.executable).parent / "piper")
    if not piper_exe or not Path(piper_exe).exists():
        raise FileNotFoundError(f"Piper binary not found: {piper_exe}. Run: pip install piper-tts")

    model_dir = DEFAULT_VOICE_DIR / voice_name
    model_path = model_dir / f"{voice_name}.onnx"
    config_path = model_dir / f"{voice_name}.onnx.json"
    if not model_path.exists() or not config_path.exists():
        raise FileNotFoundError(f"Voice model not found at {model_path}. Download from HuggingFace piper-voices.")

    has_emotional = "emotional" in voice_name
    cues = extract_audio_cues(text, language=language, has_emotional_voice=has_emotional)

    parts: list[bytes] = []
    for cue in cues:
        if cue.kind == "scene_break":
            parts.append(generate_silence_wav(cue.pause_after))
            continue

        audio_bytes = synthesize_cue(cue, piper_exe, model_path, config_path)
        if audio_bytes:
            parts.append(audio_bytes)
            if cue.pause_after > 0:
                parts.append(generate_silence_wav(cue.pause_after))

    full_wav = concatenate_wavs(parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(full_wav)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Read manuscript aloud using Piper TTS with Lixity prosody.")
    parser.add_argument("manuscript", help="Path to input Markdown manuscript")
    parser.add_argument("-o", "--output", default="manuscript_audio.wav", help="Output WAV file path")
    parser.add_argument("--voice", default="de_DE-thorsten_emotional-medium", help="Voice model name in ~/.cache/piper-voices")
    parser.add_argument("--language", default="de", help="Manuscript language")
    args = parser.parse_args()

    out = render_manuscript_audio(args.manuscript, args.output, voice_name=args.voice, language=args.language)
    print(f"Generated manuscript audio: {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
