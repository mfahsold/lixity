"""Independent font-table and reader checks for composed PDF text."""

from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from lixity.pdf_document import Block, Document, FontSet, PdfError, _write_pdf
from lixity.pdf_font import (
    EmbeddedFont,
    FontError,
    _build_cmap,
    _metrics,
    _parse_cmap,
    _Sfnt,
    subset_font,
)
from lixity.pdf_layouts import FontChoice, FontUnavailable, book_pdf, manuscript_pdf, report_pdf
from tests.test_pdf_export import BOLD, HAVE_FONTS, MONO, SERIF

SANS = SERIF.parent / "DejaVuSans.ttf"
ITALIC = SERIF.parent / "DejaVuSerif-Italic.ttf"
if not ITALIC.is_file():
    ITALIC = Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf")
pytestmark = pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")


def tables(data: bytes) -> dict[bytes, bytes]:
    result = {}
    for index in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _checksum, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        result[tag] = data[offset:offset + length]
    return result


def table_checksum(data: bytes) -> int:
    padded = data + b"\0" * (-len(data) % 4)
    return sum(struct.unpack(f">{len(padded) // 4}I", padded)) & 0xFFFFFFFF


def fixture_font(original: Path, replacements: dict[bytes, bytes]) -> bytes:
    """Build a valid synthetic derivative independently of the subset writer."""
    source = {**tables(original.read_bytes()), **replacements}
    tags = sorted(source)
    power = 2 ** (len(tags).bit_length() - 1)
    header = struct.pack(">IHHHH", 0x10000, len(tags), power * 16,
                         power.bit_length() - 1, (len(tags) - power) * 16)
    directory, body = bytearray(), bytearray()
    head_offset = 0
    for tag in tags:
        blob = source[tag]
        if tag == b"head":
            blob = blob[:8] + b"\0" * 4 + blob[12:]
        offset = len(header) + len(tags) * 16 + len(body)
        if tag == b"head":
            head_offset = offset
        directory += struct.pack(">4sIII", tag, table_checksum(blob), offset, len(blob))
        body += blob + b"\0" * (-len(blob) % 4)
    data = bytearray(header + directory + body)
    struct.pack_into(">I", data, head_offset + 8, (0xB1B0AFBA - table_checksum(data)) & 0xFFFFFFFF)
    return bytes(data)


@pytest.mark.parametrize("path", [SERIF, BOLD, MONO, SANS])
def test_subset_preserves_advance_and_side_bearing(path):
    original = tables(path.read_bytes())
    cmap = _parse_cmap(original[b"cmap"])
    face = subset_font(path, set(map(ord, "ÄÖÜ Á fi ﬁ ﬂ W A j")))
    embedded = tables(face.data)
    count = struct.unpack_from(">H", original[b"hhea"], 34)[0]
    for codepoint, new_gid in face.glyph_ids.items():
        old_gid = cmap[codepoint]
        advance_offset = min(old_gid, count - 1) * 4
        bearing_offset = old_gid * 4 + 2 if old_gid < count else count * 4 + (old_gid - count) * 2
        assert struct.unpack_from(">Hh", embedded[b"hmtx"], new_gid * 4) == (
            struct.unpack_from(">H", original[b"hmtx"], advance_offset)[0],
            struct.unpack_from(">h", original[b"hmtx"], bearing_offset)[0],
        )


def test_trailing_short_metrics_preserve_bearings(tmp_path):
    original = tables(MONO.read_bytes())
    count = struct.unpack_from(">H", original[b"hhea"], 34)[0]
    cmap = _parse_cmap(original[b"cmap"])
    codepoint = next(cp for cp, gid in cmap.items() if gid >= count)
    gid = cmap[codepoint]
    hmtx = bytearray(original[b"hmtx"])
    struct.pack_into(">h", hmtx, count * 4 + (gid - count) * 2, -137)
    path = tmp_path / "short-metric.ttf"
    path.write_bytes(fixture_font(MONO, {b"hmtx": bytes(hmtx)}))
    face = subset_font(path, {codepoint})
    assert struct.unpack_from(">h", tables(face.data)[b"hmtx"], face.glyph_ids[codepoint] * 4 + 2)[0] == -137


@pytest.mark.parametrize("path", [SERIF, SANS, MONO])
def test_every_subset_table_has_a_valid_offset_and_checksum(path):
    data = subset_font(path, set(map(ord, "ÄÖÜ ﬁ ﬂ"))).data
    table_count = struct.unpack_from(">H", data, 4)[0]
    for index in range(table_count):
        tag, stored, offset, length = struct.unpack_from(">4sIII", data, 12 + index * 16)
        assert offset >= 12 + table_count * 16
        assert offset % 4 == 0 and offset + length <= len(data)
        blob = data[offset:offset + length]
        if tag == b"head":
            blob = blob[:8] + b"\0" * 4 + blob[12:]
        assert table_checksum(blob) == stored, tag
    assert table_checksum(data) == 0xB1B0AFBA
    assert tables(data)[b"name"] == tables(path.read_bytes())[b"name"]


@pytest.mark.parametrize("path", [SERIF, MONO, ITALIC])
def test_post_header_preserves_original_metrics(path):
    if not path.is_file():
        pytest.skip("optional italic font is unavailable")
    post = tables(subset_font(path, {ord("A")}).data)[b"post"]
    assert struct.unpack_from(">I", post)[0] == 0x30000
    assert len(post) == 32
    assert post[4:16] == tables(path.read_bytes())[b"post"][4:16]


@pytest.mark.parametrize("tag,blob", [
    (b"head", tables(SERIF.read_bytes())[b"head"][:20] if HAVE_FONTS else b""),
    (b"hhea", b"\0" * 12),
    (b"cmap", struct.pack(">HHHHIHH", 0, 1, 3, 1, 12, 4, 4)),
], ids=["head", "hhea", "cmap"])
def test_truncated_font_tables_raise_a_font_error(tmp_path, tag, blob):
    path = tmp_path / "malformed-table.ttf"
    path.write_bytes(fixture_font(SERIF, {tag: blob}))
    with pytest.raises(FontError, match=r"truncated|short|usable"):
        subset_font(path, {ord("A")})


@pytest.mark.parametrize("characters", [{ord("A"), 0x1F600}, {0x1F600}])
def test_non_bmp_subset_cmap_reopens_with_all_requested_characters(tmp_path, characters):
    face = subset_font(SANS, characters)
    cmap = tables(face.data)[b"cmap"]
    for index in range(struct.unpack_from(">H", cmap, 2)[0]):
        platform, encoding, offset = struct.unpack_from(">HHI", cmap, 4 + index * 8)
        assert platform == 3 and encoding in (1, 10)
        assert offset >= 20
        if encoding == 10:
            length = struct.unpack_from(">I", cmap, offset + 4)[0]
            groups = struct.unpack_from(">I", cmap, offset + 12)[0]
            assert length == 16 + groups * 12
            assert offset + length == len(cmap)
    assert characters <= _parse_cmap(cmap).keys()
    path = tmp_path / "reopened.ttf"
    path.write_bytes(face.data)
    assert characters <= subset_font(path, characters).glyph_ids.keys()


@pytest.mark.parametrize("non_bmp", [False, True])
def test_large_bmp_repertoire_uses_full_unicode_cmap_without_uint16_overflow(non_bmp):
    mapping = dict.fromkeys(range(0x100, 0x100 + 9000), 1)
    if non_bmp:
        mapping[0x1F600] = 1
    cmap = _build_cmap(mapping)
    assert struct.unpack_from(">HHHHI", cmap, 0) == (0, 1, 3, 10, 12)
    format_number, reserved, length, language, groups = struct.unpack_from(">HHIII", cmap, 12)
    assert (format_number, reserved, language) == (12, 0, 0)
    assert length == 16 + groups * 12 == len(cmap) - 12
    assert _parse_cmap(cmap) == mapping


@pytest.mark.parametrize("version,bits,accepted", [
    (3, 0, True), (3, 2, False), (3, 4, True), (3, 8, True),
    (3, 0x100, False), (3, 0x200, False), (0, 0x100, True), (1, 0x200, True),
])
def test_embedding_permissions_respect_os2_version(tmp_path, version, bits, accepted):
    os2 = bytearray(tables(SERIF.read_bytes())[b"OS/2"])
    struct.pack_into(">H", os2, 0, version)
    struct.pack_into(">H", os2, 8, bits)
    path = tmp_path / "embedding-policy.ttf"
    path.write_bytes(fixture_font(SERIF, {b"OS/2": bytes(os2)}))
    if accepted:
        assert subset_font(path, {ord("A")}).has(ord("A"))
    else:
        with pytest.raises(FontError, match=r"embedding|subset|bitmap"):
            subset_font(path, {ord("A")})


def test_role_environment_override_is_isolated_and_explicit_choice_wins(monkeypatch):
    for key in os.environ:
        if key.startswith("LIXITY_PDF_FONT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LIXITY_PDF_FONT_HEADING", str(BOLD))
    roles = FontChoice(serif=str(SERIF), mono=str(MONO)).roles()
    assert roles["text"] == str(SERIF) and roles["mono"] == str(MONO)
    assert roles["heading"] == str(BOLD)
    assert roles["sans"] != str(BOLD)
    monkeypatch.setenv("LIXITY_PDF_FONT_TEXT", "/not-a-font.ttf")
    with pytest.raises(FontUnavailable, match=r"text.*not-a-font"):
        FontChoice().roles()
    assert FontChoice(serif=str(SERIF)).roles()["text"] == str(SERIF)


def test_unused_font_roles_do_not_prevent_a_layout():
    assert book_pdf(title="Book", chapters=[("Chapter", ["Synthetic prose."])],
                    choice=FontChoice(serif=str(SERIF), serif_bold=str(BOLD), mono="/absent"))
    assert manuscript_pdf(title="Sheet", body="Synthetic prose.",
                          choice=FontChoice(serif="/absent", mono=str(MONO)))
    assert report_pdf(title="Report", markdown="Synthetic report.",
                      choice=FontChoice(serif="/absent", sans=str(SANS), sans_bold=str(BOLD)))


def test_font_disappearing_after_selection_is_a_pdf_error(tmp_path):
    doc = Document(FontSet({"text": str(tmp_path / "disappeared.ttf")}))
    doc.add(Block("Synthetic prose."))
    with pytest.raises(PdfError, match="Cannot read configured font"):
        doc.render()


def test_pdf_font_descriptor_uses_real_subset_name_and_correct_style_flags():
    fonts = FontSet({"text": str(SERIF), "mono": str(MONO)})
    doc = Document(fonts)
    doc.add(Block("ÄÖÜ regular", role="text"))
    doc.add(Block("monospaced", role="mono"))
    data = doc.render()
    descriptors = re.findall(rb"/FontName /(\S+) /Flags (\d+)", data)
    assert len(descriptors) == 2
    for name, flags in descriptors:
        assert re.fullmatch(rb"[A-Z]{6}\+DejaVu\S+", name)
        assert not int(flags) & 64
        assert bool(int(flags) & 4) != bool(int(flags) & 32)
        if b"Mono" in name:
            assert int(flags) & 1


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftoppm"), reason="requires Poppler pdftoppm")
def test_subset_raster_matches_complete_original_font(tmp_path):
    for path in (SERIF, SANS, MONO):
        _assert_raster_matches(tmp_path, path)


def _assert_raster_matches(tmp_path, path):
    text = "Ångström ÄÖÜ áéíóú, fj W A Œ ﬁ ﬂ — naïve Café."
    fonts = FontSet({"text": str(path)})
    doc = Document(fonts)
    for size in (11, 20, 40):
        doc.add(Block(text, size=size))
    pages = doc._compose()
    subset = fonts.face("text")
    sfnt = _Sfnt(path.read_bytes())
    cmap = _parse_cmap(sfnt.table(b"cmap"))
    hmetrics = struct.unpack_from(">H", sfnt.table(b"hhea"), 34)[0]
    full = EmbeddedFont(path.read_bytes(), cmap, {
        cp: struct.unpack_from(">H", sfnt.table(b"hmtx"), min(gid, hmetrics - 1) * 4)[0]
        for cp, gid in cmap.items()
    }, _metrics(sfnt))
    rasters = []
    executable = shutil.which("pdftoppm")
    assert executable
    for name, face in (("subset", subset), ("full", full)):
        pdf = tmp_path / f"{name}.pdf"
        pdf.write_bytes(_write_pdf(pages, {"text": face}))
        result = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local PDF
            [executable, "-f", "1", "-l", "1", "-r", "144", str(pdf), str(tmp_path / name)],
            capture_output=True, check=True,
        )
        assert not result.stderr
        rasters.append((tmp_path / f"{name}-1.ppm").read_bytes())
    assert rasters[0] == rasters[1]
