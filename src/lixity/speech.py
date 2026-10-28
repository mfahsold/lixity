"""Create local listening copies with stable delivery and structural pauses.

Statistical measurements and words in the manuscript do not establish an
actor's intention. Use one explicit profile throughout a render; headings,
sentences, paragraphs and scene breaks supply the pause structure. Qwen3-TTS
CustomVoice provides the selected preset throughout a render.
"""

from __future__ import annotations

import io
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unicodedata
import wave
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .markdown_parser import counting_inline_text, parse_markdown_blocks, split_chapters
from .sentences import split_sentences
from .speech_profiles import AudioProfile, resolve_audio_profile

if TYPE_CHECKING:
    from .speech_direction import SpeechSegment
    from .speech_references import SpeechReference

MAX_SEGMENT_CHARS = 600
# Conservative per-invocation bound; this does not interrupt in-process inference.
SUBPROCESS_TIMEOUT_SECONDS = 3600


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
    pause_after: float = 0.45
    join_before: str = " "
    anchor: dict[str, Any] | None = None



def _is_cjk(character: str) -> bool:
    return ("\u3040" <= character <= "\u30ff" or "\u3400" <= character <= "\u9fff" or
            "\uf900" <= character <= "\ufaff" or "\U00020000" <= character <= "\U000323af")


def _speech_segments(text: str, language: str = "en") -> list[str]:
    """Pack sentences within the transport bound, splitting long ones at words.

    This is transport segmentation, not linguistic word segmentation. Preserve
    CJK and mixed-script text exactly; Latin tokens still remain indivisible.
    """
    if not any(_is_cjk(character) for character in text):
        segments = []
        pending = ""
        for sentence in split_sentences(text, language):
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
        return segments
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
    language: str = "en",
    chapter_filter: int | str | None = None,
    skip_editorial_markers: bool = True,
    project_config: Mapping[str, Any] | None = None,
    *, segment: bool = True,
) -> list[AudioCue]:
    """Extract spoken text and structural pauses without inferring delivery."""
    from .pipeline import resolve_document_config
    config, _resolved = resolve_document_config(text, language, project_config=project_config)
    all_chapters = split_chapters(text, config) or [(1, "", text)]
    chapters = all_chapters
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

    from bisect import bisect_left
    from itertools import accumulate

    from .markdown_parser import _chapter_spans, _front_matter_end, chapter_heading_spans
    from .pipeline import document_paragraph_texts, paragraph_identity
    anchors = {(p.start_line, p.end_line): paragraph_identity(p)
               for p in document_paragraph_texts(text, config)}
    selected_numbers = {row[0] for row in chapters}
    heading_ends = {line: end for _start, end, line, _title in chapter_heading_spans(text, config)}
    original_lines = text.splitlines(keepends=True)
    line_offsets = [0, *accumulate(len(line) for line in original_lines)]
    content_begin = line_offsets[_front_matter_end(original_lines)]
    accepted = _chapter_spans(text, config)
    if not accepted:
        accepted = [(1, '', text, 1)]
    cues: list[AudioCue] = []
    for number, title, body, heading_line in accepted:
        if number not in selected_numbers:
            continue
        if title:
            cues.append(AudioCue(title, 'heading', number, pause_after=1.0))
        begin = heading_ends.get(heading_line)
        if begin is None:
            line_index = heading_line - 1
            if title and heading_ends:
                # The shared segmenter consumes the first physical preface line.
                while line_index < len(original_lines) and not original_lines[line_index].strip():
                    line_index += 1
                line_index += 1
            begin = sum(len(line) for line in original_lines[:line_index])
        begin = max(begin, content_begin)
        offset = next((position for position in line_offsets[bisect_left(line_offsets, begin):]
                       if text.startswith(body, position)), -1)
        if offset < 0:
            raise ValueError('Accepted speech chapter cannot be aligned with its source')
        line_offset = len(text[:offset].splitlines())
        blocks: list[dict[str, Any]] = []
        for block in parse_markdown_blocks(body, config, _front_matter=False):
            if block['type']=='quote_block':
                blocks.extend({'type':'p','text':value} for value in block['paras'])
            else:
                blocks.append(block)
        for block in blocks:
            kind = block.get('type','')
            content = (block.get('text') or '').strip()
            if kind in ('divider','thematic_break'):
                cues.append(AudioCue('', 'scene_break', number, pause_after=1.2))
                continue
            if kind.startswith('h'):
                content = counting_inline_text(content)
                if content and content != title:
                    cues.append(AudioCue(content, 'heading', number, pause_after=1.0))
                continue
            if kind not in ('p','quote','paragraph','list_item'):
                continue
            if skip_editorial_markers:
                content = re.sub(r'\[(TODO|PRÜFEN|ACHTUNG|SACHCHECK)[^\]]*\]', '', content,
                                 flags=re.IGNORECASE).strip()
            content = counting_inline_text(content)
            if not content:
                continue
            anchor = anchors.get((block.get('start_line',0)+line_offset, block.get('end_line',0)+line_offset)) if 'start_line' in block else None
            cjk = any(_is_cjk(character) for character in content)
            segments = _speech_segments(content, language) if segment else [content]
            cue_kind = 'dialogue' if content.startswith(('„','»','"','“',"'")) else 'narrative'
            for index, piece in enumerate(segments):
                cues.append(AudioCue(piece, cue_kind, number,
                    pause_after=.45 if index == len(segments)-1 else 0,
                    join_before='' if cjk else ' ', anchor=anchor))
    return cues


def generate_silence_wav(
    duration_seconds: float,
    sample_rate: int = 24000,
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


def _read_pcm(data: bytes, *, allow_empty: bool = False) -> tuple[tuple[int, int, int], bytes]:
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            params = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
            count = reader.getnframes()
            frames = reader.readframes(count)
            if (reader.getcomptype() != "NONE" or (not count and not allow_empty)
                    or len(frames) != count * params[0] * params[1]):
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


def _run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Bound each FFmpeg operation without exposing captured text on timeout."""
    try:
        return subprocess.run(  # noqa: S603 - resolved executable and explicit arguments
            command, capture_output=True, check=False, timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # run() kills and waits for the direct child before raising. The caller's
        # temporary-directory context removes partial audio without publishing it.
        raise RuntimeError("FFmpeg timed out while creating audio") from None


def render_speech_audio(
    manuscript_path: str | Path,
    output_path: str | Path,
    language: str = "en",
    chapter: int | str | None = None,
    skip_markers: bool = True,
    *,
    profile: AudioProfile | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    max_audio_bytes: int | None = None,
    cache_dir: str | Path | None = None,
    fresh_audio: bool = False,
    target: str = "local",
    plan: list[SpeechSegment] | None = None,
    references: Mapping[str, SpeechReference] | None = None,
) -> Path:
    """Stream a consistent selected delivery into an atomic WAV or MP3 copy."""
    _check_cancelled(cancelled)
    if max_audio_bytes is not None and (type(max_audio_bytes) is not int or max_audio_bytes < 44):
        raise ValueError("Audio byte limit must be an integer of at least 44")
    profile = (AudioProfile.model_validate(profile.model_dump()) if profile is not None
               else resolve_audio_profile(None, language=language))
    language = profile.language
    if target not in ("local", "jetson"):
        raise ValueError("Unknown Qwen execution target")
    source = Path(manuscript_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Manuscript file not found: {source}")
    if source == output:
        raise ValueError("Audio output must differ from the manuscript")
    if output.suffix.lower() not in (".wav", ".mp3"):
        raise ValueError("Audio output must use .wav or .mp3")
    rate = 24000
    from .speech_direction import build_speech_plan

    cues = plan if plan is not None else build_speech_plan(
        source.read_text(encoding="utf-8"), profile, chapter=chapter, skip_markers=skip_markers)
    if not any(cue.text for cue in cues):
        raise ValueError("No spoken text in the selected chapter")
    from .speech_references import validate_reference
    for reference_id in {cue.profile.reference_id for cue in cues
                         if cue.text and cue.profile.engine == "qwen3-base"}:
        reference = (references or {}).get(reference_id)
        if reference is None or reference.id != reference_id:
            raise ValueError("A verified reference is required for every Qwen Base profile")
        validate_reference(reference)
    needs_tempo = any(cue.text and cue.profile.speed != 1.0 for cue in cues)
    ffmpeg = shutil.which("ffmpeg") if output.suffix.lower() == ".mp3" or needs_tempo else None
    if not ffmpeg and needs_tempo:
        raise FileNotFoundError("FFmpeg is required for audio speed adjustment; install FFmpeg or set speed to 1.0")
    if not ffmpeg and output.suffix.lower() == ".mp3":
        raise FileNotFoundError("FFmpeg is required for MP3 output; choose WAV instead")
    segment_cache = None
    if cache_dir is not None:
        from .speech_cache import SpeechSegmentCache

        segment_cache = SpeechSegmentCache(Path(cache_dir))
    # One target serves one model variant. A mixed plan can still succeed if
    # all missing segments use the same variant and the rest are cached.
    if len({cue.profile.engine for cue in cues if cue.text}) > 1:
        missing_engines: set[str] = set()
        for cue in cues:
            _check_cancelled(cancelled)
            if not cue.text:
                continue
            cached = None if fresh_audio or segment_cache is None else segment_cache.get(cue.text, cue.profile)
            if cached is None:
                missing_engines.add(cue.profile.engine)
                if len(missing_engines) > 1:
                    raise ValueError("The audio plan needs multiple uncached model variants; one worker serves "
                                     "one model. Choose profiles using the same model or reuse previously "
                                     "cached segments")
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
                if cue.pause_before:
                    write_frames(bytes(int(rate * cue.pause_before) * 2))
                if not cue.text:
                    write_frames(bytes(int(rate * cue.pause_after) * 2))
                    continue
                effective = cue.profile
                from .speech_qwen import synthesize_qwen

                data = None if fresh_audio or segment_cache is None else segment_cache.get(cue.text, effective)
                if data is None:
                    data = (synthesize_qwen(cue.text, effective, target=target,
                                           reference=(references or {})[effective.reference_id])
                            if effective.engine == "qwen3-base" else
                            synthesize_qwen(cue.text, effective, target=target))
                    params, frames = _read_pcm(data)
                    if params != (1, 2, rate):
                        raise ValueError("Unexpected Qwen audio format")
                    _check_cancelled(cancelled)
                    if segment_cache is not None:
                        segment_cache.put(cue.text, effective, data)
                else:
                    params, frames = _read_pcm(data)
                _check_cancelled(cancelled)
                if effective.speed != 1.0:
                    # Cache the unmodified model audio. Processing each spoken
                    # segment leaves explicit pauses and per-profile rates intact.
                    tempo_source = Path(directory) / "tempo-source.wav"
                    tempo_output = Path(directory) / "tempo-output.wav"
                    tempo_source.write_bytes(data)
                    if ffmpeg is None:  # defensive: checked before synthesis
                        raise FileNotFoundError("FFmpeg is required for audio speed adjustment")
                    result = _run_ffmpeg([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(tempo_source),
                                          "-af", f"atempo={effective.speed}", "-ac", "1", "-ar", str(rate),
                                          "-c:a", "pcm_s16le", str(tempo_output)])
                    if result.returncode != 0 or not tempo_output.is_file():
                        raise RuntimeError("FFmpeg failed to adjust audio speed")
                    adjusted_params, adjusted_frames = _read_pcm(tempo_output.read_bytes(), allow_empty=True)
                    if adjusted_params != (1, 2, rate):
                        raise ValueError("Unexpected tempo-adjusted audio format")
                    # At very short durations atempo can produce no samples. In
                    # that case preserve the original rather than lose speech.
                    if adjusted_frames:
                        frames = adjusted_frames
                    elif len(frames) > rate * 2 // 10:
                        raise RuntimeError("FFmpeg produced empty tempo-adjusted audio")
                    _check_cancelled(cancelled)
                write_frames(frames)
                _check_cancelled(cancelled)
                done += 1
                if progress is not None:
                    progress(done, total)
                if cue.pause_after:
                    write_frames(bytes(int(rate * cue.pause_after) * 2))
        final = pcm
        if output.suffix.lower() == ".mp3":
            if ffmpeg is None:  # defensive: checked before synthesis
                raise FileNotFoundError("FFmpeg is required for MP3 output")
            final = Path(directory) / "reading.mp3"
            result = _run_ffmpeg(
                [ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(pcm),
                                     "-b:a", "192k", str(final)])
            if result.returncode != 0 or not final.is_file() or not final.stat().st_size:
                raise RuntimeError("FFmpeg failed to create MP3 audio")
        _check_cancelled(cancelled)
        os.replace(final, output)
    return output
