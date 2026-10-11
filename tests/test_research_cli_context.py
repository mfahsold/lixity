"""Research CLI conveniences remain confined to one verified current project."""

import contextlib
import io
import json

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository


def run_cli(*arguments):
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = main(["research", *arguments])
    return status, output.getvalue(), errors.getvalue()


def files(root):
    return {str(path.relative_to(root)): None if path.is_dir() else path.read_bytes()
            for path in root.rglob("*")}


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    api.init(root, title="Synthetic current project")
    return root


@pytest.fixture
def evidence(project, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("A synthetic reading room opened in 1924.\n", encoding="utf-8")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    claim = api.create_claim(project, title="Synthetic claim", statement="A room opened in 1924.")
    return source, capture["source_id"], passage, claim["claim_id"]


def test_omitted_project_reads_only_verified_cwd_without_writes(project, monkeypatch):
    monkeypatch.chdir(project)
    before = files(project)
    expected_id = Repository(project).snapshot().project.id
    status, output, errors = run_cli("sources")
    assert status == 0 and not errors
    assert json.loads(output)["project_id"] == expected_id
    assert files(project) == before


def test_explicit_project_is_authoritative_even_with_another_valid_cwd(project, tmp_path, monkeypatch):
    other = tmp_path / "other"
    expected = api.init(other, title="Explicit other project")
    monkeypatch.chdir(project)
    status, output, errors = run_cli("sources", "--project", str(other))
    assert status == 0 and not errors
    assert json.loads(output)["project_id"] == expected["project_id"]
    missing = tmp_path / "missing"
    before = files(tmp_path)
    status, output, errors = run_cli("sources", "--project", str(missing))
    assert status == 1 and not output and errors
    assert files(tmp_path) == before


@pytest.mark.parametrize("context", ["empty", "nested", "partial", "corrupt", "symlink"])
def test_missing_or_invalid_cwd_is_not_discovered_or_initialized(project, tmp_path, monkeypatch, context):
    cwd = project / "nested" if context == "nested" else tmp_path / context
    cwd.mkdir()
    if context == "partial":
        (cwd / "research").mkdir()
    elif context == "corrupt":
        api.init(cwd, title="Synthetic corrupted project")
        (cwd / "research" / "HEAD.json").write_text("corrupt\n", encoding="utf-8")
    elif context == "symlink":
        try:
            (cwd / "research").symlink_to(project / "research", target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symbolic links are unavailable")
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("LIXITY_RESEARCH_PROJECT", str(project))
    before = files(tmp_path)
    status, output, errors = run_cli("sources")
    assert status == 1 and not output
    assert "current directory" in errors and "--project" in errors
    assert files(tmp_path) == before


def test_initialization_still_requires_an_explicit_destination(project, monkeypatch):
    monkeypatch.chdir(project)
    before = files(project)
    with pytest.raises(SystemExit) as failure:
        run_cli("init", "--title", "Do not replace the selected project")
    assert failure.value.code == 2
    assert files(project) == before


def test_short_link_saves_one_pinned_citation_using_existing_api_defaults(project, evidence, monkeypatch):
    source, source_id, passage, claim = evidence
    current = Repository(project).snapshot()
    api.revise_record(project, "claim", claim, changes={"statement": "A revised synthetic claim."},
                      expected_snapshot=current.digest, expected_revision=1,
                      change_kind="correction", reason="Synthetic correction")
    source.write_text("The latest source has a different synthetic sentence.\n", encoding="utf-8")
    api.ingest(project, source, source_id=source_id, allow_retention=True)
    monkeypatch.chdir(project)
    before = Repository(project).snapshot()
    status, output, errors = run_cli("link", passage, claim)
    assert status == 0 and not errors
    receipt = json.loads(output)
    assert receipt["schema_version"] == "research-evidence-link-local/1"
    assert receipt["passage_id"] == passage and receipt["claim_id"] == claim
    assert receipt["relation"] == "supports"
    after = Repository(project).snapshot()
    assert after.manifest.generation == before.manifest.generation + 1
    links = api.list_evidence_links(project)["evidence_links"]
    assert len(links) == 1
    assert links[0]["claim_revision"] == 2
    assert links[0]["reviewer"] == "author" and links[0]["created_by"] == "local-author"
    assert links[0]["citation"]["verbatim"] == "A synthetic reading room opened in 1924."


def test_short_link_options_and_old_named_command_both_commit_once(project, evidence, monkeypatch):
    _source, _source_id, passage, claim = evidence
    monkeypatch.chdir(project)
    before = Repository(project).snapshot().manifest.generation
    status, output, errors = run_cli(
        "link", passage, claim, "--relation", "qualifies", "--rationale", "Synthetic rationale",
        "--reviewer", "Synthetic reviewer", "--actor", "Synthetic actor",
    )
    assert status == 0 and not errors and json.loads(output)["relation"] == "qualifies"
    assert Repository(project).snapshot().manifest.generation == before + 1
    status, output, errors = run_cli(
        "link-evidence", "--project", str(project), "--passage-id", passage, "--claim-id", claim,
        "--relation", "contradicts",
    )
    assert status == 0 and not errors and json.loads(output)["relation"] == "contradicts"
    assert Repository(project).snapshot().manifest.generation == before + 2
    links = api.list_evidence_links(project)["evidence_links"]
    assert len(links) == 2
    short = next(link for link in links if link["relation"] == "qualifies")
    assert short["rationale"] == "Synthetic rationale"
    assert short["reviewer"] == "Synthetic reviewer" and short["created_by"] == "Synthetic actor"


@pytest.mark.parametrize("invalid", ["passage", "claim", "prefix", "reversed", "source", "foreign"])
def test_short_link_rejects_malformed_incomplete_and_wrong_kind_ids_without_writes(
    project, evidence, monkeypatch, invalid,
):
    _source, source_id, passage, claim = evidence
    if invalid == "passage":
        passage = "not-an-id"
    elif invalid == "claim":
        claim = "not-an-id"
    elif invalid == "prefix":
        passage = "urn:uuid:"
    elif invalid == "reversed":
        passage, claim = claim, passage
    elif invalid == "source":
        passage = source_id
    else:
        other = project.parent / "foreign"
        api.init(other, title="Another synthetic archive")
        claim = api.create_claim(other, title="Foreign claim", statement="A separate claim.")["claim_id"]
    monkeypatch.chdir(project)
    before = files(project)
    status, output, errors = run_cli("link", passage, claim)
    assert status == 1 and not output and errors
    assert files(project) == before


def test_destructive_preview_uses_the_same_verified_cwd_policy(project, evidence, monkeypatch):
    _source, source_id, _passage, _claim = evidence
    monkeypatch.chdir(project)
    before = files(project)
    status, output, errors = run_cli("purge", "--source-id", source_id, "--dry-run")
    assert status == 0 and not errors and json.loads(output)["dry_run"] is True
    assert files(project) == before
