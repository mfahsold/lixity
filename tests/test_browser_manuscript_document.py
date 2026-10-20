"""Source-span joins retain one exact owner for every analytical paragraph."""

import importlib
from dataclasses import asdict, replace

import pytest

from lixity.models import CorpusConfig
from lixity.pipeline import paragraph_identity, profile_document
from lixity.style_fingerprint import FingerprintThresholds


def test_reader_interleaves_structure_without_duplicating_profile_list_owners():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = "\n".join([
        "# Title", "", "Preface.", "", "## One", "", "Repeated prose.", "", "> Quotation.",
        "", "Repeated prose.", "", "1. First watch", "2. Second watch", "+ Lamp", "",
        "[^n]: Note.", "", "Following prose.", "", "## Anmerkungen und Literaturverzeichnis",
        "", "Appendix.",
    ])
    config = CorpusConfig()
    profiles, chapters = profile_document(source, config, FingerprintThresholds())
    before = [asdict(profile) for profile in profiles]
    identities = [paragraph_identity(profile) for profile in profiles]
    assert [(p.start_line, p.end_line, p.text) for p in profiles] == [
        (7, 7, "Repeated prose."), (11, 11, "Repeated prose."),
        (13, 15, "1. First watch 2. Second watch + Lamp"), (19, 19, "Following prose."),
    ]

    blocks = presentation.reader_blocks(source, config, profiles)

    assert [(b.kind, b.text, b.start_line, b.end_line, b.profile_index) for b in blocks] == [
        ("heading", "Title", 1, 1, None), ("paragraph", "Preface.", 3, 3, None),
        ("heading", "One", 5, 5, None), ("profile", "Repeated prose.", 7, 7, 0),
        ("quote", "Quotation.", 9, 9, None), ("profile", "Repeated prose.", 11, 11, 1),
        ("profile", "1. First watch 2. Second watch + Lamp", 13, 15, 2),
        ("note", "[n] Note.", 17, 17, None), ("profile", "Following prose.", 19, 19, 3),
        ("heading", "Anmerkungen und Literaturverzeichnis", 21, 21, None),
        ("paragraph", "Appendix.", 23, 23, None),
    ]
    assert [b.start_line for b in blocks if b.is_chapter] == [5, 21]
    assert [asdict(profile) for profile in profiles] == before
    assert [paragraph_identity(profile) for profile in profiles] == identities
    assert [chapter.num for chapter in chapters] == [1]


def test_reader_uses_source_spans_for_repeated_text_and_preserves_input_indices():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = "## One\n\nRepeated prose.\n\nRepeated prose.\n"
    profiles, _ = profile_document(source, CorpusConfig(), FingerprintThresholds())
    blocks = presentation.reader_blocks(source, CorpusConfig(), list(reversed(profiles)))
    assert [(b.start_line, b.profile_index) for b in blocks if b.kind == "profile"] == [(3, 1), (5, 0)]


def test_reader_does_not_normalize_the_existing_exact_quotation_text():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = ('## One\n\n😀 *Soft* [link](https://example.test) `literal` note.[^n] '
              '<img src="https://example.test/never"> \\input{never}\n\n[^n]: Note.\n')
    profiles, _ = profile_document(source, CorpusConfig(), FingerprintThresholds())
    blocks = presentation.reader_blocks(source, CorpusConfig(), profiles)
    assert [(b.text, b.profile_index) for b in blocks if b.kind == "profile"] == [
        ('😀 Soft [link](https://example.test) `literal` note. '
         '<img src="https://example.test/never"> \\input{never}', 0),
    ]
    assert [(b.kind, b.text) for b in blocks if b.kind == "note"] == [("note", "[n] Note.")]


def test_reader_handles_quote_code_only_and_empty_chapters_without_profiles():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = '# Title\n\nCHAPTER I\n\n> Quotation.\n\n```text\n\\input{never}\n```\n\nCHAPTER II\n'
    config = CorpusConfig(chapter_regex=r"^CHAPTER\s+")
    profiles, chapters = profile_document(source, config, FingerprintThresholds())
    assert profiles == chapters == []
    blocks = presentation.reader_blocks(source, config, profiles)
    assert [(b.kind, b.text, b.profile_index) for b in blocks] == [
        ("heading", "Title", None), ("heading", "I", None), ("quote", "Quotation.", None),
        ("code", r"\input{never}", None), ("heading", "II", None),
    ]
    assert [b.start_line for b in blocks if b.is_chapter] == [3, 11]


def test_partial_span_overlap_keeps_the_unowned_tail_as_literal_content():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = "## One\n\nFirst line.\nSecond line.\nThird line.\n"
    profiles, _ = profile_document(source, CorpusConfig(), FingerprintThresholds())
    # Exercise a supported subspan owner without letting its containing source
    # block duplicate the profile or swallow the remaining source content.
    owner = replace(profiles[0], end_line=4, text="First line. Second line.")
    blocks = presentation.reader_blocks(source, CorpusConfig(), [owner])
    assert [(b.kind, b.text, b.start_line, b.end_line) for b in blocks] == [
        ("heading", "One", 1, 1), ("profile", "First line. Second line.", 3, 4),
        ("paragraph", "Third line.", 5, 5),
    ]


def test_ambiguous_overlapping_profile_owners_fail_explicitly():
    presentation = importlib.import_module("lixity.ui.manuscript_document")
    source = "## One\n\nFirst line.\nSecond line.\n"
    profiles, _ = profile_document(source, CorpusConfig(), FingerprintThresholds())
    with pytest.raises(ValueError, match="Overlapping paragraph profile source spans"):
        presentation.reader_blocks(source, CorpusConfig(), [profiles[0], profiles[0]])
