"""Chapter destinations remain native links in the analysis overview."""

import re
from copy import deepcopy

from dashboard_fixtures import full_dashboard

from lixity import CorpusConfig
from lixity.markdown_parser import parse_markdown_blocks
from lixity.style_profile import ParagraphProfiler
from lixity.ui.components import chapter_link
from lixity.ui.dashboard import render_dashboard
from lixity.ui.narration import (
    render_characters_panel,
    render_dialogue_panel,
    render_motifs_panel,
    render_pacing_panel,
    render_showing_panel,
)


def test_shared_chapter_link_escapes_text_and_carries_optional_flag_context():
    plain = chapter_link(3, '<script>alert("x")</script>')
    assert 'class="chapter-link"' in plain
    assert 'href="#ch-3"' in plain and 'data-jump="#ch-3"' in plain
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in plain
    assert '<script>' not in plain
    assert 'data-flags=' not in plain
    flagged = chapter_link(3, 'Chapter', flags=True)
    assert 'data-flags="1"' in flagged
    assert 'class="chapter-link label"' in chapter_link(3, 'Chapter', css_class='label')


def test_matrix_chapter_identity_is_a_native_link_without_button_row():
    panel = full_dashboard().split('id="matrix"', 1)[1].split('</section>', 1)[0]
    rows = re.findall(r'<tr\b([^>]*)>(.*?)</tr>', panel.split('<tbody>', 1)[1], re.S)
    assert rows
    for attributes, body in rows:
        target = re.search(r'data-jump="(#[^"]+)"', attributes)
        assert target
        assert 'role="button"' not in attributes
        assert 'tabindex=' not in attributes
        link = re.search(r'<a\b([^>]*)>', body)
        assert link
        assert f'href="{target[1]}"' in link[1]
        assert f'data-jump="{target[1]}"' in link[1]
        assert ('data-flags="1"' in attributes) == ('data-flags="1"' in link[1])


def test_matrix_chapter_link_remains_named_when_a_title_is_empty():
    paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="en")).profile_blocks(
        parse_markdown_blocks("## A chapter\n\nA synthetic paragraph."))
    chapter = deepcopy(chapters[0])
    chapter.title = ""
    panel = render_dashboard([chapter], paragraphs, controls=False).split('id="matrix"', 1)[1]
    assert re.search(r'<a\b[^>]*href="#ch-1"[^>]*>Chapter 1</a>', panel)


def test_narrative_rows_have_native_links_and_keep_no_destination_plain():
    chapter = {"chapter_num": 2, "title": "Other <chapter>", "turns": 1,
               "dialogue_pct": 10.0, "asl": 9.0, "hook_score": 1,
               "balance": 0.5, "tell_z": 0.0, "show_z": 0.5}
    panels = [
        render_dialogue_panel({"chapters": [chapter]}),
        render_pacing_panel({"chapter_list": [chapter]}),
        render_showing_panel({"chapter_list": [chapter, {**chapter, "chapter_num": 3,
                                                        "balance": -0.5},
                                               {**chapter, "chapter_num": 4}]}),
        render_characters_panel({"chapters": 3, "figures": [
            {"name": "Mara", "first_chapter": 2, "last_chapter": 3},
            {"name": "Absent", "first_chapter": None},
        ]}, []),
        render_motifs_panel({"motifs": [{"name": "rain", "first_chapter": 2,
                                         "last_chapter": 3}],
                             "repeated_phrases": [{"phrase": "soft rain", "chapters": [2]}]}),
    ]
    for panel in panels:
        assert re.search(r'<a\b[^>]*href="#ch-2"[^>]*data-jump="#ch-2"', panel)
        assert not re.search(r'<(?:div|tr)\b[^>]*data-jump="#ch-2"[^>]*role="button"', panel)
    absent = re.search(r'<tr\b[^>]*>\s*<td class="name">Absent</td>.*?</tr>', panels[3], re.S)
    assert absent and '<a ' not in absent[0]
