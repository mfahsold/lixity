"""Shared harness for disposable loopback servers and synthetic handler state.

Ten test modules used to start their own HTTP servers, define the same handler
attributes, hand-roll request plumbing and repeat save/restore blocks. Keep
those mechanics here so each test states only what it exercises.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from lixity.language import get_language_profile
from lixity.server import LixityServerHandler
from lixity.server._state import RefreshOutcome
from lixity.server.runtime import _LoopbackHTTPServer
from lixity.style_fingerprint import FingerprintThresholds
from lixity.workspace_labels import WORKSPACE_LABELS

#: Locales with complete language and workspace label packs.
LOCALES = ("en", "de", "fr", "es", "it", "pt", "nl")

#: Class attributes covered by the state guards and the handler factory.
HANDLER_STATE = (
    "workspace_root",
    "source_input",
    "exports_dir",
    "research_dir",
    "language",
    "title",
    "title_custom",
    "thresholds",
    "project_open_overrides",
    "dashboard_html",
    "dashboard_info",
    "refresh_outcome",
    "_refresh_needs_validation",
    "_speech_generation",
    "debug",
)

_NO_PAYLOAD = object()


class HtmlControls(HTMLParser):
    """Parse rendered control attributes without depending on HTML quoting/order."""

    def __init__(self, markup: str = "") -> None:
        super().__init__()
        self.elements: dict[str, dict[str, str | None]] = {}
        self.inputs: dict[str, dict[str, str | None]] = {}
        self.numbers: list[dict[str, str | None]] = []
        self.labels: set[str] = set()
        self.feed(markup)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            self.elements[identifier] = {**values, "tag": tag}
            if tag == "input":
                self.inputs[identifier] = values
                if values.get("type") == "number":
                    self.numbers.append(values)
        if tag == "label" and values.get("for"):
            self.labels.add(str(values["for"]))


def labels_for(locale: str) -> dict[str, str]:
    """Merged language and workspace labels for one locale."""
    return {**get_language_profile(locale).labels, **WORKSPACE_LABELS[locale]}


def snapshot_handler_state(names: tuple[str, ...] = HANDLER_STATE) -> dict[str, Any]:
    """Copy selected base-class handler attributes for later restoration."""
    return {name: getattr(LixityServerHandler, name) for name in names}


def restore_handler_state(snapshot: dict[str, Any]) -> None:
    """Restore attributes captured by :func:`snapshot_handler_state`."""
    for name, value in snapshot.items():
        setattr(LixityServerHandler, name, value)


@contextlib.contextmanager
def preserved_handler_state(names: tuple[str, ...] = HANDLER_STATE) -> Iterator[dict[str, Any]]:
    """Snapshot base-class handler state and restore it afterwards."""
    original = snapshot_handler_state(names)
    try:
        yield original
    finally:
        restore_handler_state(original)


def monkeypatch_handler_state(monkeypatch: Any, names: tuple[str, ...] = HANDLER_STATE) -> None:
    """Register base-class handler state for pytest's automatic restoration."""
    for name in names:
        monkeypatch.setattr(LixityServerHandler, name, getattr(LixityServerHandler, name))


def make_handler(
    workspace_root: str | Path,
    *,
    source_input: str | Path | None = None,
    research_dir: str | Path | None = None,
    language: str = "en",
    title: str | None = None,
    title_custom: bool = False,
    thresholds: FingerprintThresholds | None = None,
    **attributes: Any,
) -> type[LixityServerHandler]:
    """Build a synthetic handler subclass with explicit loopback-safe defaults.

    Tests that need extra instance methods keep a hand-written subclass; the
    factory covers the attribute-only fixtures.
    """
    root = str(workspace_root)
    handler = type("SyntheticHandler", (LixityServerHandler,), {})
    defaults: dict[str, Any] = {
        "workspace_root": root,
        "source_input": str(source_input) if source_input is not None else None,
        "exports_dir": str(Path(root) / "exports"),
        "research_dir": str(research_dir) if research_dir is not None else None,
        "language": language,
        "title": title,
        "title_custom": title_custom,
        "thresholds": thresholds if thresholds is not None else FingerprintThresholds(),
        "project_open_overrides": {},
        "dashboard_html": "",
        "dashboard_info": {},
        "refresh_outcome": RefreshOutcome.UNKNOWN,
        "_refresh_needs_validation": False,
        "debug": False,
    }
    defaults.update(attributes)
    for name, value in defaults.items():
        setattr(handler, name, value)
    return handler


def recording_handler(workspace_root: str | Path, **attributes: Any) -> LixityServerHandler:
    """Run route methods directly with isolated class state and captured JSON."""
    def respond(self: Any, payload: Any, code: int = 200) -> None:
        self.response = code, payload

    handler = make_handler(workspace_root, _json=respond, **attributes)
    return object.__new__(handler)


@dataclass(frozen=True)
class Response:
    """One completed HTTP response from a synthetic loopback server."""

    status: int
    headers: dict[str, str]
    body: bytes

    @property
    def json(self) -> Any:
        return json.loads(self.body)


def send(
    port: int,
    path: str,
    *,
    method: str | None = None,
    payload: Any = _NO_PAYLOAD,
    body: str | bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> Response:
    """Send one request to a loopback port; ``payload`` is JSON and implies POST."""
    request_headers = dict(headers or {})
    if payload is not _NO_PAYLOAD:
        data: str | bytes | None = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
        method = method or "POST"
    else:
        data = body
        method = method or ("POST" if body is not None else "GET")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request(method, path, body=data, headers=request_headers)
        response = connection.getresponse()
        response_headers = {key.lower(): value for key, value in response.getheaders()}
        return Response(response.status, response_headers, response.read())
    finally:
        connection.close()


class LoopbackServer:
    """Disposable loopback HTTP server around one synthetic handler class."""

    def __init__(self, handler: type[LixityServerHandler]) -> None:
        self._server = _LoopbackHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )

    @property
    def port(self) -> int:
        return int(self._server.server_port)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> LoopbackServer:
        self._thread.start()
        return self

    def __enter__(self) -> LoopbackServer:
        return self.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def request(
        self,
        path: str,
        *,
        method: str | None = None,
        payload: Any = _NO_PAYLOAD,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> Response:
        """Send one request; a ``payload`` is encoded as JSON and implies POST."""
        return send(self.port, path, method=method, payload=payload, body=body,
                    headers=headers, timeout=timeout)

    def request_json(
        self,
        path: str,
        *,
        payload: Any = _NO_PAYLOAD,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, Any]:
        """Send one request and decode its JSON body."""
        response = self.request(path, payload=payload, headers=headers, timeout=timeout)
        return response.status, response.json
