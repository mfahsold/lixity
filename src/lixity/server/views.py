"""Dashboard rendering and artifact discovery for the native server.

These helpers are pure with respect to HTTP: they take paths and options and
return content, which keeps them independent of the request layer.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..characters import presence_report
from ..config import (
    load_project_config,
    resolve_thresholds,
    same_config_scope,
    validate_author_name,
)
from ..dialogue import dialogue_report
from ..io import FileUtils
from ..markers import list_markers
from ..motifs import motif_report
from ..pacing import pacing_report
from ..pipeline import analyze_document, resolve_document_config
from ..project_identity import manuscript_identity_check, project_title
from ..publication import load_publication
from ..scenes import scene_report_for_display
from ..showing import showing_report
from ..style_fingerprint import FingerprintThresholds
from ..ui import render_analysis
from .constants import NATIVE_UI_ACTIONS
from .pdf_context import manuscript_pdf_token, project_settings_token, research_context_token


def sanitize_filename(raw: str | None) -> str:
    """Sanitizes a manuscript file name to prevent directory traversal."""
    name = os.path.basename(str(raw or "").strip())
    if not re.match(r"^[\w.\- ()äöüÄÖÜß]+\.(md|markdown|txt)$", name, re.IGNORECASE):
        return "manuscript.md"
    return name



def collect_artifacts(exports_dir: str) -> list[dict[str, Any]]:
    """Collects export artifacts from the given directory safely."""
    artifacts: list[dict[str, Any]] = []
    if not os.path.isdir(exports_dir):
        return artifacts
    try:
        entries = sorted(os.listdir(exports_dir))
    except OSError:
        return artifacts

    for name in entries:
        path = os.path.join(exports_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in (".pdf", ".epub", ".html", ".json"):
            try:
                size_kb = os.path.getsize(path) / 1024.0
            except OSError:
                size_kb = 0.0
            artifacts.append({
                "name": name,
                "size_kb": size_kb,
                "href": f"/artifact/{name}",
            })
    return artifacts



def build_server_dashboard(
    source_input: str | None,
    language: str = "en",
    title: str | None = None,
    thresholds: FingerprintThresholds | None = None,
    controls: bool = True,
    api_base: str = "/api",
    exports_dir: str | None = None,
    debug: bool = False,
    project_root: str | Path | None = None,
    research_root: str | Path | None = None,
    identity_settings_override: Mapping[str, Any] | None = None,
    project_config_bytes: bytes | None = None,
    strict_source: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Generates the interactive dashboard HTML and returns (html, info_dict)."""
    text = ""
    is_empty = True
    manuscript_name = ""
    is_missing = False
    manuscript_readable = False
    manuscript_source_sha256 = ""

    if source_input:
        if os.path.isfile(source_input):
            try:
                text, manuscript_source_sha256 = FileUtils.read_source_snapshot(source_input)
                manuscript_readable = True
                is_empty = not text.strip()
                manuscript_name = os.path.basename(source_input)
            except OSError:
                if strict_source:
                    raise
                text = ""
        else:
            if strict_source:
                raise OSError("The selected manuscript is missing")
            is_missing = True
            manuscript_name = os.path.basename(source_input)

    source_is_file = bool(source_input and os.path.isfile(source_input))
    settings = load_project_config(source_input) if source_is_file else {}
    if not source_input and project_root is not None:
        settings = load_project_config(project_root)
    identity_settings = settings
    if project_root is not None:
        # Author/publication stay project-local; reuse the settings read when
        # the manuscript already sits in the selected root.
        if source_input and not (source_is_file and same_config_scope(project_root, source_input)):
            identity_settings = load_project_config(project_root)
    elif source_input and not source_is_file:
        identity_settings = load_project_config(Path(source_input).parent)
    if identity_settings_override is not None:
        identity_settings = {**identity_settings, **identity_settings_override}
    config, resolved = resolve_document_config(text, language, project_config=settings)
    status_labels = resolved.labels

    def _status_text(key: str, **values: Any) -> str:
        """Localized status text; a count of one picks the ``_one`` row."""
        chosen = key
        if values.get("count") == 1 and f"{key}_one" in status_labels:
            chosen = f"{key}_one"
        template = status_labels.get(chosen) or status_labels.get(key) or ""
        return template.format(**values) if template else key

    try:
        doc_title = project_title(source_input, text, identity_settings, title) if source_input else (
            title or identity_settings.get("title") or _status_text("status_no_project")
        )
    except ValueError:
        doc_title = Path(source_input).stem if source_input else _status_text("status_no_project")
    publication_error = ""
    try:
        publication_values: Mapping[str, Any] = load_publication(identity_settings).model_dump()
    except ValueError as exc:
        raw_publication = identity_settings.get("publication", {})
        publication_values = raw_publication if isinstance(raw_publication, Mapping) else {}
        publication_error = str(exc)
    raw_author = identity_settings.get("author_name", "")
    try:
        project_author = validate_author_name(raw_author)
    except ValueError:
        project_author = ""
    identity_check = manuscript_identity_check(
        text if manuscript_readable else None, doc_title, raw_author,
    )
    resolved_thresholds = thresholds or resolve_thresholds(project_config=settings)

    analysis = analyze_document(text, config, resolved_thresholds)
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    metrics = analysis.metrics
    markers = list_markers(text) if text else []

    artifacts = collect_artifacts(exports_dir) if exports_dir else []
    names = settings.get("names", [])

    # The header already carries the project's identity and scale (chapters,
    # words, file). The strip is reserved for real problems and operations, so
    # normal metadata is not reported twice.
    status_items = []
    if is_missing:
        status_items.append({"key": "manuscript", "state": "error",
                             "detail": f"{manuscript_name} ({_status_text('status_missing')})"})
    elif is_empty and manuscript_name:
        status_items.append({"key": "manuscript", "state": "warn",
                             "detail": f"{manuscript_name} ({_status_text('status_empty')})"})
    status_items += [
        {
            "key": "exports",
            "state": "ok" if artifacts else "warn",
            "detail": _status_text("status_exports_counts", count=len(artifacts)),
        },
        {
            "key": "markers",
            "state": "warn" if any(m.kind for m in markers) else "ok",
            "detail": _status_text("status_markers_open", count=sum(1 for m in markers if m.kind)),
        },
    ]

    html_doc = render_analysis(
        analysis,
        resolved,
        title=doc_title,
        flag_min_severity=resolved_thresholds.flag_min_severity,
        status=status_items,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, names, config) if names else None,
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, settings.get("motifs", {}), config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        scenes=scene_report_for_display(text, config, settings.get("scene_analysis"),
                                        premeasured_chapters=metrics.chapters),
        markers=markers,
        artifacts=artifacts,
        tense_available=bool(resolved.praesens_regex and resolved.praeteritum_regex),
        controls=controls,
        api_base=api_base,
        manuscript_name=manuscript_name,
        current_language=language,
        enabled_actions=NATIVE_UI_ACTIONS,
        nda_project_name=doc_title if source_input else title or (
            os.path.splitext(manuscript_name)[0] if manuscript_name and not is_missing else ""
        ),
        debug=debug,
        project_author=project_author,
        identity_check=identity_check,
        author_setting_enabled=bool(source_input or project_root is not None),
        publication=publication_values,
        publication_error=publication_error,
        project_token=project_settings_token(
            project_root or (Path(source_input).parent if source_input else None), source_input,
            config_bytes=project_config_bytes,
        ),
        manuscript_source_sha256=manuscript_source_sha256,
        manuscript_pdf_token=manuscript_pdf_token(
            source_input, project_root=project_root, language=language,
            title=title, thresholds=resolved_thresholds,
            config_bytes=project_config_bytes,
        ) if manuscript_readable and not is_empty else "",
        research_context_token=research_context_token(research_root or project_root),
    )

    info = {
        "identity_check": identity_check,
        "chapters": len(chapters),
        "paragraphs": len(paragraphs),
        "flagged": sum(1 for p in paragraphs if p.severity >= resolved_thresholds.flag_min_severity),
        "artifacts": len(artifacts),
        "markers": len(markers),
        "language": resolved.name,
        "language_key": resolved.key,
        "is_empty": is_empty,
        "is_missing": is_missing,
        "manuscript_source_sha256": manuscript_source_sha256,
    }
    return html_doc, info
