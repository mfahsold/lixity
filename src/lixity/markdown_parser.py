"""lixity.markdown_parser – Deterministic Markdown block parser with line anchors.

Parses Markdown into semantic blocks (headings, paragraphs, blockquotes, code)
preserving exact 1-based manuscript line numbers for precise editorial feedback.
Also owns the shared chapter segmentation used by the analyzer and structure
modules so chapter numbering stays identical everywhere.
"""

from __future__ import annotations

import html as html_mod
import re
from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from itertools import accumulate
from typing import TYPE_CHECKING, Any
from unicodedata import normalize
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from .models import CorpusConfig

_FN_REF_PATTERN = re.compile(r"\[\^([^\]]+)\]")
_FN_REF_STRIP_PATTERN = re.compile(r"\[\^([^\]]+)\]")
SCENE_BREAK_RE = re.compile(
    r"(?m)^\s*(?:-{3,}|-\s+-\s+-|\*{3,}|\*\s+\*\s+\*|_{3,}|_\s+_\s+_|"
    r"•{3,}|•\s+•\s+•|—{3,}|—\s+—\s+—|#\s*#\s*#|⁂)\s*$"
)
COMMENT_STRIP_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_COMMENT_STRIP_RE = COMMENT_STRIP_RE
_FRONT_MATTER_KEY_RE = re.compile(r"[\w-]+\s*:")
_FENCE_OPENER_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_HEADING_MARKUP_RE = re.compile(r"^#+\s*")
_HEADING_LINE_RE = re.compile(r"(?m)^#+.*$")
_HEADING_GE3_RE = re.compile(r"^#{3,6}\s")
_PREFACE_SENTENCE_END_RE = re.compile(r"""[.!?…][»«"“”'’)\]]*$""")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)")
_EM_TRIPLE_STRIP_RE = re.compile(r"\*\*\*(.*?)\*\*\*")
_EM_BOLD_STRIP_RE = re.compile(r"\*\*(.*?)\*\*")
_EM_ITALIC_STRIP_RE = re.compile(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)")
_EM_UNDERSCORE_STRIP_RE = re.compile(r"(?<!\w)_{1,3}(?=\S)(.*?\S)_{1,3}(?!\w)")
_EM_TRIPLE_HTML_RE = re.compile(r"\*\*\*(.+?)\*\*\*")
_EM_BOLD_HTML_RE = re.compile(r"\*\*(.+?)\*\*")
_EM_ITALIC_HTML_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_CHAPTER_SPANS_CACHE: dict[tuple[str, str], list[tuple[int, str, str, int]]] = {}


def _trim_blank_lines(content: str) -> str:
    """Trim boundary blank lines without changing indentation of retained text."""
    lines = content.splitlines(keepends=True)
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "".join(lines[start:end]).rstrip("\r\n")


def _is_indented_code(line: str) -> bool:
    """Use the same supported indentation boundary for blocks and dividers."""
    return line.startswith(("    ", "\t"))


def _front_matter_end(lines: list[str]) -> int:
    """Exclusive end of a closed leading YAML mapping, or zero when absent."""
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return 0
    first = next((line.strip() for line in lines[1:] if line.strip()), "")
    # A pair of scene dividers around prose is not metadata. Support the common
    # key/value front-matter form without interpreting arbitrary YAML values.
    if not _FRONT_MATTER_KEY_RE.match(first):
        return 0
    for index, line in enumerate(lines[1:], 1):
        if line.strip() in ("---", "..."):
            return index + 1
    return 0


def _fence_closer(line: str) -> re.Pattern[str] | None:
    """Recognize a backtick/tilde opener using the shared scene-fence rules."""
    stripped = line.rstrip("\r\n")
    if "`" not in stripped and "~" not in stripped:
        return None
    opening = _FENCE_OPENER_RE.match(stripped)
    if not opening or (opening[1][0] == "`" and "`" in opening[2]):
        return None
    marker = opening[1]
    return re.compile(r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*")


def _markdown_block_spans(text: str) -> Iterator[tuple[int, int, bool]]:
    """Yield original offsets for fenced code and comments, with a comment flag."""
    lines = text.splitlines(keepends=True)
    front_matter_end = _front_matter_end(lines)
    closing: re.Pattern[str] | None = None
    offset = fence_start = comment_end = 0
    comments_exhausted = False
    for index, line in enumerate(lines):
        end = offset + len(line)
        start = max(offset, comment_end)
        offset = end
        if closing is not None:
            if closing.fullmatch(line.rstrip("\r\n")):
                yield fence_start, end, False
                closing = None
            continue
        indent = 0 if index >= front_matter_end else None
        while start < end:
            # A fence can start after leading comments and at most three spaces.
            # Once a fence opens, comment-like text is literal until it closes.
            if indent is not None and text[start] in " `~":
                closing = _fence_closer(" " * indent + text[start:end])
                if closing is not None:
                    fence_start = start
                    break
            if comments_exhausted:
                break
            marker = text.find("<!--", start, end)
            if marker < 0:
                break
            stop = text.find("-->", marker + 4)
            if stop < 0:
                comments_exhausted = True
                break
            comment_end = stop + 3
            yield marker, comment_end, True
            if indent is not None:
                before = marker - start
                indent = (indent + before if indent + before <= 3 and text[start:marker] == " " * before
                          else None)
            start = comment_end
    if closing is not None:
        yield fence_start, len(text), False


def _strip_comments(content: str, *, preserve_lines: bool) -> str:
    if "<!--" not in content:
        return content
    parts: list[str] = []
    cursor = 0
    for start, end, is_comment in _markdown_block_spans(content):
        if is_comment:
            parts.append(content[cursor:start])
            if preserve_lines:
                parts.append("".join(character for character in content[start:end]
                                     if character in "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029"))
            cursor = end
    return "".join(parts) + content[cursor:] if parts else content


def strip_html_comments(content: str) -> str:
    """Remove Markdown HTML comments, retaining literal fenced content."""
    return _strip_comments(content, preserve_lines=False)


def _without_comments(content: str) -> str:
    """Remove Markdown HTML comments while retaining original line boundaries."""
    return _strip_comments(content, preserve_lines=True)


@lru_cache(maxsize=1)
def _appendix_offset(text: str, marker: str) -> int:
    """Find the first literal marker outside comments and fenced code."""
    start = text.find(marker)
    if start < 0:
        return len(text)
    for left, right, is_comment in _markdown_block_spans(text):
        if start + len(marker) <= left:
            break
        # A marker configured as a complete comment may deliberately mark a boundary.
        if is_comment and start == left and start + len(marker) == right:
            break
        if start < right:
            start = text.find(marker, right)
            if start < 0:
                return len(text)
    return start


def before_appendix(text: str, config: CorpusConfig) -> str:
    """Keep the original source up to its configured, visible appendix marker."""
    return text[:_appendix_offset(text, config.appendix_marker)] if config.appendix_marker else text


def chapter_heading_spans(text: str, config: CorpusConfig) -> list[tuple[int, int, int, str]]:
    """Matched heading offsets, original line numbers and actual titles.

    Match one line at a time, including its terminator, so patterns may consume
    the full heading but never the next prose line through whitespace matches.
    """
    pattern = re.compile(config.chapter_regex)
    clean_lines = _without_comments(text).splitlines(keepends=True)
    front_matter_end = _front_matter_end(clean_lines)
    headings: list[tuple[int, int, int, str]] = []
    offset = 0
    closing: re.Pattern[str] | None = None
    for index, original in enumerate(text.splitlines(keepends=True)):
        line = clean_lines[index] if index < len(clean_lines) else ""
        if index < front_matter_end:
            offset += len(original)
            continue
        if closing is not None:
            if closing.fullmatch(line.rstrip("\r\n")):
                closing = None
            offset += len(original)
            continue
        closing = _fence_closer(line)
        if closing is not None or _is_indented_code(line):
            offset += len(original)
            continue
        match = pattern.match(line)
        if match is None:
            match = pattern.match(line.rstrip("\r\n"))
        if match:
            title = line[match.end():].strip()
            if not title:
                title = _HEADING_MARKUP_RE.sub("", match.group().strip())
            headings.append((offset, offset + len(original), index + 1, title))
        offset += len(original)
    return headings


def legacy_whitespace_text(main_text: str, config: CorpusConfig) -> str:
    """Project appendix-trimmed text for historical whitespace word and character totals."""
    cleaned = strip_html_comments(main_text)
    parts: list[str] = []
    cursor = 0
    for start, end, _line, _title in chapter_heading_spans(cleaned, config):
        parts.append(cleaned[cursor:start])
        if cleaned[end - 1:end] == "\n":
            parts.append("\n")
        cursor = end
    parts.append(cleaned[cursor:])
    return _HEADING_LINE_RE.sub("", "".join(parts))


def _chapter_spans(text: str, config: CorpusConfig) -> list[tuple[int, str, str, int]]:
    """Accepted chapters with original heading lines for profile alignment.

    Every report asks for the same document's chapters; cache the most recent
    (text, configuration) result so one analysis scans and parses each chapter
    once instead of once per report. One entry keeps the retained text bounded.
    """
    key = (text, config.model_dump_json())
    cached = _CHAPTER_SPANS_CACHE.get(key)
    if cached is None:
        cached = _chapter_spans_uncached(text, config)
        _CHAPTER_SPANS_CACHE.clear()
        _CHAPTER_SPANS_CACHE[key] = cached
    return list(cached)


def _is_opening_prose(block: dict[str, Any], lines: list[str]) -> bool:
    """Recognize an opening paragraph while preserving legacy bare title lines."""
    if block["type"] != "p":
        return False
    if block["start_line"] == block["end_line"]:
        return bool(_PREFACE_SENTENCE_END_RE.search(block["text"]))
    first_line = strip_inline_markup(lines[block["start_line"] - 1])
    continuation = lines[block["start_line"]]
    initial = next((character for character in continuation if character.isalpha()), "")
    # An unmarked single-word title can be immediately followed by a sentence.
    return not (first_line.isalpha() and initial.isupper())


@lru_cache(maxsize=256)
def _has_chapter_prose(body: str, word_re: re.Pattern[str]) -> bool:
    prose = "\n\n".join(prose_paragraphs(body, _front_matter=False, _counting=False))
    return word_re.search(normalize("NFC", prose)) is not None


def _chapter_spans_uncached(text: str, config: CorpusConfig) -> list[tuple[int, str, str, int]]:
    """Compute accepted chapters with original heading lines for profile alignment."""
    from .language import compile_word_pattern, resolve_language

    text = before_appendix(text, config)
    word_re = compile_word_pattern(resolve_language(config, sample_text=text).word_regex)
    headings = chapter_heading_spans(text, config)
    first_end = headings[0][0] if headings else len(text)
    first_lines = _without_comments(text[:first_end]).splitlines(keepends=True)
    front_matter_end = _front_matter_end(first_lines)
    first = "".join(first_lines[front_matter_end:]).strip()
    if not headings:
        # Without a configured chapter marker, every prose line belongs to the
        # same implicit chapter. Its first sentence is not a chapter title.
        title = first.split("\n", 1)[0][2:].strip() if first.startswith("# ") else ""
        original_lines = text.splitlines(keepends=True)
        body = _trim_blank_lines("".join(original_lines[front_matter_end:]))
        prose = "\n\n".join(prose_paragraphs(body, _front_matter=False, _counting=False))
        return [(1, title, body, 1)] if word_re.search(normalize("NFC", prose)) else []
    spans: list[tuple[int, int, int, str | None]] = []
    if first and not first.startswith("# "):
        original_lines = text.splitlines(keepends=True)
        start = sum(len(line) for line in original_lines[:front_matter_end])
        spans.append((start, first_end, front_matter_end + 1, None))
    for index, (_start, end, line, heading_title) in enumerate(headings):
        next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        spans.append((end, next_start, line, heading_title))
    chapters: list[tuple[int, str, str, int]] = []
    for start, end, line, saved_title in spans:
        block = _trim_blank_lines(text[start:end])
        if not block:
            continue
        body = block
        if saved_title is None:
            prefix_blocks = parse_markdown_blocks(block, _front_matter=False)
            title = ""
            if (prefix_blocks and prefix_blocks[0]["type"] in ("p", "list_item", "quote_block")
                    and not _is_opening_prose(prefix_blocks[0], _without_comments(block).splitlines())):
                # Preserve an existing plain title separated from its prose.
                lines = block.split("\n")
                title = lines[0].strip().replace("# ", "")
                body = _trim_blank_lines("\n".join(lines[1:]))
        else:
            title = saved_title
        if not _has_chapter_prose(body, word_re):
            continue
        chapters.append((len(chapters) + 1, title, body, line))
    return chapters


def split_chapters(text: str, config: CorpusConfig) -> list[tuple[int, str, str]]:
    """(chapter number, title, body) – single source of truth for all callers.

    The scholarly appendix (``config.appendix_marker``) is cut off first.
    A leading ``# `` title and its front matter before explicit chapters are
    excluded. Without configured chapter markers, all prose forms one implicit
    chapter.
    Bodies without supported prose tokens are skipped, using the configured
    word tokenizer. Quote-only chapters retain their numbers even when the
    paragraph profiler intentionally omits their content.
    """
    return [(number, title, body) for number, title, body, _line in _chapter_spans(text, config)]


def chapter_body_line_offsets(text: str, config: CorpusConfig) -> dict[int, int]:
    """Map a chapter-body line to a manuscript line by adding its offset."""
    source = before_appendix(text, config)
    line_offsets = [0, *accumulate(len(line) for line in source.splitlines(keepends=True))]
    headings = chapter_heading_spans(source, config)
    heading_lines = [line for _start, _end, line, _title in headings]
    offsets = {}
    for number, _title, body, heading_line in _chapter_spans(text, config):
        next_heading = bisect_right(heading_lines, heading_line)
        stop = headings[next_heading][0] if next_heading < len(headings) else len(source)
        offset = source.rfind(body, line_offsets[heading_line - 1], stop)
        # The accepted body must be a complete line-aligned suffix of this source span.
        if offset < 0 or source[offset + len(body):stop].strip():
            continue
        line_offset = bisect_left(line_offsets, offset)
        if line_offsets[line_offset] == offset:
            offsets[number] = line_offset
    return offsets


def split_scenes(body: str) -> tuple[list[str], int]:
    """Split explicit dividers outside backtick/tilde fences; retain unit text."""
    parts: list[str] = []
    current: list[str] = []
    closing: re.Pattern[str] | None = None
    breaks = 0
    clean_lines = _without_comments(body).splitlines(keepends=True)
    for index, line in enumerate(body.splitlines(keepends=True)):
        clean_line = clean_lines[index] if index < len(clean_lines) else ""
        stripped = clean_line.rstrip("\r\n")
        if closing is not None:
            if closing.fullmatch(stripped):
                closing = None
        else:
            closing = _fence_closer(stripped)
            if (closing is None and not _is_indented_code(clean_line)
                    and SCENE_BREAK_RE.fullmatch(clean_line)):
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
    text = _COMMENT_STRIP_RE.sub("", text)
    text = _FN_REF_STRIP_PATTERN.sub("", text)
    text = _EM_TRIPLE_STRIP_RE.sub(r"\1", text)
    text = _EM_BOLD_STRIP_RE.sub(r"\1", text)
    text = _EM_ITALIC_STRIP_RE.sub(r"\1", text)
    # Underscore emphasis cannot start/end inside a word (snake_case is data).
    text = _EM_UNDERSCORE_STRIP_RE.sub(r"\1", text)
    return text.strip()


_BACKTICKS = re.compile(r"`+")


class _InlineDelimiters:
    """Index the shared recognizers' bounded pairs once per original text."""

    def __init__(self, text: str) -> None:
        self.closers: dict[int, int] = {}
        self.code: dict[int, tuple[int, int]] = {}
        stacks: dict[str, list[int]] = {"[": [], "(": []}
        index = 0
        while index < len(text):
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "\n":
                for stack in stacks.values():
                    stack.clear()
            elif char in stacks:
                stacks[char].append(index)
            elif char in "])":
                stack = stacks["[" if char == "]" else "("]
                if stack:
                    self.closers[stack.pop()] = index
            index += 1
        following: dict[int, int] = {}
        for run in reversed(list(_BACKTICKS.finditer(text))):
            # Preserve recognition even when a caller starts inside an
            # unmatched run: only a later complete run can close its suffix.
            for start in range(run.start(), run.end()):
                width = run.end() - start
                if width in following:
                    self.code[start] = following[width], width
            following[run.end() - run.start()] = run.end()


def _code_end(text: str, start: int, *, delimiters: _InlineDelimiters | None = None) -> tuple[int, int] | None:
    """Return the matching backtick span and its delimiter width, when closed."""
    if delimiters is not None:
        return delimiters.code.get(start)
    opening = _BACKTICKS.match(text, start)
    if opening is None:
        return None
    marker = opening.group()
    pattern = re.compile(r"(?<!`)" + re.escape(marker) + r"(?!`)")
    closing = pattern.search(text, start + len(marker))
    return (closing.end(), len(marker)) if closing else None


def _link_ranges(text: str, start: int, *, delimiters: _InlineDelimiters | None = None,
                 limit: int | None = None) -> tuple[tuple[int, int], tuple[int, int], int, bool] | None:
    """Recognize link ranges without copying labels during nested traversal."""
    limit = len(text) if limit is None else limit
    image = text.startswith("![", start)
    opening = start + 1 if image else start
    if opening >= limit or not text.startswith("[", opening):
        return None

    def closing_at(position: int, left: str, right: str) -> int | None:
        if delimiters is not None:
            end = delimiters.closers.get(position)
            return end if end is not None and end < limit else None
        depth = 1
        index = position + 1
        while index < limit and text[index] != "\n":
            if text[index] == "\\":
                index += 2
                continue
            if text[index] == left:
                depth += 1
            elif text[index] == right:
                depth -= 1
                if not depth:
                    return index
            index += 1
        return None

    label_end = closing_at(opening, "[", "]")
    if label_end is None:
        return None
    label = opening + 1, label_end
    destination_start = label_end + 1
    if destination_start < limit and text.startswith("(", destination_start):
        end = closing_at(destination_start, "(", ")")
    elif destination_start < limit and text.startswith("[", destination_start):
        end = closing_at(destination_start, "[", "]")
    else:
        return (label, label, label_end + 1, True) if image else None
    if end is None:
        return None
    return label, (destination_start + 1, end), end + 1, image


def _link_at(text: str, start: int, *, delimiters: _InlineDelimiters | None = None) -> tuple[str, str, int, bool] | None:
    """Read a bounded inline link/image destination, allowing grouped parentheses."""
    ranges = _link_ranges(text, start, delimiters=delimiters)
    if ranges is None:
        return None
    label_range, destination_range, end, image = ranges
    label = text[slice(*label_range)]
    return label, text[slice(*destination_range)] or label, end, image


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")

_LINK_DEFINITION = re.compile(r"(?m)^ {0,3}\[[^\]\n]+\]:[^\n]*(?:\n|$)")


def counting_inline_text(text: str) -> str:
    """Project bounded Markdown prose for counts, without changing display anchors.

    Link labels contribute; destinations, reference definitions, images and
    closed inline code do not. Malformed syntax remains literal text. Recognition
    is shared with manuscript presentation but never interprets or rejects TeX.
    Iterative label traversal avoids a recursion limit or silently lost text.
    Counts use canonical NFC; display text and manuscript anchors stay original.
    """
    if not any(marker in text for marker in ("\\", "`", "[")):
        return normalize("NFC", strip_inline_markup(text))
    text = _LINK_DEFINITION.sub(" ", text)
    delimiters = _InlineDelimiters(text)
    pending = [(0, len(text))]
    parts: list[str] = []
    while pending:
        index, limit = pending.pop()
        while index < limit:
            char = text[index]
            if char == "\\" and index + 1 < limit and text[index + 1] in r"\`*_{}[]()#+-.!":
                parts.append(text[index + 1])
                index += 2
                continue
            if char == "`":
                code = _code_end(text, index, delimiters=delimiters)
                if code and code[0] <= limit:
                    parts.append(" ")
                    index = code[0]
                    continue
            if char in "![":
                link = _link_ranges(text, index, delimiters=delimiters, limit=limit)
                if link:
                    label, _destination, end, image = link
                    if image:
                        parts.append(" ")
                        index = end
                        continue
                    pending.extend(((end, limit), label))
                    break
            parts.append(char)
            index += 1
    return normalize("NFC", strip_inline_markup("".join(parts)))


def _soft_break_offsets(lines: list[str], hard_breaks: list[bool] | None = None) -> tuple[int, ...]:
    """Offsets of the spaces inserted to fold physical lines into one block."""
    offsets = []
    offset = 0
    for index, line in enumerate(lines[:-1]):
        offset += len(line)
        if hard_breaks is None or not hard_breaks[index]:
            offsets.append(offset)
        offset += 1
    return tuple(offsets)


def parse_markdown_blocks(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True,
    _quote_lines: bool = False,
) -> list[dict[str, Any]]:
    """Parses Markdown content into semantic blocks and filters editorial HTML comments."""
    if config:
        content = before_appendix(content, config)
    headings = chapter_heading_spans(content, config) if config else []
    heading_titles = {line: title for _start, _end, line, title in headings}
    clean_content = _without_comments(content)
    lines = clean_content.splitlines()

    blocks: list[dict[str, Any]] = []
    i = _front_matter_end(lines) if _front_matter else 0

    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        closing = _fence_closer(line)
        if closing is not None:
            start_line = i + 1
            code_lines = [line]
            i += 1
            while i < len(lines):
                code_lines.append(lines[i])
                i += 1
                if closing.fullmatch(code_lines[-1]):
                    break
            blocks.append({"type": "code", "text": "\n".join(code_lines),
                           "start_line": start_line, "end_line": i})
            continue

        if _is_indented_code(line):
            start_line = i + 1
            code_lines = []
            while i < len(lines) and _is_indented_code(lines[i]):
                code_lines.append(lines[i])
                i += 1
            blocks.append({"type": "code", "text": "\n".join(code_lines),
                           "start_line": start_line, "end_line": i})
            continue

        if i + 1 in heading_titles:
            blocks.append({"type": "h2", "text": heading_titles[i + 1],
                           "start_line": i + 1, "end_line": i + 1})
            i += 1
            continue

        if SCENE_BREAK_RE.fullmatch(line):
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

        if _HEADING_GE3_RE.match(stripped):
            blocks.append(
                {"type": "h3", "text": stripped.lstrip("#").strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        # Quotes and callout blocks
        if stripped.startswith(">"):
            start_line = i + 1
            paras = []
            quote_breaks = []
            quote_lines = []
            quote_start = start_line
            cur_p: list[str] = []
            while i < len(lines):
                q_line = lines[i].rstrip("\r\n").strip()
                if q_line.startswith(">"):
                    content_q = q_line[1:].strip()
                    if content_q == "":
                        if cur_p:
                            paras.append(" ".join(cur_p))
                            if _quote_lines:
                                quote_breaks.append(_soft_break_offsets(cur_p))
                                quote_lines.append((quote_start, i))
                            cur_p = []
                    else:
                        if not cur_p:
                            quote_start = i + 1
                        cur_p.append(content_q)
                    i += 1
                else:
                    break
            if cur_p:
                paras.append(" ".join(cur_p))
                if _quote_lines:
                    quote_breaks.append(_soft_break_offsets(cur_p))
                    quote_lines.append((quote_start, i))
            blocks.append(
                {"type": "quote_block", "paras": paras, "start_line": start_line, "end_line": i}
            )
            if _quote_lines:
                blocks[-1]["quote_breaks"] = quote_breaks
                blocks[-1]["quote_lines"] = quote_lines
            continue

        # Footnote definitions [^id]: text
        fn_match = _FOOTNOTE_DEF_RE.match(stripped)
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
                if (n_line.strip() and not n_line.strip().startswith(("- ", "* ", "#", ">", "---", "[^"))
                        and _fence_closer(n_line) is None
                        and (_is_indented_code(n_line) or not SCENE_BREAK_RE.fullmatch(n_line))
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
            if _quote_lines:
                blocks[-1]["quote_breaks"] = [_soft_break_offsets(item_text)]
            continue

        # Body paragraph
        start_line = i + 1
        para_lines = [line.strip()]
        has_break = [line.endswith("  ")]
        i += 1
        while i < len(lines):
            raw_l = lines[i].rstrip("\r\n")
            if (not raw_l.strip() or raw_l.strip().startswith(("#", ">", "---", "- ", "* ", "[^"))
                    or _fence_closer(raw_l) is not None
                    or (not _is_indented_code(raw_l) and SCENE_BREAK_RE.fullmatch(raw_l))
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
        if _quote_lines:
            blocks[-1]["quote_breaks"] = [_soft_break_offsets(para_lines, has_break)]

    if config:
        chapters = _chapter_spans(content, config)
        chapter_numbers = {line: number for number, _title, _body, line in chapters}
        for block in blocks:
            if block["type"] == "h2":
                block["chapter_num"] = chapter_numbers.get(block["start_line"], 0)
        if chapters and blocks and (not headings or (
            chapters[0][3] < headings[0][2] and _is_opening_prose(blocks[0], lines)
        )):
            blocks[0]["chapter_num"] = chapters[0][0]
            blocks[0]["chapter_title"] = chapters[0][1]
    return blocks


def _prose_values(block: dict[str, Any]) -> Iterator[str]:
    if block["type"] == "quote_block":
        yield from block["paras"]
    elif block["type"] in ("p", "list_item"):
        yield block["text"]


@dataclass(frozen=True)
class CountedChapterPassage:
    """Counted prose with a chapter-body line range and context boundaries."""

    start_line: int
    end_line: int
    text: str
    region: int


def counted_chapter_passages(body: str) -> Iterator[CountedChapterPassage]:
    """Yield full counted prose with 1-based lines and structural regions."""
    region = 0
    for block in parse_markdown_blocks(body, _front_matter=False, _quote_lines=True):
        kind = block["type"]
        if kind not in ("p", "list_item"):
            region += 1
        if kind not in ("p", "list_item", "quote_block"):
            continue
        lines = block.get("quote_lines", [(block["start_line"], block["end_line"])])
        for (start, end), value in zip(lines, _prose_values(block), strict=True):
            clean = counting_inline_text(value)
            if clean:
                yield CountedChapterPassage(start, end, clean, region)
        if kind == "quote_block":
            region += 1


def _extract_prose_paragraphs(
    content: str, config: CorpusConfig | None, front_matter: bool, counting: bool
) -> list[str]:
    paragraphs: list[str] = []
    for block in parse_markdown_blocks(content, config, _front_matter=front_matter):
        for value in _prose_values(block):
            clean = counting_inline_text(value) if counting else strip_inline_markup(value)
            if clean:
                paragraphs.append(clean)
    return paragraphs


@lru_cache(maxsize=128)
def _prose_paragraphs_cached(
    content: str, front_matter: bool, counting: bool
) -> tuple[str, ...]:
    return tuple(_extract_prose_paragraphs(content, None, front_matter, counting))


def prose_paragraphs(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True,
    _counting: bool = True,
) -> list[str]:
    """Supported analysis prose, reusing blocks rather than splitting newlines.

    Body paragraphs, list items and quoted-block paragraphs contribute text.
    YAML front matter, headings, comments, code and footnote definitions do not.
    Inline counting excludes non-prose markup. The private membership projection
    retains the established chapter numbering even for image/code-only bodies.
    This is a bounded Markdown policy, not a general CommonMark implementation.
    Paragraph profiles retain
    their documented narrower body/list scope and original block line anchors.
    Chapter/scene callers disable document-only front matter handling.
    """
    if config is None:
        return list(_prose_paragraphs_cached(content, _front_matter, _counting))
    return _extract_prose_paragraphs(content, config, _front_matter, _counting)


def prose_text(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True
) -> str:
    """Supported prose with a blank line between original semantic paragraphs."""
    return "\n\n".join(prose_paragraphs(content, config, _front_matter=_front_matter))



def inline_markdown_to_html(
    text: str,
    fn_counter: dict[str, int] | None = None,
    document_id: str = "doc",
) -> str:
    """Converts inline Markdown into a safe XHTML5 fragment for EPUB 3.3.

    - ``**bold**`` → ``<strong>``, ``*italic*`` → ``<em>``, ``***x***`` → both.
    - ``[^id]`` → EPUB footnote anchor (``epub:type="noteref"``) with a unique id.
    - ``[Text](url)`` → ``<a href="url">``.
    - Line breaks (double space in the source) → ``<br/>``.
    - ``fn_counter`` ensures document-wide unique reference IDs.
    """
    if not text:
        return ""

    if fn_counter is None:
        fn_counter = {}

    # 1. Protect literal asterisks
    text = text.replace(r"\*", "\x01ASTERISK\x02")

    # 2. HTML-escape
    text = html_mod.escape(text, quote=False)

    # 3. Footnote references [^id] with unique anchor ID. Protect generated
    # attributes from later Markdown substitutions in untrusted identifiers.
    footnotes: list[str] = []
    placeholder_prefix = "\x01FOOTNOTE\x02"
    while placeholder_prefix in text or placeholder_prefix in document_id:
        placeholder_prefix += "\x01"

    def fn_ref(m: re.Match[str]) -> str:
        fn_id = html_mod.unescape(m.group(1))
        n = fn_counter.get(fn_id, 0) + 1
        fn_counter[fn_id] = n
        anchor_id = html_mod.escape(f"fnref{fn_id}-{document_id}-{n}", quote=True)
        destination = html_mod.escape("#fn" + fn_id, quote=True)
        footnotes.append(f'<a epub:type="noteref" id="{anchor_id}" href="{destination}" '
                         f'role="doc-noteref" class="fnref">{m.group(1)}</a>')
        return f"{placeholder_prefix}{len(footnotes) - 1}\x03"

    text = _FN_REF_PATTERN.sub(fn_ref, text)

    # 4. Bold-italic, bold, italic
    text = _EM_TRIPLE_HTML_RE.sub(r"<strong><em>\1</em></strong>", text)
    text = _EM_BOLD_HTML_RE.sub(r"<strong>\1</strong>", text)
    text = _EM_ITALIC_HTML_RE.sub(r"<em>\1</em>", text)

    # 5. Links [text](url)
    def link(m: re.Match[str]) -> str:
        destination = html_mod.unescape(m.group(2))
        try:
            scheme = urlsplit(destination.strip()).scheme.lower()
        except ValueError:
            return m.group(1)
        if (scheme not in ("", "http", "https", "mailto")
                or any(ord(character) < 32 or ord(character) == 127 for character in destination)):
            return m.group(1)
        return f'<a href="{html_mod.escape(destination, quote=True)}">{m.group(1)}</a>'

    text = _LINK_PATTERN.sub(link, text)

    # 6. Hard line breaks
    text = text.replace("\n", "<br/>\n")
    for index, anchor in enumerate(footnotes):
        text = text.replace(f"{placeholder_prefix}{index}\x03", anchor)

    # 7. Restore literal asterisks
    return text.replace("\x01ASTERISK\x02", "*")
