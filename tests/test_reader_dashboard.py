"""The browser projection covers structure without extending analysis coverage."""

from lixity import api
from lixity.ui.render_contracts import DashboardContent, DashboardOptions


def test_generic_reader_marks_unknown_layers_without_a_false_zero_or_comparison(tmp_path):
    from lixity.server.views import build_server_dashboard

    manuscript = tmp_path / 'draft.md'
    manuscript.write_text('Mara saw the gate. "Wait here." Mara waited.\n', encoding='utf-8')
    page, _ = build_server_dashboard(str(manuscript), language='generic')
    select = page.split('id="style-layer"', 1)[1].split('</select>', 1)[0]
    assert 'value="filter"' in select
    assert 'data-reference="measure-filter" data-available="0"' in select
    assert 'data-reference="measure-dialogue" data-available="0"' not in select
    assert 'data-reference="measure-echo" data-available="0"' not in select
    assert 'id="layer-language-unavailable"' in page
    assert 'filter":null' in page
def test_dashboard_retains_source_structure_outside_profiles():
    source = '# Voyage\n\nPreface only.\n\n## Departure\n\nA quiet garden.\n\n> Quotation only.\n\n[^n]: Note only.\n\n## Anmerkungen und Literaturverzeichnis\n\nAppendix only.\n'
    page = api.dashboard(source)
    main = page.split('<main id="chapters"', 1)[1].split('</main>', 1)[0]
    positions = [main.index(text) for text in ('Voyage', 'Preface only.', 'Departure', 'A quiet garden.', 'Quotation only.', '[n] Note only.', 'Appendix only.')]
    assert positions == sorted(positions)
    assert main.count('id="p-0"') == 1
    assert 'reader-coverage' in main
    assert '<img ' not in main


def test_structure_only_document_has_readable_main():
    page = api.dashboard('# Title\n\n## Empty\n\n> Quotation only.\n\n```\n<img src=https://example.test/never>\n```\n')
    main = page.split('<main id="chapters"', 1)[1].split('</main>', 1)[0]
    assert 'Quotation only.' in main
    assert '&lt;img src=https://example.test/never&gt;' in main
    assert 'data-reader-paragraph' not in main


def test_implicit_chapter_keeps_public_chapter_target():
    from lixity.pipeline import analyze_document, resolve_document_config
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui.dashboard import render_analysis
    from lixity.ui.manuscript_document import reader_blocks

    source = '# Title\n\nA quiet garden gives this sentence a place to begin.\n'
    config, resolved = resolve_document_config(source, 'en', project_config={})
    analysis = analyze_document(source, config, FingerprintThresholds())
    page = render_analysis(
               analysis,
               resolved,
               title='Title',
               flag_min_severity=2,
               content=DashboardContent(
                   reader_document=reader_blocks(source, config, analysis.paragraphs),
               ),
               options=DashboardOptions(
                   controls=True,
               ),
           )
    assert '<section class="chapter reader-preface" id="ch-1"' in page
    assert 'id="reader-preface"' in page
    assert '<option value="ch-1">' in page
    assert page.count('id="p-0"') == 1


def test_opening_prose_has_its_own_reader_chapter_and_picker_target():
    from lixity.pipeline import analyze_document, resolve_document_config
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui.dashboard import render_analysis
    from lixity.ui.manuscript_document import reader_blocks

    source = "A quiet garden.\n\n## Departure\n\nThe door opens.\n"
    config, resolved = resolve_document_config(source)
    analysis = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    page = render_analysis(
        analysis, resolved, title="Title", flag_min_severity=2,
        content=DashboardContent(reader_document=reader_blocks(source, config, analysis.paragraphs)),
        options=DashboardOptions(controls=True),
    )
    main = page.split('<main id="chapters"', 1)[1].split('</main>', 1)[0]
    assert main.index('id="ch-1"') < main.index('id="p-0"') < main.index('id="ch-2"') < main.index('id="p-1"')
    picker = page.split('id="reader-chapter"', 1)[1].split('</select>', 1)[0]
    assert '<option value="ch-1">Manuscript</option>' in picker


def test_chapter_picker_keeps_empty_chapters_in_source_order():
    from lixity.pipeline import analyze_document, resolve_document_config
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui.manuscript_document import reader_blocks
    from lixity.ui.manuscript_reader import reading_controls

    source = '## One\n\nA quiet garden.\n\n## Empty\n\n## Three\n\nA door opens.\n'
    config, _ = resolve_document_config(source, 'en', project_config={})
    analysis = analyze_document(source, config, FingerprintThresholds())
    controls = reading_controls(analysis.chapters, None, reader_blocks(source, config, analysis.paragraphs))
    assert controls.index('One</option>') < controls.index('Empty</option>') < controls.index('Three</option>')


def test_quote_only_measured_chapter_has_a_canonical_structural_anchor():
    from lixity.pipeline import analyze_document, resolve_document_config, supplementary_reports
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui.dashboard import render_analysis
    from lixity.ui.manuscript_document import reader_blocks

    source = "## Same\n\n> The birds sing.\n\n## Empty\n\n## Same\n\nThe door opens.\n"
    config, resolved = resolve_document_config(source)
    analysis = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    reports = supplementary_reports(source, config, analysis)
    page = render_analysis(
        analysis, resolved, title="Title", flag_min_severity=2,
        content=DashboardContent(reader_document=reader_blocks(source, config, analysis.paragraphs),
                                 pacing=reports["pacing"]),
        options=DashboardOptions(controls=True),
    )
    main = page.split('<main id="chapters"', 1)[1].split('</main>', 1)[0]
    assert main.count('id="ch-1"') == main.count('id="ch-2"') == 1
    assert main.index('id="ch-1"') < main.index('id="source-5"') < main.index('id="ch-2"')
    assert '<blockquote class="reader-structural reader-quote"' in main
    assert main.count('id="p-0"') == 1 and 'id="p-1"' not in main
    assert 'href="#ch-1"' in page
    picker = page.split('id="reader-chapter"', 1)[1].split('</select>', 1)[0]
    assert '<option value="ch-1">1. Same</option>' in picker
    assert '<option value="source-5">Empty</option>' in picker
    assert '<option value="ch-2">2. Same</option>' in picker


def test_reader_dashboard_unifies_inline_evidence_in_measure_dropdown():
    from lixity.pipeline import analyze_document, resolve_document_config
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui.dashboard import render_analysis
    from lixity.ui.manuscript_document import reader_blocks

    source = '## Chapter 1\n\n"Hello," she said softly, and walked across the quiet room.\n'
    config, resolved = resolve_document_config(source, 'en', project_config={})
    analysis = analyze_document(source, config, FingerprintThresholds(), include_evidence=True)
    page = render_analysis(
               analysis,
               resolved,
               title='Title',
               flag_min_severity=2,
               content=DashboardContent(
                   reader_document=reader_blocks(source, config, analysis.paragraphs),
               ),
               options=DashboardOptions(
                   controls=True,
               ),
           )
    assert 'id="reader-inline-evidence-layers"' not in page
    for layer_key in ("sticky", "dialogue_tag", "echo"):
        assert f'value="{layer_key}"' in page
    assert "::highlight(lixity-analysis-evidence)" in page
