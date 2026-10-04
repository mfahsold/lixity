"""lixity.markdown_parser – Deterministic Markdown block parser with line anchors.

Parses Markdown into semantic blocks (headings, paragraphs, blockquotes, code)
preserving exact 1-based manuscript line numbers for precise editorial feedback.
Also owns the shared chapter segmentation used by the analyzer and structure
modules so chapter numbering stays identical everywhere.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import CorpusConfig

_FN_REF_PATTERN = re.compile(r"\[\^([^\]]+)\]")
_FN_REF_STRIP_PATTERN = re.compile(r"\[\^([^\]]+)\]")
SCENE_BREAK_RE = re.compile(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,}|•{3,}|#\s*#\s*#|\*\s+\*\s+\*)\s*$")


def _without_comments(content: str) -> str:
    """Remove comments while retaining their original line boundaries."""
    return re.sub(
        r"<!--.*?-->",
        lambda match: "".join(character for character in match.group()
                             if character in "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"),
        content, flags=re.DOTALL,
    )


def chapter_heading_spans(text: str, config: CorpusConfig) -> list[tuple[int, int, int, str]]:
    """Matched heading offsets, original line numbers and actual titles.

    Match one line at a time, including its terminator, so patterns may consume
    the full heading but never the next prose line through whitespace matches.
    """
    pattern = re.compile(config.chapter_regex)
    clean_lines = _without_comments(text).splitlines(keepends=True)
    headings: list[tuple[int, int, int, str]] = []
    offset = 0
    for index, original in enumerate(text.splitlines(keepends=True)):
        line = clean_lines[index] if index < len(clean_lines) else ""
        match = pattern.match(line)
        if match is None:
            match = pattern.match(line.rstrip("\r\n"))
        if match:
            title = line[match.end():].strip()
            if not title:
                title = re.sub(r"^#+\s*", "", match.group().strip())
            headings.append((offset, offset + len(original), index + 1, title))
        offset += len(original)
    return headings


def _chapter_spans(text: str, config: CorpusConfig) -> list[tuple[int, str, str, int]]:
    """Accepted chapters with original heading lines for profile alignment."""
    from .language import resolve_language

    if config.appendix_marker:
        text = text.split(config.appendix_marker, 1)[0]
    word_re = re.compile(resolve_language(config, sample_text=text).word_regex)
    headings = chapter_heading_spans(text, config)
    first_end = headings[0][0] if headings else len(text)
    first = _without_comments(text[:first_end]).strip()
    if not headings:
        # Without a configured chapter marker, every prose line belongs to the
        # same implicit chapter. Its first sentence is not a chapter title.
        title = first.split("\n", 1)[0][2:].strip() if first.startswith("# ") else ""
        body = text.strip()
        prose = re.sub(r"(?m)^#+.*$", "", re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL))
        return [(1, title, body, 1)] if word_re.search(prose) else []
    spans: list[tuple[int, int, int, str | None]] = []
    if first and not first.startswith("# "):
        spans.append((0, first_end, 1, None))
    for index, (_start, end, line, heading_title) in enumerate(headings):
        next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        spans.append((end, next_start, line, heading_title))
    chapters: list[tuple[int, str, str, int]] = []
    for start, end, line, saved_title in spans:
        block = text[start:end].strip()
        if not block:
            continue
        body = block
        if saved_title is None:
            lines = block.split("\n")
            title = lines[0].strip().replace("# ", "")
            body = "\n".join(lines[1:]).strip()
        else:
            title = saved_title
        prose = re.sub(r"(?m)^#+.*$", "", re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL))
        if not word_re.search(prose):
            continue
        chapters.append((len(chapters) + 1, title, body, line))
    return chapters


def split_chapters(text: str, config: CorpusConfig) -> list[tuple[int, str, str]]:
    """(chapter number, title, body) – single source of truth for all callers.

    The scholarly appendix (``config.appendix_marker``) is cut off first.
    A leading ``# `` title and its front matter before explicit chapters are
    excluded. Without configured chapter markers, all prose forms one implicit
    chapter.
    Bodies without tokens after comment/heading removal are skipped, using the
    configured word tokenizer. Quote-only chapters retain their numbers even
    when the paragraph profiler intentionally omits their content.
    """
    return [(number, title, body) for number, title, body, _line in _chapter_spans(text, config)]


def split_scenes(body: str) -> tuple[list[str], int]:
    """Split explicit dividers outside backtick/tilde fences; retain unit text."""
    parts: list[str] = []
    current: list[str] = []
    closing: re.Pattern[str] | None = None
    breaks = 0
    for line in body.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if closing is not None:
            if closing.fullmatch(stripped):
                closing = None
        else:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", stripped)
            if opening and (opening[1][0] == "~" or "`" not in opening[2]):
                marker = opening[1]
                closing = re.compile(r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*")
            elif SCENE_BREAK_RE.fullmatch(line):
                part = "".join(current)
                if part.strip():
                    parts.append(part)
                current = []
                breaks += 1
                continue
        current.append(line)
    part = "".join(current)
    if part.strip():
        parts.append(part)
    return parts, breaks


def strip_inline_markup(text: str) -> str:
    """Removes inline Markdown (comments, footnote anchors, emphasis) for counting.

    The plain text remains readable; the function is the shared cleaning stage
    of the analyzer, style profile and further analysis tools.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = _FN_REF_STRIP_PATTERN.sub("", text)
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", text)
    return text.strip()


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def parse_markdown_blocks(content: str, config: CorpusConfig | None = None) -> list[dict[str, Any]]:
    """Parses Markdown content into semantic blocks and filters editorial HTML comments."""
    if config and config.appendix_marker:
        content = content.split(config.appendix_marker, 1)[0]
    headings = chapter_heading_spans(content, config) if config else []
    heading_titles = {line: title for _start, _end, line, title in headings}
    clean_content = _without_comments(content)
    lines = clean_content.splitlines()

    blocks: list[dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if i + 1 in heading_titles:
            blocks.append({"type": "h2", "text": heading_titles[i + 1],
                           "start_line": i + 1, "end_line": i + 1})
            i += 1
            continue

        if stripped == "---":
            blocks.append({"type": "divider", "start_line": i + 1, "end_line": i + 1})
            i += 1
            continue

        if stripped.startswith("# "):
            blocks.append(
                {"type": "h1", "text": stripped[2:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        if stripped.startswith("## "):
            blocks.append(
                {"type": "h3" if config else "h2", "text": stripped[3:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        if stripped.startswith("### "):
            blocks.append(
                {"type": "h3", "text": stripped[4:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        # Quotes and callout blocks
        if stripped.startswith(">"):
            start_line = i + 1
            paras = []
            cur_p: list[str] = []
            while i < len(lines):
                q_line = lines[i].rstrip("\r\n").strip()
                if q_line.startswith(">"):
                    content_q = q_line[1:].strip()
                    if content_q == "":
                        if cur_p:
                            paras.append(" ".join(cur_p))
                            cur_p = []
                    else:
                        cur_p.append(content_q)
                    i += 1
                else:
                    break
            if cur_p:
                paras.append(" ".join(cur_p))
            blocks.append(
                {"type": "quote_block", "paras": paras, "start_line": start_line, "end_line": i}
            )
            continue

        # Footnote definitions [^id]: text
        fn_match = re.match(r"^\[\^([^\]]+)\]:\s*(.*)", stripped)
        if fn_match:
            start_line = i + 1
            fn_id = fn_match.group(1)
            fn_text = [fn_match.group(2).strip()]
            i += 1
            while i < len(lines):
                next_line = lines[i].rstrip("\r\n")
                if i + 1 in heading_titles:
                    break
                if next_line.startswith(("    ", "\t")):
                    fn_text.append(next_line.strip())
                    i += 1
                elif lines[i].strip() and not lines[i].strip().startswith("[^"):
                    fn_text.append(lines[i].strip())
                    i += 1
                else:
                    break
            blocks.append(
                {
                    "type": "footnote_def",
                    "id": fn_id,
                    "text": " ".join(fn_text),
                    "start_line": start_line,
                    "end_line": i,
                }
            )
            continue

        # List items
        if stripped.startswith(("- ", "* ")):
            start_line = i + 1
            item_text = [stripped[2:].strip()]
            i += 1
            while i < len(lines):
                n_line = lines[i].rstrip("\r\n")
                if (n_line.strip() and not n_line.strip().startswith(("- ", "* ", "#"))
                        and i + 1 not in heading_titles):
                    item_text.append(n_line.strip())
                    i += 1
                else:
                    break
            blocks.append(
                {
                    "type": "list_item",
                    "text": " ".join(item_text),
                    "start_line": start_line,
                    "end_line": i,
                }
            )
            continue

        # Body paragraph
        start_line = i + 1
        para_lines = [line.strip()]
        has_break = [line.endswith("  ")]
        i += 1
        while i < len(lines):
            raw_l = lines[i].rstrip("\r\n")
            if (not raw_l.strip() or raw_l.strip().startswith(("#", ">", "---", "- ", "* ", "[^"))
                    or i + 1 in heading_titles):
                break
            has_break.append(raw_l.endswith("  "))
            para_lines.append(raw_l.strip())
            i += 1

        parts = []
        for idx_p, p_text in enumerate(para_lines):
            parts.append(p_text)
            if idx_p < len(para_lines) - 1:
                if has_break[idx_p]:
                    parts.append("\n")
                else:
                    parts.append(" ")
        blocks.append(
            {"type": "p", "text": "".join(parts), "start_line": start_line, "end_line": i}
        )

    if config:
        chapters = _chapter_spans(content, config)
        chapter_numbers = {line: number for number, _title, _body, line in chapters}
        for block in blocks:
            if block["type"] == "h2":
                block["chapter_num"] = chapter_numbers.get(block["start_line"], 0)
        if chapters and blocks and not headings:
            blocks[0]["chapter_num"] = chapters[0][0]
            blocks[0]["chapter_title"] = chapters[0][1]
    return blocks
