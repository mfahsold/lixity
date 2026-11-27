"""Integer PCM WAV primitives shared by speech, recording and audio analysis."""

from __future__ import annotations

import io
import wave

SPEECH_PCM_FORMAT = (1, 2, 24_000)  # Channels, sample width in bytes, sample rate.
WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


def wave_reader_is_integer_pcm(reader: wave.Wave_read) -> bool:
    """Check the frame format before measuring or rewriting sample bytes."""
    # Python 3.15 added IEEE float and getformat(). Earlier wave readers accept
    # only integer PCM, including the PCM subtype of extensible WAV.
    get_format = getattr(reader, "getformat", None)
    return get_format is None or get_format() in (WAVE_FORMAT_PCM, WAVE_FORMAT_EXTENSIBLE)


def read_pcm_wav(data: bytes, *, allow_empty: bool = False) -> tuple[tuple[int, int, int], bytes]:
    """Return the format and complete PCM frames of a WAV held in memory."""
    try:
        with wave.open(io.BytesIO(data), "rb") as reader:
            if not wave_reader_is_integer_pcm(reader):
                raise ValueError("Audio segment requires integer PCM WAV")
            params = (reader.getnchannels(), reader.getsampwidth(), reader.getframerate())
            count = reader.getnframes()
            # wave reports only complete frames. Read one frame beyond its
            # count so an incomplete terminal frame is detected as well.
            frames = reader.readframes(count + 1)
            if (reader.getcomptype() != "NONE" or (not count and not allow_empty)
                    or len(frames) != count * params[0] * params[1]):
                raise ValueError("Missing or truncated PCM audio segment")
            return params, frames
    except (wave.Error, EOFError, OSError) as exc:
        raise ValueError("Invalid WAV audio segment") from exc
