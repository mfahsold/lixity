"""Generate deterministic multi-size/multi-format brand icons from docs/assets/mark.svg."""

from __future__ import annotations

import shutil
import subprocess
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

    png_sizes = (16, 32, 48, 64, 192, 512, 1024)
    for size in png_sizes:
        out = BRAND_DIR / f"icon-{size}.png"
        subprocess.run(  # noqa: S603 -- trusted magick binary and internal repo Paths
            [
                magick,
                "-background",
                "none",
                "-density",
                "384",
                str(SRC_SVG),
                "-resize",
                f"{size}x{size}",
                str(out),
            ],
            check=True,
        )

    # Apple Touch Icon requires an opaque background so iOS does not render black corners.
    subprocess.run(  # noqa: S603 -- trusted magick binary and internal repo Paths
        [
            magick,
            "-background",
            "#2949cc",
            "-density",
            "384",
            str(SRC_SVG),
            "-flatten",
            "-resize",
            "180x180",
            str(BRAND_DIR / "apple-touch-icon.png"),
        ],
        check=True,
    )

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
