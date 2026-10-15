"""The served dashboard rebuilds itself when the manuscript changed on disk."""

from pathlib import Path

from lixity.server import _state
from lixity.server.views import build_server_dashboard
from tests.support import LoopbackServer, make_handler, preserved_handler_state


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
