"""Synthetic tests for fixed local synthesis transport and atomic cancellation."""
from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
import wave
from email.message import Message
from types import SimpleNamespace

import pytest

from lixity.speech import SpeechCancelled, generate_silence_wav, render_speech_audio
from lixity.speech_profiles import QWEN_MODEL, AudioProfile
from lixity.speech_qwen import ENDPOINT, SYNTHESIS_TIMEOUT_SECONDS, synthesize_qwen, worker_server


def profile(**updates):
    return AudioProfile(engine="qwen3", voice="Ryan", language="en", **updates)


def test_adapter_fixed_endpoint_and_validated_identity():
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"
    requests = []

    class Response(io.BytesIO):
        status = 200

    def open_request(request, timeout):
        requests.append((request, timeout))
        result = Response(generate_silence_wav(.01, 24000))
        result.headers = headers
        return result

    opener = SimpleNamespace(open=open_request)
    synthesize_qwen("Synthetic text.", profile(instructions="Read calmly."), opener=opener)
    request = requests[0][0]
    assert requests[0][1] == SYNTHESIS_TIMEOUT_SECONDS == 3600
    assert request.full_url == ENDPOINT
    assert json.loads(request.data)["instructions"] == "Read calmly."
    for key in ("X-Lixity-Model", "X-Lixity-Voice"):
        original = headers[key]
        headers.replace_header(key, "wrong")
        with pytest.raises(ValueError, match="mismatch"):
            synthesize_qwen("Synthetic text.", profile(), opener=opener)
        headers.replace_header(key, original)


def test_render_applies_profile_and_progress(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen",
                        lambda text, selected: calls.append((text, selected)) or generate_silence_wav(.01, 24000))
    source = tmp_path / "source.md"
    source.write_text("A word.\n\n---\n\nAnother word.")
    selected = profile(paragraph_pause=.2, scene_pause=.3, pronunciations={"word": "werd"})
    events = []
    output = render_speech_audio(source, tmp_path / "out.wav", profile=selected,
                                 progress=lambda done, total: events.append((done, total)))
    assert [item[0] for item in calls] == ["A werd.", "Another werd."]
    assert all(item[1] == selected for item in calls)
    assert events == [(0, 2), (1, 2), (2, 2)]
    with wave.open(str(output)) as audio:
        assert audio.getframerate() == 24000
        assert audio.getnframes() == int(24000 * (.02 + .4 + .3))
    assert source.read_text() == "A word.\n\n---\n\nAnother word."


@pytest.mark.parametrize("when", ["before", "inference", "progress"])
def test_cancellation_preserves_old_output(tmp_path, monkeypatch, when):
    state = [when == "before"]

    def synthesize(_text, _profile):
        if when == "inference":
            state[0] = True
        return generate_silence_wav(.01, 24000)

    def progress(done, _total):
        if when == "progress" and done:
            state[0] = True

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    source = tmp_path / "source.md"
    source.write_text("Synthetic text.")
    output = tmp_path / "out.wav"
    output.write_bytes(b"old")
    with pytest.raises(SpeechCancelled):
        render_speech_audio(source, output, profile=profile(), cancelled=lambda: state[0], progress=progress)
    assert output.read_bytes() == b"old"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["out.wav", "source.md"]


def test_qwen_failure_does_not_fall_back(tmp_path, monkeypatch):
    def fail(*_args):
        raise RuntimeError("Qwen unavailable")

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", fail)
    source = tmp_path / "source.md"
    source.write_text("Synthetic text.")
    with pytest.raises(RuntimeError, match="Qwen unavailable"):
        render_speech_audio(source, tmp_path / "out.wav", profile=profile())
    assert not (tmp_path / "out.wav").exists()


def test_worker_health_validation_and_pcm():
    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_silence_wav(.01, 24000), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url + "/health") as response:
            assert json.load(response) == {"ready": True, "model": QWEN_MODEL}
        payload = {"model": QWEN_MODEL, "input": "Synthetic text.", "voice": "Ryan", "language": "en",
                   "instructions": "", "response_format": "wav"}
        request = urllib.request.Request(url + "/v1/audio/speech", data=json.dumps(payload).encode(),  # noqa: S310 - fixed loopback
                                         headers={"Content-Type": "application/json"})
        with opener.open(request) as response:
            assert response.headers["X-Lixity-Voice"] == "Ryan"
            assert response.read().startswith(b"RIFF")
        payload["model"] = "wrong"
        request.data = json.dumps(payload).encode()
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(request)
        with error.value:
            assert error.value.code == 400
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("audio", [b"", b"bad", generate_silence_wav(.01, 16000),
                                    generate_silence_wav(.01, 24000, channels=2),
                                    generate_silence_wav(.01, 24000)[:-2]])
def test_adapter_rejects_bad_pcm(audio):
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"

    class Response(io.BytesIO):
        status = 200

    def open_request(*_args, **_kwargs):
        result = Response(audio)
        result.headers = headers
        return result

    with pytest.raises(ValueError, match=r"audio|WAV|PCM"):
        synthesize_qwen("Synthetic text.", profile(), opener=SimpleNamespace(open=open_request))


def test_worker_rejects_redirects():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from lixity.speech_qwen import _NoRedirect

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(307)
            self.send_header("Location", "http://example.invalid/private")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}", data=b"synthetic")
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(request)
        with error.value:
            assert error.value.code == 307
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_pronunciation_phrase_crosses_transport_boundary(tmp_path, monkeypatch):
    from lixity.speech import extract_audio_cues

    body = " ".join(f"word{i}" for i in range(200)) + "."
    original = extract_audio_cues(body, language="en")
    phrase = original[0].text.split()[-1] + " " + original[1].text.split()[0]
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen",
                        lambda text, _profile: calls.append(text) or generate_silence_wav(.01, 24000))
    source = tmp_path / "source.md"
    source.write_text(body)
    render_speech_audio(source, tmp_path / "out.wav", profile=profile(pronunciations={phrase: "boundary"}))
    spoken = " ".join(calls)
    assert "boundary" in spoken and phrase not in spoken
    assert all(len(text) <= 600 for text in calls)
    assert source.read_text() == body


@pytest.mark.parametrize("device,bf16,dtype,attention,device_map", [
    ("cpu", False, "float32", "eager", "cpu"),
    ("cuda", True, "bfloat16", "sdpa", "cuda:0"),
    ("cuda", False, "float16", "sdpa", "cuda:0"),
])
def test_worker_explicit_device_loading(tmp_path, monkeypatch, device, bf16, dtype, attention, device_map):
    from lixity.speech_profiles import QWEN_LANGUAGES, QWEN_VOICES
    from lixity.speech_qwen import load_local_model

    (tmp_path / "config.json").write_text(json.dumps({
        "tts_model_type": "custom_voice", "tts_model_size": "1b7", "tokenizer_type": "qwen3_tts_tokenizer_12hz",
    }))
    calls = []
    model = SimpleNamespace(get_supported_speakers=lambda: list(QWEN_VOICES),
                            get_supported_languages=lambda: list(QWEN_LANGUAGES.values()))
    thread_counts = []
    fake_torch = SimpleNamespace(set_num_threads=thread_counts.append, float32="float32", float16="float16", bfloat16="bfloat16",
                                 cuda=SimpleNamespace(is_available=lambda: True,
                                                      is_bf16_supported=lambda **_kw: bf16))
    fake_qwen = SimpleNamespace(Qwen3TTSModel=SimpleNamespace(
        from_pretrained=lambda *args, **kwargs: calls.append((args, kwargs)) or model))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module",
                        lambda name: {"torch": fake_torch, "qwen_tts": fake_qwen}[name])
    assert callable(load_local_model(tmp_path, device=device))
    assert thread_counts == [4]
    assert calls == [((str(tmp_path),), {"device_map": device_map, "dtype": dtype,
                                        "attn_implementation": attention, "local_files_only": True})]


def test_worker_unavailable_cuda_has_no_cpu_fallback(tmp_path, monkeypatch):
    from lixity.speech_qwen import load_local_model

    (tmp_path / "config.json").write_text(json.dumps({
        "tts_model_type": "custom_voice", "tts_model_size": "1b7", "tokenizer_type": "qwen3_tts_tokenizer_12hz",
    }))
    imported = []

    def import_module(name):
        imported.append(name)
        if name == "torch":
            return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        pytest.fail("An unavailable device must fail before loading Qwen")

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module", import_module)
    with pytest.raises(RuntimeError, match=r"CUDA.*unavailable"):
        load_local_model(tmp_path, device="cuda")
    assert imported == ["torch"]


def test_worker_unknown_device_fails_before_reading_model(tmp_path):
    from lixity.speech_qwen import load_local_model

    with pytest.raises(ValueError, match="device"):
        load_local_model(tmp_path / "missing", device="remote")


@pytest.mark.parametrize("threads", [0, -1, 65, True, 1.5])
def test_worker_invalid_threads_fail_before_reading_model(tmp_path, threads):
    from lixity.speech_qwen import load_local_model

    with pytest.raises(ValueError, match="threads"):
        load_local_model(tmp_path / "missing", threads=threads)


@pytest.mark.parametrize("body,language", [
    ("这是一个测试句子。" * 80, "zh"),
    ("これは長い日本語の文章です。次も続きます\uff01" * 60, "ja"),
    (("中文 English identifiers remain intact。次は日本語です\uff01\uff1f" * 40), "ja"),
    ("中文没有标点" * 150, "zh"),
], ids=["chinese", "japanese", "mixed", "no-punctuation"])
def test_unspaced_cjk_segments_preserve_every_character(body, language):
    from lixity.speech import extract_audio_cues

    cues = extract_audio_cues(body, language=language)
    assert len(cues) > 1
    assert "".join(cue.text for cue in cues) == body
    assert all(0 < len(cue.text) <= 600 for cue in cues)
    assert sum(cue.pause_after > 0 for cue in cues) == 1


def test_cjk_profile_replanning_preserves_text(tmp_path, monkeypatch):
    body = "这是一个测试句子。" * 80
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen",
                        lambda text, _profile: calls.append(text) or generate_silence_wav(.01, 24000))
    source = tmp_path / "source.md"
    source.write_text(body)
    selected = AudioProfile(engine="qwen3", language="zh", voice="Vivian", pronunciations={"测试": "合成"})
    render_speech_audio(source, tmp_path / "out.wav", profile=selected)
    assert "".join(calls) == body.replace("测试", "合成")
    assert all(len(text) <= 600 for text in calls)


@pytest.mark.parametrize("status", [400, 307, 503])
def test_adapter_closes_http_error_response(status):
    response = io.BytesIO(b"Synthetic error")
    error = urllib.error.HTTPError(ENDPOINT, status, "Synthetic error", Message(), response)

    def fail_request(*_args, **_kwargs):
        raise error

    with pytest.raises(RuntimeError, match="worker"):
        synthesize_qwen("Synthetic text.", profile(), opener=SimpleNamespace(open=fail_request))
    assert response.closed
