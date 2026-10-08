"""Expose the authoritative local-image bounds to the dashboard component."""

import html
import json

from ..research.limits import (
    MAX_IMAGE_ALT_CHARS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_CAPTION_CHARS,
    MAX_IMAGE_PIXELS,
    MAX_SOURCE_CONTEXT_CHARS,
)


def image_limits_attribute() -> str:
    """Return HTML-safe JSON; the browser never decides the backend limits."""
    return html.escape(json.dumps({
        "bytes": MAX_IMAGE_BYTES,
        "pixels": MAX_IMAGE_PIXELS,
        "alt": MAX_IMAGE_ALT_CHARS,
        "caption": MAX_IMAGE_CAPTION_CHARS,
        "note": MAX_SOURCE_CONTEXT_CHARS,
        "url": MAX_SOURCE_CONTEXT_CHARS,
    }), quote=True)
