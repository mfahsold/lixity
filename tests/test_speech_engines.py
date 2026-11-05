"""Native routes and model identities share one explicit registry."""
import pytest


def test_native_routes_distinguish_independent_workers():
    from lixity.speech_engines import engine_for_model, native_endpoint, native_engine

    assert native_endpoint("qwen3-base", "jetson") == "http://127.0.0.1:8770/v1/audio/speech"
    assert native_endpoint("f5-tts") == "http://127.0.0.1:8771/v1/audio/speech"
    assert native_endpoint("ims-toucan") == "http://127.0.0.1:8772/v1/audio/speech"
    for engine in ("qwen3-base", "f5-tts", "ims-toucan"):
        assert native_engine(engine).reference_required
        assert engine_for_model(native_engine(engine).model) == engine
    assert not native_engine("qwen3").reference_required
    with pytest.raises(ValueError, match="target"):
        native_endpoint("ims-toucan", "jetson")
    with pytest.raises(ValueError, match="engine"):
        native_engine("unknown")
    with pytest.raises(ValueError, match="model"):
        engine_for_model("unknown")


def test_f5_cache_binds_both_model_and_reference(tmp_path):
    from lixity.speech import generate_silence_wav
    from lixity.speech_cache import SpeechSegmentCache
    from lixity.speech_profiles import AudioProfile

    first = AudioProfile(engine="f5-tts", voice="reference", language="de", reference_id="a" * 64)
    second = AudioProfile(engine="f5-tts", voice="reference", language="de", reference_id="b" * 64)
    qwen = AudioProfile(engine="qwen3-base", voice="reference", language="de", reference_id="a" * 64)
    cache = SpeechSegmentCache(tmp_path / "segments")
    audio = generate_silence_wav(.01, 24000)
    cache.put("Synthetic sentence.", first, audio)
    assert cache.get("Synthetic sentence.", first) == audio
    assert cache.get("Synthetic sentence.", second) is None
    assert cache.get("Synthetic sentence.", qwen) is None


def test_f5_status_probes_its_own_worker(monkeypatch):
    from lixity.speech_engines import F5_MODEL
    from lixity.speech_status import audio_status

    calls = []

    def probe(target, *, engine="qwen3"):
        calls.append((engine, target))
        return {"target": target, "state": "ready", "model": F5_MODEL}

    monkeypatch.setattr("lixity.speech_status.worker_health", probe)
    status = audio_status(engine="f5-tts")
    assert calls == [("f5-tts", "local")]
    assert status["targets"][0]["model_matches"] is True


def test_worker_inventory_probes_each_socket_once(monkeypatch):
    from lixity.speech_engines import native_endpoint
    from lixity.speech_status import native_worker_inventory

    calls = []

    def probe(target, *, engine="qwen3"):
        calls.append(native_endpoint(engine, target))
        return {"target": target, "state": "unavailable", "model": None}

    monkeypatch.setattr("lixity.speech_status.worker_health", probe)
    rows = native_worker_inventory()
    assert len(calls) == len(set(calls)) == 4
    assert next(row for row in rows if "ims-toucan" in row["engines"])["target"] == "local"
    assert next(row for row in rows if "f5-tts" in row["engines"])["engines"] == ["f5-tts"]
    assert [row["service_name"] for row in rows if row["target"] == "local"] == [
        "Qwen3-TTS / Coqui", "F5-TTS", "IMS-Toucan",
    ]


def test_toucan_cache_tracks_phonetic_and_prosody_changes(tmp_path):
    from lixity.speech import generate_silence_wav
    from lixity.speech_cache import SpeechSegmentCache
    from lixity.speech_profiles import AudioProfile

    profile = AudioProfile(engine="ims-toucan", voice="reference", language="de", reference_id="a" * 64)
    cache = SpeechSegmentCache(tmp_path / "segments")
    audio = generate_silence_wav(.01, 24000)
    cache.put("Hallo Welt.", profile, audio)
    for change in ({"phonemes": {"Hallo": "halo\u02d0"}}, {"prosody": {"duration_scaling_factor": 1.3}}):
        changed = AudioProfile.model_validate({**profile.model_dump(), **change})
        assert cache.get("Hallo Welt.", changed) is None


def test_cli_selects_toucan_without_changing_project(tmp_path, capsys):
    import json

    from lixity.cli import main
    from lixity.speech import generate_silence_wav
    from lixity.speech_references import save_reference

    (tmp_path / "draft.md").write_text("Ein synthetischer Satz.")
    config = tmp_path / "lixity.toml"
    original = 'manuscript = "draft.md"\nlanguage = "de"\n'
    config.write_text(original)
    reference = save_reference(tmp_path, generate_silence_wav(1), "Synthetic reference.")
    assert main(["read-aloud", "--project", str(tmp_path), "--engine", "ims-toucan",
                 "--reference-id", reference.id, "--plan-only"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["segments"][0]["profile"]["engine"] == "ims-toucan"
    assert plan["segments"][0]["profile"]["reference_id"] == reference.id
    assert config.read_text() == original


def test_cli_schema5_upgrade_requires_review_and_keeps_voice(tmp_path, capsys):
    import json

    from lixity.cli import main
    from lixity.config import read_explicit_project_config

    (tmp_path / "draft.md").write_text("Synthetic prose.")
    config = tmp_path / "lixity.toml"
    config.write_text('manuscript="draft.md"\nlanguage="de"\n[audio]\nselected="narrator"\n'
                      '[audio.profiles.narrator]\nengine="qwen3"\nvoice="Ryan"\n')
    original = config.read_bytes()
    args = ["audio-migrate", "--project", str(tmp_path), "--to-schema-5"]
    assert main(args) == 0
    preview = json.loads(capsys.readouterr().out)
    assert config.read_bytes() == original
    assert preview["applied"] is False
    backup = tmp_path.parent / (tmp_path.name + "-before.zip")
    assert main([*args, "--apply", "--expected-snapshot", preview["snapshot"], "--backup", str(backup)]) == 0
    assert backup.is_file()
    audio = read_explicit_project_config(tmp_path)["audio"]
    assert audio["schema_version"] == "lixity-audio-settings/5"
    assert audio["profiles"]["narrator"]["engine"] == "qwen3"
    assert audio["profiles"]["narrator"]["voice"] == "Ryan"
