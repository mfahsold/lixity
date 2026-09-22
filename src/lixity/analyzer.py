"""
scripts/engine/analyzer.py
==========================
Zustandslose, hochperformante Textanalyse-Engine für literarische Manuskripte.

Mathematische & linguistische Fundierung:
- Mittlere Satzlänge (ASL = Total Words / Total Sentences):
  Indikator für parataktischen Rhythmus vs. hypotaktische Schachtelung.
- Type-Token-Ratio (TTR = V / N) & Guiraud-Index (R = V / sqrt(N)):
  Empirische Messung lexikalischer Vielfalt und Streuung.
- Yule's Characteristic K = 10^4 * (M_2 - M_1) / M_1^2:
  Längenunabhängiger Index zur Stabilität des Wortschatzes (Yule 1944).
- Flesch Reading Ease (Deutsche Adaption nach Toni Amstad 1978):
  FRE = 180 - ASL - (58.5 * ASW).
- LIX (Läsbarhetsindex nach Carl-Hugo Björnsson 1968):
  LIX = ASL + (% Wörter mit mehr als 6 Buchstaben).
- Dialogquote:
  Anteil wörtlicher Rede in typografischen Anführungszeichen (»...«, „...“, "...").
"""

import os
import re
import math
from collections import Counter
from typing import Optional, List, Dict

from .language import compile_pattern, resolve_language
from .models import (
    CorpusConfig,
    CorpusMetrics,
    SentenceDistribution,
    ChapterMetrics,
)


class CorpusAnalyzer:
    """
    Zustandslose, thread-sichere Analyse-Engine für literarische Markdown-Texte.
    Führt quantitative Korpuslinguistik, Stilometrie und Kapitelgliederung durch.
    """

    def __init__(self, config: Optional[CorpusConfig] = None):
        """
        Initialisiert den Analyzer mit einer Konfiguration.
        Wird keine Konfiguration übergeben, greifen die Standardparameter.
        """
        self.config = config or CorpusConfig()
        self.lang = resolve_language(self.config)
        self._praes_re = compile_pattern(self.lang.praesens_regex)
        self._praet_re = compile_pattern(self.lang.praeteritum_regex)
        self._filter_re = compile_pattern(self.lang.filter_verbs_regex)
        self._word_re = re.compile(self.lang.word_regex)
        self._dialogue_re = re.compile(self.lang.dialogue_regex)

    @staticmethod
    def count_syllables_de(word: str) -> int:
        """
        Approximative Silbenzählung für deutsche Wörter.
        Normalisiert Diphthonge ('ei', 'ie', 'au', 'eu', 'äu') auf Einzellaut
        und zählt die verbleibenden Vokalcluster. Garantiert mindestens 1 Silbe.
        """
        w = word.lower()
        # Diphthonge und Doppellaute zu Einzellaut reduzieren
        w = re.sub(r"(ei|ey|ai|ay|au|eu|äu|ie)", "V", w)
        w = re.sub(r"[aeiouyäöü]", "V", w)
        return max(1, w.count("V"))

    def count_syllables(self, word: str) -> int:
        """
        Sprachsensitive Silbenzählung anhand der konfigurierten Sprache.
        Nutzt für 'de' die deutsche Diphthong-Heuristik, sonst generische Vokal-Cluster.
        """
        if self.lang.syllable_mode == "de":
            return self.count_syllables_de(word)
        # Generischer Fallback für romanische/germanische Sprachen
        w = word.lower()
        w = re.sub(r"[aeiouy]+", "V", w)
        return max(1, w.count("V"))

    def analyze_text(self, full_text: str) -> CorpusMetrics:
        """
        Führt die vollständige stilometrische und quantitative Analyse auf
        einem übergebenen Textstring aus.

        Ablauf:
        1. Abtrennung des wissenschaftlichen Anhangs (Single Source of Truth).
        2. Filterung von Markdown-HTML-Kommentaren (<!-- ... -->).
        3. Tokenisierung und Erfassung der Vokabulartypen.
        4. Berechnung lexikalischer Diversitätsmetriken (TTR, Guiraud, Yule).
        5. Satzzerlegung und Satzlängen-Architektur (ohne Überschriften-Artefakte).
        6. Lesbarkeitsindizes (Flesch DE, LIX).
        7. Dialog- und Absatzökonomie.
        8. Interpunktions- und Signalwortfrequenzen.
        9. Kapitelweise Segmentierung und Tempus-Klassifikation.

        Rückgabe:
            CorpusMetrics-Objekt mit allen berechneten Kennzahlen.
        """
        # 1. Trennung Haupttext vs. Anhang
        if self.config.appendix_marker and self.config.appendix_marker in full_text:
            main_text, _ = full_text.split(self.config.appendix_marker, 1)
        else:
            main_text = full_text

        # Markdown-Kommentare entfernen
        cleaned_full = re.sub(r"<!--.*?-->", "", full_text, flags=re.DOTALL)
        cleaned_main = re.sub(r"<!--.*?-->", "", main_text, flags=re.DOTALL)

        raw_words = len(cleaned_full.split())
        clean_words = len(cleaned_main.split())
        raw_chars = len(cleaned_full)
        clean_chars = len(cleaned_main)

        # Wort-Tokenisierung
        tokens = self._word_re.findall(cleaned_main)
        n_tokens = len(tokens)
        lower_tokens = [t.lower() for t in tokens]
        v_types = len(set(lower_tokens))
        freqs = Counter(lower_tokens)

        # Lexikalische Reichweite & Stabilität
        m1 = n_tokens
        m2 = sum(c ** 2 for c in freqs.values())
        yules_k = 10000.0 * (m2 - m1) / (m1 ** 2) if m1 else 0.0
        ttr = v_types / n_tokens if n_tokens else 0.0
        guiraud_r = v_types / math.sqrt(n_tokens) if n_tokens else 0.0

        # Satz-Metriken (Überschriften vor Zerlegung entfernen, um Wort-Verschleppung zu verhindern)
        prose_for_sents = re.sub(r"(?m)^#+.*$", "", cleaned_main)
        raw_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose_for_sents)
                     if s.strip()]
        sent_lens = [len(self._word_re.findall(s))
                     for s in raw_sents if len(self._word_re.findall(s)) > 0]
        total_sent = len(sent_lens)
        asl = sum(sent_lens) / total_sent if total_sent else 0.0
        sorted_lens = sorted(sent_lens)
        median_sl = sorted_lens[total_sent // 2] if total_sent else 0
        variance_sl = sum((sl - asl) ** 2 for sl in sent_lens) / total_sent if total_sent else 0.0
        std_sl = math.sqrt(variance_sl)

        # Satzlängenarchitektur
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

        # Lesbarkeit & Komplexität
        total_syllables = sum(self.count_syllables(t) for t in tokens)
        asw = total_syllables / n_tokens if n_tokens else 0.0
        flesch_de = 180.0 - asl - (58.5 * asw)
        long_words = sum(1 for t in tokens if len(t) > 6)
        pct_long_words = (long_words / n_tokens) * 100.0 if n_tokens else 0.0
        lix = asl + pct_long_words

        # Dialog-Quote (Erkennung wörtlicher Rede)
        dialog_matches = self._dialogue_re.findall(cleaned_main)
        dialog_words = sum(len(m.split()) for m in dialog_matches)
        dialog_ratio = (dialog_words / clean_words) * 100.0 if clean_words else 0.0

        # Absatz-Ökonomie
        raw_paras = [p.strip() for p in cleaned_main.split("\n\n") if p.strip()]
        prose_paras = [p for p in raw_paras
                       if not p.startswith("#") and not p.startswith("|")
                       and not p.startswith("-") and not p.startswith("*")]
        para_lens = [len(p.split()) for p in prose_paras]
        total_paras = len(para_lens)
        avg_para_len = sum(para_lens) / total_paras if total_paras else 0.0
        single_line_paras = sum(1 for pl in para_lens if pl <= self.config.min_paragraph_length_for_oneliner and pl != 8)

        # Interpunktion als stilistischer Seismograf
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

        # Signal- & Filterwörter
        signal_counts = {
            name: len(re.findall(pat, cleaned_main, re.IGNORECASE))
            for name, pat in self.lang.signal_keywords.items()
        }
        filter_cnt = len(self._filter_re.findall(cleaned_main))

        # Kapitelweise Segmentierung
        raw_chapters = re.split(self.config.chapter_regex, main_text)

        # Front Matter (alles vor dem ersten Kapitel) ist kein Kapitel:
        # Beginnt der erste Abschnitt mit einer H1 (Buchtitel/Titelei), wird er
        # übersprungen – sonst würde die Kapitelnummerierung um eins verschoben.
        if raw_chapters and raw_chapters[0].strip().startswith("# "):
            raw_chapters = raw_chapters[1:]

        chapters: List[ChapterMetrics] = []
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

            c_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cl_b)
                       if s.strip() and not s.strip().startswith("#")]
            c_sent_lens = [len(self._word_re.findall(s))
                           for s in c_sents if len(self._word_re.findall(s)) > 0]
            c_asl = sum(c_sent_lens) / len(c_sent_lens) if c_sent_lens else 0.0

            c_dial = self._dialogue_re.findall(cl_b)
            c_dial_words = sum(len(m.split()) for m in c_dial)
            c_dial_pct = (c_dial_words / len(c_words)) * 100.0 if c_words else 0.0

            c_ttr = len(set(w.lower() for w in c_words)) / len(c_words) if c_words else 0.0

            c_signals: Dict[str, int] = {}
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

            chapters.append(ChapterMetrics(
                num=c_idx,
                title=title,
                words=len(c_words),
                sentences=len(c_sent_lens),
                asl=c_asl,
                dialog_pct=c_dial_pct,
                ttr=c_ttr,
                motif_counts=c_motifs,
                filter_verbs=c_fil,
                dominance=dom,
                signal_matches=c_signals
            ))
            c_idx += 1

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
        )

    def analyze_file(self, filepath: str) -> CorpusMetrics:
        """
        Liest eine UTF-8-Textdatei ein und delegiert an analyze_text.

        Parameter:
            filepath: Absoluter oder relativer Dateipfad zum Markdown-Manuskript.

        Rückgabe:
            CorpusMetrics-Objekt.

        Raises:
            FileNotFoundError: Wenn die Datei unter dem Pfad nicht existiert.
        """
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Manuskriptdatei nicht gefunden: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return self.analyze_text(content)
