"""Minimal MCP server for Lixity (read-only, stdlib only).

Exposes the existing analysis API over JSON-RPC 2.0 on stdio following the
Model Context Protocol (``tools/list`` / ``tools/call``). No writes: manuscript
text travels only into the analysis functions and back as JSON.

Run: ``python -m lixity.mcp`` (one JSON-RPC message per line on stdin).
"""

from __future__ import annotations

import json
import sys
from typing import Any

from . import __version__
from . import api as _api

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "lixity"

_ABOUT_DESCRIPTION = (
    "Installed Lixity metadata: commands, configuration, languages, "
    "features and heuristic thresholds. No manuscript input needed."
)
_ANALYZE_DESCRIPTION = (
    "Corpus metrics for Markdown prose: words, sentences, readability, "
    "dialogue share, chapters and per-chapter style signals. "
    "Measurements support human review; they do not grade prose."
)
_PROFILE_DESCRIPTION = (
    "Paragraph tense/style profile with line anchors. "
    "flag_min_severity floors the paragraph flag cut (1|2|3)."
)

_TOOLS = (
    {
        "name": "lixity_about",
        "description": _ABOUT_DESCRIPTION,
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "lixity_analyze",
        "description": _ANALYZE_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown manuscript text."},
                "language": {
                    "type": "string",
                    "description": "Analysis language code (default en).",
                    "default": "en",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lixity_profile",
        "description": _PROFILE_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown manuscript text."},
                "language": {
                    "type": "string",
                    "description": "Analysis language code (default en).",
                    "default": "en",
                },
                "flag_min_severity": {
                    "type": ["integer", "null"],
                    "description": "Paragraph flag floor 1|2|3 (default: configured).",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
)

_ERROR_PARSE = -32700
_ERROR_INVALID_REQUEST = -32600
_ERROR_METHOD_NOT_FOUND = -32601
_ERROR_INVALID_PARAMS = -32602
_ERROR_INTERNAL = -32603


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _call_tool(name: str, arguments: Any) -> dict[str, Any]:
    """Run a read-only tool; returns an MCP content result (never raises)."""
    try:
        if name == "lixity_about":
            payload = _api.about()
        elif name == "lixity_analyze":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_analyze requires a text string."}],
                    "isError": True,
                }
            payload = _api.analyze(arguments["text"], str(arguments.get("language") or "en"))
        elif name == "lixity_profile":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_profile requires a text string."}],
                    "isError": True,
                }
            severity = arguments.get("flag_min_severity")
            payload = _api.profile(
                arguments["text"],
                str(arguments.get("language") or "en"),
                flag_min_severity=int(severity) if severity is not None else None,
            )
        else:
            return {
                "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True,
            }
    except Exception as exc:  # noqa: BLE001 -- tool isolation: failures become MCP isError results
        return {"content": [{"type": "text", "text": f"tool failed: {exc}"}], "isError": True}
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        return {
            "content": [{"type": "text", "text": f"unserializable result: {exc}"}],
            "isError": True,
        }
    return {"content": [{"type": "text", "text": text}]}


def handle_message(message: Any) -> dict[str, Any] | None:
    """Handle one decoded JSON-RPC message; None means 'no response'."""
    if not isinstance(message, dict):
        return _error(None, _ERROR_INVALID_REQUEST, "message must be an object")
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})
    if not isinstance(method, str):
        return (
            _error(request_id, _ERROR_INVALID_REQUEST, "missing method")
            if request_id is not None
            else None
        )

    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__},
            },
        )
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": list(_TOOLS)})
    if method == "tools/call":
        if not isinstance(params, dict):
            return _error(request_id, _ERROR_INVALID_PARAMS, "params must be an object")
        tool_name = params.get("name")
        if not isinstance(tool_name, str):
            return _error(request_id, _ERROR_INVALID_PARAMS, "tool name must be a string")
        return _response(request_id, _call_tool(tool_name, params.get("arguments", {})))
    if request_id is None:
        return None
    return _error(request_id, _ERROR_METHOD_NOT_FOUND, f"unknown method: {method}")


def serve(stdio_in: Any = None, stdio_out: Any = None) -> int:
    """Serve JSON-RPC over stdio until EOF; returns a process exit code."""
    stream_in = stdio_in if stdio_in is not None else sys.stdin
    stream_out = stdio_out if stdio_out is not None else sys.stdout
    for raw_line in stream_in:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response: dict[str, Any] | None = _error(None, _ERROR_PARSE, "invalid JSON")
        else:
            try:
                response = handle_message(message)
            except Exception as exc:  # noqa: BLE001 -- never kill the stdio loop on dispatch bugs
                request_id = message.get("id") if isinstance(message, dict) else None
                response = _error(request_id, _ERROR_INTERNAL, f"dispatch failed: {exc}")
        if response is not None:
            stream_out.write(json.dumps(response, ensure_ascii=False) + "\n")
            stream_out.flush()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
