"""Semantic renderer contracts for chronology and explicit authored relationships."""

from html.parser import HTMLParser

import pytest

from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if values.get("id"):
            self.ids[values["id"]] = (tag, values)


@pytest.mark.parametrize("locale", WORKSPACE_LABELS)
def test_research_feedback_controls_are_localized_and_selection_token_is_inert(locale):
    labels = WORKSPACE_LABELS[locale]
    context_marker = 'opaque<&"token'
    page = render_dashboard([], [], controls=True, labels=labels, research_context_token=context_marker)
    elements = Elements()
    elements.feed(page)
    assert elements.ids["research-manager"][1]["data-research-token"] == context_marker
    assert elements.ids["r-claims-timeline"][0] == "button"
    assert elements.ids["r-claims-list"][1]["aria-pressed"] == "true"
    assert elements.ids["research-claims-timeline"][0] == "div"
    assert elements.ids["r-find-passage"][0] == "button"
    assert elements.ids["r-relation-form"][0] == "form"
    assert elements.ids["r-relation-from"][0] == elements.ids["r-relation-to"][0] == "select"
    assert "disabled" in elements.ids["r-relation-save"][1]
    for key in ("research_timeline_hint", "research_relation_hint", "research_relation_compatibility"):
        assert labels[key] in page


def test_legacy_renderer_supplies_no_guessed_research_context():
    elements = Elements()
    elements.feed(render_dashboard([], [], controls=True))
    assert elements.ids["research-manager"][1]["data-research-token"] == ""
    assert "disabled" in elements.ids["r-relation-save"][1]
