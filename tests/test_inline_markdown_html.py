"""Restored EPUB fragments treat URLs and anchor identifiers as untrusted data."""

from html.parser import HTMLParser
from urllib.parse import urlsplit
from xml.etree import ElementTree

import pytest

from lixity.markdown_parser import inline_markdown_to_html


def assert_xhtml(value):
    # Only bounded, locally generated synthetic fragments reach this XML parser.
    ElementTree.fromstring('<div xmlns:epub="http://www.idpf.org/2007/ops">' + value + "</div>")  # noqa: S314


class Fragment(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.anchors = []
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        assert not any(name.lower().startswith("on") for name, _ in attrs), attrs
        if tag == "a":
            self.anchors.append(dict(attrs))


@pytest.mark.parametrize("url", ["javascript:alert", "JaVaScRiPt:alert", "data:text/html,evil", "vbscript:evil",
                                 " javascript:alert ", "&#106;avascript:alert"])
def test_executable_link_schemes_remain_inert(url):
    fragment = Fragment(inline_markdown_to_html(f"[Synthetic label]({url})"))
    assert all(urlsplit(anchor["href"]).scheme.lower() not in ("javascript", "data", "vbscript")
               for anchor in fragment.anchors)


def test_quote_in_link_destination_cannot_create_an_event_attribute():
    result = inline_markdown_to_html('[Synthetic label](https://example.org/"onmouseover="evil)')
    fragment = Fragment(result)
    assert len(fragment.anchors) == 1
    assert fragment.anchors[0]["href"] == 'https://example.org/"onmouseover="evil'
    assert_xhtml(result)


@pytest.mark.parametrize("note,document", [
    ('n"onmouseover="evil', "document"),
    ("note", 'doc"onfocus="evil'),
    ("note", '[label](https://example.org/)"onfocus="evil'),
])
def test_footnote_and_document_identifiers_cannot_create_attributes(note, document):
    result = inline_markdown_to_html(f"Synthetic [^{note}]", document_id=document)
    fragment = Fragment(result)
    assert len(fragment.anchors) == 1
    assert fragment.anchors[0]["id"] == f"fnref{note}-{document}-1"
    assert fragment.anchors[0]["href"] == "#fn" + note
    assert_xhtml(result)


def test_valid_epub_references_urls_and_inline_formatting_keep_their_contract():
    counters = {}
    first = inline_markdown_to_html("**Bold** and *italic* [^n1]\nNext.", counters, "chapter-01")
    second = inline_markdown_to_html("Again [^n1] and [^n2].", counters, "chapter-01")
    assert Fragment(first).anchors[0]["id"] == "fnrefn1-chapter-01-1"
    assert Fragment(second).anchors[0]["id"] == "fnrefn1-chapter-01-2"
    assert Fragment(second).anchors[1]["href"] == "#fnn2"
    assert counters == {"n1": 2, "n2": 1}
    assert "<strong>Bold</strong>" in first and "<em>italic</em>" in first and "<br/>\nNext." in first
    for url in ("https://example.org/page?a=1&b=2", "mailto:reader@example.org", "chapter-02.xhtml#note", "#fnn1"):
        result = inline_markdown_to_html(f"[Read]({url})")
        assert Fragment(result).anchors == [{"href": url}]
        assert_xhtml(result)
    assert inline_markdown_to_html(r"Literal \*star\* and <script>data</script>") == "Literal *star* and &lt;script&gt;data&lt;/script&gt;"
