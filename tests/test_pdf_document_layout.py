"""Neutral A4 exports retain authored structure through the existing PDF flow."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lixity import cli, pdf_export, pdf_layouts
from lixity.manuscript_document import manuscript_sections
from lixity.models import CorpusConfig
from lixity.pdf_document import A4, PdfError
from lixity.pdf_layouts import FontChoice
from tests.test_pdf_cli import _fonts
from tests.test_pdf_export import CHOSEN, HAVE_FONTS
from tests.test_pdf_page_information import captured_layout

pytestmark = pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")
PDFTEXT = shutil.which("pdftotext")
PDFINFO = shutil.which("pdfinfo")

SOURCE = (
    "---\ntitle: Hidden front-matter field\n---\n"
    "# Daily exposé – Grüße\n\nA preserved preface with café and naïve wording.\n\n"
    "## First section\n\n### A literal subheading\n\n"
    "A *quiet* and \\textbf{firm} warning[^a].\n\n"
    "> A preserved quotation.\n\n- A preserved list item.\n\n"
    "```text\n<x> remains literal\n```\n\n"
    "## Second section\n\nA second paragraph.\n\n"
    "\\newpage\n\nAfter an explicit page break.\n\n"
    "[^a]: A preserved note.\n\n"
    "## Anmerkungen und Literaturverzeichnis\n\nA preserved appendix.\n"
)


def compose(text=SOURCE, **kwargs):
    return pdf_export.compose_pdf(
        text, manuscript="synthetic.md", layout="document", choice=CHOSEN, **kwargs,
    )


def test_title_retention_is_explicit_and_does_not_change_existing_projection_defaults():
    source = "# Authored title\n\nA preserved preface.\n\n## First section\n\nLiteral body.\n"
    original = manuscript_sections(source, CorpusConfig())
    assert [(b.kind, b.text) for b in original[0][1]] == [("paragraph", "A preserved preface.")]
    retained = manuscript_sections(source, CorpusConfig(), include_title=True)
    assert [(b.kind, b.text) for b in retained[0][1]] == [
        ("heading", "Authored title"), ("paragraph", "A preserved preface."),
    ]
    assert retained[1] == original[1]


def test_document_geometry_is_a4_without_generated_furniture_or_correction_features(monkeypatch):
    data, document, pages = captured_layout(
        monkeypatch, compose,
        title="Metadata-only title", author="Metadata-only author", draft_notice="CONTROL NOTICE",
    )
    assert data.startswith(b"%PDF-1.4")
    assert (document.width, document.height) == A4
    assert document.left == document.right == document.top == document.bottom == 72
    assert not document.mirror and document.line_numbers is None and not document.furniture
    assert document.metadata == {
        "title": "Metadata-only title", "author": "Metadata-only author", "language": "en",
    }
    assert len(pages) == 2  # Only the authored explicit break starts a new page here.
    lines = [line for page in pages for line in page.lines]
    assert lines[0].text == "Daily exposé – Grüße"
    assert any(line.text == "First section" for line in pages[0].lines)
    assert any(line.text == "Second section" for line in pages[0].lines)
    assert all("Metadata-only" not in line.text and "CONTROL NOTICE" not in line.text for line in lines)
    assert all(line.x >= 72 and 72 <= line.y <= A4[1] - 72 for line in lines)


def test_direct_document_composer_keeps_authored_title_without_using_unused_fonts(monkeypatch):
    _data, _document, pages = captured_layout(
        monkeypatch, pdf_layouts.document_pdf,
        body="# Authored title\n\nA literal paragraph.\n", title="Metadata title",
        choice=FontChoice(serif=CHOSEN.serif, serif_bold=CHOSEN.serif_bold, mono="/absent.ttf"),
    )
    assert [line.text for page in pages for line in page.lines] == [
        "Authored title", "A literal paragraph.",
    ]


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext") or not shutil.which("pdfinfo"), reason="requires Poppler readers")
def test_real_pdf_text_keeps_unicode_inline_blocks_sections_and_metadata(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A neutral document must not analyze or add publication imprint material")

    monkeypatch.setattr(pdf_export, "analyze_document", forbidden)
    monkeypatch.setattr(pdf_export, "load_publication", forbidden)
    target = tmp_path / "document.pdf"
    target.write_bytes(compose(
        title="Metadata-only title", author="Metadata-only author", language="de",
        project_config={"draft_notice": "CONTROL NOTICE", "publication": {"invalid": "unused"}},
    ))
    result = subprocess.run(  # noqa: S603 - fixed Poppler tool and synthetic PDF
        [PDFTEXT, "-layout", str(target), "-"], check=True, capture_output=True, text=True,
    )
    visible = " ".join(result.stdout.split())
    for literal in (
        "Daily exposé – Grüße", "café", "naïve", "preserved preface", "First section",
        "literal subheading", "quiet", "firm", "[a]", "preserved quotation",
        "preserved list item", "<x> remains literal", "Second section",
        "After an explicit page break", "preserved note", "preserved appendix",
    ):
        assert literal in visible
    assert visible.count("Daily exposé – Grüße") == 1
    for excluded in ("Metadata-only", "CONTROL NOTICE", "Hidden front-matter field", "\\textbf"):
        assert excluded not in visible
    info = subprocess.run(  # noqa: S603 - fixed Poppler tool and synthetic PDF
        [PDFINFO, str(target)], check=True, capture_output=True, text=True,
    ).stdout
    assert re.search(r"Title:\s+Metadata-only title", info)
    assert re.search(r"Author:\s+Metadata-only author", info)
    assert re.search(r"Pages:\s+2\b", info)
    assert re.search(r"Page size:\s+595\.27\d* x 841\.89\d* pts \(A4\)", info)


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="requires Poppler pdftotext")
def test_document_without_authored_title_does_not_insert_filename_or_metadata_heading(tmp_path):
    target = tmp_path / "untitled.pdf"
    target.write_bytes(compose("A plain exposé paragraph.\n", title="Metadata title"))
    result = subprocess.run(  # noqa: S603 - fixed Poppler tool and synthetic PDF
        [PDFTEXT, str(target), "-"], check=True, capture_output=True, text=True,
    )
    assert result.stdout.split() == ["A", "plain", "exposé", "paragraph."]


def test_document_cli_is_idempotent_and_keeps_original_source_bytes(tmp_path):
    source = tmp_path / "synthetic.md"
    original = SOURCE.replace("\n", "\r\n").encode("utf-8")
    source.write_bytes(original)
    target = tmp_path / "neutral.pdf"
    command = ["pdf", str(source), "--layout", "document", "-o", str(target), *_fonts()]
    assert cli.main(command) == 0
    data, stamp = target.read_bytes(), target.stat().st_mtime_ns
    assert data.startswith(b"%PDF-1.4") and source.read_bytes() == original
    assert cli.main(command) == 0
    assert target.read_bytes() == data and target.stat().st_mtime_ns == stamp
    assert source.read_bytes() == original


@pytest.mark.parametrize("problem", ("unsupported-tex", "missing-font", "missing-glyph"))
def test_document_composition_errors_keep_source_and_previous_output(tmp_path, problem):
    source, target = tmp_path / "synthetic.md", tmp_path / "neutral.pdf"
    text = {
        "unsupported-tex": "A paragraph with \\input{external-file}.\n",
        "missing-font": "A synthetic paragraph.\n",
        "missing-glyph": "A synthetic paragraph with \U0001fae8.\n",
    }[problem]
    source.write_text(text, encoding="utf-8")
    before = source.read_bytes()
    target.write_bytes(b"previous reviewed copy")
    fonts = ["--serif-font", "/not-an-installed-font.ttf"] if problem == "missing-font" else _fonts()
    assert cli.main(["pdf", str(source), "--layout", "document", "-o", str(target), *fonts]) == 1
    assert target.read_bytes() == b"previous reviewed copy" and source.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["neutral.pdf", "synthetic.md"]


def test_document_atomic_replacement_failure_preserves_prior_output_and_source(tmp_path, monkeypatch):
    import lixity.io as io

    source, target = tmp_path / "synthetic.md", tmp_path / "neutral.pdf"
    source.write_text("# Exposé\n\nA synthetic paragraph.\n", encoding="utf-8")
    original = source.read_bytes()
    target.write_bytes(b"previous reviewed copy")
    replace = io.os.replace

    def denied(staged, destination):
        if Path(destination) == target:
            raise PermissionError("Synthetic replacement denial")
        return replace(staged, destination)

    monkeypatch.setattr(io.os, "replace", denied)
    assert cli.main(["pdf", str(source), "--layout", "document", "-o", str(target), *_fonts()]) == 1
    assert target.read_bytes() == b"previous reviewed copy" and source.read_bytes() == original
    assert not list(tmp_path.glob("sync_tmp_*.tmp"))


def test_document_uses_shared_empty_prose_and_font_role_guards():
    with pytest.raises(ValueError, match="prose"):
        compose("# Heading only\n", require_prose=True)
    with pytest.raises(PdfError):
        pdf_export.compose_pdf(
            "A synthetic paragraph.", manuscript="synthetic.md", layout="document",
            choice=FontChoice(serif="/absent.ttf"),
        )
