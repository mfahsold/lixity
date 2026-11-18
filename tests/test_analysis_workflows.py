"""Workflow routes include available analysis sections without hiding report content."""

from html.parser import HTMLParser

from lixity.ui.analysis_navigation import render_analysis_workflows


class WorkflowMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "button":
            self.buttons.append(attributes)
        if "hidden" in attributes:
            self.hidden.append(attributes)


def test_workflows_route_only_to_available_panels_and_keep_no_script_content_readable():
    html = render_analysis_workflows([("flags", "panel_flags"), ("style", "group_style"),
                                     ("pacing", "panel_pacing")], {})
    parser = WorkflowMarkup()
    parser.feed(html)
    workflows = [button for button in parser.buttons if "data-analysis-workflow" in button]
    targets = [button["data-analysis-section-target"] for button in parser.buttons
               if "data-analysis-section-target" in button]
    assert [button["data-analysis-workflow"] for button in workflows] == ["review", "compare", "explore"]
    assert targets == ["flags", "style", "pacing"]
    assert parser.hidden == []


def test_workflow_labels_are_escaped():
    html = render_analysis_workflows([("flags", "panel_flags")], {"workflow_review": "<Review>"})
    assert "&lt;Review&gt;" in html
    assert "<Review>" not in html


def test_native_workflow_includes_an_available_empty_marker_panel():
    from lixity.models import CorpusConfig
    from lixity.pipeline import analyze_document
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui import render_dashboard

    analysis = analyze_document("## Main\n\n" + "A quiet reader waits. " * 30,
                                CorpusConfig(language="en"), FingerprintThresholds())
    page = render_dashboard(analysis.chapters, analysis.paragraphs, markers=[], controls=True)
    assert 'data-analysis-section-target="markers"' in page
    assert 'id="markers"' in page
    without_markers = render_dashboard(analysis.chapters, analysis.paragraphs, controls=True)
    assert 'data-analysis-section-target="markers"' not in without_markers
