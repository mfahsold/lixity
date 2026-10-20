"""Faithful presentation projection, separate from analysis prose filtering."""

import importlib

import pytest

from lixity.models import CorpusConfig


def test_projection_keeps_preface_structure_notes_and_appendix():
    projection = importlib.import_module("lixity.manuscript_document")
    source = """---
title: Hidden metadata
---
# A Synthetic Voyage

Before the first chapter.[^origin]

<!-- An editorial comment. -->
## Departure

### At the quay

> A quoted warning.

- Rope
* Compass
1. First watch
2. Second watch
+ Lamp

***

[^origin]: An endnote.
## Anmerkungen und Literaturverzeichnis

Appendix remains in the export.
"""

    sections = projection.manuscript_sections(source, CorpusConfig())

    assert [(title, [(block.kind, block.text, block.level) for block in blocks])
            for title, blocks in sections] == [
        ("", [("paragraph", "Before the first chapter.[^origin]", 3)]),
        ("Departure", [
            ("heading", "At the quay", 3),
            ("quote", "A quoted warning.", 3),
            ("list_item", "- Rope", 3),
            ("list_item", "* Compass", 3),
            ("list_item", "1. First watch", 3),
            ("list_item", "2. Second watch", 3),
            ("list_item", "+ Lamp", 3),
            ("scene_break", "* * *", 3),
            ("note", "[origin] An endnote.", 3),
        ]),
        ("Anmerkungen und Literaturverzeichnis", [
            ("paragraph", "Appendix remains in the export.", 3),
        ]),
    ]


def test_projection_obeys_configured_chapters_without_discarding_empty_chapters():
    projection = importlib.import_module("lixity.manuscript_document")
    source = "# Title\n\nIntroduction.\n\nCHAPTER I\n\n## A subheading\n\nCHAPTER II\n"
    sections = projection.manuscript_sections(
        source, CorpusConfig(chapter_regex=r"^CHAPTER\s+", appendix_marker=""),
    )

    assert [title for title, _blocks in sections] == ["", "I", "II"]
    assert [(block.kind, block.text, block.level) for block in sections[1][1]] == [
        ("heading", "A subheading", 2),
    ]
    assert sections[2][1] == []


def test_inline_runs_preserve_markdown_styles_links_footnotes_and_literal_code():
    projection = importlib.import_module("lixity.manuscript_document")
    runs = projection.inline_runs(
        r"Plain *soft* **firm** ***both*** _also soft_ [port](https://example.test) "
        r"and [^n], `\input{never} *literal*`."
    )

    assert [(run.text, run.style) for run in runs] == [
        ("Plain ", "plain"), ("soft", "emphasis"), (" ", "plain"),
        ("firm", "strong"), (" ", "plain"), ("both", "strong_emphasis"),
        (" ", "plain"), ("also soft", "emphasis"),
        (" port and [n], ", "plain"), (r"\input{never} *literal*", "code"),
        (".", "plain"),
    ]


def test_inline_runs_support_nested_tex_groups_and_escaped_punctuation():
    projection = importlib.import_module("lixity.manuscript_document")
    runs = projection.inline_runs(
        r"\textbf{Firm \emph{and {nested} \{literal\}} \textnormal{ordinary}} "
        r"\texttt{code\_word} \% \& \# \$ \\Next"
    )

    assert [(run.text, run.style) for run in runs] == [
        ("Firm ", "strong"), ("and nested {literal}", "strong_emphasis"),
        (" ", "strong"), ("ordinary ", "plain"),
        ("code_word", "code"), (" % & # $ \nNext", "plain"),
    ]


def test_markdown_emphasis_can_span_embedded_tex():
    projection = importlib.import_module("lixity.manuscript_document")
    assert [(run.text, run.style) for run in projection.inline_runs(
        r"*Quiet \textbf{certainty} today.*"
    )] == [
        ("Quiet ", "emphasis"), ("certainty", "strong_emphasis"),
        (" today.", "emphasis"),
    ]


def test_images_have_explicit_readable_alternative_and_reference():
    projection = importlib.import_module("lixity.manuscript_document")
    runs = projection.inline_runs("See ![A pier](private/pier.png) and ![Map][map].")
    assert "".join(run.text for run in runs) == (
        "See [Image: A pier; reference: private/pier.png] and [Image: Map; reference: map]."
    )


def test_code_is_literal_and_comments_metadata_are_hidden():
    projection = importlib.import_module("lixity.manuscript_document")
    source = r"""---
title: \unsupported{hidden}
---
# A title

<!-- \unsupported{hidden} -->
Visible `<!-- literal --> \input{never}`.

```tex
\input{never}
<!-- literal -->
## not a chapter
```

    \write18{never}
"""
    sections = projection.manuscript_sections(source, CorpusConfig())
    assert len(sections) == 1
    assert [block.kind for block in sections[0][1]] == ["paragraph", "code", "code"]
    assert sections[0][1][0].text == r"Visible `<!-- literal --> \input{never}`."
    assert sections[0][1][1].text == (
        "\\input{never}\n<!-- literal -->\n## not a chapter"
    )
    assert sections[0][1][2].text == r"\write18{never}"


def test_notes_move_to_the_end_of_their_section_without_swallowing_prose():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "## One\n\nA reference.[^n]\n\n[^n]: Note.\n\nFollowing prose.\n",
        CorpusConfig(),
    )
    assert [(block.kind, block.text) for block in sections[0][1]] == [
        ("paragraph", "A reference.[^n]"),
        ("paragraph", "Following prose."),
        ("note", "[n] Note."),
    ]


def test_pagebreaks_and_hard_linebreaks_survive_projection():
    projection = importlib.import_module("lixity.manuscript_document")
    source = "# Title\n\n## One\nFirst  \nSecond\\\\\nThird\n\\newpage\nFourth\n\\clearpage\n"
    blocks = projection.manuscript_sections(source, CorpusConfig())[0][1]
    assert [block.kind for block in blocks] == [
        "paragraph", "page_break", "paragraph", "page_break",
    ]
    assert "".join(run.text for run in projection.inline_runs(blocks[0].text)) == (
        "First\nSecond\nThird"
    )


@pytest.mark.parametrize("command", [r"\input{file}", r"\write18{shell}", r"\frac{1}{2}"])
def test_unsupported_tex_names_the_original_manuscript_line(command):
    projection = importlib.import_module("lixity.manuscript_document")
    with pytest.raises(ValueError, match=r"Unsupported TeX.*line 7") as error:
        projection.manuscript_sections(
            "---\ntitle: A title\n---\n# Title\n\n## One\n" + command,
            CorpusConfig(),
        )
    assert command.split("{", 1)[0] in str(error.value)


@pytest.mark.parametrize("source", [r"\textbf{unclosed", r"\emph missing", r"\(x + y\)"])
def test_malformed_or_unsupported_tex_fails_explicitly(source):
    projection = importlib.import_module("lixity.manuscript_document")
    with pytest.raises(ValueError, match=r"TeX.*line 1"):
        projection.inline_runs(source)


def test_currency_is_plain_prose():
    projection = importlib.import_module("lixity.manuscript_document")
    assert [(run.text, run.style) for run in projection.inline_runs(
        "The fares are $5, $10 and $12.50."
    )] == [("The fares are $5, $10 and $12.50.", "plain")]


def test_emph_toggles_but_textit_retains_italic():
    projection = importlib.import_module("lixity.manuscript_document")
    assert [(run.text, run.style) for run in projection.inline_runs(
        r"\emph{outer \emph{inner} outer} \textit{outer \textit{inner} outer}"
    )] == [
        ("outer ", "emphasis"), ("inner", "plain"), (" outer", "emphasis"),
        (" ", "plain"), ("outer inner outer", "emphasis"),
    ]


def test_obvious_windows_paths_and_image_references_are_literal_data():
    projection = importlib.import_module("lixity.manuscript_document")
    assert "".join(run.text for run in projection.inline_runs(
        r"Read C:\draft\notes.txt or \\server\draft\notes.txt and ![Map](C:\draft\map.png)."
    )) == (
        r"Read C:\draft\notes.txt or \\server\draft\notes.txt and "
        r"[Image: Map; reference: C:\draft\map.png]."
    )


@pytest.mark.parametrize("source", ["$x$", "$2 + 2$", "$$x = 1$$", r"\[x = 1\]"])
def test_obvious_math_fails_instead_of_appearing_typeset(source):
    projection = importlib.import_module("lixity.manuscript_document")
    with pytest.raises(ValueError, match=r"Unsupported TeX.*line 1"):
        projection.inline_runs(source)


def test_open_html_comment_inside_code_does_not_hide_later_chapters():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "## One\n\n```text\n<!-- literal opening\n```\n\n## Two\n\nVisible.\n",
        CorpusConfig(),
    )
    assert [title for title, _blocks in sections] == ["One", "Two"]
    assert sections[0][1][0].text == "<!-- literal opening"
    assert sections[1][1][0].text == "Visible."


def test_tex_in_indented_note_continuation_is_validated():
    projection = importlib.import_module("lixity.manuscript_document")
    with pytest.raises(ValueError, match=r"Unsupported TeX.*line 4"):
        projection.manuscript_sections(
            "## One\n\n[^n]: A note.\n    \\input{hidden}\n", CorpusConfig(),
        )


def test_texttt_does_not_interpret_markdown_punctuation():
    projection = importlib.import_module("lixity.manuscript_document")
    assert [(run.text, run.style) for run in projection.inline_runs(
        r"\texttt{*literal* \{braces\} and \_underscores\_}"
    )] == [("*literal* {braces} and _underscores_", "code")]


def test_links_keep_their_label_and_do_not_interpret_destination_as_tex():
    projection = importlib.import_module("lixity.manuscript_document")
    assert "".join(run.text for run in projection.inline_runs(
        r"Read [the draft](C:\draft\notes.txt)."
    )) == "Read the draft."


def test_image_references_retain_balanced_parentheses():
    projection = importlib.import_module("lixity.manuscript_document")
    assert "".join(run.text for run in projection.inline_runs(
        "![Pier](images/pier(dawn).png)"
    )) == "[Image: Pier; reference: images/pier(dawn).png]"


def test_multiline_inline_code_keeps_comments_and_tex_literal():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "## One\n\nLiteral `first\n<!-- literal --> \\input{never}`.\n", CorpusConfig(),
    )
    assert "".join(run.text for run in projection.inline_runs(sections[0][1][0].text)) == (
        "Literal first <!-- literal --> \\input{never}."
    )


def test_quotes_and_lists_preserve_explicit_hard_linebreaks():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "## One\n\n> First  \n> Second\n>\n> Separate.\n\n- First  \n  Second\n",
        CorpusConfig(),
    )
    assert [(block.kind, block.text) for block in sections[0][1]] == [
        ("quote", "First\nSecond"), ("quote", "Separate."),
        ("list_item", "- First\nSecond"),
    ]


def test_windows_paths_with_spaced_directories_remain_literal_data():
    projection = importlib.import_module("lixity.manuscript_document")
    source = r"Read C:\Program Files\notes.txt and C:\Other Folder\more notes.txt."
    assert "".join(run.text for run in projection.inline_runs(source)) == source


def test_note_continuation_retains_hard_break_without_becoming_code():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "## One\n\n[^x]: first  \n    second\n", CorpusConfig(),
    )
    assert [(block.kind, block.text) for block in sections[0][1]] == [
        ("note", "[x] first\nsecond"),
    ]


def test_real_document_title_after_literal_code_is_not_repeated_in_body():
    projection = importlib.import_module("lixity.manuscript_document")
    sections = projection.manuscript_sections(
        "```markdown\n# Code example title\n```\n\n# Real document title\n\n"
        "Preface text.\n\n# Later section\n\nLater text.\n\n## Chapter one\n\nBody.\n",
        CorpusConfig(),
    )
    assert [(block.kind, block.text) for block in sections[0][1]] == [
        ("code", "# Code example title"),
        ("paragraph", "Preface text."),
        ("heading", "Later section"),
        ("paragraph", "Later text."),
    ]
    assert sections[1][0] == "Chapter one"


def test_source_projection_retains_order_absolute_spans_and_empty_custom_chapters():
    projection = importlib.import_module("lixity.manuscript_document")
    source = "\r\n".join([
        "---", "title: Synthetic title", "---", "# Synthetic title", "", "Preface.", "",
        "<!-- A comment", "CHAPTER GHOST", "-->", "", "CHAPTER I", "", "### Subheading", "",
        "Body with *emphasis* and note.[^n]", "", "[^n]: The note.", "", "Following prose.", "",
        "> First  ", "> Second.", ">", "> Separate.", "", "~~~text", "## Not a chapter",
        "<!-- literal -->", r"\input{never}", "~~~", "", "1. First watch", "2. Second watch",
        "+ Lamp", "", "***", "", "CHAPTER II", "", "CHAPTER APPENDIX", "", "Appendix.",
    ])
    blocks = projection.manuscript_blocks(
        source, CorpusConfig(chapter_regex=r"^CHAPTER\s+", appendix_marker="CHAPTER APPENDIX"),
    )
    assert [(b.kind, b.text, b.start_line, b.end_line, b.is_chapter) for b in blocks] == [
        ("heading", "Synthetic title", 4, 4, False),
        ("paragraph", "Preface.", 6, 6, False),
        ("heading", "I", 12, 12, True),
        ("heading", "Subheading", 14, 14, False),
        ("paragraph", "Body with *emphasis* and note.[^n]", 16, 16, False),
        ("note", "[n] The note.", 18, 18, False),
        ("paragraph", "Following prose.", 20, 20, False),
        ("quote", "First\nSecond.", 22, 23, False),
        ("quote", "Separate.", 25, 25, False),
        ("code", "## Not a chapter\n<!-- literal -->\n\\input{never}", 27, 31, False),
        ("list_item", "1. First watch", 33, 33, False),
        ("list_item", "2. Second watch", 34, 34, False),
        ("list_item", "+ Lamp", 35, 35, False),
        ("scene_break", "* * *", 37, 37, False),
        ("heading", "II", 39, 39, True),
        ("heading", "APPENDIX", 41, 41, True),
        ("paragraph", "Appendix.", 43, 43, False),
    ]
    assert [b.level for b in blocks if b.kind == "heading"] == [1, 2, 3, 2, 2]


def test_browser_source_projection_keeps_unsupported_tex_and_html_literal():
    projection = importlib.import_module("lixity.manuscript_document")
    source = '# Title\n\n## One\n\n\\input{never} <img src="https://example.test/never">\n'
    blocks = projection.manuscript_blocks(source, CorpusConfig())
    assert [(b.kind, b.text, b.start_line, b.end_line) for b in blocks] == [
        ("heading", "Title", 1, 1), ("heading", "One", 3, 3),
        ("paragraph", '\\input{never} <img src="https://example.test/never">', 5, 5),
    ]
    # The strict PDF adapter remains deliberately different from literal browser display.
    with pytest.raises(ValueError, match=r"Unsupported TeX.*line 5"):
        projection.manuscript_sections(source, CorpusConfig())
