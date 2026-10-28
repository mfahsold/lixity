"""Measured package diagnostics, without rendering or publication claims."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from .research.images import (
    extract_markdown_image_references,
    resolve_dossier_images,
    resolve_dossier_media,
)

if TYPE_CHECKING:
    from .research.repository import Snapshot
    from .site_export import SiteBundle


def media_summary(snapshot: Snapshot | None, bodies: Iterable[str], resources: Mapping[str, str]) -> dict[str, int]:
    """Count occurrences in exactly the dossier revisions selected for export."""
    counts = dict.fromkeys(("references", "unavailable", "not_packaged", "missing_attribution", "ordinary_image_references"), 0)
    if snapshot is None:
        return counts
    for body in bodies:
        counts["ordinary_image_references"] += sum(
            not marker.destination.lstrip("<").lower().startswith("lixity:")
            for marker in extract_markdown_image_references(body))
        for item in [*resolve_dossier_images(snapshot, body), *resolve_dossier_media(snapshot, body)]:
            counts["references"] += 1
            if item["availability"] != "available":
                counts["unavailable"] += 1
            elif item.get("url") not in resources:
                counts["not_packaged"] += 1
            context = item.get("context") or {}
            if not context.get("origin_url") or not context.get("provenance_note"):
                counts["missing_attribution"] += 1
    return counts


def preflight_report(bundle: SiteBundle) -> dict[str, Any]:
    """Measure verified files and ZIP; credits are presence checks, never rights clearance."""
    packed = bundle.to_zip()
    media = dict(bundle.media_summary)
    analysis_bytes = len(bundle.files.get("analysis.html", b""))
    sizes = {"html_bytes": len(bundle.files["index.html"]),
             "total_bytes": sum(map(len, bundle.files.values())), "zip_bytes": len(packed),
             "source_file_bytes": sum(len(content) for name, content in bundle.files.items()
                                      if name.startswith("assets/sources/")), "file_count": len(bundle.files)}
    if analysis_bytes:
        sizes["analysis_html_bytes"] = analysis_bytes
        sizes["total_html_bytes"] = sizes["html_bytes"] + analysis_bytes
    warnings = [code for field, code in (
        ("unavailable", "media_unavailable"), ("not_packaged", "media_not_packaged"),
        ("missing_attribution", "attribution_incomplete"), ("ordinary_image_references", "ordinary_images_unchecked"))
        if media.get(field)]
    if sizes["html_bytes"] + analysis_bytes > 10 * 1024 * 1024:
        warnings.append("large_html")
    if sizes["zip_bytes"] > 20 * 1024 * 1024:
        warnings.append("large_zip")
    return {"schema_version": "lixity-site-preflight/1", "mode": bundle.manifest["mode"],
            **({"analysis_sections": bundle.manifest["publication"]["analysis_sections"]}
               if bundle.manifest.get("publication", {}).get("analysis_sections") else {}),
            "sizes": sizes, "media": media, "warnings": warnings,
            "mobile_layout_check": "not_run", "rights_check": "not_performed"}
