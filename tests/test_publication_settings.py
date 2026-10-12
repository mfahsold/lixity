"""Publication data stays explicit to the selected project, not user defaults."""

import shutil
import subprocess
from pathlib import Path

import pytest

from lixity.config import load_project_config
from lixity.pdf_export import compose_pdf
from lixity.publication import PublicationSettings


def test_publication_metadata_loads_only_at_explicit_project_root(tmp_path: Path, monkeypatch):
    user_config = tmp_path / "user-defaults.toml"
    user_config.write_text('[publication]\npublisher_name = "Synthetic user default"\n', encoding="utf-8")
    monkeypatch.setattr("lixity.config.os.path.expanduser", lambda path:
                        str(user_config) if path == "~/.config/lixity.toml" else path)
    parent = tmp_path / "projects"
    parent.mkdir()
    (parent / "lixity.toml").write_text(
        '[publication]\npublisher_name = "Other project publisher"\n', encoding="utf-8")
    project = parent / "selected"
    project.mkdir()
    (project / "lixity.toml").write_text(
        '[publication]\npublisher_name = "Synthetic selected publisher"\n', encoding="utf-8")
    assert load_project_config(project).get("publication") == {
        "publisher_name": "Synthetic selected publisher"}
    monkeypatch.chdir(project)
    assert "publication" not in load_project_config()
    child = project / "drafts"
    child.mkdir()
    assert "publication" not in load_project_config(child)
    other = parent / "another"
    other.mkdir()
    assert "publication" not in load_project_config(other)


@pytest.mark.parametrize("publication", [
    {"enabled": "yes"}, {"year": "202X"}, {"year": "0000"},
    {"publisher_name": "Unsafe\x00name"}, {"isbn_print": "9781234567890"},
    {"publisher_address": ["Not a string"]}, {"unknown_field": "Unexpected"},
])
def test_pdf_rejects_invalid_publication_data(publication):
    with pytest.raises(ValueError):
        compose_pdf("# Synthetic title\n\n## Opening\n\nA bird crosses the garden.\n",
                    manuscript="synthetic.md", layout="book",
                    project_config={"publication": publication})


def test_print_and_digital_isbns_reject_two_representations_of_the_same_identifier():
    with pytest.raises(ValueError, match="distinct"):
        PublicationSettings(isbn_print="0-306-40615-2", isbn_digital="978-0-306-40615-7")


def _pdf_text(pdf: bytes) -> str:
    executable = shutil.which("pdftotext")
    if not executable:
        pytest.skip("Poppler is needed for independent PDF text extraction")
    result = subprocess.run([executable, "-", "-"], input=pdf, capture_output=True, check=True)  # noqa: S603
    return result.stdout.decode("utf-8")


@pytest.mark.native_pdf
@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="requires Poppler text extraction")
def test_book_uses_configured_identity_and_entered_publication_data():
    pdf = compose_pdf("# Manuscript title\n\n## Opening\n\nA bird crosses the garden.\n",
        manuscript="synthetic.md", layout="book", project_config={
            "title": "Stored project title", "author_name": "Synthetic Writer",
            "publication": {"enabled": True, "publisher_name": "Synthetic Publisher",
                            "publisher_address": "Example Lane 1\n00000 Example Town",
                            "rights_notice": "Explicit synthetic rights note"},
        })
    extracted = _pdf_text(pdf)
    for value in ("Stored project title", "Synthetic Writer", "Synthetic Publisher",
                  "Example Lane 1", "Explicit synthetic rights note"):
        assert value in extracted
    assert "Nationalbibliothek" not in extracted, "No unverified catalog claim may be generated"


@pytest.mark.native_pdf
@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="requires Poppler text extraction")
def test_title_detection_does_not_read_a_fenced_code_example():
    pdf = compose_pdf("```markdown\n# Code example title\n```\n\n# Real document title\n\n"
                      "## Opening\n\nA bird crosses the garden.\n",
                      manuscript="synthetic.md", layout="book")
    assert "Real document title" in _pdf_text(pdf)
    assert "Code example title" not in _pdf_text(pdf)


@pytest.mark.native_pdf
@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="requires Poppler text extraction")
def test_explicit_author_override_can_clear_configured_byline():
    pdf = compose_pdf("# Synthetic title\n\n## Opening\n\nA bird crosses the garden.\n",
                      manuscript="synthetic.md", layout="book", author="",
                      project_config={"author_name": "Configured Writer"})
    assert "Configured Writer" not in _pdf_text(pdf)
