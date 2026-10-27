"""Curated publications render reading content without research administration."""

import importlib
import importlib.util

import pytest

from lixity.language import get_language_profile
from lixity.ui.manuscript_document import ReaderBlock


def renderer():
    assert importlib.util.find_spec('lixity.ui.publication') is not None, 'The curated reading surface is missing'
    return importlib.import_module('lixity.ui.publication').render_publication


@pytest.mark.parametrize('mode', ('reader', 'companion'))
def test_curated_publication_has_explicit_progress_without_analysis_or_admin(mode):
    data = {'schema_version':'lixity-reader-publication/1', 'mode':mode, 'title':'Synthetic reading context',
            'introduction':'A public introduction.', 'max_chapter':2, 'chapters':[{'number':1},{'number':2}],
            'identity':'a'*64, 'source_sha256':'b'*64, 'profile':'public', 'project_id':'synthetic-project',
            'entries':[]}
    blocks = [ReaderBlock('heading', 'Synthetic novel', 1, 1, level=1),
              ReaderBlock('heading', 'Arrival', 3, 3, is_chapter=True),
              ReaderBlock('paragraph', 'Synthetic novel text <script>data</script>.', 5, 5)]
    page = renderer()(data, reader_document=blocks if mode == 'reader' else None,
                      labels=get_language_profile('en').labels, language_key='en')
    assert 'data-read-only="true"' in page
    assert 'id="publication-progress"' in page
    assert 'id="publication-progress-apply"' in page
    assert 'id="publication-preview-open"' in page
    assert 'id="publication-progress-reset"' in page
    assert 'id="settings-form"' not in page
    assert 'id="research-manager"' not in page
    assert 'id="manuscript-analysis-toggle"' not in page
    assert 'id="paragraph-content"' not in page
    if mode == 'reader':
        assert 'Synthetic novel text &lt;script&gt;data&lt;/script&gt;.' in page
    else:
        assert 'Synthetic novel text' not in page
        assert 'id="chapters"' not in page


@pytest.mark.parametrize('mode', ('reader', 'companion'))
def test_publications_omit_inactive_native_controllers_without_mutating_content(mode):
    import copy
    import re

    from lixity.ui.dashboard import _ASSET_DIR, _JS_FILES, _bundle, render_dashboard

    publication = {'mode': mode, 'title': 'Synthetic publication', 'max_chapter': 3,
                   'introduction': 'A safe introduction.', 'entries': [
                       {'body': 'An ordinary later passage.', 'reveal_after_chapter': 3}]}
    original = copy.deepcopy(publication)
    page = renderer()(publication)
    inactive = ('register-settings.js', 'site-publication-settings.js', 'analysis-scope.js',
                'project-overview.js', 'style-space.js', 'metric-context.js', 'workspace-reader.js',
                'manuscript-reader.js', 'manuscript-links.js', 'analysis-evidence.js', 'analysis-review.js')
    for name in inactive:
        assert (_ASSET_DIR / name).read_text() not in page, name
    script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
    assert script.startswith((_ASSET_DIR / 'read-only-site.js').read_text())
    assert len(script.encode()) < len(_bundle(_JS_FILES).encode()) - 200_000
    for name in ('reader-publication.js', 'research-content.js', 'research-evidence.js',
                 'dossier-images.js', 'dossier-geography.js', 'research-media.js'):
        assert (_ASSET_DIR / name).read_text() in script
    assert _bundle(_JS_FILES) in render_dashboard([], [], controls=True)
    assert publication == original


@pytest.mark.parametrize('mode', ('reader', 'companion'))
def test_publications_without_diagram_keywords_omit_the_diagram_library(mode):
    page = renderer()({'mode': mode, 'title': 'Synthetic publication', 'max_chapter': 3,
                       'introduction': 'A safe introduction.', 'entries': [
                           {'body': 'An ordinary hidden passage.', 'reveal_after_chapter': 3}]})
    assert 'id="research-diagram-library"' not in page
    assert len(page.encode()) < 1_500_000


@pytest.mark.parametrize('location', ('introduction', 'visible_entry', 'hidden_entry'))
@pytest.mark.parametrize('keyword', ('mermaid', 'MeRmAiD'))
def test_any_prepared_diagram_keyword_keeps_the_offline_library(location, keyword):
    import copy

    publication = {'mode': 'companion', 'title': 'Synthetic diagrams', 'max_chapter': 3,
                   'introduction': '', 'entries': [
                       {'body': 'An ordinary passage.', 'reveal_after_chapter': 0},
                       {'body': 'An ordinary hidden passage.', 'reveal_after_chapter': 3}]}
    text = f'~~~{keyword}\nflowchart LR\nA --> B\n~~~'
    if location == 'introduction':
        publication['introduction'] = text
    else:
        publication['entries'][location == 'hidden_entry']['body'] = text
    original = copy.deepcopy(publication)
    assert 'id="research-diagram-library"' in renderer()(publication)
    assert publication == original
