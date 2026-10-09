"""NDA representative identity comes from project data, never product defaults."""

from pathlib import Path

import pytest

from lixity.nda import draft_document


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_project_author_is_printed_on_the_representative_line(tmp_path: Path, language: str):
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Project Author"\n', encoding="utf-8")
    document = draft_document(tmp_path, name="Synthetic Recipient", project_name="Synthetic Project",
        date="2026-10-09", place="Synthetic City", language=language)
    assert "Synthetic Project Author" in document.text
    assert "Synthetic Recipient" in document.text
    assert "{{" not in document.text
    assert document.pdf().startswith(b"%PDF-")


def test_missing_author_remains_an_empty_manual_signature_line(tmp_path: Path):
    document = draft_document(tmp_path, name="Synthetic Recipient", project_name="Synthetic Project",
        date="2026-10-09", place="Synthetic City", language="en")
    assert "Project representative:" in document.text
    assert "Project representative: ________________________" in document.text
    assert not (tmp_path / "nda").exists()


def test_custom_model_can_use_project_author_and_old_fields(tmp_path: Path):
    (tmp_path / "lixity.toml").write_text(
        'author_name = "Synthetic Project Author"\n[nda]\ntemplate = "model.txt"\n', encoding="utf-8")
    (tmp_path / "model.txt").write_text("{{project_title}}: {{project_author}} / {{recipient_name}}", encoding="utf-8")
    document = draft_document(tmp_path, name="Synthetic Recipient", project_name="Synthetic Project",
        date="2026-10-09", place="Synthetic City", language="en")
    assert document.text == "Synthetic Project: Synthetic Project Author / Synthetic Recipient"


@pytest.mark.parametrize("value", ['true', '42', '"Two\\nlines"'])
def test_invalid_project_author_fails_visibly_in_agreement_generation(tmp_path: Path, value: str):
    (tmp_path / "lixity.toml").write_text(f"author_name = {value}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"(?i)author"):
        draft_document(tmp_path, name="Synthetic Recipient", project_name="Synthetic Project",
            date="2026-10-09", place="Synthetic City", language="en")
