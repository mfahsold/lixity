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
    if {scene["theme"] for scene in scenes} != {"light", "dark"}:
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

def _tour_recordings(plan: dict) -> list[tuple[dict, dict, Path]]:
    recording = json.loads((RAW_DIR / "product-tour.json").read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-product-tour-recording/2" or
            recording.get("fps") != plan["fps"] or recording.get("duration") != plan["duration"]):
        raise SystemExit("Recording metadata does not match the product-tour timing plan")
    segments = recording.get("segments", [])
    if [segment["id"] for segment in segments] != [scene["id"] for scene in plan["scenes"]]:
        raise SystemExit("The recording needs one ordered segment per tour scene")
    recordings = []
    for scene, segment in zip(plan["scenes"], segments, strict=True):
        filename = segment["file"]
        if Path(filename).name != filename:
            raise SystemExit("Tour segment filenames must stay in the raw recordings directory")
        source = RAW_DIR / filename
        if not source.is_file():
            raise SystemExit(f"Missing video: {source}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != segment.get("sha256"):
            raise SystemExit(f"{filename}: source hash mismatch; record the complete tour again")
        video, _ = _video_info(source)
        start = segment["startFrame"]
        frames = (scene["end"] - scene["start"]) * plan["fps"]
        if (not isinstance(start, int) or start < 0 or segment["frames"] != frames or
                segment.get("theme") != scene["theme"] or (video["width"], video["height"]) != (1440, 900) or
                Fraction(video["avg_frame_rate"]) != plan["fps"]):
            raise SystemExit(f"{filename} has an invalid frame anchor, theme, geometry, count or fps")
        if int(video["nb_read_frames"]) < start + frames:
            raise SystemExit(f"{filename} needs {start + frames} frames including its anchor; "
                             f"only {video['nb_read_frames']} were recorded")
        if not 0 < segment["actionEnd"] <= scene["end"] - scene["start"] - 3:
            raise SystemExit(f"{filename} leaves too little time to read the outcome")
        recordings.append((scene, segment, source))
    return recordings


def _drawtext(label: str, font: str, size: int, x: str, y: int) -> str:
    label = label.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")
    return (f"drawtext=text='{label}'{font}:expansion=none:"
            f"fontsize={size}:fontcolor=0xf8fafc:x={x}:y={y}")


def _detail_crop(box: dict) -> tuple[int, int, int, int]:
    """Include the verified result with a margin on even video coordinates."""
    x = max(0, int(box["x"] - 16) // 2 * 2)
    y = max(0, int(box["y"] - 16) // 2 * 2)
    right = min(1440, (int(box["x"] + box["width"] + 17) // 2 + 1) * 2)
    bottom = min(900, (int(box["y"] + box["height"] + 17) // 2 + 1) * 2)
    if right <= x or bottom <= y:
        raise SystemExit("The picture-in-picture detail must be in the recorded viewport")
    return x, y, right - x, bottom - y


def _tour_layout(recordings: list[tuple[dict, dict, Path]], width: int,
                 height: int, font: str) -> tuple[list[str], str]:
    """Compose each shot from its own raw workspace and the verified result."""
    portrait = height > width
    logo_size = 78 if portrait else 54
    logo_x, logo_y = (76, 92) if portrait else (62, 29)
    panel_width = 944 if portrait else 1152
    panel_y = 344 if portrait else 114
    inset_width, inset_height = (876, 674) if portrait else (568, 496)
    inputs: list[str] = []
    filters = []
    for index, (scene, segment, source) in enumerate(recordings):
        inputs.extend(["-i", str(source)])
        start = segment["startFrame"]
        frames = segment["frames"]
        x, y, crop_width, crop_height = _detail_crop(segment["detail"])
        inset_x = "(main_w-overlay_w)/2" if portrait else (
            "62" if x + crop_width / 2 > 720 else "main_w-overlay_w-62"
        )
        inset_y = "(2664-overlay_h)/2" if portrait else "837-overlay_h"
        detail_at = segment["actionEnd"]
        filters += [
            f"[{index}:v]trim=start_frame={start}:end_frame={start + frames},"
            f"setpts=PTS-STARTPTS,split[main{index}][detail{index}]",
            f"[main{index}]scale={panel_width}:-2:flags=lanczos,setsar=1,"
            f"pad={width}:{height}:(ow-iw)/2:{panel_y}:color=0x10192b[base{index}]",
            f"[detail{index}]crop={crop_width}:{crop_height}:{x}:{y},"
            f"scale={min(inset_width, crop_width * 2)}:{min(inset_height, crop_height * 2)}:"
            "force_original_aspect_ratio=decrease:"
            f"force_divisible_by=2:flags=lanczos,setsar=1,"
            f"pad=iw+8:ih+8:4:4:color=0x8db9ff[inset{index}]",
        ]
        title = _drawtext(scene["title"], font, 65 if portrait else 48,
                          str(logo_x) if portrait else "(w-tw)/2", 216 if portrait else 31)
        composed = [
            f"[base{index}][inset{index}]overlay=x={inset_x}:y={inset_y}:enable='gte(t,{detail_at:.3f})'",
            title,
        ]
        if scene["id"] == "pdf":
            composed.append(_drawtext("Try the demo at lixity.de", font, 47 if portrait else 29,
                                      "(w-tw)/2" if portrait else "w-tw-62", 1730 if portrait else 44))
        filters.append(",".join(composed) + f",format=yuv420p[s{index}]")
    inputs.extend(["-i", str(BASE_DIR / "docs/assets/brand/icon-192.png")])
    name = _drawtext("Lixity", font, 58 if portrait else 39,
                     str(logo_x + logo_size + 14), logo_y + (10 if portrait else 8))
    filters += [
        "".join(f"[s{index}]" for index in range(len(recordings))) +
        f"concat=n={len(recordings)}:v=1:a=0,{name}[branded]",
        f"[{len(recordings)}:v]scale={logo_size}:{logo_size}:flags=lanczos[logo]",
        f"[branded][logo]overlay=x={logo_x}:y={logo_y}[out]",
    ]
    return inputs, ";".join(filters)


def convert_product_tour(selection: str | None = None) -> None:
    """Export the branded minute from verified recordings in both orientations."""
    plan = _tour_plan()
    recordings = _tour_recordings(plan)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    fonts = (
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    )
    font = next((candidate for candidate in fonts if candidate.is_file()), None)
    font_opt = f":fontfile='{font}'" if font else ""
    h264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "25", "-movflags", "+faststart"]
    layouts = []
    if selection in (None, "product-tour"):
        layouts.append((1440, 900, (
            ("product-tour.mp4", h264),
            ("product-tour.webm", ["-c:v", "libaom-av1", "-cpu-used", "6", "-crf", "36",
                                   "-b:v", "0", "-row-mt", "1"]),
        )))
    if selection in (None, "product-tour", "portrait", "social"):
        layouts.append((1080, 1920, ((PORTRAIT_SOCIAL if selection == "social" else PORTRAIT_MASTER, h264),)))
    if selection in (None, "product-tour", "social"):
        layouts.append((1600, 900, ((LANDSCAPE_SOCIAL, h264),)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fps = plan["fps"]
    frames = plan["duration"] * fps
    budgets = {name: limit for name, _, _, limit in SOCIAL_CLIPS}
    with tempfile.TemporaryDirectory(prefix=".tour-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        for width, height, exports in layouts:
            inputs, filters = _tour_layout(recordings, width, height, font_opt)
            for name, codec in exports:
                target = staging / name
                run([ffmpeg, "-y", "-loglevel", "error", "-filter_complex_threads", "2", *inputs,
                     "-filter_complex", filters, "-map", "[out]", "-an", "-map_metadata", "-1",
                     "-frames:v", str(frames), "-r", str(fps), "-fps_mode", "cfr",
                     *codec, "-pix_fmt", "yuv420p", str(target)])
                _verify_export(target, fps=fps, frames=frames, width=width, height=height,
                               max_bytes=budgets.get(name, 4_000_000))
        if (staging / "product-tour.mp4").is_file():
            run([ffmpeg, "-y", "-loglevel", "error", "-ss", "15", "-i", str(staging / "product-tour.mp4"),
                 "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(staging / "product-tour.webp")])
        if (staging / PORTRAIT_MASTER).is_file():
            run([ffmpeg, "-y", "-loglevel", "error", "-ss", "15", "-i", str(staging / PORTRAIT_MASTER),
                 "-frames:v", "1", "-vf", "scale=540:960:flags=lanczos", str(staging / PORTRAIT_POSTER)])
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
