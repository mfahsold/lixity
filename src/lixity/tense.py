"""Shared lexical tense counting with curated finite-form precedence.

Productive endings may collide with explicitly listed present forms. This
matcher rejects those contradictory past candidates. German perfect constructions
own their auxiliary and participle instead of double counting: listed pairs or
productive candidates in a bounded head context. Other compound ambiguities
remain lexical cues.
"""

import re
from bisect import bisect_right
from collections.abc import Sequence
from typing import Any

from .language import ResolvedLanguage, compile_pattern
from .language_data import (
    GERMAN_PERFECT_FORMS,
    GERMAN_PERFECT_PARTICIPLES,
    GERMAN_PRODUCTIVE_PARTICIPLE,
    LANGUAGE_PATTERNS,
    PROFILE_DATA,
)
from .models import CorpusConfig

_WORD = re.compile(r"\w+")
_BLANK_LINE = re.compile(r"\n\s*\n")
_PERFECT_MAX_GAP_WORDS = 3
_CLAUSE_END = re.compile(r"[.!?,;:]")
_SPANISH_HABER = frozenset({"he", "has", "ha", "hemos", "habéis", "han"})
_COMPOUND_STARTER_RE = re.compile(r"^\\b\(\?:([^)]+)\)\\s\+")


def _curated_word_set(pattern: str) -> frozenset[str]:
    if not pattern:
        return frozenset()
    return frozenset(w.lower() for w in pattern[3:-3].split("|"))


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
        self._curated_present_words = _curated_word_set(curated["praesens_regex"])
        self._curated_past_words = _curated_word_set(curated["praeteritum_regex"])
        self._pronouns = frozenset(word.lower() for word in language.lexicon.get("pronouns", ()))
        self._auxiliaries = frozenset(word.lower() for word in language.lexicon.get("auxiliaries", ()))
        self._german = language.key == "de"
        self._spanish = language.key == "es"
        self._model = config.tense_model
        self._scope = config.tense_scope
        self._quotation = compile_pattern(language.dialogue_regex)
        model_language = self._model.removeprefix("stanza:").split("_", 1)[0] if self._model else language.key
        if self._model and model_language != language.key:
            raise ValueError("The selected grammatical tense model does not match the explicit analysis language")
        self._perfect_auxiliaries = {
            form: GERMAN_PERFECT_PARTICIPLES[family]
            for family, forms in GERMAN_PERFECT_FORMS.items() for form in forms
        }
        self._sein_forms = frozenset(GERMAN_PERFECT_FORMS["sein"])
        self._haben_forms = frozenset(GERMAN_PERFECT_FORMS["haben"])
        self._known_participles = frozenset().union(*GERMAN_PERFECT_PARTICIPLES.values())
        self._productive_participle = compile_pattern(GERMAN_PRODUCTIVE_PARTICIPLE)
        self._function_words = language.function_words
        self._conjunctions = frozenset(word.lower() for word in language.lexicon.get("conjunctions", ()))
        self._productive_cache: dict[str, bool] = {}
        extras = LANGUAGE_PATTERNS.get(language.key, {}).get("praeteritum", [])
        single_pats = [f"(?:{e})" for e in extras if r"\s" not in e]
        compound_pats = [f"(?:{e})" for e in extras if r"\s" in e]
        self._single_past_re = compile_pattern("|".join(single_pats)) if single_pats else None
        self._compound_past_re = compile_pattern("|".join(compound_pats)) if compound_pats else None
        starters: set[str] = set()
        for pat in extras:
            if r"\s" in pat:
                m = _COMPOUND_STARTER_RE.match(pat)
                if m is not None:
                    starters.update(w.lower() for w in m.group(1).split("|"))
        self._compound_starters = frozenset(starters)
        self._single_past_cache: dict[str, bool] = {}

    def _is_productive_participle(self, word: str) -> bool:
        hit = self._productive_cache.get(word)
        if hit is None:
            hit = (
                word not in self._function_words
                and word not in self._curated_present_words
                and word not in self._curated_past_words
                and self._productive_participle.fullmatch(word) is not None
            )
            self._productive_cache[word] = hit
        return hit

    def _is_single_productive_past(self, word: str) -> bool:
        if self._single_past_re is None:
            return False
        hit = self._single_past_cache.get(word)
        if hit is None:
            hit = self._single_past_re.fullmatch(word) is not None
            self._single_past_cache[word] = hit
        return hit

    def _german_perfect_spans(
        self,
        text: str,
        word_tokens: Sequence[tuple[int, int, str, str]] | None = None,
    ) -> list[tuple[int, int, bool]]:
        """Bounded candidate spans, with positive licensing distinct from ambiguity."""
        tokens = (
            word_tokens
            if word_tokens is not None
            else [(m.start(), m.end(), m.group(), m.group().lower()) for m in _WORD.finditer(text)]
        )
        n_words = len(tokens)
        constructions: list[tuple[int, int, bool]] = []
        for index, (aux_start, aux_end, _aux_raw, aux_low) in enumerate(tokens):
            participles = self._perfect_auxiliaries.get(aux_low)
            if participles is None or (constructions and aux_start < constructions[-1][1]):
                continue
            previous_end = aux_end
            best: tuple[int, int, bool] | None = None
            stop = min(n_words, index + _PERFECT_MAX_GAP_WORDS + 2)
            for position in range(index + 1, stop):
                c_start, c_end, c_raw, word = tokens[position]
                separator = text[previous_end:c_start]
                if not separator.isspace() or ("\n" in separator and _BLANK_LINE.search(separator)):
                    break
                productive = c_raw.islower() and self._is_productive_participle(word)
                if (
                    aux_low in self._sein_forms
                    and (word in self._known_participles or productive)
                    and position + 1 < n_words
                ):
                    f_start, f_end, _f_raw, f_low = tokens[position + 1]
                    gap = text[c_end:f_start]
                    # Passive perfect has a second, distinct participial marker.
                    # https://grammis.ids-mannheim.de/progr@mm/1695
                    if f_low == "worden" and gap.isspace() and not ("\n" in gap and _BLANK_LINE.search(gap)):
                        best = (aux_start, f_end, True)
                        break
                # Unknown ge-/-iert words can also be attributive adjectives.
                # Resolve the have-perfect only at a bounded clause/head edge,
                # never merely because an ending occurs before another word.
                head_edge = position + 1 == n_words or bool(
                    _CLAUSE_END.search(text[c_end:tokens[position + 1][0]])
                )
                if productive and head_edge and aux_low in self._haben_forms:
                    best = (aux_start, c_end, True)
                    previous_end = c_end
                    continue
                if word in self._known_participles:
                    # Auxiliary choice depends on regional usage, transitivity
                    # and meaning. Missing licensing is not a negative verdict.
                    # Continue to the bounded rightmost head: in "geschlossen
                    # gehalten" the first participle is not the perfect head.
                    best = (aux_start, c_end, word in participles)
                    previous_end = c_end
                    continue
                if (
                    word in self._perfect_auxiliaries
                    or word in self._conjunctions
                    or word in self._curated_present_words
                    or word in self._curated_past_words
                ):
                    break
                previous_end = c_end
            if best is not None:
                constructions.append(best)
        return constructions

    def count(self, text: str) -> tuple[int, int]:
        """Return present/past counts, preserving custom capture/zero-width cues."""
        present, past = self.spans(text)
        return len(present), len(past)

    def parts(self, parts: Sequence[str]) -> list[dict[str, Any] | None]:
        """Resolve shared quotation context before counting individual paragraphs."""
        if self._model is None:
            return [None] * len(parts)
        from .grammatical_tense import grammatical_parts

        return list(grammatical_parts(parts, self._model, self._scope, self._quotation))

    def spans(self, text: str, *, observation: dict[str, Any] | None = None) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        """Return effective cue ranges, including undrawable zero-width cues.

        Ranges address the supplied counting text. A perfect construction owns
        one past cue; lexical ambiguities retain the existing counting policy.
        """
        if self._model is not None:
            spans: dict[str, list[tuple[int, int]]] = {"present": [], "past": []}
            parts = text.split("\n\n")
            observations = [observation] if observation is not None else self.parts(parts)
            offset = 0
            for part, result in zip(parts, observations, strict=True):
                if result is None:
                    raise ValueError("Missing grammatical tense observation; no pattern fallback was used")
                for group in result["groups"]:
                    if group["selected"] and group["bucket"] in spans:
                        components = group["components"]
                        spans[group["bucket"]].append((offset + components[0][0], offset + components[-1][1]))
                offset += len(part) + 2
            return spans["present"], spans["past"]
        if not self._protect_finite_forms:
            return ([match.span() for match in self._present.finditer(text)],
                    [match.span() for match in self._past.finditer(text)])
        word_tokens = [(m.start(), m.end(), m.group(), m.group().lower()) for m in _WORD.finditer(text)]
        constructions = self._german_perfect_spans(text, word_tokens) if self._german else []
        starts = [start for start, _, _ in constructions]

        def consumed(start: int, end: int, *, licensed_only: bool = False) -> bool:
            if not starts:
                return False
            index = bisect_right(starts, start) - 1
            return (index >= 0 and end <= constructions[index][1]
                    and (not licensed_only or constructions[index][2]))

        past = [(start, end) for start, end, _ in constructions]
        spanish_auxiliary_starts: set[int] = set()
        i = 0
        n_words = len(word_tokens)
        while i < n_words:
            w_start, w_end, w_raw, w_low = word_tokens[i]
            m_span: tuple[int, int] | None = None
            m_words: tuple[str, ...] = ()
            if w_low in self._curated_past_words:
                m_span = (w_start, w_end)
                m_words = (w_raw,)
                i += 1
            else:
                if self._is_single_productive_past(w_low):
                    m_span = (w_start, w_end)
                    m_words = (w_raw,)
                    i += 1
                elif (
                    w_low in self._compound_starters
                    and self._compound_past_re is not None
                    and i + 1 < n_words
                ):
                    cm = self._compound_past_re.match(text, w_start)
                    if cm is not None:
                        c_end = cm.end()
                        m_span = (w_start, c_end)
                        m_words = (w_raw, word_tokens[i + 1][2])
                        i += 2 if c_end >= word_tokens[i + 1][1] else 1
                if m_span is None:
                    i += 1
                    continue
            if consumed(m_span[0], m_span[1]):
                continue
            # Only single finite candidates and pronoun + finite candidates
            # are eligible. A compound's participle may share a present-form
            # spelling, as in German "haben erzählt". Preserve auxiliary-led
            # candidates, including ambiguous pronoun/auxiliary spellings.
            if (
                self._german
                and len(m_words) > 1
                and w_low in self._perfect_auxiliaries
                and m_words[-1].istitle()
            ):
                # Reject nominal spelling in this position, without rescanning
                # the rejected phrase for new standalone suffix matches.
                # Unlisted lowercase forms keep their independent lexical cues:
                # absence from the inventory must not manufacture present tense.
                continue
            finite_candidate = (
                len(m_words) == 1
                or (len(m_words) == 2 and w_low in self._pronouns and w_low not in self._auxiliaries)
            )
            last_low = m_words[-1].lower()
            if (
                finite_candidate
                and last_low in self._curated_present_words
                and last_low not in self._curated_past_words
            ):
                continue
            past.append(m_span)
            # The Spanish default past pattern includes adjacent haber + regular
            # participle candidates. Count the detected group once, not also
            # as an isolated present auxiliary. The regex is still lexical, not
            # a POS tagger, and other languages' have/be ambiguities stay intact.
            if (
                self._spanish
                and len(m_words) == 2
                and w_low in _SPANISH_HABER
                and not _BLANK_LINE.search(text[m_span[0]:m_span[1]])
            ):
                spanish_auxiliary_starts.add(m_span[0])
        present = [
            (w_start, w_end)
            for w_start, w_end, _w_raw, w_low in word_tokens
            if w_low in self._curated_present_words
            and w_start not in spanish_auxiliary_starts
            and not consumed(w_start, w_end, licensed_only=True)
        ]
        return present, sorted(past)
