"""Synthesize manuscript audio using local TTS (Piper) enriched with Lixity stylometric cues.

Extracts manuscript structure, dialog segments, pacing, and chapter boundaries,
modulating speech parameters (tempo, pauses, speaker emotion) based on Lixity
paragraph analytics.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from .markdown_parser import parse_markdown_blocks, split_chapters
from .models import CorpusConfig
from .style_profile import ParagraphProfiler

DEFAULT_VOICE_DIR = Path.home() / ".cache" / "piper-voices"

DEFAULT_VOICES = {
    "de": "de_DE-thorsten_emotional-medium",
    "en": "en_US-lessac-medium",
}

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
    chapter_num: int = 0
    length_scale: float = 1.0  # speed: <1.0 = faster, >1.0 = slower
    sentence_silence: float = 0.2  # seconds of pause between sentences
    pause_after: float = 0.3  # silence after segment in seconds
    speaker_id: int | None = None


def extract_audio_cues(
    text: str,
    language: str = "de",
    chapter_filter: int | str | None = None,
    has_emotional_voice: bool = False,
    skip_editorial_markers: bool = True,
    base_speed: float = 1.0,
) -> list[AudioCue]:
    """Analyze manuscript blocks and generate prosody-enriched audio cues."""
    config = CorpusConfig(language=language)
    chapters = split_chapters(text, config)

    target_chapter: int | None = None
    if chapter_filter is not None:
        try:
            target_chapter = int(chapter_filter)
        except ValueError:
            target_str = str(chapter_filter).strip().lower()
            for ch_num, ch_title, _ in chapters:
                if target_str in ch_title.lower() or target_str == str(ch_num):
                    target_chapter = ch_num
                    break

    if chapters:
        target_chapters = [
            (num, title, body)
            for num, title, body in chapters
            if target_chapter is None or num == target_chapter
        ]
    else:
        target_chapters = [(1, "", text)]

    cues: list[AudioCue] = []
    speed_factor = 1.0 / max(0.2, min(3.0, base_speed))

    for ch_num, ch_title, ch_body in target_chapters:
        if ch_title:
            cues.append(
                AudioCue(
                    text=ch_title,
                    kind="heading",
                    chapter_num=ch_num,
                    length_scale=1.12 * speed_factor,
                    pause_after=1.2,
                    speaker_id=4 if has_emotional_voice else None,
                )
            )

        blocks = parse_markdown_blocks(ch_body)
        profiler = ParagraphProfiler(config)
        paragraphs, _ = profiler.profile_blocks(blocks)
        p_idx = 0

        for block in blocks:
            b_type = block.get("type", "")
            b_text = block.get("text", "") or ""

            if b_type.startswith("h"):
                clean_text = b_text.strip()
                if clean_text and clean_text != ch_title:
                    cues.append(
                        AudioCue(
                            text=clean_text,
                            kind="heading",
                            chapter_num=ch_num,
                            length_scale=1.12 * speed_factor,
                            pause_after=1.2,
                            speaker_id=4 if has_emotional_voice else None,
                        )
                    )
            elif b_type in ("divider", "thematic_break"):
                cues.append(
                    AudioCue(
                        text="",
                        kind="scene_break",
                        chapter_num=ch_num,
                        pause_after=1.6,
                    )
                )
            elif b_type in ("p", "quote", "paragraph"):
                raw_text = b_text.strip()
                if not raw_text:
                    continue

                metrics = paragraphs[p_idx] if p_idx < len(paragraphs) else None
                p_idx += 1

                if skip_editorial_markers:
                    raw_text = re.sub(
                        r"\[(TODO|PRÜFEN|ACHTUNG|SACHCHECK)[^\]]*\]", "", raw_text, flags=re.IGNORECASE
                    )
                    raw_text = raw_text.strip()
                    if not raw_text:
                        continue

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

                quoted_matches = re.findall(r"([„»\"\'“«][^„»\"\'“«\n]+[“«\"\'”])", raw_text)
                quoted_chars = sum(len(m) for m in quoted_matches)
                is_predominantly_dialogue = bool(
                    quoted_matches
                    and (
                        quoted_chars / max(1, len(raw_text)) >= 0.35
                        or raw_text.startswith(("„", "»", '"', "“", "'"))
                    )
                )

                speaker_id = (0 if is_predominantly_dialogue else 4) if has_emotional_voice else None

                cues.append(
                    AudioCue(
                        text=raw_text,
                        kind="dialogue" if is_predominantly_dialogue else "narrative",
                        chapter_num=ch_num,
                        length_scale=length_scale * speed_factor,
                        sentence_silence=sentence_silence,
                        pause_after=0.45,
                        speaker_id=speaker_id,
                    )
                )

    return cues


def generate_silence_wav(
    duration_seconds: float,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
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


def synthesize_cue_subprocess(
    cue: AudioCue, piper_bin: str, model_path: Path, config_path: Path
) -> bytes:
    """Invoke Piper via subprocess writing to a temporary file."""
    if not cue.text.strip():
        return b""

    with tempfile.NamedTemporaryFile("wb+", suffix=".wav", delete=False) as tmp_file:
        tmp_name = tmp_file.name

    try:
        cmd = [
            piper_bin,
            "-m", str(model_path),
            "-c", str(config_path),
            "--length-scale", str(round(cue.length_scale, 3)),
            "--sentence-silence", str(round(cue.sentence_silence, 3)),
            "-f", tmp_name,
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
            sys.stderr.write(f"Piper warning: {proc.stderr.decode('utf-8', errors='replace')}\n")
            return b""
        return Path(tmp_name).read_bytes()
    finally:
        tmp_p = Path(tmp_name)
        if tmp_p.exists():
            tmp_p.unlink()


def render_speech_audio(
    manuscript_path: str | Path,
    output_path: str | Path,
    voice_name: str | None = None,
    language: str = "de",
    chapter: int | str | None = None,
    base_speed: float = 1.0,
    skip_markers: bool = True,
    piper_bin: str | None = None,
) -> Path:
    """Synthesize full manuscript audio with Lixity-guided prosody."""
    src = Path(manuscript_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Manuscript file not found: {src}")

    out = Path(output_path).expanduser().resolve()
    text = src.read_text(encoding="utf-8")

    selected_voice = voice_name or DEFAULT_VOICES.get(language, DEFAULT_VOICES["de"])
    model_dir = DEFAULT_VOICE_DIR / selected_voice
    model_path = model_dir / f"{selected_voice}.onnx"
    config_path = model_dir / f"{selected_voice}.onnx.json"
    if not model_path.exists() or not config_path.exists():
        raise FileNotFoundError(
            f"Voice model '{selected_voice}' not found at {model_path}. "
            f"Download models into {DEFAULT_VOICE_DIR} from HuggingFace rhasspy/piper-voices."
        )

    has_emotional = "emotional" in selected_voice
    cues = extract_audio_cues(
        text,
        language=language,
        chapter_filter=chapter,
        has_emotional_voice=has_emotional,
        skip_editorial_markers=skip_markers,
        base_speed=base_speed,
    )

    if not cues:
        raise ValueError(f"No text segments found to synthesize for chapter filter: {chapter}")

    # Prefer direct in-process synthesis for speed if piper is importable
    piper_voice = None
    try:
        from piper.config import SynthesisConfig
        from piper.voice import PiperVoice
        piper_voice = PiperVoice.load(model_path)
    except (ImportError, RuntimeError, OSError):
        piper_voice = None

    piper_exe = None
    if piper_voice is None:
        piper_exe = piper_bin or shutil.which("piper") or str(Path(sys.executable).parent / "piper")
        if not piper_exe or not Path(piper_exe).exists():
            raise FileNotFoundError(
                f"Piper binary not found: {piper_exe}. Run: pip install piper-tts"
            )

    parts: list[bytes] = []
    for cue in cues:
        if cue.kind == "scene_break":
            parts.append(generate_silence_wav(cue.pause_after))
            continue

        if piper_voice is not None:
            syn_cfg = SynthesisConfig(
                speaker_id=cue.speaker_id,
                length_scale=cue.length_scale,
            )
            silence_bytes = bytes(
                int(piper_voice.config.sample_rate * cue.sentence_silence) * 2
            )
            c_buf = io.BytesIO()
            with wave.open(c_buf, "wb") as wf:
                wf.setframerate(piper_voice.config.sample_rate)
                wf.setsampwidth(2)
                wf.setnchannels(1)
                for i, chunk in enumerate(piper_voice.synthesize(cue.text, syn_cfg)):
                    if i > 0 and silence_bytes:
                        wf.writeframes(silence_bytes)
                    wf.writeframes(chunk.audio_int16_bytes)
            audio_bytes = c_buf.getvalue()
        elif piper_exe is not None:
            audio_bytes = synthesize_cue_subprocess(cue, piper_exe, model_path, config_path)
        else:
            audio_bytes = b""

        if audio_bytes:
            parts.append(audio_bytes)
            if cue.pause_after > 0:
                sample_rate = piper_voice.config.sample_rate if piper_voice is not None else 22050
                parts.append(generate_silence_wav(cue.pause_after, sample_rate=sample_rate))

    full_wav = concatenate_wavs(parts)
    out.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = shutil.which("ffmpeg")
    if out.suffix.lower() == ".mp3" and ffmpeg_bin:
        temp_wav = out.with_suffix(".tmp.wav")
        temp_wav.write_bytes(full_wav)
        subprocess.run(  # noqa: S603
            [ffmpeg_bin, "-y", "-i", str(temp_wav), "-b:a", "64k", str(out)],
            capture_output=True,
            check=False,
        )
        if temp_wav.exists():
            temp_wav.unlink()
    else:
        if out.suffix.lower() not in (".wav", ".mp3"):
            out = out.with_suffix(".wav")
        out.write_bytes(full_wav)

    return out
