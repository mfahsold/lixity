"""Presentation blocks for manuscript exports, independent of analysis filtering.

The shared Markdown parser supplies structure; this projection retains prefaces,
notes, dividers and appendices. Embedded TeX support is deliberately limited to
text formatting, escaped punctuation and explicit breaks. No TeX is executed.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

from .markdown_parser import (
    SCENE_BREAK_RE,
    _code_end,
    _fence_closer,
    _front_matter_end,
    _InlineDelimiters,
    _is_indented_code,
    _link_at,
    _without_comments,
    chapter_heading_spans,
    inline_markdown_to_html,
    parse_markdown_blocks,
)
from .models import CorpusConfig

RunStyle = Literal["plain", "emphasis", "strong", "strong_emphasis", "code"]
BlockKind = Literal[
    "paragraph", "heading", "quote", "list_item", "scene_break", "note", "code", "page_break",
]


@dataclass(frozen=True)
class TextRun:
    """Readable text with one supported presentation style."""

    text: str
    style: RunStyle = "plain"


@dataclass(frozen=True)
class ManuscriptBlock:
    """A semantic presentation block; heading levels retain the source level."""

    kind: BlockKind
    text: str = ""
    level: int = 3


@dataclass(frozen=True)
class SourceManuscriptBlock:
    """Source-ordered presentation with absolute, inclusive manuscript lines.

    Text is untrusted data, not HTML. Unlike the PDF projection, this form does
    not interpret or validate embedded TeX, suppress titles or relocate notes.
    """

    kind: BlockKind
    text: str
    level: int
    start_line: int
    end_line: int
    is_chapter: bool = False


ManuscriptSections = list[tuple[str, list[ManuscriptBlock]]]

_LIST = re.compile(r"^ {0,3}([-+*]|\d+[.)])\s+")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+")
_PAGE_BREAK = re.compile(r"\\(?:newpage|clearpage)\s*")
_UNDERSCORE = re.compile(r"(?<!\w)(_{1,3})(?=\S)(.*?\S)\1(?!\w)")
_COMMAND = re.compile(r"[A-Za-z]+[0-9]*")
_WINDOWS_PATH = re.compile(r'(?:[A-Za-z]:\\|\\\\[^\\\s]+\\)[^\s{}*<>|?"]+')
_SPACED_PATH = re.compile(r'(?:[ \t]+[\w.-]+)+\\[^\s{}*<>|?"]+')
_TEX_TAGS = {
    "emph": "emph", "textit": "em", "textbf": "strong", "texttt": "code",
    "textnormal": "normal",
}


class _RunReader(HTMLParser):
    """Read only markup produced by the shared safe inline Markdown renderer."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[TextRun] = []
        self.styles: list[tuple[str, tuple[bool, bool, bool]]] = []
        self.current = (False, False, False)
        self.after_break = False

    def _append(self, text: str) -> None:
        if not text:
            return
        emphasis, strong, code = self.current
        style: RunStyle = (
            "code" if code else "strong_emphasis" if emphasis and strong
            else "emphasis" if emphasis else "strong" if strong else "plain"
        )
        if self.runs and self.runs[-1].style == style:
            self.runs[-1] = TextRun(self.runs[-1].text + text, style)
        else:
            self.runs.append(TextRun(text, style))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self._append("\n")
            self.after_break = True
            return
        if tag == "a" and dict(attrs).get("role") == "doc-noteref":
            self._append("[")
            self.styles.append(("noteref", self.current))
            return
        if tag not in ("em", "emph", "strong", "code", "normal"):
            return
        self.styles.append((tag, self.current))
        emphasis, strong, code = self.current
        self.current = (
            (False, False, False) if tag == "normal" else
            (not emphasis if tag == "emph" else emphasis or tag == "em",
             strong or tag == "strong", code or tag == "code")
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.styles and self.styles[-1][0] == "noteref":
            self._append("]")
            self.styles.pop()
        elif self.styles and self.styles[-1][0] == tag:
            _tag, self.current = self.styles.pop()

    def handle_data(self, data: str) -> None:
        if self.after_break and data.startswith("\n"):
            data = data[1:]
        self.after_break = False
        self._append(data)


def _inline_runs(text: str, *, start_line: int = 1, page_breaks: bool = False) -> list[TextRun]:
    delimiters = _InlineDelimiters(text)
    protected: list[str] = []
    prefix = "\x01PRESENTATION\x02"
    while prefix in text:
        prefix += "\x01"

    def protect(fragment: str) -> str:
        protected.append(fragment)
        return f"{prefix}{len(protected) - 1}\x03"

    def failure(message: str, offset: int) -> ValueError:
        return ValueError(f"{message} at line {start_line + text.count(chr(10), 0, offset)}")

    def translate(start: int, *, group: bool = False, depth: int = 0) -> tuple[str, int]:
        if depth > 32:
            raise failure("TeX grouping exceeds the supported nesting limit", start)
        output: list[str] = []
        index = start
        while index < len(text):
            char = text[index]
            link = _link_at(text, index, delimiters=delimiters) if char in "![" else None
            if link:
                label, reference, index, image = link
                if image:
                    output.append(protect(html.escape(
                        f"[Image: {label or 'unlabelled'}; reference: {reference}]",
                    )))
                else:
                    label_runs = _inline_runs(label, start_line=start_line + text.count("\n", 0, index))
                    for run in label_runs:
                        tag = {"emphasis": "em", "strong": "strong", "code": "code",
                               "strong_emphasis": "strong"}.get(run.style)
                        literal = html.escape(run.text)
                        if run.style == "strong_emphasis":
                            literal = "<em>" + literal + "</em>"
                        output.append(protect(f"<{tag}>{literal}</{tag}>" if tag else literal))
                continue
            path = _WINDOWS_PATH.match(text, index)
            if path:
                path_end = path.end()
                # A spaced directory can continue an already explicit drive/UNC
                # path. Stop once its last component has a file extension.
                while not re.search(r"\.[A-Za-z0-9]+[.,;:!?)]?$", text[index:path_end]):
                    continuation = _SPACED_PATH.match(text, path_end)
                    if continuation is None:
                        break
                    path_end = continuation.end()
                output.append(protect(html.escape(text[index:path_end])))
                index = path_end
                continue
            if char == "`":
                span = _code_end(text, index, delimiters=delimiters)
                if span:
                    end, width = span
                    literal = text[index + width:end - width].replace("\n", " ")
                    output.append(protect("<code>" + html.escape(literal) + "</code>"))
                    index = end
                    continue
            if char == "$":
                closing = re.search(r"(?<!\\)\$", text[index + 1:])
                if closing:
                    content = text[index + 1:index + 1 + closing.start()]
                    mathematical = (
                        text.startswith("$$", index)
                        or bool(content and content == content.strip()
                                and (any(c.isalpha() for c in content)
                                     or any(c in "+*=^_{}<>" for c in content)))
                    )
                    if mathematical:
                        raise failure("Unsupported TeX math delimiter $", index)
            if char == "}" and group:
                return "".join(output), index + 1
            if char == "{" and group:
                nested, index = translate(index + 1, group=True, depth=depth + 1)
                output.append(nested)
                continue
            if char != "\\":
                output.append(char)
                index += 1
                continue
            command_start = index
            index += 1
            if index >= len(text):
                raise failure("Unsupported TeX trailing backslash", command_start)
            if text[index] == "\\":
                output.append(protect("<br/>"))
                index += 1
                while index < len(text) and text[index].isspace():
                    index += 1
                continue
            if text[index] in "{}%&#_$*":
                output.append(protect(html.escape(text[index])))
                index += 1
                continue
            command_match = _COMMAND.match(text, index)
            command = command_match.group() if command_match else text[index]
            index += len(command)
            if command in ("newpage", "clearpage") and page_breaks:
                line_start = text.rfind("\n", 0, command_start) + 1
                line_end = text.find("\n", index)
                if line_end < 0:
                    line_end = len(text)
                if _PAGE_BREAK.fullmatch(text[line_start:line_end].strip()):
                    continue
            tag = _TEX_TAGS.get(command)
            if tag is None:
                raise failure(f"Unsupported TeX command \\{command}", command_start)
            while index < len(text) and text[index].isspace():
                index += 1
            if index >= len(text) or text[index] != "{":
                raise failure(f"TeX command \\{command} requires a braced argument", command_start)
            argument, index = translate(index + 1, group=True, depth=depth + 1)
            if tag == "code":
                argument = protect(html.escape(argument))
            output.extend((protect(f"<{tag}>"), argument, protect(f"</{tag}>")))
        if group:
            raise failure("TeX group is missing a closing brace", start - 1)
        return "".join(output), index

    prepared, _end = translate(0)
    prepared = _UNDERSCORE.sub(lambda match: "*" * len(match[1]) + match[2]
                               + "*" * len(match[1]), prepared)
    rendered = inline_markdown_to_html(prepared)
    # Code-font arguments can contain protected escaped punctuation or TeX tags.
    token = re.compile(re.escape(prefix) + r"(\d+)\x03")
    while token.search(rendered):
        rendered = token.sub(lambda match: protected[int(match[1])], rendered)
    reader = _RunReader()
    reader.feed(rendered)
    reader.close()
    return reader.runs


def inline_runs(text: str) -> list[TextRun]:
    """Render bounded inline Markdown/TeX, preserving code and readable references.

    Supported TeX commands are ``emph``, ``textit``, ``textbf``, ``texttt`` and
    ``textnormal`` with braced arguments, escaped ``{}%&#_$*`` and ``\\\\`` breaks.
    Other commands, including math environments and file access, fail explicitly.
    Images become labelled alternatives with their source reference; nothing is
    fetched. Currency and other ordinary dollar signs remain literal text.
    """
    return _inline_runs(text)


def _protected_source(text: str) -> tuple[str, str, list[bool]]:
    """Shield comments in literal code from the analysis parser's comment filter."""
    sentinel = "\ue000"
    while sentinel in text:
        sentinel = chr(ord(sentinel) + 1)
    parts: list[str] = []
    index = 0
    while index < len(text):
        opening = text.find("`", index)
        if opening < 0:
            parts.append(text[index:])
            break
        parts.append(text[index:opening])
        span = _code_end(text, opening)
        end = span[0] if span else opening + 1
        parts.append(text[opening:end].replace("<", sentinel))
        index = end
    lines = "".join(parts).splitlines(keepends=True)
    protected: list[str] = []
    literal_lines: list[bool] = []
    closing: re.Pattern[str] | None = None
    for line in lines:
        literal = closing is not None or _is_indented_code(line)
        if closing is not None:
            if closing.fullmatch(line.rstrip("\r\n")):
                closing = None
        else:
            closing = _fence_closer(line)
            literal = literal or closing is not None
        literal_lines.append(literal)
        if literal:
            protected.append(line.replace("<", sentinel))
            continue
        protected.append(line)
    return "".join(protected), sentinel, literal_lines


def _joined_lines(lines: list[str]) -> str:
    """Fold soft wraps while retaining Markdown's explicit two-space breaks."""
    return "".join(line.strip() + ("\n" if line.endswith("  ") else " ")
                   for line in lines[:-1]) + (lines[-1].strip() if lines else "")


def _source_blocks(
    text: str, *, start_line: int, front_matter: bool, validate_inline: bool,
) -> list[SourceManuscriptBlock]:
    protected, sentinel, literal_lines = _protected_source(text)
    clean = _without_comments(protected)
    lines = clean.splitlines()
    metadata_end = _front_matter_end(lines) if front_matter else 0
    # Blank separators fix analysis-oriented list/note continuation swallowing
    # presentation boundaries. The line map keeps literal code slices exact.
    shadow: list[str] = []
    line_map: list[int] = []
    for index, line in enumerate(lines):
        boundary = (
            _LIST.match(line) or _HEADING.match(line) or line.lstrip().startswith("[^")
            or (line.lstrip().startswith(">")
                and not (index and lines[index - 1].lstrip().startswith(">")))
            or SCENE_BREAK_RE.fullmatch(line) or _PAGE_BREAK.fullmatch(line.strip())
        )
        code_start = (literal_lines[index] and not (index and literal_lines[index - 1])
                      and (_fence_closer(line) is not None or not index
                           or not lines[index - 1].strip()))
        if index >= metadata_end and (code_start or (not literal_lines[index] and boundary)):
            shadow.append("")
            line_map.append(index)
        shadow.append(line)
        line_map.append(index)
        if index >= metadata_end and not literal_lines[index] and _PAGE_BREAK.fullmatch(line.strip()):
            shadow.append("")
            line_map.append(index)
    result: list[SourceManuscriptBlock] = []
    for block in parse_markdown_blocks("\n".join(shadow), _front_matter=front_matter):
        first = line_map[block["start_line"] - 1]
        last = line_map[block["end_line"] - 1]
        kind = block["type"]
        value = str(block.get("text", "")).replace(sentinel, "<")

        def presentation(
            kind: BlockKind, value: str = "", level: int = 3, *,
            first_line: int = first, last_line: int = last,
        ) -> SourceManuscriptBlock:
            return SourceManuscriptBlock(
                kind, value, level, start_line + first_line, start_line + last_line,
            )

        if kind == "code":
            code_lines = lines[first:last + 1]
            closing = _fence_closer(code_lines[0])
            if closing:
                code_lines = code_lines[1:]
                if code_lines and closing.fullmatch(code_lines[-1]):
                    code_lines.pop()
            else:
                code_lines = [line[1:] if line.startswith("\t") else line[4:]
                              for line in code_lines]
            result.append(presentation("code", "\n".join(code_lines).replace(sentinel, "<")))
            continue
        raw = "\n".join(lines[first:last + 1]).replace(sentinel, "<")
        if validate_inline:
            _inline_runs(raw, start_line=start_line + first, page_breaks=True)
        if kind in ("h1", "h2", "h3"):
            match = _HEADING.match(lines[first])
            result.append(presentation("heading", value, len(match[1]) if match else 3))
        elif kind == "divider":
            result.append(presentation("scene_break", "* * *"))
        elif kind == "quote_block":
            current: list[str] = []
            paragraph_start = first
            for index in range(first, last + 1):
                quote_line = lines[index]
                quote = re.sub(r"^\s*> ?", "", quote_line).replace(sentinel, "<")
                if quote.strip():
                    if not current:
                        paragraph_start = index
                    current.append(quote)
                elif current:
                    result.append(presentation(
                        "quote", _joined_lines(current),
                        first_line=paragraph_start, last_line=index - 1,
                    ))
                    current = []
            if current:
                result.append(presentation(
                    "quote", _joined_lines(current), first_line=paragraph_start,
                ))
        elif kind == "footnote_def":
            note_lines = [line.replace(sentinel, "<") for line in lines[first:last + 1]]
            note_lines[0] = re.sub(r"^\s*\[\^[^\]]+\]:[ \t]*", "", note_lines[0])
            result.append(presentation("note", f"[{block['id']}] {_joined_lines(note_lines)}"))
        elif _PAGE_BREAK.fullmatch(value.strip()):
            result.append(presentation("page_break"))
        elif kind == "list_item":
            result.append(presentation("list_item", _joined_lines(
                [line.replace(sentinel, "<") for line in lines[first:last + 1]],
            )))
        else:
            result.append(presentation("list_item" if _LIST.match(value) else "paragraph", value))
    return result


def _blocks(text: str, *, start_line: int, front_matter: bool) -> list[ManuscriptBlock]:
    """Keep the established strict PDF policy over the shared source projection."""
    result = [ManuscriptBlock(block.kind, block.text, block.level) for block in _source_blocks(
        text, start_line=start_line, front_matter=front_matter, validate_inline=True,
    )]
    return ([block for block in result if block.kind != "note"]
            + [block for block in result if block.kind == "note"])


def manuscript_blocks(text: str, config: CorpusConfig) -> list[SourceManuscriptBlock]:
    """Retain supported document content in source order, without analysis filters.

    Configured chapter headings, including empty chapters, are explicit blocks.
    Preface titles, note positions and the analysis-excluded appendix remain.
    Consumers must escape text; unsupported inline syntax stays literal and no
    image, URL or embedded TeX instruction is executed or fetched.
    """
    protected, sentinel, _literal_lines = _protected_source(text)
    headings = chapter_heading_spans(protected, config)
    source_lines = text.splitlines()
    first_end = headings[0][0] if headings else len(text)
    blocks = _source_blocks(
        text[:first_end], start_line=1, front_matter=True, validate_inline=False,
    )
    for index, (_start, end, line, raw_title) in enumerate(headings):
        heading_line = source_lines[line - 1]
        match = _HEADING.match(heading_line)
        blocks.append(SourceManuscriptBlock(
            "heading", raw_title.replace(sentinel, "<"), len(match[1]) if match else 2,
            line, line, is_chapter=True,
        ))
        next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        blocks.extend(_source_blocks(
            text[end:next_start], start_line=line + 1, front_matter=False, validate_inline=False,
        ))
    return blocks


def manuscript_sections(
    text: str, config: CorpusConfig, *, include_title: bool = False,
) -> ManuscriptSections:
    """Retain the whole document using configured chapter boundaries.

    By default the first ``#`` title in the preface is supplied by the surrounding
    layout and omitted here. ``include_title`` retains that authored heading for
    layouts without an automatic title. Preface material remains an untitled
    section. Analysis appendix markers and prose-token filters do not apply.
    """
    protected, sentinel, _literal_lines = _protected_source(text)
    headings = chapter_heading_spans(protected, config)
    first_end = headings[0][0] if headings else len(text)
    prefix = _blocks(text[:first_end], start_line=1, front_matter=True)
    if not include_title:
        for index, block in enumerate(prefix):
            if block.kind == "heading" and block.level == 1:
                prefix.pop(index)
                break
    sections: ManuscriptSections = [("", prefix)] if prefix else []
    for index, (_start, end, line, raw_title) in enumerate(headings):
        title = raw_title.replace(sentinel, "<")
        _inline_runs(title, start_line=line)
        next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        sections.append((title, _blocks(text[end:next_start], start_line=line + 1, front_matter=False)))
    return sections
