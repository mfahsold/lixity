"""Read-only audio status exposes model identities without manuscript content."""

import json

import pytest

from lixity.speech_profiles import QWEN_DESIGN_MODEL, QWEN_MODEL


def test_status_without_project_only_reports_actual_workers(monkeypatch):
    from lixity.speech_status import audio_status

    def probe(target):
        return {'target':target, 'state':'ready', 'transport':'ssh' if target == 'jetson' else 'loopback',
                'model':QWEN_DESIGN_MODEL if target == 'jetson' else QWEN_MODEL}
    monkeypatch.setattr('lixity.speech_status.worker_health', probe)
    status = audio_status()
    assert status['schema_version'] == 'lixity-audio-status/1'
    assert status['project'] is None
    assert [item['target'] for item in status['targets']] == ['local', 'jetson']
    assert all(item['model_matches'] is None for item in status['targets'])


def test_status_project_profile_and_mismatch_without_private_details(tmp_path, monkeypatch):
    from lixity.speech_status import audio_status

    (tmp_path/'lixity.toml').write_text('''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Test narrator"
engine = "qwen3-design"
voice = "design"
language = "de"
voice_description = "private voice instructions"
instructions = "private delivery"
[audio.profiles.narrator.pronunciations]
Secret = "private spelling"
''')
    monkeypatch.setattr('lixity.speech_status.worker_health',lambda target:{
        'target':target,'state':'ready','transport':'loopback' if target=='local' else 'ssh',
        'model':QWEN_MODEL if target=='local' else QWEN_DESIGN_MODEL})
    status=audio_status(tmp_path)
    assert status['project']['selected_profile']=='narrator'
    assert status['project']['settings_source']=='configured'
    assert status['project']['profiles']==[{'id':'narrator','name':'Test narrator',
        'engine':'qwen3-design','voice':'design','language':'de'}]
    assert [item['model_matches'] for item in status['targets']]==[False,True]
    assert 'private' not in json.dumps(status)


def test_status_default_profile_is_identified_and_unavailable_is_unknown(tmp_path, monkeypatch):
    from lixity.speech_status import audio_status

    (tmp_path/'lixity.toml').write_text('language = "de"\n')
    monkeypatch.setattr('lixity.speech_status.worker_health',lambda target:{
        'target':target,'state':'unavailable','transport':'loopback' if target=='local' else 'ssh','model':None})
    status=audio_status(tmp_path)
    assert status['project']['settings_source']=='default'
    assert status['project']['profiles'][0]['language']=='de'
    assert all(item['model_matches'] is None for item in status['targets'])


def test_invalid_or_missing_project_fails_explicitly(tmp_path):
    from lixity.speech_status import audio_status

    with pytest.raises(ValueError, match='project'):
        audio_status(tmp_path/'missing')
    (tmp_path/'lixity.toml').write_text('language = "unterminated\n')
    with pytest.raises(ValueError, match='configuration'):
        audio_status(tmp_path)


def test_unresolved_speech_language_is_not_guessed_from_auto_project(tmp_path, monkeypatch):
    from lixity.speech_status import audio_status

    (tmp_path/'lixity.toml').write_text('language = "auto"\n')
    monkeypatch.setattr('lixity.speech_status.worker_health',lambda target:{
        'target':target,'state':'ready','transport':'loopback' if target=='local' else 'ssh','model':QWEN_MODEL})
    status=audio_status(tmp_path)
    assert status['project']['settings_source']=='default'
    assert status['project']['selected_profile'] is None
    assert status['project']['profiles']==[]
    assert status['project']['profile_issue']=='speech_language_unresolved'
    assert all(row['model_matches'] is None for row in status['targets'])


def test_cli_status_json_and_german_text_are_consistent(tmp_path, monkeypatch, capsys):
    from lixity.cli import main

    (tmp_path / 'lixity.toml').write_text('language = "de"\n')
    monkeypatch.setenv('LIXITY_LANG', 'de')
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda target: {
        'target': target, 'state': 'ready', 'transport': 'ssh' if target == 'jetson' else 'loopback',
        'model': QWEN_DESIGN_MODEL if target == 'jetson' else QWEN_MODEL})
    assert main(['audio-status', '--project', str(tmp_path), '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert [row['model_matches'] for row in data['targets']] == [True, False]
    assert main(['audio-status', '--project', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'Gewähltes Profil: narrator' in output and 'Modell passt: ja' in output and 'Modell passt: nein' in output


def test_status_can_compare_unsaved_engine_override_without_project(monkeypatch):
    from lixity.speech_status import audio_status
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda target: {
        'target': target, 'state': 'ready', 'transport': 'ssh' if target == 'jetson' else 'loopback',
        'model': QWEN_DESIGN_MODEL if target == 'jetson' else QWEN_MODEL})
    status = audio_status(engine='qwen3-design')
    assert status['comparison_engine'] == 'qwen3-design'
    assert [row['model_matches'] for row in status['targets']] == [False, True]
