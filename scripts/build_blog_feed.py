#!/usr/bin/env python3
"""Build ``docs/blog/feed.xml`` (Atom 1.0) from the published blog HTML pages.

The feed lists every published blog article except ``index.html`` itself, which
acts as the human-readable index linked from the feed's alternate link. Each
entry's ``id`` is the article's existing canonical URL, so the identifiers stay
stable across regenerations. ``published`` is the earliest ``<time datetime>``
on the page; ``updated`` is the latest one when at least two distinct dates
appear, otherwise equal to ``published``. Articles are sorted reverse
chronologically by ``updated`` and secondarily by their source filename, so the
output is deterministic.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

SELF_URL = "https://lixity.de/"
INDEX_URL = SELF_URL + "blog/index.html"
FEED_URL = SELF_URL + "blog/feed.xml"
ICON_URL = SELF_URL + "favicon.ico"
ATOM_NS = "http://www.w3.org/2005/Atom"
AUTHOR_NAME = "Matthias Fahsold"
AUTHOR_URI = "https://github.com/mfahsold"
DEFAULT_LANG = "en"
FEED_PATH = Path("docs/blog/feed.xml")
INDEX_FILENAME = "index.html"
TIME_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Entry:
    canonical: str
    title: str
    lang: str
    summary: str
    published: str
    updated: str
    source: Path

    @property
    def sort_key(self) -> tuple[str, str]:
        # Stable reverse-chronological order: latest updated first; within a
        # bucket, fall back to filename so two reruns produce identical bytes.
        return (self.updated, _natural_key(self.source.name))


def _natural_key(name: str) -> tuple[str, ...]:
    # Zero-padded numeric segments keep the order intuitive when readers add
    # articles later and keep every tuple element a string, so entries with the
    # same <updated> value compare without a type error.
    return tuple(
        f"{int(part):06d}" if part.isdigit() else part
        for part in re.split(r"(\d+)", name)
    )


class _EntryParser(HTMLParser):
    """Capture the fields the Atom feed needs from one blog HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.lang = DEFAULT_LANG
        self.description = ""
        self.canonical = ""
        self.times: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = {k: v for k, v in attrs if v is not None}
        if tag == "title":
            self._in_title = True
        elif tag == "html":
            self.lang = mapping.get("lang", DEFAULT_LANG) or DEFAULT_LANG
        elif tag == "meta" and mapping.get("name") == "description":
            self.description = (mapping.get("content") or "").strip()
        elif tag == "link" and mapping.get("rel") == "canonical":
            self.canonical = mapping.get("href", "")
        elif tag == "time" and mapping.get("datetime"):
            value = mapping["datetime"]
            if TIME_VALUE.match(value):
                self.times.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def _atom_datetime(date_only: str) -> str:
    """Normalise ``YYYY-MM-DD`` to a UTC full datetime with ``Z`` suffix."""
    return f"{date_only}T00:00:00Z"


def _parse_entries(blog_dir: Path) -> list[Entry]:
    entries: list[Entry] = []
    for page in sorted(blog_dir.glob("*.html")):
        if page.name == INDEX_FILENAME:
            continue
        parser = _EntryParser()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError) as exc:
            raise SystemExit(f"build_blog_feed: cannot parse {page}: {exc}") from exc
        if not parser.canonical or not parser.title.strip() or not parser.times:
            raise SystemExit(
                f"build_blog_feed: {page} is missing canonical, title or a "
                f"<time datetime> value; cannot include it in the Atom feed."
            )
        published = min(parser.times)
        updated = max(parser.times)
        entries.append(
            Entry(
                canonical=parser.canonical,
                title=parser.title.strip(),
                lang=parser.lang,
                summary=parser.description,
                published=published,
                updated=updated,
                source=page,
            )
        )
    entries.sort(key=lambda entry: entry.sort_key, reverse=True)
    return entries


def _render_feed(entries: list[Entry]) -> str:
    feed_updated = max(entry.updated for entry in entries) if entries else _atom_datetime("1970-01-01")
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<feed xmlns="{ATOM_NS}" xml:lang="{DEFAULT_LANG}">',
        f"  <id>{xml_escape(FEED_URL)}</id>",
        f"  <title>{xml_escape('Lixity blog: reading, research and revision')}</title>",
        f'  <subtitle>{xml_escape("Articles on revision, measurement, research workflow and the example project.")}</subtitle>',
        f'  <link rel="alternate" type="text/html" href="{xml_escape(INDEX_URL)}"/>',
        f'  <link rel="self" type="application/atom+xml" href="{xml_escape(FEED_URL)}"/>',
        f"  <updated>{xml_escape(_atom_datetime(feed_updated[:10]))}</updated>",
        f"  <icon>{xml_escape(ICON_URL)}</icon>",
        f"  <author><name>{xml_escape(AUTHOR_NAME)}</name><uri>{xml_escape(AUTHOR_URI)}</uri></author>",
    ]
    for entry in entries:
        lines.append("  <entry>")
        lines.append(f"    <id>{xml_escape(entry.canonical)}</id>")
        lines.append(
            f'    <title xml:lang="{xml_escape(entry.lang)}">{xml_escape(entry.title)}</title>'
        )
        lines.append(
            f'    <link rel="alternate" type="text/html" href="{xml_escape(entry.canonical)}"/>'
        )
        lines.append(f"    <published>{xml_escape(_atom_datetime(entry.published[:10]))}</published>")
        lines.append(f"    <updated>{xml_escape(_atom_datetime(entry.updated[:10]))}</updated>")
        lines.append(f"    <author><name>{xml_escape(AUTHOR_NAME)}</name></author>")
        if entry.summary:
            lines.append(
                f'    <summary xml:lang="{xml_escape(entry.lang)}" '
                f'type="text">{xml_escape(entry.summary)}</summary>'
            )
        lines.append("  </entry>")
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def build(*, check_only: bool = False, root: Path | None = None) -> list[str]:
    """Write ``docs/blog/feed.xml`` when changed; return the drift list."""
    base = root if root is not None else Path(__file__).resolve().parents[1]
    target = base / FEED_PATH
    rendered = _render_feed(_parse_entries(target.parent))
    current = target.read_text(encoding="utf-8") if target.exists() else None
    if current == rendered:
        return []
    if not check_only:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    return [str(FEED_PATH)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report drift without writing")
    args = parser.parse_args()
    drift = build(check_only=args.check)
    if args.check:
        if drift:
            for path in drift:
                print(f"  - needs sync: {path}", file=sys.stderr)
            return 1
        print("docs/blog/feed.xml is synchronized.", file=sys.stderr)
        return 0
    if drift:
        for path in drift:
            print(f"  - regenerated: {path}")
    else:
        print("docs/blog/feed.xml already current.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
