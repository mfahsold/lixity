"""Build the editable FilmCraft cut from verified Warehouse 4 recordings."""

from __future__ import annotations

import json
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
             color: str, *, serif: bool = False, clip: int | None = None, fade: bool = False) -> int:
        params = {"text": label, "position": [x, y], "size": size,
                  "font": "Georgia" if serif else "Inter",
                  "fontStyle": "Regular" if serif else "SemiBold"}
        if clip is None:
            params.update({"track": 3, "time": start * TICKS, "seconds": end - start})
        else:
            params["clip"] = clip
        layer = self.command("graphics.newText", params)
        self.command("graphics.set", {**layer, "props": {"fill_color": color}})
        if fade:
            for frame, opacity in ((0, 0), (8, 100)):
                self.command("graphics.set", {**layer, "time": start * TICKS + frame * TICKS // self.fps,
                                               "props": {"opacity": opacity}, "keyframe": True})
        return layer["clip"]

    def heading(self, start: int, end: int, kicker: str, title: str, *, background: str = INK,
                serif: bool = False, subtitle: str = "", poster: bool = False) -> int:
        """Reserve a fixed brand axis and enough air for the story and the image."""
        self.background(start, end, background)
        warm = background == INK
        foreground, accent = (PAPER, GOLD) if warm else (INK, VIOLET)
        wordmark = self.text(start, end, "Lixity", self.left + (72 if self.port else 50),
                             207 if self.port else 93, 42 if self.port else 32, foreground)
        self.text(start, end, kicker, self.left, 375 if self.port else 190 if poster else 160,
                  33 if self.port else 25, accent, clip=wordmark)
        self.text(start, end, title, self.left - int(serif) * 3,
                  492 if self.port else 283 if poster else 224,
                  (96 if serif else 64) if self.port else (68 if serif else 50),
                  foreground, serif=serif, clip=wordmark, fade=start == 0)
        if subtitle:
            self.text(start, end, subtitle, self.left, 573 if self.port else 280,
                      37 if self.port else 26, accent, clip=wordmark)
        return wordmark

    def parameter(self, clip: int, effect: int | str, name: str, value: Any) -> None:
        self.command("effects.setParam", {"clip": clip, "effect": effect, "param": name, "value": value})

    def picture(self, source: Source, start: int, end: int,
                box: tuple[float, float, float, float], *,
                crop: tuple[float, float, float, float] | None = None, track: str = "V2",
                source_frame: int = 0) -> None:
        """Put a source rectangle into a destination box using native transforms."""
        x, y, across, down = crop or (0, 0, source.width, source.height)
        x, y = max(0, x), max(0, y)
        across, down = min(source.width - x, across), min(source.height - y, down)
        if across <= 0 or down <= 0:
            raise SystemExit("The tour edit requested a crop outside its source image")
        cx, cy, width, height = box
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
        self.parameter(clip, "motion", "scale", min(width / across, height / down) * 100)

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
    picture_span = width - 2 * (54 if port else 48)
    panel = (middle, 1030, picture_span, 840) if port else (middle, 553, picture_span, 576)

    def moving(name: str, start: int, end: int, crop: tuple[float, float, float, float], *, box=panel) -> None:
        segment, video, _ = clips[name]
        edit.picture(video, start, end, box, crop=crop, source_frame=segment["startFrame"])

    def detail(name: str, start: int, end: int, *, pad: int = 0, box=panel,
               keep_height: float = 1) -> None:
        _, _, source = clips[name]
        x, y, w, h = details[name]
        crop = ((x - pad) * 2, (y - pad) * 2, (w + 2 * pad) * 2, (h * keep_height + 2 * pad) * 2)
        edit.picture(source, start, end, box, crop=crop)

    def tag(start: int, end: int, group: int, label: str, x: float, y: float, *, color: str = VIOLET) -> None:
        edit.text(start, end, label, x, y, 37 if port else 29, color, clip=group)

    opening = edit.heading(0, 5, "WAREHOUSE 4  /  FICTION", "The Blank Line", serif=True, poster=True)
    receipt_box = (middle, 1005, picture_span, 630) if port else (width * .71, 469, width * .50, 570)
    paper_crop = (114, 100, 872, 516)
    edit.picture(receipt, 0, 5, receipt_box, crop=paper_crop)
    tag(0, 5, opening, "The receiving signature is missing.", edit.left, 1410 if port else 382, color=GOLD)

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
    analysis_panel = (middle, 1020, picture_span, 790) if port else (width * .704, 495, width * .52, 590)
    detail("passage", 17, 20, box=analysis_panel, keep_height=.60)

    edit.heading(20, 23, "03  /  REVISION", "Compare the draft", background=LILAC)
    # The current file and draft both fit on a phone when cropped at their column boundaries.
    moving("compare", 20, 23, (522, 183, 795, 531) if port else (124, 179, 1190, 499))
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
    x, y, w, h = details["dossier"]
    moving("dossier", 27, 31, (x - 22, y - 53, w + 70, h + 69) if port else (x - 45, y - 75, w + 300, h + 70))
    returned = edit.heading(31, 36, "OFFICE LEDGER", "18:40", background=PAPER, subtitle="Cart 17 returned")
    ledger_box = panel if port else (middle, 550, picture_span, 510)
    edit.picture(ledger, 31, 36, ledger_box, crop=(114, 126, 872, 470 if port else 445))
    tag(31, 36, returned, "Fictional working exhibit", edit.left, 1480 if port else 841)

    joined = edit.heading(36, 42, "LEDGER  /  RECEIPT", "The same number", background=PAPER)
    edit.picture(ledger, 36, 42, (middle, 840, picture_span, 276) if port else (width * .268, 553, width * .43, 290),
                 crop=(148, 294, 801, 186))
    edit.picture(receipt, 36, 42, (middle, 1240, picture_span, 276) if port else (width * .732, 553, width * .43, 290),
                 crop=(148, 276, 801, 179), track="V3")
    tag(36, 42, joined, "18:40   /   RETURN", edit.left, 690 if port else 416)
    tag(36, 42, joined, "20:00   /   DISPATCH", edit.left if port else width * .52, 1090 if port else 416)

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

    edit.heading(52, 56, "06  /  EXPORT", "Share the evidence", background=PAPER)
    # Keep the download action above the bottom edge where player controls appear.
    export_box = panel if port else (middle, 521, picture_span, 510)
    moving("pdf", 52, 56, (277, 316, 924, 497) if port else (286, 319, 1080, 472), box=export_box)
    end = edit.heading(56, 60, "WAREHOUSE 4  /  EXHIBIT BOOK", "A saved dossier", background=PAPER)
    edit.picture(pdf, 56, 60, (middle, 825, picture_span, 236) if port else (middle, 406, picture_span, 194),
                 crop=(.11 * pdf.width, .084 * pdf.height, .78 * pdf.width, .1 * pdf.height))
    edit.picture(pdf, 56, 60, (middle, 1160, picture_span, 290) if port else (middle, 640, picture_span, 208),
                 crop=(.11 * pdf.width, .79 * pdf.height, .78 * pdf.width, .1 * pdf.height), track="V3")
    edit.text(56, 60, "Try the demo at lixity.de", edit.left, 1430 if port else 829, 39 if port else 30,
              VIOLET, clip=end, fade=True)
    logo_size = 54 if port else 40
    edit.picture(logo, 0, 60, (edit.left + logo_size / 2, 191 if port else 82, logo_size, logo_size), track="V5")

    for scene in plan["scenes"]:
        edit.marker(scene["id"], scene["start"])
    edit.marker("end", plan["duration"])
    edit.verify_fonts()
