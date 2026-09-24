"""lixity.syllables – language-specific syllable-count heuristics.

Curated, deterministic plug-in estimators used by the readability formulas
(Flesch family; LIX uses word lengths rather than syllables). Known weaknesses
such as hiatus and foreign words are discussed in ``docs/STABILITY.md``.
Regression fixtures do not establish language-wide accuracy percentages.

All rules are data: regex tables and exception dictionaries live here, the
counting logic stays a pure function per language.
"""

from __future__ import annotations

import re

# --- Rule tables (data) -----------------------------------------------------

DE_DIPHTHONG = re.compile(r"(ei|ey|ai|ay|au|eu|äu|ie|aa|ee|oo)")
DE_VOWEL = re.compile(r"[aeiouyäöü]")

EN_CLEAN = re.compile(r"[^a-z]")
EN_VOWEL_GROUP = re.compile(r"[aeiouy]+")
EN_EXCEPTIONS: dict[str, int] = {
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

FR_CLEAN = re.compile(r"[^a-zàâäéèêëîïôöùûüÿçœæ]")
FR_VOWEL_GROUP = re.compile(r"[aeiouyàâäéèêëîïôöùûüÿœæ]+")

ES_CLEAN = re.compile(r"[^a-záéíóúüñ]")
ES_STRONG = "aeoáéó"
ES_WEAK = "iuü"

IT_CLEAN = re.compile(r"[^a-zàèéìíòóùú]")
IT_VOWELS = "aeiouàèéìíòóùú"
IT_WEAK = "iu"

PT_CLEAN = re.compile(r"[^a-zàâãáéêíóôõúüç]")
PT_VOWEL_GROUP = re.compile(r"[aeiouàâãáéêíóôõúü]+")

NL_CLEAN = re.compile(r"[^a-záéíóúäëïöüâêîôû]")
NL_VOWEL_GROUP = re.compile(r"[aeiouyáéíóúäëïöüâêîôûI]+")

GENERIC_VOWEL_GROUP = re.compile(r"[aeiouy]+")


# --- Counting functions -----------------------------------------------------


def count_de(word: str) -> int:
    """German: diphthongs and double vowels are one nucleus, vowel clusters count."""
    w = DE_DIPHTHONG.sub("V", word.lower())
    w = DE_VOWEL.sub("V", w)
    return max(1, w.count("V"))


def count_en(word: str) -> int:
    """English: vowel groups plus silent-e / -ed / -es rules and a curated exception list."""
    w = EN_CLEAN.sub("", word.lower())
    if not w:
        return 0
    if w in EN_EXCEPTIONS:
        return EN_EXCEPTIONS[w]
    count = len(EN_VOWEL_GROUP.findall(w))
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


def count_fr(word: str) -> int:
    """French: vowel groups with mute final -e / -ent / -es."""
    w = FR_CLEAN.sub("", word.lower())
    if not w:
        return 0
    count = len(FR_VOWEL_GROUP.findall(w))
    if w.endswith("e") and not w.endswith(("ée", "eé", "eë", "eü")) and count > 1:
        count -= 1
    if w.endswith("ent") and count > 1:
        count -= 1
    if w.endswith("es") and count > 1 and w[-3] not in "aeiouyàâäéèêëîïôöùûüÿœæ":
        count -= 1
    return max(1, count)


def count_es(word: str) -> int:
    """Spanish: strong/weak vowel diphthong detection (accented vowels break diphthongs)."""
    w = ES_CLEAN.sub("", word.lower())
    if not w:
        return 0
    marked = w.replace("í", "I").replace("ú", "U")
    count = 0
    i = 0
    while i < len(marked):
        c = marked[i]
        if c in ES_STRONG or c in "IU":
            count += 1
            j = i + 1
            while j < len(marked) and marked[j] in ES_WEAK:
                j += 1
                if j < len(marked) and marked[j] in ES_STRONG:
                    j += 1
            i = j
        else:
            i += 1
    return max(1, count)


def count_it(word: str) -> int:
    """Italian: weak i/u join adjacent vowels into diphthongs."""
    w = IT_CLEAN.sub("", word.lower())
    if not w:
        return 0
    count = 0
    i = 0
    while i < len(w):
        if w[i] in IT_VOWELS:
            count += 1
            j = i + 1
            while j < len(w) and w[j] in IT_WEAK:
                j += 1
            i = j
        else:
            i += 1
    return max(1, count)


def count_pt(word: str) -> int:
    """Portuguese: vowel groups including nasal vowels and diphthongs."""
    w = PT_CLEAN.sub("", word.lower())
    if not w:
        return 0
    return max(1, len(PT_VOWEL_GROUP.findall(w)))


def count_nl(word: str) -> int:
    """Dutch: 'ij' is one nucleus, otherwise vowel groups count."""
    w = NL_CLEAN.sub("", word.lower())
    if not w:
        return 0
    marked = w.replace("ij", "I").replace("IJ", "I")
    return max(1, len(NL_VOWEL_GROUP.findall(marked)))


def count_generic(word: str) -> int:
    """Fallback: plain vowel-group counting."""
    w = EN_CLEAN.sub("", word.lower())
    if not w:
        return 0
    return max(1, len(GENERIC_VOWEL_GROUP.findall(w)))


_COUNTERS = {
    "de": count_de,
    "en": count_en,
    "fr": count_fr,
    "es": count_es,
    "it": count_it,
    "pt": count_pt,
    "nl": count_nl,
}


def count_syllables(word: str, language_key: str = "generic") -> int:
    """Dispatches to the language heuristic (generic fallback: vowel groups)."""
    counter = _COUNTERS.get(language_key)
    if counter is not None:
        return counter(word)
    return count_generic(word)
