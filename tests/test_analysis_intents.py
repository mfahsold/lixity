"""Author intentions only change through a guarded, project-local write."""

import json
from urllib.parse import urlencode

import pytest

from lixity.io import FileUtils
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.site_export import prepare_site
from tests.support import LoopbackServer, make_handler

ROUTE = "/api/analysis-intents"
STATE = ".lixity/analysis-intents.json"
OPENING = "## Arrival\n\nEva knocked and then waited by the door.\n"
MANUSCRIPT = OPENING + '\n---\n\n"I know the way," said Jo.\n'
NOTE = "Let the answer wait until Jo is asked twice."


@pytest.fixture
def project(tmp_path):
    (tmp_path / "manuscript.md").write_text(MANUSCRIPT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n', encoding="utf-8")
    handler = make_handler(tmp_path, source_input=tmp_path / "manuscript.md")
    handler.refresh()
    return tmp_path, handler


def _context_token(handler):
    return manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                language=handler.language, title=handler.title, thresholds=handler.thresholds)


def _read(server, token):
    response = server.request(ROUTE + "?" + urlencode({"project_token": token}))
    assert response.status == 200, response.body
    return response.json


def _write_payload(token, view, action="save", **fields):
    return {"project_token": token, "action": action,
            "expected_source_sha256": view["source_sha256"],
            "expected_analysis_sha256": view["analysis_sha256"],
            "expected_intents_sha256": view["intents_sha256"], **fields}


def _write(server, payload):
    response = server.request(ROUTE, payload=payload)
    assert response.status == 200, response.body
    return response.json


def test_author_cards_preview_and_explicit_order_are_project_local(project):
    root, handler = project
    token = _context_token(handler)
    with LoopbackServer(handler) as server:
        first = _read(server, token)
        assert first["schema_version"] == "lixity-analysis-intents/1"
        assert first["cards"] == []
        assert not (root / STATE).exists()
        save = _write_payload(token, first, kind="question", scene_id="1:1", intent=NOTE,
                              hypothesis="A doubt stays open", voice="Eva")
        assert server.request(ROUTE, payload={**save, "scene_id": "2:8"}).status == 400
        first = _write(server, save)
        assert server.request(ROUTE, payload=save).status == 409
        first_id = first["cards"][0]["id"]
        assert first["cards"][0] == {"id": first_id, "kind": "question", "scene_id": "1:1", "scene_title": "Arrival · 1",
                                     "intent": NOTE, "hypothesis": "A doubt stays open", "voice": "Eva",
                                     "review_status": "current", "scene_available": True}
        second = _write(server, _write_payload(token, first, kind="reveal", scene_id="1:2", intent="Jo answers."))
        second_id = second["cards"][1]["id"]
        assert [card["id"] for card in _read(server, token)["cards"]] == [first_id, second_id]
        order = _write_payload(token, second, "save_order", ids=[second_id, first_id])
        for invalid in ([second_id], [second_id, second_id]):
            assert server.request(ROUTE, payload={**order, "ids": invalid}).status == 400
        ordered = _write(server, order)
        assert [card["id"] for card in ordered["cards"]] == [second_id, first_id]
        assert ordered == _read(server, token)
        assert (root / "manuscript.md").read_text(encoding="utf-8") == MANUSCRIPT
        state = json.loads((root / STATE).read_bytes())
        assert state["schema_version"] == "lixity-analysis-intents-state/1"
        assert [card["scene_id"] for card in state["cards"]] == ["1:2", "1:1"]
        assert all(card["source_path"] == "manuscript.md" for card in state["cards"])

        bundle = prepare_site(root)
        assert STATE not in bundle.files
        assert all(NOTE.encode() not in content for content in bundle.files.values())
        assert not any(b'id="scene-rehearsal"' in content for content in bundle.files.values())

        deleted = _write(server, _write_payload(token, ordered, "delete", id=second_id))
        assert [card["id"] for card in deleted["cards"]] == [first_id]


def test_retaining_and_explicitly_reviewing_a_stale_card(project):
    root, handler = project
    token = _context_token(handler)
    source = root / "manuscript.md"
    with LoopbackServer(handler) as server:
        result = _write(server, _write_payload(token, _read(server, token),
                        kind="turning_point", scene_id="1:2", intent=NOTE))
        stored = (root / STATE).read_bytes()
        source.write_text(OPENING, encoding="utf-8")
        url = ROUTE + "?" + urlencode({"project_token": token})
        assert server.request(url).status == 409
        handler.refresh()
        stale = _read(server, token)
        card = stale["cards"][0]
        assert card["review_status"] == "stale"
        assert card["scene_available"] is False
        assert card["scene_id"] == "1:2"
        assert (root / STATE).read_bytes() == stored
        review = _write_payload(token, stale, id=card["id"], kind=card["kind"],
                                scene_id="1:1", intent=card["intent"])
        assert server.request(ROUTE, payload={**review, "expected_source_sha256": result["source_sha256"]}).status == 409
        reviewed = _write(server, review)
        assert reviewed["cards"][0]["id"] == card["id"]
        assert reviewed["cards"][0]["review_status"] == "current"
        assert source.read_text(encoding="utf-8") == OPENING

        settings = root / "lixity.toml"
        settings.write_text(settings.read_text(encoding="utf-8") + '\n[scene_analysis.titles]\n"1:1" = "Door"\n',
                            encoding="utf-8")
        new_token = _context_token(handler)
        assert server.request(ROUTE + "?" + urlencode({"project_token": new_token})).status == 409
        handler.refresh()
        relabeled = _read(server, new_token)
        assert relabeled["source_sha256"] == reviewed["source_sha256"]
        assert relabeled["analysis_sha256"] != reviewed["analysis_sha256"]
        assert relabeled["cards"][0]["review_status"] == "stale"


def test_context_binding_and_manuscript_change_during_save(project, monkeypatch):
    root, handler = project
    token = _context_token(handler)
    source = root / "manuscript.md"
    with LoopbackServer(handler) as server:
        before = _read(server, token)
        url = ROUTE + "?" + urlencode({"project_token": token})
        assert server.request(url, headers={"Origin": "https://other.invalid"}).status == 403
        assert server.request(ROUTE + "?project_token=" + "0" * 64).status == 409
        save = _write_payload(token, before, scene_id="1:1", kind="resolution", intent=NOTE)
        assert server.request(ROUTE, payload={**save, "effect_score": 5}).status == 400

        original_write = FileUtils.atomic_write_bytes_if_changed

        def write_with_external_revision(path, content, *, before_replace):
            def change_source_then_check():
                source.write_text(MANUSCRIPT + "\nThe house was empty.\n", encoding="utf-8")
                before_replace()

            return original_write(path, content, before_replace=change_source_then_check)

        monkeypatch.setattr(FileUtils, "atomic_write_bytes_if_changed", staticmethod(write_with_external_revision))
        assert server.request(ROUTE, payload=save).status == 409
        assert not (root / STATE).exists()


@pytest.mark.parametrize("without_measurements", ["empty_text", "invalid_scene_settings"])
def test_saved_cards_remain_available_without_measured_scenes(project, without_measurements):
    root, handler = project
    with LoopbackServer(handler) as server:
        token = _context_token(handler)
        saved = _write(server, _write_payload(token, _read(server, token), kind="question",
                                             scene_id="1:1", intent=NOTE))
        state_bytes = (root / STATE).read_bytes()
        if without_measurements == "empty_text":
            (root / "manuscript.md").write_text("", encoding="utf-8")
        else:
            config = root / "lixity.toml"
            config.write_text(
                config.read_text(encoding="utf-8")
                + '\n[scene_analysis.assignments]\n"99:1" = "register"\n[scene_analysis.groups.register]\n',
                encoding="utf-8",
            )
        handler.refresh()
        view = _read(server, _context_token(handler))
        card, = view["cards"]
        assert card["id"] == saved["cards"][0]["id"]
        assert card["review_status"] == "stale" and card["scene_available"] is False
        assert (root / STATE).read_bytes() == state_bytes
        page = server.request("/").body
        assert page.count(b'id="scene-rehearsal"') == 1
        assert b'class="panel-disclosure scene-intent-editor-unavailable"' in page
        assert NOTE.encode() not in page  # Local author content is loaded by the guarded endpoint.


def test_storage_may_not_overwrite_the_selected_manuscript(tmp_path):
    source = tmp_path / STATE
    source.parent.mkdir()
    original = b'{"schema_version":"lixity-analysis-intents-state/1","cards":[]}'
    source.write_bytes(original)
    handler = make_handler(tmp_path, source_input=source)
    handler.refresh()
    token = _context_token(handler)
    with LoopbackServer(handler) as server:
        view = _read(server, token)
        scene, = handler.dashboard_info["scene_intent_context"].scenes
        save = _write_payload(token, view, scene_id=scene, kind="question", intent=NOTE)
        assert server.request(ROUTE, payload=save).status == 400
    assert source.read_bytes() == original
