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
SOURCE_PAPER = "#EEE4D2"
GOLD = "#D5BB89"
LILAC = "#F1EEF7"
VIOLET = "#593E79"
RECEIPT = "docs/assets/research/warehouse-4-receipt.png"
LEDGER = "docs/assets/research/warehouse-4-ledger.png"
ICON = "docs/assets/brand/icon-192.png"
TEXT_SCALE = 0.85
LOGO_SCALE = 0.85
CAPTURE_SCALE = math.sqrt(1.12)
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
                                         "video": 5, "audio": 0}, first=True)

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

    def text(self, start: int, end: int, label: str, x: float, y: float, size: int,
             color: str, *, serif: bool = False, clip: int | None = None,
             check_safe: bool = True) -> int:
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
            params.update({"track": 3, "time": start * TICKS, "seconds": end - start})
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

    def parameter(self, clip: int, effect: int | str, name: str, value: Any,
                  *, time: int | None = None, keyframe: bool = False) -> None:
        params: dict[str, Any] = {"clip": clip, "effect": effect, "param": name, "value": value}
        if time is not None:
            params["time"] = time
        if keyframe:
            params["keyframe"] = True
        self.command("effects.setParam", params)

    def picture(self, source: Source, start: int, end: int,
                box: tuple[float, float, float, float], *,
                crop: tuple[float, float, float, float] | None = None, track: str = "V2",
                source_frame: int = 0, push: float = 1.0) -> None:
        """Fit the final crop inside its box and preserve side margins through motion."""
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
        placed = self.command("timeline.place", {"item": source.item, "track": track, "seconds": start,
                                                 "duration": {"seconds": end - start},
                                                 "sourceIn": {"frame": source_frame}, "audio": False})
        clip = placed["clips"][0]
        if crop is not None:
            effect = self.command("effects.apply", {"clips": [clip], "effect": "crop"})["applied"][0]["index"]
            edges = {"left": x / source.width, "right": 1 - (x + across) / source.width,
                     "top": y / source.height, "bottom": 1 - (y + down) / source.height}
            for key, fraction in edges.items():
                self.parameter(clip, effect, key, max(0, fraction) * 100)
        self.parameter(clip, "motion", "anchor", [x + across / 2, y + down / 2])
        self.parameter(clip, "motion", "position", [cx, cy])
        if push == 1.0:
            self.parameter(clip, "motion", "scale", scale)
        else:
            self.parameter(clip, "motion", "scale", scale / push, time=start * TICKS, keyframe=True)
            self.parameter(clip, "motion", "scale", scale,
                           time=int((start + (end - start) * .5) * TICKS), keyframe=True)

    def marker(self, name: str, seconds: int) -> None:
        self.command("markers.add", {"target": "program", "time": seconds * TICKS, "name": name})

    def verify_fonts(self) -> None:
        fonts = self.command("graphics.fonts.used", {})
        if {(font["family"], font["style"]) for font in fonts if not font["missing"]} != {
            ("Inter", "SemiBold"), ("Georgia", "Regular"),
        }:
            raise SystemExit("The FilmCraft cut needs Georgia Regular and Inter SemiBold")

    def render(self, frames: Path, preview_times: tuple[int, ...]) -> Path:
        """Render review PNGs and a reviewable lossless numbered picture sequence."""
        for seconds in preview_times:
            subprocess.run(  # noqa: S603 - fixed FilmCraft invocation
                [self.cli, "--project", str(self.path), "render", "--seconds", str(seconds),
                 "--scale", str(360 / self.width), "--out", str(self.path.with_name(f"{self.path.stem}-{seconds:02}.png"))],
                check=True,
            )
        exported = self.command("file.exportMedia", {"path": str(frames / "frame.png"), "format": "png",
                                                        "range": "entire", "audio": False, "wait": True})
        if exported["offlineMedia"] or exported["warnings"] or exported["result"]["frames"] != 60 * self.fps:
            raise SystemExit(f"FilmCraft could not render the complete tour: {exported}")
        first = Path(exported["path"])
        digits = len(first.stem) - len("frame")
        if digits <= 0 or not first.stem.startswith("frame"):
            raise SystemExit(f"Unexpected FilmCraft frame numbering: {first.name}")
        return first.with_name(f"frame%0{digits}d.png")


def compose(edit: Edit, root: Path, plan: dict[str, Any],
            footage: list[tuple[dict[str, Any], Path, Path]], exhibit: Path) -> None:
    """Set the visual rhythm. Internal cuts leave the six chapter cues intact."""
    artwork = [root / asset for asset in (RECEIPT, LEDGER, ICON)]
    receipt, ledger, logo, pdf = edit.import_sources(
        [*artwork, exhibit], [png_size(path) for path in (*artwork, exhibit)],
    )
    clips = {}
    details = {}
    for segment, movie, still in footage:
        video, held = edit.import_sources([movie, still], [(1440, 900), png_size(still)])
        clips[segment["id"]] = segment, video, held
        details[segment["id"]] = tuple(segment["detail"][axis] for axis in ("x", "y", "width", "height"))
    width, port = edit.width, edit.port
    middle = width / 2
    picture_span = width - 2 * (84 if port else 56)
    panel = (middle, 910, picture_span, 620) if port else (middle, 543, picture_span, 576)

    def capture(source: Source, start: int, end: int, box: tuple[float, float, float, float], *,
                crop: tuple[float, float, float, float], source_frame: int = 0, track: str = "V2",
                push: float = 1.0) -> None:
        """Give recordings 12% more projected area before applying the frame inset."""
        cx, cy, across, down = box
        edit.picture(source, start, end, (cx, cy, across * CAPTURE_SCALE, down * CAPTURE_SCALE),
                     crop=crop, source_frame=source_frame, track=track, push=push)

    def moving(name: str, start: int, end: int, crop: tuple[float, float, float, float], *,
               box: tuple[float, float, float, float] = panel, source_seconds: float = 0, track: str = "V2") -> None:
        segment, video, _ = clips[name]
        offset = math.ceil(source_seconds * edit.fps)
        if offset + (end - start) * edit.fps > segment["frames"]:
            raise SystemExit(f"The {name} recording is too short for its cut")
        capture(video, start, end, box, crop=crop, source_frame=segment["startFrame"] + offset, track=track)

    def detail(name: str, start: int, end: int, *, pad: int = 0, box: tuple[float, float, float, float] = panel,
               keep_height: float = 1) -> None:
        _, _, source = clips[name]
        x, y, w, h = details[name]
        crop = ((x - pad) * 2, (y - pad) * 2, (w + 2 * pad) * 2, (h * keep_height + 2 * pad) * 2)
        capture(source, start, end, box, crop=crop)

    def tag(start: int, end: int, group: int, label: str, x: float, y: float, *, color: str = VIOLET) -> None:
        edit.text(start, end, label, x, y, 37 if port else 29, color, clip=group)

    opening = edit.heading(0, 5, "WAREHOUSE 4  /  FICTION", "The Blank Line", serif=True, poster=True)
    receipt_box = (middle, 868, 936, 530) if port else (width * .713, 463, width * .49, 570)
    paper_crop = (155, 394, 674, 130)
    edit.picture(receipt, 0, 5, receipt_box, crop=paper_crop, push=1.05)
    question = "Can Mara sign for an arrival she never saw?"
    if port:
        question = question.replace(" she never", "\nshe never")
    tag(0, 5, opening, question, edit.left, 600 if port else 382, color=GOLD)

    edit.heading(5, 14, "01  /  MANUSCRIPT", "Mara’s account")
    # Begin on the settled position so the reader's recorded scroll does not repeat the next sentence.
    _, _, reader = clips["read"]
    capture(reader, 5, 14, (middle, 865, picture_span, 600) if port else panel,
            crop=(948, 416, 1436, 944), push=1.05)

    edit.heading(14, 20, "02  /  EXPLANATION", "Trace the count", background=LILAC)
    x, y, w, _ = details["passage"]
    moving("passage", 14, 16, (x - 62, y - 79, w + 402, 270),
           box=(middle, 780 if port else 505, picture_span, 420))
    analysis_panel = (middle, 906, picture_span, 620) if port else (width * .691, 491, width * .53, 590)
    detail("passage", 16, 20, box=analysis_panel, keep_height=.61)

    comparison = edit.heading(20, 27, "03  /  REVISION", "Compare one sentence", background=LILAC)
    # The verified still contains the changed lines without the comparison panel's blinking caret.
    _, _, compared = clips["compare"]
    pane_width = picture_span if port else width * .414
    current_x, draft_x = (middle, middle) if port else (width * .264, width * .736)
    capture(compared, 20, 27, (current_x, 795 if port else 543, pane_width, 298),
            crop=(1062, 924, 758, 260))
    capture(compared, 20, 27, (draft_x, 1124 if port else 495, pane_width, 221),
            crop=(1840, 922, 780, 144), track="V3")
    tag(20, 27, comparison, "CURRENT FILE · 31 WORDS", edit.left if port else current_x - pane_width * CAPTURE_SCALE / 2,
        606 if port else 390)
    tag(20, 27, comparison, "UNSAVED DRAFT · 12 WORDS", edit.left if port else draft_x - pane_width * CAPTURE_SCALE / 2,
        1002 if port else 390)

    edit.heading(27, 31, "04  /  RESEARCH", "Find the source records", background=PAPER)
    exhibit_click = clips["dossier"][0]["clicks"][0]
    left = details["dossier"][0] - 18
    moving("dossier", 27, 29, (left, exhibit_click["y"] - 130, exhibit_click["x"] - left + 155, 157),
           box=(middle, 777, picture_span, 440) if port else (middle, 504, picture_span, 440))
    _, _, dossier = clips["dossier"]
    capture(dossier, 29, 31, (middle, 879 if port else 552, picture_span, 550), crop=(2268, 136, 476, 505))

    entry = edit.heading(31, 34, "04  /  RESEARCH", "Read the return entry", background=SOURCE_PAPER)
    joined = edit.heading(34, 42, "04  /  RESEARCH", "Match the records", background=SOURCE_PAPER)
    record_width = 936 if port else width * .452
    ledger_x = middle if port else width * .266
    receipt_x = middle if port else width * .734
    edit.picture(ledger, 31, 42, (ledger_x, 750 if port else 503, record_width, 241), crop=(155, 299, 674, 65))
    edit.picture(receipt, 34, 42, (receipt_x, 1000 if port else 523, record_width, 241),
                 crop=(155, 279, 674, 113), track="V3")
    tag(31, 34, entry, "OFFICE LEDGER", ledger_x - record_width / 2, 665 if port else 425)
    tag(34, 42, joined, "OFFICE LEDGER", ledger_x - record_width / 2, 665 if port else 425)
    tag(34, 42, joined, "DISPATCH RECEIPT", receipt_x - record_width / 2, 893 if port else 425)

    edit.heading(42, 46, "05  /  MANUSCRIPT", "Mara’s decision")
    moving("decision", 42, 44, (474, 345, 721, 173),
           box=(middle, 804, picture_span, 520) if port else (middle, 488, picture_span, 495))
    _, _, decision = clips["decision"]
    capture(decision, 44, 46, (middle, 799 if port else 491, picture_span, 305), crop=(950, 1000, 1440, 170))
    ending = edit.heading(46, 52, "05  /  MANUSCRIPT", "Mara’s decision")
    edit.text(46, 52, "“The receiving line\nstayed blank.”" if port else "“The receiving line stayed blank.”",
              edit.left - 3, 811 if port else 484, 72 if port else 70, PAPER, serif=True, clip=ending)

    edit.heading(52, 55, "06  /  EXPORT", "Share the evidence", background=PAPER)
    # The action starts on the download button and widens once the confirmation is available.
    x, y, _, h = details["pdf"]
    moving("pdf", 52, 54, (x - 12, y - 3, 124, h + 6),
           box=(width * .285, 761, picture_span, 163) if port else (width * .365, 493, width * .56, 153),
           source_seconds=clips["pdf"][0]["actionStart"])
    detail("pdf", 54, 55, pad=6, box=(middle, 761, picture_span, 218) if port else (middle, 493, width * .56, 205))
    edit.heading(55, 57, "06  /  EXPORT", "From the saved version", background=PAPER)
    capture(pdf, 55, 57, (middle, 757, picture_span, 218) if port else (middle, 494, picture_span, 240),
            crop=(.10 * pdf.width, .084 * pdf.height, .80 * pdf.width, .10 * pdf.height))
    end = edit.heading(57, 60, "WAREHOUSE 4", "Try the demo", serif=True, poster=True)
    edit.text(57, 60, "lixity.de", edit.left, 718 if port else 473, 58 if port else 47,
              GOLD, clip=end)
    logo_size = round((54 if port else 40) * LOGO_SCALE)
    edit.picture(logo, 0, 60, (edit.left + logo_size / 2, 191 if port else 82, logo_size, logo_size), track="V5")

    for scene in plan["scenes"]:
        edit.marker(scene["id"], scene["start"])
    edit.marker("end", plan["duration"])
    edit.verify_fonts()
