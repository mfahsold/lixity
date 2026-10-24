"""Global overview counts use the same prose scope as corpus measurements."""

import re

import pytest

from lixity.api import dashboard


@pytest.mark.parametrize("text", [
    "# Titel\n\nVor dem Kapitel.\n\n## Kapitel\n\nSie geht heim.",
    "## Kapitel\n\n> Vor dem Absatz.\n\nSie geht heim.",
])
def test_global_words_and_sentence_tiles_share_the_corpus_scope(text):
    document = dashboard(text, language="de", project_config={})
    measurements = document.split('id="analysis-measurements"', 1)[1]
    values = re.findall(r'class="kpi\b[^>]*><b>([^<]*)</b>', measurements)
    assert values[:4] == ["6", "1", "1", "2"]
    assert 'data-help="' in measurements
