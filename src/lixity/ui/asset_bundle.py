"""Ordered packaged assets shared by UI renderers and local asset routes."""

from functools import lru_cache
from pathlib import Path

ASSET_DIR = Path(__file__).with_name("assets")
DIAGRAM_LIBRARY_FILE = "vendor/mermaid-tiny-12.3.0.min.js"
DIAGRAM_LIBRARY_ROUTE = "/api/" + DIAGRAM_LIBRARY_FILE
PASSAGE_NAVIGATION_SCRIPT = "analysis-passage-navigation.js"
_DOSSIER_CHARACTER_SCRIPT = "research-dossier-character.js"
_DOSSIER_CHARACTER_STYLE = "research-dossier-character.css"
WORKSPACE_STYLES = (
    "design-tokens.css",
    "components.css",
    "dashboard.css",
    "vendor/photoswipe-5.4.4.css",
    "research-media.css",
    "research-navigation.css",
    "research-tools.css",
    "research-collections.css",
    _DOSSIER_CHARACTER_STYLE,
    "dossier-images.css",
    "vendor/leaflet-1.9.4.css",
    "dossier-geography.css",
    "workspace-reader.css",
    "manuscript-links.css",
    "manuscript-reader.css",
    "decision-review.css",
    "analysis-scope.css",
    "analysis-navigation.css",
    "section-navigation.css",
    "analysis-evidence.css",
    "reader-publication.css",
    "project-overview.css",
    "teleprompter.css",
)
WORKSPACE_SCRIPTS = (
    "read-only-site.js",
    "vendor/preact-10.29.8.min.js",
    "vendor/htm-3.1.1.umd.js",
    "vendor/leaflet-1.9.4.min.js",
    "vendor/photoswipe-5.4.4.umd.min.js",
    "research-media.js",
    "icons.js",
    "component-layer.js",
    "logging.js",
    "tooltips.js",
    "analysis-navigation.js",
    "interactions.js",
    "command-palette.js",
    "section-navigation.js",
    "register-settings.js",
    "site-publication-settings.js",
    "dashboard.js",
    PASSAGE_NAVIGATION_SCRIPT,
    "analysis-scope.js",
    "zotero-results.js",
    "research-cards.js",
    "research-core.js",
    _DOSSIER_CHARACTER_SCRIPT,
    "research-content.js",
    "research-evidence.js",
    "research-lists.js",
    "research-collections.js",
    "research-review.js",
    "research-workspace.js",
    "research-dossier-drafts.js",
    "research-tools.js",
    "markdown-editor.js",
    "research-revisions.js",
    "workspace-state.js",
    "workspace-motion.js",
    "project-ui.js",
    "project-overview.js",
    "dossier-images.js",
    "dossier-geography.js",
    "style-space.js",
    "metric-context.js",
    "workspace-reader.js",
    "manuscript-links.js",
    "manuscript-reader.js",
    "analysis-evidence.js",
    "analysis-review.js",
    "reader-publication.js",
    "audio-take.js",
    "speech-presentation.js",
    "teleprompter.js",
)
NATIVE_AUDIO_SCRIPTS = ("speech-direction.js", "speech-player.js", "speech.js",)
# Standalone analysis reports have no workspace research or map controls.
REPORT_SCRIPTS = tuple(name for name in WORKSPACE_SCRIPTS if name not in (
    "manuscript-reader.js", "teleprompter.js", "speech-presentation.js",
    "audio-take.js", "register-settings.js", "site-publication-settings.js", "research-collections.js", "research-tools.js", "analysis-navigation.js",
    "research-dossier-drafts.js", "research-revisions.js", "project-overview.js",
    "vendor/leaflet-1.9.4.min.js", "dossier-geography.js",
    PASSAGE_NAVIGATION_SCRIPT, _DOSSIER_CHARACTER_SCRIPT,
))
REPORT_STYLES = tuple(
    name for name in WORKSPACE_STYLES if name not in {
        "teleprompter.css", "research-collections.css", "research-tools.css", "analysis-navigation.css",
        _DOSSIER_CHARACTER_STYLE,
    }
)

# Curated publications reuse the shared renderers without dormant workspace controls.
PUBLICATION_STYLES = tuple(name for name in REPORT_STYLES if name != "analysis-evidence.css")
PUBLICATION_SCRIPTS = tuple(
    name for name in WORKSPACE_SCRIPTS if name not in {
        "register-settings.js", "site-publication-settings.js", "analysis-scope.js",
        "project-overview.js", "style-space.js", "metric-context.js", "workspace-reader.js",
        "manuscript-reader.js", "manuscript-links.js", "analysis-evidence.js", "analysis-review.js",
        "teleprompter.js", "speech-presentation.js", "audio-take.js",
        "research-collections.js", "research-dossier-drafts.js", "research-tools.js",
        PASSAGE_NAVIGATION_SCRIPT, _DOSSIER_CHARACTER_SCRIPT,
    }
)


@lru_cache(maxsize=16)
def bundle_assets(files: tuple[str, ...]) -> str:
    """Join packaged assets on first use; importing the module does no I/O."""
    return "\n".join((ASSET_DIR / name).read_text(encoding="utf-8") for name in files)
