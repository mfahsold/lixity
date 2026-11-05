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


@pytest.mark.parametrize("text", [
    "## Chapter\n\nThe.\n\n" + "river " * 99 + ".",
    "## Chapter\n\n> The.\n\n" + "river " * 99 + ".",
    "# Title\n\nThe.\n\n## Chapter\n\n" + "river " * 99 + ".",
])
def test_function_word_tile_uses_global_token_counts_including_quotes_and_preamble(text):
    document = dashboard(text, language="en", project_config={})
    tile = re.search(r'<div[^>]*data-layer="function"[^>]*><b>([^<]*)</b>', document)
    assert tile is not None
    assert tile.group(1) == "1.0%"


def test_older_metric_payload_without_global_function_share_displays_unknown():
    from lixity.analyzer import CorpusAnalyzer
    from lixity.models import CorpusMetrics
    from lixity.ui import render_dashboard

    raw = CorpusAnalyzer().analyze_text("## Chapter\n\nThe river flows.").model_dump()
    raw.pop("function_word_pct", None)
    old_metrics = CorpusMetrics.model_validate(raw)
    assert old_metrics.function_word_pct is None
    document = render_dashboard([], [], metrics=old_metrics)
    tile = re.search(r'<div[^>]*data-layer="function"[^>]*><b>([^<]*)</b>', document)
    assert tile is not None
    assert tile.group(1) == "–"
