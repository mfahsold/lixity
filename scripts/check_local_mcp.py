"""Verify the local stdio handshake and a read-only tool call for each server."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Any

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18")
TIMEOUT = 10


def probe(command: list[str], name: str, tool: str) -> tuple[dict, str, int, dict]:
    """Exercise the same process boundary as an MCP client."""
    with subprocess.Popen(  # noqa: S603 - selected local executables and fixed server arguments
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8",
    ) as process:
        source, output = process.stdin, process.stdout
        if source is None or output is None:
            raise ValueError(f"{name} has no stdio pipes")
        messages: Queue[str | None] = Queue()

        def receive() -> None:
            try:
                for line in output:
                    messages.put(line)
            finally:
                messages.put(None)

        Thread(target=receive, daemon=True).start()
        sequence = 0

        def send(method: str, params: dict, *, request: bool = True) -> Any:
            nonlocal sequence
            message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
            if request:
                sequence += 1
                message["id"] = sequence
            source.write(json.dumps(message) + "\n")
            source.flush()
            if not request:
                return None
            deadline = time.monotonic() + TIMEOUT
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError(f"{name} timed out during {method}")
                try:
                    line = messages.get(timeout=remaining)
                except Empty:
                    raise ValueError(f"{name} timed out during {method}") from None
                if line is None:
                    raise ValueError(f"{name} closed stdout during {method}. Check its launcher and inputs.")
                try:
                    reply = json.loads(line)
                except ValueError:
                    raise ValueError(f"{name} emitted a non-JSON line during {method}") from None
                if not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0":
                    raise ValueError(f"{name} emitted invalid JSON-RPC during {method}")
                if reply.get("id") is None and "method" in reply:
                    continue
                if reply.get("id") != sequence or "result" not in reply:
                    raise ValueError(f"{name} did not return a successful response to {method}")
                return reply["result"]

        try:
            initialized = send("initialize", {
                "protocolVersion": PROTOCOL_VERSIONS[0], "capabilities": {},
                "clientInfo": {"name": "lixity-check-local-mcp", "version": "1"},
            })
            protocol = initialized["protocolVersion"]
            if protocol not in PROTOCOL_VERSIONS:
                raise ValueError(f"{name} negotiated a protocol version this check does not support")
            send("notifications/initialized", {}, request=False)
            inventory = send("tools/list", {})["tools"]
            if tool not in {entry["name"] for entry in inventory}:
                raise ValueError(f"{name} did not advertise {tool}")
            result = send("tools/call", {"name": tool, "arguments": {}})
            if result.get("isError"):
                raise ValueError(f"{name} reported a tool error for {tool}")
            payload = result.get("structuredContent")
            if payload is None:
                try:
                    payload = json.loads(result["content"][0]["text"])
                except (ValueError, KeyError, IndexError, TypeError):
                    raise ValueError(f"{name} returned an unreadable payload for {tool}") from None
            if not isinstance(payload, dict):
                raise ValueError(f"{name} did not return an object for {tool}")
            return initialized["serverInfo"], protocol, len(inventory), payload
        finally:
            source.close()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filmcraft-project", type=Path, help="Inspect a synthetic .fcproj through headless FilmCraft")
    args = parser.parse_args()
    try:
        info, protocol, count, about = probe([sys.executable, "-m", "lixity", "mcp"], "Lixity", "lixity_about")
        version = about["meta"]["version"]
        if info["name"] != "lixity" or version != info["version"]:
            raise ValueError("Lixity returned inconsistent build identities")
        print(f"Lixity {version} · MCP {protocol} · {count} tools · lixity_about OK")
        if args.filmcraft_project is not None:
            filmcraft = shutil.which("filmcraft-cli")
            project = args.filmcraft_project.resolve()
            if not filmcraft or not project.is_file() or project.suffix != ".fcproj":
                raise ValueError("FilmCraft needs filmcraft-cli on PATH and an existing .fcproj file")
            info, protocol, count, sequence = probe(
                [filmcraft, "--project", str(project), "mcp"], "FilmCraft", "sequence_inspect",
            )
            if not sequence.get("durationFrames"):
                raise ValueError("FilmCraft returned an empty sequence")
            print(f"FilmCraft {info['version']} · MCP {protocol} · {count} tools · {sequence['durationFrames']} frames")
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f"MCP check failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
