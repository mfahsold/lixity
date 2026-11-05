"""Mixed voice engines must be feasible before starting a long render."""
import pytest

from lixity.speech import generate_silence_wav, render_speech_audio
from lixity.speech_cache import SpeechSegmentCache
from lixity.speech_direction import SpeechSegment
from lixity.speech_profiles import AudioProfile


def _plan():
    preset = AudioProfile(language='de')
    design = AudioProfile(engine='qwen3-design', voice='design', language='de',
                          voice_description='A natural German voice')
    return preset, design, [SpeechSegment('Ein Satz.', preset), SpeechSegment('Noch ein Satz.', design)]


def test_mixed_uncached_models_fail_before_synthesis_and_keep_old_output(tmp_path, monkeypatch):
    preset, _design, plan = _plan()
    source, output = tmp_path / 'text.md', tmp_path / 'audio.wav'
    source.write_text('Ein Satz. Noch ein Satz.')
    output.write_bytes(b'old audio')
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen',
                        lambda *a, **kw: pytest.fail('render must not begin'))
    with pytest.raises(ValueError, match=r'multiple.*model'):
        render_speech_audio(source, output, profile=preset, plan=plan)
    assert output.read_bytes() == b'old audio'


def test_mixed_models_allow_cached_one_and_render_only_other(tmp_path, monkeypatch):
    preset, design, plan = _plan()
    source, output, cache = tmp_path / 'text.md', tmp_path / 'audio.wav', tmp_path / 'cache'
    source.write_text('Ein Satz. Noch ein Satz.')
    SpeechSegmentCache(cache).put('Noch ein Satz.', design, generate_silence_wav(.01, 24000))
    calls = []
    def synthesize(text, profile, **_kwargs):
        calls.append((text, profile.engine))
        return generate_silence_wav(.01, 24000)
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen', synthesize)
    render_speech_audio(source, output, profile=preset, plan=plan, cache_dir=cache)
    assert calls == [('Ein Satz.', 'qwen3')]
    assert output.read_bytes().startswith(b'RIFF')


def test_fresh_render_does_not_count_cached_segments(tmp_path, monkeypatch):
    preset, design, plan = _plan()
    source, output, cache = tmp_path / 'text.md', tmp_path / 'audio.wav', tmp_path / 'cache'
    source.write_text('Ein Satz. Noch ein Satz.')
    SpeechSegmentCache(cache).put('Noch ein Satz.', design, generate_silence_wav(.01, 24000))
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen',
                        lambda *a, **kw: pytest.fail('fresh render must not begin'))
    with pytest.raises(ValueError, match=r'multiple.*model'):
        render_speech_audio(source, output, profile=preset, plan=plan, cache_dir=cache, fresh_audio=True)


def test_all_cached_mixed_models_do_not_need_a_worker(tmp_path, monkeypatch):
    preset, design, plan = _plan()
    source, output, cache = tmp_path / 'text.md', tmp_path / 'audio.wav', tmp_path / 'cache'
    source.write_text('Ein Satz. Noch ein Satz.')
    stored = SpeechSegmentCache(cache)
    stored.put('Ein Satz.', preset, generate_silence_wav(.01, 24000))
    stored.put('Noch ein Satz.', design, generate_silence_wav(.01, 24000))
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen',
                        lambda *a, **kw: pytest.fail('cached render must not use a worker'))
    render_speech_audio(source, output, profile=preset, plan=plan, cache_dir=cache)
    assert output.read_bytes().startswith(b'RIFF')


def test_corrupt_cache_does_not_make_mixed_plan_look_runnable(tmp_path, monkeypatch):
    preset, design, plan = _plan()
    source, output, cache = tmp_path / 'text.md', tmp_path / 'audio.wav', tmp_path / 'cache'
    source.write_text('Ein Satz. Noch ein Satz.')
    SpeechSegmentCache(cache).put('Noch ein Satz.', design, generate_silence_wav(.01, 24000))
    next(cache.glob('*.wav')).write_bytes(b'corrupt')
    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen',
                        lambda *a, **kw: pytest.fail('render must not begin'))
    with pytest.raises(ValueError, match=r'multiple.*model'):
        render_speech_audio(source, output, profile=preset, plan=plan, cache_dir=cache)


def test_independent_workers_can_render_one_plan(tmp_path, monkeypatch):
    from lixity.speech_references import save_reference

    source, output = tmp_path / 'text.md', tmp_path / 'audio.wav'
    source.write_text('Two independent models.')
    reference = save_reference(tmp_path, generate_silence_wav(1), 'Synthetic reference.')
    preset = AudioProfile(language='de')
    f5 = AudioProfile(engine='f5-tts', voice='reference', language='de', reference_id=reference.id)
    plan = [SpeechSegment('First voice.', preset), SpeechSegment('Second voice.', f5)]
    calls = []

    def synthesize(text, profile, **kwargs):
        calls.append((text, profile.engine))
        if profile.engine == 'f5-tts':
            assert kwargs['reference'] == reference
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr('lixity.speech_qwen.synthesize_qwen', synthesize)
    monkeypatch.setattr('lixity.speech_f5.synthesize_f5', synthesize)
    render_speech_audio(source, output, profile=preset, plan=plan, references={reference.id: reference})
    assert calls == [('First voice.', 'qwen3'), ('Second voice.', 'f5-tts')]
    assert output.read_bytes().startswith(b'RIFF')
