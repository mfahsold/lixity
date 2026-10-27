"""Configured paragraph counters and literal evidence for human review.

Offsets address exact displayed profile text, never Markdown source bytes.
An unavailable mapping preserves the measured count without inventing a span.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from unicodedata import normalize

from .language import (
    ResolvedLanguage,
    compile_pattern,
    compile_word_pattern,
    count_nominal_matches,
    resolve_language,
)
from .markdown_parser import counting_inline_text, parse_markdown_blocks, strip_inline_markup
from .models import CorpusConfig
from .sentences import split_sentence_spans, split_sentences
from .tense import TenseMatcher
from .text_normalization import counting_view

if TYPE_CHECKING:
    from .style_profile import ParagraphProfile


class _EvidenceSpan(TypedDict):
    start: int
    end: int
    count: int


class EvidenceSpan(_EvidenceSpan, total=False):
    words: int


class _LayerEvidence(TypedDict):
    status: Literal["available", "partial", "unavailable"]
    kind: str
    count: int | None
    mapped_count: int
    spans: list[EvidenceSpan]


class LayerEvidence(_LayerEvidence, total=False):
    reason: str


class _TenseEvidence(TypedDict):
    present: LayerEvidence
    past: LayerEvidence


class TenseEvidence(_TenseEvidence, total=False):
    trigger: str
    grammar: dict[str, Any]


class _ParagraphEvidence(TypedDict):
    schema_version: str
    paragraph_sha256: str
    offset_unit: str
    layers: dict[str, LayerEvidence]


class ParagraphEvidence(_ParagraphEvidence, total=False):
    tense: TenseEvidence


_KINDS = {"asl": "sentence", "function": "word", "dialogue": "dialogue",
          "filter": "pattern", "modal": "word", "nominal": "pattern", "passive": "pattern"}


@dataclass(frozen=True)
class ParagraphCounts:
    words: int
    sentences: list[str]
    dialogue: int
    function: int
    filter: int
    modal: int
    nominal: int
    passive: int

    def layers(self) -> dict[str, int]:
        """Sentence units for ASL, quoted-word contributions for dialogue."""
        return {"asl": len(self.sentences), "function": self.function, "dialogue": self.dialogue,
                "filter": self.filter, "modal": self.modal, "nominal": self.nominal,
                "passive": self.passive}


def _layer(kind: str, count: int, spans: list[EvidenceSpan], *,
           reason: str = "zero_width_matches") -> LayerEvidence:
    drawable = [span for span in spans if span["end"] > span["start"] and span["count"] > 0]
    mapped = sum(span["count"] for span in drawable)
    if mapped > count:
        drawable, mapped, reason = [], 0, "count_mismatch"
    result: LayerEvidence = {
        "status": "available" if mapped == count else "partial" if mapped else "unavailable",
        "kind": kind, "count": count, "mapped_count": mapped, "spans": drawable,
    }
    if mapped != count:
        result["reason"] = reason
    return result


def _envelope(text: str, layers: dict[str, LayerEvidence]) -> ParagraphEvidence:
    result: ParagraphEvidence = {"schema_version": "paragraph-evidence/1",
                                "paragraph_sha256": sha256(text.encode("utf-8")).hexdigest(),
                                "offset_unit": "unicode_codepoint",
                                "layers": {key: value for key, value in layers.items() if key in _KINDS}}
    if "present" in layers:
        result["tense"] = {"present": layers["present"], "past": layers["past"]}
    return result


class ParagraphMatcher:
    """Single counting path shared by paragraph profiles and their evidence."""

    def __init__(self, config: CorpusConfig, language: ResolvedLanguage) -> None:
        self.language = language
        self.word = compile_word_pattern(language.word_regex)
        self.dialogue = compile_pattern(language.dialogue_regex)
        self.filter = compile_pattern(language.filter_verbs_regex)
        self.passive = compile_pattern(language.passive_regex)
        self.nominal = compile_pattern(language.nominal_regex)
        self.nominal_exclusions = language.function_words if config.nominal_regex is None else frozenset()
        self.modals = frozenset(word.lower() for word in language.lexicon.get("modals", ()))

    def count(self, clean: str) -> ParagraphCounts:
        """Count canonical NFC prose with the configured token/capture rules."""
        clean = normalize("NFC", clean)
        tokens = [token.lower() for token in self.word.findall(clean)]
        sentences = [sentence for sentence in split_sentences(clean, self.language.key)
                     if self.word.findall(sentence)]
        return ParagraphCounts(
            words=len(tokens), sentences=sentences,
            dialogue=sum(len(self.word.findall(part)) for part in self.dialogue.findall(clean)),
            function=sum(token in self.language.function_words for token in tokens),
            filter=len(self.filter.findall(clean)),
            modal=sum(token in self.modals for token in tokens),
            nominal=count_nominal_matches(clean, self.nominal, self.nominal_exclusions),
            passive=len(self.passive.findall(clean)),
        )

    def evidence(self, clean: str, display: str, counts: ParagraphCounts, *,
                 tense_spans: tuple[list[tuple[int, int]], list[tuple[int, int]]] | None = None) -> ParagraphEvidence:
        values = counts.layers()
        kinds = dict(_KINDS)
        if tense_spans is not None:
            kinds.update(present="pattern", past="pattern")
            values.update(present=len(tense_spans[0]), past=len(tense_spans[1]))
        clean = normalize("NFC", clean)
        view = counting_view(display)
        if clean != view.text:
            # The parser's count projection may remove code or destinations
            # still present in ParagraphProfile.text. Do not relocate matches.
            layers = {key: _layer(kinds[key], count, [], reason="inline_mapping_unavailable")
                      for key, count in values.items()}
            return _envelope(display, layers)

        spans: dict[str, list[EvidenceSpan]] = {key: [] for key in kinds}
        if tense_spans is not None:
            for key, cues in zip(("present", "past"), tense_spans, strict=True):
                spans[key] = [{"start": start, "end": end, "count": 1} for start, end in cues]
        for (start, end), sentence in zip(split_sentence_spans(clean, self.language.key),
                                          split_sentences(clean, self.language.key), strict=True):
            words = len(self.word.findall(sentence))
            if words:
                spans["asl"].append({"start": start, "end": end, "count": 1, "words": words})
        for match in self.word.finditer(clean):
            # With one capture findall returns that capture, not the full
            # match. Preserve the actual counted token and its exact range.
            group = 1 if self.word.groups == 1 else 0
            token = (match.group(group) or "").lower()
            start, end = match.span(group)
            if token in self.language.function_words:
                spans["function"].append({"start": start, "end": end, "count": 1})
            if token in self.modals:
                spans["modal"].append({"start": start, "end": end, "count": 1})
        for key, pattern in (("filter", self.filter), ("passive", self.passive),
                             ("nominal", self.nominal)):
            for match in pattern.finditer(clean):
                if key == "nominal" and match.group().lower() in self.nominal_exclusions:
                    continue
                spans[key].append({"start": match.start(), "end": match.end(), "count": 1})
        for match in self.dialogue.finditer(clean):
            group = 1 if self.dialogue.groups == 1 else 0
            count = len(self.word.findall(match.group(group) or ""))
            start, end = match.span(group)
            if count:
                spans["dialogue"].append({"start": start, "end": end, "count": count})
        unmapped: set[str] = set()
        if view.text != display:
            for key, matches in spans.items():
                mapped: list[EvidenceSpan] = []
                for span in matches:
                    source = view.source_span(span["start"], span["end"])
                    if source is None:
                        unmapped.add(key)
                        continue
                    mapped.append({**span, "start": source[0], "end": source[1]})
                spans[key] = mapped
        return _envelope(display, {
            key: _layer(kinds[key], count, spans[key],
                        reason="unicode_mapping_unavailable" if key in unmapped else "zero_width_matches")
            for key, count in values.items()
        })


def paragraph_evidence(text: str, config: CorpusConfig,
                       paragraphs: Sequence["ParagraphProfile"]) -> dict[int, ParagraphEvidence]:
    """Build optional evidence for profiles from the same text/configuration.

    Existing anchors and exact display text must agree. This does not profile
    again, change paragraph identities, or retain another copy of the prose.
    """
    language = resolve_language(config, sample_text=text)
    matcher = ParagraphMatcher(config, language)
    tense = TenseMatcher(config, language)
    blocks: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for block in parse_markdown_blocks(text, config):
        if block.get("type") in ("p", "list_item"):
            blocks.setdefault((block.get("start_line", 0), block.get("end_line", 0)), []).append(block)
    result: dict[int, ParagraphEvidence] = {}
    for index, paragraph in enumerate(paragraphs):
        candidates = [block for block in blocks.get((paragraph.start_line, paragraph.end_line), [])
                      if strip_inline_markup(block.get("text", "")) == paragraph.text]
        if len(candidates) != 1:
            layers: dict[str, LayerEvidence] = {
                key: {"status": "unavailable", "kind": kind, "count": None, "mapped_count": 0,
                      "spans": [], "reason": "source_mismatch"} for key, kind in _KINDS.items()
            }
            result[index] = _envelope(paragraph.text, layers)
            continue
        clean = counting_inline_text(candidates[0].get("text", ""))
        result[index] = matcher.evidence(clean, paragraph.text, matcher.count(clean),
                                        tense_spans=tense.spans(clean, observation=paragraph.tense_analysis))
        result[index]["tense"]["trigger"] = paragraph.tense_trigger
        grammar = paragraph.tense_analysis
        if grammar is not None:
            result[index]["tense"]["grammar"] = grammar
    return result
