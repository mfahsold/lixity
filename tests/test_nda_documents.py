"""Minimal NDA drafts preserve project language, fields and full document text."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from lixity import nda


def project_at(root: Path, language: str = "de", settings: str = "", text: str | None = None) -> Path:
    project = root / "project"
    project.mkdir()
    (project / "lixity.toml").write_text(
        f'language = "{language}"\ntitle = "Synthetic review"\n[nda]\n' + settings,
        encoding="utf-8",
    )
    if text is not None:
        (project / "agreement.txt").write_text(text, encoding="utf-8")
    return project


def draft(project: Path, **changes):
    values = {"name": "Example Reader", "address": "", "project_name": "Synthetic review",
              "date": "2026-10-06", "place": "Example City"}
    return nda.draft_document(project, **(values | changes))


@pytest.mark.parametrize("language,title", [
    ("en", "Confidentiality agreement"), ("de", "Vertraulichkeitsvereinbarung"),
    ("fr", "Accord de confidentialité"), ("es", "Acuerdo de confidencialidad"),
    ("it", "Accordo di riservatezza"), ("pt", "Acordo de confidencialidade"),
    ("nl", "Geheimhoudingsovereenkomst"),
])
def test_simple_draft_uses_each_project_language_without_creating_a_store(language: str, title: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = project_at(Path(directory), language)
        document = draft(project)
        assert title in document.text
        assert "Example Reader" in document.text and "Example City" in document.text
        assert "2026-10-06" in document.text and "{{" not in document.text
        assert document.language == language
        assert "Agreement Receipt" not in document.text
        assert not (project / "nda").exists()
        assert document.pdf().startswith(b"%PDF-1.4")


def test_effective_language_is_used_and_explicit_document_override_wins() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = project_at(Path(directory))
        assert "Accord de confidentialité" in draft(project, language="fr").text
        config = project / "lixity.toml"
        config.write_text(config.read_text() + 'language = "de"\n', encoding="utf-8")
        assert "Vertraulichkeitsvereinbarung" in draft(project, language="fr").text


def test_long_configured_template_is_complete_paginated_and_substituted() -> None:
    with tempfile.TemporaryDirectory() as directory:
        text = "Recipient: {{recipient_name}}\nProject: {{project_title}}\n\n"
        text += "\n".join(f"SECTION-{n:03}: Synthetic paragraph number {n}." for n in range(160))
        text += "\nFINAL-SIGNATURE {{recipient_address}}\n"
        project = project_at(Path(directory), settings='template = "agreement.txt"\n', text=text)
        document = draft(project, address="reader@example.invalid")
        data = document.pdf()
        assert data.count(b"/Type /Page ") >= 4
        assert b"Example Reader" in data and b"Synthetic review" in data
        assert all(f"SECTION-{n:03}".encode() in data for n in range(160))
        assert b"FINAL-SIGNATURE reader@example.invalid" in data
        assert not (project / "nda").exists()


@pytest.mark.parametrize("settings,text", [
    ('template = "missing.txt"\n', None),
    ('template = "agreement.txt"\n', "Unresolved {{unknown_party}}"),
    ('template = "agreement.txt"\n', "Unresolved {{UnknownParty}}"),
    ('template = "agreement.txt"\n', ""),
    ('template = "../outside.txt"\n', None),
])
def test_invalid_templates_reject_without_writing_any_document(settings: str, text: str | None) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "outside.txt").write_text("Outside confidential text", encoding="utf-8")
        project = project_at(root, settings=settings, text=text)
        with pytest.raises((ValueError, OSError)):
            draft(project)
        assert not (project / "nda").exists()


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "Injected\nclause"}, {"project_name": ""},
    {"date": "2026-02-30"}, {"place": "Injected\nclause"},
    {"date": "20261006"}, {"date": "2026-W41-2"}, {"place": ""},
    {"name": "Injected\vclause"}, {"place": "Injected\fclause"},
    {"project_name": "Injected\u2028clause"},
])
def test_required_identity_and_calendar_fields_are_validated(changes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = project_at(Path(directory))
        with pytest.raises(ValueError):
            draft(project, **changes)
        assert not (project / "nda").exists()


def test_text_preserves_unicode_and_pdf_fails_without_silent_replacement() -> None:
    with tempfile.TemporaryDirectory() as directory:
        document = draft(project_at(Path(directory)), name="Example 李")
        assert "Example 李" in document.text
        with pytest.raises(ValueError, match="character"):
            document.pdf()


def test_malformed_document_settings_do_not_silently_choose_another_text() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = project_at(Path(directory))
        (project / "lixity.toml").write_text('language = "de"\nnda = "agreement.txt"\n', encoding="utf-8")
        with pytest.raises(ValueError, match="settings"):
            draft(project)


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="Poppler text extraction is required")
def test_poppler_reads_last_page_and_project_language_accents() -> None:
    with tempfile.TemporaryDirectory() as directory:
        text = "\n".join(f"Abschnitt {n}: Größe, äußere Prüfung und Maß." for n in range(160))
        text += "\nENDMARK Müller – Prüfung €\n"
        project = project_at(Path(directory), settings='template = "agreement.txt"\n', text=text)
        path = Path(directory) / "draft.pdf"
        path.write_bytes(draft(project).pdf())
        binary = shutil.which("pdftotext")
        assert binary is not None
        result = subprocess.run(  # noqa: S603 - fixed tool and synthetic temporary document
            [binary, "-layout", str(path), "-"], check=True, capture_output=True, text=True,
        )
        assert "ENDMARK Müller – Prüfung €" in result.stdout
        assert all(f"Abschnitt {n}:" in result.stdout for n in range(160))
