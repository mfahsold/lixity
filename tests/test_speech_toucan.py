"""Synthetic Toucan controls and offline loading, without optional model imports."""
from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import threading
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_engines import TOUCAN_MODEL
from lixity.speech_profiles import AudioProfile
from lixity.speech_references import SpeechReference, _identity


def _save_set(tmp_path, *, fallback_part_index=1, reverse=False):
    from lixity.speech_probe import build_voice_probe_script
    from lixity.speech_references import prepare_reference, save_reference_set

    text = " ".join(
        f"Synthetic sentence number {index} describes a calm private test passage."
        for index in range(100)
    )
    script = build_voice_probe_script(text, language="de", target_seconds=125)
    assert script.status == "ready"
    probe = script.to_dict()
    parts = [
        prepare_reference(generate_silence_wav(150 / len(script.parts)), f"Synthetic part {index}.")
        for index in range(1, len(script.parts) + 1)
    ]
    if reverse:
        parts.reverse()
    return save_reference_set(
        tmp_path, parts, source_sha256=script.source_sha256, settings_sha256=script.settings_sha256,
        probe_sha256=script.probe_sha256, language="de", terms=("Mara",),
        fallback_part_index=fallback_part_index, probe=probe,
    )


def test_missing_toucan_assets_fail_before_importing_optional_dependencies(tmp_path, monkeypatch):
    from lixity import speech_toucan

    monkeypatch.setattr(speech_toucan.importlib, "import_module", lambda _name: pytest.fail("optional import"))
    with pytest.raises(ValueError, match="local"):
        speech_toucan.load_renderer(tmp_path, tmp_path, tmp_path)


@pytest.mark.parametrize("version", ["2.4.1", "2.5.1+cpu", "2.6.0rc1", "unknown"])
def test_toucan_refuses_unsupported_torch_before_checkpoint_loading(tmp_path, monkeypatch, version):
    from lixity import speech_toucan

    def load_module(name):
        assert name == "torch"
        return SimpleNamespace(__version__=version, load=lambda *args, **kw: pytest.fail("checkpoint load"))

    monkeypatch.setattr(speech_toucan.importlib, "import_module", load_module)
    with pytest.raises(ValueError, match=r"requires PyTorch 2\.6\.0 or later"):
        speech_toucan._load_runtime(tmp_path, tmp_path, device="cpu", threads=1)


def test_toucan_recognizes_stable_patched_torch_with_platform_suffix(tmp_path, monkeypatch):
    from lixity import speech_toucan

    setup = []

    def load_module(name):
        if name == "torch":
            return SimpleNamespace(__version__="2.6.0+cpu", set_num_threads=setup.append)
        raise ImportError(name)

    monkeypatch.setattr(speech_toucan.importlib, "import_module", load_module)
    with pytest.raises(ImportError, match="soundfile"):
        speech_toucan._load_runtime(tmp_path, tmp_path, device="cpu", threads=1)
    assert setup == [1]


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

    with pytest.raises(ValueError, match="control") as error:
        prepare_phones("Name", {"Name": replacement}, phonemize=lambda _: pytest.fail("fallback"),
                       validate=lambda _: None)
    assert error.value.code == "reserved_control_token"


@pytest.mark.parametrize("phones", ["a \u02d0", "\u02c8 a", "\u02c8\u02c8a", "\u02c8", "~\u02d0a", "a.\u0303", "a\u02d0\u02d0"])
def test_phoneme_modifiers_cannot_target_boundaries_or_silently_collapse(phones):
    from lixity.speech_toucan import _validate_phone_order

    with pytest.raises(ValueError, match="modifier") as error:
        _validate_phone_order(phones, {"a", "n"})
    assert error.value.code == "invalid_modifier_order"


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
                           phonemes={"Name": "na\u02d0mə", "Unused": "ʊn"}, prosody={"pitch_variance_scale": 0.8})
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


def test_toucan_segments_keep_paragraph_prosody_context():
    from lixity.speech_direction import build_speech_plan, segment_speech_text
    from lixity.speech_profiles import TOUCAN_SEGMENT_CHARS

    text = " ".join(f"Satz {index} steht im Absatz." for index in range(60))
    toucan = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id="a" * 64)
    pieces = segment_speech_text(text, toucan)
    assert len(pieces) == 1
    assert len(pieces[0]) > 600
    assert len(pieces[0]) <= TOUCAN_SEGMENT_CHARS

    long_text = " ".join("Ein längerer Absatz behält seinen Kontext." for _ in range(200))
    pieces = segment_speech_text(long_text, toucan)
    assert 1 < len(pieces) <= (len(long_text) // 600 + 1)
    assert all(len(piece) <= TOUCAN_SEGMENT_CHARS for piece in pieces)

    qwen = AudioProfile(speed=1.0)
    plan = build_speech_plan("## Kapitel\n\n" + text, toucan, chapter=1)
    assert len([row for row in plan if row.anchor]) == 1
    assert all(len(row.text) <= TOUCAN_SEGMENT_CHARS for row in plan if row.text)
    assert len(segment_speech_text(text, qwen)) > 1


def test_toucan_http_worker_accepts_long_segments_and_rejects_transport_limit():
    from lixity.speech_profiles import TOUCAN_SEGMENT_CHARS
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
               "phonemes": {}, "prosody": {}}
    def post(value):
        return opener.open(urllib.request.Request(endpoint, data=json.dumps(value).encode(),
                                                  headers={"Content-Type": "application/json"}))
    try:
        long_text = "Ein Absatz. " * (TOUCAN_SEGMENT_CHARS // 12)
        with post({**payload, "input": long_text}) as response:
            assert response.status == 200
        with pytest.raises(urllib.error.HTTPError) as error:
            post({**payload, "input": long_text + "Zu lang." * 500})
        with error.value:
            assert error.value.code == 400
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_toucan_adapter_sends_all_probe_parts_for_embedding_aggregation(tmp_path):
    from lixity.speech_toucan import synthesize_toucan

    reference = _save_set(tmp_path)
    profile = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id=reference.id)
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
    payload = json.loads(calls[0].data)
    assert len(payload["reference_parts"]) == len(reference.parts)
    assert [base64.b64decode(part["audio"]) for part in payload["reference_parts"]] == [
        part.audio for part in reference.parts
    ]
    assert [part["text"] for part in payload["reference_parts"]] == [
        part.transcript for part in reference.parts
    ]
    assert "reference_audio" not in payload and "reference_text" not in payload


def test_toucan_set_embedding_aggregation_and_memory_key_are_versioned():
    import numpy as np

    from lixity.speech_engines import REFERENCE_SET_AGGREGATION_VERSION
    from lixity.speech_toucan import _normalized_mean_speaker_embedding, _reference_cache_key

    embeddings = [np.asarray([3.0, 0.0]), np.asarray([0.0, 5.0]), np.asarray([1.0, 1.0])]
    expected = np.mean([
        np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0]), np.asarray([1.0, 1.0]) / np.sqrt(2.0),
    ], axis=0)
    expected /= np.linalg.norm(expected)
    combined = _normalized_mean_speaker_embedding(embeddings, np)
    assert np.allclose(combined, expected)
    assert np.isclose(np.linalg.norm(combined), 1.0)

    decoded = [(b"first", b""), (b"second", b""), (b"third", b"")]
    key = _reference_cache_key(decoded, reference_set=True)
    assert key == (REFERENCE_SET_AGGREGATION_VERSION, tuple(
        hashlib.sha256(audio).digest() for audio, _frames in decoded
    ))
    assert key != _reference_cache_key(list(reversed(decoded)), reference_set=True)
    single = [(b"first", b"")]
    assert _reference_cache_key(single, reference_set=False) == hashlib.sha256(b"first").hexdigest()


@pytest.mark.parametrize("embeddings", [
    [np.asarray([0.0, 0.0]), np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])],
    [np.asarray([np.nan, 0.0]), np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])],
    [np.asarray([np.inf, 0.0]), np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])],
    [np.asarray([1.0]), np.asarray([1.0, 0.0]), np.asarray([0.0, 1.0])],
    [np.asarray([1.0, 0.0]), np.asarray([-0.5, np.sqrt(3.0) / 2.0]),
     np.asarray([-0.5, -np.sqrt(3.0) / 2.0])],
])
def test_toucan_set_embedding_aggregation_rejects_invalid_vectors(embeddings):
    import numpy as np

    from lixity.speech_toucan import _normalized_mean_speaker_embedding

    with pytest.raises(ValueError, match="embedding"):
        _normalized_mean_speaker_embedding(embeddings, np)


def test_toucan_http_worker_validates_reference_set_transport_and_limits():
    import http.client

    from lixity.speech_worker import (
        MAX_BASE_REQUEST_BYTES,
        MAX_REFERENCE_SET_REQUEST_BYTES,
        MAX_REQUEST_BYTES,
        worker_server,
    )

    assert MAX_BASE_REQUEST_BYTES == MAX_REQUEST_BYTES + 4 * ((3 * 1024 * 1024 + 2) // 3)
    assert MAX_REFERENCE_SET_REQUEST_BYTES == 16 * 1024 * 1024
    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_silence_wav(.1), port=0, model=TOUCAN_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/audio/speech"

    def parts(durations):
        return [
            {"audio": base64.b64encode(generate_silence_wav(duration)).decode(),
             "text": f"Private reference {index}."}
            for index, duration in enumerate(durations, 1)
        ]

    valid_parts = parts((40, 40, 40))
    payload = {"model": TOUCAN_MODEL, "input": "Name.", "language": "de", "voice": "reference",
               "instructions": "", "response_format": "wav", "phonemes": {}, "prosody": {}}

    def post(value):
        return opener.open(urllib.request.Request(endpoint, data=json.dumps(value).encode(),
                                                   headers={"Content-Type": "application/json"}))

    try:
        with post({**payload, "reference_parts": valid_parts}) as response:
            assert response.status == 200
        assert [part["text"] for part in calls[0]["reference_parts"]] == [
            part["text"] for part in valid_parts
        ]
        invalid = [
            {**payload, "reference_parts": valid_parts[:2]},
            {**payload, "reference_parts": [*valid_parts, valid_parts[0]]},
            {**payload, "reference_parts": parts((40, 40, 39.999))},
            {**payload, "reference_parts": parts((45, 45, 45, 45.001))},
            {**payload, "reference_parts": [{**valid_parts[0], "unexpected": "PRIVATE"}]},
            {**payload, "reference_parts": valid_parts,
             "reference_audio": valid_parts[0]["audio"], "reference_text": valid_parts[0]["text"]},
        ]
        for value in invalid:
            with pytest.raises(urllib.error.HTTPError) as error:
                post(value)
            with error.value:
                assert error.value.code == 400
                assert b"PRIVATE" not in error.value.read()
        assert len(calls) == 1
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        try:
            connection.putrequest("POST", "/v1/audio/speech")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(MAX_REFERENCE_SET_REQUEST_BYTES + 1))
            connection.endheaders()
            assert connection.getresponse().status == 400
        finally:
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_toucan_worker_returns_validation_code_for_unsupported_phoneme():
    from lixity.speech_worker import SpeechRequestValidationError, worker_server

    def synthesize(_request):
        raise SpeechRequestValidationError("unsupported_phoneme", "Unsupported phoneme")

    server = worker_server(synthesize, port=0, model=TOUCAN_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/audio/speech"
    payload = {"model": TOUCAN_MODEL, "input": "Name.", "language": "de", "voice": "reference",
               "instructions": "", "response_format": "wav", "reference_text": "Synthetic reference.",
               "reference_audio": base64.b64encode(generate_silence_wav(1)).decode(),
               "phonemes": {"Name": "ɚ"}, "prosody": {}}
    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            opener.open(urllib.request.Request(endpoint, data=json.dumps(payload).encode(),
                                               headers={"Content-Type": "application/json"}))
        with error.value:
            assert error.value.code == 400
            assert json.loads(error.value.read())["code"] == "unsupported_phoneme"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


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
