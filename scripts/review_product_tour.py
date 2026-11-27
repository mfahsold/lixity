"""Generate local contact sheets from exact frames of the encoded product tour."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__:
    from .make_videos import (
        BASE_DIR,
        LANDSCAPE_SOCIAL,
        OUT_DIR,
        PORTRAIT_MASTER,
        PORTRAIT_SOCIAL,
        TOUR_TIMING_PATH,
        _tour_plan,
        _verify_export,
    )
else:
    from make_videos import (
        BASE_DIR,
        LANDSCAPE_SOCIAL,
        OUT_DIR,
        PORTRAIT_MASTER,
        PORTRAIT_SOCIAL,
        TOUR_TIMING_PATH,
        _tour_plan,
        _verify_export,
    )

TOUR = BASE_DIR / ".artifacts" / "filmcraft" / "warehouse-4-tour"
OUTPUT = TOUR / "layout-review" / "final"
FRAME_NAME = re.compile(r"frame-(\d+)\.png")
SHEET_NAME = re.compile(r"sheet-\d+\.png")
SHEET_COLUMNS = 3
SHEET_ROWS = 2


@dataclass(frozen=True)
class Layout:
    asset: str
    width: int
    height: int
    preview_width: int

    @property
    def name(self) -> str:
        return f"{self.width}x{self.height}"


LAYOUTS = {
    "portrait": Layout(PORTRAIT_MASTER, 1080, 1920, 360),
    "landscape": Layout("product-tour.mp4", 1440, 900, 540),
    "social": Layout(LANDSCAPE_SOCIAL, 1600, 900, 540),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipts() -> list[tuple[Path, dict]]:
    receipts = []
    for path in TOUR.glob("receipt-*.json"):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("schema_version") == "lixity-product-tour-build/1":
            receipts.append((path, receipt))
    return sorted(receipts, key=lambda item: (item[1]["built_at"], item[0].stat().st_mtime_ns), reverse=True)


def _review_frames(layout: Layout, receipt: dict, required: set[int], total: int) -> tuple[list[int], str]:
    if "review_frames" in receipt:
        frames = receipt["review_frames"].get(layout.asset)
        source = "Frame indices recorded in the matching build receipt."
    else:
        cuts = TOUR / f"warehouse-4-{layout.name}-cuts"
        if not cuts.is_dir():
            raise ValueError(f"Missing FilmCraft review samples for {layout.asset}. Rebuild this tour variant.")
        frames = sorted(int(match[1]) for path in cuts.iterdir() if (match := FRAME_NAME.fullmatch(path.name)))
        source = "Local FilmCraft cut samples. The older build receipt does not record their indices."
    if (not isinstance(frames, list) or not frames or any(type(frame) is not int for frame in frames)
            or frames != sorted(set(frames)) or frames[0] != 0 or frames[-1] != total - 1
            or not required.issubset(frames)):
        raise ValueError(f"Review samples for {layout.asset} must include the first and last frames and both sides of each scene cut.")
    return frames, source


def _run_ffmpeg(ffmpeg: str, arguments: list[str]) -> None:
    subprocess.run([ffmpeg, "-v", "error", *arguments], check=True)  # noqa: S603 - selected FFmpeg, fixed options


def _decode(ffmpeg: str, video: Path, frames: list[int], width: int, work: Path) -> list[Path]:
    # Adjacent transition samples form one range, keeping the FFmpeg expression shallow.
    ranges: list[tuple[int, int]] = []
    for frame in frames:
        if ranges and frame == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], frame)
        else:
            ranges.append((frame, frame))
    select = "+".join(f"eq(n,{start})" if start == end else f"between(n,{start},{end})" for start, end in ranges)
    _run_ffmpeg(ffmpeg, [
        "-i", str(video), "-vf", f"select='{select}',scale={width}:-2:flags=lanczos",
        "-fps_mode", "passthrough", "-an", "-threads", "1", "-start_number", "0",
        str(work / "decoded-%04d.png"),
    ])
    decoded = sorted(work.glob("decoded-*.png"))
    if len(decoded) != len(frames):
        raise ValueError(f"Requested {len(frames)} frames from {video.name}, decoded {len(decoded)}")
    return [path.rename(work / f"frame-{frame:04d}.png") for frame, path in zip(frames, decoded, strict=True)]


def _contact_sheet(ffmpeg: str, images: list[Path], destination: Path) -> None:
    playlist = destination.with_suffix(".ffconcat")
    playlist.write_text(
        "ffconcat version 1.0\n" + "".join(f"file {image.name}\n" for image in images),
        encoding="utf-8",
    )
    _run_ffmpeg(ffmpeg, [
        "-f", "concat", "-i", str(playlist),
        "-vf", f"tile={SHEET_COLUMNS}x{SHEET_ROWS}:nb_frames={len(images)}:padding=4:margin=4:color=0x909090",
        "-frames:v", "1", "-threads", "1", str(destination),
    ])


def _build(ffmpeg: str, layout: Layout, receipts: list[tuple[Path, dict]], plan: dict) -> None:
    video = OUT_DIR / layout.asset
    digest = _sha256(video)
    latest = next(((path, record) for path, record in receipts if layout.asset in record["outputs_sha256"]), None)
    if latest is None:
        raise ValueError(
            f"No local build receipt for {video.name}. For a visual check of the current export, "
            "use the direct FFmpeg spot check in docs/videos/README.md."
        )
    receipt_path, receipt = latest
    if receipt["outputs_sha256"][layout.asset] != digest:
        raise ValueError(f"{video.name} differs from {receipt_path.name}. Rebuild this tour variant first.")
    if receipt["inputs_sha256"].get(TOUR_TIMING_PATH.name) != _sha256(TOUR_TIMING_PATH):
        raise ValueError(f"Tour timing changed after {receipt_path.name}. Rebuild this tour variant first.")
    portrait_alias = layout.asset == PORTRAIT_MASTER
    if portrait_alias and _sha256(OUT_DIR / PORTRAIT_SOCIAL) != digest:
        raise ValueError("The website and social portrait files differ. Rebuild this tour variant first.")

    fps = plan["fps"]
    total = plan["duration"] * fps
    boundaries = {index for scene in plan["scenes"] for index in (scene["start"] * fps - 1, scene["start"] * fps)
                  if index >= 0}
    frames, source = _review_frames(layout, receipt, boundaries, total)
    _verify_export(video, fps=fps, frames=total, width=layout.width, height=layout.height)

    destination = OUTPUT / layout.name
    destination.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="review-", dir=destination) as temporary:
        work = Path(temporary)
        images = _decode(ffmpeg, video, frames, layout.preview_width, work)
        index = [
            f"# {video.name} encoded frame review", "",
            f"Export `{video.relative_to(BASE_DIR)}`", "",
            f"Build receipt `{receipt_path.name}`", "", source, "",
            f"SHA-256 `{digest}`", "",
            f"{layout.width} x {layout.height} at {fps} fps, sampled at {layout.preview_width} px wide", "",
            f"{len(images)} samples in zero-based display order. Read each sheet left to right and top to bottom.", "",
        ]
        if portrait_alias:
            index.extend([f"The same bytes ship as `{PORTRAIT_SOCIAL}`.", ""])
        sheets = []
        page_size = SHEET_COLUMNS * SHEET_ROWS
        for offset in range(0, len(images), page_size):
            samples = images[offset:offset + page_size]
            sheet = work / f"sheet-{1 + offset // page_size:02d}.png"
            _contact_sheet(ffmpeg, samples, sheet)
            sheets.append(sheet)
            index.extend([f"## [{sheet.name}]({sheet.name})", ""])
            index.extend(f"- [{path.stem}]({path.name}) at {frame / fps:.3f} s"
                         for frame, path in zip(frames[offset:offset + page_size], samples, strict=True))
            index.append("")
        if _sha256(video) != digest:
            raise ValueError(f"{video.name} changed during review. Rerun after encoding finishes.")
        report = work / "index.md"
        report.write_text("\n".join(index), encoding="utf-8")
        outputs = [*images, *sheets, report]
        keep = {path.name for path in outputs}
        for path in outputs:
            path.replace(destination / path.name)
        for path in destination.iterdir():
            if path.name not in keep and (FRAME_NAME.fullmatch(path.name) or SHEET_NAME.fullmatch(path.name)):
                path.unlink()
    print(f"{layout.name} · {len(images)} decoded samples · {(destination / 'index.md').relative_to(BASE_DIR)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=LAYOUTS, help="Review one deliverable format")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        parser.error("FFmpeg is required to extract the encoded frames")
    try:
        plan = _tour_plan()
        receipts = _receipts()
        for name in [args.only] if args.only else LAYOUTS:
            _build(ffmpeg, LAYOUTS[name], receipts, plan)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
