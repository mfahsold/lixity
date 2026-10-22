"""One read-only project observation is shared by the CLI, Python and native UI."""

import json
from urllib.parse import quote, urlencode

import pytest

from lixity import api
from lixity.cli import main
from lixity.server.pdf_context import project_settings_token
from tests.support import LoopbackServer, make_handler


def project_files(root):
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


@pytest.fixture
def project(tmp_path):
    manuscript = tmp_path / "draft.md"
    manuscript.write_text("## One\n\nSynthetic project prose.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    return tmp_path, manuscript


def test_cli_json_and_python_observe_the_same_metadata_without_writes(project, capsys, monkeypatch):
    root, _ = project
    def unexpected_config(*_args, **_kwargs):
        pytest.fail("Project inspection must not discover ancestor/user analysis settings")
    monkeypatch.setattr("lixity.cli.load_project_config", unexpected_config)
    before = project_files(root)
    assert main(["project", "--project", str(root), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == api.inspect_project(root)
    assert result["schema_version"] == "lixity-project-structure/1"
    assert project_files(root) == before
    assert not (root / "exports").exists()


def test_cli_reports_structural_errors_as_json_and_a_nonzero_exit(project, capsys):
    root, manuscript = project
    manuscript.unlink()
    assert main(["project", str(root), "--json"]) == 1
    output = capsys.readouterr()
    assert not output.err
    result = json.loads(output.out)
    assert result["ok"] is True and result["has_errors"] is True
    assert any(issue["code"] == "manuscript-missing" for issue in result["issues"])


@pytest.mark.parametrize("locale", ["en", "de"])
def test_cli_human_output_names_sources_and_unknown_output_origin(project, capsys, monkeypatch, locale):
    root, _ = project
    exports = root / "exports"
    exports.mkdir()
    (exports / "synthetic_report.html").write_text("Synthetic output", encoding="utf-8")
    monkeypatch.setenv("LIXITY_LANG", locale)
    assert main(["project", str(root)]) == 0
    text = capsys.readouterr().out
    assert "draft.md" in text and "synthetic_report.html" in text
    assert "lixity-project-structure/1" not in text
    assert "unknown" in text.lower() if locale == "en" else "unbekannt" in text.lower()


def test_project_command_is_discoverable_with_its_own_contract():
    command = next(item for item in api.about()["commands"] if item["name"] == "project")
    assert command["schema_version"] == "lixity-project-structure/1"
    assert command["writes"] is False


def test_project_completion_offers_inspection_options_without_analysis_flags(tmp_path):
    import shutil
    import subprocess

    from lixity.cli import _completion_scripts

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("Bash is unavailable")
    script = _completion_scripts()[0]
    probe = '\nCOMP_WORDS=(lixity project --); COMP_CWORD=2; _lixity_complete; printf "%s\\n" "${COMPREPLY[@]}"\n'
    result = subprocess.run(  # noqa: S603 - resolved Bash, emitted completion and fixed synthetic words
        [bash, "--noprofile", "--norc"], input=script + probe,
        cwd=tmp_path, text=True, capture_output=True, check=True,
    )
    assert set(result.stdout.splitlines()) == {"--help", "--project", "--json"}


def test_http_project_inspection_requires_current_context_and_origin(project):
    root, manuscript = project
    handler = make_handler(root, source_input=manuscript)
    token = project_settings_token(root, str(manuscript))
    before = project_files(root)
    with LoopbackServer(handler) as server:
        index = server.request("/api").json
        assert "/api/project-structure" in index["routes"]["GET"]
        url = "/api/project-structure?" + urlencode({"project_token": token})
        response = server.request(url)
        assert response.status == 200
        assert response.json == api.inspect_project(root, selected_manuscript=manuscript)
        assert server.request("/api/project-structure").status == 400
        assert server.request(url + "&project_token=" + token).status == 400
        assert server.request(url, headers={"Origin": "https://untrusted.example"}).status == 403
        (root / "lixity.toml").write_text('manuscript = "draft.md"\ntitle = "Changed settings"\n', encoding="utf-8")
        assert server.request(url).status == 409
        # A stale tab must not inspect the next selected project either.
        second = root / "second"
        second.mkdir()
        other = second / "draft.md"
        other.write_text("## Other\n\nOther synthetic prose.\n", encoding="utf-8")
        handler.workspace_root = str(second)
        handler.source_input = str(other)
        assert server.request(url).status == 409
    # Only the test's intentional settings edit and second project were written.
    assert manuscript.read_bytes() == before["draft.md"]
    assert not (root / "exports").exists()


def test_idle_server_never_inspects_its_working_directory(tmp_path):
    handler = make_handler(tmp_path)
    with LoopbackServer(handler) as server:
        response = server.request("/api/project-structure?project_token=" + "a" * 64)
        assert response.status == 400 and response.json["ok"] is False
        assert str(tmp_path) not in response.body.decode()


def test_research_only_project_is_inspectable_without_creating_a_manuscript(tmp_path):
    (tmp_path / "research").mkdir()
    handler = make_handler(tmp_path, research_dir=tmp_path)
    token = project_settings_token(tmp_path, None)
    with LoopbackServer(handler) as server:
        response = server.request("/api/project-structure?project_token=" + token)
        assert response.status == 200
        assert next(role for role in response.json["roles"] if role["role"] == "manuscript")["state"] == "unassigned"
        assert not response.json["has_errors"]
    assert list(tmp_path.iterdir()) == [tmp_path / "research"]


def test_overview_artifact_links_decode_names_once_and_reject_stale_context(project):
    root, manuscript = project
    exports = root / "exports"
    exports.mkdir()
    name = "Synthetic résumé #1.html"
    (exports / name).write_text("Synthetic generated output", encoding="utf-8")
    handler = make_handler(root, source_input=manuscript)
    token = project_settings_token(root, str(manuscript))
    url = "/artifact/" + quote(name, safe="") + "?" + urlencode({"project_token": token})
    with LoopbackServer(handler) as server:
        response = server.request(url)
        assert response.status == 200 and response.body == b"Synthetic generated output"
        assert server.request(url, headers={"Origin": "https://untrusted.example"}).status == 403
        assert server.request(url + "&project_token=" + token).status == 400
        (root / "lixity.toml").write_text('manuscript = "draft.md"\ntitle = "Changed"\n', encoding="utf-8")
        assert server.request(url).status == 409
        assert server.request("/artifact/" + quote(name, safe="")).status == 200


@pytest.mark.parametrize("protected", ["draft.md", "lixity.toml"])
def test_artifact_transport_rejects_source_and_config_hardlink_aliases(project, protected):
    import os

    root, manuscript = project
    exports = root / "exports"
    exports.mkdir()
    try:
        os.link(root / protected, exports / "alias.html")
    except (OSError, NotImplementedError):
        pytest.skip("Hardlinks are unavailable on this filesystem")
    handler = make_handler(root, source_input=manuscript)
    with LoopbackServer(handler) as server:
        assert server.request("/artifact/alias.html").status == 404


def test_artifact_transport_rejects_encoded_path_components_and_oversized_files(project, monkeypatch):
    root, manuscript = project
    exports = root / "exports"
    exports.mkdir()
    (exports / "safe.html").write_text("Synthetic output", encoding="utf-8")
    (exports / "large.html").write_bytes(b"x" * 129)
    monkeypatch.setattr("lixity.server.handler.MAX_ARTIFACT_BYTES", 128)
    with LoopbackServer(make_handler(root, source_input=manuscript)) as server:
        assert server.request("/artifact/..%2Fsafe.html").status == 404
        assert server.request("/artifact/large.html").status == 413


def test_artifact_transport_protects_a_discovered_manuscript_without_a_selected_source(tmp_path):
    import os

    (tmp_path / "research").mkdir()
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source, not an output.", encoding="utf-8")
    exports = tmp_path / "exports"
    exports.mkdir()
    try:
        os.link(source, exports / "alias.html")
    except (OSError, NotImplementedError):
        pytest.skip("Hardlinks are unavailable on this filesystem")
    with LoopbackServer(make_handler(tmp_path, research_dir=tmp_path)) as server:
        token = project_settings_token(tmp_path, None)
        assert server.request("/artifact/alias.html?project_token=" + token).status == 404
