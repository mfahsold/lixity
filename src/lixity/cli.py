"""Lixity – command line: corpus analysis, style profile and dashboard."""

import argparse
import json
import sys

from .analyzer import CorpusAnalyzer
from .formatters import ReportFormatter
from .language import resolve_language
from .markdown_parser import parse_markdown_blocks
from .models import CorpusConfig
from .style_profile import ParagraphProfiler
from .visualizer import render_dashboard


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lixity",
        description="Lixity – quantitative text linguistics, stylometry and style dashboards.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("analyze", "Print corpus metrics (text/JSON)"),
        ("profile", "Paragraph-accurate tense profiles (JSON)"),
        ("dashboard", "Generate a single-file HTML dashboard"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("file", help="Markdown manuscript")
        p.add_argument("--language", default="auto", help="de|en|fr|es|it|pt|nl|generic|auto")
        p.add_argument("--json", action="store_true", help="JSON output (analyze/profile)")
        p.add_argument("--output", help="Target file (dashboard)")
    args = parser.parse_args(argv)

    with open(args.file, "r", encoding="utf-8") as f:
        text = f.read()
    config = CorpusConfig(language=args.language)
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config).analyze_text(text)
        if args.json:
            print(ReportFormatter.to_json(metrics))
        else:
            ReportFormatter.print_rich_report(metrics, texts=resolved.labels)
        return 0

    if args.command == "profile":
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
        payload = {
            "language": resolved.key,
            "chapters": [c.__dict__ for c in chapters],
            "paragraphs": [{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    html = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        title=os.path.basename(args.file),
        labels=resolved.labels,
        language_name=resolved.name,
    )
    output = args.output or "lixity-dashboard.html"
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard written: {output}")
    return 0


if __name__ == "__main__":
    import os  # noqa: E402
    sys.exit(main())
