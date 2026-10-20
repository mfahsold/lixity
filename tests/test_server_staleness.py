"""The served dashboard rebuilds itself when the manuscript changed on disk."""

from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from threading import Event

import pytest

from lixity.server import _state
from lixity.server.views import build_server_dashboard
from tests.support import LOCALES, LoopbackServer, labels_for, make_handler, preserved_handler_state


class _FreshnessNotice(HTMLParser):
    """Read the visible notice, rather than translated strings in script data."""

    def __init__(self, body: bytes) -> None:
        super().__init__()
        self.attributes: dict[str, str | None] = {}
        self.text = ""
        self.retry_href: str | None = None
        self._depth = 0
        self.feed(body.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id") == "dashboard-freshness":
            self.attributes = values
            self._depth = 1
        elif self._depth:
            self._depth += 1
            if tag == "a":
                self.retry_href = values.get("href")

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth:
            self.text += data


def _assert_notice(response, outcome: str, language: str, label_key: str) -> None:
    assert response.status == 200
    notice = _FreshnessNotice(response.body)
    assert notice.attributes.get("data-dashboard-freshness") == outcome
    assert "hidden" not in notice.attributes
    assert notice.attributes.get("role") == "status"
    assert labels_for(language)[label_key] in notice.text
    assert notice.retry_href == "/"


def _render_project(handler) -> dict:
    html, info = build_server_dashboard(
        str(handler.source_input),
        language=handler.language,
        controls=True,
        exports_dir=handler.exports_dir,
    )
    handler.publish_dashboard(html, info)
    return info


def test_served_dashboard_rebuilds_after_manuscript_edit(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text(
        "## Eins\n\nEr ging nach Hause. Sie blieb am Fenster stehen.\n", encoding="utf-8"
    )
    handler = make_handler(tmp_path, source_input=manuscript, language="de")
    info = _render_project(handler)
    assert info["chapters"] == 1

    with preserved_handler_state(), LoopbackServer(handler) as server:
        first = server.request("/")
        assert first.status == 200 and "Eins" in first.body.decode("utf-8")
        assert handler.dashboard_info["chapters"] == 1

        manuscript.write_text(
            "## Eins\n\nEr ging nach Hause. Sie blieb am Fenster stehen.\n\n"
            "## Zwei\n\nDer Regen fiel den ganzen Abend auf die leeren Straßen.\n",
            encoding="utf-8",
        )
        second = server.request("/")
        assert second.status == 200
        assert handler.dashboard_info["chapters"] == 2
        assert "Zwei" in second.body.decode("utf-8")


def test_unchanged_manuscript_serves_the_cache(tmp_path: Path, monkeypatch) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Eins\n\nEr ging nach Hause.\n", encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript, language="de")
    _render_project(handler)

    def forbidden(*args, **kwargs):
        raise AssertionError("An unchanged manuscript must serve the cache")

    monkeypatch.setattr(_state, "build_server_dashboard", forbidden)
    with preserved_handler_state(), LoopbackServer(handler) as server:
        response = server.request("/")
        assert response.status == 200 and "Eins" in response.body.decode("utf-8")


@pytest.mark.parametrize("language", LOCALES)
def test_removed_manuscript_keeps_last_good_analysis_with_localized_notice(
    tmp_path: Path, language: str,
) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Original\n\nThe river carries the small boat.\n", encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript, language=language)
    original_info = _render_project(handler)
    original_html = handler.dashboard_html
    manuscript.unlink()

    with LoopbackServer(handler) as server:
        response = server.request("/")
        _assert_notice(response, "missing", language, "status_source_missing")
        assert "The river carries the small boat." in response.body.decode("utf-8")
        assert handler.dashboard_html == original_html
        assert handler.dashboard_info == original_info


def test_unreadable_snapshot_keeps_cache_until_same_bytes_are_validated(
    tmp_path: Path, monkeypatch,
) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Original\n\nThe river carries the small boat.\n", encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript, language="de")
    original_info = _render_project(handler)
    original_html = handler.dashboard_html

    def unreadable(*args, **kwargs):
        raise OSError("private /source/location and exception detail")

    def forbidden(*args, **kwargs):
        raise AssertionError("Identical restored bytes must not rebuild the analysis")

    with LoopbackServer(handler) as server:
        with monkeypatch.context() as failure:
            failure.setattr(_state.FileUtils, "read_source_snapshot", unreadable)
            for _ in range(2):
                response = server.request("/")
                _assert_notice(response, "unreadable", "de", "status_source_unreadable")
                assert "private /source/location" not in response.body.decode("utf-8")
                assert handler.dashboard_html == original_html
                assert handler.dashboard_info == original_info
        monkeypatch.setattr(_state, "build_server_dashboard", forbidden)
        recovered = server.request("/")
        assert recovered.status == 200
        assert not _FreshnessNotice(recovered.body).attributes
        assert handler.dashboard_info == original_info


@pytest.mark.parametrize("restore_changed", [False, True])
def test_removed_manuscript_recovers_after_restoration(
    tmp_path: Path, restore_changed: bool,
) -> None:
    manuscript = tmp_path / "manuscript.md"
    original = "## Original\n\nThe river carries the small boat.\n"
    manuscript.write_text(original, encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript)
    original_hash = _render_project(handler)["manuscript_source_sha256"]

    with LoopbackServer(handler) as server:
        manuscript.unlink()
        _assert_notice(server.request("/"), "missing", "en", "status_source_missing")
        restored = original + "\n## Restored\n\nThe boat reaches the shore.\n" if restore_changed else original
        manuscript.write_text(restored, encoding="utf-8")
        response = server.request("/index.html")
        assert response.status == 200
        assert not _FreshnessNotice(response.body).attributes
        assert handler.dashboard_info["chapters"] == (2 if restore_changed else 1)
        assert (handler.dashboard_info["manuscript_source_sha256"] != original_hash) == restore_changed


def test_initially_missing_source_recovers_without_claiming_saved_analysis(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    handler = make_handler(tmp_path, source_input=manuscript)
    _render_project(handler)
    assert handler.dashboard_info["is_missing"] is True
    assert not handler.dashboard_info["manuscript_source_sha256"]

    with LoopbackServer(handler) as server:
        missing = server.request("/")
        assert missing.status == 200
        assert not _FreshnessNotice(missing.body).attributes
        manuscript.write_text("## Restored\n\nThe boat reaches the shore.\n", encoding="utf-8")
        restored = server.request("/")
        assert restored.status == 200
        assert "The boat reaches the shore." in restored.body.decode("utf-8")
        assert handler.dashboard_info["manuscript_source_sha256"]


def test_failed_rebuild_keeps_original_identity_until_render_succeeds(
    tmp_path: Path, monkeypatch,
) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Original\n\nThe river carries the small boat.\n", encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript)
    original_info = _render_project(handler)
    original_html = handler.dashboard_html
    manuscript.write_text("## Changed\n\nThe boat reaches the shore.\n", encoding="utf-8")

    def failed_render(*args, **kwargs):
        raise RuntimeError("private /render/location and exception detail")

    with LoopbackServer(handler) as server:
        with monkeypatch.context() as failure:
            failure.setattr(_state, "build_server_dashboard", failed_render)
            for _ in range(2):
                response = server.request("/")
                _assert_notice(response, "refresh-failed", "en", "status_refresh_failed")
                assert "The river carries the small boat." in response.body.decode("utf-8")
                assert "private /render/location" not in response.body.decode("utf-8")
                assert handler.dashboard_html == original_html
                assert handler.dashboard_info == original_info
            failed = server.request("/api/rebuild", payload={})
            assert failed.status == 500 and failed.json["ok"] is False
            assert "private /render/location" not in failed.json["message"]
            assert handler.dashboard_info == original_info
        recovered = server.request("/")
        assert recovered.status == 200
        assert not _FreshnessNotice(recovered.body).attributes
        assert "The boat reaches the shore." in recovered.body.decode("utf-8")
        assert handler.dashboard_info["manuscript_source_sha256"] != original_info["manuscript_source_sha256"]


def test_explicit_refresh_of_removed_source_preserves_last_good_cache(tmp_path: Path) -> None:
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Original\n\nThe river carries the small boat.\n", encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript)
    original_info = _render_project(handler)
    original_html = handler.dashboard_html
    manuscript.unlink()

    with LoopbackServer(handler) as server:
        response = server.request("/api/rebuild", payload={})
        assert response.status == 500 and response.json["ok"] is False
        assert str(tmp_path) not in response.json["message"]
        assert handler.dashboard_info == original_info
        assert handler.dashboard_html == original_html
        _assert_notice(server.request("/"), "missing", "en", "status_source_missing")


@pytest.mark.parametrize("recovery", ["changed", "same", "missing-then-same"])
def test_invalid_config_does_not_replace_last_good_analysis(
    tmp_path: Path, recovery: str,
) -> None:
    manuscript = tmp_path / "manuscript.md"
    original = "## Original\n\nThe river carries the small boat.\n"
    manuscript.write_text(original, encoding="utf-8")
    config = tmp_path / "lixity.toml"
    config.write_text('language = "en"\n', encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript)
    original_info = _render_project(handler)
    original_html = handler.dashboard_html
    manuscript.write_text("## Changed\n\nThe boat reaches the shore.\n", encoding="utf-8")
    config.write_text('language = [private invalid data\n', encoding="utf-8")

    with LoopbackServer(handler) as server:
        response = server.request("/")
        _assert_notice(response, "refresh-failed", "en", "status_refresh_failed")
        assert "private invalid data" not in response.body.decode("utf-8")
        assert handler.dashboard_info == original_info
        assert handler.dashboard_html == original_html
        if recovery != "changed":
            if recovery == "missing-then-same":
                manuscript.unlink()
                _assert_notice(server.request("/"), "missing", "en", "status_source_missing")
            manuscript.write_text(original, encoding="utf-8")
            _assert_notice(server.request("/"), "refresh-failed", "en", "status_refresh_failed")
        config.write_text('language = "en"\n', encoding="utf-8")
        recovered = server.request("/")
        assert recovered.status == 200
        assert not _FreshnessNotice(recovered.body).attributes
        expected = "The boat reaches the shore." if recovery == "changed" else "The river carries the small boat."
        assert expected in recovered.body.decode("utf-8")


def test_failed_old_source_check_cannot_mark_new_project_stale(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    manuscript = first / "manuscript.md"
    manuscript.write_text("## Original\n\nThe river carries the small boat.\n", encoding="utf-8")
    (second / "manuscript.md").write_text("## Second\n\nA lantern lights the room.\n", encoding="utf-8")
    handler = make_handler(first, source_input=manuscript)
    _render_project(handler)
    read_started, allow_read = Event(), Event()
    read_snapshot = _state.FileUtils.read_source_snapshot

    def delayed_snapshot(path, *args, **kwargs):
        if path == str(manuscript):
            read_started.set()
            assert allow_read.wait(5)
            raise OSError("old project snapshot unavailable")
        return read_snapshot(path, *args, **kwargs)

    monkeypatch.setattr(_state.FileUtils, "read_source_snapshot", delayed_snapshot)
    with LoopbackServer(handler) as server, ThreadPoolExecutor(max_workers=2) as pool:
        reading = pool.submit(server.request, "/")
        assert read_started.wait(5)
        switching = pool.submit(server.request, "/api/project-open", payload={"path": str(second)})
        allow_read.set()
        old_response = reading.result(timeout=10)
        opened = switching.result(timeout=10)
        assert opened.status == 200 and opened.json["ok"] is True
        current = server.request("/")
        assert current.status == 200
        assert "A lantern lights the room." in current.body.decode("utf-8")
        assert not _FreshnessNotice(current.body).attributes
        _assert_notice(old_response, "unreadable", "en", "status_source_unreadable")
        assert "A lantern lights the room." not in old_response.body.decode("utf-8")
