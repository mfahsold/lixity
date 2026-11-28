"""Deterministic project-specific voice calibration scripts.

A probe combines natural manuscript prose with the project's important and
difficult terms. It is private author data: callers decide where the resulting
script is displayed or stored, and diagnostics never log its text.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Literal

from .characters import _name_pattern, resolve_character_settings
from .language import ResolvedLanguage, compile_pattern, compile_word_pattern
from .markdown_parser import prose_text
from .pipeline import document_paragraph_texts, resolve_document_config
from .quotation import scan_quotations
from .sentences import split_sentence_spans
from .speech_controls import (
    merge_pronunciation_spans,
    phoneme_spans,
    pronunciation_spans,
)
from .speech_profiles import AudioProfile, AudioSettings, parse_audio_settings
from .terms import derive_manuscript_term_occurrences, parse_terms

PROBE_SCHEMA = "lixity-voice-probe-script/1"
PROBE_METHOD_VERSION = "lixity-voice-probe-method/1"
DURATION_METHOD = "word_count_at_130_wpm"
MIN_PROBE_SECONDS = 120
MAX_PROBE_SECONDS = 180
DEFAULT_PROBE_SECONDS = 150
WORDS_PER_MINUTE = 130
MIN_PROBE_WORDS = MIN_PROBE_SECONDS * WORDS_PER_MINUTE // 60
MAX_PROBE_WORDS = MAX_PROBE_SECONDS * WORDS_PER_MINUTE // 60
MAX_PROBE_TERMS = 24
MIN_PART_WORDS = 43
MAX_PART_WORDS = 87
MAX_SENTENCE_WORDS = 32

ProbeStatus = Literal["ready", "insufficient_source", "invalid_configuration"]
TermKind = Literal["configured_term", "character", "lexicon", "frequent", "special_form"]
PronunciationKind = Literal["substitution", "phoneme"]

_KIND_RANK: Mapping[TermKind, int] = {
    "configured_term": 0,
    "character": 1,
    "lexicon": 2,
    "special_form": 3,
    "frequent": 4,
}
_SENTENCE_INITIAL_ARTICLES = frozenset({
    "a", "an", "the", "der", "die", "das", "den", "dem", "des", "ein", "eine",
    "einen", "einem", "einer", "eines", "le", "la", "les", "un", "une", "el",
    "los", "las", "il", "lo", "gli", "o", "as", "os", "um", "uma", "de", "da",
    "do", "het", "een",
})
_SPECIAL_RE = re.compile(
    r"(?<!\w)(?:(?:[^\W\d_]{1,4}\.){1,3}|\d+(?:[.,:/-]\d+)*|[^\W_]+(?:[-'’][^\W_]+)*)(?!\w)",
    re.UNICODE,
)
_OPENING_MARKS = " \t\r\n\"'„“»«\u2018’([{"


@dataclass(frozen=True)
class ProbeWarning:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class ProbeTerm:
    term: str = field(repr=False)
    kind: TermKind
    count: int
    ipa: str | None = field(default=None, repr=False)
    respelling: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"term": self.term, "kind": self.kind, "count": self.count}
        if self.ipa is not None:
            result["ipa"] = self.ipa
        if self.respelling is not None:
            result["respelling"] = self.respelling
        return result


@dataclass(frozen=True)
class ProbePronunciation:
    start: int
    end: int
    source: str = field(repr=False)
    replacement: str = field(repr=False)
    kind: PronunciationKind

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "source": self.source,
            "replacement": self.replacement,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class ProbeSentence:
    words: int
    start_line: int
    end_line: int
    text: str = field(repr=False)
    terms: tuple[str, ...] = field(default=(), repr=False)
    dialogue: bool = False
    source_order: int = field(default=0, repr=False)
    paragraph_index: int = field(default=0, repr=False)
    paragraph_start: int = field(default=0, repr=False)
    paragraph_end: int = field(default=0, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "words": self.words,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "terms": list(self.terms),
            "dialogue": self.dialogue,
        }


@dataclass(frozen=True)
class ProbePart:
    index: int
    words: int
    terms: tuple[str, ...] = field(repr=False)
    text: str = field(repr=False)
    sentences: tuple[ProbeSentence, ...] = field(repr=False)
    substitutions: tuple[ProbePronunciation, ...] = field(default=(), repr=False)
    phonemes: tuple[ProbePronunciation, ...] = field(default=(), repr=False)

    @property
    def estimated_seconds(self) -> int:
        return _estimated_seconds(self.words)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "words": self.words,
            "estimated_seconds": self.estimated_seconds,
            "terms": list(self.terms),
            "substitutions": [span.to_dict() for span in self.substitutions],
            "phonemes": [span.to_dict() for span in self.phonemes],
            "sentences": [sentence.to_dict() for sentence in self.sentences],
        }


@dataclass(frozen=True)
class VoiceProbeScript:
    language: str
    target_seconds: int
    estimated_seconds: int
    status: ProbeStatus
    warnings: tuple[ProbeWarning, ...]
    source_sha256: str
    settings_sha256: str
    method_version: str
    duration_method: str
    parts: tuple[ProbePart, ...] = field(repr=False)
    selected_terms: tuple[str, ...] = field(repr=False)
    covered_terms: tuple[str, ...] = field(repr=False)
    term_provenance: tuple[ProbeTerm, ...] = field(repr=False)
    probe_sha256: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not self.probe_sha256:
            object.__setattr__(self, "probe_sha256", voice_probe_sha256(self.to_dict()))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": PROBE_SCHEMA,
            "status": self.status,
            "language": self.language,
            "target_seconds": self.target_seconds,
            "estimated_seconds": self.estimated_seconds,
            "duration_method": self.duration_method,
            "method_version": self.method_version,
            "source_sha256": self.source_sha256,
            "settings_sha256": self.settings_sha256,
            "selected_terms": list(self.selected_terms),
            "covered_terms": list(self.covered_terms),
            "term_provenance": [term.to_dict() for term in self.term_provenance],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "parts": [part.to_dict() for part in self.parts],
        }
        payload["probe_sha256"] = voice_probe_sha256(payload)
        return payload


@dataclass
class _TermMatch:
    term: str
    kind: TermKind
    score: int
    start: int
    end: int
    ipa: str | None = None
    respelling: str | None = None
    metadata_priority: int = 0


@dataclass
class _Candidate:
    term: str = field(repr=False)
    kind: TermKind
    score: int
    spans: set[tuple[int, int, int]] = field(default_factory=set, repr=False)
    ipa: str | None = field(default=None, repr=False)
    respelling: str | None = field(default=None, repr=False)
    ipa_priority: int = -1
    respelling_priority: int = -1

    @property
    def count(self) -> int:
        return len(self.spans)


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted((_canonical_value(item) for item in value), key=lambda item: json.dumps(
            item, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ))
    return value


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        _canonical_value(value), sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def voice_probe_sha256(probe_dict: Mapping[str, Any]) -> str:
    """Hash a canonical script payload, ignoring its top-level self-hash."""
    payload = {key: value for key, value in probe_dict.items() if key != "probe_sha256"}
    return _canonical_sha256(payload)


def _settings_sha256(settings: Mapping[str, Any]) -> str:
    # The selected manuscript path is project-local plumbing, not a generator
    # setting. Its exact bytes are already bound by source_sha256.
    relevant = {key: value for key, value in settings.items() if key != "manuscript"}
    return _canonical_sha256(relevant)


def _word_count(text: str, word_re: re.Pattern[str]) -> int:
    return sum(1 for match in word_re.finditer(text) if match.group(0))


def _estimated_seconds(words: int) -> int:
    return round(words * 60 / WORDS_PER_MINUTE)


def _warning(status: ProbeStatus) -> ProbeWarning:
    if status == "invalid_configuration":
        return ProbeWarning(
            "invalid_configuration",
            "Project configuration is invalid; review the configured terms, characters and audio settings. "
            "The script is not savable.",
        )
    return ProbeWarning(
        "insufficient_source",
        "The manuscript does not contain enough unique prose for a balanced 120–180 second voice probe. "
        "The script is not savable.",
    )


def _empty_script(
    *,
    settings: Mapping[str, Any],
    language: str,
    target_seconds: int,
    status: ProbeStatus,
    source_sha256: str,
) -> VoiceProbeScript:
    return VoiceProbeScript(
        language=language,
        target_seconds=target_seconds,
        estimated_seconds=0,
        status=status,
        warnings=(_warning(status),),
        source_sha256=source_sha256,
        settings_sha256=_settings_sha256(settings),
        method_version=PROBE_METHOD_VERSION,
        duration_method=DURATION_METHOD,
        parts=(),
        selected_terms=(),
        covered_terms=(),
        term_provenance=(),
    )


def _add_match(
    matches: list[_TermMatch],
    *,
    term: str,
    kind: TermKind,
    score: int,
    start: int,
    end: int,
    ipa: str | None = None,
    respelling: str | None = None,
    metadata_priority: int = 0,
) -> None:
    if start < 0 or end <= start:
        return
    matches.append(_TermMatch(
        term=term, kind=kind, score=score, start=start, end=end,
        ipa=ipa, respelling=respelling, metadata_priority=metadata_priority,
    ))


def _matched_key(text: str, start: int, end: int, keys: Sequence[str], *, case_sensitive: bool) -> str | None:
    source = text[start:end]
    comparable = source if case_sensitive else source.casefold()
    for key in sorted(keys, key=lambda value: (-len(value), value)):
        if (key if case_sensitive else key.casefold()) == comparable:
            return key
    return None


def _explicit_term_forms(settings: Mapping[str, Any], terms: Mapping[str, Any], audio: AudioSettings) -> set[str]:
    forms = {term.casefold() for term in terms}
    for profile in terms.values():
        forms.update(alias.casefold() for alias in profile.aliases)
        forms.update(alternative.term.casefold() for alternative in profile.scoped_alternatives)
    characters = settings.get("characters")
    if isinstance(characters, Mapping):
        forms.update(str(label).casefold() for label in characters)
        for values in characters.values():
            if isinstance(values, Mapping):
                forms.update(str(alias).casefold() for alias in values.get("aliases", []))
    legacy_names = settings.get("names")
    if isinstance(legacy_names, Mapping):
        forms.update(str(label).casefold() for label in legacy_names.values())
    elif isinstance(legacy_names, Sequence) and not isinstance(legacy_names, str | bytes):
        forms.update(str(name).casefold() for name in legacy_names)
    forms.update(term.casefold() for term in audio.pronunciations)
    if audio.pronunciation_lexicon is not None:
        forms.update(term.casefold() for term in audio.pronunciation_lexicon.entries)
    selected = audio.profiles.get(audio.selected)
    if selected is not None:
        forms.update(term.casefold() for term in selected.phonemes)
        forms.update(term.casefold() for term in selected.pronunciations)
    return forms


def _unselected_audio_forms(audio: AudioSettings) -> set[str]:
    selected = audio.profiles.get(audio.selected)
    selected_forms = set(selected.phonemes) | set(selected.pronunciations) if selected is not None else set()
    forms: set[str] = set()
    for profile_id, profile in audio.profiles.items():
        if profile_id == audio.selected:
            continue
        forms.update(term.casefold() for term in profile.phonemes)
        forms.update(term.casefold() for term in profile.pronunciations)
    return forms - {term.casefold() for term in selected_forms}


def _configured_matches(
    paragraphs: Sequence[Any],
    sentences: Sequence[ProbeSentence],
    terms: Mapping[str, Any],
    source_sha256: str,
) -> list[list[_TermMatch]]:
    matches: list[list[_TermMatch]] = [[] for _ in sentences]
    if not terms:
        return matches
    report = derive_manuscript_term_occurrences(
        paragraphs, terms, source_path="", source_sha256=source_sha256,
    )
    by_paragraph: dict[int, list[dict[str, Any]]] = {}
    for hit in report["occurrences"]:
        if hit["expected_in_chapter"]:
            by_paragraph.setdefault(int(hit["paragraph_index"]), []).append(hit)
    for index, sentence in enumerate(sentences):
        seen: set[tuple[int, int]] = set()
        for hit in by_paragraph.get(sentence.paragraph_index, []):
            start = int(hit["start"])
            end = int(hit["end"])
            if end <= sentence.paragraph_start or start >= sentence.paragraph_end:
                continue
            if (start, end) in seen:
                continue
            seen.add((start, end))
            local_start = max(start, sentence.paragraph_start) - sentence.paragraph_start
            local_end = min(end, sentence.paragraph_end) - sentence.paragraph_start
            _add_match(
                matches[index], term=str(hit["term"]), kind="configured_term", score=1000,
                start=local_start, end=local_end,
            )
    return matches


def _character_matches(sentences: Sequence[ProbeSentence], settings: Mapping[str, Any]) -> list[list[_TermMatch]]:
    matches: list[list[_TermMatch]] = [[] for _ in sentences]
    resolved = resolve_character_settings(None, settings)
    names = resolved.names
    entries = names.items() if isinstance(names, Mapping) else ((name, name) for name in names)
    patterns = [(label, _name_pattern(pattern)) for pattern, label in entries]
    for index, sentence in enumerate(sentences):
        for label, pattern in patterns:
            right = -1
            for match in pattern.finditer(sentence.text):
                start, end = match.span()
                if start < right or end <= start:
                    continue
                right = end
                _add_match(
                    matches[index], term=str(label), kind="character", score=950,
                    start=start, end=end,
                )
    return matches


def _build_sentences(
    text: str,
    config: Any,
    resolved: ResolvedLanguage,
) -> list[ProbeSentence]:
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_pattern = compile_pattern(config.dialogue_regex) if config.dialogue_regex is not None else None
    sentences: list[ProbeSentence] = []
    source_order = 0
    for paragraph_index, paragraph in enumerate(document_paragraph_texts(text, config)):
        dialogue_spans = scan_quotations(
            paragraph.text, resolved.key, pattern=dialogue_pattern,
        ).spans
        for start, end in split_sentence_spans(paragraph.text, resolved.key):
            value = paragraph.text[start:end].strip()
            offset = paragraph.text.find(value, start, end)
            if offset < 0:
                offset = start
            words = _word_count(value, word_re)
            if not 4 <= words <= MAX_SENTENCE_WORDS:
                continue
            dialogue = any(
                span.start < offset + len(value) and offset < span.end for span in dialogue_spans
            )
            sentences.append(ProbeSentence(
                words=words,
                start_line=paragraph.start_line,
                end_line=paragraph.end_line,
                text=value,
                dialogue=dialogue,
                source_order=source_order,
                paragraph_index=paragraph_index,
                paragraph_start=offset,
                paragraph_end=offset + len(value),
            ))
            source_order += 1
    return sentences


def _generic_matches(
    sentences: Sequence[ProbeSentence],
    resolved: ResolvedLanguage,
    suppressed_forms: set[str],
    explicit_forms: set[str],
) -> list[list[_TermMatch]]:
    matches: list[list[_TermMatch]] = [[] for _ in sentences]
    word_re = compile_word_pattern(resolved.word_regex)
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    token_spans: list[list[tuple[int, int, str]]] = []
    for sentence in sentences:
        spans: list[tuple[int, int, str]] = []
        for match in word_re.finditer(sentence.text):
            token = match.group(0)
            if not token:
                continue
            key = token.casefold()
            counts[key] += 1
            display.setdefault(key, token)
            spans.append((match.start(), match.end(), token))
        token_spans.append(spans)
    blacklist = resolved.function_words | resolved.stopwords
    for index, sentence in enumerate(sentences):
        for start, end, token in token_spans[index]:
            key = token.casefold()
            if key in explicit_forms or (key in suppressed_forms and key not in explicit_forms):
                continue
            if len(token) >= 3 and token.isalpha() and counts[key] >= 2 and key not in blacklist:
                _add_match(
                    matches[index], term=display[key], kind="frequent", score=min(counts[key], 500),
                    start=start, end=end,
                )
        for match in _SPECIAL_RE.finditer(sentence.text):
            term = match.group(0)
            key = term.casefold()
            if key in blacklist or key in explicit_forms or (
                key in suppressed_forms and key not in explicit_forms
            ):
                continue
            start, end = match.span()
            before = sentence.text[:start]
            sentence_initial = not before.strip(_OPENING_MARKS)
            if sentence_initial and key in _SENTENCE_INITIAL_ARTICLES:
                continue
            if "." in term and term.endswith(".") and not sentence.text[end:].strip():
                continue
            score = 0
            if any(character.isdigit() for character in term):
                score = 650
            elif "." in term or (term.isupper() and 2 <= len(term) <= 12):
                score = 750
            elif "-" in term or "'" in term or "’" in term:
                score = 700
            elif term[:1].isupper():
                score = 550
            elif any(character.isupper() for character in term[1:]):
                score = 600
            if score:
                _add_match(
                    matches[index], term=term, kind="special_form", score=score,
                    start=start, end=end,
                )
    return matches


def _audio_matches(
    sentences: Sequence[ProbeSentence],
    audio: AudioSettings,
) -> list[list[_TermMatch]]:
    matches: list[list[_TermMatch]] = [[] for _ in sentences]
    profile = audio.profiles.get(audio.selected)
    matching = audio.pronunciation_matching
    pronunciations = dict(audio.pronunciations)
    if profile is not None:
        pronunciations.update(profile.pronunciations)
    pronunciation_keys = sorted(pronunciations)
    lexicon = audio.pronunciation_lexicon.entries if audio.pronunciation_lexicon is not None else {}
    lexicon_keys = sorted(lexicon)
    phoneme_keys = sorted(profile.phonemes) if profile is not None else []
    for index, sentence in enumerate(sentences):
        for start, end, _replacement in pronunciation_spans(
            sentence.text, pronunciations,
            case_sensitive=matching.case_sensitive,
            whole_words=matching.whole_words,
        ):
            key = _matched_key(
                sentence.text, start, end, pronunciation_keys,
                case_sensitive=matching.case_sensitive,
            )
            if key is None:
                continue
            selected_value = profile.pronunciations.get(key) if profile is not None else None
            replacement = selected_value if selected_value is not None else audio.pronunciations[key]
            priority = 20 if selected_value is not None else 10
            _add_match(
                matches[index], term=key, kind="special_form", score=850,
                start=start, end=end, respelling=replacement,
                metadata_priority=priority,
            )
        for start, end, term in phoneme_spans(sentence.text, {key: key for key in lexicon_keys}):
            entry = lexicon[term]
            _add_match(
                matches[index], term=term, kind="lexicon", score=875,
                start=start, end=end, ipa=entry.ipa, respelling=entry.respelling,
                metadata_priority=30,
            )
        profile_phonemes = dict(sorted(profile.phonemes.items())) if profile is not None else {}
        for start, end, ipa in phoneme_spans(sentence.text, profile_phonemes):
            key = _matched_key(sentence.text, start, end, phoneme_keys, case_sensitive=True)
            if key is None:
                continue
            _add_match(
                matches[index], term=key, kind="special_form", score=850,
                start=start, end=end, ipa=ipa, metadata_priority=20,
            )
    return matches


def _aggregate_candidates(
    sentence_matches: Sequence[Sequence[_TermMatch]],
) -> tuple[dict[str, _Candidate], list[tuple[str, ...]]]:
    candidates: dict[str, _Candidate] = {}
    sentence_terms: list[tuple[str, ...]] = []
    for source_order, matches in enumerate(sentence_matches):
        terms: list[str] = []
        for match in matches:
            candidate = candidates.get(match.term)
            if candidate is None:
                candidate = _Candidate(term=match.term, kind=match.kind, score=match.score)
                candidates[match.term] = candidate
            if _KIND_RANK[match.kind] < _KIND_RANK[candidate.kind]:
                candidate.kind = match.kind
            candidate.score = max(candidate.score, match.score)
            candidate.spans.add((source_order, match.start, match.end))
            if match.ipa is not None and match.metadata_priority >= candidate.ipa_priority:
                candidate.ipa = match.ipa
                candidate.ipa_priority = match.metadata_priority
            if match.respelling is not None and match.metadata_priority >= candidate.respelling_priority:
                candidate.respelling = match.respelling
                candidate.respelling_priority = match.metadata_priority
            terms.append(match.term)
        sentence_terms.append(tuple(dict.fromkeys(terms)))
    return candidates, sentence_terms


def _candidate_category(candidate: _Candidate) -> str:
    if candidate.kind in {"configured_term", "character", "lexicon"} or candidate.score >= 850:
        return "configured"
    if any(character.isdigit() for character in candidate.term):
        return "number"
    if "." in candidate.term or (candidate.term.isupper() and len(candidate.term) >= 2):
        return "abbreviation"
    if "-" in candidate.term or "'" in candidate.term or "’" in candidate.term:
        return "connector"
    if candidate.kind == "frequent":
        return "frequent"
    return "capitalized"


def _rank_candidates(candidates: Mapping[str, _Candidate]) -> list[_Candidate]:
    ordered = sorted(
        candidates.values(),
        key=lambda candidate: (
            -candidate.score, -candidate.count, candidate.term.casefold(), candidate.term,
        ),
    )
    groups: dict[str, list[_Candidate]] = {
        category: [] for category in (
            "configured", "abbreviation", "number", "connector", "capitalized", "frequent",
        )
    }
    for candidate in ordered:
        groups[_candidate_category(candidate)].append(candidate)
    selected: list[_Candidate] = []
    positions = dict.fromkeys(groups, 0)
    while len(selected) < MAX_PROBE_TERMS:
        added = False
        for category, values in groups.items():
            position = positions[category]
            if position >= len(values):
                continue
            selected.append(values[position])
            positions[category] = position + 1
            added = True
            if len(selected) == MAX_PROBE_TERMS:
                break
        if not added:
            break
    return selected


def _annotate_sentences(
    sentences: Sequence[ProbeSentence], sentence_terms: Sequence[tuple[str, ...]],
) -> list[ProbeSentence]:
    return [
        ProbeSentence(
            words=sentence.words,
            start_line=sentence.start_line,
            end_line=sentence.end_line,
            text=sentence.text,
            terms=sentence_terms[index],
            dialogue=sentence.dialogue,
            source_order=sentence.source_order,
            paragraph_index=sentence.paragraph_index,
            paragraph_start=sentence.paragraph_start,
            paragraph_end=sentence.paragraph_end,
        )
        for index, sentence in enumerate(sentences)
    ]


def _deduplicate_sentences(sentences: Sequence[ProbeSentence]) -> list[ProbeSentence]:
    seen: set[str] = set()
    unique: list[ProbeSentence] = []
    for sentence in sorted(sentences, key=lambda value: value.source_order):
        key = unicodedata.normalize("NFC", sentence.text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    return unique


def _dialogue_share(sentences: Sequence[ProbeSentence]) -> float:
    total = sum(sentence.words for sentence in sentences)
    if not total:
        return 0.0
    return sum(sentence.words for sentence in sentences if sentence.dialogue) / total


def _ordered_selection(
    sentences: Sequence[ProbeSentence],
    selected_terms: Sequence[str],
    candidates: Mapping[str, _Candidate],
    source_dialogue_share: float,
) -> list[ProbeSentence]:
    remaining = set(range(len(sentences)))
    chosen: list[ProbeSentence] = []
    uncovered = set(selected_terms)
    current_words = 0

    def category_bonus(sentence: ProbeSentence) -> int:
        if not chosen:
            return 0
        has_dialogue = any(item.dialogue for item in chosen)
        has_narration = any(not item.dialogue for item in chosen)
        return int((not has_dialogue and sentence.dialogue) or (not has_narration and not sentence.dialogue))

    while uncovered and current_words < MAX_PROBE_WORDS:
        best_index = max(
            (
                index for index in remaining
                if current_words + sentences[index].words <= MAX_PROBE_WORDS
                and uncovered.intersection(sentences[index].terms)
            ),
            key=lambda index: (
                sum(candidates[term].score for term in uncovered.intersection(sentences[index].terms)),
                len(uncovered.intersection(sentences[index].terms)),
                category_bonus(sentences[index]),
                -abs(sentences[index].words - 14),
                -sentences[index].source_order,
            ),
            default=None,
        )
        if best_index is None:
            break
        sentence = sentences[best_index]
        chosen.append(sentence)
        remaining.remove(best_index)
        current_words += sentence.words
        uncovered.difference_update(sentence.terms)

    while remaining and current_words < MAX_PROBE_WORDS:
        dialogue_words = sum(item.words for item in chosen if item.dialogue)
        current_share = dialogue_words / current_words if current_words else source_dialogue_share

        def balance_bonus(
            sentence: ProbeSentence,
            *,
            selected_words: int = current_words,
            selected_dialogue_words: int = dialogue_words,
            selected_share: float = current_share,
        ) -> int:
            if selected_words == 0:
                return 0
            after = (selected_dialogue_words + (sentence.words if sentence.dialogue else 0)) / (
                selected_words + sentence.words
            )
            return int(abs(after - source_dialogue_share) < abs(selected_share - source_dialogue_share))

        best_index = max(
            (
                index for index in remaining
                if current_words + sentences[index].words <= MAX_PROBE_WORDS
            ),
            key=lambda index: (
                len(uncovered.intersection(sentences[index].terms)),
                balance_bonus(sentences[index]) * 1000 + category_bonus(sentences[index]) * 500,
                len(sentences[index].terms),
                -abs(sentences[index].words - 14),
                -sentences[index].source_order,
            ),
            default=None,
        )
        if best_index is None:
            break
        sentence = sentences[best_index]
        chosen.append(sentence)
        remaining.remove(best_index)
        current_words += sentence.words
        uncovered.difference_update(sentence.terms)
    return chosen


def _partition_ready(sentences: Sequence[ProbeSentence], target_seconds: int) -> tuple[ProbePart, ...] | None:
    if len(sentences) < 3:
        return None
    total_words = sum(sentence.words for sentence in sentences)
    if not MIN_PROBE_WORDS <= total_words <= MAX_PROBE_WORDS:
        return None
    overall_dialogue = _dialogue_share(sentences)
    target_words = round(target_seconds * WORDS_PER_MINUTE / 60)
    preferred_parts = max(3, min(6, round(target_words / 65) or 3))
    best_key: tuple[float, int, int] | None = None
    best_ranges: list[tuple[int, int]] | None = None
    count = len(sentences)
    for part_count in range(3, 7):
        if count < part_count:
            continue
        desired = total_words / part_count
        costs: list[list[float | None]] = [[None] * (part_count + 1) for _ in range(count + 1)]
        previous: list[list[int | None]] = [[None] * (part_count + 1) for _ in range(count + 1)]
        costs[0][0] = 0.0
        for used in range(part_count):
            for start in range(count):
                base = costs[start][used]
                if base is None:
                    continue
                words = 0
                dialogue_words = 0
                for end in range(start + 1, count + 1):
                    sentence = sentences[end - 1]
                    words += sentence.words
                    dialogue_words += sentence.words if sentence.dialogue else 0
                    if words > MAX_PART_WORDS:
                        break
                    if words < MIN_PART_WORDS:
                        continue
                    dialogue_share = dialogue_words / words
                    cost = base + (words - desired) ** 2 + (dialogue_share - overall_dialogue) ** 2 * words
                    current = costs[end][used + 1]
                    if current is None or cost < current:
                        costs[end][used + 1] = cost
                        previous[end][used + 1] = start
        final_cost = costs[count][part_count]
        if final_cost is None:
            continue
        key = (round(final_cost, 9), abs(part_count - preferred_parts), part_count)
        if best_key is not None and key >= best_key:
            continue
        ranges: list[tuple[int, int]] = []
        end = count
        for used in range(part_count, 0, -1):
            boundary_start = previous[end][used]
            if boundary_start is None:
                raise RuntimeError("Voice probe partition lost its sentence boundary")
            ranges.append((boundary_start, end))
            end = boundary_start
        if end != 0:
            raise RuntimeError("Voice probe partition does not cover its sentences")
        best_key = key
        best_ranges = list(reversed(ranges))
    if best_ranges is None:
        return None
    return tuple(
        _make_part(index, sentences[start:end])
        for index, (start, end) in enumerate(best_ranges, 1)
    )


def _short_parts(sentences: Sequence[ProbeSentence]) -> tuple[ProbePart, ...]:
    if not sentences:
        return ()
    groups: list[list[ProbeSentence]] = []
    current: list[ProbeSentence] = []
    words = 0
    for sentence in sentences:
        if current and words + sentence.words > MAX_PART_WORDS:
            groups.append(current)
            current, words = [], 0
        current.append(sentence)
        words += sentence.words
    if current:
        groups.append(current)
    return tuple(_make_part(index, group) for index, group in enumerate(groups, 1))


def _make_part(
    index: int,
    sentences: Sequence[ProbeSentence],
    audio: AudioSettings | None = None,
    profile: AudioProfile | None = None,
) -> ProbePart:
    text = " ".join(sentence.text for sentence in sentences)
    substitutions: list[ProbePronunciation] = []
    phonemes: dict[tuple[int, int], ProbePronunciation] = {}
    if audio is not None:
        matching = audio.pronunciation_matching
        pronunciations = dict(audio.pronunciations)
        if profile is not None:
            pronunciations.update(profile.pronunciations)
        legacy = pronunciation_spans(
            text, pronunciations,
            case_sensitive=matching.case_sensitive,
            whole_words=matching.whole_words,
        )
        lexicon = audio.pronunciation_lexicon.entries if audio.pronunciation_lexicon is not None else {}
        selected_spans: list[tuple[int, int, str]] = []
        for start, end, term in phoneme_spans(text, {key: key for key in sorted(lexicon)}):
            entry = lexicon[term]
            if entry.ipa is not None and profile is not None and profile.control_support.phonemes:
                phonemes[start, end] = ProbePronunciation(
                    start, end, term, entry.ipa, "phoneme",
                )
                selected_spans.append((start, end, term))
            elif entry.respelling is not None:
                selected_spans.append((start, end, entry.respelling))
            elif entry.ipa is not None:
                phonemes[start, end] = ProbePronunciation(
                    start, end, term, entry.ipa, "phoneme",
                )
                selected_spans.append((start, end, term))
        merged = merge_pronunciation_spans(legacy, selected_spans)
        for start, end, replacement in merged:
            source = text[start:end]
            if source == replacement:
                continue
            substitutions.append(ProbePronunciation(
                start, end, source, replacement, "substitution",
            ))
        if profile is not None:
            for start, end, ipa in phoneme_spans(text, dict(sorted(profile.phonemes.items()))):
                key = _matched_key(text, start, end, sorted(profile.phonemes), case_sensitive=True)
                source = key if key is not None else text[start:end]
                phonemes.setdefault((start, end), ProbePronunciation(
                    start, end, source, ipa, "phoneme",
                ))
    return ProbePart(
        index=index,
        words=sum(sentence.words for sentence in sentences),
        terms=tuple(dict.fromkeys(term for sentence in sentences for term in sentence.terms)),
        text=text,
        sentences=tuple(sentences),
        substitutions=tuple(sorted(substitutions, key=lambda span: (span.start, span.end, span.source))),
        phonemes=tuple(sorted(phonemes.values(), key=lambda span: (span.start, span.end, span.source))),
    )


def _select_ready_parts(
    sentences: Sequence[ProbeSentence],
    selected_terms: Sequence[str],
    candidates: Mapping[str, _Candidate],
    target_seconds: int,
) -> tuple[ProbePart, ...] | None:
    source_share = _dialogue_share(sentences)
    primary = _ordered_selection(sentences, selected_terms, candidates, source_share)
    orderings = (primary, list(sentences))
    target_words = round(target_seconds * WORDS_PER_MINUTE / 60)
    best_key: tuple[int, int, float, int, int, int] | None = None
    best_parts: tuple[ProbePart, ...] | None = None
    for ordering in orderings:
        total = 0
        for length, sentence in enumerate(ordering, 1):
            total += sentence.words
            if total > MAX_PROBE_WORDS:
                break
            if total < MIN_PROBE_WORDS:
                continue
            ordered = sorted(ordering[:length], key=lambda value: value.source_order)
            parts = _partition_ready(ordered, target_seconds)
            if parts is None:
                continue
            covered = {term for part in parts for term in part.terms}
            uncovered = len(set(selected_terms) - covered)
            dialogue_delta = abs(_dialogue_share(ordered) - source_share)
            key = (
                uncovered,
                abs(sum(part.estimated_seconds for part in parts) - target_seconds),
                dialogue_delta,
                abs(total - target_words),
                abs(len(parts) - max(3, min(6, round(target_words / 65) or 3))),
                length,
            )
            if best_key is None or key < best_key:
                best_key = key
                best_parts = parts
    return best_parts


def build_voice_probe_script(
    text: str,
    *,
    language: str = "en",
    project_config: Mapping[str, Any] | None = None,
    target_seconds: int = DEFAULT_PROBE_SECONDS,
    source_sha256: str | None = None,
) -> VoiceProbeScript:
    """Build a deterministic manuscript-derived calibration script.

    ``ready`` is the only savable status. Invalid project configuration and
    insufficient unique prose return explicit, structured diagnostics instead
    of padding, duplicating or inventing manuscript text. ``source_sha256``
    may bind normalized snapshot text to its original retained bytes.
    """
    if type(target_seconds) is not int or not MIN_PROBE_SECONDS <= target_seconds <= MAX_PROBE_SECONDS:
        raise ValueError("Voice probe duration must be between 120 and 180 seconds")
    if not isinstance(text, str):
        raise ValueError("A manuscript is required to build a voice probe")
    if project_config is not None and not isinstance(project_config, Mapping):
        raise ValueError("Project configuration must be a mapping")
    if source_sha256 is not None and (
        not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None
    ):
        raise ValueError("source_sha256 must be 64 lowercase hexadecimal characters")
    source_digest = (
        source_sha256 if source_sha256 is not None
        else hashlib.sha256(text.encode("utf-8")).hexdigest()
    )
    settings = dict(project_config or {})
    requested_language = str(language).strip().lower() or "en"
    try:
        config, resolved = resolve_document_config(text, requested_language, project_config=settings)
        terms = parse_terms(settings.get("terms"))
        resolve_character_settings(None, settings)
        audio = parse_audio_settings(settings.get("audio"), language=resolved.key)
    except (TypeError, ValueError):
        return _empty_script(
            settings=settings, source_sha256=source_digest, language=requested_language,
            target_seconds=target_seconds, status="invalid_configuration",
        )
    try:
        prose = prose_text(text, config, _front_matter=False)
        paragraphs = document_paragraph_texts(text, config)
    except (TypeError, ValueError):
        return _empty_script(
            settings=settings, source_sha256=source_digest, language=requested_language,
            target_seconds=target_seconds, status="invalid_configuration",
        )
    if not prose.strip():
        return _empty_script(
            settings=settings, source_sha256=source_digest, language=resolved.key,
            target_seconds=target_seconds, status="insufficient_source",
        )
    try:
        sentences = _build_sentences(text, config, resolved)
    except (TypeError, ValueError):
        return _empty_script(
            settings=settings, source_sha256=source_digest, language=resolved.key,
            target_seconds=target_seconds, status="invalid_configuration",
        )
    if not sentences:
        return _empty_script(
            settings=settings, source_sha256=source_digest, language=resolved.key,
            target_seconds=target_seconds, status="insufficient_source",
        )

    suppressed_forms = _unselected_audio_forms(audio)
    explicit_forms = _explicit_term_forms(settings, terms, audio)
    sentence_matches = _generic_matches(sentences, resolved, suppressed_forms, explicit_forms)
    match_groups = (
        _audio_matches(sentences, audio),
        _character_matches(sentences, settings),
        _configured_matches(paragraphs, sentences, terms, source_digest),
    )
    for group in match_groups:
        for index, matches in enumerate(group):
            sentence_matches[index].extend(matches)
    candidates, sentence_terms = _aggregate_candidates(sentence_matches)
    sentences = _annotate_sentences(sentences, sentence_terms)
    unique_sentences = _deduplicate_sentences(sentences)
    ranked_candidates = _rank_candidates(candidates)
    selected_terms = tuple(candidate.term for candidate in ranked_candidates)
    profile = audio.profiles.get(audio.selected)

    if sum(sentence.words for sentence in unique_sentences) < MIN_PROBE_WORDS:
        parts = _short_parts(unique_sentences)
        status: ProbeStatus = "insufficient_source"
    else:
        ready_parts = _select_ready_parts(unique_sentences, selected_terms, candidates, target_seconds)
        if ready_parts is None:
            parts = _short_parts(unique_sentences)
            status = "insufficient_source"
        else:
            parts = tuple(
                _make_part(part.index, part.sentences, audio, profile)
                for part in ready_parts
            )
            status = "ready"
    if status != "ready":
        parts = tuple(_make_part(part.index, part.sentences, audio, profile) for part in parts)
    covered_terms = tuple(term for term in selected_terms if any(term in part.terms for part in parts))
    provenance = tuple(ProbeTerm(
        term=candidate.term,
        kind=candidate.kind,
        count=candidate.count,
        ipa=candidate.ipa,
        respelling=candidate.respelling,
    ) for candidate in ranked_candidates)
    return VoiceProbeScript(
        language=resolved.key,
        target_seconds=target_seconds,
        estimated_seconds=sum(part.estimated_seconds for part in parts),
        status=status,
        warnings=(() if status == "ready" else (_warning(status),)),
        source_sha256=source_digest,
        settings_sha256=_settings_sha256(settings),
        method_version=PROBE_METHOD_VERSION,
        duration_method=DURATION_METHOD,
        parts=parts,
        selected_terms=selected_terms,
        covered_terms=covered_terms,
        term_provenance=provenance,
    )
