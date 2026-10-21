"""Declared chapter groups filter display without becoming a new reference."""

from copy import deepcopy
from html.parser import HTMLParser

from lixity.analyzer import CorpusAnalyzer
from lixity.characters import presence_report
from lixity.models import CorpusConfig
from lixity.style_fingerprint import StyleFingerprint
from lixity.ui.heatmap import render_heatmap_panel


class ScopeMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = {}
        self.rows = []
        self.options = {}
        self.select = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.elements[attrs["id"]] = attrs
        if tag == "select":
            self.select = attrs.get("id")
            self.options[self.select] = []
        if tag == "option" and self.select:
            self.options[self.select].append(attrs)
        if tag == "tr" and "data-fdr-count" in attrs:
            self.rows.append(attrs)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select = None


def comparison(*, registered=True):
    text = "\n\n".join(
        f"## Chapter {number}\n\n" + (("moss " * length).strip() + ". ") * 20
        for number, length in enumerate((8, 9, 10, 11, 70), 1)
    )
    name = 'Letters <img src=x onerror="alert(1)">'
    config = CorpusConfig(language="en", **({
        "register_profiles": {name: {}}, "chapter_registers": {"2": name, "4": name},
    } if registered else {}))
    metrics = CorpusAnalyzer(config).analyze_text(text)
    return text, config, metrics, StyleFingerprint.from_metrics(metrics, config=config)


def test_register_groups_keep_original_chapter_ids_and_scores():
    _, _, metrics, fingerprint = comparison()
    before = deepcopy(fingerprint.passport())
    markup = ScopeMarkup(render_heatmap_panel(fingerprint, metrics))
    assert "analysis-scope-register" in markup.elements
    assert "analysis-scope-pov" not in markup.elements
    assert [row["id"] for row in markup.rows] == [f"heatmap-ch-{n}" for n in (1, 2, 3, 4, 5)]
    assert [row["data-scope-register"] for row in markup.rows] == ["unassigned", "r-0", "unassigned", "r-0", "unassigned"]
    assert [item["value"] for item in markup.options["analysis-scope-register"]] == ["", "r-0", "unassigned"]
    assert fingerprint.passport() == before


def test_declared_pov_membership_is_separate_from_name_mentions():
    text, config, metrics, fingerprint = comparison(registered=False)
    name = 'Alex "<script>"'
    characters = presence_report(text, {"Alex": name, "moss": "Mention only"}, config,
                                declared_pov={name: [1, 3]})
    assert next(figure for figure in characters["figures"] if figure["name"] == name)["mentions"] == 0
    markup = ScopeMarkup(render_heatmap_panel(fingerprint, metrics, characters=characters))
    assert "analysis-scope-pov" in markup.elements
    assert "analysis-scope-register" not in markup.elements
    assert [item["value"] for item in markup.options["analysis-scope-pov"]] == ["", "p-0"]
    assert [row["data-scope-pov"] for row in markup.rows] == ["p-0", "", "p-0", "", ""]


def test_no_declared_groups_adds_no_display_controls():
    _, _, metrics, fingerprint = comparison(registered=False)
    html = render_heatmap_panel(fingerprint, metrics)
    assert 'id="analysis-scope"' not in html
    assert 'id="heatmap-fdr-only"' in html


def test_overlap_keeps_both_explicit_pov_memberships():
    text, config, metrics, fingerprint = comparison(registered=False)
    characters = presence_report(text, {"Alex": "Alex", "Robin": "Robin"}, config,
                                declared_pov={"Alex": [1, 3], "Robin": [3, 5]})
    markup = ScopeMarkup(render_heatmap_panel(fingerprint, metrics, characters=characters))
    assert [row["data-scope-pov"] for row in markup.rows] == ["p-0", "", "p-0 p-1", "", "p-1"]
