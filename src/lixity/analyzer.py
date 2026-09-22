"""
scripts/engine/analyzer.py
==========================
Stateless, high-performance text analysis engine for literary manuscripts.

Mathematical & linguistic foundation:
- Average Sentence Length (ASL = Total Words / Total Sentences):
  indicator for paratactic rhythm vs. hypotactic nesting.
- Type-Token Ratio (TTR = V / N) & Guiraud index (R = V / sqrt(N)):
  empirical measurement of lexical variety and dispersion.
- Yule's Characteristic K = 10^4 * (M_2 - M_1) / M_1^2:
  length-independent index for vocabulary stability (Yule 1944).
- Flesch Reading Ease (German adaptation according to Toni Amstad 1978):
  FRE = 180 - ASL - (58.5 * ASW).
- LIX (Läsbarhetsindex according to Carl-Hugo Björnsson 1968):
  LIX = ASL + (% words with more than 6 letters).
- Dialogue ratio:
  share of direct speech in typographic quotation marks (»...«, „...“, "...").
"""

import math
import os
import random
import re
from collections import Counter

from .language import compile_pattern, resolve_language
from .models import (
    ChapterMetrics,
    CorpusConfig,
    CorpusMetrics,
    SentenceDistribution,
)


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
            first = tokens[0].lower()
            starters[first] += 1
            if first in self._starters:
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
        """
        rest = n_corpus - n_chapter
        if rest < 1 or n_chapter < 1:
            return 0.0, []
        vocab = set(chapter_counter) | set(corpus_counter)
        jsd = 0.0
        contribs: dict[str, float] = {}
        for w in vocab:
            p = chapter_counter[w] / n_chapter
            q = (corpus_counter[w] - chapter_counter[w]) / rest
            m = 0.5 * (p + q)
            term = 0.0
            if p > 0.0:
                term += p * math.log(p / m)
            if q > 0.0:
                term += q * math.log(q / m)
            contrib = 0.5 * term
            contribs[w] = contrib
            jsd += contrib
        top = [
            w
            for w, _ in sorted(contribs.items(), key=lambda kv: kv[1], reverse=True)
            if len(w) > 1 and chapter_counter[w] > 0 and w not in self._content_blacklist
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
        w = re.sub(r"(ei|ey|ai|ay|au|eu|äu|ie)", "V", w)
        w = re.sub(r"[aeiouyäöü]", "V", w)
        return max(1, w.count("V"))

    def count_syllables(self, word: str) -> int:
        """
        Language-sensitive syllable counting based on the configured language.
        Uses the German diphthong heuristic for 'de', otherwise generic vowel clusters.
        """
        if self.lang.syllable_mode == "de":
            return self.count_syllables_de(word)
        # Generic fallback for Romance/Germanic languages
        w = word.lower()
        w = re.sub(r"[aeiouy]+", "V", w)
        return max(1, w.count("V"))

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
        cleaned_full = re.sub(r"<!--.*?-->", "", full_text, flags=re.DOTALL)
        cleaned_main = re.sub(r"<!--.*?-->", "", main_text, flags=re.DOTALL)

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
        m1 = n_tokens
        m2 = sum(c**2 for c in freqs.values())
        yules_k = 10000.0 * (m2 - m1) / (m1**2) if m1 else 0.0
        ttr = v_types / n_tokens if n_tokens else 0.0
        guiraud_r = v_types / math.sqrt(n_tokens) if n_tokens else 0.0

        # Sentence metrics (remove headings before segmentation to prevent word carry-over)
        prose_for_sents = re.sub(r"(?m)^#+.*$", "", cleaned_main)
        raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose_for_sents) if s.strip()]
        sent_lens = [
            len(self._word_re.findall(s)) for s in raw_sents if len(self._word_re.findall(s)) > 0
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

        # Readability & complexity
        total_syllables = sum(self.count_syllables(t) for t in tokens)
        asw = total_syllables / n_tokens if n_tokens else 0.0
        flesch_de = 180.0 - asl - (58.5 * asw)
        long_words = sum(1 for t in tokens if len(t) > 6)
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

        # Punctuation as a stylistic seismograph
        punctuation = {
            "Punkte (.)": cleaned_main.count("."),
            "Kommata (,)": cleaned_main.count(","),
            "Gedankenstriche (–/—)": len(re.findall(r"[–—]", cleaned_main)),
            "Doppelpunkte (:)": cleaned_main.count(":"),
            "Semikolons (;)": cleaned_main.count(";"),
            "Fragezeichen (?)": cleaned_main.count("?"),
            "Ausrufezeichen (!)": cleaned_main.count("!"),
            "Auslassungspunkte (…/...)": len(re.findall(r"(?:…|\.{3})", cleaned_main)),
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

        # Chapter-wise segmentation
        raw_chapters = re.split(self.config.chapter_regex, main_text)

        # Front matter (everything before the first chapter) is not a chapter:
        # If the first section starts with an H1 (book title/front matter), it is
        # skipped – otherwise the chapter numbering would shift by one.
        if raw_chapters and raw_chapters[0].strip().startswith("# "):
            raw_chapters = raw_chapters[1:]

        chapters: list[ChapterMetrics] = []
        chapter_tokens: list[list[str]] = []
        c_idx = 1

        for rc in raw_chapters:
            rc = rc.strip()
            if not rc:
                continue
            lines = rc.split("\n")
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
            ratio = pr_c / (pt_c + 0.001)
            if ratio > 1.5:
                dom = "Präsens (Szenisch)"
            elif ratio < 0.67:
                dom = "Präteritum (Episch)"
            else:
                dom = "Hybrid / Montage"

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
            c_long_words = sum(1 for t in c_words if len(t) > 6)
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
