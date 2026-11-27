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
RECEIPT = "docs/assets/research/warehouse-4-receipt.png"
LEDGER = "docs/assets/research/warehouse-4-ledger.png"
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
        self.left = 84 if self.port else 76
        self.fps = fps
        self.command("file.newSequence", {"name": f"Warehouse 4 | {width}x{height}",
                                         "width": width, "height": height, "fps": fps,
                                         "video": 5, "audio": 0}, first=True)

    def command(self, name: str, params: dict, *, first: bool = False) -> Any:
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
        return layer["clip"]

    def heading(self, start: int, end: int, kicker: str, title: str, *, background: str = INK,
                serif: bool = False, subtitle: str = "", poster: bool = False) -> int:
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
        if subtitle:
            self.text(start, end, subtitle, self.left, 573 if self.port else 280,
                      37 if self.port else 26, accent, clip=wordmark)
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


def compose(edit: Edit, root: Path, plan: dict, recording: dict,
            footage: list[tuple[dict, Path, Path]], exhibit: Path) -> None:
    """Set the visual rhythm. Internal cuts leave the six chapter cues intact."""
    artwork = [root / asset for asset in (RECEIPT, LEDGER, ICON)]
    receipt, ledger, logo, pdf = edit.import_sources(
        [*artwork, exhibit], [png_size(path) for path in (*artwork, exhibit)],
    )
    clips = {}
    details = {}
    for segment, movie, still in footage:
        moving, held = edit.import_sources([movie, still], [(1440, 900), png_size(still)])
        clips[segment["id"]] = segment, moving, held
        details[segment["id"]] = tuple(segment["detail"][axis] for axis in ("x", "y", "width", "height"))
    width, port = edit.width, edit.port
    middle = width / 2
    picture_span = width - 2 * (84 if port else 56)
    panel = (middle, 925, picture_span, 620) if port else (middle, 553, picture_span, 576)

    def moving(name: str, start: int, end: int, crop: tuple[float, float, float, float], *,
               box=panel, source_seconds: float = 0, track: str = "V2") -> None:
        segment, video, _ = clips[name]
        offset = math.ceil(source_seconds * edit.fps)
        if offset + (end - start) * edit.fps > segment["frames"]:
            raise SystemExit(f"The {name} recording is too short for its cut")
        edit.picture(video, start, end, box, crop=crop, source_frame=segment["startFrame"] + offset, track=track)

    def detail(name: str, start: int, end: int, *, pad: int = 0, box=panel,
               keep_height: float = 1) -> None:
        _, _, source = clips[name]
        x, y, w, h = details[name]
        crop = ((x - pad) * 2, (y - pad) * 2, (w + 2 * pad) * 2, (h * keep_height + 2 * pad) * 2)
        edit.picture(source, start, end, box, crop=crop)

    def tag(start: int, end: int, group: int, label: str, x: float, y: float, *, color: str = VIOLET) -> None:
        edit.text(start, end, label, x, y, 37 if port else 29, color, clip=group)

    opening = edit.heading(0, 5, "WAREHOUSE 4  /  FICTION", "The Blank Line", serif=True, poster=True)
    receipt_box = (middle, 992, picture_span, 530) if port else (width * .73, 469, width * .46, 570)
    paper_crop = (114, 100, 872, 516)
    edit.picture(receipt, 0, 5, receipt_box, crop=paper_crop, push=1.05)
    question = "Can Mara sign for an arrival she never saw?"
    if port:
        question = question.replace(" she never", "\nshe never")
    tag(0, 5, opening, question, edit.left, 600 if port else 382, color=GOLD)

    edit.heading(5, 9, "01  /  MANUSCRIPT", "Read the passage")
    moving("read", 5, 9, (466, 111, 757, 620) if port else (430, 100, 840, 425))
    reading = edit.heading(9, 14, "01  /  MANUSCRIPT", "From the draft")
    excerpt = recording["originalSentence"].split(" that she began", 1)[0]
    excerpt = excerpt.replace(" at it", "\nat it") if port else excerpt
    edit.text(9, 14, f"“{excerpt}…”", edit.left, 740 if port else 409, 55 if port else 49, PAPER,
              serif=True, clip=reading)
    detail("read", 9, 14, pad=12,
           box=(middle, 1110, picture_span, 245) if port else (middle, 625, picture_span, 206))

    edit.heading(14, 20, "02  /  EXPLANATION", "22 of 31 words", background=LILAC, subtitle="Counted as function words")
    x, y, w, h = details["passage"]
    if port:
        moving("passage", 14, 17, (x - 52, y - 68, w + 112, h + 78))
    else:
        moving("passage", 14, 17, (x - 62, y - 79, w + 417, h + 14))
    analysis_panel = (middle, 924, picture_span, 620) if port else (width * .704, 495, width * .52, 590)
    detail("passage", 17, 20, box=analysis_panel, keep_height=.61 if port else .64)

    comparison = edit.heading(20, 23, "03  /  REVISION", "Compare the draft", background=LILAC)
    # Use the verified, scrolled comparison after the editor has applied the draft change.
    compared_at = clips["compare"][0]["actionEnd"] + 2 / edit.fps
    if port:
        tag(20, 23, comparison, "CURRENT FILE", edit.left, 650)
        tag(20, 23, comparison, "DRAFT TO REVIEW", edit.left, 947)
        moving("compare", 20, 23, (531, 467, 379, 120),
               box=(middle, 778, picture_span, 221), source_seconds=compared_at)
        moving("compare", 20, 23, (920, 467, 390, 64),
               box=(middle, 1074, picture_span, 221), source_seconds=compared_at, track="V3")
    else:
        moving("compare", 20, 23, (124, 179, 1190, 499), source_seconds=compared_at)
    compared = edit.heading(23, 27, "UNSAVED DRAFT  /  SAME SETTINGS", "31 to 12 words", background=LILAC)
    before = recording["originalSentence"].split(" that she began", 1)[0] + "…"
    after = recording["draftSentence"]
    second_column = edit.left if port else width * .53
    tag(23, 27, compared, "ORIGINAL EXCERPT", edit.left, 760 if port else 403)
    tag(23, 27, compared, "DRAFT", second_column, 1055 if port else 403)
    lines = (before.replace(" at it", "\nat it"), after.replace("why he", "\nwhy he")) if port else (
        before.replace(" she looked", "\nshe looked"), after.replace("why he", "\nwhy he"),
    )
    for line, column, row in zip(
        lines, (edit.left, second_column), (846, 1141) if port else (487, 487), strict=True,
    ):
        edit.text(23, 27, line, column, row, 51 if port else 38, INK, serif=True, clip=compared)

    edit.heading(27, 31, "04  /  RESEARCH", "The exhibit book", background=PAPER)
    exhibit_click = clips["dossier"][0]["clicks"][0]
    left = details["dossier"][0] - 18
    moving("dossier", 27, 30, (left, exhibit_click["y"] - 130, exhibit_click["x"] - left + 58, 166),
           box=(middle, 899, picture_span, 440) if port else (middle, 503, picture_span, 440))
    detail("dossier", 30, 31, box=panel)
    edit.heading(31, 36, "OFFICE LEDGER", "18:40", background=PAPER, subtitle="Cart 17 returned")
    ledger_box = (middle, 925, picture_span, 590) if port else (middle, 552, picture_span, 510)
    edit.picture(ledger, 31, 36, ledger_box, crop=(114, 126, 872, 470 if port else 445))

    joined = edit.heading(36, 42, "LEDGER  /  RECEIPT", "The same number", background=PAPER)
    edit.picture(ledger, 36, 42, (middle, 795, picture_span, 236) if port else (width * .268, 553, width * .43, 290),
                 crop=(148, 294, 801, 186))
    edit.picture(receipt, 36, 42, (middle, 1114, picture_span, 236) if port else (width * .732, 553, width * .43, 290),
                 crop=(148, 276, 801, 179), track="V3")
    tag(36, 42, joined, "18:40   /   RETURN", edit.left, 650 if port else 416)
    tag(36, 42, joined, "20:00   /   DISPATCH", edit.left if port else width * .52, 970 if port else 416)
    for x, y in ((width - 138, 650), (width - 138, 970)) if port else ((width * .45, 416), (width * .91, 416)):
        edit.text(36, 42, "17", x, y, 45 if port else 35, VIOLET, serif=True, clip=joined)

    edit.heading(42, 47, "05  /  MANUSCRIPT", "Return to the text")
    moving("decision", 42, 44, (445, 230, 824, 465) if port else (450, 260, 785, 405))
    detail("decision", 44, 47, pad=22)
    signed = edit.heading(47, 52, "WAREHOUSE 4  /  MANUSCRIPT", "The final line", serif=True, poster=True)
    quote = recording["closingSentence"]
    edit.text(47, 52, "“" + (quote.replace(" stayed", "\nstayed") if port else quote) + "”",
              edit.left, 809 if port else 453, 58 if port else 51, PAPER, serif=True, clip=signed)
    edit.picture(receipt, 47, 52,
                 (middle, 1135, picture_span, 310) if port else (width * .69, 647, width * .50, 240),
                 crop=(148, 445, 801, 80))

    edit.heading(52, 55, "06  /  EXPORT", "Share the evidence", background=PAPER)
    # The recorded control and confirmation sit below the dossier's review notice.
    x, y, w, h = details["pdf"]
    moving("pdf", 52, 55, (x - 12, y - 12, w + 24, h + 24),
           box=(middle, 915, picture_span, 218) if port else (middle, 493, width * .56, 205),
           source_seconds=clips["pdf"][0]["actionStart"])
    edit.heading(55, 57, "WAREHOUSE 4  /  EXHIBIT BOOK", "A saved dossier", background=PAPER)
    edit.picture(pdf, 55, 57, (middle, 737, picture_span, 203) if port else (middle, 386, picture_span, 178),
                 crop=(.10 * pdf.width, .084 * pdf.height, .80 * pdf.width, .10 * pdf.height))
    edit.picture(pdf, 55, 57, (middle, 1000, picture_span, 230) if port else (middle, 617, picture_span, 208),
                 crop=(.10 * pdf.width, .79 * pdf.height, .80 * pdf.width, .10 * pdf.height), track="V3")
    end = edit.heading(57, 60, "WAREHOUSE 4  /  FICTION", "", poster=True)
    edit.text(57, 60, "“" + (quote.replace(" stayed", "\nstayed") if port else quote) + "”",
              edit.left, 638 if port else 323, 75 if port else 58, PAPER, serif=True, clip=end)
    edit.picture(receipt, 57, 60, (middle, 965, picture_span, 174) if port else (middle, 548, picture_span, 147),
                 crop=(148, 445, 801, 80))
    edit.text(57, 60, "Try the demo at lixity.de", edit.left, 1213 if port else 752, 33 if port else 26,
              GOLD, clip=end)
    logo_size = round((54 if port else 40) * LOGO_SCALE)
    edit.picture(logo, 0, 60, (edit.left + logo_size / 2, 191 if port else 82, logo_size, logo_size), track="V5")

    for scene in plan["scenes"]:
        edit.marker(scene["id"], scene["start"])
    edit.marker("end", plan["duration"])
    edit.verify_fonts()
