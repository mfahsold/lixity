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
        self.left = 96 if self.port else 88
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
        wordmark = self.text(start, end, "Lixity", self.left + (78 if self.port else 54),
                             210 if self.port else 96, 46 if self.port else 34, foreground)
        self.text(start, end, kicker, self.left, 405 if self.port else 206 if poster else 180,
                  36 if self.port else 26, accent, clip=wordmark)
        self.text(start, end, title, self.left - int(serif) * 3,
                  550 if self.port else 318 if poster else 253,
                  (109 if serif else 72) if self.port else (77 if serif else 56),
                  foreground, serif=serif, clip=wordmark, fade=start == 0)
        if subtitle:
            self.text(start, end, subtitle, self.left, 637 if self.port else 312,
                      43 if self.port else 28, accent, clip=wordmark)
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
    span = width - 2 * edit.left
    panel = (middle, 1050, span, 720) if port else (middle, 563, span, 496)

    def moving(name: str, start: int, end: int, crop=None) -> None:
        segment, video, _ = clips[name]
        edit.picture(video, start, end, panel, crop=crop, source_frame=segment["startFrame"])

    def detail(name: str, start: int, end: int, *, pad: int = 0, box=panel,
               keep_height: float = 1) -> None:
        _, _, source = clips[name]
        x, y, w, h = details[name]
        crop = ((x - pad) * 2, (y - pad) * 2, (w + 2 * pad) * 2, (h * keep_height + 2 * pad) * 2)
        edit.picture(source, start, end, box, crop=crop)

    def tag(start: int, end: int, group: int, label: str, x: float, y: float, *, color: str = VIOLET) -> None:
        edit.text(start, end, label, x, y, 43 if port else 32, color, clip=group)

    opening = edit.heading(0, 5, "WAREHOUSE 4  /  FICTION", "The Blank Line", serif=True, poster=True)
    receipt_box = (middle, 1045, span, 600) if port else (width * .73, 469, width * .46, 530)
    paper_crop = (114, 100, 872, 516)
    edit.picture(receipt, 0, 5, receipt_box, crop=paper_crop)
    tag(0, 5, opening, "The receiving signature is missing.", edit.left, 1480 if port else 411, color=GOLD)

    edit.heading(5, 9, "01  /  MANUSCRIPT", "Read the passage")
    moving("read", 5, 9, (449, 70, 765, 640))
    reading = edit.heading(9, 14, "01  /  MANUSCRIPT", "From the draft")
    excerpt = recording["originalSentence"].split(" that she began", 1)[0]
    excerpt = excerpt.replace(" at it", "\nat it") if port else excerpt
    edit.text(9, 14, f"“{excerpt}…”", edit.left, 840 if port else 470, 61 if port else 55, PAPER,
              serif=True, clip=reading)
    detail("read", 9, 14, pad=12, box=(middle, 1280, span, 245) if port else (middle, 688, span, 194))

    edit.heading(14, 20, "02  /  EXPLANATION", "22 of 31 words", background=LILAC, subtitle="Counted as function words")
    x, y, w, h = details["passage"]
    if port:
        moving("passage", 14, 17, (x - 16, max(0, y - 70), w + 32, min(650, h + 90)))
    else:
        moving("passage", 14, 17)
    analysis_panel = (middle, 1086, span, 745) if port else (width * .714, 504, width * .48, 534)
    detail("passage", 17, 20, box=analysis_panel, keep_height=.60)

    edit.heading(20, 23, "03  /  REVISION", "Compare the draft", background=LILAC)
    moving("compare", 20, 23, (127, 207, 1186, 550) if port else None)
    compared = edit.heading(23, 27, "UNSAVED DRAFT  /  SAME SETTINGS", "31 to 12 words", background=LILAC)
    before = recording["originalSentence"].split(" that she began", 1)[0] + "…"
    after = recording["draftSentence"]
    second_column = edit.left if port else width * .53
    tag(23, 27, compared, "ORIGINAL EXCERPT", edit.left, 838 if port else 430)
    tag(23, 27, compared, "DRAFT", second_column, 1160 if port else 430)
    lines = (before.replace(" at it", "\nat it"), after.replace("why he", "\nwhy he")) if port else (
        before.replace(" she looked", "\nshe looked"), after.replace("why he", "\nwhy he"),
    )
    for line, column, row in zip(
        lines, (edit.left, second_column), (939, 1260) if port else (530, 530), strict=True,
    ):
        edit.text(23, 27, line, column, row, 56 if port else 41, INK, serif=True, clip=compared)

    edit.heading(27, 31, "04  /  RESEARCH", "The exhibit book", background=PAPER)
    moving("dossier", 27, 31, (285, 130, 960, 680) if port else None)
    returned = edit.heading(31, 36, "OFFICE LEDGER", "18:40", background=PAPER, subtitle="Cart 17 returned")
    edit.picture(ledger, 31, 36, panel, crop=(114, 126, 872, 470))
    tag(31, 36, returned, "Fictional working exhibit", edit.left, 1500 if port else 818)

    joined = edit.heading(36, 42, "LEDGER  /  RECEIPT", "The same number", background=PAPER)
    edit.picture(ledger, 36, 42, (middle, 872, span, 276) if port else (width * .28, 558, width * .40, 290),
                 crop=(148, 294, 801, 186))
    edit.picture(receipt, 36, 42, (middle, 1280, span, 276) if port else (width * .72, 558, width * .40, 290),
                 crop=(148, 276, 801, 179), track="V3")
    tag(36, 42, joined, "18:40   /   RETURN", edit.left, 720 if port else 432)
    tag(36, 42, joined, "20:00   /   DISPATCH", edit.left if port else width * .52, 1128 if port else 432)

    edit.heading(42, 47, "05  /  MANUSCRIPT", "Return to the text")
    moving("decision", 42, 44, (285, 110, 1060, 705) if port else None)
    detail("decision", 44, 47, pad=22)
    signed = edit.heading(47, 52, "WAREHOUSE 4  /  MANUSCRIPT", "The final line", serif=True, poster=True)
    quote = recording["closingSentence"]
    edit.text(47, 52, "“" + (quote.replace(" stayed", "\nstayed") if port else quote) + "”",
              edit.left, 910 if port else 502, 66 if port else 57, PAPER, serif=True, clip=signed)
    edit.picture(receipt, 47, 52,
                 (middle, 1190, span, 310) if port else (width * .71, 675, width * .47, 240),
                 crop=(148, 445, 801, 80))

    edit.heading(52, 56, "06  /  EXPORT", "Share the evidence", background=PAPER)
    moving("pdf", 52, 56, (265, 219, 1000, 650) if port else None)
    end = edit.heading(56, 60, "WAREHOUSE 4  /  EXHIBIT BOOK", "A saved dossier", background=PAPER)
    edit.picture(pdf, 56, 60, (middle, 838, span, 236) if port else (middle, 415, span, 150),
                 crop=(.11 * pdf.width, .084 * pdf.height, .78 * pdf.width, .1 * pdf.height))
    edit.picture(pdf, 56, 60, (middle, 1180, span, 290) if port else (middle, 647, span, 185),
                 crop=(.11 * pdf.width, .79 * pdf.height, .78 * pdf.width, .1 * pdf.height), track="V3")
    edit.text(56, 60, "Try the demo at lixity.de", edit.left, 1490 if port else 824, 44 if port else 32,
              VIOLET, clip=end, fade=True)
    edit.picture(logo, 0, 60, (edit.left + (29 if port else 21), 191 if port else 83, 58 if port else 42,
                              58 if port else 42), track="V5")

    for scene in plan["scenes"]:
        edit.marker(scene["id"], scene["start"])
    edit.marker("end", plan["duration"])
    edit.verify_fonts()
