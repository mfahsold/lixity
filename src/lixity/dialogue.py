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
from collections.abc import Sequence
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
    all_dialogue_q_excl = 0
    all_narration_q_excl = 0
    all_dialogue_tokens: Counter[str] = Counter()
    all_narration_tokens: Counter[str] = Counter()
    tag_available = resolved.key in _DIALOGUE_TAG_PATTERNS
    adverbial_tag_available = tag_available and (resolved.key in _MANNER_ADVERB_PATTERNS)

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
        voice_separation=voice_separation,
    )
