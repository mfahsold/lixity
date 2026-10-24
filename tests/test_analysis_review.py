"""Review decisions are author assertions bound to exact text and analysis state."""

import json
from dataclasses import replace
from urllib.parse import urlencode

import pytest

from lixity.analysis_review import record_analysis_review, review_analysis
from lixity.cli import main
from lixity.research.repository import ResearchConflictError
from lixity.style_fingerprint import FingerprintThresholds
from tests.support import LoopbackServer, make_handler

TEXT = (
    "## First\n\nShe walks. She waits. She watches.\n\n"
    "She walks. She waits. She watches. She walked. She waited. She watched.\n\n"
    "## Second\n\nHe walks. He waits. He watches. He walked. He waited. He watched.\n"
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "manuscript.md").write_text(TEXT)
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n')
    return tmp_path


def save(project, report, status="kept", **overrides):
    arguments = {"expected_source_sha256": report["source_sha256"],
                 "expected_analysis_sha256": report["analysis_sha256"],
                 "expected_review_sha256": report["review_sha256"]}
    arguments.update(overrides)
    return record_analysis_review(project, report["observations"][0]["id"], status, **arguments)


def files(project):
    return {path.relative_to(project).as_posix(): path.read_bytes() for path in project.rglob("*") if path.is_file()}


def test_read_is_nonmutating_and_decision_does_not_edit_manuscript(project):
    before = files(project)
    report = review_analysis(project)
    assert report["schema_version"] == "lixity-analysis-review/1"
    assert report["total"] >= 2 and report["completed"] == 0
    assert files(project) == before
    saved = save(project, report)
    assert saved["observations"][0]["status"] == "kept"
    assert saved["completed"] == 1
    assert (project / "manuscript.md").read_text() == TEXT
    assert not (project / "research").exists()
    state = json.loads((project / ".lixity/analysis-review.json").read_text())
    assert state["schema_version"] == "lixity-analysis-review-state/1"
    assert "She walks" not in json.dumps(state)
    assert review_analysis(project) == saved


def test_later_remains_open_and_changed_is_only_an_author_status(project):
    report = review_analysis(project)
    later = save(project, report, "later")
    assert later["completed"] == 0
    changed = save(project, later, "changed")
    assert changed["completed"] == 1
    assert (project / "manuscript.md").read_text() == TEXT


def test_source_settings_and_concurrent_decisions_invalidate_old_context(project):
    report = review_analysis(project)
    saved = save(project, report)
    with pytest.raises(ResearchConflictError):
        save(project, report)
    (project / "manuscript.md").write_text(TEXT + "\nA new unrelated paragraph.\n")
    stale = review_analysis(project)
    assert stale["observations"][0]["status"] == "stale"
    assert stale["observations"][0]["previous_status"] == "kept"
    assert stale["completed"] == 0
    with pytest.raises(ResearchConflictError):
        save(project, saved)
    (project / "manuscript.md").write_text(TEXT)
    settings = review_analysis(project, thresholds=replace(FingerprintThresholds(), z_mild=2.7))
    assert settings["observations"][0]["status"] == "stale"


def test_marker_policy_changes_invalidate_saved_decisions(project, monkeypatch):
    import lixity.analysis_review as review_module

    with monkeypatch.context() as previous_policy:
        previous_policy.setattr(review_module, "_ANALYSIS_POLICY", "tense-review/1", raising=False)
        previous = review_analysis(project)
        save(project, previous)
    current = review_analysis(project)
    assert current["source_sha256"] == previous["source_sha256"]
    assert current["analysis_sha256"] != previous["analysis_sha256"]
    assert current["observations"][0]["status"] == "stale"
    assert current["observations"][0]["previous_status"] == "kept"


def test_corrupt_or_foreign_review_state_never_looks_unreviewed(project):
    report = review_analysis(project)
    with pytest.raises(ValueError):
        record_analysis_review(project, "0" * 64, "kept",
            expected_source_sha256=report["source_sha256"], expected_analysis_sha256=report["analysis_sha256"],
            expected_review_sha256=report["review_sha256"])
    save(project, report)
    path = project / ".lixity/analysis-review.json"
    path.write_text('{"schema_version":"unknown","decisions":[]}')
    with pytest.raises(ValueError):
        review_analysis(project)
    with pytest.raises(ValueError):
        review_analysis(project, manuscript="../outside.md")


def test_cli_read_and_guarded_write_share_the_same_state(project, capsys):
    assert main(["analysis-review", "--project", str(project), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    args = ["analysis-review", "--project", str(project), "--json", "--observation",
            report["observations"][0]["id"], "--status", "later",
            "--expected-source-sha256", report["source_sha256"],
            "--expected-analysis-sha256", report["analysis_sha256"],
            "--expected-review-sha256", report["review_sha256"]]
    assert main(args) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["observations"][0]["status"] == "later"
    assert main(args) == 1
    assert "changed" in capsys.readouterr().err


def test_native_context_guards_and_static_state_exclusion(project):
    from lixity.server.pdf_context import manuscript_pdf_token
    from lixity.site_export import prepare_site

    handler = make_handler(project, source_input=project / "manuscript.md")
    handler.refresh()
    token = manuscript_pdf_token(str(project / "manuscript.md"), project_root=project,
                                language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        url = "/api/analysis-review?" + urlencode({"project_token": token})
        response = server.request(url)
        assert response.status == 200, response.body
        report = response.json
        payload = {"project_token": token, "observation_id": report["observations"][0]["id"], "status": "kept",
                   "expected_source_sha256": report["source_sha256"],
                   "expected_analysis_sha256": report["analysis_sha256"],
                   "expected_review_sha256": report["review_sha256"]}
        assert server.request("/api/analysis-review", payload=payload).status == 200
        assert server.request("/api/analysis-review", payload=payload).status == 409
        assert server.request(url, headers={"Origin": "https://other.invalid"}).status == 403
        assert server.request("/api/analysis-review?project_token=wrong").status == 409
        assert server.request("/api/analysis-review", payload={**payload, "text": "not allowed"}).status == 400
        (project / "manuscript.md").write_text(TEXT + "\nChanged source.\n")
        assert server.request(url).status == 409
    bundle = prepare_site(project)
    assert not any("analysis-review.json" in name for name in bundle.files)
    assert b'data-review-capable="false"' in bundle.files["index.html"]
    assert b'data-review-capable="true"' not in bundle.files["index.html"]
