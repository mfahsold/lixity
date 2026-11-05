"""Offline HTML article extraction and clean Markdown conversion (Defuddle style).

Extracts article metadata and converts DOM article contents into structured Markdown
using only Python standard library html.parser, with no network access or external deps.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

from pydantic import BaseModel, Field


class ArticleDocument(BaseModel):
    title: str = ""
    byline: str | None = None
    published_time: str | None = None
    site_name: str | None = None
    description: str | None = None
    canonical_url: str | None = None
    markdown: str = ""
    word_count: int = 0
    excerpt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_research_markdown(self, origin_url: str | None = None) -> str:
        """Format as a research source draft with provenance header."""
        meta_lines = [
            "<!-- lixity-research-article/1",
            f"title: {self.title}",
        ]
        if self.byline:
            meta_lines.append(f"author: {self.byline}")
        if self.published_time:
            meta_lines.append(f"date: {self.published_time}")
        if self.site_name:
            meta_lines.append(f"site: {self.site_name}")
        url = origin_url or self.canonical_url
        if url:
            meta_lines.append(f"origin_url: {url}")
        meta_lines.append("extractor: lixity-defuddle/1")
        meta_lines.append("-->\n")

        header = f"# {self.title}\n\n" if self.title else ""
        byline_str = f"*{self.byline}*\n\n" if self.byline else ""
        return "\n".join(meta_lines) + "\n" + header + byline_str + self.markdown.strip() + "\n"


class _ArticleHtmlParser(HTMLParser):
    def __init__(self, base_url: str | None = None) -> None:
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.byline: str | None = None
        self.published_time: str | None = None
        self.site_name: str | None = None
        self.description: str | None = None
        self.canonical_url: str | None = None

        self._in_title = False
        self._title_buffer: list[str] = []

        self._ignore_tags = {
            "script", "style", "noscript", "svg", "nav", "footer", "form",
            "header", "aside", "dialog", "iframe", "button"
        }
        self._ignore_depth = 0

        self._lines: list[str] = []
        self._current_line: list[str] = []
        self._tag_stack: list[str] = []

        # List tracking
        self._list_stack: list[tuple[str, int]] = []  # ('ul'|'ol', index)
        # Blockquote tracking
        self._blockquote_depth = 0
        # Table tracking
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._table_current_row: list[str] = []
        self._table_cell_buffer: list[str] = []
        # Code block tracking
        self._in_pre = False
        self._pre_buffer: list[str] = []
        self._current_line_link_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        tag_lower = tag.lower()

        # Extract metadata
        if tag_lower == "meta":
            prop = attr_dict.get("property", "").lower()
            name = attr_dict.get("name", "").lower()
            content = attr_dict.get("content", "").strip()
            if content:
                if prop in ("og:title", "twitter:title") or name in ("title", "twitter:title"):
                    if not self.title:
                        self.title = content
                elif prop in ("og:description", "description") or name == "description":
                    if not self.description:
                        self.description = content
                elif prop in ("og:site_name", "site_name"):
                    if not self.site_name:
                        self.site_name = content
                elif (name in ("author", "article:author") or prop == "article:author") and not self.byline:
                    self.byline = content
                elif (prop == "article:published_time" or name in ("date", "pubdate")) and not self.published_time:
                    self.published_time = content
            return

        if tag_lower == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href", "").strip()
            if rel == "canonical" and href:
                self.canonical_url = urljoin(self.base_url, href) if self.base_url else href
            return

        if tag_lower == "title":
            self._in_title = True
            return

        # Check ignore tags or ignore classes (ads, widgets, sidebars)
        cls_id = (attr_dict.get("class", "") + " " + attr_dict.get("id", "")).lower()
        if tag_lower in self._ignore_tags or any(noise in cls_id for noise in ("comment", "sidebar", "ad-", "social", "share", "cookie")):
            self._ignore_depth += 1
            return
        if self._ignore_depth > 0:
            self._ignore_depth += 1
            return

        self._tag_stack.append(tag_lower)

        if tag_lower == "pre":
            self._in_pre = True
            self._pre_buffer = []
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._flush_line()
            level = int(tag_lower[1])
            self._current_line.append("#" * level + " ")
        elif tag_lower == "p":
            self._flush_line()
        elif tag_lower == "br":
            self._current_line.append("\n")
        elif tag_lower == "hr":
            self._flush_line()
            self._lines.append("---")
        elif tag_lower in ("strong", "b"):
            self._current_line.append("**")
        elif tag_lower in ("em", "i"):
            self._current_line.append("*")
        elif tag_lower == "code" and not self._in_pre:
            self._current_line.append("`")
        elif tag_lower == "blockquote":
            self._flush_line()
            self._blockquote_depth += 1
        elif tag_lower == "ul":
            self._flush_line()
            self._list_stack.append(("ul", 0))
        elif tag_lower == "ol":
            self._flush_line()
            self._list_stack.append(("ol", 1))
        elif tag_lower == "li":
            self._flush_line()
            indent = "  " * (len(self._list_stack) - 1) if len(self._list_stack) > 1 else ""
            if self._list_stack:
                kind, idx = self._list_stack[-1]
                if kind == "ol":
                    self._current_line.append(f"{indent}{idx}. ")
                    self._list_stack[-1] = (kind, idx + 1)
                else:
                    self._current_line.append(f"{indent}- ")
            else:
                self._current_line.append("- ")
        elif tag_lower == "a":
            href = attr_dict.get("href", "").strip()
            if href and not href.startswith(("javascript:", "data:")):
                if self.base_url:
                    href = urljoin(self.base_url, href)
                self._current_line.append("[")
                self._current_line_link_href = href
            else:
                self._current_line_link_href = None
        elif tag_lower == "img":
            src = attr_dict.get("src", "").strip()
            alt = attr_dict.get("alt", "").strip()
            if src:
                if self.base_url:
                    src = urljoin(self.base_url, src)
                self._current_line.append(f"![{alt}]({src})")
        elif tag_lower == "table":
            self._in_table = True
            self._table_rows = []
        elif tag_lower == "tr":
            self._table_current_row = []
        elif tag_lower in ("td", "th"):
            self._table_cell_buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = False
            if not self.title and self._title_buffer:
                self.title = "".join(self._title_buffer).strip()
            return

        if self._ignore_depth > 0:
            self._ignore_depth -= 1
            return

        if self._tag_stack and self._tag_stack[-1] == tag_lower:
            self._tag_stack.pop()

        if tag_lower == "pre":
            self._in_pre = False
            self._flush_line()
            code_text = "".join(self._pre_buffer).rstrip()
            self._lines.append(f"```\n{code_text}\n```")
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self._flush_line()
        elif tag_lower in ("strong", "b"):
            self._current_line.append("**")
        elif tag_lower in ("em", "i"):
            self._current_line.append("*")
        elif tag_lower == "code" and not self._in_pre:
            self._current_line.append("`")
        elif tag_lower == "blockquote":
            self._flush_line()
            self._blockquote_depth = max(0, self._blockquote_depth - 1)
        elif tag_lower in ("ul", "ol"):
            self._flush_line()
            if self._list_stack:
                self._list_stack.pop()
        elif tag_lower == "li":
            self._flush_line()
        elif tag_lower == "a":
            href = getattr(self, "_current_line_link_href", None)
            if href:
                self._current_line.append(f"]({href})")
                self._current_line_link_href = None
        elif tag_lower in ("td", "th"):
            cell_text = "".join(self._table_cell_buffer).strip().replace("|", "\\|")
            self._table_current_row.append(cell_text)
        elif tag_lower == "tr":
            if self._table_current_row:
                self._table_rows.append(self._table_current_row)
        elif tag_lower == "table":
            self._in_table = False
            self._render_table()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buffer.append(data)
            return

        if self._ignore_depth > 0:
            return

        if self._in_table:
            self._table_cell_buffer.append(data)
            return

        if self._in_pre:
            self._pre_buffer.append(data)
            return

        # Normalize whitespace in normal prose
        cleaned = re.sub(r"[ \t]+", " ", data)
        if cleaned:
            self._current_line.append(cleaned)

    def _flush_line(self) -> None:
        if self._current_line:
            text = "".join(self._current_line).strip()
            if text:
                if self._blockquote_depth > 0:
                    prefix = "> " * self._blockquote_depth
                    text = prefix + text
                self._lines.append(text)
            self._current_line = []

    def _render_table(self) -> None:
        if not self._table_rows:
            return
        num_cols = max(len(row) for row in self._table_rows)
        if num_cols == 0:
            return
        # Pad cells
        formatted_rows = [row + [""] * (num_cols - len(row)) for row in self._table_rows]

        table_md_lines = []
        header = formatted_rows[0]
        table_md_lines.append("| " + " | ".join(header) + " |")
        table_md_lines.append("| " + " | ".join("---" for _ in range(num_cols)) + " |")
        table_md_lines.extend("| " + " | ".join(row) + " |" for row in formatted_rows[1:])
        self._lines.append("\n".join(table_md_lines))


def extract_article(html_content: str | bytes, origin_url: str | None = None) -> ArticleDocument:
    """Extract clean title, metadata and structured Markdown from raw HTML."""
    if isinstance(html_content, bytes):
        text = html_content.decode("utf-8", errors="replace")
    else:
        text = html_content

    parser = _ArticleHtmlParser(base_url=origin_url)
    parser.feed(text)
    parser._flush_line()

    # Reconstruct paragraphs separated by double newlines
    blocks = []
    for line in parser._lines:
        line_clean = line.strip()
        if line_clean:
            blocks.append(line_clean)
    markdown = "\n\n".join(blocks)

    words = len(re.findall(r"\w+", markdown))
    excerpt = markdown[:200] + "…" if len(markdown) > 200 else markdown

    return ArticleDocument(
        title=parser.title or "Untitled article",
        byline=parser.byline,
        published_time=parser.published_time,
        site_name=parser.site_name,
        description=parser.description,
        canonical_url=parser.canonical_url or origin_url,
        markdown=markdown,
        word_count=words,
        excerpt=excerpt,
    )
