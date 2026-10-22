"""Descriptive scene measurements and explicit manuscript register references."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .analyzer import CorpusAnalyzer
from .diversity import MIN_TOKENS_LD
from .markdown_parser import split_chapters, split_scenes
from .math_core import mad, median
from .models import ChapterMetrics, CorpusConfig
from .registers import validate_target_ranges
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


def _settings(settings: Any) -> tuple[dict[str, str], dict[str, dict[str, list[float | None]]], set[str]]:
    """Validate author-supplied targets; no genre prescriptions are built in."""
    if not isinstance(settings, Mapping) or set(settings) - {"assignments", "groups", "planned"}:
        raise ValueError("scene_analysis accepts only assignments, groups and planned")
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
        targets[name] = validate_target_ranges(group.get("targets", {}), fields)
    for identifier, group_name in assignments.items():
        if not isinstance(identifier, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", identifier):
            raise ValueError("Scene assignment keys must be chapter:scene numbers, for example 1:2")
        if not isinstance(group_name, str) or group_name not in targets:
            raise ValueError(f"Unknown register for scene {identifier}")
    planned = settings.get("planned", [])
    if (not isinstance(planned, list)
            or any(not isinstance(identifier, str) or identifier not in assignments for identifier in planned)
            or len(set(planned)) != len(planned)):
        raise ValueError("Planned scenes must be a unique list of scene assignment IDs")
    return dict(assignments), targets, set(planned)


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
    assignments, targets, planned = _settings({} if settings is None else settings)
    analyzer = CorpusAnalyzer(config, sample_text=text)
    measured_chapters = {chapter.num: chapter for chapter in (_premeasured_chapters or ())}
    items: list[dict[str, Any]] = []
    chapter_dividers: dict[int, int] = {}
    breaks = 0
    for chapter_num, title, body in split_chapters(text, config):
        clean = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        parts, scene_breaks = split_scenes(clean)
        chapter_dividers[chapter_num] = scene_breaks
        breaks += scene_breaks
        for index, part in enumerate(parts, 1):
            measured = measured_chapters.get(chapter_num) if not scene_breaks else None
            if measured is None or measured.title != title:
                measured = analyzer.measure_unit(part)
            if measured is None or measured.words == 0:
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
    unplanned = missing - planned
    if unplanned:
        details = []
        for chapter in sorted({int(identifier.split(":")[0]) for identifier in unplanned}):
            if chapter not in chapter_dividers:
                details.append(f"Chapter {chapter} is not present in this manuscript.")
                continue
            identifiers = [item["id"] for item in items if item["chapter"] == chapter]
            count = len(identifiers)
            dividers = chapter_dividers[chapter]
            details.append(
                f"Chapter {chapter}: {count} measured scene{'s' if count != 1 else ''} "
                f"({', '.join(identifiers) or 'none'}); "
                f"{dividers} recognized scene divider{'s' if dividers != 1 else ''}."
            )
        raise ValueError(
            "Scene assignments no longer match this manuscript: " + ", ".join(sorted(unplanned))
            + "\n" + "\n".join(details)
            + "\nReview scene_analysis.assignments after merging or removing scenes. "
            "For unwritten scenes, explicitly list their assigned IDs in scene_analysis.planned. "
            "Review intended scene breaks: use a standalone --- or * * *. Blank lines do not split scenes."
        )
    baselines: dict[str, dict[str, Any]] = {}
    for group in targets:
        members = [item for item in items if item["group"] == group]
        baselines[group] = {}
        for field, _, _ in FEATURES:
            values = [item["features"][field] for item in members if item["features"][field] is not None]
            centre = median(values) if len(values) >= 2 else None
            baselines[group][field] = {
                "n": len(values), "median": centre,
                "mad": mad(values, centre) if centre is not None else None,
            }
    report: dict[str, Any] = {"items": items, "baselines": baselines, "explicit_scene_breaks": breaks,
              "scenes_are_chapters": breaks == 0,
              "baseline_scope": "explicit register assignments within this manuscript only",
              "uncertainty_scope": "approximate core standard errors; no validated reliability or quality score"}
    if planned:
        report["planned_items"] = [
            {"id": identifier, "chapter": int(identifier.split(":")[0]),
             "scene": int(identifier.split(":")[1]), "group": assignments[identifier], "state": "planned"}
            for identifier in sorted(missing & planned, key=lambda value: tuple(map(int, value.split(":"))))
        ]
    return report
