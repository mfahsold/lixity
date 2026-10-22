"""Disclosure choices are strict and never become stored project permissions."""

import pytest
from pydantic import ValidationError

from lixity.site_contracts import SiteExportOptions, SiteExportRequest


@pytest.mark.parametrize('invalid', [None, 0, 1, 'true', [], {}])
def test_export_flags_are_booleans_in_the_shared_model(invalid):
    with pytest.raises(ValidationError):
        SiteExportOptions(include_research=invalid)


def test_source_disclosure_requires_research_and_unknown_options_fail():
    assert SiteExportOptions().model_dump() == {'include_research': False, 'include_source_files': False, 'mode': 'review', 'publication_profile': None, 'max_chapter': None}
    with pytest.raises(ValidationError, match='requires --include-research'):
        SiteExportOptions(include_source_files=True)
    with pytest.raises(ValidationError):
        SiteExportOptions(recipient='Not a hosted permissions model')


def test_native_request_requires_context_and_both_explicit_choices():
    with pytest.raises(ValidationError):
        SiteExportRequest(project_token='a' * 64)
    request = SiteExportRequest(project_token='a' * 64, include_research=True, include_source_files=False)
    assert request.include_research is True
    invalid_context = 'stale'
    with pytest.raises(ValidationError):
        SiteExportRequest(project_token=invalid_context, include_research=False, include_source_files=False)
    with pytest.raises(ValidationError):
        SiteExportRequest(project_token='a' * 64, include_research=False, include_source_files=False,
                          path='/must-not-select-a-project')


def test_public_demo_manifest_uses_the_same_publication_contract():
    from pathlib import Path

    from lixity.site_contracts import SiteManifest

    path = Path(__file__).resolve().parents[1] / 'docs/demo/manifest.json'
    if not path.exists():
        pytest.skip('Public demo has not been generated in this checkout')
    manifest = SiteManifest.model_validate_json(path.read_bytes())
    assert manifest.entrypoint == 'report.html'
    assert manifest.capabilities.read_only is True


@pytest.mark.parametrize('mode', ['reader', 'companion'])
def test_publication_modes_require_curated_scope_and_exclude_raw_archive(mode):
    with pytest.raises(ValidationError, match='publication-profile'):
        SiteExportOptions(mode=mode)
    with pytest.raises(ValidationError, match='internal archive'):
        SiteExportOptions(mode=mode, publication_profile='readers', include_research=True)
    selected = SiteExportOptions(mode=mode, publication_profile='readers',
                                 include_source_files=True, max_chapter=3)
    assert selected.include_research is False and selected.max_chapter == 3


@pytest.mark.parametrize('options', [
    {'publication_profile': 'readers'}, {'max_chapter': 3},
    {'mode': 'companion', 'publication_profile': '../outside'},
    {'mode': 'reader', 'publication_profile': 'readers', 'max_chapter': True},
])
def test_invalid_publication_options_fail_in_the_shared_model(options):
    with pytest.raises(ValidationError):
        SiteExportOptions(**options)
