"""Synthetic local raster and PDF bytes shared by research tests."""

import struct
import zlib


def png(width=1, height=1):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


# A public-format, synthetic one-pixel JPEG; no manuscript or external fixture.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300" + "01" * 64 +
    "ffc0000b080001000101011100"
    "ffc40014000100000000000000000000000000000000"
    "ffc40014100100000000000000000000000000000000"
    "ffda0008010100003f003fffd9"
)


def make_synthetic_pdf(text: str) -> bytes:
    """Generate a minimal valid PDF-1.4 containing text in a standard Type1 font."""
    stream_bytes = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin1")
    stream_obj = (
        f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin1")
        + stream_bytes
        + b"\nendstream"
    )
    objs = [
        b"",
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        stream_obj,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = [b"%PDF-1.4\n"]
    offsets = [0]
    for i in range(1, len(objs)):
        offsets.append(sum(len(x) for x in pdf))
        pdf.append(f"{i} 0 obj\n".encode("latin1") + objs[i] + b"\nendobj\n")
    xref_offset = sum(len(x) for x in pdf)
    pdf.append(f"xref\n0 {len(objs)}\n0000000000 65535 f \n".encode("latin1"))
    pdf.extend(f"{off:010d} 00000 n \n".encode("latin1") for off in offsets[1:])
    pdf.append(
        f"trailer\n<< /Size {len(objs)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "latin1"
        )
    )
    return b"".join(pdf)
