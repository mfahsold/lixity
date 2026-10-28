"""Explicit dossier drafts preserve text without becoming a second archive."""

import json
import os

import pytest

from lixity.research import api
from lixity.research.models import Dossier
from lixity.research.repository import Repository, ResearchError


@pytest.fixture
def project(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic notes", language="en")
    return project


@pytest.mark.parametrize("body", [
    "# Notes\n\nCafé, 港 and spaces.  \n", "A\r\n\r\nB\r\n", "A\rB\r", "No final newline",
    "\n\nLeading and trailing\n\n", "---\ntitle: Body frontmatter\n---\nText.",
    '<!-- lixity-dossier-edit/99\n{}\n-->\nOrdinary body. ![Map](research:image:example)',
])
def test_edit_document_preserves_exact_body_and_identity(project, body):
    from lixity.research.dossier_edit import decode_dossier_edit, encode_dossier_edit

    identifier = api.create_dossier(project, "Notes --> <safe>", body, tags=["draft"])["dossier_id"]
    record = Repository(project).snapshot().latest(identifier, Dossier)
    text = encode_dossier_edit(record)
    header, suffix = text.split("\n-->\n", 1)
    assert suffix.encode("utf-8") == body.encode("utf-8")
    assert "Notes --> <safe>" not in header
    decoded = decode_dossier_edit(text)
    assert decoded == {
        "project_id": record.project_id, "kind": "dossier", "record_id": identifier,
        "base_revision": 1, "fields": {"title": "Notes --> <safe>", "language": "en",
            "tags": ["draft"], "geography": None, "evidence_ids": []}, "body": body,
    }


def _document(header, body="Synthetic note."):
    return "<!-- lixity-dossier-edit/1\n" + json.dumps(header) + "\n-->\n" + body


def _header():
    return {"project_id": "urn:uuid:00000000-0000-4000-8000-000000000001", "kind": "dossier",
            "record_id": "urn:uuid:00000000-0000-4000-8000-000000000002", "base_revision": 1,
            "fields": {"title": "Notes", "language": "en", "tags": [], "geography": None, "evidence_ids": []}}


@pytest.mark.parametrize("opening,ending", [("\n", "\n"), ("\r\n", "\r\n"), ("\n", "\r\n"), ("\r\n", "\n")])
def test_control_header_accepts_lf_and_crlf_without_changing_body(opening, ending):
    from lixity.research.dossier_edit import decode_dossier_edit

    body = "First\r\nsecond\nthird\rlast"
    text = "<!-- lixity-dossier-edit/1" + opening + json.dumps(_header()) + ending + "-->" + ending + body
    assert decode_dossier_edit(text)["body"] == body


def test_read_dossier_edit_allows_crlf_control_envelope_at_size_limit(tmp_path, monkeypatch):
    from lixity.research import dossier_edit

    monkeypatch.setattr(dossier_edit, "MAX_RESEARCH_OBJECT_BYTES", 10)
    monkeypatch.setattr(dossier_edit, "_BODY_MAX_BYTES", 10)
    text = "<!-- lixity-dossier-edit/1\r\n" + "x" * 10 + "\r\n-->\r\n" + "y" * 10
    path = tmp_path / "draft.md"
    path.write_bytes(text.encode("utf-8"))
    assert dossier_edit.read_dossier_edit(path) == text


@pytest.mark.parametrize("change", [
    {"kind": "claim"}, {"base_revision": True}, {"base_revision": 0}, {"base_revision": 1.5},
    {"project_id": "../other"}, {"record_id": "00000000-0000-4000-8000-000000000002"},
    {"extra": "unknown"}, {"fields": {"title": "Notes", "unknown": "value"}},
])
def test_invalid_control_fields_fail_explicitly(change):
    from lixity.research.dossier_edit import decode_dossier_edit

    with pytest.raises(ResearchError):
        decode_dossier_edit(_document(_header() | change))


@pytest.mark.parametrize("text", [
    "Ordinary Markdown", "\ufeff<!-- lixity-dossier-edit/1\n{}\n-->\nBody",
    "<!-- lixity-dossier-edit/2\n{}\n-->\nBody", "<!-- lixity-dossier-edit/1\n{}",
    '<!-- lixity-dossier-edit/1\n{"kind":"dossier","kind":"claim"}\n-->\nBody',
    '<!-- lixity-dossier-edit/1\n{"fields":{"geography":NaN}}\n-->\nBody',
])
def test_malformed_control_header_is_not_treated_as_note_text(text):
    from lixity.research.dossier_edit import decode_dossier_edit

    with pytest.raises(ResearchError):
        decode_dossier_edit(text)


def test_codec_accepts_maximum_geography_feature_and_position_counts(project):
    from lixity.research.dossier_edit import decode_dossier_edit, encode_dossier_edit

    geography = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1.0, 2.0]] * 50},
        "properties": {"label": "L" * 500, "description": "D" * 4000,
                       "waypoint_labels": ["W" * 500] * 50},
    } for _ in range(200)]}
    identifier = api.create_dossier(project, "Route notes", "Synthetic.", geography=geography)["dossier_id"]
    record = Repository(project).snapshot().latest(identifier, Dossier)
    decoded = decode_dossier_edit(encode_dossier_edit(record))
    assert len(decoded["fields"]["geography"]["features"]) == 200
    assert sum(len(feature["geometry"]["coordinates"])
               for feature in decoded["fields"]["geography"]["features"]) == 10000
    assert decoded["fields"]["geography"]["features"][0]["properties"]["waypoint_labels"][0] == "W" * 500


def test_codec_enforces_header_and_body_budgets(monkeypatch):
    from lixity.research import dossier_edit

    monkeypatch.setattr(dossier_edit, "MAX_RESEARCH_OBJECT_BYTES", 64)
    with pytest.raises(ResearchError, match="header"):
        dossier_edit.decode_dossier_edit(_document(_header()))
    monkeypatch.setattr(dossier_edit, "MAX_RESEARCH_OBJECT_BYTES", 32 * 1024 * 1024)
    with pytest.raises(ResearchError, match="body"):
        dossier_edit.decode_dossier_edit(_document(_header(), "x" * (2 * 1024 * 1024 + 1)))


def test_numeric_overflow_in_edit_metadata_is_rejected():
    from lixity.research.dossier_edit import decode_dossier_edit

    text = _document(_header()).replace('"geography": null', '"geography": 1e999')
    with pytest.raises(ResearchError):
        decode_dossier_edit(text)


def test_explicit_edit_reconciles_from_header_base_without_writing(project):
    from lixity.research.dossier_edit import export_dossier_edit, prepare_dossier_edit
    from tests.research_support import retained_files, revise_record

    identifier = api.create_dossier(project, "Notes", "Base body.")["dossier_id"]
    document = export_dossier_edit(project, identifier)
    revise_record(project, "dossier", identifier, {"tags": ["concurrent"]})
    before = retained_files(project)
    unchanged = prepare_dossier_edit(project, identifier, document)
    assert unchanged["ready"] and not unchanged["has_changes"]
    edited = document.replace('"title":"Notes"', '"title":"Revised notes"').replace("Base body.", "Edited body.")
    preview = prepare_dossier_edit(project, identifier, edited)
    assert preview["ready"] and preview["current"]["record"]["revision"] == 2
    assert preview["changes"] == {"body": "Edited body.", "title": "Revised notes"}
    assert retained_files(project) == before


def test_edit_rejects_foreign_or_changed_identity_and_reports_conflicts(project, tmp_path):
    from lixity.research.dossier_edit import export_dossier_edit, prepare_dossier_edit
    from tests.research_support import retained_files, revise_record

    identifier = api.create_dossier(project, "Notes", "Base body.")["dossier_id"]
    document = export_dossier_edit(project, identifier)
    other = tmp_path / "other"
    api.init(other, title="Other", language="en")
    for selected, text in [(identifier, document.replace(Repository(project).snapshot().project.id,
                                                        Repository(other).snapshot().project.id)),
                           ("urn:uuid:00000000-0000-4000-8000-000000000099", document)]:
        with pytest.raises(ResearchError):
            prepare_dossier_edit(project, selected, text)
    revise_record(project, "dossier", identifier, {"body": "Concurrent body."})
    before = retained_files(project)
    preview = prepare_dossier_edit(project, identifier, document.replace("Base body.", "Edited body."))
    assert not preview["ready"]
    assert preview["conflicts"] == [{"field": "body", "base": "Base body.",
                                     "current": "Concurrent body.", "mine": "Edited body."}]
    assert retained_files(project) == before


def test_export_file_is_exact_exclusive_and_outside_the_authoritative_store(project, tmp_path):
    from lixity.research.dossier_edit import read_dossier_edit, write_dossier_edit
    from tests.research_support import retained_files

    identifier = api.create_dossier(project, "Notes", "CRLF\r\nNo final newline")["dossier_id"]
    before = retained_files(project)
    target = tmp_path / "draft.md"
    write_dossier_edit(project, identifier, target)
    assert target.read_bytes().endswith(b"CRLF\r\nNo final newline")
    assert read_dossier_edit(target).endswith("CRLF\r\nNo final newline")
    with pytest.raises(ResearchError, match="exist"):
        write_dossier_edit(project, identifier, target)
    for protected in (project / "research" / "note.md", project / ".lixity" / "note.md"):
        with pytest.raises(ResearchError):
            write_dossier_edit(project, identifier, protected)
        assert not protected.exists()
    assert retained_files(project) == before
    invalid = tmp_path / "invalid.md"
    invalid.write_bytes(b"\xff")
    with pytest.raises(ResearchError, match="UTF-8"):
        read_dossier_edit(invalid)
    with pytest.raises(ResearchError):
        read_dossier_edit(tmp_path / "missing.md")


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory-descriptor publication")
@pytest.mark.parametrize("race", ["resolution", "staging", "publication"])
def test_edit_export_parent_replacement_cannot_redirect_into_archive(project, tmp_path, monkeypatch, race):
    from lixity.research import dossier_edit
    from tests.research_support import retained_files

    parent = tmp_path / "drafts"
    parent.mkdir()
    moved = tmp_path / "original-drafts"
    before = retained_files(project)
    opened, link, resolve = os.open, os.link, dossier_edit.Path.resolve
    triggered = False

    def replace_parent():
        nonlocal triggered
        if not triggered:
            triggered = True
            parent.rename(moved)
            parent.symlink_to(project / "research", target_is_directory=True)

    def staging(path, *args, **kwargs):
        if race == "staging" and str(path).startswith(".lixity-edit-"):
            replace_parent()
        return opened(path, *args, **kwargs)

    def publishing(*args, **kwargs):
        if race == "publication":
            replace_parent()
        return link(*args, **kwargs)

    def resolving(path, *args, **kwargs):
        resolved = resolve(path, *args, **kwargs)
        if race == "resolution" and path == parent / "draft.md":
            replace_parent()
        return resolved

    monkeypatch.setattr(dossier_edit.os, "open", staging)
    monkeypatch.setattr(dossier_edit.os, "link", publishing)
    monkeypatch.setattr(dossier_edit.Path, "resolve", resolving)
    # The old tempfile path also provides the staging-race regression before
    # directory-relative publication is implemented.
    original_mkstemp = dossier_edit.tempfile.mkstemp

    def legacy_staging(*args, **kwargs):
        if race == "staging":
            replace_parent()
        return original_mkstemp(*args, **kwargs)

    monkeypatch.setattr(dossier_edit.tempfile, "mkstemp", legacy_staging)
    with pytest.raises(ResearchError, match=r"changed|outside"):
        dossier_edit.write_research_draft_file(project, parent / "draft.md", "Synthetic draft.")
    assert triggered
    assert not (project / "research" / "draft.md").exists()
    assert list(moved.iterdir()) == []
    assert retained_files(project) == before


def test_prepare_dossier_edits_multi_file_and_atomic_batch(project, tmp_path):
    from lixity.research.dossier_edit import prepare_dossier_edits, write_dossier_edit

    id1 = api.create_dossier(project, "Dossier 1", "Body 1.")["dossier_id"]
    id2 = api.create_dossier(project, "Dossier 2", "Body 2.")["dossier_id"]

    draft1 = tmp_path / "draft1.md"
    draft2 = tmp_path / "draft2.md"
    write_dossier_edit(project, id1, draft1)
    write_dossier_edit(project, id2, draft2)

    # Edit both files
    draft1.write_text(draft1.read_text(encoding="utf-8").replace("Body 1.", "Updated 1."), encoding="utf-8")
    draft2.write_text(draft2.read_text(encoding="utf-8").replace("Body 2.", "Updated 2."), encoding="utf-8")

    batch_preview = prepare_dossier_edits(
        project,
        [draft1, draft2],
        change_kind="correction",
        reason="Atomic batch update",
    )
    assert batch_preview["ready"] is True
    assert batch_preview["total_files"] == 2
    assert batch_preview["changed_files"] == 2
    assert batch_preview["batch_packet"] is not None

    # Apply the batch packet
    result = api.apply_record_revisions(
        project,
        batch_preview["batch_packet"],
        expected_snapshot=batch_preview["batch_packet"]["snapshot"],
    )
    assert len(result["records"]) == 2

    # Verify both dossiers were updated
    doc1 = api.get_dossier(project, id1)
    doc2 = api.get_dossier(project, id2)
    assert doc1["revision"] == 2
    assert doc1["body"] == "Updated 1."
    assert doc2["revision"] == 2
    assert doc2["body"] == "Updated 2."


def test_batch_prepare_accepts_crlf_draft_and_preserves_body(project, tmp_path):
    from lixity.research.dossier_edit import prepare_dossier_edits, write_dossier_edit

    identifier = api.create_dossier(project, "Notes", "Original.")["dossier_id"]
    draft = tmp_path / "draft.md"
    write_dossier_edit(project, identifier, draft)
    document = draft.read_bytes().replace(b"\n", b"\r\n").replace(b"Original.", b"First\r\nSecond\n")
    draft.write_bytes(document)
    preview = prepare_dossier_edits(project, [draft])
    assert preview["ready"] and preview["changed_files"] == 1
    api.apply_record_revisions(project, preview["batch_packet"], expected_snapshot=preview["snapshot"])
    assert api.get_dossier(project, identifier)["body"] == "First\r\nSecond\n"


def test_prepare_dossier_edits_rejects_duplicate_and_foreign_files(project, tmp_path):
    from lixity.research.dossier_edit import prepare_dossier_edits, write_dossier_edit

    id1 = api.create_dossier(project, "Dossier 1", "Body 1.")["dossier_id"]
    draft1 = tmp_path / "draft1.md"
    write_dossier_edit(project, id1, draft1)

    # Duplicate dossier ID in file list
    with pytest.raises(ResearchError, match="Duplicate dossier edit draft"):
        prepare_dossier_edits(project, [draft1, draft1])

    # Other project
    other = tmp_path / "other_proj"
    api.init(other, title="Other", language="en")
    other_draft = tmp_path / "other_draft.md"
    id_other = api.create_dossier(other, "Other", "Other body.")["dossier_id"]
    write_dossier_edit(other, id_other, other_draft)

    with pytest.raises(ResearchError, match="different project"):
        prepare_dossier_edits(project, [draft1, other_draft])

