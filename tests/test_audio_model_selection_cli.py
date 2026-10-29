"""CLI model selection keeps explicit controls and explains required choices."""

import json

import pytest

from lixity.cli import main
from lixity.speech import generate_silence_wav
from lixity.speech_references import save_reference


def _project(tmp_path):
    (tmp_path / 'draft.md').write_text('## Scene\n\nA synthetic passage.\n', encoding='utf-8')
    (tmp_path / 'lixity.toml').write_text('manuscript = "draft.md"\nlanguage = "de"\n', encoding='utf-8')
    return tmp_path


def test_base_selection_explains_inherited_instruction_and_never_drops_it(tmp_path, capsys):
    root = _project(tmp_path)
    (root / 'lixity.toml').write_text('''manuscript = "draft.md"
language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
engine = "qwen3"
language = "de"
instructions = "PRIVATE DIRECTION"
''', encoding='utf-8')
    reference = save_reference(root, generate_silence_wav(1), 'Synthetic reference.')
    args = ['read-aloud', '--project', str(root), '--preview', '--plan-only', '--no-direction',
            '--engine', 'qwen3-base', '--reference-id', reference.id]
    assert main(args) == 1
    failed = capsys.readouterr()
    assert "--instructions ''" in failed.err
    assert 'PRIVATE DIRECTION' not in failed.err
    assert main([*args, '--instructions', '']) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan['segments'][0]['profile']['engine'] == 'qwen3-base'
    assert plan['segments'][0]['profile']['voice'] == 'reference'
    assert plan['segments'][0]['profile']['instructions'] == ''


def test_base_selection_explains_missing_reference(tmp_path, capsys):
    root = _project(tmp_path)
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3-base']) == 1
    err = capsys.readouterr().err
    assert '--reference-id' in err and 'audio-reference create' in err


def test_voice_design_selection_explains_missing_description(tmp_path, capsys):
    root = _project(tmp_path)
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3-design']) == 1
    assert '--voice-description' in capsys.readouterr().err


def test_base_rejects_explicit_delivery_instruction_without_exposing_it(tmp_path, capsys):
    root = _project(tmp_path)
    reference = save_reference(root, generate_silence_wav(1), 'Synthetic reference.')
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3-base', '--reference-id', reference.id,
                 '--instructions', 'PRIVATE EXPLICIT DIRECTION']) == 1
    error = capsys.readouterr().err
    assert "--instructions ''" in error
    assert 'PRIVATE EXPLICIT DIRECTION' not in error


def test_base_rejects_explicit_voice_description_instead_of_discarding_it(tmp_path, capsys):
    root = _project(tmp_path)
    reference = save_reference(root, generate_silence_wav(1), 'Synthetic reference.')
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3-base', '--reference-id', reference.id,
                 '--voice-description', 'PRIVATE EXPLICIT DESCRIPTION']) == 1
    assert 'PRIVATE EXPLICIT DESCRIPTION' not in capsys.readouterr().err


@pytest.mark.parametrize('engine,extra', [('qwen3', ['--voice', 'Ryan']),
                                          ('qwen3-design', ['--voice-description', 'A calm voice'])])
def test_explicit_reference_is_not_silently_discarded_on_engine_switch(tmp_path, capsys, engine, extra):
    root = _project(tmp_path)
    reference = save_reference(root, generate_silence_wav(1), 'Synthetic reference.')
    (root / 'lixity.toml').write_text(f'''manuscript = "draft.md"
language = "de"
[audio]
selected = "base"
[audio.profiles.base]
engine = "qwen3-base"
voice = "reference"
language = "de"
reference_id = "{reference.id}"
''', encoding='utf-8')
    args = ['read-aloud', '--project', str(root), '--preview', '--plan-only', '--engine', engine, *extra]
    assert main([*args, '--reference-id', reference.id]) == 1
    assert '--reference-id' in capsys.readouterr().err
    assert main(args) == 0
    profile = json.loads(capsys.readouterr().out)['segments'][0]['profile']
    assert profile['engine'] == engine and not profile.get('reference_id')


def test_custom_voice_requires_a_deliberate_preset_after_design_selection(tmp_path, capsys):
    root = _project(tmp_path)
    (root / 'lixity.toml').write_text('''manuscript = "draft.md"
language = "de"
[audio]
selected = "narrator"
[audio.profiles.narrator]
engine = "qwen3-design"
voice = "design"
language = "de"
voice_description = "Synthetic description"
''', encoding='utf-8')
    args = ['read-aloud', '--project', str(root), '--preview', '--plan-only', '--engine', 'qwen3']
    assert main(args) == 1
    assert '--voice' in capsys.readouterr().err
    assert main([*args, '--voice', 'Ryan']) == 0
    assert json.loads(capsys.readouterr().out)['segments'][0]['profile']['voice'] == 'Ryan'


def test_status_text_identifies_the_engine_being_compared(monkeypatch, capsys):
    monkeypatch.setenv('LIXITY_LANG', 'de')
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda target: {
        'target': target, 'state': 'ready', 'transport': 'loopback', 'model': None})
    assert main(['audio-status', '--engine', 'qwen3-base']) == 0
    assert 'Vergleichsmodell: qwen3-base' in capsys.readouterr().out


def test_read_aloud_help_explains_model_choices_and_preset_limit(monkeypatch, capsys):
    monkeypatch.setenv('LIXITY_LANG', 'en')
    with pytest.raises(SystemExit):
        main(['read-aloud', '--help'])
    output = ' '.join(capsys.readouterr().out.split())
    assert 'preset voices' in output and 'saved reference' in output
    assert 'Ryan' in output and 'no German-native preset' in output
