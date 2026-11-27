"""Build the editable FilmCraft cut from verified Warehouse 4 recordings."""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TICKS = 254_016_000_000
INK = "#18283D"
PAPER = "#FAF4E7"
GOLD = "#D5BB89"
LILAC = "#F1EEF7"
VIOLET = "#593E79"
ICON = "docs/assets/brand/icon-192.png"
TEXT_SCALE = 0.85
LOGO_SCALE = 0.85
#: Safe content zones for critical on-frame text (brand bug exempt).
#: Landscape 1440x900: title-safe 90-810 (player controls below ~820).
#: Portrait 1080x1920: title-safe 384-1536, platform strict 384-1248
#: (top 15% / bottom 35% free for TikTok/Reels/Shorts overlays).
LANDSCAPE_SAFE_Y = (90.0, 810.0)
PORTRAIT_SAFE_Y = (384.0, 1248.0)


def _type_size(value: int) -> int:
    """Shrink on-frame type while keeping FilmCraft point sizes as integers."""
    return max(1, round(value * TEXT_SCALE))


@dataclass(frozen=True)
class Source:
    item: int
    width: int
    height: int


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        return struct.unpack(">II", source.read(24)[16:24])


class Edit:
    """Keep the title, picture and logo independently editable in FilmCraft."""

    def __init__(self, path: Path, width: int, height: int, fps: int) -> None:
        cli = shutil.which("filmcraft-cli")
        if cli is None:
            raise SystemExit("FilmCraft CLI 0.20.1 or newer is required to build the product tour.")
        self.cli = cli
        self.path = path
        self.width, self.height = width, height
        self.port = width < height
        self.left = 72 if self.port else 76
        self.fps = fps
        self.command("file.newSequence", {"name": f"Warehouse 4 | {width}x{height}",
                                         "width": width, "height": height, "fps": fps,
                                         "video": 6 if self.port else 5, "audio": 0}, first=True)

    def command(self, name: str, params: dict[str, Any], *, first: bool = False) -> Any:
        project = ["--save-as", str(self.path)] if first else ["--project", str(self.path), "--save"]
        result = subprocess.check_output(  # noqa: S603 - fixed FilmCraft invocation
            [self.cli, *project, "exec", name, json.dumps(params)], text=True,
        )
        return json.loads(result)

    def import_sources(self, paths: list[Path], sizes: list[tuple[int, int]]) -> list[Source]:
        items = self.command("file.import", {"paths": [str(path) for path in paths]})
        if items["errors"]:
            raise SystemExit(f"FilmCraft could not import tour sources: {items['errors']}")
        return [Source(item, *size) for item, size in zip(items["items"], sizes, strict=True)]

    def background(self, start: int, end: int, color: str) -> None:
        rectangle = self.command("graphics.newRectangle", {
            "position": [self.width / 2, self.height / 2], "size": [self.width, self.height],
            "track": 0, "time": start * TICKS, "seconds": end - start,
        })
        self.command("graphics.set", {**rectangle, "props": {"fill_color": color, "stroke": False}})

    def text(self, start: float, end: float, label: str, x: float, y: float, size: int,
             color: str, *, serif: bool = False, clip: int | None = None,
             check_safe: bool = True, track: int = 3) -> int:
        size = _type_size(size)
        if check_safe:
            low, high = PORTRAIT_SAFE_Y if self.port else LANDSCAPE_SAFE_Y
            if not (low <= y <= high):
                raise SystemExit(
                    f"On-frame text '{label[:24]}' at y={y} leaves the safe zone "
                    f"{low:.0f}-{high:.0f} ({'portrait' if self.port else 'landscape'})"
                )
        params = {"text": label, "position": [x, y], "size": size,
                  "font": "Georgia" if serif else "Inter",
                  "fontStyle": "Regular" if serif else "SemiBold"}
        if clip is None:
            params.update({"track": track, "time": round(start * TICKS), "seconds": end - start})
        else:
            params["clip"] = clip
        layer = self.command("graphics.newText", params)
        self.command("graphics.set", {**layer, "props": {"fill_color": color}})
        return int(layer["clip"])

    def heading(self, start: int, end: int, kicker: str, title: str, *, background: str = INK,
                serif: bool = False, poster: bool = False) -> int:
        """Reserve a fixed brand axis and enough air for the story and the image."""
        self.background(start, end, background)
        warm = background == INK
        foreground, accent = (PAPER, GOLD) if warm else (INK, VIOLET)
        wordmark = self.text(start, end, "Lixity", self.left + (72 if self.port else 50),
                             207 if self.port else 93, 42 if self.port else 32, foreground,
                             check_safe=False)
        self.text(start, end, kicker, self.left, 390 if self.port else 190 if poster else 160,
                  33 if self.port else 25, accent, clip=wordmark)
        if title:
            self.text(start, end, title, self.left - int(serif) * 3,
                      492 if self.port else 283 if poster else 224,
                      (96 if serif else 64) if self.port else (68 if serif else 50),
                      foreground, serif=serif, clip=wordmark)
        return wordmark

    def parameter(self, clip: int, effect: int | str, name: str, value: Any) -> None:
        self.command("effects.setParam", {"clip": clip, "effect": effect, "param": name, "value": value})

    def picture(self, source: Source, start_frame: int, end_frame: int,
                box: tuple[float, float, float, float], *,
                crop: tuple[float, float, float, float] | None = None, track: str = "V2",
                source_frame: int = 0, align_top: bool = False) -> None:
        """Fit the selected area without stretching the recording."""
        x, y, across, down = crop or (0, 0, source.width, source.height)
        x, y = max(0, x), max(0, y)
        across, down = min(source.width - x, across), min(source.height - y, down)
        if across <= 0 or down <= 0:
            raise SystemExit("The tour edit requested a crop outside its source image")
        cx, cy, width, height = box
        inset = self.width * .06 if self.port else 24
        available = min(width, 2 * (min(cx, self.width - cx) - inset))
        if available <= 0 or height <= 0:
            raise SystemExit("The tour edit requested a picture outside its safe frame")
        scale = min(available / across, height / down) * 100
        if align_top:
            cy += down * scale / 200
        placed = self.command("timeline.place", {
            "item": source.item, "track": track, "frame": start_frame,
            "duration": {"frame": end_frame - start_frame},
            "sourceIn": {"frame": source_frame}, "audio": False,
        })
        clip = placed["clips"][0]
        if crop is not None:
            effect = self.command("effects.apply", {"clips": [clip], "effect": "crop"})["applied"][0]["index"]
            edges = {"left": x / source.width, "right": 1 - (x + across) / source.width,
                     "top": y / source.height, "bottom": 1 - (y + down) / source.height}
            for key, fraction in edges.items():
                self.parameter(clip, effect, key, max(0, fraction) * 100)
        self.parameter(clip, "motion", "anchor", [x + across / 2, y + down / 2])
        self.parameter(clip, "motion", "position", [cx, cy])
        self.parameter(clip, "motion", "scale", scale)

    def marker(self, name: str, seconds: int) -> None:
        self.command("markers.add", {"target": "program", "time": seconds * TICKS, "name": name})

    def verify_fonts(self) -> None:
        fonts = self.command("graphics.fonts.used", {})
        if {(font["family"], font["style"]) for font in fonts if not font["missing"]} != {
            ("Inter", "SemiBold"), ("Georgia", "Regular"),
        }:
            raise SystemExit("The FilmCraft cut needs Georgia Regular and Inter SemiBold")

    def render(self, frames: Path, preview_times: tuple[int, ...], *, duration: int) -> Path:
        """Render review PNGs and a reviewable lossless numbered picture sequence."""
        for seconds in preview_times:
            subprocess.run(  # noqa: S603 - fixed FilmCraft invocation
                [self.cli, "--project", str(self.path), "render", "--seconds", str(seconds),
                 "--scale", str(360 / self.width), "--out", str(self.path.with_name(f"{self.path.stem}-{seconds:02}.png"))],
                check=True,
            )
        exported = self.command("file.exportMedia", {"path": str(frames / "frame.png"), "format": "png",
                                                        "range": "entire", "audio": False, "wait": True})
        if exported["offlineMedia"] or exported["warnings"] or exported["result"]["frames"] != duration * self.fps:
            raise SystemExit(f"FilmCraft could not render the complete tour: {exported}")
        first = Path(exported["path"])
        digits = len(first.stem) - len("frame")
        if digits <= 0 or not first.stem.startswith("frame"):
            raise SystemExit(f"Unexpected FilmCraft frame numbering: {first.name}")
        return first.with_name(f"frame%0{digits}d.png")


SCENE_HEADINGS = {
    "passage": ("PASSAGE", "Inspect the word count", INK),
    "research": ("RESEARCH", "Open the linked source", INK),
    "compare": ("REVISION", "Compare the new draft", LILAC),
    "save": ("SAVE", "Keep the reviewed change", LILAC),
    "export": ("EXPORT", "Check the reading copy", PAPER),
    "reader": ("READING COPY", "Open the result", PAPER),
}


def _framed_crop(source: Source, focus: dict[str, Any], *, portrait: bool) -> tuple[float, float, float, float]:
    """Keep the action in frame, with enough of the workspace around it to orient the viewer."""
    x, y, width, height = (float(focus[axis]) for axis in ("x", "y", "width", "height"))
    if not all(math.isfinite(value) for value in (x, y, width, height)) or width <= 0 or height <= 0:
        raise SystemExit("The tour capture supplied an invalid focus region")
    pad = 24 if portrait else 36
    across = min(source.width, max(418 if portrait else 900, width + 2 * pad))
    down = min(source.height, max(240 if portrait else 450, height + 2 * pad))
    return (
        min(max(0, x + (width - across) / 2), source.width - across),
        min(max(0, y + (height - down) / 2), source.height - down),
        across, down,
    )


def _portrait_comparison(edit: Edit, source: Source, region: dict[str, Any],
                         start: int, end: int, source_frame: int) -> bool:
    """Keep the changed sentence and its original visible while the draft is actually typed."""
    draft = region.get("portrait")
    if draft is None or draft["height"] != region["height"] or draft["height"] < 240:
        return False
    pane_width = draft["width"]
    if draft["x"] - region["x"] < pane_width:
        return False

    # Both editor panes share the same screen recording and the same destination frames.
    # The draft selection sits slightly higher because its textarea is focused and scrolled.
    pane_height = draft["height"]
    crop_height = pane_height * .385
    image_width = edit.width - 144
    slot_height = 297
    label_x = (edit.width - min(image_width, slot_height * pane_width / crop_height)) / 2
    rows = (
        ("Current file", region["x"], .40, 568, "V2"),
        ("Draft to review", draft["x"], .37, 909, "V3"),
    )
    label_clip = None
    for label, x, offset, label_y, track in rows:
        edit.picture(
            source, start, end, (edit.width / 2, label_y + 24, image_width, slot_height),
            crop=(x, draft["y"] + pane_height * offset, pane_width, crop_height),
            track=track, source_frame=source_frame, align_top=True,
        )
        label_clip = edit.text(start / edit.fps, end / edit.fps, label, label_x, label_y,
                               37, VIOLET, clip=label_clip, track=5)
    return True


def compose(edit: Edit, root: Path, plan: dict[str, Any],
            footage: list[tuple[dict[str, Any], Path, Path]]) -> None:
    """Follow the recorded author journey from the evidence to the delivered reading copy."""
    width, port, rate = edit.width, edit.port, edit.fps
    middle = width / 2
    picture_box = (middle, 550, width - 144, 687) if port else (middle, 539, width - 112, 558)
    movies = list(dict.fromkeys(movie for _, movie, _ in footage))
    artwork = root / ICON
    logo, *recordings = edit.import_sources(
        [artwork, *movies],
        [png_size(artwork), *((1440, 900) for _ in movies)],
    )
    sources = dict(zip(movies, recordings, strict=True))
    clips = {segment["id"]: (segment, sources[movie]) for segment, movie, _ in footage}

    cursor = 0
    for capture in plan["captures"]:
        name = capture["id"]
        duration = capture["duration"]
        stop = cursor + duration
        segment, source = clips[name]
        destination_frames = duration * rate
        if destination_frames > segment["frames"] or segment["actionEnd"] > duration:
            raise SystemExit(f"The {name} recording does not contain its complete action within the edit")

        heading_start = cursor
        if name == "passage":
            heading_start = plan["scenes"][0]["end"]
            edit.heading(cursor, heading_start, "WAREHOUSE 4", "Why is this marked?", serif=True)
        kicker, title, color = SCENE_HEADINGS[name]
        edit.heading(heading_start, stop, kicker, title, background=color)
        # Short focus cuts follow the actual UI action without re-timing the recording.
        focus = {0: segment["detail"]}
        for region in segment.get("focus", ()):
            frame = round(float(region["seconds"]) * rate)
            if 0 <= frame < destination_frames:
                focus[frame] = region
        cuts = sorted(focus)
        for begin, end in zip(cuts, [*cuts[1:], destination_frames], strict=True):
            region = focus[begin]
            start_frame, end_frame = cursor * rate + begin, cursor * rate + end
            source_frame = segment["startFrame"] + begin
            if port and name == "compare" and _portrait_comparison(
                edit, source, region, start_frame, end_frame, source_frame,
            ):
                continue
            action = region.get("portrait", region) if port else region
            if port and name == "research" and action["height"] >= 600:
                # The previous cut shows the whole drawer. The outcome holds on the
                # linked claim and exact passage, above the unrelated decision rows.
                action = {**action, "y": action["y"] + 212, "height": 310}
            if name == "save" and end == destination_frames:
                # The reader's writing hint sits to the right of the reopened line.
                # Frame the saved sentence itself, leaving that hint out of the hold.
                crop = (action["x"] - 18, action["y"] - 18, action["width"] * .87, action["height"] * 2.1)
            else:
                crop = _framed_crop(source, action, portrait=port)
            edit.picture(
                source, start_frame, end_frame, picture_box,
                crop=crop, source_frame=source_frame, align_top=port,
            )
        cursor = stop

    if cursor >= plan["duration"]:
        raise SystemExit("The tour needs time for its final demo link")
    duration = plan["duration"]
    end_title = edit.heading(cursor, duration, "WAREHOUSE 4", "Try this passage", serif=True, poster=True)
    edit.text(cursor, duration, "lixity.de", edit.left, 718 if port else 473,
              58 if port else 47, GOLD, clip=end_title)
    logo_size = round((54 if port else 40) * LOGO_SCALE)
    edit.picture(logo, 0, duration * rate,
                 (edit.left + logo_size / 2, 191 if port else 82, logo_size, logo_size), track="V5")
    for scene in plan["scenes"]:
        edit.marker(scene["id"], scene["start"])
    edit.marker("end", duration)
    edit.verify_fonts()
