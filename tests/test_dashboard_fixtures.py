"""Verify dashboard fixture parameterization, default caching, and legacy globals compatibility."""

import dashboard_fixtures
from dashboard_fixtures import SAMPLE, full_dashboard


def test_full_dashboard_caches_default_immutable_render(monkeypatch):
    dashboard_fixtures._DEFAULT_CACHE.clear()
    calls = 0
    original = dashboard_fixtures.render_dashboard

    def counted_render(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(dashboard_fixtures, "render_dashboard", counted_render)
    monkeypatch.setattr(dashboard_fixtures, "_DEFAULT_RENDER_DASHBOARD", counted_render)

    first = full_dashboard()
    second = full_dashboard()
    assert first == second
    assert calls == 1

    custom = full_dashboard(title="Custom Title")
    assert "Custom Title" in custom
    assert calls == 2


def test_full_dashboard_parameterizes_sample_append_and_render_overrides():
    html = full_dashboard(
        sample_text="## Custom Opening\n\nSynthetic harbor prose.",
        append_text="\n\n## Appended Chapter\n\nAppended synthetic sentence.",
        title="Parameterized Dashboard",
    )
    assert "Parameterized Dashboard" in html
    assert "Custom Opening" in html
    assert "Appended Chapter" in html
    assert SAMPLE.splitlines()[0] not in html


def test_full_dashboard_preserves_globals_monkeypatch_backwards_compatibility(monkeypatch):
    dashboard_fixtures._DEFAULT_CACHE.clear()
    original_render = full_dashboard.__globals__["render_dashboard"]
    monkeypatch.setitem(
        full_dashboard.__globals__,
        "SAMPLE",
        "## Legacy Global Chapter\n\nLegacy global prose.",
    )

    def wrapped_render(*args, **kwargs):
        return original_render(*args, **{**kwargs, "title": "Legacy Wrapped Title"})

    monkeypatch.setitem(full_dashboard.__globals__, "render_dashboard", wrapped_render)

    html = full_dashboard()
    assert "Legacy Wrapped Title" in html
    assert "Legacy Global Chapter" in html
