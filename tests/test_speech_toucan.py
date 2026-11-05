"""Synthetic Toucan controls and offline loading, without optional model imports."""
from __future__ import annotations

import base64
import importlib
import io
import json
import threading
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_engines import TOUCAN_MODEL
from lixity.speech_profiles import AudioProfile
from lixity.speech_references import SpeechReference, _identity


def test_missing_toucan_assets_fail_before_importing_optional_dependencies(tmp_path, monkeypatch):
    from lixity import speech_toucan

    monkeypatch.setattr(speech_toucan.importlib, "import_module", lambda _name: pytest.fail("optional import"))
    with pytest.raises(ValueError, match="local"):
        speech_toucan.load_renderer(tmp_path, tmp_path, tmp_path)


def test_phoneme_overrides_are_exact_longest_whole_word_and_plain_gaps_use_g2p():
    module = importlib.import_module("lixity.speech_toucan")
    calls = []
    checked = []
    def phonemize(text):
        calls.append(text)
        return text.lower()
    result = module.prepare_phones("A New York Yorker.", {"New": "n", "New York": "nju jɔɹk", "York": "j"},
                                   phonemize=phonemize, validate=checked.append)
    assert result == "~a nju jɔɹk yorker.~#"
    assert calls == ["A ", " Yorker."]
    assert "nju jɔɹk" in checked


def test_phoneme_validation_fails_before_any_inference_or_fallback():
    module = importlib.import_module("lixity.speech_toucan")
    def invalid(_phones):
        raise ValueError("Unsupported phoneme")
    with pytest.raises(ValueError, match="Unsupported phoneme"):
        module.prepare_phones("Name", {"Name": "unsupported"}, phonemize=lambda _: pytest.fail("fallback"), validate=invalid)


@pytest.mark.parametrize("replacement", ["~#", "a#", "a~", "a.a", "a!", "a?"])
def test_explicit_ipa_cannot_replace_words_with_toucan_control_tokens(replacement):
    from lixity.speech_toucan import prepare_phones

    with pytest.raises(ValueError, match="control"):
        prepare_phones("Name", {"Name": replacement}, phonemize=lambda _: pytest.fail("fallback"),
                       validate=lambda _: None)


@pytest.mark.parametrize("phones", ["a \u02d0", "\u02c8 a", "\u02c8\u02c8a", "\u02c8", "~\u02d0a", "a.\u0303", "a\u02d0\u02d0"])
def test_phoneme_modifiers_cannot_target_boundaries_or_silently_collapse(phones):
    from lixity.speech_toucan import _validate_phone_order

    with pytest.raises(ValueError, match="modifier"):
        _validate_phone_order(phones, {"a", "n"})


def test_phoneme_modifiers_can_target_actual_adjacent_phones():
    from lixity.speech_toucan import _validate_phone_order

    _validate_phone_order("~\u02c8a\u02d0\u0303 na~#", {"a", "n"})


@pytest.mark.parametrize(("text", "overrides", "expected"), [
    ("Name, weiter", {"Name": "na"}, "~na~ weiter~#"),
    ("vorher, Name", {"Name": "na"}, "~vorher~ na~#"),
    ("Name,", {"Name": "na"}, "~na~~#"),
])
def test_plain_gap_punctuation_survives_next_to_phoneme_overrides(text, overrides, expected):
    from lixity.speech_toucan import _normalize_gap, prepare_phones

    # The upstream normalizer trims silence at both outer edges. A gap is
    # internal to the sentence, so its edge punctuation must remain meaningful.
    def normalize(raw):
        return "~" + raw.replace(",", "~").lstrip("~").rstrip("~")
    assert prepare_phones(text, overrides, phonemize=lambda gap: _normalize_gap(gap, normalize),
                          validate=lambda _: None) == expected


def test_toucan_local_files_are_explicit_and_bounded(tmp_path: Path):
    from lixity.speech_toucan import load_renderer

    with pytest.raises(ValueError, match="Threads"):
        load_renderer(tmp_path, tmp_path, tmp_path, threads=0)
    with pytest.raises(ValueError, match="Device"):
        load_renderer(tmp_path, tmp_path, tmp_path, device="automatic")


def test_toucan_adapter_sends_exact_structured_controls_and_verified_reference():
    from lixity.speech_toucan import synthesize_toucan

    audio = generate_silence_wav(1)
    reference = SpeechReference(_identity(audio, "Reference."), audio, "Reference.")
    profile = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id=reference.id,
                           phonemes={"Name": "na\u02d0mə"}, prosody={"pitch_variance_scale": 0.8})
    calls = []
    class Response(io.BytesIO):
        status = 200
    def open_request(request, timeout):
        calls.append(request)
        response = Response(generate_silence_wav(.1))
        response.headers = Message()
        response.headers["Content-Type"] = "audio/wav"
        response.headers["X-Lixity-Model"] = TOUCAN_MODEL
        response.headers["X-Lixity-Voice"] = "reference"
        return response
    synthesize_toucan("Name.", profile, reference=reference, opener=SimpleNamespace(open=open_request))
    assert calls[0].full_url == "http://127.0.0.1:8772/v1/audio/speech"
    payload = json.loads(calls[0].data)
    assert payload["phonemes"] == {"Name": "na\u02d0mə"}
    assert payload["prosody"] == {"pitch_variance_scale": 0.8}
    assert base64.b64decode(payload["reference_audio"]) == audio
    with pytest.raises(ValueError, match="target"):
        synthesize_toucan("Name.", profile, target="jetson", reference=reference)


def test_toucan_http_worker_enforces_controls_before_inference():
    from lixity.speech_worker import worker_server

    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_silence_wav(.1), port=0, model=TOUCAN_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/audio/speech"
    payload = {"model": TOUCAN_MODEL, "input": "Name.", "language": "de", "voice": "reference",
               "instructions": "", "response_format": "wav", "reference_text": "Synthetic reference.",
               "reference_audio": base64.b64encode(generate_silence_wav(1)).decode(),
               "phonemes": {"Name": "na\u02d0mə"}, "prosody": {"duration_scaling_factor": 1.1}}
    def post(value):
        return opener.open(urllib.request.Request(endpoint, data=json.dumps(value).encode(),
                                                  headers={"Content-Type": "application/json"}))
    try:
        with post(payload) as response:
            assert response.headers["X-Lixity-Model"] == TOUCAN_MODEL
            assert response.read().startswith(b"RIFF")
        for update in ({"instructions": "Whisper"}, {"language": "unknown"}, {"phonemes": []},
                       {"prosody": {"pitch_variance_scale": -1}}, {"prosody": {"guess_emotion": "sad"}},
                       {"reference_audio": "!"}):
            with pytest.raises(urllib.error.HTTPError) as error:
                post({**payload, **update})
            with error.value:
                assert error.value.code == 400
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
