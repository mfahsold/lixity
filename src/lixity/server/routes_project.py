"""Project lifecycle routes: browsing, creation, opening, loading and settings."""

from __future__ import annotations

import contextlib
import json
import os
import re
from bisect import insort
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import load_project_config, resolve_thresholds
from ..research import api as research_api
from ..research.repository import ResearchError
from ..style_fingerprint import FingerprintThresholds
from ..workspace import discover
from ..workspace_labels import WORKSPACE_LABELS
from ._base import ResponseMixin
from .constants import LANGUAGE_CHOICES
from .views import build_server_dashboard, sanitize_filename

MAX_TITLE = 500


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

            selected: list[tuple[int, str, str, str, str]] = []
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
                    insort(selected, (0 if kind == "directory" else 1, entry.name.casefold(),
                                      entry.name, entry.path, kind))
                    if len(selected) > 200:
                        selected.pop()
                        truncated = True
        except PermissionError:
            self._json({"ok": False, "message": "Directory is not readable"}, 403)
            return
        except (OSError, RuntimeError, ValueError):
            self._json({"ok": False, "message": "Invalid project path"}, 400)
            return

        self._json({
            "ok": True, "path": str(target),
            "parent": str(target.parent) if target.parent != target else None,
            "entries": [{"name": name, "path": path, "kind": kind}
                        for _, _, name, path, kind in selected],
            "truncated": truncated,
        })

    def _handle_settings(self, payload: dict[str, Any]) -> None:
        lang = str(payload.get("language") or self.language).strip().lower()
        if lang not in LANGUAGE_CHOICES:
            self._json({"ok": False, "message": f"Unknown language: {lang}"}, 400)
            return

        if "title" in payload:
            raw_title = payload.get("title")
            title = str(raw_title or "").strip() or None
            title_custom = title is not None
        else:
            title = self.title
            title_custom = self.title_custom

        try:
            z_mild = float(payload.get("z_mild", self.thresholds.z_mild))
            z_strong = float(payload.get("z_strong", self.thresholds.z_strong))
            fdr_q = float(payload.get("fdr_q", self.thresholds.fdr_q))
            flag_min = int(payload.get("flag_min_severity", self.thresholds.flag_min_severity))
            dim_thr = float(payload.get("dim_score_threshold", self.thresholds.dim_score_threshold))
        except (TypeError, ValueError):
            self._json({"ok": False, "message": "Invalid threshold parameter format"}, 400)
            return

        if (
            z_strong < z_mild
            or not (0.5 <= z_mild <= 6.0)
            or not (1.0 <= z_strong <= 8.0)
            or not (0.01 <= fdr_q <= 0.5)
            or flag_min not in (1, 2, 3)
            or not (1.0 <= dim_thr <= 4.0)
        ):
            self._json(
                {
                    "ok": False,
                    "message": "Thresholds out of bounds (z* 0.5–6.0, strong 1.0–8.0, q 0.01–0.5, flags 1–3, dim 1.0–4.0)",
                },
                400,
            )
            return

        self.__class__.language = lang
        self.__class__.title = title
        self.__class__.title_custom = title_custom
        self.__class__.thresholds = FingerprintThresholds(
            z_mild=z_mild,
            z_strong=z_strong,
            fdr_q=fdr_q,
            fdr_method=self.thresholds.fdr_method,
            min_chapters=self.thresholds.min_chapters,
            flag_min_severity=flag_min,
            dim_score_threshold=dim_thr,
        )
        self.refresh()
        self._json({
            "ok": True,
            "message": f"Settings applied · Language: {lang} · z* ≥ {z_mild:.1f} / {z_strong:.1f}",
            "reload": True,
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

        config_file = target_path / "lixity.toml"
        if not config_file.exists():
            cfg_text = f'title = {json.dumps(title, ensure_ascii=False)}\nlanguage = {json.dumps(lang)}\n'
            with contextlib.suppress(OSError):
                config_file.write_text(cfg_text, encoding="utf-8")

        if init_research:
            with contextlib.suppress(ResearchError, OSError, ValueError):
                research_api.init(target_path, title=title, language=lang)

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
            if target_path.is_file():
                if target_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
                    raise ValueError(
                        "Unsupported manuscript file type (use .md, .markdown, or .txt)"
                    )
                ws_root = str(target_path.parent)
                manuscript = str(target_path)
            elif target_path.is_dir():
                try:
                    ws = discover(root=str(target_path))
                except FileNotFoundError:
                    if not (target_path / "research").is_dir():
                        raise
                    research_api.list_sources(target_path)
                    ws_root = str(target_path)
                    manuscript = None
                else:
                    ws_root = ws.root
                    manuscript = ws.manuscript
            else:
                raise ValueError("Project path must be a folder or manuscript file")

            if manuscript is not None:
                # build_server_dashboard historically treats read errors as an
                # empty manuscript. Opening must fail before switching state.
                Path(manuscript).read_text(encoding="utf-8")

            settings = load_project_config(ws_root)
            overrides = self.project_open_overrides
            same_project = (
                bool(self.workspace_root)
                and Path(ws_root).resolve() == Path(self.workspace_root).resolve()
            )
            language = overrides.get("language", settings.get("language", "en"))
            if language not in LANGUAGE_CHOICES:
                raise ValueError(f"Unknown project language: {language}")
            title = overrides.get(
                "title", self.title if same_project and self.title_custom else settings.get("title")
            )
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
        self.__class__.title_custom = "title" in overrides or (same_project and self.title_custom)
        self.__class__.thresholds = thresholds
        self.__class__.dashboard_html = html
        self.__class__.dashboard_info = info

        self._json(
            {
                "ok": True,
                "message": f"Workspace loaded: {Path(manuscript).name if manuscript else Path(ws_root).name}",
                "workspace_root": ws_root,
                "manuscript": manuscript,
                "reload": True,
            }
        )
