"""
scripts/engine/models.py
========================
Pydantic v2 data models for quantitative corpus linguistics, stylometry,
sentence-length architecture, chapter metrics and synchronisation audits.

Strict schema definitions guarantee type safety, automatic validation
and standards-compliant orjson serialisation both for internal workflows and
for later distribution as a standalone open-source package.
"""

from pydantic import BaseModel, Field


class CorpusConfig(BaseModel):
    """
    Configuration schema for quantitative corpus analysis.

    Language-dependent patterns (tense, dialogue, word tokens, filter verbs,
    signal words) are defined as **optional overrides**: ``None`` means
    "use the default of the selected language profile" (``scripts/engine/language.py``).
    This makes the engine work for any language and any writing style without
    code changes – new languages are registered as ``LanguageProfile``.
    """

    chapter_regex: str = Field(
        default=r"(?m)^##\s+", description="Regulärer Ausdruck zur Erkennung von Kapitelgrenzen."
    )
    appendix_marker: str = Field(
        default="## Anmerkungen und Literaturverzeichnis",
        description="Trennmarker, ab welchem Fließprosa in wissenschaftlichen Anhang übergeht.",
    )
    language: str = Field(
        default="de",
        description="Sprachschlüssel des Sprachprofils ('de', 'en', 'generic'; erweiterbar).",
    )
    min_paragraph_length_for_oneliner: int = Field(
        default=25,
        description="Wortschwelle, unterhalb derer ein Absatz als potentieller Einzeiler klassifiziert wird.",
    )
    motif_regexes: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Projekt-/roman-spezifische Leitmotive als Label→RegEx (z. B. Titelwortfelder). "
            "Wird je Kapitel gezählt (ChapterMetrics.motif_counts)."
        ),
    )

    # Optional language overrides (None = language profile default)
    signal_keywords: dict[str, str] | None = Field(
        default=None,
        description="Thematische Signalwörter als Label→RegEx (None = Sprachprofil-Standard).",
    )
    filter_verbs_regex: str | None = Field(
        default=None,
        description="RegEx für Perzeptionsfilter ('Telling'-Indikatoren; None = Sprachprofil-Standard).",
    )
    praesens_regex: str | None = Field(
        default=None,
        description="RegEx für Gegenwartsmarker (Präsens; None = Sprachprofil-Standard).",
    )
    praeteritum_regex: str | None = Field(
        default=None,
        description="RegEx für Vergangenheitsmarker (Präteritum; None = Sprachprofil-Standard).",
    )
    dialogue_regex: str | None = Field(
        default=None,
        description="RegEx zur Erkennung wörtlicher Rede (None = Sprachprofil-Standard).",
    )
    word_regex: str | None = Field(
        default=None,
        description="RegEx zur Worttokenisierung (None = Sprachprofil-Standard).",
    )
    first_person_starters: list[str] | None = Field(
        default=None,
        description="Wörter der 1. Person Singular für die Satzanfangs-Analyse (None = Sprachprofil).",
    )
    passive_regex: str | None = Field(
        default=None,
        description="RegEx für Passiv-Marker (None = Sprachprofil-Standard).",
    )
    nominal_regex: str | None = Field(
        default=None,
        description="RegEx für Nominalisierungs-Suffixe (None = Sprachprofil-Standard).",
    )
    adjective_regex: str | None = Field(
        default=None,
        description="RegEx für Adjektiv-Suffixe (None = Sprachprofil-Standard).",
    )


class SentenceDistribution(BaseModel):
    """
    Statistical distribution of the sentence-length architecture.
    Serves the analysis of rhythmic staccato vs. cascading periods.
    """

    short_count: int = Field(description="Anzahl Kurzsätze (<= 6 Wörter, Staccato/Befehle).")
    short_pct: float = Field(description="Prozentualer Anteil der Kurzsätze.")
    medium_count: int = Field(description="Anzahl mittlerer Sätze (7–15 Wörter, Normprosa).")
    medium_pct: float = Field(description="Prozentualer Anteil der mittleren Sätze.")
    long_count: int = Field(description="Anzahl langer Sätze (16–25 Wörter, Erweiterung).")
    long_pct: float = Field(description="Prozentualer Anteil der langen Sätze.")
    complex_count: int = Field(description="Anzahl komplexer Hypotaxen (> 25 Wörter).")
    complex_pct: float = Field(description="Prozentualer Anteil komplexer Hypotaxen.")


class ChapterMetrics(BaseModel):
    """
    Linguistic and narratological profile of a single chapter.
    """

    num: int = Field(description="Kapitelnummer (1-basiert).")
    title: str = Field(description="Bereinigter Kapiteltitel.")
    words: int = Field(description="Reine Wortanzahl des Kapitels ohne Markdown-Kommentare.")
    sentences: int = Field(description="Anzahl der Sinneinheiten/Sätze im Kapitel.")
    asl: float = Field(description="Mittlere Satzlänge (Average Sentence Length) in Wörtern.")
    dialog_pct: float = Field(description="Prozentualer Anteil wörtlicher Rede am Text.")
    ttr: float = Field(description="Type-Token-Ratio des Kapitels (lexikalische Dichte).")
    motif_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Kapitelzählung der konfigurierten Leitmotive (CorpusConfig.motif_regexes).",
    )
    filter_verbs: int = Field(default=0, description="Häufigkeit von Perzeptionsfiltern.")
    dominance: str = Field(
        default="Hybrid / Montage", description="Tempus-Tendenz (Präsens vs. Präteritum)."
    )
    signal_matches: dict[str, int] = Field(
        default_factory=dict, description="Generische Fundstellen aller Signalwörter."
    )
    # --- Self-calibrating style features (house-style fingerprint) ---
    staccato_pct: float = Field(
        default=0.0, description="Anteil sehr kurzer Sätze (≤ 6 Wörter) in Prozent."
    )
    kaskade_pct: float = Field(
        default=0.0, description="Anteil komplexer Sätze (> 25 Wörter) in Prozent."
    )
    sentence_cv: float = Field(
        default=0.0, description="Variationskoeffizient der Satzlängen (Std/Mittel)."
    )
    start_entropy: float = Field(
        default=0.0, description="Shannon-Entropie der Satzanfänge (Monotonie-Indikator)."
    )
    first_person_start_rate: float = Field(
        default=0.0, description="Anteil der Sätze, die mit der 1. Person Singular beginnen."
    )
    passive_density: float = Field(default=0.0, description="Passiv-Marker je 1.000 Wörter.")
    nominalization_density: float = Field(
        default=0.0, description="Nominalisierungen je 1.000 Wörter."
    )
    adjective_density: float = Field(
        default=0.0, description="Adjektiv-Suffix-Treffer je 1.000 Wörter."
    )
    modal_density: float = Field(default=0.0, description="Modalverben je 1.000 Wörter.")
    filter_density: float = Field(default=0.0, description="Perzeptionsfilter je 1.000 Wörter.")
    long_word_pct: float = Field(
        default=0.0, description="Anteil langer Wörter (> 6 Buchstaben) in Prozent."
    )
    guiraud_r: float = Field(default=0.0, description="Guiraud-Index R = V / sqrt(N).")
    hd_d: float | None = Field(
        default=None, description="HD-D lexikalische Diversität (McCarthy & Jarvis 2010)."
    )
    jsd: float = Field(
        default=0.0, description="Jensen-Shannon-Distanz der Wortverteilung zum Restkorpus."
    )
    jsd_top_words: list[str] = Field(
        default_factory=list,
        description="Stärkste Treiberwörter der Kapitel-Divergenz (Inhaltswörter).",
    )
    function_word_pct: float = Field(
        default=0.0, description="Anteil der Funktionswörter an den Kapitel-Tokens."
    )


class CorpusMetrics(BaseModel):
    """
    Holistic quantitative and stylometric metrics of the manuscript.
    """

    raw_words: int = Field(description="Wortzahl Volltext inklusive Anhang und Verzeichnisse.")
    clean_words: int = Field(description="Bereinigte Wortzahl der reinen Romanprosa.")
    raw_chars: int = Field(description="Gesamtzeichenzahl inklusive Leerzeichen und Anhang.")
    clean_chars: int = Field(description="Bereinigte Zeichenzahl der reinen Romanprosa.")
    tokens: int = Field(description="Gesamtzahl analysierter Wort-Token (N).")
    vocab_types: int = Field(description="Anzahl distinkter Vokabulartypen (V).")
    ttr: float = Field(description="Type-Token-Ratio (V / N, lexikalische Diversität).")
    guiraud_r: float = Field(description="Guiraud-Index R = V / sqrt(N), textlängenstabilisiert.")
    yules_k: float = Field(description="Yule's Characteristic K (Stabilität des Erzähleridioms).")
    total_sentences: int = Field(description="Gesamtzahl Sätze der reinen Romanprosa.")
    asl: float = Field(description="Mittlere Satzlänge (Average Sentence Length).")
    median_sl: int = Field(description="Median der Satzlänge in Wörtern.")
    std_sl: float = Field(description="Standardabweichung der Satzlänge.")
    sentence_dist: SentenceDistribution = Field(description="Satzlängen-Architekturprofil.")
    asw: float = Field(description="Mittlere Silbenanzahl pro Wort (Average Syllables per Word).")
    flesch_de: float = Field(description="Flesch Reading Ease (deutsche Amstad-Formel).")
    lix: float = Field(description="Läsbarhetsindex (LIX = ASL + % Langwörter > 6 Buchstaben).")
    dialog_words: int = Field(description="Wortanzahl in wörtlicher Rede.")
    dialog_ratio: float = Field(description="Prozentualer Dialoganteil an der Romanprosa.")
    total_paragraphs: int = Field(description="Gesamtzahl der Fließprosa-Absätze.")
    avg_paragraph_len: float = Field(description="Mittlere Absatzlänge in Wörtern.")
    single_line_paragraphs: int = Field(description="Anzahl kurzer/isolierter Absätze.")
    punctuation: dict[str, int] = Field(description="Absolute Häufigkeiten aller Satzzeichen.")
    signal_counts: dict[str, int] = Field(description="Fundstellen der Signal-Keywords.")
    filter_count: int = Field(description="Gesamtzahl gefundener Perzeptionsfilter.")
    chapters: list[ChapterMetrics] = Field(description="Detaillierte Metriken aller Einzelkapitel.")
    # --- Self-calibrating style features (house-style fingerprint, corpus level) ---
    staccato_pct: float = Field(default=0.0, description="Anteil Kurzsätze (≤ 6 Wörter).")
    kaskade_pct: float = Field(default=0.0, description="Anteil komplexer Sätze (> 25 Wörter).")
    sentence_cv: float = Field(default=0.0, description="Variationskoeffizient der Satzlängen.")
    start_entropy: float = Field(default=0.0, description="Shannon-Entropie der Satzanfänge.")
    first_person_start_rate: float = Field(default=0.0, description="Anteil der Ich-Satzanfänge.")
    passive_density: float = Field(default=0.0, description="Passiv-Marker je 1.000 Wörter.")
    nominalization_density: float = Field(
        default=0.0, description="Nominalisierungen je 1.000 Wörter."
    )
    adjective_density: float = Field(
        default=0.0, description="Adjektiv-Suffix-Treffer je 1.000 Wörter."
    )
    modal_density: float = Field(default=0.0, description="Modalverben je 1.000 Wörter.")
    filter_density: float = Field(default=0.0, description="Perzeptionsfilter je 1.000 Wörter.")
    hd_d: float | None = Field(
        default=None, description="HD-D lexikalische Diversität (McCarthy & Jarvis 2010)."
    )


class DossierStatus(BaseModel):
    """
    Synchronisation and consistency status of a single companion dossier.
    """

    ok: bool = Field(description="True wenn das Dossier 100% synchron zum Manuskript ist.")
    details: str = Field(description="Kurzbeschreibung der geprüften Domäne.")
    drift: list[str] = Field(
        default_factory=list, description="Liste identifizierter Diskrepanzen."
    )


class CorpusAuditReport(BaseModel):
    """
    Complete audit report to prevent fragmentation and documentation drift.
    """

    manuscript: str = Field(description="Dateiname des analysierten Manuskripts.")
    raw_words: int = Field(description="Gesamtwortzahl Volltext.")
    main_words: int = Field(description="Bereinigte Wortzahl Romanprosa.")
    chars: int = Field(description="Gesamtzeichenzahl.")
    asl: float = Field(description="Mittlere Satzlänge.")
    ttr: float = Field(description="Lexikalische Diversität.")
    markers: int = Field(description="Anzahl noch offener Arbeitsmarker (PRÜFEN/SACHCHECK).")
    kap23_words: int = Field(description="Wortanzahl Kapitel 23.")
    kap24_words: int = Field(description="Wortanzahl Kapitel 24.")
    kap25_words: int | None = Field(default=None, description="Wortanzahl Kapitel 25.")
    dossiers: dict[str, DossierStatus] = Field(description="Audit-Ergebnisse je Begleitdossier.")
    all_synced: bool = Field(description="True wenn ausnahmslos alle Dossiers synchron sind.")
