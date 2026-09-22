"""
scripts/engine/layout.py
========================
Generic, renderer-independent layout configuration for book publications.

Pure data class (no PyCairo/Pango, no project hardcodings) so that
type-area presets are independently testable and reusable.
The three focused publication formats are:
- ``a4``          : lectorate copy (DIN A4, line numbers, correction margins)
- ``taschenbuch`` : print master (135 x 205 mm, justified, recto/verso)
- ``mobile``      : smartphone reading flow (108 x 192 mm, ragged right)
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class BookLayoutConfig:
    """Publishing and typographic layout configuration."""

    page_width: float  # in DTP points (1 pt = 1/72 inch)
    page_height: float
    margin_left: float
    margin_right: float
    margin_top: float
    margin_bottom: float

    # Rhythm & type area
    line_spacing: Optional[float] = None
    para_spacing: float = 4.5
    first_line_indent: float = 0.0
    justify_body: bool = True
    is_spread: bool = True

    # Structure & lectorate tools
    show_line_numbers: bool = False  # line numbers (lector anchor "p. x, l. y")
    line_number_gutter: float = 22.0  # width of the digit gutter left of the column
    line_number_font_size: float = 7.5
    hyphenate_body: bool = True  # Pyphen hyphenation for body text

    # Font family & styles
    font_family: str = "P052, Palatino, URW Palladio L, FreeSerif, serif"
    font_size_body: float = 9.8
    font_size_h1: float = 20.0
    font_size_h2: float = 14.5
    font_size_h3: float = 11.0
    font_size_quote: float = 9.0
    font_size_footer: float = 7.8
    font_size_footnote: float = 7.8

    # Front matter (page 1)
    title_sub_size: float = 12.0  # "Novel by Matthias Fahsold"
    title_status_size: float = 9.8  # status line (lectorate version etc.)
    title_contact_size: float = 8.0  # contact footer line
    pitch_heading_size: float = 11.5  # "About this novel"

    # Imprint & notes (page 2)
    imprint_top_offset: float = 10.0
    disclaimer_font_size: float = 8.0
    disclaimer_heading_size: float = 11.5
    disclaimer_heading_gap: float = 6.0
    disclaimer_gap: float = 3.5
    confidential_font_size: float = 7.5
    confidential_heading_size: float = 9.0
    confidential_heading_gap: float = 3.0
    confidential_gap: float = 3.0

    # Colour palette
    color_text: str = "#181818"
    color_heading: str = "#151515"
    color_muted: str = "#555555"
    color_footer: str = "#777777"
    color_border: Tuple[float, float, float] = (0.75, 0.75, 0.75)
    color_divider: Tuple[float, float, float] = (0.88, 0.88, 0.88)

    # Imprint
    contact_info: str = "Kontakt: mfahsold@googlemail.com · Hamburg, 2026"
    creator_engine: str = "Modern Markdown Book Publishing Engine (PDF 1.7)"

    @property
    def content_width(self) -> float:
        return self.page_width - self.margin_left - self.margin_right

    @property
    def content_height(self) -> float:
        return self.page_height - self.margin_top - self.margin_bottom

    @property
    def font_body(self) -> str:
        return f"{self.font_family} {self.font_size_body}"

    @property
    def font_h1(self) -> str:
        return f"{self.font_family} Bold {self.font_size_h1}"

    @property
    def font_h2(self) -> str:
        return f"{self.font_family} Bold {self.font_size_h2}"

    @property
    def font_h3(self) -> str:
        return f"{self.font_family} Bold {self.font_size_h3}"

    @property
    def font_quote(self) -> str:
        return f"{self.font_family} Italic {self.font_size_quote}"

    @property
    def font_footer(self) -> str:
        return f"{self.font_family} Italic {self.font_size_footer}"

    @property
    def font_footnote(self) -> str:
        return f"{self.font_family} Italic {self.font_size_footnote}"

    @classmethod
    def from_preset(
        cls, preset: str = "taschenbuch", font_family: Optional[str] = None
    ) -> "BookLayoutConfig":
        """Creates one of the three focused publication formats (a4, taschenbuch, mobile)."""
        family = font_family or "P052, Palatino, URW Palladio L, FreeSerif, serif"
        key = (preset or "taschenbuch").strip().lower()

        if key in ("a4", "lektorat", "manuskript"):
            # Lectorate copy / working draft (DIN A4, correction margins, line numbers)
            return cls(
                page_width=595.28,  # 210 mm
                page_height=841.89,  # 297 mm
                margin_left=62.0,  # incl. 22 pt digit gutter for line numbers
                margin_right=66.0,  # wide margin for handwritten lector notes
                margin_top=56.0,
                margin_bottom=56.0,
                line_spacing=None,  # natural leading: 17 pt at 12 pt (1.42x)
                para_spacing=6.0,  # airy paragraph spacing for annotations
                first_line_indent=0.0,
                justify_body=False,  # ragged right (manuscript norm, no whitespace rivers)
                is_spread=False,  # single-sided working flow
                show_line_numbers=True,
                line_number_gutter=22.0,
                line_number_font_size=7.5,
                hyphenate_body=False,  # no hyphenation in working drafts
                font_family=family,
                font_size_body=12.0,
                font_size_h1=22.0,
                font_size_h2=17.0,
                font_size_h3=13.0,
                font_size_quote=11.5,
                font_size_footer=9.5,
                font_size_footnote=9.0,
                title_sub_size=14.0,
                title_status_size=12.0,
                title_contact_size=10.0,
                pitch_heading_size=14.0,
                imprint_top_offset=14.0,
                disclaimer_font_size=10.5,
                disclaimer_heading_size=14.0,
                disclaimer_heading_gap=8.0,
                disclaimer_gap=5.0,
                confidential_font_size=10.0,
                confidential_heading_size=11.5,
                confidential_heading_gap=5.0,
                confidential_gap=4.0,
            )
        elif key in ("mobile", "smartphone", "phone"):
            # Format for mobile reading on smartphones (ragged right, ergonomic)
            return cls(
                page_width=306.14,  # 108 mm (9:16 aspect ratio)
                page_height=544.25,  # 192 mm
                margin_left=30.0,
                margin_right=30.0,
                margin_top=34.0,
                margin_bottom=40.0,
                line_spacing=0.88,  # approx. 12.4 pt baseline distance at 8.8 pt (1.41x)
                para_spacing=3.2,  # pleasant mobile reading flow
                first_line_indent=0.0,
                justify_body=False,  # ragged right against whitespace rivers on mobile devices
                is_spread=False,  # single-sided mobile reading flow
                font_family=family,
                font_size_body=8.8,  # ergonomically scaled for narrow displays (approx. 48-52 CPL)
                font_size_h1=16.5,
                font_size_h2=12.0,
                font_size_h3=9.5,
                font_size_quote=8.2,
                font_size_footer=7.2,
                font_size_footnote=7.2,
                title_sub_size=11.0,
                title_status_size=9.0,
                title_contact_size=7.2,
                pitch_heading_size=11.0,
                imprint_top_offset=4.0,
                disclaimer_font_size=7.6,
                disclaimer_heading_size=11.0,
                disclaimer_heading_gap=4.0,
                disclaimer_gap=2.2,
                confidential_font_size=7.0,
                confidential_heading_size=8.5,
                confidential_heading_gap=2.0,
                confidential_gap=2.0,
            )
        else:
            # Default: paperback (print, 135 x 205 mm, bibliophile KiWi/Suhrkamp literary typesetting)
            return cls(
                page_width=382.68,  # 135 mm
                page_height=581.10,  # 205 mm
                margin_left=46.0,  # gutter (increased for perfect binding)
                margin_right=42.0,  # outer margin
                margin_top=40.0,
                margin_bottom=48.0,
                line_spacing=0.88,  # approx. 12.0 pt baseline distance at 8.5 pt (1.41x)
                para_spacing=0.0,  # classic literary book typesetting without paragraph gaps
                first_line_indent=10.5,  # 1.25-em paragraph indent (except after headings/scene breaks)
                justify_body=True,  # justified for classic book layout
                is_spread=True,  # two-sided book typesetting with recto/verso running heads
                font_family=family,
                font_size_body=8.5,  # harmonious character count (approx. 55-60 CPL, calm justification)
                font_size_h1=17.5,
                font_size_h2=12.5,
                font_size_h3=9.8,
                font_size_quote=8.0,
                font_size_footer=7.2,
                font_size_footnote=7.2,
                title_sub_size=12.0,
                title_status_size=9.8,
                title_contact_size=8.0,
                pitch_heading_size=11.5,
                imprint_top_offset=10.0,
                disclaimer_font_size=8.0,
                disclaimer_heading_size=11.5,
                disclaimer_heading_gap=6.0,
                disclaimer_gap=3.5,
                confidential_font_size=7.5,
                confidential_heading_size=9.0,
                confidential_heading_gap=3.0,
                confidential_gap=3.0,
            )
