"""Export scope and commands cannot accidentally invoke audio synthesis."""

import base64
import hashlib
import json
from xml.etree import ElementTree

import pytest

from lixity.cli import main
from lixity.server.pdf_context import project_settings_token
from tests.support import LoopbackServer, make_handler, send


def test_export_only_dashboard_exposes_audio_without_synthesis_capability():
    from lixity.ui import render_dashboard

    document = render_dashboard([], [], controls=True, enabled_actions=("speech-plan",))
    assert 'data-speech-capable="true"' in document
    assert 'data-speech-render-capable="false"' in document
    assert "Project-local listening drafts share one token-bound native dialog" in document


@pytest.fixture
def export_project(tmp_path, monkeypatch):
    source = tmp_path / "draft.md"
    source.write_text("## First\n\nThe red bird sings.\n\nThe blue bird answers.\n\n## Second\n\nThe river flows.\n")
    (tmp_path / "lixity.toml").write_text('language="en"\nmanuscript="draft.md"\n')

    def forbidden(*args, **kwargs):
        raise RuntimeError("Export must not invoke synthesis or load a reference recording")

    monkeypatch.setattr("lixity.speech.render_speech_audio", forbidden)
    monkeypatch.setattr("lixity.speech_references.references_for_plan", forbidden)
    monkeypatch.setattr("lixity.server.routes_speech.references_for_plan", forbidden)
    return source


def test_ssml_flag_alone_is_an_export(export_project, capsys):
    assert main(["read-aloud", "--project", str(export_project.parent), "--ssml"]) == 0
    output = capsys.readouterr().out
    document = ElementTree.fromstring(output)  # noqa: S314 - generated synthetic SSML
    assert document.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "en"
    assert "The river flows." in output


def test_timeline_cli_exports_all_chapters_without_synthesis(export_project, capsys):
    assert main(["read-aloud", "--project", str(export_project.parent), "--timeline"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "lixity-audio-timeline/1"
    assert result["source"]["sha256"] == hashlib.sha256(export_project.read_bytes()).hexdigest()
    assert any(row["text"] == "The river flows." for row in result["segments"])


@pytest.mark.parametrize("mode,chapter,includes_second", [("chapter", 1, False), ("manuscript", None, True)])
def test_http_export_preserves_selected_scope(export_project, monkeypatch, mode, chapter, includes_second):
    monkeypatch.setattr("lixity.speech_status.worker_health", lambda target: {"target": target, "state": "unavailable", "model": None})
    handler = make_handler(export_project.parent, source_input=export_project, language="en")
    payload = {
        "project_token": project_settings_token(handler.workspace_root, str(export_project)),
        "source_sha256": hashlib.sha256(export_project.read_bytes()).hexdigest(),
        "mode": mode, "chapter": chapter,
    }
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    assert result["timeline"]["schema_version"] == "lixity-audio-timeline/1"
    assert "The red bird sings." in result["ssml"]
    assert "The blue bird answers." in result["ssml"]
    assert ("The river flows." in result["ssml"]) is includes_second
    assert isinstance(result["export_warnings"], list)


def test_named_export_command_defaults_to_timeline(export_project, capsys):
    assert main(["audio-export-plan", "--project", str(export_project.parent), "--chapter", "2"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "lixity-audio-timeline/1"
    assert any(row["text"] == "The river flows." for row in result["segments"])
    assert not any("bird" in row["text"] for row in result["segments"])


def test_http_external_draft_exports_and_compares_without_native_language_default(export_project):
    from lixity.speech import generate_silence_wav

    export_project.write_text("De rivier stroomt.")
    (export_project.parent / "lixity.toml").write_text('language="nl"\nmanuscript="draft.md"\n')
    handler = make_handler(export_project.parent, source_input=export_project, language="nl")
    payload = {"project_token": project_settings_token(handler.workspace_root, str(export_project)),
               "source_sha256": hashlib.sha256(export_project.read_bytes()).hexdigest(),
               "mode": "manuscript", "chapter": None,
               "profile": {"engine": "openai-compatible", "language": "nl", "base_url": "http://127.0.0.1:8000/v1",
                           "model": "synthetic", "voice": "synthetic"}}
    audio = generate_silence_wav(1)
    transcript = {"schema_version": "lixity-audio-transcript/1", "audio_sha256": hashlib.sha256(audio).hexdigest(),
                  "words": [{"text": text, "start": index * 0.1, "end": index * 0.1 + 0.08}
                            for index, text in enumerate(("De", "rivier", "stroomt"))]}
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/speech-plan", payload=payload)
        assert response.status == 200, response.body
        assert 'xml:lang="nl"' in json.loads(response.body)["ssml"]
        compared = send(server.port, "/api/audio-audit", payload={**payload,
            "audio": base64.b64encode(audio).decode(), "filename": "chapter.wav", "transcript": transcript})
        assert compared.status == 200, compared.body
        assert json.loads(compared.body)["audit"]["alignment"]["matched_words"] == 3


def test_audio_inspect_cli_reports_unknown_text_without_transcript(tmp_path, capsys):
    from lixity.speech import generate_silence_wav

    audio = tmp_path / "chapter.wav"
    audio.write_bytes(generate_silence_wav(1))
    assert main(["audio-inspect", str(audio)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == "lixity-audio-audit/1"
    assert result["alignment"]["status"] == "unknown"


def test_http_audio_audit_is_read_only_and_rejects_wrong_transcript(export_project):
    from lixity.speech import generate_silence_wav

    handler = make_handler(export_project.parent, source_input=export_project, language="en")
    before = export_project.read_bytes()
    settings_before = (export_project.parent / "lixity.toml").read_bytes()
    payload = {
        "project_token": project_settings_token(handler.workspace_root, str(export_project)),
        "source_sha256": hashlib.sha256(before).hexdigest(),
        "mode": "chapter", "chapter": 1, "filename": "selected.wav",
        "audio": base64.b64encode(generate_silence_wav(1)).decode(),
        "profile": {"invalid": "Signal-only inspection does not need a voice profile"},
    }
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/audio-audit", payload=payload)
        assert response.status == 200, response.body
        assert json.loads(response.body)["audit"]["alignment"]["status"] == "unknown"
        payload.pop("profile")
        payload["transcript"] = {"schema_version": "lixity-audio-transcript/1",
                                 "audio_sha256": "0" * 64, "words": []}
        rejected = send(server.port, "/api/audio-audit", payload=payload)
        assert rejected.status == 400
    assert export_project.read_bytes() == before
    assert (export_project.parent / "lixity.toml").read_bytes() == settings_before


def test_provider_schema_upgrade_requires_review_and_keeps_source(export_project, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path.parent / (tmp_path.name + "-app-data")))
    handler = make_handler(export_project.parent, source_input=export_project, language="en")
    before = export_project.read_bytes()
    config = export_project.parent / "lixity.toml"
    original = config.read_bytes()
    payload = {"project_token": project_settings_token(handler.workspace_root, str(export_project)),
               "source_sha256": hashlib.sha256(before).hexdigest()}
    with LoopbackServer(handler) as server:
        preview = send(server.port, "/api/audio-schema", payload=payload)
        assert preview.status == 200, preview.body
        proposal = json.loads(preview.body)["migration"]
        assert proposal["target_schema"] == "lixity-audio-settings/4"
        assert config.read_bytes() == original
        rejected = send(server.port, "/api/audio-schema", payload={**payload, "apply": True})
        assert rejected.status == 400
        applied = send(server.port, "/api/audio-schema", payload={**payload, "apply": True, "snapshot": proposal["snapshot"]})
        assert applied.status == 200, applied.body
    assert export_project.read_bytes() == before
    assert b"lixity-audio-settings/4" in config.read_bytes()
    from pathlib import Path
    assert Path(json.loads(applied.body)["backup"]).is_file()


@pytest.mark.parametrize("ssml_language,long_word", [("en_US", False), ("en", True)])
def test_http_timeline_does_not_depend_on_other_export_formats(export_project, ssml_language, long_word):
    if long_word:
        export_project.write_text("## First\n\n" + "a" * 700 + "\n")
    handler = make_handler(export_project.parent, source_input=export_project, language="en")
    payload = {"project_token": project_settings_token(handler.workspace_root, str(export_project)),
               "source_sha256": hashlib.sha256(export_project.read_bytes()).hexdigest(), "mode": "chapter", "chapter": 1,
               "profile": {"engine": "openai-compatible", "voice": "test", "model": "test",
                           "base_url": "http://localhost:9999/v1", "language": ssml_language}}
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/speech-plan", payload=payload)
    assert response.status == 200, response.body
    result = json.loads(response.body)
    assert result["timeline"]["segments"]
    if long_word:
        assert result["plan"] is None and result["legacy_plan_error"]
    else:
        assert result["ssml"] is None
        assert result["export_warnings"][0]["code"] == "ssml_unavailable"


def test_audio_audit_rejects_direction_changed_during_inspection(export_project, monkeypatch):
    from lixity.speech import generate_silence_wav

    inspected = []
    def inspect(*args, **kwargs):
        inspected.append(True)
        monkeypatch.setattr("lixity.server.routes_speech.direction_snapshot", lambda root: "0" * 64)
        return {"alignment": {"status": "compared"}}
    monkeypatch.setattr("lixity.audio_audit.inspect_audio", inspect)
    handler = make_handler(export_project.parent, source_input=export_project, language="en")
    audio = generate_silence_wav(1)
    payload = {"project_token": project_settings_token(handler.workspace_root, str(export_project)),
               "source_sha256": hashlib.sha256(export_project.read_bytes()).hexdigest(), "mode": "chapter", "chapter": 1,
               "audio": base64.b64encode(audio).decode(), "filename": "chapter.wav",
               "transcript": {"schema_version": "lixity-audio-transcript/1", "audio_sha256": hashlib.sha256(audio).hexdigest(), "words": []}}
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/audio-audit", payload=payload)
    assert inspected
    assert response.status == 409


def test_cli_engine_switch_discards_only_inapplicable_inherited_bindings(export_project, capsys):
    config = export_project.parent / "lixity.toml"
    config.write_text('language="en"\n[audio]\nschema_version="lixity-audio-settings/4"\nselected="narrator"\n'
                      '[audio.profiles.narrator]\nengine="qwen3-base"\nvoice="reference"\nreference_id="' + "a" * 64 + '"\n')
    args = ["audio-export-plan", "--project", str(export_project.parent)]
    assert main([*args, "--engine", "openai-compatible", "--voice", "synthetic", "--model", "test",
                 "--base-url", "http://localhost:9999/v1"]) == 0
    external = json.loads(capsys.readouterr().out)
    assert external["segments"][0]["profile"].get("reference_id") is None
    config.write_text('language="en"\n[audio]\nschema_version="lixity-audio-settings/4"\nselected="narrator"\n'
                      '[audio.profiles.narrator]\nengine="openai-compatible"\nvoice="synthetic"\nmodel="test"\nbase_url="http://localhost:9999/v1"\n')
    assert main([*args, "--engine", "qwen3", "--voice", "Ryan"]) == 0
    native = json.loads(capsys.readouterr().out)
    assert "base_url" not in native["segments"][0]["profile"]
