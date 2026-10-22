"""Comparison CLI language comes only from the selected project's root."""

import json

import pytest

from lixity.research import api
from tests.research_support import capture_research

TEXT = "## Erstes Kapitel\n\nDie Frau ist in dem Haus. Sie liest ein Buch und der Mann wartet vor der Tür.\n"


@pytest.fixture
def comparison(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic German archive", language="de")
    source = tmp_path / "source.txt"
    source.write_text(TEXT, encoding="utf-8")
    source_id = api.ingest(project, source, allow_retention=True)["source_id"]
    manuscript = project / "drafts/manuscript.md"
    manuscript.parent.mkdir()
    manuscript.write_text(TEXT, encoding="utf-8")
    return project, source_id, manuscript


def compare(comparison, *options):
    project, source_id, manuscript = comparison
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    result = capture_research("compare", "--project", str(project), "--source-id", source_id,
                              "--manuscript", str(manuscript), *options)
    assert {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()} == before
    return result


def test_compare_cli_inherits_selected_root_language_without_changing_python_default(comparison):
    project, source_id, manuscript = comparison
    (project / "lixity.toml").write_text('language = "de"\n', encoding="utf-8")
    status, output, errors = compare(comparison)
    assert status == 0 and errors == ""
    result = json.loads(output)
    assert result["meta"]["manuscript_language"] == "de"
    assert result["meta"]["lexical_comparable"] is True
    assert "cross_language_lexical_comparison" not in result["comparison_limits"]
    explicit = api.compare_source(project, source_id, manuscript, language="de")
    assert result == explicit
    assert api.compare_source(project, source_id, manuscript)["meta"]["manuscript_language"] == "en"


@pytest.mark.parametrize("language,expected", [("en", "en"), ("auto", "de")])
def test_explicit_language_and_detection_override_project_language(comparison, language, expected):
    project, _, _ = comparison
    (project / "lixity.toml").write_text('language = "fr"\n', encoding="utf-8")
    status, output, errors = compare(comparison, "--language", language)
    assert status == 0 and errors == ""
    assert json.loads(output)["meta"]["manuscript_language"] == expected


@pytest.mark.parametrize("local", [None, 'title = "Synthetic title"\n'])
def test_missing_root_language_defaults_to_english_not_archive_or_ambient_config(comparison, monkeypatch, local):
    from lixity import config

    project, _, manuscript = comparison
    (project.parent / "lixity.toml").write_text('language = "fr"\n', encoding="utf-8")
    (manuscript.parent / "lixity.toml").write_text('language = "it"\n', encoding="utf-8")
    if local is not None:
        (project / "lixity.toml").write_text(local, encoding="utf-8")
    monkeypatch.chdir(manuscript.parent)

    def ambient_forbidden(*args, **kwargs):
        pytest.fail("Comparison must not read user, ancestor or implicit working-directory settings")

    monkeypatch.setattr(config, "load_project_config", ambient_forbidden)
    status, output, errors = compare(comparison)
    assert status == 0 and errors == ""
    result = json.loads(output)
    assert result["meta"]["source_language"] == "de"
    assert result["meta"]["manuscript_language"] == "en"
    assert result["meta"]["lexical_comparable"] is False


def test_root_lixity_language_overrides_root_pyproject_language(comparison):
    project, _, _ = comparison
    (project / "pyproject.toml").write_text('[tool.lixity]\nlanguage = "fr"\n', encoding="utf-8")
    status, output, errors = compare(comparison)
    assert status == 0 and errors == ""
    assert json.loads(output)["meta"]["manuscript_language"] == "fr"
    (project / "lixity.toml").write_text('language = "de"\n', encoding="utf-8")
    status, output, errors = compare(comparison)
    assert status == 0 and errors == ""
    assert json.loads(output)["meta"]["manuscript_language"] == "de"


def test_configured_manuscript_and_current_project_keep_root_language(comparison, monkeypatch):
    project, source_id, _ = comparison
    (project / "lixity.toml").write_text(
        'language = "de"\nmanuscript = "drafts/manuscript.md"\n', encoding="utf-8")
    monkeypatch.chdir(project)
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    status, output, errors = capture_research("compare", "--source-id", source_id)
    assert status == 0 and errors == ""
    assert json.loads(output)["meta"]["manuscript_language"] == "de"
    assert {path.relative_to(project): path.read_bytes() for path in project.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("settings", ['language = [', 'language = 42\n', 'language = "unknown"\n'])
def test_invalid_root_config_is_an_error_not_an_english_or_generic_fallback(comparison, settings):
    project, _, _ = comparison
    (project / "lixity.toml").write_text(settings, encoding="utf-8")
    status, output, errors = compare(comparison)
    assert status == 1 and output == ""
    assert "[error]" in errors
    assert "configuration" in errors.lower() or "language" in errors.lower()


def test_unreadable_root_config_fails_explicitly(comparison, monkeypatch):
    from lixity.io import FileUtils

    project, _, _ = comparison
    path = project / "lixity.toml"
    path.write_text('language = "de"\n', encoding="utf-8")
    read = FileUtils.read_file

    def unreadable(filepath, encoding="utf-8"):
        if str(filepath) == str(path):
            raise PermissionError("Synthetic denied project configuration")
        return read(filepath, encoding)

    monkeypatch.setattr(FileUtils, "read_file", unreadable)
    status, output, errors = compare(comparison)
    assert status == 1 and output == ""
    assert "Could not resolve project configuration" in errors
    assert "Synthetic denied" in errors


def test_explicit_language_does_not_need_unrelated_project_settings(comparison):
    project, _, _ = comparison
    (project / "lixity.toml").write_text('language = [', encoding="utf-8")
    status, output, errors = compare(comparison, "--language", "de")
    assert status == 0 and errors == ""
    assert json.loads(output)["meta"]["manuscript_language"] == "de"


def test_language_inheritance_preserves_code_default_chapter_and_appendix_scope(comparison):
    project, source_id, manuscript = comparison
    manuscript.write_text(TEXT + "\n## Anmerkungen und Literaturverzeichnis\n\nAppendixonly.\n", encoding="utf-8")
    (project / "lixity.toml").write_text(
        'language = "de"\nchapter_regex = "(?m)^### "\nappendix_marker = "## Other appendix"\n', encoding="utf-8")
    status, output, errors = compare(comparison)
    assert status == 0 and errors == ""
    assert json.loads(output) == api.compare_source(project, source_id, manuscript, language="de")
    assert len(json.loads(output)["chapter_grounding"]) == 1
