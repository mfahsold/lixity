"""Minimal MCP server for Lixity (read-only, stdlib only).

Exposes the existing analysis API over JSON-RPC 2.0 on stdio following the
Model Context Protocol (``tools/list`` / ``tools/call``, ``prompts/list`` / ``prompts/get``).
No writes: manuscript text travels only into the analysis functions and back as JSON.

Run: ``python -m lixity.mcp`` or ``lixity mcp`` (one JSON-RPC message per line on stdin).
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
_PACING_DESCRIPTION = (
    "Scene structure, pacing metrics, sticky sentences, rhythm_profile (asl_cv, asl_iqr, "
    "length_entropy), scene entry/exit hooks, and optional non-prescriptive genre reference corridor orientation."
)
_SCENES_DESCRIPTION = (
    "Scene-level measurements, entry/exit hook classification (dialogue/action/reflection/question), "
    "hook distribution, intra-scene dynamics (asl_shift, dialogue_shift, scene_dynamic), "
    "scene showing-vs-telling (filter_per_1000, sensory_per_1000), corpus pacing_plateaus, "
    "and heuristic implicit_breaks."
)
_CORRIDORS_DESCRIPTION = (
    "List optional non-prescriptive genre reference corridors (crime_thriller, literary, romance, speculative) "
    "and optionally orient a manuscript against one."
)
_DIALOGUE_DESCRIPTION = (
    "Quoted speech detection, speaker shares, dialogue-to-narrative distribution, "
    "dialogue_tags, adverbial_tags, indirect_speech, and voice_separation (dialogue vs. narrative prose)."
)
_SHOWING_DESCRIPTION = (
    "Sensory showing-vs-telling signals: sensory detail density vs perception filter verbs."
)
_MOTIFS_DESCRIPTION = (
    "Thematic motifs, repetition tracking, and local phrase echoes across chapters."
)
_CHARACTERS_DESCRIPTION = (
    "Cast presence, declared point-of-view (POV), character name mentions, "
    "and per-character dialogue voice profiles (character_voices) across chapters."
)
_MARKERS_DESCRIPTION = (
    "Extract embedded editorial review markers (pruefen, sachcheck, todo, achtung) with line anchors."
)
_FINGERPRINT_DESCRIPTION = (
    "Stylistic fingerprint: lexical richness, clause complexity, and reading ease reference."
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
    {
        "name": "lixity_pacing",
        "description": _PACING_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown manuscript text."},
                "language": {
                    "type": "string",
                    "description": "Analysis language code (default en).",
                    "default": "en",
                },
                "genre": {
                    "type": ["string", "null"],
                    "description": "Optional non-prescriptive genre reference corridor (crime_thriller, literary, romance, speculative).",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lixity_scenes",
        "description": _SCENES_DESCRIPTION,
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
        "name": "lixity_corridors",
        "description": _CORRIDORS_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": ["string", "null"], "description": "Optional Markdown manuscript text."},
                "genre": {
                    "type": ["string", "null"],
                    "description": "Optional non-prescriptive genre corridor key.",
                },
                "language": {
                    "type": "string",
                    "description": "Analysis language code (default en).",
                    "default": "en",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "lixity_dialogue",
        "description": _DIALOGUE_DESCRIPTION,
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
        "name": "lixity_showing",
        "description": _SHOWING_DESCRIPTION,
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
        "name": "lixity_motifs",
        "description": _MOTIFS_DESCRIPTION,
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
        "name": "lixity_characters",
        "description": _CHARACTERS_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown manuscript text."},
                "names": {
                    "type": ["array", "object", "null"],
                    "description": "Character names list or alias mapping (e.g. ['Matteo', 'Chiara']).",
                },
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
        "name": "lixity_markers",
        "description": _MARKERS_DESCRIPTION,
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Markdown manuscript text."},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lixity_fingerprint",
        "description": _FINGERPRINT_DESCRIPTION,
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
)

_PROMPTS = (
    {
        "name": "manuscript_pacing_audit",
        "description": "Analyze chapter pacing, sentence length distribution, and scene progression without rewriting prose.",
        "arguments": [
            {"name": "text", "description": "Markdown manuscript text", "required": True},
            {"name": "language", "description": "Analysis language code (default: en)", "required": False},
        ],
    },
    {
        "name": "manuscript_dialogue_review",
        "description": "Review dialogue-to-narration ratio, quoted speech balance, and character voices.",
        "arguments": [
            {"name": "text", "description": "Markdown manuscript text", "required": True},
            {"name": "language", "description": "Analysis language code (default: en)", "required": False},
        ],
    },
    {
        "name": "manuscript_showing_triage",
        "description": "Inspect sensory cues versus perception filter words to help the author deepen immediacy.",
        "arguments": [
            {"name": "text", "description": "Markdown manuscript text", "required": True},
            {"name": "language", "description": "Analysis language code (default: en)", "required": False},
        ],
    },
)


def _handle_prompt_pacing(arguments: dict[str, Any]) -> dict[str, Any]:
    text = arguments.get("text", "")
    lang = arguments.get("language") or "en"
    return {
        "description": "Examine chapter pacing and sentence cadence without rewriting prose.",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please analyze the prose pacing and sentence rhythms for this manuscript in {lang}. "
                        "Observe sentence length variations, scene hooks, and acceleration/deceleration. "
                        "Respect the author's creative intent: present observations as prompts for review, "
                        "not as quality scores or instructions to rewrite prose.\n\n"
                        f"Manuscript:\n{text}"
                    ),
                },
            }
        ],
    }


def _handle_prompt_dialogue(arguments: dict[str, Any]) -> dict[str, Any]:
    text = arguments.get("text", "")
    lang = arguments.get("language") or "en"
    return {
        "description": "Review dialogue-to-narration ratio and quoted speech balance.",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please review the dialogue-to-narration distribution for this manuscript in {lang}. "
                        "Examine dialogue percentage per chapter, character speech tags, and scene balance. "
                        "Treat statistical metrics as mirrors of structure, never as arbitrary target quotas.\n\n"
                        f"Manuscript:\n{text}"
                    ),
                },
            }
        ],
    }


def _handle_prompt_showing(arguments: dict[str, Any]) -> dict[str, Any]:
    text = arguments.get("text", "")
    lang = arguments.get("language") or "en"
    return {
        "description": "Inspect sensory cues versus perception filter words to deepen immediacy.",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": (
                        f"Please evaluate the sensory showing and perception filter signals in this manuscript ({lang}). "
                        "Highlight visceral details (sight, sound, tactile cues) and locate filter phrases ('she heard', 'he saw') "
                        "that may create narrative distance. Present these as artistic choices for the author to weigh.\n\n"
                        f"Manuscript:\n{text}"
                    ),
                },
            }
        ],
    }


_PROMPT_HANDLERS = {
    "manuscript_pacing_audit": _handle_prompt_pacing,
    "manuscript_dialogue_review": _handle_prompt_dialogue,
    "manuscript_showing_triage": _handle_prompt_showing,
}

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
    payload: Any
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
        elif name == "lixity_pacing":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_pacing requires a text string."}],
                    "isError": True,
                }
            genre = arguments.get("genre")
            payload = _api.pacing(
                arguments["text"],
                str(arguments.get("language") or "en"),
                genre=str(genre) if genre is not None else None,
            )
        elif name == "lixity_scenes":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_scenes requires a text string."}],
                    "isError": True,
                }
            payload = _api.scenes(
                arguments["text"],
                language=str(arguments.get("language") or "en"),
            )
        elif name == "lixity_corridors":
            args_dict = arguments if isinstance(arguments, dict) else {}
            text_arg = args_dict.get("text")
            genre_arg = args_dict.get("genre")
            payload = _api.corridors(
                text=str(text_arg) if text_arg is not None else None,
                genre=str(genre_arg) if genre_arg is not None else None,
                language=str(args_dict.get("language") or "en"),
            )
        elif name == "lixity_dialogue":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_dialogue requires a text string."}],
                    "isError": True,
                }
            payload = _api.dialogue(arguments["text"], str(arguments.get("language") or "en"))
        elif name == "lixity_showing":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_showing requires a text string."}],
                    "isError": True,
                }
            payload = _api.showing(arguments["text"], str(arguments.get("language") or "en"))
        elif name == "lixity_motifs":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_motifs requires a text string."}],
                    "isError": True,
                }
            payload = _api.motifs(arguments["text"], language=str(arguments.get("language") or "en"))
        elif name == "lixity_characters":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_characters requires a text string."}],
                    "isError": True,
                }
            names = arguments.get("names")
            if not names:
                names = ["Narrator"]
            payload = _api.characters(
                arguments["text"],
                names=names,
                language=str(arguments.get("language") or "en"),
            )
        elif name == "lixity_markers":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_markers requires a text string."}],
                    "isError": True,
                }
            payload = _api.markers(arguments["text"])
        elif name == "lixity_fingerprint":
            if not isinstance(arguments, dict) or not isinstance(arguments.get("text"), str):
                return {
                    "content": [{"type": "text", "text": "lixity_fingerprint requires a text string."}],
                    "isError": True,
                }
            payload = _api.fingerprint(arguments["text"], str(arguments.get("language") or "en"))
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
                "capabilities": {
                    "tools": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
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
    if method == "prompts/list":
        return _response(request_id, {"prompts": list(_PROMPTS)})
    if method == "prompts/get":
        if not isinstance(params, dict):
            return _error(request_id, _ERROR_INVALID_PARAMS, "params must be an object")
        prompt_name = params.get("name")
        if not isinstance(prompt_name, str) or prompt_name not in _PROMPT_HANDLERS:
            return _error(request_id, _ERROR_INVALID_PARAMS, f"unknown prompt: {prompt_name}")
        return _response(request_id, _PROMPT_HANDLERS[prompt_name](params.get("arguments", {})))
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
