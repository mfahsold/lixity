"""Pure verb-group morphology and language-specific periphrase rules.

These rules consume immutable syntax annotations. They do not load models,
cache manuscript text, select quotation scope or project UI evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from .language_data import GERMAN_PERFECT_PARTICIPLES
from .linguistic_models import SyntaxToken

_MODAL = frozenset({"dürfen", "können", "mögen", "müssen", "sollen", "wollen"})


@dataclass(frozen=True)
class VerbGroup:
    components: tuple[tuple[int, int], ...]
    tense: str
    mood: str
    voice: str
    reason: str = ""
    aspect: str = "unspecified"

    @property
    def span(self) -> tuple[int, int]:
        return self.components[0][0], self.components[-1][1]


def is_finite(token: SyntaxToken) -> bool:
    return token.form == "Fin" or (not token.form and token.tag.endswith("FIN"))


def classify_german(tokens: list[SyntaxToken]) -> VerbGroup:
    components = tuple(sorted((t.start, t.end) for t in tokens))
    # Replacement infinitives can be tagged VMFIN because their surface form
    # is syncretic. In a haben complex they are not a second finite clause.
    have = any(t.lemma == "haben" and is_finite(t) for t in tokens)
    finite = [t for t in tokens if is_finite(t) and not (
        have and t.lemma in _MODAL and t.dep in ("oc", "aux")
    )]
    def unknown(reason: str) -> VerbGroup:
        return VerbGroup(components, "unresolved", "unresolved", "unresolved", reason)
    if len(finite) != 1:
        return unknown("missing_finite" if not finite else "multiple_finite")
    head = finite[0]
    if head.mood not in ("Ind", "Sub", "Imp"):
        return unknown("missing_mood")
    mood = {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative"}[head.mood]
    parts = [t for t in tokens if t.form == "Part" or t.tag.endswith("PP")]
    infinitives = [t for t in tokens if t.form == "Inf" or t.tag.endswith("INF")]
    replacement = have and any(t.lemma in _MODAL and t is not head for t in tokens) and bool(infinitives)
    passive = bool(parts) and (
        any(t.lemma == "werden" and t is not head for t in tokens)
        or (head.lemma == "werden" and not infinitives)
    )
    voice = "passive" if passive else "active"
    if head.mood == "Imp":
        return VerbGroup(components, "imperative", mood, voice)
    if head.tense not in ("Pres", "Past"):
        return unknown("missing_finite_tense")
    if head.lemma == "werden" and infinitives:
        tense = "future_perfect" if parts and any(t.lemma in ("haben", "sein") for t in infinitives) else "future"
    elif head.lemma == "haben" and (parts or replacement):
        tense = "perfect" if head.tense == "Pres" else "pluperfect"
    elif head.lemma == "sein" and parts:
        if any(t.lemma == "sein" for t in parts):
            tense = "perfect" if head.tense == "Pres" else "pluperfect"
            voice = "state_or_adjectival" if any(t.pos == "VERB" for t in parts) else "active"
        elif any(t.text.casefold() == "worden" for t in parts):
            tense = "perfect" if head.tense == "Pres" else "pluperfect"
            voice = "passive"
        elif any(t.dep == "pd" for t in parts):
            tense = "present" if head.tense == "Pres" else "preterite"
            voice = "state_or_adjectival"
        elif all(t.text.casefold() in GERMAN_PERFECT_PARTICIPLES["sein"] for t in parts):
            tense = "perfect" if head.tense == "Pres" else "pluperfect"
        else:
            return VerbGroup(components, "unresolved", mood, "unresolved", "sein_participle_ambiguous")
    else:
        tense = "present" if head.tense == "Pres" else "preterite"
    return VerbGroup(components, tense, mood, voice)


_HAVE = {
    "en": frozenset({"have"}), "fr": frozenset({"avoir"}), "es": frozenset({"haber"}),
    "it": frozenset({"avere"}), "pt": frozenset({"ter", "haver"}), "nl": frozenset({"hebben"}),
}
# Positive auxiliary licensing for unambiguously intransitive lemmas only.
# Other be/participle combinations remain explicitly state/perfect ambiguous.
_BE_PERFECT = {
    "fr": frozenset({"aller", "arriver", "venir", "devenir", "revenir", "naître", "mourir", "rester", "tomber"}),
    "it": frozenset({"andare", "arrivare", "venire", "divenire", "nascere", "morire", "restare", "rimanere"}),
    "nl": frozenset({"komen", "gaan", "sterven", "ontstaan", "gebeuren", "blijven", "verdwijnen"}),
}
_BE = {"fr": "être", "it": "essere", "nl": "zijn"}


def classify_other(tokens: list[SyntaxToken], language: str, *, reflexive: bool = False) -> VerbGroup:
    """Compose forms, preserving absent mood features rather than inventing them."""
    components = tuple(sorted((t.start, t.end) for t in tokens))
    finite = [t for t in tokens if is_finite(t)]
    if len(finite) != 1:
        return VerbGroup(components, "unresolved", "unresolved", "unresolved",
                         "missing_finite" if not finite else "multiple_finite")
    head = finite[0]
    mood = {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative", "Cnd": "conditional"}.get(head.mood)
    # English and the tested Dutch model leave Mood absent on many ordinary
    # finite forms. Preserve that absence in output; never label it indicative.
    if mood is None and language in ("en", "nl"):
        mood = "unmarked"
    if mood is None:
        return VerbGroup(components, "unresolved", "unresolved", "unresolved", "missing_mood")
    parts = [t for t in tokens if t.form == "Part" and t.aspect != "Prog" and t.tag != "VBG"]
    infinitives = [t for t in tokens if t.form == "Inf"]
    progressive = any(t.form == "Ger" or t.aspect == "Prog" or t.tag == "VBG" for t in tokens)
    aspect = "progressive" if progressive else "unspecified"
    # Full relation labels (aux:tense vs aux:pass) matter here, even though
    # both join the same syntactic component.
    voice = "passive" if any(t.dep in ("aux:pass", "auxpass") for t in tokens) else "active"
    perfect = bool(parts) and any(t.lemma in _HAVE[language] for t in tokens)
    if parts and language in ("fr", "it") and reflexive and head.lemma == _BE[language]:
        perfect = True
        voice = "active"
    if any(t.pos == "VERB" for t in parts) and (
        (language in ("es", "pt") and any(t.lemma == "ser" for t in tokens))
        or (language in ("fr", "it") and any(t.lemma == _BE[language] and t.form == "Part" for t in tokens))
    ):
        voice = "passive"
    if language == "it" and head.lemma == "essere" and any(t.lemma == "essere" for t in parts):
        perfect = True
    if language == "nl" and head.lemma == "hebben" and infinitives:
        # Dutch IPP requires a recognized modal infinitive; possession/task
        # hebben + te + infinitive is not a perfect construction.
        perfect = perfect or any(t.lemma in ("moeten", "kunnen", "mogen", "willen", "zullen", "hoeven") for t in infinitives)
    if language in _BE and parts and head.lemma == _BE[language] and not perfect:
        lexical = [t for t in parts if t.pos == "VERB"]
        if lexical and all(t.lemma in _BE_PERFECT[language] for t in lexical):
            perfect = True
            voice = "active"
        elif language == "nl":
            # Dutch zijn+participle can be a result state or perfect passive
            # with an omitted geworden. Neither temporal interpretation wins.
            return VerbGroup(components, "unresolved", mood, "state_or_perfect_passive", "be_participle_ambiguous")
        else:
            voice = "passive_or_state"
    if language == "en":
        if head.lemma in ("would", "could", "might", "should"):
            mood = "conditional" if head.lemma == "would" else "modal"
        if head.lemma == "will" or head.text.casefold() in ("will", "shall"):
            return VerbGroup(components, "future_perfect" if perfect else "future", mood, voice, aspect=aspect)
        if mood in ("conditional", "modal"):
            return VerbGroup(components, ("conditional" if mood == "conditional" else "modal") + ("_perfect" if perfect else ""), mood, voice, aspect=aspect)
        if head.lemma in ("can", "may", "must", "ought") and not head.tense:
            return VerbGroup(components, "modal_perfect" if perfect else "modal", "modal", voice, aspect=aspect)
    if language == "nl" and head.lemma == "zullen":
        mood = "conditional" if head.text.casefold() in ("zou", "zouden") else mood
        return VerbGroup(components, ("conditional" if mood == "conditional" else "future") + ("_perfect" if perfect else ""), mood, voice, aspect=aspect)
    if mood == "imperative":
        return VerbGroup(components, "imperative", mood, voice)
    if mood == "conditional":
        return VerbGroup(components, "conditional_perfect" if perfect else "conditional", mood, voice, aspect=aspect)
    simple = {"Pres": "present", "Past": "preterite", "Imp": "imperfect", "Pqp": "pluperfect", "Fut": "future"}.get(head.tense)
    if simple is None:
        return VerbGroup(components, "unresolved", mood, voice, "missing_finite_tense")
    if perfect:
        simple = {"present": "perfect", "imperfect": "pluperfect", "preterite": "anterior_perfect" if language in ("fr", "it", "es") else "pluperfect", "future": "future_perfect"}.get(simple, "unresolved")
    return VerbGroup(components, simple, mood, voice, aspect=aspect)


SUPPORTED_LANGUAGES = frozenset({"de", *_HAVE})
