"""Read-only audio diagnostics and bounded comparisons with external transcripts.

No recognizer, model, project archive or network is used. Timestamped words are
external evidence, not proof of what the recording contains. Signal thresholds
are descriptive heuristics, never calibrated quality or naturalness judgments.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import wave
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO
from unicodedata import normalize

from .language import LANGUAGE_PROFILES, compile_word_pattern

if TYPE_CHECKING:
    from .speech_direction import SpeechSegment

SCHEMA = "lixity-audio-audit/1"
TRANSCRIPT_SCHEMA = "lixity-audio-transcript/1"
MAX_INPUT_BYTES = 2 * 1024**3
MAX_DECODED_BYTES = 1024**3
MAX_JSON_BYTES = 16 * 1024**2
MAX_AUDIO_SECONDS = 6 * 3600
MAX_PCM_SAMPLES = 500_000_000
MAX_WORDS = 100_000
MAX_SEGMENTS = 10_000
MAX_PLAN_CHARS = 2_000_000
MAX_ALIGNMENT_CELLS = 64_000_000
MAX_SILENCES = 10_000
_SILENCE_DBFS = -50.0
_MIN_SILENCE_SECONDS = 0.1
_WINDOW_SECONDS = 0.02
_DECODE_TIMEOUT_SECONDS = 120


@contextmanager
def _input(path: str | Path, maximum: int) -> Iterator[BinaryIO]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                 | getattr(os, "O_NOFOLLOW", 0))
    # FFmpeg inherits this file descriptor. An unbuffered reader keeps its OS
    # offset consistent with seek() after wave has inspected an unsupported fmt.
    with os.fdopen(fd, "rb", buffering=0) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError("Audio audit input must be a bounded regular file")
        yield stream


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field in audio audit input")
        result[key] = value
    return result


def _nonfinite_json(_value: str) -> None:
    raise ValueError("Audio audit JSON numbers must be finite")


def load_audit_json(path: str | Path) -> dict[str, Any]:
    """Read a bounded JSON object without retaining it or accepting duplicate keys."""
    with _input(path, MAX_JSON_BYTES) as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Audio audit JSON exceeds the size limit")
    try:
        value = json.loads(raw, object_pairs_hook=_json_pairs, parse_constant=_nonfinite_json)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Malformed audio audit JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("Audio audit JSON must be an object")
    return value


def _digest(stream: BinaryIO) -> str:
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024**2):
        size += len(chunk)
        if size > MAX_INPUT_BYTES:
            raise ValueError("Audio input exceeds the size limit")
        digest.update(chunk)
    stream.seek(0)
    return digest.hexdigest()


def _wav_format(stream: BinaryIO) -> tuple[int, int, bytes]:
    """Validate declared RIFF/chunk bounds before any optional decoder can trim them."""
    try:
        size = stream.seek(0, os.SEEK_END)
        stream.seek(0)
        header = stream.read(12)
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise ValueError("Invalid or truncated WAV header")
        end = 8 + int.from_bytes(header[4:8], "little")
        if not 12 <= end <= size:
            raise ValueError("Truncated WAV input; declared RIFF bytes are missing")
        position = 12
        format_chunk: tuple[int, int, bytes] | None = None
        data_found = False
        chunks = 0
        while position < end:
            chunks += 1
            if chunks > 10_000:
                raise ValueError("WAV metadata exceeds the chunk budget")
            stream.seek(position)
            chunk = stream.read(8)
            if position + 8 > end or len(chunk) != 8:
                raise ValueError("Truncated WAV chunk header")
            length = int.from_bytes(chunk[4:], "little")
            offset = position + 8
            if offset + length > end:
                raise ValueError("Truncated WAV input; declared chunk bytes are missing")
            if chunk[:4] == b"fmt ":
                if format_chunk is not None or length < 16:
                    raise ValueError("Invalid WAV format chunk")
                content = stream.read(min(length, 40))
                if len(content) != min(length, 40):
                    raise ValueError("Truncated WAV format chunk")
                format_chunk = offset, length, content
            elif chunk[:4] == b"data":
                data_found = True
            position = offset + length
            # Python's own wave writer omits padding for a final odd data chunk.
            if position < end:
                position += length % 2
        if format_chunk is None or not data_found:
            raise ValueError("WAV requires format and audio data chunks")
        return format_chunk
    finally:
        stream.seek(0)


def _portable_decoded_wav(path: Path) -> None:
    """Normalize only the disposable decoder header, without rewriting PCM samples.

    FFmpeg emits WAVE_FORMAT_EXTENSIBLE for pcm_s32le. Python 3.10/3.11's wave
    cannot read that tag. A verified integer-PCM fmt becomes a classic 16-byte
    PCM fmt, and the existing extension occupies a same-size JUNK chunk. Audio
    offsets, sample width, rate, channel order and every sample byte stay intact.
    """
    with path.open("r+b") as stream:
        offset, length, content = _wav_format(stream)
        tag = int.from_bytes(content[:2], "little")
        bits = int.from_bytes(content[14:16], "little")
        pcm_guid = bytes.fromhex("0100000000001000800000aa00389b71")
        extensible_pcm = (tag == 0xFFFE and len(content) >= 40
                          and int.from_bytes(content[16:18], "little") >= 22
                          and int.from_bytes(content[18:20], "little") == 32
                          and content[24:40] == pcm_guid)
        if bits != 32 or not (tag == 1 or extensible_pcm):
            raise ValueError("Audio decoder did not produce 32-bit integer PCM")
        if extensible_pcm:
            stream.seek(offset - 4)
            stream.write((16).to_bytes(4, "little"))
            stream.write(b"\x01\x00")
            stream.seek(offset + 16)
            stream.write(b"JUNK" + (length - 24).to_bytes(4, "little"))


@contextmanager
def _decoded(stream: BinaryIO, audio_format: str) -> Iterator[tuple[wave.Wave_read, str]]:
    if audio_format == "wav":
        _wav_format(stream)
        try:
            with wave.open(stream, "rb") as reader:
                yield reader, "stdlib-wave"
            return
        except wave.Error as exc:
            # Unsupported encodings (including floating point WAV) need FFmpeg;
            # malformed/truncated PCM must not silently become a shorter file.
            if "unknown format" not in str(exc):
                raise ValueError("Invalid or truncated WAV input") from exc
        except (EOFError, OSError) as exc:
            raise ValueError("Invalid or truncated WAV input") from exc
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise ValueError("This audio encoding requires an installed FFmpeg decoder")
    stream.seek(0)
    with tempfile.TemporaryDirectory(prefix="lixity-audio-audit-") as directory:
        output = Path(directory) / "decoded.wav"
        try:
            process = subprocess.run(  # noqa: S603 -- fixed decoder arguments; input via local fd
                [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-xerror",
                 "-protocol_whitelist", "file,pipe", "-f", audio_format, "-i", "pipe:0",
                 "-map", "0:a:0", "-vn", "-sn", "-dn", "-map_metadata", "-1",
                 "-threads", "1", "-c:a", "pcm_s32le", "-t", str(MAX_AUDIO_SECONDS + 1),
                 "-fs", str(MAX_DECODED_BYTES), "-f", "wav", str(output)],
                stdin=stream, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=_DECODE_TIMEOUT_SECONDS, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Audio decoding exceeded the time budget") from exc
        if process.returncode or not output.is_file():
            raise ValueError("Audio decoding failed; no partial audit was produced")
        # FFmpeg's -fs can stop at a packet boundary. Treat the final MiB as a
        # conservative guard zone rather than accepting a potentially cut tail.
        if output.stat().st_size >= MAX_DECODED_BYTES - 1024**2:
            raise ValueError("Decoded audio exceeds the bounded temporary-file budget")
        _portable_decoded_wav(output)
        try:
            with wave.open(str(output), "rb") as reader:
                yield reader, "ffmpeg-pcm32"
        except (wave.Error, EOFError) as exc:
            raise ValueError("Invalid or truncated decoded audio") from exc


def _samples(raw: bytes, width: int) -> Sequence[int]:
    if width == 1:
        return [value - 128 for value in raw]
    if width == 3:
        return [int.from_bytes(raw[index:index + 3], "little", signed=True)
                for index in range(0, len(raw), 3)]
    result = array.array("h" if width == 2 else "i")
    result.frombytes(raw)
    if sys.byteorder != "little":
        result.byteswap()
    return result


def _db(amplitude: float) -> float | None:
    return round(20 * math.log10(amplitude), 6) if amplitude > 0 else None


def _measure(reader: wave.Wave_read) -> tuple[dict[str, Any], dict[str, Any]]:
    channels, width, rate, frames = (reader.getnchannels(), reader.getsampwidth(),
                                     reader.getframerate(), reader.getnframes())
    if channels not in range(1, 9) or width not in (1, 2, 3, 4) or not 0 < rate <= 384000:
        raise ValueError("Audio audit supports PCM with 1–8 channels, 8–32 bits and rates up to 384 kHz")
    if frames == 0:
        raise ValueError("Audio has no frames (empty recording)")
    if frames / rate > MAX_AUDIO_SECONDS or frames * channels > MAX_PCM_SAMPLES:
        raise ValueError("Audio exceeds the duration or decoded-sample budget; split the recording")
    scale = 1 << (8 * width - 1)
    totals = [0] * channels
    squares = [0] * channels
    peaks = [0] * channels
    clipped = [0] * channels
    silences: list[dict[str, float]] = []
    silence_start: int | None = None
    silence_frames = silence_count = position = 0
    step = max(1, round(rate * _WINDOW_SECONDS))
    silence_power = 10 ** (_SILENCE_DBFS / 10)

    def close_silence(end: int) -> None:
        nonlocal silence_start, silence_frames, silence_count
        if silence_start is not None and (end - silence_start) / rate >= _MIN_SILENCE_SECONDS:
            silence_frames += end - silence_start
            silence_count += 1
            if len(silences) < MAX_SILENCES:
                silences.append({"start": round(silence_start / rate, 9),
                                 "end": round(end / rate, 9),
                                 "duration": round((end - silence_start) / rate, 9)})
        silence_start = None

    while position < frames:
        count = min(step, frames - position)
        raw = reader.readframes(count)
        if len(raw) != count * channels * width:
            raise ValueError("Truncated PCM data; declared audio frames are missing")
        samples = _samples(raw, width)
        silent = True
        for channel in range(channels):
            values = samples[channel::channels]
            power = sum(value * value for value in values)
            totals[channel] += sum(values)
            squares[channel] += power
            peaks[channel] = max(peaks[channel], abs(min(values)), abs(max(values)))
            clipped[channel] += values.count(-scale) + values.count(scale - 1)
            if power / (count * scale**2) > silence_power:
                silent = False
        if silent:
            if silence_start is None:
                silence_start = position
        else:
            close_silence(position)
        position += count
    close_silence(position)
    per_channel = [{"channel": index + 1, "peak_dbfs": _db(peaks[index] / scale),
                    "rms_dbfs": _db(math.sqrt(squares[index] / frames) / scale),
                    "dc_offset": totals[index] / (frames * scale),
                    "clipped_samples": clipped[index],
                    "clipped_sample_fraction": clipped[index] / frames}
                   for index in range(channels)]
    signal: dict[str, Any] = {
        "method": "descriptive-uncalibrated",
        "peak_dbfs": _db(max(peaks) / scale),
        "rms_dbfs": _db(math.sqrt(sum(squares) / (frames * channels)) / scale),
        "dc_offset": sum(totals) / (frames * channels * scale),
        "clipped_samples": sum(clipped),
        "clipped_sample_fraction": sum(clipped) / (frames * channels),
        "channel_metrics": per_channel,
        "silences": silences, "silence_seconds": silence_frames / rate,
        "silence_count": silence_count, "silences_truncated": silence_count > len(silences),
        "silence_method": {"threshold_dbfs": _SILENCE_DBFS, "window_seconds": step / rate,
                           "minimum_seconds": _MIN_SILENCE_SECONDS,
                           "channels": "every channel must be below the RMS threshold"},
        "noise_floor_dbfs": None, "bandwidth_hz": None,
        "unknowns": [{"measurement": "noise_floor_dbfs",
                      "reason": "Speech and background noise are not separated by this audit."},
                     {"measurement": "bandwidth_hz",
                      "reason": "No validated long-recording bandwidth estimate is computed."}],
        "limitations": ["Full-scale PCM samples are a clipping indication, not proof of distortion.",
                        "Silence windows are a level heuristic, not speech or natural-pause detection.",
                        "A null level for digital silence represents negative infinity dBFS.",
                        "Decoded compressed or floating-point audio is measured as integer PCM."],
    }
    return ({"duration_seconds": frames / rate, "channels": channels, "sample_rate_hz": rate,
             "frames": frames, "sample_width_bits": width * 8}, signal)


@dataclass(frozen=True)
class _Segment:
    text: str
    before: float
    after: float


@dataclass(frozen=True)
class _Word:
    text: str
    start: float
    end: float


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def _segments(plan: Mapping[str, Any] | Sequence[SpeechSegment]) -> list[_Segment]:
    if isinstance(plan, Mapping):
        if plan.get("schema_version") not in ("lixity-speech-plan/1", "lixity-audio-timeline/1"):
            raise ValueError("Expected a versioned speech plan or audio timeline")
        rows = plan.get("segments")
    else:
        rows = plan
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) > MAX_SEGMENTS:
        raise ValueError("Expected a bounded sequence of speech plan segments")
    result = []
    characters = 0
    for row in rows:
        if isinstance(row, Mapping):
            text, before, after = row.get("text"), row.get("pause_before", 0), row.get("pause_after", 0)
        else:
            from .speech_direction import SpeechSegment
            if not isinstance(row, SpeechSegment):
                raise ValueError("Invalid speech plan segment")
            text, before, after = row.text, row.pause_before, row.pause_after
        if not isinstance(text, str):
            raise ValueError("Speech plan segment text must be a string")
        characters += len(text)
        if characters > MAX_PLAN_CHARS:
            raise ValueError("Speech plan exceeds the text budget")
        leading, trailing = _number(before, "Planned pause"), _number(after, "Planned pause")
        if not 0 <= leading <= MAX_AUDIO_SECONDS or not 0 <= trailing <= MAX_AUDIO_SECONDS:
            raise ValueError("Planned pauses must be nonnegative and bounded")
        result.append(_Segment(text, leading, trailing))
    return result


def _tokens(text: str, pattern: re.Pattern[str]) -> list[str]:
    return [match.group(0).lower() for match in pattern.finditer(normalize("NFC", text))]


def _transcript(value: Mapping[str, Any], digest: str, duration: float,
                pattern: re.Pattern[str]) -> tuple[list[_Word], dict[str, Any]]:
    if (not isinstance(value, Mapping) or
            set(value) - {"schema_version", "audio_sha256", "words", "model"} or
            value.get("schema_version") != TRANSCRIPT_SCHEMA):
        raise ValueError("Expected a lixity-audio-transcript/1 object")
    if value.get("audio_sha256") != digest:
        raise ValueError("Transcript audio_sha256 does not match the exact audio file")
    entries = value.get("words")
    if not isinstance(entries, list) or len(entries) > MAX_WORDS:
        raise ValueError("Transcript words must be a bounded list")
    model = value.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 200):
        raise ValueError("Transcript model must be a nonempty string or null")
    attribution = ({"status": "declared", "name": model} if model is not None else
                   {"status": "unknown", "name": None,
                    "reason": "The external transcript does not identify its recognizer model."})
    words: list[_Word] = []
    previous = 0.0
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"text", "start", "end"}:
            raise ValueError("Each transcript word needs text, start and end")
        text = entry["text"]
        if not isinstance(text, str) or not 0 < len(text) <= 1000:
            raise ValueError("Transcript word text must be a bounded nonempty string")
        tokens = _tokens(text, pattern)
        if len(tokens) != 1:
            raise ValueError("Each transcript entry must contain exactly one language-profile token")
        start, end = _number(entry["start"], "Word start"), _number(entry["end"], "Word end")
        if not previous <= start < end <= duration:
            raise ValueError("Transcript times must be ordered, nonoverlapping and within audio duration")
        previous = end
        words.append(_Word(tokens[0], start, end))
    return words, attribution


def _opcodes(expected: list[str], observed: list[str]) -> list[tuple[str, int, int, int, int]]:
    prefix = 0
    while prefix < min(len(expected), len(observed)) and expected[prefix] == observed[prefix]:
        prefix += 1
    left, right = len(expected), len(observed)
    while left > prefix and right > prefix and expected[left - 1] == observed[right - 1]:
        left -= 1
        right -= 1
    if (left - prefix) * (right - prefix) > MAX_ALIGNMENT_CELLS:
        raise ValueError("Alignment exceeds the comparison budget; split the plan and transcript")
    operations: list[tuple[str, int, int, int, int]] = [(tag, i + prefix, j + prefix, k + prefix, end + prefix)
                  for tag, i, j, k, end in SequenceMatcher(
                      None, expected[prefix:left], observed[prefix:right], autojunk=False).get_opcodes()]
    if prefix:
        operations.insert(0, ("equal", 0, prefix, 0, prefix))
    if left < len(expected):
        operations.append(("equal", left, len(expected), right, len(observed)))
    return operations


def _unknown(reason: str) -> dict[str, Any]:
    return {"status": "unknown", "reason": reason, "coverage": None}


def _pauses(segments: list[_Segment], ranges: list[tuple[int, int]], matched: dict[int, int],
            words: list[_Word], signal: dict[str, Any]) -> dict[str, Any]:
    spoken = [index for index, (start, end) in enumerate(ranges) if end > start]
    comparisons: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for left, right in pairwise(spoken):
        a, b = ranges[left], ranges[right]
        indices = [matched.get(index) for start, end in (a, b) for index in range(start, end)]
        if any(index is None for index in indices) or any(
                after != before + 1 for before, after in pairwise(indices)
                if before is not None and after is not None):
            unavailable.append({"after_segment": left, "before_segment": right,
                                "reason": "Both adjacent segments must match fully with no intervening transcript words."})
            continue
        start, end = words[matched[a[1] - 1]].end, words[matched[b[0]]].start
        planned = segments[left].after + segments[right].before + sum(
            item.before + item.after for item in segments[left + 1:right])
        silence = (None if signal["silences_truncated"] else sum(
            max(0.0, min(end, interval["end"]) - max(start, interval["start"]))
            for interval in signal["silences"]))
        comparisons.append({"after_segment": left, "before_segment": right,
                            "start": start, "end": end, "planned_seconds": planned,
                            "observed_seconds": end - start, "difference_seconds": end - start - planned,
                            "detected_silence_seconds": silence})
    return {"status": "compared" if comparisons else "unknown", "comparisons": comparisons,
            "unanchored_boundaries": unavailable,
            "reason": None if comparisons else "No fully matching adjacent spoken segments can anchor a pause.",
            "method": "Observed gaps use external word timestamps; they may include breath or noise, not only silence.",
            "segment_index_base": 0}


def _alignment(segments: list[_Segment], words: list[_Word], model: dict[str, Any],
               language: str, pattern: re.Pattern[str], signal: dict[str, Any]
               ) -> tuple[dict[str, Any], dict[str, Any]]:
    expected: list[str] = []
    ranges = []
    for segment in segments:
        start = len(expected)
        expected.extend(_tokens(segment.text, pattern))
        ranges.append((start, len(expected)))
        if len(expected) > MAX_WORDS:
            raise ValueError("Expected speech plan exceeds the word budget")
    if not expected:
        reason = "The speech plan contains no comparable word tokens."
        return _unknown(reason), {"status": "unknown", "reason": reason, "comparisons": []}
    observed = [word.text for word in words]
    missing: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []
    replacements: list[dict[str, Any]] = []
    matched: dict[int, int] = {}
    for tag, left, right, start, end in _opcodes(expected, observed):
        if tag == "equal":
            matched.update(zip(range(left, right), range(start, end), strict=True))
        elif tag == "delete":
            missing.extend({"text": expected[index], "index": index, "start": None, "end": None,
                            "after_seconds": words[start - 1].end if start else None,
                            "before_seconds": words[start].start if start < len(words) else None}
                           for index in range(left, right))
        elif tag == "insert":
            extra.extend({"text": words[index].text, "index": index,
                          "start": words[index].start, "end": words[index].end}
                         for index in range(start, end))
        else:
            replacements.append({"expected_words": expected[left:right],
                                 "transcript_words": observed[start:end],
                                 "expected_start_index": left, "transcript_start_index": start,
                                 "start": words[start].start, "end": words[end - 1].end})
    return ({"status": "compared", "reason": None, "language": language,
             "normalization": "NFC and lowercase; tokens use the explicit Lixity language profile. Punctuation outside tokens is ignored.",
             "method": "Bounded difflib token comparison against external timestamped words; no acoustic verification.",
             "transcript_model": model, "expected_word_count": len(expected),
             "transcript_word_count": len(words), "matched_words": len(matched),
             "coverage": len(matched) / len(expected), "word_index_base": 0,
             "missing_words": missing, "extra_words": extra, "replacements": replacements,
             "limitations": ["Recognition mistakes and ambiguous repeated words can change the comparison.",
                             "Coverage is the matched expected-token fraction, not recognizer confidence or a quality score.",
                             "Missing words have no observed timestamp; neighboring timestamps only bracket the omission."]},
            _pauses(segments, ranges, matched, words, signal))


def inspect_audio(audio_path: str | Path, *,
                  expected_plan: Mapping[str, Any] | Sequence[SpeechSegment] | None = None,
                  transcript: Mapping[str, Any] | None = None, language: str = "en") -> dict[str, Any]:
    """Inspect an explicit WAV/FLAC/MP3 and optionally compare an external transcript.

    Source bytes remain untouched and are never archived. PCM is streamed; other
    encodings use an installed FFmpeg and a bounded, discarded private temporary
    WAV. Invalid or oversized inputs fail explicitly without a partial report.
    """
    if language not in LANGUAGE_PROFILES:
        raise ValueError("Choose an explicit registered language for audio transcript tokenization")
    pattern = compile_word_pattern(LANGUAGE_PROFILES[language].word_regex)
    segments = _segments(expected_plan) if expected_plan is not None else None
    audio_format = Path(audio_path).suffix.lower().lstrip(".")
    if audio_format not in {"wav", "flac", "mp3"}:
        raise ValueError("Audio audit accepts explicit WAV, FLAC or MP3 files")
    with _input(audio_path, MAX_INPUT_BYTES) as stream:
        digest = _digest(stream)
        with _decoded(stream, audio_format) as (reader, decoder):
            audio, signal = _measure(reader)
        if _digest(stream) != digest:
            raise ValueError("Audio changed during inspection; retry with a stable file")
    audio.update({"sha256": digest, "format": audio_format, "decoded_format": "integer-pcm",
                  "decoder": decoder})
    words, model = (_transcript(transcript, digest, audio["duration_seconds"], pattern)
                    if transcript is not None else ([], {}))
    if segments is not None and transcript is not None:
        alignment, pauses = _alignment(segments, words, model, language, pattern, signal)
    else:
        reason = ("No external timestamped transcript was provided; recording text is unknown."
                  if transcript is None else "No expected spoken plan was provided for text comparison.")
        alignment = _unknown(reason)
        pauses = {"status": "unknown", "reason": reason, "comparisons": []}
    return {"schema_version": SCHEMA, "audio": audio, "signal": signal,
            "alignment": alignment, "pauses": pauses,
            "limitations": ["This audit does not run speech recognition or contact an external service.",
                            "It does not establish acoustic quality, intelligibility, voice identity or text correctness."]}
