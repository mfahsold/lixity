"""Completed synthetic segments survive failures without publishing partial audio."""
from __future__ import annotations

import hashlib
import json
import shutil
from types import SimpleNamespace

import pytest

from lixity.speech import SpeechCancelled, generate_silence_wav, render_speech_audio
from lixity.speech_profiles import AudioProfile


def narrator(**changes):
    return AudioProfile(**{"engine": "qwen3", "voice": "Ryan", "language": "en", **changes})


def _prepared_cache_parts():
    from lixity.speech_probe import build_voice_probe_script
    from lixity.speech_references import prepare_reference

    text = " ".join(
        f"Synthetic sentence number {index} describes a calm private test passage."
        for index in range(100)
    )
    script = build_voice_probe_script(text, language="de", target_seconds=125)
    assert script.status == "ready"
    return [
        prepare_reference(generate_silence_wav(150 / len(script.parts)), f"Private fallback transcript {index}.")
        for index in range(1, len(script.parts) + 1)
    ]


def _save_reference_set(tmp_path, parts, *, fallback_part_index=1):
    from lixity.speech_probe import build_voice_probe_script
    from lixity.speech_references import save_reference_set

    text = " ".join(
        f"Synthetic sentence number {index} describes a calm private test passage."
        for index in range(100)
    )
    script = build_voice_probe_script(text, language="de", target_seconds=125)
    assert script.status == "ready" and len(script.parts) == len(parts)
    probe = script.to_dict()
    return save_reference_set(
        tmp_path, parts, source_sha256=script.source_sha256, settings_sha256=script.settings_sha256,
        probe_sha256=script.probe_sha256, language="de", terms=("Mara",),
        fallback_part_index=fallback_part_index, probe=probe,
    )


def test_failed_render_reuses_only_completed_exact_requests(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("First sentence.\n\nSecond sentence.")
    target = tmp_path / "reading.wav"
    target.write_bytes(b"previous complete file")
    cache = tmp_path / "segments"
    calls = []

    def synthesize(text, profile, **_kwargs):
        calls.append((text, profile.instructions))
        if len(calls) == 2:
            raise RuntimeError("Synthetic interruption")
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    with pytest.raises(RuntimeError, match="Synthetic interruption"):
        render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    assert target.read_bytes() == b"previous complete file"
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    assert [text for text, _ in calls] == ["First sentence.", "Second sentence.", "Second sentence."]
    assert target.read_bytes().startswith(b"RIFF")
    render_speech_audio(source, target, profile=narrator(instructions="Read softly."), cache_dir=cache)
    assert len(calls) == 5
    source.write_text("Changed sentence.\n\nSecond sentence.")
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    assert len(calls) == 6 and calls[-1][0] == "Changed sentence."
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache, fresh_audio=True)
    assert len(calls) == 8


def test_cancelled_render_retains_completed_work_but_not_partial_output(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("First sentence.\n\nSecond sentence.")
    target, cache = tmp_path / "out.wav", tmp_path / "segments"
    cancelled = [False]
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))

    def progress(done, total):
        if done == 1:
            cancelled[0] = True

    with pytest.raises(SpeechCancelled):
        render_speech_audio(source, target, profile=narrator(), cache_dir=cache,
                            progress=progress, cancelled=lambda: cancelled[0])
    assert not target.exists()
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    assert calls == ["First sentence.", "Second sentence."]


def test_corrupted_segment_is_recomputed_and_symlink_cache_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("One sentence.")
    target, cache = tmp_path / "out.wav", tmp_path / "segments"
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    next(cache.glob("*.wav")).write_bytes(b"damaged")
    render_speech_audio(source, target, profile=narrator(), cache_dir=cache)
    assert len(calls) == 2
    link = tmp_path / "link"
    link.symlink_to(cache, target_is_directory=True)
    with pytest.raises(ValueError, match=r"symlink|Symlink"):
        render_speech_audio(source, target, profile=narrator(), cache_dir=link)
    assert len(calls) == 2


def test_cache_is_bounded_and_retains_no_raw_prose_in_metadata(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache
    cache = SpeechSegmentCache(tmp_path / "segments", max_bytes=1000)
    audio = generate_silence_wav(.01, 24000)
    cache.put("Private synthetic phrase one.", narrator(), audio)
    cache.put("Private synthetic phrase two.", narrator(), audio)
    assert cache.get("Private synthetic phrase one.", narrator()) is None
    assert cache.get("Private synthetic phrase two.", narrator()) == audio
    assert all("Private synthetic" not in p.read_text() for p in cache.directory.glob("*.json"))
    assert cache.get("Private synthetic phrase two.", narrator(voice="Aiden")) is None


def test_toucan_adapter_identity_separates_old_sentence_chunks(tmp_path):
    import hashlib
    import json

    from lixity.speech_cache import SpeechSegmentCache
    from lixity.speech_engines import TOUCAN_MODEL

    profile = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id="a" * 64)
    audio = generate_silence_wav(.01, 24000)
    text = "Synthetischer Absatz mit mehreren Sätzen."
    request = {"schema_version": "lixity-speech-segment/1", "model": TOUCAN_MODEL,
               "text": text, "language": "de", "voice": "reference", "instructions": "",
               "adapter": "lixity-toucan/2", "phonemes": {}, "prosody": {},
               "reference_id": "a" * 64}
    expected = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    cache = SpeechSegmentCache(tmp_path / "segments")
    key, wav, _metadata = cache._paths(text, profile)
    assert key == expected
    cache.put(text, profile, audio)
    assert wav.name == expected + ".wav"
    assert cache.get(text, profile) == audio


def test_toucan_cache_identity_uses_only_phonemes_matching_the_segment(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache

    cache = SpeechSegmentCache(tmp_path / "segments")
    first = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id="a" * 64,
                         phonemes={"Name": "na\u02d0mə"})
    unrelated = AudioProfile(engine="ims-toucan", language="de", voice="reference", reference_id="a" * 64,
                             phonemes={"Name": "na\u02d0mə", "Unused": "ʊn"})
    assert cache._paths("Name.", first)[0] == cache._paths("Name.", unrelated)[0]
    assert cache._paths("Unused.", first)[0] != cache._paths("Unused.", unrelated)[0]


def test_base_cache_separates_reference_and_model_but_not_playback_speed(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache

    cache = SpeechSegmentCache(tmp_path / "segments")
    first_id, second_id = "a" * 64, "b" * 64
    def base(reference_id, *, speed=1.0):
        return AudioProfile(engine="qwen3-base", voice="reference", language="de",
                            reference_id=reference_id, speed=speed)

    audio = generate_silence_wav(.01, 24000)
    text = "Synthetic reference cache text."
    cache.put(text, base(first_id), audio)
    assert cache.get(text, base(first_id, speed=1.8)) == audio
    assert cache.get(text, base(second_id)) is None
    custom = SimpleNamespace(engine="qwen3", voice="reference", language="de", instructions="")
    assert cache.get(text, custom) is None
    metadata = next(cache.directory.glob("*.json")).read_text()
    assert text not in metadata and first_id not in metadata


def test_reference_set_cache_identity_includes_order_and_explicit_policy(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache
    from lixity.speech_engines import (
        QWEN_BASE_MODEL,
        REFERENCE_SET_AGGREGATION,
        REFERENCE_SET_AGGREGATION_VERSION,
        REFERENCE_SET_FALLBACK,
        TOUCAN_MODEL,
    )
    from lixity.speech_profiles import MLX_AUDIO_BASE_URL, MLX_AUDIO_TTS_MODEL
    from lixity.speech_providers import speech_endpoint

    parts = _prepared_cache_parts()
    reference = _save_reference_set(tmp_path, parts, fallback_part_index=2)
    reordered = _save_reference_set(tmp_path, list(reversed(parts)), fallback_part_index=2)
    other_fallback = _save_reference_set(tmp_path, parts, fallback_part_index=1)
    cache = SpeechSegmentCache(tmp_path / "segments")
    text = "Synthetic reference cache text."
    audio = generate_silence_wav(.01, 24000)

    profiles = {
        "qwen3-base": AudioProfile(engine="qwen3-base", language="de", voice="reference",
                                  reference_id=reference.id),
        "mlx-audio": AudioProfile(engine="mlx-audio", language="de", voice="reference",
                                 reference_id=reference.id),
        "ims-toucan": AudioProfile(engine="ims-toucan", language="de", voice="reference",
                                  reference_id=reference.id),
    }
    keys = {}
    for engine, selected in profiles.items():
        key = cache._paths(text, selected, reference)[0]
        keys[engine] = key
        single = selected.model_copy(update={"reference_id": parts[0].id})
        assert cache._paths(text, single, parts[0])[0] == cache._paths(text, single)[0]
        assert key != cache._paths(text, single, parts[0])[0]
        assert key != cache._paths(text, selected.model_copy(update={"reference_id": reordered.id}), reordered)[0]
        assert key != cache._paths(text, selected.model_copy(update={"reference_id": other_fallback.id}), other_fallback)[0]

    base_request = {
        "schema_version": "lixity-speech-segment/1", "model": QWEN_BASE_MODEL,
        "text": text, "language": "de", "voice": "reference", "instructions": "",
        "reference_id": reference.id, "reference_mode": "set",
        "reference_set_fallback": REFERENCE_SET_FALLBACK, "reference_set_fallback_index": 2,
    }
    assert keys["qwen3-base"] == hashlib.sha256(json.dumps(
        base_request, sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()

    zonos_request = {
        "schema_version": "lixity-speech-segment/1", "model": MLX_AUDIO_TTS_MODEL,
        "text": text, "language": "de", "voice": "reference", "instructions": "",
        "endpoint": speech_endpoint(MLX_AUDIO_BASE_URL), "adapter": "lixity-mlx-audio/1",
        "api_key_env": "", "speed": 1.1, "reference_id": reference.id, "reference_mode": "set",
        "reference_set_aggregation": REFERENCE_SET_AGGREGATION,
        "reference_set_aggregation_version": REFERENCE_SET_AGGREGATION_VERSION,
    }
    assert keys["mlx-audio"] == hashlib.sha256(json.dumps(
        zonos_request, sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    assert cache._paths(text, profiles["mlx-audio"], reference_set=True)[0] == keys["mlx-audio"]

    toucan_request = {
        "schema_version": "lixity-speech-segment/1", "model": TOUCAN_MODEL,
        "text": text, "language": "de", "voice": "reference", "instructions": "",
        "adapter": "lixity-toucan/2", "phonemes": {}, "prosody": {},
        "reference_id": reference.id, "reference_mode": "set",
        "reference_set_aggregation": REFERENCE_SET_AGGREGATION,
        "reference_set_aggregation_version": REFERENCE_SET_AGGREGATION_VERSION,
    }
    assert keys["ims-toucan"] == hashlib.sha256(json.dumps(
        toucan_request, sort_keys=True, ensure_ascii=False,
    ).encode()).hexdigest()
    assert cache._paths(text, profiles["ims-toucan"], reference_set=True)[0] == keys["ims-toucan"]

    cache.put(text, profiles["qwen3-base"], audio, reference)
    assert cache.get(text, profiles["qwen3-base"], reference) == audio
    metadata = next(cache.directory.glob("*.json")).read_text()
    assert text not in metadata
    assert all(part.transcript not in metadata for part in parts)
    assert reference.id not in metadata
    assert "embedding" not in metadata


def test_render_passes_resolved_reference_sets_to_segment_cache(tmp_path, monkeypatch):
    parts = _prepared_cache_parts()
    first = _save_reference_set(tmp_path, parts, fallback_part_index=1)
    second = _save_reference_set(tmp_path, parts, fallback_part_index=2)
    source, output = tmp_path / "source.md", tmp_path / "out.wav"
    source.write_text("Synthetic source.")
    calls = []

    def synthesize(_text, _profile, **kwargs):
        calls.append(kwargs["reference"])
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    for reference in (first, first, second, second):
        selected = AudioProfile(engine="qwen3-base", language="de", voice="reference",
                                reference_id=reference.id)
        render_speech_audio(source, output, profile=selected, cache_dir=tmp_path / "cache",
                            references={reference.id: reference})
    assert calls == [first, second]


def test_existing_voice_cache_keys_remain_stable(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache

    cache = SpeechSegmentCache(tmp_path / "segments")
    audio = generate_silence_wav(.01, 24000)
    text = "Cache contract sample."
    design = AudioProfile(engine="qwen3-design", voice="design", language="en",
                          voice_description="A synthetic voice.")
    cache.put(text, narrator(), audio)
    cache.put(text, design, audio)
    assert {p.stem for p in cache.directory.glob("*.json")} == {
        "8b7ec6d77ba432b441af1b9354c84f1a4a1123418de4780f87b4d089efa71dee",
        "8247f46630f3a6f5cf0f870e2f15cd3105d12d288f6024a72b51f207d08a378e",
    }


def test_cli_reuses_project_segments_and_explicit_fresh_flag(tmp_path, monkeypatch):
    from lixity.cli import main
    from lixity.config import prepare_project_settings
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "user-cache"))
    source = tmp_path / "manuscript.md"
    source.write_text("A synthetic listening passage.")
    (tmp_path / "lixity.toml").write_text('language="en"\nmanuscript="manuscript.md"\n')
    prepare_project_settings(tmp_path, {"audio": {"selected": "reader", "profiles": {"reader": narrator().model_dump()}}}).commit()
    config = (tmp_path / "lixity.toml").read_bytes()
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
    args = ["read-aloud", "--project", str(tmp_path), "--profile", "reader", "-o", str(tmp_path / "out.wav")]
    assert main(args) == 0
    assert main(args) == 0 and len(calls) == 1
    assert main([*args, "--fresh-audio"]) == 0 and len(calls) == 2
    assert (tmp_path / "lixity.toml").read_bytes() == config
    assert source.read_text() == "A synthetic listening passage."


def test_read_only_project_with_external_output_and_cache_opt_out(tmp_path, monkeypatch):
    from lixity.cli import main
    from lixity.config import prepare_project_settings
    from lixity.speech_cache import project_audio_cache
    project = tmp_path / "read-only"
    project.mkdir()
    source = project / "manuscript.md"
    source.write_text("A read-only synthetic passage.")
    (project / "lixity.toml").write_text('language="en"\nmanuscript="manuscript.md"\n')
    prepare_project_settings(project, {"audio": {"selected": "reader", "profiles": {"reader": narrator().model_dump()}}}).commit()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
    args = ["read-aloud", "--project", str(project), "-o", str(tmp_path / "outside.wav")]
    project.chmod(0o555)
    try:
        assert main(args) == 0
        assert main(args) == 0 and len(calls) == 1
        assert main([*args, "--no-audio-cache"]) == 0 and len(calls) == 2
        assert project_audio_cache(project).is_dir()
        assert sorted(p.name for p in project.iterdir()) == ["lixity.toml", "manuscript.md"]
    finally:
        project.chmod(0o755)


@pytest.mark.parametrize("target", [None, "local", "jetson"])
def test_cli_dispatches_execution_target_without_saving_it(tmp_path, monkeypatch, target):
    from lixity.cli import main
    from lixity.config import prepare_project_settings

    source = tmp_path / "manuscript.md"
    source.write_text("A synthetic target dispatch passage.")
    config = tmp_path / "lixity.toml"
    config.write_text('language="en"\nmanuscript="manuscript.md"\n')
    prepare_project_settings(tmp_path, {"audio": {
        "selected": "reader", "profiles": {"reader": narrator().model_dump()},
    }}).commit()
    original = config.read_bytes()
    observed = []

    def synthesize(text, profile, **kwargs):
        observed.append((kwargs["target"], profile.model_dump()))
        return generate_silence_wav(.01, 24000)

    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    output = tmp_path / "result.wav"
    args = ["read-aloud", "--project", str(tmp_path), "--no-audio-cache", "-o", str(output)]
    if target is not None:
        args.extend(["--speech-target", target])
    assert main(args) == 0
    assert output.read_bytes().startswith(b"RIFF")
    assert observed == [(target or "local", narrator().model_dump())]
    assert "target" not in observed[0][1]
    assert config.read_bytes() == original
    assert source.read_text() == "A synthetic target dispatch passage."


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="Default playback speed requires FFmpeg")
def test_cli_default_qwen_uses_jetson_without_saving_a_profile(tmp_path, monkeypatch):
    from lixity.cli import main

    source = tmp_path / "manuscript.md"
    source.write_text("A synthetic default narrator passage.")
    (tmp_path / "lixity.toml").write_text('language="en"\nmanuscript="manuscript.md"\n')
    output = tmp_path / "result.wav"
    output.write_bytes(b"retained listening copy")
    calls = []
    def synthesize(text, profile, **kwargs):
        calls.append((text, profile.engine, profile.voice, kwargs["target"]))
        # The implicit profile applies tempo processing, which needs more than
        # a few milliseconds of PCM to produce a valid output segment.
        return generate_silence_wav(.2, 24000)

    original = (tmp_path / "lixity.toml").read_bytes()
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    assert main(["read-aloud", "--project", str(tmp_path), "--speech-target", "jetson",
                 "--no-audio-cache", "-o", str(output)]) == 0
    assert output.read_bytes().startswith(b"RIFF")
    assert calls == [("A synthetic default narrator passage.", "qwen3", "Ryan", "jetson")]
    assert (tmp_path / "lixity.toml").read_bytes() == original


def test_design_cache_separates_model_and_voice_description(tmp_path):
    from lixity.speech_cache import SpeechSegmentCache
    cache = SpeechSegmentCache(tmp_path / 'segments')
    one = AudioProfile(engine='qwen3-design', voice='design', language='de', voice_description='A German voice.')
    two = AudioProfile(engine='qwen3-design', voice='design', language='de', voice_description='Another German voice.')
    data = generate_silence_wav(.01, 24000)
    cache.put('Ein kurzer Satz.', one, data)
    assert cache.get('Ein kurzer Satz.', one) == data
    assert cache.get('Ein kurzer Satz.', two) is None
