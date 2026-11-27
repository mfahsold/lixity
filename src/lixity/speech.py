"""Create listening copies through explicit providers with structural pauses.

Statistical measurements and words in the manuscript do not establish an
actor's intention. Use one explicit profile throughout a render; headings,
sentences, paragraphs and scene breaks supply the pause structure. Native
workers and configured external providers share the same output pipeline.
"""

from __future__ import annotations

import functools
import io
import logging
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import textwrap
import time
import unicodedata
import wave
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

from .audio_pcm import SPEECH_PCM_FORMAT, read_pcm_wav
from .log import get_logger, log_event, speech_diagnostic_scope
from .markdown_parser import counting_inline_text, parse_markdown_blocks, split_chapters
from .sentences import split_sentences
from .speech_leveling import level_speech_pcm
from .speech_profiles import (
    EXTERNAL_ENGINES,
    MAX_PLAYBACK_SPEED,
    MIN_PLAYBACK_SPEED,
    QWEN_LANGUAGES,
    QWEN_VOICES,
    AudioProfile,
    resolve_audio_profile,
)

if TYPE_CHECKING:
    from .speech_direction import SpeechSegment
    from .speech_references import SpeechReference

MAX_SEGMENT_CHARS = 600
_EDGE_FADE_MS = 5
# Conservative per-invocation bound; this does not interrupt in-process inference.
SUBPROCESS_TIMEOUT_SECONDS = 3600


class SpeechCancelled(RuntimeError):
    """The caller cancelled a render before publication."""


class SpeechBackendTimeout(RuntimeError):
    """A synthesis worker or a conversion process exceeded its deadline."""


_P = ParamSpec("_P")
_R = TypeVar("_R")


def _speech_error_kind(error: BaseException) -> str:
    # Exception text and untrusted class names can contain private input.
    if isinstance(error, SpeechCancelled):
        return "cancelled"
    if isinstance(error, KeyboardInterrupt):
        return "interrupted"
    if isinstance(error, (TimeoutError, SpeechBackendTimeout)):
        return "timeout"
    if isinstance(error, FileNotFoundError):
        return "missing"
    if isinstance(error, ValueError):
        return "validation"
    if isinstance(error, OSError):
        return "io"
    if isinstance(error, RuntimeError):
        return "runtime"
    return "other"


def _changed_value(previous: str | None, current: str) -> bool | str:
    if previous is None:
        return "first"
    return previous != current


def _observe_speech_render(func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Report bounded diagnostics even when preflight or cancellation fails."""
    @functools.wraps(func)
    def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with speech_diagnostic_scope():
            logger = get_logger("speech")
            started = time.monotonic()
            log_event(logger, "render_start")
            status, error_kind = "success", "none"
            try:
                return func(*args, **kwargs)
            except BaseException as error:
                error_kind = _speech_error_kind(error)
                status = "cancelled" if error_kind in ("cancelled", "interrupted") else "error"
                raise
            finally:
                log_event(logger, "render_end", status=status, error=error_kind,
                          duration_ms=max(0, round((time.monotonic() - started) * 1000)))
    return wrapped


@contextmanager
def _observe_speech_segment(index: int, total: int, profile: AudioProfile,
                            pcm_start_ms: int, instruction_changed: bool | str,
                            description_changed: bool | str, reference_changed: bool | str) -> Iterator[dict[str, Any]]:
    """Track timings and selected controls without recording text or paths."""
    logger = get_logger("speech")
    from .speech_engines import NATIVE_ENGINES

    engine = profile.engine if profile.engine in NATIVE_ENGINES or profile.engine in EXTERNAL_ENGINES else "unknown"
    voice = profile.voice if profile.voice in (*QWEN_VOICES, "design", "reference", "thorsten") else "unknown"
    language = profile.language if profile.language in QWEN_LANGUAGES else "unknown"
    speed = (profile.speed if type(profile.speed) in (int, float) and math.isfinite(profile.speed)
             and MIN_PLAYBACK_SPEED <= profile.speed <= MAX_PLAYBACK_SPEED else None)
    log_event(logger, "segment_start", logging.DEBUG, index=index, total=total, requested_engine=engine,
              voice=voice, language=language, tempo=speed if speed is not None else "unknown",
              has_instruction=bool(profile.instructions), instruction_changed=instruction_changed,
              description_changed=description_changed, reference_changed=reference_changed, pcm_start_ms=pcm_start_ms)
    state: dict[str, Any] = {"cache": "unknown", "pcm_end_ms": None}
    started = time.monotonic()
    status, error_kind = "success", "none"
    try:
        yield state
    except BaseException as error:
        error_kind = _speech_error_kind(error)
        status = "cancelled" if error_kind in ("cancelled", "interrupted") else "error"
        raise
    finally:
        log_event(logger, "segment_end", logging.DEBUG, index=index, total=total, status=status,
                  error=error_kind, cache=state["cache"], pcm_start_ms=pcm_start_ms,
                  pcm_end_ms=state["pcm_end_ms"] if state["pcm_end_ms"] is not None else "unknown",
                  **{key: state[key] for key in ("level_active_rms_dbfs", "level_gain_db", "level_sample_peak_dbfs")
                     if key in state},
                  duration_ms=max(0, round((time.monotonic() - started) * 1000)))


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


def _speech_segments(text: str, language: str = "en", *, maximum: int = MAX_SEGMENT_CHARS) -> list[str]:
    """Pack sentences within an explicit fragment bound, splitting at words.

    This is transport segmentation, not linguistic word segmentation. Preserve
    CJK and mixed-script text exactly; Latin tokens still remain indivisible.
    """
    if not any(_is_cjk(character) for character in text):
        segments = []
        pending = ""
        for sentence in split_sentences(text, language):
            for piece in textwrap.wrap(sentence, maximum, break_long_words=False,
                                       break_on_hyphens=False):
                if len(piece) > maximum:
                    raise ValueError("A word exceeds the speech segment limit; its spelling was not changed")
                if pending and len(pending) + len(piece) + 1 > maximum:
                    segments.append(pending)
                    pending = ""
                pending = (pending + " " + piece).strip()
        if pending:
            segments.append(pending)
        return segments
    pieces = []
    while len(text) > maximum:
        boundaries = []
        sentences = []
        for index in range(1, maximum + 1):
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
    sample_rate: int = SPEECH_PCM_FORMAT[2],
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


def _fade_pcm_edges(frames: bytes, rate: int, *, fade_in: bool, fade_out: bool) -> bytes:
    """Fade adjoining mono PCM16 edges without shifting any sample."""
    width = min(rate * _EDGE_FADE_MS // 1000, len(frames) // 4)
    if width < 2 or not (fade_in or fade_out):
        return frames
    filtered = bytearray(frames)
    for index in range(width - 1):
        gain = (1 - math.cos(math.pi * index / (width - 1))) / 2
        if fade_in:
            offset = 2 * index
            sample, = struct.unpack_from("<h", frames, offset)
            struct.pack_into("<h", filtered, offset, round(sample * gain))
        if fade_out:
            offset = len(frames) - 2 * (index + 1)
            sample, = struct.unpack_from("<h", frames, offset)
            struct.pack_into("<h", filtered, offset, round(sample * gain))
    return bytes(filtered)


def concatenate_wavs(wav_bytes_list: list[bytes]) -> bytes:
    """Join complete PCM streams; never reinterpret a mismatched sample format."""
    if not wav_bytes_list:
        raise ValueError("No audio segments to concatenate")
    output = io.BytesIO()
    chunks = iter(wav_bytes_list)
    expected, first_frames = read_pcm_wav(next(chunks))
    with wave.open(output, "wb") as writer:
        writer.setparams((*expected, 0, "NONE", "not compressed"))
        writer.writeframes(first_frames)
        for data in chunks:
            params, frames = read_pcm_wav(data)
            if params != expected:
                raise ValueError("Incompatible PCM audio format")
            writer.writeframes(frames)
    return output.getvalue()


def _ffmpeg_env() -> dict[str, str]:
    """Pass only minimal execution variables to FFmpeg, never ambient secrets."""
    from .io import sanitized_subprocess_env

    return sanitized_subprocess_env(overrides={"LC_ALL": "C"})


def _run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Bound each FFmpeg operation without exposing captured text or secrets."""
    try:
        return subprocess.run(  # noqa: S603 - resolved executable and explicit arguments
            command, capture_output=True, check=False, timeout=SUBPROCESS_TIMEOUT_SECONDS,
            env=_ffmpeg_env(),
        )
    except subprocess.TimeoutExpired:
        # run() kills and waits for the direct child before raising. The caller's
        # temporary-directory context removes partial audio without publishing it.
        raise SpeechBackendTimeout("FFmpeg timed out while creating audio") from None


def _adjust_pcm_tempo(data: bytes, frames: bytes, *, directory: Path, ffmpeg: str,
                      speed: float) -> bytes:
    """Convert one segment without reusing output from an earlier conversion."""
    source = directory / "tempo-source.wav"
    output = directory / "tempo-output.wav"
    source.write_bytes(data)
    output.unlink(missing_ok=True)
    channels, width, rate = SPEECH_PCM_FORMAT
    result = _run_ffmpeg([ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(source),
                          "-af", f"atempo={speed}", "-ac", str(channels), "-ar", str(rate),
                          "-c:a", "pcm_s16le", str(output)])
    if result.returncode or not output.is_file():
        raise RuntimeError("FFmpeg failed to adjust audio speed")
    params, adjusted = read_pcm_wav(output.read_bytes(), allow_empty=True)
    if params != SPEECH_PCM_FORMAT:
        raise ValueError("Unexpected tempo-adjusted audio format")
    if adjusted:
        return adjusted
    # At very short durations atempo can produce no samples. Preserve the
    # original in that case, while surfacing unexpectedly empty longer output.
    if len(frames) > rate * channels * width // 10:
        raise RuntimeError("FFmpeg produced empty tempo-adjusted audio")
    return frames


def _synthesize_segment(
    text: str,
    profile: AudioProfile,
    *,
    target: str,
    references: Mapping[str, SpeechReference] | None,
) -> bytes:
    """Dispatch one uncached segment to its configured synthesis adapter."""
    from .speech_profiles import profile_uses_reference

    reference = (references or {}).get(profile.reference_id) if profile_uses_reference(profile) else None
    if profile.engine in EXTERNAL_ENGINES:
        from .speech_providers import synthesize_external

        return synthesize_external(text, profile, reference=reference)
    if profile.engine == "f5-tts":
        from .speech_f5 import synthesize_f5

        return synthesize_f5(text, profile, target=target, reference=reference)
    if profile.engine == "ims-toucan":
        from .speech_toucan import synthesize_toucan

        return synthesize_toucan(text, profile, target=target, reference=reference)
    from .speech_qwen import synthesize_qwen

    return synthesize_qwen(text, profile, target=target, reference=reference)


@_observe_speech_render
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
    if target not in ("local", "jetson"):
        raise ValueError("Unknown speech execution target")
    source = Path(manuscript_path).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Manuscript file not found: {source}")
    if source == output:
        raise ValueError("Audio output must differ from the manuscript")
    if output.suffix.lower() not in (".wav", ".mp3"):
        raise ValueError("Audio output must use .wav or .mp3")
    channels, width, rate = SPEECH_PCM_FORMAT
    frame_bytes = channels * width
    from .speech_direction import build_speech_plan, require_render_direction

    cues = plan if plan is not None else build_speech_plan(
        source.read_text(encoding="utf-8"), profile, chapter=chapter, skip_markers=skip_markers)
    if not any(cue.text for cue in cues):
        raise ValueError("No spoken text in the selected chapter")
    for cue in cues:
        AudioProfile.model_validate(cue.profile.model_dump())
    from .speech_engines import NATIVE_ENGINES, native_endpoint
    from .speech_profiles import mlx_audio_uses_model_speed, profile_uses_reference

    native_bindings: dict[str, str] = {}
    for cue in cues:
        if not cue.text:
            continue
        engine = cue.profile.engine
        if engine not in EXTERNAL_ENGINES and engine not in native_bindings:
            native_bindings[engine] = native_endpoint(engine, target)
        require_render_direction(cue.profile, cue.profile.instructions)
    if target != "local" and any(cue.text and cue.profile.engine in EXTERNAL_ENGINES for cue in cues):
        raise ValueError("External speech uses its configured provider URL, not the Jetson execution target")
    from .speech_references import validate_reference
    for reference_id in {cue.profile.reference_id for cue in cues if cue.text and profile_uses_reference(cue.profile)}:
        reference = (references or {}).get(reference_id)
        if reference is None or reference.id != reference_id:
            raise ValueError("A verified reference is required for every reference voice profile")
        validate_reference(reference)

    needs_tempo = any(cue.text and cue.profile.speed != 1.0
                      and not mlx_audio_uses_model_speed(cue.profile) for cue in cues)
    ffmpeg = shutil.which("ffmpeg") if output.suffix.lower() == ".mp3" or needs_tempo else None
    if not ffmpeg and needs_tempo:
        raise FileNotFoundError("FFmpeg is required for audio speed adjustment; install FFmpeg or set speed to 1.0")
    if not ffmpeg and output.suffix.lower() == ".mp3":
        raise FileNotFoundError("FFmpeg is required for MP3 output; choose WAV instead")
    segment_cache = None
    if cache_dir is not None:
        from .speech_cache import SpeechSegmentCache

        segment_cache = SpeechSegmentCache(Path(cache_dir))
    def claim_native_endpoint(claims: dict[str, str], engine: str) -> None:
        endpoint = native_bindings.get(engine)
        if endpoint is not None and claims.setdefault(endpoint, engine) != engine:
            raise ValueError("The audio plan needs multiple uncached model variants; one worker serves "
                             "one model. Choose profiles using the same model or reuse previously "
                             "cached segments")

    # Independent workers and external providers do not depend on cache hits.
    # Preflight shared endpoints without holding the cached audio in memory.
    endpoint_use = Counter(native_bindings.values())
    shared_endpoints = {endpoint for endpoint, count in endpoint_use.items() if count > 1}
    if shared_endpoints:
        preflight_claims: dict[str, str] = {}
        for cue in cues:
            _check_cancelled(cancelled)
            if not cue.text or native_bindings.get(cue.profile.engine) not in shared_endpoints:
                continue
            if fresh_audio or segment_cache is None or segment_cache.get(cue.text, cue.profile) is None:
                claim_native_endpoint(preflight_claims, cue.profile.engine)
    render_claims: dict[str, str] = {}
    total = sum(bool(cue.text) for cue in cues)
    requested_engines = sorted({cue.profile.engine if cue.profile.engine in NATIVE_ENGINES or cue.profile.engine in EXTERNAL_ENGINES else "unknown"
                                for cue in cues if cue.text})
    cache_mode = "disabled" if segment_cache is None else "fresh" if fresh_audio else "enabled"
    log_event(get_logger("speech"), "render_plan", target=target, requested_engines=",".join(requested_engines),
              segments=total, cache_mode=cache_mode, output_format="mp3" if output.suffix.lower() == ".mp3" else "wav")
    done = 0
    if progress is not None:
        progress(done, total)
    _check_cancelled(cancelled)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Streaming limits memory to one bounded segment. Temporary files live on
    # the output filesystem so replace is atomic and old copies survive errors.
    with tempfile.TemporaryDirectory(prefix=".lixity-speech-", dir=output.parent) as directory:
        render_dir = Path(directory)
        pcm = render_dir / "reading.wav"
        with wave.open(str(pcm), "wb") as writer:
            writer.setparams((*SPEECH_PCM_FORMAT, 0, "NONE", "not compressed"))
            written = 44

            def write_frames(frames: bytes) -> None:
                nonlocal written
                if max_audio_bytes is not None and written + len(frames) > max_audio_bytes:
                    raise ValueError("Audio output exceeds the configured byte limit")
                writer.writeframes(frames)
                written += len(frames)

            previous_profile: AudioProfile | None = None
            for index, cue in enumerate(cues):
                _check_cancelled(cancelled)
                if cue.pause_before:
                    write_frames(bytes(int(rate * cue.pause_before) * frame_bytes))
                if not cue.text:
                    write_frames(bytes(int(rate * cue.pause_after) * frame_bytes))
                    continue
                effective = cue.profile

                instruction_changed = _changed_value(previous_profile.instructions if previous_profile else None,
                                                     effective.instructions)
                description_changed = _changed_value(previous_profile.voice_description if previous_profile else None,
                                                     effective.voice_description)
                reference_changed = _changed_value(previous_profile.reference_id if previous_profile else None,
                                                   effective.reference_id)
                previous_profile = effective
                with _observe_speech_segment(done + 1, total, effective, writer.getnframes() * 1000 // rate,
                                             instruction_changed, description_changed, reference_changed) as diagnostic:
                    data = None if fresh_audio or segment_cache is None else segment_cache.get(cue.text, effective)
                    cached = data is not None
                    diagnostic["cache"] = ("disabled" if segment_cache is None else "fresh" if fresh_audio else
                                           "hit" if cached else "miss")
                    if data is None:
                        # A cache entry may have been evicted after preflight.
                        claim_native_endpoint(render_claims, effective.engine)
                        data = _synthesize_segment(cue.text, effective, target=target, references=references)
                    params, frames = read_pcm_wav(data)
                    if params != SPEECH_PCM_FORMAT:
                        raise ValueError("Unexpected synthesized audio format")
                    _check_cancelled(cancelled)
                    if not cached and segment_cache is not None:
                        segment_cache.put(cue.text, effective, data)
                        _check_cancelled(cancelled)
                    if effective.speed != 1.0 and not mlx_audio_uses_model_speed(effective):
                        # Cache the unmodified model audio. Processing each spoken
                        # segment leaves explicit pauses and per-profile rates intact.
                        if ffmpeg is None:  # defensive: checked before synthesis
                            raise FileNotFoundError("FFmpeg is required for audio speed adjustment")
                        frames = _adjust_pcm_tempo(data, frames, directory=render_dir, ffmpeg=ffmpeg,
                                                   speed=effective.speed)
                        _check_cancelled(cancelled)
                    # Level and fade only the final assembly. An explicit
                    # alternate delivery keeps its level apart from peak protection.
                    level = level_speech_pcm(frames, rate, preserve_delivery=(
                        effective.instructions != profile.instructions or effective.prosody != profile.prosody
                        or effective.reference_id != profile.reference_id
                        or effective.voice_description != profile.voice_description
                        or effective.engine != profile.engine or effective.voice != profile.voice
                    ))
                    _check_cancelled(cancelled)
                    diagnostic["level_active_rms_dbfs"] = ("unknown" if level.active_rms_dbfs is None
                                                            else round(level.active_rms_dbfs, 1))
                    diagnostic["level_gain_db"] = round(level.gain_db, 2)
                    diagnostic["level_sample_peak_dbfs"] = ("unknown" if level.sample_peak_dbfs is None
                                                             else round(level.sample_peak_dbfs, 1))
                    follows_audio = writer.getnframes() > 0
                    precedes_audio = (done + 1 < total or int(rate * cue.pause_after) > 0
                                      or any(int(rate * following.pause_before) > 0
                                             or int(rate * following.pause_after) > 0
                                             for following in cues[index + 1:]))
                    write_frames(_fade_pcm_edges(level.frames, rate, fade_in=follows_audio, fade_out=precedes_audio))
                    diagnostic["pcm_end_ms"] = writer.getnframes() * 1000 // rate
                    _check_cancelled(cancelled)
                done += 1
                if progress is not None:
                    progress(done, total)
                if cue.pause_after:
                    write_frames(bytes(int(rate * cue.pause_after) * frame_bytes))
        final = pcm
        if output.suffix.lower() == ".mp3":
            if ffmpeg is None:  # defensive: checked before synthesis
                raise FileNotFoundError("FFmpeg is required for MP3 output")
            final = render_dir / "reading.mp3"
            result = _run_ffmpeg(
                [ffmpeg, "-nostdin", "-y", "-v", "error", "-i", str(pcm),
                                     "-b:a", "192k", str(final)])
            if result.returncode != 0 or not final.is_file() or not final.stat().st_size:
                raise RuntimeError("FFmpeg failed to create MP3 audio")
        _check_cancelled(cancelled)
        os.replace(final, output)
    return output
