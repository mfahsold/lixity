"""Shared in-memory manuscript and analysis PDF composition."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import resolve_thresholds, validate_author_name
from .formatters import ReportFormatter
from .markdown_parser import prose_paragraphs, split_chapters
from .models import CorpusConfig
from .pdf_layouts import FontChoice, book_pdf, manuscript_pdf, report_pdf
from .pipeline import analyze_document, resolve_document_config
from .project_identity import project_title
from .publication import load_publication, publication_imprint
from .style_fingerprint import FingerprintThresholds
from .workspace_labels import WORKSPACE_LABELS


def pdf_title(manuscript: str, text: str, project_config: Mapping[str, Any]) -> str:
    """Prefer the project's title, then a manuscript heading, then its file name."""
    return project_title(manuscript, text, project_config)


def manuscript_sections(text: str, config: CorpusConfig) -> list[tuple[str, list[str]]]:
    """Split chapter headings and prose using the existing manuscript parser."""
    sections = []
    for number, heading, body in split_chapters(text, config):
        sections.append((heading or f"Chapter {number}", prose_paragraphs(body, config)))
    return sections


def compose_pdf(
    text: str, *, manuscript: str, layout: str, language: str = "en",
    project_config: Mapping[str, Any] | None = None, title: str | None = None,
    author: str | None = None, thresholds: FingerprintThresholds | None = None,
    choice: FontChoice | None = None, require_prose: bool = False,
    identity_config: Mapping[str, Any] | None = None,
) -> bytes:
    """Compose bytes from explicit inputs without discovering or writing files."""
    if layout not in ("book", "sheet", "report"):
        raise ValueError("PDF layout must be book, sheet or report")
    settings = project_config or {}
    identity = identity_config if identity_config is not None else settings
    publication = load_publication(identity) if layout == "book" else None
    config, resolved = resolve_document_config(text, language, project_config=settings)
    document_title = project_title(manuscript, text, identity, title)
    document_author = validate_author_name(identity.get("author_name", "") if author is None else author)
    metadata = {"title": document_title, "author": document_author,
                "language": resolved.key if resolved.key != "generic" else "und"}
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
            author=document_author, metadata=metadata, choice=choice,
        )
    if layout == "book":
        return book_pdf(title=document_title, author=document_author, chapters=sections, choice=choice,
                        metadata=metadata,
                        front_matter=publication_imprint(
                            publication, WORKSPACE_LABELS.get(resolved.key, WORKSPACE_LABELS["en"]),
                        ) if publication else None)
    return manuscript_pdf(title=document_title, author=document_author, chapters=sections,
                          metadata=metadata, choice=choice)
