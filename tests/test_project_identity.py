"""Project-local author persistence and explicit manuscript identity checks."""

import stat
from unittest.mock import patch

import pytest

from lixity import config


def test_author_is_explicit_project_data_not_inherited_defaults(tmp_path, monkeypatch):
    user = tmp_path / "user.toml"
    user.write_text('author_name = "Global Writer"\nz_mild = 3.0\n', encoding="utf-8")
    monkeypatch.setattr(config.os.path, "expanduser", lambda value: str(user))
    (tmp_path / "lixity.toml").write_text('author_name = "Parent Writer"\nfdr_q = 0.03\n', encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    settings = config.load_project_config(project)
    assert "author_name" not in settings
    assert settings["z_mild"] == 3.0
    assert settings["fdr_q"] == 0.03
    (project / "pyproject.toml").write_text('[tool.lixity]\nauthor_name = "Project Writer"\n', encoding="utf-8")
    assert config.load_project_config(project)["author_name"] == "Project Writer"
    config.save_project_author(project, "")
    assert config.load_project_config(project)["author_name"] == ""
    monkeypatch.chdir(project)
    assert "author_name" not in config.load_project_config()


def test_author_save_preserves_other_project_bytes_and_reads_back(tmp_path):
    path = tmp_path / "lixity.toml"
    original = '# Project settings\r\ntitle = "Synthetic Book"\r\nz_mild = 8.0\r\n[nda]\r\ntemplate = "custom.txt"\r\n'
    path.write_bytes(original.encode())
    config.save_project_author(tmp_path, '  Á. Synthetic "Writer"  ')
    saved = path.read_bytes()
    assert saved.endswith(original.encode())
    assert config.load_project_config(tmp_path)["author_name"] == 'Á. Synthetic "Writer"'
    assert config.load_project_config(tmp_path)["z_mild"] == 8.0


def test_existing_author_update_preserves_comment_table_and_mode(tmp_path):
    path = tmp_path / "lixity.toml"
    path.write_text('# Keep\n"author_name" = \'Old Writer\' # Identity\ntitle = "Synthetic"\n[extra]\nauthor_name = "Other value"\n', encoding="utf-8")
    path.chmod(0o640)
    original_mode = stat.S_IMODE(path.stat().st_mode)
    config.save_project_author(tmp_path, "New Writer")
    saved = path.read_text(encoding="utf-8")
    assert '# Identity\ntitle = "Synthetic"\n[extra]\nauthor_name = "Other value"\n' in saved
    assert saved.startswith('# Keep\n"author_name" = "New Writer"')
    assert stat.S_IMODE(path.stat().st_mode) == original_mode
    assert config.load_project_config(tmp_path)["author_name"] == "New Writer"
    config.save_project_author(tmp_path, "")
    assert config.load_project_config(tmp_path)["author_name"] == ""


def test_save_never_changes_parent_or_user_config(tmp_path, monkeypatch):
    parent = tmp_path / "lixity.toml"
    parent.write_text('title = "Parent"\n', encoding="utf-8")
    project = tmp_path / "child"
    project.mkdir()
    user = tmp_path / "user" / ".config"
    user.mkdir(parents=True)
    global_config = user / "lixity.toml"
    global_config.write_text('title = "Global"\n', encoding="utf-8")
    monkeypatch.setattr(config.os.path, "expanduser", lambda value: str(global_config) if value == "~/.config/lixity.toml" else value)
    config.save_project_author(project, "Synthetic Writer")
    assert parent.read_text() == 'title = "Parent"\n'
    assert global_config.read_text() == 'title = "Global"\n'
    assert config.load_project_config(project)["author_name"] == "Synthetic Writer"


@pytest.mark.parametrize("value", [None, 4, True, [], "x\n", "x\r", "x\0", "x\x7f", "x\x85", "x\u2028", "x\u2029", "x" * 501])
def test_invalid_author_never_changes_config(tmp_path, value):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "Keep"\n')
    with pytest.raises(ValueError):
        config.save_project_author(tmp_path, value)
    assert path.read_bytes() == b'title = "Keep"\n'


@pytest.mark.parametrize("content", ['title = "Unclosed\n', 'author_name = """Old\nWriter"""\n'])
def test_malformed_or_unsupported_config_is_not_rewritten(tmp_path, content):
    path = tmp_path / "lixity.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        config.save_project_author(tmp_path, "New Writer")
    assert path.read_text(encoding="utf-8") == content


def test_missing_project_and_symlink_config_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        config.save_project_author(None, "Writer")
    with pytest.raises(ValueError):
        config.save_project_author(tmp_path / "absent", "Writer")
    outside = tmp_path / "outside.toml"
    outside.write_text('title = "Outside"\n')
    (tmp_path / "lixity.toml").symlink_to(outside)
    with pytest.raises(ValueError):
        config.save_project_author(tmp_path, "Writer")
    assert outside.read_text() == 'title = "Outside"\n'


def test_atomic_replace_failure_keeps_original(tmp_path):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "Keep"\n')
    with patch("lixity.config.os.replace", side_effect=OSError("Synthetic failure")), pytest.raises(OSError):
        config.save_project_author(tmp_path, "Writer")
    assert path.read_bytes() == b'title = "Keep"\n'
    assert set(tmp_path.iterdir()) == {path}


def test_author_limits_preserve_inner_spacing_and_unicode():
    assert config.MAX_AUTHOR_NAME_CHARS == 500
    assert config.validate_author_name("  É.  Writer  ") == "É.  Writer"
    assert config.validate_author_name("x" * 500) == "x" * 500


def check(text, title="Synthetic Book", author="Á. Writer"):
    from lixity.project_identity import manuscript_identity_check
    return manuscript_identity_check(text, title, author)


def test_flat_metadata_matches_normalized_formatting_without_changing_value():
    result = check('---\ntitle: "Synthetic  Book"\nauthor: "A\u0301. Writer"\n---\n\n## One\n\nProse.\n')
    assert result == {
        "title": {"status": "matched", "value": "Synthetic  Book", "source": "front_matter"},
        "author_name": {"status": "matched", "value": "A\u0301. Writer", "source": "front_matter"},
    }


def test_metadata_mismatch_preserves_only_explicit_value():
    result = check("---\ntitle: Other Book\nauthor: Different Writer\n---\nPrivate synthetic prose.\n")
    assert result["title"] == {"status": "mismatch", "value": "Other Book", "source": "front_matter"}
    assert result["author_name"] == {"status": "mismatch", "value": "Different Writer", "source": "front_matter"}
    assert "prose" not in str(result)


@pytest.mark.parametrize("marker", ["by", "von", "Author:", "Autor:"])
def test_leading_title_page_has_explicit_title_and_author(marker):
    result = check(f"# Synthetic Book\n\n{marker} Á. Writer\n\n## One\n\nStory.\n")
    assert result["title"] == {"status": "matched", "value": "Synthetic Book", "source": "title_page"}
    assert result["author_name"] == {"status": "matched", "value": "Á. Writer", "source": "title_page"}


@pytest.mark.parametrize("text", [
    "By the time dawn arrived, the station was empty.\n",
    "Von dort aus ging sie zum Bahnhof.\n",
    "Author: Á. Writer\n",
    "## One\n\nÁ. Writer is mentioned in prose.\n\nAuthor: Á. Writer\n",
    "```yaml\ntitle: Synthetic Book\nauthor: Á. Writer\n```\n",
    "    # Synthetic Book\n    by Á. Writer\n",
    "# Synthetic Book\n\nThis is ordinary prose.\n\nby Á. Writer\n",
    "# Synthetic Book\n\n```\nAuthor: Á. Writer\n```\n",
])
def test_authorship_is_not_inferred_from_prose_or_code(text):
    assert check(text)["author_name"] == {"status": "missing", "value": None, "source": None}


@pytest.mark.parametrize("metadata", [
    "author: [Á. Writer]", "author: |\n  Á. Writer", "author: &name Á. Writer",
    "author: !tag Á. Writer", "author: *writer", "author: 12", "author: true",
    "author: Á. Writer\nauthor: Other", "author: {name: Á. Writer}",
])
def test_unsupported_author_metadata_is_reported_without_inventing_a_name(metadata):
    result = check(f"---\ntitle: Synthetic Book\n{metadata}\n---\n")
    assert result["title"]["status"] == "matched"
    assert result["author_name"] == {"status": "unsupported", "value": None, "source": "front_matter"}


def test_nested_author_is_missing_and_unclosed_metadata_is_unsupported():
    assert check("---\ntitle: Synthetic Book\nextra:\n  author: Á. Writer\n---\n")["author_name"]["status"] == "missing"
    result = check("---\ntitle: Synthetic Book\nauthor: Á. Writer\n")
    assert result["title"]["status"] == "unsupported"
    assert result["author_name"]["status"] == "unsupported"


def test_quoted_metadata_keeps_punctuation_and_comments_as_data():
    result = check("---\ntitle: 'Synthetic # Book'\nauthor: 'Writer <!-- name -->'\n---\n", "Synthetic # Book", "Writer <!-- name -->")
    assert result["title"]["status"] == "matched"
    assert result["author_name"]["value"] == "Writer <!-- name -->"


def test_unavailable_input_or_expected_name_is_not_an_authorship_verdict():
    assert check(None)["author_name"]["status"] == "unavailable"
    assert check("# Synthetic Book\n\nby Á. Writer\n", author="")["author_name"]["status"] == "unavailable"
    assert check("# Synthetic Book\n\nby á. Writer\n")["author_name"]["status"] == "mismatch"


def test_concurrent_config_change_is_not_overwritten(tmp_path):
    import tempfile
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "Before"\n')
    original_mkstemp = tempfile.mkstemp

    def concurrent_create(*args, **kwargs):
        created = original_mkstemp(*args, **kwargs)
        path.write_bytes(b'title = "Concurrent"\n')
        return created

    with patch("lixity.config.tempfile.mkstemp", side_effect=concurrent_create), pytest.raises(ValueError):
        config.save_project_author(tmp_path, "Writer")
    assert path.read_bytes() == b'title = "Concurrent"\n'
    assert set(tmp_path.iterdir()) == {path}


def test_nan_and_fake_author_line_in_multiline_data_remain_unchanged(tmp_path):
    path = tmp_path / "lixity.toml"
    content = 'author_name = "Old"\ncustom = nan\nnote = """\nauthor_name = \'Not a setting\'\n"""\n'
    path.write_text(content, encoding="utf-8")
    config.save_project_author(tmp_path, "New")
    assert path.read_text() == content.replace('author_name = "Old"', 'author_name = "New"')


@pytest.mark.parametrize("expected", [42, True, "Writer\n", "Writer\x85", "x" * 501])
def test_invalid_configured_author_is_unsupported_not_missing(expected):
    assert check("# Synthetic Book\n\nby Á. Writer\n", author=expected)["author_name"]["status"] == "unsupported"


def test_scene_divider_does_not_make_later_prose_into_front_matter():
    result = check("---\nOrdinary opening prose.\n\nauthor: Á. Writer\n")
    assert result["author_name"] == {"status": "missing", "value": None, "source": None}


def test_conflicting_title_page_bylines_are_unsupported():
    result = check("# Synthetic Book\n\nby Á. Writer\nAuthor: Other Writer\n")
    assert result["author_name"] == {"status": "unsupported", "value": None, "source": "title_page"}


@pytest.mark.parametrize("previous", ["true", "42", "1.5"])
def test_invalid_single_line_author_can_be_repaired_without_other_changes(tmp_path, previous):
    path = tmp_path / "lixity.toml"
    original = f'author_name = {previous} # Identity\nlanguage = "en"\n[extra]\nkeep = true\n'
    path.write_text(original, encoding="utf-8")
    config.save_project_author(tmp_path, "Synthetic Writer")
    assert path.read_text() == original.replace(f"author_name = {previous}", 'author_name = "Synthetic Writer"')
    assert config.load_project_config(tmp_path)["author_name"] == "Synthetic Writer"


def test_invalid_author_data_does_not_block_unrelated_analysis(tmp_path):
    from lixity import api
    path = tmp_path / "lixity.toml"
    path.write_text('author_name = ["Unsupported metadata"]\nlanguage = "en"\n')
    loaded = config.load_project_config(tmp_path)
    assert loaded["author_name"] == ["Unsupported metadata"]
    result = api.fingerprint("## One\n\nA synthetic writer opens a door.\n", project_config=loaded)
    assert result["meta"]["z_mild"] == 2.5


@pytest.mark.parametrize("field", ["title", "author"])
def test_multiline_plain_metadata_is_unsupported_not_a_partial_match(field):
    result = check(f"---\n{field}: Jane\n  Smith\n---\n", title="Jane", author="Jane")
    key = "author_name" if field == "author" else field
    assert result[key] == {"status": "unsupported", "value": None, "source": "front_matter"}


def test_comment_only_yaml_author_does_not_become_a_name():
    result = check("---\ntitle: Synthetic Book\nauthor: # Not an author\n---\n", author="# Not an author")
    assert result["author_name"] == {"status": "unsupported", "value": None, "source": "front_matter"}


def test_unpaired_unicode_surrogates_are_rejected_before_ui_serialization(tmp_path):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "Keep"\n')
    with pytest.raises(ValueError):
        config.validate_author_name("Writer \ud800")
    with pytest.raises(ValueError):
        config.save_project_author(tmp_path, "Writer \ud800")
    assert path.read_bytes() == b'title = "Keep"\n'
    result = check('---\ntitle: Synthetic Book\nauthor: "\\ud800"\n---\n')
    assert result["author_name"] == {"status": "unsupported", "value": None, "source": "front_matter"}


def test_unchanged_author_with_identical_nested_value_is_a_noop(tmp_path):
    path = tmp_path / "lixity.toml"
    original = 'author_name = "Writer"\n[extra]\nauthor_name = "Writer"\n'
    path.write_text(original, encoding="utf-8")
    before = path.stat().st_mtime_ns
    config.save_project_author(tmp_path, "Writer")
    assert path.read_text() == original
    assert path.stat().st_mtime_ns == before
