"""Client transport aborts do not become processing failures or hide real errors."""

import io
import json
from contextlib import redirect_stderr

import pytest

from lixity.research import api
from lixity.server._base import ResponseMixin
from lixity.server.routes_nda import NdaRoutesMixin
from lixity.server.routes_research import ResearchRoutesMixin


class DisconnectWriter(io.BytesIO):
    def __init__(self, error, *, fail_at):
        super().__init__()
        self.error = error
        self.fail_at = fail_at
        self.attempts = 0

    def write(self, content):
        self.attempts += 1
        if self.attempts == self.fail_at:
            raise self.error
        return super().write(content)


class ResponseHarness(ResponseMixin):
    def __init__(self, writer):
        self.wfile = writer
        self.codes = []
        self.response_headers = {}
        self.close_connection = False
        self.debug = False
        self.command = "GET"
        self.path = "/synthetic"

    def send_response(self, code, message=None):
        self.codes.append(code)

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        self.wfile.write(b"synthetic headers\r\n\r\n")


@pytest.mark.parametrize("error_type", [BrokenPipeError, ConnectionResetError, ConnectionAbortedError])
@pytest.mark.parametrize("fail_at", [1, 2], ids=["headers", "body"])
def test_expected_client_abort_stops_one_response(error_type, fail_at):
    writer = DisconnectWriter(error_type(), fail_at=fail_at)
    response = ResponseHarness(writer)
    response._json({"ok": True, "text": "Synthetic café"})
    assert response.codes == [200]
    assert response.close_connection is True
    assert writer.attempts == fail_at


def test_non_transport_write_error_still_propagates():
    response = ResponseHarness(DisconnectWriter(OSError("Synthetic unexpected write failure"), fail_at=2))
    with pytest.raises(OSError, match="unexpected write failure"):
        response._json({"ok": True})
    assert response.close_connection is False


def test_response_preparation_failure_is_not_mistaken_for_client_abort():
    class FailedPreparation(ResponseHarness):
        def send_response(self, code, message=None):
            raise BrokenPipeError("Synthetic logging pipe failed before transport")

    response = FailedPreparation(io.BytesIO())
    with pytest.raises(BrokenPipeError, match="before transport"):
        response._json({"ok": True})


def test_abort_debug_message_is_generic_and_timestamped():
    response = ResponseHarness(DisconnectWriter(BrokenPipeError(), fail_at=2))
    response.debug = True
    output = io.StringIO()
    with redirect_stderr(output):
        response._json({"ok": True, "text": "Synthetic private-looking content"})
    assert "HTTP 200" in output.getvalue()
    assert "UTC] [server:debug]" in output.getvalue()
    assert "Synthetic private-looking content" not in output.getvalue()


def test_normal_response_keeps_its_headers_and_unicode_json():
    writer = io.BytesIO()
    response = ResponseHarness(writer)
    response._json({"ok": True, "text": "Synthetic café"})
    body = writer.getvalue().split(b"\r\n\r\n", 1)[1]
    assert json.loads(body) == {"ok": True, "text": "Synthetic café"}
    assert response.response_headers == {
        "Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(body)),
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    }
    assert response.close_connection is False


def test_status_success_with_disconnected_client_never_attempts_backend_500(tmp_path, monkeypatch):
    project = tmp_path / "project"
    api.init(project, title="Synthetic status archive")

    class StatusResponse(ResearchRoutesMixin, ResponseHarness):
        research_dir = str(project)

    monkeypatch.setattr(api, "ocr_status", lambda: {"status": "synthetic"})
    response = StatusResponse(DisconnectWriter(BrokenPipeError(), fail_at=2))
    response._handle_research_status()
    assert response.codes == [200]
    assert response.close_connection is True


def test_status_processing_error_still_returns_backend_500(tmp_path, monkeypatch):
    project = tmp_path / "project"
    api.init(project, title="Synthetic status archive")

    class StatusResponse(ResearchRoutesMixin, ResponseHarness):
        research_dir = str(project)

    def unreadable(*args, **kwargs):
        raise OSError("Synthetic archive cannot be read")

    monkeypatch.setattr(api, "ocr_status", lambda: {"status": "synthetic"})
    monkeypatch.setattr(api, "project_overview", unreadable)
    writer = io.BytesIO()
    response = StatusResponse(writer)
    response._handle_research_status()
    assert response.codes == [500]
    body = json.loads(writer.getvalue().split(b"\r\n\r\n", 1)[1])
    assert body == {"ok": False, "message": "Synthetic archive cannot be read"}


@pytest.mark.parametrize("output", ["pdf", "text"])
def test_download_client_abort_uses_the_same_boundary(tmp_path, output):
    (tmp_path / "lixity.toml").write_text('language="en"\n[nda]\n', encoding="utf-8")

    class DownloadResponse(NdaRoutesMixin, ResponseHarness):
        workspace_root = str(tmp_path)

    response = DownloadResponse(DisconnectWriter(ConnectionResetError(), fail_at=2))
    response.dashboard_info = {"language_key": "en"}
    response._handle_nda_draft({"name": "Synthetic Reader", "project_name": "Synthetic project",
                              "date": "2026-10-06", "place": "Synthetic city", "format": output})
    assert response.codes == [200]
    assert response.close_connection is True
    assert response.response_headers["Content-Disposition"] == f'attachment; filename="nda.{"pdf" if output == "pdf" else "txt"}"'
    assert response.response_headers["Content-Language"] == "en"
    assert response.response_headers["Cache-Control"] == "no-store"
