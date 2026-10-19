"""Prepared metadata writes preserve unrelated project data and reject races."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.config import load_project_config, prepare_project_settings


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
