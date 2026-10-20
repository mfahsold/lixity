"""Generate Markdown alternates for HTML guides and blog pages.

The linked ``<page>.html.md`` alternates provide the same maintained content
for readers and tools that consume Markdown. Convert the main content of each
guide or blog page deterministically and without new dependencies.

Run it after changing a page; ``tests/test_guide_markdown.py`` fails while the
committed files are outdated.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "docs" / "guides"
BLOG = ROOT / "docs" / "blog"

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
SKIP_TAGS = {"script", "style", "nav", "svg"}
BLOCK_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "p",
    "ul",
    "ol",
    "pre",
    "table",
    "details",
    "figure",
    "footer",
    "a",
}


class Node:
    def __init__(self, tag: str, attrs: dict[str, str] | None = None) -> None:
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node | str] = []


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {name: value or "" for name, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def _inline(node: Node | str) -> str:
    if isinstance(node, str):
        return re.sub(r"\s+", " ", node)
    tag = node.tag
    inner = "".join(_inline(child) for child in node.children)
    if tag in {"strong", "b"}:
        return f"**{inner.strip()}**" if inner.strip() else ""
    if tag in {"em", "i"}:
        return f"*{inner.strip()}*" if inner.strip() else ""
    if tag == "code":
        text = inner.strip()
        return f"`{text}`" if text else ""
    if tag == "a":
        href = node.attrs.get("href", "")
        text = inner.strip() or href
        return f"[{text}]({href})" if href else text
    if tag == "img":
        return f"![{node.attrs.get('alt', '')}]({node.attrs.get('src', '')})"
    if tag == "br":
        return "  \n"
    if tag == "time":
        return inner.strip()
    return inner


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("\u00a0", " ")).strip()


def _render_blocks(node: Node, out: list[str]) -> None:
    for child in node.children:
        if isinstance(child, str):
            text = _clean(child)
            if text:
                out.append(text)
            continue
        if child.tag in SKIP_TAGS:
            continue
        if child.tag in {"h1", "h2", "h3", "h4"}:
            level = int(child.tag[1])
            out.append("#" * level + " " + _clean(_inline(child)))
        elif child.tag == "p":
            text = _clean(_inline(child))
            if text:
                out.append(text)
        elif child.tag in {"ul", "ol"}:
            # Whitespace text nodes sit between the <li> elements; counting the
            # item positions alone keeps ordered lists at 1., 2., 3., ...
            entries = [item for item in child.children
                       if isinstance(item, Node) and item.tag == "li"]
            lines = []
            for index, item in enumerate(entries, start=1):
                marker = f"{index}." if child.tag == "ol" else "-"
                lines.append(f"{marker} {_clean(_inline(item))}")
            if lines:
                out.extend(lines)
        elif child.tag == "pre":
            code = "".join(
                grand
                for part in child.children
                if isinstance(part, Node)
                for grand in part.children
                if isinstance(grand, str)
            )
            out.append("```\n" + code.strip("\n") + "\n```")
        elif child.tag == "table":
            rows: list[list[str]] = []
            for row in _walk(child):
                if row.tag != "tr":
                    continue
                cells = [
                    _clean(_inline(cell)).replace("|", r"\|")
                    for cell in row.children
                    if isinstance(cell, Node) and cell.tag in {"th", "td"}
                ]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(len(row) for row in rows)
                lines = ["| " + " | ".join(rows[0] + [""] * (width - len(rows[0]))) + " |",
                         "| " + " | ".join(["---"] * width) + " |"]
                lines.extend("| " + " | ".join(row + [""] * (width - len(row))) + " |" for row in rows[1:])
                out.append("\n".join(lines))
        elif child.tag == "summary":
            out.append("**" + _clean(_inline(child)) + "**")
        elif child.tag == "figure":
            out.extend(_inline(part) for part in _walk(child) if part.tag == "img")
            sources = [
                grand.attrs.get("src", "")
                for part in child.children
                if isinstance(part, Node)
                for grand in part.children
                if isinstance(grand, Node) and grand.tag == "source"
            ]
            out.extend(f"[Video walkthrough]({source})" for source in sources if source)
            out.extend("*" + _clean(_inline(part)) + "*" for part in child.children
                       if isinstance(part, Node) and part.tag == "figcaption")
        elif child.tag == "footer":
            out.append(_clean(_inline(child)))
        elif child.tag in {"div", "section", "article", "main", "body", "root", "details"}:
            _render_blocks(child, out)
        else:
            text = _clean(_inline(child))
            if text:
                out.append(text)


def guide_markdown(path: Path) -> str:
    """Return the main content of one guide or blog page as Markdown."""
    builder = _Builder()
    builder.feed(path.read_text(encoding="utf-8"))
    main = next((node for node in _walk(builder.root) if node.tag == "main"), None)
    if main is None:
        raise ValueError(f"No <main> element in {path.name}")
    blocks: list[str] = []
    _render_blocks(main, blocks)
    # Drop the leading documentation link and the guide navigation line.
    blocks = [block for block in blocks
              if block and not block.lstrip("[").startswith("Lixity · Documentation")]
    text = "\n\n".join(blocks).strip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


def _walk(node: Node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from _walk(child)


def build(check_only: bool = False) -> list[str]:
    """Generate all alternates; return outdated file names in check mode."""
    outdated: list[str] = []
    for path in sorted([*GUIDES.glob("*.html"), *BLOG.glob("*.html")]):
        target = path.with_suffix(path.suffix + ".md")
        content = guide_markdown(path)
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current != content:
            outdated.append(str(target.relative_to(ROOT / "docs")))
            if not check_only:
                target.write_text(content, encoding="utf-8")
    return outdated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Report outdated alternates without writing"
    )
    args = parser.parse_args()
    outdated = build(check_only=args.check)
    if args.check:
        if outdated:
            print("Outdated Markdown alternates: " + ", ".join(outdated), file=sys.stderr)
            return 1
        print("Markdown alternates are up to date.")
        return 0
    print(f"Updated {len(outdated)} Markdown alternate(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
