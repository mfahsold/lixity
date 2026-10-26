"""Explicit author-chosen terms and props with source-bound manuscript occurrences.

Lexical occurrences in displayed manuscript paragraphs are derived candidate
views. They never create archive revisions, establish physical presence, or
assert semantic contradictions without explicit author review.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from .pipeline import paragraph_identity
from .publication import validate_metadata_text
from .research.models import Identifier
from .style_profile import ParagraphProfile, ParagraphText

TERMS_SCOPE = (
    "Lexical occurrences in displayed manuscript paragraphs are derived candidate hits, "
    "not accepted claim associations, physical presence, or semantic contradictions."
)


def _normalize_term_text(value: str, label: str, max_length: int = 100) -> str:
    cleaned = validate_metadata_text(value, label, max_length)
    normalized = unicodedata.normalize("NFC", cleaned)
    if not normalized or normalized != cleaned.strip():
        raise ValueError(f"{label} must be nonempty and have no surrounding whitespace")
    return normalized


class ScopedTermAlternative(BaseModel):
    """An author-declared alternative term form scoped to explicit 1-based chapters."""

    model_config = ConfigDict(extra="forbid", strict=True)

    term: Annotated[str, Field(min_length=1, max_length=100)]
    chapters: list[Annotated[int, Field(strict=True, ge=1)]] = Field(
        min_length=1,
        description="Explicit 1-based chapter numbers where this alternative is intended.",
    )
    note: Annotated[str, Field(max_length=240)] | None = None

    @field_validator("term")
    @classmethod
    def _valid_term(cls, value: str) -> str:
        return _normalize_term_text(value, "Scoped alternative term", 100)

    @field_validator("chapters")
    @classmethod
    def _unique_chapters(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("Scoped alternative chapter numbers must not repeat")
        return sorted(values)

    @field_validator("note")
    @classmethod
    def _valid_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = validate_metadata_text(value, "Scoped alternative note", 240)
        return cleaned or None


class TermProfile(BaseModel):
    """Explicit author-chosen term or prop profile with aliases and chapter-scoped forms."""

    model_config = ConfigDict(extra="forbid", strict=True)

    aliases: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list,
        description="Unscoped literal aliases accepted across all chapters.",
    )
    scoped_alternatives: list[ScopedTermAlternative] = Field(
        default_factory=list,
        description="Chapter-scoped alternative forms; hits outside their chapters are flagged for review.",
    )
    case_sensitive: bool = False
    # When true, hyphens (and other intra-word connectors) are treated as part
    # of a word for boundary checks, so a short term such as "RM" no longer
    # matches inside a hyphenated code like "RM-CURIA-084". Defaults to the
    # value of case_sensitive for backwards-compatible strictness; authors can
    # override it independently in either direction.
    strict_boundaries: bool | None = None
    dossier_id: Identifier | None = None
    claim_id: Identifier | None = None

    @field_validator("aliases")
    @classmethod
    def _valid_aliases(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for raw in values:
            cleaned = _normalize_term_text(raw, "Term alias", 100)
            if cleaned in result:
                raise ValueError(f"Duplicate term alias: {cleaned!r}")
            result.append(cleaned)
        return result

    @model_validator(mode="after")
    def _disjoint_variants(self) -> TermProfile:
        seen: dict[str, str] = {}
        for alias in self.aliases:
            key = alias if self.case_sensitive else alias.casefold()
            if key in seen:
                raise ValueError(f"Term aliases collide under matching rules: {alias!r}")
            seen[key] = alias
        scoped_seen: dict[str, str] = {}
        for alt in self.scoped_alternatives:
            key = alt.term if self.case_sensitive else alt.term.casefold()
            if key in seen:
                raise ValueError(f"Scoped alternative {alt.term!r} duplicates an unscoped alias")
            if key in scoped_seen:
                raise ValueError(f"Scoped alternative {alt.term!r} is declared more than once")
            scoped_seen[key] = alt.term
        return self


_TERMS_MAP: TypeAdapter[dict[str, TermProfile]] = TypeAdapter(
    dict[Annotated[str, Field(min_length=1, max_length=100)], TermProfile]
)


def parse_terms(raw: object) -> dict[str, TermProfile]:
    """Validate and normalize project-configured terms and props."""
    if raw is None:
        return {}
    if isinstance(raw, list):
        converted: dict[str, Any] = {}
        for item in raw:
            if not isinstance(item, Mapping) or "term" not in item:
                raise ValueError("Term list entries must be objects with a 'term' key")
            key = str(item["term"])
            if key in converted:
                raise ValueError(f"Duplicate term profile: {key!r}")
            converted[key] = {k: v for k, v in item.items() if k != "term"}
        raw = converted
    if not isinstance(raw, Mapping) or len(raw) > 200:
        raise ValueError("terms must be a table of at most 200 named term/prop profiles")
    validated = _TERMS_MAP.validate_python(dict(raw))
    normalized: dict[str, TermProfile] = {}
    for label, profile in validated.items():
        clean_label = _normalize_term_text(label, "Term name", 100)
        if clean_label != label:
            raise ValueError(
                "Term names must be normalized NFC text without surrounding whitespace"
            )
        canon_key = clean_label if profile.case_sensitive else clean_label.casefold()
        for variant in [
            *profile.aliases,
            *(alt.term for alt in profile.scoped_alternatives),
        ]:
            v_key = variant if profile.case_sensitive else variant.casefold()
            if v_key == canon_key:
                raise ValueError(
                    f"Term profile {clean_label!r} repeats its canonical name in aliases or alternatives"
                )
        normalized[clean_label] = profile
    return normalized


def terms_configuration_schema() -> dict[str, Any]:
    """Export the JSON Schema for [tool.lixity.terms]."""
    schema = _TERMS_MAP.json_schema()
    schema["$comment"] = (
        "Project-only author-chosen terms and props mapped to aliases and "
        "chapter-scoped alternatives."
    )
    return schema


def _is_word_char(ch: str, *, strict: bool = False) -> bool:
    # In strict mode, hyphens count as intra-word characters so that a term
    # does not match as a prefix/suffix inside a hyphenated code such as
    # "RM-CURIA-084".
    if ch.isalnum() or ch == "_":
        return True
    return bool(strict and ch == "-")


def _boundary_class(strict: bool) -> str:
    # Character class used for negative lookbehind/lookahead. Mirrors
    # _is_word_char so regex boundaries stay consistent with the manual scan.
    if strict:
        return r"[\w-]"
    return r"\w"


def _variant_pattern(form: str, *, case_sensitive: bool, strict: bool = False) -> re.Pattern[str]:
    escaped = re.escape(form)
    prefix = rf"(?<!{_boundary_class(strict)})" if _is_word_char(form[0], strict=strict) else ""
    suffix = rf"(?!{_boundary_class(strict)})" if _is_word_char(form[-1], strict=strict) else ""
    flags = re.UNICODE | (0 if case_sensitive else re.IGNORECASE)
    return re.compile(f"{prefix}(?:{escaped}){suffix}", flags)


def _find_variant_spans(
    text: str,
    form: str,
    *,
    case_sensitive: bool,
    strict: bool = False,
) -> list[tuple[int, int, list[str]]]:
    """Find token-bounded occurrences of `form` in `text`, noting Unicode ambiguities."""
    results: list[tuple[int, int, list[str]]] = []
    pattern = _variant_pattern(form, case_sensitive=case_sensitive, strict=strict)
    seen_spans: set[tuple[int, int]] = set()
    for match in pattern.finditer(text):
        start, end = match.span()
        slice_text = text[start:end]
        reasons: list[str] = []
        if unicodedata.normalize("NFC", slice_text) != slice_text:
            reasons.append("unicode_non_nfc")
        if not case_sensitive and len(slice_text) != len(form):
            reasons.append("unicode_casefold_length")
        seen_spans.add((start, end))
        results.append((start, end, reasons))

    # Check if decomposed/compatibility Unicode sequences in `text` would match under NFC/casefold
    # when raw regex missed them or shifted codepoint lengths.
    if not unicodedata.is_normalized("NFC", text) or (
        not case_sensitive and "ß" in (text + form).lower()
    ):
        target = form if case_sensitive else form.casefold()
        n = len(text)
        for i in range(n):
            if (
                _is_word_char(form[0], strict=strict)
                and i > 0
                and _is_word_char(text[i - 1], strict=strict)
            ):
                continue
            for j in range(i + 1, min(n, i + len(form) * 2 + 4) + 1):
                if (i, j) in seen_spans:
                    continue
                if (
                    _is_word_char(form[-1], strict=strict)
                    and j < n
                    and _is_word_char(text[j], strict=strict)
                ):
                    continue
                candidate = unicodedata.normalize("NFC", text[i:j])
                comparable = candidate if case_sensitive else candidate.casefold()
                if comparable == target:
                    reasons = ["unicode_normalization"]
                    if not case_sensitive and len(text[i:j]) != len(form):
                        reasons.append("unicode_casefold_length")
                    seen_spans.add((i, j))
                    results.append((i, j, reasons))
                    break
    results.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    return results


def derive_manuscript_term_occurrences(
    paragraphs: Sequence[ParagraphProfile | ParagraphText],
    terms_config: Mapping[str, TermProfile],
    *,
    source_path: str,
    source_sha256: str | None,
    source_state: str = "available",
    selected_term: str | None = None,
) -> dict[str, Any]:
    """Derive source-bound candidate occurrences of configured terms across displayed paragraphs."""
    if selected_term is not None and selected_term not in terms_config:
        raise ValueError(f"Unknown configured term: {selected_term!r}")

    active_terms = (
        {selected_term: terms_config[selected_term]}
        if selected_term is not None
        else dict(terms_config)
    )
    if source_state != "available":
        return {
            "source_path": source_path,
            "source_sha256": source_sha256,
            "source_state": source_state,
            "scope": TERMS_SCOPE,
            "term_count": len(active_terms),
            "occurrence_count": 0,
            "out_of_scope_count": 0,
            "ambiguous_count": 0,
            "terms": [
                {
                    "term": term_name,
                    "aliases": list(profile.aliases),
                    "scoped_alternatives": [
                        alt.model_dump(mode="json") for alt in profile.scoped_alternatives
                    ],
                    "case_sensitive": profile.case_sensitive,
                    "strict_boundaries": profile.strict_boundaries,
                    "dossier_id": profile.dossier_id,
                    "claim_id": profile.claim_id,
                    "occurrence_count": 0,
                    "out_of_scope_count": 0,
                    "ambiguous_count": 0,
                    "chapters_present": [],
                }
                for term_name, profile in active_terms.items()
            ],
            "occurrences": [],
            "chapters": [],
            "summary": {
                "term_count": len(active_terms),
                "occurrence_count": 0,
                "out_of_scope_count": 0,
                "ambiguous_count": 0,
            },
        }

    identities = [(p, paragraph_identity(p)) for p in paragraphs]

    # Collect raw hits across ALL configured terms first so cross-term overlaps are detected
    # even when filtering output to one `selected_term`.
    raw_by_paragraph: dict[int, list[dict[str, Any]]] = {}
    for p_idx, (paragraph, identity) in enumerate(identities):
        text = paragraph.text
        if not text:
            continue
        p_hits: list[dict[str, Any]] = []
        for term_name, profile in terms_config.items():
            variants: list[tuple[str, str, list[int] | None, str | None]] = [
                (term_name, "preferred", None, None),
                *((alias, "alias", None, None) for alias in profile.aliases),
                *(
                    (alt.term, "scoped_alternative", alt.chapters, alt.note)
                    for alt in profile.scoped_alternatives
                ),
            ]
            # Sort longest variant first so within a single term profile, longer phrases win over sub-spans.
            variants.sort(key=lambda item: (-len(item[0]), item[0]))
            term_spans: list[tuple[int, int, str]] = []
            for form, kind, scoped_chapters, scoped_note in variants:
                for start, end, unicode_reasons in _find_variant_spans(
                    text,
                    form,
                    case_sensitive=profile.case_sensitive,
                    strict=(
                        profile.strict_boundaries
                        if profile.strict_boundaries is not None
                        else profile.case_sensitive
                    ),
                ):
                    overlapping_same = [
                        existing_form for s, e, existing_form in term_spans if start < e and end > s
                    ]
                    if overlapping_same and any(s <= start and end <= e for s, e, _ in term_spans):
                        # If enclosed in an already-matched longer variant of the same term, skip.
                        continue
                    term_spans.append((start, end, form))
                    chapter = paragraph.chapter_num if paragraph.chapter_num > 0 else None
                    in_scope = True
                    effective_kind = kind
                    if scoped_chapters is not None and (
                        chapter is None or chapter not in scoped_chapters
                    ):
                        in_scope = False
                        effective_kind = "out_of_scope_alternative"
                    reasons = list(unicode_reasons)
                    if overlapping_same:
                        reasons.append(f"same_term_partial_overlap:{','.join(overlapping_same)}")
                    flags: list[str] = []
                    if not in_scope:
                        flags.append("out_of_scope_alternative")
                    if unicode_reasons:
                        flags.append("unicode_ambiguity")
                    if overlapping_same:
                        flags.append("overlapping_term")
                    quote_text = text[start:end]
                    p_hits.append(
                        {
                            "term": term_name,
                            "matched_form": form,
                            "quote": quote_text,
                            "variant_kind": effective_kind,
                            "expected_in_chapter": in_scope,
                            "allowed_chapters": scoped_chapters,
                            "scoped_note": scoped_note,
                            "flags": flags,
                            "ambiguous": bool(reasons),
                            "ambiguity_reasons": reasons,
                            "overlapping_terms": [],
                            "source_path": source_path,
                            "source_sha256": source_sha256,
                            "chapter": chapter,
                            "chapter_num": paragraph.chapter_num,
                            "chapter_title": paragraph.chapter_title,
                            "paragraph_index": p_idx,
                            "paragraph_sha256": identity["paragraph_sha256"],
                            "start_line": paragraph.start_line,
                            "end_line": paragraph.end_line,
                            "start": start,
                            "end": end,
                            "anchor": {
                                "start_line": paragraph.start_line,
                                "end_line": paragraph.end_line,
                                "paragraph_sha256": identity["paragraph_sha256"],
                                "start": start,
                                "end": end,
                                "quote": quote_text,
                            },
                            "dossier_id": profile.dossier_id,
                            "claim_id": profile.claim_id,
                        }
                    )
        if p_hits:
            # Check cross-term overlaps within the same paragraph
            for i, first in enumerate(p_hits):
                for j, second in enumerate(p_hits):
                    if i == j or first["term"] == second["term"]:
                        continue
                    if first["start"] < second["end"] and first["end"] > second["start"]:
                        if second["term"] not in first["overlapping_terms"]:
                            first["overlapping_terms"].append(second["term"])
                        reason = f"overlapping_term:{second['term']}"
                        if reason not in first["ambiguity_reasons"]:
                            first["ambiguity_reasons"].append(reason)
                        if "overlapping_term" not in first["flags"]:
                            first["flags"].append("overlapping_term")
                        first["ambiguous"] = True
            p_hits.sort(
                key=lambda item: (
                    item["start"],
                    item["end"],
                    item["term"],
                    item["matched_form"],
                )
            )
            raw_by_paragraph[p_idx] = p_hits

    occurrences: list[dict[str, Any]] = [
        hit
        for p_idx in sorted(raw_by_paragraph)
        for hit in raw_by_paragraph[p_idx]
        if selected_term is None or hit["term"] == selected_term
    ]

    term_summaries: list[dict[str, Any]] = []
    for term_name, profile in active_terms.items():
        term_hits = [h for h in occurrences if h["term"] == term_name]
        chapters_present = sorted(
            {int(h["chapter"]) for h in term_hits if isinstance(h["chapter"], int)}
        )
        term_summaries.append(
            {
                "term": term_name,
                "aliases": list(profile.aliases),
                "scoped_alternatives": [
                    alt.model_dump(mode="json") for alt in profile.scoped_alternatives
                ],
                "case_sensitive": profile.case_sensitive,
                "strict_boundaries": profile.strict_boundaries,
                "dossier_id": profile.dossier_id,
                "claim_id": profile.claim_id,
                "occurrence_count": len(term_hits),
                "out_of_scope_count": sum(1 for h in term_hits if not h["expected_in_chapter"]),
                "ambiguous_count": sum(1 for h in term_hits if h["ambiguous"]),
                "chapters_present": chapters_present,
            }
        )

    chapter_groups: dict[int | None, dict[str, Any]] = {}
    for hit in occurrences:
        ch = hit["chapter"]
        group = chapter_groups.get(ch)
        if group is None:
            group = {
                "chapter": ch,
                "chapter_title": hit["chapter_title"],
                "occurrences": [],
            }
            chapter_groups[ch] = group
        group["occurrences"].append(hit)

    out_of_scope_total = sum(1 for h in occurrences if not h["expected_in_chapter"])
    ambiguous_total = sum(1 for h in occurrences if h["ambiguous"])
    return {
        "source_path": source_path,
        "source_sha256": source_sha256,
        "source_state": source_state,
        "scope": TERMS_SCOPE,
        "term_count": len(active_terms),
        "occurrence_count": len(occurrences),
        "out_of_scope_count": out_of_scope_total,
        "ambiguous_count": ambiguous_total,
        "terms": term_summaries,
        "occurrences": occurrences,
        "chapters": list(chapter_groups.values()),
        "summary": {
            "term_count": len(active_terms),
            "occurrence_count": len(occurrences),
            "out_of_scope_count": out_of_scope_total,
            "ambiguous_count": ambiguous_total,
        },
    }
