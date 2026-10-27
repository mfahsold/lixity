"""One HTTP origin retains independent synthetic project workspaces."""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from threading import Event, RLock

from lixity.server import LixityServerHandler
from tests.support import LoopbackServer


def test_two_projects_keep_their_tabs_and_routes_independent(tmp_path, monkeypatch):
    from lixity.server.workspaces import WorkspaceRegistry

    files = []
    for name in ('First', 'Second'):
        project = tmp_path / name
        project.mkdir()
        (project / 'lixity.toml').write_text(f'title = "{name}"\nlanguage = "en"\n')
        source = project / 'manuscript.md'
        source.write_text(f'## {name}\n\nA bird watches the {name.lower()} courtyard.\n')
        files.append(source)
    entered, release = Event(), Event()
    def slow_open(self, payload):
        entered.set()
        release.wait(2)
        return LixityServerHandler._handle_project_open(self, payload)
    handler = type('SyntheticApp', (LixityServerHandler,), {
        '_handle_project_open': slow_open,
        '_workspace_lock': RLock(), 'workspace_root': str(tmp_path), 'source_input': None,
        'exports_dir': str(tmp_path / 'exports'), 'dashboard_info': {}, 'dashboard_html': '',
        'project_open_overrides': {'language': 'fr'},
    })
    handler.refresh()
    with LoopbackServer(handler) as server:
        registry = WorkspaceRegistry(handler)
        server._server.workspaces = registry
        def request(method, path, body=None):
            connection = HTTPConnection('127.0.0.1', server.port)
            payload = json.dumps(body) if body is not None else None
            connection.request(method, path, payload, {'Content-Type': 'application/json'})
            response = connection.getresponse()
            value = response.read().decode()
            connection.close()
            return response.status, value
        status, raw = request('GET', '/')
        assert status == 303
        urls = []
        for source in files:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(request, 'POST', '/api/project-open/', {'path': str(source)})
                assert entered.wait(1)
                if not release.is_set():
                    assert len(registry.items()) == 1, 'An unprepared candidate is not advertised'
                release.set()
                status, raw = pending.result(timeout=3)
            assert status == 200, raw
            urls.append(json.loads(raw)['workspace_url'])
        assert urls[0] != urls[1]
        monkeypatch.setattr('lixity.server.handler.worker_health', lambda target: {
            'target': target, 'state': 'ready' if target == 'local' else 'unavailable',
            'transport': 'loopback' if target == 'local' else 'ssh'})
        status, raw = request('GET', urls[0] + 'api/runtime')
        assert status == 200
        observation = json.loads(raw)
        assert observation['schema_version'] == 'lixity-runtime-local/1'
        assert [item['state'] for item in observation['audio']['targets']] == ['ready', 'unavailable']
        assert str(tmp_path) not in raw and 'courtyard' not in raw

        for index, url in enumerate(urls):
            status, html = request('GET', url)
            assert status == 200
            assert f'data-api="{url}api"' in html
            status, raw = request('GET', url + 'api')
            assert status == 200
            assert json.loads(raw)['project']['manuscript_loaded']
            assert json.loads(raw)['project']['language'] == 'en', 'Startup language must not override another project'
            assert registry.items()[index + 1]['url'] == url
        first_html = request('GET', urls[0])[1]
        token = re.search(r'<form id="settings-form"[^>]*data-project-token="([^"]+)"', first_html)[1]
        # Matching origin is insufficient: a project's token cannot cross scopes.
        status, _ = request('GET', urls[1] + 'api/project-structure?project_token=' + token)
        assert status == 409
        export = files[0].parent / 'exports'
        export.mkdir(exist_ok=True)
        (export / 'result.json').write_text('{"synthetic":true}')
        assert request('GET', urls[0] + 'artifact/result.json?project_token=' + token)[0] == 200
        assert request('GET', urls[1] + 'artifact/result.json?project_token=' + token)[0] == 409
        assert 'First' in request('GET', urls[0])[1]
        assert 'Second' in request('GET', urls[1])[1]
        status, _ = request('GET', '/w/' + '0' * 32 + '/')
        assert status == 410
        # A failed project open cannot replace an existing project.
        status, _ = request('POST', urls[0] + 'api/project-open', {'path': str(tmp_path / 'missing')})
        assert status == 404
        assert len(registry.items()) == 3
        # A second view of the same source still owns distinct audio jobs.
        from lixity.speech import generate_silence_wav
        from lixity.speech_jobs import SpeechJobs
        status, raw = request('POST', '/api/project-open', {'path': str(files[0])})
        same_project = json.loads(raw)['workspace_url']
        def render(_source, output, **_kwargs):
            output.write_bytes(generate_silence_wav(0.01))
        server._server.speech_jobs = SpeechJobs(renderer=render)
        digest = re.search(r'data-manuscript-source-sha256="([^"]+)"', first_html)[1]
        payload = {'project_token': token, 'source_sha256': digest, 'mode': 'preview', 'chapter': 1,
                   'profile': {'engine': 'qwen3', 'voice': 'Ryan', 'language': 'en'}}
        status, raw = request('POST', urls[0] + 'api/speech-render', payload)
        assert status == 202, raw
        identifier = json.loads(raw)['job']['id']
        query = f'?project_token={token}&source_sha256={digest}&id={identifier}'
        for _ in range(100):
            status, raw = request('GET', urls[0] + 'api/speech-job' + query)
            if json.loads(raw)['job']['state'] == 'ready':
                break
            time.sleep(0.01)
        assert json.loads(raw)['job']['state'] == 'ready'
        assert request('GET', same_project + 'api/speech-job' + query)[0] == 400
        assert request('GET', same_project + 'api/speech-audio' + query)[0] == 400
        status, raw = request('POST', urls[0] + 'api/workspace-close', {'id': urls[1].split('/')[2]})
        assert status == 200, raw
        assert request('GET', urls[1])[0] == 410
        assert files[1].is_file()
        assert 'First' in request('GET', urls[0])[1]
