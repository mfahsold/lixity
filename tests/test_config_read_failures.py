"""Configuration failures must remain visible when defaults are used."""

import errno
import io
import json
import os
from contextlib import redirect_stdout

import pytest

from lixity.cli import main
from lixity.config import _load_toml, load_project_config, read_project_config


@pytest.mark.parametrize("content,section", [
    ('tool = "invalid"\n', "tool"),
    ('tool = false\n', "tool"),
    ('tool = []\n', "tool"),
    ('[tool]\nlixity = "invalid"\n', "tool.lixity"),
    ('[tool]\nlixity = false\n', "tool.lixity"),
    ('[tool]\nlixity = []\n', "tool.lixity"),
])
def test_present_nontable_sections_warn_before_default_analysis(tmp_path, content, section):
    source = tmp_path / "manuscript.md"
    source.write_text("## One\n\nA synthetic scene.\n", encoding="utf-8")
    config = tmp_path / "pyproject.toml"
    original = content.encode()
    config.write_bytes(original)
    output = io.StringIO()
    with pytest.warns(UserWarning) as warnings, redirect_stdout(output):
        assert main(["analyze", str(source), "--json"]) == 0
    message = str(warnings[0].message)
    assert str(config) in message and section in message and "table" in message
    assert "ignored" in message and "defaults" in message
    assert json.loads(output.getvalue())["meta"]["language"] == "en"
    assert config.read_bytes() == original


@pytest.mark.parametrize("content,expected", [
    ("", {}),
    ('[project]\nname = "synthetic"\n', {}),
    ("[tool]\n", {}),
    ("[tool.lixity]\n", {}),
    ('[tool.lixity]\nlanguage = "de"\n', {"language": "de"}),
])
def test_missing_and_valid_pyproject_sections_stay_quiet(tmp_path, content, expected):
    target = tmp_path / "pyproject.toml"
    target.write_text(content, encoding="utf-8")
    assert _load_toml(target) == expected
    assert target.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("scope", ["project", "user", "exact"])
@pytest.mark.parametrize("error_number", [errno.EACCES, errno.EIO])
def test_config_metadata_failure_warns_instead_of_looking_absent(
    tmp_path, monkeypatch, scope, error_number,
):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "manuscript.md"
    source.write_text("## One\n\nA synthetic scene.\n", encoding="utf-8")
    user = tmp_path / "user.toml"
    monkeypatch.setattr("lixity.config.os.path.expanduser", lambda _path: str(user))
    target = user if scope == "user" else project / "lixity.toml"
    original = b'language = "de"\n'
    target.write_bytes(original)
    real_stat = os.stat

    def failed_stat(path, *args, **kwargs):
        if os.fspath(path) == str(target):
            raise OSError(error_number, "Synthetic metadata failure", str(target))
        return real_stat(path, *args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(os, "stat", failed_stat)
        with pytest.warns(UserWarning) as warnings:
            settings = (read_project_config(project) if scope == "exact"
                        else load_project_config(source))
    assert settings == {}
    message = str(warnings[0].message)
    assert str(target) in message and "ignored" in message
    assert target.read_bytes() == original


def test_absent_config_is_quiet_and_nearest_project_scope_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr("lixity.config.os.path.expanduser", lambda _path: str(tmp_path / "missing"))
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    assert read_project_config(child) == {}
    assert load_project_config(child) == {}
    (parent / "lixity.toml").write_text('language = "de"\ntitle = "Parent"\n')
    assert read_project_config(child) == {}
    assert load_project_config(child) == {"language": "de", "title": "Parent"}
    (child / "lixity.toml").write_text('language = "fr"\n')
    assert read_project_config(child) == {"language": "fr"}
    assert load_project_config(child) == {"language": "fr"}


def test_config_beneath_nondirectory_is_absent_not_an_unreadable_file(tmp_path):
    source = tmp_path / "manuscript.md"
    original = b"A synthetic scene.\n"
    source.write_bytes(original)
    assert read_project_config(source) == {}
    assert source.read_bytes() == original
