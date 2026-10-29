"""Contracts for German Coqui and reference-voice audio profiles."""

import json
import threading
import urllib.request

import pytest
from pydantic import ValidationError

from lixity.speech import generate_silence_wav, render_speech_audio
from lixity.speech_cache import SpeechSegmentCache
from lixity.speech_direction import (
    CoquiDirectionConflict,
    Direction,
    build_speech_plan,
    plan_json,
    speech_passages,
)
from lixity.speech_profiles import (
    COQUI_MODEL,
    COQUI_REFERENCE_MODEL,
    AudioProfile,
    audio_capabilities,
    parse_audio_settings,
)
from lixity.speech_qwen import synthesize_qwen, worker_server
from lixity.speech_references import save_reference


def test_coqui_profiles_advertise_supported_controls() -> None:
    capabilities = audio_capabilities()
    for engine in ("coqui", "coqui-reference"):
        assert capabilities[engine]["languages"] == ["de"]
        assert capabilities[engine]["control_support"]["direction"] == "unsupported"
        assert capabilities[engine]["control_support"]["pronunciation"] == "text_substitution"


def test_reference_profile_requires_verified_identity_and_rejects_direction() -> None:
    profile = AudioProfile(engine="coqui-reference", language="de", voice="reference", reference_id="a" * 64)
    assert profile.reference_id == "a" * 64
    with pytest.raises(ValidationError):
        AudioProfile(engine="coqui-reference", language="de", voice="reference")
    with pytest.raises(ValidationError):
        AudioProfile(engine="coqui-reference", language="de", voice="reference", reference_id="a" * 64, instructions="whisper")


def test_coqui_preset_is_german_only() -> None:
    AudioProfile(engine="coqui", language="de", voice="thorsten")
    with pytest.raises(ValidationError):
        AudioProfile(engine="coqui", language="en", voice="thorsten")
    with pytest.raises(ValueError, match="local"):
        synthesize_qwen("Hallo", AudioProfile(engine="coqui", language="de", voice="thorsten"), target="jetson")


def test_coqui_saved_profiles_require_versioned_settings() -> None:
    profile = AudioProfile(engine="coqui", language="de", voice="thorsten")
    settings = {"selected": "voice", "profiles": {"voice": profile.model_dump()}}
    with pytest.raises(ValidationError):
        parse_audio_settings({**settings, "schema_version": "lixity-audio-settings/2"})
    assert parse_audio_settings({**settings, "schema_version": "lixity-audio-settings/3"}).profiles["voice"] == profile


def test_schema_upgrade_is_reviewed_and_backed_up(tmp_path) -> None:
    from lixity.config import read_explicit_project_config
    from lixity.speech_migration import prepare_schema3_migration

    project = tmp_path / "project"
    project.mkdir()
    config = project / "lixity.toml"
    config.write_text('language = "de"\n[audio]\nschema_version = "lixity-audio-settings/1"\nselected = "narrator"\n[audio.profiles.narrator]\nengine = "qwen3"\nvoice = "Ryan"\nlanguage = "de"\n', encoding="utf-8")
    before = config.read_bytes()
    candidate = prepare_schema3_migration(project)
    assert config.read_bytes() == before
    assert candidate.public_dict()["target_schema"] == "lixity-audio-settings/3"
    candidate.apply(tmp_path / "backup.zip")
    assert read_explicit_project_config(project)["audio"]["schema_version"] == "lixity-audio-settings/3"
    assert (tmp_path / "backup.zip").is_file()


def test_schema_upgrade_rejects_changed_configuration(tmp_path) -> None:
    from lixity.speech_migration import prepare_schema3_migration

    project = tmp_path / "project"
    project.mkdir()
    config = project / "lixity.toml"
    config.write_text('language = "de"\n', encoding="utf-8")
    candidate = prepare_schema3_migration(project)
    config.write_text('language = "en"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        candidate.apply(tmp_path / "backup.zip")
    assert not (tmp_path / "backup.zip").exists()


def test_coqui_plan_applies_pronunciation_and_reports_unsupported_direction() -> None:
    profile = AudioProfile(engine="coqui", language="de", voice="thorsten", pronunciations={"Lixity": "Liksiti"})
    plan = build_speech_plan("# Kapitel\n\nLixity ist hier.", profile)
    assert any("Liksiti" in row.text for row in plan)
    assert plan_json(plan)["controls"]["instructions"] == "unsupported"


def test_coqui_refuses_saved_text_direction_without_discarding_it() -> None:
    text = "# Kapitel\n\nEin Satz."
    profile = AudioProfile(engine="coqui", language="de", voice="thorsten")
    anchor = speech_passages(text, "de")[-1]["anchor"]
    direction = Direction(anchor=anchor, instructions="Flüstern")
    with pytest.raises(CoquiDirectionConflict, match="Coqui"):
        build_speech_plan(text, profile, directions=[direction])


def test_coqui_cache_keys_do_not_collide_with_qwen_or_other_references(tmp_path) -> None:
    cache = SpeechSegmentCache(tmp_path)
    qwen = AudioProfile(language="de")
    preset = AudioProfile(engine="coqui", language="de", voice="thorsten")
    ref_a = AudioProfile(engine="coqui-reference", language="de", voice="reference", reference_id="a" * 64)
    ref_b = AudioProfile(engine="coqui-reference", language="de", voice="reference", reference_id="b" * 64)
    keys = {cache._paths("Hallo", p)[0] for p in (qwen, preset, ref_a, ref_b)}
    assert len(keys) == 4


def test_coqui_worker_accepts_valid_requests_and_identifies_model() -> None:
    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_silence_wav(.01), port=0, model=COQUI_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"model": COQUI_MODEL, "input": "Hallo", "voice": "thorsten", "language": "de", "instructions": "", "response_format": "wav"}).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/audio/speech", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:  # noqa: S310 - local test worker
            assert response.headers["X-Lixity-Model"] == COQUI_MODEL
            assert response.read().startswith(b"RIFF")
        assert calls[0]["input"] == "Hallo"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_reference_plan_sends_verified_reference_through_worker(tmp_path, monkeypatch) -> None:
    import lixity.speech_qwen as transport

    reference = save_reference(tmp_path, generate_silence_wav(2), "Synthetic reference transcript")
    profile = AudioProfile(engine="coqui-reference", language="de", voice="reference", speed=1.0,
                           reference_id=reference.id, pronunciations={"Lixity": "Liksiti"})
    calls = []
    server = worker_server(lambda request: calls.append(request) or generate_silence_wav(.1),
                           port=0, model=COQUI_REFERENCE_MODEL)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setitem(transport.TARGET_ENDPOINTS, "local", f"http://127.0.0.1:{server.server_port}/v1/audio/speech")
        source = tmp_path / "source.md"
        source.write_text("Lixity ist hier.", encoding="utf-8")
        output = tmp_path / "output.wav"
        progress = []
        render_speech_audio(source, output, profile=profile, references={reference.id: reference},
                            progress=lambda done, total: progress.append((done, total)))
        assert output.read_bytes().startswith(b"RIFF")
        assert "Liksiti" in calls[0]["input"]
        assert calls[0]["reference_text"] == reference.transcript
        assert progress[0] == (0, 1) and progress[-1] == (1, 1)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
