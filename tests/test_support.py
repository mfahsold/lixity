"""The shared loopback harness stays explicit, disposable and state-safe."""

from pathlib import Path

from lixity.server import LixityServerHandler
from tests.support import (
    HANDLER_STATE,
    LoopbackServer,
    Response,
    labels_for,
    make_handler,
    preserved_handler_state,
    snapshot_handler_state,
)


def test_make_handler_sets_defaults_without_touching_the_base_class(tmp_path: Path):
    before = snapshot_handler_state()
    handler = make_handler(tmp_path, source_input=tmp_path / "manuscript.md")
    assert handler.workspace_root == str(tmp_path)
    assert handler.source_input == str(tmp_path / "manuscript.md")
    assert handler.exports_dir == str(tmp_path / "exports")
    assert handler.research_dir is None
    assert handler.language == "en"
    assert handler.title is None
    assert handler.title_custom is False
    assert issubclass(handler, LixityServerHandler)
    assert snapshot_handler_state() == before


def test_preserved_handler_state_restores_every_covered_attribute():
    with preserved_handler_state() as original:
        LixityServerHandler.title = "Synthetic mutation"
        LixityServerHandler.language = "de"
        assert original["title"] != "Synthetic mutation"
    assert snapshot_handler_state() == original
    assert set(original) == set(HANDLER_STATE)


def test_loopback_server_round_trips_json_and_headers(tmp_path: Path):
    with LoopbackServer(make_handler(tmp_path)) as server:
        response = server.request("/api")
        assert isinstance(response, Response)
        assert response.status == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json["schema_version"] == "lixity-api-index/1"
        missing = server.request("/api/does-not-exist")
        assert missing.status == 404 and missing.json["ok"] is False


def test_labels_for_merges_language_and_workspace_labels():
    labels = labels_for("de")
    assert labels["app_suffix"]
    assert labels["research_dossier_claims_empty"] == "Keine Thesen mit diesem Dossier verknüpft."
