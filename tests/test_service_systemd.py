"""Optional real Linux user-manager checks with isolated synthetic state."""

import socket
import urllib.request

import pytest

from lixity.service import ServiceManager


def test_systemd_owned_lifecycle_preserves_literal_dollar_and_unicode_data(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    app = ServiceManager(port, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                         backend="systemd", startup_timeout=30, stop_timeout=10)
    if not app._systemd_available():
        pytest.skip("Requires a compatible active Linux systemd user manager")
    project = tmp_path / "A book – Grüße ${LIXITY_TEST_DO_NOT_EXPAND}"
    project.mkdir()
    source = project / "manuscript.md"
    source.write_text("# Synthetic manuscript\n\n## Opening\n\nEin Vogel fliegt über den Garten.\n", encoding="utf-8")
    title = "Literal ${LIXITY_TEST_DO_NOT_EXPAND} – Grüße"
    before = source.read_bytes()
    try:
        started = app.control("start", {"project": str(project), "language": "de", "title": title})
        assert started["ok"] and started["backend"] == "systemd", started
        assert app.control("status", {})["ok"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as response:
            page = response.read().decode("utf-8")
        assert "<h1>" + title + "</h1>" in page
        assert 'id="manuscript-pdf-form"' in page
        assert source.read_bytes() == before
        stopped = app.control("stop", {})
        assert stopped["ok"] and stopped["state"] == "stopped", stopped
        assert not app.runtime_file.exists()
    finally:
        app.control("stop", {})
