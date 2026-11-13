"""Descriptive scene measurements and explicit manuscript register references."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .analyzer import CorpusAnalyzer
from .diversity import MIN_TOKENS_LD
from .language import compile_pattern, compile_word_pattern, quotation_texts, resolve_language
from .markdown_parser import prose_text, split_chapters, split_scenes, strip_html_comments
from .math_core import mad, median
from .models import ChapterMetrics, CorpusConfig
from .pacing import HOOK_TYPES, _hook_score, classify_scene_hook
from .registers import MAX_REGISTER_NAME_CHARS, validate_target_ranges
from .sentences import split_prose_sentences
from .style_fingerprint import FEATURES

_INTRA_SCENE_MIN_WORDS = 120


def _intra_scene_dynamics(
    scene_sentences: Sequence[str],
    words: int,
    word_re: re.Pattern[str],
    dialogue_re: re.Pattern[str],
) -> tuple[float | None, float | None, str]:
    """Measure first-half vs. second-half ASL and dialogue shifts within a scene."""
    if words < _INTRA_SCENE_MIN_WORDS or len(scene_sentences) < 2:
        return None, None, "insufficient_length"
    mid = len(scene_sentences) // 2
    first_half = scene_sentences[:mid]
    second_half = scene_sentences[mid:]

    def _half_stats(sents: Sequence[str]) -> tuple[float, float]:
        total_w = sum(len(word_re.findall(s)) for s in sents)
        asl = total_w / len(sents)
        dlg_w = sum(len(word_re.findall(m)) for s in sents for m in quotation_texts(dialogue_re, s))
        dlg_pct = (dlg_w / total_w * 100.0) if total_w else 0.0
        return asl, dlg_pct

    first_asl, first_dlg = _half_stats(first_half)
    second_asl, second_dlg = _half_stats(second_half)
    asl_shift = round(second_asl - first_asl, 2)
    dialogue_shift = round(second_dlg - first_dlg, 2)

    if dialogue_shift >= 15.0:
        dynamic = "dialogue_surge"
    elif asl_shift <= -2.5:
        dynamic = "accelerating"
    elif asl_shift >= 2.5:
        dynamic = "decelerating"
    else:
        dynamic = "steady"
    return asl_shift, dialogue_shift, dynamic


def _detect_pacing_plateaus(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Find consecutive >=3 scene spans where exit hooks or pacing flatten."""
    plateaus: list[dict[str, Any]] = []
    covered: set[int] = set()

    def _emit(run: Sequence[Mapping[str, Any]], reason: str) -> None:
        asls = [float(item["features"]["asl"]) for item in run if item["features"].get("asl") is not None]
        mean_asl = round(sum(asls) / len(asls), 2) if asls else 0.0
        plateaus.append({
            "start_id": run[0]["id"],
            "end_id": run[-1]["id"],
            "scene_count": len(run),
            "mean_asl": mean_asl,
            "reason": reason,
        })

    idx = 0
    n = len(items)
    while idx < n:
        if items[idx]["exit_hook_score"] <= 1:
            end = idx + 1
            while end < n and items[end]["exit_hook_score"] <= 1:
                end += 1
            if end - idx >= 3:
                _emit(items[idx:end], "low_exit_hooks")
                covered.update(range(idx, end))
            idx = end
        else:
            idx += 1

    idx = 0
    while idx < n:
        if idx not in covered and items[idx]["scene_dynamic"] == "steady" and items[idx]["words"] >= _INTRA_SCENE_MIN_WORDS:
            end = idx + 1
            while (
                end < n
                and end not in covered
                and items[end]["scene_dynamic"] == "steady"
                and items[end]["words"] >= _INTRA_SCENE_MIN_WORDS
            ):
                end += 1
            if end - idx >= 3:
                asls = [float(item["features"]["asl"]) for item in items[idx:end] if item["features"].get("asl") is not None]
                if asls and (max(asls) - min(asls)) <= 1.5:
                    _emit(items[idx:end], "flat_pacing")
            idx = end
        else:
            idx += 1

    return plateaus


def scene_report_for_display(
    text: str, config: CorpusConfig, settings: Any = None, *,
    premeasured_chapters: Sequence[ChapterMetrics] | None = None,
    pov_by_chapter: Mapping[int, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Keep the dashboard readable when project assignments need maintenance.

    Internal display callers may reuse chapters from their shared analysis of
    exactly this text and config. Explicitly split scenes still need their own
    measurements; no result is retained across requests.
    """
    try:
        return scene_report(
            text, config, settings,
            _premeasured_chapters=premeasured_chapters,
            pov_by_chapter=pov_by_chapter,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def _settings(
    settings: Any,
) -> tuple[dict[str, str], dict[str, dict[str, list[float | None]]], set[str], dict[str, str]]:
    """Validate author-supplied targets; no genre prescriptions are built in."""
    if not isinstance(settings, Mapping) or set(settings) - {"assignments", "groups", "planned", "titles"}:
        raise ValueError("scene_analysis accepts only assignments, groups, planned and titles")
    assignments = settings.get("assignments", {})
    groups = settings.get("groups", {})
    raw_titles = settings.get("titles", {})
    if (
        not isinstance(assignments, Mapping)
        or not isinstance(groups, Mapping)
        or not isinstance(raw_titles, Mapping)
    ):
        raise ValueError("Scene assignments, groups and titles must be tables")
    targets: dict[str, dict[str, list[float | None]]] = {}
    fields = {f[0] for f in FEATURES}
    for name, group in groups.items():
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_REGISTER_NAME_CHARS:
            raise ValueError(f"Register names must contain 1–{MAX_REGISTER_NAME_CHARS} characters")
        if not isinstance(group, Mapping) or set(group) - {"targets"}:
            raise ValueError("Each scene group accepts only a targets table")
        targets[name] = validate_target_ranges(group.get("targets", {}), fields)
    for identifier, group_name in assignments.items():
        if not isinstance(identifier, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", identifier):
            raise ValueError("Scene assignment keys must be chapter:scene numbers, for example 1:2")
        if not isinstance(group_name, str) or group_name not in targets:
            raise ValueError(f"Unknown register for scene {identifier}")
    titles: dict[str, str] = {}
    for identifier, title_text in raw_titles.items():
        if not isinstance(identifier, str) or not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", identifier):
            raise ValueError("Scene title keys must be chapter:scene numbers, for example 1:2")
        if not isinstance(title_text, str) or not title_text.strip():
            raise ValueError(f"Scene title for {identifier} must be a nonempty string")
        titles[identifier] = title_text.strip()
    planned = settings.get("planned", [])
    if (not isinstance(planned, list)
            or any(not isinstance(identifier, str) or identifier not in assignments for identifier in planned)
            or len(set(planned)) != len(planned)):
        raise ValueError("Planned scenes must be a unique list of scene assignment IDs")
    return dict(assignments), targets, set(planned), titles


def scene_report(
    text: str, config: CorpusConfig, settings: Any = None, *,
    _premeasured_chapters: Sequence[ChapterMetrics] | None = None,
    pov_by_chapter: Mapping[int, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Use existing analysis features per pacing unit; never analyze sources.

    Standard errors reuse the core's approximate plug-ins. Zero plug-in errors
    are withheld: absent events or constant samples do not establish certainty.
    HD-D remains an exact 42-draw value on [0, 1], guarded below 100 tokens;
    no population uncertainty is estimated for it. Group medians and MAD are
    descriptive and include the measured scene, not external quality baselines.
    """
    assignments, targets, planned, titles = _settings({} if settings is None else settings)
    analyzer = CorpusAnalyzer(config, sample_text=text)
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    dialogue_re = compile_pattern(resolved.dialogue_regex)
    filter_verbs_re = compile_pattern(resolved.filter_verbs_regex)
    measured_chapters = {chapter.num: chapter for chapter in (_premeasured_chapters or ())}
    items: list[dict[str, Any]] = []
    entry_counts = dict.fromkeys(HOOK_TYPES, 0)
    exit_counts = dict.fromkeys(HOOK_TYPES, 0)
    chapter_dividers: dict[int, int] = {}
    breaks = 0
    for chapter_num, title, body in split_chapters(text, config):
        clean = strip_html_comments(body)
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
            scene_heading = titles.get(identifier)
            if not scene_heading:
                for line in part.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    m = re.match(r"^#{1,6}\s+(.+?)(?:\s+#+)?$", stripped)
                    if m:
                        scene_heading = m.group(1).strip()
                    break
            if not scene_heading:
                scene_heading = title if not scene_breaks else f"{title} · {index}"
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
            scene_prose = prose_text(part, _front_matter=False)
            scene_sentences = [
                s for s in split_prose_sentences(scene_prose, resolved.key)
                if word_re.search(s)
            ]
            entry_sentence = scene_sentences[0] if scene_sentences else ""
            exit_sentence = scene_sentences[-1] if scene_sentences else ""
            entry_hook_type = classify_scene_hook(
                entry_sentence, dialogue_re=dialogue_re, filter_verbs_re=filter_verbs_re
            )
            exit_hook_type = classify_scene_hook(
                exit_sentence, dialogue_re=dialogue_re, filter_verbs_re=filter_verbs_re
            )
            exit_is_dialogue = bool(dialogue_re.search(exit_sentence)) if exit_sentence else False
            exit_hook_score, _, _ = _hook_score(
                exit_sentence,
                exit_is_dialogue,
                word_re,
                hook_short_sentence=config.hook_short_sentence,
            )
            asl_shift, dialogue_shift, scene_dynamic = _intra_scene_dynamics(
                scene_sentences, measured.words, word_re, dialogue_re
            )
            entry_counts[entry_hook_type] = entry_counts.get(entry_hook_type, 0) + 1
            exit_counts[exit_hook_type] = exit_counts.get(exit_hook_type, 0) + 1
            item_dict: dict[str, Any] = {
                "id": identifier, "chapter": chapter_num, "chapter_title": title,
                "scene": index, "scene_title": scene_heading, "group": group, "words": measured.words,
                "sentences": measured.sentences, "features": features,
                "standard_errors": errors, "targets": comparisons,
                "entry_hook_type": entry_hook_type,
                "exit_hook_type": exit_hook_type,
                "exit_hook_score": exit_hook_score,
                "asl_shift": asl_shift,
                "dialogue_shift": dialogue_shift,
                "scene_dynamic": scene_dynamic,
                "filter_per_1000": round(float(measured.filter_density), 2),
                "sensory_per_1000": round(float(measured.sensory_density), 2),
                "data_support": {"diversity_min_tokens": MIN_TOKENS_LD,
                                 "diversity_available": measured.words >= MIN_TOKENS_LD},
            }
            if pov_by_chapter is not None:
                item_dict["pov_characters"] = list(pov_by_chapter.get(chapter_num, ()))
            items.append(item_dict)
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
              "hook_distribution": {"entry": entry_counts, "exit": exit_counts},
              "pacing_plateaus": _detect_pacing_plateaus(items),
              "baseline_scope": "explicit register assignments within this manuscript only",
              "uncertainty_scope": "approximate core standard errors; no validated reliability or quality score"}
    if planned:
        report["planned_items"] = [
            {"id": identifier, "chapter": int(identifier.split(":")[0]),
             "scene": int(identifier.split(":")[1]), "group": assignments[identifier], "state": "planned"}
            for identifier in sorted(missing & planned, key=lambda value: tuple(map(int, value.split(":"))))
        ]
    return report
