"""Encode recorded guide walkthroughs, the homepage tour and social clips.

Recordings come from ``scripts/make_screenshots.py --video`` (Playwright WebM in
``.artifacts/screenshots/videos/``). The guide outputs use MP4, GIF and PNG.
The homepage and social tours use the same raw shots and timing. See
``docs/videos/README.md`` for encoding prerequisites and review steps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

if __package__:
    from .product_tour_edit import Edit, compose
else:
    from product_tour_edit import Edit, compose

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / ".artifacts" / "screenshots" / "videos"
OUT_DIR = BASE_DIR / "docs" / "videos"
TOUR_TIMING_PATH = OUT_DIR / "product-tour-timing.json"
LANDSCAPE_SOCIAL = "social-hook-16x9.mp4"
PORTRAIT_SOCIAL = "social-hook-9x16.mp4"
PORTRAIT_MASTER = "product-tour-portrait.mp4"
PORTRAIT_POSTER = "product-tour-portrait.png"
SOCIAL_CLIPS = (
    (LANDSCAPE_SOCIAL, 1600, 900, 3_500_000),
    (PORTRAIT_SOCIAL, 1080, 1920, 4_000_000),
)

#: name, poster timestamp, max MP4 bytes, max GIF bytes
WALKTHROUGHS: tuple[tuple[str, str, int, int], ...] = (
    ("research-timeline", "6.0", 2_000_000, 4_000_000),
    ("analysis-review", "5.5", 2_000_000, 4_000_000),
    ("editorial-loop", "11.5", 2_000_000, 4_000_000),
)
PUBLIC_VIDEO_FILES = {
    "README.md", "product-tour.mp4", "product-tour.webm", "product-tour.webp",
    PORTRAIT_MASTER, PORTRAIT_POSTER, LANDSCAPE_SOCIAL, PORTRAIT_SOCIAL,
    *(f"{name}.{suffix}" for name, _, _, _ in WALKTHROUGHS for suffix in ("mp4", "gif", "png")),
}


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


def _tour_plan() -> dict:
    """Load the timeline also consumed by the recorder and localized homepages."""
    plan = json.loads(TOUR_TIMING_PATH.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "lixity-product-tour-timing/2":
        raise SystemExit("Unknown product-tour timing schema")
    scenes = plan["scenes"]
    fps = plan["fps"]
    if not isinstance(fps, int) or fps <= 0 or len(scenes) != 6 or len({scene["id"] for scene in scenes}) != len(scenes):
        raise SystemExit("The product tour needs six ordered scenes and a positive integer fps")
    captures = plan["captures"]
    if {shot["theme"] for shot in captures} != {"light", "dark"}:
        raise SystemExit("The product tour needs actual light and dark workspace shots")
    previous_end = 0
    for scene in scenes:
        start, end = scene["start"], scene["end"]
        if start != previous_end or end <= start or (end - start) * fps % 1:
            raise SystemExit("Tour scenes must cover a contiguous, whole-frame timeline")
        previous_end = end
    if previous_end != plan["duration"]:
        raise SystemExit("Tour scenes do not cover the declared duration")
    return plan


def _video_info(path: Path) -> tuple[dict, dict]:
    """Count decoded frames; container duration alone cannot prove capture capacity."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise SystemExit("ffprobe is required to validate published walkthrough videos.")
    if not path.is_file():
        raise SystemExit(f"Missing video: {path}")
    result = subprocess.run(  # noqa: S603 - fixed ffprobe invocation
        [ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format",
         "-of", "json", str(path)], check=True, capture_output=True, text=True,
    )
    media = json.loads(result.stdout)
    videos = [stream for stream in media["streams"] if stream["codec_type"] == "video"]
    if len(videos) != 1:
        raise SystemExit(f"{path.name} needs exactly one video stream")
    return videos[0], media


def _verify_export(path: Path, *, fps: int, frames: int, width: int, height: int,
                   max_bytes: int = 4_000_000) -> None:
    video, media = _video_info(path)
    if (int(video["nb_read_frames"]) != frames or
            Fraction(video["avg_frame_rate"]) != fps or
            (video["width"], video["height"]) != (width, height) or
            video.get("sample_aspect_ratio") != "1:1" or
            abs(float(media["format"]["duration"]) - frames / fps) > .002 or
            len(media["streams"]) != 1):
        raise SystemExit(f"{path.name} has incomplete timing, unexpected geometry or audio")
    if path.stat().st_size > max_bytes:
        raise SystemExit(f"{path.name} exceeds its {max_bytes:,} byte budget")
    print(f"{path.relative_to(BASE_DIR)} {path.stat().st_size:,} bytes")

def _read_source(filename: str, digest: str, base: Path) -> Path:
    if Path(filename).name != filename:
        raise SystemExit("Tour segment filenames must stay in the raw recordings directory")
    source = base / filename
    if not source.is_file():
        raise SystemExit(f"Missing video source: {source}")
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"{filename}: source hash mismatch; record the complete tour again")
    return source


def _tour_recordings(plan: dict) -> tuple[dict, list[tuple[dict, Path, Path]], Path]:
    recording = json.loads((RAW_DIR / "product-tour.json").read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-product-tour-recording/3" or
            recording.get("fps") != plan["fps"] or recording.get("duration") != plan["duration"]):
        raise SystemExit("Recording metadata does not match the product-tour timing plan")
    segments = recording.get("segments", [])
    if [segment["id"] for segment in segments] != [scene["id"] for scene in plan["captures"]]:
        raise SystemExit("The recording needs one ordered segment per planned camera shot")
    recordings = []
    for scene, segment in zip(plan["captures"], segments, strict=True):
        filename = segment["file"]
        source = _read_source(filename, segment["sha256"], RAW_DIR)
        video, _ = _video_info(source)
        start = segment["startFrame"]
        frames = scene["duration"] * plan["fps"]
        if (not isinstance(start, int) or start < 0 or segment["frames"] != frames or
                segment.get("theme") != scene["theme"] or (video["width"], video["height"]) != (1440, 900) or
                Fraction(video["avg_frame_rate"]) != plan["fps"]):
            raise SystemExit(f"{filename} has an invalid frame anchor, theme, geometry, count or fps")
        if int(video["nb_read_frames"]) < start + frames:
            raise SystemExit(f"{filename} needs {start + frames} frames including its anchor; "
                             f"only {video['nb_read_frames']} were recorded")
        if not 0 < segment["actionEnd"] <= scene["duration"] - 3:
            raise SystemExit(f"{filename} leaves too little time to read the outcome")
        still = _read_source(segment["still"], segment["stillSha256"], RAW_DIR)
        recordings.append((segment, source, still))
    pdf = recording["exhibitPage"]
    return recording, recordings, _read_source(pdf["file"], pdf["sha256"], RAW_DIR)


def _webm_codec(encoders: str) -> list[str]:
    if "libsvtav1" in encoders:
        return ["-c:v", "libsvtav1", "-preset", "9", "-crf", "34"]
    if "libaom-av1" in encoders:
        return ["-c:v", "libaom-av1", "-cpu-used", "7", "-crf", "34", "-b:v", "0", "-row-mt", "1"]
    raise SystemExit("FFmpeg needs an AV1 encoder (libsvtav1 or libaom-av1) for the homepage WebM.")


def convert_product_tour(selection: str | None = None) -> None:
    """Encode the editable FilmCraft cut once per destination codec."""
    plan = _tour_plan()
    recording, recordings, exhibit = _tour_recordings(plan)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    cwebp = shutil.which("cwebp")
    h264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "25", "-movflags", "+faststart"]
    layouts = []
    if selection in (None, "product-tour"):
        encoders = subprocess.check_output([ffmpeg, "-hide_banner", "-encoders"], text=True)  # noqa: S603
        if cwebp is None and "libwebp" not in encoders:
            raise SystemExit("The landscape poster needs cwebp or FFmpeg with libwebp.")
        layouts.append((1440, 900, (
            ("product-tour.mp4", h264),
            ("product-tour.webm", _webm_codec(encoders)),
        )))
    if selection in (None, "product-tour", "portrait", "social"):
        layouts.append((1080, 1920, ((PORTRAIT_SOCIAL if selection == "social" else PORTRAIT_MASTER, h264),)))
    if selection in (None, "product-tour", "social"):
        layouts.append((1600, 900, ((LANDSCAPE_SOCIAL, h264),)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fps = plan["fps"]
    frames = plan["duration"] * fps
    budgets = {name: limit for name, _, _, limit in SOCIAL_CLIPS}

    def encode(width: int, height: int, exports: tuple, staging: Path) -> None:
        review = BASE_DIR / ".artifacts" / "filmcraft" / "warehouse-4-tour"
        review.mkdir(parents=True, exist_ok=True)
        edit = Edit(review / f"warehouse-4-{width}x{height}.fcproj", width, height, fps)
        compose(edit, BASE_DIR, plan, recording, recordings, exhibit)
        with tempfile.TemporaryDirectory(prefix="frames-", dir=review) as temp:
            sequence = edit.render(Path(temp), (2, 7, 10, 16, 18, 22, 25, 30, 34, 39, 43, 49, 54, 58))
            for name, codec in exports:
                target = staging / name
                run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(sequence),
                     "-vf", "setsar=1", "-an", "-map_metadata", "-1",
                     "-frames:v", str(frames), "-r", str(fps), "-fps_mode", "cfr",
                     *codec, "-pix_fmt", "yuv420p", str(target)])
                _verify_export(target, fps=fps, frames=frames, width=width, height=height,
                               max_bytes=budgets.get(name, 4_000_000))
            poster = sequence.with_name(sequence.name % (2 * fps))
            if width == 1440:
                target = staging / "product-tour.webp"
                if cwebp:
                    run([cwebp, "-quiet", "-q", "85", str(poster), "-o", str(target)])
                else:
                    run([ffmpeg, "-y", "-loglevel", "error", "-i", str(poster),
                         "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(target)])
            if width == 1080 and selection != "social":
                run([ffmpeg, "-y", "-loglevel", "error", "-i", str(poster),
                     "-frames:v", "1", "-vf", "scale=540:960:flags=lanczos", str(staging / PORTRAIT_POSTER)])

    with tempfile.TemporaryDirectory(prefix=".tour-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        with ThreadPoolExecutor(max_workers=min(3, len(layouts))) as pool:
            futures = [pool.submit(encode, width, height, exports, staging) for width, height, exports in layouts]
            for future in futures:
                future.result()
        if selection in (None, "product-tour"):
            shutil.copyfile(staging / PORTRAIT_MASTER, staging / PORTRAIT_SOCIAL)
        for target in staging.iterdir():
            target.replace(OUT_DIR / target.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["product-tour", "portrait", "social", *(item[0] for item in WALKTHROUGHS)])
    args = parser.parse_args()
    jobs = []
    if args.only in (None, "product-tour", "portrait", "social"):
        jobs.append((convert_product_tour, (args.only,)))
    for name, poster_at, max_mp4, max_gif in WALKTHROUGHS:
        if args.only in (None, name):
            jobs.append((convert, (name, poster_at, max_mp4, max_gif)))
    workers = min(len(jobs), max(1, min(4, os.cpu_count() or 2)))
    if workers <= 1:
        for fn, fn_args in jobs:
            fn(*fn_args)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fn, *fn_args) for fn, fn_args in jobs]
            for future in futures:
                future.result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
