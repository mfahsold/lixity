"""Lixity – command line: corpus analysis, style profile, style reference and dashboard."""

import argparse
import os
import sys

import orjson
from rich import box
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import CorpusAnalyzer
from .formatters import ReportFormatter
from .io import FileUtils
from .language import resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import SCHEMA_VERSION, CorpusConfig
from .style_fingerprint import StyleFingerprint
from .style_profile import ParagraphProfiler
from .ui import render_dashboard
from .workspace import discover

EXIT_OK = 0
EXIT_ERROR = 1


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
# LIXITY_LANG=de (the book project uses this for its German control UI).
CLI_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "about_title": "lixity {version} – quantitative text linguistics & stylometry",
        "about_languages": "Languages: {languages}",
        "about_features": "Features ({count}):",
        "about_heuristics": (
            "Heuristics: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, dimensions={n_dimensions}"
        ),
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
    },
    "de": {
        "about_title": "lixity {version} – quantitative Textlinguistik & Stilometrie",
        "about_languages": "Sprachen: {languages}",
        "about_features": "Merkmale ({count}):",
        "about_heuristics": (
            "Heuristiken: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, Dimensionen={n_dimensions}"
        ),
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
_lixity_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmds="analyze profile dialogue characters dashboard style build about completion"
    local opts="--language --json --output --help"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds" -- "$cur") )
        return 0
    fi
    case "$prev" in
        --language)
            COMPREPLY=( $(compgen -W "auto de en fr es it pt nl generic" -- "$cur") )
            return 0
            ;;
        -o|--output)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
    esac
    COMPREPLY=( $(compgen -W "$opts" -- "$cur") )
    COMPREPLY+=( $(compgen -f -- "$cur") )
}
complete -F _lixity_complete lixity
"""

_ZSH_COMPLETION = """#compdef lixity
# zsh completion for lixity – place in a directory of $fpath
_lixity() {
    _arguments \
        '1:command:(analyze profile dashboard style about completion)' \
        '*:file:_files' \
        '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
        '--json[JSON output]' \
        '-o[output file]:file:_files' \
        '--output[output file]:file:_files'
}
compdef _lixity lixity
"""


def _meta_payload(language_key: str, **body) -> dict:
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
    print(_m("about_license", license=data["license"]))


def _cmd_dialogue(args) -> int:
    """Dialogue turn structure as a Rich table or JSON."""
    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .dialogue import dialogue_report

    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)
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


def _cmd_characters(args) -> int:
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

    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)
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


def _cmd_build(args) -> int:
    """Idempotent workspace build: analyzes the manuscript and publishes artifacts."""
    try:
        workspace = discover(explicit=args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    text = workspace.read_manuscript()
    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)

    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    fingerprint = StyleFingerprint.from_metrics(metrics)
    title = os.path.splitext(os.path.basename(workspace.manuscript))[0]

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


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lixity",
        description=(
            "Lixity – quantitative text linguistics, stylometry, self-calibrating "
            "style references and single-file dashboards for literary manuscripts."
        ),
    )
    parser.add_argument("--version", action="version", version=f"lixity {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("analyze", "Corpus metrics (text/JSON, self-describing meta block)"),
        ("profile", "Paragraph-accurate tense/style profiles (JSON)"),
        ("dialogue", "Dialogue turn structure (text/JSON)"),
        ("characters", "Character presence across chapters (text/JSON)"),
        ("style", "Self-calibrated style reference of the manuscript (text/JSON)"),
        ("dashboard", "Generate a single-file HTML dashboard"),
        ("build", "Idempotent workspace build: exports/ artifacts and nda/ folder"),
        ("about", "Tool metadata for agents: languages, features, heuristics"),
        ("completion", "Shell completion script (bash or zsh)"),
    ):
        p = sub.add_parser(name, help=help_text)
        if name == "completion":
            p.add_argument("shell", nargs="?", default="bash", help="bash|zsh")
            continue
        if name == "about":
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name == "build":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: auto-discovery)")
            p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
            p.add_argument("--dry-run", action="store_true", help="Show planned artifacts only")
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
            p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        p.add_argument("file", help="Markdown manuscript")
        p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
        p.add_argument(
            "--json", action="store_true", help="JSON output (analyze/profile/style/dialogue)"
        )
        p.add_argument("-o", "--output", help="Target file (dashboard)")
    args = parser.parse_args(argv)

    if args.command == "completion":
        shell = (args.shell or "bash").strip().lower()
        if shell in ("bash", "sh"):
            sys.stdout.write(_BASH_COMPLETION)
            return EXIT_OK
        if shell == "zsh":
            sys.stdout.write(_ZSH_COMPLETION)
            return EXIT_OK
        print(f"{_m('err_prefix')} {_m('err_shell', shell=args.shell)}", file=sys.stderr)
        return EXIT_ERROR

    if args.command == "about":
        _print_about_json() if args.json else _print_about_text()
        return EXIT_OK

    if args.command == "build":
        return _cmd_build(args)

    if args.command == "dialogue":
        return _cmd_dialogue(args)

    if args.command == "characters":
        return _cmd_characters(args)

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        if args.json:
            payload = _meta_payload(resolved.key, metrics=metrics.model_dump())
            print(_json(payload))
        else:
            ReportFormatter.print_rich_report(metrics, language_key=resolved.key)
        return EXIT_OK

    if args.command == "profile":
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
        payload = _meta_payload(
            resolved.key,
            chapters=[c.__dict__ for c in chapters],
            paragraphs=[{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
        )
        print(_json(payload, indent=True))
        return EXIT_OK

    if args.command == "style":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        if args.json:
            print(_json(fingerprint.passport(), indent=True))
        else:
            print(fingerprint.passport_text(labels=resolved.labels, language_key=resolved.key))
        return EXIT_OK

    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    fingerprint = StyleFingerprint.from_metrics(metrics)
    html = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        title=os.path.basename(args.file),
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
    )
    output = args.output or "lixity-dashboard.html"
    changed = FileUtils.atomic_write_if_changed(output, html)
    print(_m("dashboard_written" if changed else "dashboard_unchanged", output=output))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
