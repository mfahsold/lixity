"""Shared lexical tense counting with curated finite-form precedence.

Productive endings may collide with explicitly listed present forms. This
matcher rejects those contradictory past candidates, without interpreting
compound constructions or resolving forms listed in both curated inventories.
"""

import re

from .language import ResolvedLanguage, compile_pattern
from .language_data import PROFILE_DATA
from .models import CorpusConfig

_WORD = re.compile(r"\w+")


class TenseMatcher:
    """Count effective cues; explicit overrides retain independent matching."""

    def __init__(self, config: CorpusConfig, language: ResolvedLanguage) -> None:
        self._present = compile_pattern(language.praesens_regex)
        self._past = compile_pattern(language.praeteritum_regex)
        self._protect_finite_forms = (
            config.praesens_regex is None and config.praeteritum_regex is None
        )
        curated = PROFILE_DATA[language.key]
        self._curated_present = compile_pattern(curated["praesens_regex"])
        self._curated_past = compile_pattern(curated["praeteritum_regex"])
        self._pronouns = frozenset(word.lower() for word in language.lexicon.get("pronouns", ()))
        self._auxiliaries = frozenset(word.lower() for word in language.lexicon.get("auxiliaries", ()))

    def count(self, text: str) -> tuple[int, int]:
        """Return present/past counts, preserving custom capture/zero-width cues."""
        present = len(self._present.findall(text))
        if not self._protect_finite_forms:
            return present, len(self._past.findall(text))
        past = 0
        for match in self._past.finditer(text):
            # Only single finite candidates and pronoun + finite candidates
            # are eligible. A compound's participle may share a present-form
            # spelling, as in German "haben erzählt". Preserve auxiliary-led
            # candidates, including ambiguous pronoun/auxiliary spellings.
            words = _WORD.findall(match.group())
            finite_candidate = (
                (len(words) == 1 and words[0] == match.group())
                or (len(words) == 2 and words[0].lower() in self._pronouns
                    and words[0].lower() not in self._auxiliaries)
            )
            if (finite_candidate and self._curated_present.fullmatch(words[-1])
                    and not self._curated_past.fullmatch(words[-1])):
                continue
            past += 1
        return present, past
