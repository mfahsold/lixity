"""Descriptive scene measurements and explicit manuscript register references."""

import math
import re
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from .analyzer import CorpusAnalyzer
from .diversity import MIN_TOKENS_LD
from .markdown_parser import split_chapters, split_scenes
from .models import ChapterMetrics, CorpusConfig
from .style_fingerprint import FEATURES


def scene_report_for_display(
    text: str, config: CorpusConfig, settings: Any = None, *,
    premeasured_chapters: Sequence[ChapterMetrics] | None = None,
) -> dict[str, Any]:
    """Keep the dashboard readable when project assignments need maintenance.

    Internal display callers may reuse chapters from their shared analysis of
    exactly this text and config. Explicitly split scenes still need their own
    measurements; no result is retained across requests.
    """
    try:
        return scene_report(text, config, settings, _premeasured_chapters=premeasured_chapters)
    except ValueError as exc:
        return {"error": str(exc)}


def _settings(settings: Any) -> tuple[dict[str, str], dict[str, dict[str, list[float | None]]]]:
    """Validate author-supplied targets; no genre prescriptions are built in."""
    if not isinstance(settings, Mapping) or set(settings) - {"assignments", "groups"}:
        raise ValueError("scene_analysis accepts only assignments and groups")
    assignments = settings.get("assignments", {})
    groups = settings.get("groups", {})
    if not isinstance(assignments, Mapping) or not isinstance(groups, Mapping):
        raise ValueError("Scene assignments and groups must be tables")
    targets: dict[str, dict[str, list[float | None]]] = {}
    fields = {f[0] for f in FEATURES}
    for name, group in groups.items():
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError("Register names must contain 1–100 characters")
        if not isinstance(group, Mapping) or set(group) - {"targets"}:
            raise ValueError("Each scene group accepts only a targets table")
        values = group.get("targets", {})
        if not isinstance(values, Mapping):
            raise ValueError("Register targets must be a table of feature ranges")
        targets[name] = {}
        for feature, target_range in values.items():
            if feature not in fields:
                raise ValueError(f"Unknown scene feature: {feature}")
            if isinstance(target_range, Mapping):
                if set(target_range) - {"lower", "upper"}:
                    raise ValueError(f"{feature}: range tables accept lower and upper only")
                bounds = [target_range.get("lower"), target_range.get("upper")]
            else:
                bounds = target_range
            if not isinstance(bounds, list) or len(bounds) != 2 or bounds == [None, None]:
                raise ValueError(f"{feature}: provide [lower, upper], using null for one open bound")
            maximum = 1 if feature == "hd_d" else 100 if feature.endswith("_pct") or feature == "first_person_start_rate" else None
            for bound in bounds:
                if bound is not None and (type(bound) not in (int, float) or not math.isfinite(bound)
                                          or bound < 0 or (maximum is not None and bound > maximum)):
                    raise ValueError(f"Invalid target range for {feature}")
            if all(b is not None for b in bounds) and bounds[0] > bounds[1]:
                raise ValueError(f"Reversed target range for {feature}")
            targets[name][feature] = bounds
    for identifier, group_name in assignments.items():
        if not isinstance(identifier, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*", identifier):
            raise ValueError("Scene assignment keys must be chapter:scene numbers, for example 1:2")
        if not isinstance(group_name, str) or group_name not in targets:
            raise ValueError(f"Unknown register for scene {identifier}")
    return dict(assignments), targets


def scene_report(
    text: str, config: CorpusConfig, settings: Any = None, *,
    _premeasured_chapters: Sequence[ChapterMetrics] | None = None,
) -> dict[str, Any]:
    """Use existing analysis features per pacing unit; never analyze sources.

    Standard errors reuse the core's approximate plug-ins. Zero plug-in errors
    are withheld: absent events or constant samples do not establish certainty.
    HD-D remains an exact 42-draw value on [0, 1], guarded below 100 tokens;
    no population uncertainty is estimated for it. Group medians and MAD are
    descriptive and include the measured scene, not external quality baselines.
    """
    assignments, targets = _settings({} if settings is None else settings)
    analyzer = CorpusAnalyzer(config)
    measured_chapters = {chapter.num: chapter for chapter in (_premeasured_chapters or ())}
    items: list[dict[str, Any]] = []
    breaks = 0
    for chapter_num, title, body in split_chapters(text, config):
        clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        parts, scene_breaks = split_scenes(clean)
        breaks += scene_breaks
        for index, part in enumerate(parts, 1):
            measured = measured_chapters.get(chapter_num) if not scene_breaks else None
            if measured is None or measured.title != title:
                measured = analyzer.measure_unit(part)
            if measured is None:
                continue
            identifier = f"{chapter_num}:{index}"
            group = assignments.get(identifier)
            features = {field: getattr(measured, field) for field, _, _ in FEATURES}
            if measured.sentences < 2:
                features["sentence_cv"] = None
            errors = {field: se for field, se in measured.style_se.items()
                      if se > 0 and features.get(field) is not None and measured.sentences > 1}
            comparisons = {}
            for field, bounds in targets.get(group or "", {}).items():
                value = features[field]
                position = ("unavailable" if value is None else
                            "below" if bounds[0] is not None and value < bounds[0] else
                            "above" if bounds[1] is not None and value > bounds[1] else "within")
                comparisons[field] = {"lower": bounds[0], "upper": bounds[1], "position": position}
            items.append({
                "id": identifier, "chapter": chapter_num, "chapter_title": title,
                "scene": index, "group": group, "words": measured.words,
                "sentences": measured.sentences, "features": features,
                "standard_errors": errors, "targets": comparisons,
                "data_support": {"diversity_min_tokens": MIN_TOKENS_LD,
                                 "diversity_available": measured.words >= MIN_TOKENS_LD},
            })
    missing = assignments.keys() - {item["id"] for item in items}
    if missing:
        raise ValueError("Scene assignments no longer match this manuscript: " + ", ".join(sorted(missing)))
    baselines: dict[str, dict[str, Any]] = {}
    for group in targets:
        members = [item for item in items if item["group"] == group]
        baselines[group] = {}
        for field, _, _ in FEATURES:
            values = [item["features"][field] for item in members if item["features"][field] is not None]
            centre = statistics.median(values) if len(values) >= 2 else None
            baselines[group][field] = {
                "n": len(values), "median": centre,
                "mad": statistics.median(abs(value - centre) for value in values) if centre is not None else None,
            }
    return {"items": items, "baselines": baselines, "explicit_scene_breaks": breaks,
            "scenes_are_chapters": breaks == 0,
            "baseline_scope": "explicit register assignments within this manuscript only",
            "uncertainty_scope": "approximate core standard errors; no validated reliability or quality score"}
