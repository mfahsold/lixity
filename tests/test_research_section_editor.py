"""Section editing reconciles only the chosen subtree through canonical revisions."""

from pathlib import Path

import pytest

from lixity.research import api
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from lixity.server.routes_research import ResearchRoutesMixin


@pytest.fixture
def dossier(tmp_path: Path):
    api.init(tmp_path, title="Synthetic section editor")
    created = api.create_dossier(tmp_path, "Notes", "# One\r\nOld content.\r\n\r\n# Two\r\nOther content.\r\n")
    return tmp_path, created["dossier_id"]


def test_section_prepare_keeps_unrelated_current_changes_and_is_read_only(dossier):
    project, identifier = dossier
    before = api.get_record(project, "dossier", identifier)
    current_body = before["record"]["body"].replace("Other content.", "Concurrent other content.")
    api.revise_record(project, "dossier", identifier, expected_snapshot=before["snapshot"],
                      expected_revision=1, change_kind="supersession", reason="Synthetic concurrent note",
                      changes={"body": current_body})
    head = Repository(project).snapshot().digest
    prepared = api.prepare_dossier_section(project, identifier, base_revision=1,
                                          section="One", content="New chosen content.")
    assert prepared["ready"] and prepared["has_changes"]
    assert "Concurrent other content." in prepared["changes"]["body"]
    assert prepared["changes"]["body"].endswith("# Two\r\nConcurrent other content.\r\n")
    assert "Old content." not in prepared["changes"]["body"]
    assert Repository(project).snapshot().digest == head
    current = prepared["current"]
    api.revise_record(project, "dossier", identifier, expected_snapshot=current["snapshot"],
        expected_revision=current["record"]["revision"], changes=prepared["changes"],
        change_kind="supersession", reason="Synthetic selected section edit")
    assert api.get_dossier(project, identifier)["body"] == prepared["changes"]["body"]
    with pytest.raises(ResearchConflictError):
        api.revise_record(project, "dossier", identifier, expected_snapshot=current["snapshot"],
            expected_revision=current["record"]["revision"], changes={"body": "Stale overwrite"},
            change_kind="supersession", reason="Synthetic stale request")
    assert api.get_dossier(project, identifier)["body"] == prepared["changes"]["body"]


def test_section_prepare_reports_only_the_conflicting_section(dossier):
    project, identifier = dossier
    before = api.get_record(project, "dossier", identifier)
    changed = before["record"]["body"].replace("Old content.", "Concurrent chosen content.")
    api.revise_record(project, "dossier", identifier, expected_snapshot=before["snapshot"],
                      expected_revision=1, change_kind="correction", reason="Synthetic correction",
                      changes={"body": changed})
    prepared = api.prepare_dossier_section(project, identifier, base_revision=1,
                                          section="One", content="My chosen content.")
    assert not prepared["ready"]
    assert prepared["conflicts"] == [{"field": "body", "base": "Old content.",
                                      "current": "Concurrent chosen content.", "mine": "My chosen content."}]
    resolved = api.prepare_dossier_section(project, identifier, base_revision=1,
                                          section="One", content="My chosen content.", resolutions={"body": "mine"})
    assert resolved["ready"] and "Other content." in resolved["changes"]["body"]
    assert api.get_dossier(project, identifier, revision=1, section="One")["content"] == "Old content."
    assert api.get_dossier(project, identifier, section="One")["content"] == "Concurrent chosen content."


def test_section_prepare_rejects_ambiguous_and_missing_headings(dossier):
    project, identifier = dossier
    with pytest.raises(ResearchError, match="not found"):
        api.prepare_dossier_section(project, identifier, base_revision=1, section="Absent", content="Text")
    current = api.get_record(project, "dossier", identifier)
    api.revise_record(project, "dossier", identifier, expected_snapshot=current["snapshot"],
                      expected_revision=1, change_kind="supersession", reason="Synthetic duplicate",
                      changes={"body": "# One\nFirst\n\n# One\nSecond\n"})
    with pytest.raises(ResearchError, match="ambiguous"):
        api.prepare_dossier_section(project, identifier, base_revision=2, section="One", content="Text")
    assert api.get_dossier(project, identifier)["editable_sections"] == []


def test_section_targets_exclude_preamble_code_and_casefold_duplicates(dossier):
    project, identifier = dossier
    current = api.get_record(project, "dossier", identifier)
    api.revise_record(project, "dossier", identifier, expected_snapshot=current["snapshot"],
        expected_revision=1, change_kind="supersession", reason="Synthetic section targets",
        changes={"body": "Preamble\n\n# Straße\nOne\n\n# STRASSE\nTwo\n\n```md\n# Fake\n```\n\n## Real\nText\n"})
    assert api.get_dossier(project, identifier)["editable_sections"] == ["Real"]
    assert api.get_dossier(project, identifier, summary=True)["editable_sections"] == ["Real"]


def test_section_prepare_preserves_markdown_spaces_and_indentation(dossier):
    project, identifier = dossier
    prepared = api.prepare_dossier_section(project, identifier, base_revision=1,
        section="One", content="    Synthetic code block.\n\nHard line break.  \n")
    assert "\r\n    Synthetic code block.\r\n\r\nHard line break.  \r\n" in prepared["changes"]["body"]
    current = api.get_record(project, "dossier", identifier)
    api.revise_record(project, "dossier", identifier, expected_snapshot=current["snapshot"],
        expected_revision=1, changes=prepared["changes"], change_kind="correction", reason="Preserve Markdown")
    assert api.get_dossier(project, identifier, section="One")["content"] == "    Synthetic code block.\r\n\r\nHard line break.  "
    current_content = api.get_dossier(project, identifier, section="One")["content"]
    unchanged = api.prepare_dossier_section(project, identifier, base_revision=2,
        section="One", content=current_content.replace("\r\n", "\n"))
    assert unchanged["ready"] and not unchanged["has_changes"]


@pytest.mark.parametrize("revision", [0, -1, True, 1.5, "1"])
def test_section_read_rejects_invalid_revision(dossier, revision):
    project, identifier = dossier
    with pytest.raises(ResearchError, match="positive integer"):
        api.get_dossier(project, identifier, revision=revision)


@pytest.mark.parametrize("revision", [None, 0, -1, True, 1.5, "1"])
def test_revision_prepare_requires_an_explicit_positive_base(dossier, revision):
    project, identifier = dossier
    with pytest.raises(ResearchError, match="positive integer"):
        api.prepare_dossier_section(project, identifier, base_revision=revision, section="One", content="New")
    with pytest.raises(ResearchError, match="positive integer"):
        api.prepare_record_revision(project, "dossier", identifier, base_revision=revision, changes={"body": "New"})


def test_http_section_read_and_preview_delegate_without_writing(dossier):
    project, identifier = dossier

    class Routes(ResearchRoutesMixin):
        research_dir = str(project)

        def _json(self, payload, code=200):
            self.response = code, payload

    routes = Routes()
    routes.path = f"/api/research/dossiers?id={identifier}&section=One&revision=1"
    routes._handle_research_dossiers()
    assert routes.response[0] == 200
    assert routes.response[1]["content"] == "Old content."
    before = Repository(project).snapshot().digest
    routes._handle_research_record_prepare({"kind": "dossier", "id": identifier,
        "base_revision": 1, "section": "One", "changes": {"body": "A new section."}})
    assert routes.response[0] == 200 and routes.response[1]["ready"]
    assert "Other content." in routes.response[1]["changes"]["body"]
    assert Repository(project).snapshot().digest == before


def test_http_decision_creation_links_current_dossier(dossier):
    project, identifier = dossier

    class Routes(ResearchRoutesMixin):
        research_dir = str(project)

        def _json(self, payload, code=200):
            self.response = code, payload

    routes = Routes()
    routes._handle_research_decision_add({"title": "Synthetic choice", "rationale": "Chosen by the author",
                                        "dossier_ids": [identifier]})
    assert routes.response[0] == 200
    assert routes.response[1]["dossier_ids"] == [identifier]
    decision = api.get_record(project, "decision", routes.response[1]["decision_id"])
    assert decision["record"]["dossier_refs"] == [{"id": identifier, "revision": 1}]


def test_http_section_read_rejects_explicit_blank_revision(dossier):
    project, identifier = dossier

    class Routes(ResearchRoutesMixin):
        research_dir = str(project)

        def _json(self, payload, code=200):
            self.response = code, payload

    routes = Routes()
    routes.path = f"/api/research/dossiers?id={identifier}&revision="
    routes._handle_research_dossiers()
    assert routes.response[0] == 400


@pytest.mark.parametrize("identifiers", ["id", 1, [1], [None]])
def test_http_decision_creation_rejects_invalid_dossier_list(dossier, identifiers):
    project, _ = dossier

    class Routes(ResearchRoutesMixin):
        research_dir = str(project)

        def _json(self, payload, code=200):
            self.response = code, payload

    before = Repository(project).snapshot().digest
    routes = Routes()
    routes._handle_research_decision_add({"title": "Synthetic choice", "rationale": "Author note",
                                        "dossier_ids": identifiers})
    assert routes.response[0] == 400
    assert Repository(project).snapshot().digest == before
