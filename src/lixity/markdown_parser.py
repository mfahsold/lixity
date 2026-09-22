"""
scripts/engine/markdown_parser.py
=================================
Generic, project-neutral Markdown parser and inline converter.

This engine layer is deliberately free of PyCairo/Pango and project
dependencies so that it can be shared deterministically by all publication
adapters (export_pdf.py, export_epub.py, create_excerpt.py).

Provides:
- ``parse_markdown_blocks``: converts Markdown text into semantic blocks
  (h1/h2/h3, paragraphs, quote blocks, list items, dividers, footnotes).
  Each block carries line anchors (``start_line``/``end_line``, 1-based) for
  precise tracing in the manuscript (lectorate and analysis UI).
- ``parse_markdown_file``: file variant with UTF-8 read handling.
- ``inline_markdown_to_html``: converts inline markup into safe XHTML5
  (for EPUB 3.3); including EPUB footnote reference generation.

Editorial HTML comments (``<!-- PRÜFEN ... -->``) are always
and completely filtered out so that they never appear in publication outputs.
"""

import html as html_mod
import re
from typing import Any

_FN_REF_PATTERN = re.compile(r"\[\^([^\]]+)\]")
_FN_REF_STRIP_PATTERN = re.compile(r"\[\^([^\]]+)\]")


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


def parse_markdown_blocks(content: str) -> list[dict[str, Any]]:
    """Parses Markdown content into semantic blocks and filters editorial HTML comments."""
    # Remove editorial comments (<!-- ... -->) completely
    clean_content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    lines = clean_content.splitlines()

    blocks: list[dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
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
                {"type": "h2", "text": stripped[3:].strip(), "start_line": i + 1, "end_line": i + 1}
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
            cur_p = []
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
                if n_line.strip() and not (n_line.strip().startswith(("- ", "* ", "#"))):
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
            if not raw_l.strip() or raw_l.strip().startswith(("#", ">", "---", "- ", "* ", "[^")):
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

    return blocks


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

    # 3. Footnote references [^id] with unique anchor ID
    def fn_ref(m: re.Match) -> str:
        fn_id = m.group(1)
        n = fn_counter.get(fn_id, 0) + 1
        fn_counter[fn_id] = n
        return (
            f'<a epub:type="noteref" id="fnref{fn_id}-{document_id}-{n}" '
            f'href="#fn{fn_id}" role="doc-noteref" class="fnref">{fn_id}</a>'
        )

    text = _FN_REF_PATTERN.sub(fn_ref, text)

    # 4. Bold-italic, bold, italic
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)

    # 5. Links [text](url)
    text = _LINK_PATTERN.sub(r'<a href="\2">\1</a>', text)

    # 6. Hard line breaks
    text = text.replace("\n", "<br/>\n")

    # 7. Restore literal asterisks
    text = text.replace("\x01ASTERISK\x02", "*")

    return text
