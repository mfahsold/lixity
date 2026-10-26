"""Content-free discovery from the server's registered dispatch paths."""

from collections.abc import Mapping
from typing import Any

from .. import __version__
from ..site import docs_url


def api_index(get_routes: Mapping[str, str], post_routes: Mapping[str, str], *,
              manuscript_loaded: bool, research_configured: bool,
              research_store_present: bool, language: str) -> dict[str, Any]:
    """Describe supported canonical routes and bounded workspace state."""
    return {
        "ok": True,
        "schema_version": "lixity-api-index/1",
        "version": __version__,
        "routes": {"GET": sorted(get_routes), "POST": sorted(f"/api/{action}" for action in post_routes)},
        "capabilities": {
            "analysis": {"analyze", "rebuild"}.issubset(post_routes),
            "analysis_review": "analysis-review" in post_routes,
            "markers": {"marker-add", "marker-resolve"}.issubset(post_routes),
            "research": "research-init" in post_routes,
            "research_images": {"research-image-ingest", "research-dossier-image"}.issubset(post_routes),
            "research_media": {"research-media-ingest", "research-dossier-media"}.issubset(post_routes),
            "manuscript_pdf": "manuscript-pdf" in post_routes,
            "reading_website": "site-export" in post_routes,
            "reading_website_preflight": "site-preflight" in post_routes,
            "manuscript_links": "research-manuscript-link" in post_routes,
            "speech": {"speech-render", "speech-cancel"}.issubset(post_routes),
            "nda_draft": "nda-draft" in post_routes,
        },
        "project": {"manuscript_loaded": manuscript_loaded, "research_configured": research_configured,
                    "research_store_present": research_store_present, "language": language},
        "documentation": docs_url("AGENTS.md"),
    }
