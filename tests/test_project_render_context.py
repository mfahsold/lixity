"""Selected projects share root-local analysis settings across reading exports."""

from lixity.pipeline import resolve_document_config
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.server.views import build_server_dashboard
from lixity.site_export import prepare_site
from tests.support import recording_handler


def configured_project(tmp_path, monkeypatch):
    home = tmp_path / "synthetic-home"
    (home / ".config").mkdir(parents=True)
    (home / ".config/lixity.toml").write_text('min_paragraph_length_for_oneliner=999\n[motif_regexes]\nAmbient="keeper"\n')
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "selected-project"
    source = project / "drafts/manuscript.md"
    source.parent.mkdir(parents=True)
    source.write_text('# Synthetic title\n\n### Arrival\n\nThe gate opened in the rain.\n\n'
                      '### Return\n\nThe keeper closed the gate.\n')
    (project / "lixity.toml").write_text(
        'manuscript="drafts/manuscript.md"\nlanguage="en"\ntitle="Selected project"\n'
        "chapter_regex='(?m)^###\\s+'\n[motif_regexes]\nRoot='gate'\n"
    )
    (source.parent / "lixity.toml").write_text(
        "language='de'\nchapter_regex='(?m)^##\\s+'\n[motif_regexes]\nNested='rain'\n"
    )
    return project, source


def test_selected_project_native_and_website_use_identical_root_settings(tmp_path, monkeypatch):
    from lixity.server import views

    project, source = configured_project(tmp_path, monkeypatch)
    def ambient_forbidden(*args, **kwargs):
        raise AssertionError('An explicit selected project must not read ambient settings')
    monkeypatch.setattr(views, 'load_project_config', ambient_forbidden)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    native, info = build_server_dashboard(str(source), project_root=project, language="en")
    site = prepare_site(project).files['index.html'].decode()
    for page in (native, site):
        assert '>Root<' in page
        assert '>Nested<' not in page
        assert '>Ambient<' not in page
        assert '<html lang="en">' in page
        assert 'id="ch-2"' in page
    assert info['chapters'] == 2
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_native_pdf_uses_the_same_selected_root_context(tmp_path, monkeypatch):
    from lixity.server import routes_pdf

    project, source = configured_project(tmp_path, monkeypatch)
    handler = recording_handler(project, source_input=source, language="en")
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
        language=handler.language, title=handler.title, thresholds=handler.thresholds)
    captured = {}
    def compose(text, **options):
        captured.update(options)
        config, resolved = resolve_document_config(text, options['language'], project_config=options['project_config'])
        assert config.chapter_regex == r'(?m)^###\s+'
        assert config.motif_regexes == {'Root': 'gate'}
        assert config.min_paragraph_length_for_oneliner == 25
        assert resolved.key == 'en'
        return b'%PDF-1.4 synthetic root-context check'
    monkeypatch.setattr(routes_pdf.pdf_export, 'compose_pdf', compose)
    sent = []
    monkeypatch.setattr(handler, '_send', lambda code, body, *args, **kwargs: sent.append((code, body)))
    handler._handle_manuscript_pdf({'layout':'report', 'project_token':token})
    assert sent == [(200, b'%PDF-1.4 synthetic root-context check')]
    assert captured['identity_config'] == captured['project_config']


def test_legacy_renderer_without_project_keeps_source_nearest_settings(tmp_path, monkeypatch):
    _project, source = configured_project(tmp_path, monkeypatch)
    page, _info = build_server_dashboard(str(source), language='en')
    assert '>Nested<' in page
    assert '>Root<' not in page
