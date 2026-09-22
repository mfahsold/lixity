"""lixity.formatters – Presentation layer for corpus metrics and stylometric reports.

Supports Rich terminal dashboards, GitHub-Flavored Markdown tables,
and strict orjson serialization for automated consumption.
"""

from collections.abc import Mapping

import orjson
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import CorpusMetrics

DEFAULT_TEXTE: dict[str, str] = {
    # Structure (Markdown report)
    "sec_1_1": "### 1.1 Gesamtkorpus-Kennzahlen",
    "sec_1_2": "### 1.2 Satzlängen-Architektur & Rhythmusprofil",
    "sec_1_3": "### 1.3 Interpunktion als stilistischer Seismograf",
    "sec_1_4": "### 1.4 Kapitelweise Vergleichsmatrix (Linguistische Tiefenprofile)",
    "md_col_tempus": "Dominantes Tempus",
    "md_intro_sentence": "Die empirische Verteilung der Sätze des Haupttextes:",
    # Markdown 1.1 – assessments (neutral)
    "md_raw_words": "Volltext inklusive Anhang.",
    "md_clean_words": "Reine Romanprosa.",
    "md_sentences": "Satzgesamtzahl des Haupttextes.",
    "md_asl": "Mittlere Satzlänge des Haupttextes.",
    "md_median": "Median der Satzlänge.",
    "md_std": "Streuung der Satzlängen.",
    "md_ttr": "Lexikalische Diversität (Type-Token-Ratio).",
    "md_guiraud": "Längenstabilisierte lexikalische Streuung.",
    "md_yules": "Stabilität des Wortschatzes über die Textlänge.",
    "md_flesch": "Lesbarkeit nach Flesch (deutsche Adaption).",
    "md_lix": "Lesbarkeitsindex (LIX).",
    "md_dialog": "Anteil wörtlicher Rede an der Prosa.",
    "md_paras": "Absatzökonomie des Haupttextes.",
    # Markdown 1.2 – sentence-length functions (neutral)
    "md_short": "Kurze Takte und Handlungsbefehle.",
    "md_medium": "Handlungsfortgang und Anschauung.",
    "md_long": "Assoziative Erweiterungen.",
    "md_complex": "Hypotaxen; bewusst begrenzt.",
    # Markdown 1.3 – punctuation functions (neutral)
    "punct_Punkte": "Grundtakt der Satzbildung.",
    "punct_Kommata": "Aufzählungen und Beisätze.",
    "punct_Gedankenstriche": "Nachklapp, Selbstkorrektur, Einschub.",
    "punct_Doppelpunkte": "Ankündigung von Listen, Zitaten, Einsichten.",
    "punct_Fragezeichen": "Selbstbefragung und Dialog.",
    "punct_Ausrufezeichen": "Sparsam dosiert.",
    "punct_Semikolons": "Selten; vermeidet dozierenden Ton.",
    "punct_Auslassungspunkte": "Abreißen des Gedankens.",
    # Rich table 1 – reference & assessment (neutral)
    "t1_asl_ref": "8,0 – 11,5 W.",
    "t1_asl_note": "Kurze, parataktische Struktur.",
    "t1_median_ref": "7 – 9 Wörter",
    "t1_median_note": "Lakonischer Rhythmus.",
    "t1_std_ref": "5,5 – 7,5 Wörter",
    "t1_std_note": "Dynamik zwischen Fragment und Kaskade.",
    "t1_ttr_ref": "0,17 – 0,22",
    "t1_ttr_note": "Homogene Lexik.",
    "t1_yules_ref": "50,0 – 70,0",
    "t1_yules_note": "Stabiles Erzähleridiom.",
    "t1_flesch_ref": "65,0 – 80,0",
    "t1_flesch_note": "Leichter Lesefluss.",
    "t1_lix_ref": "< 40 (leicht/flüssig)",
    "t1_lix_note": "Zugängliche Prosa.",
    "t1_dialog_ref": "5,0 – 15,0 %",
    "t1_dialog_note": "Dialoganteil der Prosa.",
    "t1_filter_ref": "Minimiert",
    "t1_filter_note": "Geringe Telling-Dichte.",
    # Rich table 2 – dramaturgical function (neutral)
    "t2_short": "Kurze Takte, Handlungsbefehle.",
    "t2_medium": "Handlungsfortgang und Anschauung.",
    "t2_long": "Assoziative Erweiterungen.",
    "t2_complex": "Hypotaxen; bewusst begrenzt.",
}


def _t(texts: Mapping[str, str] | None, key: str) -> str:
    """Returns the project text or the neutral engine default."""
    if texts and key in texts:
        return texts[key]
    return DEFAULT_TEXTE.get(key, "")


class ReportFormatter:
    """Formatting of corpus data for terminal, Markdown and JSON."""

    @staticmethod
    def print_rich_report(
        m: CorpusMetrics,
        console: Console | None = None,
        texts: Mapping[str, str] | None = None,
    ) -> None:
        """Renders a modern, highly aesthetic Rich terminal dashboard."""
        con = console or Console()
        con.print()
        ns_250 = m.raw_words / 250.0
        ns_1500 = m.raw_chars / 1500.0

        # Title panel
        header_text = Text()
        header_text.append(
            "📖 Korpuslinguistische Textanalyse & Manuskriptprofil\n", style="bold cyan"
        )
        header_text.append(
            f"Umfang: {m.raw_words:,} Wörter | {m.raw_chars:,} Zeichen | {len(m.chapters)} Kapitel vollendet\n",
            style="dim white",
        )
        header_text.append(
            f"Normseiten: ~{ns_250:.1f} NS (à 250 W.) | ~{ns_1500:.1f} NS (à 1.500 Z.)",
            style="green",
        )
        con.print(Panel(header_text, border_style="cyan", box=box.ROUNDED))

        # Table 1: core metrics
        table1 = Table(
            title="Linguistische Kennzahlen & Stilistische DNA",
            box=box.SIMPLE_HEAVY,
            header_style="bold magenta",
        )
        table1.add_column("Metrik", style="bold white")
        table1.add_column("Messwert", justify="right", style="cyan")
        table1.add_column("Referenz / Zielkorridor", style="dim")
        table1.add_column("Literarische Bewertung", style="yellow")

        table1.add_row(
            "Mittlere Satzlänge (ASL)",
            f"{m.asl:.2f} W./Satz",
            _t(texts, "t1_asl_ref"),
            _t(texts, "t1_asl_note"),
        )
        table1.add_row(
            "Median der Satzlänge",
            f"{m.median_sl} Wörter",
            _t(texts, "t1_median_ref"),
            _t(texts, "t1_median_note"),
        )
        table1.add_row(
            "Standardabweichung",
            f"{m.std_sl:.2f} Wörter",
            _t(texts, "t1_std_ref"),
            _t(texts, "t1_std_note"),
        )
        table1.add_row(
            "Lexikalische Diversität (TTR)",
            f"{m.ttr:.4f}",
            _t(texts, "t1_ttr_ref"),
            _t(texts, "t1_ttr_note"),
        )
        table1.add_row(
            "Yule's Characteristic K",
            f"{m.yules_k:.2f}",
            _t(texts, "t1_yules_ref"),
            _t(texts, "t1_yules_note"),
        )
        table1.add_row(
            "Flesch Reading Ease (DE)",
            f"{m.flesch_de:.1f}",
            _t(texts, "t1_flesch_ref"),
            _t(texts, "t1_flesch_note"),
        )
        table1.add_row(
            "LIX-Lesbarkeitsindex",
            f"{m.lix:.1f}",
            _t(texts, "t1_lix_ref"),
            _t(texts, "t1_lix_note"),
        )
        table1.add_row(
            "Dialogquote",
            f"{m.dialog_ratio:.2f} %",
            _t(texts, "t1_dialog_ref"),
            _t(texts, "t1_dialog_note"),
        )
        table1.add_row(
            "Perzeptionsfilter (Showing)",
            f"{m.filter_count} Belege",
            _t(texts, "t1_filter_ref"),
            _t(texts, "t1_filter_note"),
        )
        con.print(table1)

        # Table 2: sentence-length distribution
        table2 = Table(
            title="Satzlängen-Architektur & Rhythmisierung",
            box=box.SIMPLE,
            header_style="bold green",
        )
        table2.add_column("Kategorie", style="bold white")
        table2.add_column("Kriterium", style="dim")
        table2.add_column("Anzahl", justify="right", style="cyan")
        table2.add_column("Anteil", justify="right", style="green")
        table2.add_column("Funktion")

        d = m.sentence_dist
        table2.add_row(
            "Kurzsätze (Staccato)",
            "≤ 6 Wörter",
            f"{d.short_count:,}",
            f"{d.short_pct:.1f} %",
            _t(texts, "t2_short"),
        )
        table2.add_row(
            "Mittlere Sätze (Norm)",
            "7–15 Wörter",
            f"{d.medium_count:,}",
            f"{d.medium_pct:.1f} %",
            _t(texts, "t2_medium"),
        )
        table2.add_row(
            "Lange Sätze (Erweiterung)",
            "16–25 Wörter",
            f"{d.long_count:,}",
            f"{d.long_pct:.1f} %",
            _t(texts, "t2_long"),
        )
        table2.add_row(
            "Komplexe Hypotaxen",
            "> 25 Wörter",
            f"{d.complex_count:,}",
            f"{d.complex_pct:.1f} %",
            _t(texts, "t2_complex"),
        )
        con.print(table2)

    @staticmethod
    def format_markdown_report(m: CorpusMetrics, texts: Mapping[str, str] | None = None) -> str:
        """Generates GitHub-Flavored Markdown for embedding into dossiers."""
        ns_250 = m.raw_words / 250.0
        ns_1500 = m.raw_chars / 1500.0

        lines = [
            _t(texts, "sec_1_1"),
            "",
            "| Linguistische Metrik | Gemessener Wert | Einordnung & Referenzbereich |",
            "| :--- | :--- | :--- |",
            f"| **Gesamtwortzahl (Volltext inkl. Anhang)** | **{m.raw_words:,} Wörter** ({m.raw_chars:,} Zeichen) | {_t(texts, 'md_raw_words')} (~{ns_250:.1f} Normseiten à 250 W. / {ns_1500:.1f} NS à 1.500 Z.). |",
            f"| **Wortzahl Haupttext (Reine Romanprosa)** | **{m.clean_words:,} Wörter** ({m.clean_chars:,} Zeichen) | {_t(texts, 'md_clean_words')} ({len(m.chapters)} Kapitel). |",
            f"| **Satz-Gesamtzahl (Haupttext)** | **{m.total_sentences:,} Sätze** | {_t(texts, 'md_sentences')} |",
            f"| **Mittlere Satzlänge (ASL)** | **{m.asl:.2f} Wörter / Satz** | {_t(texts, 'md_asl')} |",
            f"| **Median der Satzlänge** | **{m.median_sl} Wörter** | {_t(texts, 'md_median')} |",
            f"| **Standardabweichung Satzlänge** | **{m.std_sl:.2f} Wörter** | {_t(texts, 'md_std')} |",
            f"| **Lexikalische Diversität (TTR)** | **{m.ttr:.4f}** (V = {m.vocab_types:,} bei N = {m.tokens:,}) | {_t(texts, 'md_ttr')} |",
            f"| **Guiraud-Index R ($V / \\sqrt{{N}}$)** | **{m.guiraud_r:.2f}** | {_t(texts, 'md_guiraud')} |",
            f"| **Yule's Characteristic K** | **{m.yules_k:.2f}** | {_t(texts, 'md_yules')} |",
            f"| **Flesch Reading Ease (DE-Adaption)** | **ca. {m.flesch_de:.1f}** | {_t(texts, 'md_flesch')} |",
            f"| **LIX (Lesbarkeitsindex)** | **{m.lix:.1f}** | {_t(texts, 'md_lix')} |",
            f"| **Dialogquote (Wörtliche Rede)** | **{m.dialog_words:,} Wörter ({m.dialog_ratio:.2f} %)** | {_t(texts, 'md_dialog')} |",
            f"| **Fließprosa-Absätze** | **{m.total_paragraphs} Absätze** (Mittelwert: {m.avg_paragraph_len:.1f} W./Absatz) | {_t(texts, 'md_paras')} |",
            "",
            "---",
            "",
            _t(texts, "sec_1_2"),
            "",
            _t(texts, "md_intro_sentence"),
            "",
            "| Satzlängen-Kategorie | Kriterium | Anzahl Sätze | Prozentualer Anteil | Funktion |",
            "| :--- | :--- | ---:| ---:| :--- |",
        ]

        d = m.sentence_dist
        lines.append(
            f"| **Kurzsätze (Staccato)** | $\\le 6$ Wörter | **{d.short_count:,}** | **{d.short_pct:.1f} %** | {_t(texts, 'md_short')} |"
        )
        lines.append(
            f"| **Mittlere Sätze (Normprosa)** | 7–15 Wörter | **{d.medium_count:,}** | **{d.medium_pct:.1f} %** | {_t(texts, 'md_medium')} |"
        )
        lines.append(
            f"| **Lange Sätze (Erweiterung)** | 16–25 Wörter | **{d.long_count:,}** | **{d.long_pct:.1f} %** | {_t(texts, 'md_long')} |"
        )
        lines.append(
            f"| **Komplexe Hypotaxen** | $> 25$ Wörter | **{d.complex_count:,}** | **{d.complex_pct:.1f} %** | {_t(texts, 'md_complex')} |"
        )

        lines.extend(
            [
                "",
                "---",
                "",
                _t(texts, "sec_1_3"),
                "",
                "| Satzzeichen | Häufigkeit | Dichte (pro 1.000 Wörter) | Funktion |",
                "| :--- | ---:| ---:| :--- |",
            ]
        )

        for k, v in m.punctuation.items():
            density = (v / m.clean_words) * 1000.0 if m.clean_words else 0.0
            fn = ""
            for prefix, key in (
                ("Punkte", "punct_Punkte"),
                ("Kommata", "punct_Kommata"),
                ("Gedankenstriche", "punct_Gedankenstriche"),
                ("Doppelpunkte", "punct_Doppelpunkte"),
                ("Fragezeichen", "punct_Fragezeichen"),
                ("Ausrufezeichen", "punct_Ausrufezeichen"),
                ("Semikolons", "punct_Semikolons"),
                ("Auslassungspunkte", "punct_Auslassungspunkte"),
            ):
                if prefix in k:
                    fn = _t(texts, key)
                    break
            lines.append(f"| **{k}** | {v:,} | {density:.1f} | {fn} |")

        # Chapter matrix: motif columns dynamically from motif_counts
        motif_keys: list = []
        for c in m.chapters:
            for key in c.motif_counts:
                if key not in motif_keys:
                    motif_keys.append(key)

        header = "| Kap. | Titel | Wörter | Sätze | ASL | Dialog-% | TTR |"
        separator = "| :--- | :--- | ---:| ---:| ---:| ---:| ---:|"
        for key in motif_keys:
            header += f" {key} |"
            separator += " ---:|"
        header += " Filterverben | " + _t(texts, "md_col_tempus") + " |"
        separator += " ---:| :--- |"

        lines.extend(["", "---", "", _t(texts, "sec_1_4"), "", header, separator])

        for c in m.chapters:
            motifs = "".join(f" {c.motif_counts.get(key, 0)} |" for key in motif_keys)
            lines.append(
                f"| {c.num:02d} | {c.title} | {c.words:,} | {c.sentences} | "
                f"{c.asl:.1f} | {c.dialog_pct:.1f} % | {c.ttr:.3f} |"
                f"{motifs} {c.filter_verbs} | {c.dominance} |"
            )

        return "\n".join(lines)

    @staticmethod
    def to_json(m: CorpusMetrics, indent: bool = True) -> str:
        """Serialises CorpusMetrics with orjson."""
        opts = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(m.model_dump(), option=opts).decode("utf-8")
