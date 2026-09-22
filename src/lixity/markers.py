"""
scripts/engine/markers.py
=========================
Editor-visible work markers for manuscripts – set from the dashboard,
consumed in the text editor.

Design (SOTA best practices for plain-text files, cf. Marginalia/RFM):
- Markers are **inline HTML comments** with a stable ID and structured,
  machine-readable attributes: ``<!-- LIXITY-MARKER id="…" kind="…" note="…" -->``.
  They are invisible in every renderer, survive all pipeline stages (the
  analysis strips HTML comments) and travel with the text in Git.
- **Standalone marker lines** (placed directly above the target paragraph):
  robust against edits inside the paragraph – the marker moves with the
  paragraph, and the line number is re-derived on every parse (no stale
  offsets, no re-anchoring machinery).
- **Deterministic IDs** (short content hash): idempotent add operations –
  setting the same marker twice changes nothing.
- Notes are sanitised (``-->`` cannot break the comment); the paragraph
  anchor is expressed as a 1-based line number.
"""

import hashlib
import re
from dataclasses import dataclass

MARKER_PREFIX = "LIXITY-MARKER"
MARKER_KINDS = ("pruefen", "sachcheck", "todo", "achtung")

_MARKER_RE = re.compile(r"<!--\s*LIXITY-MARKER\s+(.*?)\s*-->")
_ATTR_RE = re.compile(r'([a-zA-Z_][\w-]*)="([^"]*)"')


@dataclass(frozen=True)
class Marker:
    """A single work marker anchored to a manuscript line (1-based)."""

    id: str
    kind: str
    note: str
    line: int

    def render(self) -> str:
        return f"<!-- {MARKER_PREFIX} {self.render_attrs()} -->"

    def render_attrs(self) -> str:
        return f'id="{self.id}" kind="{self.kind}" note="{_sanitize(self.note)}"'


def _sanitize(note: str) -> str:
    """Keeps the note inside the comment boundary (never contains ``-->``)."""
    return str(note or "").replace("-->", "->").replace("\r", " ").replace("\n", " ").strip()


def marker_id(kind: str, note: str, line: int) -> str:
    """Deterministic 8-hex id from kind, note and anchor line (no randomness)."""
    digest = hashlib.sha1(  # noqa: S324 – non-cryptographic content hash for stable ids
        f"{kind}\u0000{note}\u0000{line}".encode()
    ).hexdigest()
    return digest[:8]


def _parse_attrs(raw: str) -> dict[str, str]:
    return dict(_ATTR_RE.findall(raw))


def list_markers(text: str) -> list[Marker]:
    """Finds all LIXITY-MARKER comments and derives their line anchors."""
    markers = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = _MARKER_RE.search(line)
        if not match:
            continue
        attrs = _parse_attrs(match.group(1))
        marker_id_value = attrs.get("id", "")
        if not marker_id_value:
            continue
        markers.append(
            Marker(
                id=marker_id_value,
                kind=attrs.get("kind", "pruefen"),
                note=attrs.get("note", ""),
                line=line_no,
            )
        )
    return markers


def add_marker(
    text: str, kind: str, note: str, target_line: int, marker_id_value: str | None = None
) -> tuple[str, Marker]:
    """
    Inserts a standalone marker line directly above ``target_line`` (1-based).

    Idempotent: an identical marker at the same position is not duplicated.
    Returns (updated text, marker). The paragraph anchor of the marker is the
    line of the paragraph it precedes – it moves with the paragraph on edits.
    """
    if kind not in MARKER_KINDS:
        raise ValueError(f"Unbekannte Marker-Art: {kind} (erlaubt: {', '.join(MARKER_KINDS)})")
    lines = text.splitlines()
    anchor = max(1, min(int(target_line), len(lines) + 1))
    marker_id_value = marker_id_value or marker_id(kind, note, anchor)
    marker = Marker(id=marker_id_value, kind=kind, note=_sanitize(note), line=anchor)
    rendered = marker.render()
    # Idempotency: identical marker line directly above the anchor already?
    if anchor <= len(lines) and lines[anchor - 1].strip() == rendered:
        return text, marker
    if anchor - 2 >= 0 and anchor - 2 < len(lines) and lines[anchor - 2].strip() == rendered:
        return text, marker
    insert_at = anchor - 1 if anchor <= len(lines) else len(lines)
    lines.insert(insert_at, rendered)
    new_text = "\n".join(lines)
    if text.endswith(("\n",)) and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, marker


def resolve_marker(text: str, marker_id_value: str) -> str:
    """Removes every marker line with the given id (accept-all semantics)."""
    lines = text.splitlines()
    kept = [
        line
        for line in lines
        if not (
            (match := _MARKER_RE.search(line))
            and _parse_attrs(match.group(1)).get("id") == marker_id_value
        )
    ]
    return "\n".join(kept) + ("\n" if text.endswith("\n") else "")


def update_marker(
    text: str, marker_id_value: str, kind: str | None = None, note: str | None = None
) -> tuple[str, Marker | None]:
    """Updates kind/note of the first marker with the given id (id stays stable)."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        match = _MARKER_RE.search(line)
        if not match or _parse_attrs(match.group(1)).get("id") != marker_id_value:
            continue
        attrs = _parse_attrs(match.group(1))
        new_kind = kind if kind is not None else attrs.get("kind", "pruefen")
        new_note = note if note is not None else attrs.get("note", "")
        if new_kind not in MARKER_KINDS:
            raise ValueError(f"Unbekannte Marker-Art: {new_kind}")
        marker = Marker(id=marker_id_value, kind=new_kind, note=_sanitize(new_note), line=idx + 1)
        lines[idx] = marker.render()
        return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), marker
    return text, None


def count_markers(text: str) -> int:
    return len(list_markers(text))
