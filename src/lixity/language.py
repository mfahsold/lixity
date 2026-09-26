"""lixity.language – Pluggable multilingual architecture and automatic language detection.

Manages language profiles (de, en, fr, es, it, pt, nl, generic) and resolves
lexicons, tense markers, and register signals via function-word distribution vectors.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from .language_data import (
    GROUP_LABELS,
    GUIDANCE_LABELS,
    HELP_TEXTS,
    IDENTITY_LABELS,
    LABELS,
    LANGUAGE_PATTERNS,
    LAYER_LABELS,
    LEXICON,
    METRIC_LABELS,
    PROFILE_DATA,
    STYLE_DATA,
    UI_LABELS,
)
from .models import CorpusConfig
from .workspace_labels import WORKSPACE_LABELS


def _suffix_pattern(suffixes: Sequence[str]) -> str:
    """Builds a suffix regex for the style heuristics; empty list -> never matches."""
    if not suffixes:
        return ""
    return r"\b\w+(?:" + "|".join(re.escape(s) for s in suffixes) + r")\b"


@dataclass(frozen=True)
class LanguageProfile:
    """Curated patterns of one language profile (also the resolved, effective view).

    ``_build_profiles()`` creates the static registry; ``resolve_language()``
    derives the effective profile from it via :func:`dataclasses.replace`,
    overriding only the fields the config actually sets.
    """

    key: str
    name: str
    syllable_mode: str
    word_regex: str
    dialogue_regex: str
    praesens_regex: str
    praeteritum_regex: str
    filter_verbs_regex: str
    signal_keywords: Mapping[str, str]
    stopwords: frozenset[str]
    labels: Mapping[str, str]
    lexicon: Mapping[str, Sequence[str]]
    function_words: frozenset[str]
    first_person_starters: frozenset[str]
    passive_regex: str
    nominal_regex: str
    adjective_regex: str


# The effective profile after config overrides is structurally the same object.
ResolvedLanguage = LanguageProfile


FUNCTION_CATEGORIES = (
    "articles",
    "pronouns",
    "prepositions",
    "conjunctions",
    "particles",
    "auxiliaries",
    "modals",
)


def _function_words(key: str) -> frozenset[str]:
    lex = LEXICON.get(key, {})
    return frozenset(w.lower() for cat in FUNCTION_CATEGORIES for w in lex.get(cat, ()))


def _build_profiles() -> dict[str, LanguageProfile]:
    """Builds the registry from the data layer (including productive tense patterns)."""
    profiles: dict[str, LanguageProfile] = {}
    for key, data in PROFILE_DATA.items():
        past_parts = []
        if data["praeteritum_regex"]:
            past_parts.append(f"(?:{data['praeteritum_regex']})")
        past_parts.extend(
            f"(?:{extra})" for extra in LANGUAGE_PATTERNS.get(key, {}).get("praeteritum", [])
        )
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
                **GUIDANCE_LABELS.get(key, GUIDANCE_LABELS["en"]),
                **IDENTITY_LABELS.get(key, IDENTITY_LABELS["en"]),
                **LABELS.get(key, LABELS["generic"]),
                **METRIC_LABELS.get(key, METRIC_LABELS["en"]),
                **HELP_TEXTS.get(key, HELP_TEXTS["en"]),
                **GROUP_LABELS.get(key, GROUP_LABELS["en"]),
                **LAYER_LABELS.get(key, LAYER_LABELS["en"]),
                **UI_LABELS.get(key, UI_LABELS["en"]),
                **WORKSPACE_LABELS.get(key, WORKSPACE_LABELS["en"]),
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


def resolve_language(
    config: CorpusConfig, sample_text: str | None = None
) -> ResolvedLanguage:
    """Combines config overrides (None = profile default) into the effective profile.

    ``language="auto"`` uses stop word detection; without ``sample_text``
    the resolution falls back to the generic profile.
    """
    key = str(getattr(config, "language", "en") or "en").strip().lower()
    if key == "auto":
        key = detect_language(sample_text) if sample_text else "generic"
    profile = get_language_profile(key)

    # Overrides: only fields the config actually sets replace profile defaults.
    resolved = profile
    for field_name in (
        "word_regex",
        "dialogue_regex",
        "praesens_regex",
        "praeteritum_regex",
        "filter_verbs_regex",
        "passive_regex",
        "nominal_regex",
        "adjective_regex",
        "first_person_starters",
    ):
        value = getattr(config, field_name, None)
        if value is not None:
            resolved = replace(resolved, **{field_name: value})
    configured_signals = getattr(config, "signal_keywords", None)
    if configured_signals is not None:
        resolved = replace(resolved, signal_keywords=configured_signals)
    return resolved
