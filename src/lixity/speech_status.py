"""Read-only, content-free view of audio profiles and actual local workers."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .config import read_explicit_project_config
from .speech_profiles import QWEN_LANGUAGES, audio_capabilities, parse_audio_settings
from .speech_qwen import worker_health


def audio_status(project: str | Path | None = None, *, engine: str | None = None) -> dict[str, Any]:
    """Return explicit project profiles and actual worker identities, without prose.

    ``model_matches`` compares identities only; ``None`` means unknown or no
    selected profile, not a failed or successful compatibility check. Worker
    readiness remains separate from model identity.
    """
    project_view: dict[str, Any] | None = None
    expected_model: str | None = None
    comparison_engine = engine
    if engine is not None and engine not in audio_capabilities():
        raise ValueError("Unknown audio engine")
    if project is not None:
        root = Path(project).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Audio project is not an existing directory: {root}")
        config = read_explicit_project_config(root)
        language = config.get("language", "en")
        if not isinstance(language, str):
            raise ValueError("Project language must be a language code")
        raw_settings = config.get("audio")
        if raw_settings is None and language not in QWEN_LANGUAGES:
            # Do not inspect manuscript text or guess an automatically detected
            # speech language just to display the worker status.
            project_view = {"root": str(root), "selected_profile": None, "settings_source": "default",
                            "profiles": [], "profile_issue": "speech_language_unresolved"
                            if language == "auto" else "speech_language_unsupported"}
        else:
            settings = parse_audio_settings(raw_settings, language=language)
            selected = settings.profiles[settings.selected]
            comparison_engine = engine or selected.engine
            project_view = {
                "root": str(root),
                "selected_profile": settings.selected,
                "settings_source": "configured" if raw_settings is not None else "default",
                "profiles": [{"id": key, "name": profile.name, "engine": profile.engine,
                              "voice": profile.voice, "language": profile.language}
                             for key, profile in settings.profiles.items()],
            }
    if comparison_engine is not None:
        expected_model = audio_capabilities()[comparison_engine]["model"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        targets = list(pool.map(worker_health, ("local", "jetson")))
    for target in targets:
        actual = target.get("model")
        target["model_matches"] = actual == expected_model if actual is not None and expected_model else None
    return {"schema_version": "lixity-audio-status/1", "project": project_view, "comparison_engine": comparison_engine,
            "targets": targets}
