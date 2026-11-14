"""lixity.dialogue – dialogue and interaction structure of a manuscript.

Beyond the plain dialogue share (see ``CorpusMetrics.dialog_ratio``) this
module describes the *turn structure*: how often speech starts, how long the
turns are, how dialogue is distributed across chapters and paragraphs.

Deliberately heuristic and offline: quoted speech is detected with the
language profile's dialogue pattern (curated per language); there is no
speaker attribution – a "turn" is one quoted segment, not a named speaker.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from .language import (
    compile_pattern,
    compile_word_pattern,
    quotation_capture_group,
    quotation_texts,
    resolve_language,
)
from .markdown_parser import prose_paragraphs, split_chapters  # shared segmentation (re-export)
from .models import (
    DEFAULT_DIALOGUE_PARAGRAPH_SHARE,
    DEFAULT_LONG_TURN_MIN_WORDS,
    DEFAULT_SHORT_TURN_MAX_WORDS,
    CorpusConfig,
)
from .sentences import split_prose_sentences

# A paragraph counts as dialogue paragraph when at least this share of its
# words sits inside quotation marks.
DIALOGUE_PARAGRAPH_SHARE = DEFAULT_DIALOGUE_PARAGRAPH_SHARE

# Turn-length cadence thresholds (words per recognized quoted span):
# rapid back-and-forth exchange (stichomythia proxy) vs. extended speech/monologue.
SHORT_TURN_MAX_WORDS = DEFAULT_SHORT_TURN_MAX_WORDS
LONG_TURN_MIN_WORDS = DEFAULT_LONG_TURN_MIN_WORDS

# Curated speech-attribution verbs per language for dialogue-tag density heuristics.
_DIALOGUE_TAG_VERBS: dict[str, str] = {
    "en": (
        r"\b(?:said|says|asked|asks|replied|replies|answered|answers|whispered|whispers|"
        r"murmured|murmurs|muttered|mutters|shouted|shouts|yelled|yells|called|calls|"
        r"cried|cries|laughed|laughs|sighed|sighs|snapped|snaps|added|adds|"
        r"continued|continues|explained|explains|insisted|insists|noted|notes|"
        r"told|tells|demanded|demands|groaned|groans|breathed|breathes)\b"
    ),
    "de": (
        r"\b(?:sagte|sagten|sagt|fragte|fragten|fragt|antwortete|antworteten|antwortet|"
        r"flüsterte|flüsterten|flüstert|murmelte|murmelten|murmelt|rief|riefen|ruft|"
        r"schrie|schrien|schreit|entgegnete|entgegneten|erwiderte|erwiderten|"
        r"meinte|meinten|lachte|lachten|seufzte|seufzten|brummte|brummten|"
        r"zischte|zischten|fügte|fuhr|knurrte|hauchte|stöhnte)\b"
    ),
    "fr": (
        r"\b(?:dit|dirent|demanda|demandèrent|répondit|répondirent|murmura|murmurèrent|"
        r"chuchota|chuchotèrent|cria|crièrent|lança|lancèrent|ajouta|ajoutèrent|"
        r"reprit|souffla|soupira|grommela)\b"
    ),
    "es": (
        r"\b(?:dijo|dijeron|preguntó|preguntaron|respondió|respondieron|contestó|contestaron|"
        r"susurró|susurraron|murmuró|murmuraron|gritó|gritaron|añadió|añadieron|"
        r"exclamó|exclamaron|replicó|replicaron|musitó|suspiró)\b"
    ),
    "it": (
        r"\b(?:disse|dissero|chiese|chiesero|rispose|risposero|sussurrò|sussurrarono|"
        r"mormorò|mormorarono|gridò|gridarono|aggiunse|aggiunsero|replicò|esclamò|sospirò)\b"
    ),
    "pt": (
        r"\b(?:disse|disseram|perguntou|perguntaram|respondeu|responderam|sussurrou|"
        r"murmurou|gritou|gritaram|acrescentou|acrescentaram|exclamou|replicou|suspirou)\b"
    ),
    "nl": (
        r"\b(?:zei|zeiden|zegt|vroeg|vroegen|vraagt|antwoordde|antwoordden|fluisterde|"
        r"fluisterden|mompelde|mompelden|riep|riepen|schreeuwde|voegde|zuchtte)\b"
    ),
}

_DIALOGUE_TAG_PATTERNS: dict[str, re.Pattern[str]] = {
    lang: re.compile(pattern, re.IGNORECASE | re.UNICODE)
    for lang, pattern in _DIALOGUE_TAG_VERBS.items()
}

_MANNER_ADVERB_REGEXES: dict[str, str] = {
    "en": r"\b[a-z]{3,}ly\b",
    "de": (
        r"\b(?:leise|laut|schnell|langsam|ruhig|nervös|wütend|zornig|sanft|hart|kalt|warm|"
        r"bitter|scharf|heftig|zaghaft|zögernd|flüsternd|lachend|seufzend|müde|traurig|"
        r"fröhlich|ernst|streng|freundlich|ungeduldig|geduldig|vorsichtig|hastig|barsch|"
        r"schroff|spöttisch|trocken|kühl|heiter|ängstlich|erleichtert|verzweifelt|"
        r"beiläufig|nachdenklich|entschlossen|energisch)\b"
    ),
    "fr": r"\b[a-zàâäéèêëîïôöùûüç]{3,}ment\b",
    "es": r"\b[a-záéíóúüñ]{3,}mente\b",
    "it": r"\b[a-zàèéìíîòóùú]{3,}mente\b",
    "pt": r"\b[a-záàâãéêíóôõúç]{3,}mente\b",
    "nl": (
        r"\b(?:zacht|zachtjes|luid|snel|langzaam|rustig|kalm|boos|kwaad|teder|hard|"
        r"koud|bitter|scherp|aarzelend|moe|verdrietig|vrolijk|ernstig|streng|vriendelijk|"
        r"ongeduldig|voorzichtig|haastig|kortaf|droog|koel|angstig|opgelucht|wanhopig|"
        r"peinzend|beslist)\b"
    ),
}

_MANNER_ADVERB_PATTERNS: dict[str, re.Pattern[str]] = {
    lang: re.compile(pattern, re.IGNORECASE | re.UNICODE)
    for lang, pattern in _MANNER_ADVERB_REGEXES.items()
}

_NON_MANNER_ADVERBS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "only", "really", "early", "daily", "family", "reply", "rely", "apply",
        "supply", "ally", "belly", "jelly", "holy", "ugly", "likely", "lovely",
        "friendly", "lonely", "silly",
    }),
    "fr": frozenset({
        "moment", "comment", "seulement", "vraiment", "élément", "bâtiment",
        "vêtement", "sentiment", "document",
    }),
    "es": frozenset({"solamente", "realmente", "finalmente", "exactamente", "mente"}),
    "it": frozenset({"solamente", "veramente", "finalmente", "mente"}),
    "pt": frozenset({"somente", "realmente", "finalmente", "mente"}),
}


def dialogue_tag_pattern(language_key: str) -> re.Pattern[str] | None:
    """Return the compiled speech-attribution verb pattern for a language, if any."""
    return _DIALOGUE_TAG_PATTERNS.get(language_key)


MIN_CHARACTER_VOICE_TURNS = 3

_INDIRECT_SPEECH_REGEXES: dict[str, tuple[str, ...]] = {
    "en": (
        r"\b(?:said|told\s+\w+|asked|replied|answered|explained|claimed|insisted|"
        r"admitted|whispered|murmured|noted|added|thought|felt|knew|believed|"
        r"realized|wondered|remembered|suspected|hoped|feared|imagined|assumed|"
        r"supposed)\s+(?:that|whether|if)\b",
        r"\b(?:asked|wondered)\s+(?:why|how|when|where|who|what)\b",
    ),
    "de": (
        r"\b(?:sagte|sagten|erklärte|erklärten|behauptete|behaupteten|meinte|meinten|"
        r"betonte|betonten|erwiderte|erwiderten|antwortete|antworteten|fragte|fragten|"
        r"dachte|dachten|glaubte|glaubten|vermutete|vermuteten|hoffte|hofften|"
        r"fürchtete|fürchteten|ahnte|ahnten|wusste|wussten|überlegte|überlegten|"
        r"gestand|gestanden|versicherte|versicherten|berichtete|berichteten|"
        r"erzählte|erzählten)\s*,\s*(?:dass|daß|ob)\b",
        r"\b(?:er|sie|es|man)\s+(?:sei|habe|werde|könne|müsse|dürfe|wolle|solle|"
        r"wäre|hätte|würde|könnte|müsste|dürfte|wollte|sollte)\b",
    ),
    "fr": (
        r"\b(?:dit|déclara|affirma|répondit|expliqua|ajouta|demanda|pensa|crut|"
        r"sentit|sut|comprit|espéra|craignit)\s+(?:qu'|que|si)\b",
    ),
    "es": (
        r"\b(?:dijo|declaró|afirmó|respondió|explicó|añadió|preguntó|pensó|creyó|"
        r"sintió|supo|comprendió|esperó|temió)\s+(?:que|si)\b",
    ),
    "it": (
        r"\b(?:disse|dichiarò|affermò|rispose|spiegò|aggiunse|chiese|pensò|credeva|"
        r"sentì|seppe|capì|sperò|temette)\s+(?:che|se)\b",
    ),
    "pt": (
        r"\b(?:disse|declarou|afirmou|respondeu|explicou|acrescentou|perguntou|"
        r"pensou|acreditou|sentiu|soube|compreendeu|esperou|temeu)\s+(?:que|se)\b",
    ),
    "nl": (
        r"\b(?:zei|verklaarde|beweerde|antwoordde|legde\s+uit|voegde\s+toe|vroeg|"
        r"dacht|geloofde|voelde|wist|begreep|hoopte|vreesde)\s+(?:dat|of)\b",
    ),
}

_INDIRECT_SPEECH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    lang: tuple(re.compile(pat, re.IGNORECASE | re.UNICODE) for pat in pats)
    for lang, pats in _INDIRECT_SPEECH_REGEXES.items()
}


def indirect_speech_available(language_key: str) -> bool:
    """Return True when indirect speech / thought heuristics exist for the language."""
    return language_key in _INDIRECT_SPEECH_PATTERNS


def find_indirect_speech_spans(
    clean: str,
    quoted_spans: Sequence[tuple[int, int]],
    language_key: str,
) -> list[tuple[int, int]]:
    """Return sorted non-overlapping spans of indirect speech or thought outside quotes."""
    patterns = _INDIRECT_SPEECH_PATTERNS.get(language_key)
    if not patterns or not clean:
        return []
    candidates: list[tuple[int, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(clean):
            start, end = match.span()
            if end > start and not _overlaps_any(start, end, quoted_spans):
                candidates.append((start, end))
    candidates.sort()
    deduped: list[tuple[int, int]] = []
    for start, end in candidates:
        if deduped and start < deduped[-1][1]:
            continue
        deduped.append((start, end))
    return deduped


@dataclass(frozen=True)
class VoiceSeparation:
    """Comparison of spoken dialogue vs. narrative prose."""

    available: bool
    dialogue_words: int
    narrative_words: int
    dialogue_asl: float
    narrative_asl: float
    asl_delta: float | None
    dialogue_question_excl_pct: float
    narrative_question_excl_pct: float
    cosine_similarity: float | None
    separation_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "dialogue_words": self.dialogue_words,
            "narrative_words": self.narrative_words,
            "dialogue_asl": round(self.dialogue_asl, 2),
            "narrative_asl": round(self.narrative_asl, 2),
            "asl_delta": round(self.asl_delta, 2) if self.asl_delta is not None else None,
            "dialogue_question_excl_pct": round(self.dialogue_question_excl_pct, 2),
            "narrative_question_excl_pct": round(self.narrative_question_excl_pct, 2),
            "cosine_similarity": (
                round(self.cosine_similarity, 4) if self.cosine_similarity is not None else None
            ),
            "separation_label": self.separation_label,
        }


def _empty_voice_separation() -> VoiceSeparation:
    return VoiceSeparation(
        available=False,
        dialogue_words=0,
        narrative_words=0,
        dialogue_asl=0.0,
        narrative_asl=0.0,
        asl_delta=None,
        dialogue_question_excl_pct=0.0,
        narrative_question_excl_pct=0.0,
        cosine_similarity=None,
        separation_label="unavailable",
    )


@dataclass(frozen=True)
class DialogueChapter:
    """Turn structure of one chapter."""

    chapter_num: int
    title: str
    turns: int
    turn_words: int
    dialogue_words: int
    words: int
    dialogue_pct: float
    avg_turn_words: float
    longest_turn_words: int
    dialogue_paragraphs: int
    paragraphs: int
    short_turns: int = 0
    short_turn_pct: float = 0.0
    long_turns: int = 0
    dialogue_asl: float = 0.0
    narration_asl: float = 0.0
    asl_contrast: float | None = None
    dialogue_tags: int = 0
    dialogue_tag_pct: float = 0.0
    dialogue_tags_per_1000: float = 0.0
    dialogue_tag_available: bool = True
    adverbial_tags: int = 0
    adverbial_tag_pct: float = 0.0
    adverbial_tag_available: bool = True
    indirect_speech: int = 0
    indirect_speech_per_1000: float = 0.0
    indirect_speech_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "turns": self.turns,
            "turn_words": self.turn_words,
            "dialogue_words": self.dialogue_words,
            "words": self.words,
            "dialogue_pct": round(self.dialogue_pct, 2),
            "avg_turn_words": round(self.avg_turn_words, 2),
            "longest_turn_words": self.longest_turn_words,
            "dialogue_paragraphs": self.dialogue_paragraphs,
            "paragraphs": self.paragraphs,
            "short_turns": self.short_turns,
            "short_turn_pct": round(self.short_turn_pct, 2),
            "long_turns": self.long_turns,
            "dialogue_asl": round(self.dialogue_asl, 2),
            "narration_asl": round(self.narration_asl, 2),
            "asl_contrast": (
                round(self.asl_contrast, 2) if self.asl_contrast is not None else None
            ),
            "dialogue_tags": self.dialogue_tags,
            "dialogue_tag_pct": round(self.dialogue_tag_pct, 2),
            "dialogue_tags_per_1000": round(self.dialogue_tags_per_1000, 2),
            "dialogue_tag_available": self.dialogue_tag_available,
            "adverbial_tags": self.adverbial_tags,
            "adverbial_tag_pct": round(self.adverbial_tag_pct, 2),
            "adverbial_tag_available": self.adverbial_tag_available,
            "indirect_speech": self.indirect_speech,
            "indirect_speech_per_1000": round(self.indirect_speech_per_1000, 2),
            "indirect_speech_available": self.indirect_speech_available,
        }


@dataclass(frozen=True)
class DialogueReport:
    """Corpus-level dialogue structure with per-chapter detail."""

    language: str
    turns: int
    turn_words: int
    dialogue_words: int
    words: int
    dialogue_pct: float
    avg_turn_words: float
    median_turn_words: float
    longest_turn_words: int
    turns_per_1000: float
    dialogue_paragraph_pct: float
    chapters: list[DialogueChapter] = field(default_factory=list)
    short_turns: int = 0
    short_turn_pct: float = 0.0
    long_turns: int = 0
    dialogue_asl: float = 0.0
    narration_asl: float = 0.0
    asl_contrast: float | None = None
    dialogue_tags: int = 0
    dialogue_tag_pct: float = 0.0
    dialogue_tags_per_1000: float = 0.0
    dialogue_tag_available: bool = True
    adverbial_tags: int = 0
    adverbial_tag_pct: float = 0.0
    adverbial_tag_available: bool = True
    indirect_speech: int = 0
    indirect_speech_per_1000: float = 0.0
    indirect_speech_available: bool = True
    voice_separation: VoiceSeparation = field(default_factory=_empty_voice_separation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "turns": self.turns,
            "turn_words": self.turn_words,
            "dialogue_words": self.dialogue_words,
            "words": self.words,
            "dialogue_pct": round(self.dialogue_pct, 2),
            "avg_turn_words": round(self.avg_turn_words, 2),
            "median_turn_words": round(self.median_turn_words, 2),
            "longest_turn_words": self.longest_turn_words,
            "turns_per_1000": round(self.turns_per_1000, 2),
            "dialogue_paragraph_pct": round(self.dialogue_paragraph_pct, 2),
            "short_turns": self.short_turns,
            "short_turn_pct": round(self.short_turn_pct, 2),
            "long_turns": self.long_turns,
            "dialogue_asl": round(self.dialogue_asl, 2),
            "narration_asl": round(self.narration_asl, 2),
            "asl_contrast": (
                round(self.asl_contrast, 2) if self.asl_contrast is not None else None
            ),
            "dialogue_tags": self.dialogue_tags,
            "dialogue_tag_pct": round(self.dialogue_tag_pct, 2),
            "dialogue_tags_per_1000": round(self.dialogue_tags_per_1000, 2),
            "dialogue_tag_available": self.dialogue_tag_available,
            "adverbial_tags": self.adverbial_tags,
            "adverbial_tag_pct": round(self.adverbial_tag_pct, 2),
            "adverbial_tag_available": self.adverbial_tag_available,
            "indirect_speech": self.indirect_speech,
            "indirect_speech_per_1000": round(self.indirect_speech_per_1000, 2),
            "indirect_speech_available": self.indirect_speech_available,
            "voice_separation": self.voice_separation.to_dict(),
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


def find_dialogue_tag_spans(
    clean: str,
    quoted_spans: Sequence[tuple[int, int]],
    tag_re: re.Pattern[str] | None,
) -> list[tuple[int, int]]:
    """Return sorted unique spans of speech-attribution verbs adjacent to quoted spans."""
    if tag_re is None or not quoted_spans:
        return []
    seen_spans: set[tuple[int, int]] = set()
    for start, end in quoted_spans:
        para_start = clean.rfind("\n\n", 0, start)
        para_start = 0 if para_start < 0 else para_start + 2
        para_end = clean.find("\n\n", end)
        if para_end < 0:
            para_end = len(clean)
        after_start = end
        after_end = min(para_end, end + 60)
        matched = False
        if after_start < after_end:
            match = tag_re.search(clean, after_start, after_end)
            if match is not None:
                seen_spans.add(match.span())
                matched = True
        if not matched:
            before_start = max(para_start, start - 50)
            if before_start < start:
                match = tag_re.search(clean, before_start, start)
                if match is not None:
                    seen_spans.add(match.span())
    return sorted(seen_spans)


def _count_dialogue_tags(
    clean: str,
    quoted_spans: Sequence[tuple[int, int]],
    tag_re: re.Pattern[str] | None,
) -> int:
    """Count unique speech-attribution verb hits adjacent to quoted spans."""
    return len(find_dialogue_tag_spans(clean, quoted_spans, tag_re))


def _overlaps_any(start: int, end: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(start < q_end and end > q_start for q_start, q_end in spans)


def _count_adverbial_tags(
    clean: str,
    tag_spans: Sequence[tuple[int, int]],
    quoted_spans: Sequence[tuple[int, int]],
    language_key: str,
) -> int:
    """Count speech-attribution tags accompanied by a manner adverb outside quotes."""
    adverb_re = _MANNER_ADVERB_PATTERNS.get(language_key)
    if adverb_re is None or not tag_spans:
        return 0
    exclusions = _NON_MANNER_ADVERBS.get(language_key, frozenset())
    count = 0
    for tag_start, tag_end in tag_spans:
        para_start = clean.rfind("\n\n", 0, tag_start)
        para_start = 0 if para_start < 0 else para_start + 2
        para_end = clean.find("\n\n", tag_end)
        if para_end < 0:
            para_end = len(clean)
        win_start = max(para_start, tag_start - 35)
        win_end = min(para_end, tag_end + 35)
        # Clamp window so it does not cross quoted spans or sentence terminators.
        for q_start, q_end in quoted_spans:
            if q_end <= tag_start and q_end > win_start:
                win_start = q_end
            if q_start >= tag_end and q_start < win_end:
                win_end = q_start
        for sep in (".", "!", "?"):
            pos = clean.rfind(sep, win_start, tag_start)
            if pos >= 0 and pos + 1 > win_start:
                win_start = pos + 1
            pos = clean.find(sep, tag_end, win_end)
            if pos >= 0 and pos < win_end:
                win_end = pos
        for match in adverb_re.finditer(clean, win_start, win_end):
            if match.group(0).lower() in exclusions:
                continue
            if _overlaps_any(match.start(), match.end(), quoted_spans):
                continue
            count += 1
            break
    return count


def _is_question_or_excl(sentence: str) -> bool:
    stripped = sentence.strip().rstrip("\"'»«„“”\u201a\u2018\u2019)]")
    return stripped.endswith(("?", "!"))


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float | None:
    if not left or not right:
        return None
    norm_left = math.sqrt(sum(v * v for v in left.values()))
    norm_right = math.sqrt(sum(v * v for v in right.values()))
    if norm_left == 0.0 or norm_right == 0.0:
        return None
    dot = sum(v * right[k] for k, v in left.items() if k in right)
    return dot / (norm_left * norm_right)


@dataclass(frozen=True)
class _ChapterTurnStats:
    turn_word_counts: list[int]
    dialogue_words: int
    words: int
    dialogue_paragraphs: int
    paragraphs: int
    dialogue_sentences: int
    narration_words: int
    narration_sentences: int
    dialogue_tags: int
    adverbial_tags: int
    indirect_speech: int
    dialogue_q_excl: int
    narration_q_excl: int
    dialogue_tokens: Counter[str]
    narration_tokens: Counter[str]


def _turn_stats(
    body: str,
    dialogue_re: re.Pattern[str],
    word_re: re.Pattern[str],
    language_key: str = "en",
    *,
    dialogue_paragraph_share: float = DIALOGUE_PARAGRAPH_SHARE,
) -> _ChapterTurnStats:
    paragraphs = prose_paragraphs(body, _front_matter=False)
    clean = "\n\n".join(paragraphs)
    matches = list(quotation_texts(dialogue_re, clean))
    turn_word_counts: list[int] = []
    dialogue_tokens: Counter[str] = Counter()
    dialogue_sentences = 0
    dialogue_q_excl = 0
    for match_text in matches:
        tokens = [str(t).lower() for t in word_re.findall(match_text)]
        count = len(tokens)
        turn_word_counts.append(count)
        if count > 0:
            dialogue_tokens.update(tokens)
            sents = [
                s
                for s in split_prose_sentences(match_text, language_key)
                if word_re.search(s)
            ]
            if sents:
                dialogue_sentences += len(sents)
                dialogue_q_excl += sum(1 for s in sents if _is_question_or_excl(s))
            else:
                dialogue_sentences += 1
                if _is_question_or_excl(match_text):
                    dialogue_q_excl += 1
    dialogue_words = sum(turn_word_counts)
    words = len(word_re.findall(clean))

    # A recognized quoted span may continue across paragraph boundaries.
    # Reuse the same chapter-wide matches for paragraph shares instead of
    # requiring both quote delimiters to occur inside each paragraph.
    capture = quotation_capture_group(dialogue_re)
    spans = sorted(match.span(capture) for match in dialogue_re.finditer(clean)
                   if match.start(capture) >= 0 and match.end(capture) > match.start(capture))
    quoted_spans: list[tuple[int, int]] = []
    for start, end in spans:
        if quoted_spans and start <= quoted_spans[-1][1]:
            quoted_spans[-1] = (quoted_spans[-1][0], max(end, quoted_spans[-1][1]))
        else:
            quoted_spans.append((start, end))

    narration_parts: list[str] = []
    cursor = 0
    for start, end in quoted_spans:
        narration_parts.append(clean[cursor:start])
        cursor = end
    narration_parts.append(clean[cursor:])
    narration_text = " ".join(narration_parts)
    narration_token_list = [str(t).lower() for t in word_re.findall(narration_text)]
    narration_words = len(narration_token_list)
    narration_tokens: Counter[str] = Counter(narration_token_list)
    nar_sents = [
        s
        for s in split_prose_sentences(narration_text, language_key)
        if word_re.search(s)
    ]
    narration_sentences = max(1, len(nar_sents)) if narration_words > 0 else 0
    narration_q_excl = sum(1 for s in nar_sents if _is_question_or_excl(s)) if nar_sents else 0

    dialogue_paragraphs = 0
    paragraph_start = 0
    first_span = 0
    for paragraph in paragraphs:
        paragraph_end = paragraph_start + len(paragraph)
        while first_span < len(quoted_spans) and quoted_spans[first_span][1] <= paragraph_start:
            first_span += 1
        paragraph_words = len(word_re.findall(paragraph))
        if paragraph_words:
            quoted = 0
            index = first_span
            while index < len(quoted_spans) and quoted_spans[index][0] < paragraph_end:
                start, end = quoted_spans[index]
                fragment = paragraph[max(0, start - paragraph_start):min(len(paragraph), end - paragraph_start)]
                quoted += len(word_re.findall(fragment))
                index += 1
            if quoted / paragraph_words >= dialogue_paragraph_share:
                dialogue_paragraphs += 1
        paragraph_start = paragraph_end + 2  # separator inserted in clean

    tag_spans = find_dialogue_tag_spans(
        clean, quoted_spans, _DIALOGUE_TAG_PATTERNS.get(language_key)
    )
    dialogue_tags = len(tag_spans)
    adverbial_tags = _count_adverbial_tags(clean, tag_spans, quoted_spans, language_key)
    indirect_speech = len(find_indirect_speech_spans(clean, quoted_spans, language_key))

    return _ChapterTurnStats(
        turn_word_counts=turn_word_counts,
        dialogue_words=dialogue_words,
        words=words,
        dialogue_paragraphs=dialogue_paragraphs,
        paragraphs=len(paragraphs),
        dialogue_sentences=dialogue_sentences,
        narration_words=narration_words,
        narration_sentences=narration_sentences,
        dialogue_tags=dialogue_tags,
        adverbial_tags=adverbial_tags,
        indirect_speech=indirect_speech,
        dialogue_q_excl=dialogue_q_excl,
        narration_q_excl=narration_q_excl,
        dialogue_tokens=dialogue_tokens,
        narration_tokens=narration_tokens,
    )


def dialogue_report(text: str, config: CorpusConfig | None = None) -> DialogueReport:
    """Dialogue turn structure of a manuscript (deterministic, heuristic)."""
    config = config or CorpusConfig()
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)

    chapters: list[DialogueChapter] = []
    all_turn_lengths: list[int] = []
    all_dialogue_words = 0
    all_words = 0
    all_paragraphs = 0
    all_dialogue_paragraphs = 0
    all_dialogue_sentences = 0
    all_narration_words = 0
    all_narration_sentences = 0
    all_dialogue_tags = 0
    all_adverbial_tags = 0
    all_indirect_speech = 0
    all_dialogue_q_excl = 0
    all_narration_q_excl = 0
    all_dialogue_tokens: Counter[str] = Counter()
    all_narration_tokens: Counter[str] = Counter()
    tag_available = resolved.key in _DIALOGUE_TAG_PATTERNS
    adverbial_tag_available = tag_available and (resolved.key in _MANNER_ADVERB_PATTERNS)
    ind_speech_available = indirect_speech_available(resolved.key)

    for number, title, body in split_chapters(text, config):
        stats = _turn_stats(
            body,
            dialogue_re,
            word_re,
            resolved.key,
            dialogue_paragraph_share=config.dialogue_paragraph_share,
        )
        if not stats.words:
            continue
        turns = len(stats.turn_word_counts)
        short_turns = sum(1 for w in stats.turn_word_counts if 1 <= w <= config.short_turn_max_words)
        long_turns = sum(1 for w in stats.turn_word_counts if w >= config.long_turn_min_words)
        dialogue_asl = (stats.dialogue_words / stats.dialogue_sentences) if stats.dialogue_sentences else 0.0
        narration_asl = (stats.narration_words / stats.narration_sentences) if stats.narration_sentences else 0.0
        asl_contrast = (
            (dialogue_asl - narration_asl)
            if (stats.dialogue_sentences > 0 and stats.narration_sentences > 0)
            else None
        )
        chapters.append(
            DialogueChapter(
                chapter_num=number,
                title=title,
                turns=turns,
                turn_words=stats.dialogue_words,
                dialogue_words=stats.dialogue_words,
                words=stats.words,
                dialogue_pct=(stats.dialogue_words / stats.words * 100.0) if stats.words else 0.0,
                avg_turn_words=(stats.dialogue_words / turns) if turns else 0.0,
                longest_turn_words=max(stats.turn_word_counts, default=0),
                dialogue_paragraphs=stats.dialogue_paragraphs,
                paragraphs=stats.paragraphs,
                short_turns=short_turns,
                short_turn_pct=(short_turns / turns * 100.0) if turns else 0.0,
                long_turns=long_turns,
                dialogue_asl=dialogue_asl,
                narration_asl=narration_asl,
                asl_contrast=asl_contrast,
                dialogue_tags=stats.dialogue_tags,
                dialogue_tag_pct=(min(100.0, stats.dialogue_tags / turns * 100.0) if (turns and tag_available) else 0.0),
                dialogue_tags_per_1000=((stats.dialogue_tags / stats.words * 1000.0) if (stats.words and tag_available) else 0.0),
                dialogue_tag_available=tag_available,
                adverbial_tags=stats.adverbial_tags,
                adverbial_tag_pct=(
                    min(100.0, stats.adverbial_tags / stats.dialogue_tags * 100.0)
                    if (stats.dialogue_tags and adverbial_tag_available)
                    else 0.0
                ),
                adverbial_tag_available=adverbial_tag_available,
                indirect_speech=stats.indirect_speech,
                indirect_speech_per_1000=(
                    (stats.indirect_speech / stats.words * 1000.0)
                    if (stats.words and ind_speech_available)
                    else 0.0
                ),
                indirect_speech_available=ind_speech_available,
            )
        )
        all_turn_lengths.extend(stats.turn_word_counts)
        all_dialogue_words += stats.dialogue_words
        all_words += stats.words
        all_paragraphs += stats.paragraphs
        all_dialogue_paragraphs += stats.dialogue_paragraphs
        all_dialogue_sentences += stats.dialogue_sentences
        all_narration_words += stats.narration_words
        all_narration_sentences += stats.narration_sentences
        all_dialogue_tags += stats.dialogue_tags
        all_adverbial_tags += stats.adverbial_tags
        all_indirect_speech += stats.indirect_speech
        all_dialogue_q_excl += stats.dialogue_q_excl
        all_narration_q_excl += stats.narration_q_excl
        all_dialogue_tokens.update(stats.dialogue_tokens)
        all_narration_tokens.update(stats.narration_tokens)

    turns = len(all_turn_lengths)
    short_turns = sum(1 for w in all_turn_lengths if 1 <= w <= config.short_turn_max_words)
    long_turns = sum(1 for w in all_turn_lengths if w >= config.long_turn_min_words)
    corpus_dialogue_asl = (
        (all_dialogue_words / all_dialogue_sentences) if all_dialogue_sentences else 0.0
    )
    corpus_narration_asl = (
        (all_narration_words / all_narration_sentences) if all_narration_sentences else 0.0
    )
    corpus_asl_contrast = (
        (corpus_dialogue_asl - corpus_narration_asl)
        if (all_dialogue_sentences > 0 and all_narration_sentences > 0)
        else None
    )

    vs_available = all_dialogue_words > 0 and all_narration_words > 0
    cosine_sim = _cosine_similarity(all_dialogue_tokens, all_narration_tokens) if vs_available else None
    if not vs_available or cosine_sim is None:
        sep_label = "unavailable"
    elif cosine_sim < 0.45 or (corpus_asl_contrast is not None and abs(corpus_asl_contrast) >= 6.0 and cosine_sim < 0.65):
        sep_label = "distinct"
    elif cosine_sim < 0.72:
        sep_label = "moderate"
    else:
        sep_label = "blended"

    voice_separation = VoiceSeparation(
        available=vs_available,
        dialogue_words=all_dialogue_words,
        narrative_words=all_narration_words,
        dialogue_asl=corpus_dialogue_asl,
        narrative_asl=corpus_narration_asl,
        asl_delta=corpus_asl_contrast if vs_available else None,
        dialogue_question_excl_pct=(
            (all_dialogue_q_excl / all_dialogue_sentences * 100.0)
            if all_dialogue_sentences
            else 0.0
        ),
        narrative_question_excl_pct=(
            (all_narration_q_excl / all_narration_sentences * 100.0)
            if all_narration_sentences
            else 0.0
        ),
        cosine_similarity=cosine_sim,
        separation_label=sep_label,
    )

    return DialogueReport(
        language=resolved.key,
        turns=turns,
        turn_words=all_dialogue_words,
        dialogue_words=all_dialogue_words,
        words=all_words,
        dialogue_pct=(all_dialogue_words / all_words * 100.0) if all_words else 0.0,
        avg_turn_words=(all_dialogue_words / turns) if turns else 0.0,
        median_turn_words=median(all_turn_lengths) if all_turn_lengths else 0.0,
        longest_turn_words=max(all_turn_lengths, default=0),
        turns_per_1000=(turns / all_words * 1000.0) if all_words else 0.0,
        dialogue_paragraph_pct=(
            all_dialogue_paragraphs / all_paragraphs * 100.0 if all_paragraphs else 0.0
        ),
        chapters=chapters,
        short_turns=short_turns,
        short_turn_pct=(short_turns / turns * 100.0) if turns else 0.0,
        long_turns=long_turns,
        dialogue_asl=corpus_dialogue_asl,
        narration_asl=corpus_narration_asl,
        asl_contrast=corpus_asl_contrast,
        dialogue_tags=all_dialogue_tags,
        dialogue_tag_pct=(min(100.0, all_dialogue_tags / turns * 100.0) if (turns and tag_available) else 0.0),
        dialogue_tags_per_1000=((all_dialogue_tags / all_words * 1000.0) if (all_words and tag_available) else 0.0),
        dialogue_tag_available=tag_available,
        adverbial_tags=all_adverbial_tags,
        adverbial_tag_pct=(
            min(100.0, all_adverbial_tags / all_dialogue_tags * 100.0)
            if (all_dialogue_tags and adverbial_tag_available)
            else 0.0
        ),
        adverbial_tag_available=adverbial_tag_available,
        indirect_speech=all_indirect_speech,
        indirect_speech_per_1000=(
            (all_indirect_speech / all_words * 1000.0)
            if (all_words and ind_speech_available)
            else 0.0
        ),
        indirect_speech_available=ind_speech_available,
        voice_separation=voice_separation,
    )


def _compile_character_patterns(
    names: Mapping[str, str] | Sequence[str],
) -> dict[str, list[re.Pattern[str]]]:
    patterns: dict[str, list[re.Pattern[str]]] = {}
    entries = names.items() if isinstance(names, Mapping) else ((name, name) for name in names)
    for pattern, label in entries:
        compiled = re.compile(rf"(?<!\w)(?:{pattern})(?!\w)", re.IGNORECASE | re.UNICODE)
        patterns.setdefault(label, []).append(compiled)
    return patterns


def _attribute_turn_speaker(
    clean: str,
    span: tuple[int, int],
    prev_end: int,
    next_start: int,
    patterns: Mapping[str, Sequence[re.Pattern[str]]],
) -> str | None:
    """Return the unique configured character in the adjacent attribution window, if any."""
    start, end = span
    para_start = clean.rfind("\n\n", 0, start)
    para_start = 0 if para_start < 0 else para_start + 2
    para_end = clean.find("\n\n", end)
    if para_end < 0:
        para_end = len(clean)

    post_lo = end
    post_hi = min(para_end, next_start, end + 60)
    if post_lo < post_hi:
        post_win = clean[post_lo:post_hi]
        post_hits = [
            label
            for label, pats in patterns.items()
            if any(pat.search(post_win) for pat in pats)
        ]
        if len(post_hits) == 1:
            return post_hits[0]
        if len(post_hits) > 1:
            return None

    pre_lo = max(para_start, prev_end, start - 60)
    pre_hi = start
    if pre_lo < pre_hi:
        pre_win = clean[pre_lo:pre_hi]
        pre_hits = [
            label
            for label, pats in patterns.items()
            if any(pat.search(pre_win) for pat in pats)
        ]
        if len(pre_hits) == 1:
            return pre_hits[0]
    return None


def character_voice_profiles(
    text: str,
    names: Mapping[str, str] | Sequence[str],
    config: CorpusConfig | None = None,
    *,
    min_turns: int = MIN_CHARACTER_VOICE_TURNS,
) -> dict[str, Any]:
    """Per-character dialogue voice profiles compared against the narrator baseline.

    Inspired by Michel et al. (EMNLP 2024) and Chiron: deterministic adjacent-window
    speaker attribution with an explicit ambiguity guard and honest ``insufficient_turns``
    reporting below ``min_turns``.
    """
    config = config or CorpusConfig()
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)
    capture = quotation_capture_group(dialogue_re)
    patterns = _compile_character_patterns(names)
    func_words = resolved.function_words

    accum: dict[str, dict[str, int]] = {
        label: {"turns": 0, "words": 0, "sentences": 0, "q_excl": 0, "func_words": 0}
        for label in patterns
    }
    narrator_words = 0
    narrator_sentences = 0
    narrator_q_excl = 0
    narrator_func_words = 0

    for _number, _title, body in split_chapters(text, config):
        paragraphs = prose_paragraphs(body, _front_matter=False)
        clean = "\n\n".join(paragraphs)
        if not clean:
            continue
        raw_spans = sorted(
            match.span(capture)
            for match in dialogue_re.finditer(clean)
            if match.start(capture) >= 0 and match.end(capture) > match.start(capture)
        )
        quoted_spans: list[tuple[int, int]] = []
        for s_pos, e_pos in raw_spans:
            if quoted_spans and s_pos <= quoted_spans[-1][1]:
                quoted_spans[-1] = (quoted_spans[-1][0], max(e_pos, quoted_spans[-1][1]))
            else:
                quoted_spans.append((s_pos, e_pos))

        nar_parts: list[str] = []
        cursor = 0
        for s_pos, e_pos in quoted_spans:
            nar_parts.append(clean[cursor:s_pos])
            cursor = e_pos
        nar_parts.append(clean[cursor:])
        nar_text = " ".join(nar_parts)
        nar_tokens = [str(t).lower() for t in word_re.findall(nar_text)]
        if nar_tokens:
            narrator_words += len(nar_tokens)
            if func_words:
                narrator_func_words += sum(1 for tok in nar_tokens if tok in func_words)
            nar_sents = [
                s for s in split_prose_sentences(nar_text, resolved.key) if word_re.search(s)
            ]
            narrator_sentences += max(1, len(nar_sents))
            narrator_q_excl += sum(1 for s in nar_sents if _is_question_or_excl(s))

        for idx, span in enumerate(quoted_spans):
            prev_end = quoted_spans[idx - 1][1] if idx > 0 else 0
            next_start = quoted_spans[idx + 1][0] if idx + 1 < len(quoted_spans) else len(clean)
            speaker = _attribute_turn_speaker(clean, span, prev_end, next_start, patterns)
            if speaker is None:
                continue
            turn_text = clean[span[0]:span[1]]
            tokens = [str(t).lower() for t in word_re.findall(turn_text)]
            if not tokens:
                continue
            sents = [
                s for s in split_prose_sentences(turn_text, resolved.key) if word_re.search(s)
            ]
            n_sents = max(1, len(sents))
            n_q_excl = (
                sum(1 for s in sents if _is_question_or_excl(s))
                if sents
                else (1 if _is_question_or_excl(turn_text) else 0)
            )
            bucket = accum[speaker]
            bucket["turns"] += 1
            bucket["words"] += len(tokens)
            bucket["sentences"] += n_sents
            bucket["q_excl"] += n_q_excl
            if func_words:
                bucket["func_words"] += sum(1 for tok in tokens if tok in func_words)

    nar_asl = (narrator_words / narrator_sentences) if narrator_sentences else None
    nar_q_rate = (
        (narrator_q_excl / narrator_sentences * 100.0) if narrator_sentences else None
    )
    nar_func_share = (
        (narrator_func_words / narrator_words * 100.0)
        if (func_words and narrator_words)
        else None
    )

    characters: list[dict[str, Any]] = []
    for label, stats in accum.items():
        turns = stats["turns"]
        words = stats["words"]
        sentences = stats["sentences"]
        if turns < min_turns or words == 0 or sentences == 0:
            characters.append({
                "name": label,
                "status": "insufficient_turns",
                "turns": turns,
                "min_turns": min_turns,
                "words": words,
                "dialogue_asl": None,
                "question_excl_rate": None,
                "function_word_share": None,
                "narrator_asl_delta": None,
                "narrator_question_excl_delta": None,
                "narrator_function_word_delta": None,
            })
            continue
        char_asl = words / sentences
        char_q_rate = stats["q_excl"] / sentences * 100.0
        char_func_share = (stats["func_words"] / words * 100.0) if func_words else None
        characters.append({
            "name": label,
            "status": "available",
            "turns": turns,
            "min_turns": min_turns,
            "words": words,
            "dialogue_asl": round(char_asl, 2),
            "question_excl_rate": round(char_q_rate, 2),
            "function_word_share": (
                round(char_func_share, 2) if char_func_share is not None else None
            ),
            "narrator_asl_delta": (
                round(char_asl - nar_asl, 2) if nar_asl is not None else None
            ),
            "narrator_question_excl_delta": (
                round(char_q_rate - nar_q_rate, 2) if nar_q_rate is not None else None
            ),
            "narrator_function_word_delta": (
                round(char_func_share - nar_func_share, 2)
                if (char_func_share is not None and nar_func_share is not None)
                else None
            ),
        })
    characters.sort(key=lambda item: (-item["turns"], item["name"]))
    return {
        "min_turns": min_turns,
        "narrator": {
            "words": narrator_words,
            "asl": round(nar_asl, 2) if nar_asl is not None else None,
            "question_excl_rate": round(nar_q_rate, 2) if nar_q_rate is not None else None,
            "function_word_share": (
                round(nar_func_share, 2) if nar_func_share is not None else None
            ),
        },
        "characters": characters,
    }
