"""Displayed anchor text shares the full profiler's existing Markdown scope."""

import hashlib

import pytest

from lixity.models import CorpusConfig
from lixity.pipeline import paragraph_identity, profile_document
from lixity.style_fingerprint import FingerprintThresholds


@pytest.mark.parametrize(
    "text, settings, expected",
    [
        (
            "---\ntitle: Synthetic\n---\n\n# Title\n\n## Empty\n\n```md\nIgnored.\n```\n\n"
            "## First\n\nThe **room** is open.  \nA visitor arrived.\n\n> Quoted text.\n\n"
            "- A [label](https://example.org) `code`.\n\n[^note]: A footnote.\n\n"
            "## Appendix\n\nExcluded body.\n",
            {"appendix_marker": "## Appendix"},
            [(15, 16, "The room is open.\nA visitor arrived."),
             (20, 20, "A [label](https://example.org) `code`.")],
        ),
        ("An implicit **chapter**.\n\n> Quoted only.\n\n- A list item.\n", {},
         [(1, 1, "An implicit chapter."), (5, 5, "A list item.")]),
        ("CHAPTER One\n\nThe **door** opens.\n\nCHAPTER Empty\n\n> Quote only.\n\n"
         "CHAPTER Two\n\nA visitor waits.\n", {"chapter_regex": r"(?m)^CHAPTER\s+"},
         [(3, 3, "The door opens."), (11, 11, "A visitor waits.")]),
        ("## One\n\n<!-- hidden\ncomment -->\nThe **window** opens.\n\n!!!\n", {},
         [(5, 5, "The window opens."), (7, 7, "!!!")]),
        ("## One\n\n> Quote only.\n\n## Two\n\n`code`\n\n![image](image.png)\n", {},
         [(7, 7, "`code`"), (9, 9, "![image](image.png)")]),
    ],
)
def test_projection_preserves_literal_display_text_lines_and_hashes(text, settings, expected):
    from lixity.pipeline import document_paragraph_texts

    config = CorpusConfig(**settings)
    projected = document_paragraph_texts(text, config)
    profiles, _ = profile_document(text, config, FingerprintThresholds())
    wanted = [{"start_line": start, "end_line": end,
               "paragraph_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest()}
              for start, end, display in expected]
    assert [(p.start_line, p.end_line, p.text) for p in projected] == expected
    assert [paragraph_identity(p) for p in projected] == wanted
    assert [(p.start_line, p.end_line, p.text) for p in profiles] == expected
    assert [paragraph_identity(p) for p in profiles] == wanted


def test_projection_keeps_explicit_word_pattern_chapter_membership():
    from lixity.pipeline import document_paragraph_texts

    config = CorpusConfig(word_regex=r"\d+")
    text = "## Empty\n\nWords only.\n\n## Accepted\n\nNumber **42**.\n"
    projected = document_paragraph_texts(text, config)
    assert [(p.start_line, p.end_line, p.text) for p in projected] == [(7, 7, "Number 42.")]


def test_manual_profile_blocks_keep_chapter_end_when_paragraph_end_is_missing():
    from lixity.style_profile import ParagraphProfiler

    blocks = [
        {"type": "h2", "text": "One", "start_line": 1, "end_line": 2},
        {"type": "p", "text": "The visitor arrives.", "start_line": 3, "end_line": 4},
        {"type": "p", "text": "The door opens.", "start_line": 5},
        {"type": "h2", "text": "Two", "start_line": 10, "end_line": 11},
        {"type": "p", "text": "The reader waits.", "start_line": 12},
    ]
    paragraphs, chapters = ParagraphProfiler().profile_blocks(blocks)
    assert [(p.start_line, p.end_line) for p in paragraphs] == [(3, 4), (5, 0), (12, 0)]
    assert [(c.start_line, c.end_line) for c in chapters] == [(1, 4), (10, 11)]
