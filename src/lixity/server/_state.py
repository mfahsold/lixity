"""Shared workspace state for the native server.

Every route group reads selected workspace state here. `refresh()` and prepared
project/settings transitions reuse `build_server_dashboard` for resolution and
`publish_dashboard` for the cached view; no route maintains another renderer.
"""

from __future__ import annotations

import email.message
import os
import warnings
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, ClassVar

from ..io import FileUtils
from ..style_fingerprint import FingerprintThresholds
from .views import build_server_dashboard

if TYPE_CHECKING:
    pass


class RefreshOutcome(str, Enum):
    """Current source availability, separate from the cached analysis identity."""

    UNKNOWN = "unknown"
    CURRENT = "current"
    REBUILT = "rebuilt"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    REFRESH_FAILED = "refresh-failed"


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

    _workspace_dispatched: bool = False
    _workspace_selection: bool = False
    _workspace_selection_ok: bool = False

    _workspace_lock: ClassVar[RLock] = RLock()
    api_base: ClassVar[str] = "/api"
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
    refresh_outcome: ClassVar[RefreshOutcome] = RefreshOutcome.UNKNOWN
    _refresh_needs_validation: ClassVar[bool] = False
    _speech_generation: ClassVar[int] = 0
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
        cls._speech_generation += 1
        cls.dashboard_html, cls.dashboard_info = html, info
        cls.refresh_outcome = RefreshOutcome.REBUILT
        cls._refresh_needs_validation = False

    @classmethod
    def refresh(cls, *, strict_source: bool = False) -> None:
        """Prepare and publish one complete dashboard under the workspace lock.

        Startup may render an initially missing source. Refreshing last-good
        content requires a readable source so an empty fallback cannot replace it.
        """
        with cls._workspace_lock:
            if strict_source and cls.source_input:
                try:
                    FileUtils.read_source_snapshot(cls.source_input)
                except FileNotFoundError:
                    cls.refresh_outcome = RefreshOutcome.MISSING
                    raise
                except OSError:
                    cls.refresh_outcome = RefreshOutcome.UNREADABLE
                    raise
            try:
                with warnings.catch_warnings():
                    if strict_source:
                        warnings.filterwarnings("error", category=UserWarning, module=r"lixity\.config")
                    html, info = build_server_dashboard(
                        cls.source_input,
                        language=cls.language,
                        title=cls.title,
                        thresholds=cls.thresholds,
                        controls=True,
                        api_base=cls.api_base,
                        exports_dir=cls.exports_dir,
                        debug=cls.debug,
                        project_root=cls.get_author_project_root(),
                        research_root=cls.get_research_root(),
                        strict_source=strict_source,
                    )
            except (OSError, ValueError, RuntimeError, UserWarning):
                cls.refresh_outcome = RefreshOutcome.REFRESH_FAILED
                cls._refresh_needs_validation = True
                raise
            cls.publish_dashboard(html, info)

    @classmethod
    def refresh_when_source_changed(cls) -> RefreshOutcome:
        """Validate source availability and rebuild only changed manuscript bytes.

        Failures keep the last successful HTML and source digest intact. The
        separate outcome lets responses label that retained content truthfully.
        The lock binds validation and publication to one selected workspace.
        """
        with cls._workspace_lock:
            source = cls.source_input
            rendered = cls.dashboard_info.get("manuscript_source_sha256")
            if not source:
                cls.refresh_outcome = RefreshOutcome.CURRENT
                return cls.refresh_outcome
            try:
                _, current = FileUtils.read_source_snapshot(source)
            except FileNotFoundError:
                cls.refresh_outcome = RefreshOutcome.MISSING
                return cls.refresh_outcome
            except OSError:
                cls.refresh_outcome = RefreshOutcome.UNREADABLE
                return cls.refresh_outcome
            # A failed rebuild may concern settings or rendering, so matching
            # manuscript bytes alone cannot validate that failed operation.
            if current == rendered and not cls._refresh_needs_validation:
                cls.refresh_outcome = RefreshOutcome.CURRENT
                return cls.refresh_outcome
            try:
                cls.refresh(strict_source=True)
            except (OSError, ValueError, RuntimeError, UserWarning):
                return cls.refresh_outcome
            return cls.refresh_outcome
