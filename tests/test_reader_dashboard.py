"""The browser projection covers structure without extending analysis coverage."""

from lixity import api


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
    page = render_analysis(analysis, resolved, title='Title', flag_min_severity=2,
                           controls=True, reader_document=reader_blocks(source, config, analysis.paragraphs))
    assert '<section class="chapter reader-preface" id="ch-1"' in page
    assert 'id="reader-preface"' in page
    assert '<option value="ch-1">' in page
    assert page.count('id="p-0"') == 1


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
