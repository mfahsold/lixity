"""Dashboard rendering and artifact discovery for the native server.

These helpers are pure with respect to HTTP: they take paths and options and
return content, which keeps them independent of the request layer.
"""

from __future__ import annotations

import os
import re
from typing import Any

from ..characters import presence_report
from ..config import load_project_config, resolve_thresholds
from ..dialogue import dialogue_report
from ..markers import list_markers
from ..motifs import motif_report
from ..pacing import pacing_report
from ..pipeline import analyze_document, resolve_document_config
from ..scenes import scene_report_for_display
from ..showing import showing_report
from ..style_fingerprint import FingerprintThresholds
from ..ui import render_dashboard

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
) -> tuple[str, dict[str, Any]]:
    """Generates the interactive dashboard HTML and returns (html, info_dict)."""
    text = ""
    is_empty = True
    manuscript_name = ""
    is_missing = False

    if source_input:
        if os.path.isfile(source_input):
            try:
                with open(source_input, encoding="utf-8") as f:
                    text = f.read()
                is_empty = not text.strip()
                manuscript_name = os.path.basename(source_input)
            except OSError:
                text = ""
        else:
            is_missing = True
            manuscript_name = os.path.basename(source_input)

    doc_title = title or (
        os.path.splitext(manuscript_name)[0]
        if manuscript_name and not is_missing
        else ("No Project Loaded" if language != "de" else "Kein Projekt geladen")
    )

    settings = load_project_config(source_input) if source_input and os.path.isfile(source_input) else {}
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
        enabled_actions=("analyze", "rebuild", "nda-draft"),
        nda_project_name=title or (
            os.path.splitext(manuscript_name)[0] if manuscript_name and not is_missing else ""
        ),
        debug=debug,
    )

    info = {
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
