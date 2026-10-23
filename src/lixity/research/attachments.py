"""Explicit attachment placement shared by individual and batch captures."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field, model_validator

from .images import extract_markdown_image_references
from .limits import MAX_IMAGE_ALT_CHARS, MAX_IMAGE_CAPTION_CHARS
from .models import Digest, SourceContext, StrictModel
from .repository import ResearchError
from .sections import _section_candidates, _section_spans, _section_subtree_end, update_section


class ImageBatchItem(StrictModel):
    file: Annotated[str, Field(min_length=1, max_length=4096)]
    alt: Annotated[str, Field(max_length=MAX_IMAGE_ALT_CHARS)] = ""
    caption: Annotated[str, Field(max_length=MAX_IMAGE_CAPTION_CHARS)] | None = None
    section: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    replace_reference: Annotated[str, Field(min_length=1, max_length=10000)] | None = None
    title: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    context: SourceContext | None = None
    origin_url: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    sha256: Digest | None = None

    @model_validator(mode="after")
    def valid_placement(self) -> ImageBatchItem:
        if "\n" in self.alt or "\r" in self.alt:
            raise ValueError("Image alternative text must be one line")
        if self.section is not None and self.replace_reference is not None:
            raise ValueError("Choose section or exact replacement, not both")
        return self


def place_attachment(body: str, markup: str, *, section: str | None,
                     replace_reference: str | None) -> str:
    """Preserve outside bytes and reject ambiguous or reserved replacement markers."""
    if replace_reference is not None:
        if not isinstance(replace_reference, str) or not replace_reference or section is not None:
            raise ResearchError("Image replacement requires one exact ordinary Markdown image reference")
        matches = [reference for reference in extract_markdown_image_references(body)
                   if reference.marker == replace_reference
                   and not re.match(r"<?lixity:", reference.destination, re.IGNORECASE)]
        if body.count(replace_reference) != 1 or len(matches) != 1:
            raise ResearchError("Image replacement reference must occur exactly once outside Markdown code")
        selected = matches[0]
        return body[:selected.start] + markup + body[selected.end:]
    if section is None:
        line_break = re.search(r"\r\n|\r|\n", body)
        newline = line_break.group() if line_break else "\n"
        prefix = "" if not body or body.endswith(newline * 2) else newline if body.endswith(newline) else newline * 2
        return body + prefix + markup.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline) + newline
    if not isinstance(section, str):
        raise ResearchError("Image section must identify an existing unique dossier heading")
    spans = _section_spans(body)
    section_matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
    if len(section_matches) != 1:
        raise ResearchError("Image section must identify an existing unique dossier heading; "
                            f"available: {_section_candidates(spans)}")
    span = section_matches[0]
    existing = body[span.content_start:_section_subtree_end(spans, span, len(body))]
    return update_section(body, section, existing.rstrip() + "\n\n" + markup)


def attachment_markup(alt: str, namespace: str, source_id: str, version_id: str,
                      caption: str | None) -> str:
    escaped = alt.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    return f"![{escaped}](lixity:{namespace}/{source_id}/{version_id})" + ("\n\n" + caption if caption else "")
