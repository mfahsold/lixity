"""Offline language-specific verb complexes over contextual syntax annotations.

Composition follows the separation of morphology and verbal periphrases in IDS
Grammis and Dönicke (2020, https://aclanthology.org/2020.tlt-1.1/). This is an
independent implementation, not that paper's evaluated system. Parser errors,
ambiguous sein-participles and unrecognized quotation formats remain explicit.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import asdict
from threading import RLock
from typing import Any

from .linguistic_models import SyntaxToken, parse_tokens, parser_language, validate_tokens
from .linguistic_models import model_identity as _parser_identity
from .verb_grammar import SUPPORTED_LANGUAGES, VerbGroup, classify_german, classify_other, is_finite

POLICY = "multilingual-verb-groups/1"
_LOCK = RLock()
_CACHE: OrderedDict[tuple[str, str], tuple[VerbGroup, ...]] = OrderedDict()
_MAX_CACHE_CHARS = 1_000_000
_MAX_TEXT_CHARS = 250_000


def compose_verbs(text: str, tokens: tuple[SyntaxToken, ...], language: str) -> tuple[VerbGroup, ...]:
    """Compose parser-linked auxiliaries; never join verbs by word distance."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported grammatical tense language: {language}")
    validate_tokens(text, tokens)
    indexed = {t.i: t for t in tokens}
    verbs = {t.i: t for t in tokens if t.pos in ("VERB", "AUX")}
    parents = {i: i for i in verbs}
    nonverbal_heads: dict[int, int] = {}
    reflexive_heads = {t.head for t in tokens if t.pos == "PRON" and t.lemma in ("se", "si", "soi")}

    def root(i: int) -> int:
        while parents[i] != i:
            i = parents[i]
        return i

    for token in verbs.values():
        parent = verbs.get(token.head)
        if parent is None:
            if token.dep.split(":", 1)[0] in ("aux", "auxpass", "cop"):
                peer = nonverbal_heads.setdefault(token.head, token.i)
                parents[root(token.i)] = root(peer)
            continue
        if parent.i == token.i:
            continue
        if (token.dep.split(":", 1)[0] in ("aux", "auxpass", "cop")
                or (language == "es" and parent.pos == "AUX" and parent.lemma == "haber"
                    and token.form == "Part" and token.dep == "obj")
                or (token.dep in ("oc", "pd") and parent.pos == "AUX")):
            parents[root(token.i)] = root(parent.i)
    groups: dict[int, list[SyntaxToken]] = {}
    for token in verbs.values():
        groups.setdefault(root(token.i), []).append(token)

    def coordination_anchor(members: list[SyntaxToken]) -> SyntaxToken | None:
        indices = {token.i for token in members}
        return min((token for token in members if token.dep in ("conj", "cj")
                    and token.head not in indices), key=lambda token: token.start, default=None)

    result: list[VerbGroup] = []
    for members in groups.values():
        effective = members
        # Coordinated participles can share an auxiliary, but finite conjuncts
        # own their own tense. TIGER uses a conjunction node between conjuncts.
        if not any(is_finite(t) for t in members):
            first = coordination_anchor(members)
            # Nested coordination A,(B,C) links C to B, whose own component
            # need not contain the shared auxiliary. Follow only coordination
            # links and stop at any finite component, including lexical ones.
            visited: set[int] = set()
            while first is not None and first.i not in visited:
                visited.add(first.i)
                governor = indexed.get(first.head)
                if first.dep == "cj" and governor and governor.pos == "CCONJ":
                    governor = indexed.get(governor.head)
                if governor is None or governor.i not in verbs:
                    break
                inherited_group = groups[root(governor.i)]
                if any(is_finite(t) for t in inherited_group):
                    effective = [*members, *(t for t in inherited_group if t.pos == "AUX")]
                    break
                first = coordination_anchor(inherited_group)
        indices = {t.i for t in effective}
        reflexive = bool(indices & reflexive_heads)
        result.append(classify_german(effective) if language == "de" else classify_other(effective, language, reflexive=reflexive))
    return tuple(sorted(result, key=lambda g: g.span))


def compose_german(text: str, tokens: tuple[SyntaxToken, ...]) -> tuple[VerbGroup, ...]:
    """German specialization of the shared dependency-component traversal."""
    return compose_verbs(text, tokens, "de")


def model_identity(name: str) -> dict[str, str]:
    return {"policy": POLICY, **_parser_identity(name)}


def analyze_verbs(text: str, model: str) -> tuple[VerbGroup, ...]:
    """Bounded private in-memory reuse of exact input, shared by all adapters."""
    if len(text) > _MAX_TEXT_CHARS:
        raise ValueError("Grammatical tense input exceeds 250000 characters; split the chapter explicitly")
    key = model, text
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
        language = parser_language(model)
        try:
            result = compose_verbs(text, parse_tokens(text, model), language)
        except Exception as exc:
            raise ValueError(f"Grammatical tense analysis failed for {model!r}; no pattern fallback was used") from exc
        while _CACHE and (sum(len(k[1]) for k in _CACHE) + len(text) > _MAX_CACHE_CHARS or len(_CACHE) >= 256):
            _CACHE.popitem(last=False)
        _CACHE[key] = result
        return result


def _quotation_spans(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int]]:
    """Match the existing dialogue counter's single-capture convention."""
    group = 1 if pattern.groups == 1 else 0
    return [match.span(group) for match in pattern.finditer(text) if match.start(group) >= 0]


def grammatical_observation(text: str, model: str, scope: str, quotation_regex: re.Pattern[str], *,
                            quotation_spans: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    """Keep all verb groups, scope exclusions and unresolved analyses inspectable."""
    quotes = quotation_spans if quotation_spans is not None else _quotation_spans(text, quotation_regex)
    groups = []
    for group in analyze_verbs(text, model):
        quoted = [any(start <= a and b <= end for start, end in quotes) for a, b in group.components]
        context = "quotation" if all(quoted) else "narration" if not any(quoted) else "unresolved"
        selected = scope == "all" or context == "narration"
        bucket = ("present" if group.tense == "present" else "past" if group.tense in
                  ("preterite", "imperfect", "perfect", "pluperfect", "anterior_perfect") else None) if group.mood in ("indicative", "unmarked") else None
        groups.append({**asdict(group), "scope": context, "selected": selected, "bucket": bucket})
    return {"schema_version": "grammatical-tense/1", **model_identity(model), "scope": scope,
            "offset_unit": "counting_text_unicode_codepoint", "groups": groups}


def grammatical_parts(parts: Sequence[str], model: str, scope: str,
                      quotation_regex: re.Pattern[str]) -> list[dict[str, Any]]:
    """Parse paragraphs consistently, resolving quotation scope across them first."""
    quotes = _quotation_spans("\n\n".join(parts), quotation_regex)
    observations = []
    offset = 0
    for part in parts:
        local = [(max(0, start - offset), min(len(part), end - offset)) for start, end in quotes
                 if start < offset + len(part) and end > offset]
        observations.append(grammatical_observation(part, model, scope, quotation_regex, quotation_spans=local))
        offset += len(part) + 2
    return observations
