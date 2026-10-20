"""Invalid native requests must not silently change meaning or project scope."""

from pathlib import Path

import pytest

from lixity.research import api
from lixity.research.repository import Repository
from tests.support import LoopbackServer, make_handler


@pytest.fixture
def research_endpoint(tmp_path):
    project = tmp_path / "archive"
    api.init(project, title="Synthetic archive")
    source = tmp_path / "source.txt"
    source.write_text("A synthetic archive opened in 1924.\n", encoding="utf-8")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    claim = api.create_claim(
        project, title="Synthetic claim", statement="The archive opened in 1924."
    )["claim_id"]
    with LoopbackServer(make_handler(project, research_dir=project)) as server:
        yield project, passage, claim, server


@pytest.mark.parametrize(
    "action,field", [("research-claim-add", "confidence"), ("research-evidence-link", "relation")]
)
@pytest.mark.parametrize("value", ["unsupported", "", None, False, 9, [], {}])
def test_explicit_invalid_research_enums_are_rejected_without_writing(
    research_endpoint, action, field, value
):
    project, passage, claim, server = research_endpoint
    before = Repository(project).snapshot().digest
    body = {
        "title": "Synthetic claim",
        "statement": "Synthetic statement.",
        "claim_id": claim,
        "passage_id": passage,
        field: value,
    }
    response = server.request("/api/" + action, payload=body)
    assert response.status == 400, response.body
    assert response.json["ok"] is False and field in response.json["message"].lower()
    assert Repository(project).snapshot().digest == before


@pytest.mark.parametrize(
    "changes,wanted",
    [
        ({}, "hypothetical"),
        ({"confidence": "hypothetical"}, "hypothetical"),
        ({"confidence": " EVIDENCED "}, "evidenced"),
        ({"confidence": "Disputed"}, "disputed"),
    ],
)
def test_claim_confidence_keeps_omission_defaults_and_case_normalization(
    research_endpoint, changes, wanted
):
    project, _, _, server = research_endpoint
    response = server.request(
        "/api/research-claim-add",
        payload={
            "title": "Synthetic review state",
            "statement": "An authored synthetic statement.",
            **changes,
        },
    )
    assert response.status == 200, response.body
    assert response.json["confidence"] == wanted
    saved = api.get_record(project, "claim", response.json["claim_id"])
    assert saved["record"]["confidence"] == wanted


@pytest.mark.parametrize(
    "changes,wanted",
    [
        ({}, "supports"),
        ({"relation": "supports"}, "supports"),
        ({"relation": " CONTRADICTS "}, "contradicts"),
        ({"relation": "Qualifies"}, "qualifies"),
        ({"relation": "contextualizes"}, "contextualizes"),
    ],
)
def test_evidence_relation_keeps_omission_defaults_and_case_normalization(
    research_endpoint, changes, wanted
):
    project, passage, claim, server = research_endpoint
    response = server.request(
        "/api/research-evidence-link", payload={"claim_id": claim, "passage_id": passage, **changes}
    )
    assert response.status == 200, response.body
    assert response.json["relation"] == wanted
    assert api.list_evidence_links(project)["evidence_links"][0]["relation"] == wanted


@pytest.fixture
def creation_endpoint(tmp_path):
    previous = tmp_path / "previous"
    api.init(previous, title="Previously selected synthetic archive")
    manuscript = previous / "manuscript.md"
    manuscript.write_text(
        "# Previous project\n\nAn existing synthetic manuscript.\n", encoding="utf-8"
    )
    handler = make_handler(previous, research_dir=previous, source_input=manuscript)
    handler.refresh()
    with LoopbackServer(handler) as server:
        yield tmp_path / "new-project", handler, server


@pytest.mark.parametrize(
    "failure", ["config-write", "config-path", "research-init", "research-path", "invalid-archive"]
)
def test_incomplete_project_setup_reports_failure_and_keeps_files_and_selection(
    creation_endpoint, monkeypatch, failure
):
    project, handler, server = creation_endpoint
    project.mkdir()
    if failure == "research-path":
        (project / "research").write_text("Synthetic path collision", encoding="utf-8")
    elif failure == "config-path":
        (project / "lixity.toml").mkdir()
    elif failure == "invalid-archive":
        (project / "research").mkdir()
        (project / "research" / "HEAD.json").write_text(
            "Synthetic invalid archive", encoding="utf-8"
        )
    elif failure == "config-write":
        from lixity import io

        original_replace = io.os.replace

        def denied_config(source, destination):
            if Path(destination) == project / "lixity.toml":
                raise PermissionError("Synthetic denied project configuration")
            return original_replace(source, destination)

        monkeypatch.setattr(io.os, "replace", denied_config)
    else:

        def denied_init(*_args, **_kwargs):
            raise OSError("Synthetic research filesystem failure")

        monkeypatch.setattr(api, "init", denied_init)

    before_root, before_source, before_html = (
        handler.workspace_root,
        handler.source_input,
        handler.dashboard_html,
    )
    before_head = Repository(before_root).snapshot().digest
    text = "# New synthetic project\n\nThe imported text must be retained after setup failure.\n"
    response = server.request(
        "/api/project-create",
        payload={
            "path": str(project),
            "title": "New synthetic project",
            "content": text,
            "author_name": "Synthetic Author",
            "init_research": True,
        },
    )
    assert response.status in (400, 500), response.body
    result = response.json
    assert result["ok"] is False and not result.get("reload")
    assert str(project) in result["message"] and "open" in result["message"].lower()
    assert (project / "manuscript.md").read_text(encoding="utf-8") == text
    assert (handler.workspace_root, handler.source_input, handler.dashboard_html) == (
        before_root,
        before_source,
        before_html,
    )
    assert Repository(before_root).snapshot().digest == before_head
    if failure == "config-write":
        assert not (project / "lixity.toml").exists()
        assert not (project / "research").exists()
    elif failure == "config-path":
        assert (project / "lixity.toml").is_dir()
        assert not (project / "research").exists()
    else:
        assert 'author_name = "Synthetic Author"' in (project / "lixity.toml").read_text(
            encoding="utf-8"
        )
    if failure == "research-path":
        assert (project / "research").read_text(encoding="utf-8") == "Synthetic path collision"
    elif failure == "invalid-archive":
        assert (project / "research" / "HEAD.json").read_text(
            encoding="utf-8"
        ) == "Synthetic invalid archive"


@pytest.mark.parametrize("existing_archive", [False, True])
def test_project_creation_initializes_or_reuses_a_valid_archive(
    creation_endpoint, existing_archive
):
    project, handler, server = creation_endpoint
    before = None
    if existing_archive:
        api.init(project, title="Retained synthetic archive")
        before = Repository(project).snapshot().digest
        (project / "lixity.toml").write_text(
            'title = "Retained metadata"\nlanguage = "en"\n# Preserved comment\n', encoding="utf-8"
        )
    response = server.request(
        "/api/project-create",
        payload={"path": str(project), "title": "New synthetic project", "init_research": True},
    )
    assert response.status == 200, response.body
    assert response.json["ok"] is True and response.json["reload"] is True
    assert handler.workspace_root == str(project)
    after = Repository(project).snapshot()
    if before is not None:
        assert after.digest == before
        assert (project / "lixity.toml").read_text(
            encoding="utf-8"
        ) == 'title = "Retained metadata"\nlanguage = "en"\n# Preserved comment\n'
    assert api.audit(project)["ok"]
