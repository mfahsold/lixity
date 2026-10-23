"""Bounded retained document/video containers, not codec or content verification."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any, NoReturn

from .limits import MAX_PDF_BYTES

VIDEO_TYPES = {"video/mp4", "video/webm"}
MEDIA_TYPES = {"application/pdf", *VIDEO_TYPES}
MEDIA_SUFFIXES = {".pdf": "application/pdf", ".mp4": "video/mp4", ".webm": "video/webm"}


def _error(message: str) -> NoReturn:
    from .repository import ResearchError
    raise ResearchError(message)


def validate_media(content: bytes, *, filename: str | None = None) -> dict[str, Any]:
    """Check bounded container structure without executing or decoding content."""
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_PDF_BYTES:
        _error("Document/video must be nonempty and at most 50 MiB")
    if re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]", content):
        if not content.rstrip().endswith(b"%%EOF"):
            _error("PDF is missing its final end marker")
        media_type = "application/pdf"
    elif content[:4] == b"\x1a\x45\xdf\xa3":
        _validate_webm(content)
        media_type = "video/webm"
    elif content[4:8] == b"ftyp":
        _validate_mp4(content)
        media_type = "video/mp4"
    else:
        _error("Only local PDF, MP4 and WebM containers are supported")
    if filename is not None and MEDIA_SUFFIXES.get(Path(filename).suffix.lower()) != media_type:
        _error("Media filename extension must match its PDF, MP4 or WebM container")
    return {"media_type": media_type}


def _validate_mp4(content: bytes) -> None:
    offset, kinds = 0, set()
    while offset + 8 <= len(content):
        size, kind = struct.unpack_from(">I4s", content, offset)
        header = 8
        if size == 1:
            if offset + 16 > len(content):
                _error("Truncated MP4 box")
            size = struct.unpack_from(">Q", content, offset + 8)[0]
            header = 16
        elif size == 0:
            size = len(content) - offset
        if size < header or offset + size > len(content):
            _error("Invalid MP4 box length")
        if offset == 0:
            if kind != b"ftyp" or size < header + 8 or (size - header) % 4:
                _error("MP4 requires a valid initial file-type box")
            brands = {b"isom", b"iso2", b"iso4", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash"}
            if (content[offset + header:offset + header + 4] not in brands
                    and not any(content[n:n + 4] in brands for n in range(offset + header + 8, offset + size, 4))):
                _error("Unsupported MP4 file type")
        if kind in {b"moov", b"mdat"} and size == header:
            _error("MP4 metadata and media boxes must not be empty")
        kinds.add(kind)
        offset += size
    if offset != len(content) or not {b"ftyp", b"moov", b"mdat"} <= kinds:
        _error("MP4 requires complete file-type, metadata and media boxes")


def _vint(content: bytes, offset: int, *, identifier: bool = False) -> tuple[int, int]:
    if offset >= len(content) or not content[offset]:
        _error("Invalid WebM element header")
    first = content[offset]
    width = 9 - first.bit_length()
    if width > (4 if identifier else 8) or offset + width > len(content):
        _error("Truncated WebM element header")
    value = int.from_bytes(content[offset:offset + width], "big")
    if not identifier:
        value &= (1 << (7 * width)) - 1
        if value == (1 << (7 * width)) - 1:
            value = -1
    return value, offset + width


def _elements(content: bytes, start: int, end: int) -> list[tuple[int, int, int]]:
    elements: list[tuple[int, int, int]] = []
    while start < end:
        if len(elements) >= 10000:
            _error("WebM container exceeds the bounded element count")
        identifier, offset = _vint(content, start, identifier=True)
        size, offset = _vint(content, offset)
        stop = end if size == -1 else offset + size
        if stop > end or stop < offset:
            _error("Invalid WebM element length")
        elements.append((identifier, offset, stop))
        start = stop
    return elements


def _validate_webm(content: bytes) -> None:
    roots = _elements(content, 0, len(content))
    if not roots or roots[0][0] != 0x1A45DFA3:
        _error("WebM requires an EBML header")
    header = _elements(content, roots[0][1], roots[0][2])
    if not any(kind == 0x4282 and content[start:end] == b"webm" for kind, start, end in header):
        _error("Only WebM video is supported, not other EBML formats")
    segments = [item for item in roots[1:] if item[0] == 0x18538067]
    if len(segments) != 1:
        _error("WebM requires one retained segment")
    children = _elements(content, segments[0][1], segments[0][2])
    if not {0x1654AE6B, 0x1F43B675} <= {kind for kind, start, end in children if end > start}:
        _error("WebM requires nonempty tracks and a media cluster")
