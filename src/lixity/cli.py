"""Lixity – command line: corpus analysis, style profile, style reference and dashboard."""

import argparse
import os
import sys
from typing import Any

import orjson
from rich import box
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import CorpusAnalyzer
from .config import load_project_config, resolve_thresholds
from .formatters import ReportFormatter
from .io import FileUtils
from .models import SCHEMA_VERSION
from .pipeline import (
    analyze_document,
    fingerprint_document,
    profile_document,
    resolve_document_config,
)
from .style_fingerprint import FingerprintThresholds
from .ui import render_dashboard
from .workspace import discover

EXIT_OK = 0
EXIT_ERROR = 1


def _document_title(args: argparse.Namespace, manuscript: str) -> str:
    configured = args._project_config.get("title")
    if isinstance(configured, str) and configured.strip():
        return configured.strip()
    return os.path.splitext(os.path.basename(manuscript))[0]


def _thresholds_from_args(
    args: argparse.Namespace, config: dict[str, Any] | None = None
) -> FingerprintThresholds:
    """Builds FingerprintThresholds from CLI flags (defaults = documented heuristics).

    Precedence: CLI flag > project config (``[tool.lixity]`` / ``lixity.toml``) >
    built-in default — shared builder ``config.resolve_thresholds``.
    """
    return resolve_thresholds(
        project_config=config,
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

# User-facing CLI messages: English is the engine default, German via
# LIXITY_LANG=de.
CLI_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "about_title": "lixity {version} – quantitative text linguistics & stylometry",
        "about_languages": "Languages: {languages}",
        "about_features": "Features ({count}):",
        "about_heuristics": (
            "Heuristics: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, dimensions={n_dimensions}"
        ),
        "about_commands": "Commands:",
        "about_license": "License: {license}",
        "err_prefix": "[error]",
        "err_shell": "Unknown shell: {shell} (bash|zsh)",
        "err_file": "File not readable: {file} ({exc})",
        "build_workspace": "Workspace: {root}",
        "build_manuscript": "Manuscript: {file} (language: {language})",
        "state_written": "written",
        "state_unchanged": "unchanged",
        "build_dry_run": ("Dry run: {changed} to write, {unchanged} unchanged – no files changed."),
        "build_done": "Done: {changed} written, {unchanged} unchanged · nda/ ready.",
        "dashboard_written": "Dashboard written: {output}",
        "dashboard_unchanged": "Dashboard unchanged: {output}",
        "err_no_names": "No figure names given (use --name or --names).",
        "dlg_metric": "Dialogue metric",
        "dlg_value": "Value",
        "dlg_turns": "Turns (quoted segments)",
        "dlg_dialogue_pct": "Dialogue share",
        "dlg_avg_turn": "Average turn (words)",
        "dlg_median_turn": "Median turn (words)",
        "dlg_longest_turn": "Longest turn (words)",
        "dlg_turns_per_1000": "Turns per 1,000 words",
        "dlg_paragraph_pct": "Dialogue paragraphs",
        "dlg_chapter": "Ch.",
        "dlg_title": "Title",
        "chr_name": "Figure",
        "chr_mentions": "Mentions",
        "chr_chapters": "Chapters present",
        "chr_span": "Chapter span",
        "chr_gap": "Longest gap",
        "chr_share": "Presence",
        "pac_metric": "Pacing metric",
        "pac_value": "Value",
        "pac_chapters": "Chapters",
        "pac_scenes": "Scenes",
        "pac_avg_scene": "Average scene (words)",
        "pac_hook_mean": "Hook score (mean)",
        "pac_fastest": "Fastest chapter",
        "pac_slowest": "Slowest chapter",
        "pac_chapter": "Ch.",
        "pac_title": "Title",
        "pac_asl": "ASL",
        "pac_dialogue": "Dialogue",
        "pac_hook": "Hook",
        "pac_no_breaks": (
            "No explicit scene dividers found — scenes = chapters "
            "(scene structure is uninformative)."
        ),
        "err_motif_spec": "Invalid motif (expected NAME=REGEX): {spec}",
        "mot_name": "Motif",
        "mot_mentions": "Mentions",
        "mot_density": "Per 1,000 words",
        "mot_span": "Chapter span",
        "mot_gap": "Longest gap",
        "mot_top_words": "Most frequent content words:",
        "mot_phrase": "Repeated phrase",
        "mot_count": "Count",
        "mot_chapters": "Chapters",
        "show_metric": "Narrative distance",
        "show_value": "Value",
        "show_chapters": "Chapters",
        "show_tell_z": "Telling (mean z)",
        "show_show_z": "Showing (mean z)",
        "show_balance": "Balance (show - tell)",
        "show_most_telling": "Most telling chapters",
        "show_most_showing": "Most showing chapters",
        "show_chapter": "Ch.",
        "show_title": "Title",
    },
    "de": {
        "about_title": "lixity {version} – quantitative Textlinguistik & Stilometrie",
        "about_languages": "Sprachen: {languages}",
        "about_features": "Merkmale ({count}):",
        "about_heuristics": (
            "Heuristiken: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, Dimensionen={n_dimensions}"
        ),
        "about_commands": "Kommandos:",
        "about_license": "Lizenz: {license}",
        "err_prefix": "[Fehler]",
        "err_shell": "Unbekannte Shell: {shell} (bash|zsh)",
        "err_file": "Datei nicht lesbar: {file} ({exc})",
        "build_workspace": "Workspace: {root}",
        "build_manuscript": "Manuskript: {file} (Sprache: {language})",
        "state_written": "geschrieben",
        "state_unchanged": "unverändert",
        "build_dry_run": (
            "Dry-Run: {changed} zu schreiben, {unchanged} unverändert – keine Dateien geändert."
        ),
        "build_done": "Fertig: {changed} geschrieben, {unchanged} unverändert · nda/ bereit.",
        "dashboard_written": "Dashboard geschrieben: {output}",
        "dashboard_unchanged": "Dashboard unverändert: {output}",
        "err_no_names": "Keine Figurennamen angegeben (--name oder --names).",
        "dlg_metric": "Dialogmetrik",
        "dlg_value": "Wert",
        "dlg_turns": "Turns (Redeabschnitte)",
        "dlg_dialogue_pct": "Dialoganteil",
        "dlg_avg_turn": "Ø Turn (Wörter)",
        "dlg_median_turn": "Median Turn (Wörter)",
        "dlg_longest_turn": "Längster Turn (Wörter)",
        "dlg_turns_per_1000": "Turns je 1.000 Wörter",
        "dlg_paragraph_pct": "Dialogabsätze",
        "dlg_chapter": "Kap.",
        "dlg_title": "Titel",
        "chr_name": "Figur",
        "chr_mentions": "Erwähnungen",
        "chr_chapters": "Kapitel anwesend",
        "chr_span": "Kapitelspanne",
        "chr_gap": "Größte Lücke",
        "chr_share": "Präsenz",
        "pac_metric": "Pacing-Metrik",
        "pac_value": "Wert",
        "pac_chapters": "Kapitel",
        "pac_scenes": "Szenen",
        "pac_avg_scene": "Ø Szene (Wörter)",
        "pac_hook_mean": "Haken-Ø",
        "pac_fastest": "Schnellstes Kapitel",
        "pac_slowest": "Langsamstes Kapitel",
        "pac_chapter": "Kap.",
        "pac_title": "Titel",
        "pac_asl": "ASL",
        "pac_dialogue": "Dialog",
        "pac_hook": "Haken",
        "pac_no_breaks": (
            "Keine expliziten Szenentrenner gefunden — Szenen = Kapitel "
            "(Szenenstruktur ohne Aussagekraft)."
        ),
        "err_motif_spec": "Ungültiges Motiv (erwartet NAME=REGEX): {spec}",
        "mot_name": "Motiv",
        "mot_mentions": "Treffer",
        "mot_density": "Je 1.000 Wörter",
        "mot_span": "Kapitelspanne",
        "mot_gap": "Größte Lücke",
        "mot_top_words": "Häufigste Inhaltswörter:",
        "mot_phrase": "Wiederholte Phrase",
        "mot_count": "Anzahl",
        "mot_chapters": "Kapitel",
        "show_metric": "Erzähldistanz",
        "show_value": "Wert",
        "show_chapters": "Kapitel",
        "show_tell_z": "Telling (Ø z)",
        "show_show_z": "Showing (Ø z)",
        "show_balance": "Balance (Show - Tell)",
        "show_most_telling": "Telling-lastigste Kapitel",
        "show_most_showing": "Showing-lastigste Kapitel",
        "show_chapter": "Kap.",
        "show_title": "Titel",
    },
}


def _lang() -> str:
    value = os.environ.get("LIXITY_LANG", "en").strip().lower()
    return value if value in CLI_TEXTS else "en"


def _m(key: str, **fmt: object) -> str:
    pack = CLI_TEXTS[_lang()]
    text = pack.get(key) or CLI_TEXTS["en"].get(key, key)
    return text.format(**fmt) if fmt else text


_BASH_COMPLETION = """# bash completion for lixity – source this file or add it to bash_completion.d/
#   lixity completion bash > /etc/bash_completion.d/lixity   # system
#   lixity completion bash > ~/.local/share/bash-completion/completions/lixity
_lixity_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmds="analyze profile dialogue characters pacing motifs showing dashboard serve style build about completion research"
    local opts="--help --version --language --json --output -o --dry-run --names --motif --phrases --name"
    local style_opts="--z-mild --z-strong --fdr-q --fdr-method --dim-threshold --flag-min-severity --min-chapters"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds --help --version" -- "$cur") )
        return 0
    fi
    case "$prev" in
        research)
            COMPREPLY=( $(compgen -W "init ingest reindex search cite audit schema analyze dashboard compare withdraw purge" -- "$cur") )
            return 0
            ;;
        --project)
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
        --file|--manuscript)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --language)
            COMPREPLY=( $(compgen -W "auto de en fr es it pt nl generic" -- "$cur") )
            return 0
            ;;
        --fdr-method)
            COMPREPLY=( $(compgen -W "bh by" -- "$cur") )
            return 0
            ;;
        --flag-min-severity)
            COMPREPLY=( $(compgen -W "1 2 3" -- "$cur") )
            return 0
            ;;
        -o|--output)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") )
            return 0
            ;;
    esac
    if [[ ${COMP_WORDS[1]} == research ]]; then
        COMPREPLY=( $(compgen -W "--project --file --title --language --actor --source-id --version-id --reason --allow-retention --dry-run --context --thresholds --query --limit --passage --help" -- "$cur") )
        return 0
    fi
    COMPREPLY=( $(compgen -W "$opts $style_opts" -- "$cur") )
    COMPREPLY+=( $(compgen -f -- "$cur") )
}
complete -F _lixity_complete lixity
"""

_ZSH_COMPLETION = """#compdef lixity
# zsh completion for lixity – place in a directory of $fpath
#   lixity completion zsh > "${fpath[1]}/_lixity"
_lixity_style_flags=(
  '--z-mild[Notable |z*| threshold]:threshold:'
  '--z-strong[Strong |z*| threshold]:threshold:'
  '--fdr-q[FDR q]:q:'
  '--fdr-method[FDR method]:method:(bh by)'
  '--min-chapters[Minimum chapters for baseline]:count:'
  '--dim-threshold[Dimension score threshold]:threshold:'
  '--flag-min-severity[Minimum severity]:severity:(1 2 3)'
)
_lixity() {
  local -a cmds
  cmds=(
    'analyze:Corpus metrics (text/JSON)'
    'profile:Paragraph tense/style profiles'
    'dialogue:Dialogue turn structure'
    'characters:Character presence across chapters'
    'pacing:Scene structure and pacing'
    'motifs:Motif tracking and repetition'
    'showing:Showing vs telling balance'
    'style:Self-calibrated style reference'
    'dashboard:Single-file HTML dashboard'
    'serve:Run local HTTP development server and interactive dashboard'
    'build:Idempotent workspace build'
    'about:Tool metadata for agents'
    'completion:Shell completion script'
    'research:Experimental local research archive and lexical search'
  )
  _arguments -C \
    '--version[Print version and exit]' \
    '1: :->command' \
    '*:: :->args'
  case $state in
    command)
      _describe -t commands 'lixity command' cmds
      ;;
    args)
      case $words[1] in
        research)
          _arguments \
            '1:action:(init ingest reindex search cite audit schema analyze dashboard compare withdraw purge)' \
            '--project[Explicit project root]:directory:_files -/' \
            '--file[UTF-8 source]:file:_files' \
            '--manuscript[Path to manuscript file]:file:_files' \
            '--title[Source or project title]:title:' \
            '--language[Language]:language:(en de fr es it pt nl generic)' \
            '--actor[Local actor]:actor:' \
            '--source-id[Source identifier]:id:' \
            '--version-id[Explicit source version identifier]:id:' \
            '--reason[Reason for action]:reason:' \
            '--allow-retention[Confirm local retention permission]' \
            '--dry-run[Preview without writing]' \
            '--context[Source criticism context JSON file]:file:_files' \
            '--thresholds[Analysis thresholds]:thresholds:' \
            '--query[Literal search words]:query:' \
            '--limit[Maximum hits]:limit:' \
            '--passage[Immutable passage ID]:id:'
          ;;
        completion)
          _values 'shell' bash zsh sh
          ;;
        about)
          _arguments '--json[JSON output]' '--help[Help]'
          ;;
        serve)
          _arguments \
            '1:path:_files' \
            '--host[Bind address]:host:' \
            '--port[Port]:port:' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--title[Dashboard title]:title:' \
            '--open[Open in browser]' \
            '--no-project[Start without preloading a project]' \
            "${_lixity_style_flags[@]}"
          ;;
        build)
          _arguments \
            '1:file:_files' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--dry-run[Show planned artifacts only]' \
            "${_lixity_style_flags[@]}"
          ;;
        motifs)
          _arguments \
            '1:file:_files' \
            '--motif[NAME=REGEX]' \
            '--phrases[Phrase size]:n:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        characters)
          _arguments \
            '1:file:_files' \
            '--name[Figure name or alias]' \
            '--names[Comma-separated names]:names:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        dashboard)
          _arguments \
            '1:file:_files' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--names[Character names]:names:' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
        *)
          _arguments \
            '1:file:_files' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
      esac
      ;;
  esac
}
_lixity "$@"
"""


def _meta_payload(language_key: str, **body: Any) -> dict[str, Any]:
    payload = {"meta": {**_META, "language": language_key}}
    payload.update(body)
    return payload


def _print_about_json() -> None:
    from .api import about

    print(_json(about(), indent=True))


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
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .dialogue import dialogue_report

    config, resolved = resolve_document_config(text, args.language)
    report = dialogue_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, dialogue=report.to_dict()), indent=True))
        return EXIT_OK

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
    ):
        summary.add_row(_m(key), value)
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
    """Character presence as a Rich table or JSON."""
    names: list[str] = list(args.name or [])
    if args.names:
        names.extend(part.strip() for part in args.names.split(",") if part.strip())
    if not names:
        print(f"{_m('err_prefix')} {_m('err_no_names')}", file=sys.stderr)
        return EXIT_ERROR
    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .characters import presence_report

    config, resolved = resolve_document_config(text, args.language)
    report = presence_report(text, names, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, **report), indent=True))
        return EXIT_OK

    con = Console()
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    table.add_column(_m("chr_name"), style="bold white")
    table.add_column(_m("chr_mentions"), justify="right", style="cyan")
    table.add_column(_m("chr_chapters"), justify="right")
    table.add_column(_m("chr_span"))
    table.add_column(_m("chr_gap"), justify="right")
    table.add_column(_m("chr_share"), justify="right")
    for figure in report["figures"]:
        span = (
            f"{figure['first_chapter']}–{figure['last_chapter']}"
            if figure["first_chapter"]
            else "–"
        )
        table.add_row(
            figure["name"],
            str(figure["mentions"]),
            f"{len(figure['chapters_present'])} / {report['chapters']}",
            span,
            str(figure["longest_gap"]),
            f"{figure['presence_ratio'] * 100:.0f} %",
        )
    con.print(table)
    return EXIT_OK


def _cmd_pacing(args: argparse.Namespace) -> int:
    """Scene structure, pacing signals and chapter hooks (Rich table or JSON)."""
    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .pacing import pacing_report

    config, resolved = resolve_document_config(text, args.language)
    report = pacing_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, pacing=report.to_dict()), indent=True))
        return EXIT_OK

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("pac_metric"), style="bold white")
    summary.add_column(_m("pac_value"), justify="right", style="cyan")
    for key, value in (
        ("pac_chapters", str(report.chapters)),
        ("pac_scenes", str(report.scenes)),
        ("pac_avg_scene", f"{report.avg_scene_words:.0f}"),
        ("pac_hook_mean", f"{report.hook_score_mean:.2f}"),
        ("pac_fastest", str(report.fastest_chapter or "–")),
        ("pac_slowest", str(report.slowest_chapter or "–")),
    ):
        summary.add_row(_m(key), value)
    con.print(summary)
    if report.scenes_are_chapters and report.chapters:
        con.print(f"[yellow]{_m('pac_no_breaks')}[/yellow]")

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("pac_chapter"), justify="right")
        table.add_column(_m("pac_title"))
        table.add_column(_m("pac_scenes"), justify="right")
        table.add_column(_m("pac_asl"), justify="right")
        table.add_column(_m("pac_dialogue"), justify="right")
        table.add_column(_m("pac_hook"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                str(chapter.scenes),
                f"{chapter.asl:.1f}",
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
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .motifs import motif_report

    config, resolved = resolve_document_config(text, args.language)
    report = motif_report(text, motifs, config, phrase_size=max(2, args.phrases))

    if args.json:
        print(_json(_meta_payload(resolved.key, **report.to_dict()), indent=True))
        return EXIT_OK

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

    if report.repeated_phrases:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("mot_phrase"))
        table.add_column(_m("mot_count"), justify="right")
        table.add_column(_m("mot_chapters"))
        for phrase in report.repeated_phrases:
            table.add_row(phrase.phrase, str(phrase.count), ", ".join(map(str, phrase.chapters)))
        con.print(table)
    return EXIT_OK


def _cmd_showing(args: argparse.Namespace) -> int:
    """Showing vs. telling balance (Rich table or JSON)."""
    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .showing import showing_report

    config, resolved = resolve_document_config(text, args.language)
    report = showing_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, showing=report.to_dict()), indent=True))
        return EXIT_OK

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("show_metric"), style="bold white")
    summary.add_column(_m("show_value"), justify="right", style="cyan")
    for key, value in (
        ("show_chapters", str(report.chapters)),
        ("show_tell_z", f"{report.tell_z_mean:+.2f}"),
        ("show_show_z", f"{report.show_z_mean:+.2f}"),
        ("show_balance", f"{report.balance_mean:+.2f}"),
        ("show_most_telling", ", ".join(map(str, report.most_telling))),
        ("show_most_showing", ", ".join(map(str, report.most_showing))),
    ):
        summary.add_row(_m(key), value)
    con.print(summary)

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("show_chapter"), justify="right")
        table.add_column(_m("show_title"))
        table.add_column(_m("show_tell_z"), justify="right")
        table.add_column(_m("show_show_z"), justify="right")
        table.add_column(_m("show_balance"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                f"{chapter.tell_z:+.2f}",
                f"{chapter.show_z:+.2f}",
                f"{chapter.balance:+.2f}",
            )
        con.print(table)
    return EXIT_OK


def _cmd_build(args: argparse.Namespace) -> int:
    """Idempotent workspace build: analyzes the manuscript and publishes artifacts."""
    try:
        workspace = discover(explicit=args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    text = workspace.read_manuscript()
    config, resolved = resolve_document_config(text, args.language)

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    fingerprint = analysis.fingerprint
    title = _document_title(args, workspace.manuscript)

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
        f"{workspace.slug}_dashboard.html": render_dashboard(
            chapters,
            paragraphs,
            metrics=metrics,
            fingerprint=fingerprint,
            title=title,
            labels=resolved.labels,
            language_name=resolved.name,
            language_key=resolved.key,
            flag_min_severity=fp_thresholds.flag_min_severity,
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
        workspace.ensure_layout()
    changed = 0
    for name, content in artifacts.items():
        is_changed = workspace.publish(name, content, dry_run=args.dry_run)
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lixity",
        description=(
            "Lixity – quantitative text linguistics, stylometry, self-calibrating "
            "style references and single-file dashboards for literary manuscripts."
        ),
        epilog=(
            "Examples:  lixity analyze manuscript.md   |   "
            "lixity style manuscript.md --json   |   "
            "lixity completion bash\n"
            "Docs: https://mfahsold.github.io/lixity/  ·  "
            "Report language: LIXITY_LANG=de"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"lixity {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    from .research.cli import configure as configure_research

    configure_research(sub.add_parser("research", help="Experimental local sources, citations and lexical search (JSON)"))
    for name, help_text in (
        ("analyze", "Corpus metrics (text/JSON, self-describing meta block)"),
        ("profile", "Paragraph-accurate tense/style profiles (JSON)"),
        ("dialogue", "Dialogue turn structure (text/JSON)"),
        ("characters", "Character presence across chapters (text/JSON)"),
        ("pacing", "Scene structure, pacing and chapter hooks (text/JSON)"),
        ("motifs", "Motif tracking and repetition analysis (text/JSON)"),
        ("showing", "Showing vs. telling balance (text/JSON)"),
        ("style", "Self-calibrated style reference of the manuscript (text/JSON, schema v4)"),
        ("dashboard", "Generate a single-file HTML dashboard"),
        ("serve", "Run local HTTP development server and interactive dashboard"),
        ("build", "Idempotent workspace build: exports/ artifacts and nda/ folder"),
        ("about", "Tool metadata for agents: languages, features, heuristics"),
        ("completion", "Shell completion script (bash or zsh)"),
    ):
        p = sub.add_parser(name, help=help_text)
        if name == "completion":
            p.add_argument(
                "shell",
                nargs="?",
                default="bash",
                choices=("bash", "zsh", "sh"),
                help="Target shell (default: bash)",
            )
            continue
        if name == "about":
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name in ("style", "dashboard", "build"):
            p.add_argument("--min-chapters", type=int, default=None,
                           help="Minimum chapters required for a style baseline (default: 2)")
        if name == "build":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: auto-discovery)")
            p.add_argument("--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)")
            p.add_argument("--dry-run", action="store_true", help="Show planned artifacts only")
            p.add_argument(
                "--z-mild", type=float, default=None, help="Notable |z*| threshold (default 2.5)"
            )
            p.add_argument(
                "--z-strong", type=float, default=None, help="Strong |z*| threshold (default 3.5)"
            )
            p.add_argument(
                "--fdr-q", type=float, default=None, help="Benjamini-Hochberg q (default 0.05)"
            )
            p.add_argument(
                "--fdr-method",
                choices=("bh", "by"),
                default=None,
                help="FDR method: bh (Benjamini-Hochberg) or by (Benjamini-Yekutieli)",
            )
            p.add_argument(
                "--dim-threshold",
                type=float,
                default=None,
                help="|dimension score| threshold (default 2.5)",
            )
            p.add_argument(
                "--flag-min-severity",
                type=int,
                choices=(1, 2, 3),
                default=None,
                help="Minimum paragraph severity for flags panel (default 2)",
            )
            continue
        if name == "motifs":
            p.add_argument("file", help="Markdown manuscript")
            p.add_argument(
                "--motif",
                action="append",
                default=[],
                help="Motif as NAME=REGEX (repeatable)",
            )
            p.add_argument("--phrases", type=int, default=3, help="Phrase size (default 3)")
            p.add_argument("--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)")
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name == "characters":
            p.add_argument("file", help="Markdown manuscript")
            p.add_argument(
                "--name",
                action="append",
                default=[],
                help="Figure name or alias pattern (repeatable)",
            )
            p.add_argument("--names", help="Comma-separated figure names")
            p.add_argument("--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)")
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name == "dashboard":
            p.add_argument("file", help="Markdown manuscript")
            p.add_argument("--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)")
            p.add_argument("--names", help="Comma-separated figure names (character panel)")
            p.add_argument("-o", "--output", help="Target file (dashboard)")
            p.add_argument(
                "--z-mild", type=float, default=None, help="Notable |z*| threshold (default 2.5)"
            )
            p.add_argument(
                "--z-strong", type=float, default=None, help="Strong |z*| threshold (default 3.5)"
            )
            p.add_argument(
                "--fdr-q", type=float, default=None, help="Benjamini-Hochberg q (default 0.05)"
            )
            p.add_argument(
                "--fdr-method",
                choices=("bh", "by"),
                default=None,
                help="FDR method: bh or by",
            )
            p.add_argument(
                "--dim-threshold",
                type=float,
                default=None,
                help="|dimension score| threshold (default 2.5)",
            )
            p.add_argument(
                "--flag-min-severity",
                type=int,
                choices=(1, 2, 3),
                default=None,
                help="Minimum paragraph severity for flags panel (default 2)",
            )
            continue
        if name == "serve":
            p.add_argument(
                "path",
                nargs="?",
                default=None,
                help="Manuscript file or workspace folder (default: ambient)",
            )
            p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
            p.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
            p.add_argument("--language", default="auto", help="Language profile (default: auto)")
            p.add_argument("--title", default=None, help="Dashboard title (default: filename)")
            p.add_argument("--open", action="store_true", help="Open dashboard in browser")
            p.add_argument(
                "--no-project",
                action="store_true",
                help="Start without preloading a project",
            )
            p.add_argument(
                "--z-mild", type=float, default=None, help="Notable |z*| threshold (default 2.5)"
            )
            p.add_argument(
                "--z-strong", type=float, default=None, help="Strong |z*| threshold (default 3.5)"
            )
            p.add_argument(
                "--fdr-q", type=float, default=None, help="Benjamini-Hochberg q (default 0.05)"
            )
            p.add_argument(
                "--fdr-method",
                choices=("bh", "by"),
                default=None,
                help="FDR method: bh (Benjamini-Hochberg) or by (Benjamini-Yekutieli)",
            )
            p.add_argument(
                "--dim-threshold",
                type=float,
                default=None,
                help="|dimension score| threshold (default 2.5)",
            )
            p.add_argument(
                "--flag-min-severity",
                type=int,
                choices=(1, 2, 3),
                default=None,
                help="Minimum paragraph severity for flags panel (default 2)",
            )
            continue
        p.add_argument("file", help="Markdown manuscript")
        p.add_argument("--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)")
        p.add_argument(
            "--json", action="store_true", help="JSON output (analyze/profile/style/dialogue)"
        )
        p.add_argument("-o", "--output", help="Target file (dashboard)")
        p.add_argument(
            "--z-mild", type=float, default=None, help="Notable |z*| threshold (default 2.5)"
        )
        p.add_argument(
            "--z-strong", type=float, default=None, help="Strong |z*| threshold (default 3.5)"
        )
        p.add_argument(
            "--fdr-q", type=float, default=None, help="Benjamini-Hochberg q (default 0.05)"
        )
        p.add_argument(
            "--fdr-method",
            choices=("bh", "by"),
            default=None,
            help="FDR method: bh or by",
        )
        p.add_argument(
            "--dim-threshold",
            type=float,
            default=None,
            help="|dimension score| threshold (default 2.5)",
        )
        p.add_argument(
            "--flag-min-severity",
            type=int,
            choices=(1, 2, 3),
            default=None,
            help="Minimum paragraph severity for flags panel (default 2)",
        )
    args = parser.parse_args(argv)
    if args.command == "research":
        from .research.cli import run as run_research

        return run_research(args)
    if getattr(args, "min_chapters", None) is not None and args.min_chapters < 2:
        parser.error("--min-chapters must be at least 2")
    project_config = load_project_config(getattr(args, "file", None))
    args._project_config = project_config
    if hasattr(args, "language") and args.language is None:
        args.language = project_config.get("language", "en")

    if args.command == "completion":
        shell = (args.shell or "bash").strip().lower()
        if shell in ("bash", "sh"):
            sys.stdout.write(_BASH_COMPLETION)
            return EXIT_OK
        if shell == "zsh":
            sys.stdout.write(_ZSH_COMPLETION)
            return EXIT_OK
        # argparse choices already rejected unknown shells; keep a defensive path
        print(f"{_m('err_prefix')} {_m('err_shell', shell=args.shell)}", file=sys.stderr)
        return EXIT_ERROR

    if args.command == "about":
        _print_about_json() if args.json else _print_about_text()
        return EXIT_OK

    if args.command == "serve":
        from .server import run_server

        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        try:
            run_server(
                target_path=args.path,
                host=args.host,
                port=args.port,
                language=args.language,
                title=args.title,
                no_project=args.no_project,
                thresholds=fp_thresholds,
                open_browser=args.open,
            )
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR

    if args.command == "build":
        return _cmd_build(args)

    if args.command == "dialogue":
        return _cmd_dialogue(args)

    if args.command == "characters":
        return _cmd_characters(args)

    if args.command == "pacing":
        return _cmd_pacing(args)

    if args.command == "motifs":
        return _cmd_motifs(args)

    if args.command == "showing":
        return _cmd_showing(args)

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    config, resolved = resolve_document_config(text, args.language)

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        if args.json:
            payload = _meta_payload(resolved.key, metrics=metrics.model_dump())
            print(_json(payload))
        else:
            ReportFormatter.print_rich_report(metrics, language_key=resolved.key)
        return EXIT_OK

    if args.command == "profile":
        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        paragraphs, chapters = profile_document(text, config, fp_thresholds)
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

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    fingerprint = analysis.fingerprint
    from .characters import presence_report
    from .dialogue import dialogue_report

    names = [
        part.strip() for part in (getattr(args, "names", None) or "").split(",") if part.strip()
    ]
    html = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, names, config) if names else None,
        title=_document_title(args, args.file),
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        flag_min_severity=fp_thresholds.flag_min_severity,
    )
    output = args.output or "lixity-dashboard.html"
    changed = FileUtils.atomic_write_if_changed(output, html)
    print(_m("dashboard_written" if changed else "dashboard_unchanged", output=output))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
