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
import math
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

if __package__:
    from .build_evidence import utc_now, write_build_receipt
    from .product_tour_edit import (
        ICON,
        Edit,
        compose,
        inspect_cut_plan,
        prepare_project_path,
        prune_stale_tour_artifacts,
    )
else:
    from build_evidence import utc_now, write_build_receipt
    from product_tour_edit import (
        ICON,
        Edit,
        compose,
        inspect_cut_plan,
        prepare_project_path,
        prune_stale_tour_artifacts,
    )

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
TOUR_VARIANTS = ("landscape", "portrait", "social-16x9")
CANONICAL_TOUR_MARKERS = {
    "warehouse-4-1440x900-markers.csv",
    "warehouse-4-1080x1920-markers.csv",
    "warehouse-4-1600x900-markers.csv",
}
CANONICAL_TOUR_RECEIPTS = {
    "receipt-product-tour.json",
    "receipt-landscape.json",
    "receipt-portrait.json",
    "receipt-social.json",
    "receipt-social-16x9.json",
}
TOUR_VIDEO_LIMITS = {name: limit for name, _, _, limit in SOCIAL_CLIPS}
DEFAULT_TOUR_VIDEO_LIMIT = 4_000_000
TOUR_VIDEO_FILTER = (
    "scale=in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p,"
    "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=iec61966-2-1,setsar=1"
)
GUIDE_VIDEO_FILTER = (
    "scale='min(iw,1920)':-2:flags=lanczos:out_color_matrix=bt709:out_range=tv,format=yuv420p,"
    "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=iec61966-2-1,setsar=1"
)

#: name, poster timestamp, max MP4 bytes, max GIF bytes
WALKTHROUGHS: tuple[tuple[str, str, int, int], ...] = (
    ("research-timeline", "6.0", 2_000_000, 4_000_000),
    ("analysis-review", "7.6", 2_000_000, 4_000_000),
    ("editorial-loop", "13.4", 2_000_000, 4_000_000),
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
    sidecar = source.with_suffix(".json")
    if not source.is_file() or not sidecar.is_file():
        raise SystemExit(
            f"Missing recording or frame anchor for {name}. "
            f"Run 'python scripts/make_screenshots.py --video --only {name}' first."
        )
    recording = json.loads(sidecar.read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-guide-recording/1" or recording.get("file") != source.name
            or recording.get("sha256") != hashlib.sha256(source.read_bytes()).hexdigest()):
        raise SystemExit(f"The {name} recording does not match its frame anchor. Record it again.")
    video, _ = _video_info(source)
    start = recording.get("startFrame")
    rate = Fraction(video["avg_frame_rate"])
    if rate != 25 or not isinstance(start, int) or not 0 < start < int(video["nb_read_frames"]):
        raise SystemExit(f"The {name} recording has an invalid frame anchor or frame rate.")
    poster_frame = start + math.ceil(Fraction(poster_at) * rate)
    if poster_frame >= int(video["nb_read_frames"]):
        raise SystemExit(f"The {name} recording does not reach its poster timestamp.")

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", str(source)]
    trim = f"trim=start_frame={start},setpts=PTS-STARTPTS"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{name}-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        mp4, gif, poster = (staging / f"{name}.{extension}" for extension in ("mp4", "gif", "png"))
        run([*command, "-vf", f"{trim},{GUIDE_VIDEO_FILTER}", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "19",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)])
        gif_input = f"{trim},fps=10,scale=800:-1:flags=lanczos,split[s0][s1];"
        for palette, dither in (("", "bayer"), (":max_colors=192", "none:diff_mode=rectangle")):
            run([*command, "-an", "-vf", f"{gif_input}[s0]palettegen=stats_mode=diff{palette}[p];"
                 f"[s1][p]paletteuse=dither={dither}", "-loop", "0", str(gif)])
            if gif.stat().st_size <= max_gif:
                break
        run([*command, "-vf", f"trim=start_frame={poster_frame}", "-frames:v", "1", "-update", "1", str(poster)])
        for path, limit in ((mp4, max_mp4), (gif, max_gif)):
            size = path.stat().st_size
            if size > limit:
                raise SystemExit(f"{path.name} is {size:,} bytes; the limit is {limit:,}.")
        for path in (mp4, gif, poster):
            target = path.replace(OUT_DIR / path.name)
            print(f"{target.relative_to(BASE_DIR)} {target.stat().st_size:,} bytes")


def _tour_plan() -> dict:
    """Load the timeline also consumed by the recorder and localized homepages."""
    plan = json.loads(TOUR_TIMING_PATH.read_text(encoding="utf-8"))
    if plan.get("schema_version") != "lixity-product-tour-timing/3":
        raise SystemExit("Unknown product-tour timing schema")
    scenes = plan["scenes"]
    fps = plan["fps"]
    if not isinstance(fps, int) or fps <= 0 or not scenes or len({scene["id"] for scene in scenes}) != len(scenes):
        raise SystemExit("The product tour needs distinct caption cues and a positive integer fps")
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
    if (len({shot["id"] for shot in captures}) != len(captures) or
            any(not 0 < shot["duration"] <= shot["record_duration"] or
                shot["record_duration"] * fps % 1 or shot["duration"] * fps % 1 for shot in captures) or
            sum(shot["duration"] for shot in captures) != scenes[-1]["start"]):
        raise SystemExit("Tour captures must cover the whole-frame timeline before the end card")
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


def _verify_export(path: Path, *, fps: int, frames: int, width: int, height: int) -> None:
    video, media = _video_info(path)
    if (int(video["nb_read_frames"]) != frames or
            Fraction(video["avg_frame_rate"]) != fps or
            (video["width"], video["height"]) != (width, height) or
            video.get("sample_aspect_ratio") != "1:1" or
            abs(float(media["format"]["duration"]) - frames / fps) > .002 or
            len(media["streams"]) != 1):
        raise SystemExit(f"{path.name} has incomplete timing, unexpected geometry or audio")
    if (video.get("color_range"), video.get("color_space"), video.get("color_primaries"),
            video.get("color_transfer")) != ("tv", "bt709", "bt709", "iec61966-2-1"):
        raise SystemExit(f"{path.name} needs the RGB capture's sRGB transfer and explicit video color metadata")
    max_bytes = TOUR_VIDEO_LIMITS.get(path.name, DEFAULT_TOUR_VIDEO_LIMIT)
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


def _tour_recordings(plan: dict) -> tuple[dict, list[tuple[dict, Path, Path]]]:
    recording = json.loads((RAW_DIR / "product-tour.json").read_text(encoding="utf-8"))
    if (recording.get("schema_version") != "lixity-product-tour-recording/5" or
            recording.get("fps") != plan["fps"] or recording.get("duration") != plan["duration"]):
        raise SystemExit("Recording metadata does not match the tour; record the complete tour again")
    segments = recording.get("segments", [])
    if [segment["id"] for segment in segments] != [scene["id"] for scene in plan["captures"]]:
        raise SystemExit("The recording needs one ordered segment per planned camera shot")
    recordings = []
    streams = {}
    for scene, segment in zip(plan["captures"], segments, strict=True):
        filename = segment["file"]
        source = _read_source(filename, segment["sha256"], RAW_DIR)
        if source not in streams:
            streams[source] = _video_info(source)[0]
        video = streams[source]
        start = segment["startFrame"]
        frames = scene["record_duration"] * plan["fps"]
        if (not isinstance(start, int) or start < 0 or segment["frames"] != frames or
                segment.get("theme") != scene["theme"] or
                (video["width"], video["height"]) not in {(1440, 900), (2880, 1800)} or
                Fraction(video["avg_frame_rate"]) != plan["fps"]):
            raise SystemExit(f"{filename} has an invalid frame anchor, theme, geometry, count or fps")
        segment["sourceSize"] = (video["width"], video["height"])
        if int(video["nb_read_frames"]) < start + frames:
            raise SystemExit(f"{filename} needs {start + frames} frames including its anchor; "
                             f"only {video['nb_read_frames']} were recorded")
        if not 0 < segment["actionEnd"] <= scene["duration"] - .5:
            raise SystemExit(f"{filename} leaves too little time to read the outcome")
        still = _read_source(segment["still"], segment["stillSha256"], RAW_DIR)
        recordings.append((segment, source, still))
    return recording, recordings


def _webm_codec(encoders: str) -> list[str]:
    if "libsvtav1" in encoders:
        return ["-c:v", "libsvtav1", "-preset", "6", "-crf", "28"]
    if "libaom-av1" in encoders:
        return ["-c:v", "libaom-av1", "-cpu-used", "6", "-crf", "28", "-b:v", "0", "-row-mt", "1"]
    raise SystemExit("FFmpeg needs an AV1 encoder (libsvtav1 or libaom-av1) for the homepage WebM.")


def _tour_tool_versions(tools: dict[str, tuple[str, str]]) -> dict[str, str]:
    versions = {}
    for name, (executable, flag) in tools.items():
        output = subprocess.check_output([executable, flag], text=True)  # noqa: S603 - version query for selected tools
        versions[name] = output.splitlines()[0]
    return versions


def _print_cut_plan(plan: dict, recordings: list, layouts: list[tuple[int, int, tuple]]) -> None:
    fps = plan["fps"]
    for width, height, _ in layouts:
        rows = inspect_cut_plan(plan, recordings, width=width, height=height, fps=fps)
        print(f"=== Cut plan: warehouse-4-{width}x{height} ({len(rows)} cuts, {plan['duration']}s @ {fps}fps) ===")
        for row in rows:
            cw, ch = row["css_crop"]
            flags = []
            if row["inset"]:
                flags.append("inset")
            if row["comparison"]:
                flags.append("compare")
            flag_text = f" [{','.join(flags)}]" if flags else ""
            print(
                f"  {row['shot']:8s}[{row['cut']}] {row['start_s']:5.2f}-{row['end_s']:5.2f}s "
                f"({row['frames']:3d}f, src={row['source_frame']:4d}, hold={row['hold_frames']}f) "
                f"crop={cw:4d}x{ch:<3d} css={row['css_scale']:.2f}x phys={row['physical_scale']:.2f}x{flag_text}"
            )


def convert_product_tour(
    selection: str | None = None,
    *,
    variant: str | None = None,
    inspect_cuts: bool = False,
    keep_projects: bool = True,
) -> None:
    """Encode the editable FilmCraft cut once per destination codec."""
    plan = _tour_plan()
    recording, recordings = _tour_recordings(plan)
    effective_selection = variant or selection or "product-tour"
    want_landscape = (variant == "landscape") if variant else selection in (None, "product-tour")
    want_portrait = (variant == "portrait") if variant else True
    want_social_16x9 = (variant == "social-16x9") if variant else selection in (None, "product-tour", "social")

    if inspect_cuts:
        preview_layouts: list[tuple[int, int, tuple]] = []
        if want_landscape:
            preview_layouts.append((1440, 900, ()))
        if want_portrait:
            preview_layouts.append((1080, 1920, ()))
        if want_social_16x9:
            preview_layouts.append((1600, 900, ()))
        _print_cut_plan(plan, recordings, preview_layouts)
        return

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to publish walkthrough videos.")
    cwebp = shutil.which("cwebp")
    h264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "19", "-movflags", "+faststart"]
    layouts = []
    if want_landscape:
        encoders = subprocess.check_output([ffmpeg, "-hide_banner", "-encoders"], text=True)  # noqa: S603
        if cwebp is None and "libwebp" not in encoders:
            raise SystemExit("The landscape poster needs cwebp or FFmpeg with libwebp.")
        layouts.append((1440, 900, (
            ("product-tour.mp4", h264),
            ("product-tour.webm", _webm_codec(encoders)),
        )))
    if want_portrait:
        layouts.append((1080, 1920, ((PORTRAIT_MASTER, h264),)))
    if want_social_16x9:
        layouts.append((1600, 900, ((LANDSCAPE_SOCIAL, h264),)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fps = plan["fps"]
    frames = plan["duration"] * fps
    review = BASE_DIR / ".artifacts" / "filmcraft" / "warehouse-4-tour"
    review.mkdir(parents=True, exist_ok=True)
    filmcraft = shutil.which("filmcraft-cli")
    ffprobe = shutil.which("ffprobe")
    if filmcraft is None or ffprobe is None:
        raise SystemExit(
            "FilmCraft CLI (filmcraft-cli) and ffprobe are required to build the product tour. "
            "Check PATH and see docs/videos/README.md."
        )
    tools = {"filmcraft": (filmcraft, "--version"), "ffmpeg": (ffmpeg, "-version"), "ffprobe": (ffprobe, "-version")}
    if cwebp and want_landscape:
        tools["cwebp"] = (cwebp, "-version")
    versions = _tour_tool_versions(tools)
    script = Path(__file__).resolve()
    inputs = (
        TOUR_TIMING_PATH, RAW_DIR / "product-tour.json", script, script.with_name("product_tour_edit.py"),
        script.with_name("product_tour_capture.cjs"),
        BASE_DIR / ICON,
    )
    input_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}

    def encode(width: int, height: int, exports: tuple, staging: Path) -> tuple[dict[str, list[int]], Path, Path]:
        stem = f"warehouse-4-{width}x{height}"
        project = prepare_project_path(review, width, height)
        edit = Edit(project, width, height, fps)
        compose(edit, BASE_DIR, plan, recordings)
        markers = review / f"{stem}-markers.csv"
        edit.export_markers(markers, plan)
        with tempfile.TemporaryDirectory(prefix="frames-", dir=review) as temp:
            sequence = edit.render(Path(temp), duration=plan["duration"])
            for name, codec in exports:
                target = staging / name
                run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(sequence),
                     "-vf", TOUR_VIDEO_FILTER, "-an", "-map_metadata", "-1",
                     "-frames:v", str(frames), "-r", str(fps), "-fps_mode", "cfr",
                     *codec, "-pix_fmt", "yuv420p", str(target)])
                _verify_export(target, fps=fps, frames=frames, width=width, height=height)
            poster = sequence.with_name(sequence.name % (2 * fps))
            if width == 1440:
                target = staging / "product-tour.webp"
                if cwebp:
                    run([cwebp, "-quiet", "-q", "85", str(poster), "-o", str(target)])
                else:
                    run([ffmpeg, "-y", "-loglevel", "error", "-i", str(poster),
                         "-frames:v", "1", "-c:v", "libwebp", "-quality", "85", str(target)])
            if width == 1080:
                run([ffmpeg, "-y", "-loglevel", "error", "-i", str(poster),
                     "-frames:v", "1", str(staging / PORTRAIT_POSTER)])
        return {name: edit.review_frames for name, _ in exports}, markers, project

    with tempfile.TemporaryDirectory(prefix=".tour-", dir=OUT_DIR) as pending:
        staging = Path(pending)
        review_frames = {}
        marker_reports = {}
        built_projects: list[Path] = []
        with ThreadPoolExecutor(max_workers=min(3, len(layouts))) as pool:
            futures = [pool.submit(encode, width, height, exports, staging) for width, height, exports in layouts]
            for future in futures:
                samples, markers, project = future.result()
                review_frames.update(samples)
                marker_reports[markers.name] = hashlib.sha256(markers.read_bytes()).hexdigest()
                built_projects.append(project)
        if want_portrait:
            shutil.copyfile(staging / PORTRAIT_MASTER, staging / PORTRAIT_SOCIAL)
            review_frames[PORTRAIT_SOCIAL] = review_frames[PORTRAIT_MASTER]
        targets = sorted(staging.iterdir())
        outputs = {target.name: hashlib.sha256(target.read_bytes()).hexdigest() for target in targets}
        for target in targets:
            target.replace(OUT_DIR / target.name)
        receipt_name = f"receipt-{effective_selection}.json"
        write_build_receipt(review / receipt_name, {
            "schema_version": "lixity-product-tour-build/1",
            "built_at": utc_now(),
            "selection": effective_selection,
            "tools": versions,
            "inputs_sha256": input_hashes,
            "recording_sha256": {
                name: digest
                for segment in recording["segments"]
                for name, digest in ((segment["file"], segment["sha256"]), (segment["still"], segment["stillSha256"]))
            },
            "encoders": {name: codec for _, _, exports in layouts for name, codec in exports},
            "outputs_sha256": outputs,
            "review_frames": review_frames,
            "filmcraft_marker_reports_sha256": marker_reports,
        })
        full_tour = effective_selection == "product-tour"
        prune_stale_tour_artifacts(
            review,
            keep_receipts={receipt_name} if full_tour else CANONICAL_TOUR_RECEIPTS,
            keep_markers=set(marker_reports) if full_tour else CANONICAL_TOUR_MARKERS,
        )
        if not keep_projects:
            for project in built_projects:
                if project.exists():
                    project.unlink()
                cuts_dir = project.with_name(f"{project.stem}-cuts")
                if cuts_dir.is_dir():
                    shutil.rmtree(cuts_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["product-tour", "portrait", "social", *(item[0] for item in WALKTHROUGHS)])
    parser.add_argument(
        "--variant",
        choices=TOUR_VARIANTS,
        help="Build or inspect a single product-tour variant (landscape, portrait, or social-16x9).",
    )
    parser.add_argument(
        "--inspect-cuts",
        action="store_true",
        help="Dry-run: print cut timing and crop-scale geometry for the selected product-tour variant(s) without rendering.",
    )
    parser.add_argument(
        "--keep-projects",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep editable FilmCraft .fcproj files and *-cuts samples under .artifacts/filmcraft/warehouse-4-tour/ (default: true).",
    )
    args = parser.parse_args()
    walkthrough_names = {item[0] for item in WALKTHROUGHS}
    if (args.variant or args.inspect_cuts) and args.only in walkthrough_names:
        parser.error("--variant and --inspect-cuts apply only to product-tour builds")
    if args.inspect_cuts:
        convert_product_tour(args.only, variant=args.variant, inspect_cuts=True, keep_projects=args.keep_projects)
        return 0
    jobs = []
    if args.variant or args.only in (None, "product-tour", "portrait", "social"):
        jobs.append((convert_product_tour, (args.only,), {"variant": args.variant, "keep_projects": args.keep_projects}))
    if not args.variant:
        for name, poster_at, max_mp4, max_gif in WALKTHROUGHS:
            if args.only in (None, name):
                jobs.append((convert, (name, poster_at, max_mp4, max_gif), {}))
    workers = min(len(jobs), max(1, min(4, os.cpu_count() or 2)))
    if workers <= 1:
        for fn, fn_args, fn_kwargs in jobs:
            fn(*fn_args, **fn_kwargs)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(fn, *fn_args, **fn_kwargs) for fn, fn_args, fn_kwargs in jobs]
            for future in futures:
                future.result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
