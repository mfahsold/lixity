"""lixity.markdown_parser – Deterministic Markdown block parser with line anchors.

Parses Markdown into semantic blocks (headings, paragraphs, blockquotes, code)
preserving exact 1-based manuscript line numbers for precise editorial feedback.
Also owns the shared chapter segmentation used by the analyzer and structure
modules so chapter numbering stays identical everywhere.
"""

from __future__ import annotations

import html as html_mod
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

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
    if not re.match(r"[\w-]+\s*:", first):
        return 0
    for index, line in enumerate(lines[1:], 1):
        if line.strip() in ("---", "..."):
            return index + 1
    return 0


def _fence_closer(line: str) -> re.Pattern[str] | None:
    """Recognize a backtick/tilde opener using the shared scene-fence rules."""
    opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
    if not opening or (opening[1][0] == "`" and "`" in opening[2]):
        return None
    marker = opening[1]
    return re.compile(r" {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*")


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
                title = re.sub(r"^#+\s*", "", match.group().strip())
            headings.append((offset, offset + len(original), index + 1, title))
        offset += len(original)
    return headings


def _chapter_spans(text: str, config: CorpusConfig) -> list[tuple[int, str, str, int]]:
    """Accepted chapters with original heading lines for profile alignment."""
    from .language import compile_word_pattern, resolve_language

    if config.appendix_marker:
        text = text.split(config.appendix_marker, 1)[0]
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
        prose = prose_text(body, _front_matter=False)
        return [(1, title, body, 1)] if word_re.search(prose) else []
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
            if prefix_blocks and prefix_blocks[0]["type"] not in ("p", "list_item", "quote_block"):
                # Nonprose prefixes must keep their fences and indentation intact.
                title = ""
            else:
                lines = block.split("\n")
                title = lines[0].strip().replace("# ", "")
                body = _trim_blank_lines("\n".join(lines[1:]))
        else:
            title = saved_title
        prose = prose_text(body, _front_matter=False)
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
    Bodies without supported prose tokens are skipped, using the configured
    word tokenizer. Quote-only chapters retain their numbers even when the
    paragraph profiler intentionally omits their content.
    """
    return [(number, title, body) for number, title, body, _line in _chapter_spans(text, config)]


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
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = _FN_REF_STRIP_PATTERN.sub("", text)
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", text)
    # Underscore emphasis cannot start/end inside a word (snake_case is data).
    text = re.sub(r"(?<!\w)_{1,3}(?=\S)(.*?\S)_{1,3}(?!\w)", r"\1", text)
    return text.strip()


_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def parse_markdown_blocks(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True
) -> list[dict[str, Any]]:
    """Parses Markdown content into semantic blocks and filters editorial HTML comments."""
    if config and config.appendix_marker:
        content = content.split(config.appendix_marker, 1)[0]
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

        if re.match(r"^#{3,6}\s", stripped):
            blocks.append(
                {"type": "h3", "text": stripped.lstrip("#").strip(), "start_line": i + 1, "end_line": i + 1}
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


def prose_paragraphs(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True
) -> list[str]:
    """Supported analysis prose, reusing blocks rather than splitting newlines.

    Body paragraphs, list items and quoted-block paragraphs contribute text.
    YAML front matter, headings, comments, code and footnote definitions do not.
    Inline emphasis and footnote anchors are removed. This is a bounded Markdown
    policy, not a general CommonMark implementation. Paragraph profiles retain
    their documented narrower body/list scope and original block line anchors.
    Chapter/scene callers disable document-only front matter handling.
    """
    paragraphs: list[str] = []
    for block in parse_markdown_blocks(content, config, _front_matter=_front_matter):
        values = (block["paras"] if block["type"] == "quote_block" else
                  [block["text"]] if block["type"] in ("p", "list_item") else [])
        for value in values:
            clean = strip_inline_markup(value)
            if clean:
                paragraphs.append(clean)
    return paragraphs


def prose_text(
    content: str, config: CorpusConfig | None = None, *, _front_matter: bool = True
) -> str:
    """Supported prose with a blank line between original semantic paragraphs."""
    return "\n\n".join(prose_paragraphs(content, config, _front_matter=_front_matter))


def parse_markdown_file(filepath: str) -> list[dict[str, Any]]:
    """Reads a Markdown file in a UTF-8-safe way and parses it into semantic blocks."""
    with open(filepath, encoding="utf-8") as f:
        return parse_markdown_blocks(f.read())


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
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)

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
