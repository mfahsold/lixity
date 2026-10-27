"""Create local listening copies with stable delivery and structural pauses.

Statistical measurements and words in the manuscript do not establish an
actor's intention. Use one explicit profile throughout a render; headings,
sentences, paragraphs and scene breaks supply the pause structure. Without a
profile, the existing neutral Piper delivery and explicit user speed apply.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unicodedata
import wave
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .markdown_parser import counting_inline_text, parse_markdown_blocks, split_chapters
from .models import CorpusConfig
from .sentences import split_sentences
from .speech_profiles import AudioProfile

DEFAULT_VOICE_DIR = Path.home() / ".cache" / "piper-voices"
DEFAULT_VOICES = {"de": "de_DE-thorsten-medium", "en": "en_US-lessac-medium"}
MAX_SEGMENT_CHARS = 600


class SpeechCancelled(RuntimeError):
    """The caller cancelled a render before publication."""


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise SpeechCancelled("Speech rendering was cancelled")


@dataclass
class AudioCue:
    text: str
    kind: str
    chapter_num: int = 0
    length_scale: float = 1.0
    sentence_silence: float = 0.15
    pause_after: float = 0.45
    speaker_id: int | None = None
    noise_scale: float | None = None
    noise_w_scale: float | None = None
    join_before: str = " "



def _is_cjk(character: str) -> bool:
    return ("\u3040" <= character <= "\u30ff" or "\u3400" <= character <= "\u9fff" or
            "\uf900" <= character <= "\ufaff" or "\U00020000" <= character <= "\U000323af")


def _speech_segments(text: str) -> list[str]:
    """Bound synthesis input at whitespace or Han/kana character boundaries.

    This is transport segmentation, not linguistic word segmentation. Preserve
    CJK and mixed-script text exactly; Latin tokens still remain indivisible.
    """
    if not any(_is_cjk(character) for character in text):
        pieces = textwrap.wrap(text, MAX_SEGMENT_CHARS, break_long_words=False, break_on_hyphens=False)
        if any(len(piece) > MAX_SEGMENT_CHARS for piece in pieces):
            raise ValueError("A word exceeds the speech segment limit; its spelling was not changed")
        return pieces
    pieces = []
    while len(text) > MAX_SEGMENT_CHARS:
        boundaries = []
        sentences = []
        for index in range(1, MAX_SEGMENT_CHARS + 1):
            previous, following = text[index - 1], text[index]
            if unicodedata.category(following).startswith("M") or following in ("\u200d", "\ufe0f"):
                continue
            if previous in "。\uff01\uff1f":
                sentences.append(index)
            if previous.isspace() or following.isspace() or _is_cjk(previous) or _is_cjk(following):
                boundaries.append(index)
        candidates = sentences or boundaries
        if not candidates:
            raise ValueError("A word exceeds the speech segment limit; its spelling was not changed")
        end = candidates[-1]
        pieces.append(text[:end])
        text = text[end:]
    if text:
        pieces.append(text)
    return pieces

def extract_audio_cues(
    text: str,
    language: str = "de",
    chapter_filter: int | str | None = None,
    has_emotional_voice: bool = False,
    skip_editorial_markers: bool = True,
    base_speed: float = 1.0,
) -> list[AudioCue]:
    """Keep delivery constant; the renderer resolves the model's neutral ID.

    ``has_emotional_voice`` retains the existing Thorsten cue API. It selects
    its neutral ID, never emotion inferred from the text or chapter title.
    """
    if not math.isfinite(base_speed) or not 0.2 <= base_speed <= 3.0:
        raise ValueError("Reading speed must be finite and between 0.2 and 3.0")
    config = CorpusConfig(language=language)
    chapters = split_chapters(text, config) or [(1, "", text)]
    if chapter_filter is not None:
        try:
            chapter_number = int(chapter_filter)
        except ValueError:
            matches = [item for item in chapters if str(chapter_filter).strip().lower() in item[1].lower()]
        else:
            matches = [item for item in chapters if item[0] == chapter_number]
        if len(matches) != 1 or str(chapter_filter).strip() == "":
            raise ValueError("Chapter selection must identify one existing chapter")
        chapters = matches

    cues: list[AudioCue] = []
    for number, title, body in chapters:
        if title:
            cues.append(AudioCue(title, "heading", number, 1 / base_speed,
                                 pause_after=1.0, speaker_id=4 if has_emotional_voice else None))
        blocks: list[dict[str, Any]] = []
        for block in parse_markdown_blocks(body, config):
            if block["type"] == "quote_block":
                blocks.extend({"type": "p", "text": value} for value in block["paras"])
            else:
                blocks.append(block)
        for block in blocks:
            kind = block.get("type", "")
            content = (block.get("text") or "").strip()
            if kind in ("divider", "thematic_break"):
                cues.append(AudioCue("", "scene_break", number, pause_after=1.2))
                continue
            if kind.startswith("h"):
                content = counting_inline_text(content)
                if content and content != title:
                    cues.append(AudioCue(content, "heading", number, 1 / base_speed,
                                         pause_after=1.0, speaker_id=4 if has_emotional_voice else None))
                continue
            if kind not in ("p", "quote", "paragraph", "list_item"):
                continue
            if skip_editorial_markers:
                content = re.sub(r"\[(TODO|PRÜFEN|ACHTUNG|SACHCHECK)[^\]]*\]", "", content,
                                 flags=re.IGNORECASE).strip()
            content = counting_inline_text(content)
            if not content:
                continue
            # Bound model inputs at sentence/word boundaries without dropping
            # prose. Intermediate fragments do not acquire paragraph pauses.
            cjk = any(_is_cjk(character) for character in content)
            if cjk:
                segments = _speech_segments(content)
            else:
                segments = []
                pending = ""
                for sentence in split_sentences(content, language):
                    for piece in textwrap.wrap(sentence, MAX_SEGMENT_CHARS, break_long_words=False,
                                              break_on_hyphens=False):
                        if len(piece) > MAX_SEGMENT_CHARS:
                            raise ValueError("A word exceeds the speech segment limit; its spelling was not changed")
                        if pending and len(pending) + len(piece) + 1 > MAX_SEGMENT_CHARS:
                            segments.append(pending)
                            pending = ""
                        pending = (pending + " " + piece).strip()
                if pending:
                    segments.append(pending)
            cue_kind = "dialogue" if content.startswith(("„", "»", '"', "“", "'")) else "narrative"
            speaker_id = 4 if has_emotional_voice else None
            for index, segment in enumerate(segments):
                cues.append(AudioCue(segment, cue_kind, number, 1 / base_speed,
                                     pause_after=.45 if index == len(segments) - 1 else 0,
                                     speaker_id=speaker_id, join_before="" if cjk else " "))
    return cues


def generate_silence_wav(
    duration_seconds: float,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Generate PCM silence with whole sample frames."""
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        raise ValueError("Silence duration must be finite and positive")
    frames = bytes(int(sample_rate * duration_seconds) * channels * sample_width)
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((channels, sample_width, sample_rate, 0, "NONE", "not compressed"))
        writer.writeframes(frames)
    return output.getvalue()


def _read_pcm(data: bytes) -> tuple[tuple[int, int, int], bytes]:
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            params = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
            count = reader.getnframes()
            frames = reader.readframes(count)
            if reader.getcomptype() != "NONE" or not count or len(frames) != count * params[0] * params[1]:
                raise ValueError("Missing or truncated PCM audio segment")
            return params, frames
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Invalid WAV audio segment") from exc


def concatenate_wavs(wav_bytes_list: list[bytes]) -> bytes:
    """Join complete PCM streams; never reinterpret a mismatched sample format."""
    if not wav_bytes_list:
        raise ValueError("No audio segments to concatenate")
    output = io.BytesIO()
    expected, _frames = _read_pcm(wav_bytes_list[0])
    with wave.open(output, "wb") as writer:
        writer.setparams((*expected, 0, "NONE", "not compressed"))
        for data in wav_bytes_list:
            params, frames = _read_pcm(data)
            if params != expected:
                raise ValueError("Incompatible PCM audio format")
            writer.writeframes(frames)
    return output.getvalue()


def synthesize_cue_subprocess(
    cue: AudioCue, piper_bin: str, model_path: Path, config_path: Path
) -> bytes:
    """Invoke Piper; a failed or empty segment aborts the export."""
    with tempfile.TemporaryDirectory(prefix="lixity-piper-") as directory:
        target = Path(directory) / "segment.wav"
        command = [piper_bin, "-m", str(model_path), "-c", str(config_path),
                   "--length-scale", str(cue.length_scale),
                   "--sentence-silence", str(cue.sentence_silence), "-f", str(target)]
        if cue.speaker_id is not None:
            command.extend(["-s", str(cue.speaker_id)])
        for option, value in (("--noise-scale", cue.noise_scale), ("--noise-w", cue.noise_w_scale)):
            if value is not None:
                command.extend([option, str(value)])
        result = subprocess.run(command, input=cue.text.encode("utf-8"), capture_output=True, check=False)  # noqa: S603
        if result.returncode != 0 or not target.is_file():
            raise RuntimeError("Piper failed to synthesize an audio segment")
        data = target.read_bytes()
        _read_pcm(data)
        return data


def render_speech_audio(
    manuscript_path: str | Path,
    output_path: str | Path,
    voice_name: str | None = None,
    language: str = "de",
    chapter: int | str | None = None,
    base_speed: float = 1.0,
    skip_markers: bool = True,
    piper_bin: str | None = None,
    *,
    profile: AudioProfile | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    max_audio_bytes: int | None = None,
    cache_dir: str | Path | None = None,
    fresh_audio: bool = False,
    target: str = "local",
) -> Path:
    """Stream a consistent selected delivery into an atomic WAV or MP3 copy."""
    _check_cancelled(cancelled)
    if max_audio_bytes is not None and (type(max_audio_bytes) is not int or max_audio_bytes < 44):
        raise ValueError("Audio byte limit must be an integer of at least 44")
    if profile is not None:
        profile = AudioProfile.model_validate(profile.model_dump())
        language, voice_name, base_speed = profile.language, profile.voice, profile.speed
    qwen = profile is not None and profile.engine == "qwen3"
    if target not in ("local", "jetson") or (not qwen and target != "local"):
        raise ValueError("Execution target is not supported by this speech engine")
    source = Path(manuscript_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Manuscript file not found: {source}")
    if source == output:
        raise ValueError("Audio output must differ from the manuscript")
    if output.suffix.lower() not in (".wav", ".mp3"):
        raise ValueError("Audio output must use .wav or .mp3")
    ffmpeg = shutil.which("ffmpeg") if output.suffix.lower() == ".mp3" else None
    if output.suffix.lower() == ".mp3" and not ffmpeg:
        raise FileNotFoundError("FFmpeg is required for MP3 output; choose WAV instead")
    rate, speaker, selected = 24000, None, None
    model, configuration = Path(), Path()
    if not qwen:
        selected = voice_name or DEFAULT_VOICES.get(language)
        if not selected or not re.fullmatch(r"[\w.-]+", selected) or selected in (".", ".."):
            raise ValueError("Choose a cached voice model for the requested language")
        model = DEFAULT_VOICE_DIR / selected / f"{selected}.onnx"
        configuration = model.with_suffix(".onnx.json")
        if not model.is_file() or not configuration.is_file():
            raise FileNotFoundError(f"Voice model and configuration required at {model}")
        try:
            settings = json.loads(configuration.read_text(encoding="utf-8"))
            rate = settings["audio"]["sample_rate"]
            speakers = settings.get("num_speakers", 1)
            speaker = settings.get("speaker_id_map", {}).get("neutral", settings.get("default_speaker_id", 0)) if speakers > 1 else None
            if not isinstance(rate, int) or rate <= 0 or (speaker is not None and
                    (not isinstance(speaker, int) or not 0 <= speaker < speakers)):
                raise ValueError("Invalid voice sample rate or speaker mapping")
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid Piper voice configuration") from exc
    cues = extract_audio_cues(source.read_text(encoding="utf-8"), language, chapter,
                              has_emotional_voice="emotional" in (selected or ""),
                              skip_editorial_markers=skip_markers, base_speed=base_speed)
    if profile is not None:
        planned: list[AudioCue] = []
        # Recover whole paragraph text before replacing phrases, including
        # phrases that straddle the initial transport segment boundary.
        paragraphs: list[AudioCue] = []
        for cue in cues:
            if (paragraphs and paragraphs[-1].text and cue.text and
                    paragraphs[-1].kind == cue.kind and paragraphs[-1].chapter_num == cue.chapter_num and
                    paragraphs[-1].pause_after == 0):
                previous = paragraphs[-1]
                paragraphs[-1] = replace(previous, text=previous.text + cue.join_before + cue.text, pause_after=cue.pause_after)
            else:
                paragraphs.append(cue)
        replacements = profile.pronunciations
        pattern = re.compile("|".join(re.escape(key) for key in sorted(replacements, key=len, reverse=True))) if replacements else None
        for cue in paragraphs:
            if cue.kind == "scene_break":
                cue.pause_after = profile.scene_pause
            elif cue.kind != "heading" and cue.pause_after:
                cue.pause_after = profile.paragraph_pause
            if pattern is not None:
                cue.text = pattern.sub(lambda match: replacements[match[0]], cue.text)
            pieces = _speech_segments(cue.text) or [""]
            planned.extend(replace(cue, text=piece, pause_after=cue.pause_after if index == len(pieces) - 1 else 0)
                           for index, piece in enumerate(pieces))
        cues = planned
    if not any(cue.text for cue in cues):
        raise ValueError("No spoken text in the selected chapter")
    segment_cache = None
    if qwen and cache_dir is not None:
        from .speech_cache import SpeechSegmentCache

        segment_cache = SpeechSegmentCache(Path(cache_dir))
    voice = None
    if not qwen and piper_bin is None:
        try:
            from piper.config import SynthesisConfig
            from piper.voice import PiperVoice
        except ImportError:
            pass
        else:
            voice = PiperVoice.load(model, config_path=configuration)
    executable = piper_bin or shutil.which("piper") or str(Path(sys.executable).parent / "piper")
    if not qwen and voice is None and not Path(executable).is_file():
        raise FileNotFoundError("Piper is required; install piper-tts in the Python environment")
    total = sum(bool(cue.text) for cue in cues)
    done = 0
    if progress is not None:
        progress(done, total)
    _check_cancelled(cancelled)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Streaming limits memory to one bounded segment. Temporary files live on
    # the output filesystem so replace is atomic and old copies survive errors.
    with tempfile.TemporaryDirectory(prefix=".lixity-speech-", dir=output.parent) as directory:
        pcm = Path(directory) / "reading.wav"
        with wave.open(str(pcm), "wb") as writer:
            writer.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            written = 44

            def write_frames(frames: bytes) -> None:
                nonlocal written
                if max_audio_bytes is not None and written + len(frames) > max_audio_bytes:
                    raise ValueError("Audio output exceeds the configured byte limit")
                writer.writeframes(frames)
                written += len(frames)

            for cue in cues:
                _check_cancelled(cancelled)
                if cue.speaker_id is None:
                    cue.speaker_id = speaker
                if cue.kind == "scene_break":
                    write_frames(bytes(int(rate * cue.pause_after) * 2))
                    continue
                if qwen and profile is not None:
                    from .speech_qwen import synthesize_qwen

                    data = None if fresh_audio or segment_cache is None else segment_cache.get(cue.text, profile)
                    if data is None:
                        data = synthesize_qwen(cue.text, profile, target=target)
                        params, frames = _read_pcm(data)
                        if params != (1, 2, rate):
                            raise ValueError("Unexpected Qwen audio format")
                        _check_cancelled(cancelled)
                        if segment_cache is not None:
                            segment_cache.put(cue.text, profile, data)
                    else:
                        params, frames = _read_pcm(data)
                    _check_cancelled(cancelled)
                    write_frames(frames)
                elif voice is not None:
                    synthesis = SynthesisConfig(speaker_id=cue.speaker_id if cue.speaker_id is not None else speaker,
                                                length_scale=cue.length_scale,
                                                noise_scale=cue.noise_scale, noise_w_scale=cue.noise_w_scale)
                    count = 0
                    for chunk in voice.synthesize(cue.text, synthesis):
                        _check_cancelled(cancelled)
                        if (chunk.sample_channels, chunk.sample_width, chunk.sample_rate) != (1, 2, rate):
                            raise ValueError("Unexpected Piper audio format")
                        frames = chunk.audio_int16_bytes
                        if not frames or len(frames) % 2:
                            raise ValueError("Empty or incomplete Piper audio segment")
                        if count:
                            write_frames(bytes(int(rate * cue.sentence_silence) * 2))
                        write_frames(frames)
                        count += 1
                    if not count:
                        raise ValueError("Piper returned no audio for a spoken segment")
                else:
                    params, frames = _read_pcm(synthesize_cue_subprocess(cue, executable, model, configuration))
                    if params != (1, 2, rate):
                        raise ValueError("Unexpected Piper audio format")
                    write_frames(frames)
                _check_cancelled(cancelled)
                done += 1
                if progress is not None:
                    progress(done, total)
                if cue.pause_after:
                    write_frames(bytes(int(rate * cue.pause_after) * 2))
        final = pcm
        if ffmpeg:
            final = Path(directory) / "reading.mp3"
            result = subprocess.run(  # noqa: S603 - resolved executable, explicit argument list
                [ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(pcm),
                                     "-b:a", "192k", str(final)], capture_output=True, check=False)
            if result.returncode != 0 or not final.is_file() or not final.stat().st_size:
                raise RuntimeError("FFmpeg failed to create MP3 audio")
        _check_cancelled(cancelled)
        os.replace(final, output)
    return output
