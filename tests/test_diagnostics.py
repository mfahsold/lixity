"""Installation diagnostics distinguish source, distribution and live service."""

import json
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace

import pytest

from lixity import __version__


@pytest.fixture
def installed(monkeypatch):
    from lixity import diagnostics

    monkeypatch.setattr(diagnostics.metadata, 'distribution',
                        lambda _name: SimpleNamespace(version=__version__))
    monkeypatch.setattr(diagnostics, 'service_status', lambda port: {
        'schema_version': 'lixity-service-status/1', 'ok': True,
        'state': 'stopped', 'running': False, 'port': port,
        'pid': None, 'backend': None, 'running_version': None,
        'installed_version': __version__, 'url': f'http://127.0.0.1:{port}/',
    })
    return diagnostics


def test_consistent_installation_and_stopped_service_are_healthy(installed):
    report = installed.doctor(port=59991)
    assert report['schema_version'] == 'lixity-doctor/1'
    assert report['ok'] is True and report['issues'] == []
    assert report['installation']['cli_version'] == __version__
    assert report['installation']['distribution_version'] == __version__
    assert Path(report['installation']['module_path']).name == '__init__.py'
    assert Path(report['installation']['interpreter']).is_absolute()
    assert report['service']['running'] is False and report['service']['port'] == 59991
    assert report['schemas']['reading_website'] == 'lixity-read-only-site/1'


def test_distribution_mismatch_is_explicit_and_never_repaired(installed, monkeypatch):
    monkeypatch.setattr(installed.metadata, 'distribution',
                        lambda _name: SimpleNamespace(version='1.15.0.dev0'))
    report = installed.doctor()
    assert report['ok'] is False
    assert report['installation']['distribution_version'] == '1.15.0.dev0'
    assert [issue['code'] for issue in report['issues']] == ['distribution-version-mismatch']


@pytest.mark.parametrize('error', [metadata.PackageNotFoundError('lixity'), OSError('PRIVATE_METADATA_PATH')])
def test_unavailable_metadata_remains_unknown(installed, monkeypatch, error):
    def unavailable(_name):
        raise error
    monkeypatch.setattr(installed.metadata, 'distribution', unavailable)
    report = installed.doctor()
    assert report['ok'] is False and report['installation']['distribution_version'] is None
    assert 'PRIVATE_METADATA_PATH' not in json.dumps(report)
    assert report['issues'][0]['code'] == 'distribution-metadata-unavailable'


def test_running_older_service_reports_restart_need(installed, monkeypatch):
    previous = installed.service_status
    monkeypatch.setattr(installed, 'service_status', lambda port: {
        **previous(port), 'state': 'running', 'running': True, 'running_version': '0.7.3',
    })
    report = installed.doctor()
    assert report['ok'] is False
    assert [issue['code'] for issue in report['issues']] == ['service-version-mismatch']


def test_unknown_service_does_not_look_stopped(installed, monkeypatch):
    monkeypatch.setattr(installed, 'service_status', lambda port: {
        'schema_version': 'lixity-service-status/1', 'ok': False,
        'state': 'unknown', 'running': None, 'port': port,
    })
    report = installed.doctor()
    assert report['service']['running'] is None and report['ok'] is False
    assert report['issues'][0]['code'] == 'service-inspection-unavailable'


def test_doctor_never_reads_project_configuration(installed, tmp_path, monkeypatch):
    import lixity.cli as cli

    monkeypatch.chdir(tmp_path)
    (tmp_path / 'lixity.toml').write_text('PRIVATE_MANUSCRIPT = "unclosed')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    def forbidden(*_args, **_kwargs):
        pytest.fail('Installation diagnostics must not load project or user settings')
    monkeypatch.setattr(cli, 'load_project_config', forbidden)
    monkeypatch.setattr(cli, 'read_explicit_project_config', forbidden)
    report = installed.doctor()
    assert 'PRIVATE_MANUSCRIPT' not in json.dumps(report)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_doctor_cli_json_and_discovery(installed, capsys):
    from lixity import api
    from lixity.cli import main

    assert main(['doctor', '--port', '59991', '--json']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['service']['port'] == 59991
    command = next(item for item in api.about()['commands'] if item['name'] == 'doctor')
    assert command['schema_version'] == report['schema_version']


def test_doctor_cli_mismatch_is_machine_readable_and_nonzero(installed, monkeypatch, capsys):
    from lixity.cli import main

    monkeypatch.setattr(installed.metadata, 'distribution', lambda _name: SimpleNamespace(version='0.0.0'))
    assert main(['doctor', '--json']) == 1
    assert json.loads(capsys.readouterr().out)['issues'][0]['code'] == 'distribution-version-mismatch'


@pytest.mark.parametrize('port', [True, 0, 65536])
def test_invalid_port_fails_before_inspection(installed, monkeypatch, port):
    def forbidden(_port):
        pytest.fail('Invalid ports must not inspect local services')
    monkeypatch.setattr(installed, 'service_status', forbidden)
    with pytest.raises(ValueError, match='port'):
        installed.doctor(port=port)


def test_real_service_inspection_creates_no_directories(installed, tmp_path, monkeypatch):
    from lixity.service import service_status

    monkeypatch.setenv('LIXITY_SERVICE_STATE_DIR', str(tmp_path / 'absent-state'))
    monkeypatch.setenv('LIXITY_SERVICE_RUNTIME_DIR', str(tmp_path / 'absent-runtime'))
    monkeypatch.setattr(installed, 'service_status', service_status)
    assert installed.doctor(port=59989)['service']['state'] in {'stopped', 'busy'}
    assert list(tmp_path.iterdir()) == []


def test_running_service_with_unavailable_version_does_not_claim_a_mismatch(installed, monkeypatch):
    previous = installed.service_status
    monkeypatch.setattr(installed, 'service_status', lambda port: {
        **previous(port), 'state': 'running', 'running': True, 'running_version': None,
    })
    report = installed.doctor()
    assert report['ok'] is False
    assert [issue['code'] for issue in report['issues']] == ['service-version-unavailable']


@pytest.mark.parametrize('arguments,environment', [
    (['doctor', '--json'], 'synthetic-private-source-secret'),
    (['doctor', '--port', '0', '--json'], '8765'),
])
def test_invalid_cli_service_port_is_sanitized_json(installed, monkeypatch, capsys, arguments, environment):
    from lixity.cli import main

    monkeypatch.setenv('LIXITY_PORT', environment)
    assert main(arguments) == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report['schema_version'] == 'lixity-doctor/1' and report['ok'] is False
    assert report['error']['code'] == 'invalid-service-port'
    assert 'synthetic-private-source-secret' not in output.out + output.err
