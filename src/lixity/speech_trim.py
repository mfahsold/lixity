"""Create an exact PCM excerpt with an explicitly configured local SoundCraft CLI."""

from __future__ import annotations

import base64
import binascii
import io
import json
import os
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

from .audio_pcm import wave_reader_is_integer_pcm
from .io import FileUtils, sanitized_subprocess_env
from .speech_recording_settings import MAX_REFERENCE_SECONDS, MIN_REFERENCE_SECONDS
from .speech_worker import REFERENCE_WAV_FORMAT

_CLI_SETTING = "LIXITY_SOUNDCRAFT_CLI"
_VERSION = "soundcraft-cli 0.20.1"
_CHANNELS, _FRAME_BYTES, _RATE = REFERENCE_WAV_FORMAT
MAX_TRIM_INPUT_SECONDS = 120
_MAX_INPUT_FRAMES = MAX_TRIM_INPUT_SECONDS * _RATE
_WAV_HEADER_ALLOWANCE = 64 * 1024
_MAX_INPUT_BYTES = _MAX_INPUT_FRAMES * _FRAME_BYTES + _WAV_HEADER_ALLOWANCE
_MAX_BASE64_BYTES = 4 * ((_MAX_INPUT_BYTES + 2) // 3)
MAX_TRIM_REQUEST_BYTES = _MAX_BASE64_BYTES + 4096
_trim_slot = threading.Lock()


def configured_soundcraft() -> Path | None:
    """Return an explicit executable path, without probing default installations."""
    value = os.environ.get(_CLI_SETTING)
    if not value:
        return None
    path = Path(value)
    try:
        return path if path.is_absolute() and path.is_file() and os.access(path, os.X_OK) else None
    except OSError:
        return None


def _pcm_frames(wav: bytes, maximum_frames: int) -> bytes:
    try:
        with wave.open(io.BytesIO(wav), "rb") as reader:
            if not wave_reader_is_integer_pcm(reader) or (
                reader.getnchannels(), reader.getsampwidth(), reader.getframerate()
            ) != REFERENCE_WAV_FORMAT:
                raise ValueError("Choose an uncompressed 24 kHz mono 16-bit WAV")
            frames = reader.getnframes()
            if not MIN_REFERENCE_SECONDS * _RATE <= frames <= maximum_frames:
                raise ValueError("The recording duration is outside the supported range")
            pcm = reader.readframes(frames)
            if len(pcm) != frames * _FRAME_BYTES:
                raise ValueError("The recording contains incomplete PCM samples")
            return pcm
    except (EOFError, wave.Error) as exc:
        raise ValueError("Choose an uncompressed 24 kHz mono 16-bit WAV") from exc


def _wav_bytes(pcm: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((_CHANNELS, _FRAME_BYTES, _RATE, 0, "NONE", "not compressed"))
        writer.writeframes(pcm)
    return output.getvalue()


def _run(executable: Path, args: list[str], directory: Path, *, version: bool = False) -> bytes:
    folder = str(directory)
    isolated_paths = ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
                      "APPDATA", "LOCALAPPDATA", "TMPDIR", "TEMP", "TMP")
    env = sanitized_subprocess_env(overrides=dict.fromkeys(isolated_paths, folder))
    env["SOUNDCRAFT_NO_PREFS"] = "1"
    try:
        result = subprocess.run(  # noqa: S603 - operator-configured CLI, fixed arguments and temporary WAVs
            [str(executable), *args], cwd=directory, env=env, timeout=5 if version else 30,
            check=True, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE if version else subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("SoundCraft could not complete the audio excerpt") from exc
    return result.stdout or b""


def trim_audio_take(executable: Path, encoded: object, start: object, end: object) -> str:
    """Validate a bounded WAV and return only the verified samples in the selected range."""
    if not isinstance(encoded, str) or len(encoded) > _MAX_BASE64_BYTES:
        raise ValueError(f"Choose a WAV recording of at most {MAX_TRIM_INPUT_SECONDS} seconds")
    if type(start) is not int or type(end) is not int or not (
        MIN_REFERENCE_SECONDS * _RATE <= end - start <= MAX_REFERENCE_SECONDS * _RATE
    ):
        raise ValueError(f"Choose a range between {MIN_REFERENCE_SECONDS} and {MAX_REFERENCE_SECONDS} seconds")
    try:
        wav = base64.b64decode(encoded, validate=True)
        if len(wav) > _MAX_INPUT_BYTES:
            raise ValueError("The WAV exceeds the supported byte limit")
        pcm = _pcm_frames(wav, _MAX_INPUT_FRAMES)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(
            f"Choose a valid 24 kHz mono 16-bit WAV of {MIN_REFERENCE_SECONDS} to {MAX_TRIM_INPUT_SECONDS} seconds"
        ) from exc
    frames = len(pcm) // _FRAME_BYTES
    if not 0 <= start < end <= frames or (start == 0 and end == frames):
        raise ValueError("Choose a shorter range within the recording")

    if not _trim_slot.acquire(blocking=False):
        raise RuntimeError("Another audio excerpt is being prepared")
    try:
        with tempfile.TemporaryDirectory(prefix="lixity-soundcraft-") as scratch:
            folder = Path(scratch)
            version = _run(executable, ["--version"], folder, version=True)
            if not version.strip().startswith((_VERSION + " (").encode()):
                raise RuntimeError(f"The audio excerpt requires {_VERSION}")
            source = folder / "take.wav"
            source.write_bytes(_wav_bytes(pcm))
            clips, output = folder / "clips", folder / "excerpt.wav"
            args = ["run"]
            for command, parameters in (
                ("session.new", {"sample_rate": _RATE, "bit_depth": 16}),
                ("file.import_audio", {"path": str(source)}),
                ("edit.select", {"tracks": ["take"], "start": start, "end": end, "exact": True}),
                ("edit.trim_to_selection", {}),
                ("file.export_clips", {"dir": str(clips), "format": "wav"}),
            ):
                args.extend(("--cmd", f"{command}={json.dumps(parameters)}"))
            _run(executable, args, folder)
            _run(executable, ["convert", str(clips / "take.wav"), str(output), "--bit-depth", "16", "--no-dither"], folder)
            count = end - start
            try:
                result, _ = FileUtils.read_bounded_regular_bytes(
                    output, maximum=count * _FRAME_BYTES + _WAV_HEADER_ALLOWANCE, verify_stable=True,
                )
                excerpt = _pcm_frames(result, count)
            except (OSError, ValueError) as exc:
                raise RuntimeError("SoundCraft did not return a verified audio excerpt") from exc
            if excerpt != pcm[start * _FRAME_BYTES:end * _FRAME_BYTES]:
                raise RuntimeError("SoundCraft changed samples in the selected range")
            return base64.b64encode(_wav_bytes(excerpt)).decode("ascii")
    finally:
        _trim_slot.release()
