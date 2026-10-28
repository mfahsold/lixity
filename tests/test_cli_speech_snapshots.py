"""CLI speech publishes only while its source context remains current."""
import json

import pytest

from lixity.cli import main
from lixity.speech import generate_silence_wav


@pytest.mark.parametrize('changed', ['source', 'settings', 'direction'])
def test_cli_never_replaces_output_when_context_changes_during_synthesis(tmp_path, monkeypatch, capsys, changed):
    import lixity.speech_qwen as qwen

    source = tmp_path / 'draft.md'
    source.write_text('## One\n\nA synthetic sentence.\n')
    settings = tmp_path / 'lixity.toml'
    settings.write_text('manuscript="draft.md"\nlanguage="en"\n')
    output = tmp_path / 'out.wav'
    output.write_bytes(b'old output')

    def synthesize(text, profile, **kwargs):
        if changed == 'source':
            source.write_text('## One\n\nA changed sentence.\n')
        elif changed == 'settings':
            settings.write_text('manuscript="draft.md"\nlanguage="de"\n')
        else:
            ledger = tmp_path / '.lixity/audio-directions.json'
            ledger.parent.mkdir(exist_ok=True)
            ledger.write_text(json.dumps({'schema_version':'lixity-audio-directions/1','entries':[]}))
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr(qwen, 'synthesize_qwen', synthesize)
    status = main(['read-aloud', '--project', str(tmp_path), '--no-audio-cache', '--speed', '1.0', '-o', str(output)])
    error = capsys.readouterr().err
    assert status == 1 and 'changed' in error.lower()
    assert output.read_bytes() == b'old output'


def test_cli_no_direction_ignores_changes_to_the_direction_ledger(tmp_path, monkeypatch):
    import lixity.speech_qwen as qwen

    source = tmp_path / 'draft.md'
    source.write_text('A synthetic sentence.\n')
    (tmp_path / 'lixity.toml').write_text('manuscript="draft.md"\nlanguage="en"\n')
    ledger = tmp_path / '.lixity/audio-directions.json'
    ledger.parent.mkdir()
    ledger.write_text('not valid json')
    def synthesize(text, profile, **kwargs):
        ledger.write_text('still invalid')
        return generate_silence_wav(.01, 24000)
    monkeypatch.setattr(qwen, 'synthesize_qwen', synthesize)
    output = tmp_path / 'out.wav'
    assert main(['read-aloud', '--project', str(tmp_path), '--no-direction', '--no-audio-cache', '--speed', '1.0', '-o', str(output)]) == 0
    assert output.read_bytes().startswith(b'RIFF')


def test_cli_cache_reuse_works_without_a_worker_when_context_is_unchanged(tmp_path, monkeypatch):
    import lixity.speech_qwen as qwen

    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    (tmp_path / 'draft.md').write_text('A synthetic sentence.\n')
    (tmp_path / 'lixity.toml').write_text('manuscript="draft.md"\nlanguage="en"\n')
    calls = []
    def synthesize(text, profile, **kwargs):
        calls.append(text)
        return generate_silence_wav(.01, 24000)
    monkeypatch.setattr(qwen, 'synthesize_qwen', synthesize)
    args = ['read-aloud', '--project', str(tmp_path), '--speed', '1.0', '-o', str(tmp_path / 'out.wav')]
    assert main(args) == 0
    assert calls
    calls.clear()
    assert main(args) == 0
    assert calls == []
