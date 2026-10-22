"""Static website export is discoverable and guards native download scope."""

from pathlib import Path

import pytest

from lixity import api
from lixity.cli import main
from lixity.server.pdf_context import manuscript_pdf_token
from tests.support import recording_handler


def test_site_export_help_explains_explicit_disclosure(capsys):
    with pytest.raises(SystemExit) as stopped:
        main(["export-site", "--help"])
    assert stopped.value.code == 0
    output = capsys.readouterr().out
    for text in ("--include-research", "--include-source-files", "--project", "--output",
                 "read-only", "history", "new directory"):
        assert text in output


def test_site_export_is_discoverable_with_its_own_contract():
    command = next(item for item in api.about()["commands"] if item["name"] == "export-site")
    assert command["schema_version"] == "lixity-read-only-site/1"
    assert command["output"] == "directory|json"


@pytest.mark.parametrize("extra", [
    {"include_research": "yes"}, {"include_source_files": 1},
    {"include_source_files": True}, {"path": "/elsewhere"}, {"project_token": "stale"},
])
def test_site_download_rejects_ambiguous_scope_before_assembly(tmp_path: Path, extra):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose remains untouched.\n")
    handler = recording_handler(tmp_path, source_input=manuscript)
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title,
                                 thresholds=handler.thresholds)
    before = manuscript.read_bytes()
    handler._handle_site_export({"project_token": token, "include_research": False,
                                 "include_source_files": False, **extra})
    assert handler.response[0] == 400
    assert manuscript.read_bytes() == before
    assert not (tmp_path / "exports").exists()


def test_site_download_rejects_changed_selected_context(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose remains untouched.\n")
    handler = recording_handler(tmp_path, source_input=manuscript)
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title,
                                 thresholds=handler.thresholds)
    handler.__class__.language = "de"
    handler._handle_site_export({"project_token": token, "include_research": False,
                                 "include_source_files": False})
    assert handler.response[0] == 409


def test_native_site_download_contains_only_selected_project_without_writes(tmp_path: Path):
    import io
    import json
    import zipfile

    from tests.support import LoopbackServer, make_handler, send

    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nA synthetic door opens.\n\n## Two\n\nA synthetic window closes.\n")
    (tmp_path / "lixity.toml").write_text('title = "Reading copy"\nlanguage = "de"\n')
    (tmp_path / "private-notes.txt").write_text("Must not be implicitly published")
    handler = make_handler(tmp_path, source_input=manuscript, language="de")
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title,
                                 thresholds=handler.thresholds)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/site-export", payload={
            "project_token": token, "include_research": False, "include_source_files": False,
        })
        assert response.status == 200, response.body.decode(errors="replace")[:300]
        assert response.headers["content-type"] == "application/zip"
        assert response.headers["content-disposition"].endswith('reading-website.zip"')
        with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
            assert "index.html" in archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["schema_version"] == "lixity-read-only-site/1"
            document = archive.read("index.html").decode()
            assert 'data-read-only="true"' in document
            assert "A synthetic door opens." in document
            assert "Must not be implicitly published" not in document
            assert str(tmp_path) not in document
        cross_origin = send(server.port, "/api/site-export", payload={
            "project_token": token, "include_research": False, "include_source_files": False,
        }, headers={"Origin": "https://untrusted.example"})
        assert cross_origin.status == 403
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_cli_site_export_uses_project_language_and_prints_manifest(tmp_path: Path, capsys):
    import json

    source = tmp_path / "project"
    source.mkdir()
    (source / "manuscript.md").write_text("## Eins\n\nEine Tür öffnet sich.\n")
    (source / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "de"\n')
    destination = tmp_path / "reading-copy"
    assert main(["export-site", "--project", str(source), "-o", str(destination), "--json"]) == 0
    result = capsys.readouterr()
    manifest = json.loads(result.out)
    assert manifest == json.loads((destination / "manifest.json").read_text())
    assert manifest["schema_version"] == "lixity-read-only-site/1"
    assert '<html lang="de"' in (destination / "index.html").read_text()
    assert not (source / "exports").exists()
    assert main(["export-site", "--project", str(source), "-o", str(destination)]) == 1
    assert capsys.readouterr().err


def test_publication_profile_settings_require_current_project_token(tmp_path: Path):
    manuscript = tmp_path / 'manuscript.md'
    manuscript.write_text('## One\n\nSynthetic prose.\n')
    handler = recording_handler(tmp_path, source_input=manuscript)
    handler._handle_settings({'site_publications': {}})
    assert handler.response[0] == 409
    assert not (tmp_path / 'lixity.toml').exists()


def _publication_project(root: Path) -> Path:
    from lixity.config import prepare_project_settings
    from lixity.research import api as research

    root.mkdir()
    manuscript = root / 'private-draft-name.md'
    manuscript.write_text('## One\n\nEARLY_PUBLIC_PROSE opens the door.\n\n## Two\n\nLATER_PRIVATE_PROSE closes it.\n')
    (root / 'lixity.toml').write_text('manuscript = "private-draft-name.md"\nlanguage = "de"\n')
    research.init(root, title='Internal working archive')
    dossier = research.create_dossier(root, 'Internal dossier title',
                                      '## Place\n\nSELECTED_PUBLIC_NOTE\n\n## Secret\n\nPRIVATE_SECTION')['dossier_id']
    prepare_project_settings(root, {'site_publications': {'readers': {
        'title': 'Public reading companion', 'entries': [{'dossier_id': dossier,
            'section': 'Place', 'title': 'The place', 'reveal_after_chapter': 0}],
    }}}).commit()
    return manuscript


@pytest.mark.parametrize('mode', ['reader', 'companion'])
def test_publication_cli_cap_is_applied_before_output(tmp_path: Path, capsys, mode):
    import json

    project = tmp_path / 'project'
    _publication_project(project)
    output = tmp_path / 'website'
    assert main(['export-site', '--project', str(project), '-o', str(output),
                 '--mode', mode, '--publication-profile', 'readers', '--max-chapter', '1', '--json']) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest['mode'] == mode and manifest['publication']['max_chapter'] == 1
    page = (output / 'index.html').read_text()
    assert 'SELECTED_PUBLIC_NOTE' in page and 'PRIVATE_SECTION' not in page
    assert 'LATER_PRIVATE_PROSE' not in page and 'private-draft-name.md' not in page
    assert ('EARLY_PUBLIC_PROSE' in page) is (mode == 'reader')


@pytest.mark.parametrize('mode', ['reader', 'companion'])
def test_native_publication_download_uses_public_title_and_curated_scope(tmp_path: Path, mode):
    import io
    import json
    import zipfile

    from tests.support import LoopbackServer, make_handler, send

    project = tmp_path / 'project'
    manuscript = _publication_project(project)
    handler = make_handler(project, source_input=manuscript, language='de')
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title,
                                 thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        response = send(server.port, '/api/site-export', payload={
            'project_token': token, 'include_research': False, 'include_source_files': False,
            'mode': mode, 'publication_profile': 'readers', 'max_chapter': 1,
        })
    assert response.status == 200, response.body.decode(errors='replace')[:200]
    assert 'Public_reading_companion-reading-website.zip' in response.headers['content-disposition']
    assert 'private-draft-name' not in response.headers['content-disposition']
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['mode'] == mode and manifest['research']['included'] is False
        assert manifest['analysis'] is None
        page = archive.read('index.html').decode()
        assert 'SELECTED_PUBLIC_NOTE' in page and 'PRIVATE_SECTION' not in page
        assert 'LATER_PRIVATE_PROSE' not in page and 'private-draft-name.md' not in page
        assert ('EARLY_PUBLIC_PROSE' in page) is (mode == 'reader')
