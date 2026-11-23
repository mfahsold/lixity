#!/usr/bin/env python3
"""Generate deterministic Tauri v2 desktop icons for macOS, Windows and Linux.

Derives all icons directly from the maintained brand assets under
`docs/assets/brand/` and `docs/favicon.ico` using Python's standard library so
the output is byte-identical on macOS, Linux and Windows.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND_DIR = ROOT / "docs" / "assets" / "brand"
FAVICON_ICO = ROOT / "docs" / "favicon.ico"
OUT_DIR = ROOT / "desktop" / "src-tauri" / "icons"

ICNS_PNG_SLOTS: tuple[tuple[bytes, str], ...] = (
    (b"icp4", "icon-16.png"),
    (b"icp5", "icon-32.png"),
    (b"icp6", "icon-64.png"),
    (b"ic07", "icon-128.png"),
    (b"ic08", "icon-256.png"),
    (b"ic09", "icon-512.png"),
    (b"ic10", "icon-1024.png"),
)


def build_icns_bytes(brand_dir: Path) -> bytes:
    """Assemble a valid multi-resolution Apple ICNS container from PNG assets."""
    chunks: list[bytes] = []
    for ostype, filename in ICNS_PNG_SLOTS:
        png = (brand_dir / filename).read_bytes()
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"Expected PNG asset for {filename}")
        chunks.append(ostype + struct.pack(">I", 8 + len(png)) + png)
    body = b"".join(chunks)
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def expected_icon_bytes() -> dict[str, bytes]:
    return {
        "32x32.png": (BRAND_DIR / "icon-32.png").read_bytes(),
        "128x128.png": (BRAND_DIR / "icon-128.png").read_bytes(),
        "128x128@2x.png": (BRAND_DIR / "icon-256.png").read_bytes(),
        "icon.png": (BRAND_DIR / "icon-512.png").read_bytes(),
        "icon.ico": FAVICON_ICO.read_bytes(),
        "icon.icns": build_icns_bytes(BRAND_DIR),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify icons on disk match brand assets")
    args = parser.parse_args(argv)

    expected = expected_icon_bytes()
    if args.check:
        mismatches = [
            name
            for name, content in expected.items()
            if not (OUT_DIR / name).is_file() or (OUT_DIR / name).read_bytes() != content
        ]
        if mismatches:
            raise SystemExit(
                f"Desktop icons out of sync ({', '.join(mismatches)}); "
                "run desktop/scripts/generate_desktop_icons.py"
            )
        print(f"[OK] {OUT_DIR} matches brand assets ({len(expected)} icon files).")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in expected.items():
        (OUT_DIR / name).write_bytes(content)
    print(f"[OK] Generated {len(expected)} desktop icon files in {OUT_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
