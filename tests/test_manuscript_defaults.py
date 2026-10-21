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
def test_review_and_find_anchor_explicit_path_win_over_bad_setting(tmp_path, named):
    api.init(tmp_path, title="Synthetic explicit path")
    (tmp_path / "lixity.toml").write_text("manuscript = false\n", encoding="utf-8")
    explicit = tmp_path / "explicit.md"
    explicit.write_text("## One\n\nAn explicit synthetic manuscript.\n", encoding="utf-8")
    flags = ["--manuscript", "explicit.md"] if named else ["explicit.md"]
    status, output, errors = run_review("--project", str(tmp_path), *flags)
    assert status == 0 and not errors
    assert json.loads(output)["source_path"] == "explicit.md"
    status, output, errors = run_cli("research", "find-anchor", "--project", str(tmp_path),
                                     "explicit.md", "--query", "An explicit synthetic manuscript.")
    assert status == 0 and not errors
    assert json.loads(output)["quote"] == "An explicit synthetic manuscript."


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


ANALYSIS_COMMANDS = (
    "analyze", "profile", "dialogue", "pacing", "showing", "style",
    "motifs", "characters", "dashboard", "pdf", "scenes", "build",
)
SYNTHETIC_MANUSCRIPT = (
    "# Synthetic draft\n\n## One\n\nMara öffnet die Tür. Regen fällt.\n\n"
    '„Komm herein“, sagt Mara.\n\n## Two\n\nMara wartet am Fenster. Der Regen bleibt.\n'
)


def run_cli(*arguments):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = main(list(arguments))
    return status, output.getvalue(), errors.getvalue()


@pytest.mark.parametrize("command", ANALYSIS_COMMANDS)
@pytest.mark.parametrize("outside", [False, True], ids=["cwd-root", "explicit-root"])
def test_analysis_configured_default_matches_explicit_selected_project(
    tmp_path, monkeypatch, command, outside,
):
    root = tmp_path / "project"
    drafts = root / "drafts"
    drafts.mkdir(parents=True)
    manuscript = drafts / "selected.md"
    manuscript.write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    (root / "manuscript.md").write_text("A wrong conventional file.", encoding="utf-8")
    (root / "lixity.toml").write_text(
        'manuscript = "drafts/selected.md"\nlanguage = "de"\ntitle = "Root title"\n', encoding="utf-8",
    )
    (drafts / "lixity.toml").write_text('language = "fr"\ntitle = "Wrong child title"\n', encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    (other / "lixity.toml").write_text('manuscript = "absent.md"\nlanguage = "en"\n', encoding="utf-8")
    monkeypatch.chdir(other if outside else root)
    options = [] if command in ("dashboard", "pdf", "build") else ["--json"]
    if command == "characters":
        options += ["--names", "Mara"]
    if command == "motifs":
        options += ["--motif", "rain=Regen"]
    output_path = tmp_path / ("result.pdf" if command == "pdf" else "result.html")
    if command in ("dashboard", "pdf"):
        options += ["--output", str(output_path)]
    status, output, errors = run_cli(command, "drafts/selected.md", "--project", str(root), *options)
    assert status == 0 and not errors
    if command == "build":
        explicit = {p.name: p.read_bytes() for p in (root / "exports").iterdir() if p.is_file()}
    elif command in ("dashboard", "pdf"):
        explicit = output_path.read_bytes()
        output_path.unlink()
    else:
        explicit = json.loads(output)
        if command != "style":
            assert explicit["meta"]["language"] == "de"
    flags = ["--project", str(root)] if outside else []
    status, output, errors = run_cli(command, *flags, *options)
    assert status == 0 and not errors
    if command == "build":
        configured = {p.name: p.read_bytes() for p in (root / "exports").iterdir() if p.is_file()}
        assert json.loads(configured["selected_metrics.json"])["meta"]["language"] == "de"
        assert b"Root title" in configured["selected_dashboard.html"]
        assert not (drafts / "exports").exists()
    elif command in ("dashboard", "pdf"):
        configured = output_path.read_bytes()
        assert (b"Root title" in configured) if command == "dashboard" else configured.startswith(b"%PDF-")
    else:
        configured = json.loads(output)
    assert configured == explicit
    assert not (other / "exports").exists()


@pytest.mark.parametrize("setting", [None, 'manuscript = [\n', 'manuscript = false\n',
    'manuscript = "missing.md"\n', 'manuscript = "../outside.md"\n',
    'manuscript = "drafts/../manuscript.md"\n'])
def test_analysis_omission_requires_valid_root_configured_file(tmp_path, monkeypatch, setting):
    (tmp_path / "manuscript.md").write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    if setting is not None:
        (tmp_path / "lixity.toml").write_text(setting, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    before = files(tmp_path)
    status, output, errors = run_cli("analyze", "--json")
    assert status == 1 and not output and errors
    assert "manuscript" in errors.lower() or "configuration" in errors.lower()
    assert files(tmp_path) == before


@pytest.mark.parametrize("kind", ["directory", "fifo", "escaping-alias"])
def test_analysis_rejects_nonregular_or_escaping_configured_source(tmp_path, monkeypatch, kind):
    root = tmp_path / "project"
    root.mkdir()
    selected = root / "selected.md"
    if kind == "directory":
        selected.mkdir()
    elif kind == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs unavailable")
        os.mkfifo(selected)
    else:
        outside = tmp_path / "outside.md"
        outside.write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
        selected.symlink_to(outside)
    (root / "lixity.toml").write_text('manuscript = "selected.md"\n', encoding="utf-8")
    monkeypatch.chdir(root)
    status, output, errors = run_cli("analyze", "--json")
    assert status == 1 and not output and errors


@pytest.mark.parametrize("selector", ["../outside.md", "alias.md"])
def test_analysis_explicit_project_rejects_escaping_explicit_source(tmp_path, selector):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    (root / "alias.md").symlink_to(outside)
    status, output, errors = run_cli("analyze", selector, "--project", str(root), "--json")
    assert status == 1 and not output and "project" in errors.lower()


def test_analysis_explicit_project_file_wins_over_unused_bad_manuscript_setting(tmp_path):
    (tmp_path / "explicit.md").write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = false\nlanguage = "de"\n', encoding="utf-8")
    status, output, errors = run_cli("analyze", "explicit.md", "--project", str(tmp_path), "--json")
    assert status == 0 and not errors
    assert json.loads(output)["meta"]["language"] == "de"


def test_analysis_omission_ignores_user_ancestor_and_environment_selectors(tmp_path, monkeypatch):
    parent = tmp_path / "parent"
    root = parent / "project"
    root.mkdir(parents=True)
    (parent / "draft.md").write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    (parent / "lixity.toml").write_text('manuscript = "draft.md"\nlanguage = "fr"\n', encoding="utf-8")
    user = Path(os.environ["HOME"]) / ".config"
    user.mkdir()
    (user / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    monkeypatch.setenv("LIXITY_DIR", str(parent))
    monkeypatch.chdir(root)
    status, output, errors = run_cli("analyze", "--json")
    assert status == 1 and not output and "manuscript" in errors.lower()


def test_analysis_switching_selected_roots_uses_each_nested_manuscript_and_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name, language, text in [("one", "de", SYNTHETIC_MANUSCRIPT), ("two", "fr", "## Un\n\nUne porte reste ouverte.\n")]:
        root = tmp_path / name
        (root / "drafts").mkdir(parents=True)
        (root / "drafts" / "draft.md").write_text(text, encoding="utf-8")
        (root / "lixity.toml").write_text(f'manuscript = "drafts/draft.md"\nlanguage = "{language}"\n', encoding="utf-8")
        status, output, errors = run_cli("analyze", "--project", str(root), "--json")
        assert status == 0 and not errors
        assert json.loads(output)["meta"]["language"] == language


def test_research_configured_default_find_link_reconcile_unlink_and_compare(tmp_path, monkeypatch):
    root = tmp_path / "project"
    api.init(root, title="Synthetic defaults")
    (root / "drafts").mkdir()
    manuscript = root / "drafts" / "draft.md"
    manuscript.write_text("## One\n\nA synthetic observer waits.\n", encoding="utf-8")
    (root / "lixity.toml").write_text('manuscript = "drafts/draft.md"\n', encoding="utf-8")
    claim = api.create_claim(root, title="Observation", statement="A synthetic observation.")["claim_id"]
    source = tmp_path / "source.txt"
    source.write_text("A synthetic observer waits in a reading room.\n", encoding="utf-8")
    source_id = api.ingest(root, source, allow_retention=True)["source_id"]
    monkeypatch.chdir(tmp_path)
    flags = ["--project", str(root)]
    before = files(root)
    status, explicit, errors = run_cli("research", "find-anchor", *flags, "drafts/draft.md", "--query", "A synthetic observer waits.")
    assert status == 0 and not errors
    status, configured, errors = run_cli("research", "find-anchor", *flags, "--query", "A synthetic observer waits.")
    assert status == 0 and not errors
    assert json.loads(configured) == json.loads(explicit)
    assert files(root) == before
    status, output, errors = run_cli("research", "link-manuscript", *flags, "--claim-id", claim, "--claim-revision", "1", "--quote", "A synthetic observer waits.", "--allow-retention")
    assert status == 0 and not errors
    link_id = json.loads(output)["link_id"]
    before = files(root)
    def no_writer_lock(self):
        pytest.fail("Configured reconciliation preview must not acquire a writer lock")
    with monkeypatch.context() as preview:
        preview.setattr(Repository, "locked", no_writer_lock)
        for command, options in [("review-manuscript", []), ("reconcile-manuscript", []),
                                 ("compare", ["--source-id", source_id])]:
            explicit_path = ["--manuscript", str(manuscript)]
            status, explicit, errors = run_cli("research", command, *flags, *explicit_path, *options)
            assert status == 0 and not errors
            status, configured, errors = run_cli("research", command, *flags, *options)
            assert status == 0 and not errors
            assert json.loads(configured) == json.loads(explicit)
    assert files(root) == before
    status, output, errors = run_cli("research", "unlink-manuscript", *flags, "--link-id", link_id, "--reason", "Synthetic retraction")
    assert status == 0 and not errors
    assert json.loads(output)["record"]["state"] == "retracted"


@pytest.mark.parametrize("command", ANALYSIS_COMMANDS)
def test_analysis_completion_offers_explicit_project(tmp_path, command):
    import shutil

    from lixity.cli import _completion_scripts

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash unavailable")
    script = _completion_scripts()[0]
    probe = f'\nCOMP_WORDS=(lixity {command} --proj); COMP_CWORD=2; _lixity_complete; printf "%s\\n" "${{COMPREPLY[@]}}"\n'
    completed = subprocess.run(  # noqa: S603 - resolved Bash and fixed CLI command names
        [bash, "--noprofile", "--norc"], input=script + probe,
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    assert not completed.stderr
    assert completed.stdout.split() == ["--project"]


@pytest.mark.parametrize("command", ANALYSIS_COMMANDS)
def test_analysis_help_explains_optional_file_and_explicit_project(command, capsys):
    with pytest.raises(SystemExit) as stopped:
        main([command, "--help"])
    assert stopped.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "[file]" in help_text and "--project PATH" in help_text
    assert "relative manuscript files resolve inside it" in help_text


@pytest.mark.parametrize("source_state", ["unreadable", "directory", "fifo"])
def test_configured_review_preserves_unreadable_source_and_analysis_fails(
    tmp_path, monkeypatch, source_state,
):
    api.init(tmp_path, title="Synthetic unavailable source")
    selected = tmp_path / "draft.md"
    if source_state == "directory":
        selected.mkdir()
    elif source_state == "fifo":
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFOs unavailable")
        os.mkfifo(selected)
    else:
        selected.write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
        original_open = os.open
        def unreadable(path, *args, **kwargs):
            if os.fspath(path) == str(selected):
                raise PermissionError(errno.EACCES, "Synthetic source is unreadable", str(selected))
            return original_open(path, *args, **kwargs)
        monkeypatch.setattr(os, "open", unreadable)
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    status, output, errors = run_review()
    assert status == 0 and not errors
    assert json.loads(output)["source_state"] == "unreadable"
    status, output, errors = run_cli("analyze", "--json")
    assert status == 1 and not output and errors
    status, output, errors = run_cli("research", "find-anchor", "--query", "Synthetic observer")
    assert status == 1 and not output and errors


@pytest.mark.parametrize("command,options", [
    ("review-manuscript", []), ("find-anchor", ["--query", "Synthetic quote"]),
    ("link-manuscript", ["--claim-id", "urn:uuid:5268acf4-d0e3-433d-8f92-fd611402f376", "--claim-revision", "1", "--quote", "Synthetic quote"]),
    ("unlink-manuscript", ["--link-id", "urn:uuid:5268acf4-d0e3-433d-8f92-fd611402f376", "--reason", "Synthetic reason"]),
    ("reconcile-manuscript", []),
    ("compare", ["--source-id", "urn:uuid:5268acf4-d0e3-433d-8f92-fd611402f376"]),
])
def test_research_default_validates_explicit_archive_before_bad_config(tmp_path, command, options):
    (tmp_path / "lixity.toml").write_text("manuscript = [\n", encoding="utf-8")
    status, output, errors = run_cli("research", command, "--project", str(tmp_path), *options)
    assert status == 1 and not output
    assert "config" not in errors.lower() and errors


def test_configured_defaults_keep_retention_and_reconciliation_guards(tmp_path, monkeypatch):
    import hashlib

    api.init(tmp_path, title="Synthetic guarded manuscript")
    selected = tmp_path / "draft.md"
    selected.write_text("## One\n\nA synthetic observer waits.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    claim = api.create_claim(tmp_path, title="Observation", statement="A synthetic observation.")["claim_id"]
    monkeypatch.chdir(tmp_path)
    link = ["research", "link-manuscript", "--claim-id", claim, "--claim-revision", "1", "--quote", "A synthetic observer waits."]
    before = files(tmp_path)
    status, output, errors = run_cli(*link)
    assert status == 1 and not output and "retention" in errors
    assert files(tmp_path) == before
    status, output, errors = run_cli(*link, "--allow-retention")
    assert status == 0 and not errors
    link_id = json.loads(output)["link_id"]
    selected.write_text("## One\n\nA new synthetic paragraph.\n\nA synthetic observer waits.\n", encoding="utf-8")
    before = files(tmp_path)
    snapshot = Repository(tmp_path).snapshot()
    strict_cases = [
        ["--expected-snapshot", "0" * 64],
        ["--expected-source-sha256", "0" * 64, "--expected-snapshot", snapshot.digest],
    ]
    for options in strict_cases:
        status, output, errors = run_cli("research", "reconcile-manuscript", "--accept-moved", *options)
        assert status == 1 and not output and errors
        assert files(tmp_path) == before
    # Bulk reconciliation reports per-association conflicts as skips unless a
    # strict snapshot was supplied; omission must preserve that contract.
    status, output, errors = run_cli("research", "reconcile-manuscript", "--accept-moved",
                                   "--expected-source-sha256", "0" * 64)
    assert status == 0 and not errors
    result = json.loads(output)
    assert result["accepted"] == [] and len(result["skipped"]) == 1
    assert result["skipped"][0]["link_id"] == link_id
    assert files(tmp_path) == before
    status, output, errors = run_cli("research", "reconcile-manuscript", "--accept-moved",
        "--expected-snapshot", snapshot.digest, "--expected-source-sha256", hashlib.sha256(selected.read_bytes()).hexdigest())
    assert status == 0 and not errors
    saved = Repository(tmp_path).snapshot().records[link_id]
    assert saved.revision == 2 and saved.anchor.start_line == 5


def test_selected_root_does_not_inherit_ancestor_settings_and_preserves_internal_alias(tmp_path):
    root = tmp_path / "project"
    (root / "drafts").mkdir(parents=True)
    target = root / "drafts" / "draft.md"
    target.write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    (root / "alias.md").symlink_to(target)
    (tmp_path / "lixity.toml").write_text('language = "fr"\n', encoding="utf-8")
    (root / "lixity.toml").write_text(
        'manuscript = "alias.md"\n[register_profiles.voice]\n[chapter_registers]\n"1" = "voice"\n', encoding="utf-8")
    status, output, errors = run_cli("analyze", "--project", str(root), "--json")
    assert status == 0 and not errors
    assert json.loads(output)["meta"]["language"] == "en"
    status, output, errors = run_cli("style", "--project", str(root), "--json")
    assert status == 0 and not errors
    assert json.loads(output)["meta"]["chapter_registers"] == {"1": "voice"}


@pytest.mark.parametrize("command", ["scenes", "build"])
@pytest.mark.parametrize("configured", [False, True], ids=["legacy-conventions", "root-configured"])
def test_folder_commands_preserve_user_defaults_only_for_legacy_conventions(
    tmp_path, monkeypatch, command, configured,
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "manuscript.md").write_text(SYNTHETIC_MANUSCRIPT, encoding="utf-8")
    config = 'title = "Root project title"\n'
    if configured:
        config += 'manuscript = "manuscript.md"\n'
    (root / "lixity.toml").write_text(config, encoding="utf-8")
    user = Path(os.environ["HOME"]) / ".config"
    user.mkdir()
    (user / "lixity.toml").write_text('language = "de"\nfdr_q = 0.031\n', encoding="utf-8")
    monkeypatch.chdir(root)
    status, output, errors = run_cli(command, *([] if command == "build" else ["--json"]))
    assert status == 0 and not errors
    if command == "build":
        result = json.loads((root / "exports" / "manuscript_metrics.json").read_text(encoding="utf-8"))
        style = json.loads((root / "exports" / "manuscript_style.json").read_text(encoding="utf-8"))
        assert style["meta"]["fdr_q"] == (0.05 if configured else 0.031)
        assert "Root project title" in (root / "exports" / "manuscript_dashboard.html").read_text(encoding="utf-8")
    else:
        result = json.loads(output)
    assert result["meta"]["language"] == ("en" if configured else "de")
