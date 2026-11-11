"""Convert recorded walkthroughs into published MP4, GIF and poster files.

Recordings come from ``scripts/make_screenshots.py --video`` (Playwright WebM in
``.artifacts/screenshots/videos/``). This script requires ``ffmpeg`` on PATH and
writes the reviewed outputs into ``docs/videos/``; commit them together with the
documentation that embeds them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / ".artifacts" / "screenshots" / "videos"
OUT_DIR = BASE_DIR / "docs" / "videos"

#: name, poster timestamp, max MP4 bytes, max GIF bytes
WALKTHROUGHS: tuple[tuple[str, str, int, int], ...] = (
    ("research-timeline", "6.0", 2_000_000, 4_000_000),
    ("analysis-review", "5.5", 2_000_000, 4_000_000),
    ("editorial-loop", "11.5", 2_000_000, 4_000_000),
)


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)  # noqa: S603 - fixed ffmpeg invocation


def convert(name: str, poster_at: str, max_mp4: int, max_gif: int) -> None:
    source = RAW_DIR / f"{name}.webm"
    if not source.is_file():
        raise SystemExit(
            f"Missing recording: {source}. Run 'python scripts/make_screenshots.py --video' first."
        )
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mp4 = OUT_DIR / f"{name}.mp4"
    gif = OUT_DIR / f"{name}.gif"
    poster = OUT_DIR / f"{name}.png"
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(mp4),
        ]
    )
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-an",
            "-vf",
            "fps=5,scale=800:-1:flags=lanczos,split[s0][s1];"
            "[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer",
            "-loop",
            "0",
            str(gif),
        ]
    )
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            poster_at,
            "-i",
            str(source),
            "-frames:v",
            "1",
            str(poster),
        ]
    )
    for path, limit in ((mp4, max_mp4), (gif, max_gif)):
        size = path.stat().st_size
        if size > limit:
            raise SystemExit(f"{path.name} is {size:,} bytes; the limit is {limit:,}.")
        print(f"{path.relative_to(BASE_DIR)} {size:,} bytes")
    print(f"{poster.relative_to(BASE_DIR)} {poster.stat().st_size:,} bytes")


def convert_product_tour() -> None:
    """Encode the quiet homepage tour without baking a language into its frames."""
    source = RAW_DIR / "product-tour.webm"
    timing = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scenes = timing["scenes"]
    if len(scenes) != 6 or any(abs(scene["start"] - index * 8) > .2
                               for index, scene in enumerate(scenes)):
        raise SystemExit("Tour scenes have drifted from their localized caption times")

    def value(key: str) -> str:
        expression = str(scenes[-1][key])
        for index in range(4, -1, -1):
            expression = f"if(lt(in_time,{(index + 1) * 8}),{scenes[index][key]},{expression})"
        return expression

    # Ease into a bounded detail view, hold it, then restore the overview before
    # the next dissolve. Captions remain outside the encoded camera transform.
    # Upscale before zoompan: fractional zoom steps on a 2x canvas avoid the
    # integer rounding that made slow pushes look jerky, then downscale.
    phase = "mod(in_time,8)"
    ease = (f"if(lt({phase},0.7),0,if(lt({phase},2.3),(1-cos(PI*({phase}-0.7)/1.6))/2,"
            f"if(lt({phase},5.9),1,if(lt({phase},7.3),(1+cos(PI*({phase}-5.9)/1.4))/2,0))))")
    filters = ("fps=20,scale=2880:1800:flags=lanczos,"
               f"zoompan=z='1+({value('zoom')}-1)*({ease})':"
               f"x='max(0,min(iw-iw/zoom,iw*({value('x')})-iw/zoom/2))':"
               f"y='max(0,min(ih-ih/zoom,ih*({value('y')})-ih/zoom/2))':"
               "d=1:s=2880x1800:fps=20,"
               "scale=1440:900:flags=lanczos,fps=20")
    for suffix, codec in (
        ("mp4", ["-c:v", "libx264", "-preset", "veryslow", "-crf", "30", "-movflags", "+faststart"]),
        ("webm", ["-c:v", "libaom-av1", "-cpu-used", "6", "-crf", "40", "-b:v", "0", "-row-mt", "1", "-threads", "4"]),
    ):
        target = OUT_DIR / f"product-tour.{suffix}"
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", str(timing["trim"]),
             "-i", str(source), "-t", "48", "-an", "-map_metadata", "-1", "-vf", filters,
             *codec, "-pix_fmt", "yuv420p", str(target)])
        if target.stat().st_size > 4_000_000:
            raise SystemExit(f"{target.name} exceeds its 4 MB budget")
        print(f"{target.relative_to(BASE_DIR)} {target.stat().st_size:,} bytes")
    run([ffmpeg, "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(OUT_DIR / "product-tour.mp4"),
         "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(OUT_DIR / "product-tour.webp")])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["product-tour", *(item[0] for item in WALKTHROUGHS)])
    args = parser.parse_args()
    if args.only in (None, "product-tour"):
        convert_product_tour()
    for name, poster_at, max_mp4, max_gif in WALKTHROUGHS:
        if args.only in (None, name):
            convert(name, poster_at, max_mp4, max_gif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
