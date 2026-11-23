"""Prepared metadata writes preserve unrelated project data and reject races."""

import os
from math import inf, nextafter
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.config import (
    load_project_config,
    prepare_project_settings,
    read_explicit_project_config,
)
from lixity.dialogue import dialogue_report
from lixity.dossier_draft_settings import resolve_dossier_draft_settings
from lixity.models import CorpusConfig


def test_combined_metadata_write_preserves_other_tables_and_comments(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    original = '# Kept\ntitle = "Old" # Title\nauthor_name = "Old writer"\nlanguage = "de"\n[custom]\nvalue = "untouched"\n'
    path.write_text(original, encoding="utf-8")
    prepared = prepare_project_settings(tmp_path, {
        "title": "New title", "author_name": "New writer",
        "publication": {"enabled": True, "publisher_address": "First street\n12345 City"},
    })
    assert path.read_text() == original
    prepared.commit()
    saved = path.read_text()
    assert '# Kept\ntitle = "New title" # Title\n' in saved
    assert 'language = "de"\n[custom]\nvalue = "untouched"\n' in saved
    settings = load_project_config(tmp_path)
    assert settings["title"] == "New title"
    assert settings["author_name"] == "New writer"
    assert settings["publication"]["publisher_address"] == "First street\n12345 City"
    prepared_again = prepare_project_settings(tmp_path, {"publication": settings["publication"]})
    with patch("lixity.io.os.replace") as replace:
        prepared_again.commit()
    replace.assert_not_called()


@pytest.mark.parametrize("existing_q", ["0.001", "1e-3", "+1.0E-3", "1_0.0e-4"])
def test_analysis_defaults_use_the_existing_preserving_writer(tmp_path: Path, existing_q: str):
    path = tmp_path / "lixity.toml"
    path.write_text(f'# Preserve\nlanguage = "de"\nfdr_q = {existing_q} # Range\n'
                    'min_chapters = 7\n[custom]\nvalue = "untouched"\n')
    prepared = prepare_project_settings(tmp_path, {
        "language": "auto", "fdr_q": 0.013000000000003,
        "z_mild": 2.123456789012345, "z_strong": 4.0,
    })
    prepared.commit()
    saved = load_project_config(tmp_path)
    assert saved["language"] == "auto"
    assert saved["fdr_q"] == 0.013000000000003
    assert saved["z_mild"] == 2.123456789012345
    assert saved["z_strong"] == 4.0
    assert saved["min_chapters"] == 7
    assert '# Preserve\nlanguage = "auto"\n' in path.read_text()
    assert '# Range\nmin_chapters = 7\n[custom]\nvalue = "untouched"\n' in path.read_text()


def test_partial_analysis_defaults_validate_the_resulting_project(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    original = 'z_mild = 5.0\nz_strong = 6.0\n'
    path.write_text(original)
    with pytest.raises(ValueError, match=r"z_mild.*z_strong"):
        prepare_project_settings(tmp_path, {"z_strong": 4.0})
    assert path.read_text() == original


def test_corpus_limits_validate_against_project_values(tmp_path: Path) -> None:
    path = tmp_path / "lixity.toml"
    original = 'short_sentence_max = 10\nmedium_sentence_max = 14 # Keep\n[custom]\nkeep = true\n'
    path.write_text(original)
    with pytest.raises(ValueError, match="short_sentence_max"):
        prepare_project_settings(tmp_path, {"short_sentence_max": 15})
    with pytest.raises(ValueError, match="numbers"):
        prepare_project_settings(tmp_path, {"short_sentence_max": True})
    with pytest.raises(ValueError, match="dialogue_paragraph_share"):
        prepare_project_settings(tmp_path, {"dialogue_paragraph_share": 1.1})
    assert path.read_text() == original

    changes = {"short_sentence_max": 9, "dialogue_paragraph_share": 0.072, "language": "auto"}
    prepare_project_settings(tmp_path, changes).commit()
    saved = read_explicit_project_config(tmp_path)
    assert saved["short_sentence_max"] == 9
    assert saved["dialogue_paragraph_share"] == 0.072
    assert saved["language"] == "auto"
    assert 'medium_sentence_max = 14 # Keep\n[custom]\nkeep = true\n' in path.read_text()

    text = '## One\n\n“' + ' '.join(['Harbour'] * 9) + '.” ' + ' '.join(['Stone'] * 116) + '.'
    exact = saved["dialogue_paragraph_share"]
    included = dialogue_report(text, CorpusConfig(dialogue_paragraph_share=exact)).chapters[0]
    excluded = dialogue_report(text, CorpusConfig(dialogue_paragraph_share=nextafter(exact, inf))).chapters[0]
    assert (included.dialogue_words, included.words, included.dialogue_paragraphs) == (9, 125, 1)
    assert excluded.dialogue_paragraphs == 0


def test_place_name_settings_replace_multiline_list_and_override_inherited_mode(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    inherited = '[tool.lixity]\nlocations = ["Harbor"]\n'
    pyproject.write_text(inherited)
    path = tmp_path / "lixity.toml"
    original = 'locations = [\n  "Bay # 1", # Author note\n  "West [Fort]",\n] # Place mode\n\n[custom]\nkeep = true\n'
    path.write_text(original)
    for mode, expected in ((["Northport", "northport"], ["Northport"]), ([], []), ("auto", "auto")):
        prepare_project_settings(tmp_path, {"locations": mode}).commit()
        assert pyproject.read_text() == inherited
        saved = path.read_text()
        assert "# Author note" in saved and "# Place mode" in saved and "Bay # 1" not in saved
        assert "[custom]\nkeep = true" in saved
        assert load_project_config(tmp_path)["locations"] == expected


def test_dossier_preferences_reuse_the_project_writer_and_schema(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    inherited = "[tool.lixity.dossier_drafts]\ninferred_location_limit = 4\n"
    pyproject.write_text(inherited, encoding="utf-8")
    path = tmp_path / "lixity.toml"
    original = 'title = "Story"\n\n[terms.key]\naliases = ["spare key"]\n'
    path.write_text(original, encoding="utf-8")

    requested = {"inferred_location_limit": 4, "character_context_sentences": 0, "character_report_passages": False}
    prepare_project_settings(tmp_path, {"dossier_drafts": requested}).commit()
    assert pyproject.read_text() == inherited
    assert path.read_text().startswith(original)
    accepted = resolve_dossier_draft_settings(read_explicit_project_config(tmp_path))
    assert accepted.model_dump(exclude_defaults=True) == requested
    with pytest.raises(ValueError, match="character_context_sentences"):
        prepare_project_settings(tmp_path, {"dossier_drafts": {**requested, "character_context_sentences": "2"}})
    assert resolve_dossier_draft_settings(read_explicit_project_config(tmp_path)) == accepted


@pytest.mark.parametrize("existing", [
    'publication = { enabled = false, publisher_name = "Old" } # Keep\n[custom]\nkeep = true\n',
    '[publication] # Keep\nenabled = false\npublisher_name = "Old" # Name\n[custom]\nkeep = true\n',
])
def test_publication_inline_and_table_updates_preserve_other_values(tmp_path: Path, existing: str):
    path = tmp_path / "lixity.toml"
    path.write_text(existing)
    prepared = prepare_project_settings(tmp_path, {"publication": {"enabled": True, "publisher_name": "New"}})
    prepared.commit()
    assert "# Keep" in path.read_text()
    assert '[custom]\nkeep = true\n' in path.read_text()
    assert load_project_config(tmp_path)["publication"]["publisher_name"] == "New"


def test_prepared_settings_refuse_concurrent_root_or_pyproject_changes(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    path.write_text('author_name = "Before"\n')
    prepared = prepare_project_settings(tmp_path, {"author_name": "After"})
    path.write_text('author_name = "Concurrent"\n')
    with pytest.raises(ValueError, match="changed"):
        prepared.commit()
    assert path.read_text() == 'author_name = "Concurrent"\n'
    prepared = prepare_project_settings(tmp_path, {"author_name": "After"})
    (tmp_path / "pyproject.toml").write_text('[tool.lixity]\ntitle = "Concurrent"\n')
    with pytest.raises(ValueError, match="changed"):
        prepared.commit()
    assert path.read_text() == 'author_name = "Concurrent"\n'


def test_failed_replacement_preserves_combined_settings_and_removes_stage(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    original = b'author_name = "Before"\n'
    path.write_bytes(original)
    prepared = prepare_project_settings(tmp_path, {"author_name": "After", "publication": {"enabled": True}})
    with patch("lixity.io.os.replace", side_effect=OSError("Synthetic failure")), pytest.raises(OSError):
        prepared.commit()
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX file-node regression")
@pytest.mark.parametrize("name", ["lixity.toml", "pyproject.toml"])
def test_settings_preparation_and_tokens_do_not_read_special_nodes(tmp_path: Path, name: str):
    from lixity.server.pdf_context import project_settings_token
    path = tmp_path / name
    os.mkfifo(path)
    # A read on the FIFO would wait indefinitely. Assert the domain-level
    # refusal before permitting any content read, without a hanging test.
    with patch.object(Path, "read_bytes", side_effect=AssertionError("Special node read")):
        with pytest.raises(ValueError, match="regular nonsymlink"):
            prepare_project_settings(tmp_path, {"author_name": "Writer"})
        assert len(project_settings_token(tmp_path, None)) == 64
