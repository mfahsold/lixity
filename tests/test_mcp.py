"""Protocol tests for the read-only MCP server (stdio JSON-RPC, no network)."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from lixity import cli, mcp
from lixity.status import ABOUT_SECTIONS, LANGUAGE_CHOICES
from lixity.style_fingerprint import FingerprintThresholds

SAMPLE = "# Chapter One\n\nShe walked home. He had already left the grey house.\n"


def _request(method, params=None, request_id=1):
    message: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return mcp.handle_message(message)


def test_initialize_negotiates_protocol():
    response = _request("initialize", {"protocolVersion": mcp.PROTOCOL_VERSION})
    assert response["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION
    assert response["result"]["serverInfo"]["name"] == "lixity"
    assert "tools" in response["result"]["capabilities"]
    assert "prompts" in response["result"]["capabilities"]


def test_tools_list_names_readonly_tools():
    response = _request("tools/list")
    names = [tool["name"] for tool in response["result"]["tools"]]
    expected = [
        "lixity_about",
        "lixity_service_status",
        "lixity_analyze",
        "lixity_profile",
        "lixity_pacing",
        "lixity_scenes",
        "lixity_corridors",
        "lixity_dialogue",
        "lixity_showing",
        "lixity_motifs",
        "lixity_characters",
        "lixity_markers",
        "lixity_fingerprint",
        "revision_diff",
        "lixity_manuscript_dossier_drafts",
        "lixity_outlier_matrix",
        "lixity_research_gaps",
    ]
    assert names == expected
    for tool in response["result"]["tools"]:
        assert set(tool) == {"name", "description", "inputSchema"}


def test_call_about_returns_metadata():
    response = _request("tools/call", {"name": "lixity_about", "arguments": {}})
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["meta"]["tool"] == "lixity"
    assert "languages" in payload


@pytest.mark.parametrize("section", ABOUT_SECTIONS)
def test_mcp_about_sections_match_cli(section, capsys):
    tools = _request("tools/list")["result"]["tools"]
    tool = next(tool for tool in tools if tool["name"] == "lixity_about")
    assert tool["inputSchema"]["properties"]["section"]["enum"] == list(ABOUT_SECTIONS)
    response = _request("tools/call", {"name": "lixity_about", "arguments": {"section": section}})
    payload = json.loads(response["result"]["content"][0]["text"])
    assert set(payload) == {"meta", section}
    assert cli.main(["about", "--section", section]) == 0
    assert payload == json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("argument", [{"section": "license"}, {"section": None}, {"project": "./synthetic-project"}])
def test_mcp_about_rejects_unsupported_arguments(argument):
    result = _request("tools/call", {"name": "lixity_about", "arguments": argument})["result"]
    assert result["isError"] is True and "section" in result["content"][0]["text"]


@pytest.mark.parametrize(("argument", "hint"), [
    ({"project": "./synthetic-project"}, "local CLI"),
    ({"kind": None}, "kind must be"),
    ({"language": 42}, "supported language"),
    ({"language": "zz"}, "supported language"),
])
def test_mcp_dossier_drafts_rejects_options_outside_text_contract(argument, hint):
    result = _request("tools/call", {
        "name": "lixity_manuscript_dossier_drafts", "arguments": {"text": SAMPLE, **argument},
    })["result"]
    assert result["isError"] is True and hint in result["content"][0]["text"]


@pytest.mark.parametrize("invalid", ["dee", "", 42, None, True])
def test_mcp_language_errors_are_reported_instead_of_changing_profiles(invalid):
    tools = _request("tools/list")["result"]["tools"]
    for tool in tools:
        schema = tool["inputSchema"]
        language = schema["properties"].get("language")
        if language is None:
            continue
        assert language["enum"] == list(LANGUAGE_CHOICES)
        arguments = dict.fromkeys(schema.get("required", ()), SAMPLE)
        arguments["language"] = invalid
        result = _request("tools/call", {"name": tool["name"], "arguments": arguments})["result"]
        assert result["isError"] is True, tool["name"]
        assert "supported language" in result["content"][0]["text"], tool["name"]


@pytest.mark.parametrize(("options", "expected"), [
    ({}, "en"), ({"language": "generic"}, "generic"), ({"language": " DE "}, "de"), ({"language": "auto"}, "de"),
])
def test_mcp_analysis_preserves_explicit_and_default_profiles(options, expected):
    result = _request("tools/call", {
        "name": "lixity_analyze",
        "arguments": {"text": "## Licht\n\nIch bin hier und du bist dort. In der Stadt ist es hell.", **options},
    })["result"]
    assert not result.get("isError")
    assert json.loads(result["content"][0]["text"])["meta"]["language"] == expected


@pytest.mark.parametrize("severity", [2.9, True, "2", 0, 4])
def test_mcp_profile_rejects_coerced_or_unsupported_flag_levels(severity):
    tools = _request("tools/list")["result"]["tools"]
    tool = next(tool for tool in tools if tool["name"] == "lixity_profile")
    schema = tool["inputSchema"]["properties"]["flag_min_severity"]
    assert schema["enum"] == [*FingerprintThresholds.flag_severities, None]
    result = _request("tools/call", {
        "name": "lixity_profile", "arguments": {"text": SAMPLE, "flag_min_severity": severity},
    })["result"]
    assert result["isError"] is True
    assert "flag_min_severity" in result["content"][0]["text"]


@pytest.mark.parametrize(("state", "ready"), [
    ("running", True), ("starting", False), ("stopped", False), ("busy", False), ("unknown", None),
])
def test_service_status_tool_reuses_the_read_only_projection(monkeypatch, state, ready):
    from lixity import __version__, service

    observations = []

    def observe(manager, action, overrides):
        observations.append((manager.port, action, overrides))
        return {"state": state, "running_version": "0.1.0", "log": "PRIVATE_SERVICE_PATH"}

    monkeypatch.setenv("LIXITY_PORT", "8765")
    monkeypatch.setattr(service.ServiceManager, "control", observe)
    response = _request("tools/call", {"name": "lixity_service_status", "arguments": {"port": 8767}})
    assert not response["result"].get("isError")
    raw = response["result"]["content"][0]["text"]
    result = json.loads(raw)
    assert observations == [(8767, "status", {})]
    assert result["schema_version"] == "lixity-service-status/1"
    assert result["ok"] is (state != "unknown")
    assert result["running"] is ready and result["state"] == state and result["port"] == 8767
    assert result["installed_version"] == __version__
    assert result["running_version"] == ("0.1.0" if state in ("running", "starting") else None)
    assert "PRIVATE_SERVICE_PATH" not in raw


@pytest.mark.parametrize("arguments", [
    [], {}, {"port": True}, {"port": "8767"}, {"port": 8767.0}, {"port": 0}, {"port": 65536},
    {"port": 8767, "host": "PRIVATE_SERVICE_PATH"},
])
def test_service_status_tool_rejects_non_explicit_or_invalid_ports(monkeypatch, arguments):
    from lixity import service

    def forbidden(_port):
        pytest.fail("Invalid MCP arguments must not inspect a port")

    monkeypatch.setattr(service, "service_status", forbidden)
    response = _request("tools/call", {"name": "lixity_service_status", "arguments": arguments})
    assert response["result"]["isError"]
    assert "PRIVATE_SERVICE_PATH" not in response["result"]["content"][0]["text"]


def test_call_analyze_returns_metrics():
    response = _request(
        "tools/call", {"name": "lixity_analyze", "arguments": {"text": SAMPLE, "language": "en"}}
    )
    assert response["result"].get("isError", False) is False
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["meta"]["language"] == "en"
    assert "metrics" in payload


def test_call_profile_returns_paragraphs():
    response = _request(
        "tools/call", {"name": "lixity_profile", "arguments": {"text": SAMPLE, "language": "en"}}
    )
    assert response["result"].get("isError", False) is False
    payload = json.loads(response["result"]["content"][0]["text"])
    assert "paragraphs" in payload and "chapters" in payload


def test_mcp_text_analysis_does_not_inherit_working_directory_thresholds(tmp_path, monkeypatch):
    from lixity.status import FLAG_MIN_SEVERITY

    (tmp_path / "lixity.toml").write_text("min_chapters = 99\nflag_min_severity = 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    passages = (
        "The ferryman greeted the guests by the river.",
        "It rained. We waited. The water rose.",
        "The lantern made a faint arc above the water while Marta kept her hands on the rail "
        "and read the name painted on the ferry.",
    )
    text = "\n\n".join(f"## Chapter {number}\n\n" + " ".join([passage] * 35)
                       for number, passage in enumerate(passages, 1))

    def call(name, **arguments):
        response = _request("tools/call", {"name": name, "arguments": {"text": text, **arguments}})
        result = response["result"]
        assert not result.get("isError")
        return json.loads(result["content"][0]["text"])

    reference = call("lixity_fingerprint")
    matrix = call("lixity_outlier_matrix")
    assert reference["measured_cells"] == matrix["measured_cells"] > 0
    profile = call("lixity_profile")
    assert {paragraph["flag_min"] for paragraph in profile["paragraphs"]} == {int(FLAG_MIN_SEVERITY)}
    explicit = call("lixity_profile", flag_min_severity=1)
    assert {paragraph["flag_min"] for paragraph in explicit["paragraphs"]} == {1}


def test_call_extended_tools():
    for tool in ("lixity_pacing", "lixity_dialogue", "lixity_showing", "lixity_motifs", "lixity_characters", "lixity_fingerprint"):
        response = _request("tools/call", {"name": tool, "arguments": {"text": SAMPLE, "language": "en"}})
        assert response["result"].get("isError", False) is False, f"{tool} failed"
        assert len(response["result"]["content"][0]["text"]) > 0

    markers_res = _request("tools/call", {"name": "lixity_markers", "arguments": {"text": SAMPLE}})
    assert markers_res["result"].get("isError", False) is False

    outlier_res = _request(
        "tools/call",
        {"name": "lixity_outlier_matrix", "arguments": {"text": SAMPLE, "language": "en", "z_threshold": 1.0}},
    )
    assert outlier_res["result"].get("isError", False) is False
    outlier_payload = json.loads(outlier_res["result"]["content"][0]["text"])
    assert outlier_payload["schema_version"] == "lixity-outlier-matrix/1"
    assert isinstance(outlier_payload["cells"], list)


def test_outlier_matrix_reports_chapter_features_and_preserves_measured_zeroes():
    from lixity import api

    chapters = [
        "The ferryman greeted the guests by the river.",
        "The guests waited on the wooden dock, where the leaves of the old trees hung over the quiet water.",
        "It rained. We waited. The water rose.",
        "The captain turned the boat. We heard the bell.",
        "The lantern made a faint arc above the water while Marta kept her hands on the rail "
        "and read the name painted on the ferry.",
    ]
    text = "\n".join(f"## Chapter {number}\n\n" + " ".join([line] * 35)
                     for number, line in enumerate(chapters, 1))
    text += "\n\n## Short chapter\n\nA gate closed.\n"

    for cutoff in (0, 1, 4):
        response = _request("tools/call", {
            "name": "lixity_outlier_matrix", "arguments": {"text": text, "z_threshold": cutoff},
        })
        assert not response["result"].get("isError")
        result = json.loads(response["result"]["content"][0]["text"])
        reference = api.fingerprint(text, z_mild=cutoff, z_strong=4, project_config={})
        assert result["schema_version"] == "lixity-outlier-matrix/1"
        assert result["measured_cells"] == reference["measured_cells"]
        assert result["consistency"] == reference["consistency"]
        assert result["outliers_by_chapter"] == {
            chapter: len(features) for chapter, features in reference["deviations"].items()
        }
        rows = result["cells"]
        assert result["outlier_count"] == len(rows) > 0
        assert all(row["chapter"] != "6" and abs(row["z_star"]) >= cutoff for row in rows)
        assert [abs(row["z_star"]) for row in rows] == sorted(
            (abs(row["z_star"]) for row in rows), reverse=True,
        )
        for row in rows:
            assert round(row["z_star"], 2) == reference["deviations"][row["chapter"]][row["feature"]]
        if cutoff == 0:
            assert len(rows) == result["measured_cells"]
            assert any(row["z_star"] == 0 for row in rows)
        if cutoff == 1:
            sentence_length = next(row for row in rows if row["chapter"] == "5" and row["feature"] == "asl")
            assert sentence_length["value"] == 25.0
            assert sentence_length["median"] == 8.0
            assert sentence_length["mad"] == pytest.approx(17 / 3)


@pytest.mark.parametrize("cutoff", [-1, "1", True, float("inf"), float("nan")])
def test_outlier_matrix_rejects_invalid_thresholds(cutoff):
    response = _request("tools/call", {
        "name": "lixity_outlier_matrix", "arguments": {"text": SAMPLE, "z_threshold": cutoff},
    })
    assert response["result"]["isError"]
    assert "z_threshold" in response["result"]["content"][0]["text"]


def test_call_research_gaps_audits_archive(tmp_path):
    from lixity.research import api as research_api

    research_api.init(tmp_path, title="Gap Audit", language="en")
    research_api.create_claim(
        tmp_path,
        title="Unbacked claim",
        statement="The bridge opened in 1924.",
        confidence="hypothetical",
    )
    response = _request(
        "tools/call",
        {"name": "lixity_research_gaps", "arguments": {"project": str(tmp_path)}},
    )
    assert response["result"].get("isError", False) is False
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["schema_version"] == "research-gaps-local/1"
    assert payload["summary"]["unsupported_claims"] == 1
    assert payload["summary"]["unanchored_claims"] == 1


def test_prompts_list_and_get():
    list_res = _request("prompts/list")
    prompts = list_res["result"]["prompts"]
    names = [p["name"] for p in prompts]
    assert "manuscript_pacing_audit" in names
    assert "manuscript_dialogue_review" in names
    assert "manuscript_showing_triage" in names

    get_res = _request("prompts/get", {"name": "manuscript_pacing_audit", "arguments": {"text": SAMPLE, "language": "en"}})
    assert "messages" in get_res["result"]
    assert SAMPLE in get_res["result"]["messages"][0]["content"]["text"]


def test_call_rejects_missing_text():
    response = _request("tools/call", {"name": "lixity_analyze", "arguments": {}})
    assert response["result"]["isError"] is True


def test_call_rejects_unknown_tool():
    response = _request("tools/call", {"name": "lixity_delete_everything", "arguments": {}})
    assert response["result"]["isError"] is True


def test_unknown_method_is_protocol_error():
    response = _request("resources/list")
    assert response["error"]["code"] == -32601


def test_notifications_have_no_response():
    assert mcp.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_serve_roundtrip_over_stdio():
    script = "\n".join(
        [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "lixity_about", "arguments": {}},
                }
            ),
            "not json at all",
        ]
    )
    out = io.StringIO()
    assert mcp.serve(io.StringIO(script), out) == 0
    lines = [json.loads(line) for line in out.getvalue().strip().splitlines()]
    by_id = {entry.get("id"): entry for entry in lines}
    assert by_id[1]["result"]["serverInfo"]["name"] == "lixity"
    assert len(by_id[2]["result"]["tools"]) == 17
    assert "lixity" in by_id[3]["result"]["content"][0]["text"]
    assert lines[-1]["error"]["code"] == -32700


def _run_mcp_cli(*arguments, request=""):
    return subprocess.run(  # noqa: S603 -- fixed module and synthetic parser test inputs
        [sys.executable, "-m", "lixity", "mcp", *arguments],
        input=request, capture_output=True, text=True, timeout=10, check=False,
    )


def test_mcp_cli_help_advertises_only_the_stdio_interface():
    completed = _run_mcp_cli("--help")
    assert completed.returncode == 0 and not completed.stderr
    assert "usage: lixity mcp [-h]" in completed.stdout
    assert "tools/list" in completed.stdout and "prompts/list" in completed.stdout
    for argument in ("--project", "--language", "--json", "--output", "--z-mild", "[file]"):
        assert argument not in completed.stdout


@pytest.mark.parametrize("arguments", [["manuscript.md"], ["--project", "."], ["--json"]])
def test_mcp_cli_rejects_ignored_report_arguments(arguments):
    completed = _run_mcp_cli(*arguments)
    assert completed.returncode == 2 and not completed.stdout
    assert "unrecognized arguments" in completed.stderr


def test_mcp_cli_stdout_contains_only_protocol_responses():
    request = '{"jsonrpc":"2.0","id":1,"method":"ping"}\n'
    completed = _run_mcp_cli(request=request)
    assert completed.returncode == 0 and not completed.stderr
    assert json.loads(completed.stdout) == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_mcp_contract_documents_registered_tools_and_skill_points_to_discovery():
    root = Path(__file__).resolve().parent.parent
    contract = (root / "docs" / "AGENTS.md").read_text(encoding="utf-8")
    skill = (root / "skills" / "lixity" / "SKILL.md").read_text(encoding="utf-8")
    response = _request("tools/list")
    registered = [tool["name"] for tool in response["result"]["tools"]]
    assert all(f"`{name}`" in contract for name in registered)
    assert "docs/AGENTS.md#model-context-protocol-mcp-server" in skill
    assert "`tools/list`" in skill
