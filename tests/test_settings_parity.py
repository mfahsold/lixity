"""Settings preserve the mathematical threshold domain and exact values."""

import http.client
import json
import threading
from collections.abc import Iterator
from dataclasses import asdict
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from typing import Any

import pytest

from lixity.config import resolve_thresholds
from lixity.server import LixityServerHandler
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui.settings import settings_form


class NumberControls(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "input" and attributes.get("type") == "number":
            control_id = attributes["id"]
            assert control_id is not None
            self.inputs[control_id] = attributes


@pytest.fixture
def settings_server(tmp_path) -> Iterator[tuple[type[LixityServerHandler], Any]]:
    class SettingsHandler(LixityServerHandler):
        source_input = None
        workspace_root = str(tmp_path)
        exports_dir = str(tmp_path / "exports")
        research_dir = None
        language = "en"
        title = "Synthetic project"
        title_custom = True
        thresholds = FingerprintThresholds()

    SettingsHandler.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), SettingsHandler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
    thread.start()

    def post(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            connection.request("POST", "/api/settings", body=json.dumps(payload),
                               headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    try:
        yield SettingsHandler, post
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("payload", [{"language": "fr"}, {"title": "New synthetic title"}])
def test_unrelated_settings_preserve_wide_thresholds_and_exact_floats(settings_server, payload):
    handler, post = settings_server
    handler.thresholds = FingerprintThresholds(
        z_mild=8.123456789012345, z_strong=9.876543210987654,
        fdr_q=0.013000000000003, dim_score_threshold=0.123456789012345,
        fdr_method="by", min_chapters=7, flag_min_severity=3,
    )
    original = asdict(handler.thresholds)
    status, response = post(payload)
    assert status == 200, response
    assert response["ok"] is True
    assert asdict(handler.thresholds) == original
    if "language" in payload:
        assert handler.language == "fr"
    if "title" in payload:
        assert handler.title == "New synthetic title"


@pytest.mark.parametrize("values", [
    {"z_mild": 8, "z_strong": 9, "fdr_q": 0.013, "dim_score_threshold": 7.13},
    {"z_mild": 0, "z_strong": 0, "fdr_q": 0.000001, "dim_score_threshold": 0.000001},
    {"z_mild": 1e100, "z_strong": 1e100, "fdr_q": 0.9999999,
     "dim_score_threshold": 1e100, "min_chapters": 100, "fdr_method": "by"},
])
def test_settings_accept_the_core_threshold_domain(settings_server, values):
    handler, post = settings_server
    status, response = post(values)
    assert status == 200, response
    for name, value in values.items():
        assert getattr(handler.thresholds, name) == value


INVALID_VALUES = [
    {"z_mild": False}, {"z_strong": True}, {"fdr_q": False},
    {"dim_score_threshold": True}, {"z_mild": float("nan")},
    {"z_strong": float("inf")}, {"fdr_q": float("-inf")},
    {"dim_score_threshold": float("nan")}, {"z_mild": -0.001},
    {"z_mild": 4, "z_strong": 3}, {"fdr_q": 0}, {"fdr_q": 1},
    {"fdr_method": "invalid"}, {"dim_score_threshold": 0},
    {"flag_min_severity": True}, {"flag_min_severity": 2.5},
    {"flag_min_severity": 2.0}, {"flag_min_severity": 0},
    {"flag_min_severity": 4}, {"min_chapters": False}, {"min_chapters": 1},
    {"min_chapters": 2.5}, {"min_chapters": 2.0}, {"z_mild": "2.5"},
    {"z_mild": 10 ** 1000},
]


@pytest.mark.parametrize("values", INVALID_VALUES)
def test_settings_reject_invalid_thresholds_without_mutating_state(settings_server, values):
    handler, post = settings_server
    original_thresholds = handler.thresholds
    original_dashboard = handler.dashboard_html
    status, response = post({"language": "fr", "title": "Changed", **values})
    assert status == 400, response
    assert response["ok"] is False
    assert handler.thresholds is original_thresholds
    assert handler.language == "en"
    assert handler.title == "Synthetic project"
    assert handler.dashboard_html == original_dashboard


@pytest.mark.parametrize("values", INVALID_VALUES)
def test_core_and_configuration_reject_invalid_thresholds(values):
    with pytest.raises(ValueError):
        FingerprintThresholds(**values)
    with pytest.raises(ValueError):
        resolve_thresholds(project_config=values)


def test_rendered_values_round_trip_exact_floats_and_allow_the_core_domain():
    thresholds = FingerprintThresholds(
        z_mild=8.123456789012345, z_strong=9.876543210987654,
        fdr_q=0.013000000000003, dim_score_threshold=0.123456789012345,
    )
    controls = NumberControls()
    controls.feed(settings_form(None, "Synthetic project", "en", [("en", "English")], thresholds))
    for control_id, value in (
        ("set-z-mild", 8.123456789012345), ("set-z-strong", 9.876543210987654),
        ("set-fdr-q", 0.013000000000003), ("set-dim-threshold", 0.123456789012345),
    ):
        attributes = controls.inputs[control_id]
        assert float(attributes["value"]) == value
        assert attributes["step"] == "any"
        assert attributes["min"] == "0"
        if control_id != "set-fdr-q":
            assert "max" not in attributes
    assert controls.inputs["set-fdr-q"]["max"] == "1"
    assert controls.inputs["set-fdr-q"]["data-min-exclusive"] == "true"
    assert controls.inputs["set-fdr-q"]["data-max-exclusive"] == "true"
    assert controls.inputs["set-dim-threshold"]["data-min-exclusive"] == "true"
    assert "data-min-exclusive" not in controls.inputs["set-z-mild"]


def test_rendered_settings_submit_without_rounding_thresholds(settings_server):
    handler, post = settings_server
    handler.thresholds = FingerprintThresholds(
        z_mild=2.123456789012345, z_strong=3.876543210987654,
        fdr_q=0.013000000000003, dim_score_threshold=2.123456789012345,
        fdr_method="by", min_chapters=7,
    )
    original = asdict(handler.thresholds)
    handler.refresh()
    controls = NumberControls()
    controls.feed(handler.dashboard_html)
    payload = {name: float(controls.inputs[control_id]["value"]) for name, control_id in (
        ("z_mild", "set-z-mild"), ("z_strong", "set-z-strong"),
        ("fdr_q", "set-fdr-q"), ("dim_score_threshold", "set-dim-threshold"),
    )}
    status, response = post({"language": "fr", **payload})
    assert status == 200, response
    assert asdict(handler.thresholds) == original
