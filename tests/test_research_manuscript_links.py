"""Explicit manuscript selections retain only reviewed quotes and exact claim pins."""

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from lixity.pipeline import profile_document, resolve_document_config
from lixity.research import api, cli
from lixity.research.manuscript import manuscript_links_data
from lixity.research.models import Head, Manifest, Reference, Tombstone
from lixity.research.repository import (
    Repository,
    ResearchConflictError,
    ResearchError,
    digest,
    encode,
)
from lixity.style_fingerprint import FingerprintThresholds
from tests.research_support import research_parser
from tests.research_support import revise_record as revise


@pytest.fixture
def manuscript_archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic manuscript archive")
    dossier = api.create_dossier(project, "Reading room", "Synthetic research notes.")["dossier_id"]
    claim = api.create_claim(project, title="Room", statement="The room was open.", dossier_id=dossier)["claim_id"]
    manuscript = project / "draft.md"
    # Binary writing keeps the fixture bytes identical on every platform; a
    # text-mode write would translate LF on Windows and break byte-level checks.
    content = "## Chapter One\n\nThe **reading room** was open. 🦉 A visitor arrived.\n"
    manuscript.write_bytes(content.encode("utf-8"))
    return project, manuscript, claim, dossier


def selection(quote="🦉 A visitor arrived."):
    paragraph = "The reading room was open. 🦉 A visitor arrived."
    start = paragraph.index(quote)
    return {"start_line": 3, "end_line": 3, "paragraph_sha256": hashlib.sha256(paragraph.encode()).hexdigest(),
            "start": start, "end": start + len(quote), "quote": quote}


def save_link(archive, **overrides):
    project, manuscript, claim, _ = archive
    snapshot = Repository(project).snapshot()
    values = {"claim_revision": 1, "selection": selection(), "expected_project_id": snapshot.project.id,
              "expected_snapshot": snapshot.digest, "expected_source_sha256": digest(manuscript.read_bytes()),
              "allow_retention": True}
    values.update(overrides)
    return api.link_manuscript_claim(project, manuscript, claim, **values)


def accepted_bytes(project):
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for path in (project / "research").rglob("*") if path.is_file()}


@pytest.mark.parametrize("target_kind,expected", [("claim", True), ("source", False)])
def test_manuscript_link_availability_uses_indexed_claim_lifecycle(manuscript_archive, target_kind, expected):
    project, _manuscript, claim, _dossier = manuscript_archive
    save_link(manuscript_archive)
    repository = Repository(project)
    snapshot = repository.snapshot()
    tombstone = Tombstone(**api.envelope(snapshot.project.id, "synthetic-author"),
                          target_kind=target_kind, target_ref=Reference(id=claim, revision=2),
                          operation="withdraw", reason="Synthetic availability review")
    snapshot = repository.commit([tombstone], {}, snapshot)

    class CountedRecords(dict):
        scans = 0

        def values(self):
            self.scans += 1
            return super().values()

    records = CountedRecords(snapshot.records)
    snapshot = replace(snapshot, records=records)
    records.scans = 0
    result = manuscript_links_data(snapshot)
    assert result["links"][0]["claim_withdrawn"] is expected
    assert result["links"][0]["review_needed"] is expected
    assert records.scans == 1


def test_save_preserves_old_records_and_retains_only_selected_quote(manuscript_archive):
    project, manuscript, claim, _ = manuscript_archive
    repository = Repository(project)
    before = repository.snapshot()
    records = {entry.ref: repository.record_path(entry).read_bytes() for entry in before.manifest.entries}
    result = save_link(manuscript_archive)
    assert result["schema_version"] == "research-manuscript-link-local/1"
    assert result["project_id"] == before.project.id
    after = repository.snapshot()
    assert after.manifest.schema_version == "research-manifest-local/7"
    record = after.records[result["link_id"]]
    assert record.schema_version == "research-local/7"
    assert record.kind == "manuscript_claim_link"
    assert record.claim_ref == Reference(id=claim, revision=1)
    assert record.anchor.source_path == "draft.md"
    assert record.anchor.source_sha256 == digest(manuscript.read_bytes())
    assert record.anchor.quote == "🦉 A visitor arrived."
    assert record.anchor.offset_unit == "unicode_codepoint" and record.anchor.retention_confirmed
    assert record.anchor.selector_version == "paragraph-profile-text/1"
    assert "The reading room was open." not in encode(record).decode()
    assert not (project / "research" / "blobs").exists()
    for entry in before.manifest.entries:
        assert repository.record_path(entry).read_bytes() == records[entry.ref]
    assert api.audit(project)["ok"]


def test_shared_paragraph_identity_matches_rendered_profile_text(manuscript_archive):
    from lixity.pipeline import paragraph_identity

    _, manuscript, _, _ = manuscript_archive
    text = manuscript.read_text(encoding="utf-8")
    config, _ = resolve_document_config(text)
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    assert paragraph_identity(paragraphs[0]) == {key: selection()[key]
                                                for key in ("start_line", "end_line", "paragraph_sha256")}


@pytest.mark.parametrize("manifest_version", range(1, 7))
def test_reads_and_review_do_not_upgrade_supported_archives(manuscript_archive, manifest_version):
    project, manuscript, _, _ = manuscript_archive
    repository = Repository(project)
    old = repository.snapshot()
    manifest = Manifest(schema_version=f"research-manifest-local/{manifest_version}",
                        project_id=old.project.id, generation=old.manifest.generation + 1,
                        parent=old.digest, entries=old.manifest.entries)
    content = encode(manifest)
    (repository.data / "manifests" / f"{digest(content)}.json").write_bytes(content)
    (repository.data / "HEAD.json").write_bytes(encode(Head(sha256=digest(content))))
    before = accepted_bytes(project)
    assert api.list_manuscript_links(project)["links"] == []
    assert api.review_manuscript_links(project, manuscript)["links"] == []
    assert accepted_bytes(project) == before


@pytest.mark.parametrize("changes", [
    {"allow_retention": False},
    {"allow_retention": 1},
    {"expected_project_id": f"urn:uuid:{uuid4()}"},
    {"expected_snapshot": "0" * 64},
    {"expected_source_sha256": "0" * 64},
    {"claim_revision": 2},
    {"selection": {**selection(), "paragraph_sha256": "0" * 64}},
    {"selection": {**selection(), "quote": "A fabricated selection."}},
    {"selection": {**selection(), "end_line": 4}},
    {"selection": {**selection(), "start": True}},
    {"selection": {**selection(), "start": selection()["start"] + 1, "end": selection()["end"] + 1}},
    {"selection": {**selection(), "offset_unit": "utf16"}},
])
def test_invalid_or_stale_save_never_retains_text_or_upgrades(manuscript_archive, changes):
    project, _, _, _ = manuscript_archive
    before = accepted_bytes(project)
    with pytest.raises(ResearchError):
        save_link(manuscript_archive, **changes)
    assert accepted_bytes(project) == before


def test_changed_claim_requires_current_review_before_initial_save(manuscript_archive):
    project, _, claim, _ = manuscript_archive
    revise(project, "claim", claim, {"statement": "The room may have been open."})
    before = accepted_bytes(project)
    with pytest.raises(ResearchConflictError, match="Claim revision changed"):
        save_link(manuscript_archive)
    assert accepted_bytes(project) == before


def test_save_rejects_utf16_offsets_after_non_bmp_character(manuscript_archive):
    selected = selection("A visitor arrived.")
    assert selected["start"] != len("The reading room was open. 🦉 ".encode("utf-16-le")) // 2
    shifted = {**selected, "start": selected["start"] + 1, "end": selected["end"] + 1}
    with pytest.raises(ResearchError):
        save_link(manuscript_archive, selection=shifted)
    saved = save_link(manuscript_archive, selection=selected)
    assert saved["record"]["anchor"]["quote"] == "A visitor arrived."


@pytest.mark.parametrize("escape", ["../outside.md", "/outside.md", "linked.md"])
def test_save_refuses_paths_outside_explicit_project(manuscript_archive, tmp_path, escape):
    project, _, claim, dossier = manuscript_archive
    outside = tmp_path / "outside.md"
    outside.write_text("## Chapter One\n\nThe **reading room** was open. 🦉 A visitor arrived.\n", encoding="utf-8")
    if escape == "/outside.md":
        target = outside
    elif escape == "linked.md":
        target = project / escape
        target.symlink_to(outside)
    else:
        target = project / escape
    before = accepted_bytes(project)
    with pytest.raises(ResearchError):
        save_link((project, target, claim, dossier))
    assert accepted_bytes(project) == before


def test_newer_claim_and_dossier_pins_do_not_retarget_saved_link(manuscript_archive):
    project, manuscript, claim, dossier = manuscript_archive
    result = save_link(manuscript_archive)
    revise(project, "dossier", dossier, {"title": "New notes"})
    revise(project, "claim", claim, {"statement": "The room was closed.", "dossier_revision": 2})
    listed = api.list_manuscript_links(project)["links"][0]
    assert listed["link_id"] == result["link_id"]
    assert listed["claim_revision"] == 1 and listed["claim_current_revision"] == 2
    assert listed["claim_changed"] and listed["review_needed"]
    assert listed["dossier_id"] == dossier and listed["dossier_revision"] == 1
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["claim_changed"] and reviewed["anchor_state"] == "resolved"
    assert reviewed["claim_revision"] == 1


def test_changed_source_and_paragraph_report_drift_without_silent_reanchor(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    result = save_link(manuscript_archive)
    before = accepted_bytes(project)
    manuscript.write_text("## Chapter One\n\nThe reading room was closed. A visitor left.\n", encoding="utf-8")
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["source_changed", "anchor_changed"]
    assert reviewed["anchor_state"] == "changed" and reviewed["review_needed"]
    assert api.get_record(project, "manuscript_claim_link", result["link_id"])["record"]["anchor"]["start_line"] == 3
    assert accepted_bytes(project) == before


def test_moved_duplicate_paragraph_is_ambiguous_and_never_highlighted(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    before = accepted_bytes(project)
    paragraph = "The **reading room** was open. 🦉 A visitor arrived."
    manuscript.write_text(f"## Chapter One\n\nA new introduction.\n\n{paragraph}\n\n{paragraph}\n", encoding="utf-8")
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["source_changed", "anchor_ambiguous"]
    assert reviewed["anchor_state"] == "ambiguous"
    assert reviewed["resolved_start_line"] is None
    assert reviewed["candidate_lines"] == [5, 7]
    assert accepted_bytes(project) == before


def test_uniquely_moved_paragraph_is_only_a_review_candidate(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    manuscript.write_text("## Chapter One\n\nAn introduction.\n\nThe **reading room** was open. 🦉 A visitor arrived.\n", encoding="utf-8")
    before = accepted_bytes(project)
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["source_changed", "anchor_moved"]
    assert reviewed["anchor_state"] == "moved" and reviewed["candidate_lines"] == [5]
    assert reviewed["resolved_start_line"] == 5 and reviewed["resolved_end_line"] == 5
    assert reviewed["resolved_start"] == selection()["start"]
    assert reviewed["resolved_end"] == selection()["end"]
    assert reviewed["anchor"]["start_line"] == 3
    assert accepted_bytes(project) == before


def test_missing_source_and_withdrawn_claim_are_explicit_review_states(manuscript_archive):
    project, manuscript, claim, _ = manuscript_archive
    save_link(manuscript_archive)
    repository = Repository(project)
    snapshot = repository.snapshot()
    repository.commit([Tombstone(**api.envelope(snapshot.project.id, "synthetic-author"),
                                target_ref=Reference(id=claim), target_kind="claim", operation="withdraw",
                                reason="Synthetic author withdrew claim")], {}, snapshot)
    manuscript.unlink()
    before = accepted_bytes(project)
    reviewed = api.review_manuscript_links(project, manuscript)
    assert reviewed["source_state"] == "missing" and reviewed["current_source_sha256"] is None
    assert reviewed["links"][0]["flags"] == ["claim_withdrawn", "source_missing"]
    assert reviewed["links"][0]["anchor_state"] == "unavailable"
    assert accepted_bytes(project) == before


def test_invalid_utf8_source_is_unreadable_not_missing(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    manuscript.write_bytes(b"\xff\xfe")
    reviewed = api.review_manuscript_links(project, manuscript)
    assert reviewed["source_state"] == "unreadable"
    assert reviewed["links"][0]["flags"] == ["source_unreadable"]


def test_retraction_and_pin_revision_reuse_history_and_disallow_generic_anchor_changes(manuscript_archive):
    project, _, claim, _ = manuscript_archive
    result = save_link(manuscript_archive)
    identifier = result["link_id"]
    original = api.get_record(project, "manuscript_claim_link", identifier)["record"]
    revise(project, "claim", claim, {"statement": "A revised author assertion."})
    preview = api.prepare_record_revision(project, "manuscript_claim_link", identifier, base_revision=1,
                                           changes={"claim_id": claim, "note": "The previous version remains relevant."})
    assert preview["ready"] and preview["changes"] == {"note": "The previous version remains relevant."}
    changed = revise(project, "manuscript_claim_link", identifier, {"state": "retracted", "claim_revision": 2})
    assert changed["record"]["revision"] == 2 and changed["record"]["schema_version"] == "research-local/7"
    assert changed["record"]["anchor"] == original["anchor"]
    assert changed["record"]["claim_ref"] == {"id": claim, "revision": 2}
    assert api.list_manuscript_links(project)["links"] == []
    assert api.list_manuscript_links(project, include_retracted=True)["links"][0]["state"] == "retracted"
    assert api.get_record(project, "manuscript_claim_link", identifier, revision=1)["record"] == original
    assert [row["revision"] for row in api.record_history(project, "manuscript_claim_link", identifier)["revisions"]] == [2, 1]
    before = accepted_bytes(project)
    with pytest.raises(ResearchError, match="unknown or immutable"):
        revise(project, "manuscript_claim_link", identifier, {"anchor": {**original["anchor"], "quote": "Changed quote"}})
    assert accepted_bytes(project) == before


def test_archive_round_trip_keeps_link_quote_and_history_without_manuscript(manuscript_archive, tmp_path):
    project, _, _, _ = manuscript_archive
    result = save_link(manuscript_archive)
    revise(project, "manuscript_claim_link", result["link_id"], {"note": "Reviewed synthetic quote."})
    archive = tmp_path / "links.tar.gz"
    api.export_archive(project, archive)
    restored = tmp_path / "restored"
    api.restore_archive(archive, restored)
    assert api.list_manuscript_links(restored)["links"] == api.list_manuscript_links(project)["links"]
    assert not (restored / "draft.md").exists()
    assert api.audit(restored)["ok"]
    assert api.review_manuscript_links(restored, restored / "draft.md")["source_state"] == "missing"


def test_explicit_project_settings_control_supported_manuscript_paragraphs(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    manuscript.write_text("## Anmerkungen und Literaturverzeichnis\n\nThe **reading room** was open. 🦉 A visitor arrived.\n", encoding="utf-8")
    before = accepted_bytes(project)
    with pytest.raises(ResearchError):
        save_link(manuscript_archive)
    assert accepted_bytes(project) == before
    (project / "lixity.toml").write_text('appendix_marker = "## Other appendix"\n', encoding="utf-8")
    saved = save_link(manuscript_archive)
    assert api.review_manuscript_links(project, manuscript)["links"][0]["anchor_state"] == "resolved"
    assert saved["record"]["anchor"]["quote"] == selection()["quote"]


def test_review_can_reuse_current_pipeline_paragraphs(manuscript_archive):
    from lixity.research.manuscript import manuscript_review_data

    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    text = manuscript.read_text(encoding="utf-8")
    config, _ = resolve_document_config(text)
    paragraphs, _ = profile_document(text, config, FingerprintThresholds())
    report = manuscript_review_data(Repository(project).snapshot(), source_path="draft.md",
                                    source_sha256=digest(manuscript.read_bytes()), paragraphs=paragraphs)
    assert report["links"][0]["anchor_state"] == "resolved"
    assert report["review_needed_count"] == 0


def test_crlf_source_hash_preserves_raw_bytes_and_normalized_profile(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    manuscript.write_bytes(manuscript.read_bytes().replace(b"\n", b"\r\n"))
    original = manuscript.read_bytes()
    saved = save_link(manuscript_archive)
    assert saved["record"]["anchor"]["source_sha256"] == digest(original)
    assert manuscript.read_bytes() == original
    assert api.review_manuscript_links(project, manuscript)["links"][0]["flags"] == []


def test_ancestor_settings_never_participate_in_anchor_resolution(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    (project.parent / "lixity.toml").write_text('appendix_marker = "## Chapter One"\n', encoding="utf-8")
    save_link(manuscript_archive)
    assert api.review_manuscript_links(project, manuscript)["links"][0]["anchor_state"] == "resolved"


def test_path_changed_to_escaping_symlink_before_publication_is_rejected(manuscript_archive, monkeypatch):
    from lixity.io import FileUtils

    project, manuscript, _, _ = manuscript_archive
    outside = project.parent / "outside.md"
    outside.write_bytes(manuscript.read_bytes())
    before = accepted_bytes(project)
    read = FileUtils.read_source_snapshot
    reads = []

    def change_path_after_read(filepath, encoding="utf-8"):
        reads.append(filepath)
        result = read(filepath, encoding)
        if len(reads) == 1:
            manuscript.unlink()
            manuscript.symlink_to(outside)
        return result

    monkeypatch.setattr(FileUtils, "read_source_snapshot", change_path_after_read)
    with pytest.raises(ResearchError, match="escapes"):
        save_link(manuscript_archive)
    assert len(reads) == 1
    assert accepted_bytes(project) == before


def test_archive_anchor_retention_flag_is_strict_boolean(manuscript_archive):
    from pydantic import ValidationError

    from lixity.research.models import ManuscriptAnchor

    saved = save_link(manuscript_archive)["record"]["anchor"]
    with pytest.raises(ValidationError):
        ManuscriptAnchor.model_validate({**saved, "retention_confirmed": 1})


def test_unrelated_source_edit_stays_informational(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    assert api.review_manuscript_links(project, manuscript)["review_needed_count"] == 0
    manuscript.write_bytes(manuscript.read_bytes() + b"\n## Chapter Two\n\nA later scene arrives.\n")
    report = api.review_manuscript_links(project, manuscript)
    row = report["links"][0]
    assert row["anchor_state"] == "resolved"
    assert "source_changed" in row["flags"]
    assert row["review_needed"] is False
    assert report["review_needed_count"] == 0


def test_cli_link_list_and_review_round_trip(manuscript_archive, capsys):
    project, _, claim, _ = manuscript_archive
    parser = research_parser()
    link_args = parser.parse_args([
        "link-manuscript", "--project", str(project), "--manuscript", "draft.md",
        "--claim-id", claim, "--claim-revision", "1",
        "--selection", json.dumps(selection()), "--allow-retention"])
    assert cli.run(link_args) == 0
    linked = json.loads(capsys.readouterr().out)
    assert linked["claim_id"] == claim
    assert linked["record"]["kind"] == "manuscript_claim_link"
    list_args = parser.parse_args(["manuscript-links", "--project", str(project)])
    assert cli.run(list_args) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row["link_id"] for row in listed["links"]] == [linked["link_id"]]
    review_args = parser.parse_args([
        "review-manuscript", "--project", str(project), "--manuscript", "draft.md"])
    assert cli.run(review_args) == 0
    reviewed = json.loads(capsys.readouterr().out)
    assert reviewed["links"][0]["anchor_state"] == "resolved"
    assert reviewed["review_needed_count"] == 0


def test_reanchor_accepts_unique_moved_anchor_and_keeps_history(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    linked = save_link(manuscript_archive)
    manuscript.write_bytes(
        "## Chapter One\n\nA new note.\n\nThe **reading room** was open. \U0001F989 A visitor arrived.\n".encode("utf-8"))
    report = api.review_manuscript_links(project, manuscript)
    row = report["links"][0]
    assert row["anchor_state"] == "moved" and row["candidate_lines"] == [5]
    snapshot = Repository(project).snapshot()
    result = api.reanchor_manuscript_link(
        project, manuscript, linked["link_id"], expected_project_id=snapshot.project.id,
        expected_snapshot=snapshot.digest, expected_revision=1,
        expected_source_sha256=digest(manuscript.read_bytes()))
    assert result["record"]["revision"] == 2
    assert result["record"]["anchor"]["start_line"] == 5
    assert result["record"]["anchor"]["source_sha256"] == digest(manuscript.read_bytes())
    reviewed = api.review_manuscript_links(project, manuscript)
    assert reviewed["links"][0]["anchor_state"] == "resolved"
    assert reviewed["review_needed_count"] == 0
    history = api.record_history(project, "manuscript_claim_link", linked["link_id"])
    assert [entry["revision"] for entry in history["revisions"]] == [2, 1]
    pinned = api.get_record(project, "manuscript_claim_link", linked["link_id"], revision=1)
    assert pinned["record"]["anchor"]["start_line"] == 3


def test_reanchor_refuses_ambiguous_or_unchanged_anchors(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    linked = save_link(manuscript_archive)
    snapshot = Repository(project).snapshot()
    with pytest.raises(ResearchError, match="still resolves"):
        api.reanchor_manuscript_link(
            project, manuscript, linked["link_id"], expected_project_id=snapshot.project.id,
            expected_snapshot=snapshot.digest, expected_revision=1,
            expected_source_sha256=digest(manuscript.read_bytes()))
    manuscript.write_bytes(
        "## Chapter One\n\nA new note.\n\nThe **reading room** was open. \U0001F989 A visitor arrived.\n\n"
        "The **reading room** was open. \U0001F989 A visitor arrived.\n".encode("utf-8"))
    report = api.review_manuscript_links(project, manuscript)
    assert report["links"][0]["anchor_state"] == "ambiguous"
    snapshot = Repository(project).snapshot()
    with pytest.raises(ResearchError, match="uniquely resolvable"):
        api.reanchor_manuscript_link(
            project, manuscript, linked["link_id"], expected_project_id=snapshot.project.id,
            expected_snapshot=snapshot.digest, expected_revision=1,
            expected_source_sha256=digest(manuscript.read_bytes()))


def test_resolve_manuscript_anchor_reports_exact_fields(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    resolved = api.resolve_manuscript_anchor(project, "draft.md", query="\U0001F989 A visitor arrived.")
    expected = selection()
    assert {key: resolved[key] for key in expected} == expected
    with pytest.raises(ResearchError, match="Markdown"):
        api.resolve_manuscript_anchor(project, "draft.md", query="**reading room**")
    manuscript.write_bytes(manuscript.read_bytes() + b"\nA second room. Another visitor arrives.\n")
    with pytest.raises(ResearchError, match="ambiguous"):
        api.resolve_manuscript_anchor(project, "draft.md", query="room")
    narrowed = api.resolve_manuscript_anchor(project, "draft.md", query="room", line=3)
    assert narrowed["start_line"] == 3


@pytest.mark.parametrize("text, quote", [("banana", "ana"), ("aaa", "aa"), ("Owl 🦉🦉🦉", "🦉🦉")])
def test_resolve_manuscript_anchor_rejects_overlapping_occurrences(manuscript_archive, text, quote):
    project, manuscript, _, _ = manuscript_archive
    manuscript.write_text(f"## Fruit\n\n{text}\n", encoding="utf-8")
    for line in (None, 3):
        with pytest.raises(ResearchError, match="ambiguous"):
            api.resolve_manuscript_anchor(project, manuscript, query=quote, line=line)


def test_anchor_resolution_does_not_measure_linguistic_features(manuscript_archive, monkeypatch):
    from lixity.paragraph_evidence import ParagraphMatcher

    def unexpected_measurement(*args, **kwargs):
        raise AssertionError("Literal anchor lookup must not measure paragraph style")

    monkeypatch.setattr(ParagraphMatcher, "count", unexpected_measurement)
    project, manuscript, _, _ = manuscript_archive
    result = api.resolve_manuscript_anchor(project, manuscript, query="🦉 A visitor arrived.")
    assert {key: result[key] for key in selection()} == selection()


def test_paragraph_edit_outside_the_quote_stays_resolvable(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    linked = save_link(manuscript_archive)
    before = accepted_bytes(project)
    # The quoted evidence stays verbatim; only surrounding text changes.
    manuscript.write_text(
        "## Chapter One\n\nThe **reading room** was open until midnight. 🦉 A visitor arrived.\n",
        encoding="utf-8")
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["source_changed", "anchor_adjusted"]
    assert reviewed["anchor_state"] == "adjusted" and reviewed["review_needed"]
    assert reviewed["candidate_lines"] == [3]
    assert reviewed["resolved_start_line"] == 3 and reviewed["resolved_end_line"] == 3
    assert accepted_bytes(project) == before

    snapshot = Repository(project).snapshot()
    result = api.reanchor_manuscript_link(
        project, manuscript, linked["link_id"], expected_project_id=snapshot.project.id,
        expected_snapshot=snapshot.digest, expected_revision=1,
        expected_source_sha256=digest(manuscript.read_bytes()))
    anchor = result["record"]["anchor"]
    adjusted = "The reading room was open until midnight. 🦉 A visitor arrived."
    assert anchor["quote"] == "🦉 A visitor arrived."
    assert anchor["start_line"] == 3 and anchor["end_line"] == 3
    assert anchor["paragraph_sha256"] == hashlib.sha256(adjusted.encode()).hexdigest()
    assert anchor["start"] == adjusted.index("🦉 A visitor arrived.")
    assert anchor["end"] == anchor["start"] + len("🦉 A visitor arrived.")
    assert result["record"]["change"]["reason"].startswith("Re-anchor to the adjusted")
    resolved = api.review_manuscript_links(project, manuscript)
    assert resolved["links"][0]["anchor_state"] == "resolved"
    assert resolved["review_needed_count"] == 0


def test_edited_quote_still_requires_review(manuscript_archive):
    project, manuscript, _, _ = manuscript_archive
    save_link(manuscript_archive)
    before = accepted_bytes(project)
    # The quoted wording itself changed: the retained evidence no longer exists.
    manuscript.write_text(
        "## Chapter One\n\nThe **reading room** was open. 🦉 A visitor came by.\n",
        encoding="utf-8")
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["flags"] == ["source_changed", "anchor_changed"]
    assert reviewed["anchor_state"] == "changed" and reviewed["review_needed"]
    snapshot = Repository(project).snapshot()
    with pytest.raises(ResearchError, match="uniquely resolvable"):
        api.reanchor_manuscript_link(
            project, manuscript, api.list_manuscript_links(project)["links"][0]["link_id"],
            expected_project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
            expected_revision=1, expected_source_sha256=digest(manuscript.read_bytes()))
    assert accepted_bytes(project) == before


@pytest.mark.parametrize("anchor_state,content,line", [
    ("adjusted", "## Chapter One\n\nThe **reading room** was open until midnight. 🦉 A visitor arrived.\n", 3),
    ("moved", "## Chapter One\n\nA new note.\n\nThe **reading room** was open. 🦉 A visitor arrived.\n", 5),
], ids=["adjusted", "moved"])
def test_cli_reconcile_previews_then_accepts_unique_anchor(manuscript_archive, capsys, anchor_state, content, line):
    project, manuscript, _, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    manuscript.write_bytes(content.encode("utf-8"))
    before = accepted_bytes(project)
    parser = research_parser()
    argv = ["reconcile-manuscript", "--project", str(project), "--manuscript", "draft.md"]
    assert cli.run(parser.parse_args(argv)) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["dry_run"] is True
    assert len(planned["candidates"]) == 1
    assert planned["candidates"][0]["link_id"] == saved["link_id"]
    assert planned["candidates"][0]["anchor_state"] == anchor_state
    assert planned["candidates"][0]["candidate_lines"] == [line]
    assert accepted_bytes(project) == before
    assert cli.run(parser.parse_args([*argv, "--accept-moved"])) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["dry_run"] is False and done["skipped"] == []
    assert done["accepted"] == [{"link_id": saved["link_id"], "revision": 2}]
    reviewed = api.review_manuscript_links(project, manuscript)
    assert reviewed["review_needed_count"] == 0
    assert reviewed["links"][0]["anchor_state"] == "resolved"
    assert reviewed["links"][0]["anchor"]["start_line"] == line


def test_cli_reconcile_previews_and_repins_changed_quote_explicitly(manuscript_archive, capsys):
    project, manuscript, _, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    link_id = saved["link_id"]
    manuscript.write_text(
        "## Chapter One\n\nThe **study room** was open until midnight. 🦉\n",
        encoding="utf-8",
    )
    assert api.review_manuscript_links(project, manuscript)["links"][0]["anchor_state"] == "changed"
    parser = research_parser()
    preview = parser.parse_args([
        "reconcile-manuscript", "--project", str(project), "draft.md",
        "--link-id", link_id, "--new-quote", "The study room was open",
    ])
    assert cli.run(preview) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["dry_run"] is True
    assert planned["candidates"][0]["old_quote"] == "🦉 A visitor arrived."
    assert planned["candidates"][0]["new_quote"] == "The study room was open"
    assert planned["candidates"][0]["candidate_lines"] == [3]

    apply = parser.parse_args([
        "reconcile-manuscript", "--project", str(project), "draft.md",
        "--link-id", link_id, "--new-quote", "The study room was open",
        "--reason", "Glättung des Satzes", "--accept-moved",
    ])
    assert cli.run(apply) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["record"]["revision"] == 2
    assert done["record"]["anchor"]["quote"] == "The study room was open"
    assert done["record"]["change"]["reason"] == "Glättung des Satzes"
    review = api.review_manuscript_links(project, manuscript)
    assert review["review_needed_count"] == 0
    assert review["links"][0]["anchor_state"] == "resolved"
    history = api.record_history(project, "manuscript_claim_link", link_id)
    assert len(history["revisions"]) == 2


def test_cli_review_allows_configured_default_but_rejects_two_explicit_paths():
    parser = research_parser()
    args = parser.parse_args(["review-manuscript", "--project", "/synthetic"])
    assert getattr(args, "manuscript", None) is None
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["review-manuscript", "--project", "/synthetic", "draft.md", "--manuscript", "draft.md"])
    assert error.value.code == 2


def test_cli_find_anchor_and_quote_convenience(manuscript_archive, capsys):
    project, _, claim, _ = manuscript_archive
    parser = research_parser()
    find_args = parser.parse_args(["find-anchor", "--project", str(project),
                                   "--manuscript", "draft.md", "--query", "\U0001F989 A visitor arrived."])
    assert cli.run(find_args) == 0
    anchored = json.loads(capsys.readouterr().out)
    assert {key: anchored[key] for key in selection()} == selection()
    link_args = parser.parse_args([
        "link-manuscript", "--project", str(project), "--manuscript", "draft.md",
        "--claim-id", claim, "--claim-revision", "1", "--quote", "\U0001F989 A visitor arrived.",
        "--allow-retention"])
    assert cli.run(link_args) == 0
    linked = json.loads(capsys.readouterr().out)
    assert linked["record"]["anchor"]["start_line"] == 3


@pytest.mark.parametrize("source_missing", [False, True], ids=["existing-source", "missing-source"])
def test_unlink_manuscript_retracts_link_and_preserves_history(manuscript_archive, capsys, source_missing):
    project, manuscript, _, _ = manuscript_archive
    link = save_link(manuscript_archive)
    link_id = link["link_id"]
    if source_missing:
        manuscript.unlink()
    parser = research_parser()
    args = parser.parse_args(["unlink-manuscript", "--project", str(project),
                              "--manuscript", "draft.md", "--link-id", link_id])
    assert cli.run(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["link_id"] == link_id
    # Link should no longer appear in default list.
    listing = api.list_manuscript_links(project)
    assert listing["links"] == []
    # But should appear with include_retracted.
    listing2 = api.list_manuscript_links(project, include_retracted=True)
    assert len(listing2["links"]) == 1
    assert listing2["links"][0]["state"] == "retracted"
    assert result["record"]["revision"] == 2
    original = api.get_record(project, "manuscript_claim_link", link_id, revision=1)
    assert original["record"] == link["record"]


@pytest.mark.parametrize("moved,selected,accept_moved", [
    (False, False, False), (False, False, True), (False, True, False), (False, True, True),
    (True, False, True), (True, True, True),
])
def test_cli_accepts_claim_updates_once(manuscript_archive, capsys, moved, selected, accept_moved):
    project, manuscript, claim, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    revise(project, "claim", claim, {"statement": "The room was closed."})
    if moved:
        manuscript.write_text("Extra paragraph.\n\n" + manuscript.read_text(encoding="utf-8"), encoding="utf-8")
    parser = research_parser()
    argv = ["reconcile-manuscript", "--project", str(project), "draft.md", "--accept-claim-updates"]
    if accept_moved:
        argv.append("--accept-moved")
    if selected:
        argv.extend(["--link-id", saved["link_id"]])
    assert cli.run(parser.parse_args(argv)) == 0
    result = json.loads(capsys.readouterr().out)
    assert result.get("dry_run") is not True
    if not selected:
        assert result["accepted"] == [{"link_id": saved["link_id"], "revision": 2}]
        assert result["skipped"] == []
    reviewed = api.review_manuscript_links(project, manuscript)["links"][0]
    assert reviewed["claim_revision"] == 2
    assert reviewed["revision"] == 2  # Moving and accepting the claim share one revision.
    assert reviewed["review_needed"] is False
    snapshot = Repository(project).snapshot()
    assert snapshot.revisions[(saved["link_id"], 1)].claim_ref.revision == 1
    if not moved:
        assert snapshot.records[saved["link_id"]].change.reason == "Accept current claim revision"


@pytest.mark.parametrize("output_format", ["text", "table"])
@pytest.mark.parametrize("command", ["find-anchor", "link-manuscript", "manuscript-links",
                                     "review-manuscript", "reconcile-manuscript", "unlink-manuscript"])
def test_manuscript_commands_render_requested_format(manuscript_archive, capsys, command, output_format):
    project, _, claim, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    argv = [command, "--project", str(project), "--format", output_format]
    if command != "manuscript-links":
        argv.append("draft.md")
    if command == "find-anchor":
        argv.extend(["--query", "A visitor arrived."])
    elif command == "link-manuscript":
        argv.extend(["--claim-id", claim, "--claim-revision", "1", "--quote", "reading room",
                     "--allow-retention"])
    elif command == "unlink-manuscript":
        argv.extend(["--link-id", saved["link_id"]])
    parser = research_parser()
    assert cli.run(parser.parse_args(argv)) == 0
    output = capsys.readouterr().out
    assert output.strip() and not output.lstrip().startswith("{")
    if command == "find-anchor":
        assert "A visitor arrived." in output and "3" in output
    elif command in ("manuscript-links", "review-manuscript"):
        assert "Room" in output and "3" in output
    elif command == "unlink-manuscript":
        assert "retracted" in output
    elif command == "link-manuscript":
        assert "reading room" in output
    else:
        assert "preview" in output.lower()




def test_record_grammar_rejects_unknown_action(manuscript_archive, capsys):
    project, _, _, dossier = manuscript_archive
    parser = research_parser()
    assert cli.run(parser.parse_args(["dossier", "typo", dossier, "--project", str(project)])) != 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("selectors", [("show",), ("list", "unused-id")])
def test_sources_grammar_rejects_missing_or_extra_id(manuscript_archive, capsys, selectors):
    project, _, _, _ = manuscript_archive
    parser = research_parser()
    assert cli.run(parser.parse_args(["sources", *selectors, "--project", str(project)])) != 0
    assert capsys.readouterr().out == ""


def test_reconcile_quote_preview_text_shows_replacement(manuscript_archive, capsys):
    project, _, _, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    parser = research_parser()
    args = parser.parse_args(["reconcile-manuscript", "--project", str(project), "draft.md",
                              "--link-id", saved["link_id"], "--new-quote", "reading room", "--format", "text"])
    assert cli.run(args) == 0
    output = capsys.readouterr().out
    assert "preview" in output.lower()
    assert "🦉 A visitor arrived." in output and "reading room" in output
    assert "ManuscriptState" not in output




@pytest.mark.parametrize("failure_point", [
    "source_read", "head_publication", "head_read", "nested_head_read", "lock_io", "lock_busy", "unsafe_lock",
])
def test_reconcile_system_failures_exit_nonzero(manuscript_archive, monkeypatch, capsys, failure_point):
    from lixity.io import FileUtils
    from lixity.research import repository as storage

    project, manuscript, _, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    manuscript.write_text("Extra paragraph.\n\n" + manuscript.read_text(encoding="utf-8"), encoding="utf-8")
    before = Repository(project).snapshot().digest
    if failure_point == "source_read":
        read = FileUtils.read_source_snapshot
        reads = 0

        def unavailable_source(path):
            nonlocal reads
            reads += 1
            if reads == 3:  # The source becomes unreadable after the command's initial review.
                raise PermissionError(13, "Permission denied", str(manuscript))
            return read(path)

        monkeypatch.setattr(FileUtils, "read_source_snapshot", unavailable_source)
    elif failure_point == "head_publication":
        publish = storage.publish

        def readonly_head(path, content, **kwargs):
            if path.name == "HEAD.json":
                raise OSError(30, "Read-only file system", str(path))
            return publish(path, content, **kwargs)

        monkeypatch.setattr(storage, "publish", readonly_head)
    elif failure_point in ("head_read", "nested_head_read"):
        read = Repository.read
        review = api.review_manuscript_links
        remaining_reads = None

        def reviewed(*args, **kwargs):
            nonlocal remaining_reads
            result = review(*args, **kwargs)
            remaining_reads = 1 if failure_point == "head_read" else 2
            return result

        def unavailable_head(self, path, **kwargs):
            nonlocal remaining_reads
            if path.name == "HEAD.json" and remaining_reads:
                remaining_reads -= 1
                if remaining_reads == 0:
                    raise FileNotFoundError(2, "Synthetic HEAD unavailable", str(path))
            return read(self, path, **kwargs)

        monkeypatch.setattr(api, "review_manuscript_links", reviewed)
        monkeypatch.setattr(Repository, "read", unavailable_head)
    elif failure_point == "unsafe_lock":
        lock = Repository(project).cache / "writer.lock"
        lock.unlink(missing_ok=True)
        try:
            lock.symlink_to(project / "synthetic-lock-target")
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks unavailable")
    else:
        import errno
        import sys

        def failed_lock(*args):
            code = errno.EIO if failure_point == "lock_io" else errno.EAGAIN
            raise OSError(code, "Synthetic lock failure")

        if sys.platform == "win32":
            import msvcrt
            monkeypatch.setattr(msvcrt, "locking", failed_lock)
        else:
            import fcntl
            monkeypatch.setattr(fcntl, "flock", failed_lock)
    parser = research_parser()
    args = parser.parse_args(["reconcile-manuscript", "--project", str(project), "draft.md", "--accept-moved"])
    assert cli.run(args) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert any(detail in output.err for detail in (
        "Permission denied", "Read-only file system", "Synthetic HEAD unavailable", "Synthetic lock failure",
        "Symlinks are not allowed",
    ))
    after = Repository(project).snapshot()
    assert after.digest == before
    assert after.records[saved["link_id"]].revision == 1


@pytest.mark.parametrize("operation", ["reanchor", "claim_revision", "retract"])
def test_manuscript_revision_records_current_actor_and_timestamp(manuscript_archive, operation):
    project, manuscript, claim, _ = manuscript_archive
    saved = save_link(manuscript_archive)
    if operation == "reanchor":
        manuscript.write_text("Extra paragraph.\n\n" + manuscript.read_text(encoding="utf-8"), encoding="utf-8")
    elif operation == "claim_revision":
        revise(project, "claim", claim, {"statement": "The room was closed."})
    snapshot = Repository(project).snapshot()
    values = {"expected_project_id": snapshot.project.id, "expected_snapshot": snapshot.digest,
              "expected_revision": 1, "actor": "synthetic-reviewer"}
    before = datetime.now(timezone.utc)
    if operation == "retract":
        result = api.retract_manuscript_link(project, manuscript, saved["link_id"], **values)
    elif operation == "claim_revision":
        result = api.reanchor_manuscript_claim_revision(
            project, manuscript, saved["link_id"], **values,
            expected_source_sha256=digest(manuscript.read_bytes()), new_claim_revision=2)
    else:
        result = api.reanchor_manuscript_link(
            project, manuscript, saved["link_id"], **values,
            expected_source_sha256=digest(manuscript.read_bytes()))
    after = datetime.now(timezone.utc)
    record = result["record"]
    assert record["created_by"] == "synthetic-reviewer"
    timestamp = datetime.strptime(record["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
    assert before <= timestamp <= after
    original = api.get_record(project, "manuscript_claim_link", saved["link_id"], revision=1)["record"]
    assert original == saved["record"]
    assert original["created_by"] == "local-author" and original["created_at"] != record["created_at"]


@pytest.mark.parametrize("strict", [False, True])
def test_reconcile_explicit_snapshot_rejects_late_external_edit(manuscript_archive, monkeypatch, capsys, strict):
    project, manuscript, _, dossier = manuscript_archive
    saved = save_link(manuscript_archive)
    manuscript.write_text("Extra paragraph.\n\n" + manuscript.read_text(encoding="utf-8"), encoding="utf-8")
    expected = Repository(project).snapshot().digest
    review = api.review_manuscript_links

    def concurrent_edit(*args, **kwargs):
        reviewed = review(*args, **kwargs)
        revise(project, "dossier", dossier, {"title": "Concurrent unrelated change"})
        return reviewed

    monkeypatch.setattr(api, "review_manuscript_links", concurrent_edit)
    parser = research_parser()
    argv = ["reconcile-manuscript", "--project", str(project), "draft.md", "--accept-moved"]
    if strict:
        argv.extend(["--expected-snapshot", expected])
    assert cli.run(parser.parse_args(argv)) == (1 if strict else 0)
    output = capsys.readouterr()
    if strict:
        assert output.out == "" and "snapshot" in output.err.lower()
    snapshot = Repository(project).snapshot()
    assert snapshot.records[saved["link_id"]].revision == (1 if strict else 2)
    assert snapshot.records[dossier].revision == 2


def test_reconcile_strict_snapshot_allows_own_prior_commits(manuscript_archive, capsys):
    project, manuscript, _, _ = manuscript_archive
    first = save_link(manuscript_archive)
    second = save_link(manuscript_archive, selection=selection("reading room"))
    manuscript.write_text("Extra paragraph.\n\n" + manuscript.read_text(encoding="utf-8"), encoding="utf-8")
    expected = Repository(project).snapshot().digest
    parser = research_parser()
    args = parser.parse_args(["reconcile-manuscript", "--project", str(project), "draft.md",
                              "--accept-moved", "--expected-snapshot", expected])
    assert cli.run(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["skipped"] == []
    assert {row["link_id"] for row in result["accepted"]} == {first["link_id"], second["link_id"]}
    assert [row["revision"] for row in result["accepted"]] == [2, 2]
