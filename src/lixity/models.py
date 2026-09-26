"""lixity.models – Pydantic data schemas for corpus linguistics and stylometry.

Defines strict, validated models for corpus configuration, sentence distributions,
chapter metrics, tense profiles, and synchronization reports.
"""

from pydantic import BaseModel, Field

from .status import SCHEMA_VERSION_ANALYZE

# Version of the machine-readable JSON contracts (analyze/profile).
# v2: tense values are language-neutral (present/past/mixed/neutral).
SCHEMA_VERSION = SCHEMA_VERSION_ANALYZE


class CorpusConfig(BaseModel):
    """
    Configuration schema for quantitative corpus analysis.

    Language-dependent patterns (tense, dialogue, word tokens, filter verbs,
    signal words) are defined as **optional overrides**: ``None`` means
    "use the default of the selected language profile" (``lixity.language``).
    This makes the engine work for any language and any writing style without
    code changes – new languages are registered as ``LanguageProfile``.
    """

    chapter_regex: str = Field(
        default=r"(?m)^##\s+", description="Regular expression to identify chapter boundaries."
    )
    appendix_marker: str = Field(
        default="## Anmerkungen und Literaturverzeichnis",
        description="Divider marker where narrative prose transitions to scholarly appendix/notes.",
    )
    language: str = Field(
        default="en",
        description="Language code of the profile ('de', 'en', 'generic'; extensible).",
    )
    min_paragraph_length_for_oneliner: int = Field(
        default=25,
        description="Word threshold below which a paragraph is classified as a potential one-liner.",
    )
    motif_regexes: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Project- or novel-specific motifs as label→regex mapping (e.g., thematic clusters). "
            "Counted per chapter (ChapterMetrics.motif_counts)."
        ),
    )

    # Optional language overrides (None = language profile default)
    signal_keywords: dict[str, str] | None = Field(
        default=None,
        description="Thematic signal keywords as label→regex mapping (None = language profile default).",
    )
    filter_verbs_regex: str | None = Field(
        default=None,
        description="Regex for perception filters ('telling' indicators; None = language profile default).",
    )
    praesens_regex: str | None = Field(
        default=None,
        description="Regex for present-tense markers (None = language profile default).",
    )
    praeteritum_regex: str | None = Field(
        default=None,
        description="Regex for past-tense markers (None = language profile default).",
    )
    dialogue_regex: str | None = Field(
        default=None,
        description="Regex for quoted/direct speech detection (None = language profile default).",
    )
    word_regex: str | None = Field(
        default=None,
        description="Regex for word tokenization (None = language profile default).",
    )
    first_person_starters: list[str] | None = Field(
        default=None,
        description="First-person singular pronouns for sentence-starter analysis (None = language profile default).",
    )
    passive_regex: str | None = Field(
        default=None,
        description="Regex for passive-voice markers (None = language profile default).",
    )
    nominal_regex: str | None = Field(
        default=None,
        description="Regex for nominalisation suffixes (None = language profile default).",
    )
    adjective_regex: str | None = Field(
        default=None,
        description="Regex for adjective suffixes (None = language profile default).",
    )


class SentenceDistribution(BaseModel):
    """
    Statistical distribution of the sentence-length architecture.
    Serves the analysis of rhythmic staccato vs. cascading periods.
    """

    short_count: int = Field(description="Count of short sentences (<= 6 words, staccato/commands).")
    short_pct: float = Field(description="Percentage of short sentences.")
    medium_count: int = Field(description="Count of medium sentences (7–15 words, standard prose).")
    medium_pct: float = Field(description="Percentage of medium sentences.")
    long_count: int = Field(description="Count of long sentences (16–25 words, extended period).")
    long_pct: float = Field(description="Percentage of long sentences.")
    complex_count: int = Field(description="Count of complex hypotactic sentences (> 25 words).")
    complex_pct: float = Field(description="Percentage of complex hypotactic sentences.")


class ChapterMetrics(BaseModel):
    """
    Linguistic and narratological profile of a single chapter.
    """

    num: int = Field(description="Chapter number (1-based).")
    title: str = Field(description="Cleaned chapter title.")
    words: int = Field(description="Net word count of the chapter excluding Markdown comments.")
    sentences: int = Field(description="Count of sense units / sentences in the chapter.")
    asl: float = Field(description="Average sentence length (ASL) in words.")
    dialog_pct: float = Field(description="Percentage of direct dialogue in the text.")
    ttr: float = Field(description="Type-Token Ratio of the chapter (lexical density).")
    motif_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Chapter count of configured motifs (CorpusConfig.motif_regexes).",
    )
    filter_verbs: int = Field(default=0, description="Frequency of perception filter verbs.")
    dominance: str = Field(
        default="mixed",
        description="Tense tendency (canonical: present/past/mixed/neutral).",
    )
    signal_matches: dict[str, int] = Field(
        default_factory=dict, description="Generic match counts of all signal words."
    )
    # --- Self-calibrating style features (house-style fingerprint) ---
    staccato_pct: float = Field(
        default=0.0, description="Percentage of very short sentences (≤ 6 words)."
    )
    kaskade_pct: float = Field(
        default=0.0, description="Percentage of complex sentences (> 25 words)."
    )
    sentence_cv: float = Field(
        default=0.0, description="Coefficient of variation of sentence lengths (std / mean)."
    )
    start_entropy: float = Field(
        default=0.0, description="Shannon entropy of sentence starters (monotony indicator)."
    )
    first_person_start_rate: float = Field(
        default=0.0, description="Share of sentences opening with first-person singular pronouns."
    )
    passive_density: float = Field(default=0.0, description="Passive-voice markers per 1,000 words.")
    nominalization_density: float = Field(
        default=0.0, description="Nominalisations per 1,000 words."
    )
    adjective_density: float = Field(
        default=0.0, description="Adjective suffix matches per 1,000 words."
    )
    modal_density: float = Field(default=0.0, description="Modal verbs per 1,000 words.")
    filter_density: float = Field(default=0.0, description="Perception filter verbs per 1,000 words.")
    long_word_pct: float = Field(
        default=0.0, description="Percentage of long words (> 6 letters)."
    )
    guiraud_r: float = Field(default=0.0, description="Guiraud index R = V / sqrt(N).")
    hd_d: float | None = Field(
        default=None, description="HD-D lexical diversity (McCarthy & Jarvis 2010)."
    )
    jsd: float = Field(
        default=0.0, description="Jensen-Shannon divergence of word distribution against remaining corpus."
    )
    jsd_top_words: list[str] = Field(
        default_factory=list,
        description="Strongest driver content words of chapter divergence.",
    )
    function_word_pct: float = Field(
        default=0.0, description="Share of function words among chapter tokens."
    )
    style_se: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Measurement uncertainty (standard error) per style feature. Documented "
            "approximations: Poisson for count densities, binomial for shares, "
            "ASL/CV/entropy/HD-D plug-ins. Empty = feature not measurable."
        ),
    )


class CorpusMetrics(BaseModel):
    """
    Holistic quantitative and stylometric metrics of the manuscript.
    """

    raw_words: int = Field(description="Total word count including appendix and directories.")
    clean_words: int = Field(description="Cleaned word count of pure narrative prose.")
    raw_chars: int = Field(description="Total character count including whitespace and appendix.")
    clean_chars: int = Field(description="Cleaned character count of pure narrative prose.")
    tokens: int = Field(description="Total analyzed word tokens (N).")
    vocab_types: int = Field(description="Distinct vocabulary types (V).")
    ttr: float = Field(description="Type-Token Ratio (V / N, lexical diversity).")
    guiraud_r: float = Field(description="Guiraud index R = V / sqrt(N), text-length stabilized.")
    yules_k: float = Field(description="Yule's characteristic K (stability of authorial vocabulary).")
    total_sentences: int = Field(description="Total sentence count of pure narrative prose.")
    asl: float = Field(description="Average sentence length (ASL).")
    median_sl: int = Field(description="Legacy upper median sentence length in words.")
    median_sl_exact: float | None = Field(
        default=None,
        description="Conventional median sentence length; absent in older metric payloads.",
    )
    std_sl: float = Field(description="Standard deviation of sentence length.")
    sentence_dist: SentenceDistribution = Field(description="Sentence-length architectural profile.")
    asw: float = Field(description="Average syllables per word.")
    flesch_de: float = Field(description="Flesch Reading Ease (language-calibrated formula).")
    flesch_variant: str = Field(
        default="",
        description="Name of the applied readability formula (e.g., Amstad, Kandel-Moles).",
    )
    lix: float = Field(description="Läsbarhetsindex (LIX = ASL + % long words > 6 letters).")
    dialog_words: int = Field(description="Word count in direct speech.")
    dialog_ratio: float = Field(description="Percentage of direct dialogue in narrative prose.")
    total_paragraphs: int = Field(description="Total count of narrative prose paragraphs.")
    avg_paragraph_len: float = Field(description="Average paragraph length in words.")
    single_line_paragraphs: int = Field(description="Count of short or isolated paragraphs.")
    punctuation: dict[str, int] = Field(description="Absolute frequencies of all punctuation marks.")
    signal_counts: dict[str, int] = Field(description="Match counts of signal keywords.")
    filter_count: int = Field(description="Total count of perception filter verbs.")
    chapters: list[ChapterMetrics] = Field(description="Detailed metrics of all individual chapters.")
    # --- Self-calibrating style features (house-style fingerprint, corpus level) ---
    staccato_pct: float = Field(default=0.0, description="Percentage of short sentences (≤ 6 words).")
    kaskade_pct: float = Field(default=0.0, description="Percentage of complex sentences (> 25 words).")
    sentence_cv: float = Field(default=0.0, description="Coefficient of variation of sentence lengths.")
    start_entropy: float = Field(default=0.0, description="Shannon entropy of sentence starters.")
    first_person_start_rate: float = Field(default=0.0, description="Share of first-person sentence openings.")
    passive_density: float = Field(default=0.0, description="Passive-voice markers per 1,000 words.")
    nominalization_density: float = Field(
        default=0.0, description="Nominalisations per 1,000 words."
    )
    adjective_density: float = Field(
        default=0.0, description="Adjective suffix matches per 1,000 words."
    )
    modal_density: float = Field(default=0.0, description="Modal verbs per 1,000 words.")
    filter_density: float = Field(default=0.0, description="Perception filter verbs per 1,000 words.")
    hd_d: float | None = Field(
        default=None, description="HD-D lexical diversity (McCarthy & Jarvis 2010)."
    )
    mtld: float | None = Field(
        default=None,
        description="MTLD Measure of Textual Lexical Diversity (McCarthy & Jarvis 2010).",
    )
    mattr: float | None = Field(
        default=None,
        description="MATTR Moving-Average Type-Token Ratio (Covington & McFall 2010).",
    )
    maas_a2: float | None = Field(
        default=None, description="Maas a² = (log N − log V) / (log N)² (Maas 1972)."
    )


class DossierStatus(BaseModel):
    """
    Synchronisation and consistency status of a single companion dossier.
    """

    ok: bool = Field(description="True when the dossier is 100% synchronized with the manuscript.")
    details: str = Field(description="Short summary of the verified domain.")
    drift: list[str] = Field(
        default_factory=list, description="List of identified discrepancies."
    )


class CorpusAuditReport(BaseModel):
    """
    Complete audit report to prevent fragmentation and documentation drift.
    """

    manuscript: str = Field(description="Filename of the analyzed manuscript.")
    raw_words: int = Field(description="Total full-text word count.")
    main_words: int = Field(description="Cleaned narrative prose word count.")
    chars: int = Field(description="Total character count.")
    asl: float = Field(description="Average sentence length.")
    ttr: float = Field(description="Lexical diversity.")
    markers: int = Field(description="Count of unresolved work markers (TODO/CHECK).")
    tracked_chapters: dict[str, int] = Field(
        default_factory=dict,
        description="Word counts of project-tracked chapters (label → words).",
    )
    dossiers: dict[str, DossierStatus] = Field(description="Audit results per companion dossier.")
    all_synced: bool = Field(description="True when all dossiers without exception are synchronized.")
