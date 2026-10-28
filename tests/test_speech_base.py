"""Reference voices must not pretend to support Qwen Base delivery instructions."""

import pytest

from lixity.speech import generate_silence_wav
from lixity.speech_profiles import AudioProfile, audio_capabilities


def test_base_profile_requires_reference_and_advertises_actual_controls():
    reference_id = "a" * 64
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference_id,
                           language="de", instructions="", speed=1.2)
    assert profile.reference_id == reference_id
    assert profile.model_dump()["reference_id"] == reference_id
    capability = audio_capabilities()["qwen3-base"]
    assert capability["instructions"] is False
    assert capability["control_support"]["direction"] == "unsupported"
    assert capability["reference_required"] is True


@pytest.mark.parametrize("updates", [
    {"reference_id": ""}, {"reference_id": "../escape"}, {"voice": "Ryan"},
    {"instructions": "Whisper"}, {"voice_description": "A German voice"},
])
def test_base_profile_rejects_missing_reference_and_unsupported_controls(updates):
    data = {"engine": "qwen3-base", "voice": "reference", "reference_id": "a" * 64}
    with pytest.raises(ValueError):
        AudioProfile.model_validate({**data, **updates})


def test_non_base_profile_rejects_reference_and_does_not_change_existing_dump():
    assert "reference_id" not in AudioProfile().model_dump()
    with pytest.raises(ValueError):
        AudioProfile(reference_id="a" * 64)


def test_base_plan_only_allows_explicit_empty_direction_and_reports_limits(tmp_path):
    from lixity.speech_direction import Direction, build_speech_plan, plan_json, speech_passages
    from lixity.speech_references import save_reference

    text = "## Scene\n\nA short passage.\n"
    reference = save_reference(tmp_path, generate_silence_wav(1), "Exact transcript.")
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference.id)
    passage = speech_passages(text, "en")[0]
    allowed = Direction(anchor=passage["anchor"], instructions="", pause_after=0.2)
    plan = build_speech_plan(text, profile, directions=[allowed])
    assert plan_json(plan)["controls"]["instructions"] == "unsupported"
    assert any(row.pause_after == 0.2 for row in plan)
    with pytest.raises(ValueError, match="instructions"):
        build_speech_plan(text, profile, directions=[allowed.model_copy(update={"instructions": "Whisper."})])


def test_base_voice_changes_only_for_explicitly_assigned_ranges(tmp_path):
    from lixity.speech_direction import Direction, build_speech_plan, speech_passages
    from lixity.speech_references import save_reference

    text = "## Scene\n\nNarrator. Dialogue. Narrator.\n"
    first = save_reference(tmp_path, generate_silence_wav(1), "First reference.")
    second = save_reference(tmp_path, generate_silence_wav(1.1), "Second reference.")
    narrator = AudioProfile(engine="qwen3-base", voice="reference", reference_id=first.id)
    character = AudioProfile(engine="qwen3-base", voice="reference", reference_id=second.id)
    passage = speech_passages(text, "en")[0]
    start = passage["text"].index("Dialogue.")
    direction = Direction(anchor=passage["anchor"], start=start, end=start + len("Dialogue."), profile_id="character")
    plan = build_speech_plan(text, narrator, directions=[direction], profiles={"character": character})
    spoken = [(row.text.strip(), row.profile.reference_id) for row in plan if row.anchor and row.text.strip()]
    assert spoken == [("Narrator.", first.id), ("Dialogue.", second.id), ("Narrator.", first.id)]


def test_base_adapter_transports_only_verified_matching_reference(tmp_path):
    import base64
    import io
    import json
    from dataclasses import replace
    from email.message import Message
    from types import SimpleNamespace

    from lixity.speech_qwen import synthesize_qwen
    from lixity.speech_references import save_reference

    reference = save_reference(tmp_path, generate_silence_wav(1), "Exact transcript.")
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference.id)
    headers = Message()
    headers["Content-Type"] = "audio/wav"
    headers["X-Lixity-Model"] = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
    headers["X-Lixity-Voice"] = "reference"
    requests = []
    def open_request(request, timeout):
        requests.append(json.loads(request.data))
        response = io.BytesIO(generate_silence_wav(.2))
        response.status = 200
        response.headers = headers
        return response
    opener = SimpleNamespace(open=open_request)
    synthesize_qwen("Hello.", profile, reference=reference, opener=opener)
    assert base64.b64decode(requests[0]["reference_audio"]) == reference.audio
    assert requests[0]["reference_text"] == reference.transcript
    assert requests[0]["instructions"] == ""
    with pytest.raises(ValueError, match="reference"):
        synthesize_qwen("Hello.", profile, opener=opener)
    with pytest.raises(ValueError, match="reference"):
        synthesize_qwen("Hello.", profile,
                        reference=replace(reference, transcript="Different transcript."), opener=opener)
    assert len(requests) == 1


def test_base_render_requires_snapshot_before_synthesis_and_preserves_output(tmp_path, monkeypatch):
    from lixity.speech import render_speech_audio
    from lixity.speech_references import save_reference

    reference = save_reference(tmp_path, generate_silence_wav(1), "Exact transcript.")
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference.id)
    source, output = tmp_path / "manuscript.md", tmp_path / "out.wav"
    source.write_text("A synthetic passage.")
    output.write_bytes(b"old")
    calls = []
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen",
                        lambda text, selected, **kwargs: calls.append(kwargs["reference"]) or generate_silence_wav(.2))
    with pytest.raises(ValueError, match="reference"):
        render_speech_audio(source, output, profile=profile)
    assert not calls and output.read_bytes() == b"old"
    render_speech_audio(source, output, profile=profile, references={reference.id: reference})
    assert calls == [reference] and output.read_bytes().startswith(b"RIFF")


def test_reference_cli_creation_is_explicit_and_outputs_no_private_content(tmp_path, capsys):
    import json

    from lixity.cli import main
    from lixity.speech_references import load_reference

    audio = tmp_path / "voice.wav"
    transcript = tmp_path / "voice.txt"
    audio.write_bytes(generate_silence_wav(1))
    transcript.write_text("Private synthetic transcript.", encoding="utf-8")
    assert main(["audio-reference", "create", "--project", str(tmp_path),
                 "--audio", str(audio), "--transcript-file", str(transcript)]) == 0
    output = capsys.readouterr().out
    data = json.loads(output)
    assert data["schema_version"] == "lixity-audio-reference-created/1"
    assert "Private synthetic transcript" not in output
    assert load_reference(tmp_path, data["id"]).transcript == "Private synthetic transcript."


def test_base_cli_plan_binds_reference_without_embedding_private_audio(tmp_path, capsys):
    import json

    from lixity.cli import main
    from lixity.speech_references import save_reference

    (tmp_path / "manuscript.md").write_text("## Scene\n\nA synthetic passage.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n')
    reference = save_reference(tmp_path, generate_silence_wav(1), "Private synthetic reference.")
    assert main(["read-aloud", "--project", str(tmp_path), "--engine", "qwen3-base",
                 "--reference-id", reference.id, "--plan-only"]) == 0
    output = capsys.readouterr().out
    result = json.loads(output)
    assert result["controls"]["instructions"] == "unsupported"
    assert result["segments"][-1]["profile"]["reference_id"] == reference.id
    assert "Private synthetic reference" not in output
    assert "reference_audio" not in output


def test_base_cli_rejects_changed_reference_before_publishing(tmp_path, capsys, monkeypatch):
    from lixity.cli import main
    from lixity.speech_references import save_reference

    (tmp_path / "manuscript.md").write_text("## Scene\n\nA synthetic passage.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n')
    reference = save_reference(tmp_path, generate_silence_wav(1), "Exact transcript.")
    target = tmp_path / "result.wav"
    target.write_bytes(b"previous output")
    def synthesize(_text, _profile, **kwargs):
        assert kwargs["reference"] == reference
        path = tmp_path / ".lixity" / "audio-references" / f"{reference.id}.json"
        path.write_text("changed")
        return generate_silence_wav(.2)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen", synthesize)
    assert main(["read-aloud", "--project", str(tmp_path), "--engine", "qwen3-base",
                 "--reference-id", reference.id, "--speed", "1.0", "--no-audio-cache",
                 "--output", str(target)]) != 0
    assert target.read_bytes() == b"previous output"
    assert "changed" in capsys.readouterr().err


def test_background_job_receives_immutable_reference_snapshot(tmp_path):
    import time

    from lixity.speech_jobs import SpeechJobs
    from lixity.speech_references import save_reference

    reference = save_reference(tmp_path, generate_silence_wav(1), "Exact transcript.")
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference.id)
    received = []
    def render(_source, output, **kwargs):
        received.append(kwargs["references"][reference.id])
        output.write_bytes(generate_silence_wav(.2))
    jobs = SpeechJobs(renderer=render)
    try:
        job = jobs.start("key", "Synthetic text.", profile, {}, lambda: True,
                         references={reference.id: reference})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and jobs.status(job["id"], "key")["state"] not in ("ready", "error"):
            time.sleep(.01)
        assert jobs.status(job["id"], "key")["state"] == "ready"
        assert received == [reference]
    finally:
        jobs.close()
