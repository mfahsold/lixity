"""Encode recorded guide walkthroughs, the homepage tour and social clips.

Recordings come from ``scripts/make_screenshots.py --video`` (Playwright WebM in
``.artifacts/screenshots/videos/``). The guide outputs use MP4, GIF and PNG.
The homepage tour uses landscape MP4 and WebM and a portrait MP4. The validated
landscape MP4 is the input for both social clips. See ``docs/videos/README.md``
for encoding prerequisites and review steps.
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
SOCIAL_CLIPS = (
    ("social-hook-16x9.mp4", 1600, 900, 3_500_000),
    ("social-hook-9x16.mp4", 1080, 1920, 4_000_000),
)
PORTRAIT_MASTER = "product-tour-portrait.mp4"
PORTRAIT_POSTER = "product-tour-portrait.png"
#: Portrait crop windows per scene (x offset in the 1440-wide source, 506 px
#: wide -> 1080 out). Passage keeps the evidence detail (x=874..1248) in frame.
PORTRAIT_WINDOWS = {
    "read": 467,
    "passage": 800,
    "compare": 528,
    "chapters": 302,
    "dossier": 300,
    "pdf": 300,
}

#: name, poster timestamp, max MP4 bytes, max GIF bytes
WALKTHROUGHS: tuple[tuple[str, str, int, int], ...] = (
    ("research-timeline", "6.0", 2_000_000, 4_000_000),
    ("analysis-review", "5.5", 2_000_000, 4_000_000),
    ("editorial-loop", "11.5", 2_000_000, 4_000_000),
)
PUBLIC_VIDEO_FILES = {
    "README.md", "product-tour.mp4", "product-tour.webm", "product-tour.webp",
    PORTRAIT_MASTER, PORTRAIT_POSTER,
    *(name for name, _, _, _ in SOCIAL_CLIPS),
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
    if plan.get("schema_version") != "lixity-product-tour-timing/1":
        raise SystemExit("Unknown product-tour timing schema")
    scenes = plan["scenes"]
    fps = plan["fps"]
    if not isinstance(fps, int) or fps <= 0 or len(scenes) != 6 or len({scene["id"] for scene in scenes}) != len(scenes):
        raise SystemExit("The product tour needs six ordered scenes and a positive integer fps")
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


def convert_product_tour() -> None:
    """Join six frame-anchored scenes without setup footage or camera effects."""
    plan = _tour_plan()
    recording = json.loads((RAW_DIR / "product-tour.json").read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-product-tour-recording/1" or
            recording.get("fps") != plan["fps"] or recording.get("duration") != plan["duration"]):
        raise SystemExit("Recording metadata does not match the product-tour timing plan")
    segments = recording.get("segments", [])
    if [segment["id"] for segment in segments] != [scene["id"] for scene in plan["scenes"]]:
        raise SystemExit("The recording needs one ordered segment per tour scene")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    inputs: list[str] = []
    filters: list[str] = []
    for index, (scene, segment) in enumerate(zip(plan["scenes"], segments, strict=True)):
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
                Fraction(video["avg_frame_rate"]) != plan["fps"]):
            raise SystemExit(f"{filename} has an invalid frame anchor, count or recording fps")
        if int(video["nb_read_frames"]) < start + frames:
            raise SystemExit(f"{filename} needs {start + frames} frames including its anchor; "
                             f"only {video['nb_read_frames']} were recorded")
        inputs.extend(["-i", str(source)])
        filters.append(
            f"[{index}:v]trim=start_frame={start}:end_frame={start + frames},"
            f"setpts=PTS-STARTPTS,scale=1440:900:flags=lanczos,setsar=1,"
            f"format=yuv420p[s{index}]"
        )
    filters.append("".join(f"[s{index}]" for index in range(len(segments))) +
                   f"concat=n={len(segments)}:v=1:a=0[out]")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = plan["duration"] * plan["fps"]
    with tempfile.TemporaryDirectory(prefix=".tour-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        for suffix, codec in (
            ("mp4", ["-c:v", "libx264", "-preset", "slow", "-crf", "25", "-movflags", "+faststart"]),
            ("webm", ["-c:v", "libaom-av1", "-cpu-used", "6", "-crf", "36", "-b:v", "0", "-row-mt", "1"]),
        ):
            target = staging / f"product-tour.{suffix}"
            run([ffmpeg, "-y", "-loglevel", "error", *inputs,
                 "-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-map_metadata", "-1",
                 "-frames:v", str(frames), "-r", str(plan["fps"]), "-fps_mode", "cfr",
                 *codec, "-pix_fmt", "yuv420p", str(target)])
            _verify_export(target, fps=plan["fps"], frames=frames, width=1440, height=900)
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", "3", "-i", str(staging / "product-tour.mp4"),
             "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(staging / "product-tour.webp")])
        for target in staging.iterdir():
            target.replace(OUT_DIR / target.name)


def convert_product_portrait() -> None:
    """Reframe the six landscape tour segments to a 1080x1920 master.

    Single generation from the camera raws (no crop of the published master):
    each 8 s scene keeps its action window (see PORTRAIT_WINDOWS), scaled with
    lanczos to phone width. Silent, no burned captions; the homepage transcript
    stays localized. The camera windows follow the reviewed scene content.
    """
    plan = _tour_plan()
    recording = json.loads((RAW_DIR / "product-tour.json").read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-product-tour-recording/1" or
            recording.get("fps") != plan["fps"] or recording.get("duration") != plan["duration"]):
        raise SystemExit("Recording metadata does not match the product-tour timing plan")
    segments = recording.get("segments", [])
    if [segment["id"] for segment in segments] != [scene["id"] for scene in plan["scenes"]]:
        raise SystemExit("The recording needs one ordered segment per tour scene")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    inputs: list[str] = []
    filters: list[str] = []
    for index, (scene, segment) in enumerate(zip(plan["scenes"], segments, strict=True)):
        filename = segment["file"]
        if Path(filename).name != filename:
            raise SystemExit("Tour segment filenames must stay in the raw recordings directory")
        source = RAW_DIR / filename
        if not source.is_file():
            raise SystemExit(f"Missing video: {source}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != segment.get("sha256"):
            raise SystemExit(f"{filename}: source hash mismatch; record the complete tour again")
        video, _ = _video_info(source)
        if (video["width"], video["height"]) != (1440, 900):
            raise SystemExit(f"{filename}: portrait windows require a 1440x900 recording")
        start = segment["startFrame"]
        frames = (scene["end"] - scene["start"]) * plan["fps"]
        if (not isinstance(start, int) or start < 0 or segment["frames"] != frames or
                Fraction(video["avg_frame_rate"]) != plan["fps"]):
            raise SystemExit(f"{filename} has an invalid frame anchor, count or recording fps")
        if int(video["nb_read_frames"]) < start + frames:
            raise SystemExit(f"{filename} needs {start + frames} frames including its anchor; "
                             f"only {video['nb_read_frames']} were recorded")
        x = PORTRAIT_WINDOWS[scene["id"]]
        if not 0 <= x <= 1440 - 506:
            raise SystemExit(f"Portrait window out of frame for scene {scene['id']}")
        inputs.extend(["-i", str(source)])
        filters.append(
            f"[{index}:v]trim=start_frame={start}:end_frame={start + frames},"
            f"setpts=PTS-STARTPTS,crop=506:900:{x}:0,"
            f"scale=1080:1920:flags=lanczos,setsar=1,"
            f"format=yuv420p[s{index}]"
        )
    filters.append("".join(f"[s{index}]" for index in range(len(segments))) +
                   f"concat=n={len(segments)}:v=1:a=0[out]")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = plan["duration"] * plan["fps"]
    with tempfile.TemporaryDirectory(prefix=".tour-portrait-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        target = staging / PORTRAIT_MASTER
        run([ffmpeg, "-y", "-loglevel", "error", *inputs,
             "-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-map_metadata", "-1",
             "-frames:v", str(frames), "-r", str(plan["fps"]), "-fps_mode", "cfr",
             "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(target)])
        _verify_export(target, fps=plan["fps"], frames=frames, width=1080, height=1920)
        run([ffmpeg, "-y", "-loglevel", "error", "-ss", "10", "-i", str(target),
             "-frames:v", "1", "-vf", "scale=540:960:flags=lanczos",
             str(staging / PORTRAIT_POSTER)])
        for target in staging.iterdir():
            target.replace(OUT_DIR / target.name)


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def convert_social_cuts() -> None:
    """Show one sticky-sentence explanation from the validated tour."""
    plan = _tour_plan()
    source = OUT_DIR / "product-tour.mp4"
    fps = plan["fps"]
    _verify_export(source, fps=fps, frames=plan["duration"] * fps,
                   width=1440, height=900)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish social clips.")
    font = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_opt = f":fontfile={font}" if Path(font).is_file() else ""
    scene = next(scene for scene in plan["scenes"] if scene["id"] == "passage")
    duration = scene["end"] - scene["start"]
    reading_hold = 4
    frames = (duration + reading_hold) * fps
    detail = plan["social_detail"]
    x, y, detail_width, detail_height = (detail[key] for key in ("x", "y", "width", "height"))
    if not (0 <= x < x + detail_width <= 1440 and 0 <= y < y + detail_height <= 900):
        raise SystemExit("The picture-in-picture detail must fit inside the tour recording")
    for name, width, height, max_bytes in SOCIAL_CLIPS:
        portrait = height > width
        shot = [
            f"trim=start_frame={scene['start'] * fps}:end_frame={scene['end'] * fps}",
            "setpts=PTS-STARTPTS",
            f"tpad=stop_mode=clone:stop_duration={reading_hold}",
        ]
        layout = []
        if portrait:
            layout.extend(("crop=1120:ih:320:0", "scale=1080:-2:flags=lanczos", "setsar=1"))
        frame_y = "310" if portrait else "(oh-ih)/2"
        layout.append(f"pad={width}:{height}:(ow-iw)/2:{frame_y}:color=0x0d1322")
        inset_width = 518 if portrait else 424
        inset_x = "(main_w-overlay_w)/2" if portrait else "80"
        inset_y = 1100 if portrait else 175
        detail_filters = (
            f"crop={detail_width}:{detail_height}:{x}:{y},"
            f"scale={inset_width}:-2:flags=lanczos,setsar=1,"
            "pad=iw+8:ih+8:4:4:color=0x93c5fd"
        )
        filters = [
            f"[0:v]{','.join(shot)},split[context][detail]",
            f"[context]{','.join(layout)}[base]",
            f"[detail]{detail_filters}[inset]",
        ]
        composed = [
            f"[base][inset]overlay=x={inset_x}:y={inset_y}:enable='gte(t,{duration / 2:g})'",
        ]
        if portrait:
            composed.append(
                f"drawtext=text='LIXITY'{font_opt}:fontsize=30:fontcolor=0x93c5fd:"
                "x=(w-text_w)/2:y=126"
            )
        caption_y = "198" if portrait else "h-text_h-36"
        caption_size = 54 if portrait else 32
        captions = (
            ("Why is this sentence underlined?", f"lt(t,{duration / 2:g})"),
            ("See the words Lixity counted.", f"between(t,{duration / 2:g},{duration - 1 / fps:g})"),
            ("Try it on the Lixity demo.", f"gte(t,{duration})"),
        )
        for text, interval in captions:
            composed.append(
                f"drawtext=text='{_escape_drawtext(text)}'{font_opt}:expansion=none:"
                f"fontsize={caption_size}:fontcolor=white:box=1:boxcolor=0x0d1322@0.94:"
                f"boxborderw=14:x=(w-text_w)/2:y={caption_y}:enable='{interval}'"
            )
        filters.append(",".join(composed) + "[out]")
        with tempfile.TemporaryDirectory(prefix=".clip-", dir=OUT_DIR) as pending:
            target = Path(pending) / name
            run([ffmpeg, "-y", "-loglevel", "error", "-i", str(source),
                 "-filter_complex", ";".join(filters), "-map", "[out]", "-an", "-map_metadata", "-1",
                 "-frames:v", str(frames), "-r", str(fps), "-fps_mode", "cfr",
                 "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(target)])
            _verify_export(target, fps=fps, frames=frames, width=width, height=height,
                           max_bytes=max_bytes)
            target.replace(OUT_DIR / name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["product-tour", "portrait", "social", *(item[0] for item in WALKTHROUGHS)])
    args = parser.parse_args()
    jobs = []
    if args.only in (None, "product-tour"):
        jobs.append((convert_product_tour, ()))
    if args.only in (None, "product-tour", "portrait"):
        jobs.append((convert_product_portrait, ()))
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
    # Social clips consume the final tour, so they must follow its successful export.
    if args.only in (None, "product-tour", "social"):
        convert_social_cuts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
