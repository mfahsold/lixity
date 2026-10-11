"""Shared in-memory manuscript and analysis PDF composition."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .config import resolve_thresholds
from .formatters import ReportFormatter
from .markdown_parser import prose_paragraphs, split_chapters
from .models import CorpusConfig
from .pdf_layouts import FontChoice, book_pdf, manuscript_pdf, report_pdf
from .pipeline import analyze_document, resolve_document_config
from .style_fingerprint import FingerprintThresholds


def pdf_title(manuscript: str, text: str, project_config: Mapping[str, Any]) -> str:
    """Prefer the project's title, then a manuscript heading, then its file name."""
    configured = project_config.get("title")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            heading = stripped[2:].strip()
            if heading:
                return heading
    return os.path.splitext(os.path.basename(manuscript))[0]


def manuscript_sections(text: str, config: CorpusConfig) -> list[tuple[str, list[str]]]:
    """Split chapter headings and prose using the existing manuscript parser."""
    sections = []
    for number, heading, body in split_chapters(text, config):
        sections.append((heading or f"Chapter {number}", prose_paragraphs(body, config)))
    return sections


def compose_pdf(
    text: str, *, manuscript: str, layout: str, language: str = "en",
    project_config: Mapping[str, Any] | None = None, title: str | None = None,
    author: str = "", thresholds: FingerprintThresholds | None = None,
    choice: FontChoice | None = None, require_prose: bool = False,
) -> bytes:
    """Compose bytes from explicit inputs without discovering or writing files."""
    if layout not in ("book", "sheet", "report"):
        raise ValueError("PDF layout must be book, sheet or report")
    settings = project_config or {}
    config, resolved = resolve_document_config(text, language, project_config=settings)
    document_title = title if title is not None else pdf_title(manuscript, text, settings)
    sections = manuscript_sections(text, config) if layout != "report" or require_prose else []
    if require_prose and not any(paragraphs for _heading, paragraphs in sections):
        raise ValueError("The selected manuscript contains no supported prose")
    if layout == "report":
        selected_thresholds = thresholds or resolve_thresholds(project_config=settings)
        metrics = analyze_document(text, config, selected_thresholds).metrics
        return report_pdf(
            title=document_title,
            markdown=ReportFormatter.format_markdown_report(
                metrics, labels=resolved.labels, language_key=resolved.key,
            ),
            choice=choice,
        )
    if layout == "book":
        return book_pdf(title=document_title, author=author, chapters=sections, choice=choice)
    return manuscript_pdf(title=document_title, chapters=sections, choice=choice)
