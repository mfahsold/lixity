"""Record-scoped CLI convenience preserves explicit revisions and backend CAS."""

import json

import pytest

from lixity.research import api
from tests.research_support import capture_research
from tests.research_support import revise_record as revise


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic CLI updates")
    dossier = api.create_dossier(project, "Room notes", "Synthetic notes.")["dossier_id"]
    claim = api.create_claim(project, title="Room", statement="The room was open.", dossier_id=dossier)["claim_id"]
    return project, dossier, claim


def run(*arguments):
    status, output, errors = capture_research(*arguments)
    return status, json.loads(output) if output else None, errors


def update(project, claim, *flags, expected_revision=1):
    return run("claim", "--project", str(project), "--claim-id", claim, "--update",
               "--expected-revision", str(expected_revision), "--change-kind", "correction",
               "--reason", "Synthetic author update", *flags)



def test_omitted_snapshot_allows_unrelated_archive_write(archive):
    project, _, claim = archive
    original = api.get_record(project, "claim", claim)
    api.create_dossier(project, "Unrelated notes", "A separate synthetic note.")
    status, result, errors = update(project, claim, "--statement", "The room may have been open.")
    assert status == 0, errors
    assert result["record"]["revision"] == original["record"]["revision"] + 1
    assert result["record"]["statement"] == "The room may have been open."


def test_same_record_change_requires_prepare_instead_of_overwrite(archive):
    project, _, claim = archive
    revise(project, "claim", claim, {"statement": "Another author changed this statement."})
    before = api.get_record(project, "claim", claim)
    status, result, errors = update(project, claim, "--title", "My title")
    assert status == 1 and result is None
    assert "revision changed" in errors.lower() and "--prepare" in errors and "--base-revision 1" in errors
    assert api.get_record(project, "claim", claim) == before


def test_snapshot_convenience_never_retries_writer_race(archive, monkeypatch):
    project, _, claim = archive
    writer = api.revise_record
    calls = []

    def race(*args, **kwargs):
        calls.append(kwargs)
        api.create_dossier(project, "Race notes", "Synthetic racing write.")
        return writer(*args, **kwargs)

    monkeypatch.setattr(api, "revise_record", race)
    status, result, errors = update(project, claim, "--title", "My title")
    assert status == 1 and result is None
    assert "snapshot changed" in errors.lower() and "--prepare" in errors
    assert len(calls) == 1
    assert api.get_record(project, "claim", claim)["record"]["revision"] == 1


def test_explicit_snapshot_stays_strict_after_unrelated_write(archive):
    project, _, claim = archive
    reviewed = api.get_record(project, "claim", claim)["snapshot"]
    api.create_dossier(project, "Unrelated notes", "Synthetic unrelated write.")
    status, result, errors = update(project, claim, "--title", "My title", "--expected-snapshot", reviewed)
    assert status == 1 and result is None
    assert "snapshot changed" in errors.lower()
    assert api.get_record(project, "claim", claim)["record"]["revision"] == 1


def test_unchanged_association_id_keeps_reviewed_pin_when_target_changes(archive):
    project, dossier, claim = archive
    revise(project, "dossier", dossier, {"body": "A newer synthetic note."})
    status, result, errors = update(project, claim, "--title", "My title", "--dossier-id", dossier)
    assert status == 0, errors
    assert result["record"]["dossier_ref"] == {"id": dossier, "revision": 1}


def test_new_association_requires_explicit_pin_without_reviewed_snapshot(archive):
    project, _, claim = archive
    dossier = api.create_dossier(project, "New notes", "Synthetic new association.")["dossier_id"]
    status, result, errors = update(project, claim, "--dossier-id", dossier)
    assert status == 1 and result is None
    assert "--dossier-revision" in errors and "--expected-snapshot" in errors
    assert api.get_record(project, "claim", claim)["record"]["revision"] == 1
    status, result, errors = update(project, claim, "--dossier-id", dossier, "--dossier-revision", "1")
    assert status == 0, errors
    assert result["record"]["dossier_ref"] == {"id": dossier, "revision": 1}


def test_invalid_association_pin_still_fails_backend_validation(archive):
    project, _, claim = archive
    dossier = api.create_dossier(project, "New notes", "Synthetic new association.")["dossier_id"]
    status, result, errors = update(project, claim, "--dossier-id", dossier, "--dossier-revision", "99")
    assert status == 1 and result is None
    assert "pinned reference" in errors
    assert api.get_record(project, "claim", claim)["record"]["revision"] == 1


def test_new_decision_dossier_requires_pin_map_and_keeps_old_dossier_pin(archive):
    project, dossier, _ = archive
    decision = api.record_decision(project, title="Keep room", rationale="Synthetic interpretation.",
                                   dossier_ids=[dossier])["decision_id"]
    added = api.create_dossier(project, "Added notes", "Synthetic added note.")["dossier_id"]
    revise(project, "dossier", dossier, {"body": "Newer note text."})
    arguments = ("decision", "--project", str(project), "--decision-id", decision, "--update",
                 "--expected-revision", "1", "--change-kind", "correction", "--reason", "Synthetic update",
                 "--dossiers", f"{dossier},{added}")
    status, _, errors = run(*arguments)
    assert status == 1 and "--dossier-revisions" in errors
    status, result, errors = run(*arguments, "--dossier-revisions", json.dumps({added: 1}))
    assert status == 0, errors
    assert result["record"]["dossier_refs"] == [{"id": dossier, "revision": 1}, {"id": added, "revision": 1}]



def test_explicit_snapshot_keeps_existing_association_behavior(archive, monkeypatch):
    project, _, claim = archive
    dossier = api.create_dossier(project, "New notes", "Synthetic new association.")["dossier_id"]
    snapshot = api.get_record(project, "claim", claim)["snapshot"]

    def unexpected_read(*args, **kwargs):
        pytest.fail("An explicit snapshot must not trigger convenience rereading")

    with monkeypatch.context() as patch:
        patch.setattr(api, "get_record", unexpected_read)
        status, result, errors = update(project, claim, "--dossier-id", dossier, "--expected-snapshot", snapshot)
    assert status == 0, errors
    assert result["record"]["dossier_ref"] == {"id": dossier, "revision": 1}


def test_omitted_snapshot_still_requires_reviewed_revision(archive):
    project, _, claim = archive
    status, result, errors = run("claim", "--project", str(project), "--claim-id", claim, "--update",
                                 "--title", "My title", "--change-kind", "correction", "--reason", "Synthetic update")
    assert status == 1 and result is None and "--expected-revision" in errors
    assert api.get_record(project, "claim", claim)["record"]["revision"] == 1


@pytest.mark.parametrize("command", ["decision", "relate"])
def test_changed_claim_associations_require_pins_for_each_endpoint(archive, command):
    project, _, claim = archive
    second = api.create_claim(project, title="Another room", statement="A second room was open.")["claim_id"]
    third = api.create_claim(project, title="Third room", statement="A third room was open.")["claim_id"]
    if command == "decision":
        record = api.record_decision(project, title="Keep room", rationale="Synthetic interpretation.",
                                     claim_id=claim)["decision_id"]
        flags = ("--decision-id", record)
        changed = ("--claim-id", second)
        pin_flag, ref_name = "--claim-revision", "claim_ref"
    else:
        record = api.create_claim_relation(project, claim, second)["relation_id"]
        flags = ("--relation-id", record)
        changed = (third,)
        pin_flag, ref_name = "--from-claim-revision", "from_claim_ref"
    arguments = (command, "--project", str(project), *flags, "--update", "--expected-revision", "1",
                 "--change-kind", "correction", "--reason", "Synthetic association update", *changed)
    status, result, errors = run(*arguments)
    assert status == 1 and result is None and pin_flag in errors
    status, result, errors = run(*arguments, pin_flag, "1")
    assert status == 0, errors
    assert result["record"][ref_name] == {"id": second if command == "decision" else third, "revision": 1}
