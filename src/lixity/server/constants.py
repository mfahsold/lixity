"""Shared limits and defaults for the native server."""

from __future__ import annotations

from ..config import DEFAULT_HOST as DEFAULT_HOST  # re-exported
from ..config import DEFAULT_PORT as DEFAULT_PORT  # re-exported
from ..language import LANGUAGE_CHOICES as LANGUAGE_CHOICES  # re-exported

MAX_PAYLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_PAYLOAD_BYTES = 32 * 1024 * 1024
MAX_MEDIA_PAYLOAD_BYTES = 72 * 1024 * 1024
MAX_ARTIFACT_BYTES = 200 * 1024 * 1024  # 200 MB

# Native UI capabilities, also used by synthetic documentation captures.
NATIVE_UI_ACTIONS = (
    "speech-render",
    "site-export",
    "site-preflight",
    "analyze", "nda-draft", "manuscript-pdf", "research-reader", "research-image-ingest", "research-dossier-image",
    "research-media-ingest", "research-dossier-media",
    "analysis-review",
    "research-manuscript-link",
    "research-manuscript-reanchor",
)

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
