"""Lixity – command line: corpus analysis, style profile, style reference and dashboard."""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout
from io import StringIO
from time import monotonic as _monotonic
from typing import TYPE_CHECKING, Any

import orjson

from . import __version__
from .cli_texts import CLI_TEXTS as CLI_TEXTS
from .cli_texts import _lang, _m
from .io import FileUtils
from .site import docs_url
from .speech_engines import EXTERNAL_ENGINES, NATIVE_ENGINES, native_engine
from .status import (
    ABOUT_SECTIONS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    LAYER_FEATURES,
    SCHEMA_VERSION_ANALYZE,
    SCHEMA_VERSION_STYLE,
)

if TYPE_CHECKING:
    from .language import ResolvedLanguage
    from .models import CorpusConfig
    from .style_fingerprint import FingerprintThresholds, ParagraphLayerCell
    from .style_profile import ParagraphProfile

SCHEMA_VERSION = SCHEMA_VERSION_ANALYZE
EXIT_OK = 0
EXIT_ERROR = 1


def load_project_config(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Lazy wrapper kept on lixity.cli for direct callers and test monkeypatches."""
    from .config import load_project_config as _load

    return _load(*args, **kwargs)


def read_explicit_project_config(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Lazy wrapper kept on lixity.cli for direct callers and test monkeypatches."""
    from .config import read_explicit_project_config as _read

    return _read(*args, **kwargs)


def _audio_progress() -> Callable[[int, int], None]:
    """Report segment progress and a clear estimate, without changing the render."""
    started: float | None = None
    last_report: float | None = None

    def report(done: int, total: int) -> None:
        nonlocal started, last_report
        now = _monotonic()
        if started is None:
            started = now
        pct = (done / total * 100) if total else 0.0
        elapsed = now - started
        message = f"Audio: {done}/{total} ({pct:5.1f}%)"
        if done >= 1:
            seg_time = elapsed / done
            if done < total:
                remaining = max(0, math.ceil((total - done) * seg_time))
                mins, secs = divmod(remaining, 60)
                time_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                message += f" · ETA: ~{time_str} ({seg_time:.1f}s/seg)"
            else:
                mins, secs = divmod(math.ceil(elapsed), 60)
                tot_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
                message += f" · Fertig in {tot_str}"
        print(message, file=sys.stderr)

    return report


def _document_title(args: argparse.Namespace, manuscript: str, text: str) -> str:
    from .project_identity import project_title

    return project_title(manuscript, text, args._project_config)


def _thresholds_from_args(
    args: argparse.Namespace, config: dict[str, Any] | None = None
) -> FingerprintThresholds:
    """Builds FingerprintThresholds from CLI flags (defaults = documented heuristics).

    Precedence: CLI flag > project config (``[tool.lixity]`` / ``lixity.toml``) >
    built-in default — shared builder ``config.resolve_thresholds``.
    """
    from .config import resolve_thresholds

    return resolve_thresholds(
        project_config=config,
        preset=getattr(args, "preset", None),
        z_mild=getattr(args, "z_mild", None),
        z_strong=getattr(args, "z_strong", None),
        fdr_q=getattr(args, "fdr_q", None),
        fdr_method=getattr(args, "fdr_method", None),
        dim_score_threshold=getattr(args, "dim_threshold", None),
        flag_min_severity=getattr(args, "flag_min_severity", None),
        min_chapters=getattr(args, "min_chapters", None),
    )


def _json(payload: object, indent: bool = False) -> str:
    """Serialises to UTF-8 JSON with orjson (one serializer for the whole CLI)."""
    option = orjson.OPT_NON_STR_KEYS | (orjson.OPT_INDENT_2 if indent else 0)
    return orjson.dumps(payload, option=option).decode("utf-8")


_META = {
    "tool": "lixity",
    "version": __version__,
    "schema_version": SCHEMA_VERSION,
}

def _completion_scripts() -> tuple[str, str]:
    """Bash and Zsh scripts with live command and research-action lists."""
    from .cli_completions import build_completion_scripts

    return build_completion_scripts(_COMMANDS, ABOUT_SECTIONS)


#: Top-level commands: name and help text drive the parser and both emitted
#: completion scripts, so adding a command lists it everywhere at once.
_COMMANDS: tuple[tuple[str, str], ...] = (
    ("project", "Inspect project sources, output locations and structural issues without writing"),
    ("project-backup", "Back up selected project files and research"),
    ("project-restore", "Verify a bundle and restore a new project"),
    ("research", "Local sources, dossiers, citations and lexical search (text/JSON)"),
    ("service", "Manage an owned local dashboard process"),
    ("analyze", "Corpus metrics (text/JSON, self-describing meta block)"),
    ("profile", "Paragraph tense/style estimates (JSON; --layer text/JSON)"),
    ("analysis-review", "Review tense observations and save explicit project-local author decisions"),
    ("dialogue", "Recognized quoted passages and word shares (text/JSON)"),
    ("characters", "Curated name mentions and declared POV across chapters (text/JSON)"),
    ("pacing", "Scene structure, pacing and chapter hooks (text/JSON)"),
    ("scenes", "Scene features, register references and author targets (text/JSON)"),
    ("canvas", "Export narrative scenes into a JSON Canvas 1.0 storyboard (.canvas)"),
    ("motifs", "Motif tracking, repetition and local phrase echoes (text/JSON)"),
    ("showing", "Compare word-pattern and quotation/short-sentence signals (text/JSON)"),
    ("style", f"Self-calibrated style reference of the manuscript (text/JSON, schema v{SCHEMA_VERSION_STYLE})"),
    ("diff", "Compare two manuscript files or recorded revisions (text/JSON)"),
    ("dashboard", "Generate a single-file HTML dashboard"),
    ("export-site", "Export a static read-only project website"),
    ("pdf", "Compose a PDF for editing, reading, submission or analysis"),
    ("read-aloud", "Create a local listening copy with project voice profiles"),
    ("audio-export-plan", "Export manuscript direction as JSON timeline or SSML without synthesis"),
    ("audio-inspect", "Inspect a chapter audio file locally (JSON; no speech recognition)"),
    ("audio-verify", "Compare chapter audio with a direction plan and optional timestamped transcript (JSON)"),
    ("audio-transcribe", "Transcribe audio through an explicit local MLX-Audio service"),
    ("audio-import-transcript", "Convert external ASR word timestamps (e.g. Whisper) to lixity-audio-transcript/1"),
    ("audio-status", "Inspect audio profiles and worker readiness"),
    ("audio-microphone", "Inspect and set hardware microphone gain and list recording devices"),
    ("audio-calibrate", "Record one microphone test and suggest a gain adjustment (text/JSON)"),
    ("audio-reference", "Record, create, inspect or generate private voice references; print reading text"),
    ("audio-import", "Retain a completed chapter WAV for an exact manuscript revision (JSON)"),
    ("audio-direction", "Inspect and save project-local passage speech direction (JSON)"),
    ("audio-migrate", "Preview or apply backed-up audio settings upgrades or removed-engine replacements"),
    ("serve", "Run local HTTP development server and interactive dashboard"),
    ("build", "Idempotent workspace build of analysis exports and artifact archive"),
    ("doctor", "Inspect installed versions, module location and local service without changing them"),
    ("about", "Installed metadata: commands, configuration, languages, features and heuristics"),
    ("schema", "Installed metadata: commands, configuration, languages, features and heuristics"),
    ("mcp", "Run read-only Model Context Protocol (MCP) server on stdio for AI assistants"),
    ("completion", "Shell completion script (bash or zsh)"),
)


def _meta_payload(language_key: str, **body: Any) -> dict[str, Any]:
    payload = {"meta": {**_META, "language": language_key}}
    payload.update(body)
    return payload


def _print_paragraph_layer(
    report: dict[str, Any], source: str, language_key: str, labels: Mapping[str, str],
    *, paragraphs: list[ParagraphProfile], measurements: Mapping[int, ParagraphLayerCell],
    measurement_available: bool,
) -> None:
    """Print measurements and anchors, with literal snippets only when requested."""
    from .format import num, safe_text
    from .style_fingerprint import FEATURE_UNITS, FEATURES

    pack = CLI_TEXTS.get(language_key, CLI_TEXTS["en"])

    def message(key: str, **values: object) -> str:
        return pack[key].format(**values)

    feature = report["feature"]
    label_key = next(label for field, label, _unit in FEATURES if field == feature)
    unit = FEATURE_UNITS.get(language_key, {}).get(feature, report["unit"])
    minimum = report["comparison"]["minimum_paragraphs"]
    print(f"{labels.get(label_key, feature)} ({unit})")
    print(message("layer_reference", minimum=minimum))
    cutoff = num(report["comparison"]["notable_abs_z"], language_key, 2)
    print(message("layer_notable", cutoff=cutoff))
    counts = report["selection"]
    print(message("layer_counts", **counts))
    if not measurement_available:
        print(message("layer_language_unavailable"))
    if counts["selected_count"] == 0:
        print(message("layer_empty"))
        if counts["total_count"] == 0:
            print(message("layer_empty_source"))
        if counts["comparable_count"]:
            print(message("layer_empty_cutoff"))
        if paragraphs and measurement_available:
            chapters: dict[int, set[str | None]] = {}
            for index, paragraph in enumerate(paragraphs):
                cell = measurements.get(index)
                chapters.setdefault(paragraph.chapter_num, set()).add(cell.reason if cell else "unmeasured")
            reasons = {"layer_short": 0, "layer_no_spread": 0, "layer_unmeasured": 0}
            for chapter in chapters.values():
                if None in chapter:
                    continue
                if "zero_spread" in chapter:
                    reasons["layer_no_spread"] += 1
                elif "short_paragraph" in chapter or "too_few_paragraphs" in chapter:
                    reasons["layer_short"] += 1
                else:
                    reasons["layer_unmeasured"] += 1
            for reason_key, count in reasons.items():
                if count:
                    print(message(reason_key, count=count, minimum=minimum))
        from shlex import join

        command = join(["lixity", "profile", source, "--language", language_key,
                        "--layer", report["layer"], "--evidence", "--json"])
        print(message("layer_full", command=safe_text(command)))
    for row in report["paragraphs"]:
        value = "—" if row["value"] is None else num(row["value"], language_key, 2)
        comparison = (
            message("layer_unavailable") if row["z"] is None
            else message("layer_local", z=num(row["z"], language_key, 2, signed=True))
        )
        notable = " · " + message("layer_flag") if row["notable"] is True else ""
        anchor = safe_text(f"{source}:{row['start_line']}-{row['end_line']}")
        title = safe_text(row["chapter_title"])
        print(
            f"{anchor} · {row['chapter_num']}: {title} · "
            f"{value} {unit} · {comparison}{notable}"
        )
        if "evidence" in row:
            evidence = row["evidence"]["layers"][report["layer"]]
            reason = f" · {evidence['reason']}" if evidence.get("reason") else ""
            evidence_unit = message("layer_" + evidence["kind"])
            status_key = {"available": "layer_available", "partial": "layer_partial",
                          "unavailable": "layer_missing"}[evidence["status"]]
            print("  " + message("layer_evidence", status=message(status_key),
                                 mapped=evidence["mapped_count"], count=evidence["count"],
                                 unit=evidence_unit, reason=reason))
            for span in evidence["spans"][:8]:
                snippet = paragraphs[row["index"]].text[span["start"]:span["end"]]
                snippet = snippet[:120] + ("…" if len(snippet) > 120 else "")
                sentence_words = f" · {span['words']} {message('layer_words')}" if "words" in span else ""
                print(f"    [{span['start']}:{span['end']}] x{span['count']}{sentence_words} "
                      f"{safe_text(snippet)}")
            if len(evidence["spans"]) > 8:
                print(f"    … {len(evidence['spans']) - 8} {message('layer_more')}")


def _print_about_json(section: str | None = None) -> None:
    from .api import about

    print(_json(about(section=section), indent=True))


def _print_about_text() -> None:
    from .api import about

    data = about()
    print(_m("about_title", version=data["meta"]["version"]))
    print(_m("about_languages", languages=", ".join(data["languages"])))
    print(_m("about_features", count=len(data["features"])))
    for feat in data["features"]:
        print(f"  {feat['field']:<24} [{feat['unit']}]")
    heuristics = data["heuristics"]
    print(
        _m(
            "about_heuristics",
            z_mild=heuristics["z_mild"],
            z_strong=heuristics["z_strong"],
            fdr_q=heuristics["fdr_q"],
            min_chapters=heuristics["min_chapters"],
            n_dimensions=heuristics["n_dimensions"],
            min_comparable_words=heuristics["min_comparable_words"],
            min_comparable_sentences=heuristics["min_comparable_sentences"],
        )
    )
    if data.get("commands"):
        print(_m("about_commands"))
        for command in data["commands"]:
            print(f"  {command['name']:<12} {command['purpose']} [{command['output']}]")
    print(_m("about_license", license=data["license"]))


def _cmd_dialogue(args: argparse.Namespace) -> int:
    """Dialogue turn structure as a Rich table or JSON."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .dialogue import dialogue_report
    from .pipeline import resolve_document_config

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = dialogue_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, dialogue=report.to_dict()), indent=True))
        return EXIT_OK

    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("dlg_metric"), style="bold white")
    summary.add_column(_m("dlg_value"), justify="right", style="cyan")
    for key, value in (
        ("dlg_turns", str(report.turns)),
        ("dlg_dialogue_pct", f"{report.dialogue_pct:.1f} %"),
        ("dlg_avg_turn", f"{report.avg_turn_words:.1f}"),
        ("dlg_median_turn", f"{report.median_turn_words:.0f}"),
        ("dlg_longest_turn", str(report.longest_turn_words)),
        ("dlg_turns_per_1000", f"{report.turns_per_1000:.1f}"),
        ("dlg_paragraph_pct", f"{report.dialogue_paragraph_pct:.1f} %"),
        ("dlg_short_turn_pct", f"{report.short_turn_pct:.1f} % ({report.short_turns})"),
        ("dlg_long_turns", str(report.long_turns)),
        (
            "dlg_voice_contrast",
            f"{report.asl_contrast:+.1f}" if report.asl_contrast is not None else "–",
        ),
        (
            "Dialogue tags",
            (
                f"{report.dialogue_tags} ({report.dialogue_tag_pct:.1f} %, {report.dialogue_tags_per_1000:.1f}/1k)"
                if report.dialogue_tag_available
                else "–"
            ),
        ),
        (
            "Adverbial tags",
            (
                f"{report.adverbial_tags} ({report.adverbial_tag_pct:.1f} %)"
                if report.adverbial_tag_available
                else "–"
            ),
        ),
        (
            "Indirect speech",
            (
                f"{report.indirect_speech} ({report.indirect_speech_per_1000:.1f}/1k)"
                if report.indirect_speech_available
                else "–"
            ),
        ),
        (
            "Voice separation",
            (
                f"{report.voice_separation.separation_label} "
                f"(cos {report.voice_separation.cosine_similarity:.2f}, "
                f"ΔASL {report.voice_separation.asl_delta:+.1f})"
                if report.voice_separation.available
                and report.voice_separation.cosine_similarity is not None
                and report.voice_separation.asl_delta is not None
                else "–"
            ),
        ),
    ):
        label = (_m(key, short_words=config.short_turn_max_words, long_words=config.long_turn_min_words)
                 if key.startswith("dlg_") else key)
        summary.add_row(label, value)
    con.print(summary)

    if report.chapters:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("dlg_chapter"), justify="right")
        table.add_column(_m("dlg_title"))
        table.add_column(_m("dlg_turns"), justify="right")
        table.add_column(_m("dlg_dialogue_pct"), justify="right")
        table.add_column(_m("dlg_avg_turn"), justify="right")
        table.add_column(_m("dlg_longest_turn"), justify="right")
        for chapter in report.chapters:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                str(chapter.turns),
                f"{chapter.dialogue_pct:.1f} %",
                f"{chapter.avg_turn_words:.1f}",
                str(chapter.longest_turn_words),
            )
        con.print(table)
    return EXIT_OK


def _cmd_characters(args: argparse.Namespace) -> int:
    """Curated name mentions and declared POV as a Rich table or JSON."""
    from .characters import presence_report, resolve_character_settings
    from .pipeline import resolve_document_config

    names: list[str] = list(args.name or [])
    if args.names is not None:
        names.extend(part.strip() for part in args.names.split(",") if part.strip())
    try:
        selection = resolve_character_settings(
            names if args.name or args.names is not None else None, args._project_config)
        if not selection.names:
            print(f"{_m('err_prefix')} {_m('err_no_names')}", file=sys.stderr)
            return EXIT_ERROR
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
        config, resolved = resolve_document_config(text, args.language, project_config=args._project_config)
        report = presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
    except (OSError, UnicodeError) as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(_json(_meta_payload(resolved.key, **report), indent=True))
        return EXIT_OK

    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    table.add_column(_m("chr_name"), style="bold white")
    table.add_column(_m("chr_mentions"), justify="right", style="cyan")
    table.add_column(_m("chr_chapters"), justify="right")
    table.add_column(_m("chr_span"))
    table.add_column(_m("chr_gap"), justify="right")
    table.add_column(_m("chr_share"), justify="right")
    if selection.declared_pov:
        table.add_column(_m("chr_pov"))
        table.add_column("POV gap", justify="right")
    for figure in report["figures"]:
        span = (
            f"{figure['first_chapter']}–{figure['last_chapter']}"
            if figure["first_chapter"]
            else "–"
        )
        row = [
            figure["name"],
            str(figure["mentions"]),
            f"{len(figure['chapters_present'])} / {report['chapters']}",
            span,
            str(figure["longest_gap"]),
            f"{figure['presence_ratio'] * 100:.0f} %",
        ]
        if selection.declared_pov:
            row.append(", ".join(str(number) for number in figure.get("declared_pov_chapters", [])) or "–")
            row.append(str(figure.get("pov_longest_gap", "–")))
        table.add_row(*row)
    con.print(table)
    return EXIT_OK


def _cmd_pacing(args: argparse.Namespace) -> int:
    """Scene structure, pacing signals and chapter hooks (Rich table or JSON)."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .corridors import evaluate_genre_corridor, pacing_corridor_observation
    from .pacing import pacing_report
    from .pipeline import resolve_document_config

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = pacing_report(text, config)
    effective_genre = getattr(args, "genre", None) or config.genre_corridor
    corridor_data: dict[str, Any] | None = None
    if effective_genre:
        corridor_data = evaluate_genre_corridor(
            effective_genre, pacing_corridor_observation(report)
        )

    if args.json:
        extra: dict[str, Any] = {"pacing": report.to_dict()}
        if corridor_data is not None:
            extra["genre_corridor"] = corridor_data
        print(_json(_meta_payload(resolved.key, **extra), indent=True))
        return EXIT_OK

    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("pac_metric"), style="bold white")
    summary.add_column(_m("pac_value"), justify="right", style="cyan")
    for key, value in (
        ("pac_chapters", str(report.chapters)),
        ("pac_scenes", str(report.scenes)),
        ("pac_avg_scene", f"{report.avg_scene_words:.0f}"),
        ("pac_hook_mean", f"{report.hook_score_mean:.2f}"),
        ("pac_cohesion", f"{report.sentence_overlap_pct:.1f} %"),
        ("pac_monotony", str(report.repeated_start_runs)),
        (
            "Sticky sentences",
            (
                f"{report.sticky_sentences} ({report.sticky_sentence_pct:.1f} %, mean glue {report.mean_glue_pct:.1f} %)"
                if report.sticky_available
                else "–"
            ),
        ),
        (
            "Rhythm profile",
            (
                f"CV {report.rhythm_profile['asl_cv']:.2f}, "
                f"IQR {report.rhythm_profile['asl_iqr']:.1f}, "
                f"H {report.rhythm_profile['length_entropy']:.2f}"
                if report.rhythm_profile.get("available")
                else "–"
            ),
        ),
        ("pac_fastest", str(report.fastest_chapter or "–")),
        ("pac_slowest", str(report.slowest_chapter or "–")),
    ):
        label = _m(key, min_run=config.monotony_min_run) if key.startswith("pac_") else key
        summary.add_row(label, value)
    con.print(summary)
    if corridor_data is not None:
        corridor_table = Table(
            title=f"Genre Reference Corridor ({corridor_data['label']}, non-prescriptive)",
            box=box.SIMPLE,
            header_style="bold magenta",
        )
        corridor_table.add_column("Metric")
        corridor_table.add_column("Observed", justify="right")
        corridor_table.add_column("Reference Band", justify="right")
        corridor_table.add_column("Position", justify="right")
        for metric_name, entry in corridor_data["metrics"].items():
            obs_str = f"{entry['observed']:.1f}" if entry["observed"] is not None else "–"
            corridor_table.add_row(
                metric_name,
                obs_str,
                f"{entry['low']:.1f}–{entry['high']:.1f}",
                entry["position"],
            )
        con.print(corridor_table)
    if report.scenes_are_chapters and report.chapters:
        con.print(f"[yellow]{_m('pac_no_breaks')}[/yellow]")

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("pac_chapter"), justify="right")
        table.add_column(_m("pac_title"))
        table.add_column(_m("pac_scenes"), justify="right")
        table.add_column(_m("pac_asl"), justify="right")
        table.add_column(_m("pac_sparkline"), justify="center")
        table.add_column(_m("pac_dialogue"), justify="right")
        table.add_column(_m("pac_hook"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                str(chapter.scenes),
                f"{chapter.asl:.1f}",
                chapter.pacing_sparkline or "–",
                f"{chapter.dialogue_pct:.1f} %",
                str(chapter.hook_score),
            )
        con.print(table)
    return EXIT_OK


def _cmd_motifs(args: argparse.Namespace) -> int:
    """Motif presence and repetition signals (Rich tables or JSON)."""
    motifs: dict[str, str] = {}
    for spec in args.motif or []:
        name, separator, pattern = spec.partition("=")
        if not separator or not name.strip() or not pattern.strip():
            print(f"{_m('err_prefix')} {_m('err_motif_spec', spec=spec)}", file=sys.stderr)
            return EXIT_ERROR
        motifs[name.strip()] = pattern.strip()
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .motifs import motif_report
    from .pipeline import resolve_document_config

    try:
        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config,
            **({"motif_regexes": motifs} if args.motif else {}),
        )
        report = motif_report(text, motifs if args.motif else None, config, phrase_size=max(2, args.phrases))
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(_json(_meta_payload(resolved.key, **report.to_dict()), indent=True))
        return EXIT_OK

    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    if report.motifs:
        table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
        table.add_column(_m("mot_name"), style="bold white")
        table.add_column(_m("mot_mentions"), justify="right", style="cyan")
        table.add_column(_m("mot_density"), justify="right")
        table.add_column(_m("mot_span"))
        table.add_column(_m("mot_gap"), justify="right")
        for motif in report.motifs:
            span = f"{motif.first_chapter}–{motif.last_chapter}" if motif.first_chapter else "–"
            table.add_row(
                motif.name,
                str(motif.mentions),
                f"{motif.density_per_1000:.2f}",
                span,
                str(motif.longest_gap),
            )
        con.print(table)

    if report.top_words:
        words = ", ".join(f"{word} ({count})" for word, count in report.top_words)
        con.print(f"[bold]{_m('mot_top_words')}[/bold] {words}")

    from .language_data import UI_LABELS

    labels = UI_LABELS[_lang()]
    if report.repeated_phrases:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("mot_phrase"))
        table.add_column(labels["mot_global_count"], justify="right")
        table.add_column(_m("mot_chapters"))
        for phrase in report.repeated_phrases:
            table.add_row(phrase.phrase, str(phrase.count), ", ".join(map(str, phrase.chapters)))
        con.print(table)

    if report.echoes:
        con.print(f"[bold]{labels['mot_echoes']}[/bold]")
        con.print(labels["mot_echo_note"])
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("mot_phrase"))
        table.add_column(labels["mot_echo_chapter"], justify="right")
        table.add_column(labels["mot_echo_count"], justify="right")
        table.add_column(labels["mot_echo_words"], justify="right")
        for echo in report.echoes:
            table.add_row(echo.term, str(echo.chapter), str(echo.count),
                          f"{echo.first_word}–{echo.last_word}")
        con.print(table)
        con.print(labels["mot_echo_limits"])
    return EXIT_OK


def _cmd_showing(args: argparse.Namespace) -> int:
    """Compare measured cue groups (Rich table or stable showing JSON)."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .pipeline import resolve_document_config
    from .showing import showing_report

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = showing_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, showing=report.to_dict()), indent=True))
        return EXIT_OK

    def signed(value: float | None) -> str:
        # Below the comparability floor no z-score is derived; keep it visible.
        return "–" if value is None else f"{value:+.2f}"

    from rich import box
    from rich.console import Console
    from rich.table import Table

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("show_metric"), style="bold white")
    summary.add_column(_m("show_value"), justify="right", style="cyan")
    summary_rows = [
        ("show_chapters", str(report.chapters)),
        ("show_tell_z", signed(report.tell_z_mean)),
        ("show_show_z", signed(report.show_z_mean)),
        ("show_balance", signed(report.balance_mean)),
    ]
    if report.sensory_density_mean is not None:
        summary_rows.append(("show_sensory", f"{report.sensory_density_mean:.1f}"))
    if report.immersion_ratio_mean is not None:
        summary_rows.append(("show_immersion", f"{report.immersion_ratio_mean:.2f}"))
    summary_rows.extend([
        ("show_most_telling", ", ".join(map(str, report.most_telling))),
        ("show_most_showing", ", ".join(map(str, report.most_showing))),
    ])
    for key, value in summary_rows:
        summary.add_row(_m(key), value)
    con.print(summary)

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("show_chapter"), justify="right")
        table.add_column(_m("show_title"))
        table.add_column(_m("show_tell_z"), justify="right")
        table.add_column(_m("show_show_z"), justify="right")
        table.add_column(_m("show_balance"), justify="right")
        table.add_column(_m("show_sensory"), justify="right")
        table.add_column(_m("show_immersion"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                signed(chapter.tell_z),
                signed(chapter.show_z),
                signed(chapter.balance),
                f"{chapter.sensory_density:.1f}",
                f"{chapter.immersion_ratio:.2f}" if chapter.immersion_ratio is not None else "–",
            )
        con.print(table)
    return EXIT_OK


def _cmd_pdf(args: argparse.Namespace) -> int:
    """Compose one of the PDF layouts from the manuscript or the analysis."""
    from .pdf_document import PdfError
    from .pdf_export import compose_pdf
    from .pdf_layouts import FontChoice

    workspace = args._workspace
    output = args.output or os.path.join(workspace.root, f"{workspace.slug}-{args.layout}.pdf")
    try:
        FileUtils.require_distinct_output(workspace.manuscript, output)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    choice = FontChoice(
        serif=args.serif_font,
        serif_bold=args.bold_font,
        mono=args.mono_font,
        sans=args.sans_font,
        sans_bold=args.sans_bold_font,
        serif_italic=args.italic_font,
        serif_bold_italic=args.bold_italic_font,
    )
    try:
        text = workspace.read_manuscript()
        thresholds = (
            _thresholds_from_args(args, getattr(args, "_project_config", None))
            if args.layout == "report"
            else None
        )
        payload = compose_pdf(
            text,
            manuscript=workspace.manuscript,
            layout=args.layout,
            language=args.language,
            project_config=args._project_config,
            title=args.title,
            author=args.author,
            draft_notice=args.draft_notice,
            thresholds=thresholds,
            choice=choice,
        )
    except (OSError, PdfError, ValueError, RuntimeError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        changed = FileUtils.atomic_write_bytes_if_changed(
            output, payload,
            before_replace=lambda: FileUtils.require_distinct_output(workspace.manuscript, output),
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(_m("pdf_written" if changed else "pdf_unchanged", output=output))
    return EXIT_OK


def _cmd_read_aloud(args: argparse.Namespace) -> int:
    """Create a local manuscript listening copy with a validated project profile."""
    import warnings

    from .speech import render_speech_audio
    from .speech_cache import project_audio_cache
    from .speech_profiles import (
        DEFAULT_PLAYBACK_SPEED,
        AudioProfile,
        parse_audio_settings,
        resolve_audio_profile,
    )
    from .speech_references import SpeechReference, references_for_plan, references_unchanged

    workspace = args._workspace
    args.plan_only = args.plan_only or args.ssml or args.timeline
    preview = args.preview or args.preview_line is not None
    output = args.output or os.path.join(
        workspace.root,
        f"{workspace.slug}-preview.wav" if preview else
        f"{workspace.slug}-chapter-{args.chapter}.wav" if args.chapter is not None else f"{workspace.slug}.wav",
    )
    try:
        FileUtils.require_distinct_output(workspace.manuscript, output)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        raw_audio = args._project_config.get("audio")
        saved_audio = parse_audio_settings(raw_audio, language=args.language) if raw_audio is not None else None
        external_bootstrap = args.engine in EXTERNAL_ENGINES and (
            (saved_audio is None and args.profile in (None, "narrator"))
            or (saved_audio is not None and not saved_audio.profiles and args.profile is None)
        )
        previous_engine = None
        if external_bootstrap:
            # Validate the requested provider directly, without an unrelated native language gate.
            changes = {"engine": args.engine, "language": args.language, "speed": DEFAULT_PLAYBACK_SPEED}
        else:
            profile = resolve_audio_profile(args._project_config, args.profile, language=args.language)
            changes = profile.model_dump()
            previous_engine = profile.engine
        for name, value in (("engine", args.engine),
                            ("voice", args.voice),
                            ("voice_description", args.voice_description),
                            ("reference_id", args.reference_id),
                            ("instructions", args.instructions),
                            ("speed", args.speed),
                            ("base_url", args.base_url),
                            ("model", args.model),
                            ("api_key_env", args.api_key_env),
                            ("supports_instructions", args.supports_instructions),
                            ("language", getattr(args, "_speech_explicit_language", None))):
            if value is not None:
                changes[name] = value
        if args.engine == "qwen3-design" and args.voice is None and previous_engine != "qwen3-design":
            changes["voice"] = "design"
        if args.engine in NATIVE_ENGINES and native_engine(args.engine).reference_required and args.voice is None:
            changes["voice"] = "reference"
        if args.engine == "mlx-audio" and args.reference_id and args.voice is None:
            changes["voice"] = "reference"
        if args.engine in ("coqui", "coqui-reference") and args.voice is None:
            changes["voice"] = "reference" if args.engine == "coqui-reference" else "thorsten"
        if args.engine and args.engine != "qwen3-design" and previous_engine == "qwen3-design" and args.voice_description is None:
            changes.pop("voice_description", None)
        if (args.engine and (args.engine not in NATIVE_ENGINES or not native_engine(args.engine).reference_required)
                and previous_engine is not None and previous_engine in NATIVE_ENGINES and native_engine(previous_engine).reference_required
                and args.reference_id is None):
            changes.pop("reference_id", None)
        if args.engine and args.engine not in EXTERNAL_ENGINES and previous_engine in EXTERNAL_ENGINES:
            for key in ("base_url", "model", "api_key_env", "supports_instructions"):
                if getattr(args, key) is None:
                    changes.pop(key, None)
        if (args.engine == "openai-compatible" and previous_engine not in EXTERNAL_ENGINES
                and args.voice is None):
            raise ValueError("Choose an explicit --voice identifier supported by the external provider")
        reference_engine = ((changes["engine"] in NATIVE_ENGINES
                             and native_engine(changes["engine"]).reference_required)
                            or (changes["engine"] == "mlx-audio"
                                and changes.get("voice") == "reference"))
        if not reference_engine and args.reference_id:
            raise ValueError(_m("audio_reference_wrong_engine"))
        if reference_engine:
            if not changes.get("reference_id"):
                raise ValueError(_m("audio_base_reference_required"))
            if (changes.get("instructions")
                    and changes["engine"] not in ("ims-toucan", "mlx-audio")):
                raise ValueError(_m("audio_base_instructions_inherited" if args.instructions is None
                                    else "audio_base_instructions_explicit"))
        if changes["engine"] == "qwen3-design" and not changes.get("voice_description"):
            raise ValueError(_m("audio_design_description_required"))
        if args.engine == "qwen3" and previous_engine != "qwen3" and args.voice is None:
            raise ValueError(_m("audio_custom_voice_required"))
        profile = AudioProfile.model_validate(changes)
        from .speech_direction import (
            build_speech_plan,
            direction_snapshot,
            direction_state,
            plan_json,
            saved_directions,
        )
        from .speech_export import ssml_export, timeline_json
        text, source_hash = FileUtils.read_source_snapshot(workspace.manuscript)
        view = None if args.no_direction else direction_state(workspace.root, workspace.manuscript, language=profile.language)
        if view is not None and view["source_sha256"] != source_hash:
            raise ValueError("Manuscript changed while preparing speech; retry")
        direction_hash = view["direction_sha256"] if view is not None else None
        references: dict[str, SpeechReference] = {}

        def check_context() -> bool:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", UserWarning)
                    use_explicit, start = args._speech_config_selection
                    current_settings = (read_explicit_project_config(start) if use_explicit
                                        else load_project_config(start))
                valid = (FileUtils.read_source_snapshot(workspace.manuscript)[1] == source_hash
                         and current_settings == args._project_config
                         and (direction_hash is None or direction_snapshot(workspace.root) == direction_hash)
                         and references_unchanged(workspace.root, references))
            except (OSError, ValueError, UserWarning) as exc:
                raise ValueError("Manuscript, settings or speech directions changed or became unreadable; retry") from exc
            if not valid:
                raise ValueError("Manuscript, settings or speech directions changed during rendering; retry")
            return False

        check_context()
        profiles = (saved_audio.profiles if saved_audio is not None else {"narrator": profile}
                    if external_bootstrap else parse_audio_settings(None, language=profile.language).profiles)
        if args.speed is not None:
            profiles = {key: AudioProfile.model_validate({**item.model_dump(), "speed": args.speed})
                        for key, item in profiles.items()}
        plan = build_speech_plan(text, profile,
            directions=saved_directions(view) if view is not None else [], profiles=profiles,
            chapter=args.chapter, project_config=args._project_config, skip_markers=not args.keep_markers,
            for_export=args.plan_only)
        if preview:
            anchors = [row.anchor for row in plan if row.text and row.anchor]
            selected = next((anchor for anchor in anchors if args.preview_line is None or
                             anchor["start_line"] <= args.preview_line <= anchor["end_line"]), None)
            if selected is None:
                raise ValueError("No anchored paragraph or list item found at the selected line or chapter; quote blocks cannot currently be selected for preview")
            plan = [row for row in plan if row.anchor == selected]
            if not args.plan_only and sum(len(row.text) for row in plan) > 6000:
                raise ValueError("Passage preview exceeds 6000 characters; render the chapter")
        if args.plan_only:
            check_context()
            if getattr(args, "ssml", False):
                exported = ssml_export(plan, default_lang=profile.language)
                if args.output:
                    _run_text_report(args, lambda: print(exported["ssml"]) or EXIT_OK)
                else:
                    print(exported["ssml"])
                for warning in exported["warnings"]:
                    print(f"[export] {warning}", file=sys.stderr)
            elif args.timeline:
                timeline = timeline_json(plan)
                timeline["source"] = {"sha256": source_hash, "mode": "preview" if preview else "chapter" if args.chapter else "manuscript",
                                      "chapter": args.chapter}
                text_content = _json(timeline, indent=True)
                if args.output:
                    _run_text_report(args, lambda: print(text_content) or EXIT_OK)
                else:
                    print(text_content)
            else:
                text_content = _json(plan_json(plan), indent=True)
                if args.output:
                    _run_text_report(args, lambda: print(text_content) or EXIT_OK)
                else:
                    print(text_content)
            return EXIT_OK
        references = references_for_plan(workspace.root, plan)
        render_options: dict[str, Any] = {"references": references} if references else {}
        out_path = render_speech_audio(
            manuscript_path=workspace.manuscript,
            output_path=output,
            language=profile.language,
            chapter=args.chapter,
            profile=profile,
            skip_markers=not args.keep_markers,
            cache_dir=project_audio_cache(workspace.root) if not args.no_audio_cache and not preview else None,
            fresh_audio=args.fresh_audio,
            target=args.speech_target,
            plan=plan,
            cancelled=check_context,
            progress=_audio_progress() if args.progress else None,
            **render_options,
        )
        if args.project is not None and args.chapter is not None and not preview and os.path.splitext(out_path)[1].lower() == ".wav":
            from .speech_artifacts import MAX_CHAPTER_AUDIO_BYTES, retain_chapter_audio
            from .speech_references import read_reference_input

            def retained_context() -> bool:
                check_context()
                return True

            try:
                retained_context()
                retain_chapter_audio(workspace.root, read_reference_input(out_path, MAX_CHAPTER_AUDIO_BYTES),
                                     source_sha256=source_hash, chapter=args.chapter, origin="generated",
                                     valid=retained_context)
            except (OSError, ValueError, RuntimeError) as exc:
                raise RuntimeError(f"Audio was written to {out_path}, but chapter retention failed: {exc}") from exc
    except (OSError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(_m("speech_written", output=str(out_path)))
    return EXIT_OK


def _cmd_build(args: argparse.Namespace) -> int:
    """Idempotent workspace build: analyzes the manuscript and publishes artifacts."""
    from .formatters import ReportFormatter
    from .motifs import motif_report
    from .pipeline import analyze_document, resolve_document_config
    from .scenes import scene_report_for_display
    from .ui import render_analysis
    from .ui.manuscript_document import reader_blocks
    from .ui.render_contracts import DashboardContent

    workspace = args._workspace

    try:
        text = workspace.read_manuscript()
        title = _document_title(args, workspace.manuscript, text)
        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    fingerprint = analysis.fingerprint

    artifacts = {
        f"{workspace.slug}_metrics.json": _json(
            _meta_payload(resolved.key, metrics=metrics.model_dump()),
            indent=True,
        )
        + "\n",
        f"{workspace.slug}_profile.json": _json(
            _meta_payload(
                resolved.key,
                chapters=[c.__dict__ for c in chapters],
                paragraphs=[
                    {k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs
                ],
            ),
            indent=True,
        )
        + "\n",
        f"{workspace.slug}_style.json": _json(fingerprint.passport(), indent=True) + "\n",
        f"{workspace.slug}_style_passport.txt": fingerprint.passport_text(
            labels=resolved.labels, language_key=resolved.key
        )
        + "\n",
        f"{workspace.slug}_report.md": ReportFormatter.format_markdown_report(
            metrics, labels=resolved.labels, language_key=resolved.key
        ),
        f"{workspace.slug}_dashboard.html": render_analysis(
            analysis,
            resolved,
            title=title,
            flag_min_severity=fp_thresholds.flag_min_severity,
            content=DashboardContent(
                reader_document=reader_blocks(text, config, analysis.paragraphs),
                motifs=motif_report(text, config=config, _paragraphs=analysis.paragraphs).to_display_dict(),
                scenes=scene_report_for_display(
                    text,
                    config,
                    args._project_config.get("scene_analysis"),
                    premeasured_chapters=metrics.chapters,
                ),
            ),
        ),
    }

    print(_m("build_workspace", root=workspace.root))
    print(
        _m(
            "build_manuscript",
            file=os.path.basename(workspace.manuscript),
            language=resolved.key,
        )
    )
    if not args.dry_run:
        try:
            workspace.ensure_layout()
        except OSError as exc:
            print(
                f"{_m('err_prefix')} {_m('err_build_target', dir=workspace.exports_dir, exc=exc)}",
                file=sys.stderr,
            )
            return EXIT_ERROR
    changed = 0
    for name, content in artifacts.items():
        try:
            is_changed = workspace.publish(name, content, dry_run=args.dry_run)
        except OSError as exc:
            print(
                f"{_m('err_prefix')} {_m('err_build_target', dir=workspace.exports_dir, exc=exc)}",
                file=sys.stderr,
            )
            return EXIT_ERROR
        changed += is_changed
        prefix = "(dry-run) " if args.dry_run else ""
        state = _m("state_written") if is_changed else _m("state_unchanged")
        print(f"  {prefix}{state:<13} exports/{name}")
    unchanged = len(artifacts) - changed
    if args.dry_run:
        print(_m("build_dry_run", changed=changed, unchanged=unchanged))
    else:
        print(_m("build_done", changed=changed, unchanged=unchanged))
    return EXIT_OK


def _cmd_project(args: argparse.Namespace) -> int:
    """Print the same bounded, metadata-only observation used by the native UI."""
    from .format import safe_text
    from .project_structure import inspect_project
    from .workspace_labels import (
        PROJECT_STRUCTURE_ISSUE_LABELS,
        PROJECT_STRUCTURE_ROLE_LABELS,
        PROJECT_STRUCTURE_STATE_LABELS,
        workspace_labels_for,
    )

    try:
        result = inspect_project(getattr(args, "project_path", "."))
    except (OSError, ValueError, RuntimeError) as exc:
        print(safe_text(f"{_m('err_prefix')} {exc}"), file=sys.stderr)
        return EXIT_ERROR
    if args.json:
        print(_json(result, indent=True))
    else:
        labels = workspace_labels_for(_lang())
        def text(key: str) -> str:
            return labels.get(key, key)
        print(text("project_structure_title"))
        print(safe_text(result["root"]))
        for role in result["roles"]:
            name = text(PROJECT_STRUCTURE_ROLE_LABELS[role["role"]])
            state = text(PROJECT_STRUCTURE_STATE_LABELS[role["state"]])
            print(safe_text(f"{name}: {role['path'] or '—'} · {state}"))
        if result["artifacts"]:
            print("\n" + text("project_structure_outputs"))
            for artifact in result["artifacts"]:
                print(safe_text(f"  {artifact['path']} · " + text("project_structure_provenance_unknown")))
        for issue in result["issues"]:
            message = text(PROJECT_STRUCTURE_ISSUE_LABELS[issue["code"]])
            path = f" · {issue['path']}" if issue["path"] is not None else ""
            severity = text("project_structure_issue_" + issue["severity"])
            print(safe_text(f"[{severity}] {message}{path}"))
    return EXIT_ERROR if result["has_errors"] else EXIT_OK


def _positive_chapter(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("Chapter must be a positive number")
    return value


def _scene_identifier(raw: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", raw):
        raise argparse.ArgumentTypeError("Scene must be a chapter:scene ID, for example 1:2")
    return raw


def _select_scenes(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Select output after validation, retaining full-manuscript comparisons."""
    if args.chapter is None and args.scene is None and not args.latest:
        return report
    if args.chapter is not None and args.scene is not None and int(args.scene.split(":")[0]) != args.chapter:
        raise ValueError("--chapter must match the chapter in --scene")

    def matches(item: dict[str, Any]) -> bool:
        return ((args.chapter is None or item["chapter"] == args.chapter)
                and (args.scene is None or item["id"] == args.scene))

    items = [item for item in report["items"] if matches(item)]
    planned = [item for item in report.get("planned_items", []) if matches(item)]
    if args.latest:
        items = items[-1:]
        planned = []
    if not items and not planned:
        kind = "measured scene" if args.latest else "measured or planned scene"
        raise ValueError(f"No {kind} matches the requested selection; use the chapter:scene IDs from scenes")
    selection = {
        "chapter": args.chapter, "scene": args.scene, "latest": args.latest,
        "selected_count": len(items), "total_count": len(report["items"]),
        "reference_scope": "full_manuscript",
    }
    selected = {**report, "items": items, "selection": selection}
    if "planned_items" in report:
        selected["planned_items"] = planned
        selection.update(selected_planned_count=len(planned), total_planned_count=len(report["planned_items"]))
    return selected


def _threshold_number(key: str) -> Callable[[str], float]:
    def parse(raw: str) -> float:
        from .style_fingerprint import FingerprintThresholds

        try:
            value = float(raw)
            FingerprintThresholds.numeric_inputs[key].validate(key, value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc
        return value

    return parse


def _add_threshold_arguments(parser: argparse.ArgumentParser) -> None:
    """Use the backend's defaults and bounds for CLI help and scalar validation."""
    from .style_fingerprint import FingerprintThresholds

    defaults = FingerprintThresholds()
    parser.add_argument(
        "--preset", choices=FingerprintThresholds.presets, default=None,
        help=(
            "Editorial review preset: balanced (built-in default), "
            "developmental (macro chapter shifts), line_editing (close prose pass), "
            "or conservative_by (arbitrary-dependence FDR); explicit threshold flags override preset values"
        ),
    )
    for key, flag, description in (
        ("z_mild", "--z-mild", "Notable |z*| threshold"),
        ("z_strong", "--z-strong", "Strong |z*| threshold"),
        ("fdr_q", "--fdr-q", "Nominal q for the selected FDR method"),
        ("dim_score_threshold", "--dim-threshold", "Per-axis |score| cutoff in standardized midrank PCA space"),
    ):
        policy = FingerprintThresholds.numeric_inputs[key]
        bounds = f"{'>' if policy.minimum_exclusive else '>='} {policy.minimum:g}"
        if policy.maximum is not None:
            bounds += f" and {'<' if policy.maximum_exclusive else '<='} {policy.maximum:g}"
        parser.add_argument(
            flag, type=_threshold_number(key), default=None,
            help=f"{description}; finite, {bounds} (built-in default: {getattr(defaults, key)}; project may override)",
        )
    parser.add_argument(
        "--fdr-method", choices=FingerprintThresholds.fdr_methods, default=None,
        help=f"FDR method: bh (Benjamini-Hochberg) or by (Benjamini-Yekutieli); built-in default: {defaults.fdr_method}; project may override",
    )
    parser.add_argument(
        "--flag-min-severity", type=int, choices=FingerprintThresholds.flag_severities, default=None,
        help=f"Minimum paragraph severity for flags panel (built-in default: {defaults.flag_min_severity}; project may override)",
    )


def _run_text_report(args: argparse.Namespace, render: Callable[[], int], *, source_file: str | None = None) -> int:
    """Write successful report data atomically, leaving diagnostics on stderr."""
    output = getattr(args, "output", None)
    source = source_file or getattr(args, "file", None) or getattr(args, "audio", None)
    try:
        if output is None:
            return render()
        if source:
            FileUtils.require_distinct_output(source, output)
        with StringIO() as captured, redirect_stdout(captured):
            status = render()
            content = captured.getvalue()
        if status != EXIT_OK:
            return status
        FileUtils.atomic_write_if_changed(
            output, content,
            before_replace=(lambda: FileUtils.require_distinct_output(source, output)) if source else None,
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def _cmd_analysis_report(
    args: argparse.Namespace, text: str, config: CorpusConfig, resolved: ResolvedLanguage,
) -> int:
    """Render the shared document analysis reports without choosing a destination."""
    from .analyzer import CorpusAnalyzer
    from .formatters import ReportFormatter
    from .paragraph_evidence import ParagraphEvidence, available_paragraph_layers
    from .pipeline import fingerprint_document, profile_document
    from .style_fingerprint import paragraph_layer_projection, prepare_paragraph_layer
    if args.command == "scenes":
        from .api import scenes

        try:
            report = scenes(text, resolved.key, project_config=args._project_config)
            report["scenes"] = _select_scenes(report["scenes"], args)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(report, indent=True))
        else:
            from .diversity import MIN_TOKENS_LD
            from .format import num, safe_text
            from .style_fingerprint import FEATURE_UNITS, FEATURES

            labels = resolved.labels
            units = FEATURE_UNITS.get(resolved.key, {})
            scene_report = report["scenes"]
            limits = scene_report["quote_block_limits"]
            half_limits = scene_report["within_scene_limits"]
            short_limit, long_limit = limits["short_max_words"], limits["long_min_words"]

            def whole(value: int) -> str:
                return num(value, resolved.key, 0)

            medium_range = (
                "—" if short_limit + 1 == long_limit
                else whole(short_limit + 1) if short_limit + 2 == long_limit
                else f"{whole(short_limit + 1)}–{whole(long_limit - 1)}"
            )
            quote_ranges = {"short": f"≤{whole(short_limit)}", "medium": medium_range,
                            "long": f"≥{whole(long_limit)}"}
            for item in scene_report["items"]:
                group = item["group"] or labels["scene_unassigned"]
                print(safe_text(f"{item['id']} · {item['chapter_title']} · {group}"))
                print(
                    f"  {whole(item['words'])} {labels['words']} · "
                    f"{whole(item['sentences'])} {labels['sentences']}"
                )
                print(
                    f"  L1 · {labels['scene_half_comparison']} · "
                    f"{labels['scene_dynamic_' + item['scene_dynamic']]}"
                )
                if item["within_scene"] is not None:
                    asl = num(item["asl_shift"], resolved.key, 2, signed=True)
                    dialogue = num(item["dialogue_shift"], resolved.key, 2, signed=True)
                    samples = {
                        f"{half}_{key}": whole(value)
                        for half, counts in item["within_scene"].items()
                        for key, value in counts.items()
                    }
                    print(f"    {labels['scene_half_asl'].format(delta=asl)}")
                    print(f"    {labels['scene_half_dialogue'].format(delta=dialogue)}")
                    print(f"    {labels['scene_half_samples'].format(**samples)}")
                quote_blocks = item["quote_blocks"]
                quote_bins = " · ".join(
                    f"{labels['scene_block_' + key]} ({range_text}): {whole(quote_blocks[key])}"
                    for key, range_text in quote_ranges.items()
                )
                print(f"  L2 · {labels['scene_quote_lengths']} · {quote_bins}")
                if quote_blocks["unresolved_ranges"]:
                    print(f"    {labels['scene_quote_unresolved']}")
                print(
                    f"  {labels['scene_filter_per_1000']}: {num(item['filter_per_1000'], resolved.key, 2)} · "
                    f"{labels['scene_sensory_per_1000']}: {num(item['sensory_per_1000'], resolved.key, 2)}"
                )
                for field, label_key, unit in FEATURES:
                    value = item["features"][field] if field != "asl" or item["sentences"] else None
                    target = item["targets"].get(field)
                    detail = ""
                    if target:
                        lower = (
                            "…"
                            if target["lower"] is None
                            else num(target["lower"], resolved.key, 2)
                        )
                        upper = (
                            "…"
                            if target["upper"] is None
                            else num(target["upper"], resolved.key, 2)
                        )
                        position = target["position"] if value is not None else "unavailable"
                        detail = f" · {labels['scene_' + position]} [{lower} – {upper}]"
                    rendered = "—" if value is None else num(value, resolved.key, 2)
                    level_prefix = "L0 · " if field in {"asl", "dialog_pct"} else ""
                    print(
                        f"  {level_prefix}{labels.get(label_key, field)}: {rendered} {units.get(field, unit)}{detail}"
                    )
            plateaus = scene_report.get("pacing_plateaus", [])
            if plateaus:
                for p in plateaus:
                    print(safe_text(
                        f"  {labels['scene_pacing_plateaus']} · {p['start_id']}–{p['end_id']} · "
                        f"{whole(p['scene_count'])} · {labels['scene_mean_words']}: "
                        f"{num(p['mean_asl'], resolved.key, 2)} · {labels['scene_plateau_' + p['reason']]}"
                    ))
            planned_items = scene_report.get("planned_items", [])
            if planned_items:
                print(labels["scene_planned"])
                for item in planned_items:
                    print(safe_text(f"  {item['id']} · {item['group']}"))
                print(labels["scene_planned_note"])
            if scene_report["items"]:
                print(labels["scene_half_rule"].format(
                    words=whole(half_limits["min_words"]), sentences=whole(half_limits["min_sentences"]),
                ))
                print(labels["scene_quote_lengths_help"])
            print(labels["scene_guidance"])
            print(labels["scene_support"].replace("{min_tokens}", str(MIN_TOKENS_LD)))
        return EXIT_OK

    if args.command == "canvas":
        from .api import scenes
        from .canvas import export_scenes_canvas

        try:
            report = scenes(text, resolved.key, project_config=args._project_config)
            canvas_obj = export_scenes_canvas(report["scenes"])
            print(canvas_obj.to_json())
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
        if args.json:
            payload = _meta_payload(resolved.key, metrics=metrics.model_dump())
            print(_json(payload))
        else:
            ReportFormatter.print_rich_report(metrics, language_key=resolved.key)
        return EXIT_OK

    if args.command == "profile":
        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        evidence: dict[int, ParagraphEvidence] | None = {} if args.evidence else None
        paragraphs, chapters = profile_document(text, config, fp_thresholds, evidence=evidence)
        if args.layer is not None:
            measurement_available = args.layer in available_paragraph_layers(resolved, config=config)
            measurements = prepare_paragraph_layer(paragraphs, args.layer) if measurement_available else {}
            payload = _meta_payload(
                resolved.key,
                **paragraph_layer_projection(paragraphs, args.layer, only_notable=args.only_notable,
                                             measurements=measurements),
            )
            payload["meta"]["schema_version"] = "paragraph-layer/1"
            if evidence is not None:
                payload["meta"]["schema_version"] = "paragraph-layer-evidence/1"
                for row in payload["paragraphs"]:
                    row["evidence"] = evidence[row["index"]]
            if args.json:
                print(_json(payload, indent=True))
            else:
                _print_paragraph_layer(payload, args.file, resolved.key, resolved.labels,
                                       paragraphs=paragraphs, measurements=measurements,
                                       measurement_available=measurement_available)
            return EXIT_OK
        payload = _meta_payload(
            resolved.key,
            chapters=[c.__dict__ for c in chapters],
            paragraphs=[{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
        )
        print(_json(payload, indent=True))
        return EXIT_OK

    if args.command == "style":
        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        fingerprint = fingerprint_document(text, config, fp_thresholds)
        if args.json:
            print(_json(fingerprint.passport(), indent=True))
        else:
            print(fingerprint.passport_text(labels=resolved.labels, language_key=resolved.key))
        return EXIT_OK

    raise ValueError("Unknown textual analysis report")


def _build_parser(only_command: str | None = None) -> argparse.ArgumentParser:
    """Build help and grammar without loading a project or dispatching commands.

    When ``only_command`` names one registered command (or ``"__top__"`` for
    top-level help), sibling subcommands still register their name, group and
    summary for help formatting, while skipping their heavy option imports.
    """
    from .cli_help import AUDIO_OPTION_HELP, GroupedHelpFormatter, finish_command_help

    parser = argparse.ArgumentParser(
        prog="lixity",
        description=(
            "Read and analyze manuscripts, maintain research, and prepare reading "
            "or audio exports. Measurements support human review; they do not grade prose."
        ),
        epilog=(
            "Open the local app:  lixity service start --open\n"
            "Read a report:      lixity analyze manuscript.md --language en\n"
            "Inspect commands:   lixity COMMAND --help  |  lixity about --json\n"
            f"Manuals: {docs_url('README.md')}\n"
            "Help is in English. LIXITY_LANG=de selects report/message language;\n"
            "--language selects manuscript analysis language (default: project setting or en)."
        ),
        formatter_class=GroupedHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"lixity {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND", title="Commands")

    for name, help_text in _COMMANDS:
        if only_command is not None and name != only_command:
            sub.add_parser(name, help=help_text, description=help_text)
            continue
        if name == "research":
            from .research.cli import configure as configure_research

            configure_research(sub.add_parser(name, help=help_text))
            continue
        if name == "service":
            from .service import configure as configure_service

            configure_service(sub.add_parser(name, help=help_text))
            continue
        p = sub.add_parser(name, help=help_text, description=help_text)
        if name == "mcp":
            continue
        if name == "project-backup":
            p.add_argument("--project", required=True)
            p.add_argument("--manuscript", required=True, help="Project-relative manuscript file")
            p.add_argument("--settings", action="append", default=[], help="Root settings file; repeatable")
            p.add_argument("--attachment", action="append", default=[], help="Selected project-relative file; repeatable")
            p.add_argument("--output", required=True, help="New bundle directory outside project")
            continue
        if name == "project-restore":
            p.add_argument("--from", dest="bundle", required=True)
            p.add_argument("--to", dest="target", required=True)
            continue
        if name in ("audio-inspect", "audio-verify"):
            p.add_argument("audio", help="WAV, FLAC or MP3 audio file (read-only)")
            p.add_argument("--plan", required=name == "audio-verify", help="Exported JSON direction timeline")
            p.add_argument("--transcript", help="Timestamped lixity-audio-transcript/1 JSON tied to this audio SHA-256")
            p.add_argument("--language", default="en", help="Explicit tokenization language (default: en)")
            p.add_argument("--json", action="store_true", help="JSON output (also the default)")
            continue
        if name == "audio-transcribe":
            from .speech_transcription import DEFAULT_BASE_URL, DEFAULT_MODEL
            p.add_argument("audio", help="WAV, FLAC or MP3 audio file sent to the explicit service")
            p.add_argument("--base-url", default=DEFAULT_BASE_URL,
                           help="MLX-Audio OpenAI-compatible base URL (default: local service)")
            p.add_argument("--model", default=DEFAULT_MODEL, help="MLX-Audio transcription model")
            p.add_argument("--language", default=None, help="Optional explicit transcription language code")
            p.add_argument("-o", "--output", help="Write transcription JSON atomically")
            continue
        if name == "audio-import-transcript":
            p.add_argument("audio", help="Reference WAV, FLAC or MP3 file for SHA-256 binding")
            p.add_argument("transcript", help=AUDIO_OPTION_HELP[name]['transcript'])
            p.add_argument("-o", "--output", help=AUDIO_OPTION_HELP[name]['--output'])
            p.add_argument("--model", help=AUDIO_OPTION_HELP[name]['--model'])
            p.add_argument("--language", default="en", help="Explicit tokenization language (default: en)")
            continue
        if name == "audio-status":
            p.add_argument("--project", help="Explicit project root; omit to inspect workers only")
            p.add_argument("--engine", choices=(*NATIVE_ENGINES, *EXTERNAL_ENGINES), help="Compare this model variant instead of the selected profile")
            p.add_argument("--json", action="store_true", help="Machine-readable status")
            continue
        if name == "audio-microphone":
            p.add_argument("action", nargs="?", default="status", choices=("status", "set", "devices", "calibrate"), help=AUDIO_OPTION_HELP[name]['action'])
            p.add_argument("--gain", type=int, default=None, help=AUDIO_OPTION_HELP[name]['--gain'])
            p.add_argument("--device", default=None, help=AUDIO_OPTION_HELP[name]['--device'])
            p.add_argument("--card", default=1, help=AUDIO_OPTION_HELP[name]['--card'])
            p.add_argument("--control", default="Mic", help=AUDIO_OPTION_HELP[name]['--control'])
            p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
            continue
        if name == "audio-calibrate":
            p.add_argument("--gain", type=int, default=None, help=AUDIO_OPTION_HELP[name]['--gain'])
            p.add_argument("--duration", type=float, default=8.0, help=AUDIO_OPTION_HELP[name]['--duration'])
            p.add_argument("--countdown", type=float, default=4.0, help="Prep countdown delay in seconds (default: 4.0)")
            p.add_argument("--device", default=None, help=AUDIO_OPTION_HELP[name]['--device'])
            p.add_argument("--json", action="store_true", help="Machine-readable JSON calibration result")
            continue
        if name == "audio-import":
            from .speech_artifacts_cli import configure
            configure(p)
            continue
        if name == "audio-reference":
            p.add_argument("action", choices=("create", "inspect", "record", "generate", "calibration-text"))
            p.add_argument("--project", default=None, help=AUDIO_OPTION_HELP[name]['--project'])
            p.add_argument("--audio", help=AUDIO_OPTION_HELP[name]['--audio'])
            p.add_argument("--transcript-file", help=AUDIO_OPTION_HELP[name]['--transcript-file'])
            p.add_argument("--transcript", default=None, help="record/generate: exact inline transcript text")
            p.add_argument("--reference-id", help="inspect: saved reference identity to measure")
            p.add_argument("--duration", type=float, default=15.0, help=AUDIO_OPTION_HELP[name]['--duration'])
            p.add_argument("--gain", type=int, default=None, help=AUDIO_OPTION_HELP[name]['--gain'])
            p.add_argument("--device", default=None, help="record: hardware capture device")
            p.add_argument("--calibration-text", action="store_true", help="record: read the standard phonetically balanced calibration text")
            p.add_argument("--variant", choices=("phonetic", "short"), default="phonetic", help=AUDIO_OPTION_HELP[name]['--variant'])
            p.add_argument("--language", default="de", choices=("de", "en"), help=AUDIO_OPTION_HELP[name]['--language'])
            p.add_argument("--voice-description", default=None, help="generate: description of the voice to synthesize")
            p.add_argument("-o", "--output", help=AUDIO_OPTION_HELP[name]['--output'])
            continue
        if name == "audio-direction":
            from .speech_direction_cli import configure
            p.epilog = None
            configure(p)
            continue
        if name == "audio-migrate":
            p.add_argument("--project", required=True, help="Explicit project root")
            schemas = p.add_mutually_exclusive_group()
            schemas.add_argument("--to-schema-3", action="store_true", help="Prepare a backed-up upgrade for Coqui profiles")
            schemas.add_argument("--to-schema-4", action="store_true", help="Prepare a backed-up upgrade for external speech providers")
            schemas.add_argument("--to-schema-5", action="store_true", help="Prepare a backed-up upgrade for phonetics and structured prosody")
            p.add_argument("--replace", action="append", default=[], metavar="PROFILE=VOICE",
                           help=AUDIO_OPTION_HELP[name]['--replace'])
            p.add_argument("--instructions", action="append", default=[], metavar="PROFILE=TEXT",
                           help=AUDIO_OPTION_HELP[name]['--instructions'])
            p.add_argument("--apply", action="store_true", help="Apply the reviewed candidate; default only previews")
            p.add_argument("--backup", help=AUDIO_OPTION_HELP[name]['--backup'])
            p.add_argument("--expected-snapshot", help=AUDIO_OPTION_HELP[name]['--expected-snapshot'])
            continue
        if name == "analysis-review":
            p.add_argument("--project", required=True, help="Explicit project root")
            p.add_argument("--manuscript", help="Manuscript within project (default: configured manuscript)")
            p.add_argument("--language", default=None, help="Explicit analysis language; default: project setting or en")
            p.add_argument("--tense-model", default=None, help="Explicit installed local syntax model; no download or fallback")
            p.add_argument("--tense-scope", choices=("all", "narration"), default=None,
                           help="Grammatical tense scope: all predicates or outside recognized quotations")
            p.add_argument("--json", action="store_true", help="Complete versioned observation and review identities")
            p.add_argument("--observation", help="Exact observation ID from a current read")
            p.add_argument("--status", choices=("kept", "changed", "later"), help="Your decision, never a verified text edit")
            for name_part in ("source", "analysis", "review"):
                p.add_argument("--expected-" + name_part + "-sha256", help="Reviewed exact identity required for saving")
            p.epilog = ("Reads write nothing. To save, supply --observation, --status and all three reviewed "
                        "--expected-*-sha256 values. Decisions live in .lixity/analysis-review.json, not manuscript prose. "
                        "Changed text or analysis makes prior decisions stale; deferred items stay open.")
            continue
        if name == "project":
            selector = p.add_mutually_exclusive_group()
            selector.add_argument("project_path", nargs="?", default=argparse.SUPPRESS,
                                  help="Explicit project folder (default: current directory)")
            selector.add_argument("--project", dest="project_path", default=argparse.SUPPRESS,
                                  metavar="PATH", help="Explicit project folder (same as positional)")
            p.add_argument("--json", action="store_true", help="Metadata observation and structural findings as JSON")
            p.epilog = ("Reads only the selected root and bounded export metadata. No files are moved, "
                        "created or repaired; research integrity and output freshness are not inferred. "
                        "Exit 1 indicates structural errors or an unavailable project. "
                        "Example: lixity project --project ./novel --json")
            continue
        if name == "doctor":
            p.add_argument("--json", action="store_true", help="Machine-readable installation diagnostics")
            p.add_argument("--port", type=int, default=None, help=f"Service port (default: LIXITY_PORT or {DEFAULT_PORT})")
            continue
        if name == "export-site":
            from .site_contracts import SITE_MODES

            p.add_argument("file", nargs="?", help="Manuscript inside the selected project (default: project manuscript)")
            p.add_argument("--project", required=True, metavar="PATH", help="Explicit project root")
            p.add_argument("-o", "--output", help="A new directory for the reading website; existing paths are never overwritten")
            p.add_argument("--preflight", action="store_true", help="Measure the prepared package without writing it; omit --output")
            p.add_argument("--language", default=None, help="Analysis language (default: project language or en)")
            p.add_argument("--include-research", action="store_true", help="Review mode only: include authored research, revision history, cited excerpts and manuscript links")
            p.add_argument("--include-source-files", action="store_true", help="Include selected source files with redistribution permission; review mode also requires --include-research")
            p.add_argument("--include-audio", action="store_true", help="Reader mode: include saved chapter WAVs matching the current manuscript, within the chapter cap; never synthesize")
            p.add_argument("--mode", choices=SITE_MODES, default="review", help="review (default): author workspace; reader: curated novel; companion: notes without novel text")
            p.add_argument("--publication-profile", metavar="NAME", help="Required in reader/companion mode: root-local site_publications profile")
            p.add_argument("--max-chapter", type=int, metavar="N", help="Reader/companion only: last included chapter (0 or higher); later content/assets are omitted")
            p.add_argument("--analysis", action="append", choices=("chapters", "language", "full", "all"),
                           help="Reader only: disclose chapters/language (each once), or full alone (all is an alias); default none")
            p.add_argument("--json", action="store_true", help="JSON output: preflight report with --preflight, export manifest otherwise")
            p.epilog = (
                "Creates a portable read-only snapshot, not an authenticated website or backup. "
                "Open index.html locally or serve the exported directory with static hosting. "
                "Review all included content before sharing; copying cannot be prevented. "
                "Exporting does not publish, upload or change the source project."
            )
            continue
        if name not in ("serve", "completion", "about", "schema"):
            p.add_argument("--project", metavar="PATH",
                           help="Select an explicit project root; relative manuscript files resolve inside it; settings are root-local (no user or ancestor configuration)")
        if name in ("analyze", "profile", "style", "dashboard", "serve", "build", "scenes"):
            p.add_argument("--tense-model", default=None,
                           help="Explicit installed local syntax model for grammatical verb groups (no download/fallback)")
            p.add_argument("--tense-scope", choices=("all", "narration"), default=None,
                           help="Grammatical tense scope: all predicates or outside recognized quotations")
        if name == "style":
            p.epilog = (
                "Dimensions compare complete chapters using standardized midranks. "
                "Text output explains coverage, chapter scores and signed loadings; "
                "JSON dimension_diagnostics reports support and unavailable-data reasons. "
                "The per-axis cutoff box is not a confidence region or a literary-quality target."
            )
        if name == "completion":
            p.add_argument(
                "shell",
                nargs="?",
                default="bash",
                choices=("bash", "zsh", "sh"),
                help="Target shell (default: bash)",
            )
            continue
        if name in ("about", "schema"):
            p.add_argument(
                "--json", action="store_true",
                help="JSON output" if name == "about" else "Tool metadata as JSON (default; same as about --json)",
            )
            p.add_argument(
                "--section", choices=ABOUT_SECTIONS,
                help="Return one metadata section as JSON, retaining version metadata",
            )
            continue
        if name == "scenes":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: selected workspace manuscript)")
            p.add_argument(
                "--language", default=None, help="Language profile (default: project setting or en)"
            )
            p.add_argument("--json", action="store_true", help="JSON output (scene schema v1)")
            p.add_argument("-o", "--output", help="Write report text or JSON to a file instead of stdout")
            p.add_argument("--chapter", type=_positive_chapter, metavar="N",
                           help="Select a canonical chapter number; comparisons retain the full manuscript")
            scene_selector = p.add_mutually_exclusive_group()
            scene_selector.add_argument("--scene", type=_scene_identifier, metavar="CHAPTER:SCENE",
                                        help="Select an exact measured or planned scene ID; --chapter must agree when supplied")
            scene_selector.add_argument("--latest", action="store_true",
                                        help="Last measured scene in document order, optionally within --chapter (not modification time)")
            continue
        if name == "pacing":
            from .corridors import GENRE_CORRIDOR_KEYS

            p.add_argument(
                "--genre",
                choices=GENRE_CORRIDOR_KEYS,
                default=None,
                help="Optional non-prescriptive genre reference corridor for descriptive orientation",
            )
        if name == "canvas":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: selected workspace manuscript)")
            p.add_argument(
                "--language", default=None, help="Language profile (default: project setting or en)"
            )
            p.add_argument("-o", "--output", help="Write .canvas file to a path instead of stdout")
            continue
        if name == "diff":
            p.add_argument("base", help="Base manuscript file (or single manuscript for recorded revisions)")
            p.add_argument("target", nargs="?", help="Target manuscript file (omit to diff recorded revisions)")
            p.add_argument("--base-rev", default=None, help="Base revision SHA-256 when diffing recorded revisions")
            p.add_argument("--target-rev", default=None, help="Target revision SHA-256 when diffing recorded revisions")
            p.add_argument("--language", default=None, help="Explicit tokenization language (default: project setting or en)")
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name in ("style", "dashboard", "serve", "build"):
            p.add_argument(
                "--min-chapters",
                type=int,
                default=None,
                help="Minimum usable chapters for a style baseline (project override; built-in default: 2)",
            )
        if name not in ("motifs", "characters", "read-aloud", "audio-export-plan"):
            _add_threshold_arguments(p)
        if name == "build":
            p.epilog = (
                "Writes metrics, paragraph profile and style JSON, a style passport, "
                "a Markdown report and an HTML dashboard under the project's exports/ "
                "folder. Changed artifacts are archived; identical content is not "
                "rewritten. Use --dry-run to inspect planned paths without writing. "
                "This does not switch a running app's project."
            )
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: configured manuscript or folder discovery)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: project setting or en; auto requests detection)"
            )
            p.add_argument("--dry-run", action="store_true", help="Show planned artifacts only")
            continue
        if name == "motifs":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--motif",
                action="append",
                default=[],
                help="Motif as NAME=REGEX (repeatable)",
            )
            p.add_argument("--phrases", type=int, default=3, help="Phrase size (default 3)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: project setting or en; auto requests detection)"
            )
            p.add_argument("--json", action="store_true", help="JSON output")
            p.add_argument("-o", "--output", help="Write report text or JSON to a file instead of stdout")
            continue
        if name == "characters":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--name",
                action="append",
                default=[],
                help="Figure name or alias regex (repeatable; overrides project selection)",
            )
            p.add_argument("--names", help="Comma-separated names; omitted uses project characters or legacy names")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: project setting or en; auto requests detection)"
            )
            p.add_argument("--json", action="store_true", help="JSON output")
            p.add_argument("-o", "--output", help="Write report text or JSON to a file instead of stdout")
            continue
        if name == "dashboard":
            p.description = "Generate a self-contained offline HTML report containing manuscript text, measurements and work-marker notes."
            p.epilog = (
                "Open the written HTML file in your browser. It embeds manuscript "
                "text and notes: review it before sharing. Project changes and "
                "research writes require the local app: lixity service start --open."
            )
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: project setting or en; auto requests detection)"
            )
            p.add_argument("--names", help="Comma-separated figure names (character panel)")
            p.add_argument("-o", "--output", help="HTML target file (default: lixity-dashboard.html)")
            continue
        if name in ("read-aloud", "audio-export-plan"):
            p.epilog = None
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: configured manuscript or folder discovery)")
            p.add_argument("-o", "--output", help=AUDIO_OPTION_HELP[name]['--output'])
            p.add_argument("--chapter", type=int, default=None, help=AUDIO_OPTION_HELP[name]['--chapter'])
            p.add_argument("--language", default=None, help=AUDIO_OPTION_HELP[name]['--language'])
            p.add_argument("--profile", default=None, help="Saved project audio profile (default: selected project profile)")
            p.add_argument("--plan-only", action="store_true", help=AUDIO_OPTION_HELP[name]['--plan-only'])
            exports = p.add_mutually_exclusive_group()
            exports.add_argument("--ssml", action="store_true", help="Export W3C SSML; implies --plan-only; unsupported controls are reported on stderr")
            exports.add_argument("--timeline", action="store_true", help="Export a lossless direction timeline as JSON; implies --plan-only")
            p.add_argument("--base-url", help="Explicit OpenAI-compatible service URL; only contacted when rendering")
            p.add_argument("--model", help="External provider model identifier")
            p.add_argument("--api-key-env", help="Environment variable containing the provider credential (never the credential itself)")
            p.add_argument("--supports-instructions", action="store_true", default=None, help="Declare that this external provider accepts delivery instructions")
            previews = p.add_mutually_exclusive_group()
            previews.add_argument("--preview", action="store_true", help="Preview the first anchored paragraph or list item")
            previews.add_argument("--preview-line", type=int, help="Preview the anchored paragraph or list item containing this source line")
            p.add_argument("--progress", action="store_true", help="Report segment progress and estimated remaining time to stderr")
            p.add_argument("--no-direction", action="store_true", help="Ignore saved passage direction, range voice assignments and pauses for this invocation")
            p.add_argument("--instructions", default=None, help="Delivery instructions for this invocation; selected engine must support free-text direction")
            p.add_argument("--engine", choices=(*NATIVE_ENGINES, *EXTERNAL_ENGINES), default=None, help=AUDIO_OPTION_HELP[name]['--engine'])
            p.add_argument("--voice-description", default=None, help="VoiceDesign voice description")
            p.add_argument("--reference-id", default=None, help="Project-local saved voice reference identity")
            p.add_argument("--voice", default=None, help=AUDIO_OPTION_HELP[name]['--voice'])
            p.add_argument("--speed", type=float, default=None, help="Override all profile tempo factors for this render (0.5–2.0; FFmpeg required unless 1.0)")
            p.add_argument("--speech-target", choices=("local", "jetson"), default="local", help=AUDIO_OPTION_HELP[name]['--speech-target'])
            p.add_argument("--no-audio-cache", action="store_true", help="Render without reading or retaining reusable audio segments")
            p.add_argument("--fresh-audio", action="store_true", help=AUDIO_OPTION_HELP[name]['--fresh-audio'])
            p.add_argument("--keep-markers", action="store_true", help="Read editorial markers aloud instead of omitting them")
            if name == "audio-export-plan":
                p.set_defaults(plan_only=True, timeline=True)
            continue
        if name == "serve":
            p.epilog = (
                "Keeps the server in this terminal; Ctrl+C stops it. Use "
                "--no-project to start an empty workspace. For the managed app, "
                "use lixity service start --open; service stop only manages "
                "instances created by that controller."
            )
            p.add_argument("--_service-token", help=argparse.SUPPRESS)
            p.add_argument("--_desktop-mode", action="store_true", help=argparse.SUPPRESS)
            p.add_argument(
                "path",
                nargs="?",
                default=None,
                help="Manuscript file or workspace folder (default: LIXITY_DIR or current folder)",
            )
            p.add_argument(
                "--host", default=DEFAULT_HOST, help=f"Bind address (default: {DEFAULT_HOST})"
            )
            p.add_argument(
                "--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})"
            )
            p.add_argument(
                "--language",
                default=None,
                help="Language profile (default: project setting or en; auto is explicit)",
            )
            p.add_argument("--title", default=None, help="Dashboard title (default: filename)")
            p.add_argument("--open", action="store_true", help="Open dashboard in browser")
            p.add_argument(
                "--no-project",
                action="store_true",
                help="Start without preloading a project",
            )
            p.add_argument(
                "--research-project",
                "--research-dir",
                dest="research_project",
                default=None,
                help="Explicit research project root for evidence management",
            )
            p.add_argument(
                "--debug",
                action="store_true",
                help="Enable verbose request logging, stack traces, and browser devtools debugging",
            )
            continue
        p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
        p.add_argument(
            "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: project setting or en; auto requests detection)"
        )
        p.add_argument(
            "--json", action="store_true", help=argparse.SUPPRESS if name == "pdf" else "JSON output"
        )
        if name == "profile":
            p.formatter_class = argparse.RawDescriptionHelpFormatter
            p.epilog = (
                "Start with one question, such as sentence rhythm:\n"
                "  lixity profile manuscript.md --language en --layer asl --only-notable\n"
                "Then inspect the counted text:\n"
                "  lixity profile manuscript.md --language en --layer asl --only-notable --evidence\n\n"
                "ASL means words per sentence. Read the reported source lines before deciding.\n"
                "Paragraph comparisons use the same chapter, not the manuscript-wide chapter baseline.\n"
                "Notable means a descriptive difference, not an error or quality verdict.\n"
                "Unavailable comparison is not a measured zero. English is the default;\n"
                "choose the manuscript language explicitly. Add --json for structured output."
            )
            p.add_argument(
                "--layer", choices=tuple(LAYER_FEATURES),
                help="Inspect one paragraph metric and its within-chapter comparison (text; --json for paragraph-layer/1)",
            )
            p.add_argument(
                "--only-notable", action="store_true",
                help="With --layer, show only notable paragraphs; retain the full chapter reference",
            )
            p.add_argument(
                "--evidence", action="store_true",
                help="With --layer, include literal counted spans (JSON: paragraph-layer-evidence/1)",
            )
        p.add_argument("-o", "--output", help="PDF target file" if name == "pdf" else "Write report text or JSON to a file instead of stdout")
        if name == "pdf":
            from .pdf_export import PDF_LAYOUTS

            p.epilog = (
                "Manuscript layouts retain headings, scene breaks, lists, quotations and endnotes. "
                r"Embedded LaTeX supports \emph, \textit, \textbf, \texttt and \textnormal; "
                r"standalone \newpage/\clearpage request page breaks. "
                "No TeX execution, mathematics typesetting or image placement. "
                "Unsupported TeX constructs fail before the output file is written."
            )
            p.add_argument(
                "--layout",
                choices=PDF_LAYOUTS,
                default="report",
                help="editor: A4 editorial copy with line numbers and comment margins · "
                "book: A5 reading copy · sheet: 30 lines of 60 characters · report: A4 analysis · "
                "document: neutral A4 text without line numbers or a generated cover",
            )
            p.add_argument(
                "--title",
                default=None,
                help="Document title override (default: project or manuscript title)",
            )
            p.add_argument("--author", default=None, help="Author byline and running header")
            p.add_argument(
                "--draft-notice",
                default=None,
                help="Running-header notice on every layout (default: project draft_notice)",
            )
            p.add_argument("--serif-font", default=None, help="TrueType file for running text")
            p.add_argument("--bold-font", default=None, help="TrueType file for headings")
            p.add_argument("--italic-font", default=None, help="TrueType file for italic manuscript text")
            p.add_argument("--bold-italic-font", default=None, help="TrueType file for bold italic manuscript text")
            p.add_argument("--mono-font", default=None, help="TrueType file for the sheet grid")
            p.add_argument("--sans-font", default=None, help="TrueType file for the report text")
            p.add_argument(
                "--sans-bold-font", default=None, help="TrueType file for report headings"
            )
    for command_name, command_parser in sub.choices.items():
        finish_command_help(command_parser, command_name)
    return parser


def _main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    if raw_argv in (["--version"], ["-V"]):
        print(f"lixity {__version__}")
        raise SystemExit(EXIT_OK)
    command_names = {name for name, _help in _COMMANDS}
    if raw_argv in (["--help"], ["-h"], []):
        only_command: str | None = "__top__"
    elif raw_argv and raw_argv[0] in command_names:
        only_command = raw_argv[0]
    else:
        only_command = None
    parser = _build_parser(only_command=only_command)
    args = parser.parse_args(argv)
    if args.command in ("project-backup", "project-restore"):
        from . import project_backup
        from .research.repository import ResearchError

        try:
            if args.command == "project-backup":
                backup_result = project_backup.backup(args.project, args.output,
                    manuscript=args.manuscript, settings=args.settings, attachments=args.attachment)
            else:
                backup_result = project_backup.restore(args.bundle, args.target)
        except (OSError, ResearchError) as exc:
            print(f"Project backup/restore failed: {exc}", file=sys.stderr)
            return 2
        print(_json(backup_result))
        return EXIT_OK
    if args.command == "audio-export-plan":
        args.command = "read-aloud"
    if args.command == "analysis-review":
        from .analysis_review import record_analysis_review, review_analysis
        from .format import safe_text

        fields = (args.observation, args.status, args.expected_source_sha256,
                  args.expected_analysis_sha256, args.expected_review_sha256)
        if any(value is not None for value in fields) and not all(value is not None for value in fields):
            parser.error("Saving requires --observation, --status and all three --expected-*-sha256 values")
        try:
            if args.status:
                triage_report = record_analysis_review(args.project, args.observation, args.status,
                    manuscript=args.manuscript, language=args.language,
                    tense_model=args.tense_model, tense_scope=args.tense_scope,
                    expected_source_sha256=args.expected_source_sha256,
                    expected_analysis_sha256=args.expected_analysis_sha256,
                    expected_review_sha256=args.expected_review_sha256)
            else:
                triage_report = review_analysis(args.project, manuscript=args.manuscript, language=args.language,
                                               tense_model=args.tense_model, tense_scope=args.tense_scope)
            if args.json:
                print(orjson.dumps(triage_report, option=orjson.OPT_INDENT_2).decode())
            else:
                print(f"Tense-pattern review: {triage_report['completed']} / {triage_report['total']} decisions completed.")
                print("Differences are not errors; changed is your assertion, and later remains open.")
                unmatched = triage_report["unmatched_decisions"]
                if unmatched:
                    noun, verb, retained = (("decision", "matches", "it is") if unmatched == 1
                                            else ("decisions", "match", "they are"))
                    print(f"{unmatched} previously saved {noun} for this manuscript no longer {verb} current observations; "
                          f"{retained} retained in the project.")
                for observation in triage_report["observations"][:20]:
                    print(safe_text(f"{triage_report['source_path']}:{observation['start_line']}-{observation['end_line']} · "
                        f"{observation['status']} · present {observation['present_hits']} / past {observation['past_hits']} · {observation['id']}"))
                if triage_report["total"] > 20:
                    print("First 20 observations shown; use --json for the complete guarded report.")
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as error:
            print(f"{_m('err_prefix')} {safe_text(str(error))}", file=sys.stderr)
            return EXIT_ERROR
    if args.command == "project":
        return _cmd_project(args)
    if args.command == "service":
        from .service import run as run_service

        return run_service(args)
    if args.command == "research":
        from .research.cli import run as run_research

        return run_research(args)
    if args.command == "doctor":
        from .diagnostics import DOCTOR_SCHEMA, doctor

        try:
            port = args.port if args.port is not None else int(os.environ.get("LIXITY_PORT") or DEFAULT_PORT)
            result = doctor(port=port)
        except ValueError:
            result = {"schema_version": DOCTOR_SCHEMA, "ok": False,
                      "error": {"code": "invalid-service-port", "message": _m("doctor_invalid_service_port")}}
        if args.json:
            print(orjson.dumps(result).decode("utf-8"))
        elif "error" in result:
            print(f"{_m('err_prefix')} {result['error']['message']}", file=sys.stderr)
        else:
            installation = result["installation"]
            for key in ("cli_version", "distribution_version", "module_path", "interpreter"):
                print(f"{_m('doctor_' + key)}: {installation[key] if installation[key] is not None else _m('doctor_unknown')}")
            service = result["service"]
            print(f"{_m('doctor_service')}: {service['state']} ({service['port']})")
            if service["state"] in ("running", "starting"):
                version = service.get("running_version") or _m("doctor_unknown")
                print(f"{_m('doctor_running_version')}: {version}")
            for issue in result["issues"]:
                print("- " + _m("doctor_" + issue["code"].replace("-", "_")))
            if result["ok"]:
                print(_m("doctor_ok"))
        return EXIT_OK if result["ok"] else EXIT_ERROR
    if args.command == "about":
        _print_about_json(args.section) if args.json or args.section else _print_about_text()
        return EXIT_OK
    if args.command == "schema":
        _print_about_json(args.section)
        return EXIT_OK
    if args.command == "mcp":
        from .mcp import main as mcp_main
        return mcp_main()
    if args.command == "diff":
        from pathlib import Path

        from .manuscript_editing import ManuscriptStore, compare_texts

        if args.project is not None and args.target is not None:
            parser.error("diff --project requires a single manuscript file")
        try:
            base_path = Path(args.base)
            target_path = Path(args.target) if args.target is not None else base_path
            history_root = None
            if args.project is not None:
                from .workspace import resolve_manuscript_target

                history_workspace = resolve_manuscript_target(args.base, project=args.project)
                history_root = Path(history_workspace.root)
                base_path = Path(history_workspace.manuscript)
                proj_cfg = read_explicit_project_config(history_root)
            else:
                proj_cfg = load_project_config(target_path)
            lang = str(args.language or proj_cfg.get("language") or "en")
            if args.target is not None:
                base_text = FileUtils.read_file(str(base_path))
                target_text = FileUtils.read_file(str(target_path))
                payload = compare_texts(
                    base_text, target_text, language=lang, project_config=proj_cfg
                )
            else:
                history_source = base_path if history_root is not None else base_path.resolve(strict=True)
                store = ManuscriptStore(
                    history_root if history_root is not None else history_source.parent,
                    history_source,
                    language=lang,
                    project_config=proj_cfg,
                )
                payload = store.delta(base_revision=args.base_rev, target_revision=args.target_rev)
        except (OSError, ValueError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(payload, indent=True))
        else:
            deltas = payload.get("deltas")
            if not deltas:
                print(f"{payload.get('schema_version', 'lixity-diff/1')}: no baseline revision available")
            else:
                lines = [f"{payload.get('schema_version', 'lixity-diff/1')}"]
                for key in (
                    "words",
                    "sentences",
                    "asl",
                    "asl_cv",
                    "length_entropy",
                    "sticky_pct",
                    "indirect_speech_per_1000",
                    "dialogue_ratio",
                    "mattr",
                ):
                    val = deltas.get(key)
                    if val is not None:
                        sign = "+" if isinstance(val, (int, float)) and val > 0 else ""
                        lines.append(f"  {key}: {sign}{val}")
                print("\n".join(lines))
        return EXIT_OK
    if args.command == "completion":
        shell = (args.shell or "bash").strip().lower()
        if shell in ("bash", "sh"):
            sys.stdout.write(_completion_scripts()[0])
            return EXIT_OK
        if shell == "zsh":
            sys.stdout.write(_completion_scripts()[1])
            return EXIT_OK
        # argparse choices already rejected unknown shells; keep a defensive path
        print(f"{_m('err_prefix')} {_m('err_shell', shell=args.shell)}", file=sys.stderr)
        return EXIT_ERROR
    if args.command == "audio-transcribe":
        from .speech_transcription import transcribe_audio
        try:
            result = transcribe_audio(
                args.audio, base_url=args.base_url, model=args.model, language=args.language,
            )
            return _run_text_report(args, lambda: print(_json(result, indent=True)) or EXIT_OK)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
    if args.command in ("audio-inspect", "audio-verify"):
        from .audio_audit import inspect_audio, load_audit_json
        try:
            result = inspect_audio(args.audio,
                expected_plan=load_audit_json(args.plan) if args.plan else None,
                transcript=load_audit_json(args.transcript) if args.transcript else None,
                language=args.language)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_json(result, indent=True))
        return EXIT_OK
    if args.command == "audio-import-transcript":
        from .audio_audit import (
            build_transcript_from_words,
            load_audit_json,
            parse_external_transcript,
        )
        try:
            raw_data = load_audit_json(args.transcript)
            words, model = parse_external_transcript(raw_data)
            effective_model = args.model or model
            transcript_obj = build_transcript_from_words(
                args.audio,
                words,
                model=effective_model,
                language=args.language,
            )
            content = _json(transcript_obj, indent=True)
            if args.output:
                _run_text_report(args, lambda: print(content) or EXIT_OK)
            else:
                print(content)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        return EXIT_OK
    if args.command == "audio-microphone":
        from .speech_record import (
            get_microphone_status,
            list_capture_devices,
            run_calibration,
            set_alsa_gain,
        )
        try:
            if args.action == "set":
                if args.gain is None:
                    raise ValueError("audio-microphone set requires --gain <0-50>")
                ok = set_alsa_gain(args.gain, card=args.card, control=args.control)
                if not ok:
                    raise RuntimeError(f"Could not set ALSA capture gain to {args.gain} on card {args.card}")
                if args.json:
                    print(_json({"status": "updated", "gain": args.gain, "card": args.card, "control": args.control}, indent=True))
                else:
                    print(f"Mikrofon-Gain erfolgreich auf {args.gain} gesetzt (Karte {args.card}, Regler {args.control}).")
                return EXIT_OK
            if args.action == "devices":
                devs = list_capture_devices()
                if args.json:
                    print(_json({"devices": devs}, indent=True))
                else:
                    print("Erkannte Audio-Aufnahmegeräte:")
                    for d in devs:
                        print(f"  • {d['label']}  [ALSA: {d['alsa_id']}]")
                return EXIT_OK
            if args.action == "calibrate":
                calib = run_calibration(gain=args.gain, device=args.device)
                if args.json:
                    print(_json(calib, indent=True))
                else:
                    print(f"Kalibrierung abgeschlossen: Peak {calib['peak_dbfs']} dBFS -> {calib['verdict_label']}")
                return EXIT_OK
            status = get_microphone_status()
            if args.json:
                print(_json(status, indent=True))
            else:
                gain_val = status["current_gain"]
                gain_str = str(gain_val) if gain_val is not None else "unbekannt"
                info = status.get("gain_info")
                db_str = f" ({info['db']:+.1f} dB, {info['percent']}%)" if info and info.get("db") is not None else ""
                lim_str = f" [Bereich {info['min']}–{info['max']}]" if info else ""
                print("Mikrofon- und Aufnahme-Status:")
                print(f"  Hardware-Gain:   {gain_str}{db_str}{lim_str}")
                print(f"  Standard-Gerät:  {status['default_device']}")
                print("  Erkannte Geräte:")
                for d in status["devices"]:
                    print(f"    • {d['label']} (ID: {d['alsa_id']})")
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
    if args.command == "audio-calibrate":
        from .speech_record import run_calibration
        try:
            if not args.json:
                print("Bereit machen: 4 Sekunden Vorlauf, danach 8 Sekunden Testaufgabe:", file=sys.stderr)
                print("  3x lautes 'POPP' -> 2x klatschen -> 1x normal 'Eins zwei drei' sprechen.\n", file=sys.stderr)
            calib = run_calibration(gain=args.gain, duration=args.duration, countdown=args.countdown, device=args.device)
            if args.json:
                print(_json(calib, indent=True))
                return EXIT_OK
            print("Datei: Testaufnahme")
            print(f"  Laenge: {calib['duration_seconds']}s | {calib['sample_rate']} Hz mono")
            print(f"  Peak:      {calib['peak_dbfs']:+7.1f} dBFS")
            print(f"  Clipping:  {calib['clipping_samples']} Samples >= -0.1 dBFS")
            print(f"  Rauschuntergrund (min 0.5s): {calib['noise_floor_dbfs']:+7.1f} dBFS")
            print(f"  Sprachabstand zu Rauschen:   {calib['snr_db']:.1f} dB\n")
            print("==================== URTEIL ====================")
            print(f"  Peak {calib['peak_dbfs']} dBFS -> {calib['verdict_label']}")
            if calib["verdict"] == "too_hot":
                print("  Handlungsempfehlung: ZU HEISS. Gain senken und nochmal versuchen:")
                print(f"      lixity audio-calibrate --gain {calib['recommended_gain']}")
            elif calib["verdict"] == "too_quiet":
                print("  Handlungsempfehlung: MEHR LUFT ALS NOETIG (optional). Gain erhoehen:")
                print(f"      lixity audio-calibrate --gain {calib['recommended_gain']}")
            else:
                print("  Handlungsempfehlung: GAIN BEHALTEN. Kalibriert fuer Aufnahmen!")
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
    if args.command == "audio-import":
        from .speech_artifacts_cli import run
        try:
            print(_json(run(args), indent=True))
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
    if args.command == "audio-reference":
        from .speech_qwen import MAX_REFERENCE_BYTES
        from .speech_reference_quality import assess_reference
        from .speech_references import (
            get_calibration_text,
            load_reference,
            read_reference_input,
            save_reference,
        )
        try:
            if args.action == "calibration-text":
                print(get_calibration_text(args.language, args.variant))
                return EXIT_OK
            if not args.project:
                raise ValueError(f"audio-reference {args.action} requires --project")
            if args.action == "generate":
                from .speech_references import generate_reference

                reference = generate_reference(
                    args.project,
                    text=args.transcript,
                    language=args.language,
                    voice_description=args.voice_description,
                )
                quality = assess_reference(reference.audio)
                print(_json({"schema_version": "lixity-audio-reference-created/1", "id": reference.id, "quality": quality}, indent=True))
                return EXIT_OK
            if args.action == "inspect":
                if not args.reference_id:
                    raise ValueError(_m("audio_reference_inspect_input"))
                reference = load_reference(args.project, args.reference_id)
                print(_json({**assess_reference(reference.audio), "reference_id": reference.id}, indent=True))
                return EXIT_OK
            if args.action == "record":
                from pathlib import Path

                from .speech_record import analyze_signal, record_audio

                transcript = args.transcript
                if not transcript and args.transcript_file:
                    transcript = read_reference_input(args.transcript_file, 8000).decode("utf-8")
                if not transcript and args.calibration_text:
                    transcript = get_calibration_text(args.language, args.variant)

                duration = args.duration
                if args.calibration_text and duration == 15.0 and args.variant == "phonetic":
                    duration = 24.0

                if args.calibration_text and transcript:
                    print("\n================== KALIBRIERUNGSTEXT (TELEPROMPTER) ==================", file=sys.stderr)
                    print(f"Sprache: {args.language} | Variante: {args.variant} | Dauer: {duration:.0f}s", file=sys.stderr)
                    print("Bitte nach dem Countdown laut, ruhig und deutlich vorlesen:\n", file=sys.stderr)
                    print(transcript, file=sys.stderr)
                    print("=======================================================================\n", file=sys.stderr)

                print(f"Aufnahme ({duration:.0f}s) startet in 2 Sekunden... Sprechen Sie Ihren Referenztext.", file=sys.stderr)
                audio = record_audio(duration, gain=args.gain, device=args.device, countdown=2.0)
                if args.output:
                    Path(args.output).write_bytes(audio)
                    print(f"Aufnahmedatei gespeichert: {args.output}", file=sys.stderr)
                if transcript:
                    reference = save_reference(args.project, audio, transcript)
                    quality = assess_reference(reference.audio)
                    print(_json({"schema_version": "lixity-audio-reference-created/1", "id": reference.id, "quality": quality}, indent=True))
                    return EXIT_OK
                signal_stats = analyze_signal(audio)
                print(_json({
                    "status": "recorded",
                    "duration_seconds": duration,
                    "quality": signal_stats,
                    "action_required": f"Referenz anlegen mit: lixity audio-reference create --project {args.project} --audio {args.output or 'recording.wav'} --transcript-file TEXT.txt",
                }, indent=True))
                return EXIT_OK
            if not args.audio or not args.transcript_file:
                raise ValueError(_m("audio_reference_create_inputs"))
            audio = read_reference_input(args.audio, MAX_REFERENCE_BYTES)
            transcript = read_reference_input(args.transcript_file, 8000).decode("utf-8")
            reference = save_reference(args.project, audio, transcript)
            quality = assess_reference(reference.audio)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_json({"schema_version": "lixity-audio-reference-created/1", "id": reference.id, "quality": quality}, indent=True))
        return EXIT_OK
    if args.command == "audio-status":
        from .format import safe_text
        from .speech_status import audio_status
        try:
            status = audio_status(args.project, engine=args.engine)
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(status, indent=True))
        else:
            if status['comparison_engine'] is not None:
                print(f"{_m('audio_status_comparison')}: {status['comparison_engine']}")
            if status['project'] is not None:
                print(f"{_m('audio_status_project')}: {safe_text(status['project']['root'])}")
                print(f"{_m('audio_status_selected')}: {status['project']['selected_profile'] or _m('audio_status_unknown')}")
                for item in status['project']['profiles']:
                    print(safe_text(f"  {item['id']}: {item['name']} · {item['engine']} · {item['voice']} · {item['language']}"))
                if status['project'].get('profile_issue'):
                    print(f"{_m('audio_status_unavailable')}: {status['project']['profile_issue']}")
            for target in status['targets']:
                match = target['model_matches']
                matching = _m('audio_status_yes' if match is True else 'audio_status_no' if match is False else 'audio_status_unknown')
                print(f"{target['target']}: {target['state']} · {target.get('model') or _m('audio_status_unknown')} · "
                      f"{_m('audio_status_match')}: {matching}")
            if status['comparison_engine'] == 'qwen3-design':
                print(_m('audio_status_design_hint'))
            elif status['comparison_engine'] == 'qwen3-base':
                print(_m('audio_status_base_hint'))
        return EXIT_OK
    if args.command == "audio-direction":
        from .speech_direction_cli import run
        try:
            print(_json(run(args), indent=True))
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(_json({"ok": False, "message": str(exc)}, indent=True))
            return EXIT_ERROR
    if args.command == "audio-migrate":
        from .speech_migration import (
            prepare_audio_migration,
            prepare_schema3_migration,
            prepare_schema4_migration,
            prepare_schema5_migration,
        )

        def pairs(values: list[str]) -> dict[str, str]:
            result: dict[str, str] = {}
            for value in values:
                key, separator, item = value.partition("=")
                if not separator or not key or not item or key in result:
                    raise ValueError("Supply unique PROFILE=VALUE entries")
                result[key] = item
            return result

        if args.apply and (not args.backup or not args.expected_snapshot):
            parser.error("audio-migrate --apply requires --backup and --expected-snapshot from a reviewed preview")
        if not args.apply and (args.backup or args.expected_snapshot):
            parser.error("Omit --backup and --expected-snapshot for a read-only preview")
        try:
            if (args.to_schema_3 or args.to_schema_4 or args.to_schema_5) and (args.replace or args.instructions):
                raise ValueError("Schema upgrade cannot be combined with profile replacements")
            prepared = (prepare_schema5_migration(args.project) if args.to_schema_5 else
                        prepare_schema4_migration(args.project) if args.to_schema_4 else
                        prepare_schema3_migration(args.project) if args.to_schema_3 else
                        prepare_audio_migration(args.project, pairs(args.replace), instructions=pairs(args.instructions)))
            if args.apply and args.expected_snapshot != prepared.snapshot:
                raise ValueError("Migration snapshot changed; prepare and review the migration again")
            result = prepared.apply(args.backup) if args.apply else prepared.public_dict()
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_json(result, indent=True))
        return EXIT_OK
    if args.command == "export-site":
        from .site_contracts import SiteExportOptions
        from .site_export import SiteExportLimitError, export_site, prepare_site

        if args.preflight and args.output:
            parser.error("--preflight does not write an output directory; omit --output")
        if not args.preflight and not args.output:
            parser.error("export-site requires --output, or --preflight to check without writing")
        try:
            sections = args.analysis or []
            if "all" in sections:
                if sections != ["all"]:
                    raise ValueError("The all-analysis choice cannot be combined with other sections")
                sections = ["full"]
            options = SiteExportOptions(include_research=args.include_research,
                                        include_source_files=args.include_source_files,
                                        include_audio=args.include_audio,
                                        mode=args.mode, publication_profile=args.publication_profile,
                                        max_chapter=args.max_chapter, analysis_sections=sections)
            if args.preflight:
                report = prepare_site(args.project, manuscript=args.file, language=args.language,
                                      **options.model_dump(exclude_defaults=True)).preflight()
                if args.json:
                    print(_json(report, indent=True))
                else:
                    sizes, media = report["sizes"], report["media"]
                    print(f"HTML: {sizes['html_bytes']:,} bytes; ZIP: {sizes['zip_bytes']:,} bytes; "
                          f"all files: {sizes['total_bytes']:,} bytes ({sizes['file_count']} files)")
                    print(f"Media references: {media['references']}; unavailable: {media['unavailable']}; "
                          f"not packaged: {media['not_packaged']}; attribution incomplete: {media['missing_attribution']}; "
                          f"ordinary images unchecked: {media['ordinary_image_references']}")
                    print("Mobile layout: not checked. Rights: not verified. No output written.")
                    if report["warnings"]:
                        print("Warnings: " + ", ".join(report["warnings"]))
                return EXIT_OK
            manifest = export_site(
                args.project, args.output, manuscript=args.file, language=args.language,
                **options.model_dump(exclude_defaults=True),
            )
        except SiteExportLimitError as exc:
            if args.json:
                print(_json(exc.diagnostic, indent=True))
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(manifest, indent=True))
        else:
            from pathlib import Path

            from .format import safe_text

            print(safe_text(str(Path(args.output).expanduser().resolve() / "index.html")))
            print(_m("site_export_done"))
        return EXIT_OK
    if getattr(args, "min_chapters", None) is not None and args.min_chapters < 2:
        parser.error("--min-chapters must be at least 2")
    if args.command == "profile" and args.only_notable and args.layer is None:
        parser.error("--only-notable requires --layer")
    if args.command == "profile" and args.evidence and args.layer is None:
        parser.error("--evidence requires --layer")
    if args.command == "pdf" and args.json:
        parser.error("--json is not supported for PDF output; use analyze or style --json for measurements")
    if args.command == "serve":
        project_config = {} if args.no_project else load_project_config(args.path)
    else:
        explicit_file = args.file
        try:
            from .workspace import resolve_manuscript_target

            workspace = resolve_manuscript_target(
                explicit_file, project=args.project,
                allow_discovery=args.command in ("scenes", "build", "read-aloud"),
            )
            args._workspace = workspace
            # Keep the legacy spelling for explicit files without --project.
            if explicit_file is None or args.project is not None:
                args.file = workspace.manuscript
                project_config = read_explicit_project_config(workspace.root)
                speech_config_selection = (True, workspace.root)
                if (args.project is None and args.command in ("scenes", "build", "read-aloud")
                        and "manuscript" not in project_config):
                    # Preserve conventional folder users' defaults, rooted at
                    # the selected workspace rather than an implicit cwd.
                    project_config = load_project_config(workspace.root)
                    speech_config_selection = (False, workspace.root)
            else:
                project_config = load_project_config(explicit_file)
                speech_config_selection = (False, explicit_file)
            if args.command == "read-aloud":
                args._speech_config_selection = speech_config_selection
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    project_config = {**project_config, **{key: value for key in ("tense_model", "tense_scope")
                      if (value := getattr(args, key, None)) is not None}}
    args._project_config = project_config
    explicit_language = getattr(args, "language", None)
    if args.command == "read-aloud":
        args._speech_explicit_language = explicit_language
    if hasattr(args, "language") and args.language is None:
        args.language = project_config.get("language", "en")

    if args.command == "serve":
        from .server import DesktopSession, run_server
        from .service import ManagedServe

        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        project_open_overrides = {
            key: value
            for key, value in (
                ("language", explicit_language),
                ("title", args.title),
                ("z_mild", args.z_mild),
                ("z_strong", args.z_strong),
                ("fdr_q", args.fdr_q),
                ("fdr_method", args.fdr_method),
                ("min_chapters", getattr(args, "min_chapters", None)),
                ("dim_score_threshold", args.dim_threshold),
                ("flag_min_severity", args.flag_min_severity),
                ("tense_model", args.tense_model),
                ("tense_scope", args.tense_scope),
            )
            if value is not None
        }
        managed = None
        desktop_session = None
        try:
            if args._desktop_mode and args._service_token is not None:
                raise ValueError("Desktop mode cannot be combined with managed service launch")
            if args._desktop_mode:
                desktop_session = DesktopSession.from_stdin()
            elif args._service_token is not None:
                managed = ManagedServe(args._service_token, args.port)
            run_server(
                target_path=args.path,
                host=args.host,
                port=args.port,
                language=args.language,
                title=args.title or project_config.get("title"),
                no_project=args.no_project or (args._desktop_mode and args.path is None),
                thresholds=fp_thresholds,
                open_browser=False if args._desktop_mode else args.open,
                research_dir=args.research_project,
                project_open_overrides=project_open_overrides,
                debug=args.debug,
                announce=not args._desktop_mode,
                on_ready=managed.ready if managed is not None else None,
                desktop_session=desktop_session,
            )
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            if managed is not None:
                managed.close()

    if args.command == "pdf":
        return _cmd_pdf(args)

    if args.command == "read-aloud":
        return _cmd_read_aloud(args)

    if args.command == "build":
        return _cmd_build(args)

    if args.command == "dialogue":
        return _run_text_report(args, lambda: _cmd_dialogue(args))

    if args.command == "characters":
        return _run_text_report(args, lambda: _cmd_characters(args))

    if args.command == "pacing":
        return _run_text_report(args, lambda: _cmd_pacing(args))

    if args.command == "motifs":
        return _run_text_report(args, lambda: _cmd_motifs(args))

    if args.command == "showing":
        return _run_text_report(args, lambda: _cmd_showing(args))

    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    try:
        from .pipeline import resolve_document_config

        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config
        )
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.command in ("scenes", "canvas", "analyze", "profile", "style"):
        return _run_text_report(args, lambda: _cmd_analysis_report(args, text, config, resolved))

    from .characters import presence_report, resolve_character_settings
    from .dialogue import dialogue_report
    from .pipeline import analyze_document
    from .scenes import scene_report_for_display
    from .ui import render_analysis
    from .ui.manuscript_document import reader_blocks
    from .ui.render_contracts import DashboardContent

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics

    try:
        raw_names = getattr(args, "names", None)
        selection = resolve_character_settings(
            [part.strip() for part in raw_names.split(",") if part.strip()] if raw_names is not None else None,
            args._project_config,
        )
        character_report = (presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
                            if selection.names else None)
        title = _document_title(args, args.file, text)
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    html = render_analysis(
        analysis,
        resolved,
        title=title,
        flag_min_severity=fp_thresholds.flag_min_severity,
        content=DashboardContent(
            reader_document=reader_blocks(text, config, analysis.paragraphs),
            scenes=scene_report_for_display(
                text,
                config,
                args._project_config.get("scene_analysis"),
                premeasured_chapters=metrics.chapters,
            ),
            dialogue=dialogue_report(text, config).to_display_dict(config),
            characters=character_report,
        ),
    )
    output = args.output or "lixity-dashboard.html"
    try:
        FileUtils.require_distinct_output(args.file, output)
        changed = FileUtils.atomic_write_if_changed(
            output, html, before_replace=lambda: FileUtils.require_distinct_output(args.file, output),
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(_m("dashboard_written" if changed else "dashboard_unchanged", output=output))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Keep ordinary configuration/model failures inside the CLI error contract."""
    try:
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
