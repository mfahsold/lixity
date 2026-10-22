"""Reader publications omit unselected archive data before HTML/media assembly."""

import json
from urllib.parse import unquote

import pytest

from lixity.config import prepare_project_settings
from lixity.research import api
from lixity.research.repository import ResearchError
from lixity.site_export import prepare_site
from tests.test_research_images import png
from tests.test_site_export import file_bytes, site_data

pytestmark = pytest.mark.portability


@pytest.fixture
def publication_project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'private-filename.md').write_text('# PRIVATE_FRONT_MATTER\n\n## EARLY_CHAPTER_TITLE\n\nEARLY_NOVEL_PROSE opens the gate.\n'
        '<!-- lixity:marker id="x" kind="todo" note="PRIVATE_MARKER_NOTE" -->\n\n'
        '## MIDDLE_CHAPTER_TITLE\n\nMIDDLE_NOVEL_PROSE closes the window.\n\n## LATE_CHAPTER_TITLE\n\nLATE_NOVEL_SENTINEL ends the story.\n\n'
        '## Anmerkungen und Literaturverzeichnis\n\nPRIVATE_APPENDIX_NOTE\n')
    (root / 'lixity.toml').write_text('manuscript = "private-filename.md"\nlanguage = "en"\n')
    api.init(root, title='PRIVATE_ARCHIVE_TITLE')
    source = tmp_path / 'source.txt'
    source.write_text('APPROVED_CITATION_QUOTE records the open gate.\n\nUNSELECTED_SOURCE_PASSAGE\n')
    captured = api.ingest(root, source, title='Approved register', allow_retention=True,
                          context={'provenance_note': 'PRIVATE_SOURCE_CONTEXT'})
    passage = api.get_source(root, captured['source_id'])['passages'][0]
    dossier = api.create_dossier(root, 'PRIVATE_ORIGINAL_DOSSIER_TITLE',
        '## Earlier\n\nAPPROVED_PUBLIC_BODY explains the place.\n\n### Detail\n\nAPPROVED_NESTED_DETAIL\n\n'
        '```text\n## Not a heading\nAPPROVED_CODE\n```\n\n## Later\n\nLATE_DOSSIER_SENTINEL\n',
        evidence_ids=[passage['id']])['dossier_id']
    attached = api.attach_dossier_image(root, dossier, png(), filename='selected.png', section='Earlier',
        alt='APPROVED_IMAGE_ALT', allow_retention=True,
        expected_snapshot=api.get_record(root, 'dossier', dossier)['snapshot'], expected_revision=1)
    claim = api.create_claim(root, title='PRIVATE_CLAIM_TITLE', statement='PRIVATE_CLAIM_STATEMENT', dossier_id=dossier)['claim_id']
    api.record_decision(root, title='PRIVATE_DECISION_TITLE', rationale='PRIVATE_DECISION_RATIONALE', claim_id=claim)
    late_image = api.ingest_image(root, png(), filename='PRIVATE_LATE_IMAGE_FILENAME.png', title='PRIVATE_LATE_IMAGE_TITLE', allow_retention=True)
    late = api.create_dossier(root, 'LATE_ENTRY_TITLE', 'LATE_ENTRY_BODY')['dossier_id']
    profiles = {'readers': {'title': 'Reader companion', 'introduction': 'APPROVED_INTRODUCTION', 'entries': [
        {'dossier_id': dossier, 'revision': 2, 'section': 'Earlier', 'title': 'Public location', 'reveal_after_chapter': 0},
        {'dossier_id': late, 'title': 'LATE_OVERRIDE_TITLE', 'reveal_after_chapter': 3},
    ]}}
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    return root, profiles, dossier, captured, attached, late_image


def test_standalone_companion_contains_only_curated_content_and_no_manuscript_or_archive(publication_project):
    root, _profiles, _dossier, _source, _image, _late_image = publication_project
    before = file_bytes(root)
    bundle = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    assert file_bytes(root) == before
    data = site_data(bundle)
    assert data['responses'] == {} and data['resources'] == {}
    publication = data['publication']
    assert publication['profile'] == 'readers'
    assert publication['mode'] == 'companion'
    assert publication['max_chapter'] == 1
    assert publication['chapters'] == [{'number': 1}]
    assert publication['entries'][0]['title'] == 'Public location'
    assert publication['entries'][0]['revision'] == 2
    assert publication['entries'][0]['citations'] == []
    assert publication['entries'][0]['geography'] is None
    assert 'APPROVED_NESTED_DETAIL' in publication['entries'][0]['body']
    assert 'APPROVED_CODE' in publication['entries'][0]['body']
    public = b'\n'.join(bundle.files.values())
    for sentinel in ('EARLY_NOVEL_PROSE', 'MIDDLE_NOVEL_PROSE', 'LATE_NOVEL_SENTINEL', 'EARLY_CHAPTER_TITLE', 'MIDDLE_CHAPTER_TITLE',
                     'LATE_CHAPTER_TITLE', 'PRIVATE_FRONT_MATTER', 'PRIVATE_APPENDIX_NOTE', 'PRIVATE_MARKER_NOTE',
                     'PRIVATE_ORIGINAL_DOSSIER_TITLE', 'LATE_DOSSIER_SENTINEL', 'LATE_ENTRY_BODY', 'LATE_OVERRIDE_TITLE',
                     'PRIVATE_CLAIM_TITLE', 'PRIVATE_CLAIM_STATEMENT', 'PRIVATE_DECISION_RATIONALE',
                     'APPROVED_CITATION_QUOTE', 'UNSELECTED_SOURCE_PASSAGE', 'PRIVATE_SOURCE_CONTEXT',
                     'PRIVATE_LATE_IMAGE_TITLE', 'private-filename.md'):
        assert sentinel.encode() not in public, sentinel
    assert bundle.manifest['mode'] == 'companion'
    assert bundle.manifest['analysis'] is None
    assert bundle.manifest['capabilities']['analysis'] is False
    assert bundle.manifest['research']['included'] is False
    assert not any(name.startswith('assets/sources/') for name in bundle.files)


def test_reader_cap_removes_later_prose_and_diagnostics_before_rendering(publication_project):
    root, *_ = publication_project
    bundle = prepare_site(root, mode='reader', publication_profile='readers', max_chapter=1)
    page = bundle.files['index.html'].decode()
    assert 'EARLY_NOVEL_PROSE' in page and 'EARLY_CHAPTER_TITLE' in page
    for sentinel in ('MIDDLE_NOVEL_PROSE', 'LATE_NOVEL_SENTINEL', 'PRIVATE_MARKER_NOTE', 'PRIVATE_APPENDIX_NOTE', 'LATE_ENTRY_BODY'):
        assert sentinel not in page
    assert 'data-paragraph-evidence=' not in page
    assert 'analysis-overview' not in page
    publication = site_data(bundle)['publication']
    assert 'EARLY_NOVEL_PROSE' not in json.dumps(publication)


def test_cap_zero_has_only_prechapter_entries_and_no_novel(publication_project):
    root, *_ = publication_project
    bundle = prepare_site(root, mode='reader', publication_profile='readers', max_chapter=0)
    assert site_data(bundle)['publication']['chapters'] == []
    assert b'EARLY_NOVEL_PROSE' not in bundle.files['index.html']
    assert 'APPROVED_PUBLIC_BODY' in site_data(bundle)['publication']['entries'][0]['body']


def test_current_selection_resolves_once_and_reveals_only_selected_version(publication_project):
    root, profiles, dossier, *_ = publication_project
    profiles['readers']['entries'][0]['revision'] = None
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    api.revise_record(root, 'dossier', dossier, changes={'body': '## Earlier\n\nCURRENT_APPROVED_VERSION\n\n## Later\n\nLATE_UNSELECTED_VERSION'},
        expected_revision=2, change_kind='correction', reason='PRIVATE_REVISION_REASON')
    bundle = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    entry = site_data(bundle)['publication']['entries'][0]
    assert entry['revision'] == 3 and entry['body'].strip() == 'CURRENT_APPROVED_VERSION'
    assert b'PRIVATE_REVISION_REASON' not in b'\n'.join(bundle.files.values())


def test_selected_sources_and_images_require_optin_and_never_expand_to_archive(publication_project):
    root, profiles, _dossier, source, image, late_image = publication_project
    profiles['readers']['entries'][0]['include_citations'] = True
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    excerpt = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    entry = site_data(excerpt)['publication']['entries'][0]
    assert [cite['verbatim'] for cite in entry['citations']] == ['APPROVED_CITATION_QUOTE records the open gate.']
    assert site_data(excerpt)['resources'] == {}
    bundle = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1, include_source_files=True)
    data = site_data(bundle)
    assert data['responses'] == {}
    keys = unquote('\n'.join(data['resources']))
    assert source['source_id'] in keys
    assert image['images'][0]['source_id'] in keys
    assert late_image['source_id'] not in keys
    serialized = json.dumps(data)
    assert 'UNSELECTED_SOURCE_PASSAGE' not in serialized
    assert 'PRIVATE_SOURCE_CONTEXT' not in serialized
    assert len([path for path in bundle.files if path.endswith('.png')]) == 1


@pytest.mark.parametrize('changes', [
    {'max_chapter': 4}, {'max_chapter': True}, {'publication_profile': 'unknown'},
    {'include_research': True},
])
def test_invalid_publication_selection_fails_closed(publication_project, changes):
    root, *_ = publication_project
    with pytest.raises((ResearchError, ValueError)):
        prepare_site(root, **{'mode': 'companion', 'publication_profile': 'readers', **changes})


def test_ambiguous_sections_fail_instead_of_exporting_wrong_text(publication_project):
    root, profiles, dossier, *_ = publication_project
    api.revise_record(root, 'dossier', dossier, changes={'body': '## Earlier\n\nOne.\n\n## Earlier\n\nTwo.'},
        expected_revision=2, change_kind='correction', reason='Synthetic ambiguity')
    profiles['readers']['entries'][0]['revision'] = None
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    with pytest.raises(ResearchError, match='ambiguous'):
        prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)


def test_curated_modes_never_run_analysis_or_internal_archive_serializers(publication_project, monkeypatch):
    import lixity.site_export as module

    root, *_ = publication_project
    def forbidden(*args, **kwargs):
        pytest.fail('Reader publications must not build internal analysis/archive payloads')
    monkeypatch.setattr(module, 'analyze_document', forbidden)
    monkeypatch.setattr(module, '_research', forbidden)
    monkeypatch.setattr(api, '_project_overview', forbidden)
    monkeypatch.setattr(api, '_get_dossier', forbidden)
    for mode in ('reader', 'companion'):
        bundle = prepare_site(root, mode=mode, publication_profile='readers', max_chapter=1)
        assert site_data(bundle)['responses'] == {}


def test_later_entries_are_excluded_before_reference_resolution(publication_project):
    root, profiles, *_ = publication_project
    profiles['readers']['entries'][1]['dossier_id'] = 'urn:uuid:00000000-0000-4000-8000-000000000099'
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    assert len(site_data(prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1))['publication']['entries']) == 1
    with pytest.raises(ResearchError):
        prepare_site(root, mode='companion', publication_profile='readers', max_chapter=3)


def test_withdrawn_selection_fails_instead_of_publishing_historical_private_notes(publication_project):
    root, _profiles, dossier, *_ = publication_project
    current = api.get_record(root, 'dossier', dossier)
    api.withdraw(root, dossier_id=dossier, expected_revision=2,
                 expected_snapshot=current['snapshot'], reason='Retired synthetic notes')
    with pytest.raises(ResearchError, match='withdrawn'):
        prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)


def test_geography_is_a_separate_explicit_whole_dossier_choice(publication_project):
    root, profiles, dossier, *_ = publication_project
    geography = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [11.0, 46.0]},
        'properties': {'label': 'APPROVED_MAP_LABEL', 'description': 'MAP_DESCRIPTION_SENTINEL'}}]}
    api.revise_record(root, 'dossier', dossier, changes={'geography': geography},
        expected_revision=2, change_kind='correction', reason='Synthetic map')
    profiles['readers']['entries'][0]['revision'] = None
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    default = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    assert b'MAP_DESCRIPTION_SENTINEL' not in b'\n'.join(default.files.values())
    profiles['readers']['entries'][0]['include_geography'] = True
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    selected = prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    feature = site_data(selected)['publication']['entries'][0]['geography']['features'][0]
    assert feature['geometry'] == {'type': 'Point', 'coordinates': [11.0, 46.0]}
    assert feature['properties']['label'] == 'APPROVED_MAP_LABEL'
    assert feature['properties']['description'] == 'MAP_DESCRIPTION_SENTINEL'
    assert site_data(selected)['resources'] == {}


def test_publication_still_rejects_manuscript_changes_during_render(publication_project, monkeypatch):
    import lixity.ui.publication as renderer

    root, *_ = publication_project
    original = renderer.render_publication
    def changed(*args, **kwargs):
        document = original(*args, **kwargs)
        (root / 'private-filename.md').write_text('## Changed\n\nThis source changed during the export.\n')
        return document
    monkeypatch.setattr(renderer, 'render_publication', changed)
    with pytest.raises(ResearchError, match='changed'):
        prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)


def test_implicit_canonical_chapter_has_a_reader_target_without_an_analysis_profile(publication_project):
    root, profiles, *_ = publication_project
    (root / 'private-filename.md').write_text('IMPLICIT_NOVEL_PROSE has no chapter heading.\n')
    profiles['readers']['entries'] = profiles['readers']['entries'][:1]
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    bundle = prepare_site(root, mode='reader', publication_profile='readers', max_chapter=1)
    page = bundle.files['index.html'].decode()
    assert 'IMPLICIT_NOVEL_PROSE' in page
    assert 'id="publication-chapter-1"' in page
    assert site_data(bundle)['publication']['chapters'] == [{'number': 1}]


def test_repeated_entries_stop_at_data_budget_before_resolving_all_selections(publication_project, monkeypatch):
    import lixity.site_export as module

    root, profiles, dossier, *_ = publication_project
    api.revise_record(root, 'dossier', dossier, changes={'body': '## Earlier\n\n' + 'Bounded publication text. ' * 100},
        expected_revision=2, change_kind='correction', reason='Synthetic bounded repeated content')
    profiles['readers']['entries'] = [{'dossier_id': dossier, 'section': 'Earlier'} for _ in range(40)]
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    monkeypatch.setattr(module, 'MAX_SITE_DATA_BYTES', 30000)
    resolved = []
    original = module._record
    def counted(*args, **kwargs):
        resolved.append(args[2])
        return original(*args, **kwargs)
    monkeypatch.setattr(module, '_record', counted)
    with pytest.raises(ResearchError, match='data limit'):
        prepare_site(root, mode='companion', publication_profile='readers', max_chapter=1)
    assert 0 < len(resolved) < 40


def test_total_prepared_envelope_includes_resource_mapping_in_data_budget(publication_project, monkeypatch):
    import lixity.site_export as module

    root, profiles, *_ = publication_project
    profiles['readers']['entries'] = [profiles['readers']['entries'][0]] * 40
    prepare_project_settings(root, {'site_publications': profiles}).commit()
    options = {'mode': 'companion', 'publication_profile': 'readers',
               'max_chapter': 1, 'include_source_files': True}
    prepared = site_data(prepare_site(root, **options))
    assert prepared['resources']
    complete_size = len(module._json(prepared))
    assert len(module._json(prepared['publication'])) < complete_size - 1
    monkeypatch.setattr(module, 'MAX_SITE_DATA_BYTES', complete_size - 1)
    with pytest.raises(ResearchError, match='data limit'):
        prepare_site(root, **options)
