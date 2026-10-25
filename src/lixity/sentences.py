"""lixity.sentences – sentence segmentation with abbreviation and number guards.

A single splitter for the whole engine (corpus metrics and paragraph
profiling): splits on terminal punctuation (``.`` ``!`` ``?``) followed by
whitespace, but protects

- common abbreviations (titles, ``z.B.``, ``e.g.``, ``usw.`` …) per language,
- periods between digits (``1.000,50``, ``3.14``, ``8.30``),
- single-letter initials (``J. R. R. Tolkien``),

and keeps closing quotation/bracket marks with the sentence they close
(``»Komm!« Er ging.`` → ``»Komm!«`` + ``Er ging.``).

The abbreviation list is deliberately curated and documented: it is a
heuristic, not a parser – unknown abbreviations still split.
"""

from __future__ import annotations

import re
from unicodedata import category

# Universal abbreviations (titles, Latin loans, common English forms).
_ABBREVIATIONS_UNIVERSAL = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "st",
        "vs",
        "etc",
        "e.g",
        "i.e",
        "fig",
        "cf",
        "vol",
        "pp",
        "jr",
        "sr",
        "inc",
        "ltd",
    }
)

_ABBREVIATIONS_DE = frozenset(
    {
        "z.b",
        "d.h",
        "u.a",
        "u.ä",
        "u.s.w",
        "u.v.m",
        "bzw",
        "ca",
        "evtl",
        "ggf",
        "inkl",
        "sog",
        "usw",
        "vgl",
        "nr",
        "abs",
        "art",
        "bd",
        "kap",
        "std",
        "mio",
        "mrd",
        "z.t",
        "o.ä",
    }
)

_ABBREVIATIONS_FR = frozenset({"m", "mme", "mlle", "p.ex", "c.-à-d", "réf", "éd"})
_ABBREVIATIONS_ES = frozenset({"sr", "sra", "srta", "d", "p.ej", "etc", "núm"})
_ABBREVIATIONS_IT = frozenset({"sig", "sigg", "dott", "d.ssa", "es", "ecc", "n"})
_ABBREVIATIONS_PT = frozenset({"sr", "sra", "srta", "exmo", "p.ex", "etc", "núm"})
_ABBREVIATIONS_NL = frozenset({"dhr", "mevr", "bijv", "bv", "d.w.z", "enz", "nr"})

_ABBREVIATIONS: dict[str, frozenset[str]] = {
    "de": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_DE,
    "en": _ABBREVIATIONS_UNIVERSAL,
    "fr": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_FR,
    "es": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_ES,
    "it": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_IT,
    "pt": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_PT,
    "nl": _ABBREVIATIONS_UNIVERSAL | _ABBREVIATIONS_NL,
}

#: Sentence-length bins shared by the analyzer and pacing heuristics.
SHORT_SENTENCE_MAX = 6
MEDIUM_SENTENCE_MAX = 15
LONG_SENTENCE_MAX = 25

_MASK = "\x00"  # replaces protected periods

# Abbreviation at the end of a token, e.g. "z.B." / "Mr."
_ABBR_RE = re.compile(
    r"(?<![A-Za-zÄÖÜäöüß])([A-Za-zÄÖÜäöüß][\wÄÖÜäöüß.&-]*?)\.(?=\s|$)", re.UNICODE
)
# Period between digits: 1.000 / 3.14 / 8.30
_DIGIT_PERIOD_RE = re.compile(r"(?<=\d)\.(?=\d)")
# Single-letter initial followed by space and another capital: "J. R. R. Tolkien"
_INITIAL_RE = re.compile(r"(?<!\w)([A-ZÄÖÜ])\.(?=\s+[A-ZÄÖÜ])")
# Closing marks that belong to the preceding sentence
_CLOSERS = "»«\"“”'’\u2018)]"
_SPLIT_RE = re.compile(r"(?<=[.!?])([" + re.escape(_CLOSERS) + r"]*)\s+")
# Blank line between semantic blocks: a sentence boundary never crosses it.
_BLOCK_BOUNDARY_RE = re.compile(r"\n[ \t]*\n+")
# Pair direction comes from the unmatched opener, including reversed guillemets
# and low opening quotes. This is bounded punctuation matching, not a parser.
_QUOTE_PAIRS = {"«": "»", "»": "«", "“": "”", "„": "“”", "\u2018": "’",
                "\u201a": "\u2018’", '"': '"', "'": "'", "(": ")", "[": "]"}
_PAIR_MARK_RE = re.compile("[" + re.escape("".join(_QUOTE_PAIRS) + "”’)]") + "]")


def _protect(text: str, language_key: str) -> str:
    abbreviations = _ABBREVIATIONS.get(language_key, _ABBREVIATIONS_UNIVERSAL)
    text = _DIGIT_PERIOD_RE.sub(_MASK, text)
    text = _INITIAL_RE.sub(lambda m: m.group(1) + _MASK, text)

    def _abbr(match: re.Match[str]) -> str:
        candidate = match.group(1).lower().rstrip(".")
        if candidate in abbreviations:
            return match.group(1) + _MASK
        return match.group(0)

    return _ABBR_RE.sub(_abbr, text)


def _matched_closer_positions(text: str) -> set[int]:
    """Find paired closers without treating a new quotation as a closing mark."""
    stack: list[str] = []
    closers: set[int] = set()
    previous = 0
    for match in _PAIR_MARK_RE.finditer(text):
        index, mark = match.start(), match.group()
        if _BLOCK_BOUNDARY_RE.search(text, previous, index):
            stack.clear()
        previous = index + 1
        # An apostrophe within a word is not a quotation delimiter. Combining
        # marks count as word continuations for callers supplying raw NFD.
        if mark in "'’" and 0 < index < len(text) - 1 and all(
            char.isalnum() or category(char).startswith("M")
            for char in (text[index - 1], text[index + 1])
        ):
            continue
        if stack and mark in stack[-1]:
            stack.pop()
            closers.add(index)
        elif mark in _QUOTE_PAIRS:
            # A word-final possessive apostrophe may close an active quotation,
            # but must not open one and capture a later sentence's opening quote.
            if mark == "'" and index > 0 and (
                text[index - 1].isalnum() or category(text[index - 1]).startswith("M")
            ):
                continue
            stack.append(_QUOTE_PAIRS[mark])
    return closers


def _sentence_spans(protected: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    matched_closers = _matched_closer_positions(protected)
    start = 0
    for boundary in _SPLIT_RE.finditer(protected):
        end = boundary.start() + len(boundary.group(1))
        following = boundary.end()
        while following in matched_closers:
            end = following + 1
            following = end
            while following < len(protected) and protected[following].isspace():
                following += 1
        while start < end and protected[start].isspace():
            start += 1
        if start < end:
            spans.append((start, end))
        start = following
    end = len(protected)
    while start < end and protected[start].isspace():
        start += 1
    while end > start and protected[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end))
    return spans


def split_sentence_spans(text: str, language_key: str = "generic") -> list[tuple[int, int]]:
    """Exact codepoint ranges from the shared abbreviation-aware splitter."""
    return _sentence_spans(_protect(text, language_key))


def split_sentences(text: str, language_key: str = "generic") -> list[str]:
    """Splits prose into sentences (deterministic, abbreviation-aware)."""
    protected = _protect(text, language_key)
    return [protected[start:end].replace(_MASK, ".")
            for start, end in _sentence_spans(protected)]


def split_prose_sentences(text: str, language_key: str = "generic") -> list[str]:
    """Splits multi-paragraph prose without ever crossing a blank line.

    ``split_sentences`` receives whole chapters here, so an unterminated
    block (a stage note, a salutation, a sign) would otherwise merge into
    the next block's sentence and inflate its measured length. Splitting
    every semantic block on its own keeps fragments local: a block without
    terminal punctuation stays one fragment unit, matching paragraph
    profiles and scene measurements.
    """
    sentences: list[str] = []
    for block in _BLOCK_BOUNDARY_RE.split(text):
        sentences.extend(split_sentences(block, language_key))
    return sentences
