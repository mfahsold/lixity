"""Opt-in reader analysis only discloses explicitly selected capped content."""

import io
import json
import re
import zipfile

import pytest

from lixity.cli import main
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.site_export import prepare_site
from tests.support import LoopbackServer, make_handler, send
from tests.test_site_export import site_data
from tests.test_site_export_interfaces import _publication_project


@pytest.mark.parametrize('sections', [['chapters'], ['language'], ['chapters', 'language'], ['full']])
def test_selected_analysis_is_physical_and_capped(tmp_path, sections):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    manuscript.write_text('## One\n\n<!-- LIXITY-MARKER id="1" kind="todo" note="PRIVATE_MARKER_SENTINEL" -->\n\n'
                          'EARLY_PUBLIC_PROSE opens the door.\n\n## Two\n\nLATER_PRIVATE_PROSE closes it.\n')
    (project / 'lixity.toml').write_text((project / 'lixity.toml').read_text() +
                                        '\n[characters.PRIVATE_CHARACTER_SENTINEL]\n')
    bundle = prepare_site(project, mode='reader', publication_profile='readers', max_chapter=1,
                          analysis_sections=sections)
    manifest = bundle.manifest
    assert manifest['schema_version'] == 'lixity-read-only-site/2'
    assert manifest['publication']['analysis_sections'] == sections
    assert manifest['capabilities']['analysis'] is True
    assert 'analysis.html' in bundle.files
    assert b'analysis.html' in bundle.files['index.html']
    data = b'\n'.join(bundle.files.values())
    for forbidden in (b'LATER_PRIVATE_PROSE', b'PRIVATE_MARKER_SENTINEL', b'PRIVATE_CHARACTER_SENTINEL',
                      b'private-draft-name.md', str(project).encode()):
        assert forbidden not in data
    analysis = bundle.files['analysis.html']
    if sections != ['full']:
        assert (b'analysis-section-chapters' in analysis) == ('chapters' in sections)
        assert (b'analysis-section-language' in analysis) == ('language' in sections)
        assert b'EARLY_PUBLIC_PROSE' not in analysis
    else:
        assert b'EARLY_PUBLIC_PROSE' in analysis
    assert bundle.preflight()['analysis_sections'] == sections
    sizes = bundle.preflight()['sizes']
    assert sizes['html_bytes'] == len(bundle.files['index.html'])
    assert sizes['analysis_html_bytes'] == len(bundle.files['analysis.html'])
    assert sizes['total_html_bytes'] == sizes['html_bytes'] + sizes['analysis_html_bytes']


def test_default_and_incompatible_options_remain_explicit(tmp_path):
    project = tmp_path / 'project'
    _publication_project(project)
    bundle = prepare_site(project, mode='reader', publication_profile='readers')
    assert bundle.manifest['schema_version'] == 'lixity-read-only-site/1'
    assert not bundle.manifest['capabilities']['analysis']
    assert 'analysis.html' not in bundle.files
    selected = prepare_site(project, mode='reader', publication_profile='readers', analysis_sections=['chapters'])
    assert site_data(bundle)['publication'] == site_data(selected)['publication']
    for invalid in (['unknown'], ['chapters', 'chapters'], ['full', 'language']):
        with pytest.raises(ValueError):
            prepare_site(project, mode='reader', publication_profile='readers', analysis_sections=invalid)
    with pytest.raises(ValueError):
        prepare_site(project, mode='companion', publication_profile='readers', analysis_sections=['chapters'])
    with pytest.raises(ValueError):
        prepare_site(project, analysis_sections=['chapters'])


def test_cli_and_native_download_expose_same_requested_scope(tmp_path, capsys):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    output = tmp_path / 'out'
    assert main(['export-site', '--project', str(project), '--mode', 'reader',
                 '--publication-profile', 'readers', '--max-chapter', '1',
                 '--analysis', 'chapters', '--analysis', 'language', '-o', str(output), '--json']) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest['publication']['analysis_sections'] == ['chapters', 'language']
    handler = make_handler(project, source_input=manuscript, language='de')
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        response = send(server.port, '/api/site-export', payload={'project_token': token,
            'include_research': False, 'include_source_files': False, 'mode': 'reader',
            'publication_profile': 'readers', 'max_chapter': 1, 'analysis_sections': ['chapters', 'language']})
    assert response.status == 200, response.body.decode(errors='replace')[:500]
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        native = json.loads(archive.read('manifest.json'))
        assert native['publication']['analysis_sections'] == manifest['publication']['analysis_sections']
        assert archive.read('analysis.html') == (output / 'analysis.html').read_bytes()


@pytest.mark.parametrize('sections', [['chapters'], ['language'], ['full']])
def test_analysis_preserves_selected_chapters_with_nondefault_headings_and_appendix(tmp_path, sections):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    config = project / 'lixity.toml'
    config.write_text("chapter_regex = '(?m)^###\\s+'\nappendix_marker = '### END'\n" + config.read_text())
    manuscript.write_text('### Chapter One\n\nA first simple sentence.\n\n'
                          '## Anmerkungen und Literaturverzeichnis\n\n'
                          'A visible final sentence after heading.\n\n'
                          '### Chapter Two\n\nPRIVATE_FUTURE_SENTINEL.\n')
    original = manuscript.read_bytes()
    bundle = prepare_site(project, mode='reader', publication_profile='readers',
                          max_chapter=1, analysis_sections=sections)
    page = bundle.files['analysis.html']
    assert b'PRIVATE_FUTURE_SENTINEL' not in b'\n'.join(bundle.files.values())
    assert b'#' * 128 not in b'\n'.join(bundle.files.values())
    assert b'LIXITYREADERAPPENDIXBOUNDARY' not in b'\n'.join(bundle.files.values())
    assert manuscript.read_bytes() == original
    if sections == ['chapters']:
        assert page.count(b'class="reader-analysis-chapter"') == 1
    elif sections == ['language']:
        assert '<dt>Wörter</dt><dd>10</dd>'.encode() in page
    else:
        assert b'A first simple sentence.' in page
        assert b'A visible final sentence after heading.' in page
        anchors = re.findall(rb'id="p-\d+" data-start="(\d+)" data-end="(\d+)"', page)
        assert anchors == [(b'3', b'3'), (b'7', b'7')]


def test_analysis_boundary_cannot_match_authored_content(tmp_path):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    authored_heading = '#' * 128 + ' literal text retained.'
    manuscript.write_text('## One\n\n' + authored_heading + '\n')
    bundle = prepare_site(project, mode='reader', publication_profile='readers', max_chapter=1,
                          analysis_sections=['full'])
    page = bundle.files['analysis.html']
    assert authored_heading.encode() in page
    assert b'#' * 129 not in page


def test_analysis_does_not_create_chapters_from_inner_headings(tmp_path):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    config = project / 'lixity.toml'
    config.write_text("chapter_regex = '(?m)^###\\s+'\n" + config.read_text())
    manuscript.write_text('### One\n\nFirst words.\n\n## Inner heading\n\nMore words.\n\n### Two\n\nHidden.\n')
    bundle = prepare_site(project, mode='reader', publication_profile='readers', max_chapter=1,
                          analysis_sections=['chapters'])
    assert bundle.files['analysis.html'].count(b'class="reader-analysis-chapter"') == 1


@pytest.mark.parametrize('sections', [['chapters'], ['language'], ['full']])
def test_analysis_keeps_untitled_chapter_and_does_not_expose_internal_boundary(tmp_path, sections):
    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    manuscript.write_text('## \n\nVisible untitled chapter.\n\n## Next\n\nUnselected.\n')
    bundle = prepare_site(project, mode='reader', publication_profile='readers', max_chapter=1,
                          analysis_sections=sections)
    data = b'\n'.join(bundle.files.values())
    assert b'#' * 128 not in data
    assert b'Unselected.' not in data
    if sections == ['full']:
        assert b'Visible untitled chapter.' in bundle.files['analysis.html']
        assert b'id="p-0" data-start="3" data-end="3"' in bundle.files['analysis.html']
        assert b'<section class="chapter" id="ch-1"' in bundle.files['analysis.html']
    if sections == ['chapters']:
        assert bundle.files['analysis.html'].count(b'class="reader-analysis-chapter"') == 1


@pytest.mark.parametrize('sections', [['chapters'], ['language'], ['full']])
def test_zero_chapter_cap_is_empty_and_all_alias_works_in_preflight(tmp_path, capsys, sections):
    project = tmp_path / 'project'
    _publication_project(project)
    assert main(['export-site', '--project', str(project), '--mode', 'reader',
                 '--publication-profile', 'readers', '--max-chapter', '0',
                 '--analysis', 'all', '--preflight', '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['analysis_sections'] == ['full']
    assert report['sizes']['analysis_html_bytes'] > 0
    bundle = prepare_site(project, mode='reader', publication_profile='readers', max_chapter=0,
                          analysis_sections=sections)
    assert b'EARLY_PUBLIC_PROSE' not in b'\n'.join(bundle.files.values())
    assert b'LATER_PRIVATE_PROSE' not in b'\n'.join(bundle.files.values())
    assert not (project / 'exports').exists()
