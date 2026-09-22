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

from .format import num as format_num
from .format import pct as format_pct
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
    "md_mtld": "Längeninvariante Vokabelvielfalt (McCarthy & Jarvis 2010).",
    "md_mattr": "Fensterstabile Type-Token-Ratio (Covington & McFall 2010).",
    "md_maas": "Vokabelkonzentration (Maas 1972; niedriger = reicher).",
    "md_flesch": "Sprachkalibrierte Lesbarkeitsformel des aktiven Sprachprofils.",
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
    # Punctuation display names (language-neutral keys in the metrics payload)
    "pname_periods": "Punkte (.)",
    "pname_commas": "Kommata (,)",
    "pname_dashes": "Gedankenstriche (–/—)",
    "pname_colons": "Doppelpunkte (:)",
    "pname_semicolons": "Semikolons (;)",
    "pname_questions": "Fragezeichen (?)",
    "pname_exclamations": "Ausrufezeichen (!)",
    "pname_ellipses": "Auslassungspunkte (…/...)",
    # Rich table 1 – reference & assessment (neutral)
    "t1_asl_ref": "8,0 – 11,5 W.",
    "t1_asl_note": "Prägnanter Satzbau.",
    "t1_median_ref": "7 – 9 Wörter",
    "t1_median_note": "Lakonischer Rhythmus.",
    "t1_std_ref": "5,5 – 7,5 Wörter",
    "t1_std_note": "Dynamische Satzlängen.",
    "t1_ttr_ref": "0,17 – 0,22",
    "t1_ttr_note": "Homogener Wortschatz.",
    "t1_yules_ref": "50,0 – 70,0",
    "t1_yules_note": "Stabiler Wortschatz.",
    "t1_mtld_ref": "≥ 60 (reich)",
    "t1_mtld_note": "Längeninvariante Vokabelvielfalt.",
    "t1_mattr_ref": "≥ 0,70 (reich)",
    "t1_mattr_note": "Fensterstabile Vielfalt.",
    "t1_maas_ref": "≤ 0,08 (reich)",
    "t1_maas_note": "Vokabelkonzentration (niedriger = reicher).",
    "t1_flesch_ref": "65,0 – 80,0",
    "t1_flesch_note": "Leichter Lesefluss.",
    "t1_lix_ref": "< 40 (leicht)",
    "t1_lix_note": "Zugängliche Prosa.",
    "t1_dialog_ref": "5,0 – 15,0 %",
    "t1_dialog_note": "Lebendige Dialoge.",
    "t1_filter_ref": "Minimiert",
    "t1_filter_note": "Minimiertes Telling.",
    # Rich table 2 – dramaturgical function (neutral)
    "t2_short": "Kurze Takte, Tempo.",
    "t2_medium": "Fließende Erzählung.",
    "t2_long": "Assoziative Sätze.",
    "t2_complex": "Komplexe Gedanken.",
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
        language_key: str = "de",
    ) -> None:
        """Renders a modern, highly aesthetic Rich terminal dashboard."""

        def _n(value: float, decimals: int = 1, signed: bool = False) -> str:
            return format_num(value, language_key, decimals, signed)

        def _p(value: float, decimals: int = 1) -> str:
            return format_pct(value, language_key, decimals)

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
            f"Umfang: {_n(m.raw_words, 0)} Wörter | {_n(m.raw_chars, 0)} Zeichen | {len(m.chapters)} Kapitel vollendet\n",
            style="dim white",
        )
        header_text.append(
            f"Normseiten: ~{_n(ns_250, 1)} NS (à 250 W.) | ~{_n(ns_1500, 1)} NS (à 1.500 Z.)",
            style="green",
        )
        con.print(Panel(header_text, border_style="cyan", box=box.ROUNDED))

        # Table 1: core metrics
        table1 = Table(
            title="Linguistische Kennzahlen & Stilistische DNA",
            box=box.SIMPLE_HEAVY,
            header_style="bold magenta",
        )
        table1.add_column("Metrik", style="bold white", no_wrap=True)
        table1.add_column("Messwert", justify="right", style="cyan", no_wrap=True)
        table1.add_column("Referenz / Zielkorridor", style="dim")
        table1.add_column("Literarische Bewertung", style="yellow")

        table1.add_row(
            "Mittlere Satzlänge (ASL)",
            f"{_n(m.asl, 2)} W./Satz",
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
            f"{_n(m.std_sl, 2)} Wörter",
            _t(texts, "t1_std_ref"),
            _t(texts, "t1_std_note"),
        )
        table1.add_row(
            "Lexikalische Diversität (TTR)",
            f"{_n(m.ttr, 4)}",
            _t(texts, "t1_ttr_ref"),
            _t(texts, "t1_ttr_note"),
        )
        table1.add_row(
            "Yule's Characteristic K",
            f"{_n(m.yules_k, 2)}",
            _t(texts, "t1_yules_ref"),
            _t(texts, "t1_yules_note"),
        )
        table1.add_row(
            "MTLD (Textual Lexical Diversity)",
            f"{_n(m.mtld, 1)}" if m.mtld is not None else "–",
            _t(texts, "t1_mtld_ref"),
            _t(texts, "t1_mtld_note"),
        )
        table1.add_row(
            "MATTR (Moving-Average TTR)",
            f"{_n(m.mattr, 3)}" if m.mattr is not None else "–",
            _t(texts, "t1_mattr_ref"),
            _t(texts, "t1_mattr_note"),
        )
        table1.add_row(
            "Maas a²",
            f"{_n(m.maas_a2, 4)}" if m.maas_a2 is not None else "–",
            _t(texts, "t1_maas_ref"),
            _t(texts, "t1_maas_note"),
        )
        table1.add_row(
            m.flesch_variant or "Flesch Reading Ease",
            f"{_n(m.flesch_de, 1)}",
            _t(texts, "t1_flesch_ref"),
            _t(texts, "t1_flesch_note"),
        )
        table1.add_row(
            "LIX-Lesbarkeitsindex",
            f"{_n(m.lix, 1)}",
            _t(texts, "t1_lix_ref"),
            _t(texts, "t1_lix_note"),
        )
        table1.add_row(
            "Dialogquote",
            f"{_p(m.dialog_ratio, 2)}",
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
        table2.add_column("Kategorie", style="bold white", no_wrap=True)
        table2.add_column("Kriterium", style="dim", no_wrap=True)
        table2.add_column("Anzahl", justify="right", style="cyan")
        table2.add_column("Anteil", justify="right", style="green")
        table2.add_column("Funktion")

        d = m.sentence_dist
        table2.add_row(
            "Kurzsätze (Staccato)",
            "≤ 6 Wörter",
            f"{_n(d.short_count, 0)}",
            f"{_p(d.short_pct, 1)}",
            _t(texts, "t2_short"),
        )
        table2.add_row(
            "Mittlere Sätze (Norm)",
            "7–15 Wörter",
            f"{_n(d.medium_count, 0)}",
            f"{_p(d.medium_pct, 1)}",
            _t(texts, "t2_medium"),
        )
        table2.add_row(
            "Lange Sätze (Erweiterung)",
            "16–25 Wörter",
            f"{_n(d.long_count, 0)}",
            f"{_p(d.long_pct, 1)}",
            _t(texts, "t2_long"),
        )
        table2.add_row(
            "Komplexe Hypotaxen",
            "> 25 Wörter",
            f"{_n(d.complex_count, 0)}",
            f"{_p(d.complex_pct, 1)}",
            _t(texts, "t2_complex"),
        )
        con.print(table2)

    @staticmethod
    def format_markdown_report(
        m: CorpusMetrics,
        texts: Mapping[str, str] | None = None,
        language_key: str = "de",
    ) -> str:
        """Generates GitHub-Flavored Markdown for embedding into dossiers."""

        def _n(value: float, decimals: int = 1, signed: bool = False) -> str:
            return format_num(value, language_key, decimals, signed)

        def _p(value: float, decimals: int = 1) -> str:
            return format_pct(value, language_key, decimals)

        ns_250 = m.raw_words / 250.0
        ns_1500 = m.raw_chars / 1500.0

        lines = [
            _t(texts, "sec_1_1"),
            "",
            "| Linguistische Metrik | Gemessener Wert | Einordnung & Referenzbereich |",
            "| :--- | :--- | :--- |",
            f"| **Gesamtwortzahl (Volltext inkl. Anhang)** | **{_n(m.raw_words, 0)} Wörter** ({_n(m.raw_chars, 0)} Zeichen) | {_t(texts, 'md_raw_words')} (~{_n(ns_250, 1)} Normseiten à 250 W. / {_n(ns_1500, 1)} NS à 1.500 Z.). |",
            f"| **Wortzahl Haupttext (Reine Romanprosa)** | **{_n(m.clean_words, 0)} Wörter** ({_n(m.clean_chars, 0)} Zeichen) | {_t(texts, 'md_clean_words')} ({len(m.chapters)} Kapitel). |",
            f"| **Satz-Gesamtzahl (Haupttext)** | **{_n(m.total_sentences, 0)} Sätze** | {_t(texts, 'md_sentences')} |",
            f"| **Mittlere Satzlänge (ASL)** | **{_n(m.asl, 2)} Wörter / Satz** | {_t(texts, 'md_asl')} |",
            f"| **Median der Satzlänge** | **{m.median_sl} Wörter** | {_t(texts, 'md_median')} |",
            f"| **Standardabweichung Satzlänge** | **{_n(m.std_sl, 2)} Wörter** | {_t(texts, 'md_std')} |",
            f"| **Lexikalische Diversität (TTR)** | **{_n(m.ttr, 4)}** (V = {_n(m.vocab_types, 0)} bei N = {_n(m.tokens, 0)}) | {_t(texts, 'md_ttr')} |",
            f"| **Guiraud-Index R ($V / \\sqrt{{N}}$)** | **{_n(m.guiraud_r, 2)}** | {_t(texts, 'md_guiraud')} |",
            f"| **Yule's Characteristic K** | **{_n(m.yules_k, 2)}** | {_t(texts, 'md_yules')} |",
            f"| **MTLD** | **{f'{_n(m.mtld, 1)}' if m.mtld is not None else '–'}** | {_t(texts, 'md_mtld')} |",
            f"| **MATTR** | **{f'{_n(m.mattr, 3)}' if m.mattr is not None else '–'}** | {_t(texts, 'md_mattr')} |",
            f"| **Maas a²** | **{f'{_n(m.maas_a2, 4)}' if m.maas_a2 is not None else '–'}** | {_t(texts, 'md_maas')} |",
            f"| **{m.flesch_variant or 'Flesch Reading Ease'}** | **ca. {_n(m.flesch_de, 1)}** | {_t(texts, 'md_flesch')} |",
            f"| **LIX (Lesbarkeitsindex)** | **{_n(m.lix, 1)}** | {_t(texts, 'md_lix')} |",
            f"| **Dialogquote (Wörtliche Rede)** | **{_n(m.dialog_words, 0)} Wörter ({_p(m.dialog_ratio, 2)})** | {_t(texts, 'md_dialog')} |",
            f"| **Fließprosa-Absätze** | **{m.total_paragraphs} Absätze** (Mittelwert: {_n(m.avg_paragraph_len, 1)} W./Absatz) | {_t(texts, 'md_paras')} |",
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
            f"| **Kurzsätze (Staccato)** | $\\le 6$ Wörter | **{_n(d.short_count, 0)}** | **{_p(d.short_pct, 1)}** | {_t(texts, 'md_short')} |"
        )
        lines.append(
            f"| **Mittlere Sätze (Normprosa)** | 7–15 Wörter | **{_n(d.medium_count, 0)}** | **{_p(d.medium_pct, 1)}** | {_t(texts, 'md_medium')} |"
        )
        lines.append(
            f"| **Lange Sätze (Erweiterung)** | 16–25 Wörter | **{_n(d.long_count, 0)}** | **{_p(d.long_pct, 1)}** | {_t(texts, 'md_long')} |"
        )
        lines.append(
            f"| **Komplexe Hypotaxen** | $> 25$ Wörter | **{_n(d.complex_count, 0)}** | **{_p(d.complex_pct, 1)}** | {_t(texts, 'md_complex')} |"
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

        punct_names = {
            "periods": "Punkte (.)",
            "commas": "Kommata (,)",
            "dashes": "Gedankenstriche (–/—)",
            "colons": "Doppelpunkte (:)",
            "semicolons": "Semikolons (;)",
            "questions": "Fragezeichen (?)",
            "exclamations": "Ausrufezeichen (!)",
            "ellipses": "Auslassungspunkte (…/...)",
        }
        punct_text_keys = {
            "periods": "punct_Punkte",
            "commas": "punct_Kommata",
            "dashes": "punct_Gedankenstriche",
            "colons": "punct_Doppelpunkte",
            "semicolons": "punct_Semikolons",
            "questions": "punct_Fragezeichen",
            "exclamations": "punct_Ausrufezeichen",
            "ellipses": "punct_Auslassungspunkte",
        }
        for k, v in m.punctuation.items():
            density = (v / m.clean_words) * 1000.0 if m.clean_words else 0.0
            fn = _t(texts, punct_text_keys.get(k, ""))
            name = _t(texts, f"pname_{k}") or punct_names.get(k, k)
            lines.append(f"| **{name}** | {_n(v, 0)} | {_n(density, 1)} | {fn} |")

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
                f"| {c.num:02d} | {c.title} | {_n(c.words, 0)} | {c.sentences} | "
                f"{_n(c.asl, 1)} | {_p(c.dialog_pct, 1)} | {_n(c.ttr, 3)} |"
                f"{motifs} {c.filter_verbs} | {c.dominance} |"
            )

        return "\n".join(lines)

    @staticmethod
    def to_json(m: CorpusMetrics, indent: bool = True) -> str:
        """Serialises CorpusMetrics with orjson."""
        opts = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(m.model_dump(), option=opts).decode("utf-8")
