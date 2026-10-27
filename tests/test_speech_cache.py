"""Completed synthetic segments survive failures without publishing partial audio."""
from __future__ import annotations

import pytest

from lixity.speech import SpeechCancelled, generate_silence_wav, render_speech_audio
from lixity.speech_profiles import AudioProfile


def narrator(**changes):
    return AudioProfile(**{"engine": "qwen3", "voice": "Ryan", "language": "en", **changes})


def test_failed_render_reuses_only_completed_exact_requests(tmp_path, monkeypatch):
    source = tmp_path / "source.md"
    source.write_text("First sentence.\n\nSecond sentence.")
    target = tmp_path / "reading.wav"
    target.write_bytes(b"previous complete file")
    cache = tmp_path / "segments"
    calls = []

    def synthesize(text, profile):
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
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _: calls.append(text) or generate_silence_wav(.01, 24000))

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
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _: calls.append(text) or generate_silence_wav(.01, 24000))
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
    assert sum(p.stat().st_size for p in cache.directory.iterdir()) <= 1000
    assert cache.get("Private synthetic phrase one.", narrator()) is None
    assert cache.get("Private synthetic phrase two.", narrator()) == audio
    assert all("Private synthetic" not in p.read_text() for p in cache.directory.glob("*.json"))
    assert cache.get("Private synthetic phrase two.", narrator(voice="Aiden")) is None


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
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _: calls.append(text) or generate_silence_wav(.01, 24000))
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
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", lambda text, _: calls.append(text) or generate_silence_wav(.01, 24000))
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
