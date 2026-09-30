"""Shared limits and defaults for the native server."""

from __future__ import annotations

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
