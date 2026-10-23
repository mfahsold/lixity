"""ATX-section spans and section edits shared by the research API and revisions.

Split out of ``research.api`` so ``research.revisions`` no longer needs a
deferred reverse import. The public names are re-exported from
``lixity.research.api`` for callers.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import NamedTuple

from .images import markdown_code_mask
from .repository import ResearchError


class _Section(NamedTuple):
    title: str
    level: int
    start: int
    content_start: int
    end: int


def _section_spans(body: str) -> list[_Section]:
    """Find ATX headings outside fenced/indented code, retaining source offsets."""
    headings: list[tuple[str, int, int, int]] = []
    offset = 0
    for line in markdown_code_mask(body, inline=False).splitlines(keepends=True):
        heading = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*$", line.rstrip("\r\n"))
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading.group(2)).strip()
            if title:
                headings.append((title, len(heading.group(1)), offset, offset + len(line)))
        offset += len(line)
    return [
        _Section(title, level, start, content_start,
                 headings[index + 1][2] if index + 1 < len(headings) else len(body))
        for index, (title, level, start, content_start) in enumerate(headings)
    ]


def _section_subtree_end(spans: list[_Section], selected: _Section, body_length: int) -> int:
    """Bound a section and its descendants at the next same/higher heading."""
    return next((span.start for span in spans
                 if span.start > selected.start and span.level <= selected.level), body_length)


def _editable_section_titles(spans: list[_Section]) -> list[str]:
    """Expose only real, unambiguous headings as section-editing targets."""
    counts = Counter(span.title.casefold() for span in spans)
    return [span.title for span in spans if counts[span.title.casefold()] == 1]


def _section_candidates(spans: list[_Section]) -> str:
    titles = list(dict.fromkeys(span.title for span in spans))
    shown = ", ".join(repr(title) for title in titles[:20]) or "none"
    return shown + (f"; {len(titles) - 20} more in the full dossier" if len(titles) > 20 else "")


def preamble_text(body: str) -> str:
    """Return the exact prefix before the first real ATX heading, if present."""
    spans = _section_spans(body)
    return body[:spans[0].start] if spans else body


def update_preamble(body: str, content: str) -> str:
    """Replace only the prefix; retain all heading and section bytes unchanged."""
    if not isinstance(content, str):
        raise ResearchError("Preamble content must be text")
    spans = _section_spans(body)
    prefix_end = spans[0].start if spans else len(body)
    if content == body[:prefix_end]:
        return body
    line_break = re.search(r"\r\n|\r|\n", body)
    newline = line_break.group() if line_break else "\n"
    replacement = content.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    if not spans:
        return replacement
    replacement = replacement.strip("\r\n")
    return (replacement + newline * 2 if replacement else "") + body[spans[0].start:]


def extract_sections(body: str) -> dict[str, str]:
    """Map ATX titles to direct content; retain all repeated-title fragments."""
    return _extract_sections(body, _section_spans(body))


def _extract_sections(body: str, spans: list[_Section]) -> dict[str, str]:
    preamble = body[:spans[0].start].strip() if spans else body.strip()
    sections: dict[str, str] = {}
    if preamble:
        label = "Introduction" if spans and spans[0].title.casefold() == "overview" else "Overview"
        sections[label] = preamble
    keys = {title.casefold(): title for title in sections}
    for span in spans:
        content = body[span.content_start:span.end].strip()
        existing = keys.get(span.title.casefold())
        if existing is None:
            sections[span.title] = content
            keys[span.title.casefold()] = span.title
        else:
            heading = body[span.start:span.content_start].rstrip("\r\n")
            sections[existing] += f"\n\n{heading}\n\n{content}"
    return sections


def update_section(body: str, section_title: str, new_content: str) -> str:
    """Replace a unique ATX section subtree; preserve bytes outside its content."""
    clean_title = section_title.strip()
    if not clean_title or "\r" in clean_title or "\n" in clean_title:
        raise ResearchError("Section title must be nonblank and contain only one line")
    spans = _section_spans(body)
    matches = [span for span in spans if span.title.casefold() == clean_title.casefold()]
    if len(matches) > 1:
        raise ResearchError(f"Section '{clean_title}' is ambiguous: {len(matches)} headings share this title")
    selected = matches[0] if matches else None
    nearby = body[selected.start:selected.content_start] if selected else body
    line_break = re.search(r"\r\n|\r|\n", nearby) or re.search(r"\r\n|\r|\n", body)
    newline = line_break.group() if line_break else "\n"
    replacement = new_content.replace("\r\n", "\n").replace("\r", "\n").strip("\n").replace("\n", newline)
    if selected is None:
        prefix = "" if not body or body.endswith(newline * 2) else newline if body.endswith(newline) else newline * 2
        return f"{body}{prefix}## {clean_title}{newline}{newline}{replacement}{newline}"
    end = _section_subtree_end(spans, selected, len(body))
    old_content = body[selected.content_start:end]
    leading_match = re.match(r"(?:[ \t]*(?:\r\n|\r|\n))*", old_content)
    leading = leading_match.group() if leading_match else ""
    remaining = old_content[len(leading):]
    trailing_match = re.search(r"(?:\r\n|\r|\n)(?:[ \t]*(?:\r\n|\r|\n))*$", remaining)
    trailing = trailing_match.group() if trailing_match else ""
    if not body[selected.start:selected.content_start].endswith(("\r", "\n")):
        leading = newline + leading
    if end < len(body) and not trailing:
        trailing = newline
    return body[:selected.content_start] + leading + replacement + trailing + body[end:]
