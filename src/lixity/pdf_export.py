"""Shared in-memory manuscript and analysis PDF composition."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import resolve_thresholds, validate_author_name, validate_draft_notice
from .formatters import ReportFormatter
from .manuscript_document import inline_runs, manuscript_sections
from .markdown_parser import prose_paragraphs
from .pdf_layouts import FontChoice, book_pdf, document_pdf, editor_pdf, manuscript_pdf, report_pdf
from .pipeline import analyze_document, resolve_document_config
from .project_identity import project_title
from .publication import load_publication, publication_imprint
from .style_fingerprint import FingerprintThresholds
from .workspace_labels import WORKSPACE_LABELS

PDF_LAYOUTS = ("editor", "book", "sheet", "report", "document")


def pdf_title(manuscript: str, text: str, project_config: Mapping[str, Any]) -> str:
    """Prefer the project's title, then a manuscript heading, then its file name."""
    return project_title(manuscript, text, project_config)


def compose_pdf(
    text: str, *, manuscript: str, layout: str, language: str = "en",
    project_config: Mapping[str, Any] | None = None, title: str | None = None,
    author: str | None = None, draft_notice: str | None = None,
    thresholds: FingerprintThresholds | None = None,
    choice: FontChoice | None = None, require_prose: bool = False,
    identity_config: Mapping[str, Any] | None = None,
) -> bytes:
    """Compose bytes from explicit inputs without discovering or writing files."""
    if layout not in PDF_LAYOUTS:
        raise ValueError("PDF layout must be " + ", ".join(PDF_LAYOUTS))
    settings = project_config or {}
    identity = identity_config if identity_config is not None else settings
    publication = load_publication(identity) if layout == "book" else None
    config, resolved = resolve_document_config(text, language, project_config=settings)
    document_title = project_title(manuscript, text, identity, title)
    if title is None and not identity.get("title"):
        document_title = "".join(run.text for run in inline_runs(document_title))
    document_author = validate_author_name(identity.get("author_name", "") if author is None else author)
    document_draft = validate_draft_notice(
        identity.get("draft_notice", "") if draft_notice is None else draft_notice
    )
    metadata = {"title": document_title, "author": document_author,
                "language": resolved.key if resolved.key != "generic" else "und"}
    if layout == "report":
        if require_prose and not prose_paragraphs(text, config):
            raise ValueError("The selected manuscript contains no supported prose")
        selected_thresholds = thresholds or resolve_thresholds(project_config=settings)
        metrics = analyze_document(text, config, selected_thresholds).metrics
        return report_pdf(
            title=document_title,
            markdown=ReportFormatter.format_markdown_report(
                metrics, labels=resolved.labels, language_key=resolved.key,
            ),
            author=document_author, draft_notice=document_draft,
            metadata=metadata, choice=choice,
        )
    sections = manuscript_sections(text, config, include_title=layout == "document")
    if require_prose and not any(
        block.kind in ("paragraph", "quote", "list_item") and block.text.strip()
        for _heading, blocks in sections for block in blocks
    ):
        raise ValueError("The selected manuscript contains no supported prose")
    if layout == "document":
        return document_pdf(title=document_title, author=document_author,
                            chapters=sections, metadata=metadata, choice=choice)
    if layout == "book":
        return book_pdf(title=document_title, author=document_author, draft_notice=document_draft,
                        chapters=sections, choice=choice, metadata=metadata,
                        front_matter=publication_imprint(
                            publication, WORKSPACE_LABELS.get(resolved.key, WORKSPACE_LABELS["en"]),
                        ) if publication else None)
    if layout == "editor":
        return editor_pdf(title=document_title, author=document_author, draft_notice=document_draft,
                          chapters=sections, metadata=metadata, choice=choice)
    return manuscript_pdf(title=document_title, author=document_author, draft_notice=document_draft,
                          chapters=sections, metadata=metadata, choice=choice)
