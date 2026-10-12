"""TrueType subsetting with the standard library only.

Lixity ships without font tooling, so embedding Unicode text means reading a
``glyf``-flavoured sfnt ourselves and writing a smaller, self-consistent one.
The subset keeps composite-glyph closure, a format 4/12 ``cmap`` and recomputed
table checksums; a malformed checksum makes viewers silently reject the font,
so every table is rebuilt rather than copied through.

Only fonts whose ``OS/2`` ``fsType`` permits embedding are accepted. Restricted
licences, and CFF/OpenType-CFF outlines, are refused with an actionable message
instead of producing a document that renders as blank pages.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

SFNT_TRUETYPE = 0x00010000
SFNT_CFF = 0x4F54544F  # 'OTTO'
UNIFONT_MAGIC = 0x74746366  # 'ttcf'

# OpenType OS/2 embedding permissions; versions 0–1 ignore the high bits.
FS_TYPE_RESTRICTED = 0x0002
FS_TYPE_PREVIEW_AND_PRINT = 0x0004
FS_TYPE_EDITABLE = 0x0008
FS_TYPE_NO_SUBSETTING = 0x0100
FS_TYPE_BITMAP_ONLY = 0x0200


class FontError(Exception):
    """Raised when a font cannot be read, subset or legally embedded."""


@dataclass(frozen=True)
class FontMetrics:
    units_per_em: int
    ascent: int
    descent: int
    cap_height: int
    italic_angle: float
    bbox: tuple[int, int, int, int]
    stem_v: int
    flags: int
    postscript_name: str = "TrueTypeFont"


@dataclass(frozen=True)
class EmbeddedFont:
    """A subset font ready to be referenced as CIDFontType2."""

    data: bytes
    glyph_ids: dict[int, int]
    advances: dict[int, int]
    metrics: FontMetrics

    def has(self, codepoint: int) -> bool:
        return codepoint in self.glyph_ids

    def advance(self, codepoint: int) -> float:
        """Return the glyph width in 1/1000 em, independent of the chosen point size."""
        return self.advances.get(codepoint, 0) * 1000 / self.metrics.units_per_em


def _u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise FontError("Font table is truncated")
    return int(struct.unpack_from(">H", data, offset)[0])


def _s16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise FontError("Font table is truncated")
    return int(struct.unpack_from(">h", data, offset)[0])


def _u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise FontError("Font table is truncated")
    return int(struct.unpack_from(">I", data, offset)[0])


def checksum(data: bytes) -> int:
    """Return the sfnt table checksum, padding with zeros to a 4-byte multiple."""
    padded = data + b"\0" * (-len(data) % 4)
    total = 0
    for index in range(0, len(padded), 4):
        total = (total + struct.unpack_from(">I", padded, index)[0]) & 0xFFFFFFFF
    return total


class _Sfnt:
    def __init__(self, data: bytes) -> None:
        if len(data) < 12:
            raise FontError("Font file is too small to contain a table directory")
        magic = _u32(data, 0)
        if magic == UNIFONT_MAGIC:
            raise FontError(
                "TrueType collections are not supported; supply a single-face font file"
            )
        if magic not in (SFNT_TRUETYPE, SFNT_CFF):
            raise FontError("Unsupported font format; expected a TrueType outline font")
        if magic == SFNT_CFF:
            raise FontError("CFF outlines are not supported; supply a TrueType (glyf) font file")
        self.data = data
        count = _u16(data, 4)
        self.tables: dict[bytes, tuple[int, int]] = {}
        for index in range(count):
            base = 12 + index * 16
            if base + 16 > len(data):
                raise FontError("Truncated font table directory")
            tag = data[base : base + 4]
            if tag in self.tables:
                raise FontError(f"Duplicate font table {tag.decode('latin-1')}")
            self.tables[tag] = (_u32(data, base + 8), _u32(data, base + 12))
        for required in (b"head", b"hhea", b"maxp", b"hmtx", b"cmap", b"loca", b"glyf"):
            if required not in self.tables:
                raise FontError(f"Font lacks the required {required.decode('latin-1')} table")

    def table(self, tag: bytes) -> bytes:
        try:
            offset, length = self.tables[tag]
        except KeyError:
            raise FontError(f"Font lacks the required {tag.decode('latin-1')} table") from None
        end = offset + length
        if end > len(self.data):
            raise FontError(f"Font table {tag.decode('latin-1')} extends past the end of the file")
        return self.data[offset:end]


def _parse_cmap(data: bytes) -> dict[int, int]:
    """Return Unicode codepoint to glyph id, preferring full-repertoire subtables."""
    if len(data) < 4:
        raise FontError("Font cmap table is truncated")
    best: dict[int, int] = {}
    best_rank = -1
    for index in range(_u16(data, 2)):
        base = 4 + index * 8
        if base + 8 > len(data):
            break
        platform, encoding, offset = _u16(data, base), _u16(data, base + 2), _u32(data, base + 4)
        # (3,10) format 12 covers the full Unicode range, (3,1) covers the BMP,
        # (0,x) is Unicode and preferred over legacy Macintosh encodings.
        if platform == 3 and encoding == 10:
            rank = 4
        elif platform == 0:
            rank = 3
        elif platform == 3 and encoding == 1:
            rank = 2
        elif platform == 0 or platform == 3:
            rank = 1
        else:
            continue
        if rank <= best_rank or offset + 4 > len(data):
            continue
        try:
            table = _parse_cmap_subtable(data, offset)
        except FontError:
            continue
        best_rank, best = rank, table
    if not best:
        raise FontError("Font has no usable Unicode character map")
    return best


def _parse_cmap_subtable(data: bytes, offset: int) -> dict[int, int]:
    fmt = _u16(data, offset)
    mapping: dict[int, int] = {}
    if fmt == 4:
        seg_x2 = _u16(data, offset + 6)
        segments = seg_x2 // 2
        ends = offset + 14
        starts = ends + seg_x2 + 2
        deltas = starts + seg_x2
        ranges = deltas + seg_x2
        for segment in range(segments):
            end = _u16(data, ends + segment * 2)
            start = _u16(data, starts + segment * 2)
            delta = _u16(data, deltas + segment * 2)
            range_offset = _u16(data, ranges + segment * 2)
            if start > end:
                continue
            for codepoint in range(start, min(end, 0xFFFF) + 1):
                if range_offset == 0:
                    glyph = (codepoint + delta) & 0xFFFF
                else:
                    position = ranges + segment * 2 + range_offset + (codepoint - start) * 2
                    if position + 2 > len(data):
                        continue
                    glyph = _u16(data, position)
                    if glyph:
                        glyph = (glyph + delta) & 0xFFFF
                if glyph:
                    mapping[codepoint] = glyph
    elif fmt == 12:
        groups = _u32(data, offset + 12)
        for group in range(groups):
            base = offset + 16 + group * 12
            if base + 12 > len(data):
                break
            start, end, glyph = struct.unpack_from(">III", data, base)
            if start > end:
                continue
            for codepoint in range(start, min(end, start + 0x10000) + 1):
                mapping[codepoint] = glyph + (codepoint - start)
    elif fmt == 6:
        first, count = _u16(data, offset + 6), _u16(data, offset + 8)
        for step in range(count):
            position = offset + 10 + step * 2
            if position + 2 > len(data):
                break
            glyph = _u16(data, position)
            if glyph:
                mapping[first + step] = glyph
    elif fmt == 0:
        for codepoint in range(256):
            position = offset + 6 + codepoint
            if position >= len(data):
                break
            if data[position]:
                mapping[codepoint] = data[position]
    else:
        raise FontError(f"Unsupported cmap subtable format {fmt}")
    return mapping


def _loca(sfnt: _Sfnt, num_glyphs: int) -> list[int]:
    raw = sfnt.table(b"loca")
    long_format = _s16(sfnt.table(b"head"), 50) == 1
    offsets = []
    for index in range(num_glyphs + 1):
        if long_format:
            if (index + 1) * 4 > len(raw):
                raise FontError("Font loca table is shorter than its glyph count")
            offsets.append(_u32(raw, index * 4))
        else:
            if (index + 1) * 2 > len(raw):
                raise FontError("Font loca table is shorter than its glyph count")
            offsets.append(_u16(raw, index * 2) * 2)
    return offsets


def _composite_closure(glyf: bytes, loca: list[int], roots: set[int]) -> set[int]:
    """Add every glyph reachable through composite outlines, bounding the loop."""
    needed = set(roots)
    queue = list(roots)
    while queue:
        gid = queue.pop()
        if gid + 1 >= len(loca):
            raise FontError("Composite glyph references an outline outside the font")
        start, end = loca[gid], loca[gid + 1]
        if end <= start or end > len(glyf):
            continue
        glyph = glyf[start:end]
        if len(glyph) < 10 or int(struct.unpack_from(">h", glyph, 0)[0]) >= 0:
            continue
        for component in _components(glyph):
            if component not in needed:
                needed.add(component)
                queue.append(component)
    return needed


def _build_cmap(mapping: dict[int, int]) -> bytes:
    """Use BMP format 4 when bounded, and format 12 for the full repertoire."""
    bmp = {cp: gid for cp, gid in mapping.items() if cp <= 0xFFFF}
    full = mapping if any(cp > 0xFFFF for cp in mapping) else {}

    segments: list[tuple[int, int]] = []
    for codepoint in sorted(bmp):
        if (
            segments
            and codepoint == segments[-1][1] + 1
            and bmp[codepoint] == bmp.get(segments[-1][1], -1) + 1
            and segments[-1][1] - segments[-1][0] < 0xFFFF
        ):
            segments[-1] = (segments[-1][0], codepoint)
        else:
            segments.append((codepoint, codepoint))
    if not segments or segments[0][0] != 0:
        segments.insert(0, (0, 0))
    segments.append((0xFFFF, 0xFFFF))

    seg_count = len(segments)
    ends, starts, deltas, offsets = [], [], [], []
    for start, end in segments:
        ends.append(end)
        starts.append(start)
        # The (0,0) and (0xFFFF,0xFFFF) sentinels must resolve to the missing glyph.
        deltas.append(1 if start == 0xFFFF else (bmp.get(start, 0) - start) & 0xFFFF)
        offsets.append(0)
    # Format 4 order is endCode, reservedPad, startCode, idDelta, idRangeOffset.
    # idRangeOffset is always zero here, so glyphIdArray stays empty and the
    # declared length must match exactly or fontTools and viewers reject it.
    length = 16 + seg_count * 8
    if length > 0xFFFF:
        return _full_unicode_cmap(mapping)
    entry_selector = max(0, (seg_count - 1).bit_length() - 1)
    search_range = 2 << entry_selector
    subtable = (
        struct.pack(
            ">HHHHHHH",
            4,
            length,
            0,
            seg_count * 2,
            search_range,
            entry_selector,
            seg_count * 2 - search_range,
        )
        + b"".join(struct.pack(">H", value) for value in ends)
        + struct.pack(">H", 0)
        + b"".join(
            struct.pack(">H", value) for group in (starts, deltas, offsets) for value in group
        )
    )

    if not full:
        return struct.pack(">HHHHI", 0, 1, 3, 1, 12) + subtable

    return _full_unicode_cmap(full, subtable)


def _full_unicode_cmap(mapping: dict[int, int], bmp_subtable: bytes | None = None) -> bytes:
    """Share format 12 packing for non-BMP and larger-than-format-4 mappings."""

    groups: list[list[int]] = []
    for codepoint in sorted(mapping):
        if (
            groups
            and codepoint == groups[-1][1] + 1
            and mapping[codepoint] == mapping[groups[-1][1]] + 1
        ):
            groups[-1][1] = codepoint
        else:
            groups.append([codepoint, codepoint])
    header12 = struct.pack(">HHIII", 12, 0, 16 + len(groups) * 12, 0, len(groups))
    body12 = b"".join(struct.pack(">III", start, end, mapping[start]) for start, end in groups)
    if bmp_subtable is None:
        return struct.pack(">HHHHI", 0, 1, 3, 10, 12) + header12 + body12
    record = struct.pack(">HHI", 3, 1, 20)
    record12 = struct.pack(">HHI", 3, 10, 20 + len(bmp_subtable))
    header = struct.pack(">HH", 0, 2)
    return header + record + record12 + bmp_subtable + header12 + body12


def _embedding_permissions(data: bytes) -> None:
    """Refuse restricted outlines/subsets without misreading editable rights."""
    if len(data) < 10:
        raise FontError("Truncated OS/2 embedding permissions")
    version, fs_type = _u16(data, 0), _u16(data, 8)
    permission = fs_type & 0x000E
    if version >= 3 and permission not in (0, 2, 4, 8):
        raise FontError("Invalid font embedding permissions")
    # Older tables can combine permissions; the least restrictive takes effect.
    if permission & FS_TYPE_RESTRICTED and not permission & (
        FS_TYPE_PREVIEW_AND_PRINT | FS_TYPE_EDITABLE
    ):
        raise FontError("Font licence forbids embedding; choose an embeddable TrueType font")
    if version >= 2:
        if fs_type & FS_TYPE_NO_SUBSETTING:
            raise FontError("Font licence forbids subsetting; choose a font permitting subsets")
        if fs_type & FS_TYPE_BITMAP_ONLY:
            raise FontError("Font permits bitmap embedding only; TrueType outlines cannot be embedded")


def _postscript_name(sfnt: _Sfnt) -> str:
    if b"name" not in sfnt.tables:
        return "TrueTypeFont"
    data = sfnt.table(b"name")
    if len(data) < 6:
        raise FontError("Font name table is truncated")
    choices: list[tuple[int, str]] = []
    count, strings = _u16(data, 2), _u16(data, 4)
    for index in range(count):
        position = 6 + index * 12
        if position + 12 > len(data):
            raise FontError("Font name records are truncated")
        platform, _encoding, _language, name_id, length, offset = struct.unpack_from(
            ">6H", data, position)
        if name_id != 6 or strings + offset + length > len(data):
            continue
        raw = data[strings + offset:strings + offset + length]
        try:
            if platform in (0, 3):
                name = raw.decode("utf-16-be")
            elif platform == 1:
                name = raw.decode("mac_roman")
            else:
                continue
        except UnicodeDecodeError:
            continue
        if name.strip():
            choices.append((2 if platform in (0, 3) else 1, name.strip()))
    return max(choices)[1] if choices else "TrueTypeFont"


def _metrics(sfnt: _Sfnt) -> FontMetrics:
    head = sfnt.table(b"head")
    hhea = sfnt.table(b"hhea")
    maxp = sfnt.table(b"maxp")
    units = _u16(head, 18) or 1000
    bbox = (_s16(head, 36), _s16(head, 38), _s16(head, 40), _s16(head, 42))
    ascent, descent = _s16(hhea, 4), _s16(hhea, 6)
    cap_height = round(ascent * 0.7)
    # Identity-H addresses a Unicode CID repertoire, not a standard Latin encoding.
    italic, flags, stem_v = 0.0, 4, 80
    os2 = sfnt.tables.get(b"OS/2")
    if os2 is not None:
        data = sfnt.table(b"OS/2")
        _embedding_permissions(data)
        if len(data) >= 78:
            selection = _u16(data, 62)
            if selection & (0x0001 | 0x0200):
                flags |= 64
            if data[32] == 2 and 2 <= data[33] <= 10:  # PANOSE Latin serif styles
                flags |= 2
            cap_height = _s16(data, 88) if len(data) >= 90 and _s16(data, 88) else cap_height
    post = sfnt.tables.get(b"post")
    if post is not None:
        data = sfnt.table(b"post")
        if len(data) >= 12:
            fixed = struct.unpack_from(">i", data, 4)[0]
            if fixed != 0:  # stored as a 16.16 fraction
                italic = fixed / 65536.0
        if len(data) >= 16 and _u32(data, 12):
            flags |= 1
    # head.macStyle bit 1 marks an italic face; the PDF wants that as bit 6.
    if _s16(head, 44) & 0x0002:
        flags |= 0x0040
    # maxp 0.5 omits the composite fields; both versions describe glyf outlines.
    if _u32(maxp, 0) not in (0x00005000, 0x00010000):
        raise FontError("Unsupported font version")
    return FontMetrics(units, ascent, descent, cap_height, italic, bbox, stem_v, flags,
                       _postscript_name(sfnt))


def subset_font(path: str | Path, codepoints: set[int]) -> EmbeddedFont:
    """Build a subset containing ``codepoints`` plus composite dependencies."""
    with Path(path).open("rb") as stream:
        sfnt = _Sfnt(stream.read())
    metrics = _metrics(sfnt)
    if not codepoints:
        raise FontError("No characters to embed; supply text with at least one printable character")
    cmap = _parse_cmap(sfnt.table(b"cmap"))
    maxp = sfnt.table(b"maxp")
    num_glyphs = _u16(maxp, 4)
    glyf = sfnt.table(b"glyf")
    loca = _loca(sfnt, num_glyphs)

    roots = {0}
    for codepoint in sorted(codepoints):
        glyph = cmap.get(codepoint)
        if glyph is None:
            continue
        roots.add(glyph)
    if roots == {0}:
        raise FontError("The font cannot draw any of the requested characters")
    needed = _composite_closure(glyf, loca, roots)
    order = sorted(needed)
    remap = {gid: index for index, gid in enumerate(order)}

    hmtx = sfnt.table(b"hmtx")
    hhea = sfnt.table(b"hhea")
    # hhea uses 16-bit FWORD metrics, so numberOfHMetrics lands at offset 34.
    original_hmetrics = _u16(hhea, 34)
    advances, bearings = [], []
    for gid in order:
        # longHorMetric is advanceWidth uint16 plus lsb int16, so entries are 4 bytes.
        if gid < original_hmetrics:
            if (gid + 1) * 4 > len(hmtx):
                raise FontError("Font hmtx table is shorter than its metric count")
            advances.append(_u16(hmtx, gid * 4))
            bearings.append(_s16(hmtx, gid * 4 + 2))
        else:
            if original_hmetrics == 0 or original_hmetrics * 4 > len(hmtx):
                raise FontError("Font hmtx table cannot supply a default advance width")
            advances.append(_u16(hmtx, (original_hmetrics - 1) * 4))
            bearing_offset = original_hmetrics * 4 + (gid - original_hmetrics) * 2
            if bearing_offset + 2 > len(hmtx):
                raise FontError("Font hmtx table lacks a trailing side bearing")
            bearings.append(_s16(hmtx, bearing_offset))

    new_glyf = bytearray()
    new_loca = [0]
    for gid in order:
        start, end = loca[gid], loca[gid + 1]
        if end > len(glyf):
            raise FontError("Font loca table points past the glyf table")
        outline = glyf[start:end]
        if _glyph_is_composite(outline):
            # Composite records address glyphs by id. Those ids change when the
            # font is subset, so each component must be rewritten or the glyph
            # points at an outline that is no longer in the file.
            outline = _remap_composite(outline, remap)
        new_glyf += outline
        while len(new_glyf) % 4:
            new_glyf.append(0)
        new_loca.append(len(new_glyf))
    if not new_glyf:
        new_loca = [0, 0]
    loca_blob = struct.pack(f">{len(new_loca)}I", *new_loca)
    hmtx_blob = b"".join(struct.pack(">Hh", advance, bearing)
                         for advance, bearing in zip(advances, bearings, strict=True))

    head = bytearray(sfnt.table(b"head"))
    struct.pack_into(">i", head, 8, 0)  # checkSumAdjustment
    struct.pack_into(">h", head, 50, 1)  # long loca format

    new_hhea = bytearray(hhea)
    struct.pack_into(">H", new_hhea, 34, min(len(advances), 0xFFFF))

    maxp_stats = _outline_stats(glyf, loca, order)
    new_maxp = bytearray(maxp)
    struct.pack_into(">H", new_maxp, 4, len(order))
    struct.pack_into(">H", new_maxp, 6, maxp_stats[0])
    struct.pack_into(">H", new_maxp, 8, maxp_stats[1])
    struct.pack_into(">H", new_maxp, 10, maxp_stats[2])
    struct.pack_into(">H", new_maxp, 12, maxp_stats[3])
    if len(new_maxp) >= 36:  # maxComponentDepth exists only in maxp version 1.0
        struct.pack_into(">H", new_maxp, 34, 0)

    # post 3.0 stores no glyph names, so the original name data is dropped
    # rather than carried along behind a header that says it is absent.
    original_post = sfnt.table(b"post") if b"post" in sfnt.tables else b""
    post = bytearray(original_post[:32].ljust(32, b"\0"))
    struct.pack_into(">I", post, 0, 0x00030000)
    os2 = bytes(sfnt.table(b"OS/2")) if b"OS/2" in sfnt.tables else b""
    name = bytes(sfnt.table(b"name")) if b"name" in sfnt.tables else b""

    mapping = {cp: remap[cmap[cp]] for cp in codepoints if cp in cmap and cmap[cp] in remap}
    tables: dict[bytes, bytes] = {
        b"cmap": _build_cmap(mapping),
        b"glyf": bytes(new_glyf),
        b"head": bytes(head),
        b"hhea": bytes(new_hhea),
        b"hmtx": hmtx_blob,
        b"loca": loca_blob,
        b"maxp": bytes(new_maxp),
        b"post": bytes(post),
    }
    if os2:
        tables[b"OS/2"] = os2
    if name:
        tables[b"name"] = name
    embedded = mapping
    widths = {cp: advances[new_gid] for cp, new_gid in embedded.items()}
    return EmbeddedFont(_assemble(tables), embedded, widths, metrics)


def _outline_stats(glyf: bytes, loca: list[int], glyphs: list[int]) -> tuple[int, int, int, int]:
    """Return maxPoints, maxContours and their composite-only counterparts.

    ``maxp`` stores the worst case over the whole font, so composite outlines
    contribute the totals of the glyphs they reference. Understating these
    fields makes rasterisers drop outlines; overstating them is only wasteful.
    """
    memo: dict[int, tuple[int, int, bool]] = {}

    def walk(gid: int, seen: frozenset[int]) -> tuple[int, int, bool]:
        if gid in memo:
            return memo[gid]
        if gid in seen or gid + 1 >= len(loca):
            return (0, 0, False)
        start, end = loca[gid], loca[gid + 1]
        if end <= start or end > len(glyf):
            return (0, 0, False)
        glyph = glyf[start:end]
        if not _glyph_is_composite(glyph):
            result = (_simple_points(glyph), _simple_contours(glyph), False)
        else:
            points = contours = 0
            for component in _components(glyph):
                child_points, child_contours, _ = walk(component, seen | {gid})
                points += child_points
                contours += child_contours
            result = (points, contours, True)
        memo[gid] = result
        return result

    points = contours = composite_points = composite_contours = 0
    for gid in glyphs:
        glyph_points, glyph_contours, composite = walk(gid, frozenset())
        points = max(points, glyph_points)
        contours = max(contours, glyph_contours)
        if composite:
            composite_points = max(composite_points, glyph_points)
            composite_contours = max(composite_contours, glyph_contours)
    return points, contours, composite_points, composite_contours


_ARG_1_AND_2_ARE_WORDS = 0x0001
_WE_HAVE_A_SCALE = 0x0008
_MORE_COMPONENTS = 0x0020
_WE_HAVE_AN_X_AND_Y_SCALE = 0x0040
_WE_HAVE_A_TWO_BY_TWO = 0x0080


def _component_offsets(glyph: bytes) -> list[int]:
    """Return the byte offset of each component glyph id inside a composite outline.

    Both the closure walk and the remapping writer must step over the composite
    records identically, so the record layout is decoded in exactly one place.
    """
    offsets: list[int] = []
    cursor = 10
    while cursor + 4 <= len(glyph):
        flags = int(struct.unpack_from(">H", glyph, cursor)[0])
        offsets.append(cursor + 2)
        cursor += 4
        cursor += 4 if flags & _ARG_1_AND_2_ARE_WORDS else 2
        if flags & _WE_HAVE_A_SCALE:
            cursor += 2
        elif flags & _WE_HAVE_AN_X_AND_Y_SCALE:
            cursor += 4
        elif flags & _WE_HAVE_A_TWO_BY_TWO:
            cursor += 8
        if not flags & _MORE_COMPONENTS:
            break
    return offsets


def _components(glyph: bytes) -> list[int]:
    """Return the component glyph ids of a composite outline, in record order."""
    return [int(struct.unpack_from(">H", glyph, offset)[0]) for offset in _component_offsets(glyph)]


def _simple_contours(glyph: bytes) -> int:
    return max(struct.unpack_from(">h", glyph, 0)[0], 0) if len(glyph) >= 10 else 0


def _simple_points(glyph: bytes) -> int:
    if len(glyph) < 10:
        return 0
    contours = int(struct.unpack_from(">h", glyph, 0)[0])
    if contours <= 0 or 12 + contours * 2 > len(glyph):
        return 0
    return int(struct.unpack_from(">H", glyph, 10 + (contours - 1) * 2)[0]) + 1


def _glyph_is_composite(glyph: bytes) -> bool:
    return len(glyph) >= 10 and struct.unpack_from(">h", glyph, 0)[0] < 0


def _remap_composite(glyph: bytes, remap: dict[int, int]) -> bytes:
    """Rewrite every component glyph id of a composite outline."""
    patched = bytearray(glyph)
    for offset in _component_offsets(glyph):
        component = int(struct.unpack_from(">H", patched, offset)[0])
        if component not in remap:
            raise FontError("Composite glyph references an outline missing from the subset")
        struct.pack_into(">H", patched, offset, remap[component])
    return bytes(patched)


def _assemble(tables: dict[bytes, bytes]) -> bytes:
    """Serialise tables in the required order with a correct checkSumAdjustment."""
    tags = sorted(tables)
    count = len(tags)
    search_range = 16
    entry_selector = 0
    while search_range * 2 <= count * 16:
        search_range *= 2
        entry_selector += 1
    header = struct.pack(
        ">IHHHH", SFNT_TRUETYPE, count, search_range, entry_selector, count * 16 - search_range
    )
    directory = bytearray()
    body = bytearray()
    offset = len(header) + count * 16
    for tag in tags:
        blob = tables[tag]
        if tag == b"head":
            blob = blob[:8] + b"\0" * 4 + blob[12:]
        padded = blob + b"\0" * (-len(blob) % 4)
        directory += struct.pack(">4sIII", tag, checksum(blob), offset, len(blob))
        body += padded
        offset += len(padded)
    font = bytearray(header + directory + body)
    head_offset = struct.unpack_from(">I", directory, tags.index(b"head") * 16 + 8)[0]
    struct.pack_into(">I", font, head_offset + 8, 0)
    adjustment = (0xB1B0AFBA - checksum(bytes(font))) & 0xFFFFFFFF
    struct.pack_into(">I", font, head_offset + 8, adjustment)
    return bytes(font)


def compress_font(data: bytes) -> bytes:
    return zlib.compress(data, 9)
