"""Public product site and documentation URLs (single source).

Every user-visible link to the documentation site is built from here, so a
deployment change touches one constant instead of scattered string literals.
"""

from __future__ import annotations

DOCS_BASE = "https://mfahsold.github.io/lixity"
FUNDING_DETAILS_URL = "https://github.com/mfahsold/lixity/blob/main/docs/FUNDING.md"


def docs_url(path: str = "") -> str:
    """Return an absolute documentation URL for a path inside the site."""
    if not path:
        return f"{DOCS_BASE}/"
    return f"{DOCS_BASE}/{path.lstrip('/')}"
