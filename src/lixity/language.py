"""
scripts/engine/language.py
==========================
Sprachprofil-Schicht der Analyse-Engine: vollständig austauschbare
Sprachmuster für Tempus-, Dialog-, Wort- und Silbenerkennung.

Damit funktioniert die Engine für jede Sprache, jeden Schreibstil und jede
Romanidee: Sprache wird über ``CorpusConfig.language`` gewählt; alle Muster
sind zusätzlich per Config überschreibbar (None = Profil-Standard).

- Profile: ``de``, ``en``, ``fr``, ``es``, ``it``, ``pt``, ``nl`` und
  ``generic`` (neutraler Fallback ohne Tempusklassifikation).
- ``auto``: Spracherkennung über Stopwort-Häufigkeit (abhängigkeitsfrei);
  Stopwort-Verfahren sind für Fließtexte belastbar, für Einzelwörter jedoch
  unzuverlässig (vgl. fastlang/langidentify). Ohne Textprobe fällt ``auto``
  auf ``generic`` zurück.
- Die kuratierten Marker und produktiven Tempusmuster liegen in
  ``language_data.py``; Analyzer, Profiler und UI folgen der Registry
  automatisch – neue Sprache = ein Eintrag, keine Codeänderung.
"""

import re
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from .language_data import HELP_TEXTS, LABELS, LANGUAGE_PATTERNS, LEXICON, METRIC_LABELS, PROFILE_DATA


@dataclass(frozen=True)
class LanguageProfile:
    """Statische, kuratierte Sprachmuster eines Sprachprofils."""

    key: str
    name: str
    syllable_mode: str
    word_regex: str
    dialogue_regex: str
    praesens_regex: str
    praeteritum_regex: str
    filter_verbs_regex: str
    signal_keywords: Mapping[str, str]
    stopwords: frozenset
    labels: Mapping[str, str]
    lexicon: Mapping[str, tuple]
    function_words: frozenset


@dataclass(frozen=True)
class ResolvedLanguage:
    """Effektive Sprachmuster nach Config-Overrides (None = Profil-Standard)."""

    key: str
    name: str
    syllable_mode: str
    word_regex: str
    dialogue_regex: str
    praesens_regex: str
    praeteritum_regex: str
    filter_verbs_regex: str
    signal_keywords: Mapping[str, str]
    labels: Mapping[str, str]
    lexicon: Mapping[str, tuple]
    function_words: frozenset


FUNCTION_CATEGORIES = (
    "articles",
    "pronouns",
    "prepositions",
    "conjunctions",
    "particles",
    "auxiliaries",
    "modals",
)


def _function_words(key: str) -> frozenset:
    lex = LEXICON.get(key, {})
    return frozenset(
        w.lower() for cat in FUNCTION_CATEGORIES for w in lex.get(cat, ())
    )


def _build_profiles() -> Dict[str, LanguageProfile]:
    """Erzeugt die Registry aus der Datenschicht (inkl. produktiver Tempusmuster)."""
    profiles: Dict[str, LanguageProfile] = {}
    for key, data in PROFILE_DATA.items():
        past_parts = []
        if data["praeteritum_regex"]:
            past_parts.append(f"(?:{data['praeteritum_regex']})")
        for extra in LANGUAGE_PATTERNS.get(key, {}).get("praeteritum", []):
            past_parts.append(f"(?:{extra})")
        profiles[key] = LanguageProfile(
            key=key,
            name=data["name"],
            syllable_mode=data["syllable_mode"],
            word_regex=data["word_regex"],
            dialogue_regex=data["dialogue_regex"],
            praesens_regex=data["praesens_regex"],
            praeteritum_regex="|".join(past_parts),
            filter_verbs_regex=data["filter_verbs_regex"],
            signal_keywords=data["signal_keywords"],
            stopwords=frozenset(data.get("stopwords", ())),
            labels={
                **LABELS.get(key, LABELS["generic"]),
                **METRIC_LABELS.get(key, METRIC_LABELS["en"]),
                **HELP_TEXTS.get(key, HELP_TEXTS["en"]),
            },
            lexicon=LEXICON.get(key, {}),
            function_words=_function_words(key),
        )
    return profiles


LANGUAGE_PROFILES: Dict[str, LanguageProfile] = _build_profiles()


def compile_pattern(pattern: str) -> "re.Pattern[str]":
    """Kompiliert ein Sprachmuster; leere Muster matchen nie (neutraler Fallback)."""
    return re.compile(pattern or r"(?!x)x", re.IGNORECASE)


def get_language_profile(key: str) -> LanguageProfile:
    """Liefert das Sprachprofil; unbekannte Schlüssel fallen auf ``generic`` zurück."""
    return LANGUAGE_PROFILES.get((key or "").strip().lower(), LANGUAGE_PROFILES["generic"])


def detect_language(text: str, min_hits: int = 3) -> str:
    """Erkennt die Sprache über Stopwort-Häufigkeit (abhängigkeitsfrei, offline).

    Rückgabe: Sprachschlüssel oder ``generic``, wenn das Signal zu schwach oder
    mehrdeutig ist (kurze Texte, Eigennamen, Zahlen).
    """
    words = re.findall(r"[^\W\d_]+", text.lower())
    if not words:
        return "generic"

    scores: Dict[str, int] = {}
    for key, profile in LANGUAGE_PROFILES.items():
        signal = profile.stopwords | profile.function_words
        if not signal:
            continue
        scores[key] = sum(1 for w in words if w in signal)
    if not scores:
        return "generic"

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_key, best_score = ranked[0]
    if best_score < min_hits:
        return "generic"
    if len(ranked) > 1 and ranked[1][1] == best_score:
        return "generic"  # Gleichstand: kein belastbares Signal
    return best_key


def resolve_language(config, sample_text: Optional[str] = None) -> ResolvedLanguage:
    """Verrechnet Config-Overrides (None = Profil-Standard) zu effektiven Mustern.

    ``language="auto"`` nutzt die Stopwort-Erkennung; ohne ``sample_text``
    fällt die Auflösung auf das generische Profil zurück.
    """
    key = str(getattr(config, "language", "de") or "de").strip().lower()
    if key == "auto":
        key = detect_language(sample_text) if sample_text else "generic"
    profile = get_language_profile(key)
    configured_signals = getattr(config, "signal_keywords", None)
    signals: Mapping[str, str] = (
        configured_signals if configured_signals is not None else profile.signal_keywords
    )
    return ResolvedLanguage(
        key=profile.key,
        name=profile.name,
        syllable_mode=profile.syllable_mode,
        word_regex=getattr(config, "word_regex", None) or profile.word_regex,
        dialogue_regex=getattr(config, "dialogue_regex", None) or profile.dialogue_regex,
        praesens_regex=getattr(config, "praesens_regex", None) or profile.praesens_regex,
        praeteritum_regex=getattr(config, "praeteritum_regex", None) or profile.praeteritum_regex,
        filter_verbs_regex=getattr(config, "filter_verbs_regex", None)
        or profile.filter_verbs_regex,
        signal_keywords=signals,
        labels=profile.labels,
        lexicon=profile.lexicon,
        function_words=profile.function_words,
    )
