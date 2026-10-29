"""Project-bound speech previews/jobs; browser prose and paths are never inputs."""

from __future__ import annotations

import hashlib
import threading
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import load_project_config
from ..io import FileUtils
from ..markdown_parser import split_chapters
from ..pipeline import document_paragraph_texts, resolve_document_config
from ..speech import MAX_SEGMENT_CHARS
from ..speech_cache import project_audio_cache
from ..speech_direction import (
    BaseDirectionConflict,
    Direction,
    build_speech_plan,
    direction_id,
    direction_snapshot,
    direction_state,
    plan_json,
    save_direction,
    saved_directions,
)
from ..speech_jobs import SpeechJobs, prepare_speech_source
from ..speech_profiles import (
    AudioProfile,
    audio_capabilities,
    parse_audio_settings,
    requires_audio_migration,
    resolve_audio_profile,
)
from ..speech_references import references_for_plan, references_unchanged
from ..speech_status import audio_status
from ..workspace_labels import WORKSPACE_LABELS
from ._base import ResponseMixin
from .pdf_context import project_settings_token


class _SpeechStale(ValueError):
    pass


class SpeechRoutesMixin(ResponseMixin):
    _speech_manager_lock = threading.Lock()

    def _speech_manager(self) -> SpeechJobs:
        with self._speech_manager_lock:
            manager = getattr(self.server, "speech_jobs", None)
            if not isinstance(manager, SpeechJobs):
                manager = SpeechJobs()
                self.server.speech_jobs = manager
            return manager

    def _speech_bound(self, supplied: dict[str, Any]) -> tuple[str, str, dict[str, Any], str]:
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
            (self.api_base + expected + digest + self.language + str(self._speech_generation)).encode()
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
        message = (WORKSPACE_LABELS.get(self.language, WORKSPACE_LABELS["en"])["speech_base_direction_conflict"]
                   if isinstance(exc, BaseDirectionConflict) else str(exc))
        self._json({"ok": False, "message": message}, code)

    @classmethod
    def _direction_view(cls) -> dict[str, Any]:
        root, source = cls.get_author_project_root(), cls.source_input
        if root is None or source is None:
            raise ValueError("Open a manuscript project before using direction")
        return direction_state(root, source, language=cls.language)

    def _handle_speech(self, _query: Any = None) -> None:
        try:
            query = self._speech_query()
            self._speech_manager().cancel_stale()
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
                response = {
                    "ok": True,
                    "schema_version": "lixity-speech-local/1",
                    "settings": settings,
                    "configuration_error": configuration_error,
                    "requires_migration": requires_audio_migration(config.get("audio")),
                    "capabilities": audio_capabilities(),
                    "direction": self._direction_view(),
                    "chapters": chapters,
                    "project_token": query["project_token"],
                    "source_sha256": digest,
                }
            # Probe fixed loopback endpoints without holding the workspace lock.
            # A worker status is a snapshot, not a promise of later readiness.
            response["workers"] = audio_status()["targets"]
            with self._workspace_lock:
                self._speech_bound(query)
                self._json(response)
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_direction(self, payload: dict[str, Any]) -> None:
        try:
            allowed = {"project_token", "source_sha256", "expected_settings_sha256", "expected_direction_sha256", "direction", "remove_id", "replace_id"}
            if set(payload) - allowed or not {"project_token", "source_sha256", "expected_settings_sha256", "expected_direction_sha256"} <= set(payload):
                raise ValueError("Supply the selected direction and its observed snapshots")
            with self._workspace_lock:
                self._speech_bound(payload)
                root, source = self.get_author_project_root(), self.source_input
                if root is None or source is None:
                    raise ValueError("Open a manuscript project before saving direction")
                result = save_direction(root, source, payload.get("direction"),
                    expected_source_sha256=payload["source_sha256"],
                    expected_settings_sha256=payload["expected_settings_sha256"],
                    expected_direction_sha256=payload["expected_direction_sha256"],
                    language=self.language, remove_id=payload.get("remove_id"), replace_id=payload.get("replace_id"))
            self._speech_manager().cancel_stale()
            self._json({"ok": True, "direction": result})
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            from ..research.repository import ResearchConflictError
            if isinstance(exc, ResearchConflictError):
                exc = _SpeechStale(str(exc))
            self._speech_error(exc)

    def _handle_speech_plan(self, payload: dict[str, Any]) -> None:
        self._handle_speech_render(payload, plan_only=True)

    def _handle_speech_render(self, payload: dict[str, Any], *, plan_only: bool = False) -> None:
        try:
            allowed = {
                "project_token",
                "source_sha256",
                "mode",
                "chapter",
                "profile",
                "profile_id",
                "fresh_audio",
                "target",
                "paragraph",
                "draft_direction",
                "draft_replace_id",
                "ignore_direction",
            }
            if set(payload) - allowed or not {
                "project_token",
                "source_sha256",
                "mode",
                "chapter",
            } <= set(payload):
                raise ValueError("Supply selected audio scope, not browser text or paths")
            if payload.get("target", "local") not in ("local", "jetson"):
                raise ValueError("Unknown speech execution target")
            if type(payload.get("fresh_audio", False)) is not bool:
                raise ValueError("Fresh audio must be a boolean")
            if "profile" in payload and "profile_id" in payload:
                raise ValueError("Choose a draft profile or a saved profile, not both")
            self._speech_manager().cancel_stale()
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
                view = self._direction_view()
                if type(payload.get("ignore_direction", False)) is not bool:
                    raise ValueError("Ignore direction must be a boolean")
                directions = [] if payload.get("ignore_direction") else saved_directions(view)
                if "draft_replace_id" in payload and "draft_direction" not in payload:
                    raise ValueError("Draft replacement requires a direction")
                if "draft_direction" in payload:
                    if payload["mode"] != "preview":
                        raise ValueError("Save passage direction before rendering a chapter")
                    draft = Direction.model_validate(payload["draft_direction"])
                    replacement = payload.get("draft_replace_id", direction_id(draft))
                    if "draft_replace_id" in payload and not any(direction_id(d) == replacement for d in directions):
                        raise ValueError("Choose an existing direction to replace")
                    directions = [d for d in directions if direction_id(d) != replacement] + [draft]
                profiles = parse_audio_settings(settings.get("audio"), language=self.language).profiles
                plan = build_speech_plan(text, profile, directions=directions, profiles=profiles,
                                         chapter=payload["chapter"], project_config=settings)
                if payload["mode"] == "preview":
                    selected = payload.get("paragraph")
                    if not selected:
                        selected = next((row.anchor for row in plan if row.anchor), None)
                    if selected is None:
                        raise ValueError("No anchored paragraph or list item found at the selected line or chapter; quote blocks cannot currently be selected for preview")
                    plan = [row for row in plan if row.anchor == selected]
                    if not plan:
                        raise ValueError("Choose a displayed spoken paragraph")
                    passage = next((item["text"] for item in view["passages"] if item["anchor"] == selected), None)
                    if passage is None:
                        raise ValueError("The selected passage changed; choose it again")
                    context["excerpt"] = (passage[:MAX_SEGMENT_CHARS].rstrip() + "…"
                                          if len(passage) > MAX_SEGMENT_CHARS else passage)
                    context["truncated"] = False
                    if sum(len(row.text) for row in plan) > 6000:
                        raise ValueError("Passage preview exceeds 6000 characters; render the chapter")
                context["direction_sha256"] = view["direction_sha256"]
                root = self.get_author_project_root()
                if root is None:
                    raise ValueError("Open a manuscript project before using audio")
                references = references_for_plan(root, plan)
                if plan_only:
                    self._json({"ok": True, "plan": plan_json(plan), "context": context})
                    return
                binding = {name: payload[name] for name in ("project_token", "source_sha256")}
                handler = type(self)
                registry = getattr(self.server, "workspaces", None)
                generation = handler._speech_generation

                def valid() -> bool:
                    try:
                        if registry is not None and not registry.contains(handler):
                            return False
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
                            root = handler.get_author_project_root()
                            if (root is None or direction_snapshot(root) != view["direction_sha256"]
                                    or not references_unchanged(root, references)):
                                return False
                            return bool(
                                FileUtils.read_source_snapshot(handler.source_input)[1]
                                == binding["source_sha256"]
                            )
                    except (OSError, ValueError):
                        return False

                cache_dir = (project_audio_cache(root) if root is not None and
                             profile.engine in ("qwen3", "qwen3-design", "qwen3-base") and payload["mode"] == "chapter" else None)
            reference_options = {"references": references} if references else {}
            job = self._speech_manager().start(key, prepared, profile, context, valid, cache_dir=cache_dir,
                                               fresh_audio=payload.get("fresh_audio", False),
                                               target=payload.get("target", "local"), plan=plan, **reference_options)
            self._json({"ok": True, "job": job}, 202)
        except (OSError, TypeError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_job(self, _query: Any = None) -> None:
        try:
            query = self._speech_query(job=True)
            self._speech_manager().cancel_stale()
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
            self._speech_manager().cancel_stale()
            with self._workspace_lock:
                _text, _digest, _settings, key = self._speech_bound(payload)
                self._json({"ok": True, "job": self._speech_manager().cancel(payload["id"], key)})
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            self._speech_error(exc)

    def _handle_speech_audio(self, _query: Any = None) -> None:
        try:
            query = self._speech_query(job=True)
            self._speech_manager().cancel_stale()
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
