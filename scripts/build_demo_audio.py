#!/usr/bin/env python3
"""Regenerate the reviewed synthetic chapter clip without playing sound.

Synthesis requires the locally installed eSpeak NG shared library and data.
Use --reuse-recording after manuscript edits that leave the exact spoken text
unchanged. Ordinary example builds reuse the checked-in WAV and verify its
source and audio hashes.
The callback ABI is documented in espeak-ng/src/include/espeak-ng/speak_lib.h.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import io
import json
import wave
from pathlib import Path

from lixity.io import FileUtils
from lixity.pipeline import resolve_document_config
from lixity.speech import extract_audio_cues
from lixity.speech_jobs import prepare_speech_source

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "samples/first-look.md"
TARGET = ROOT / "docs/assets/audio/warehouse-4-chapter-1.wav"
SCHEMA_VERSION = "lixity-demo-audio/1"
CHAPTER = 1
REVIEWED_GENERATORS = ("eSpeak NG", "Lixity Qwen")


def demo_spoken_text(source: bytes, chapter: int) -> bytes:
    text = source.decode("utf-8")
    config, _language = resolve_document_config(text, "en", project_config={})
    selected, _context = prepare_speech_source(text, language=config.language, mode="chapter", chapter=chapter)
    return "\n\n".join(cue.text for cue in extract_audio_cues(selected, language="en") if cue.text).encode("utf-8")


def _recording_metadata(target: Path, chapter: int) -> dict:
    manifest = target.with_suffix(".json")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("The recording needs a reviewed demo audio manifest")
    generator = metadata.get("generator")
    if (type(metadata.get("chapter")) is not int or metadata["chapter"] != chapter
            or not isinstance(generator, dict) or generator.get("name") not in REVIEWED_GENERATORS):
        raise SystemExit("The recording needs reviewed chapter provenance")
    return metadata


def read_reviewed_recording(target: Path, source: bytes, chapter: int) -> bytes:
    """Read a demonstration track tied to the complete manuscript and spoken chapter."""
    metadata = _recording_metadata(target, chapter)
    audio = target.read_bytes()
    if (metadata.get("source_sha256") != hashlib.sha256(source).hexdigest()
            or metadata.get("spoken_text_sha256") != hashlib.sha256(demo_spoken_text(source, chapter)).hexdigest()
            or metadata.get("audio_sha256") != hashlib.sha256(audio).hexdigest()):
        raise ValueError("Regenerate and review the synthetic chapter audio before building publications")
    return audio


def _reuse_recording(source_sha256: str, spoken_sha256: str, target: Path, chapter: int) -> None:
    metadata = _recording_metadata(target, chapter)
    if metadata.get("spoken_text_sha256") != spoken_sha256:
        raise SystemExit("The chapter's spoken text changed. Regenerate and review the recording.")
    if metadata.get("audio_sha256") != hashlib.sha256(target.read_bytes()).hexdigest():
        raise SystemExit("The WAV differs from the reviewed recording")
    metadata["source_sha256"] = source_sha256
    FileUtils.atomic_write_if_changed(str(target.with_suffix(".json")), json.dumps(metadata, indent=2) + "\n")
    print(f"{target.name}: verified spoken text and WAV for the current manuscript")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chapter", type=int, choices=(1, 2), default=CHAPTER)
    parser.add_argument("--reuse-recording", action="store_true",
                        help="Refresh the manuscript hash after checking the exact spoken text and existing WAV")
    args = parser.parse_args(argv)
    target = TARGET if args.chapter == CHAPTER else TARGET.with_name(f"warehouse-4-chapter-{args.chapter}.wav")
    source = SOURCE.read_bytes()
    spoken_bytes = demo_spoken_text(source, args.chapter)
    source_sha256 = hashlib.sha256(source).hexdigest()
    spoken_sha256 = hashlib.sha256(spoken_bytes).hexdigest()
    if args.reuse_recording:
        _reuse_recording(source_sha256, spoken_sha256, target, args.chapter)
        return

    library = ctypes.util.find_library("espeak-ng")
    if library is None:
        raise SystemExit("Install eSpeak NG locally to regenerate the demo audio")
    engine = ctypes.CDLL(library)
    callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
    engine.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    engine.espeak_Initialize.restype = ctypes.c_int
    engine.espeak_SetSynthCallback.argtypes = [callback_type]
    engine.espeak_SetSynthCallback.restype = None
    engine.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    engine.espeak_SetParameter.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
    engine.espeak_Synth.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
                                    ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint), ctypes.c_void_p]
    engine.espeak_Info.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
    engine.espeak_Info.restype = ctypes.c_char_p
    chunks = []

    @callback_type
    def collect(samples: object, count: int, _events: object) -> int:
        if samples and count:
            chunks.append(ctypes.string_at(samples, count * 2))
        return 0

    # AUDIO_OUTPUT_SYNCHRONOUS delivers PCM to this callback, never a sound device.
    rate = engine.espeak_Initialize(2, 0, None, 0x8000)
    if rate <= 0:
        raise SystemExit("eSpeak NG data is unavailable")
    try:
        engine.espeak_SetSynthCallback(collect)
        if engine.espeak_SetVoiceByName(b"en") != 0 or engine.espeak_SetParameter(1, 165, 0) != 0:
            raise SystemExit("The reviewed eSpeak NG voice/rate is unavailable")
        encoded = spoken_bytes + b"\0"
        identifier = ctypes.c_uint()
        if engine.espeak_Synth(encoded, len(encoded), 0, 1, 0, 1, ctypes.byref(identifier), None) != 0:
            raise SystemExit("Demo synthesis failed")
        version = engine.espeak_Info(None).decode("utf-8")
    finally:
        engine.espeak_Terminate()
    pcm = b"".join(chunks)
    if not pcm:
        raise SystemExit("No demo audio was produced")
    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        writer.writeframes(pcm)
    content = output.getvalue()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    metadata = {"schema_version": SCHEMA_VERSION, "chapter": args.chapter,
                "source_sha256": source_sha256,
                "spoken_text_sha256": spoken_sha256,
                "audio_sha256": hashlib.sha256(content).hexdigest(),
                "duration_seconds": len(pcm) / (2 * rate),
                "generator": {"name": "eSpeak NG", "version": version, "voice": "en", "rate": 165},
                "description": "Synthetic Warehouse 4 chapter recording using a generic English voice."}
    target.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"{target.relative_to(ROOT)}: {len(content):,} bytes; {metadata['duration_seconds']:.1f}s; no playback")


if __name__ == "__main__":
    main()
