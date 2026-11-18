"""Synthetic regressions for analysis identity and prepared render inputs."""

import importlib
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.pipeline import analyze_document, resolve_document_config
from lixity.research import api as research_api
from lixity.research.analysis import analyze
from lixity.style_fingerprint import FingerprintThresholds

SOURCE = "## One\n\n" + "A quiet visitor reads beside the window. " * 25


def test_archived_source_identity_survives_html_without_optional_context(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source = tmp_path / "source.md"
    source.write_text(SOURCE)
    research_api.init(project, title="Synthetic")
    retained = research_api.ingest(project, source, allow_retention=True)
    result = analyze(project, retained["source_id"])
    assert result.report_data["interpretation"]["scope"] == "source_internal"
    assert 'data-analysis-scope="source_internal"' in result.dashboard_html
    assert 'data-context-status="user_supplied_unverified"' in result.dashboard_html
    assert retained["source_id"] in result.dashboard_html
    assert retained["source_version_id"] in result.dashboard_html


def test_prepared_facade_never_recomputes_paragraph_statistics() -> None:
    from lixity.ui import render_analysis

    config, resolved = resolve_document_config(SOURCE, "en", project_config={})
    analysis = analyze_document(SOURCE, config, FingerprintThresholds())
    with patch("lixity.style_fingerprint.layer_stats", side_effect=AssertionError("recomputed")), \
         patch("lixity.ui.dashboard.layer_stats", side_effect=AssertionError("recomputed"), create=True):
        assert "<html" in render_analysis(analysis, resolved, title="Synthetic", flag_min_severity=2)


def test_native_render_bundle_cache_is_warm_on_second_render() -> None:
    ui = importlib.import_module("lixity.ui.dashboard")
    ui._bundle.cache_clear()
    ui.render_dashboard([], [], controls=True)
    first = ui._bundle.cache_info()
    ui.render_dashboard([], [], controls=True)
    second = ui._bundle.cache_info()
    assert second.misses == first.misses
    assert second.hits >= first.hits + 3


def test_facade_has_no_unchecked_keyword_passthrough() -> None:
    from lixity.ui import render_analysis

    assert all(parameter.kind is not inspect.Parameter.VAR_KEYWORD
               for parameter in inspect.signature(render_analysis).parameters.values())


def test_render_identity_is_typed_and_cannot_silently_lose_source_provenance() -> None:
    from lixity.ui.render_contracts import AnalysisIdentity

    with pytest.raises(ValueError):
        AnalysisIdentity(scope="source_internal")
    identity = AnalysisIdentity(scope="source_internal", context_status="user_supplied_unverified",
                                source_id="synthetic-source", source_version_id="synthetic-version")
    assert identity.scope == "source_internal"


def test_source_title_cannot_override_the_backend_analysis_identity() -> None:
    from lixity.ui import render_analysis
    from lixity.ui.render_contracts import AnalysisIdentity, DashboardContent

    config, resolved = resolve_document_config(SOURCE, "en", project_config={})
    analysis = analyze_document(SOURCE, config, FingerprintThresholds())
    page = render_analysis(analysis, resolved, title='<img src=x onerror="bad()">', flag_min_severity=2,
                           content=DashboardContent(identity=AnalysisIdentity(
                               scope="source_internal", context_status="user_supplied_unverified",
                               source_id="<source>", source_version_id="version&one")))
    assert 'data-analysis-scope="source_internal"' in page
    assert "&lt;source&gt;" in page and "version&amp;one" in page
    assert '<img src=x onerror="bad()">' not in page
