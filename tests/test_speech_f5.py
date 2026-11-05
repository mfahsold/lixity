"""Unit tests for offline F5-TTS Flow-Matching speech adapter and worker."""
from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

from lixity.speech_controls import speech_control_support
from lixity.speech_direction import same_narrator
from lixity.speech_f5 import F5_MODEL, load_renderer, synthesize_f5
from lixity.speech_profiles import AudioProfile, audio_capabilities
from lixity.speech_references import SpeechReference, _identity


def generate_test_wav(duration_seconds: float = 0.1, sample_rate: int = 24000) -> bytes:
    import struct
    import wave

    output = io.BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frames = int(duration_seconds * sample_rate)
        writer.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))
    return output.getvalue()


def test_f5_profile_validation_requires_reference_id_and_forbids_instructions():
    valid = AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, language="de")
    assert valid.engine == "f5-tts"
    assert valid.voice == "reference"

    with pytest.raises(ValueError, match="reference"):
        AudioProfile(engine="f5-tts", voice="other", reference_id="a" * 64, language="de")

    with pytest.raises(ValueError, match="reference"):
        AudioProfile(engine="f5-tts", voice="reference", reference_id="", language="de")

    with pytest.raises(ValueError, match="instructions"):
        AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, instructions="Quiet.", language="de")

    with pytest.raises(ValueError, match="German and English"):
        AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, language="zh")


def test_f5_advertises_capabilities_and_control_support():
    caps = audio_capabilities()["f5-tts"]
    assert caps["name"] == "F5-TTS Flow-Matching"
    assert caps["model"] == F5_MODEL
    assert caps["reference_required"] is True
    assert caps["targets"] == ["local"]
    assert caps["instructions"] is False

    support = speech_control_support("f5-tts")
    assert support.direction == "unsupported"
    assert support.pauses == "explicit_silence"


def test_f5_narrator_integrity_allows_delivery_references():
    primary = AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, language="de")
    delivery = AudioProfile(engine="f5-tts", voice="reference", reference_id="b" * 64, language="de", speed=0.9)
    other_lang = AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, language="en")
    other_engine = AudioProfile(engine="qwen3-base", voice="reference", reference_id="a" * 64, language="de")

    assert same_narrator(primary, delivery) is True
    assert same_narrator(primary, other_lang) is False
    assert same_narrator(primary, other_engine) is False


def test_synthesize_f5_validates_request_and_reference():
    profile = AudioProfile(engine="f5-tts", voice="reference", reference_id="a" * 64, language="de")
    ref_audio = generate_test_wav(0.2)
    reference = SpeechReference(id="a" * 64, audio=ref_audio, transcript="Referenztext.")

    with pytest.raises(ValueError, match="matching verified reference"):
        synthesize_f5("Hallo Welt.", profile, reference=None)

    wrong_ref = SpeechReference(id="b" * 64, audio=ref_audio, transcript="Referenztext.")
    with pytest.raises(ValueError, match="matching verified reference"):
        synthesize_f5("Hallo Welt.", profile, reference=wrong_ref)

    with pytest.raises(ValueError, match="synthesis request"):
        synthesize_f5("   ", profile, reference=reference)


def test_synthesize_f5_sends_payload_and_receives_wav():
    ref_audio = generate_test_wav(1.0)
    ref_id = _identity(ref_audio, "Referenztext.")
    profile = AudioProfile(engine="f5-tts", voice="reference", reference_id=ref_id, language="de")
    reference = SpeechReference(id=ref_id, audio=ref_audio, transcript="Referenztext.")
    wav_response = generate_test_wav(0.5)

    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = F5_MODEL
    headers["X-Lixity-Voice"] = "reference"

    class Response(io.BytesIO):
        status = 200

    requests = []

    def mock_open(req, timeout):
        requests.append(json.loads(req.data.decode("utf-8")))
        res = Response(wav_response)
        res.headers = headers
        return res

    opener = SimpleNamespace(open=mock_open)
    audio = synthesize_f5("Guten Morgen.", profile, opener=opener, reference=reference)
    assert audio == wav_response
    assert len(requests) == 1
    assert requests[0]["model"] == F5_MODEL
    assert requests[0]["input"] == "Guten Morgen."
    assert requests[0]["voice"] == "reference"
    assert requests[0]["language"] == "de"
    assert requests[0]["reference_text"] == "Referenztext."
    assert "reference_audio" in requests[0]


def test_synthesize_f5_rejects_mismatched_model_header():
    ref_audio = generate_test_wav(1.0)
    ref_id = _identity(ref_audio, "Referenztext.")
    profile = AudioProfile(engine="f5-tts", voice="reference", reference_id=ref_id, language="de")
    reference = SpeechReference(id=ref_id, audio=ref_audio, transcript="Referenztext.")

    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = "wrong-model"
    headers["X-Lixity-Voice"] = "reference"

    class Response(io.BytesIO):
        status = 200

    def mock_open(req, timeout):
        res = Response(b"")
        res.headers = headers
        return res

    opener = SimpleNamespace(open=mock_open)
    with pytest.raises(ValueError, match="model or voice mismatch"):
        synthesize_f5("Guten Morgen.", profile, opener=opener, reference=reference)


def test_load_renderer_validates_checkpoint_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_model"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="checkpoint file"):
        load_renderer(empty_dir)

    with pytest.raises(ValueError, match="Threads"):
        load_renderer(empty_dir, threads=0)

    with pytest.raises(ValueError, match="Device"):
        load_renderer(empty_dir, device="invalid")


def test_unverified_f5_loader_fails_explicitly_before_optional_imports(tmp_path, monkeypatch):
    """A checkpoint alone cannot satisfy the upstream vocabulary/vocoder API."""
    (tmp_path / "model_1200000.safetensors").write_bytes(b"synthetic checkpoint")
    monkeypatch.setattr("importlib.import_module", lambda _: pytest.fail("unverified optional runtime import"))
    with pytest.raises(ValueError, match="F5-TTS runtime integration is unavailable"):
        load_renderer(tmp_path)


def test_retired_f5_cli_reports_actionable_failure_and_help(tmp_path, monkeypatch, capsys):
    from lixity.speech_f5 import main

    (tmp_path / "model_1200000.safetensors").write_bytes(b"synthetic checkpoint")
    monkeypatch.setattr("sys.argv", ["worker", "--model", str(tmp_path)])
    with pytest.raises(SystemExit) as failed:
        main()
    assert failed.value.code == 2
    error = capsys.readouterr().err
    assert "F5-TTS runtime integration is unavailable" in error
    assert "IMS-Toucan" in error and "existing F5 profiles and references are preserved" in error
    assert "Traceback" not in error
    monkeypatch.setattr("sys.argv", ["worker", "--help"])
    with pytest.raises(SystemExit) as helped:
        main()
    assert helped.value.code == 0
    assert "F5-TTS runtime integration is unavailable" in capsys.readouterr().out


def test_f5_worker_accepts_its_reference_contract_and_rejects_browser_origins():
    """The advertised F5 worker must start and validate real HTTP requests."""
    import base64

    from lixity.speech_qwen import worker_server

    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_test_wav(), port=0, model=F5_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = f"http://127.0.0.1:{server.server_port}"
    payload = {"model": F5_MODEL, "input": "Synthetic text.", "language": "en", "voice": "reference",
               "instructions": "", "response_format": "wav", "reference_text": "Synthetic reference.",
               "reference_audio": base64.b64encode(generate_test_wav(1)).decode()}
    try:
        with opener.open(endpoint + "/health") as response:
            assert json.load(response) == {"ready": True, "model": F5_MODEL}
        request = urllib.request.Request(endpoint + "/v1/audio/speech", data=json.dumps(payload).encode(),  # noqa: S310 - loopback
                                         headers={"Content-Type": "application/json"})
        with opener.open(request) as response:
            assert response.headers["X-Lixity-Model"] == F5_MODEL
            assert response.read().startswith(b"RIFF")
        request.add_header("Origin", "http://example.invalid")
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(request)
        with error.value:
            assert error.value.code == 403
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
