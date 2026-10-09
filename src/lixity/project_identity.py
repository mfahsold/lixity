"""Read explicit manuscript identity metadata; never infer or edit authorship."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from .config import validate_author_name
from .markdown_parser import _fence_closer, _front_matter_end, _is_indented_code, _without_comments


def _scalar(raw: str) -> str | None:
    """Recognize a bounded string subset, without evaluating arbitrary YAML."""
    raw = raw.strip()
    if raw.startswith('"'):
        match = re.fullmatch(r'("(?:[^"\\]|\\.)*")[ \t]*(?:#.*)?', raw)
        if not match:
            return None
        try:
            value = json.loads(match[1])
        except ValueError:
            return None
    elif raw.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'[ \t]*(?:#.*)?", raw)
        if not match:
            return None
        value = match[1].replace("''", "'")
    else:
        value = re.split(r"[ \t]+#", raw, maxsplit=1)[0].strip()
        if (not value or value[0] in "[{|>&*!#@`%" or value.startswith("- ") or ": " in value
                or value.casefold() in {"null", "~", "true", "false", "yes", "no", "on", "off"}
                or re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value)):
            return None
    try:
        return validate_author_name(value) or None
    except ValueError:
        return None


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def manuscript_identity_check(text: str | None, title: str | None, author_name: str | None) -> dict[str, Any]:
    """Compare explicit strings using NFC/whitespace formatting normalization.

    Supports flat leading YAML title/author strings and the leading H1 title-page
    block with by/von/Author/Autor lines. Unsupported/ambiguous metadata is never
    replaced by prose inference. This checks metadata agreement, not authorship.
    """
    found: dict[str, tuple[str | None, str | None, bool]] = {
        "title": (None, None, False), "author_name": (None, None, False)}
    if text is not None:
        lines = text.splitlines()
        end = _front_matter_end(lines)
        first = lines[0].lstrip("\ufeff").strip() if lines else ""
        first_metadata = next((line.strip() for line in lines[1:] if line.strip()), "")
        unclosed = first == "---" and not end and bool(re.match(r"[\w-]+\s*:", first_metadata))
        if end or unclosed:
            seen = set()
            if unclosed:
                found = dict.fromkeys(found, (None, "front_matter", True))
            previous_field = None
            for line in lines[1:end - 1] if end else lines[1:]:
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                if line.startswith((" ", "\t")):
                    if previous_field is not None:
                        found[previous_field] = (None, "front_matter", True)
                    continue
                match = re.match(r"^(title|author)[ \t]*:[ \t]*(.*)$", line)
                previous_field = None
                if not match:
                    continue
                key = "author_name" if match[1] == "author" else "title"
                previous_field = key
                value = _scalar(match[2])
                unsupported = key in seen or value is None or unclosed
                found[key] = (None if unsupported else value, "front_matter", unsupported)
                seen.add(key)
        else:
            # Prose comments are masked only outside front matter; quoted
            # metadata punctuation and HTML-like text remain literal data.
            for line in _without_comments(text).splitlines():
                if not line.strip():
                    continue
                if _is_indented_code(line) or _fence_closer(line):
                    break
                heading = re.fullmatch(r" {0,3}#[ \t]+(.+)", line)
                byline = re.fullmatch(r" {0,3}(?:(?:by|von)[ \t]+|(?:Author|Autor)[ \t]*:[ \t]*)(.+)", line, re.IGNORECASE)
                if heading and found["title"][1] is None:
                    value = re.sub(r"[ \t]+#+[ \t]*$", "", heading[1]).strip()
                    found["title"] = (value, "title_page", False)
                elif byline and found["title"][1] == "title_page":
                    if found["author_name"][1] is not None:
                        found["author_name"] = (None, "title_page", True)
                        continue
                    try:
                        value = validate_author_name(byline[1])
                        found["author_name"] = (value, "title_page", False)
                    except ValueError:
                        found["author_name"] = (None, "title_page", True)
                else:
                    break
    result = {}
    for key, expected in (("title", title), ("author_name", author_name)):
        value, source, unsupported = found[key]
        invalid_expected = False
        if expected is not None:
            try:
                validate_author_name(expected)
            except ValueError:
                invalid_expected = True
        if text is None or expected is None or (isinstance(expected, str) and not expected.strip()):
            status = "unavailable"
        elif invalid_expected or unsupported:
            status = "unsupported"
        elif value is None:
            status = "missing"
        else:
            status = "matched" if _normalized(value) == _normalized(expected) else "mismatch"
        result[key] = {"status": status, "value": value, "source": source}
    return result
