"""Native audio uses selected-source snapshots, not browser-provided prose."""

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest

from lixity.server.pdf_context import project_settings_token
from lixity.speech import generate_silence_wav
from tests.support import LoopbackServer, make_handler, send


@pytest.fixture
def speech_server(tmp_path, monkeypatch):
    import lixity.speech_jobs as jobs

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "user-cache"))
    monkeypatch.setattr("lixity.speech_status.worker_health", lambda target: {
        "target": target, "state": "unavailable", "transport": "loopback" if target == "local" else "ssh",
        "model": None,
    })
    source = tmp_path / "manuscript.md"
    source.write_text(
        "## First\n\nA bird crosses the garden.\n\n## Second\n\nThe second scene begins.\n"
    )
    (tmp_path / "lixity.toml").write_text('language = "en"\n')
    observed = []

    def render(source, output, **kw):
        observed.append(Path(source).read_text())
        kw["progress"](1, 1)
        Path(output).write_bytes(generate_silence_wav(0.01))
        return Path(output)

    monkeypatch.setattr(jobs, "render_speech_audio", render)
    handler = make_handler(tmp_path, source_input=source, language="en")
    handler.refresh()
    with LoopbackServer(handler) as server:
        yield server.port, source, handler, observed


def context(source, handler):
    return {
        "project_token": project_settings_token(handler.workspace_root, str(source)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


@pytest.mark.parametrize("language", ["en", "de"])
def test_base_direction_conflict_explains_opt_in_without_silencing_direction(speech_server, language, capsys):
    from lixity.cli import main
    from lixity.speech_direction import direction_state, save_direction
    from lixity.speech_profiles import AudioProfile
    from lixity.speech_references import save_reference

    port, source, handler, _observed = speech_server
    handler.language = language
    reference = save_reference(source.parent, generate_silence_wav(1), "Synthetic reference.")
    view = direction_state(source.parent, source, language=language)
    entry = {"anchor": view["passages"][0]["anchor"], "instructions": "Read quietly."}
    save_direction(source.parent, source, entry, expected_source_sha256=view["source_sha256"],
                   expected_settings_sha256=view["settings_sha256"],
                   expected_direction_sha256=view["direction_sha256"], language=language)
    profile = AudioProfile(engine="qwen3-base", voice="reference", reference_id=reference.id, language=language)
    payload = {**context(source, handler), "mode": "chapter", "chapter": 1, "profile": profile.model_dump()}

    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 400
    message = json.loads(response.body)["message"]
    assert "Qwen Base" in message and "validation error" not in message
    assert ("Passagenregie" if language == "de" else "passage direction") in message
    assert ("Stimmzuordnungen" if language == "de" else "voice assignments") in message
    assert ("Pausen" if language == "de" else "pauses") in message
    # A deliberate choice ignores all passage controls, while leaving saved direction intact.
    response = send(port, "/api/speech-plan", payload={**payload, "ignore_direction": True})
    assert response.status == 200
    assert len(direction_state(source.parent, source, language=language)["directions"]) == 1

    args = ["read-aloud", "--project", str(source.parent), "--chapter", "1", "--plan-only",
            "--engine", "qwen3-base", "--voice", "reference", "--reference-id", reference.id,
            "--instructions", "", "--language", language]
    assert main(args) != 0
    cli_error = capsys.readouterr().err
    assert "--no-direction" in cli_error
    assert "voice assignments" in cli_error and "pauses" in cli_error
    assert "validation error" not in cli_error
    assert main([*args, "--no-direction"]) == 0


@pytest.mark.parametrize("saved", [False, True], ids=["draft", "saved"])
def test_first_paragraph_preview_keeps_all_directed_segments(speech_server, saved, capsys):
    from lixity.cli import main
    from lixity.speech_direction import direction_state, save_direction

    port, source, handler, _observed = speech_server
    view = direction_state(source.parent, source, language="en")
    entry = {"anchor": view["passages"][0]["anchor"], "start": 0, "end": 6, "instructions": "Calm."}
    if saved:
        save_direction(source.parent, source, entry, expected_source_sha256=view["source_sha256"],
                       expected_settings_sha256=view["settings_sha256"],
                       expected_direction_sha256=view["direction_sha256"], language="en")
    payload = {**context(source, handler), "mode": "preview", "chapter": 1}
    if not saved:
        payload["draft_direction"] = entry
    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    segments = result["plan"]["segments"]
    assert [row["text"] for row in segments] == ["A bird", "crosses the garden."]
    assert [row["profile"]["instructions"] for row in segments] == ["Calm.", ""]
    assert result["context"]["excerpt"] == "A bird crosses the garden."
    assert result["context"]["truncated"] is False
    if saved:
        assert main(["read-aloud", "--project", str(source.parent), "--chapter", "1", "--preview", "--plan-only"]) == 0
        cli = json.loads(capsys.readouterr().out)
        assert cli["segments"] == segments


def test_first_paragraph_preview_does_not_report_truncation_for_complete_split_paragraph(speech_server):
    port, source, handler, _observed = speech_server
    paragraph = "A quiet bird flies. " * 45
    source.write_text("## First\n\n" + paragraph.strip() + "\n", encoding="utf-8")
    payload = {**context(source, handler), "mode": "preview", "chapter": 1}
    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    segments = result["plan"]["segments"]
    assert len(segments) > 1
    assert " ".join(row["text"] for row in segments) == paragraph.strip()
    assert result["context"]["truncated"] is False
    assert len(result["context"]["excerpt"]) <= 601
    assert result["context"]["excerpt"].endswith("…")


def test_first_paragraph_preview_context_matches_selected_paragraph_after_quote(speech_server):
    port, source, handler, _observed = speech_server
    source.write_text("## First\n\n> A quoted opening.\n\nA bird crosses the garden.\n", encoding="utf-8")
    payload = {**context(source, handler), "mode": "preview", "chapter": 1}
    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    assert [row["text"] for row in result["plan"]["segments"]] == ["A bird crosses the garden."]
    assert result["context"]["excerpt"] == "A bird crosses the garden."
    assert result["context"]["truncated"] is False


def test_preview_without_anchored_paragraph_does_not_read_chapter_heading(speech_server, capsys):
    from lixity.cli import main

    port, source, handler, _observed = speech_server
    source.write_text("## First\n\n> A quoted opening.\n", encoding="utf-8")
    response = send(port, "/api/speech-plan", payload={**context(source, handler), "mode": "preview", "chapter": 1})
    assert response.status == 400
    assert "No anchored paragraph" in json.loads(response.body)["message"]
    assert main(["read-aloud", "--project", str(source.parent), "--chapter", "1", "--preview", "--plan-only"]) != 0
    assert "No anchored paragraph" in capsys.readouterr().err


@pytest.mark.parametrize("explicit_paragraph", [False, True])
def test_first_paragraph_preview_rejects_over_limit_for_both_entry_points(speech_server, explicit_paragraph):
    from lixity.speech_direction import speech_passages

    port, source, handler, _observed = speech_server
    source.write_text("## First\n\n" + "A quiet bird flies. " * 350 + "\n", encoding="utf-8")
    payload = {**context(source, handler), "mode": "preview", "chapter": 1}
    if explicit_paragraph:
        payload["paragraph"] = speech_passages(source.read_text(), "en")[0]["anchor"]
    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 400
    assert "exceeds 6000 characters" in json.loads(response.body)["message"]


def test_speech_fixture_does_not_probe_external_workers(speech_server, monkeypatch):
    port, source, handler, _observed = speech_server

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Synthetic speech fixture contacted a worker")

    monkeypatch.setattr("lixity.speech_qwen.urllib.request.build_opener", forbidden)
    response = send(port, "/api/speech?" + urlencode(context(source, handler)))
    assert response.status == 200
    assert [worker["state"] for worker in json.loads(response.body)["workers"]] == ["unavailable", "unavailable"]


def test_speech_view_exposes_actual_workers_without_sensitive_details(speech_server, monkeypatch):
    from lixity.speech_profiles import QWEN_BASE_MODEL

    port, source, handler, _observed = speech_server
    observed_targets = []

    def health(target):
        observed_targets.append(target)
        return {"target": target, "state": "ready" if target == "local" else "unavailable",
                "transport": "loopback" if target == "local" else "ssh",
                "model": QWEN_BASE_MODEL if target == "local" else None}

    monkeypatch.setattr("lixity.speech_status.worker_health", health)
    response = send(port, "/api/speech?" + urlencode(context(source, handler)))
    assert response.status == 200
    data = json.loads(response.body)
    assert {row["target"] for row in data["workers"]} == {"local", "jetson"}
    local, remote = data["workers"]
    assert local["state"] == "ready" and local["model"] == QWEN_BASE_MODEL
    assert remote["state"] == "unavailable" and remote["model"] is None
    assert all(row["model_matches"] is None for row in data["workers"])
    assert set(observed_targets) == {"local", "jetson"}
    assert "A bird crosses" not in json.dumps(data["workers"])


def test_speech_view_rejects_stale_context_before_probing_workers(speech_server, monkeypatch):
    port, source, handler, _observed = speech_server
    calls = []
    monkeypatch.setattr("lixity.speech_status.worker_health", calls.append)
    bound = context(source, handler)
    bound["source_sha256"] = "stale"
    assert send(port, "/api/speech?" + urlencode(bound)).status == 409
    assert calls == []


@pytest.mark.parametrize("changed_file", ["manuscript.md", "lixity.toml"])
def test_speech_view_rechecks_context_after_probing_workers(speech_server, monkeypatch, changed_file):
    port, source, handler, _observed = speech_server
    bound = context(source, handler)

    def health(target):
        if target == "local":
            changed = source.parent / changed_file
            changed.write_text(changed.read_text() + "\n", encoding="utf-8")
        return {"target": target, "state": "unavailable", "transport": "loopback", "model": None}

    monkeypatch.setattr("lixity.speech_status.worker_health", health)
    assert send(port, "/api/speech?" + urlencode(bound)).status == 409


def test_preview_and_download_are_bound_to_actual_source_without_writes(speech_server):
    port, source, handler, observed = speech_server
    before = source.read_bytes()
    bound = context(source, handler)
    response = send(port, "/api/speech?" + urlencode(bound))
    assert response.status == 200, response.body
    data = json.loads(response.body)
    assert data["settings"]["selected"] == "narrator" and len(data["chapters"]) == 2
    assert set(data["capabilities"]) == {"qwen3", "qwen3-design", "qwen3-base"}
    assert data["requires_migration"] is False
    assert data["capabilities"]["qwen3"]["instructions"] is True
    assert data["settings"]["profiles"]["narrator"]["engine"] == "qwen3"
    request = {
        **bound,
        "mode": "preview",
        "chapter": 1,
        "profile": data["settings"]["profiles"]["narrator"],
    }
    response = send(port, "/api/speech-render", payload=request)
    assert response.status == 202, response.body
    identifier = json.loads(response.body)["job"]["id"]
    query = urlencode({**bound, "id": identifier})
    for _ in range(100):
        response = send(port, "/api/speech-job?" + query)
        if json.loads(response.body)["job"]["state"] == "ready":
            break
        time.sleep(0.01)
    audio = send(port, "/api/speech-audio?" + query)
    assert audio.status == 200 and audio.body.startswith(b"RIFF")
    assert audio.headers["content-type"] == "audio/wav"
    assert observed == ["A bird crosses the garden."]
    assert source.read_bytes() == before
    source.write_text(source.read_text() + "Changed source.\n")
    assert send(port, "/api/speech-audio?" + query).status == 409


def test_global_lexicon_reaches_ui_draft_plan_and_survives_profile_save(speech_server):
    from lixity.config import read_explicit_project_config

    port, source, handler, _observed = speech_server
    config = source.parent / "lixity.toml"
    config.write_text('''language = "en"
[audio]
schema_version = "lixity-audio-settings/2"
selected = "narrator"
pronunciations = { BIRD = "berd" }
pronunciation_matching = { case_sensitive = false, whole_words = true }
[audio.profiles.narrator]
engine = "qwen3"
pronunciations = { garden = "gardn" }
''')
    bound = context(source, handler)
    response = send(port, "/api/speech?" + urlencode(bound))
    assert response.status == 200, response.body
    audio = json.loads(response.body)["settings"]
    assert audio["pronunciations"] == {"BIRD": "berd"}
    profile = audio["profiles"]["narrator"]
    response = send(port, "/api/speech-plan", payload={**bound, "mode": "preview", "chapter": 1,
                                                       "profile": profile})
    assert response.status == 200, response.body
    assert json.loads(response.body)["plan"]["segments"][0]["text"] == "A berd crosses the gardn."
    profile["voice"] = "Vivian"
    response = send(port, "/api/settings", payload={"project_token": bound["project_token"], "audio": audio})
    assert response.status == 200, response.body
    stored = read_explicit_project_config(source.parent)["audio"]
    assert stored["schema_version"] == "lixity-audio-settings/2"
    assert stored["pronunciations"] == {"BIRD": "berd"}
    assert stored["pronunciation_matching"] == {"case_sensitive": False, "whole_words": True}
    assert stored["profiles"]["narrator"]["pronunciations"] == {"garden": "gardn"}


@pytest.mark.parametrize(
    "change",
    [
        {"text": "Browser manuscript"},
        {"path": "../other.md"},
        {"mode": "whole-book"},
        {"chapter": 0},
        {"chapter": True},
    ],
)
def test_arbitrary_or_invalid_render_requests_fail(speech_server, change):
    port, source, handler, observed = speech_server
    response = send(
        port,
        "/api/speech-render",
        payload={**context(source, handler), "mode": "preview", "chapter": 1, **change},
    )
    assert response.status == 400, response.body
    assert observed == []


def test_cross_origin_and_old_context_cannot_access_audio(speech_server):
    port, source, handler, _observed = speech_server
    query = urlencode(context(source, handler))
    assert (
        send(port, "/api/speech?" + query, headers={"Origin": "https://example.invalid"}).status
        == 403
    )
    assert (
        send(port, "/api/speech?" + query.replace("source_sha256=", "source_sha256=wrong")).status
        == 409
    )


def test_observed_source_change_cancels_old_job_even_if_bytes_return(speech_server, monkeypatch):
    import threading

    import lixity.speech_jobs as jobs

    port, source, handler, _observed = speech_server
    original = source.read_bytes()
    release = threading.Event()
    entered = threading.Event()

    def render(source, output, **kwargs):
        entered.set()
        release.wait(3)
        Path(output).write_bytes(generate_silence_wav(0.01))

    monkeypatch.setattr(jobs, "render_speech_audio", render)
    bound = context(source, handler)
    try:
        created = send(
            port, "/api/speech-render", payload={**bound, "mode": "preview", "chapter": 1}
        )
        identifier = json.loads(created.body)["job"]["id"]
        assert entered.wait(1)
        source.write_text(source.read_text() + "Changed.\n")
        cancelled = send(port, "/api/speech-cancel", payload={**bound, "id": identifier})
        assert cancelled.status == 409
        source.write_bytes(original)
        release.set()
        query = urlencode({**bound, "id": identifier})
        for _ in range(100):
            state = json.loads(send(port, "/api/speech-job?" + query).body)["job"]["state"]
            if state not in ("pending", "running"):
                break
            time.sleep(0.01)
        assert state == "cancelled"
        assert send(port, "/api/speech-audio?" + query).status == 400
    finally:
        release.set()


def test_reselecting_same_project_cannot_revive_an_earlier_job(speech_server):
    port, source, handler, _observed = speech_server
    bound = context(source, handler)
    created = send(port, "/api/speech-render", payload={**bound, "mode": "preview", "chapter": 1})
    identifier = json.loads(created.body)["job"]["id"]
    query = urlencode({**bound, "id": identifier})
    for _ in range(100):
        state = json.loads(send(port, "/api/speech-job?" + query).body)["job"]["state"]
        if state == "ready":
            break
        time.sleep(0.01)
    assert send(port, "/api/speech-audio?" + query).status == 200
    handler.publish_dashboard(handler.dashboard_html, handler.dashboard_info)
    handler.publish_dashboard(handler.dashboard_html, handler.dashboard_info)
    assert send(port, "/api/speech-audio?" + query).status == 400


@pytest.mark.parametrize("engine", ["qwen3", "qwen3-design"])
def test_qwen_chapters_reuse_completed_segments_but_previews_stay_fresh(speech_server, monkeypatch, engine):
    import lixity.speech_jobs as jobs
    from lixity.speech import render_speech_audio
    from lixity.speech_cache import project_audio_cache
    from lixity.speech_profiles import AudioProfile

    port, source, handler, _observed = speech_server
    before = source.read_bytes()
    calls = []
    monkeypatch.setattr(jobs, "render_speech_audio", render_speech_audio)
    monkeypatch.setattr("lixity.speech_qwen.synthesize_qwen",
                        lambda text, profile, **_kwargs: calls.append(text) or generate_silence_wav(.01, 24000))
    bound = context(source, handler)
    profile_data = {"engine": engine, "language": "en", "voice": "Ryan"}
    if engine == "qwen3-design":
        profile_data.update(voice="design", voice_description="A calm German narrator.")
    profile = AudioProfile.model_validate(profile_data).model_dump()

    def render(mode, fresh=False):
        response = send(port, "/api/speech-render", payload={**bound, "mode": mode, "chapter": 1, "profile": profile, "fresh_audio": fresh})
        assert response.status == 202, response.body
        identifier = json.loads(response.body)["job"]["id"]
        query = urlencode({**bound, "id": identifier})
        for _ in range(200):
            status = json.loads(send(port, "/api/speech-job?" + query).body)["job"]
            if status["state"] not in ("pending", "running"):
                break
            time.sleep(.01)
        assert status["state"] == "ready", status
        assert send(port, "/api/speech-audio?" + query).status == 200

    render("chapter")
    count = len(calls)
    assert count > 0 and project_audio_cache(source.parent).is_dir()
    render("chapter")
    assert len(calls) == count
    render("chapter", fresh=True)
    assert len(calls) == count * 2
    render("preview")
    render("preview")
    assert len(calls) == count * 2 + 2
    assert source.read_bytes() == before


@pytest.mark.parametrize("target", [None, "local", "jetson"])
@pytest.mark.parametrize("explicit_profile", [False, True])
def test_api_dispatches_target_without_mutating_saved_profiles(speech_server, monkeypatch, target, explicit_profile):
    import lixity.speech_jobs as jobs
    from lixity.speech_profiles import AudioProfile, parse_audio_settings

    port, source, handler, _observed = speech_server
    received = []
    original_config = (source.parent / "lixity.toml").read_bytes()
    original_source = source.read_bytes()
    profile = AudioProfile(engine="qwen3", voice="Ryan").model_dump()

    def render(source, output, **kwargs):
        received.append((kwargs["target"], kwargs["profile"].model_dump()))
        Path(output).write_bytes(generate_silence_wav(.01))

    monkeypatch.setattr(jobs, "render_speech_audio", render)
    bound = context(source, handler)
    payload = {**bound, "mode": "preview", "chapter": 1}
    if explicit_profile:
        payload["profile"] = profile
    if target is not None:
        payload["target"] = target
    response = send(port, "/api/speech-render", payload=payload)
    assert response.status == 202, response.body
    identifier = json.loads(response.body)["job"]["id"]
    query = urlencode({**bound, "id": identifier})
    for _ in range(100):
        status = json.loads(send(port, "/api/speech-job?" + query).body)["job"]
        if status["state"] not in ("pending", "running"):
            break
        time.sleep(.01)
    assert status["state"] == "ready", status
    assert send(port, "/api/speech-audio?" + query).status == 200
    expected = profile if explicit_profile else parse_audio_settings(None).profiles["narrator"].model_dump()
    assert received == [(target or "local", expected)]
    assert "target" not in received[0][1]
    assert (source.parent / "lixity.toml").read_bytes() == original_config
    assert source.read_bytes() == original_source


@pytest.mark.parametrize("change", [
    {"target": "remote"},
    {"target": "http://127.0.0.1:8770"},
    {"target": None},
    {"target": {"host": "jetson"}},
])
def test_api_rejects_untrusted_execution_targets(speech_server, change):
    port, source, handler, observed = speech_server
    before = source.read_bytes()
    config_before = (source.parent / "lixity.toml").read_bytes()
    response = send(port, "/api/speech-render", payload={
        **context(source, handler), "mode": "preview", "chapter": 1, **change,
    })
    assert response.status == 400, response.body
    assert observed == []
    assert source.read_bytes() == before
    assert (source.parent / "lixity.toml").read_bytes() == config_before


@pytest.mark.parametrize("target", ["local", "jetson"])
def test_explicit_piper_draft_is_rejected_without_fallback_or_state_changes(speech_server, target):
    port, source, handler, observed = speech_server
    config = source.parent / "lixity.toml"
    config_before, source_before = config.read_bytes(), source.read_bytes()
    response = send(port, "/api/speech-render", payload={
        **context(source, handler), "mode": "preview", "chapter": 1, "target": target,
        "profile": {"engine": "piper", "language": "en", "voice": "en_US-lessac-medium"},
    })
    assert response.status == 400, response.body
    error = json.loads(response.body)
    assert error["ok"] is False and "Piper" in error["message"] and "audio-migrate" in error["message"]
    assert "job" not in error and observed == []
    assert config.read_bytes() == config_before and source.read_bytes() == source_before
    # A valid request after rejection remains dispatchable in the same context.
    valid = send(port, "/api/speech-render", payload={
        **context(source, handler), "mode": "preview", "chapter": 1, "target": target,
    })
    assert valid.status == 202, valid.body


def test_saved_piper_configuration_is_reported_and_never_rendered_or_rewritten(speech_server):
    port, source, handler, observed = speech_server
    config = source.parent / "lixity.toml"
    config.write_text('''language = "en"
[audio]
schema_version = "lixity-audio-settings/1"
selected = "narrator"
[audio.profiles.narrator]
engine = "piper"
voice = "en_US-lessac-medium"
''')
    config_before, source_before = config.read_bytes(), source.read_bytes()
    bound = context(source, handler)
    response = send(port, "/api/speech?" + urlencode(bound))
    assert response.status == 200, response.body
    data = json.loads(response.body)
    assert data["settings"] is None and set(data["capabilities"]) == {"qwen3", "qwen3-design", "qwen3-base"}
    assert "Piper" in data["configuration_error"] and "audio-migrate" in data["configuration_error"]
    response = send(port, "/api/speech-render", payload={**bound, "mode": "preview", "chapter": 1})
    assert response.status == 400, response.body
    error = json.loads(response.body)
    assert "Piper" in error["message"] and "job" not in error
    assert observed == []
    assert config.read_bytes() == config_before and source.read_bytes() == source_before


def test_legacy_audio_cannot_be_replaced_through_normal_settings_save(speech_server):
    from lixity.config import read_explicit_project_config
    from lixity.speech_profiles import parse_audio_settings

    port, source, handler, _observed = speech_server
    config = source.parent / "lixity.toml"
    config.write_text('''language = "en"
[audio]
schema_version = "lixity-audio-settings/1"
selected = "retained_narrator"
[audio.profiles.retained_narrator]
name = "Retained synthetic name"
engine = "piper"
language = "en"
voice = "en_US-lessac-medium"
pronunciations = { "Synthetic" = "Example" }
[audio.profiles.retained_second]
name = "Second narrator"
engine = "piper"
language = "de"
voice = "de_DE-thorsten-medium"
''')
    before, source_before, title_before = config.read_bytes(), source.read_bytes(), handler.title
    legacy_audio = read_explicit_project_config(source.parent)["audio"]
    bound = context(source, handler)
    data = json.loads(send(port, "/api/speech?" + urlencode(bound)).body)
    response = send(port, "/api/settings", payload={
        "project_token": bound["project_token"], "title": "Must not be saved",
        "audio": parse_audio_settings(None).model_dump(by_alias=True),
    })
    assert response.status == 400, response.body
    assert "audio-migrate" in json.loads(response.body)["message"]
    assert data["requires_migration"] is True and data["settings"] is None
    assert config.read_bytes() == before and source.read_bytes() == source_before
    assert handler.title == title_before
    # Unrelated settings remain editable and keep every legacy profile intact.
    response = send(port, "/api/settings", payload={
        "project_token": bound["project_token"], "title": "Allowed synthetic title",
    })
    assert response.status == 200, response.body
    assert read_explicit_project_config(source.parent)["audio"] == legacy_audio
    assert source.read_bytes() == source_before
    response = send(port, "/api/settings", payload={
        "project_token": context(source, handler)["project_token"],
        "title": "Another allowed title", "audio": legacy_audio,
    })
    assert response.status == 200, response.body
    assert read_explicit_project_config(source.parent)["audio"] == legacy_audio
    assert source.read_bytes() == source_before


def test_native_direction_save_plan_and_stale_snapshot(speech_server):
    port, source, handler, observed = speech_server
    bound = context(source, handler)
    data = json.loads(send(port, '/api/speech?' + urlencode(bound)).body)
    state = data['direction']
    entry = {'anchor': state['passages'][0]['anchor'], 'instructions': 'Restrained tension.'}
    payload = {**bound, 'expected_settings_sha256':state['settings_sha256'],
               'expected_direction_sha256':state['direction_sha256'], 'direction':entry}
    saved = send(port,'/api/speech-direction',payload=payload)
    assert saved.status == 200, saved.body
    assert send(port,'/api/speech-direction',payload=payload).status == 409
    planned = send(port,'/api/speech-plan',payload={**bound,'chapter':1,'mode':'chapter'})
    assert planned.status == 200, planned.body
    plan = json.loads(planned.body)['plan']
    assert any(row['profile']['instructions']=='Restrained tension.' for row in plan['segments'])
    assert observed == []
    assert source.read_text().startswith('## First')


def test_native_base_plan_binds_reference_and_rejects_changed_reference(speech_server):
    from lixity.speech_references import save_reference

    port, source, handler, _observed = speech_server
    bound = context(source, handler)
    reference = save_reference(source.parent, generate_silence_wav(1), "Exact transcript.")
    profile = {"name": "Reference", "engine": "qwen3-base", "language": "en",
               "voice": "reference", "reference_id": reference.id}
    payload = {**bound, "mode": "preview", "chapter": 1, "profile": profile}
    response = send(port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    plan = json.loads(response.body)["plan"]
    assert plan["controls"]["instructions"] == "unsupported"
    assert b"Exact transcript" not in response.body
    path = source.parent / ".lixity" / "audio-references" / f"{reference.id}.json"
    path.write_text("changed")
    assert send(port, "/api/speech-render", payload=payload).status == 400


def test_native_base_download_expires_when_reference_changes(speech_server):
    from lixity.speech_references import save_reference

    port, source, handler, _observed = speech_server
    bound = context(source, handler)
    reference = save_reference(source.parent, generate_silence_wav(1), "Exact transcript.")
    profile = {"name": "Reference", "engine": "qwen3-base", "language": "en",
               "voice": "reference", "reference_id": reference.id}
    response = send(port, "/api/speech-render", payload={**bound, "mode": "preview", "chapter": 1, "profile": profile})
    assert response.status == 202, response.body
    query = urlencode({**bound, "id": json.loads(response.body)["job"]["id"]})
    for _ in range(100):
        status = json.loads(send(port, "/api/speech-job?" + query).body)["job"]
        if status["state"] == "ready":
            break
        time.sleep(.01)
    assert status["state"] == "ready"
    assert send(port, "/api/speech-audio?" + query).status == 200
    path = source.parent / ".lixity" / "audio-references" / f"{reference.id}.json"
    path.write_text("changed")
    assert send(port, "/api/speech-audio?" + query).status != 200


def test_saving_direction_invalidates_a_completed_download(speech_server):
    port, source, handler, _observed = speech_server
    bound=context(source,handler)
    response=send(port,'/api/speech-render',payload={**bound,'mode':'preview','chapter':1})
    identifier=json.loads(response.body)['job']['id']
    query=urlencode({**bound,'id':identifier})
    for _ in range(100):
        status=json.loads(send(port,'/api/speech-job?'+query).body)['job']
        if status['state']=='ready':
            break
        time.sleep(.01)
    assert send(port,'/api/speech-audio?'+query).status==200
    state=json.loads(send(port,'/api/speech?'+urlencode(bound)).body)['direction']
    saved=send(port,'/api/speech-direction',payload={**bound,
        'expected_settings_sha256':state['settings_sha256'],
        'expected_direction_sha256':state['direction_sha256'],
        'direction':{'anchor':state['passages'][0]['anchor'],'instructions':'Calm.'}})
    assert saved.status==200
    assert send(port,'/api/speech-audio?'+query).status!=200
