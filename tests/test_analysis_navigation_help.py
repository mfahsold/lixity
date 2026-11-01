"""Navigation explanations remain localized descriptions of native links."""

from html.parser import HTMLParser

import pytest

from lixity.ui.components import ANALYSIS_SECTIONS, analysis_outline_nav, section_nav
from lixity.workspace_labels import WORKSPACE_LABELS


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_analysis_navigation_links_have_localized_descriptions(language):
    labels = WORKSPACE_LABELS[language]
    parsed = _Links()
    parsed.feed(section_nav(ANALYSIS_SECTIONS, labels))
    assert len(parsed.links) == len(ANALYSIS_SECTIONS)
    for link, (target, _) in zip(parsed.links, ANALYSIS_SECTIONS, strict=True):
        assert link["href"] == f"#{target}"
        assert link["data-jump"] == f"#{target}"
        assert link["data-help"] == labels[f"analysis_nav_help_{target}"]
        assert link["data-help"].strip()
        assert "tabindex" not in link


def test_analysis_navigation_escapes_description_in_attribute():
    parsed = _Links()
    parsed.feed(section_nav([("flags", "panel_flags")], {
        "panel_flags": "Flags",
        "analysis_nav_help_flags": 'Read "this" <safely> & return.',
    }))
    assert parsed.links[0]["data-help"] == 'Read "this" <safely> & return.'


def test_unknown_section_does_not_show_a_missing_translation_key():
    parsed = _Links()
    parsed.feed(section_nav([("future", "future_section")], {"future_section": "Future"}))
    assert "data-help" not in parsed.links[0]


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_outline_reuses_the_same_descriptions_and_describes_review(language):
    labels = WORKSPACE_LABELS[language]
    parsed = _Links()
    parsed.feed(analysis_outline_nav([("analysis-review", "review_title"), *ANALYSIS_SECTIONS], labels))
    assert parsed.links[0]["data-help"] == labels["analysis_nav_help_analysis-review"]
    for link, (target, _) in zip(parsed.links[1:], ANALYSIS_SECTIONS, strict=True):
        assert link["data-help"] == labels[f"analysis_nav_help_{target}"]
        assert "tabindex" not in link


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "nl"])
def test_audio_help_describes_the_available_capability(language):
    labels = WORKSPACE_LABELS[language]
    assert labels["speech_reader_help"].strip()
    assert labels["speech_reader_help_plan"].strip()
    assert labels["speech_reader_help"] != labels["speech_reader_help_plan"]
