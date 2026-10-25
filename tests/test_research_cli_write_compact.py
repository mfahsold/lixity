"""Compact write receipts preserve the native mutation and preview contracts."""

import json

import pytest

from lixity.research import api
from tests.research_support import capture_research, retained_files


@pytest.fixture
def dossier(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic compact writes")
    identifier = api.create_dossier(project, "Room notes", "Original notes.")["dossier_id"]
    return project, identifier


def update(project, identifier, *arguments, revision=1):
    return capture_research(
        "dossier", identifier, "--project", str(project), "--update",
        "--expected-revision", str(revision), "--change-kind", "correction",
        "--reason", "Clarify the synthetic room notes.", *arguments,
    )


def test_compact_dry_run_reports_changed_fields_without_body_or_writes(dossier):
    project, identifier = dossier
    before = retained_files(project)
    body = "LONG_SYNTHETIC_BODY_MUST_NOT_BE_ECHOED " * 2000
    status, output, errors = update(project, identifier, "--body", body, "--dry-run", "--compact")
    assert (status, errors) == (0, "")
    result = json.loads(output)
    assert result["schema_version"] == "research-revision-write-summary-local/1"
    assert result["record_id"] == identifier and result["kind"] == "dossier"
    assert result["dry_run"] is True and result["ready"] is True and result["changed"] is True
    assert result["base_revision"] == 1 and result["candidate_revision"] == 2
    assert result["changed_fields"] == ["body"]
    assert "revision" not in result
    assert "LONG_SYNTHETIC_BODY_MUST_NOT_BE_ECHOED" not in output and len(output) < 2000
    assert retained_files(project) == before


def test_compact_apply_saves_native_revision_and_reports_only_accepted_metadata(dossier):
    project, identifier = dossier
    status, output, errors = update(project, identifier, "--body", "Revised notes.", "--compact")
    assert (status, errors) == (0, "")
    result = json.loads(output)
    assert result["dry_run"] is False and result["changed"] is True
    assert result["base_revision"] == 1 and result["revision"] == 2
    assert result["change"]["previous_revision"] == 1
    assert "candidate_revision" not in result and "changed_fields" not in result
    assert "Revised notes." not in output
    current = api.get_record(project, "dossier", identifier)
    assert current["record"]["body"] == "Revised notes."
    assert current["snapshot"] == result["snapshot"]


@pytest.mark.parametrize("preview", [False, True])
def test_compact_noop_does_not_report_a_previous_revision_change_as_new(dossier, preview):
    project, identifier = dossier
    assert update(project, identifier, "--body", "Revised notes.")[0] == 0
    before = retained_files(project)
    flags = ("--dry-run",) if preview else ()
    status, output, errors = update(project, identifier, "--body", "Revised notes.",
                                   "--compact", *flags, revision=2)
    assert (status, errors) == (0, "")
    result = json.loads(output)
    assert result["changed"] is False and result["change"] is None
    assert result["candidate_revision" if preview else "revision"] == 2
    if preview:
        assert result["changed_fields"] == []
    assert retained_files(project) == before


def test_compact_human_result_is_short_and_keeps_warning_and_control_boundaries(dossier):
    project, identifier = dossier
    status, output, errors = update(project, identifier, "--body", "Revised notes.",
                                   "--compact", "--format", "text")
    assert (status, errors) == (0, "")
    assert "Saved revision 2" in output and identifier in output
    assert "Revised notes." not in output
    assert len(output.splitlines()) <= 4
    status, output, errors = update(project, identifier, "--body", "Revised notes.",
                                   "--compact", "--format", "text", revision=2)
    assert (status, errors) == (0, "")
    assert "No changes" in output


@pytest.mark.parametrize("flags", [
    (), ("--history",), ("--inspect",), ("--revision", "1"),
    ("--diff", "--body", "Draft"), ("--prepare", "--base-revision", "1", "--body", "Draft"),
    ("--update", "--body", "Draft", "--expected-revision", "1", "--change-kind", "correction",
     "--reason", "Synthetic change", "--format", "table"),
])
def test_invalid_compact_modes_fail_before_any_archive_change(dossier, flags):
    project, identifier = dossier
    before = retained_files(project)
    status, output, errors = capture_research("dossier", identifier, "--project", str(project), "--compact", *flags)
    assert status != 0 and not output and "--compact" in errors
    assert retained_files(project) == before


def test_default_full_write_json_remains_the_existing_record_contract(dossier):
    project, identifier = dossier
    status, output, errors = update(project, identifier, "--body", "Revised notes.")
    assert (status, errors) == (0, "")
    result = json.loads(output)
    assert result["schema_version"] == "research-record-local/1"
    assert result["record"]["body"] == "Revised notes."


def test_compact_conflict_does_not_return_a_success_receipt(dossier):
    project, identifier = dossier
    assert update(project, identifier, "--body", "Another author's notes.")[0] == 0
    before = retained_files(project)
    status, output, errors = update(project, identifier, "--body", "Stale draft.", "--compact")
    assert status == 1 and not output and "revision changed" in errors.lower()
    assert retained_files(project) == before


@pytest.mark.parametrize("preview", [False, True])
def test_compact_keeps_all_authored_record_kinds_and_claim_warnings(tmp_path, monkeypatch, preview):
    project = tmp_path / "project"
    api.init(project, title="Synthetic authored receipts")
    dossier_id = api.create_dossier(project, "Room", "Original notes.")["dossier_id"]
    claim = api.create_claim(project, title="Opening", statement="The room opened.")["claim_id"]
    second = api.create_claim(project, title="Visit", statement="A visitor arrived.")["claim_id"]
    decision = api.record_decision(project, title="Keep opening", rationale="Original rationale.")["decision_id"]
    relation = api.create_claim_relation(project, claim, second)["relation_id"]
    source = tmp_path / "source.txt"
    source.write_text("The synthetic room opened in 1924.", encoding="utf-8")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    evidence = api.link_evidence(project, claim_id=claim, passage_id=passage)["evidence_link_id"]

    def unexpected_read(*args, **kwargs):
        pytest.fail("Compact receipts must not fetch the record again after a guarded operation")

    operations = (
        ("dossier", "dossier", "--dossier-id", dossier_id, ("--body", "Reviewed notes.")),
        ("claim", "claim", "--claim-id", claim, ("--time-period", "one autumn")),
        ("decision", "decision", "--decision-id", decision, ("--rationale", "Reviewed rationale.")),
        ("relate", "claim_relation", "--relation-id", relation, ("--rationale", "Reviewed rationale.")),
        ("link-evidence", "evidence_link", "--evidence-link-id", evidence, ("--rationale", "Reviewed rationale.")),
    )
    with monkeypatch.context() as patch:
        patch.setattr(api, "get_record", unexpected_read)
        for command, kind, flag, identifier, changes in operations:
            status, output, errors = capture_research(
                command, flag, identifier, "--project", str(project), "--update", "--compact",
                "--expected-revision", "1", "--change-kind", "correction", "--reason", "Synthetic review",
                *changes, *(("--dry-run",) if preview else ()),
            )
            assert (status, errors) == (0, "")
            receipt = json.loads(output)
            assert receipt["kind"] == kind and receipt["record_id"] == identifier
            assert receipt["changed"] is True and receipt["candidate_revision" if preview else "revision"] == 2
            if kind == "claim":
                assert receipt["warnings"] and "one autumn" in receipt["warnings"][0]
    for _, kind, _, identifier, _ in operations:
        assert api.get_record(project, kind, identifier)["record"]["revision"] == (1 if preview else 2)


def test_compact_latest_uses_the_single_review_read_already_required(dossier, monkeypatch):
    project, identifier = dossier
    get_record = api.get_record
    calls = []

    def count_read(*args, **kwargs):
        calls.append(args)
        return get_record(*args, **kwargs)

    monkeypatch.setattr(api, "get_record", count_read)
    status, output, errors = capture_research(
        "dossier", identifier, "--project", str(project), "--update", "--latest", "--compact",
        "--body", "Revised notes.", "--change-kind", "correction", "--reason", "Synthetic review",
    )
    assert (status, errors) == (0, "")
    assert len(calls) == 1 and json.loads(output)["revision"] == 2


def test_compact_human_warning_cannot_inject_terminal_controls(dossier):
    project, _ = dossier
    claim = api.create_claim(project, title="Opening", statement="The room opened.")["claim_id"]
    status, output, errors = capture_research(
        "claim", claim, "--project", str(project), "--update", "--compact", "--format", "text",
        "--expected-revision", "1", "--change-kind", "correction", "--reason", "Synthetic review",
        "--time-period", "one\x1b[2J autumn\u202e", "--dry-run",
    )
    assert (status, errors) == (0, "")
    assert "Warnings:" in output and "\x1b" not in output and "\u202e" not in output
