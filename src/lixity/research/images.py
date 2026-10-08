"""Bounded raster structure checks and exact local-image Markdown references.

These checks validate signatures, dimensions and container structure, not every
compressed pixel or codec feature. Rendering remains the browser's responsibility.
"""

from __future__ import annotations

import re
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import urlencode

from .limits import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
from .models import Reference, Source, SourceVersion

if TYPE_CHECKING:
    from .repository import Repository, Snapshot

IMAGE_TYPES = {"image/png", "image/jpeg"}
IMAGE_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
_UUID = r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
_TARGET = re.compile(rf"lixity:image/({_UUID})/({_UUID})\Z")
_IMAGE = re.compile(r"!\[((?:\\[^\r\n]|[^\]\\\r\n])*)\]\((lixity:image[^\r\n)]*)\)")


def _error(message: str) -> NoReturn:
    from .repository import ResearchError
    raise ResearchError(message)


def validate_image(content: bytes, *, filename: str | None = None) -> dict[str, Any]:
    """Inspect at most 16 MiB without allocating a decoded pixel buffer."""
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_IMAGE_BYTES:
        _error("Image must be nonempty PNG/JPEG bytes of at most 16 MiB")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
        width, height = _png_dimensions(content)
    elif content.startswith(b"\xff\xd8"):
        media_type = "image/jpeg"
        width, height = _jpeg_dimensions(content)
    else:
        _error("Only local PNG and JPEG images are supported")
    if filename is not None and IMAGE_SUFFIXES.get(Path(filename).suffix.lower()) != media_type:
        _error("Image filename extension must match its PNG/JPEG bytes")
    if not width or not height or width * height > MAX_IMAGE_PIXELS:
        _error("Image dimensions must be positive and at most 64 million pixels")
    return {"media_type": media_type, "width": width, "height": height}


def _png_dimensions(content: bytes) -> tuple[int, int]:
    offset = 8
    dimensions: tuple[int, int] | None = None
    data_seen = False
    data_ended = False
    while offset + 12 <= len(content):
        length = struct.unpack_from(">I", content, offset)[0]
        kind = content[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(content) or not re.fullmatch(rb"[A-Za-z]{4}", kind):
            _error("Invalid PNG chunk structure")
        payload = memoryview(content)[offset + 8:offset + 8 + length]
        checksum = zlib.crc32(payload, zlib.crc32(kind))
        if checksum != struct.unpack_from(">I", content, end - 4)[0]:
            _error("PNG chunk checksum mismatch")
        if kind == b"IHDR":
            if offset != 8 or length != 13 or dimensions is not None:
                _error("Invalid PNG image header")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if depth not in depths.get(color, set()) or compression or filtering or interlace not in (0, 1):
                _error("Unsupported PNG image header")
            dimensions = (width, height)
        elif dimensions is None:
            _error("PNG must begin with an image header")
        elif kind in (b"acTL", b"fcTL", b"fdAT"):
            _error("Animated PNG is unsupported; select a static PNG image")
        elif kind[0] < 97 and kind not in (b"PLTE", b"IDAT", b"IEND"):
            _error("Unsupported critical PNG chunk")
        elif kind == b"IDAT":
            if data_ended:
                _error("PNG image data chunks must be consecutive")
            data_seen = data_seen or length > 0
        elif kind == b"IEND":
            if length or not data_seen or end != len(content):
                _error("Invalid PNG end or missing image data")
            return dimensions
        elif data_seen:
            data_ended = True
        offset = end
    _error("Truncated PNG image")


def _jpeg_dimensions(content: bytes) -> tuple[int, int]:
    offset = 2
    dimensions: tuple[int, int] | None = None
    scan_seen = False
    in_scan = False
    while offset < len(content):
        if in_scan:
            offset = content.find(b"\xff", offset)
            if offset < 0:
                break
        if content[offset] != 0xFF:
            _error("Invalid JPEG marker structure")
        while offset < len(content) and content[offset] == 0xFF:
            offset += 1
        if offset >= len(content):
            break
        marker = content[offset]
        offset += 1
        if in_scan and (marker == 0 or 0xD0 <= marker <= 0xD7):
            continue
        in_scan = False
        if marker == 0xD9:
            if dimensions is None or not scan_seen or offset != len(content):
                _error("Invalid JPEG end or missing image scan")
            return dimensions
        if marker in (0, 0xD8) or 0xD0 <= marker <= 0xD7 or offset + 2 > len(content):
            _error("Invalid JPEG marker")
        length = struct.unpack_from(">H", content, offset)[0]
        end = offset + length
        if length < 2 or end > len(content):
            _error("Truncated JPEG segment")
        if marker in (0xC0, 0xC1, 0xC2):
            if length < 8 or dimensions is not None:
                _error("Invalid JPEG frame header")
            depth, height, width, components = struct.unpack_from(">BHHB", content, offset + 2)
            if depth != 8 or components not in (1, 3, 4) or length != 8 + 3 * components:
                _error("Unsupported JPEG frame header")
            dimensions = (width, height)
        elif 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            _error("Unsupported JPEG frame format")
        elif marker == 0xDA:
            if dimensions is None or length < 6:
                _error("JPEG scan requires a frame header")
            components = content[offset + 2]
            if not 1 <= components <= 4 or length != 6 + 2 * components:
                _error("Invalid JPEG scan header")
            scan_seen = True
            in_scan = True
        offset = end
    _error("Truncated JPEG image")


def markdown_code_mask(body: str, *, inline: bool = True) -> str:
    """Mask code while preserving line breaks and offsets; no Markdown rendering."""
    chars = list(body)
    fence: tuple[str, int] | None = None
    offset = 0
    for line in body.splitlines(keepends=True):
        text = line.rstrip("\r\n")
        delimiter = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", text)
        masked = fence is not None or line.startswith(("    ", "\t"))
        if fence is not None:
            if (delimiter and delimiter.group(1)[0] == fence[0]
                    and len(delimiter.group(1)) >= fence[1] and not delimiter.group(2).strip()):
                fence = None
        elif delimiter and (delimiter.group(1)[0] != "`" or "`" not in delimiter.group(2)):
            fence = (delimiter.group(1)[0], len(delimiter.group(1)))
            masked = True
        if masked:
            chars[offset:offset + len(text)] = " " * len(text)
        offset += len(line)
    masked_body = "".join(chars)
    if inline:
        runs = list(re.finditer(r"`+", masked_body))
        index = 0
        while index < len(runs):
            opening = runs[index]
            if _escaped(masked_body, opening.start()):
                index += 1
                continue
            closing = next((n for n in range(index + 1, len(runs)) if runs[n].group() == opening.group()), None)
            if closing is None:
                index += 1
                continue
            for position in range(opening.start(), runs[closing].end()):
                if chars[position] not in "\r\n":
                    chars[position] = " "
            index = closing + 1
    return "".join(chars)


def _escaped(body: str, offset: int) -> bool:
    preceding = offset - 1
    while preceding >= 0 and body[preceding] == "\\":
        preceding -= 1
    return (offset - preceding - 1) % 2 == 1


@dataclass(frozen=True)
class ImageReference:
    source_id: str
    source_version_id: str
    alt: str


def _image_tokens(body: str) -> list[re.Match[str]]:
    if "lixity:image" not in body:
        return []
    masked = markdown_code_mask(body)
    return [match for match in _IMAGE.finditer(body)
            if masked[match.start()] == "!" and not _escaped(body, match.start())]


def extract_image_references(body: str, *, strict: bool = False, previous_body: str = "") -> list[ImageReference]:
    """Extract exact pins; preserve former-release malformed body data as inert.

    Strict writes reject newly introduced malformed reserved tokens. Reads skip
    those tokens; audits can separately request strict inspection of their bytes.
    """
    retained = Counter(match.group() for match in _image_tokens(previous_body)) if strict else Counter()
    refs = []
    for match in _image_tokens(body):
        target = _TARGET.fullmatch(match.group(2))
        if target is None:
            if strict and not retained[match.group()]:
                _error("Image reference requires canonical source and version UUID4 URNs")
            retained[match.group()] -= 1
            continue
        alt = _alternative_text(match.group(1))
        refs.append(ImageReference(target.group(1), target.group(2), alt))
    return refs


def _alternative_text(value: str) -> str:
    return re.sub(r"\\([\\\[\]])", r"\1", value)


def image_descriptions(body: str) -> str:
    """Replace canonical prose image tokens with alt text for display excerpts."""
    pieces: list[str] = []
    end = 0
    for match in _image_tokens(body):
        if _TARGET.fullmatch(match.group(2)) is None:
            continue
        pieces.extend((body[end:match.start()], _alternative_text(match.group(1))))
        end = match.end()
    pieces.append(body[end:])
    return "".join(pieces)


def resolve_image_reference(snapshot: Snapshot, ref: ImageReference) -> dict[str, Any]:
    """Resolve a pin in one explicit snapshot, retaining lifecycle context."""
    purged = snapshot.lifecycle.get(("purge", "source_version", ref.source_version_id))
    source = snapshot.records.get(ref.source_id)
    version = snapshot.records.get(ref.source_version_id)
    base: dict[str, Any] = {"project_id": snapshot.project.id, "source_id": ref.source_id,
                            "source_version_id": ref.source_version_id, "alt": ref.alt,
                            "url": None}
    missing = {**base, "availability": "missing", "reason": None, "media_type": None,
               "context": None, "title": None}
    if version is None:
        if not purged or purged.source_ref != Reference(id=ref.source_id):
            return missing
        return {**base, "availability": "purged", "reason": purged.reason,
                "media_type": None, "context": None, "title": None}
    if not isinstance(source, Source) or not isinstance(version, SourceVersion) or version.source_ref.id != ref.source_id:
        return missing
    if version.blob.media_type not in IMAGE_TYPES:
        return missing
    withdrawn = (snapshot.lifecycle.get(("withdraw", "source", source.id))
                 or snapshot.lifecycle.get(("withdraw", "source_version", version.id)))
    url = "/api/research/image?" + urlencode({"project_id": snapshot.project.id,
                                           "source_id": source.id, "version_id": version.id})
    return {**base, "availability": "withdrawn" if withdrawn else "available", "url": None if withdrawn else url,
            "reason": withdrawn.reason if withdrawn else None,
            "media_type": version.blob.media_type, "context": version.context.model_dump(mode="json"),
            "title": source.title, "sequence": version.sequence}


def resolve_dossier_images(snapshot: Snapshot, body: str) -> list[dict[str, Any]]:
    return [resolve_image_reference(snapshot, ref) for ref in extract_image_references(body)]


def validate_image_changes(snapshot: Snapshot, body: str, previous_body: str = "") -> None:
    """Keep accepted unavailable pins, while refusing new purged/foreign pins."""
    retained = {(ref.source_id, ref.source_version_id) for ref in extract_image_references(previous_body)}
    for ref in extract_image_references(body, strict=True, previous_body=previous_body):
        resolved = resolve_image_reference(snapshot, ref)
        if (ref.source_id, ref.source_version_id) not in retained:
            if resolved["availability"] == "purged":
                _error("New image references cannot identify a purged version")
            if resolved["availability"] == "missing":
                _error("Image reference source and version do not match or are unavailable PNG/JPEG records")


def read_image(repository: Repository, snapshot: Snapshot, *, project_id: str,
               source_id: str, version_id: str) -> dict[str, Any]:
    if project_id != snapshot.project.id:
        _error("Image project does not match the selected research project")
    try:
        source = snapshot.get(Reference(id=source_id), Source)
        version = snapshot.get(Reference(id=version_id), SourceVersion)
    except ValueError as exc:
        _error(str(exc))
    if version.source_ref.id != source.id:
        _error("Image source version does not belong to the requested source")
    if version.blob.media_type not in IMAGE_TYPES:
        _error("Requested source version is not a PNG/JPEG image")
    content = repository.read_blob(version.blob)
    info = validate_image(content)
    if info["media_type"] != version.blob.media_type:
        _error("Retained image type does not match its blob descriptor")
    return {"content": content, **info}
