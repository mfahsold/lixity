"""Inspect a stock WebKitGTK control and Lixity's offline sample under Xvfb."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

CONTROL_HEADING = "Stock WebKitGTK rendered this document"
CONTROL_BUTTON = "Visible WebKitGTK control"
EXAMPLE_BUTTON = "Try the example offline"
IMPORT_BUTTON = "Import and analyze manuscript"


def _control() -> None:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk, WebKit2

    content = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        f'<h1>{CONTROL_HEADING}</h1><button type="button">{CONTROL_BUTTON}</button></html>'
    ).encode()

    class ControlDocument(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    with ThreadingHTTPServer(("127.0.0.1", 0), ControlDocument) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        window = Gtk.Window(title="Stock WebKitGTK control")
        window.set_default_size(1000, 720)
        window.connect("destroy", Gtk.main_quit)
        view = WebKit2.WebView()
        window.add(view)
        window.show_all()
        view.load_uri(f"http://127.0.0.1:{server.server_port}/")
        Gtk.main()
        server.shutdown()


def _descendants(node: Any, depth: int = 0) -> Iterator[tuple[int, str, str, Any]]:
    if node is None or depth > 32:
        return
    try:
        name = node.name or ""
        role = node.getRoleName()
        if not name and role in ("heading", "paragraph", "static", "text"):
            try:
                text = node.queryText()
                name = text.getText(0, min(text.characterCount, 200)) or ""
            except NotImplementedError:
                pass
    except (LookupError, RuntimeError):
        return
    yield depth, role, name, node
    try:
        for index in range(node.childCount):
            yield from _descendants(node.getChildAtIndex(index), depth + 1)
    except (LookupError, RuntimeError):
        return


def _has_painted_detail(pixbuf: Any) -> bool:
    """Require contrasting pixels in a named control's rectangle, ignoring row padding."""
    data = pixbuf.get_pixels()
    stride = pixbuf.get_rowstride()
    channels = pixbuf.get_n_channels()
    row_bytes = pixbuf.get_width() * channels
    histogram = [0] * 256
    for offset in range(0, stride * pixbuf.get_height(), stride):
        for index in range(offset, offset + row_bytes, channels):
            grey = (data[index] + data[index + 1] + data[index + 2]) // 3
            histogram[grey] += 1
    # A few isolated pixels should not turn an otherwise blank capture into a pass.
    dark = next((tone for tone, count in enumerate(histogram) if count >= 8), None)
    light = next((tone for tone in range(255, -1, -1) if histogram[tone] >= 8), None)
    return dark is not None and light is not None and light - dark >= 32


def _click(node: Any, coordinates: int) -> None:
    try:
        action = node.queryAction()
        if action.nActions and action.doAction(0):
            return
    except (LookupError, NotImplementedError, RuntimeError):
        pass
    bounds = node.queryComponent().getExtents(coordinates)
    x = bounds.x + bounds.width // 2
    y = bounds.y + bounds.height // 2
    subprocess.run(  # noqa: S603 - fixed QA tool and coordinates from the isolated X11 session
        ["/usr/bin/xdotool", "mousemove", str(x), str(y), "click", "1"], check=True,
    )


def _observe(stage: str, output: Path, sample: Path) -> None:
    import gi
    import pyatspi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gtk

    Gtk.init_check()
    window = Gdk.get_default_root_window()
    if window is None:
        raise RuntimeError("No X11 display is available")
    width, height = window.get_width(), window.get_height()

    def save_evidence(name: str, rows: list[tuple[int, str, str, Any]]) -> None:
        (output / f"{name}.json").write_text(
            json.dumps([row[:3] for row in rows], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        screenshot = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
        if screenshot is not None:
            screenshot.savev(str(output / f"{name}.png"), "png", [], [])

    def wait_until_painted(name: str, label: str, *, button: bool = False) -> Any:
        deadline = time.monotonic() + 25
        rows = []
        while time.monotonic() < deadline:
            rows = list(_descendants(pyatspi.Registry.getDesktop(0)))
            for _, role, text, node in rows:
                if label not in text or (button and (role != "push button" or label != text)):
                    continue
                try:
                    state = node.getState()
                    if not state.contains(pyatspi.STATE_SHOWING) or (
                        button and not state.contains(pyatspi.STATE_SENSITIVE)
                    ):
                        continue
                    bounds = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
                    x, y = max(0, bounds.x), max(0, bounds.y)
                    w = min(bounds.x + bounds.width, width) - x
                    h = min(bounds.y + bounds.height, height) - y
                    if w > 0 and h > 0:
                        tile = Gdk.pixbuf_get_from_window(window, x, y, w, h)
                        if tile is not None and _has_painted_detail(tile):
                            save_evidence(name, rows)
                            print(json.dumps({"stage": name, "painted_label": label}), flush=True)
                            return node
                except (LookupError, NotImplementedError, RuntimeError):
                    continue
            time.sleep(0.25)
        save_evidence(name, rows)
        raise AssertionError(f"No visible painted {label!r} at {name}")

    if stage == "control":
        wait_until_painted("control", CONTROL_BUTTON, button=True)
        return

    expected = sample.read_bytes()
    heading = re.search(r"^## (.+)$", expected.decode(), re.MULTILINE)
    if heading is None:
        raise ValueError("The offline sample must have a chapter heading")
    _click(wait_until_painted("welcome", EXAMPLE_BUTTON, button=True), pyatspi.DESKTOP_COORDS)
    import_button = wait_until_painted("preview", IMPORT_BUTTON, button=True)
    projects = Path.home() / "Lixity"
    if any(projects.rglob("*")):
        raise AssertionError("The offline preview created project files before confirmation")
    _click(import_button, pyatspi.DESKTOP_COORDS)
    # A chapter label can only appear after the reader loads. The project title also appears in recents.
    wait_until_painted("reader", heading.group(1))
    manuscripts = list(projects.rglob("manuscript.md"))
    if len(manuscripts) != 1 or manuscripts[0].read_bytes() != expected:
        raise AssertionError("Expected one saved manuscript matching the bundled example byte for byte")
    print(json.dumps({"saved_bytes_match": True, "sha256": hashlib.sha256(expected).hexdigest()}))


if __name__ == "__main__":
    if sys.argv[1:] == ["control"]:
        _control()
    else:
        _observe(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))
