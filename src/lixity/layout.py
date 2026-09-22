"""
scripts/engine/layout.py
========================
Generische, renderer-unabhängige Layout-Konfiguration für Buch-Publikationen.

Reine Dataklasse (kein PyCairo/Pango, keine Projekt-Hardcodings), damit
Satzspiegel-Presets unabhängig testbar und wiederverwendbar sind.
Die drei fokussierten Publikationsformate sind:
- ``a4``          : Lektoratsexemplar (DIN A4, Zeilennummern, Korrekturränder)
- ``taschenbuch`` : Druckvorlage (135 x 205 mm, Blocksatz, Recto/Verso)
- ``mobile``      : Smartphone-Lesefluss (108 x 192 mm, Flattersatz)
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class BookLayoutConfig:
    """Verlags- und typografische Layout-Konfiguration."""

    page_width: float  # in DTP-Punkten (1 pt = 1/72 Zoll)
    page_height: float
    margin_left: float
    margin_right: float
    margin_top: float
    margin_bottom: float

    # Rhythmus & Satzspiegel
    line_spacing: Optional[float] = None
    para_spacing: float = 4.5
    first_line_indent: float = 0.0
    justify_body: bool = True
    is_spread: bool = True

    # Struktur- & Lektoratswerkzeuge
    show_line_numbers: bool = False  # Zeilennummern (Lektoren-Anker "S. x, Z. y")
    line_number_gutter: float = 22.0  # Breite des Ziffern-Kanals links der Spalte
    line_number_font_size: float = 7.5
    hyphenate_body: bool = True  # Pyphen-Silbentrennung für Fließtext

    # Schriftfamilie & Stile
    font_family: str = "P052, Palatino, URW Palladio L, FreeSerif, serif"
    font_size_body: float = 9.8
    font_size_h1: float = 20.0
    font_size_h2: float = 14.5
    font_size_h3: float = 11.0
    font_size_quote: float = 9.0
    font_size_footer: float = 7.8
    font_size_footnote: float = 7.8

    # Titelei (Seite 1)
    title_sub_size: float = 12.0  # "Roman von Matthias Fahsold"
    title_status_size: float = 9.8  # Statuszeile (Lektoratsfassung etc.)
    title_contact_size: float = 8.0  # Kontaktfußzeile
    pitch_heading_size: float = 11.5  # "Über diesen Roman"

    # Impressum & Hinweise (Seite 2)
    imprint_top_offset: float = 10.0
    disclaimer_font_size: float = 8.0
    disclaimer_heading_size: float = 11.5
    disclaimer_heading_gap: float = 6.0
    disclaimer_gap: float = 3.5
    confidential_font_size: float = 7.5
    confidential_heading_size: float = 9.0
    confidential_heading_gap: float = 3.0
    confidential_gap: float = 3.0

    # Farbpalette
    color_text: str = "#181818"
    color_heading: str = "#151515"
    color_muted: str = "#555555"
    color_footer: str = "#777777"
    color_border: Tuple[float, float, float] = (0.75, 0.75, 0.75)
    color_divider: Tuple[float, float, float] = (0.88, 0.88, 0.88)

    # Impressum
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
        """Erzeugt eines der drei fokussierten Publikationsformate (a4, taschenbuch, mobile)."""
        family = font_family or "P052, Palatino, URW Palladio L, FreeSerif, serif"
        key = (preset or "taschenbuch").strip().lower()

        if key in ("a4", "lektorat", "manuskript"):
            # Lektoratsexemplar / Arbeitsfassung (DIN A4, Korrekturränder, Zeilennummern)
            return cls(
                page_width=595.28,  # 210 mm
                page_height=841.89,  # 297 mm
                margin_left=62.0,  # inkl. 22 pt Ziffern-Kanal für Zeilennummern
                margin_right=66.0,  # breiter Rand für handschriftliche Lektoren-Notizen
                margin_top=56.0,
                margin_bottom=56.0,
                line_spacing=None,  # natürlicher Durchschuss: 17 pt bei 12 pt (1.42x)
                para_spacing=6.0,  # luftige Absatzabstände für Anmerkungen
                first_line_indent=0.0,
                justify_body=False,  # Flattersatz (Manuskriptnorm, keine Weißraumgassen)
                is_spread=False,  # Einzelseitiger Arbeitsfluss
                show_line_numbers=True,
                line_number_gutter=22.0,
                line_number_font_size=7.5,
                hyphenate_body=False,  # keine Silbentrennung in Arbeitsfassungen
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
            # Format für mobiles Lesen auf Smartphones (Flattersatz, ergonomisch)
            return cls(
                page_width=306.14,  # 108 mm (9:16 Aspect Ratio)
                page_height=544.25,  # 192 mm
                margin_left=30.0,
                margin_right=30.0,
                margin_top=34.0,
                margin_bottom=40.0,
                line_spacing=0.88,  # ca. 12.4 pt Grundlinienabstand bei 8.8 pt (1.41x)
                para_spacing=3.2,  # Angenehmer mobiler Lesefluss
                first_line_indent=0.0,
                justify_body=False,  # Flattersatz gegen Weißraumgassen auf Mobilgeräten
                is_spread=False,  # Einzelseitiger mobiler Lesefluss
                font_family=family,
                font_size_body=8.8,  # Ergonomisch skaliert für schmale Displays (ca. 48-52 CPL)
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
            # Standard: Taschenbuch (Print, 135 x 205 mm, bibliophiler KiWi/Suhrkamp-Belletristiksatz)
            return cls(
                page_width=382.68,  # 135 mm
                page_height=581.10,  # 205 mm
                margin_left=46.0,  # Bundsteg (erhöht für Klebebindung)
                margin_right=42.0,  # Außensteg
                margin_top=40.0,
                margin_bottom=48.0,
                line_spacing=0.88,  # ca. 12.0 pt Grundlinienabstand bei 8.5 pt (1.41x)
                para_spacing=0.0,  # Klassischer belletristischer Buchsatz ohne Absatzlücken
                first_line_indent=10.5,  # 1.25-Geviert Absatzeinzug (außer nach Überschriften/Szenenwechsel)
                justify_body=True,  # Blocksatz für klassisches Buchlayout
                is_spread=True,  # Doppelseitiger Buchsatz mit Recto/Verso-Kolumnentiteln
                font_family=family,
                font_size_body=8.5,  # Harmonische Zeichenzahl (ca. 55-60 CPL, ruhiger Blocksatz)
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
