"""HTTP preserves uncertain or committed research writes without retrying them."""

import hashlib
from pathlib import Path

import pytest

from lixity.pipeline import paragraph_identity, profile_document, resolve_document_config
from lixity.research import api, repository
from lixity.research.repository import (
    Repository,
    ResearchCleanupError,
    ResearchConflictError,
    ResearchError,
    ResearchPublicationError,
    ResearchStorageError,
)
from lixity.server.pdf_context import manuscript_pdf_token, research_context_token
from lixity.style_fingerprint import FingerprintThresholds
from tests.support import LoopbackServer, make_handler


@pytest.fixture
def endpoint(tmp_path):
    project = tmp_path / "archive"
    api.init(project, title="Synthetic archive")
    source = tmp_path / "source.txt"
    source.write_text("A synthetic observer opens a gate.\n", encoding="utf-8")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    dossier = api.create_dossier(project, title="Existing dossier", body="Synthetic notes.")["dossier_id"]
    claim = api.create_claim(project, title="Existing claim", statement="A synthetic observation.")["claim_id"]
    other_claim = api.create_claim(project, title="Other claim", statement="Another observation.")["claim_id"]
    decision = api.record_decision(project, title="Existing decision", rationale="An authored choice.",
                                   dossier_ids=[dossier])["decision_id"]
    manuscript = project / "manuscript.md"
    text = "## Scene\n\nA synthetic observer opens a gate.\n"
    manuscript.write_text(text, encoding="utf-8")
    config, _ = resolve_document_config(text)
    paragraph = profile_document(text, config, FingerprintThresholds())[0][0]
    snapshot = Repository(project).snapshot()
    selection = {**paragraph_identity(paragraph), "start": 0, "end": len(paragraph.text),
                 "quote": paragraph.text}
    link = api.link_manuscript_claim(
        project, manuscript, claim, claim_revision=1, selection=selection,
        expected_project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
        expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(),
        allow_retention=True,
    )["link_id"]
    handler = make_handler(project, research_dir=project, source_input=manuscript)
    snapshot = Repository(project).snapshot()
    operation = {"kind": "dossier", "id": dossier, "changes": {"title": "Revised dossier"},
                 "expected_revision": 1, "change_kind": "correction", "reason": "Reviewed notes"}
    context = {"project_id": snapshot.project.id, "research_token": research_context_token(project),
               "project_token": manuscript_pdf_token(str(manuscript), project_root=str(project),
                   language="en", title=None, thresholds=handler.thresholds),
               "expected_snapshot": snapshot.digest,
               "expected_source_sha256": hashlib.sha256(manuscript.read_bytes()).hexdigest()}
    bodies = {
        "research-dossier": {"title": "New dossier", "body": "Synthetic new notes."},
        "research-claim-add": {"title": "New claim", "statement": "Synthetic new observation."},
        "research-decision-add": {"title": "New decision", "rationale": "Synthetic new choice."},
        "research-evidence-link": {"claim_id": claim, "passage_id": passage},
        "research-record-revise": {**operation, "expected_snapshot": snapshot.digest},
        "research-revision-batch-apply": {"operations": [operation], "expected_snapshot": snapshot.digest},
        "research-decision-acknowledge": {"decision_id": decision, "dossier_id": dossier,
            "status": "applied", "expected_snapshot": snapshot.digest,
            "expected_decision_revision": 1, "expected_dossier_revision": 1},
        "research-claim-relation": {"project_id": snapshot.project.id,
            "research_token": context["research_token"], "expected_snapshot": snapshot.digest,
            "from_claim_id": claim, "to_claim_id": other_claim,
            "from_claim_revision": 1, "to_claim_revision": 1},
        "research-manuscript-link": {**context, "claim_id": claim, "claim_revision": 1,
            "selection": selection, "allow_retention": True},
        "research-manuscript-reanchor": {**context, "link_id": link, "expected_revision": 1},
    }
    with LoopbackServer(handler) as server:
        yield project, handler, bodies, server


@pytest.mark.parametrize("route", [
    "research-dossier", "research-claim-add", "research-decision-add", "research-evidence-link",
    "research-record-revise", "research-revision-batch-apply", "research-decision-acknowledge",
    "research-claim-relation",
])
def test_visible_head_sync_failure_returns_server_error_and_does_not_repeat_write(
    endpoint, monkeypatch, route,
):
    project, _, bodies, server = endpoint
    before = Repository(project).snapshot()
    old_head = (project / "research" / "HEAD.json").read_bytes()
    original_sync = repository.sync_directory

    def failed_head_sync(path):
        if Path(path) == project / "research" and (Path(path) / "HEAD.json").read_bytes() != old_head:
            raise OSError("Synthetic directory sync failure after HEAD replacement")
        return original_sync(path)

    with monkeypatch.context() as failure:
        failure.setattr(repository, "sync_directory", failed_head_sync)
        response = server.request("/api/" + route, payload=bodies[route])
    accepted = Repository(project).snapshot()
    assert accepted.digest != before.digest
    assert accepted.manifest.generation == before.manifest.generation + 1
    assert response.status == 500, response.body
    assert set(response.json) == {"ok", "message"} and response.json["ok"] is False
    assert accepted.digest in response.json["message"]
    assert "published" in response.json["message"].lower()
    assert "reload" in response.json["message"].lower()
    assert api.audit(project)["ok"]


@pytest.mark.parametrize("failure,status", [
    ("published", 500), ("unknown", 500), ("cleanup", 500), ("storage", 400),
    ("validation", 400), ("io", 400), ("conflict", 409),
])
def test_only_publication_and_cleanup_types_change_existing_http_classification(
    endpoint, monkeypatch, failure, status,
):
    project, _, bodies, server = endpoint
    before = Repository(project).snapshot().digest
    errors = {
        "published": ResearchPublicationError(before, published=True),
        "unknown": ResearchPublicationError(before, published=False),
        "cleanup": ResearchCleanupError(before, [project / "research" / "retained.json"], project_root=project),
        "storage": ResearchStorageError("Synthetic ordinary storage error"),
        "validation": ResearchError("Synthetic invalid request"),
        "io": OSError("Synthetic ordinary I/O error"),
        "conflict": ResearchConflictError("Synthetic reviewed snapshot conflict"),
    }
    error = errors[failure]

    def failed_revision(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(api, "revise_record", failed_revision)
    response = server.request("/api/research-record-revise", payload=bodies["research-record-revise"])
    assert response.status == status
    assert response.json == {"ok": False, "message": str(error)}
    assert Repository(project).snapshot().digest == before


@pytest.mark.parametrize("route,function", [
    ("research-manuscript-link", "link_manuscript_claim"),
    ("research-manuscript-reanchor", "reanchor_manuscript_link"),
])
def test_manuscript_mutation_mixin_keeps_publication_outcome_and_server_status(
    endpoint, monkeypatch, route, function,
):
    project, _, bodies, server = endpoint
    before = Repository(project).snapshot().digest
    error = ResearchPublicationError(before, published=False)

    def failed_write(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(api, function, failed_write)
    response = server.request("/api/" + route, payload=bodies[route])
    assert response.status == 500
    assert response.json == {"ok": False, "message": str(error)}
    assert Repository(project).snapshot().digest == before


def test_project_setup_keeps_recovery_message_for_uncertain_research_initialization(endpoint, monkeypatch, tmp_path):
    _, handler, _, server = endpoint
    destination = tmp_path / "new-project"
    prior = handler.workspace_root
    error = ResearchPublicationError("a" * 64, published=False)

    def failed_init(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(api, "init", failed_init)
    response = server.request("/api/project-create", payload={"path": str(destination),
        "title": "Synthetic new project", "init_research": True})
    assert response.status == 500
    assert set(response.json) == {"ok", "message"} and response.json["ok"] is False
    assert str(error) in response.json["message"] and "Open Project" in response.json["message"]
    assert handler.workspace_root == prior
    assert (destination / "manuscript.md").is_file()
