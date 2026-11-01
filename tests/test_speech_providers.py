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

from lixity.speech import _read_pcm, generate_silence_wav, render_speech_audio
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


def test_standard_request_accepts_provider_wav_without_native_headers(monkeypatch):
    from lixity.speech_providers import synthesize_external
    monkeypatch.setenv('SYNTHETIC_SPEECH_KEY', 'synthetic-secret')
    with provider() as (url, records):
        audio = synthesize_external('Synthetic text.', external(base_url=url,
            api_key_env='SYNTHETIC_SPEECH_KEY', supports_instructions=True, instructions='Calm'))
    assert _read_pcm(audio)[0] == (1, 2, 24000)
    path, headers, payload = records[0]
    assert path == '/v1/audio/speech'
    assert headers['Authorization'] == 'Bearer synthetic-secret'
    assert payload == {'model': 'synthetic-model', 'input': 'Synthetic text.',
        'voice': 'custom-voice', 'response_format': 'wav', 'instructions': 'Calm'}
    assert audio_capabilities()['openai-compatible']['instructions'] is False


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
    assert len(_read_pcm(output.read_bytes())[1]) == 960


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
            assert _read_pcm(synthesize_external('Synthetic.', external(base_url=url)))[0] == (1, 2, 24000)
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
    chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', 9600) + bytes(9600)
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
    params, frames = _read_pcm(_normalize_wav(float_wav(extended=extended)))
    assert params == (1, 2, 24000)
    assert len(frames) == 2400 * 2


@pytest.mark.parametrize('sample_width', [1, 2, 3, 4])
def test_complete_pcm_formats_include_odd_unpadded_terminal_data(sample_width):
    from lixity.speech_providers import _normalize_wav
    if sample_width != 2 and not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg is required to normalize PCM sample width')
    output = io.BytesIO()
    with wave.open(output, 'wb') as writer:
        writer.setparams((1, sample_width, 24000, 0, 'NONE', 'not compressed'))
        writer.writeframes(bytes(2401 * sample_width))
    params, frames = _read_pcm(_normalize_wav(output.getvalue()))
    assert params == (1, 2, 24000)
    assert len(frames) == 2401 * 2


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
