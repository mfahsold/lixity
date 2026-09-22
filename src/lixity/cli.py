"""Lixity – command line: corpus analysis, style profile, passport and dashboard."""

import argparse
import json
import os
import sys

from . import __version__
from .analyzer import CorpusAnalyzer
from .formatters import ReportFormatter
from .io import FileUtils
from .language import resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import CorpusConfig
from .style_fingerprint import StyleFingerprint
from .style_profile import ParagraphProfiler
from .visualizer import render_dashboard
from .workspace import discover

EXIT_OK = 0
EXIT_ERROR = 1

_META = {
    "tool": "lixity",
    "version": __version__,
    "schema_version": 1,
}

_BASH_COMPLETION = """# bash completion for lixity – source this file or add it to bash_completion.d/
_lixity_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmds="analyze profile dashboard style build about completion"
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

    print(json.dumps(about(), ensure_ascii=False, indent=2))


def _print_about_text() -> None:
    from .api import about

    data = about()
    print(f"lixity {data['meta']['version']} – quantitative Textlinguistik & Stilometrie")
    print(f"Sprachen: {', '.join(data['languages'])}")
    print(f"Merkmale ({len(data['features'])}):")
    for feat in data["features"]:
        print(f"  {feat['field']:<24} [{feat['unit']}]")
    heuristics = data["heuristics"]
    print(
        "Heuristiken: "
        f"z_mild={heuristics['z_mild']}, z_strong={heuristics['z_strong']}, "
        f"FDR q={heuristics['fdr_q']}, min_chapters={heuristics['min_chapters']}, "
        f"Dimensionen={heuristics['n_dimensions']}"
    )
    print(f"Lizenz: {data['license']}")


def _cmd_build(args) -> int:
    """Idempotent workspace build: analyzes the manuscript and publishes artifacts."""
    try:
        workspace = discover(explicit=args.file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[Fehler] {exc}", file=sys.stderr)
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
        f"{workspace.slug}_metrics.json": json.dumps(
            _meta_payload(resolved.key, metrics=metrics.model_dump()),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        f"{workspace.slug}_profile.json": json.dumps(
            _meta_payload(
                resolved.key,
                chapters=[c.__dict__ for c in chapters],
                paragraphs=[
                    {k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs
                ],
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        f"{workspace.slug}_style.json": json.dumps(
            fingerprint.passport(), ensure_ascii=False, indent=2
        )
        + "\n",
        f"{workspace.slug}_style_passport.txt": fingerprint.passport_text(
            labels=resolved.labels, language_key=resolved.key
        )
        + "\n",
        f"{workspace.slug}_report.md": ReportFormatter.format_markdown_report(
            metrics, texts=resolved.labels, language_key=resolved.key
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

    print(f"Workspace: {workspace.root}")
    print(f"Manuskript: {os.path.basename(workspace.manuscript)} (Sprache: {resolved.key})")
    if not args.dry_run:
        workspace.ensure_layout()
    changed = 0
    for name, content in artifacts.items():
        is_changed = workspace.publish(name, content, dry_run=args.dry_run)
        changed += is_changed
        prefix = "(dry-run) " if args.dry_run else ""
        state = "geschrieben" if is_changed else "unverändert"
        print(f"  {prefix}{state:<13} exports/{name}")
    unchanged = len(artifacts) - changed
    if args.dry_run:
        print(f"Dry-Run: {changed} zu schreiben, {unchanged} unverändert – keine Dateien geändert.")
    else:
        print(f"Fertig: {changed} geschrieben, {unchanged} unverändert · nda/ bereit.")
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lixity",
        description=(
            "Lixity – quantitative text linguistics, stylometry, self-calibrating "
            "style passports and single-file dashboards for literary manuscripts."
        ),
    )
    parser.add_argument("--version", action="version", version=f"lixity {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("analyze", "Corpus metrics (text/JSON, self-describing meta block)"),
        ("profile", "Paragraph-accurate tense/style profiles (JSON)"),
        ("style", "Self-calibrated style passport of the manuscript (text/JSON)"),
        ("dashboard", "Generate a single-file HTML dashboard"),
        ("build", "Idempotent workspace build: exports/ artifacts and nda/ folder"),
        ("about", "Tool metadata for agents: languages, features, heuristics"),
        ("completion", "Shell completion script (bash or zsh)"),
    ):
        p = sub.add_parser(name, help=help_text)
        if name in ("completion", "about"):
            p.add_argument("shell", nargs="?", default="bash", help="bash|zsh (completion)")
            continue
        if name == "build":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: auto-discovery)")
            p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
            p.add_argument("--dry-run", action="store_true", help="Show planned artifacts only")
            continue
        p.add_argument("file", help="Markdown manuscript")
        p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
        p.add_argument("--json", action="store_true", help="JSON output (analyze/profile/style)")
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
        print(f"[Fehler] Unbekannte Shell: {args.shell} (bash|zsh)", file=sys.stderr)
        return EXIT_ERROR

    if args.command == "about":
        if args.shell and args.shell != "bash":
            print(f"[Fehler] Unbekanntes Argument: {args.shell}", file=sys.stderr)
            return EXIT_ERROR
        _print_about_json() if "--json" in (argv or []) else _print_about_text()
        return EXIT_OK

    if args.command == "build":
        return _cmd_build(args)

    try:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
    except OSError as exc:
        print(f"[Fehler] Datei nicht lesbar: {args.file} ({exc})", file=sys.stderr)
        return EXIT_ERROR

    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        if args.json:
            payload = _meta_payload(resolved.key, metrics=metrics.model_dump())
            print(json.dumps(payload, ensure_ascii=False))
        else:
            ReportFormatter.print_rich_report(
                metrics, texts=resolved.labels, language_key=resolved.key
            )
        return EXIT_OK

    if args.command == "profile":
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
        payload = _meta_payload(
            resolved.key,
            chapters=[c.__dict__ for c in chapters],
            paragraphs=[{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return EXIT_OK

    if args.command == "style":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        fingerprint = StyleFingerprint.from_metrics(metrics)
        if args.json:
            print(json.dumps(fingerprint.passport(), ensure_ascii=False, indent=2))
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
    state = "written" if changed else "unchanged"
    print(f"Dashboard {state}: {output}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
