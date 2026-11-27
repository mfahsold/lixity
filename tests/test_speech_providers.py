"""Explicit external speech requests preserve provider and privacy boundaries."""
from __future__ import annotations

import io
import json
import shutil
import struct
import threading
import urllib.error
import wave
from contextlib import contextmanager
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from lixity.audio_pcm import read_pcm_wav
from lixity.speech import generate_silence_wav, render_speech_audio
from lixity.speech_cache import SpeechSegmentCache
from lixity.speech_direction import SpeechSegment
from lixity.speech_profiles import (
    AudioProfile,
    AudioSettings,
    audio_capabilities,
    parse_audio_settings,
)


def external(**changes):
    return AudioProfile.model_validate({"engine": "openai-compatible", "voice": "custom-voice",
        "language": "nl", "model": "synthetic-model", "base_url": "http://127.0.0.1:8768/v1", **changes})


@contextmanager
def provider(*, status=200, body=None, headers=None):
    records = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            records.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(status)
            self.send_header('Content-Type', 'audio/wav')
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(generate_silence_wav(.01) if body is None else body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', records
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_external_profile_requires_explicit_identity_and_versioned_settings():
    selected = external()
    data = {"selected": "voice", "profiles": {"voice": selected.model_dump()}}
    with pytest.raises(ValidationError, match="schema"):
        parse_audio_settings({**data, "schema_version": "lixity-audio-settings/3"})
    parsed = parse_audio_settings({**data, "schema_version": "lixity-audio-settings/4"})
    assert parsed.profiles['voice'] == selected
    for missing in ('base_url', 'model', 'voice'):
        raw = selected.model_dump()
        raw.pop(missing)
        with pytest.raises(ValidationError):
            AudioProfile.model_validate(raw)
    assert 'base_url' not in AudioProfile().model_dump()


def test_profile_instances_cannot_bypass_external_settings_schema():
    with pytest.raises(ValidationError, match='schema'):
        AudioSettings(selected='voice', profiles={'voice': external()})


@pytest.mark.parametrize('url', ['http://speech.example/v1', 'https://name:secret@example.test/v1',
    'https://example.test/v1?api_key=secret', 'https://example.test/v1#secret', 'file:///tmp/socket',
    'https://example.test/\nprivate', 'https://example.test:bad/v1'])
def test_profile_rejects_unsafe_or_credential_bearing_urls_without_echoing_them(url):
    with pytest.raises(ValidationError) as caught:
        external(base_url=url)
    assert url not in str(caught.value)


@pytest.mark.parametrize('url', ['https://speech.example/v1', 'http://localhost:5000',
    'http://127.0.0.2:9000', 'http://[::1]:8000/v1', 'http://192.168.1.5:8000/v1',
    'http://10.0.0.5:8000', 'http://[fd00::5]:8000'])
def test_explicit_https_and_local_http_urls_are_supported(url):
    assert external(base_url=url).base_url == url


@pytest.mark.parametrize('changes', [{'instructions': 'Whisper'}, {'voice_description': 'A voice'},
    {'reference_id': 'a' * 64}, {'api_key_env': 'bearer secret'}, {'api_key': 'secret'}])
def test_unsupported_controls_and_secret_values_are_rejected(changes):
    with pytest.raises(ValidationError):
        external(**changes)


@pytest.mark.parametrize(('cache_env', 'cache_path'), [
    ({}, '.cache/huggingface/hub'),
    ({'XDG_CACHE_HOME': '$HOME/xdg'}, 'xdg/huggingface/hub'),
    ({'XDG_CACHE_HOME': '$HOME/xdg', 'HF_HOME': '~/hf'}, 'hf/hub'),
    ({'XDG_CACHE_HOME': '$HOME/xdg', 'HF_HOME': '~/hf', 'HF_HUB_CACHE': '${HOME}/hub'}, 'hub'),
])
def test_local_zonos_status_checks_runtime_and_model_without_paths(tmp_path, monkeypatch, cache_env, cache_path):
    from lixity.speech_providers import external_provider_status

    for name in ('XDG_CACHE_HOME', 'HF_HOME', 'HF_HUB_CACHE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    for name, value in cache_env.items():
        monkeypatch.setenv(name, value)
    runtime = tmp_path / '.local/share/lixity/runtimes/mlx-audio/bin/python'
    runtime.parent.mkdir(parents=True)
    runtime.write_text('')
    runtime.chmod(0o700)
    snapshot = tmp_path / cache_path / 'models--mlx-community--ZONOS3-Mini/snapshots/test'
    snapshot.mkdir(parents=True)
    (snapshot / 'config.json').write_text('{}')
    (snapshot / 'model.safetensors').write_bytes(b'')
    monkeypatch.setattr('lixity.speech_providers.Path.home', lambda: tmp_path)

    ready = external_provider_status(AudioProfile(engine='mlx-audio', language='de'))
    assert ready['state'] == 'ready'
    assert ready['target'] == 'local' and ready['transport'] == 'isolated-process'
    assert ready['runtime_available'] and ready['model_cached'] and ready['model_matches']
    assert 'tmp_path' not in json.dumps(ready) and str(tmp_path) not in json.dumps(ready)
    (snapshot / 'model.safetensors').unlink()
    assert external_provider_status(None, engine='mlx-audio')['state'] == 'unavailable'


def test_local_zonos_status_and_synthesis_require_the_worker_script(tmp_path, monkeypatch):
    from lixity import speech_providers

    runtime = tmp_path / 'python'
    runtime.touch(mode=0o700)
    missing_worker = tmp_path / 'worker.py'
    monkeypatch.setattr(speech_providers, '_zonos_worker_paths', lambda: (runtime, missing_worker))
    profile = AudioProfile(engine='mlx-audio', language='de')

    status = speech_providers.external_provider_status(profile)
    assert status['state'] == 'unavailable'
    assert status['runtime_available'] is False
    with pytest.raises(FileNotFoundError, match='worker script'):
        speech_providers.synthesize_external('Hallo.', profile)


def test_standard_request_accepts_provider_wav_without_native_headers(monkeypatch):
    from lixity.speech_providers import synthesize_external
    monkeypatch.setenv('SYNTHETIC_SPEECH_KEY', 'synthetic-secret')
    with provider() as (url, records):
        audio = synthesize_external('Synthetic text.', external(base_url=url,
            api_key_env='SYNTHETIC_SPEECH_KEY', supports_instructions=True, instructions='Calm'))
    assert read_pcm_wav(audio)[0] == (1, 2, 24000)
    path, headers, payload = records[0]
    assert path == '/v1/audio/speech'
    assert headers['Authorization'] == 'Bearer synthetic-secret'
    assert payload == {'model': 'synthetic-model', 'input': 'Synthetic text.',
        'voice': 'custom-voice', 'response_format': 'wav', 'instructions': 'Calm'}
    assert audio_capabilities()['openai-compatible']['instructions'] is False


def test_mlx_audio_request_uses_language_model_speed_and_temperature():
    from lixity.speech_profiles import MLX_AUDIO_DEFAULT_VOICE, MLX_AUDIO_TTS_MODEL
    from lixity.speech_providers import synthesize_external

    with provider() as (url, records):
        selected = AudioProfile(engine='mlx-audio', base_url=url, language='de')
        synthesize_external('Synthetischer Text.', selected)
    assert records[0][2] == {
        'model': MLX_AUDIO_TTS_MODEL,
        'input': 'Synthetischer Text.',
        'response_format': 'wav',
        'voice': MLX_AUDIO_DEFAULT_VOICE,
        'lang_code': 'de',
        'speed': 1.1,
        'temperature': 0.0,
    }


def test_mlx_audio_render_dispatches_through_the_shared_pipeline(tmp_path):
    source, output = tmp_path / 'source.md', tmp_path / 'out.wav'
    source.write_text('Synthetischer Satz.')
    with provider() as (url, records):
        selected = AudioProfile(engine='mlx-audio', base_url=url, language='de', speed=1.0)
        render_speech_audio(source, output, profile=selected)
    assert output.is_file()
    assert records[0][2]['lang_code'] == 'de'
    assert read_pcm_wav(output.read_bytes())[0] == (1, 2, 24000)


def test_local_zonos_dispatches_reference_through_private_worker(monkeypatch):
    from lixity.speech_providers import synthesize_external
    from lixity.speech_references import SpeechReference

    reference = SpeechReference('a' * 64, generate_silence_wav(1), 'Synthetic reference.')
    selected = AudioProfile(engine='mlx-audio', language='de', voice='reference',
                            reference_id=reference.id)
    observed = []

    def synthesize(text, profile, bound_reference):
        observed.append((text, profile, bound_reference))
        return generate_silence_wav(1)

    monkeypatch.setattr('lixity.speech_providers._synthesize_zonos_direct', synthesize)
    audio = synthesize_external('Synthetic text.', selected, reference=reference)
    assert observed == [('Synthetic text.', selected, reference)]
    assert read_pcm_wav(audio)[0] == (1, 2, 24000)


def test_render_dispatches_multiple_external_models_and_reuses_distinct_cache(tmp_path):
    source, output = tmp_path/'source.md', tmp_path/'out.wav'
    source.write_text('Synthetic source.')
    with provider() as (url, records):
        first = external(base_url=url)
        second = external(base_url=url, model='second-model')
        plan = [SpeechSegment('One.', first, 0, 0, None), SpeechSegment('Two.', second, 0, 0, None)]
        for _ in range(2):
            render_speech_audio(source, output, profile=first, plan=plan, cache_dir=tmp_path/'cache')
        assert [row[2]['model'] for row in records] == ['synthetic-model', 'second-model']
    assert len(read_pcm_wav(output.read_bytes())[1]) == 960


def test_cache_separates_endpoint_model_and_provider_identity(tmp_path):
    cache = SpeechSegmentCache(tmp_path)
    data = generate_silence_wav(.01)
    selected = external()
    cache.put('Synthetic.', selected, data)
    assert cache.get('Synthetic.', selected) == data
    for other in (external(model='other'), external(base_url='https://speech.example/v1'), AudioProfile(voice='Ryan', language='en')):
        assert cache.get('Synthetic.', other) is None


def test_status_does_not_probe_provider_or_require_native_workers(tmp_path, monkeypatch):
    from lixity.speech_status import audio_status
    (tmp_path/'lixity.toml').write_text('''language="nl"
[audio]
schema_version="lixity-audio-settings/4"
selected="narrator"
[audio.profiles.narrator]
engine="openai-compatible"
voice="custom"
language="nl"
model="synthetic"
base_url="https://speech.example/v1"
api_key_env="UNSET_TEST_KEY"
''')
    monkeypatch.setattr('lixity.speech_status.worker_health', lambda *_: pytest.fail('Unexpected native probe'))
    result = audio_status(tmp_path)
    assert result['targets'][0]['state'] == 'unknown'
    assert result['targets'][0]['configured'] is True
    assert result['targets'][0]['model_matches'] is None


def test_missing_environment_key_fails_before_any_request(monkeypatch):
    from lixity.speech_providers import synthesize_external
    monkeypatch.delenv('UNSET_TEST_KEY', raising=False)
    with pytest.raises(ValueError, match='environment'):
        synthesize_external('Synthetic.', external(api_key_env='UNSET_TEST_KEY'),
            opener=SimpleNamespace(open=lambda *_a, **_k: pytest.fail('Unexpected request')))


def test_redirect_does_not_forward_authorization(monkeypatch):
    from lixity.speech_providers import synthesize_external
    monkeypatch.setenv('SYNTHETIC_SPEECH_KEY', 'synthetic-secret')
    with provider() as (other, other_records), provider(status=307, headers={'Location': other+'/v1/audio/speech'}) as (url, records):
        with pytest.raises(RuntimeError) as caught:
            synthesize_external('Synthetic.', external(base_url=url, api_key_env='SYNTHETIC_SPEECH_KEY'))
        assert len(records) == 1 and not other_records
        assert 'synthetic-secret' not in str(caught.value)


def test_transport_errors_do_not_expose_provider_body_url_or_credentials():
    from lixity.speech_providers import synthesize_external
    error = urllib.error.HTTPError('https://secret.example/private', 401, 'secret', Message(), io.BytesIO(b'private response'))
    def fail(*_a, **_kw):
        raise error
    with pytest.raises(RuntimeError) as caught:
        synthesize_external('Synthetic.', external(), opener=SimpleNamespace(open=fail))
    assert error.fp.closed
    assert 'private' not in str(caught.value) and 'secret' not in str(caught.value)


def test_provider_pcm_is_normalized_with_ffmpeg_or_fails_explicitly(monkeypatch):
    from lixity.speech_providers import synthesize_external
    body = generate_silence_wav(.05, sample_rate=44100, channels=2)
    with provider(body=body) as (url, _records):
        if shutil.which('ffmpeg'):
            assert read_pcm_wav(synthesize_external('Synthetic.', external(base_url=url)))[0] == (1, 2, 24000)
        monkeypatch.setattr('lixity.speech_providers.shutil.which', lambda _: None)
        with pytest.raises(FileNotFoundError, match='FFmpeg'):
            synthesize_external('Synthetic.', external(base_url=url))


def test_truncated_pcm_is_rejected_instead_of_repaired_by_decoder():
    from lixity.speech_providers import synthesize_external
    with provider(body=generate_silence_wav(.05)[:-20]) as (url, _records), pytest.raises(ValueError, match='truncated'):
        synthesize_external('Synthetic.', external(base_url=url))


def float_wav(*, extended=False):
    fmt = struct.pack('<HHIIHH', 0xFFFE if extended else 3, 1, 24000, 96000, 4, 32)
    if extended:
        fmt += struct.pack('<HHI', 22, 32, 4) + bytes.fromhex('0300000000001000800000aa00389b71')
    samples = struct.pack('<f', 0.25) * 2400
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(samples)) + samples
    return b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks


@pytest.mark.parametrize('extended', [False, True])
@pytest.mark.parametrize('repair_riff_size', [False, True])
def test_truncated_float_wav_is_rejected_before_decoder_salvage(extended, repair_riff_size, monkeypatch):
    from lixity.speech_providers import _normalize_wav
    body = float_wav(extended=extended)[:-4800]
    if repair_riff_size:
        body = body[:4] + struct.pack('<I', len(body) - 8) + body[8:]
    monkeypatch.setattr('lixity.speech._run_ffmpeg', lambda *_a, **_kw: pytest.fail('Incomplete WAV reached the decoder'))
    with pytest.raises(ValueError, match='truncated'):
        _normalize_wav(body)


@pytest.mark.parametrize('extended', [False, True])
def test_complete_float_wav_retains_all_frames_when_normalized(extended):
    from lixity.speech_providers import _normalize_wav
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg is required to decode float WAV')
    params, frames = read_pcm_wav(_normalize_wav(float_wav(extended=extended)))
    assert params == (1, 2, 24000)
    assert frames == struct.pack('<h', 8192) * 2400


@pytest.mark.parametrize('sample_width', [1, 2, 3, 4])
def test_complete_pcm_formats_include_odd_unpadded_terminal_data(sample_width):
    from lixity.speech_providers import _normalize_wav
    if sample_width != 2 and not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg is required to normalize PCM sample width')
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setparams((1, sample_width, 24000, 0, 'NONE', 'not compressed'))
        writer.writeframes(bytes(2401 * sample_width))
    params, frames = read_pcm_wav(_normalize_wav(output.getvalue()))
    assert params == (1, 2, 24000)
    assert len(frames) == 2401 * 2


def test_incomplete_final_pcm_frame_is_rejected_before_conversion(monkeypatch):
    from lixity.speech_providers import _normalize_wav

    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        writer.writeframes(bytes(5))
    monkeypatch.setattr('lixity.speech._run_ffmpeg',
                        lambda *_args, **_kwargs: pytest.fail('Partial PCM frame reached the decoder'))
    with pytest.raises(ValueError, match='truncated PCM audio'):
        _normalize_wav(output.getvalue())


def test_plan_controls_are_checked_before_transmitting_any_segment(tmp_path):
    source, output = tmp_path/'source.md', tmp_path/'out.wav'
    source.write_text('Synthetic source.')
    with provider() as (url, records):
        first = external(base_url=url)
        invalid = first.model_copy(update={'reference_id': 'a' * 64})
        plan = [SpeechSegment('One.', first, 0, 0, None), SpeechSegment('Two.', invalid, 0, 0, None)]
        with pytest.raises(ValueError, match='reference'):
            render_speech_audio(source, output, profile=first, plan=plan)
        assert not records and not output.exists()


def test_response_size_limit_is_enforced_without_parsing_or_echoing(monkeypatch):
    from lixity import speech_providers
    monkeypatch.setattr(speech_providers, 'MAX_RESPONSE_BYTES', 100)
    with provider(body=b'private-body' * 20) as (url, _records):
        with pytest.raises(ValueError, match='byte limit') as caught:
            speech_providers.synthesize_external('Synthetic.', external(base_url=url))
        assert 'private-body' not in str(caught.value)


def test_external_render_diagnostics_do_not_record_endpoint_voice_model_or_key(tmp_path, monkeypatch, caplog):
    source, output = tmp_path/'source.md', tmp_path/'out.wav'
    source.write_text('Synthetic source.')
    monkeypatch.setenv('SYNTHETIC_SPEECH_KEY', 'synthetic-secret')
    caplog.set_level('DEBUG', logger='lixity.speech')
    with provider() as (url, _records):
        selected = external(base_url=url, voice='private-voice', model='private-model', api_key_env='SYNTHETIC_SPEECH_KEY')
        render_speech_audio(source, output, profile=selected,
            plan=[SpeechSegment('Private synthetic prose.', selected, 0, 0, None)])
        assert 'requested_engine=openai-compatible' in caplog.text
        assert all(value not in caplog.text for value in (url, 'private-voice', 'private-model', 'synthetic-secret', 'Private synthetic prose.'))


def test_zonos_cache_distinguishes_reference_id_and_model_speed(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache

    cache = SpeechSegmentCache(tmp_path / 'cache')
    ref_a = AudioProfile(engine='mlx-audio', language='de', voice='reference', reference_id='a' * 64, speed=1.0)
    ref_b = AudioProfile(engine='mlx-audio', language='de', voice='reference', reference_id='b' * 64, speed=1.0)
    ref_a_fast = AudioProfile(engine='mlx-audio', language='de', voice='reference', reference_id='a' * 64, speed=1.2)
    keys = {cache._paths('Synthetischer Satz.', profile)[0] for profile in (ref_a, ref_b, ref_a_fast)}
    assert len(keys) == 3


def test_zonos_and_ffmpeg_subprocess_envs_strip_ambient_secrets(monkeypatch):
    from lixity.speech import _ffmpeg_env
    from lixity.speech_providers import _zonos_worker_env

    monkeypatch.setenv('OPENAI_API_KEY', 'sk-synthetic-secret')
    monkeypatch.setenv('HF_TOKEN', 'hf_synthetic_secret')
    monkeypatch.setenv('GH_TOKEN', 'ghp_synthetic_secret')
    zonos_env = _zonos_worker_env()
    ffmpeg_env = _ffmpeg_env()
    for secret_key in ('OPENAI_API_KEY', 'HF_TOKEN', 'GH_TOKEN'):
        assert secret_key not in zonos_env
        assert secret_key not in ffmpeg_env
    assert zonos_env['HF_HUB_OFFLINE'] == '1'
    assert zonos_env['TRANSFORMERS_OFFLINE'] == '1'
    assert ffmpeg_env['LC_ALL'] == 'C'


def test_zonos_worker_request_parser_enforces_pin_allowlist_and_symlinks(tmp_path):
    from lixity.speech_mlx_zonos import ALLOWED_MODEL, MAX_STDIN_BYTES, _parse_request

    output = tmp_path / 'out.wav'
    text, path, kwargs = _parse_request(json.dumps({
        'model': ALLOWED_MODEL, 'input': 'Hallo Welt.', 'output_path': str(output),
        'lang_code': 'de', 'speed': 1.1, 'temperature': 0.0, 'voice': 'liesel',
    }))
    assert text == 'Hallo Welt.' and path == output and kwargs['lang_code'] == 'de'

    with pytest.raises(ValueError, match='pinned local ZONOS3-Mini'):
        _parse_request(json.dumps({'model': 'evil/model', 'input': 'Hi', 'output_path': str(output)}))
    with pytest.raises(ValueError, match='Unsupported ZONOS3 worker parameters'):
        _parse_request(json.dumps({
            'model': ALLOWED_MODEL, 'input': 'Hi', 'output_path': str(output), 'trust_remote_code': True,
        }))
    with pytest.raises(ValueError, match='byte limit'):
        _parse_request(' ' * (MAX_STDIN_BYTES + 1))

    real_file = tmp_path / 'real.wav'
    real_file.write_bytes(b'RIFF')
    symlink = tmp_path / 'link.wav'
    symlink.symlink_to(real_file)
    with pytest.raises(ValueError, match='non-symlink'):
        _parse_request(json.dumps({'model': ALLOWED_MODEL, 'input': 'Hi', 'output_path': str(symlink)}))
    with pytest.raises(ValueError, match='regular file'):
        _parse_request(json.dumps({
            'model': ALLOWED_MODEL, 'input': 'Hi', 'output_path': str(output), 'ref_audio': str(symlink),
        }))


@pytest.mark.parametrize('url', [
    'http://169.254.169.254/latest/meta-data',
    'https://169.254.169.254/v1',
    'http://[fe80::1]:8000/v1',
    'https://[fe80::1]/v1',
    'https://[::ffff:169.254.169.254]/v1',
    'https://0.0.0.0/v1',
    'https://224.0.0.1/v1',
])
def test_speech_endpoint_rejects_link_local_multicast_and_unspecified_ips(url):
    from lixity.speech_providers import speech_endpoint

    with pytest.raises(ValueError):
        speech_endpoint(url)


def test_speech_endpoint_allows_link_local_only_when_explicitly_opted_in():
    from lixity.speech_providers import speech_endpoint

    assert speech_endpoint('http://169.254.1.2:8000', allow_link_local=True) == 'http://169.254.1.2:8000/v1/audio/speech'


@pytest.mark.parametrize('resolved_ip', ['169.254.169.254', '224.0.0.1', '0.' + '0.0.0', 'fe80::1', '::ffff:169.254.169.254'])
def test_resolved_endpoint_rejects_disallowed_dns_targets(monkeypatch, resolved_ip):
    import socket

    from lixity.speech_providers import validate_resolved_endpoint

    monkeypatch.setattr(
        socket,
        'getaddrinfo',
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (resolved_ip, 443))],
    )
    with pytest.raises(ValueError, match='disallowed'):
        validate_resolved_endpoint('https://speech.example/v1/audio/speech')


def test_resolved_localhost_http_rejects_dns_rebinding_to_non_loopback(monkeypatch):
    import socket

    from lixity.speech_providers import validate_resolved_endpoint

    monkeypatch.setattr(
        socket,
        'getaddrinfo',
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 8000))],
    )
    with pytest.raises(ValueError, match='loopback'):
        validate_resolved_endpoint('http://localhost:8000/v1/audio/speech')


def test_zonos_persistent_worker_reuses_single_process_across_segments(tmp_path):
    import sys
    from pathlib import Path

    from lixity.speech_providers import _ZonosWorkerSession

    worker = tmp_path / 'fake_zonos_worker.py'
    pid_file = tmp_path / 'worker_pids.txt'
    wav_bytes = generate_silence_wav(0.05)
    worker.write_text(
        f"""import json, os, sys
from pathlib import Path
Path({str(pid_file)!r}).open('a').write(str(os.getpid()) + '\\n')
sys.stdout.write(json.dumps({{'ready': True, 'model': 'mlx-community/ZONOS3-Mini'}}) + '\\n')
sys.stdout.flush()
for line in sys.stdin:
    req = json.loads(line)
    Path(req['output_path']).write_bytes({wav_bytes!r})
    sys.stdout.write('{{"ok":true}}\\n')
    sys.stdout.flush()
""",
        encoding='utf-8',
    )
    session = _ZonosWorkerSession(idle_timeout_seconds=60.0)
    try:
        for index in range(3):
            out = tmp_path / f'out-{index}.wav'
            session.synthesize(
                Path(sys.executable),
                worker,
                {'model': 'mlx-community/ZONOS3-Mini', 'input': f'Segment {index}.', 'output_path': str(out)},
            )
            assert out.read_bytes() == wav_bytes
        pids = pid_file.read_text(encoding='utf-8').splitlines()
        assert len(pids) == 1, 'Persistent ZONOS3 session must reuse the warm worker across segments'
    finally:
        session.close()


def test_zonos_worker_keeps_dependency_output_off_its_response_pipe(tmp_path):
    import sys
    from pathlib import Path

    import lixity.speech_mlx_zonos as worker_module
    from lixity.speech_providers import _ZonosWorkerSession

    worker = tmp_path / 'worker.py'
    shutil.copyfile(worker_module.__file__, worker)
    package = tmp_path / 'mlx_audio'
    package.mkdir()
    (package / 'tts.py').write_text(
        "import os\n"
        "from pathlib import Path\n"
        "from types import SimpleNamespace\n"
        "class Model:\n"
        "    def extract_speaker_embedding(self, reference):\n"
        "        embedding = Path(reference).read_bytes()\n"
        "        with Path(__file__).with_name('encoded').open('ab') as output:\n"
        "            output.write(embedding + b'\\n')\n"
        "        return embedding\n"
        "    def generate(self, text, **kwargs):\n"
        "        os.write(1, b'native generation progress\\n')\n"
        "        assert 'ref_audio' not in kwargs\n"
        "        audio = text.encode() + kwargs.get('speaker_embedding', b'')\n"
        "        yield SimpleNamespace(audio=audio, sample_rate=24000)\n"
        "def load(model):\n"
        "    print('loading local weights', flush=True)\n"
        "    return Model()\n",
        encoding='utf-8',
    )
    (package / 'audio_io.py').write_text(
        "from pathlib import Path\n"
        "def write(path, audio, sample_rate, format):\n"
        "    print('writing local audio', flush=True)\n"
        "    Path(path).write_bytes(audio)\n",
        encoding='utf-8',
    )
    session = _ZonosWorkerSession(startup_timeout_seconds=5, request_timeout_seconds=5)
    try:
        cases = (
            ('Die Sonne scheint.', None, b''),
            ('On continue.', 'reference-first.wav', b'first'),
            ('And back.', 'reference-copy.wav', b'first'),
            ('Der Mond geht auf.', 'reference-copy.wav', b'second'),
            ('Encore.', None, b''),
        )
        for segment, reference_name, reference_audio in cases:
            output = tmp_path / 'speech.wav'
            request = {
                'model': worker_module.ALLOWED_MODEL, 'input': segment, 'output_path': str(output),
            }
            if reference_name is not None:
                reference = tmp_path / reference_name
                reference.write_bytes(reference_audio)
                request['ref_audio'] = str(reference)
            session.synthesize(Path(sys.executable), worker, request)
            assert output.read_bytes() == segment.encode() + reference_audio
        assert (package / 'encoded').read_bytes().splitlines() == [b'first', b'second']
    finally:
        session.close()


def test_mlx_audio_preset_voice_is_sent_to_avoid_adapter_default():
    from lixity.speech_profiles import MLX_AUDIO_DEFAULT_VOICE
    from lixity.speech_providers import external_speech_request

    profile = AudioProfile(engine='mlx-audio', language='de')
    assert profile.voice == MLX_AUDIO_DEFAULT_VOICE
    request = external_speech_request('Hallo Welt.', profile)
    assert request['voice'] == MLX_AUDIO_DEFAULT_VOICE


def test_mlx_audio_reference_request_omits_voice_in_favour_of_reference_audio():
    from lixity.speech_providers import external_speech_request

    profile = AudioProfile(engine='mlx-audio', language='de', voice='reference',
                           reference_id='a' * 64)
    request = external_speech_request('Hallo Welt.', profile)
    assert 'voice' not in request
    assert request['lang_code'] == 'de'


def test_zonos_worker_drain_consumes_remainder_until_newline(monkeypatch):
    import sys

    import lixity.speech_mlx_zonos as worker_module

    chunks = iter(['middle-chunk', 'final-chunk\n', 'next-request\n'])
    seen: list[str] = []
    monkeypatch.setattr(
        sys, 'stdin',
        SimpleNamespace(readline=lambda _size: seen.append(1) or next(chunks, '')),
    )
    worker_module._drain_truncated_line('x' * (worker_module.MAX_STDIN_BYTES + 2))
    assert len(seen) == 2


@pytest.mark.parametrize('phase', ['startup', 'response'])
def test_zonos_session_times_out_on_hung_worker(tmp_path, phase):
    import sys
    from pathlib import Path

    from lixity.speech import SpeechBackendTimeout, _speech_error_kind
    from lixity.speech_providers import _ZonosWorkerSession

    worker = tmp_path / 'hung_worker.py'
    banner = (
        "sys.stdout.write(json.dumps({'ready': True, 'model': 'mlx-community/ZONOS3-Mini'}) + '\\n')\n"
        "sys.stdout.flush()\n"
    )
    worker.write_text(
        "import json, sys, time\n" + (banner if phase == 'response' else "") + "time.sleep(30)\n",
        encoding='utf-8',
    )
    session = _ZonosWorkerSession(
        idle_timeout_seconds=60.0,
        startup_timeout_seconds=0.2 if phase == 'startup' else 5.0,
        request_timeout_seconds=0.2,
    )
    try:
        out = tmp_path / 'out.wav'
        with pytest.raises(SpeechBackendTimeout, match=f'worker {phase} timed out') as caught:
            session.synthesize(
                Path(sys.executable),
                worker,
                {'model': 'mlx-community/ZONOS3-Mini', 'input': 'Hallo.', 'output_path': str(out)},
            )
        assert _speech_error_kind(caught.value) == 'timeout'
        assert session._process is None
    finally:
        session.close()
