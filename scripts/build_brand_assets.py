"""Generate deterministic multi-size/multi-format brand icons from docs/assets/mark.svg."""

from __future__ import annotations

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SRC_SVG = DOCS / "assets" / "mark.svg"
BRAND_DIR = DOCS / "assets" / "brand"


def _magick_bin() -> str:
    for name in ("magick", "convert"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("ImageMagick ('magick' or 'convert') is required to build brand assets.")


def main() -> int:
    magick = _magick_bin()
    BRAND_DIR.mkdir(parents=True, exist_ok=True)

    master_png = BRAND_DIR / "icon-1024.png"
    # mark.svg uses viewBox="0 0 32 32"; 3072 DPI (= 96 * 1024 / 32) rasterizes it
    # at exact native 1024x1024 vector resolution without upscaling blur.
    subprocess.run(  # noqa: S603 -- trusted magick binary and internal repo Paths
        [
            magick,
            "-background",
            "none",
            "-density",
            "3072",
            str(SRC_SVG),
            "-resize",
            "1024x1024",
            str(master_png),
        ],
        check=True,
    )

    png_sizes = (16, 32, 48, 64, 192, 512)
    commands: list[list[str]] = [
        [
            magick,
            str(master_png),
            "-filter",
            "Lanczos",
            "-resize",
            f"{size}x{size}",
            str(BRAND_DIR / f"icon-{size}.png"),
        ]
        for size in png_sizes
    ]
    # Apple Touch Icon requires an opaque background so iOS does not render black corners.
    commands.append(
        [
            magick,
            "-background",
            "#2949cc",
            str(master_png),
            "-flatten",
            "-filter",
            "Lanczos",
            "-resize",
            "180x180",
            str(BRAND_DIR / "apple-touch-icon.png"),
        ]
    )
    with ThreadPoolExecutor(max_workers=min(len(commands), max(1, os.cpu_count() or 2))) as pool:
        for future in [pool.submit(subprocess.run, cmd, check=True) for cmd in commands]:
            future.result()

    # Multi-resolution ICO fallback (16, 32, 48).
    subprocess.run(  # noqa: S603 -- trusted magick binary and internal repo Paths
        [
            magick,
            str(BRAND_DIR / "icon-16.png"),
            str(BRAND_DIR / "icon-32.png"),
            str(BRAND_DIR / "icon-48.png"),
            str(DOCS / "favicon.ico"),
        ],
        check=True,
    )

    # WebP export for modern web cards/social previews.
    subprocess.run(  # noqa: S603 -- trusted magick binary and internal repo Paths
        [
            magick,
            str(BRAND_DIR / "icon-512.png"),
            "-quality",
            "92",
            str(BRAND_DIR / "icon-512.webp"),
        ],
        check=True,
    )

    print(f"Generated brand icon suite in {BRAND_DIR} and {DOCS / 'favicon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
