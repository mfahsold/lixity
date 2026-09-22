"""lixity.formatters – Presentation layer for corpus metrics and stylometric reports.

Supports Rich terminal dashboards, GitHub-Flavored Markdown tables,
and strict orjson serialization for automated consumption.

Report texts come in two layers: an engine pack per language (English is the
default, German is shipped as well) and optional project texts that override
single keys. Project-specific reference corridors and assessments are **not**
part of the engine packs – projects supply them via ``texts``.
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

REPORT_TEXTS_EN: dict[str, str] = {
    # Structure (Markdown report)
    "sec_1_1": "### 1.1 Corpus metrics",
    "sec_1_2": "### 1.2 Sentence-length architecture & rhythm",
    "sec_1_3": "### 1.3 Punctuation as a stylistic seismograph",
    "sec_1_4": "### 1.4 Chapter comparison matrix (linguistic deep profiles)",
    "md_col_tempus": "Dominant tense",
    "md_intro_sentence": "The empirical sentence distribution of the main text:",
    # Markdown 1.1 – neutral notes
    "md_raw_words": "Full text including the appendix.",
    "md_clean_words": "Prose only.",
    "md_sentences": "Total sentences of the main text.",
    "md_asl": "Average sentence length of the main text.",
    "md_median": "Median sentence length.",
    "md_std": "Spread of sentence lengths.",
    "md_ttr": "Lexical diversity (type-token ratio).",
    "md_guiraud": "Length-stabilised lexical spread.",
    "md_yules": "Vocabulary stability across text length.",
    "md_mtld": "Length-invariant vocabulary richness (McCarthy & Jarvis 2010).",
    "md_mattr": "Window-stable type-token ratio (Covington & McFall 2010).",
    "md_maas": "Vocabulary concentration (Maas 1972; lower = richer).",
    "md_flesch": "Language-calibrated readability formula of the active profile.",
    "md_lix": "Readability index (LIX).",
    "md_dialog": "Share of quoted speech in the prose.",
    "md_paras": "Paragraph economy of the main text.",
    # Markdown 1.2 – sentence-length functions
    "md_short": "Short beats and action beats.",
    "md_medium": "Narrative flow and observation.",
    "md_long": "Associative extensions.",
    "md_complex": "Hypotaxis; deliberately limited.",
    # Markdown 1.3 – punctuation functions
    "punct_Punkte": "Basic sentence rhythm.",
    "punct_Kommata": "Enumerations and appositions.",
    "punct_Gedankenstriche": "Afterthought, self-correction, insertion.",
    "punct_Doppelpunkte": "Announcing lists, quotes, insights.",
    "punct_Fragezeichen": "Self-questioning and dialogue.",
    "punct_Ausrufezeichen": "Used sparingly.",
    "punct_Semikolons": "Rare; avoids a lecturing tone.",
    "punct_Auslassungspunkte": "Breaking off a thought.",
    # Punctuation display names (language-neutral keys in the metrics payload)
    "pname_periods": "Periods (.)",
    "pname_commas": "Commas (,)",
    "pname_dashes": "Dashes (–/—)",
    "pname_colons": "Colons (:)",
    "pname_semicolons": "Semicolons (;)",
    "pname_questions": "Question marks (?)",
    "pname_exclamations": "Exclamation marks (!)",
    "pname_ellipses": "Ellipses (…/...)",
    # Row labels and units (shared by Markdown and Rich)
    "label_raw_words": "Total word count (full text incl. appendix)",
    "label_clean_words": "Main text word count (prose only)",
    "label_sentences": "Total sentences (main text)",
    "label_asl": "Average sentence length (ASL)",
    "label_median": "Median sentence length",
    "label_std": "Sentence-length standard deviation",
    "label_ttr": "Lexical diversity (TTR)",
    "label_guiraud": "Guiraud index R ($V / \\sqrt{N}$)",
    "label_yules": "Yule's Characteristic K",
    "label_mtld": "MTLD (Textual Lexical Diversity)",
    "label_mattr": "MATTR (Moving-Average TTR)",
    "label_maas": "Maas a²",
    "label_lix": "LIX (readability index)",
    "label_dialog": "Dialogue share (quoted speech)",
    "label_filter": "Perception filters (showing)",
    "label_paras": "Prose paragraphs",
    "label_short": "Short sentences (staccato)",
    "label_medium": "Medium sentences (norm prose)",
    "label_long": "Long sentences (extension)",
    "label_complex": "Complex hypotaxis",
    "unit_words": "words",
    "unit_chars": "characters",
    "unit_sentences": "sentences",
    "unit_words_per_sentence": "words / sentence",
    "unit_words_per_paragraph": "words/paragraph",
    "unit_hits": "hits",
    "md_normpages": "~{ns250} norm pages à 250 words / ~{ns1500} norm pages à 1,500 characters",
    "md_chapters": "({chapters})",
    # Markdown table headers
    "md_header_metric": "Linguistic metric",
    "md_header_value": "Measured value",
    "md_header_note": "Interpretation & reference",
    "md_header_category": "Sentence-length category",
    "md_header_criterion": "Criterion",
    "md_header_count": "Sentences",
    "md_header_share": "Share",
    "md_header_function": "Function",
    "md_header_punct": "Punctuation mark",
    "md_header_freq": "Frequency",
    "md_header_density": "Density (per 1,000 words)",
    "md_header_chapter": "Ch.",
    "md_header_title": "Title",
    "md_header_words": "Words",
    "md_header_sentences": "Sentences",
    "md_header_asl": "ASL",
    "md_header_dialog": "Dialogue %",
    "md_header_ttr": "TTR",
    "md_header_filters": "Filter verbs",
    "crit_short": "≤ 6 words",
    "crit_medium": "7–15 words",
    "crit_long": "16–25 words",
    "crit_complex": "> 25 words",
    # Rich report
    "rich_title": "📖 Corpus Analysis & Manuscript Profile",
    "rich_scope": "Scope: {words} words | {chars} characters | {chapters}",
    "chapter": "chapter",
    "chapters": "chapters",
    "rich_normpages": "Norm pages: ~{ns250} (250 words) | ~{ns1500} (1,500 chars)",
    "rich_tbl1": "Core metrics & stylistic profile",
    "rich_tbl2": "Sentence-length architecture & rhythm",
    "col_metric": "Metric",
    "col_value": "Value",
    "col_ref": "Reference corridor",
    "col_note": "Assessment",
    "col_category": "Category",
    "col_criterion": "Criterion",
    "col_count": "Count",
    "col_share": "Share",
    "col_function": "Function",
    # Rich table 2 – sentence-length functions
    "t2_short": "Short beats, pace.",
    "t2_medium": "Flowing narration.",
    "t2_long": "Associative sentences.",
    "t2_complex": "Complex thoughts.",
}

REPORT_TEXTS_DE: dict[str, str] = {
    # Structure (Markdown report)
    "sec_1_1": "### 1.1 Gesamtkorpus-Kennzahlen",
    "sec_1_2": "### 1.2 Satzlängen-Architektur & Rhythmusprofil",
    "sec_1_3": "### 1.3 Interpunktion als stilistischer Seismograf",
    "sec_1_4": "### 1.4 Kapitelweise Vergleichsmatrix (Linguistische Tiefenprofile)",
    "md_col_tempus": "Dominantes Tempus",
    "md_intro_sentence": "Die empirische Verteilung der Sätze des Haupttextes:",
    # Markdown 1.1 – neutrale Einordnungen
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
    # Markdown 1.2 – Satzlängen-Funktionen
    "md_short": "Kurze Takte und Handlungsbefehle.",
    "md_medium": "Handlungsfortgang und Anschauung.",
    "md_long": "Assoziative Erweiterungen.",
    "md_complex": "Hypotaxen; bewusst begrenzt.",
    # Markdown 1.3 – Interpunktions-Funktionen
    "punct_Punkte": "Grundtakt der Satzbildung.",
    "punct_Kommata": "Aufzählungen und Beisätze.",
    "punct_Gedankenstriche": "Nachklapp, Selbstkorrektur, Einschub.",
    "punct_Doppelpunkte": "Ankündigung von Listen, Zitaten, Einsichten.",
    "punct_Fragezeichen": "Selbstbefragung und Dialog.",
    "punct_Ausrufezeichen": "Sparsam dosiert.",
    "punct_Semikolons": "Selten; vermeidet dozierenden Ton.",
    "punct_Auslassungspunkte": "Abreißen des Gedankens.",
    # Interpunktions-Anzeigenamen (sprachneutrale Keys in den Metriken)
    "pname_periods": "Punkte (.)",
    "pname_commas": "Kommata (,)",
    "pname_dashes": "Gedankenstriche (–/—)",
    "pname_colons": "Doppelpunkte (:)",
    "pname_semicolons": "Semikolons (;)",
    "pname_questions": "Fragezeichen (?)",
    "pname_exclamations": "Ausrufezeichen (!)",
    "pname_ellipses": "Auslassungspunkte (…/...)",
    # Zeilenlabels und Einheiten (Markdown + Rich)
    "label_raw_words": "Gesamtwortzahl (Volltext inkl. Anhang)",
    "label_clean_words": "Wortzahl Haupttext (Reine Romanprosa)",
    "label_sentences": "Satz-Gesamtzahl (Haupttext)",
    "label_asl": "Mittlere Satzlänge (ASL)",
    "label_median": "Median der Satzlänge",
    "label_std": "Standardabweichung Satzlänge",
    "label_ttr": "Lexikalische Diversität (TTR)",
    "label_guiraud": "Guiraud-Index R ($V / \\sqrt{N}$)",
    "label_yules": "Yule's Characteristic K",
    "label_mtld": "MTLD (Textual Lexical Diversity)",
    "label_mattr": "MATTR (Moving-Average TTR)",
    "label_maas": "Maas a²",
    "label_lix": "LIX (Lesbarkeitsindex)",
    "label_dialog": "Dialogquote (Wörtliche Rede)",
    "label_filter": "Perzeptionsfilter (Showing)",
    "label_paras": "Fließprosa-Absätze",
    "label_short": "Kurzsätze (Staccato)",
    "label_medium": "Mittlere Sätze (Normprosa)",
    "label_long": "Lange Sätze (Erweiterung)",
    "label_complex": "Komplexe Hypotaxen",
    "unit_words": "Wörter",
    "unit_chars": "Zeichen",
    "unit_sentences": "Sätze",
    "unit_words_per_sentence": "Wörter / Satz",
    "unit_words_per_paragraph": "W./Absatz",
    "unit_hits": "Belege",
    "md_normpages": "~{ns250} Normseiten à 250 W. / ~{ns1500} Normseiten à 1.500 Z.",
    "md_chapters": "({chapters})",
    # Markdown-Tabellenköpfe
    "md_header_metric": "Linguistische Metrik",
    "md_header_value": "Gemessener Wert",
    "md_header_note": "Einordnung & Referenzbereich",
    "md_header_category": "Satzlängen-Kategorie",
    "md_header_criterion": "Kriterium",
    "md_header_count": "Anzahl Sätze",
    "md_header_share": "Prozentualer Anteil",
    "md_header_function": "Funktion",
    "md_header_punct": "Satzzeichen",
    "md_header_freq": "Häufigkeit",
    "md_header_density": "Dichte (pro 1.000 Wörter)",
    "md_header_chapter": "Kap.",
    "md_header_title": "Titel",
    "md_header_words": "Wörter",
    "md_header_sentences": "Sätze",
    "md_header_asl": "ASL",
    "md_header_dialog": "Dialog-%",
    "md_header_ttr": "TTR",
    "md_header_filters": "Filterverben",
    "crit_short": "≤ 6 Wörter",
    "crit_medium": "7–15 Wörter",
    "crit_long": "16–25 Wörter",
    "crit_complex": "> 25 Wörter",
    # Rich-Report
    "rich_title": "📖 Korpuslinguistische Textanalyse & Manuskriptprofil",
    "rich_scope": "Umfang: {words} Wörter | {chars} Zeichen | {chapters}",
    "chapter": "Kapitel",
    "chapters": "Kapitel",
    "rich_normpages": "Normseiten: ~{ns250} NS (à 250 W.) | ~{ns1500} NS (à 1.500 Z.)",
    "rich_tbl1": "Linguistische Kennzahlen & Stilistische DNA",
    "rich_tbl2": "Satzlängen-Architektur & Rhythmisierung",
    "col_metric": "Metrik",
    "col_value": "Messwert",
    "col_ref": "Referenz / Zielkorridor",
    "col_note": "Literarische Bewertung",
    "col_category": "Kategorie",
    "col_criterion": "Kriterium",
    "col_count": "Anzahl",
    "col_share": "Anteil",
    "col_function": "Funktion",
    # Rich-Tabelle 2 – Satzlängen-Funktionen
    "t2_short": "Kurze Takte, Tempo.",
    "t2_medium": "Fließende Erzählung.",
    "t2_long": "Assoziative Sätze.",
    "t2_complex": "Komplexe Gedanken.",
}

REPORT_TEXTS: dict[str, dict[str, str]] = {"en": REPORT_TEXTS_EN, "de": REPORT_TEXTS_DE}


def _resolve_texts(texts: Mapping[str, str] | None, language_key: str = "en") -> dict[str, str]:
    """Merges the language pack with optional project overrides."""
    resolved = dict(REPORT_TEXTS.get(language_key, REPORT_TEXTS_EN))
    if texts:
        resolved.update(texts)
    return resolved


def _t(texts: Mapping[str, str], key: str) -> str:
    """Returns the (already resolved) report text for a key."""
    return texts.get(key, REPORT_TEXTS_EN.get(key, ""))


def _dominance_label(labels: Mapping[str, str] | None, value: str) -> str:
    """Localised display label for a canonical tense value (present/past/…)."""
    if labels and value in labels:
        return labels[value]
    return value


class ReportFormatter:
    """Formatting of corpus data for terminal, Markdown and JSON."""

    @staticmethod
    def print_rich_report(
        m: CorpusMetrics,
        console: Console | None = None,
        texts: Mapping[str, str] | None = None,
        language_key: str = "en",
    ) -> None:
        """Renders a modern, highly aesthetic Rich terminal dashboard."""
        texts = _resolve_texts(texts, language_key)

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
        header_text.append(f"{_t(texts, 'rich_title')}\n", style="bold cyan")
        n_chapters = len(m.chapters)
        chapter_word = _t(texts, "chapters" if n_chapters != 1 else "chapter")
        header_text.append(
            _t(texts, "rich_scope").format(
                words=_n(m.raw_words, 0),
                chars=_n(m.raw_chars, 0),
                chapters=f"{n_chapters} {chapter_word}",
            )
            + "\n",
            style="dim white",
        )
        header_text.append(
            _t(texts, "rich_normpages").format(ns250=_n(ns_250, 1), ns1500=_n(ns_1500, 1)),
            style="green",
        )
        con.print(Panel(header_text, border_style="cyan", box=box.ROUNDED))

        # Project texts may supply reference corridors and assessments; without
        # them the table stays factual (metric + value only).
        show_reference = any(
            key.startswith("t1_") and key.endswith("_ref") and texts.get(key) for key in texts
        )
        show_assessment = any(
            key.startswith("t1_") and key.endswith("_note") and texts.get(key) for key in texts
        )

        table1 = Table(
            title=_t(texts, "rich_tbl1"), box=box.SIMPLE_HEAVY, header_style="bold magenta"
        )
        table1.add_column(_t(texts, "col_metric"), style="bold white", no_wrap=True)
        table1.add_column(_t(texts, "col_value"), justify="right", style="cyan", no_wrap=True)
        if show_reference:
            table1.add_column(_t(texts, "col_ref"), style="dim")
        if show_assessment:
            table1.add_column(_t(texts, "col_note"), style="yellow")

        def _row(label_key: str, value: str, ref_key: str, note_key: str) -> None:
            cells = [_t(texts, label_key), value]
            if show_reference:
                cells.append(_t(texts, ref_key))
            if show_assessment:
                cells.append(_t(texts, note_key))
            table1.add_row(*cells)

        _row(
            "label_asl",
            f"{_n(m.asl, 2)} {_t(texts, 'unit_words_per_sentence')}",
            "t1_asl_ref",
            "t1_asl_note",
        )
        _row(
            "label_median",
            f"{m.median_sl} {_t(texts, 'unit_words')}",
            "t1_median_ref",
            "t1_median_note",
        )
        _row(
            "label_std",
            f"{_n(m.std_sl, 2)} {_t(texts, 'unit_words')}",
            "t1_std_ref",
            "t1_std_note",
        )
        _row("label_ttr", f"{_n(m.ttr, 4)}", "t1_ttr_ref", "t1_ttr_note")
        _row("label_yules", f"{_n(m.yules_k, 2)}", "t1_yules_ref", "t1_yules_note")
        _row(
            "label_mtld",
            f"{_n(m.mtld, 1)}" if m.mtld is not None else "–",
            "t1_mtld_ref",
            "t1_mtld_note",
        )
        _row(
            "label_mattr",
            f"{_n(m.mattr, 3)}" if m.mattr is not None else "–",
            "t1_mattr_ref",
            "t1_mattr_note",
        )
        _row(
            "label_maas",
            f"{_n(m.maas_a2, 4)}" if m.maas_a2 is not None else "–",
            "t1_maas_ref",
            "t1_maas_note",
        )
        _row(
            "label_lix",
            f"{_n(m.lix, 1)}",
            "t1_lix_ref",
            "t1_lix_note",
        )
        _row(
            "label_dialog",
            f"{_p(m.dialog_ratio, 2)}",
            "t1_dialog_ref",
            "t1_dialog_note",
        )
        _row(
            "label_filter",
            f"{m.filter_count} {_t(texts, 'unit_hits')}",
            "t1_filter_ref",
            "t1_filter_note",
        )
        # The Flesch row is labelled by the language-calibrated formula name.
        flesch_cells = [m.flesch_variant or "Flesch Reading Ease", f"{_n(m.flesch_de, 1)}"]
        if show_reference:
            flesch_cells.append(_t(texts, "t1_flesch_ref"))
        if show_assessment:
            flesch_cells.append(_t(texts, "t1_flesch_note"))
        table1.add_row(*flesch_cells)
        con.print(table1)

        # Table 2: sentence-length distribution
        table2 = Table(title=_t(texts, "rich_tbl2"), box=box.SIMPLE, header_style="bold green")
        table2.add_column(_t(texts, "col_category"), style="bold white", no_wrap=True)
        table2.add_column(_t(texts, "col_criterion"), style="dim", no_wrap=True)
        table2.add_column(_t(texts, "col_count"), justify="right", style="cyan")
        table2.add_column(_t(texts, "col_share"), justify="right", style="green")
        table2.add_column(_t(texts, "col_function"))

        d = m.sentence_dist
        table2.add_row(
            _t(texts, "label_short"),
            _t(texts, "crit_short"),
            f"{_n(d.short_count, 0)}",
            f"{_p(d.short_pct, 1)}",
            _t(texts, "t2_short"),
        )
        table2.add_row(
            _t(texts, "label_medium"),
            _t(texts, "crit_medium"),
            f"{_n(d.medium_count, 0)}",
            f"{_p(d.medium_pct, 1)}",
            _t(texts, "t2_medium"),
        )
        table2.add_row(
            _t(texts, "label_long"),
            _t(texts, "crit_long"),
            f"{_n(d.long_count, 0)}",
            f"{_p(d.long_pct, 1)}",
            _t(texts, "t2_long"),
        )
        table2.add_row(
            _t(texts, "label_complex"),
            _t(texts, "crit_complex"),
            f"{_n(d.complex_count, 0)}",
            f"{_p(d.complex_pct, 1)}",
            _t(texts, "t2_complex"),
        )
        con.print(table2)

    @staticmethod
    def format_markdown_report(
        m: CorpusMetrics,
        texts: Mapping[str, str] | None = None,
        labels: Mapping[str, str] | None = None,
        language_key: str = "en",
    ) -> str:
        """Generates GitHub-Flavored Markdown for embedding into dossiers."""
        texts = _resolve_texts(texts, language_key)

        def _n(value: float, decimals: int = 1, signed: bool = False) -> str:
            return format_num(value, language_key, decimals, signed)

        def _p(value: float, decimals: int = 1) -> str:
            return format_pct(value, language_key, decimals)

        ns_250 = m.raw_words / 250.0
        ns_1500 = m.raw_chars / 1500.0
        normpages = _t(texts, "md_normpages").format(ns250=_n(ns_250, 1), ns1500=_n(ns_1500, 1))
        n_chapters = len(m.chapters)
        chapters_suffix = _t(texts, "md_chapters").format(
            chapters=f"{n_chapters} {_t(texts, 'chapters' if n_chapters != 1 else 'chapter')}"
        )
        w = _t(texts, "unit_words")
        c = _t(texts, "unit_chars")

        lines = [
            _t(texts, "sec_1_1"),
            "",
            f"| {_t(texts, 'md_header_metric')} | {_t(texts, 'md_header_value')} | {_t(texts, 'md_header_note')} |",
            "| :--- | :--- | :--- |",
            f"| **{_t(texts, 'label_raw_words')}** | **{_n(m.raw_words, 0)} {w}** ({_n(m.raw_chars, 0)} {c}) | {_t(texts, 'md_raw_words')} ({normpages}). |",
            f"| **{_t(texts, 'label_clean_words')}** | **{_n(m.clean_words, 0)} {w}** ({_n(m.clean_chars, 0)} {c}) | {_t(texts, 'md_clean_words')} {chapters_suffix}. |",
            f"| **{_t(texts, 'label_sentences')}** | **{_n(m.total_sentences, 0)} {_t(texts, 'unit_sentences')}** | {_t(texts, 'md_sentences')} |",
            f"| **{_t(texts, 'label_asl')}** | **{_n(m.asl, 2)} {_t(texts, 'unit_words_per_sentence')}** | {_t(texts, 'md_asl')} |",
            f"| **{_t(texts, 'label_median')}** | **{m.median_sl} {w}** | {_t(texts, 'md_median')} |",
            f"| **{_t(texts, 'label_std')}** | **{_n(m.std_sl, 2)} {w}** | {_t(texts, 'md_std')} |",
            f"| **{_t(texts, 'label_ttr')}** | **{_n(m.ttr, 4)}** (V = {_n(m.vocab_types, 0)} / N = {_n(m.tokens, 0)}) | {_t(texts, 'md_ttr')} |",
            f"| **{_t(texts, 'label_guiraud')}** | **{_n(m.guiraud_r, 2)}** | {_t(texts, 'md_guiraud')} |",
            f"| **{_t(texts, 'label_yules')}** | **{_n(m.yules_k, 2)}** | {_t(texts, 'md_yules')} |",
            f"| **{_t(texts, 'label_mtld')}** | **{f'{_n(m.mtld, 1)}' if m.mtld is not None else '–'}** | {_t(texts, 'md_mtld')} |",
            f"| **{_t(texts, 'label_mattr')}** | **{f'{_n(m.mattr, 3)}' if m.mattr is not None else '–'}** | {_t(texts, 'md_mattr')} |",
            f"| **{_t(texts, 'label_maas')}** | **{f'{_n(m.maas_a2, 4)}' if m.maas_a2 is not None else '–'}** | {_t(texts, 'md_maas')} |",
            f"| **{m.flesch_variant or 'Flesch Reading Ease'}** | **{_n(m.flesch_de, 1)}** | {_t(texts, 'md_flesch')} |",
            f"| **{_t(texts, 'label_lix')}** | **{_n(m.lix, 1)}** | {_t(texts, 'md_lix')} |",
            f"| **{_t(texts, 'label_dialog')}** | **{_n(m.dialog_words, 0)} {w} ({_p(m.dialog_ratio, 2)})** | {_t(texts, 'md_dialog')} |",
            f"| **{_t(texts, 'label_paras')}** | **{m.total_paragraphs}** ({_n(m.avg_paragraph_len, 1)} {_t(texts, 'unit_words_per_paragraph')}) | {_t(texts, 'md_paras')} |",
            "",
            "---",
            "",
            _t(texts, "sec_1_2"),
            "",
            _t(texts, "md_intro_sentence"),
            "",
            f"| {_t(texts, 'md_header_category')} | {_t(texts, 'md_header_criterion')} | {_t(texts, 'md_header_count')} | {_t(texts, 'md_header_share')} | {_t(texts, 'md_header_function')} |",
            "| :--- | :--- | ---:| ---:| :--- |",
        ]

        d = m.sentence_dist
        lines.append(
            f"| **{_t(texts, 'label_short')}** | {_t(texts, 'crit_short')} | **{_n(d.short_count, 0)}** | **{_p(d.short_pct, 1)}** | {_t(texts, 'md_short')} |"
        )
        lines.append(
            f"| **{_t(texts, 'label_medium')}** | {_t(texts, 'crit_medium')} | **{_n(d.medium_count, 0)}** | **{_p(d.medium_pct, 1)}** | {_t(texts, 'md_medium')} |"
        )
        lines.append(
            f"| **{_t(texts, 'label_long')}** | {_t(texts, 'crit_long')} | **{_n(d.long_count, 0)}** | **{_p(d.long_pct, 1)}** | {_t(texts, 'md_long')} |"
        )
        lines.append(
            f"| **{_t(texts, 'label_complex')}** | {_t(texts, 'crit_complex')} | **{_n(d.complex_count, 0)}** | **{_p(d.complex_pct, 1)}** | {_t(texts, 'md_complex')} |"
        )

        lines.extend(
            [
                "",
                "---",
                "",
                _t(texts, "sec_1_3"),
                "",
                f"| {_t(texts, 'md_header_punct')} | {_t(texts, 'md_header_freq')} | {_t(texts, 'md_header_density')} | {_t(texts, 'md_header_function')} |",
                "| :--- | ---:| ---:| :--- |",
            ]
        )

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
            name = _t(texts, f"pname_{k}") or k
            lines.append(f"| **{name}** | {_n(v, 0)} | {_n(density, 1)} | {fn} |")

        # Chapter matrix: motif columns dynamically from motif_counts
        motif_keys: list[str] = []
        for c_ in m.chapters:
            for key in c_.motif_counts:
                if key not in motif_keys:
                    motif_keys.append(key)

        header = (
            f"| {_t(texts, 'md_header_chapter')} | {_t(texts, 'md_header_title')} | {_t(texts, 'md_header_words')} | "
            f"{_t(texts, 'md_header_sentences')} | {_t(texts, 'md_header_asl')} | {_t(texts, 'md_header_dialog')} | {_t(texts, 'md_header_ttr')} |"
        )
        separator = "| :--- | :--- | ---:| ---:| ---:| ---:| ---:|"
        for key in motif_keys:
            header += f" {key} |"
            separator += " ---:|"
        header += f" {_t(texts, 'md_header_filters')} | {_t(texts, 'md_col_tempus')} |"
        separator += " ---:| :--- |"

        lines.extend(["", "---", "", _t(texts, "sec_1_4"), "", header, separator])

        for c_ in m.chapters:
            motifs = "".join(f" {c_.motif_counts.get(key, 0)} |" for key in motif_keys)
            lines.append(
                f"| {c_.num:02d} | {c_.title} | {_n(c_.words, 0)} | {c_.sentences} | "
                f"{_n(c_.asl, 1)} | {_p(c_.dialog_pct, 1)} | {_n(c_.ttr, 3)} |"
                f"{motifs} {c_.filter_verbs} | {_dominance_label(labels, c_.dominance)} |"
            )

        return "\n".join(lines)

    @staticmethod
    def to_json(m: CorpusMetrics, indent: bool = True) -> str:
        """Serialises CorpusMetrics with orjson."""
        opts = orjson.OPT_INDENT_2 if indent else 0
        return orjson.dumps(m.model_dump(), option=opts).decode("utf-8")
