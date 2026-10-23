"""Explicit preamble edits preserve every real heading and source boundary."""

import json

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.attachments import place_attachment
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


def test_preamble_read_and_guarded_update_preserve_heading_body(tmp_path):
    api.init(tmp_path, title="Synthetic preamble")
    original = "Opening note.\r\n\r\n## Overview\r\n\r\nReal section.\r\n\r\n## Next\r\n\r\nKeep exactly.\r\n"
    dossier = api.create_dossier(tmp_path, "Dossier", original)["dossier_id"]
    before = Repository(tmp_path).snapshot()
    read = api.get_dossier(tmp_path, dossier, preamble=True)
    assert read["content"] == "Opening note.\r\n\r\n"
    assert api.get_dossier(tmp_path, dossier, section="Overview")["content"].startswith("Real section.")
    arguments = {"expected_snapshot": before.digest, "expected_revision": 1, "change_kind": "correction", "reason": "Clarify entry"}
    preview = api.revise_record(tmp_path, "dossier", dossier, changes={"preamble":"New entry.\n"}, dry_run=True, **arguments)
    assert Repository(tmp_path).snapshot().digest == before.digest
    saved = api.revise_record(tmp_path, "dossier", dossier, changes={"preamble":"New entry.\n"}, **arguments)
    assert saved["record"]["body"] == "New entry.\r\n\r\n" + original[original.index("## Overview"):]
    assert preview["candidate"]["body"] == saved["record"]["body"]
    with pytest.raises(ResearchConflictError):
        api.revise_record(tmp_path, "dossier", dossier, changes={"preamble":"Stale"}, **arguments)


def test_empty_preamble_noop_clear_and_heading_free_body(tmp_path):
    api.init(tmp_path, title="Synthetic entry")
    dossier = api.create_dossier(tmp_path, "Dossier", "## Real\n\nOriginal.\n")["dossier_id"]
    snapshot = Repository(tmp_path).snapshot().digest
    assert api.get_dossier(tmp_path, dossier, preamble=True)["content"] == ""
    saved = api.revise_record(tmp_path, "dossier", dossier, changes={"preamble":""},
        expected_snapshot=snapshot, expected_revision=1, change_kind="correction", reason="No change")
    assert saved["snapshot"] == snapshot
    other = api.create_dossier(tmp_path, "Without headings", "Only an opening note.")["dossier_id"]
    assert api.get_dossier(tmp_path, other, preamble=True)["content"] == "Only an opening note."
    with pytest.raises(ResearchError):
        api.get_dossier(tmp_path, dossier, preamble=True, section="Real")
    with pytest.raises(ResearchError):
        api.revise_record(tmp_path, "dossier", dossier, changes={"preamble":"Entry", "body":"Conflict"},
            expected_snapshot=Repository(tmp_path).snapshot().digest, expected_revision=1,
            change_kind="correction", reason="Invalid")


def test_attachment_section_error_lists_actual_candidates():
    with pytest.raises(ResearchError, match=r"1\. Harbour"):
        place_attachment("## 1. Harbour\n\nNotes.\n\n## 2. Station\n\nNotes.", "![Map](example.png)",
                         section="Harbour", replace_reference=None)


def test_cli_preamble_read_preview_and_save(tmp_path, capsys):
    api.init(tmp_path, title="Synthetic CLI")
    dossier = api.create_dossier(tmp_path, "Entry", "Old entry.\n\n## Real\n\nKeep.\n")["dossier_id"]
    common = ["research", "dossier", dossier, "--project", str(tmp_path), "--preamble"]
    assert main([*common, "--format", "text", "--body-only"]) == 0
    assert capsys.readouterr().out == "Old entry.\n\n"
    current = api.get_dossier(tmp_path, dossier)
    update = [*common, "--update", "--body", "New entry.", "--expected-snapshot", current["snapshot"],
              "--expected-revision", "1", "--change-kind", "correction", "--reason", "Clarify", "--compact"]
    assert main([*update, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert api.get_dossier(tmp_path, dossier)["body"].startswith("Old entry.")
    assert main(update) == 0
    assert json.loads(capsys.readouterr().out)["revision"] == 2
    assert api.get_dossier(tmp_path, dossier)["body"] == "New entry.\n\n## Real\n\nKeep.\n"


def test_preamble_source_roundtrip_does_not_normalize_existing_spacing():
    from lixity.research.sections import preamble_text, update_preamble

    for body in ("Entry.\n## Main\nBody.\n", "Entry.\r\n\r\n\r\n## Main\r\nBody.\r\n"):
        assert update_preamble(body, preamble_text(body)) == body
