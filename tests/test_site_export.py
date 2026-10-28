"""A project website is an explicit, portable read-only disclosure, not a backup."""

import hashlib
import importlib
import importlib.util
import io
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlencode

import pytest

from lixity.research import api
from lixity.research.repository import Repository, ResearchError
from tests.media_fixtures import png

pytestmark = pytest.mark.portability


def exporter():
    assert importlib.util.find_spec('lixity.site_export') is not None, 'Project website export is missing'
    return importlib.import_module('lixity.site_export')


def file_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def site_data(bundle):
    page = bundle.files['index.html'].decode()
    match = re.search(r'<script[^>]*id="lixity-site-data"[^>]*>(.*?)</script>', page, re.S)
    assert match, 'The shared app needs its frozen read provider'
    return json.loads(match[1])


def response(data, route, **query):
    suffix = '?' + urlencode(sorted(query.items())) if query else ''
    return data['responses']['/api/research/' + route + suffix]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'manuscript.md').write_text('# The gate\n\n## Arrival\n\nThe eastern gate was open. I could hear the rain.\n\n## Return\n\nThe keeper returned before dawn.\n')
    (root / 'lixity.toml').write_text('manuscript = "manuscript.md"\nlanguage = "en"\ntitle = "The gate"\n')
    (root / 'private-adapter.env').write_text('TOKEN=DO_NOT_INCLUDE_PRIVATE_ADAPTER')
    return root


@pytest.fixture
def research(project, tmp_path):
    api.init(project, title='The gate archive', language='en')
    source = tmp_path / 'external-evidence.txt'
    source.write_text('The register records an open gate.\n\nUNUSED_PRIVATE_SOURCE_PARAGRAPH belongs outside an excerpt export.\n')
    capture = api.ingest(project, source, title='Register', allow_retention=True,
                         context={'external_reference': {'provider': 'zotero', 'server_id': 'PRIVATE_ZOTERO_SERVER',
                             'library': 'users/1', 'item_key': 'ABCDEFGH', 'attachment_key': 'IJKLMNOP',
                             'item_version': 1, 'attachment_version': 1}})
    passages = api.get_source(project, capture['source_id'])['passages']
    dossier = api.create_dossier(project, 'Gate notes', '## Register\n\nEarlier reading.\n', evidence_ids=[passages[0]['id']])['dossier_id']
    claim = api.create_claim(project, title='An open gate', statement='The gate was open.', dossier_id=dossier)['claim_id']
    api.link_evidence(project, claim_id=claim, passage_id=passages[0]['id'])
    api.revise_record(project, 'claim', claim, changes={'title': 'A recorded open gate'}, expected_revision=1,
                      change_kind='correction', reason='Distinguish record from inference.')
    current = api.get_record(project, 'dossier', dossier)
    image = api.attach_dossier_image(project, dossier, png(), filename='one.png', alt='Synthetic pixel',
                                    allow_retention=True, expected_snapshot=current['snapshot'], expected_revision=1)
    return {'source': capture, 'passage': passages[0], 'dossier': dossier, 'claim': claim, 'image': image}


def test_default_site_is_native_analysis_only_and_does_not_copy_project_files(project):
    module = exporter()
    before = file_bytes(project)
    bundle = module.prepare_site(project)
    assert file_bytes(project) == before
    assert bundle.manifest['schema_version'] == 'lixity-read-only-site/1'
    assert bundle.manifest['manuscript']['source_sha256'] == hashlib.sha256((project / 'manuscript.md').read_bytes()).hexdigest()
    assert bundle.manifest['capabilities']['read_only'] is True
    assert bundle.manifest['capabilities']['research'] is False
    page = bundle.files['index.html'].decode()
    assert 'The eastern gate was open.' in page
    assert 'data-read-only="true"' in page
    assert str(project) not in page
    assert b'DO_NOT_INCLUDE_PRIVATE_ADAPTER' not in b'\n'.join(bundle.files.values())
    data = site_data(bundle)
    assert data['schema_version'] == 'lixity-read-only-site-data/1'
    assert data['responses'] == {}
    assert data['resources'] == {}
    assert not any(name.startswith(('research/', '.git/', '.lixity/')) for name in bundle.files)


def test_research_export_preserves_current_and_exact_versions_but_only_cited_source_text(project, research):
    module = exporter()
    before = file_bytes(project)
    bundle = module.prepare_site(project, include_research=True)
    assert file_bytes(project) == before
    data = site_data(bundle)
    for revision in (1, 2):
        got = response(data, 'record', id=research['claim'], kind='claim', revision=revision)
        expected = api.get_record(project, 'claim', research['claim'], revision=revision)
        for citation in expected['citations']:
            citation['context'].pop('external_reference', None)
        assert got == {'ok': True, **expected}
    current = response(data, 'record', id=research['claim'], kind='claim')
    assert current['record']['revision'] == 2
    assert response(data, 'history', id=research['claim'], kind='claim')['latest_revision'] == 2
    source = response(data, 'sources', id=research['source']['source_id'])
    assert source['text'] == ''
    assert [p['id'] for p in source['passages']] == [research['passage']['id']]
    assert source['context'].get('external_reference') is None
    public = b'\n'.join(bundle.files.values())
    assert b'UNUSED_PRIVATE_SOURCE_PARAGRAPH' not in public
    assert b'PRIVATE_ZOTERO_SERVER' not in public
    assert str(project).encode() not in public
    assert data['resources'] == {}
    assert not any(name.startswith('assets/sources/') for name in bundle.files)
    assert bundle.manifest['research']['snapshot'] == Repository(project).snapshot().digest
    assert bundle.manifest['capabilities']['source_files'] is False


def test_passage_context_export_matches_native_projection_without_writes(project, research):
    manuscript = project / 'manuscript.md'
    anchor = api.resolve_manuscript_anchor(project, manuscript, query='The eastern gate was open.')
    api.link_manuscript_claim(project, manuscript, research['claim'], claim_revision=2,
        selection={key: anchor[key] for key in ('start_line', 'end_line', 'paragraph_sha256', 'start', 'end', 'quote')},
        expected_project_id=anchor['project_id'], expected_snapshot=anchor['snapshot'],
        expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
    before = file_bytes(project)
    native = api.review_manuscript_links(project, manuscript, language='en', include_context=True)
    bundle = exporter().prepare_site(project, include_research=True)
    frozen = next(value for key, value in site_data(bundle)['responses'].items()
                  if key.startswith('/api/research/manuscript-review?'))
    for key in ('snapshot', 'source_path', 'current_source_sha256', 'links', 'passage_context'):
        assert frozen[key] == native[key]
    claim = frozen['passage_context']['paragraphs'][0]['groups'][0]['claims'][0]
    assert claim['versions'][0]['pinned']['revision'] == 2
    assert claim['versions'][0]['associations'][0]['anchor']['quote'] == 'The eastern gate was open.'
    assert file_bytes(project) == before


def test_source_files_are_a_separate_explicit_disclosure_and_preserve_exact_bytes(project, research):
    module = exporter()
    with pytest.raises((ResearchError, ValueError), match='research'):
        module.prepare_site(project, include_source_files=True)
    bundle = module.prepare_site(project, include_research=True, include_source_files=True)
    data = site_data(bundle)
    source = response(data, 'sources', id=research['source']['source_id'])
    assert 'UNUSED_PRIVATE_SOURCE_PARAGRAPH' in source['text']
    assert len(source['passages']) == 2
    assert data['resources']
    images = {virtual: relative for virtual, relative in data['resources'].items() if virtual.startswith('/api/research/image?')}
    assert images
    for relative in images.values():
        assert relative in bundle.files
        assert bundle.files[relative] == png()
    for virtual, relative in data['resources'].items():
        assert virtual.startswith(('/api/research/image?', '/api/site-resource?'))
        assert relative in bundle.files
    files = bundle.manifest['files']
    for name, descriptor in files.items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert descriptor['sha256'] == hashlib.sha256(bundle.files[name]).hexdigest()
        assert descriptor['byte_length'] == len(bundle.files[name])
    assert bundle.manifest['capabilities']['source_files'] is True


def test_zip_and_new_directory_share_the_verified_payload_and_never_overwrite(project, tmp_path):
    module = exporter()
    bundle = module.prepare_site(project)
    with zipfile.ZipFile(io.BytesIO(bundle.to_zip())) as archive:
        assert set(archive.namelist()) == set(bundle.files)
        assert all(archive.read(name) == payload for name, payload in bundle.files.items())
    destination = tmp_path / 'public-site'
    receipt = module.export_site(project, destination)
    assert receipt['schema_version'] == 'lixity-read-only-site/1'
    assert (destination / 'index.html').is_file()
    before = file_bytes(destination)
    with pytest.raises((ResearchError, ValueError), match='exist'):
        module.export_site(project, destination)
    assert file_bytes(destination) == before


def test_project_selection_and_output_paths_are_strict(project, tmp_path):
    module = exporter()
    outside = tmp_path / 'other.md'
    outside.write_text('## Other\n\nOUTSIDE_MANUSCRIPT_SENTINEL\n')
    with pytest.raises((ResearchError, ValueError), match=r'project|outside|escape'):
        module.prepare_site(project, manuscript=outside)
    (project / 'escape.md').symlink_to(outside)
    with pytest.raises((ResearchError, ValueError), match=r'project|symlink|escape'):
        module.prepare_site(project, manuscript='escape.md')
    for relative in ('research/site', '.lixity/site', '.git/site'):
        with pytest.raises((ResearchError, ValueError), match=r'output|destination|research|protected'):
            module.export_site(project, project / relative)
    assert not (project / '.git').exists()


def test_source_change_during_render_fails_before_publication(project, tmp_path, monkeypatch):
    module = exporter()
    original = module.render_analysis
    def changing(*args, **kwargs):
        page = original(*args, **kwargs)
        (project / 'manuscript.md').write_text('## Changed\n\nThe manuscript changed.\n')
        return page
    monkeypatch.setattr(module, 'render_analysis', changing)
    destination = tmp_path / 'changed-site'
    with pytest.raises((ResearchError, ValueError), match='changed'):
        module.export_site(project, destination)
    assert not destination.exists()


def test_archive_change_during_render_is_not_a_mixed_snapshot(project, research, tmp_path, monkeypatch):
    module = exporter()
    original = module.render_analysis
    def changing(*args, **kwargs):
        page = original(*args, **kwargs)
        api.create_claim(project, title='Later claim', statement='This was added during export.')
        return page
    monkeypatch.setattr(module, 'render_analysis', changing)
    destination = tmp_path / 'mixed-site'
    with pytest.raises((ResearchError, ValueError), match='changed'):
        module.export_site(project, destination, include_research=True)
    assert not destination.exists()


def test_inline_research_data_keeps_untrusted_script_text_inert(project):
    module = exporter()
    api.init(project, title='Synthetic archive')
    api.create_dossier(project, 'Literal script', '</script><script>UNTRUSTED_SENTINEL()</script>')
    bundle = module.prepare_site(project, include_research=True)
    page = bundle.files['index.html'].decode()
    assert '</script><script>UNTRUSTED_SENTINEL()' not in page
    assert any('UNTRUSTED_SENTINEL' in value.get('body', '')
               for key, value in site_data(bundle)['responses'].items() if key.startswith('/api/research/dossiers?'))


def test_normalized_destination_cannot_enter_protected_project_data(project, tmp_path):
    module = exporter()
    disguised = tmp_path / 'unused' / '..' / project.name / 'research' / 'site'
    with pytest.raises((ResearchError, ValueError), match=r'protected|output|destination'):
        module.export_site(project, disguised)
    assert not (project / 'research').exists()


def test_zip_refuses_uninventoried_files_and_changed_manifest(project):
    module = exporter()
    bundle = module.prepare_site(project)
    bundle.files['unexpected-private.txt'] = b'UNINVENTORIED'
    with pytest.raises((ResearchError, ValueError), match=r'inventory|changed|manifest'):
        bundle.to_zip()
    bundle.files.pop('unexpected-private.txt')
    bundle.files['manifest.json'] += b'\nUNREVIEWED'
    with pytest.raises((ResearchError, ValueError), match=r'changed|manifest'):
        bundle.to_zip()


def test_a_destination_created_at_publication_is_preserved_even_when_empty(project, tmp_path, monkeypatch):
    module = exporter()
    assert hasattr(module, '_publish_new_directory'), 'Exclusive atomic directory publication is missing'
    original = module._publish_new_directory
    destination = tmp_path / 'concurrent-site'
    saved = []
    def racing(stage, target):
        target.mkdir()
        saved.append(target.stat().st_ino)
        return original(stage, target)
    monkeypatch.setattr(module, '_publish_new_directory', racing)
    with pytest.raises((ResearchError, OSError), match=r'exist|appeared'):
        module.export_site(project, destination)
    assert destination.stat().st_ino == saved[0]
    assert list(destination.iterdir()) == []
    assert not list(tmp_path.glob('.lixity-site-*'))


def test_export_has_no_external_active_resource_policy(project):
    module = exporter()
    page = module.prepare_site(project).files['index.html'].decode()
    policy = re.search(r'<meta[^>]+http-equiv="Content-Security-Policy"[^>]+content="([^"]+)"', page)
    assert policy, 'Static output needs a resource boundary beyond the fetch adapter'
    assert "default-src 'none'" in policy[1]
    assert "connect-src 'self'" in policy[1]
    assert "img-src 'self' data: blob:" in policy[1]
    assert 'https:' not in policy[1]
    assert "form-action 'none'" in policy[1]


def test_source_passages_do_not_use_the_authored_history_budget(project, research, tmp_path, monkeypatch):
    module = exporter()
    from lixity.research.revisions import KINDS

    source = tmp_path / 'many-passages.txt'
    source.write_text('\n\n'.join(f'Synthetic register paragraph {number}.' for number in range(30)))
    api.ingest(project, source, allow_retention=True)
    snapshot = Repository(project).snapshot()
    authored_versions = sum(entry.kind in KINDS for entry in snapshot.manifest.entries)
    assert len(snapshot.revisions) > authored_versions
    monkeypatch.setattr(module, 'MAX_SITE_REVISIONS', authored_versions)
    before = file_bytes(project)

    bundle = module.prepare_site(project, include_research=True)

    assert file_bytes(project) == before
    data = site_data(bundle)
    for revision in (1, 2):
        record = response(data, 'record', kind='claim', id=research['claim'], revision=revision)['record']
        assert record['revision'] == revision
    assert bundle.manifest['research']['revision_count'] == len(snapshot.revisions)
    monkeypatch.setattr(module, 'MAX_SITE_REVISIONS', authored_versions - 1)
    destination = tmp_path / 'rejected-site'
    with pytest.raises(ResearchError, match=r'authored.*revision'):
        module.export_site(project, destination, include_research=True)
    assert not destination.exists() and file_bytes(project) == before


def test_config_change_and_export_limits_fail_explicitly(project, research, tmp_path, monkeypatch):
    module = exporter()
    with monkeypatch.context() as context:
        context.setattr(module, 'MAX_SITE_REVISIONS', 1)
        with pytest.raises((ResearchError, ValueError), match='revision'):
            module.prepare_site(project, include_research=True)
    with monkeypatch.context() as context:
        context.setattr(module, 'MAX_SITE_RESPONSES', 2)
        with pytest.raises((ResearchError, ValueError), match='limit'):
            module.prepare_site(project, include_research=True)
    with monkeypatch.context() as context:
        context.setattr(module, 'MAX_SITE_BYTES', 1024)
        with pytest.raises((ResearchError, ValueError), match='limit'):
            module.prepare_site(project)
    original = module.render_analysis
    def changed(*args, **kwargs):
        page = original(*args, **kwargs)
        with (project / 'lixity.toml').open('a') as stream:
            stream.write('z_mild = 3.0\n')
        return page
    monkeypatch.setattr(module, 'render_analysis', changed)
    with pytest.raises((ResearchError, ValueError), match='settings changed'):
        module.export_site(project, tmp_path / 'changed-settings')
    assert not (tmp_path / 'changed-settings').exists()


def test_research_collection_uses_one_snapshot_and_never_takes_a_writer_lock(project, research, monkeypatch):
    module = exporter()
    before = file_bytes(project)
    snapshots = []
    original = Repository.snapshot
    def observed(self, *args, **kwargs):
        snapshots.append(self.root)
        return original(self, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail('A reading website must not lock or index the source project')
    monkeypatch.setattr(Repository, 'snapshot', observed)
    monkeypatch.setattr(Repository, 'locked', forbidden)
    monkeypatch.setattr(api, 'reindex', forbidden)
    bundle = module.prepare_site(project, include_research=True)
    assert snapshots == [project]
    assert file_bytes(project) == before
    digest = bundle.manifest['research']['snapshot']
    assert all(value.get('snapshot', digest) == digest for value in site_data(bundle)['responses'].values())


def test_dangling_output_symlink_is_not_followed(project, tmp_path):
    module = exporter()
    outside = tmp_path / 'unrequested-output'
    target = tmp_path / 'website-link'
    target.symlink_to(outside, target_is_directory=True)
    with pytest.raises((ResearchError, ValueError), match=r'exist|symlink'):
        module.export_site(project, target)
    assert target.is_symlink()
    assert not outside.exists()


def test_duplicate_original_blobs_are_read_and_bundled_once(project, monkeypatch):
    module = exporter()
    api.init(project, title='Synthetic duplicate bytes')
    first = api.ingest_image(project, png(), filename='first.png', allow_retention=True)
    second = api.ingest_image(project, png(), filename='second.png', allow_retention=True)
    assert first['source_id'] != second['source_id']
    checksum = hashlib.sha256(png()).hexdigest()
    seen = []
    original = Repository.read_blob
    def observed(self, descriptor):
        seen.append(descriptor.sha256)
        return original(self, descriptor)
    monkeypatch.setattr(Repository, 'read_blob', observed)
    bundle = module.prepare_site(project, include_research=True, include_source_files=True)
    assert seen.count(checksum) == 1
    assert len([name for name in bundle.files if name.endswith('.png')]) == 1
    for item in (first, second):
        key = '/api/site-resource?' + urlencode(sorted({'source_id': item['source_id'], 'version_id': item['source_version_id']}.items()))
        assert bundle.files[site_data(bundle)['resources'][key]] == png()


def test_explicit_full_source_text_decode_failure_does_not_become_an_empty_success(project):
    from lixity.research.models import Activity, Blob, Extraction, Reference, Source, SourceVersion
    module = exporter()
    initialized = api.init(project, title='Synthetic invalid extracted text')
    def values():
        return api.envelope(initialized['project_id'], 'synthetic-test')
    raw = broken = b'\xff'
    source = Source(**values(), title='Invalid extraction', language='en')
    version = SourceVersion(**values(), source_ref=Reference(id=source.id), sequence=1,
                            blob=Blob(sha256=hashlib.sha256(raw).hexdigest(), byte_length=len(raw), media_type='text/plain'),
                            retention_confirmed=True)
    activity = Activity(**values(), source_version_ref=Reference(id=version.id), operation='extract_utf8',
                        implementation='utf8-paragraphs/1', status='succeeded')
    extraction = Extraction(**values(), source_version_ref=Reference(id=version.id), activity_ref=Reference(id=activity.id),
                            text_blob=Blob(sha256=hashlib.sha256(broken).hexdigest(), byte_length=1, media_type='text/plain'))
    repo = Repository(project)
    repo.commit([source, version, activity, extraction], {hashlib.sha256(raw).hexdigest(): raw, hashlib.sha256(broken).hexdigest(): broken}, repo.snapshot())
    # The established native fallback remains unchanged; export is explicitly strict.
    assert api.get_source(project, source.id)['text'] == '\ufffd'
    with pytest.raises((ResearchError, ValueError), match=r'text|decode|UTF'):
        module.prepare_site(project, include_research=True, include_source_files=True)


def test_withdrawn_dossier_keeps_explicit_history_without_a_current_alias(project, research):
    module = exporter()
    current = api.get_record(project, 'dossier', research['dossier'])
    api.withdraw(project, dossier_id=research['dossier'], expected_revision=2,
                 expected_snapshot=current['snapshot'], reason='Synthetic retired notes')
    data = site_data(module.prepare_site(project, include_research=True))
    history = response(data, 'history', kind='dossier', id=research['dossier'])
    assert history['availability'] == 'withdrawn'
    for revision in (1, 2):
        pinned = response(data, 'record', kind='dossier', id=research['dossier'], revision=revision)
        assert pinned['availability'] == 'withdrawn'
        assert pinned['record']['revision'] == revision
    with pytest.raises(ResearchError, match='withdrawn'):
        api.get_record(project, 'dossier', research['dossier'])
    with pytest.raises(KeyError):
        response(data, 'record', kind='dossier', id=research['dossier'])


def test_withdrawn_claim_retains_pinned_association_but_no_unavailable_view(project, research):
    from lixity.research.models import Reference, Tombstone
    module = exporter()
    repository = Repository(project)
    snapshot = repository.snapshot()
    repository.commit([Tombstone(**api.envelope(snapshot.project.id, 'synthetic-author'),
                                 target_ref=Reference(id=research['claim']), target_kind='claim',
                                 operation='withdraw', reason='Synthetic retired claim')], {}, snapshot)
    data = site_data(module.prepare_site(project, include_research=True))
    links = [value['record'] for key, value in data['responses'].items()
             if key.startswith('/api/research/record?') and value['record']['kind'] == 'evidence_link']
    assert links and all(item['claim_ref'] == {'id': research['claim'], 'revision': 1} for item in links)
    for revision in (None, 1, 2):
        query = {'kind': 'claim', 'id': research['claim']}
        if revision is not None:
            query['revision'] = revision
        with pytest.raises(KeyError):
            response(data, 'record', **query)


def test_unexpected_history_error_aborts_export_instead_of_omitting_records(project, research, monkeypatch):
    module = exporter()
    def unavailable(*args, **kwargs):
        raise ResearchError('Synthetic structural history failure')
    monkeypatch.setattr(module, '_record_history', unavailable)
    with pytest.raises(ResearchError, match='structural history failure'):
        module.prepare_site(project, include_research=True)


def test_manifest_scope_cannot_claim_research_that_was_not_exported(project):
    module = exporter()
    bundle = module.prepare_site(project)
    bundle.manifest['capabilities']['research'] = True
    bundle.files['manifest.json'] = (json.dumps(bundle.manifest, ensure_ascii=False,
        separators=(',', ':'), sort_keys=True) + '\n').encode()
    with pytest.raises(ValueError, match='scope'):
        bundle.to_zip()


def test_review_export_and_native_workspace_share_configured_supplementary_reports(project, monkeypatch):
    from lixity.server import views

    module = exporter()
    config = project / 'lixity.toml'
    config.write_text(config.read_text() + '\n[motifs]\nWeather = "rain"\n'
                      '\n[scene_analysis.assignments]\n"1:1" = "quiet"\n'
                      '\n[scene_analysis.groups.quiet.targets]\nasl = [2, 8]\n')
    before = file_bytes(project)
    projections = []
    for adapter in (views, module):
        render = adapter.render_analysis
        def observed(*args, _render=render, **kwargs):
            projections.append({key: kwargs[key] for key in
                                ('dialogue', 'pacing', 'motifs', 'showing', 'scenes')})
            return _render(*args, **kwargs)
        monkeypatch.setattr(adapter, 'render_analysis', observed)
    native, _ = views.build_server_dashboard(str(project / 'manuscript.md'), project_root=project)
    bundle = module.prepare_site(project)
    assert projections[0] == projections[1]
    assert projections[0]['motifs']['motifs'][0]['name'] == 'Weather'
    assert projections[0]['scenes']['items'][0]['group'] == 'quiet'
    assert 'The eastern gate was open.' in native
    assert 'The eastern gate was open.' in bundle.files['index.html'].decode()
    assert file_bytes(project) == before


@pytest.mark.parametrize(('characters', 'author', 'message'), [
    ('characters = []', 'author_name = 17', 'characters must be a table'),
    ('[characters.Mara]\npov_in_chapters = [3]', 'author_name = 17', 'Author name must be a string'),
    ('[characters.Mara]\npov_in_chapters = [3]', 'author_name = "Synthetic Author"',
     'Declared POV chapters no longer match'),
])
def test_review_export_preserves_character_and_author_error_precedence(project, characters, author, message):
    config = project / 'lixity.toml'
    config.write_text(config.read_text() + '\n' + author + '\n' + characters + '\n')
    before = file_bytes(project)
    with pytest.raises(ValueError, match=message):
        exporter().prepare_site(project)
    assert file_bytes(project) == before
