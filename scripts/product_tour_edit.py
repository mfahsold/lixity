"""Build the editable FilmCraft cut from verified Warehouse 4 recordings."""

from __future__ import annotations

import csv
import json
import math
import shutil
import struct
import subprocess
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from shutil import copyfile
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
# Leave space for native controls and portrait social overlays.
LANDSCAPE_SAFE_Y = (90.0, 810.0)
PORTRAIT_SAFE_Y = (384.0, 1248.0)
Rect = tuple[float, float, float, float]
TRACK_NAMES = ("Background", "Workspace capture", "Workspace inset", "Scene titles",
               "Lixity wordmark", "Current file label", "Draft label", "Lixity logo")


def _type_size(value: int) -> int:
    """Shrink on-frame type while keeping FilmCraft point sizes as integers."""
    return max(1, round(value * TEXT_SCALE))


@dataclass(frozen=True)
class Source:
    item: int
    width: int
    height: int


@dataclass(frozen=True)
class Take:
    start: int
    end: int
    source_frame: int = 0
    hold_end: int = 0


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
        self.graphics: dict[int, tuple[float, float]] = {}
        self.cut_frames: set[int] = set()
        self.transition_frames: set[int] = set()
        self.review_frames: list[int] = []
        self.command("file.newSequence", {"name": f"Warehouse 4 | {width}x{height}",
                                         "width": width, "height": height, "fps": fps,
                                         "video": 8, "audio": 0}, first=True)

    def command(self, name: str, params: dict[str, Any], *, first: bool = False, save: bool = True) -> Any:
        project = ["--save-as" if first else "--project", str(self.path)]
        if save and not first:
            project.append("--save")
        result = subprocess.check_output(  # noqa: S603 - fixed FilmCraft invocation
            [self.cli, *project, "exec", name, json.dumps(params)], text=True,
        )
        return json.loads(result)

    def batch(self, name: str, commands: list[dict[str, Any]]) -> None:
        script = "\n".join(json.dumps({"id": name, "params": params}) for params in commands)
        result = subprocess.run(  # noqa: S603 - fixed FilmCraft invocation
            [self.cli, "--project", str(self.path), "--save", "run", "-"],
            input=script, text=True, stdout=subprocess.PIPE, check=False,
        )
        if result.returncode:
            raise SystemExit(f"FilmCraft {name} batch failed for {self.path.name}: {result.stdout.strip()}")

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
             align: str = "left", band: tuple[float, float] | None = None, track: int = 3) -> int:
        params = {"text": label, "position": [x, y], "size": _type_size(size),
                  "font": "Georgia" if serif else "Inter",
                  "fontStyle": "Regular" if serif else "SemiBold"}
        if clip is None:
            params.update({"track": track, "time": round(start * TICKS), "seconds": end - start})
        else:
            params["clip"] = clip
        layer = self.command("graphics.newText", params)
        self.command("graphics.set", {**layer, "props": {"fill_color": color, "align": align}})
        clip_id = int(layer["clip"])
        if band is not None:
            self.graphics[clip_id] = band
        return clip_id

    def heading(self, start: int, end: int, kicker: str, title: str, *, background: str = INK,
                align: str = "left", below: bool = False, serif: bool = False, poster: bool = False) -> int:
        self.background(start, end, background)
        warm = background == INK
        foreground, accent = (PAPER, GOLD) if warm else (INK, VIOLET)
        x = self.width - self.left if align == "right" else self.left
        self.text(start, end, "Lixity", self.left + (65 if self.port else 50),
                  207 if self.port else 93, 42 if self.port else 32, foreground, track=4)
        band = self.heading_band(below=below, poster=poster)
        if self.port:
            kicker_y, title_y = (1123, 1200) if below else (420, 515 if serif else 494)
        else:
            kicker_y, title_y = (724, 792) if below else (152, 283 if poster else 219)
        clip = self.text(start, end, kicker, x, kicker_y, 33 if self.port else 25,
                         accent, align=align, band=band)
        self.text(start, end, title, x, title_y,
                  (92 if serif else 58) if self.port else (65 if serif else 50),
                  foreground, serif=serif, clip=clip, align=align)
        return clip

    def heading_band(self, *, below: bool = False, poster: bool = False) -> tuple[float, float]:
        low, high = PORTRAIT_SAFE_Y if self.port else LANDSCAPE_SAFE_Y
        if poster:
            return low, high
        if below:
            return (1089 if self.port else 694), high
        return low, (548 if self.port else 242)

    def set_parameters(self, clip: int, effects: dict[int | str, dict[str, Any]]) -> None:
        # Save once per placement so all crop edges and its transform travel together.
        self.batch("effects.setParam", [
            {"clip": clip, "effect": effect, "param": name, "value": value}
            for effect, parameters in effects.items() for name, value in parameters.items()
        ])

    def picture(self, source: Source, take: Take, box: Rect, *, crop: Rect | None = None,
                track: str = "V2", reveal: bool = False) -> None:
        """Fit the selected area without stretching the recording."""
        x, y, across, down = crop or (0, 0, source.width, source.height)
        if not (0 <= x < x + across <= source.width and 0 <= y < y + down <= source.height):
            raise SystemExit("The tour edit requested a crop outside its source image")
        left, top, width, height = box
        if not (28 <= left < left + width <= self.width - 28 and 0 <= top < top + height <= self.height):
            raise SystemExit("The tour edit requested a picture outside its safe frame")
        if crop is not None:
            low, high = PORTRAIT_SAFE_Y if self.port else LANDSCAPE_SAFE_Y
            if not low <= top < top + height <= high:
                raise SystemExit("The product capture overlaps the player controls or social overlays")
        # A single button or icon should remain visibly smaller than a full panel.
        scale = min(width / across, height / down, 3.25) * 100
        motion = {
            "anchor": [x + across / 2, y + down / 2], "position": [left + width / 2, top + height / 2], "scale": scale,
        }
        crop_edges = None
        window = None
        if crop is not None:
            edges = {"left": x / source.width, "right": 1 - (x + across) / source.width,
                     "top": y / source.height, "bottom": 1 - (y + down) / source.height}
            crop_edges = {key: max(0, value) * 100 for key, value in edges.items()}
            window = (across, down)
            self.cut_frames.add(take.start)
        moving_end = take.end - take.hold_end
        self._place_picture(source, track, take.start, moving_end, take.source_frame, motion, crop_edges,
                            window, reveal=reveal)
        if take.hold_end:
            last_source_frame = take.source_frame + moving_end - take.start - 1
            self._place_picture(source, track, moving_end, take.end, last_source_frame, motion, crop_edges,
                                window, hold=True)

    def _place_picture(self, source: Source, track: str, start: int, end: int, source_frame: int,
                       motion: dict[str, Any], crop: dict[str, float] | None, window: tuple[float, float] | None,
                       *, hold: bool = False, reveal: bool = False) -> None:
        clip, = self.command("timeline.place", {
            "item": source.item, "track": track, "frame": start,
            "duration": {"frame": end - start}, "sourceIn": {"frame": source_frame}, "audio": False,
        })["clips"]
        effects: dict[int | str, dict[str, Any]] = {"motion": motion}
        if crop is not None:
            effect = self.command("effects.apply", {"clips": [clip], "effect": "crop"})["applied"][0]["index"]
            effects[effect] = crop
        self.set_parameters(clip, effects)
        if window is not None:
            narrow = min(window)
            scale = motion["scale"] / 100
            mask = self.command("masks.add", {
                "clip": clip, "effect": "opacity", "shape": "rectangle", "center": motion["anchor"],
                "size": window, "cornerRadius": min(18, narrow * .16, 16 / scale),
            })
            self.command("masks.set", {"clip": clip, "effect": "opacity", "mask": mask["mask"],
                                       "feather": min(6, narrow * .055, 5 / scale)})
        fade = min(round(.28 * self.fps), end - start - 1)
        if reveal and fade >= 2:
            self.batch("effects.setParam", [
                {"clip": clip, "effect": "opacity", "param": "opacity", "keyframe": True,
                 "time": frame * TICKS // self.fps, "value": value}
                for frame, value in ((start, 38), (start + fade // 2, 82), (start + fade, 100))
            ])
            self.transition_frames.update(range(start, start + fade + 1))
        if hold:
            self.command("clip.frameHoldOptions", {"clips": [clip], "holdOn": "in"})

    def add_chapters(self, plan: dict[str, Any]) -> None:
        self.batch("markers.addChapter", [{"time": cue["start"] * TICKS, "name": cue["id"]}
                                          for cue in plan["scenes"]])
        self.command("markers.add", {"target": "program", "time": plan["duration"] * TICKS, "name": "end"})

    def export_markers(self, path: Path, plan: dict[str, Any]) -> None:
        """Verify the editable sequence's chapter markers against the website cue plan."""
        self.command("markers.exportCsv", {"path": str(path)}, save=False)
        rate = f"{self.fps}/1"
        expected = [(cue["id"], "Chapter", str(cue["start"] * TICKS), rate) for cue in plan["scenes"]]
        expected.append(("end", "Comment", str(plan["duration"] * TICKS), rate))
        with path.open(encoding="utf-8", newline="") as report:
            actual = [(row.get("Name"), row.get("Kind"), row.get("Start Ticks"), row.get("Frame Rate"))
                      for row in csv.DictReader(report)]
        if actual != expected:
            raise SystemExit(f"FilmCraft chapter markers differ from the tour timing plan: {path}")

    def name_tracks(self) -> None:
        self.batch("timeline.setTrack", [{"track": f"V{index}", "name": name}
                                         for index, name in enumerate(TRACK_NAMES, 1)])

    def verify_fonts(self) -> None:
        fonts = self.command("graphics.fonts.used", {}, save=False)
        if {(font["family"], font["style"]) for font in fonts if not font["missing"]} != {
            ("Inter", "SemiBold"), ("Georgia", "Regular"),
        }:
            raise SystemExit("The FilmCraft cut needs Georgia Regular and Inter SemiBold")

    def verify_type_bounds(self) -> None:
        for clip, (low, high) in self.graphics.items():
            occupied: list[Rect] = []
            for layer in self.command("graphics.list", {"clip": clip}, save=False)["layers"]:
                x, y = zip(*layer["quad"], strict=True)
                bounds = (min(x), min(y), max(x), max(y))
                left, top, right, bottom = bounds
                if layer["overflow"] or not (40 <= left < right <= self.width - 40 and low <= top < bottom <= high):
                    raise SystemExit(f"FilmCraft text leaves its layout slot: {layer.get('text', clip)} {bounds}")
                if any(left < x2 and right > x1 and top < y2 and bottom > y1 for x1, y1, x2, y2 in occupied):
                    raise SystemExit(f"FilmCraft text layers overlap in clip {clip}: {bounds}")
                occupied.append(bounds)

    def render(self, frames: Path, *, duration: int) -> Path:
        """Render the master once and use its frames for visual review."""
        media = self.command("media.status", {}, save=False)
        unavailable = [f"{item['name']} ({item['status']})" for item in media if item["status"] != "online"]
        if unavailable:
            raise SystemExit(f"FilmCraft source media unavailable in {self.path.name}: {', '.join(unavailable)}")
        exported = self.command("file.exportMedia", {"path": str(frames / "frame.png"), "format": "png",
                                                        "range": "entire", "audio": False, "wait": True}, save=False)
        if exported["offlineMedia"] or exported["warnings"] or exported["result"]["frames"] != duration * self.fps:
            raise SystemExit(f"FilmCraft could not render the complete tour: {exported}")
        first = Path(exported["path"])
        digits = len(first.stem) - len("frame")
        if digits <= 0 or not first.stem.startswith("frame"):
            raise SystemExit(f"Unexpected FilmCraft frame numbering: {first.name}")
        sequence = first.with_name(f"frame%0{digits}d.png")
        # Copy the exact source frames of the published encodes around every cut.
        cut_points = sorted({0, *self.cut_frames, duration * self.fps})
        boundary_frames = {frame for cut in cut_points for frame in (cut - 1, cut)
                           if 0 <= frame < duration * self.fps}
        midpoints = {(start + end) // 2 for start, end in pairwise(cut_points)}
        self.review_frames = sorted(boundary_frames | midpoints | self.transition_frames)
        review = self.path.with_name(f"{self.path.stem}-cuts")
        review.mkdir(exist_ok=True)
        for stale in review.glob("frame-*.png"):
            stale.unlink()
        for frame in self.review_frames:
            copyfile(sequence.with_name(sequence.name % frame), review / f"frame-{frame:04d}.png")
        return sequence


SCENE_HEADINGS = {
    "passage": ("PASSAGE", "Inspect the word count", INK),
    "research": ("RESEARCH", "Open the linked claim", INK),
    "compare": ("REVISION", "Compare the new draft", LILAC),
    "save": ("SAVE", "Keep the reviewed change", LILAC),
    "export": ("EXPORT", "Check the reading copy", PAPER),
    "reader": ("READING COPY", "Open the result", PAPER),
}

# Stable editorial choices keep the action readable while changing the layout at cuts.
RIGHT_HEADINGS = {"research", "save", "reader"}
LOW_HEADINGS = {"save"}
RIGHT_INSETS = {"research", "reader"}


def _crop(focus: dict[str, Any]) -> Rect:
    x, y, w, h = (float(focus[axis]) for axis in ("x", "y", "width", "height"))
    if not all(math.isfinite(value) for value in (x, y, w, h)) or w <= 0 or h <= 0:
        raise SystemExit("The tour capture supplied an invalid focus region")
    return x, y, w, h


def _body(edit: Edit, name: str) -> Rect:
    """Give the moving capture more room, varying the visual axis by beat."""
    right = name in RIGHT_HEADINGS
    below = name in LOW_HEADINGS
    if edit.port:
        return (56 if right else 36, 401 if below else 554, edit.width - 88, 680 if below else 686)
    return (60 if right else 36, 125 if below else 250, edit.width - 92, 560 if below else 558)


def _separate(main: Rect, inset: Rect) -> bool:
    x, y, w, h = main
    a, b, m, n = inset
    return x + w <= a or a + m <= x or y + h <= b or b + n <= y


def _paired_picture(edit: Edit, source: Source, name: str, main: Rect, inset: Rect, take: Take,
                    *, reveal: bool = False) -> None:
    """Add complementary screen context outside the primary image's bounds."""
    if not _separate(main, inset):
        raise SystemExit(f"The {name} insert repeats part of its primary workspace crop")
    x, y, w, h = _body(edit, name)
    right = name in RIGHT_INSETS
    if edit.port:
        if right:
            main_box = (x, y, w, h - 172)
            inset_box = (x + w * .22, y + h - 148, w * .78, 148)
        else:
            main_box = (x, y + 132, w, h - 132)
            inset_box = (x, y, w * .60, 108)
    else:
        inset_width = w * (.34 if right else .25)
        main_width = w - inset_width - 32
        main_box = (x if right else x + inset_width + 32, y, main_width, h)
        inset_box = (x + main_width + 32 if right else x, y + (34 if right else h - 205), inset_width, 150)
    edit.picture(source, take, main_box, crop=main, reveal=reveal)
    edit.picture(source, take, inset_box, crop=inset, track="V3", reveal=reveal)


def _comparison(edit: Edit, source: Source, regions: dict[str, Any], extent: tuple[float, float],
                take: Take) -> None:
    """Show matched source frames from the two relevant manuscript versions."""
    x, y, w, _ = _body(edit, "compare")
    if edit.port:
        rows = ((x, y + 62, w - 46, 254), (x + 46, y + 399, w - 46, 254))
    else:
        across = (w - 48) / 2
        rows = ((x, y + 116, across, 300), (x + across + 48, y + 116, across, 300))
    for key, label, slot, track in zip(("current", "draft"), ("Current file", "Draft to review"),
                                       rows, ("V2", "V3"), strict=True):
        crop = _crop(regions[key])
        left, top, width, height = slot
        scale = min(width / extent[0], height / extent[1])
        left += (width - extent[0] * scale) / 2
        edit.picture(source, take, (left, top, crop[2] * scale, crop[3] * scale), crop=crop, track=track)
        edit.text(take.start / edit.fps, take.end / edit.fps, label, max(44, left), top - 14,
                  37 if edit.port else 32, VIOLET, track=5 if track == "V2" else 6,
                  band=(top - 58, top - 4))


def _take(segment: dict[str, Any], region: dict[str, Any], *, scene_frame: int, begin: int,
          end: int, destination_frames: int, rate: int) -> Take:
    # A cut belongs to the action. Its incoming footage starts when the new
    # layout has reached the recording. Chromium can deliver recorded frames
    # after the DOM geometry is already correct, so give each new crop 120 ms.
    recording_buffer = math.ceil(.12 * rate)
    stable_frame = math.ceil(float(region["sourceSeconds"]) * rate)
    if begin:
        stable_frame += recording_buffer
    source_start = max(begin, stable_frame)
    length = end - begin
    # The comparison result reflows both panes before the response callback
    # in Playwright's clock. Freeze the previous crop before that repaint.
    outgoing = math.ceil(.2 * rate) if region.get("comparison") else recording_buffer
    moving = max(1, end - outgoing - source_start) if end < destination_frames else length
    if source_start + moving > segment["frames"]:
        raise SystemExit(f"The settled {segment['id']} picture extends beyond its native recording")
    return Take(scene_frame + begin, scene_frame + end, segment["startFrame"] + source_start, length - moving)


def compose(edit: Edit, root: Path, plan: dict[str, Any],
            footage: list[tuple[dict[str, Any], Path, Path]]) -> None:
    """Follow the recorded author journey from the evidence to the delivered reading copy."""
    port, rate = edit.port, edit.fps
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
            edit.cut_frames.add(heading_start * rate)
        kicker, title, color = SCENE_HEADINGS[name]
        edit.heading(heading_start, stop, kicker, title, background=color,
                     align="right" if name in RIGHT_HEADINGS else "left", below=name in LOW_HEADINGS)
        # Keep the overall cue timing and cut around transient UI states.
        focus = {}
        for region in segment["focus"]:
            frame = round(float(region["seconds"]) * rate)
            if 0 <= frame < destination_frames:
                focus[frame] = region
        cuts = sorted(focus)
        if not cuts or cuts[0] != 0:
            raise SystemExit(f"The {name} recording has no opening focus region")
        panes = [_crop(pane) for region in focus.values() for pane in region.get("comparison", {}).values()]
        comparison_extent = (max((pane[2] for pane in panes), default=0), max((pane[3] for pane in panes), default=0))
        for begin, end in zip(cuts, [*cuts[1:], destination_frames], strict=True):
            region = focus[begin]
            take = _take(segment, region, scene_frame=cursor * rate, begin=begin, end=end,
                         destination_frames=destination_frames, rate=rate)
            if comparison := region.get("comparison"):
                _comparison(edit, source, comparison, comparison_extent, take)
            elif inset := region.get("inset"):
                _paired_picture(edit, source, name, _crop(region), _crop(inset), take, reveal=region.get("reveal", False))
            else:
                edit.picture(source, take, _body(edit, name),
                             crop=_crop(region.get("portrait", region) if port else region),
                             reveal=region.get("reveal", False))
        cursor = stop

    if cursor >= plan["duration"]:
        raise SystemExit("The tour needs time for its final demo link")
    duration = plan["duration"]
    edit.cut_frames.add(cursor * rate)
    end_title = edit.heading(cursor, duration, "WAREHOUSE 4", "Try this passage", serif=True, poster=True)
    edit.text(cursor, duration, "lixity.de", edit.left, 718 if port else 473,
              58 if port else 47, GOLD, clip=end_title)
    logo_size = round((54 if port else 40) * LOGO_SCALE)
    edit.picture(logo, Take(0, duration * rate),
                 (edit.left, (191 if port else 82) - logo_size / 2, logo_size, logo_size), track="V8")
    edit.add_chapters(plan)
    edit.verify_fonts()
    edit.verify_type_bounds()
    edit.name_tracks()
