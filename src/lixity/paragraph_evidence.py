"""Configured paragraph counters and literal evidence for human review.

Offsets address exact displayed profile text, never Markdown source bytes.
An unavailable mapping preserves the measured count without inventing a span.
"""

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, TypedDict
from unicodedata import is_normalized, normalize

from .dialogue import (
    dialogue_tag_pattern,
    find_dialogue_tag_spans,
    find_indirect_speech_spans,
    indirect_speech_available,
)
from .language import (
    ResolvedLanguage,
    compile_pattern,
    compile_word_pattern,
    count_nominal_matches,
    quotation_capture_group,
    quotation_texts,
    resolve_language,
)
from .markdown_parser import counting_inline_text, parse_markdown_blocks, strip_inline_markup
from .models import CorpusConfig
from .sentences import split_sentence_spans
from .tense import TenseMatcher
from .text_normalization import counting_view

_WORD_RE = re.compile(r"\w+")

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


_KINDS = {
    "asl": "sentence",
    "function": "word",
    "dialogue": "dialogue",
    "filter": "pattern",
    "sensory": "pattern",
    "modal": "word",
    "nominal": "pattern",
    "passive": "pattern",
    "sticky": "sentence",
    "dialogue_tag": "pattern",
    "echo": "word",
    "indirect_speech": "pattern",
}


@dataclass(frozen=True)
class ParagraphCounts:
    words: int
    sentences: list[str]
    dialogue: int
    function: int
    filter: int
    sensory: int
    modal: int
    nominal: int
    passive: int
    sticky: int = 0
    dialogue_tag: int = 0
    echo: int = 0
    indirect_speech: int = 0

    def layers(self) -> dict[str, int]:
        """Sentence units for ASL, quoted-word contributions for dialogue."""
        return {
            "asl": len(self.sentences),
            "function": self.function,
            "dialogue": self.dialogue,
            "filter": self.filter,
            "sensory": self.sensory,
            "modal": self.modal,
            "nominal": self.nominal,
            "passive": self.passive,
            "sticky": self.sticky,
            "dialogue_tag": self.dialogue_tag,
            "echo": self.echo,
            "indirect_speech": self.indirect_speech,
        }


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
        self.sensory = compile_pattern(language.sensory_regex)
        self.passive = compile_pattern(language.passive_regex)
        self.nominal = compile_pattern(language.nominal_regex)
        self.nominal_exclusions = language.function_words if config.nominal_regex is None else frozenset()
        self.modals = frozenset(word.lower() for word in language.lexicon.get("modals", ()))
        self.sticky_min_words = config.sticky_min_words
        self.sticky_glue_pct = config.sticky_glue_pct
        self.sticky_available = bool(language.function_words)
        self.dialogue_tag = dialogue_tag_pattern(language.key)
        self.dialogue_tag_available = self.dialogue_tag is not None
        self.indirect_speech_available = indirect_speech_available(language.key)
        self._fast_cues = (
            config.filter_verbs_regex is None
            and config.sensory_regex is None
            and config.nominal_regex is None
        )
        self._cue_cache: dict[str, tuple[bool, bool, bool]] = {}
        self._last_scan: tuple[str, list[EvidenceSpan], list[EvidenceSpan]] | None = None

    def _classify_cue(self, low: str) -> tuple[bool, bool, bool]:
        hit = self._cue_cache.get(low)
        if hit is None:
            hit = (
                self.filter.fullmatch(low) is not None,
                self.sensory.fullmatch(low) is not None,
                self.nominal.fullmatch(low) is not None and low not in self.nominal_exclusions,
            )
            self._cue_cache[low] = hit
        return hit

    def _is_sticky_sentence(self, tokens: Sequence[str]) -> bool:
        n_words = len(tokens)
        if not self.sticky_available or n_words < self.sticky_min_words:
            return False
        glue_words = sum(1 for tok in tokens if tok in self.language.function_words)
        return (glue_words / n_words * 100.0) >= self.sticky_glue_pct

    def count(self, clean: str) -> ParagraphCounts:
        """Count canonical NFC prose with the configured token/capture rules."""
        if not is_normalized("NFC", clean):
            clean = normalize("NFC", clean)
        tokens = [token.lower() for token in self.word.findall(clean)]
        sentences: list[str] = []
        asl_spans: list[EvidenceSpan] = []
        sticky_spans: list[EvidenceSpan] = []
        for s_start, s_end in split_sentence_spans(clean, self.language.key):
            sentence = clean[s_start:s_end]
            s_tokens = [tok.lower() for tok in self.word.findall(sentence)]
            w_count = len(s_tokens)
            if w_count:
                sentences.append(sentence)
                asl_spans.append({"start": s_start, "end": s_end, "count": 1, "words": w_count})
                if self._is_sticky_sentence(s_tokens):
                    sticky_spans.append({"start": s_start, "end": s_end, "count": 1, "words": w_count})
        if self._fast_cues:
            f_cnt = s_cnt = n_cnt = 0
            for w in _WORD_RE.findall(clean):
                is_f, is_s, is_n = self._classify_cue(w.lower())
                if is_f:
                    f_cnt += 1
                if is_s:
                    s_cnt += 1
                if is_n:
                    n_cnt += 1
        else:
            f_cnt = len(self.filter.findall(clean))
            s_cnt = len(self.sensory.findall(clean))
            n_cnt = count_nominal_matches(clean, self.nominal, self.nominal_exclusions)

        echo_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
        group = 1 if self.word.groups == 1 else 0
        for match in self.word.finditer(clean):
            tok = (match.group(group) or "").lower()
            if len(tok) >= 4 and tok not in self.language.function_words:
                echo_positions[tok].append(match.span(group))
        echo_count = sum(len(pos) for pos in echo_positions.values() if len(pos) >= 2)

        d_group = quotation_capture_group(self.dialogue)
        quoted_spans = sorted(
            match.span(d_group)
            for match in self.dialogue.finditer(clean)
            if match.start(d_group) >= 0 and match.end(d_group) > match.start(d_group)
        )
        dialogue_tag_count = (
            len(find_dialogue_tag_spans(clean, quoted_spans, self.dialogue_tag))
            if self.dialogue_tag_available
            else 0
        )
        indirect_speech_count = (
            len(find_indirect_speech_spans(clean, quoted_spans, self.language.key))
            if self.indirect_speech_available
            else 0
        )

        self._last_scan = (clean, asl_spans, sticky_spans)
        return ParagraphCounts(
            words=len(tokens), sentences=sentences,
            dialogue=sum(len(self.word.findall(part)) for part in quotation_texts(self.dialogue, clean)),
            function=sum(token in self.language.function_words for token in tokens),
            filter=f_cnt,
            sensory=s_cnt,
            modal=sum(token in self.modals for token in tokens),
            nominal=n_cnt,
            passive=len(self.passive.findall(clean)),
            sticky=len(sticky_spans),
            dialogue_tag=dialogue_tag_count,
            echo=echo_count,
            indirect_speech=indirect_speech_count,
        )

    def evidence(self, clean: str, display: str, counts: ParagraphCounts, *,
                 tense_spans: tuple[list[tuple[int, int]], list[tuple[int, int]]] | None = None) -> ParagraphEvidence:
        values = counts.layers()
        kinds = dict(_KINDS)
        if tense_spans is not None:
            kinds.update(present="pattern", past="pattern")
            values.update(present=len(tense_spans[0]), past=len(tense_spans[1]))
        if not is_normalized("NFC", clean):
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
        if self._last_scan is not None and self._last_scan[0] == clean:
            spans["asl"] = [dict(sp) for sp in self._last_scan[1]]  # type: ignore[misc]
            spans["sticky"] = [dict(sp) for sp in self._last_scan[2]]  # type: ignore[misc]
        else:
            for start, end in split_sentence_spans(clean, self.language.key):
                s_tokens = [tok.lower() for tok in self.word.findall(clean[start:end])]
                words = len(s_tokens)
                if words:
                    spans["asl"].append({"start": start, "end": end, "count": 1, "words": words})
                    if self._is_sticky_sentence(s_tokens):
                        spans["sticky"].append({"start": start, "end": end, "count": 1, "words": words})
        group = 1 if self.word.groups == 1 else 0
        function_words = self.language.function_words
        modals = self.modals
        function_spans = spans["function"]
        modal_spans = spans["modal"]
        echo_positions: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for match in self.word.finditer(clean):
            # With one capture findall returns that capture, not the full
            # match. Preserve the actual counted token and its exact range.
            token = (match.group(group) or "").lower()
            is_func = token in function_words
            is_modal = token in modals
            is_echo_candidate = len(token) >= 4 and not is_func
            if is_func or is_modal or is_echo_candidate:
                start, end = match.span(group)
                if is_func:
                    function_spans.append({"start": start, "end": end, "count": 1})
                if is_modal:
                    modal_spans.append({"start": start, "end": end, "count": 1})
                if is_echo_candidate:
                    echo_positions[token].append((start, end))
        echo_spans_raw = sorted(
            span for pos in echo_positions.values() if len(pos) >= 2 for span in pos
        )
        spans["echo"] = [{"start": s, "end": e, "count": 1} for s, e in echo_spans_raw]
        if self._fast_cues:
            for match in _WORD_RE.finditer(clean):
                is_f, is_s, is_n = self._classify_cue(match.group().lower())
                if is_f:
                    spans["filter"].append({"start": match.start(), "end": match.end(), "count": 1})
                if is_s:
                    spans["sensory"].append({"start": match.start(), "end": match.end(), "count": 1})
                if is_n:
                    spans["nominal"].append({"start": match.start(), "end": match.end(), "count": 1})
            for match in self.passive.finditer(clean):
                spans["passive"].append({"start": match.start(), "end": match.end(), "count": 1})
        else:
            for key, pattern in (("filter", self.filter), ("sensory", self.sensory),
                                 ("passive", self.passive), ("nominal", self.nominal)):
                for match in pattern.finditer(clean):
                    if key == "nominal" and match.group().lower() in self.nominal_exclusions:
                        continue
                    spans[key].append({"start": match.start(), "end": match.end(), "count": 1})
        d_group = quotation_capture_group(self.dialogue)
        quoted_spans_for_tags: list[tuple[int, int]] = []
        for match in self.dialogue.finditer(clean):
            count = len(self.word.findall(match.group(d_group) or ""))
            start, end = match.span(d_group)
            if end > start:
                quoted_spans_for_tags.append((start, end))
            if count:
                spans["dialogue"].append({"start": start, "end": end, "count": count})
        if self.dialogue_tag_available:
            tag_spans = find_dialogue_tag_spans(clean, sorted(quoted_spans_for_tags), self.dialogue_tag)
            spans["dialogue_tag"] = [{"start": s, "end": e, "count": 1} for s, e in tag_spans]
        if self.indirect_speech_available:
            ind_spans = find_indirect_speech_spans(
                clean, sorted(quoted_spans_for_tags), self.language.key
            )
            spans["indirect_speech"] = [{"start": s, "end": e, "count": 1} for s, e in ind_spans]
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
        unavailable_by_lang = {
            key for key, avail in (
                ("sticky", self.sticky_available),
                ("dialogue_tag", self.dialogue_tag_available),
                ("indirect_speech", self.indirect_speech_available),
            )
            if not avail
        }
        result_layers: dict[str, LayerEvidence] = {}
        for key, count in values.items():
            if key in unavailable_by_lang:
                result_layers[key] = {
                    "status": "unavailable", "kind": kinds[key], "count": None,
                    "mapped_count": 0, "spans": [], "reason": "language_unavailable",
                }
            else:
                result_layers[key] = _layer(
                    kinds[key], count, spans[key],
                    reason="unicode_mapping_unavailable" if key in unmapped else "zero_width_matches",
                )
        return _envelope(display, result_layers)


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
