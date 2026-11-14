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
    scene_span = 7.0 if float(timing.get("duration", 48)) <= 43 else 8.0
    total_duration = round(float(timing.get("duration", len(scenes) * scene_span)))
    if len(scenes) != 6 or any(abs(scene["start"] - index * scene_span) > .25
                               for index, scene in enumerate(scenes)):
        raise SystemExit("Tour scenes have drifted from their localized caption times")

    cuts = timing.get("cuts") or [
        {
            "start": index * scene_span,
            "end": (index + 1) * scene_span,
            "x": scene["x"],
            "y": scene["y"],
            "zoom": scene["zoom"],
        }
        for index, scene in enumerate(scenes)
    ]

    def cut_expr(key: str) -> str:
        expression = str(cuts[-1][key])
        for cut in reversed(cuts[:-1]):
            expression = f"if(lt(in_time,{cut['end']}),{cut[key]},{expression})"
        return expression

    def cut_ease() -> str:
        # Snappy 0.22s ease-in, hold on the evidence, 0.20s ease-out before the next cut.
        def seg_ease(start: float, end: float) -> str:
            dur = max(0.6, end - start)
            out_at = max(0.3, dur - 0.20)
            local = f"(in_time-{start:.3f})"
            return (
                f"if(lt({local},0.22),(1-cos(PI*{local}/0.22))/2,"
                f"if(lt({local},{out_at:.3f}),1,"
                f"if(lt({local},{dur:.3f}),(1+cos(PI*({local}-{out_at:.3f})/0.20))/2,0)))"
            )

        expression = seg_ease(cuts[-1]["start"], cuts[-1]["end"])
        for cut in reversed(cuts[:-1]):
            expression = f"if(lt(in_time,{cut['end']}),{seg_ease(cut['start'], cut['end'])},{expression})"
        return expression

    # Upscale before zoompan: fractional zoom steps on a 2x canvas avoid
    # integer rounding jitter, then downscale cleanly to 1440x900 at 30 fps.
    filters = ("fps=30,scale=2880:1800:flags=lanczos,"
               f"zoompan=z='1+({cut_expr('zoom')}-1)*({cut_ease()})':"
               f"x='max(0,min(iw-iw/zoom,iw*({cut_expr('x')})-iw/zoom/2))':"
               f"y='max(0,min(ih-ih/zoom,ih*({cut_expr('y')})-ih/zoom/2))':"
               "d=1:s=2880x1800:fps=30,"
               "scale=1440:900:flags=lanczos,fps=30")
    for suffix, codec in (
        ("mp4", ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-movflags", "+faststart"]),
        ("webm", ["-c:v", "libaom-av1", "-cpu-used", "6", "-crf", "40", "-b:v", "0", "-row-mt", "1", "-threads", "4"]),
    ):
        target = OUT_DIR / f"product-tour.{suffix}"
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", str(timing["trim"]),
             "-i", str(source), "-t", str(total_duration), "-an", "-map_metadata", "-1", "-vf", filters,
             *codec, "-pix_fmt", "yuv420p", str(target)])
        if target.stat().st_size > 4_000_000:
            raise SystemExit(f"{target.name} exceeds its 4 MB budget")
        print(f"{target.relative_to(BASE_DIR)} {target.stat().st_size:,} bytes")
    run([ffmpeg, "-y", "-loglevel", "error", "-ss", "1.4", "-i", str(OUT_DIR / "product-tour.mp4"),
         "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(OUT_DIR / "product-tour.webp")])


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def convert_social_cuts() -> None:
    """Render punchy 16:9 and 9:16 social-media highlight reels with burned-in kinetic hooks."""
    source = RAW_DIR / "product-tour.webm"
    timing = json.loads(source.with_suffix(".json").read_text(encoding="utf-8"))
    hooks = timing.get("socialHooks") or []
    if not hooks:
        return
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish social clips.")
    font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_opt = f":fontfile={font}" if Path(font).is_file() else ""
    trim_offset = float(timing["trim"])

    # 1) 16:9 Social Reel (1440x900, 30fps)
    parts_16x9: list[str] = []
    concat_16x9: list[str] = []
    # 2) 9:16 Vertical Reel (1080x1920, 30fps)
    parts_9x16: list[str] = []
    concat_9x16: list[str] = []

    for idx, hook in enumerate(hooks):
        start = trim_offset + float(hook["start"])
        end = trim_offset + float(hook["end"])
        label = _escape_drawtext(str(hook["text"]))
        focus_x = max(0.15, min(0.85, float(hook.get("x", 0.5))))
        # 16:9 segment with bottom kinetic hook pill
        parts_16x9.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,fps=30,scale=1440:900:flags=lanczos,"
            f"drawtext=text='{label}'{font_opt}:expansion=none:fontsize=36:fontcolor=white:"
            "box=1:boxcolor=0x0d1322@0.90:boxborderw=18:x=(w-text_w)/2:y=h-text_h-48[v" + str(idx) + "]"
        )
        concat_16x9.append(f"[v{idx}]")

        # 9:16 segment: track horizontal focus, scale into centered studio frame on dark canvas, top brand + bottom hook
        crop_x = f"max(0,min(iw-iw*0.5625,iw*{focus_x:.3f}-iw*0.28125))"
        parts_9x16.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,fps=30,"
            f"crop=w=iw*0.5625:h=ih:x='{crop_x}':y=0,scale=1080:1200:flags=lanczos,"
            "pad=1080:1920:0:360:color=0x0d1322,"
            f"drawtext=text='LIXITY · OFFLINE MANUSCRIPT STUDIO'{font_opt}:fontsize=26:fontcolor=0x93c5fd:x=(w-text_w)/2:y=220,"
            f"drawtext=text='{label}'{font_opt}:expansion=none:fontsize=44:fontcolor=white:"
            "box=1:boxcolor=0x1e293b@0.92:boxborderw=22:x=(w-text_w)/2:y=1640[v" + str(idx) + "]"
        )
        concat_9x16.append(f"[v{idx}]")

    for name, parts, concat_inputs, max_bytes in (
        ("social-hook-16x9.mp4", parts_16x9, concat_16x9, 3_500_000),
        ("social-hook-9x16.mp4", parts_9x16, concat_9x16, 4_000_000),
    ):
        fc = ";".join(parts) + ";" + "".join(concat_inputs) + f"concat=n={len(hooks)}:v=1:a=0[out]"
        target = OUT_DIR / name
        run([
            ffmpeg, "-y", "-loglevel", "error", "-i", str(source),
            "-filter_complex", fc, "-map", "[out]", "-an", "-map_metadata", "-1",
            "-c:v", "libx264", "-preset", "slow", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(target),
        ])
        if target.stat().st_size > max_bytes:
            raise SystemExit(f"{target.name} exceeds its {max_bytes:,} byte budget")
        print(f"{target.relative_to(BASE_DIR)} {target.stat().st_size:,} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["product-tour", "social", *(item[0] for item in WALKTHROUGHS)])
    args = parser.parse_args()
    if args.only in (None, "product-tour"):
        convert_product_tour()
    if args.only in (None, "product-tour", "social"):
        convert_social_cuts()
    for name, poster_at, max_mp4, max_gif in WALKTHROUGHS:
        if args.only in (None, name):
            convert(name, poster_at, max_mp4, max_gif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
