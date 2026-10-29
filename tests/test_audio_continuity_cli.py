"""Audio guidance should distinguish model identities from voice continuity."""

import json

import pytest

from lixity.cli import main
from lixity.speech_profiles import QWEN_DESIGN_MODEL


def test_read_aloud_help_describes_continuity_and_neutral_comparison(capsys, monkeypatch):
    monkeypatch.setenv('LIXITY_LANG', 'en')
    with pytest.raises(SystemExit) as error:
        main(['read-aloud', '--help'])
    assert error.value.code == 0
    output = capsys.readouterr().out
    assert 'independently' in output
    assert 'reference' in output.lower()
    assert 'free-form' in output
    assert 'pronunciation' in output.lower()
    assert '--preview' in output


def test_design_status_gives_localized_human_guidance_without_changing_json(tmp_path, monkeypatch, capsys):
    (tmp_path / 'lixity.toml').write_text('''language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
engine = "qwen3-design"
voice = "design"
language = "de"
voice_description = "Private description"
''')
    monkeypatch.setenv('LIXITY_LANG', 'de')
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda target: {
        'target': target, 'state': 'ready', 'transport': 'loopback', 'model': QWEN_DESIGN_MODEL})
    assert main(['audio-status', '--project', str(tmp_path), '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['schema_version'] == 'lixity-audio-status/1'
    assert 'Private description' not in json.dumps(data)
    assert main(['audio-status', '--project', str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert 'VoiceDesign' in output and 'Abschnitt' in output
    assert 'Referenz' in output and 'Hörprobe' in output
    assert 'Private description' not in output


def test_audio_direction_help_and_base_status_explain_limits(monkeypatch, capsys):
    monkeypatch.setenv('LIXITY_LANG', 'en')
    with pytest.raises(SystemExit):
        main(['audio-direction', '--help'])
    output = capsys.readouterr().out
    assert 'VoiceDesign' in output and 'role-specific' in output and 'Base' in output
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda target: {
        'target': target, 'state': 'ready', 'transport': 'loopback', 'model': None})
    assert main(['audio-status', '--engine', 'qwen3-base']) == 0
    output = capsys.readouterr().out
    assert 'reference' in output and 'free-form direction is unsupported' in output
