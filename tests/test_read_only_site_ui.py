"""The website uses native reading surfaces with explicit read-only capabilities."""

import re

import pytest

from lixity.language import get_language_profile
from lixity.ui import render_dashboard
from lixity.ui.dashboard import _JS_FILES
from lixity.workspace_labels import WORKSPACE_LABELS


@pytest.mark.parametrize("language", ("en", "de", "fr", "es", "it", "pt", "nl"))
def test_read_only_renderer_keeps_native_reading_and_labels_scope(language):
    page = render_dashboard([], [], controls=True, read_only=True,
                            labels=get_language_profile(language).labels,
                            language_key=language,
                            enabled_actions=("research-reader", "research-manuscript-link"))
    assert 'data-read-only="true"' in page
    assert 'data-manuscript-links="read"' in page
    assert WORKSPACE_LABELS[language]["site_read_only"] in page
    assert 'id="modal-research-revision"' in page
    assert 'id="research-revision-history-tab"' in page
    assert re.search(r'id="research-revision-edit-tab"[^>]*data-requires-write', page)
    assert 'data-dossier-image-capable="false"' in page
    assert _JS_FILES[0] == "read-only-site.js"


def test_live_renderer_retains_default_capabilities():
    page = render_dashboard([], [], controls=True)
    assert 'data-read-only="false"' in page
    assert 'id="btn-modal-new-project"' in page
    assert 'id="settings-form"' in page


def test_website_action_requires_explicit_native_capability_and_context():
    page = render_dashboard([], [], controls=True, enabled_actions=("site-export",),
                            manuscript_pdf_token="selected-manuscript-context")  # noqa: S106 - synthetic context identity
    assert 'id="btn-site-export"' in page
    assert 'id="site-export-form"' in page
    assert 'id="site-export-research"' in page
    assert 'id="site-export-sources" disabled' in page
    limited = render_dashboard([], [], controls=True, enabled_actions=())
    assert 'id="btn-site-export"' not in limited
