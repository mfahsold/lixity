"""Project lifecycle routes: browsing, creation, opening, loading and settings."""

from __future__ import annotations

import json
import os
import re
import warnings
from bisect import insort
from dataclasses import replace
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import (
    ANALYSIS_SETTINGS_KEYS,
    PERSISTED_SETTINGS_KEYS,
    apply_config_to_thresholds,
    load_project_config,
    prepare_project_settings,
    read_project_config,
    resolve_thresholds,
    validate_author_name,
    validate_project_title,
)
from ..research import api as research_api
from ..research.repository import Repository, ResearchError
from ..workspace import resolve_project_target
from ..workspace_labels import WORKSPACE_LABELS
from ._base import ResponseMixin
from .constants import LANGUAGE_CHOICES
from .pdf_context import project_settings_token
from .views import build_server_dashboard, sanitize_filename


def _project_markers(directory: Path) -> bool:
    """Cheap marker check used while listing one directory level."""
    try:
        return (directory / "lixity.toml").is_file() or (directory / "research" / "HEAD.json").is_file()
    except OSError:
        return False


def _project_probe(directory: Path) -> dict[str, Any]:
    """Minimal read-only detection: config, research archive, title, language."""
    try:
        config = (directory / "lixity.toml").is_file()
        research = (directory / "research" / "HEAD.json").is_file()
    except OSError:
        config = research = False
    probe: dict[str, Any] = {"detected": bool(config or research), "config": config,
                             "research": research, "title": None, "language": None}
    if config:
        settings = read_project_config(directory)
        title = settings.get("title")
        language = settings.get("language")
        if isinstance(title, str) and title.strip():
            probe["title"] = title.strip()[:200]
        if isinstance(language, str) and language in LANGUAGE_CHOICES:
            probe["language"] = language
    return probe


class ProjectRoutesMixin(ResponseMixin):
    """Handlers for the non-research workspace actions."""

    def _handle_project_paths(self) -> None:
        """List one local directory level for the Open Project chooser."""
        requested = parse_qs(urlparse(self.path).query, keep_blank_values=True).get("path", [""])[0]
        try:
            target = Path(requested).expanduser().resolve() if requested else Path.home().resolve()
            if not target.exists():
                self._json({"ok": False, "message": "Path does not exist"}, 404)
                return
            if target.is_file():
                if target.suffix.lower() not in {".md", ".markdown", ".txt"}:
                    self._json({"ok": False, "message": "Unsupported manuscript file type"}, 400)
                    return
                target = target.parent
            if not target.is_dir():
                self._json({"ok": False, "message": "Path is not a directory"}, 400)
                return

            selected: list[tuple[int, str, str, str, str, bool]] = []
            manuscripts: list[str] = []
            truncated = False
            with os.scandir(target) as iterator:
                for entry in iterator:
                    if entry.name.startswith("."):
                        continue
                    try:
                        entry.name.encode("utf-8")
                    except UnicodeEncodeError:
                        # POSIX undecodable byte names cannot round-trip through
                        # the browser's UTF-8 URL and JSON path contract.
                        continue
                    try:
                        if entry.is_dir():
                            kind = "directory"
                        elif entry.is_file() and Path(entry.name).suffix.lower() in {".md", ".markdown", ".txt"}:
                            kind = "manuscript"
                        else:
                            continue
                    except OSError:
                        # A broken or inaccessible entry should not hide the
                        # rest of an otherwise readable directory.
                        continue
                    is_project = _project_markers(Path(entry.path)) if kind == "directory" else False
                    if kind == "manuscript":
                        manuscripts.append(entry.name)
                    insort(selected, (0 if kind == "directory" else 1, entry.name.casefold(),
                                      entry.name, entry.path, kind, is_project))
                    if len(selected) > 200:
                        selected.pop()
                        truncated = True
        except PermissionError:
            self._json({"ok": False, "message": "Directory is not readable"}, 403)
            return
        except (OSError, RuntimeError, ValueError):
            self._json({"ok": False, "message": "Invalid project path"}, 400)
            return

        probe = _project_probe(target)
        probe["manuscript"] = sorted(manuscripts, key=str.casefold)[0] if manuscripts else None
        probe["manuscripts"] = len(manuscripts)
        self._json({
            "ok": True, "path": str(target),
            "parent": str(target.parent) if target.parent != target else None,
            "project": probe,
            "entries": [
                {"name": name, "path": path, "kind": kind,
                 **({"project": project} if kind == "directory" else {})}
                for _, _, name, path, kind, project in selected
            ],
            "truncated": truncated,
        })

    def _handle_settings(self, payload: dict[str, Any]) -> None:
        save_defaults = payload.get("save_analysis_defaults", False)
        if not isinstance(save_defaults, bool):
            self._json({"ok": False, "message": "save_analysis_defaults must be a boolean"}, 400)
            return
        if save_defaults and "language" in payload and (
                not isinstance(payload["language"], str) or not payload["language"].strip()):
            self._json({"ok": False, "message": "language must be a supported language code"}, 400)
            return
        lang = str(payload.get("language") or self.language).strip().lower()
        if lang not in LANGUAGE_CHOICES:
            self._json({"ok": False, "message": f"Unknown language: {lang}"}, 400)
            return

        try:
            root = self.get_author_project_root()
            current_token = project_settings_token(root, self.source_input)
            if (save_defaults or any(key in payload for key in (
                    "publication", "register_profiles", "chapter_registers", "site_publications", "project_token"))) and (
                    not current_token or payload.get("project_token") != current_token):
                self._json({"ok": False, "message": "The selected project or its settings changed; reload before saving"}, 409)
                return
            title = validate_project_title(payload["title"]) or None if "title" in payload else self.title
            title_custom = title is not None if "title" in payload else self.title_custom
            thresholds = replace(self.thresholds, **apply_config_to_thresholds(payload))
            changes: dict[str, Any] = {key: payload[key] for key in PERSISTED_SETTINGS_KEYS if key in payload}
            if save_defaults:
                changes.update({key: lang if key == "language" else payload[key]
                                for key in ANALYSIS_SETTINGS_KEYS if key in payload})
            if root is None:
                changes.pop("title", None)
            prepared = prepare_project_settings(root, changes) if changes else None
            if "project_token" in payload and project_settings_token(root, self.source_input) != current_token:
                self._json({"ok": False, "message": "Project settings changed while preparing; reload before saving"}, 409)
                return
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=UserWarning, module=r"lixity\.config")
                html, info = build_server_dashboard(
                    self.source_input, language=lang, title=title, thresholds=thresholds,
                    controls=True, api_base="/api", exports_dir=self.exports_dir, debug=self.debug,
                    project_root=root, research_root=self.get_research_root(),
                    identity_settings_override=changes,
                    project_config_bytes=prepared.content if prepared else None,
                    strict_source=True,
                )
            if prepared:
                prepared.commit()
        except (OSError, TypeError, ValueError, RuntimeError, UserWarning) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
            return

        self.__class__.language = lang
        self.__class__.title = title
        self.__class__.title_custom = title_custom
        self.__class__.thresholds = thresholds
        self.publish_dashboard(html, info)
        self._json({
            "ok": True,
            "message": f"Settings applied · Language: {lang} · z* ≥ {thresholds.z_mild:.1f} / {thresholds.z_strong:.1f}",
            "reload": True,
            "project_token": project_settings_token(root, self.source_input),
        })

    def _handle_load(self, payload: dict[str, Any]) -> None:
        name = sanitize_filename(payload.get("name"))
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            self._json({"ok": False, "message": "Empty or missing manuscript content"}, 400)
            return

        target_dir = os.path.join(self.exports_dir, "manuscripts")
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, name)
        try:
            with open(target, "x", encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            self._json({"ok": False, "message": "A loaded manuscript with this filename already exists. Choose a different filename or open the existing project."}, 409)
            return
        except OSError as exc:
            self._json({"ok": False, "message": f"Failed to save manuscript: {exc}"}, 500)
            return

        self.__class__.source_input = target
        if not self.title_custom:
            self.__class__.title = None
        self.refresh()
        info = self.dashboard_info
        self._json({
            "ok": True,
            "message": f"Manuscript loaded: {name} · {info.get('chapters')} chapters",
            "reload": True,
        })

    def _handle_project_create(self, payload: dict[str, Any]) -> None:
        title = str(payload.get("title") or "Untitled Project").strip()
        lang = str(payload.get("language") or self.language or "en").strip().lower()
        if lang not in LANGUAGE_CHOICES and lang != "auto":
            lang = "en"
        if lang == "auto":
            lang = "en"

        author_value = ""
        author_input = payload.get("author_name")
        if isinstance(author_input, str) and author_input.strip():
            try:
                author_value = validate_author_name(author_input)
            except ValueError as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
                return

        folder_input = str(payload.get("path") or "").strip()
        if folder_input:
            target_path = Path(folder_input).expanduser().resolve()
        else:
            slug = re.sub(r"[^\w\-]+", "-", title.lower()).strip("-") or "new-project"
            base_dir = Path(self.workspace_root).resolve() if self.workspace_root else Path.cwd()
            target_path = base_dir / slug

        try:
            target_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._json({"ok": False, "message": f"Failed to create directory {target_path}: {exc}"}, 500)
            return

        template_key = str(payload.get("template") or "minimal").strip().lower()
        init_research = bool(payload.get("init_research", False) or template_key == "research")

        manuscript_file = target_path / "manuscript.md"
        custom_content = payload.get("content")
        if custom_content and isinstance(custom_content, str) and custom_content.strip():
            if manuscript_file.exists():
                self._json({"ok": False, "message": "A manuscript already exists here. Open the project or choose a new import folder."}, 409)
                return
            try:
                manuscript_file.write_text(custom_content, encoding="utf-8", newline="")
            except OSError as exc:
                self._json({"ok": False, "message": f"Failed to write manuscript: {exc}"}, 500)
                return
        elif not manuscript_file.exists():
            template_labels = WORKSPACE_LABELS.get(lang, WORKSPACE_LABELS["en"])
            if template_key == "three_act":
                sections = [(f"template_act_{act}", f"template_act_{act}_body") for act in ("one", "two", "three")]
            elif template_key == "research":
                sections = [("template_research_chapter", "template_research_body")]
            else:
                sections = [("template_minimal_chapter", "template_minimal_body")]
            ms_content = f"# {title}\n\n" + "\n\n".join(
                f"## {template_labels[heading]}\n\n{template_labels[body]}" for heading, body in sections
            ) + "\n"

            try:
                manuscript_file.write_text(ms_content, encoding="utf-8")
            except OSError as exc:
                self._json({"ok": False, "message": f"Failed to write manuscript: {exc}"}, 500)
                return

        try:
            configuration = prepare_project_settings(target_path, {})
            if configuration.original[0] is None:
                cfg_lines = [f'title = {json.dumps(title, ensure_ascii=False)}',
                             f'language = {json.dumps(lang)}']
                if author_value:
                    cfg_lines.append(f'author_name = {json.dumps(author_value, ensure_ascii=False)}')
                # Keep creation's existing title encoding; metadata edits have
                # stricter title validation. Reuse its guarded atomic commit.
                replace(configuration, content=("\n".join(cfg_lines) + "\n").encode("utf-8")).commit()
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "message": (
                f"Project setup incomplete: could not read or save configuration: {exc}. "
                f"Files in {target_path} were retained. Save lixity.toml there, "
                "then use Open Project to continue."
            )}, 500 if isinstance(exc, OSError) else 400)
            return

        if init_research:
            try:
                if (target_path / "research").exists():
                    Repository(target_path).snapshot()
                else:
                    research_api.init(target_path, title=title, language=lang)
            except (ResearchError, OSError, ValueError) as exc:
                self._research_error(exc, 500 if isinstance(exc, OSError) else 400, message=(
                    f"Project setup incomplete: could not initialize or open Research: {exc}. "
                    f"Files in {target_path} were retained. Correct the Research setup, "
                    "then use Open Project and initialize Research if needed."
                ))
                return

        self.__class__.workspace_root = str(target_path)
        self.__class__.source_input = str(manuscript_file)
        self.__class__.exports_dir = str(target_path / "exports")
        self.__class__.research_dir = str(target_path) if (target_path / "research").is_dir() else None
        self.__class__.language = lang
        self.__class__.title = title
        # A newly created project's title belongs to its config, not to the
        # server session; a later open must load the next project's title.
        self.__class__.title_custom = False
        self.refresh()

        self._json({
            "ok": True,
            "message": f"Project '{title}' created and loaded",
            "path": str(target_path),
            "manuscript": str(manuscript_file),
            "reload": True,
        })

    def _handle_project_open(self, payload: dict[str, Any]) -> None:
        target_raw = str(payload.get("path") or "").strip()
        if not target_raw:
            self._json({"ok": False, "message": "Project or manuscript path is required"}, 400)
            return

        try:
            target_path = Path(target_raw).expanduser().resolve()
        except (OSError, RuntimeError) as exc:
            self._json({"ok": False, "message": f"Invalid project path: {exc}"}, 400)
            return
        if not target_path.exists():
            self._json({"ok": False, "message": f"Path does not exist: {target_path}"}, 404)
            return

        try:
            if target_path.is_file() and target_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
                raise ValueError(
                    "Unsupported manuscript file type (use .md, .markdown, or .txt)"
                )
            target = resolve_project_target(target_path, empty="research")
            ws_root, manuscript = target.root, target.manuscript
            if target.research_only:
                research_api.list_sources(target_path)

            settings = load_project_config(ws_root)
            overrides = self.project_open_overrides
            same_project = (
                bool(self.workspace_root)
                and Path(ws_root).resolve() == Path(self.workspace_root).resolve()
            )
            language = overrides.get("language", settings.get("language", "en"))
            if language not in LANGUAGE_CHOICES:
                raise ValueError(f"Unknown project language: {language}")
            # Titles identify a project; startup/session titles must not label a different book or NDA.
            title = self.title if same_project and self.title_custom else settings.get("title")
            thresholds = resolve_thresholds(
                project_config=settings,
                **{
                    key: overrides[key]
                    for key in (
                        "z_mild",
                        "z_strong",
                        "fdr_q",
                        "fdr_method",
                        "min_chapters",
                        "dim_score_threshold",
                        "flag_min_severity",
                    )
                    if key in overrides
                },
            )
            exports_dir = str(Path(ws_root) / "exports")
            html, info = build_server_dashboard(
                manuscript,
                language=language,
                title=title,
                thresholds=thresholds,
                controls=True,
                api_base="/api",
                exports_dir=exports_dir,
                project_root=ws_root,
                research_root=ws_root,
                strict_source=True,
            )
        except (
            OSError,
            UnicodeError,
            FileNotFoundError,
            ValueError,
            TypeError,
            ResearchError,
        ) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
            return

        self.__class__.workspace_root = ws_root
        self.__class__.source_input = manuscript
        self.__class__.exports_dir = exports_dir
        self.__class__.research_dir = (
            str(Path(ws_root)) if (Path(ws_root) / "research").is_dir() else None
        )
        self.__class__.language = language
        self.__class__.title = title
        self.__class__.title_custom = same_project and self.title_custom
        self.__class__.thresholds = thresholds
        self.publish_dashboard(html, info)

        self._json(
            {
                "ok": True,
                "message": f"Workspace loaded: {Path(manuscript).name if manuscript else Path(ws_root).name}",
                "workspace_root": ws_root,
                "manuscript": manuscript,
                "reload": True,
            }
        )
