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
