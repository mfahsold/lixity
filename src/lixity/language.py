"""
scripts/engine/language.py
==========================
Language profile layer of the analysis engine: fully interchangeable
language patterns for tense, dialogue, word and syllable detection.

This makes the engine work for any language, any writing style and any
novel idea: the language is selected via ``CorpusConfig.language``; all patterns
can additionally be overridden via the config (None = profile default).

- Profiles: ``de``, ``en``, ``fr``, ``es``, ``it``, ``pt``, ``nl`` and
  ``generic`` (neutral fallback without tense classification).
- ``auto``: language detection via stop word frequency (dependency-free);
  stop word methods are robust for running text but unreliable for
  single words (cf. fastlang/langidentify). Without a text sample, ``auto``
  falls back to ``generic``.
- The curated markers and productive tense patterns live in
  ``language_data.py``; analyzer, profiler and UI follow the registry
  automatically – new language = one entry, no code change.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from .language_data import (
    HELP_TEXTS,
    LABELS,
    LANGUAGE_PATTERNS,
    LEXICON,
    METRIC_LABELS,
    PROFILE_DATA,
    STYLE_DATA,
)


def _suffix_pattern(suffixes) -> str:
    """Builds a suffix regex for the style heuristics; empty list -> never matches."""
    if not suffixes:
        return ""
    return r"\b\w+(?:" + "|".join(re.escape(s) for s in suffixes) + r")\b"


@dataclass(frozen=True)
class LanguageProfile:
    """Static, curated language patterns of one language profile."""

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
    first_person_starters: frozenset
    passive_regex: str
    nominal_regex: str
    adjective_regex: str


@dataclass(frozen=True)
class ResolvedLanguage:
    """Effective language patterns after config overrides (None = profile default)."""

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
    stopwords: frozenset
    first_person_starters: frozenset
    passive_regex: str
    nominal_regex: str
    adjective_regex: str


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
    return frozenset(w.lower() for cat in FUNCTION_CATEGORIES for w in lex.get(cat, ()))


def _build_profiles() -> dict[str, LanguageProfile]:
    """Builds the registry from the data layer (including productive tense patterns)."""
    profiles: dict[str, LanguageProfile] = {}
    for key, data in PROFILE_DATA.items():
        past_parts = []
        if data["praeteritum_regex"]:
            past_parts.append(f"(?:{data['praeteritum_regex']})")
        for extra in LANGUAGE_PATTERNS.get(key, {}).get("praeteritum", []):
            past_parts.append(f"(?:{extra})")
        style = STYLE_DATA.get(key, STYLE_DATA["generic"])
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
            first_person_starters=frozenset(style.get("first_person_starters", ())),
            passive_regex=style.get("passive_regex", ""),
            nominal_regex=_suffix_pattern(style.get("nominal_suffixes", ())),
            adjective_regex=_suffix_pattern(style.get("adjective_suffixes", ())),
        )
    return profiles


LANGUAGE_PROFILES: dict[str, LanguageProfile] = _build_profiles()


def compile_pattern(pattern: str) -> "re.Pattern[str]":
    """Compiles a language pattern; empty patterns never match (neutral fallback)."""
    return re.compile(pattern or r"(?!x)x", re.IGNORECASE)


def get_language_profile(key: str) -> LanguageProfile:
    """Returns the language profile; unknown keys fall back to ``generic``."""
    return LANGUAGE_PROFILES.get((key or "").strip().lower(), LANGUAGE_PROFILES["generic"])


def detect_language(text: str, min_hits: int = 3) -> str:
    """Detects the language via stop word frequency (dependency-free, offline).

    Returns: language key or ``generic`` if the signal is too weak or
    ambiguous (short texts, proper names, numbers).
    """
    words = re.findall(r"[^\W\d_]+", text.lower())
    if not words:
        return "generic"

    scores: dict[str, int] = {}
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
        return "generic"  # Tie: no reliable signal
    return best_key


def resolve_language(config, sample_text: str | None = None) -> ResolvedLanguage:
    """Combines config overrides (None = profile default) into effective patterns.

    ``language="auto"`` uses stop word detection; without ``sample_text``
    the resolution falls back to the generic profile.
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
        stopwords=profile.stopwords,
        first_person_starters=getattr(config, "first_person_starters", None)
        or profile.first_person_starters,
        passive_regex=getattr(config, "passive_regex", None) or profile.passive_regex,
        nominal_regex=getattr(config, "nominal_regex", None) or profile.nominal_regex,
        adjective_regex=getattr(config, "adjective_regex", None) or profile.adjective_regex,
    )
