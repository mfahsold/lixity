"""Project-bound speech previews/jobs; browser prose and paths are never inputs."""

from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import load_project_config
from ..io import FileUtils
from ..markdown_parser import split_chapters
from ..pipeline import document_paragraph_texts, resolve_document_config
from ..speech_jobs import SpeechJobs, prepare_speech_source
from ..speech_profiles import (
    AudioProfile,
    audio_capabilities,
    parse_audio_settings,
    resolve_audio_profile,
)
from ._base import ResponseMixin
from .pdf_context import project_settings_token


class _SpeechStale(ValueError):
    pass


class SpeechRoutesMixin(ResponseMixin):
    def _speech_manager(self) -> SpeechJobs:
        manager = getattr(self.server, "speech_jobs", None)
        if not isinstance(manager, SpeechJobs):
            manager = SpeechJobs()
            self.server.speech_jobs = manager
        return manager

    def _speech_bound(self, supplied: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
        manager = getattr(self.server, "speech_jobs", None)
        if isinstance(manager, SpeechJobs):
            manager.cancel_stale()
        root, source = self.get_author_project_root(), self.source_input
        if not root or not source:
            raise ValueError("Open a manuscript project before using audio")
        Path(source).resolve().relative_to(root.resolve())
        expected = project_settings_token(root, source)
        if not expected or supplied.get("project_token") != expected:
            raise _SpeechStale("The selected project/settings changed; reload before using audio")
        text, digest = FileUtils.read_source_snapshot(source)
        if supplied.get("source_sha256") != digest:
            raise _SpeechStale("The manuscript changed; reload before using audio")
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            settings = load_project_config(root)
        key = hashlib.sha256(
            (expected + digest + self.language + str(self._speech_generation)).encode()
        ).hexdigest()
        return text, digest, settings, key

    def _speech_query(self, *, job: bool = False) -> dict[str, str]:
        if not self._same_origin():
            raise PermissionError("Cross-origin request forbidden")
        raw = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        allowed = {"project_token", "source_sha256", *(("id",) if job else ())}
        if set(raw) != allowed or any(len(value) != 1 or not value[0] for value in raw.values()):
            raise ValueError("Supply one selected audio context and job ID when required")
        return {key: value[0] for key, value in raw.items()}

    def _speech_error(self, exc: Exception) -> None:
        code = (
            403
            if isinstance(exc, PermissionError)
            else 409
            if isinstance(exc, _SpeechStale)
            else 400
        )
        self._json({"ok": False, "message": str(exc)}, code)

    def _handle_speech(self, _query: Any = None) -> None:
        try:
            query = self._speech_query()
            with self._workspace_lock:
                text, digest, config, _key = self._speech_bound(query)
                settings = None
                configuration_error = ""
                try:
                    settings = parse_audio_settings(
                        config.get("audio"), language=self.language
                    ).model_dump(by_alias=True)
                except ValueError as exc:
                    configuration_error = str(exc)
                document, _resolved = resolve_document_config(
                    text, self.language, project_config=config
                )
                paragraphs = document_paragraph_texts(text, document)
                chapters = [
                    {
                        "number": number,
                        "title": title,
                        "start_line": min(
                            (p.start_line for p in paragraphs if p.chapter_num == number), default=0
                        ),
                        "end_line": max(
                            (p.end_line for p in paragraphs if p.chapter_num == number), default=0
                        ),
                    }
                    for number, title, _body in (split_chapters(text, document) or [(1, "", text)])
                ]
                self._json(
                    {
                        "ok": True,
                        "schema_version": "lixity-speech-local/1",
                        "settings": settings,
                        "configuration_error": configuration_error,
                        "capabilities": audio_capabilities(),
                        "chapters": chapters,
                        "project_token": query["project_token"],
                        "source_sha256": digest,
                    }
                )
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_render(self, payload: dict[str, Any]) -> None:
        try:
            allowed = {
                "project_token",
                "source_sha256",
                "mode",
                "chapter",
                "profile",
                "profile_id",
                "paragraph",
            }
            if set(payload) - allowed or not {
                "project_token",
                "source_sha256",
                "mode",
                "chapter",
            } <= set(payload):
                raise ValueError("Supply selected audio scope, not browser text or paths")
            if "profile" in payload and "profile_id" in payload:
                raise ValueError("Choose a draft profile or a saved profile, not both")
            with self._workspace_lock:
                text, _digest, settings, key = self._speech_bound(payload)
                profile = (
                    AudioProfile.model_validate(payload["profile"])
                    if "profile" in payload
                    else resolve_audio_profile(
                        settings, payload.get("profile_id"), language=self.language
                    )
                )
                if payload.get("paragraph") is not None and not isinstance(
                    payload["paragraph"], dict
                ):
                    raise ValueError("Supply a displayed paragraph identity")
                prepared, context = prepare_speech_source(
                    text,
                    language=self.language,
                    mode=payload["mode"],
                    chapter=payload["chapter"],
                    paragraph=payload.get("paragraph"),
                    project_config=settings,
                )
                binding = {name: payload[name] for name in ("project_token", "source_sha256")}
                handler = type(self)
                generation = handler._speech_generation

                def valid() -> bool:
                    try:
                        with handler._workspace_lock:
                            if handler._speech_generation != generation:
                                return False
                            if (
                                project_settings_token(
                                    handler.get_author_project_root(), handler.source_input
                                )
                                != binding["project_token"]
                                or not handler.source_input
                            ):
                                return False
                            return bool(
                                FileUtils.read_source_snapshot(handler.source_input)[1]
                                == binding["source_sha256"]
                            )
                    except (OSError, ValueError):
                        return False

                job = self._speech_manager().start(key, prepared, profile, context, valid)
                self._json({"ok": True, "job": job}, 202)
        except (OSError, TypeError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_job(self, _query: Any = None) -> None:
        try:
            query = self._speech_query(job=True)
            with self._workspace_lock:
                _text, _digest, _settings, key = self._speech_bound(query)
                self._json({"ok": True, "job": self._speech_manager().status(query["id"], key)})
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_cancel(self, payload: dict[str, Any]) -> None:
        try:
            if set(payload) != {"project_token", "source_sha256", "id"} or not isinstance(
                payload["id"], str
            ):
                raise ValueError("Supply one selected speech job ID")
            with self._workspace_lock:
                _text, _digest, _settings, key = self._speech_bound(payload)
                self._json({"ok": True, "job": self._speech_manager().cancel(payload["id"], key)})
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_audio(self, _query: Any = None) -> None:
        try:
            query = self._speech_query(job=True)
            with self._workspace_lock:
                _text, _digest, _settings, key = self._speech_bound(query)
                data = self._speech_manager().audio(query["id"], key)
                self._send(
                    200,
                    data,
                    "audio/wav",
                    headers={"Content-Disposition": 'attachment; filename="lixity-reading.wav"'},
                )
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)
