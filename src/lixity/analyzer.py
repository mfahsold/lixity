"""lixity.analyzer – High-performance text analysis and corpus linguistics engine.

Computes sentence-length architecture (ASL, CV, staccato/hypotaxis), lexical diversity
(TTR, Guiraud R, HD-D, MTLD, MATTR, Maas, Yule's K), language-calibrated readability
(Flesch family, LIX), dialogue ratios, register signals, and per-chapter metrics
with standard errors.
"""

import math
import os
import re
from collections import Counter
from dataclasses import dataclass

from .diversity import (
    hd_d as hd_d_value,
)
from .diversity import (
    hd_d_stats,
)
from .diversity import (
    maas_a2 as maas_a2_value,
)
from .diversity import (
    mattr as mattr_value,
)
from .diversity import (
    mtld as mtld_value,
)
from .diversity import (
    yules_k as yules_k_value,
)
from .language import compile_pattern, resolve_language
from .language_data import READABILITY
from .markdown_parser import split_chapters
from .models import (
    ChapterMetrics,
    CorpusConfig,
    CorpusMetrics,
    SentenceDistribution,
)
from .sentences import split_sentences
from .style_profile import dominance_from_hits
from .syllables import count_syllables as count_syllables_for

_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_HEADING_LINE = re.compile(r"(?m)^#+.*$")


@dataclass(frozen=True)
class SentenceStats:
    """Sentence-length architecture of a text (shared by corpus and chapters)."""

    total: int
    asl: float
    median: int
    std: float
    cv: float
    distribution: SentenceDistribution
    staccato_pct: float
    kaskade_pct: float


def share_se(pct: float, n: int) -> float:
    """Binomial standard error of a share in percentage points (plug-in)."""
    p = pct / 100.0
    return (math.sqrt(max(p * (1.0 - p), 0.0) / n) * 100.0) if n else 0.0


def count_se(cnt: int, words: int) -> float:
    """Poisson standard error of a count density (per 1,000 words)."""
    return (math.sqrt(cnt) * 1000.0 / words) if words else 0.0


class CorpusAnalyzer:
    """
    Stateless, thread-safe analysis engine for literary Markdown texts.
    Performs quantitative corpus linguistics, stylometry and chapter segmentation.
    """

    def __init__(self, config: CorpusConfig | None = None):
        """
        Initialises the analyzer with a configuration.
        If no configuration is passed, the default parameters apply.
        """
        self.config = config or CorpusConfig()
        self.lang = resolve_language(self.config)
        self._praes_re = compile_pattern(self.lang.praesens_regex)
        self._praet_re = compile_pattern(self.lang.praeteritum_regex)
        self._filter_re = compile_pattern(self.lang.filter_verbs_regex)
        self._word_re = re.compile(self.lang.word_regex)
        self._dialogue_re = re.compile(self.lang.dialogue_regex)
        # Style heuristics (self-calibrating house-style fingerprint)
        self._passive_re = compile_pattern(self.lang.passive_regex)
        self._nominal_re = compile_pattern(self.lang.nominal_regex)
        self._adjective_re = compile_pattern(self.lang.adjective_regex)
        self._modals = frozenset(w.lower() for w in self.lang.lexicon.get("modals", ()))
        self._starters = frozenset(w.lower() for w in self.lang.first_person_starters)
        self._content_blacklist = self.lang.function_words | self.lang.stopwords

    @staticmethod
    def _entropy(counts: Counter[str]) -> float:
        """Shannon entropy in bits over a token-type counter."""
        total = sum(counts.values())
        if not total:
            return 0.0
        return -sum((c / total) * math.log2(c / total) for c in counts.values())

    def _starter_stats(self, sentences: list[str]) -> tuple[float, float, float]:
        """(start entropy in bits, first-person-start rate, entropy standard error).

        The entropy uncertainty follows the Miller-Madow first-order variance
        of the maximum-likelihood estimator: Var(H) = [sum(p*log2^2(p)) - H^2] / n.
        """
        starters: Counter[str] = Counter()
        first_person = 0
        for s in sentences:
            tokens = self._word_re.findall(s)
            if not tokens:
                continue
            # Elision-aware match (fr: "J'aime" -> "je"/"j", en: "I'm" -> "i")
            first = tokens[0].lower()
            stem = first.split("'")[0].split("'")[0]
            starters[first] += 1
            if first in self._starters or stem in self._starters:
                first_person += 1
        total = sum(starters.values())
        rate = (first_person / total * 100.0) if total else 0.0
        entropy = self._entropy(starters)
        if not total:
            return entropy, rate, 0.0
        second = sum((c / total) * math.log2(c / total) ** 2 for c in starters.values())
        variance = (second - entropy**2) / total
        return entropy, rate, math.sqrt(max(0.0, variance))

    @staticmethod
    def _density(matches: int, words: int) -> float:
        """Occurrences per 1,000 tokens (length-comparable density)."""
        return (matches / words * 1000.0) if words else 0.0

    def _jsd_chapter(
        self,
        chapter_counter: Counter[str],
        corpus_counter: Counter[str],
        n_chapter: int,
        n_corpus: int,
        top_n: int = 5,
    ) -> tuple[float, list[str]]:
        """
        Jensen-Shannon distance of the chapter's word distribution to the rest
        of the corpus (leave-one-out, so small chapters are not self-biased).

        Returns (jsd, top driver words): contributions are additive per type,
        so the most divergent content words are interpretable.

        Only the chapter's own vocabulary is iterated. Types the chapter does
        not contain contribute exactly ``q * ln(2) / 2`` each, so their total
        is ``ln(2)/2 * (1 - n_chapter/rest)`` in closed form – an O(chapter
        types) computation instead of O(corpus types).
        """
        rest = n_corpus - n_chapter
        if rest < 1 or n_chapter < 1:
            return 0.0, []
        jsd = 0.0
        contribs: dict[str, float] = {}
        for w in sorted(chapter_counter):  # deterministic order: bit-identical across runs
            p = chapter_counter[w] / n_chapter
            q = (corpus_counter[w] - chapter_counter[w]) / rest
            m = 0.5 * (p + q)
            term = p * math.log(p / m)
            if q > 0.0:
                term += q * math.log(q / m)
            contrib = 0.5 * term
            contribs[w] = contrib
            jsd += contrib
        # Types absent from the chapter: p = 0, m = q/2 -> contribution q*ln(2)/2.
        jsd += 0.5 * math.log(2.0) * (1.0 - n_chapter / rest)
        top = [
            w
            for w, _ in sorted(contribs.items(), key=lambda kv: kv[1], reverse=True)
            if len(w) > 1 and w not in self._content_blacklist
        ][:top_n]
        return jsd, top

    def count_syllables(self, word: str) -> int:
        """Language-sensitive syllable counting (see :mod:`lixity.syllables`)."""
        return count_syllables_for(word, self.lang.key)

    def readability(self, asl: float, asw: float) -> tuple[float, str]:
        """Language-calibrated Reading Ease score and formula name; not clipped to 0–100."""
        rd = READABILITY.get(self.lang.key, READABILITY["generic"])
        score = rd["constant"] - rd["asl_coef"] * asl - rd["asw_coef"] * asw
        return score, rd["name"]

    def long_word_min(self) -> int:
        """Language-calibrated minimum letter count for LIX 'long words' (Björnsson)."""
        rd = READABILITY.get(self.lang.key, READABILITY["generic"])
        return int(rd["long_word_min"])

    def _sentence_stats(self, sentences: list[str]) -> SentenceStats:
        """Sentence-length architecture (lengths, ASL, median, CV, distribution)."""
        lengths = [n for n in (len(self._word_re.findall(s)) for s in sentences) if n > 0]
        total = len(lengths)
        asl = sum(lengths) / total if total else 0.0
        sorted_lengths = sorted(lengths)
        median_sl = sorted_lengths[total // 2] if total else 0
        variance = sum((x - asl) ** 2 for x in lengths) / total if total else 0.0
        std = math.sqrt(variance)
        short = sum(1 for x in lengths if x <= 6)
        medium = sum(1 for x in lengths if 7 <= x <= 15)
        long_ = sum(1 for x in lengths if 16 <= x <= 25)
        complex_ = sum(1 for x in lengths if x > 25)

        def _pct(count: int) -> float:
            return (count / total * 100.0) if total else 0.0

        return SentenceStats(
            total=total,
            asl=asl,
            median=median_sl,
            std=std,
            cv=(std / asl) if asl else 0.0,
            distribution=SentenceDistribution(
                short_count=short,
                short_pct=_pct(short),
                medium_count=medium,
                medium_pct=_pct(medium),
                long_count=long_,
                long_pct=_pct(long_),
                complex_count=complex_,
                complex_pct=_pct(complex_),
            ),
            staccato_pct=_pct(short),
            kaskade_pct=_pct(complex_),
        )

    def _paragraph_stats(self, text: str) -> tuple[int, float, int]:
        """(prose paragraphs, average words per paragraph, one-liner count)."""
        raw = [p.strip() for p in text.split("\n\n") if p.strip()]
        prose = [p for p in raw if not p.startswith(("#", "|", "-", "*"))]
        lengths = [len(p.split()) for p in prose]
        total = len(lengths)
        average = sum(lengths) / total if total else 0.0
        one_liners = sum(
            1
            for length in lengths
            if length <= self.config.min_paragraph_length_for_oneliner and length != 8
        )
        return total, average, one_liners

    def _punctuation_profile(self, text: str) -> dict[str, int]:
        """Language-neutral punctuation counts for the JSON contract."""
        return {
            "periods": text.count("."),
            "commas": text.count(","),
            "dashes": len(re.findall(r"[–—]", text)),
            "colons": text.count(":"),
            "semicolons": text.count(";"),
            "questions": text.count("?"),
            "exclamations": text.count("!"),
            "ellipses": len(re.findall(r"(?:…|\.{3})", text)),
        }

    def _chapter_metrics(
        self, num: int, title: str, body: str, lw_min: int
    ) -> tuple[ChapterMetrics | None, list[str]]:
        """Per-chapter metrics (style features, uncertainty, tense, JSD input)."""
        cl_b = _RE_HTML_COMMENT.sub("", body)
        c_words = self._word_re.findall(cl_b)
        if not c_words:
            return None, []

        n_cw = len(c_words)
        c_lower = [w.lower() for w in c_words]
        c_sentences = [
            s for s in split_sentences(cl_b, self.config.language) if not s.startswith("#")
        ]
        stats = self._sentence_stats(c_sentences)

        c_dial = self._dialogue_re.findall(cl_b)
        c_dial_words = sum(len(m.split()) for m in c_dial)
        c_dial_pct = (c_dial_words / n_cw) * 100.0 if n_cw else 0.0
        c_ttr = len(set(c_lower)) / n_cw if n_cw else 0.0
        c_signals = {
            s_name: len(re.findall(s_pat, cl_b, re.IGNORECASE))
            for s_name, s_pat in self.lang.signal_keywords.items()
        }
        c_motifs = {
            m_name: len(re.findall(m_pat, cl_b, re.IGNORECASE))
            for m_name, m_pat in self.config.motif_regexes.items()
        }
        c_fil = len(self._filter_re.findall(cl_b))
        dominance = dominance_from_hits(
            len(self._praes_re.findall(cl_b)), len(self._praet_re.findall(cl_b))
        )

        c_start_entropy, c_first_rate, c_entropy_se = self._starter_stats(c_sentences)
        c_passive_cnt = len(self._passive_re.findall(cl_b))
        c_nominal_cnt = len(self._nominal_re.findall(cl_b))
        c_adjective_cnt = len(self._adjective_re.findall(cl_b))
        c_modal_cnt = sum(1 for t in c_lower if t in self._modals)
        c_long_words = sum(1 for t in c_words if len(t) > lw_min)
        c_long_pct = (c_long_words / n_cw * 100.0) if n_cw else 0.0
        c_guiraud = len(set(c_lower)) / math.sqrt(n_cw) if n_cw else 0.0
        c_hd_d, c_hd_d_se = hd_d_stats(c_lower)
        c_func_pct = (
            sum(1 for t in c_lower if t in self.lang.function_words) / n_cw * 100.0 if n_cw else 0.0
        )

        # Measurement uncertainty per feature (documented plug-ins)
        c_se: dict[str, float] = {
            "asl": (stats.std / math.sqrt(stats.total)) if stats.total else 0.0,
            "staccato_pct": share_se(stats.staccato_pct, stats.total),
            "kaskade_pct": share_se(stats.kaskade_pct, stats.total),
            "sentence_cv": (
                (stats.cv / math.sqrt(2.0 * stats.total)) * math.sqrt(1.0 + 2.0 * stats.cv**2)
                if stats.total
                else 0.0
            ),
            "dialog_pct": share_se(c_dial_pct, n_cw),
            "function_word_pct": share_se(c_func_pct, n_cw),
            "filter_density": count_se(c_fil, n_cw),
            "modal_density": count_se(c_modal_cnt, n_cw),
            "passive_density": count_se(c_passive_cnt, n_cw),
            "nominalization_density": count_se(c_nominal_cnt, n_cw),
            "adjective_density": count_se(c_adjective_cnt, n_cw),
            "long_word_pct": share_se(c_long_pct, n_cw),
            "start_entropy": c_entropy_se,
            "first_person_start_rate": share_se(c_first_rate, stats.total),
            "guiraud_r": (0.5 * c_guiraud / math.sqrt(n_cw)) if n_cw else 0.0,
        }
        if c_hd_d is not None:
            c_se["hd_d"] = c_hd_d_se

        chapter = ChapterMetrics(
            num=num,
            title=title,
            words=n_cw,
            sentences=stats.total,
            asl=stats.asl,
            dialog_pct=c_dial_pct,
            ttr=c_ttr,
            motif_counts=c_motifs,
            filter_verbs=c_fil,
            dominance=dominance,
            signal_matches=c_signals,
            staccato_pct=stats.staccato_pct,
            kaskade_pct=stats.kaskade_pct,
            sentence_cv=stats.cv,
            start_entropy=c_start_entropy,
            first_person_start_rate=c_first_rate,
            passive_density=self._density(c_passive_cnt, n_cw),
            nominalization_density=self._density(c_nominal_cnt, n_cw),
            adjective_density=self._density(c_adjective_cnt, n_cw),
            modal_density=self._density(c_modal_cnt, n_cw),
            filter_density=self._density(c_fil, n_cw),
            long_word_pct=c_long_pct,
            guiraud_r=c_guiraud,
            hd_d=c_hd_d,
            function_word_pct=c_func_pct,
            style_se=c_se,
        )
        return chapter, c_lower

    def analyze_text(self, full_text: str) -> CorpusMetrics:
        """
        Performs the complete stylometric and quantitative analysis on
        a passed text string.

        Workflow:
        1. Separation of the scholarly appendix (single source of truth).
        2. Filtering of Markdown HTML comments (<!-- ... -->).
        3. Tokenisation and capture of vocabulary types.
        4. Computation of lexical diversity metrics (TTR, Guiraud, Yule).
        5. Sentence segmentation and sentence-length architecture (without heading artefacts).
        6. Readability indices (Flesch family, LIX).
        7. Dialogue and paragraph economy.
        8. Punctuation and signal word frequencies.
        9. Chapter-wise segmentation and tense classification.

        Returns:
            CorpusMetrics object with all computed metrics.
        """
        # 1. Main text vs. appendix, comments removed
        if self.config.appendix_marker and self.config.appendix_marker in full_text:
            main_text, _ = full_text.split(self.config.appendix_marker, 1)
        else:
            main_text = full_text
        cleaned_full = _RE_HTML_COMMENT.sub("", full_text)
        cleaned_main = _RE_HTML_COMMENT.sub("", main_text)

        raw_words = len(cleaned_full.split())
        clean_words = len(cleaned_main.split())
        raw_chars = len(cleaned_full)
        clean_chars = len(cleaned_main)

        # 2. Tokenisation
        tokens = self._word_re.findall(cleaned_main)
        n_tokens = len(tokens)
        lower_tokens = [t.lower() for t in tokens]
        v_types = len(set(lower_tokens))
        freqs = Counter(lower_tokens)

        # 3. Lexical range & stability
        ttr = v_types / n_tokens if n_tokens else 0.0
        guiraud_r = v_types / math.sqrt(n_tokens) if n_tokens else 0.0

        # 4. Sentence-length architecture (headings removed: no word carry-over)
        prose_for_sents = _RE_HEADING_LINE.sub("", cleaned_main)
        sentences = split_sentences(prose_for_sents, self.config.language)
        stats = self._sentence_stats(sentences)
        start_entropy, first_person_start_rate, _entropy_se = self._starter_stats(sentences)

        # 5. Readability & complexity (language-calibrated Flesch family + LIX)
        total_syllables = sum(self.count_syllables(t) for t in tokens)
        asw = total_syllables / n_tokens if n_tokens else 0.0
        flesch_de, flesch_variant = self.readability(stats.asl, asw)
        lw_min = self.long_word_min()
        long_words = sum(1 for t in tokens if len(t) > lw_min)
        pct_long_words = (long_words / n_tokens) * 100.0 if n_tokens else 0.0
        lix = stats.asl + pct_long_words

        # 6. Dialogue ratio
        dialog_matches = self._dialogue_re.findall(cleaned_main)
        dialog_words = sum(len(m.split()) for m in dialog_matches)
        dialog_ratio = (dialog_words / clean_words) * 100.0 if clean_words else 0.0

        # 7. Paragraph economy, punctuation, signals
        total_paras, avg_para_len, single_line_paras = self._paragraph_stats(cleaned_main)
        punctuation = self._punctuation_profile(cleaned_main)
        signal_counts = {
            name: len(re.findall(pat, cleaned_main, re.IGNORECASE))
            for name, pat in self.lang.signal_keywords.items()
        }
        filter_cnt = len(self._filter_re.findall(cleaned_main))

        # 8. Style densities (per 1,000 tokens, length-comparable)
        passive_density = self._density(len(self._passive_re.findall(cleaned_main)), n_tokens)
        nominalization_density = self._density(
            len(self._nominal_re.findall(cleaned_main)), n_tokens
        )
        adjective_density = self._density(len(self._adjective_re.findall(cleaned_main)), n_tokens)
        modal_density = self._density(sum(1 for t in lower_tokens if t in self._modals), n_tokens)
        filter_density = self._density(filter_cnt, n_tokens)

        # 9. Chapter-wise segmentation (shared split_chapters: front matter +
        #    appendix + empty-body rules identical to the structure modules).
        chapters: list[ChapterMetrics] = []
        chapter_tokens: list[list[str]] = []
        for _split_num, title, body in split_chapters(main_text, self.config):
            chapter, c_lower = self._chapter_metrics(len(chapters) + 1, title, body, lw_min)
            if chapter is None:
                continue
            chapters.append(chapter)
            chapter_tokens.append(c_lower)

        # 10. Jensen-Shannon divergence per chapter vs. the rest (leave-one-out)
        for chapter, c_lower in zip(chapters, chapter_tokens, strict=False):
            chapter.jsd, chapter.jsd_top_words = self._jsd_chapter(
                Counter(c_lower), freqs, len(c_lower), n_tokens
            )

        return CorpusMetrics(
            raw_words=raw_words,
            clean_words=clean_words,
            raw_chars=raw_chars,
            clean_chars=clean_chars,
            tokens=n_tokens,
            vocab_types=v_types,
            ttr=ttr,
            guiraud_r=guiraud_r,
            yules_k=yules_k_value(lower_tokens),
            total_sentences=stats.total,
            asl=stats.asl,
            median_sl=stats.median,
            std_sl=stats.std,
            sentence_dist=stats.distribution,
            asw=asw,
            flesch_de=flesch_de,
            flesch_variant=flesch_variant,
            lix=lix,
            dialog_words=dialog_words,
            dialog_ratio=dialog_ratio,
            total_paragraphs=total_paras,
            avg_paragraph_len=avg_para_len,
            single_line_paragraphs=single_line_paras,
            punctuation=punctuation,
            signal_counts=signal_counts,
            filter_count=filter_cnt,
            chapters=chapters,
            staccato_pct=stats.staccato_pct,
            kaskade_pct=stats.kaskade_pct,
            sentence_cv=stats.cv,
            start_entropy=start_entropy,
            first_person_start_rate=first_person_start_rate,
            passive_density=passive_density,
            nominalization_density=nominalization_density,
            adjective_density=adjective_density,
            modal_density=modal_density,
            filter_density=filter_density,
            hd_d=hd_d_value(lower_tokens),
            mtld=mtld_value(lower_tokens),
            mattr=mattr_value(lower_tokens),
            maas_a2=maas_a2_value(n_tokens, v_types),
        )

    def analyze_file(self, filepath: str) -> CorpusMetrics:
        """
        Reads a UTF-8 text file and delegates to analyze_text.

        Parameters:
            filepath: Absolute or relative file path to the Markdown manuscript.

        Returns:
            CorpusMetrics object.

        Raises:
            FileNotFoundError: If the file does not exist at the given path.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Manuscript file not found: {filepath}")
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        return self.analyze_text(content)
