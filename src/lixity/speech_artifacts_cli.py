"""Explicit chapter WAV import without conversion or inferred alignment."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import read_explicit_project_config
from .io import FileUtils
from .speech_artifacts import MAX_CHAPTER_AUDIO_BYTES, retain_chapter_audio
from .speech_jobs import prepare_speech_source
from .speech_references import read_reference_input
from .workspace import resolve_manuscript_target


def configure(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", required=True, help="Explicit project root")
    parser.add_argument("--manuscript", help="Explicit manuscript within the project")
    parser.add_argument("--audio", required=True, help="Completed chapter WAV, mono/stereo 16-bit PCM, 8–192 kHz")
    parser.add_argument("--chapter", required=True, type=int, help="Explicit 1-based chapter number")
    parser.add_argument("--source-sha256", required=True, help="Observed full manuscript SHA-256; rejects changed sources")


def run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = resolve_manuscript_target(args.manuscript, project=args.project)
    settings = read_explicit_project_config(Path(workspace.root))
    text, digest = FileUtils.read_source_snapshot(workspace.manuscript)
    if digest != args.source_sha256:
        raise ValueError("Manuscript changed; inspect its SHA-256 before importing chapter audio")
    prepare_speech_source(text, language=settings.get("language", "en"), mode="chapter",
                         chapter=args.chapter, project_config=settings, for_export=True)

    def valid() -> bool:
        return (FileUtils.read_source_snapshot(workspace.manuscript)[1] == digest
                and read_explicit_project_config(Path(workspace.root)) == settings)

    audio = read_reference_input(args.audio, MAX_CHAPTER_AUDIO_BYTES)
    entry = retain_chapter_audio(workspace.root, audio, source_sha256=digest,
                                chapter=args.chapter, origin="imported", valid=valid)
    return {"schema_version": "lixity-chapter-audio/1", **asdict(entry)}
