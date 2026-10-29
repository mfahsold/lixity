"""Explicit, backed-up audio profile replacement through project transactions."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import (
    PreparedProjectSettings,
    prepare_project_settings,
    project_config_snapshot,
    read_explicit_project_config,
)
from .speech_profiles import migrate_audio_settings, parse_audio_settings
from .workspace import discover

_MAX_CONFIG_BYTES = 1024 * 1024
_MAX_SOURCE_BYTES = 64 * 1024 * 1024


def _source_snapshot(root: Path, settings: Mapping[str, Any]) -> tuple[str | None, tuple[int, ...] | None, str | None]:
    try:
        source = Path(discover(root=str(root), project_config=settings).manuscript)
    except FileNotFoundError:
        return None, None, None
    relative = source.resolve().relative_to(root)
    current = root
    for part in source.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            raise ValueError("Migration source must not be a symlink")
    identity, content = project_config_snapshot(source, maximum_bytes=_MAX_SOURCE_BYTES)
    if identity is None:
        raise ValueError("Migration source changed while preparing")
    return relative.as_posix(), identity, hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class PreparedAudioMigration:
    """A reviewable candidate; only explicit apply creates a backup and writes."""

    _settings: PreparedProjectSettings
    _source: tuple[str | None, tuple[int, ...] | None, str | None]
    _profiles: tuple[tuple[str, str], ...]
    snapshot: str
    target_schema: str | None = None

    def public_dict(self, *, applied: bool = False) -> dict[str, Any]:
        """Expose replacement decisions and a token, never source or private style."""
        result: dict[str, Any] = {
            "schema_version": "lixity-audio-migration/1", "applied": applied,
            "snapshot": self.snapshot,
            "profiles": [{"profile_id": key, "engine": "qwen3", "voice": voice, "speed": 1.0}
                         for key, voice in self._profiles],
        }
        if self.target_schema is not None:
            result["target_schema"] = self.target_schema
        return result

    def _unchanged(self) -> None:
        root = self._settings.path.parent
        if (project_config_snapshot(self._settings.path, maximum_bytes=_MAX_CONFIG_BYTES) != self._settings.original
                or project_config_snapshot(root / "pyproject.toml", maximum_bytes=_MAX_CONFIG_BYTES)
                != self._settings.pyproject_original):
            raise ValueError("Project configuration changed; prepare and review the migration again")
        settings = read_explicit_project_config(root, maximum_bytes=_MAX_CONFIG_BYTES)
        if _source_snapshot(root, settings) != self._source:
            raise ValueError("Project source changed; prepare and review the migration again")

    def apply(self, backup: str | Path) -> dict[str, Any]:
        """Create and verify a new private config backup before the atomic write.

        Original root configs are archived exactly; manuscript bytes are never
        copied or changed. A source/configuration snapshot is checked before and
        after backup. The existing settings transaction checks both root configs
        again immediately before replacement. These are optimistic checks, not a
        cross-process manuscript lock.
        """
        self._unchanged()
        root = self._settings.path.parent
        requested = Path(backup).expanduser().absolute()
        destination = requested.parent.resolve() / requested.name
        if destination.is_relative_to(root):
            raise ValueError("Migration backup must be outside the project")
        files = {name: snapshot[1] for name, snapshot in (
            ("lixity.toml", self._settings.original), ("pyproject.toml", self._settings.pyproject_original),
        ) if snapshot[0] is not None}
        manifest = {"schema_version": "lixity-audio-backup/1", "snapshot": self.snapshot,
                    "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                    "source_sha256": self._source[2]}
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise ValueError("Migration backup already exists; refusing to overwrite it") from exc
        # Keep even a partial backup on failure: never remove an existing path
        # whose ownership may have changed, and never publish after failure.
        with os.fdopen(descriptor, "wb") as stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
                for name, content in files.items():
                    archive.writestr(name, content)
                archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        with zipfile.ZipFile(destination) as archive:
            if (set(archive.namelist()) != {*files, "manifest.json"}
                    or any(archive.read(name) != content for name, content in files.items())
                    or json.loads(archive.read("manifest.json")) != manifest):
                raise ValueError("Migration backup verification failed; project was not changed")
        self._unchanged()
        self._settings.commit()
        return self.public_dict(applied=True)


def prepare_audio_migration(
    project: str | Path, replacements: Mapping[str, str], *, instructions: Mapping[str, str] | None = None,
) -> PreparedAudioMigration:
    """Prepare a dry run using only the explicit root's saved audio settings."""
    candidate = Path(project).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("Migration requires an existing nonsymlink project directory")
    root = candidate.resolve()
    original = project_config_snapshot(root / "lixity.toml", maximum_bytes=_MAX_CONFIG_BYTES)
    pyproject = project_config_snapshot(root / "pyproject.toml", maximum_bytes=_MAX_CONFIG_BYTES)
    settings = read_explicit_project_config(root, maximum_bytes=_MAX_CONFIG_BYTES)
    if "audio" not in settings:
        raise ValueError("Project has no saved audio settings to migrate")
    source = _source_snapshot(root, settings)
    migrated = migrate_audio_settings(settings["audio"], replacements=replacements, instructions=instructions)
    prepared = prepare_project_settings(root, {"audio": migrated.model_dump(by_alias=True)})
    if prepared.original != original or prepared.pyproject_original != pyproject:
        raise ValueError("Project configuration changed while preparing migration")
    fingerprint = {"configs": [hashlib.sha256(item[1]).hexdigest() if item[0] is not None else None
                               for item in (original, pyproject)], "source": source,
                   "candidate_sha256": hashlib.sha256(prepared.content).hexdigest()}
    token = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode("utf-8")).hexdigest()
    result = PreparedAudioMigration(prepared, source, tuple(sorted(replacements.items())), token)
    result._unchanged()
    return result


def prepare_schema3_migration(project: str | Path) -> PreparedAudioMigration:
    """Prepare a reviewed, backed-up upgrade to the Coqui-capable schema."""
    candidate = Path(project).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise ValueError("Migration requires an existing nonsymlink project directory")
    root = candidate.resolve()
    original = project_config_snapshot(root / "lixity.toml", maximum_bytes=_MAX_CONFIG_BYTES)
    pyproject = project_config_snapshot(root / "pyproject.toml", maximum_bytes=_MAX_CONFIG_BYTES)
    settings = read_explicit_project_config(root, maximum_bytes=_MAX_CONFIG_BYTES)
    language = settings.get("language", "en")
    if not isinstance(language, str):
        raise ValueError("Project language must be a language code")
    audio = parse_audio_settings(settings.get("audio"), language=language)
    if audio.schema_name == "lixity-audio-settings/3":
        raise ValueError("Project already uses audio schema /3")
    data = audio.model_dump(by_alias=True)
    data["schema_version"] = "lixity-audio-settings/3"
    source = _source_snapshot(root, settings)
    prepared = prepare_project_settings(root, {"audio": data})
    if prepared.original != original or prepared.pyproject_original != pyproject:
        raise ValueError("Project configuration changed while preparing migration")
    fingerprint = {"configs": [hashlib.sha256(item[1]).hexdigest() if item[0] is not None else None
                               for item in (original, pyproject)], "source": source,
                   "candidate_sha256": hashlib.sha256(prepared.content).hexdigest()}
    token = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode("utf-8")).hexdigest()
    result = PreparedAudioMigration(prepared, source, (), token, "lixity-audio-settings/3")
    result._unchanged()
    return result
