"""Read-only, author-curated context with optional manuscript reading."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..workspace_labels import WORKSPACE_LABELS
from .components import esc, label, product_details
from .dashboard import _CSS_FILES, _PUBLICATION_JS_FILES, _bundle, _script_json
from .manuscript_document import ReaderBlock, reader_block_html


def render_publication(
    publication: Mapping[str, Any], *, reader_document: Sequence[ReaderBlock] | None = None,
    labels: Mapping[str, str] | None = None, language_key: str = "en",
    resources: Mapping[str, str] | None = None,
) -> str:
    """Render only prepared public content; progress is not a privacy boundary.

    The assembler omits material beyond the exported chapter cap before this
    function receives it. Companion mode receives no manuscript blocks.
    """
    if publication.get("mode") not in {"reader", "companion"}:
        raise ValueError("A curated publication mode is required")
    if publication["mode"] == "companion" and reader_document:
        raise ValueError("Companion websites must not contain manuscript blocks")
    def L(key: str) -> str:
        return esc(label(labels, key))
    def chapter(number: int) -> str:
        return esc(label(labels, "publication_chapter").format(number=number))
    cap = publication["max_chapter"]
    if type(cap) is not int or cap < 0:
        raise ValueError("A bounded publication chapter cap is required")
    choices = f'<option value="0">{L("publication_before")}</option>' + ''.join(
        f'<option value="{number}">{chapter(number)}</option>' for number in range(1, cap + 1))
    reading = publication["mode"] == "reader"
    language = language_key if language_key not in {"generic", "auto"} else "en"
    title = esc(publication["title"])
    ui_labels = {**WORKSPACE_LABELS.get(language, WORKSPACE_LABELS["en"]), **(labels or {})}
    # A keyword is deliberately conservative: false positives retain the library.
    # Inspect every prepared entry, including content revealed after later chapters.
    has_diagrams = any("mermaid" in text.casefold() for text in (
        publication.get("introduction", ""),
        *(entry["body"] for entry in publication.get("entries", ())),
    ))
    progress = [
        '<section class="publication-progress-controls" aria-labelledby="publication-progress-title">',
        f'<h2 id="publication-progress-title">{L("publication_progress")}</h2>',
        '<form id="publication-progress-form" class="row">',
        f'<label for="publication-progress">{L("publication_finished")}</label>',
        f'<select class="ctl" id="publication-progress">{choices}</select>',
        f'<button type="submit" class="ctl primary" id="publication-progress-apply">{L("apply")}</button>',
        f'<button type="button" class="ctl" id="publication-progress-reset">{L("dim_ctl_reset")}</button></form>',
        f'<button type="button" class="ctl" id="publication-preview-open" aria-expanded="false" aria-controls="publication-preview-form">{L("publication_preview_later")}</button>',
        '<form class="row publication-preview" id="publication-preview-form" hidden>',
        f'<label for="publication-preview-progress">{L("publication_preview_through")}</label>',
        f'<select class="ctl" id="publication-preview-progress">{choices}</select>',
        f'<button type="submit" class="ctl">{L("publication_preview")}</button>',
        f'<button type="button" class="ctl" id="publication-preview-close">{L("publication_preview_close")}</button></form>',
        '<p class="ctl-note" id="publication-progress-status" role="status" aria-live="polite"></p></section>',
        f'<p class="ctl-note publication-scope">{esc(label(labels, "publication_scope").format(chapter=label(labels, "publication_before") if cap == 0 else label(labels, "publication_chapter").format(number=cap)))}</p>',
    ]
    parts = [
        '<!DOCTYPE html>', f'<html lang="{esc(language)}"><head><meta charset="utf-8"/>',
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
        '<link rel="icon" href="data:,"/>', f'<title>{title} · Lixity</title>',
        f'<style>{_bundle(_CSS_FILES)}</style></head>',
        f'<body class="lixity-report publication-site manuscript-reading" data-read-only="true" '
        f'data-ui-labels="{esc(_script_json(ui_labels))}">',
        f'<a class="skip-link" href="#publication-context">{L("publication_context")}</a>',
        '<div class="page" id="reader-publication">',
        f'<header class="publication-header"><h1>{title}</h1><p>{L("publication_read_only")}</p></header>',
    ]
    if publication.get("introduction", "").strip():
        parts.append(f'<div class="research-prose markdown-body publication-introduction">{esc(publication["introduction"])}</div>')
    parts.extend([
        '<div class="publication-reading-layout">',
    ])
    if reading:
        parts.extend(['<section class="publication-novel" aria-label="' + L("manuscript") + '">',
                      '<nav class="row publication-reading-controls">',
                      f'<a class="ctl" href="#publication-context">{L("publication_context")}</a>',
                      f'<label for="publication-reader-chapter">{L("reading_chapter")}</label>',
                      '<select class="ctl" id="publication-reader-chapter"><option value="">' + L("reading_chapter") + '…</option>' + ''.join(
                          f'<option value="publication-chapter-{number}">{chapter(number)}</option>' for number in range(1, cap + 1)) + '</select></nav>',
                      '<main id="chapters" tabindex="-1">'])
        opened = False
        number = 0
        for block in reader_document or ():
            if block.is_chapter:
                if opened:
                    parts.append('</section>')
                number += 1
                heading = esc(block.text) if block.text else chapter(number)
                parts.append(f'<section class="chapter" id="publication-chapter-{number}"><div class="chapter-head"><h2>{heading}</h2></div>')
                opened = True
            else:
                parts.append(reader_block_html(block, heading_level=block.level + 1))
        if opened:
            parts.append('</section>')
        parts.append('</main></section>')
    parts.extend([
        '<aside class="publication-context panel" id="publication-context" aria-labelledby="publication-context-title">',
        f'<h2 id="publication-context-title">{L("publication_context")}</h2>',
        *progress,
        f'<label for="publication-context-search">{L("publication_search")}</label>',
        '<input type="search" class="ctl" id="publication-context-search"/>',
        '<p class="ctl-note" id="publication-context-count" role="status" aria-live="polite"></p>',
        f'<nav id="publication-contents" aria-label="{L("research_sections")}"></nav>',
        '<div id="publication-entries"></div>',
        f'<noscript><p>{L("publication_javascript")}</p></noscript></aside></div>',
        '<footer>' + product_details(labels) + '</footer></div>',
        *(('<script type="application/json" id="research-diagram-library">' +
           _script_json(_bundle(("vendor/mermaid-tiny-12.2.0.min.js",))) + '</script>',)
          if has_diagrams else ()),
        '<script>' + _bundle(_PUBLICATION_JS_FILES) + '</script></body></html>',
    ])
    return '\n'.join(parts) + '\n'
