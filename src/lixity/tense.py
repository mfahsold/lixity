"""Shared lexical tense counting with curated finite-form precedence.

Productive endings may collide with explicitly listed present forms. This
matcher rejects those contradictory past candidates. Listed German perfect
constructions own their auxiliary and participle instead of double counting;
other compound ambiguities remain lexical cues.
"""

import re
from bisect import bisect_right

from .language import ResolvedLanguage, compile_pattern
from .language_data import GERMAN_PERFECT_FORMS, GERMAN_PERFECT_PARTICIPLES, PROFILE_DATA
from .models import CorpusConfig

_WORD = re.compile(r"\w+")
_BLANK_LINE = re.compile(r"\n\s*\n")
_PERFECT_MAX_GAP_WORDS = 3


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
        self._german = language.key == "de"
        self._perfect_auxiliaries = {
            form: GERMAN_PERFECT_PARTICIPLES[family]
            for family, forms in GERMAN_PERFECT_FORMS.items() for form in forms
        }
        self._known_participles = frozenset().union(*GERMAN_PERFECT_PARTICIPLES.values())
        self._conjunctions = frozenset(word.lower() for word in language.lexicon.get("conjunctions", ()))

    def _german_perfect_spans(self, text: str) -> list[tuple[int, int, bool]]:
        """Bounded candidate spans, with positive licensing distinct from ambiguity."""
        words = list(_WORD.finditer(text))
        constructions: list[tuple[int, int, bool]] = []
        for index, auxiliary in enumerate(words):
            participles = self._perfect_auxiliaries.get(auxiliary.group().lower())
            if participles is None or (constructions and auxiliary.start() < constructions[-1][1]):
                continue
            previous_end = auxiliary.end()
            best: tuple[int, int, bool] | None = None
            for position, candidate in enumerate(
                words[index + 1:index + _PERFECT_MAX_GAP_WORDS + 2], start=index + 1
            ):
                separator = text[previous_end:candidate.start()]
                if not separator.isspace() or _BLANK_LINE.search(separator):
                    break
                word = candidate.group().lower()
                if (auxiliary.group().lower() in GERMAN_PERFECT_FORMS["sein"]
                        and word in self._known_participles and position + 1 < len(words)):
                    following = words[position + 1]
                    gap = text[candidate.end():following.start()]
                    # Passive perfect has a second, distinct participial marker.
                    # https://grammis.ids-mannheim.de/progr@mm/1695
                    if following.group().lower() == "worden" and gap.isspace() and not _BLANK_LINE.search(gap):
                        best = (auxiliary.start(), following.end(), True)
                        break
                if word in self._known_participles:
                    # Auxiliary choice depends on regional usage, transitivity
                    # and meaning. Missing licensing is not a negative verdict.
                    # Continue to the bounded rightmost head: in "geschlossen
                    # gehalten" the first participle is not the perfect head.
                    best = (auxiliary.start(), candidate.end(), word in participles)
                    previous_end = candidate.end()
                    continue
                if (word in self._perfect_auxiliaries or word in self._conjunctions
                        or self._curated_present.fullmatch(word) or self._curated_past.fullmatch(word)):
                    break
                previous_end = candidate.end()
            if best is not None:
                constructions.append(best)
        return constructions

    def count(self, text: str) -> tuple[int, int]:
        """Return present/past counts, preserving custom capture/zero-width cues."""
        if not self._protect_finite_forms:
            return len(self._present.findall(text)), len(self._past.findall(text))
        constructions = self._german_perfect_spans(text) if self._german else []
        starts = [start for start, _, _ in constructions]

        def consumed(start: int, end: int, *, licensed_only: bool = False) -> bool:
            index = bisect_right(starts, start) - 1
            return (index >= 0 and end <= constructions[index][1]
                    and (not licensed_only or constructions[index][2]))

        present = sum(not consumed(match.start(), match.end(), licensed_only=True)
                      for match in self._present.finditer(text))
        past = len(constructions)
        for match in self._past.finditer(text):
            if consumed(match.start(), match.end()):
                continue
            # Only single finite candidates and pronoun + finite candidates
            # are eligible. A compound's participle may share a present-form
            # spelling, as in German "haben erzählt". Preserve auxiliary-led
            # candidates, including ambiguous pronoun/auxiliary spellings.
            words = _WORD.findall(match.group())
            if self._german and len(words) > 1 and words[0].lower() in self._perfect_auxiliaries:
                # Reject nominal spelling in this position, without rescanning
                # the rejected phrase for new standalone suffix matches.
                # Unlisted lowercase forms keep their independent lexical cues:
                # absence from the inventory must not manufacture present tense.
                word = words[-1]
                if word.istitle():
                    continue
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
