"""Curated publication profiles never imply permission to expose the archive."""

import html
import importlib
import importlib.util
import json
import re

import pytest

from lixity.config import (
    configuration_metadata,
    load_project_config,
    prepare_project_settings,
    read_explicit_project_config,
)

DOSSIER = 'urn:uuid:00000000-0000-4000-8000-000000000001'


def publications():
    assert importlib.util.find_spec('lixity.site_publications') is not None, 'Curated publication profiles are missing'
    return importlib.import_module('lixity.site_publications')


def profile(**entry):
    return {'title': 'A companion', 'introduction': 'Author-approved introduction.',
            'entries': [{'dossier_id': DOSSIER, **entry}]}


def test_profiles_normalize_explicit_defaults_without_export_permissions():
    module = publications()
    values = module.validate_site_publications({'readers': profile()})
    assert values['readers']['entries'] == [{
        'dossier_id': DOSSIER, 'revision': None, 'section': None,
        'reveal_after_chapter': 0, 'title': None,
        'include_citations': False, 'include_geography': False,
    }]
    assert 'include_source_files' not in values['readers']


@pytest.mark.parametrize('entry', [
    {'revision': True}, {'revision': 0}, {'reveal_after_chapter': True},
    {'reveal_after_chapter': -1}, {'reveal_after_chapter': '2'},
    {'include_citations': 1}, {'section': ''}, {'dossier_id': 'not-an-id'},
    {'include_source_files': True},
])
def test_invalid_profile_entries_fail_instead_of_changing_scope(entry):
    module = publications()
    with pytest.raises(ValueError):
        module.validate_site_publications({'readers': profile(**entry)})


def test_profile_keys_and_unknown_profile_fields_fail_clearly():
    module = publications()
    for raw in ([], {'../unsafe': profile()}, {'readers': {**profile(), 'allow_history': True}}):
        with pytest.raises(ValueError):
            module.validate_site_publications(raw)


def test_publication_profiles_use_preserving_root_local_settings(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    path = root / 'lixity.toml'
    original = '# Keep\ntitle = "Before" # Keep title comment\n[custom]\nunchanged = true\n'
    path.write_text(original)
    prepared = prepare_project_settings(root, {'site_publications': {'readers': profile(revision=2, reveal_after_chapter=3)}})
    assert path.read_text() == original
    prepared.commit()
    settings = read_explicit_project_config(root)
    assert settings['site_publications']['readers']['entries'][0]['revision'] == 2
    assert '[custom]\nunchanged = true\n' in path.read_text()
    prepare_project_settings(root, {'title': 'After'}).commit()
    assert read_explicit_project_config(root)['site_publications'] == settings['site_publications']
    # Publication curation never inherits from user or ancestor project settings.
    home = tmp_path / 'home'
    (home / '.config').mkdir(parents=True)
    (home / '.config/lixity.toml').write_text(path.read_text())
    monkeypatch.setenv('HOME', str(home))
    child = root / 'child'
    child.mkdir()
    assert 'site_publications' not in load_project_config(child)
    assert 'site_publications' not in read_explicit_project_config(child)


def test_nested_profile_updates_preserve_other_tables_and_reject_invalid_changes(tmp_path):
    path = tmp_path / 'lixity.toml'
    path.write_text('[site_publications.readers]\ntitle = "Before"\nintroduction = "Approved"\n'
                    f'entries = [{{dossier_id = "{DOSSIER}", reveal_after_chapter = 0}}]\n'
                    '[custom]\nkeep = "literal"\n')
    prepare_project_settings(tmp_path, {'site_publications': {'readers': profile(section='History')}}).commit()
    assert '[custom]\nkeep = "literal"\n' in path.read_text()
    assert read_explicit_project_config(tmp_path)['site_publications']['readers']['entries'][0]['section'] == 'History'
    before = path.read_bytes()
    with pytest.raises(ValueError):
        prepare_project_settings(tmp_path, {'site_publications': {'readers': profile(reveal_after_chapter=-1)}})
    assert path.read_bytes() == before


def test_configuration_discovery_describes_curated_profiles_separately_from_imprint():
    schema = configuration_metadata()
    assert 'site_publications' in schema['accepted_keys']
    assert 'site_publications' in schema['project_only_keys']
    assert 'site_publications' in schema['native_settings']['persisted_keys']
    assert schema['site_publications_schema']['type'] == 'object'
    assert 'site_publications' not in schema['publication_schema']['properties']


def test_native_editor_uses_author_project_profiles_and_that_projects_context(tmp_path):
    from lixity.server.pdf_context import research_context_token
    from lixity.server.views import build_server_dashboard

    project = tmp_path / 'author-project'
    other = tmp_path / 'other-research'
    project.mkdir()
    other.mkdir()
    manuscript = project / 'manuscript.md'
    manuscript.write_text('## One\n\nA synthetic gate opens.\n')
    prepare_project_settings(project, {'site_publications': {'readers': profile()}}).commit()
    document, _ = build_server_dashboard(str(manuscript), project_root=project, research_root=other)
    editor = re.search(r'<fieldset[^>]*id="site-publication-editor"[^>]*>', document)[0]
    initial = re.search(r'data-initial="([^"]*)"', editor)[1]
    assert json.loads(html.unescape(initial))['readers']['title'] == 'A companion'
    assert f'data-context-token="{research_context_token(project)}"' in editor
    assert f'data-context-token="{research_context_token(other)}"' not in editor
