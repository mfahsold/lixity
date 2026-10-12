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
from ..config import load_project_config, resolve_thresholds, validate_author_name
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
from ..ui import render_dashboard
from .constants import NATIVE_UI_ACTIONS
from .pdf_context import manuscript_pdf_token, project_settings_token, research_context_token

MAX_ARTIFACT_BYTES = 200 * 1024 * 1024  # 200 MB


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
                "href": name,
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

    settings = load_project_config(source_input) if source_input and os.path.isfile(source_input) else {}
    if not source_input and project_root is not None:
        settings = load_project_config(project_root)
    identity_settings = settings
    if project_root is not None:
        identity_settings = load_project_config(project_root)
    elif source_input and not os.path.isfile(source_input):
        identity_settings = load_project_config(Path(source_input).parent)
    if identity_settings_override is not None:
        identity_settings = {**identity_settings, **identity_settings_override}
    try:
        doc_title = project_title(source_input, text, identity_settings, title) if source_input else (
            title or identity_settings.get("title") or ("No Project Loaded" if language != "de" else "Kein Projekt geladen")
        )
    except ValueError:
        doc_title = Path(source_input).stem if source_input else "No Project Loaded"
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
    config, resolved = resolve_document_config(text, language, project_config=settings)
    resolved_thresholds = thresholds or resolve_thresholds(project_config=settings)

    analysis = analyze_document(text, config, resolved_thresholds)
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    metrics, fingerprint = analysis.metrics, analysis.fingerprint
    markers = list_markers(text) if text else []

    artifacts = collect_artifacts(exports_dir) if exports_dir else []
    names = settings.get("names", [])

    status_items = [
        {
            "key": "manuscript",
            "state": "error" if is_missing else ("warn" if is_empty and manuscript_name else ("ok" if manuscript_name else "unknown")),
            "detail": (
                f"{manuscript_name} ({'file missing' if resolved.key != 'de' else 'Datei nicht gefunden'})"
                if is_missing
                else (
                    f"{manuscript_name} ({'empty' if resolved.key != 'de' else 'leer'})"
                    if is_empty and manuscript_name
                    else (manuscript_name or ("none loaded" if resolved.key != "de" else "kein Manuskript geladen"))
                )
            ),
        },
        {
            "key": "analysis",
            "state": "ok" if chapters else "warn",
            "detail": f"{len(chapters)} chapters · {len(paragraphs)} paragraphs · {resolved.name}"
            if resolved.key != "de"
            else f"{len(chapters)} Kapitel · {len(paragraphs)} Absätze · {resolved.name}",
        },
        {
            "key": "exports",
            "state": "ok" if artifacts else "warn",
            "detail": f"{len(artifacts)} files"
            if resolved.key != "de"
            else f"{len(artifacts)} Dateien",
        },
        {
            "key": "markers",
            "state": "warn" if any(m.kind for m in markers) else "ok",
            "detail": f"{sum(1 for m in markers if m.kind)} open"
            if resolved.key != "de"
            else f"{sum(1 for m in markers if m.kind)} offen",
        },
    ]

    html_doc = render_dashboard(
        chapters,
        paragraphs,
        status=status_items,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, names, config) if names else None,
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, settings.get("motifs", {}), config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        scenes=scene_report_for_display(text, config, settings.get("scene_analysis"),
                                        premeasured_chapters=metrics.chapters),
        metrics=metrics,
        fingerprint=fingerprint,
        markers=markers,
        artifacts=artifacts,
        title=doc_title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        tense_available=bool(resolved.praesens_regex and resolved.praeteritum_regex),
        controls=controls,
        api_base=api_base,
        manuscript_name=manuscript_name,
        current_language=language,
        flag_min_severity=resolved_thresholds.flag_min_severity,
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
    }
    return html_doc, info
