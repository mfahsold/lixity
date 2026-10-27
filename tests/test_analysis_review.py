"""Review decisions are author assertions bound to exact text and analysis state."""

import json
import re
import shutil
import subprocess
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


@pytest.mark.parametrize("previous_version", ["tense-review/1", "tense-review/2", "tense-review/3", "tense-review/4"])
def test_marker_policy_changes_invalidate_saved_decisions(project, monkeypatch, previous_version):
    import lixity.analysis_review as review_module

    with monkeypatch.context() as previous_policy:
        previous_policy.setattr(review_module, "_ANALYSIS_POLICY", previous_version)
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


@pytest.fixture
def model_project(tmp_path, monkeypatch):
    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup

    text = "## Test\n\n" + "Sie übt. Er ging. " * 5 + "\n"
    (tmp_path / "manuscript.md").write_text(text)
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "de"\n')

    def annotated(text, _model):
        return tuple(VerbGroup(((match.start(), match.end()),),
                               "present" if match.group() == "übt" else "preterite", "indicative", "active")
                     for match in re.finditer(r"übt|ging", text))

    # Replace only the optional inference/identity boundary. Real profile,
    # observation, guard, route and persistence paths remain under test.
    monkeypatch.setattr(grammatical_tense, "analyze_verbs", annotated)
    monkeypatch.setattr(grammatical_tense, "model_identity", lambda name: {
        "policy": grammatical_tense.POLICY, "model": name, "version": "test-1", "language": "de"})
    return tmp_path


def test_model_override_review_read_and_save_share_exact_analysis(model_project):
    before = files(model_project)
    disk = review_analysis(model_project)
    assert disk["total"] == 0
    selected = {"tense_model": "de_test", "tense_scope": "narration"}
    report = review_analysis(model_project, **selected)
    assert report["total"] == 1
    assert (report["observations"][0]["present_hits"], report["observations"][0]["past_hits"]) == (5, 5)
    assert report["project_settings_sha256"] == disk["project_settings_sha256"]
    assert report["analysis_sha256"] != disk["analysis_sha256"]
    assert files(model_project) == before
    with pytest.raises(ResearchConflictError):
        save(model_project, report)
    with pytest.raises(ResearchConflictError):
        save(model_project, report, tense_model="de_test", tense_scope="all")
    saved = save(model_project, report, **selected)
    assert saved["completed"] == 1
    assert review_analysis(model_project, **selected) == saved
    for path, content in before.items():
        assert (model_project / path).read_bytes() == content


def test_model_override_keeps_before_replace_disk_settings_guard(model_project, monkeypatch):
    from lixity.io import FileUtils

    selected = {"tense_model": "de_test", "tense_scope": "narration"}
    report = review_analysis(model_project, **selected)
    original = FileUtils.atomic_write_bytes_if_changed

    def race(path, content, **kwargs):
        with (model_project / "lixity.toml").open("a") as config:
            config.write('title = "Changed during save"\n')
        return original(path, content, **kwargs)

    monkeypatch.setattr(FileUtils, "atomic_write_bytes_if_changed", race)
    with pytest.raises(ResearchConflictError):
        save(model_project, report, **selected)
    assert not (model_project / ".lixity/analysis-review.json").exists()


def test_cli_model_override_review_read_and_save_agree(model_project, capsys):
    flags = ["analysis-review", "--project", str(model_project), "--json",
             "--tense-model", "de_test", "--tense-scope", "narration"]
    assert main(flags) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["total"] == 1
    assert main([*flags, "--observation", report["observations"][0]["id"], "--status", "kept",
                 "--expected-source-sha256", report["source_sha256"],
                 "--expected-analysis-sha256", report["analysis_sha256"],
                 "--expected-review-sha256", report["review_sha256"]]) == 0
    assert json.loads(capsys.readouterr().out)["completed"] == 1


def test_review_model_flags_complete_in_bash(capsys):
    shell = shutil.which("bash")
    if shell is None:
        pytest.skip("Bash is not installed")
    assert main(["completion", "bash"]) == 0
    script = capsys.readouterr().out
    probe = ('\nCOMP_WORDS=(lixity analysis-review --tense-); COMP_CWORD=2; '
             '_lixity_complete; printf "%s\\n" "${COMPREPLY[@]}"\n')
    # Only generated product completion and the literal probe reach Bash.
    result = subprocess.run([shell], input=script + probe, capture_output=True, text=True, check=True)  # noqa: S603
    assert set(result.stdout.splitlines()) == {"--tense-model", "--tense-scope"}


def test_native_model_override_survives_review_and_reopen(model_project):
    from lixity.server.pdf_context import manuscript_pdf_token

    before = files(model_project)
    handler = make_handler(model_project, source_input=model_project / "manuscript.md", language="de",
                           project_open_overrides={"tense_model": "de_test", "tense_scope": "narration"})
    handler.refresh()
    assert handler.dashboard_info["flagged"] == 1
    token = manuscript_pdf_token(str(model_project / "manuscript.md"), project_root=model_project,
                                language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        url = "/api/analysis-review?" + urlencode({"project_token": token})
        response = server.request(url)
        assert response.status == 200, response.body
        report = response.json
        assert report["total"] == 1
        payload = {"project_token": token, "observation_id": report["observations"][0]["id"], "status": "kept",
                   "expected_source_sha256": report["source_sha256"],
                   "expected_analysis_sha256": report["analysis_sha256"],
                   "expected_review_sha256": report["review_sha256"]}
        assert server.request("/api/analysis-review", payload=payload).status == 200
        reopened = server.request("/api/project-open", payload={"path": str(model_project)})
        assert reopened.status == 200, reopened.body
        assert handler.dashboard_info["flagged"] == 1
        assert server.request(url).json["completed"] == 1
    for path, content in before.items():
        assert (model_project / path).read_bytes() == content


def test_new_workspace_does_not_inherit_grammatical_override(model_project):
    from lixity.server.pdf_context import manuscript_pdf_token
    from lixity.server.workspaces import WorkspaceRegistry

    handler = make_handler(model_project, source_input=model_project / "manuscript.md", language="de",
                           project_open_overrides={"tense_model": "de_test", "tense_scope": "narration"})
    registry = WorkspaceRegistry(handler)
    assert registry.default.dashboard_info["flagged"] == 1
    token = manuscript_pdf_token(str(model_project / "manuscript.md"), project_root=model_project,
                                language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        server._server.workspaces = registry
        opened = server.request("/api/project-open", payload={"path": str(model_project)})
        assert opened.status == 200, opened.body
        workspace = opened.json["workspace_url"]
        query = "api/analysis-review?" + urlencode({"project_token": token})
        assert server.request(workspace + query).json["total"] == 0
        default = registry.default.api_base.removesuffix("api")
        assert server.request(default + query).json["total"] == 1
        registry.close(workspace.split("/")[2])
        assert server.request(workspace + query).status == 410


def test_reapplying_view_settings_preserves_grammar_and_source_bytes(model_project):
    before = files(model_project)
    handler = make_handler(model_project, source_input=model_project / "manuscript.md", language="de",
                           project_open_overrides={"tense_model": "de_test", "tense_scope": "narration"})
    handler.refresh()
    assert handler.dashboard_info["flagged"] == 1
    with LoopbackServer(handler) as server:
        applied = server.request("/api/settings", payload={"z_mild": 2.6})
        assert applied.status == 200, applied.body
        assert handler.dashboard_info["flagged"] == 1
        first = handler.dashboard_html
        reapplied = server.request("/api/settings", payload={"z_mild": 2.6})
        assert reapplied.status == 200, reapplied.body
        assert handler.dashboard_html == first
    assert files(model_project) == before
