"""lixity.server – Native HTTP development server and interactive dashboard.

Runs a loopback-only (127.0.0.1 / localhost) HTTP service that serves the
interactive Lixity dashboard, provides live metrics and style analysis,
handles settings and threshold tuning, supports uploading manuscripts,
and serves generated export artifacts.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import webbrowser
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

from .characters import presence_report
from .config import load_project_config, resolve_thresholds
from .dialogue import dialogue_report
from .io import FileUtils
from .markers import add_marker, list_markers, resolve_marker
from .motifs import motif_report
from .pacing import pacing_report
from .pipeline import analyze_document, resolve_document_config
from .research import api as research_api
from .research.repository import ResearchError
from .showing import showing_report
from .style_fingerprint import FingerprintThresholds
from .ui import render_dashboard
from .workspace import discover

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_PORT = 8765
DEFAULT_HOST = "127.0.0.1"
LANGUAGE_CHOICES = ("auto", "de", "en", "fr", "es", "it", "pt", "nl", "generic")

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".pdf": "application/pdf",
    ".epub": "application/epub+zip",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


def sanitize_filename(raw: str | None) -> str:
    """Sanitizes a manuscript file name to prevent directory traversal."""
    name = os.path.basename(str(raw or "").strip())
    if not re.match(r"^[\w.\- ()äöüÄÖÜß]+\.(md|markdown|txt)$", name, re.IGNORECASE):
        return "manuscript.md"
    return name


def collect_artifacts(exports_dir: str) -> list[dict[str, Any]]:
    """Collects export artifacts from the given directory safely."""
    artifacts: list[dict[str, Any]] = []
    if not os.path.isdir(exports_dir):
        return artifacts
    try:
        entries = sorted(os.listdir(exports_dir))
    except OSError:
        return artifacts

    for name in entries:
        path = os.path.join(exports_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in (".pdf", ".epub", ".html", ".json"):
            try:
                size_kb = os.path.getsize(path) / 1024.0
            except OSError:
                size_kb = 0.0
            artifacts.append({
                "name": name,
                "size_kb": size_kb,
                "href": name,
            })
    return artifacts


def build_server_dashboard(
    source_input: str | None,
    language: str = "auto",
    title: str | None = None,
    thresholds: FingerprintThresholds | None = None,
    controls: bool = True,
    api_base: str = "/api",
    exports_dir: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Generates the interactive dashboard HTML and returns (html, info_dict)."""
    text = ""
    is_empty = True
    manuscript_name = ""

    if source_input and os.path.isfile(source_input):
        try:
            with open(source_input, encoding="utf-8") as f:
                text = f.read()
            is_empty = not text.strip()
            manuscript_name = os.path.basename(source_input)
        except OSError:
            text = ""

    doc_title = title or (
        os.path.splitext(manuscript_name)[0]
        if manuscript_name
        else ("No Project Loaded" if language != "de" else "Kein Projekt geladen")
    )

    settings = load_project_config(source_input) if source_input and os.path.isfile(source_input) else {}
    config_kwargs: dict[str, Any] = {
        key: settings[key]
        for key in ("chapter_regex", "appendix_marker", "min_paragraph_length_for_oneliner")
        if key in settings
    }
    config_kwargs["language"] = language

    config, resolved = resolve_document_config(text, **config_kwargs)
    resolved_thresholds = thresholds or resolve_thresholds(project_config=settings)

    analysis = analyze_document(text, config, resolved_thresholds)
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    metrics, fingerprint = analysis.metrics, analysis.fingerprint
    markers = list_markers(text) if text else []

    artifacts = collect_artifacts(exports_dir) if exports_dir else []
    names = settings.get("names", [])

    status_items = [
        {
            "key": "manuscript",
            "state": "ok" if manuscript_name else "unknown",
            "detail": manuscript_name or (
                "none loaded" if resolved.key != "de" else "kein Manuskript geladen"
            ),
        },
        {
            "key": "analysis",
            "state": "ok" if chapters else "warn",
            "detail": f"{len(chapters)} chapters · {len(paragraphs)} paragraphs · {resolved.name}"
            if resolved.key != "de"
            else f"{len(chapters)} Kapitel · {len(paragraphs)} Absätze · {resolved.name}",
        },
        {
            "key": "exports",
            "state": "ok" if artifacts else "warn",
            "detail": f"{len(artifacts)} files"
            if resolved.key != "de"
            else f"{len(artifacts)} Dateien",
        },
        {
            "key": "markers",
            "state": "warn" if any(m.kind for m in markers) else "ok",
            "detail": f"{sum(1 for m in markers if m.kind)} open"
            if resolved.key != "de"
            else f"{sum(1 for m in markers if m.kind)} offen",
        },
    ]

    html_doc = render_dashboard(
        chapters,
        paragraphs,
        status=status_items,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, names, config) if names else None,
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, settings.get("motifs", {}), config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        metrics=metrics,
        fingerprint=fingerprint,
        markers=markers,
        artifacts=artifacts,
        title=doc_title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        tense_available=bool(resolved.praesens_regex and resolved.praeteritum_regex),
        controls=controls,
        api_base=api_base,
        manuscript_name=manuscript_name,
        current_language=language,
        flag_min_severity=resolved_thresholds.flag_min_severity,
    )

    info = {
        "chapters": len(chapters),
        "paragraphs": len(paragraphs),
        "flagged": sum(1 for p in paragraphs if p.severity >= resolved_thresholds.flag_min_severity),
        "artifacts": len(artifacts),
        "markers": len(markers),
        "language": resolved.name,
        "language_key": resolved.key,
        "is_empty": is_empty,
    }
    return html_doc, info


class LixityServerHandler(BaseHTTPRequestHandler):
    """Loopback HTTP request handler for the Lixity dashboard and action API."""

    server_version = "LixityServer/1.0"
    source_input: str | None = None
    workspace_root: str = ""
    exports_dir: str = ""
    research_dir: str | None = None
    language: str = "auto"
    title: str | None = None
    title_custom: bool = False
    thresholds: FingerprintThresholds = FingerprintThresholds()
    dashboard_html: str = ""
    dashboard_info: ClassVar[dict[str, Any]] = {}

    @classmethod
    def get_research_root(cls) -> Path | None:
        """Resolves the active research project root if one exists."""
        if cls.research_dir:
            p = Path(cls.research_dir).expanduser().resolve()
            return p if p.is_dir() else None
        if cls.workspace_root:
            p = Path(cls.workspace_root).resolve()
            if (p / "research").is_dir():
                return p
        return None

    @classmethod
    def refresh(cls) -> None:
        """Re-analyzes the active manuscript and updates cached dashboard HTML."""
        cls.dashboard_html, cls.dashboard_info = build_server_dashboard(
            cls.source_input,
            language=cls.language,
            title=cls.title,
            thresholds=cls.thresholds,
            controls=True,
            api_base="/api",
            exports_dir=cls.exports_dir,
        )

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: Mapping[str, Any], code: int = 200) -> None:
        self._send(
            code,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _trusted_host(self) -> bool:
        host = self.headers.get("Host", "")
        server_port = getattr(self.server, "server_port", DEFAULT_PORT)
        allowed = {f"127.0.0.1:{server_port}", f"localhost:{server_port}", "127.0.0.1", "localhost"}
        return host in allowed

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._json({"ok": False, "message": "Untrusted Host forbidden"}, 403)
            return

        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, self.dashboard_html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path.startswith("/artifact/"):
            raw_name = path[len("/artifact/"):].strip("/")
            name = os.path.basename(raw_name)
            target = os.path.realpath(os.path.join(self.exports_dir, name))
            real_exports = os.path.realpath(self.exports_dir)
            if not target.startswith(real_exports + os.sep) or not os.path.isfile(target):
                self._json({"ok": False, "message": "Artifact not found"}, 404)
                return

            ext = os.path.splitext(target)[1].lower()
            ctype = MIME_TYPES.get(ext, "application/octet-stream")
            try:
                with open(target, "rb") as f:
                    content = f.read()
                self._send(200, content, ctype)
            except OSError:
                self._json({"ok": False, "message": "Failed to read artifact"}, 500)
            return

        if path == "/api/research/status":
            self._handle_research_status()
            return

        if path == "/api/research/sources":
            self._handle_research_sources()
            return

        if path == "/api/research/dossiers":
            self._handle_research_dossiers()
            return

        self._json({"ok": False, "message": "Not found"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            self._json({"ok": False, "message": "Not found"}, 404)
            return

        if not self._trusted_host():
            self._json({"ok": False, "message": "Untrusted Host forbidden"}, 403)
            return

        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin is not None and origin not in (f"http://{host}", f"https://{host}"):
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            self._json({"ok": False, "message": "Content-Type application/json required"}, 415)
            return

        if self.headers.get("Transfer-Encoding"):
            self._json({"ok": False, "message": "Transfer-Encoding not supported"}, 400)
            return

        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json({"ok": False, "message": "Invalid Content-Length"}, 400)
            return

        if not 0 <= length <= MAX_PAYLOAD_BYTES:
            self._json({"ok": False, "message": "Payload too large or invalid"}, 413)
            return

        self.connection.settimeout(15)
        try:
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
        except (ValueError, UnicodeError, TimeoutError):
            self._json({"ok": False, "message": "Invalid JSON body"}, 400)
            return

        action = path[len("/api/"):].strip("/")

        if action == "rebuild":
            try:
                self.refresh()
                self._json({"ok": True, "message": "Dashboard rebuilt", "reload": True})
            except (OSError, ValueError, RuntimeError) as exc:
                self._json({"ok": False, "message": str(exc)}, 500)
            return

        if action == "settings":
            self._handle_settings(payload)
            return

        if action == "load":
            self._handle_load(payload)
            return

        if action == "project-create":
            self._handle_project_create(payload)
            return

        if action == "project-open":
            self._handle_project_open(payload)
            return

        if action.startswith("marker-"):
            self._handle_marker(action, payload)
            return

        if action in ("export", "analyze", "sync", "audit", "prune"):
            # Acknowledge UI triggers gracefully
            self.refresh()
            self._json({"ok": True, "message": f"Action '{action}' executed", "reload": True})
            return

        if action == "research-init":
            self._handle_research_init(payload)
            return

        if action == "research-ingest":
            self._handle_research_ingest(payload)
            return

        if action == "research-search":
            self._handle_research_search(payload)
            return

        if action == "research-dossier":
            self._handle_research_dossier(payload)
            return

        if action == "research-compare":
            self._handle_research_compare(payload)
            return

        self._json({"ok": False, "message": f"Unknown action: {action}"}, 400)

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
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
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
            try:
                manuscript_file.write_text(custom_content.strip() + "\n", encoding="utf-8")
            except OSError as exc:
                self._json({"ok": False, "message": f"Failed to write manuscript: {exc}"}, 500)
                return
        elif not manuscript_file.exists():
            if template_key == "three_act":
                if lang == "de":
                    ms_content = (
                        f"# {title}\n\n"
                        "## Erster Akt: Aufbruch\n\n"
                        "Die gewohnte Welt wird vorgestellt. Ein auslösendes Ereignis stellt die Hauptfiguren vor eine Entscheidung.\n\n"
                        "## Zweiter Akt: Konfrontation\n\n"
                        "Herausforderungen, Konflikte und Rückschläge in der neuen Welt. Die Spannung steigt bis zum Wendepunkt.\n\n"
                        "## Dritter Akt: Rückkehr\n\n"
                        "Der Höhepunkt, die finale Entscheidung und die Auflösung der offenen Fäden.\n"
                    )
                else:
                    ms_content = (
                        f"# {title}\n\n"
                        "## Act I: Departure\n\n"
                        "The ordinary world is established. An inciting incident forces the protagonist to make a fateful choice.\n\n"
                        "## Act II: Confrontation\n\n"
                        "Rising obstacles, conflicts, and trials in an unfamiliar world leading to the crucial midpoint.\n\n"
                        "## Act III: Resolution\n\n"
                        "The climax, final showdown, and resolution bringing new perspective and transformation.\n"
                    )
            elif template_key == "research":
                if lang == "de":
                    ms_content = (
                        f"# {title}\n\n"
                        "## Kapitel 1: Grundlagen und Spuren\n\n"
                        "Jede Untersuchung beginnt mit einer Frage. Die ersten Quellen geben Zeugnis von Ereignissen, die lange im Verborgenen lagen.\n"
                    )
                else:
                    ms_content = (
                        f"# {title}\n\n"
                        "## Chapter 1: Foundations\n\n"
                        "Every investigation begins with a question. The earliest accounts testify to events long kept in the shadows.\n"
                    )
            else:
                if lang == "de":
                    ms_content = (
                        f"# {title}\n\n"
                        "## Kapitel 1\n\n"
                        "Hier beginnt die Geschichte. Schreiben Sie Ihre ersten Sätze oder fügen Sie Ihr Manuskript ein.\n"
                    )
                else:
                    ms_content = (
                        f"# {title}\n\n"
                        "## Chapter 1\n\n"
                        "The story begins here. Write your opening lines or paste your manuscript content.\n"
                    )

            try:
                manuscript_file.write_text(ms_content, encoding="utf-8")
            except OSError as exc:
                self._json({"ok": False, "message": f"Failed to write manuscript: {exc}"}, 500)
                return

        config_file = target_path / "lixity.toml"
        if not config_file.exists():
            cfg_text = f'[project]\ntitle = "{title}"\nlanguage = "{lang}"\n'
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
        self.__class__.title_custom = True
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

        target_path = Path(target_raw).expanduser().resolve()
        if not target_path.exists():
            self._json({"ok": False, "message": f"Path does not exist: {target_path}"}, 404)
            return

        try:
            if target_path.is_file():
                ws_root = str(target_path.parent)
                manuscript = str(target_path)
            else:
                ws = discover(root=str(target_path))
                ws_root = ws.root
                manuscript = ws.manuscript
        except (FileNotFoundError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
            return

        self.__class__.workspace_root = ws_root
        self.__class__.source_input = manuscript
        self.__class__.exports_dir = str(Path(ws_root) / "exports")
        self.__class__.research_dir = str(Path(ws_root)) if (Path(ws_root) / "research").is_dir() else None
        if not self.title_custom:
            self.__class__.title = None
        self.refresh()

        self._json({
            "ok": True,
            "message": f"Workspace loaded: {Path(manuscript).name}",
            "workspace_root": ws_root,
            "manuscript": manuscript,
            "reload": True,
        })

    def _handle_marker(self, action: str, payload: dict[str, Any]) -> None:
        src = self.source_input
        if not src or not os.path.isfile(src):
            self._json({"ok": False, "message": "No writable manuscript loaded"}, 400)
            return

        try:
            with open(src, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            self._json({"ok": False, "message": f"Failed to read manuscript: {exc}"}, 500)
            return

        if action == "marker-add":
            kind = str(payload.get("kind") or "pruefen").strip().lower()
            try:
                line = int(payload.get("line") or 0)
            except ValueError:
                line = 0
            note = str(payload.get("note") or "").strip()
            if line < 1:
                self._json({"ok": False, "message": "Valid line number required"}, 400)
                return

            new_text, marker = add_marker(text, kind, note, line)
            FileUtils.atomic_write_if_changed(src, new_text)
            self.refresh()
            self._json({
                "ok": True,
                "message": f"Marker added: {marker.id} ({kind}) before line {line}",
                "reload": True,
            })
            return

        if action == "marker-resolve":
            marker_id = str(payload.get("id") or "").strip()
            if not marker_id:
                self._json({"ok": False, "message": "Marker ID missing"}, 400)
                return

            new_text = resolve_marker(text, marker_id)
            FileUtils.atomic_write_if_changed(src, new_text)
            self.refresh()
            self._json({"ok": True, "message": f"Marker {marker_id} resolved", "reload": True})
            return

        self._json({"ok": False, "message": f"Unknown marker action: {action}"}, 400)

    def _handle_research_status(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({
                "ok": True,
                "initialized": False,
                "project_root": str(root or self.workspace_root or ""),
            })
            return
        try:
            src_data = research_api.list_sources(root)
            dos_data = research_api.list_dossiers(root)
            self._json({
                "ok": True,
                "initialized": True,
                "project_root": str(root),
                "project_id": src_data.get("project_id", ""),
                "project_title": src_data.get("project_title", ""),
                "project_language": src_data.get("project_language", ""),
                "sources": src_data.get("sources", []),
                "dossiers": dos_data.get("dossiers", []),
                "sources_count": len(src_data.get("sources", [])),
                "dossiers_count": len(dos_data.get("dossiers", [])),
            })
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 500)

    def _handle_research_sources(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        source_id = None
        if "?" in self.path:
            params = dict(part.split("=", 1) for part in self.path.split("?", 1)[1].split("&") if "=" in part)
            source_id = params.get("id")
        try:
            if source_id:
                data = research_api.get_source(root, source_id)
            else:
                data = research_api.list_sources(root)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_dossiers(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        dossier_id = None
        if "?" in self.path:
            params = dict(part.split("=", 1) for part in self.path.split("?", 1)[1].split("&") if "=" in part)
            dossier_id = params.get("id")
        try:
            if dossier_id:
                data = research_api.get_dossier(root, dossier_id)
            else:
                data = research_api.list_dossiers(root)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_init(self, payload: dict[str, Any]) -> None:
        target_root = Path(self.research_dir or self.workspace_root or ".").resolve()
        title = str(payload.get("title") or target_root.name or "Research").strip()
        lang = str(payload.get("language") or "en").strip().lower()
        try:
            res = research_api.init(target_root, title=title, language=lang)
            self.__class__.research_dir = str(target_root)
            self._json({"ok": True, "message": f"Research initialized for '{title}'", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_ingest(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        if payload.get("allow_retention") is not True:
            self._json({"ok": False, "message": "Explicit retention permission is required (allow_retention: true)"}, 400)
            return

        content = payload.get("content") or payload.get("text")
        file_path = payload.get("file")
        title = payload.get("title") or (Path(str(file_path)).name if file_path else "Untitled Source")
        language = payload.get("language") or None
        raw_tags = payload.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        context = {"tags": tags} if tags else None

        try:
            if content is not None:
                if not isinstance(content, str) or not content.strip():
                    self._json({"ok": False, "message": "Source content cannot be empty"}, 400)
                    return
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as tf:
                    tf.write(content)
                    temp_path = tf.name
                try:
                    res = research_api.ingest(root, temp_path, allow_retention=True, title=title, language=language, context=context)
                finally:
                    with contextlib.suppress(OSError):
                        os.unlink(temp_path)
            elif file_path:
                res = research_api.ingest(root, str(file_path), allow_retention=True, title=title, language=language, context=context)
            else:
                self._json({"ok": False, "message": "Either 'content' or 'file' must be provided"}, 400)
                return

            with contextlib.suppress(ResearchError, OSError, ValueError):
                research_api.reindex(root)

            self._json({"ok": True, "message": f"Source '{title}' ingested successfully", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_search(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        query = str(payload.get("query") or "").strip()
        if not query:
            self._json({"ok": False, "message": "Empty query"}, 400)
            return
        limit = int(payload.get("limit") or 20)
        try:
            res = research_api.search(root, query, limit=limit)
            self._json({"ok": True, **res})
        except (ResearchError, OSError, ValueError):
            try:
                research_api.reindex(root)
                res = research_api.search(root, query, limit=limit)
                self._json({"ok": True, **res})
            except (ResearchError, OSError, ValueError) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_dossier(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("body") or "").strip()
        if not title:
            self._json({"ok": False, "message": "Dossier title is required"}, 400)
            return
        lang = str(payload.get("language") or "en").strip().lower()
        raw_tags = payload.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        raw_eids = payload.get("evidence_ids")
        evidence_ids: list[str] = []
        if isinstance(raw_eids, list):
            evidence_ids = [str(e).strip() for e in raw_eids if str(e).strip()]

        try:
            res = research_api.create_dossier(root, title=title, body=body, language=lang, tags=tags, evidence_ids=evidence_ids)
            self._json({"ok": True, "message": f"Dossier '{title}' created", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_compare(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        source_id = str(payload.get("source_id") or "").strip()
        if not source_id:
            self._json({"ok": False, "message": "source_id is required"}, 400)
            return
        manuscript = payload.get("manuscript") or self.source_input
        if not manuscript:
            self._json({"ok": False, "message": "No manuscript loaded or specified for comparison"}, 400)
            return
        try:
            res = research_api.compare_source(root, source_id, manuscript)
            self._json({"ok": True, **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet: suppress default request logging."""
        return


def run_server(
    target_path: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    language: str = "auto",
    title: str | None = None,
    no_project: bool = False,
    thresholds: FingerprintThresholds | None = None,
    open_browser: bool = False,
    research_dir: str | None = None,
) -> None:
    """Runs the Lixity dashboard development server on loopback."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Only loopback addresses (127.0.0.1, localhost) are permitted")

    source_input: str | None = None
    workspace_root: str = os.getcwd()
    exports_dir: str = os.path.join(workspace_root, "exports")

    if not no_project and target_path:
        target_abs = os.path.abspath(target_path)
        if os.path.isfile(target_abs):
            source_input = target_abs
            workspace_root = os.path.dirname(target_abs)
            exports_dir = os.path.join(workspace_root, "exports")
        elif os.path.isdir(target_abs):
            try:
                ws = discover(root=target_abs)
                source_input = ws.manuscript
                workspace_root = ws.root
                exports_dir = ws.exports_dir
            except (FileNotFoundError, ValueError):
                workspace_root = target_abs
                exports_dir = os.path.join(workspace_root, "exports")
                source_input = None
    elif not no_project:
        # Attempt ambient discovery in current working directory
        try:
            ws = discover(root=workspace_root)
            source_input = ws.manuscript
            workspace_root = ws.root
            exports_dir = ws.exports_dir
        except (FileNotFoundError, ValueError):
            source_input = None

    os.makedirs(exports_dir, exist_ok=True)

    LixityServerHandler.source_input = source_input
    LixityServerHandler.workspace_root = workspace_root
    LixityServerHandler.exports_dir = exports_dir
    LixityServerHandler.research_dir = research_dir
    LixityServerHandler.language = language
    LixityServerHandler.title = title
    LixityServerHandler.title_custom = title is not None
    LixityServerHandler.thresholds = thresholds or FingerprintThresholds()
    LixityServerHandler.refresh()

    server = ThreadingHTTPServer((host, port), LixityServerHandler)
    url = f"http://{host}:{port}/"
    info = LixityServerHandler.dashboard_info

    print(
        f"[OK] Lixity server running: {url}\n"
        f"     {info.get('chapters')} chapters · {info.get('paragraphs')} paragraphs · "
        f"{info.get('artifacts')} artifacts (profile: {info.get('language')})\n"
        f"     Stop with Ctrl+C"
    )

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] Lixity server stopped.")
    finally:
        server.server_close()
