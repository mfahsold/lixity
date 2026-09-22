"""lixity.analyzer – High-performance text analysis and corpus linguistics engine.

Computes sentence-length architecture (ASL, CV, staccato/hypotaxis), lexical diversity
(TTR, Guiraud R, HD-D, MTLD, MATTR, Maas, Yule's K), language-calibrated readability
(Flesch family, LIX), dialogue ratios, register signals, and per-chapter metrics
with standard errors.
"""

import math
import os
import random
import re
from collections import Counter

from .language import compile_pattern, resolve_language
from .language_data import READABILITY
from .models import (
    ChapterMetrics,
    CorpusConfig,
    CorpusMetrics,
    SentenceDistribution,
)
from .sentences import split_sentences
from .style_profile import dominance_from_hits

_RE_DE_DIPHTHONG = re.compile(r"(ei|ey|ai|ay|au|eu|äu|ie|aa|ee|oo)")
_RE_DE_VOWEL = re.compile(r"[aeiouyäöü]")
_RE_EN_CLEAN = re.compile(r"[^a-z]")
_RE_EN_VOWEL_GROUP = re.compile(r"[aeiouy]+")
_RE_FR_CLEAN = re.compile(r"[^a-zàâäéèêëîïôöùûüÿçœæ]")
_RE_FR_VOWEL_GROUP = re.compile(r"[aeiouyàâäéèêëîïôöùûüÿœæ]+")
_RE_ES_CLEAN = re.compile(r"[^a-záéíóúüñ]")
_RE_IT_CLEAN = re.compile(r"[^a-zàèéìíòóùú]")
_RE_PT_CLEAN = re.compile(r"[^a-zàâãáéêíóôõúüç]")
_RE_PT_VOWEL_GROUP = re.compile(r"[aeiouàâãáéêíóôõúü]+")
_RE_NL_CLEAN = re.compile(r"[^a-záéíóúäëïöüâêîôû]")
_RE_NL_VOWEL_GROUP = re.compile(r"[aeiouyáéíóúäëïöüâêîôûI]+")
_RE_GENERIC_VOWEL_GROUP = re.compile(r"[aeiouy]+")
_RE_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_RE_HEADING_LINE = re.compile(r"(?m)^#+.*$")


# Minimum token count for length-sensitive lexical-diversity indices
# (Bestgen 2024/2025: all LD indices are unreliable on very short texts).
MIN_TOKENS_LD = 100


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
    def hd_d(tokens: list[str], seed: int = 42, min_samples: int = 5) -> float | None:
        """
        HD-D: length-robust lexical diversity (McCarthy & Jarvis 2010).

        Mean of the type-variety of 42 random samples of 35 consecutive tokens;
        variety per sample = 1 - sum(c_t*(c_t-1)) / (n*(n-1)).
        Deterministic via fixed seed; returns None for texts too short for
        ``min_samples`` disjoint windows (no reliable statement).
        """
        value, _ = CorpusAnalyzer.hd_d_stats(tokens, seed=seed, min_samples=min_samples)
        return value

    @staticmethod
    def hd_d_stats(
        tokens: list[str], seed: int = 42, min_samples: int = 5
    ) -> tuple[float | None, float]:
        """
        HD-D with its estimation uncertainty: returns (value, standard error).

        The standard error is the sample standard deviation of the up to 42
        sample diversities divided by sqrt(#samples) – the documented plug-in
        estimator of the HD-D mean.
        """
        n = len(tokens)
        sample_size = 35
        if n < sample_size * min_samples:
            return None, 0.0
        max_samples = min(42, n // sample_size)
        rng = random.Random(seed)  # noqa: S311 – deterministic sampling, not cryptography
        starts = sorted(rng.sample(range(n - sample_size + 1), max_samples))
        diversities = []
        for s in starts:
            sample = tokens[s : s + sample_size]
            repeat = sum(c * (c - 1) for c in Counter(sample).values())
            diversities.append(1.0 - repeat / (sample_size * (sample_size - 1)))
        mean = sum(diversities) / len(diversities)
        if len(diversities) < 2:
            return mean, 0.0
        variance = sum((d - mean) ** 2 for d in diversities) / (len(diversities) - 1)
        return mean, math.sqrt(variance) / math.sqrt(len(diversities))

    @staticmethod
    def _entropy(counts: Counter) -> float:
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
        starters: Counter = Counter()
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
        chapter_counter: Counter,
        corpus_counter: Counter,
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

    @staticmethod
    def count_syllables_de(word: str) -> int:
        """
        Approximate syllable counting for German words.
        Normalises diphthongs ('ei', 'ie', 'au', 'eu', 'äu') to a single sound
        and counts the remaining vowel clusters. Guarantees at least 1 syllable.
        """
        w = word.lower()
        # Reduce diphthongs and double vowels to a single sound
        w = _RE_DE_DIPHTHONG.sub("V", w)
        w = _RE_DE_VOWEL.sub("V", w)
        return max(1, w.count("V"))

    @staticmethod
    def count_syllables_en(word: str) -> int:
        """English syllable heuristic: vowel groups + silent-e / -ed / -es / -le rules (~95%)."""
        w = _RE_EN_CLEAN.sub("", word.lower())
        if not w:
            return 0
        exceptions = {
            "the": 1,
            "are": 1,
            "were": 1,
            "there": 1,
            "here": 1,
            "where": 1,
            "one": 1,
            "once": 1,
            "eye": 1,
            "hour": 2,
            "our": 1,
            "your": 1,
            "fire": 2,
            "hire": 2,
            "more": 1,
            "sore": 1,
            "being": 2,
            "doing": 2,
            "going": 2,
            "seeing": 2,
            "said": 1,
            "says": 1,
            "people": 2,
            "business": 2,
            "different": 3,
            "interest": 2,
            "evening": 3,
            "water": 2,
            "little": 2,
            "every": 2,
            "very": 2,
            "many": 2,
            "any": 2,
            "only": 2,
            "both": 1,
            "though": 1,
            "through": 1,
            "thought": 1,
            "although": 2,
            "enough": 2,
            "rough": 1,
            "tough": 1,
            "cough": 1,
            "bought": 1,
            "brought": 1,
            "ought": 1,
            "island": 2,
            "aisle": 1,
            "honest": 2,
        }
        if w in exceptions:
            return exceptions[w]
        count = len(_RE_EN_VOWEL_GROUP.findall(w))
        if w.endswith("e") and count > 1:
            if w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy":
                pass  # syllabic l ("table", "people") keeps its vowel
            elif not w.endswith(("ee", "ye", "ie", "oe")):
                count -= 1
        if w.endswith("ed") and not w.endswith(("ted", "ded")) and count > 1:
            count -= 1
        if (
            w.endswith("es")
            and not w.endswith(("ses", "xes", "zes", "ches", "shes", "ges"))
            and count > 1
        ):
            count -= 1
        return max(1, count)

    @staticmethod
    def count_syllables_fr(word: str) -> int:
        """French syllable heuristic: vowel groups with mute final -e / -ent / -es (~90%)."""
        w = _RE_FR_CLEAN.sub("", word.lower())
        if not w:
            return 0
        count = len(_RE_FR_VOWEL_GROUP.findall(w))
        if w.endswith("e") and not w.endswith(("ée", "eé", "eë", "eü")) and count > 1:
            count -= 1
        if w.endswith("ent") and count > 1:
            count -= 1
        if w.endswith("es") and count > 1 and w[-3] not in "aeiouyàâäéèêëîïôöùûüÿœæ":
            count -= 1
        return max(1, count)

    @staticmethod
    def count_syllables_es(word: str) -> int:
        """Spanish syllable heuristic: strong/weak vowel diphthong detection (~97%)."""
        w = _RE_ES_CLEAN.sub("", word.lower())
        if not w:
            return 0
        marked = w.replace("í", "I").replace("ú", "U")
        strong = "aeoáéó"
        weak = "iuü"
        count = 0
        i = 0
        while i < len(marked):
            c = marked[i]
            if c in strong or c in "IU":
                count += 1
                j = i + 1
                while j < len(marked) and marked[j] in weak:
                    j += 1
                    if j < len(marked) and marked[j] in strong:
                        j += 1
                i = j
            else:
                i += 1
        return max(1, count)

    @staticmethod
    def count_syllables_it(word: str) -> int:
        """Italian syllable heuristic: weak i/u join adjacent vowels into diphthongs (~98%)."""
        w = _RE_IT_CLEAN.sub("", word.lower())
        if not w:
            return 0
        count = 0
        i = 0
        while i < len(w):
            c = w[i]
            if c in "aeiouàèéìíòóùú":
                count += 1
                j = i + 1
                while j < len(w) and w[j] in "iu":
                    j += 1
                i = j
            else:
                i += 1
        return max(1, count)

    @staticmethod
    def count_syllables_pt(word: str) -> int:
        """Portuguese syllable heuristic: vowel groups incl. nasal vowels/diphthongs (~95%)."""
        w = _RE_PT_CLEAN.sub("", word.lower())
        if not w:
            return 0
        count = len(_RE_PT_VOWEL_GROUP.findall(w))
        return max(1, count)

    @staticmethod
    def count_syllables_nl(word: str) -> int:
        """Dutch syllable heuristic: 'ij' counts as one nucleus, vowel groups otherwise (~94%)."""
        w = _RE_NL_CLEAN.sub("", word.lower())
        if not w:
            return 0
        marked = w.replace("ij", "I").replace("IJ", "I")
        count = len(_RE_NL_VOWEL_GROUP.findall(marked))
        return max(1, count)

    def count_syllables(self, word: str) -> int:
        """
        Language-sensitive syllable counting based on the configured language.
        Dispatches to per-language heuristics (de, en, fr, es, it, pt, nl);
        falls back to generic vowel-cluster counting.
        """
        mode = self.lang.syllable_mode
        fn = {
            "de": self.count_syllables_de,
            "en": self.count_syllables_en,
            "fr": self.count_syllables_fr,
            "es": self.count_syllables_es,
            "it": self.count_syllables_it,
            "pt": self.count_syllables_pt,
            "nl": self.count_syllables_nl,
        }.get(mode)
        if fn is not None:
            return fn(word)
        w = word.lower()
        w = _RE_GENERIC_VOWEL_GROUP.sub("V", w)
        return max(1, w.count("V"))

    def readability(self, asl: float, asw: float) -> tuple[float, str]:
        """Language-calibrated Flesch-type Reading Ease score (0–100) + formula name."""
        rd = READABILITY.get(self.lang.key, READABILITY["generic"])
        score = rd["constant"] - rd["asl_coef"] * asl - rd["asw_coef"] * asw
        return score, rd["name"]

    def long_word_min(self) -> int:
        """Language-calibrated minimum letter count for LIX 'long words' (Björnsson)."""
        rd = READABILITY.get(self.lang.key, READABILITY["generic"])
        return int(rd["long_word_min"])

    @staticmethod
    def mtld(tokens: list[str], threshold: float = 0.72) -> float | None:
        """
        MTLD: length-invariant lexical diversity (McCarthy & Jarvis 2010).

        Mean length of sequential token runs that maintain TTR >= threshold;
        computed forward and backward then averaged. Returns None below
        ``MIN_TOKENS_LD`` (100) tokens – Bestgen (2024/2025) shows that all
        lexical-diversity indices are unreliable on very short texts – and
        when no factor completes (all-unique token sequences).
        """
        n = len(tokens)
        if n < MIN_TOKENS_LD:
            return None

        def _factors(seq: list[str]) -> float:
            factors = 0.0
            types: set[str] = set()
            seg_len = 0
            for tok in seq:
                types.add(tok)
                seg_len += 1
                ttr = len(types) / seg_len
                if ttr <= threshold:
                    factors += 1.0
                    types.clear()
                    seg_len = 0
            if seg_len > 0:
                ttr = len(types) / seg_len
                factors += (1.0 - ttr) / (1.0 - threshold)
            return factors

        fwd = _factors(tokens)
        bwd = _factors(tokens[::-1])
        total_factors = (fwd + bwd) / 2.0
        if total_factors <= 0.0:
            return None
        return n / total_factors

    @staticmethod
    def mattr(tokens: list[str], window: int = 50) -> float | None:
        """
        MATTR: moving-average type-token ratio (Covington & McFall 2010).

        Mean TTR over sliding windows of ``window`` tokens – the only index
        shown to be stable across all text lengths. None if text is shorter
        than the window. O(N) via an incremental type counter.
        """
        n = len(tokens)
        if n < window:
            return None
        counts: Counter[str] = Counter(tokens[:window])
        distinct = len(counts)
        total = distinct
        for i in range(window, n):
            leaving = tokens[i - window]
            counts[leaving] -= 1
            if counts[leaving] == 0:
                del counts[leaving]
                distinct -= 1
            entering = tokens[i]
            if counts[entering] == 0:
                distinct += 1
            counts[entering] += 1
            total += distinct
        windows = n - window + 1
        return total / (window * windows)

    @staticmethod
    def yules_k(tokens: list[str]) -> float:
        """Yule's characteristic K = 10^4 * (Σ m² V_m − N) / N² (Yule 1944).

        0.0 for empty input or all-unique tokens (no repetition).
        """
        n = len(tokens)
        if n == 0:
            return 0.0
        counts = Counter(tokens)
        m2 = sum(c * c for c in counts.values())
        return 10000.0 * (m2 - n) / (n * n)

    @staticmethod
    def maas_a2(n_tokens: int, v_types: int) -> float | None:
        """Maas a² = (log N − log V) / (log N)² – lower = more diverse (Maas 1972).

        Requires ``MIN_TOKENS_LD`` tokens; shorter texts return None.
        """
        if n_tokens < MIN_TOKENS_LD or v_types <= 1:
            return None
        log_n = math.log10(n_tokens)
        log_v = math.log10(v_types)
        return (log_n - log_v) / (log_n**2)

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
        6. Readability indices (Flesch DE, LIX).
        7. Dialogue and paragraph economy.
        8. Punctuation and signal word frequencies.
        9. Chapter-wise segmentation and tense classification.

        Returns:
            CorpusMetrics object with all computed metrics.
        """
        # 1. Separation of main text vs. appendix
        if self.config.appendix_marker and self.config.appendix_marker in full_text:
            main_text, _ = full_text.split(self.config.appendix_marker, 1)
        else:
            main_text = full_text

        # Remove Markdown comments
        cleaned_full = _RE_HTML_COMMENT.sub("", full_text)
        cleaned_main = _RE_HTML_COMMENT.sub("", main_text)

        raw_words = len(cleaned_full.split())
        clean_words = len(cleaned_main.split())
        raw_chars = len(cleaned_full)
        clean_chars = len(cleaned_main)

        # Word tokenisation
        tokens = self._word_re.findall(cleaned_main)
        n_tokens = len(tokens)
        lower_tokens = [t.lower() for t in tokens]
        v_types = len(set(lower_tokens))
        freqs = Counter(lower_tokens)

        # Lexical range & stability
        yules_k = self.yules_k(lower_tokens)
        ttr = v_types / n_tokens if n_tokens else 0.0
        guiraud_r = v_types / math.sqrt(n_tokens) if n_tokens else 0.0

        # Sentence metrics (remove headings before segmentation to prevent word carry-over)
        prose_for_sents = _RE_HEADING_LINE.sub("", cleaned_main)
        raw_sents = split_sentences(prose_for_sents, self.config.language)
        sent_lens = [
            count for count in (len(self._word_re.findall(s)) for s in raw_sents) if count > 0
        ]
        total_sent = len(sent_lens)
        asl = sum(sent_lens) / total_sent if total_sent else 0.0
        sorted_lens = sorted(sent_lens)
        median_sl = sorted_lens[total_sent // 2] if total_sent else 0
        variance_sl = sum((sl - asl) ** 2 for sl in sent_lens) / total_sent if total_sent else 0.0
        std_sl = math.sqrt(variance_sl)

        # Sentence-length architecture
        short_s = sum(1 for sl in sent_lens if sl <= 6)
        med_s = sum(1 for sl in sent_lens if 7 <= sl <= 15)
        long_s = sum(1 for sl in sent_lens if 16 <= sl <= 25)
        comp_s = sum(1 for sl in sent_lens if sl > 25)

        sent_dist = SentenceDistribution(
            short_count=short_s,
            short_pct=(short_s / total_sent * 100.0) if total_sent else 0.0,
            medium_count=med_s,
            medium_pct=(med_s / total_sent * 100.0) if total_sent else 0.0,
            long_count=long_s,
            long_pct=(long_s / total_sent * 100.0) if total_sent else 0.0,
            complex_count=comp_s,
            complex_pct=(comp_s / total_sent * 100.0) if total_sent else 0.0,
        )

        # Style features (corpus level, house-style fingerprint)
        staccato_pct = (short_s / total_sent * 100.0) if total_sent else 0.0
        kaskade_pct = (comp_s / total_sent * 100.0) if total_sent else 0.0
        sentence_cv = (std_sl / asl) if asl else 0.0
        start_entropy, first_person_start_rate, _entropy_se = self._starter_stats(raw_sents)

        # Readability & complexity (language-calibrated Flesch family + LIX)
        total_syllables = sum(self.count_syllables(t) for t in tokens)
        asw = total_syllables / n_tokens if n_tokens else 0.0
        flesch_de, flesch_variant = self.readability(asl, asw)
        lw_min = self.long_word_min()
        long_words = sum(1 for t in tokens if len(t) > lw_min)
        pct_long_words = (long_words / n_tokens) * 100.0 if n_tokens else 0.0
        lix = asl + pct_long_words

        # Dialogue ratio (detection of direct speech)
        dialog_matches = self._dialogue_re.findall(cleaned_main)
        dialog_words = sum(len(m.split()) for m in dialog_matches)
        dialog_ratio = (dialog_words / clean_words) * 100.0 if clean_words else 0.0

        # Paragraph economy
        raw_paras = [p.strip() for p in cleaned_main.split("\n\n") if p.strip()]
        prose_paras = [
            p
            for p in raw_paras
            if not p.startswith("#")
            and not p.startswith("|")
            and not p.startswith("-")
            and not p.startswith("*")
        ]
        para_lens = [len(p.split()) for p in prose_paras]
        total_paras = len(para_lens)
        avg_para_len = sum(para_lens) / total_paras if total_paras else 0.0
        single_line_paras = sum(
            1 for pl in para_lens if pl <= self.config.min_paragraph_length_for_oneliner and pl != 8
        )

        # Punctuation as a stylistic seismograph (language-neutral JSON keys)
        punctuation = {
            "periods": cleaned_main.count("."),
            "commas": cleaned_main.count(","),
            "dashes": len(re.findall(r"[–—]", cleaned_main)),
            "colons": cleaned_main.count(":"),
            "semicolons": cleaned_main.count(";"),
            "questions": cleaned_main.count("?"),
            "exclamations": cleaned_main.count("!"),
            "ellipses": len(re.findall(r"(?:…|\.{3})", cleaned_main)),
        }

        # Signal & filter words
        signal_counts = {
            name: len(re.findall(pat, cleaned_main, re.IGNORECASE))
            for name, pat in self.lang.signal_keywords.items()
        }
        filter_cnt = len(self._filter_re.findall(cleaned_main))

        # Style densities (per 1,000 tokens, length-comparable)
        passive_density = self._density(len(self._passive_re.findall(cleaned_main)), n_tokens)
        nominalization_density = self._density(
            len(self._nominal_re.findall(cleaned_main)), n_tokens
        )
        adjective_density = self._density(len(self._adjective_re.findall(cleaned_main)), n_tokens)
        modal_density = self._density(sum(1 for t in lower_tokens if t in self._modals), n_tokens)
        filter_density = self._density(filter_cnt, n_tokens)
        hd_d = self.hd_d(lower_tokens)
        mtld = self.mtld(lower_tokens)
        mattr = self.mattr(lower_tokens)
        maas_a2 = self.maas_a2(n_tokens, v_types)

        # Chapter-wise segmentation
        raw_chapters = re.split(self.config.chapter_regex, main_text)

        # Front matter (everything before the first chapter) is not a chapter:
        # if the first section starts with an H1 (book title/front matter) or
        # contains only editorial comments, it is skipped – otherwise the
        # chapter numbering would shift by one.
        if raw_chapters:
            first_clean = re.sub(r"<!--.*?-->", "", raw_chapters[0], flags=re.DOTALL).strip()
            if first_clean.startswith("# ") or not first_clean:
                raw_chapters = raw_chapters[1:]

        chapters: list[ChapterMetrics] = []
        chapter_tokens: list[list[str]] = []
        c_idx = 1

        for raw_chapter in raw_chapters:
            chapter_text = raw_chapter.strip()
            if not chapter_text:
                continue
            lines = chapter_text.split("\n")
            title = lines[0].strip().replace("# ", "")
            body = "\n".join(lines[1:]).strip()
            cl_b = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
            c_words = self._word_re.findall(cl_b)
            if not c_words:
                continue

            c_sents = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", cl_b)
                if s.strip() and not s.strip().startswith("#")
            ]
            c_sent_lens = [
                len(self._word_re.findall(s)) for s in c_sents if len(self._word_re.findall(s)) > 0
            ]
            n_cs = len(c_sent_lens)
            c_asl = sum(c_sent_lens) / n_cs if n_cs else 0.0

            c_dial = self._dialogue_re.findall(cl_b)
            c_dial_words = sum(len(m.split()) for m in c_dial)
            c_dial_pct = (c_dial_words / len(c_words)) * 100.0 if c_words else 0.0

            c_lower = [w.lower() for w in c_words]
            c_ttr = len(set(c_lower)) / len(c_words) if c_words else 0.0

            c_signals: dict[str, int] = {}
            for s_name, s_pat in self.lang.signal_keywords.items():
                c_signals[s_name] = len(re.findall(s_pat, cl_b, re.IGNORECASE))

            c_motifs = {
                m_name: len(re.findall(m_pat, cl_b, re.IGNORECASE))
                for m_name, m_pat in self.config.motif_regexes.items()
            }
            c_fil = len(self._filter_re.findall(cl_b))

            pr_c = len(self._praes_re.findall(cl_b))
            pt_c = len(self._praet_re.findall(cl_b))
            dom = dominance_from_hits(pr_c, pt_c)

            # --- Style features per chapter (house-style fingerprint) ---
            n_cw = len(c_words)
            c_short = sum(1 for sl in c_sent_lens if sl <= 6)
            c_comp = sum(1 for sl in c_sent_lens if sl > 25)
            c_staccato = (c_short / n_cs * 100.0) if n_cs else 0.0
            c_kaskade = (c_comp / n_cs * 100.0) if n_cs else 0.0
            c_std = math.sqrt(sum((sl - c_asl) ** 2 for sl in c_sent_lens) / n_cs) if n_cs else 0.0
            c_cv = (c_std / c_asl) if c_asl else 0.0
            c_start_entropy, c_first_rate, c_entropy_se = self._starter_stats(c_sents)
            c_passive_cnt = len(self._passive_re.findall(cl_b))
            c_nominal_cnt = len(self._nominal_re.findall(cl_b))
            c_adjective_cnt = len(self._adjective_re.findall(cl_b))
            c_modal_cnt = sum(1 for t in c_lower if t in self._modals)
            c_passive = self._density(c_passive_cnt, n_cw)
            c_nominal = self._density(c_nominal_cnt, n_cw)
            c_adjective = self._density(c_adjective_cnt, n_cw)
            c_modal = self._density(c_modal_cnt, n_cw)
            c_filter_density = self._density(c_fil, n_cw)
            c_long_words = sum(1 for t in c_words if len(t) > lw_min)
            c_long_pct = (c_long_words / n_cw * 100.0) if n_cw else 0.0
            c_guiraud = len(set(c_lower)) / math.sqrt(n_cw) if n_cw else 0.0
            c_hd_d, c_hd_d_se = self.hd_d_stats(c_lower)
            c_func_pct = (
                sum(1 for t in c_lower if t in self.lang.function_words) / n_cw * 100.0
                if n_cw
                else 0.0
            )

            # --- Measurement uncertainty per feature (documented plug-ins) ---
            def share_se(pct: float, n: int) -> float:
                p = pct / 100.0
                return (math.sqrt(max(p * (1.0 - p), 0.0) / n) * 100.0) if n else 0.0

            def count_se(cnt: int, words: int) -> float:
                return (math.sqrt(cnt) * 1000.0 / words) if words else 0.0

            c_se: dict[str, float] = {
                "asl": (c_std / math.sqrt(n_cs)) if n_cs else 0.0,
                "staccato_pct": share_se(c_staccato, n_cs),
                "kaskade_pct": share_se(c_kaskade, n_cs),
                "sentence_cv": (
                    (c_cv / math.sqrt(2.0 * n_cs)) * math.sqrt(1.0 + 2.0 * c_cv**2) if n_cs else 0.0
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
                "first_person_start_rate": share_se(c_first_rate, n_cs),
                "guiraud_r": (0.5 * c_guiraud / math.sqrt(n_cw)) if n_cw else 0.0,
            }
            if c_hd_d is not None:
                c_se["hd_d"] = c_hd_d_se

            chapters.append(
                ChapterMetrics(
                    num=c_idx,
                    title=title,
                    words=n_cw,
                    sentences=n_cs,
                    asl=c_asl,
                    dialog_pct=c_dial_pct,
                    ttr=c_ttr,
                    motif_counts=c_motifs,
                    filter_verbs=c_fil,
                    dominance=dom,
                    signal_matches=c_signals,
                    staccato_pct=c_staccato,
                    kaskade_pct=c_kaskade,
                    sentence_cv=c_cv,
                    start_entropy=c_start_entropy,
                    first_person_start_rate=c_first_rate,
                    passive_density=c_passive,
                    nominalization_density=c_nominal,
                    adjective_density=c_adjective,
                    modal_density=c_modal,
                    filter_density=c_filter_density,
                    long_word_pct=c_long_pct,
                    guiraud_r=c_guiraud,
                    hd_d=c_hd_d,
                    function_word_pct=c_func_pct,
                    style_se=c_se,
                )
            )
            chapter_tokens.append(c_lower)
            c_idx += 1

        # Jensen-Shannon divergence per chapter vs. the rest of the corpus
        # (leave-one-out: no self-bias for small chapters; additive per word type).
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
            yules_k=yules_k,
            total_sentences=total_sent,
            asl=asl,
            median_sl=median_sl,
            std_sl=std_sl,
            sentence_dist=sent_dist,
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
            staccato_pct=staccato_pct,
            kaskade_pct=kaskade_pct,
            sentence_cv=sentence_cv,
            start_entropy=start_entropy,
            first_person_start_rate=first_person_start_rate,
            passive_density=passive_density,
            nominalization_density=nominalization_density,
            adjective_density=adjective_density,
            modal_density=modal_density,
            filter_density=filter_density,
            hd_d=hd_d,
            mtld=mtld,
            mattr=mattr,
            maas_a2=maas_a2,
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
            raise FileNotFoundError(f"Manuskriptdatei nicht gefunden: {filepath}")
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        return self.analyze_text(content)
