"""CLI auditions use the shared source-bound speech plan."""
import json

from lixity.cli import main
from lixity.speech import generate_silence_wav


def project(tmp_path):
    (tmp_path / 'lixity.toml').write_text('language="de"\nmanuscript="draft.md"\n')
    (tmp_path / 'draft.md').write_text('## Eins\n\nDer erste Absatz spricht.\n\nDer zweite Absatz spricht.\n')
    return tmp_path


def test_preview_line_plan_selects_only_requested_paragraph(tmp_path, capsys):
    root = project(tmp_path)
    status = main(['read-aloud', '--project', str(root), '--preview-line', '5', '--plan-only'])
    assert status == 0
    plan = json.loads(capsys.readouterr().out)
    assert [s['text'] for s in plan['segments']] == ['Der zweite Absatz spricht.']
    assert plan['segments'][0]['anchor']['start_line'] == 5
    assert not list(root.glob('*.wav'))


def test_preview_renders_first_paragraph_without_cache_or_overwriting_chapter(tmp_path, capsys, monkeypatch):
    root = project(tmp_path)
    chapter = root / 'chapter.wav'
    chapter.write_bytes(b'previous chapter')
    observed = []
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen', lambda text, profile, **kw:
                        observed.append(text) or generate_silence_wav(.01, 24000))
    assert main(['read-aloud', '--project', str(root), '--preview', '--progress', '--speed', '1.0']) == 0
    result = capsys.readouterr()
    assert observed == ['Der erste Absatz spricht.']
    assert '1/1' in result.err
    assert chapter.read_bytes() == b'previous chapter'
    assert list(root.glob('*preview.wav'))


def test_progress_estimates_remaining_time_after_two_segments(tmp_path, capsys, monkeypatch):
    root = project(tmp_path)
    (root / 'draft.md').write_text('## Eins\n\nErster Absatz.\n\nZweiter Absatz.\n\nDritter Absatz.\n')
    clock = [100.0]
    monkeypatch.setattr('lixity.cli._monotonic', lambda: clock[0], raising=False)

    def synthesize(text, profile, **kwargs):
        clock[0] += 10
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen', synthesize)
    assert main(['read-aloud', '--project', str(root), '--no-audio-cache', '--progress', '--speed', '1.0']) == 0
    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith('Audio: ')]
    assert lines[:2] == ['Audio: 0/4', 'Audio: 1/4']
    assert lines[2] == 'Audio: 2/4 (ETA ~20s)'
    assert lines[-1] == 'Audio: 4/4'


def test_preview_rejects_unmatched_line_without_synthesis(tmp_path, capsys, monkeypatch):
    root = project(tmp_path)
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('unexpected inference')))
    assert main(['read-aloud', '--project', str(root), '--preview-line', '4']) != 0
    assert not list(root.glob('*.wav'))


def test_design_engine_selects_its_only_voice_for_an_unsaved_audition(tmp_path, capsys):
    root = project(tmp_path)
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3-design', '--voice-description', 'A calm German voice.']) == 0
    profile = json.loads(capsys.readouterr().out)['segments'][0]['profile']
    assert profile['voice'] == 'design'


def test_preview_reports_unsupported_quote_block_without_reusing_prose_identity(tmp_path, capsys):
    root = project(tmp_path)
    (root / 'draft.md').write_text('## Eins\n\n> Der Fluss rauscht.\n')
    assert main(['read-aloud', '--project', str(root), '--preview-line', '3', '--plan-only']) == 1
    assert 'anchored paragraph or list item' in capsys.readouterr().err


def test_preview_line_accepts_an_anchored_list_item(tmp_path, capsys):
    root = project(tmp_path)
    (root / 'draft.md').write_text('## Eins\n\n- Der Fluss rauscht.\n')
    assert main(['read-aloud', '--project', str(root), '--preview-line', '3', '--plan-only']) == 0
    assert json.loads(capsys.readouterr().out)['segments'][0]['text'] == 'Der Fluss rauscht.'


def test_custom_voice_override_drops_inherited_design_description(tmp_path, capsys):
    root = project(tmp_path)
    (root / 'lixity.toml').write_text('''language = "de"
manuscript = "draft.md"
[audio]
selected = "design"
[audio.profiles.design]
engine = "qwen3-design"
voice = "design"
language = "de"
voice_description = "A German narrator."
''')
    assert main(['read-aloud', '--project', str(root), '--preview', '--plan-only',
                 '--engine', 'qwen3', '--voice', 'Ryan']) == 0
    profile = json.loads(capsys.readouterr().out)['segments'][0]['profile']
    assert profile['engine'] == 'qwen3' and profile['voice'] == 'Ryan'
    assert not profile.get('voice_description')
