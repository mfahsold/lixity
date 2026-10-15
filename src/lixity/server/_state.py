"""Shared workspace state for the native server.

Every route group reads selected workspace state here. `refresh()` and prepared
project/settings transitions reuse `build_server_dashboard` for resolution and
`publish_dashboard` for the cached view; no route maintains another renderer.
"""

from __future__ import annotations

import email.message
import os
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, ClassVar

from ..io import FileUtils
from ..style_fingerprint import FingerprintThresholds
from .views import build_server_dashboard

if TYPE_CHECKING:
    pass


class WorkspaceState:
    """Mutable workspace state shared by every route group.

    Declared here so route modules can rely on the attributes existing. Candidate
    transitions prepare a view before publishing; ordinary refresh uses the same
    builder and cache publication method.
    """

    if TYPE_CHECKING:
        # Surface supplied by BaseHTTPRequestHandler once the route mixins are
        # composed into LixityServerHandler. Declaring it keeps each route module
        # type-checkable on its own instead of importing the concrete handler.
        command: str
        path: str
        headers: email.message.Message
        rfile: Any
        wfile: Any
        connection: Any
        server: Any
        client_address: Any

        def send_response(self, code: int, message: str | None = ...) -> None: ...
        def send_header(self, keyword: str, value: str) -> None: ...
        def end_headers(self) -> None: ...
        def address_string(self) -> str: ...

    _workspace_lock: ClassVar[RLock] = RLock()
    source_input: ClassVar[str | None] = None
    workspace_root: ClassVar[str] = os.getcwd()
    exports_dir: ClassVar[str] = os.path.join(workspace_root, "exports")
    research_dir: ClassVar[str | None] = None
    language: ClassVar[str] = "en"
    title: ClassVar[str | None] = None
    title_custom: ClassVar[bool] = False
    thresholds: ClassVar[FingerprintThresholds] = FingerprintThresholds()
    project_open_overrides: ClassVar[dict[str, Any]] = {}
    dashboard_html: ClassVar[str] = ""
    dashboard_info: ClassVar[dict[str, Any]] = {}
    debug: ClassVar[bool] = False

    @classmethod
    def get_research_root(cls) -> Path | None:
        if cls.research_dir:
            return Path(cls.research_dir)
        candidate = Path(cls.workspace_root) / "research"
        return Path(cls.workspace_root) if candidate.is_dir() else None

    @classmethod
    def get_author_project_root(cls) -> Path | None:
        """Use the selected manuscript/archive project, never the idle cwd."""
        if cls.source_input:
            return Path(cls.workspace_root).resolve()
        root = Path(cls.research_dir) if cls.research_dir else None
        return root.resolve() if root and (root / "research").is_dir() else None

    @classmethod
    def publish_dashboard(cls, html: str, info: dict[str, Any]) -> None:
        """Publish an already prepared view under the caller's workspace lock."""
        cls.dashboard_html, cls.dashboard_info = html, info

    @classmethod
    def refresh(cls) -> None:
        """Re-analyzes the active manuscript and updates cached dashboard HTML."""
        html, info = build_server_dashboard(
            cls.source_input,
            language=cls.language,
            title=cls.title,
            thresholds=cls.thresholds,
            controls=True,
            api_base="/api",
            exports_dir=cls.exports_dir,
            debug=cls.debug,
            project_root=cls.get_author_project_root(),
            research_root=cls.get_research_root(),
        )
        cls.publish_dashboard(html, info)

    @classmethod
    def refresh_when_source_changed(cls) -> bool:
        """Rebuilds the cached dashboard when the manuscript changed on disk.

        The digest read is cheap and only a changed file triggers one full
        rebuild, so a served dashboard never presents numbers that no longer
        match the manuscript. Returns whether a rebuild was performed.
        """
        source = cls.source_input
        rendered = cls.dashboard_info.get("manuscript_source_sha256")
        if not source or not rendered or not os.path.isfile(source):
            return False
        try:
            _, current = FileUtils.read_source_snapshot(source)
        except OSError:
            return False
        if current == rendered:
            return False
        with cls._workspace_lock:
            if cls.dashboard_info.get("manuscript_source_sha256") != rendered:
                return False  # another request already rebuilt this digest
            try:
                cls.refresh()
            except (OSError, ValueError, RuntimeError):
                return False
        return True
