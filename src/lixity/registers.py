"""Validate explicit author register targets and resolve chapter assignments.

Target ranges describe author intent. They do not establish a probability model
and must not be converted to statistical z-scores or quality judgments.
"""

import math
from collections.abc import Collection, Mapping, Sequence
from typing import Any

from .publication import validate_metadata_text


def validate_target_ranges(
    values: Any, fields: Collection[str], *, allow_scalar: bool = False,
) -> dict[str, list[float | None]]:
    """Normalize feature bounds, sharing the chapter and scene target rules."""
    if not isinstance(values, Mapping):
        raise ValueError("Register targets must be a table of feature ranges")
    targets: dict[str, list[float | None]] = {}
    for feature, target_range in values.items():
        if feature not in fields:
            raise ValueError(f"Unknown register feature: {feature}")
        if isinstance(target_range, Mapping):
            if set(target_range) - {"lower", "upper"}:
                raise ValueError(f"{feature}: range tables accept lower and upper only")
            bounds = [target_range.get("lower"), target_range.get("upper")]
        elif allow_scalar and type(target_range) in (int, float):
            bounds = [target_range, target_range]
        else:
            bounds = target_range
        if not isinstance(bounds, list) or len(bounds) != 2 or bounds == [None, None]:
            raise ValueError(f"{feature}: provide [lower, upper], using null for one open bound")
        maximum = (1 if feature == "hd_d" else
                   100 if feature.endswith("_pct") or feature == "first_person_start_rate" else None)
        normalized: list[float | None] = []
        for bound in bounds:
            try:
                valid = (bound is None or
                         (type(bound) in (int, float) and math.isfinite(bound)
                          and bound >= 0 and (maximum is None or bound <= maximum)))
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError(f"Invalid target range for {feature}")
            normalized.append(float(bound) if bound is not None else None)
        lower, upper = normalized
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"Reversed target range for {feature}")
        targets[feature] = normalized
    return targets


def validate_register_settings(
    profiles: Any, assignments: Any,
) -> tuple[dict[str, dict[str, list[float | None]]], dict[str, str]]:
    """Validate chapter registers for both configuration and Settings saves.

    Profiles map names to feature ranges; scalar targets mean an exact value.
    Empty profiles intentionally label a register without supplying targets.
    """
    if not isinstance(profiles, Mapping) or not isinstance(assignments, Mapping):
        raise ValueError("register_profiles and chapter_registers must be tables")
    normalized_profiles: dict[str, dict[str, list[float | None]]] = {}
    if profiles:
        # Import lazily because CorpusConfig validates these settings and the
        # fingerprint module itself imports CorpusConfig.
        from .style_fingerprint import FEATURES

        fields = {feature for feature, _label, _unit in FEATURES}
        for name, targets in profiles.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                raise ValueError("Register names must contain 1–100 characters")
            validate_metadata_text(name, "Register name", 100)
            try:
                normalized_profiles[name] = validate_target_ranges(targets, fields, allow_scalar=True)
            except ValueError as exc:
                raise ValueError(f"Register {name}: {exc}") from exc
    normalized_assignments: dict[str, str] = {}
    for selector, name in assignments.items():
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("Chapter register selectors must be nonempty titles or chapter numbers")
        validate_metadata_text(selector, "Chapter register selector", len(selector))
        if not isinstance(name, str) or name not in normalized_profiles:
            raise ValueError(f"Unknown register for chapter {selector}: {name}")
        normalized_assignments[selector] = name
    return normalized_profiles, normalized_assignments


def resolve_chapter_registers(
    chapters: Sequence[Any], assignments: Mapping[str, str],
) -> dict[int, str]:
    """Prefer chapter numbers, full titles, then the longest partial title.

    Partial selectors may label several chapters. Equal-length partial matches
    use lexical order, independent of configuration insertion order.
    """
    result: dict[int, str] = {}
    matched: set[str] = set()
    for chapter in chapters:
        candidates: list[tuple[int, int, str]] = []
        for selector in assignments:
            if selector.isdecimal():
                if selector == str(chapter.num):
                    candidates.append((0, 0, selector))
                    matched.add(selector)
            elif selector == chapter.title:
                candidates.append((1, 0, selector))
                matched.add(selector)
            elif selector in chapter.title:
                candidates.append((2, -len(selector), selector))
                matched.add(selector)
        if candidates:
            result[chapter.num] = assignments[min(candidates)[2]]
    missing = assignments.keys() - matched
    if missing:
        raise ValueError("Chapter registers no longer match this manuscript: " + ", ".join(sorted(missing)))
    return result
