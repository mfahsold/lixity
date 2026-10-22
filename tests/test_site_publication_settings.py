"""Publication profile editing uses the shared project settings transaction."""

import json
from pathlib import Path

import pytest

from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui.settings import settings_form
from tests.support import LOCALES, HtmlControls, labels_for

PROFILES = {"readers": {"title": 'Reader <img src=x onerror="alert(1)">',
    "introduction": "Authored reader introduction.", "entries": [{
        "dossier_id": "urn:uuid:11111111-1111-4111-8111-111111111111", "revision": 7,
        "section": "Unavailable former section", "reveal_after_chapter": 2,
        "title": "Retained display title", "include_citations": False, "include_geography": False}]}}


@pytest.mark.parametrize("language", LOCALES)
def test_profile_editor_keeps_inert_initial_entries_and_localized_scope(language):
    labels = labels_for(language)
    markup = settings_form(labels, "Synthetic", language, (), FingerprintThresholds(),
        author_setting_enabled=True, project_token="a" * 64, site_publications=PROFILES,
        site_publication_context_token="b" * 64)
    editor = HtmlControls(markup).elements["site-publication-editor"]
    assert json.loads(editor["data-initial"]) == PROFILES
    assert editor["data-context-token"] == "b" * 64
    assert "disabled" not in editor
    terms = json.loads(editor["data-labels"])
    for key in ("publication_editor_title", "publication_editor_dossier", "publication_editor_current",
                "publication_editor_whole_body", "publication_editor_scope", "publication_editor_after"):
        assert terms[key] == labels[key]
        assert key not in terms[key]
    assert 'id="settings-site-publications-summary"' in markup
    assert '<img src=x' not in markup
    assert "data-site-source-consent" not in markup


def test_profile_editor_is_read_only_without_a_selected_project():
    markup = settings_form(labels_for("en"), "", "en", (), FingerprintThresholds(),
        site_publications=PROFILES)
    editor = HtmlControls(markup).elements["site-publication-editor"]
    assert "disabled" in editor
    assert json.loads(editor["data-initial"]) == PROFILES


def test_profile_editor_retains_malformed_existing_data_for_explicit_recovery():
    malformed = {"old": {"title": "Saved title", "entries": "must remain available for correction"}}
    markup = settings_form(labels_for("en"), "", "en", (), FingerprintThresholds(),
        author_setting_enabled=True, project_token="a" * 64, site_publications=malformed)
    editor = HtmlControls(markup).elements["site-publication-editor"]
    assert json.loads(editor["data-initial"]) == malformed


def test_profile_editor_asset_is_in_the_shared_native_bundle():
    from lixity.ui.dashboard import _JS_FILES

    assert "site-publication-settings.js" in _JS_FILES
    runtime = Path(__file__).parents[1] / "src/lixity/ui/assets/site-publication-settings.js"
    assert runtime.is_file()
