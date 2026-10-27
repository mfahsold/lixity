"""Synthetic tests for fixed local synthesis transport and atomic cancellation."""
from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
import wave
from contextlib import contextmanager
from email.message import Message
from pathlib import Path
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
                        lambda text, selected, **_kwargs: calls.append((text, selected)) or generate_silence_wav(.01, 24000))
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

    def synthesize(_text, _profile, **_kwargs):
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
    def fail(*_args, **_kwargs):
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
                        lambda text, _profile, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
    source = tmp_path / "source.md"
    source.write_text(body)
    render_speech_audio(source, tmp_path / "out.wav", profile=profile(pronunciations={phrase: "boundary"}))
    spoken = " ".join(calls)
    assert "boundary" in spoken and phrase not in spoken
    assert all(len(text) <= 600 for text in calls)
    assert source.read_text() == body


@pytest.mark.parametrize("device,bf16,dtype,attention,device_map,requested", [
    ("cpu", False, "float32", "eager", "cpu", "auto"),
    ("cuda", True, "bfloat16", "sdpa", "cuda:0", "auto"),
    ("cuda", False, "float16", "sdpa", "cuda:0", "auto"),
    ("cpu", False, "float32", "sdpa", "cpu", "sdpa"),
    ("cuda", True, "bfloat16", "eager", "cuda:0", "eager"),
])
def test_worker_explicit_device_loading(tmp_path, monkeypatch, device, bf16, dtype, attention, device_map, requested):
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
    loaded = load_local_model(tmp_path, device=device, attention=requested)
    assert callable(loaded)
    assert loaded.runtime_info.device == device
    assert loaded.runtime_info.dtype == dtype
    assert loaded.runtime_info.attention == attention
    assert loaded.runtime_info.threads == 4
    assert loaded.runtime_info.codec_chunk_frames == 300
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
                        lambda text, _profile, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
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


@pytest.mark.parametrize("target,port", [("local", 8769), ("jetson", 8770)])
def test_execution_target_uses_only_fixed_loopback_endpoints(target, port):
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = QWEN_MODEL
    headers["X-Lixity-Voice"] = "Ryan"
    calls = []

    class Response(io.BytesIO):
        status = 200

    def open_request(request, timeout):
        calls.append(request)
        result = Response(generate_silence_wav(.01, 24000))
        result.headers = headers
        return result

    synthesize_qwen("Synthetic text.", profile(), target=target, opener=SimpleNamespace(open=open_request))
    assert calls[0].full_url == f"http://127.0.0.1:{port}/v1/audio/speech"
    assert "target" not in json.loads(calls[0].data)
    with pytest.raises(ValueError, match="target"):
        synthesize_qwen("Synthetic text.", profile(), target="https://example.test")


@pytest.mark.parametrize("device,codec_device,move_codec", [
    ("cuda", "cpu", True),
    ("cuda", "model", False),
    ("cpu", "cpu", False),
    ("cpu", "model", False),
])
def test_worker_explicit_codec_placement(tmp_path, monkeypatch, device, codec_device, move_codec):
    import gc

    from lixity.speech_profiles import QWEN_LANGUAGES, QWEN_VOICES
    from lixity.speech_qwen import load_local_model

    (tmp_path / "config.json").write_text(json.dumps({
        "tts_model_type": "custom_voice", "tts_model_size": "1b7", "tokenizer_type": "qwen3_tts_tokenizer_12hz",
    }))
    events = []
    codec = SimpleNamespace(device="original", model=SimpleNamespace(
        to=lambda **kwargs: events.append(("codec", kwargs))))
    model = SimpleNamespace(model=SimpleNamespace(speech_tokenizer=codec),
                            get_supported_speakers=lambda: list(QWEN_VOICES),
                            get_supported_languages=lambda: list(QWEN_LANGUAGES.values()))

    def from_pretrained(_path, **kwargs):
        events.append(("load", kwargs))
        return model

    fake_torch = SimpleNamespace(set_num_threads=lambda _count: None,
                                 device=lambda name: "torch-device:" + name,
                                 float32="float32", float16="float16", bfloat16="bfloat16",
                                 cuda=SimpleNamespace(is_available=lambda: True,
                                                      is_bf16_supported=lambda **_kw: True,
                                                      empty_cache=lambda: events.append(("empty_cache", None))))
    fake_qwen = SimpleNamespace(Qwen3TTSModel=SimpleNamespace(from_pretrained=from_pretrained))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module",
                        lambda name: {"torch": fake_torch, "qwen_tts": fake_qwen}[name])
    monkeypatch.setattr(gc, "collect", lambda: events.append(("collect", None)))
    loaded = load_local_model(tmp_path, device=device, codec_device=codec_device)
    assert callable(loaded)
    assert loaded.runtime_info.codec_device == ("cpu" if move_codec or device == "cpu" else "cuda")
    assert events[0] == ("load", {"device_map": "cuda:0" if device == "cuda" else "cpu",
                                  "dtype": "bfloat16" if device == "cuda" else "float32",
                                  "attn_implementation": "sdpa" if device == "cuda" else "eager",
                                  "local_files_only": True})
    if move_codec:
        assert events[1:] == [("codec", {"device": "cpu", "dtype": "float32"}),
                              ("collect", None), ("empty_cache", None)]
        assert codec.device == "torch-device:cpu"
    else:
        assert events[1:] == []
        assert codec.device == "original"


def test_worker_unknown_codec_device_fails_before_imports(tmp_path, monkeypatch):
    from lixity.speech_qwen import load_local_model

    def unexpected_import(_name):
        pytest.fail("Invalid codec placement must fail before optional imports")

    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module", unexpected_import)
    with pytest.raises(ValueError, match="codec"):
        load_local_model(tmp_path / "missing", codec_device="remote")


def test_worker_unknown_attention_fails_before_optional_imports(tmp_path, monkeypatch):
    from lixity.speech_qwen import load_local_model

    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module",
                        lambda _name: pytest.fail("Invalid attention must fail before optional imports"))
    with pytest.raises(ValueError, match="attention"):
        load_local_model(tmp_path / "missing", attention="flash_attention_2")


def test_worker_synthesis_enters_inference_mode_and_restores_it_on_failure(tmp_path, monkeypatch):
    from lixity.speech_profiles import QWEN_LANGUAGES, QWEN_VOICES
    from lixity.speech_qwen import load_local_model

    (tmp_path / "config.json").write_text(json.dumps({
        "tts_model_type": "custom_voice", "tts_model_size": "1b7", "tokenizer_type": "qwen3_tts_tokenizer_12hz",
    }))
    active = False
    fail = False
    calls = []

    @contextmanager
    def inference_mode():
        nonlocal active
        assert not active
        active = True
        try:
            yield
        finally:
            active = False

    def generate(**kwargs):
        assert active, "Generation and its internal codec decode need inference mode"
        calls.append(kwargs)
        if fail:
            raise RuntimeError("Synthetic inference failure")
        return ["synthetic audio"], 24000

    model = SimpleNamespace(generate_custom_voice=generate,
                            get_supported_speakers=lambda: list(QWEN_VOICES),
                            get_supported_languages=lambda: list(QWEN_LANGUAGES.values()))
    torch = SimpleNamespace(inference_mode=inference_mode, set_num_threads=lambda _n: None, float32="float32")
    soundfile = SimpleNamespace(write=lambda output, *_args, **_kwargs: output.write(generate_silence_wav(.01, 24000)))
    qwen = SimpleNamespace(Qwen3TTSModel=SimpleNamespace(from_pretrained=lambda *_a, **_kw: model))
    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module",
                        lambda name: {"torch": torch, "soundfile": soundfile, "qwen_tts": qwen}[name])
    render = load_local_model(tmp_path)
    request = {"input": "Synthetic speech.", "language": "en", "voice": "Ryan", "instructions": "Read calmly."}
    assert render(request).startswith(b"RIFF")
    assert not active
    assert calls[0]["max_new_tokens"] == 2048
    fail = True
    with pytest.raises(RuntimeError, match="Synthetic inference failure"):
        render(request)
    assert not active


@pytest.mark.parametrize("changes", [
    {"device": "remote"}, {"dtype": "/private/model"}, {"threads": True}, {"threads": 65},
    {"attention": "unknown"}, {"codec_device": "remote"},
    {"codec_chunk_frames": 15}, {"codec_chunk_frames": 301}, {"codec_chunk_frames": True},
])
def test_worker_runtime_diagnostics_reject_unbounded_values(changes):
    from lixity.speech_qwen import WorkerRuntime

    values = {"device": "cpu", "dtype": "float32", "threads": 4, "attention": "eager", "codec_device": "cpu"}
    with pytest.raises(ValueError):
        WorkerRuntime(**(values | changes))


def test_worker_health_reports_bounded_resolved_runtime():
    from lixity.speech_qwen import WorkerRuntime

    runtime = WorkerRuntime(device="cuda", dtype="float16", threads=6, attention="sdpa", codec_device="cpu",
                            codec_chunk_frames=32)
    server = worker_server(lambda _request: generate_silence_wav(.01, 24000), port=0, runtime_info=runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{server.server_port}/health") as response:
            payload = json.load(response)
        assert payload == {"ready": True, "model": QWEN_MODEL, "runtime": {
            "device": "cuda", "dtype": "float16", "threads": 6, "attention": "sdpa", "codec_device": "cpu",
            "codec_chunk_frames": 32}}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_worker_cli_forwards_codec_device(monkeypatch):
    import sys

    import lixity.speech_qwen as worker

    calls = []

    def load(path, **kwargs):
        calls.append((path, kwargs))
        return SimpleNamespace(runtime_info="synthetic runtime")

    def worker_server(render, port, runtime_info):
        assert runtime_info == render.runtime_info == "synthetic runtime"
        return server

    def serve():
        raise KeyboardInterrupt

    server = SimpleNamespace(serve_forever=serve, server_close=lambda: calls.append("closed"))
    monkeypatch.setattr(worker, "load_local_model", load)
    monkeypatch.setattr(worker, "worker_server", worker_server)
    monkeypatch.setattr(sys, "argv", ["speech_qwen", "--model", "/synthetic/model", "--device", "cuda",
                                      "--codec-device", "cpu", "--attention", "eager", "--threads", "6",
                                      "--codec-chunk-frames", "32"])
    worker.main()
    assert calls == [(Path("/synthetic/model"), {"device": "cuda", "codec_device": "cpu", "threads": 6,
                                               "attention": "eager", "codec_chunk_frames": 32}),
                     "closed"]


@pytest.fixture
def chunk_codec(tmp_path, monkeypatch):
    from lixity.speech_profiles import QWEN_LANGUAGES, QWEN_VOICES

    (tmp_path / "config.json").write_text(json.dumps({
        "tts_model_type": "custom_voice", "tts_model_size": "1b7", "tokenizer_type": "qwen3_tts_tokenizer_12hz",
    }))
    calls = []

    class Decoder:
        def chunked_decode(self, codes, chunk_size=300, left_context_size=25):
            calls.append((self, codes, chunk_size, left_context_size))
            return "decoded waveform"

    decoder = Decoder()
    model = SimpleNamespace(model=SimpleNamespace(speech_tokenizer=SimpleNamespace(
        model=SimpleNamespace(decoder=decoder))),
        get_supported_speakers=lambda: list(QWEN_VOICES),
        get_supported_languages=lambda: list(QWEN_LANGUAGES.values()))
    torch = SimpleNamespace(set_num_threads=lambda _n: None, float32="float32")
    qwen = SimpleNamespace(Qwen3TTSModel=SimpleNamespace(from_pretrained=lambda *_a, **_kw: model))
    monkeypatch.setattr("lixity.speech_qwen.importlib.import_module",
                        lambda name: {"torch": torch, "qwen_tts": qwen}[name])
    return tmp_path, decoder, calls


@pytest.mark.parametrize("frames", [16, 32, 299])
def test_codec_chunk_override_is_per_instance_and_retains_context(chunk_codec, frames):
    from lixity.speech_qwen import load_local_model

    path, decoder, calls = chunk_codec
    peer = type(decoder)()
    render = load_local_model(path, codec_chunk_frames=frames)
    assert render.runtime_info.codec_chunk_frames == frames
    codes = object()
    assert decoder.chunked_decode(codes) == "decoded waveform"
    assert calls[-1] == (decoder, codes, frames, 25)
    peer.chunked_decode(codes)
    assert calls[-1] == (peer, codes, 300, 25), "Another loaded model must keep upstream defaults"


def test_codec_chunk_default_leaves_upstream_method_untouched(chunk_codec):
    from lixity.speech_qwen import load_local_model

    path, decoder, calls = chunk_codec
    original = decoder.chunked_decode
    render = load_local_model(path)
    assert decoder.chunked_decode == original
    assert render.runtime_info.codec_chunk_frames == 300
    decoder.chunked_decode("codes")
    assert calls[-1] == (decoder, "codes", 300, 25)


@pytest.mark.parametrize("method", [
    None,
    lambda codes, **kwargs: None,
    lambda codes, chunk_size=300: None,
    lambda codes, chunk_size=300, left_context_size=25, /: None,
])
def test_codec_chunk_override_rejects_unsupported_upstream_signature(chunk_codec, method):
    from lixity.speech_qwen import load_local_model

    path, decoder, _calls = chunk_codec
    decoder.chunked_decode = method
    with pytest.raises(ValueError, match=r"codec.*chunk"):
        load_local_model(path, codec_chunk_frames=32)


@pytest.mark.parametrize("frames", [15, 301, True, 32.0, "32"])
def test_invalid_codec_chunk_size_fails_before_reading_model(tmp_path, frames):
    from lixity.speech_qwen import load_local_model

    with pytest.raises(ValueError, match="chunk"):
        load_local_model(tmp_path / "missing", codec_chunk_frames=frames)


def test_worker_health_verifies_model_and_never_uses_proxy_or_redirects():
    from lixity.speech_qwen import worker_health

    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def read(self, limit):
            assert limit == 4097
            return json.dumps({'ready': True, 'model': QWEN_MODEL}).encode()
    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url == 'http://127.0.0.1:8770/health'
            assert timeout <= 2
            return Reply()
    assert worker_health('jetson', opener=Opener())['state'] == 'ready'
    with pytest.raises(ValueError):
        worker_health('external')
