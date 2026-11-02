"""Workspace and research navigation tabs feature localized tooltips and titles."""

from html.parser import HTMLParser

import pytest

from lixity.ui.dashboard import render_dashboard
from lixity.ui.research_panel import render_research_panel
from lixity.workspace_labels import WORKSPACE_LABELS


class _Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tabs = []
        self.buttons = []
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if attr_dict.get("role") == "tab":
            self.tabs.append(attr_dict)
        if tag == "button":
            self.buttons.append(attr_dict)
        if tag in ("input", "select"):
            self.inputs.append(attr_dict)


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_research_tabs_have_localized_tooltips(language):
    labels = WORKSPACE_LABELS[language]
    html = render_research_panel(labels, read_only=False)
    parsed = _Elements()
    parsed.feed(html)
    
    research_keys = ("dossiers", "claims", "decisions", "review", "sources", "search", "grounding")
    for key in research_keys:
        matching = [tab for tab in parsed.tabs if tab.get("id") == f"research-tab-{key}"]
        assert len(matching) == 1, f"Missing tab research-tab-{key}"
        tab = matching[0]
        expected_help = labels[f"research_tab_{key}_help"]
        assert tab.get("data-help") == expected_help
        assert tab.get("title") == labels[f"research_tab_{key}"]


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_workspace_view_tabs_have_localized_tooltips(language):
    labels = WORKSPACE_LABELS[language]
    html = render_dashboard(
        chapters=[],
        paragraphs=[],
        labels=labels,
        controls=True,
        language_key=language,
    )
    parsed = _Elements()
    parsed.feed(html)

    for view in ("analysis", "research", "project"):
        matching = [tab for tab in parsed.tabs if tab.get("id") == f"tab-view-{view}"]
        assert len(matching) == 1, f"Missing view tab tab-view-{view}"
        tab = matching[0]
        expected_help = labels[f"workspace_{view}_help"]
        assert tab.get("data-help") == expected_help
        assert tab.get("title") == labels[f"workspace_{view}"]


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_research_controls_have_localized_tooltips_and_shortcuts(language):
    labels = WORKSPACE_LABELS[language]
    html = render_research_panel(labels, read_only=False)
    parsed = _Elements()
    parsed.feed(html)

    # Check search controls
    search_input = next(inp for inp in parsed.inputs if inp.get("id") == "r-search-query")
    assert search_input.get("data-help") == labels["research_search_query_help"]
    assert search_input.get("aria-keyshortcuts") == "Enter"

    search_btn = next(btn for btn in parsed.buttons if btn.get("id") == "r-search-btn")
    assert search_btn.get("data-help") == labels["research_search_action_help"]
    assert search_btn.get("aria-keyshortcuts") == "Enter"

    # Check filters
    filter_dossiers = next(inp for inp in parsed.inputs if inp.get("id") == "r-filter-dossiers")
    assert filter_dossiers.get("data-help") == labels["research_filter_dossiers_help"]
    assert filter_dossiers.get("aria-keyshortcuts") == "Escape"

    filter_sources = next(inp for inp in parsed.inputs if inp.get("id") == "r-filter-sources")
    assert filter_sources.get("data-help") == labels["research_filter_sources_help"]
    assert filter_sources.get("aria-keyshortcuts") == "Escape"

    # Check grounding controls
    ground_select = next(inp for inp in parsed.inputs if inp.get("id") == "r-ground-source-select")
    assert ground_select.get("data-help") == labels["research_ground_source_help"]
    assert ground_select.get("title") == labels["research_select_source"]

    ground_btn = next(btn for btn in parsed.buttons if btn.get("id") == "r-ground-btn")
    assert ground_btn.get("data-help") == labels["research_ground_action_help"]
    assert ground_btn.get("title") == labels["research_ground_action"]
    assert ground_btn.get("aria-keyshortcuts") == "Enter"

    # Check action buttons
    find_passage = next(btn for btn in parsed.buttons if btn.get("id") == "r-find-passage")
    assert find_passage.get("data-help") == labels["research_find_passage_help"]

    review_refresh = next(btn for btn in parsed.buttons if btn.get("id") == "r-review-refresh")
    assert review_refresh.get("data-help") == labels["research_review_refresh_help"]

    terms_refresh = next(btn for btn in parsed.buttons if btn.get("id") == "r-terms-refresh")
    assert terms_refresh.get("data-help") == labels["research_terms_refresh_help"]
