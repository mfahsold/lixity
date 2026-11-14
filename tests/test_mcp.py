"""Protocol tests for the read-only MCP server (stdio JSON-RPC, no network)."""

import io
import json

from lixity import mcp

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
    ]
    assert names == expected
    for tool in response["result"]["tools"]:
        assert set(tool) == {"name", "description", "inputSchema"}


def test_call_about_returns_metadata():
    response = _request("tools/call", {"name": "lixity_about", "arguments": {}})
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["meta"]["tool"] == "lixity"
    assert "languages" in payload


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


def test_call_extended_tools():
    for tool in ("lixity_pacing", "lixity_dialogue", "lixity_showing", "lixity_motifs", "lixity_characters", "lixity_fingerprint"):
        response = _request("tools/call", {"name": tool, "arguments": {"text": SAMPLE, "language": "en"}})
        assert response["result"].get("isError", False) is False, f"{tool} failed"
        assert len(response["result"]["content"][0]["text"]) > 0

    markers_res = _request("tools/call", {"name": "lixity_markers", "arguments": {"text": SAMPLE}})
    assert markers_res["result"].get("isError", False) is False


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
    assert len(by_id[2]["result"]["tools"]) == 13
    assert "lixity" in by_id[3]["result"]["content"][0]["text"]
    assert lines[-1]["error"]["code"] == -32700
