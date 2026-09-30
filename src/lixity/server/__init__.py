"""lixity.server – loopback-only HTTP server and interactive dashboard.

A single ``BaseHTTPRequestHandler`` is composed from focused route groups so that
each area owns its handlers and its own path table:

=====================  =========================================================
Module                 Responsibility
=====================  =========================================================
``runtime``            Bind checks, project resolution, startup and shutdown
``handler``            Shared handler state, the route table and dispatch
``_state``             Workspace state and ``refresh()`` — the only state writer
``_base``              Response helpers plus the Host/Origin guards
``routes_project``     Browsing, creation, opening, loading and settings
``routes_research``    Sources, dossiers, claims, evidence, decisions, search
``routes_nda``         Project-owned NDA management
``routes_markers``     Inline author work markers
``views``              Dashboard rendering and artifact discovery
``constants``          Limits, defaults and MIME types
=====================  =========================================================

The public surface is re-exported here, so ``from lixity.server import
run_server, LixityServerHandler`` keeps working.
"""

from __future__ import annotations

from .constants import DEFAULT_HOST, DEFAULT_PORT, LANGUAGE_CHOICES, MAX_PAYLOAD_BYTES, MIME_TYPES
from .handler import LixityServerHandler
from .runtime import run_server
from .views import build_server_dashboard, collect_artifacts, sanitize_filename

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "LANGUAGE_CHOICES",
    "MAX_PAYLOAD_BYTES",
    "MIME_TYPES",
    "LixityServerHandler",
    "build_server_dashboard",
    "collect_artifacts",
    "run_server",
    "sanitize_filename",
]
