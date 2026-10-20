"""Configured manuscripts stay in one selected project and never hide errors."""

import contextlib
import errno
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lixity import workspace
from lixity.cli import main
from lixity.config import configuration_metadata, load_project_config
from lixity.research import api
from lixity.research.repository import Repository


@pytest.fixture(autouse=True)
def isolated_user_configuration(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def run_review(*arguments):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = main(["research", "review-manuscript", *arguments])
    return status, output.getvalue(), errors.getvalue()


def files(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("name,content", [
    ("lixity.toml", 'manuscript = "drafts/selected draft.md"\n'),
    ("pyproject.toml", '[tool.lixity]\nmanuscript = "drafts/selected draft.md"\n'),
])
def test_folder_discovery_uses_root_configured_manuscript_before_conventions(tmp_path, name, content):
    root = tmp_path / "project"
    (root / "drafts").mkdir(parents=True)
    selected = root / "drafts" / "selected draft.md"
    selected.write_text("## One\n\nA synthetic observer waits.\n", encoding="utf-8")
    (root / "manuscript.md").write_text("Wrong conventional draft.\n", encoding="utf-8")
    (root / name).write_text(content, encoding="utf-8")
    before = files(root)
    actual = workspace.discover(root=str(root))
    assert actual.manuscript == str(selected)
    assert actual.root == str(root)
    assert actual.read_manuscript() == "## One\n\nA synthetic observer waits.\n"
    assert workspace.resolve_project_target(root).manuscript == str(selected)
    assert files(root) == before


def test_local_setting_overrides_pyproject_and_never_comes_from_user_or_ancestor(tmp_path, monkeypatch):
    root = tmp_path / "parent" / "project"
    root.mkdir(parents=True)
    (root.parent / "lixity.toml").write_text('manuscript = "ancestor.md"\n', encoding="utf-8")
    user = Path(os.environ["HOME"]) / ".config"
    user.mkdir()
    (user / "lixity.toml").write_text('manuscript = "user.md"\n', encoding="utf-8")
    assert workspace.configured_manuscript(root) is None
    (root / "pyproject.toml").write_text('[tool.lixity]\nmanuscript = "pyproject.md"\n', encoding="utf-8")
    assert workspace.configured_manuscript(root) == str(root / "pyproject.md")
    (root / "lixity.toml").write_text('manuscript = "local.md"\n', encoding="utf-8")
    assert workspace.configured_manuscript(root) == str(root / "local.md")
    assert load_project_config(root)["manuscript"] == "local.md"
    monkeypatch.chdir(root)
    assert "manuscript" not in load_project_config()
    nested = root / "nested"
    nested.mkdir()
    assert "manuscript" not in load_project_config(nested)
    metadata = configuration_metadata()
    assert "manuscript" in metadata["accepted_keys"]
    assert "manuscript" in metadata["project_only_keys"]


def test_unrelated_malformed_user_and_ancestor_configs_do_not_affect_root_selection(tmp_path):
    root = tmp_path / "parent" / "project"
    root.mkdir(parents=True)
    (root.parent / "lixity.toml").write_text("broken = [\n", encoding="utf-8")
    user = Path(os.environ["HOME"]) / ".config"
    user.mkdir()
    (user / "lixity.toml").write_text("broken = [\n", encoding="utf-8")
    (root / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    assert workspace.configured_manuscript(root) == str(root / "draft.md")


@pytest.mark.parametrize("value", ['""', '"  "', 'false', '42', '[]', '{}', '"../outside.md"', '"drafts/../other.md"'])
def test_invalid_configured_value_never_falls_back_to_conventional_file(tmp_path, value):
    (tmp_path / "lixity.toml").write_text(f"manuscript = {value}\n", encoding="utf-8")
    (tmp_path / "manuscript.md").write_text("A wrong conventional manuscript.\n", encoding="utf-8")
    before = files(tmp_path)
    with pytest.raises(ValueError, match=r"[Mm]anuscript"):
        workspace.discover(root=str(tmp_path))
    assert files(tmp_path) == before


def test_absolute_configured_path_is_rejected_even_inside_project(tmp_path):
    selected = tmp_path / "draft.md"
    (tmp_path / "lixity.toml").write_text("manuscript = " + json.dumps(str(selected)) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="relative"):
        workspace.configured_manuscript(tmp_path)


def test_missing_configured_file_is_selected_without_falling_back_or_preflight(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "missing.md"\n', encoding="utf-8")
    (tmp_path / "manuscript.md").write_text("Wrong conventional manuscript.\n", encoding="utf-8")
    assert workspace.configured_manuscript(tmp_path) == str(tmp_path / "missing.md")
    for policy in ("error", "allow", "research"):
        with pytest.raises(ValueError, match=r"[Mm]anuscript"):
            workspace.resolve_project_target(tmp_path, empty=policy)


@pytest.mark.parametrize("content", ['manuscript = [\n', 'tool = false\n'])
def test_malformed_root_config_is_selection_error_without_warning_fallback(tmp_path, content):
    target = tmp_path / ("pyproject.toml" if content.startswith("tool") else "lixity.toml")
    target.write_text(content, encoding="utf-8")
    (tmp_path / "manuscript.md").write_text("Wrong conventional manuscript.\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"[Cc]onfig|[Cc]ould not"):
        workspace.discover(root=str(tmp_path))


@pytest.mark.parametrize("operation", ["stat", "read"])
def test_root_config_io_failure_is_not_a_valid_discovery_default(tmp_path, monkeypatch, operation):
    target = tmp_path / "lixity.toml"
    target.write_text('manuscript = "draft.md"\n', encoding="utf-8")
    (tmp_path / "draft.md").write_text("A valid configured manuscript.\n", encoding="utf-8")
    (tmp_path / "manuscript.md").write_text("Wrong conventional manuscript.\n", encoding="utf-8")
    original_stat, original_open = os.stat, os.open

    def failed_stat(path, *args, **kwargs):
        if os.fspath(path) == str(target):
            raise OSError(errno.EIO, "Synthetic configuration metadata failure", str(target))
        return original_stat(path, *args, **kwargs)

    def failed_read(path, *args, **kwargs):
        if os.fspath(path) == str(target):
            raise PermissionError(errno.EACCES, "Synthetic configuration read failure", str(target))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", failed_stat) if operation == "stat" else monkeypatch.setattr(os, "open", failed_read)
    with pytest.raises((OSError, ValueError), match=r"[Cc]onfig|[Cc]ould not"):
        workspace.discover(root=str(tmp_path))


def test_explicit_file_wins_without_validating_unused_bad_configured_value(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = false\n', encoding="utf-8")
    selected = tmp_path / "explicit.md"
    selected.write_text("A synthetic explicit manuscript.\n", encoding="utf-8")
    assert workspace.discover(root=str(tmp_path), explicit=str(selected)).manuscript == str(selected)


def test_escaping_symlink_configured_manuscript_is_rejected(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("A separate synthetic manuscript.\n", encoding="utf-8")
    try:
        (root / "link.md").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable")
    (root / "lixity.toml").write_text('manuscript = "link.md"\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"[Mm]anuscript|project"):
        workspace.discover(root=str(root))


@pytest.mark.parametrize("missing", [False, True])
@pytest.mark.parametrize("explicit_project", [False, True])
def test_review_uses_configured_path_in_verified_project_and_preserves_missing_state(
    tmp_path, monkeypatch, missing, explicit_project,
):
    root = tmp_path / "project"
    api.init(root, title="Synthetic configured manuscript")
    (root / "drafts").mkdir()
    if not missing:
        (root / "drafts" / "draft.md").write_text("## One\n\nA synthetic observer waits.\n", encoding="utf-8")
    (root / "lixity.toml").write_text('manuscript = "drafts/draft.md"\n', encoding="utf-8")
    other = tmp_path / "other"
    api.init(other, title="Synthetic other project")
    monkeypatch.chdir(other if explicit_project else root)
    before = files(tmp_path)
    flags = ["--project", str(root)] if explicit_project else []
    status, output, errors = run_review(*flags)
    assert status == 0 and not errors
    result = json.loads(output)
    assert result["schema_version"] == "research-manuscript-review-local/1"
    assert result["project_id"] == Repository(root).snapshot().project.id
    assert result["source_path"] == "drafts/draft.md"
    assert result["source_state"] == ("missing" if missing else "available")
    assert files(tmp_path) == before


def test_review_no_setting_requests_path_instead_of_discovering_arbitrary_file(tmp_path, monkeypatch):
    api.init(tmp_path, title="Synthetic explicit manuscript scope")
    (tmp_path / "manuscript.md").write_text("A conventional synthetic manuscript.\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    before = files(tmp_path)
    status, output, errors = run_review()
    assert status == 1 and not output
    assert "manuscript" in errors and ("--manuscript" in errors or "path" in errors)
    assert files(tmp_path) == before


def test_review_validates_archive_before_consulting_configuration(tmp_path, monkeypatch):
    (tmp_path / "lixity.toml").write_text("broken = [\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    status, output, errors = run_review()
    assert status == 1 and not output
    assert "current directory" in errors and "--project" in errors


@pytest.mark.parametrize("named", [False, True])
def test_review_explicit_path_wins_and_other_manuscript_commands_stay_required(tmp_path, named):
    api.init(tmp_path, title="Synthetic explicit path")
    (tmp_path / "lixity.toml").write_text("manuscript = false\n", encoding="utf-8")
    explicit = tmp_path / "explicit.md"
    explicit.write_text("## One\n\nAn explicit synthetic manuscript.\n", encoding="utf-8")
    flags = ["--manuscript", "explicit.md"] if named else ["explicit.md"]
    status, output, errors = run_review("--project", str(tmp_path), *flags)
    assert status == 0 and not errors
    assert json.loads(output)["source_path"] == "explicit.md"
    with contextlib.redirect_stderr(io.StringIO()), pytest.raises(SystemExit) as failure:
        main(["research", "find-anchor", "--project", str(tmp_path), "--query", "Synthetic quote"])
    assert failure.value.code == 2


def test_neutral_folder_policy_does_not_swallow_invalid_configured_path(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "../outside.md"\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"[Mm]anuscript"):
        workspace.resolve_project_target(tmp_path, empty="allow")


@pytest.mark.parametrize("name", ["lixity.toml", "pyproject.toml"])
@pytest.mark.parametrize("kind", ["directory", "fifo"])
def test_present_nonregular_root_config_never_falls_back(tmp_path, name, kind):
    target = tmp_path / name
    if kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs are unavailable")
        os.mkfifo(target)
    else:
        target.mkdir()
    (tmp_path / "manuscript.md").write_text("Wrong default manuscript.", encoding="utf-8")
    with pytest.raises(ValueError, match=r"[Cc]onfig.*regular"):
        workspace.discover(str(tmp_path))


def test_config_replaced_by_fifo_during_selection_is_rejected_without_blocking(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFOs are unavailable")
    target = tmp_path / "lixity.toml"
    target.write_text('manuscript = "draft.md"\n', encoding="utf-8")
    script = '''
import os, sys
from pathlib import Path
from lixity.config import read_explicit_project_config
target = Path(sys.argv[1]) / 'lixity.toml'
original_stat = Path.lstat
replaced = False
def stat(path, *args, **kwargs):
    global replaced
    result = original_stat(path, *args, **kwargs)
    if path == target and not replaced:
        replaced = True
        path.unlink()
        os.mkfifo(path)
    return result
Path.lstat = stat
try:
    read_explicit_project_config(target.parent)
except (OSError, ValueError) as error:
    print(error)
    sys.exit(1)
'''
    try:
        result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],  # noqa: S603 - Fixed synthetic child code.
                                check=False, capture_output=True, text=True, encoding="utf-8", timeout=3)
    except subprocess.TimeoutExpired:
        pytest.fail("Configuration selection blocked on a FIFO replacement")
    assert result.returncode == 1
    assert "regular" in result.stdout.lower()


def test_configured_internal_alias_preserves_saved_manuscript_link_identity(tmp_path):
    import hashlib

    api.init(tmp_path, title="Synthetic alias identity")
    target = tmp_path / "target.md"
    target.write_text("## Scene\n\nA synthetic observer waits.\n", encoding="utf-8")
    alias = tmp_path / "alias.md"
    try:
        alias.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable")
    claim = api.create_claim(tmp_path, title="Observation", statement="A synthetic statement.")["claim_id"]
    anchor = api.resolve_manuscript_anchor(tmp_path, "alias.md", query="A synthetic observer waits.")
    snapshot = Repository(tmp_path).snapshot()
    selection = {key: anchor[key] for key in ("start_line", "end_line", "paragraph_sha256", "start", "end", "quote")}
    api.link_manuscript_claim(tmp_path, "alias.md", claim, claim_revision=1, selection=selection,
        expected_project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
        expected_source_sha256=hashlib.sha256(alias.read_bytes()).hexdigest(), allow_retention=True)
    (tmp_path / "lixity.toml").write_text('manuscript = "alias.md"\n', encoding="utf-8")
    status, explicit, errors = run_review("--project", str(tmp_path), "alias.md")
    assert status == 0 and not errors
    status, configured, errors = run_review("--project", str(tmp_path))
    assert status == 0 and not errors
    assert json.loads(configured) == json.loads(explicit)
    assert len(json.loads(configured)["links"]) == 1
    assert workspace.configured_manuscript(tmp_path) == str(alias)


def test_dangling_root_config_cannot_select_conventional_manuscript(tmp_path):
    (tmp_path / "manuscript.md").write_text("A synthetic manuscript.\n", encoding="utf-8")
    try:
        (tmp_path / "lixity.toml").symlink_to(tmp_path / "missing-config.toml")
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable")
    with pytest.raises(ValueError, match="configuration"):
        workspace.discover(root=str(tmp_path))


def test_contained_symlink_preserves_configured_source_path_identity(tmp_path):
    target = tmp_path / "draft.md"
    target.write_text("A synthetic manuscript.\n", encoding="utf-8")
    alias = tmp_path / "selected.md"
    try:
        alias.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable")
    (tmp_path / "lixity.toml").write_text('manuscript = "selected.md"\n', encoding="utf-8")
    assert workspace.configured_manuscript(tmp_path) == str(alias)
