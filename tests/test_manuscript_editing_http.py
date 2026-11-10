"""Native-only editor routes use selected project identity and origin guards."""
from tests.support import LoopbackServer, make_handler


def test_edit_roundtrip_conflict_and_origin(tmp_path):
    source = tmp_path / "book.md"
    source.write_text("# Synthetic\n\nA quiet morning.\n")
    with LoopbackServer(make_handler(tmp_path, source_input=source)) as server:
        opened = server.request("/api/manuscript-edit").json
        assert opened["ok"]
        payload = {key: opened[key] for key in ("document", "revision")}
        payload.update(operation="a" * 32, text="Changed")
        assert server.request("/api/manuscript-edit", payload=payload, headers={"Origin": "https://evil.invalid"}).status == 403
        assert server.request("/api/manuscript-edit", payload=payload).status == 200
        assert source.read_text() == "Changed"
        payload.update(operation="b" * 32, text="Other tab")
        assert server.request("/api/manuscript-edit", payload=payload).status == 409
        assert source.read_text() == "Changed"
        assert server.request("/api/manuscript-edit", headers={"Origin": "https://evil.invalid"}).status == 403


def test_editor_not_exposed_without_selected_manuscript(tmp_path):
    with LoopbackServer(make_handler(tmp_path)) as server:
        assert server.request("/api/manuscript-edit").status == 400


def test_read_view_is_bound_to_acknowledged_source(tmp_path):
    source = tmp_path / "book.md"
    source.write_text("# Synthetic\n\nA quiet morning.\n")
    with LoopbackServer(make_handler(tmp_path, source_input=source)) as server:
        opened = server.request("/api/manuscript-edit").json
        url = f'/api/manuscript-view?document={opened["document"]}&revision={opened["revision"]}'
        response = server.request(url)
        assert response.status == 200
        assert f'data-editor-revision="{opened["revision"]}"' in response.body.decode()
        assert 'editor-bootstrap.js' not in response.body.decode()
        assert "frame-ancestors 'self'" in response.headers['content-security-policy']
        assert server.request(url, headers={"Origin": "https://evil.invalid"}).status == 403
        source.write_text("# Changed elsewhere\n")
        assert server.request(url).status == 409
        assert server.request(url.replace(opened['document'], '0' * 64)).status == 409


def test_read_view_rejects_source_changed_during_analysis(tmp_path, monkeypatch):
    source = tmp_path / "book.md"
    source.write_text("# Synthetic\n\nA quiet morning.\n")
    handler = make_handler(tmp_path, source_input=source)
    refresh = handler.refresh_when_source_changed

    def racing_refresh(cls):
        outcome = refresh()
        source.write_text("# External change during rendering\n")
        return outcome

    monkeypatch.setattr(handler, "refresh_when_source_changed", classmethod(racing_refresh))
    with LoopbackServer(handler) as server:
        opened = server.request("/api/manuscript-edit").json
        url = f'/api/manuscript-view?document={opened["document"]}&revision={opened["revision"]}'
        assert server.request(url).status == 409


def test_editor_recovery_query_rejects_unknown_and_duplicate_fields(tmp_path):
    source = tmp_path / "book.md"
    source.write_text("Synthetic", encoding="utf-8")
    with LoopbackServer(make_handler(tmp_path, source_input=source)) as server:
        assert server.request("/api/manuscript-edit?unknown=1").status == 400
        assert server.request("/api/manuscript-edit?recovery=a&recovery=b").status == 400
        assert server.request("/api/manuscript-edit?recovery=").status == 400
