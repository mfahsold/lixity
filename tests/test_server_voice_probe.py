"""Project voice probes and immutable multi-part references use synthetic data."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest

from lixity.server.pdf_context import project_settings_token
from lixity.speech import generate_silence_wav
from tests.support import LoopbackServer, make_handler, send


def _manuscript() -> str:
    lines = ["## Harbour", ""]
    for index in range(1, 31):
        lines.extend([
            f"Mara visits the old lighthouse at Travemünde number {index}.",
            f"Hansen checks Kowalski's freight manifest beside the harbour of Lübeck number {index}.",
            f"The latent taxes disturb the invoice from Rotterdam number {index}.",
            "",
        ])
    return "\n".join(lines)


@pytest.fixture
def probe_server(tmp_path, monkeypatch):
    import lixity.speech_status as speech_status

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "user-cache"))
    monkeypatch.setattr(speech_status, "worker_health", lambda target, **kwargs: {
        "target": target, "state": "unavailable", "model": None,
    })
    monkeypatch.setattr("lixity.speech_record.get_microphone_status", lambda: {"devices": []})
    source = tmp_path / "manuscript.md"
    source.write_text(_manuscript(), encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "en"\n', encoding="utf-8")
    handler = make_handler(tmp_path, source_input=source, language="en")
    handler.refresh()
    with LoopbackServer(handler) as server:
        yield server.port, source, handler


def _context(source: Path, handler) -> dict[str, str]:
    return {
        "project_token": project_settings_token(handler.workspace_root, str(source)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }


def _generate(port: int, bound: dict[str, str], target: int = 150) -> dict:
    response = send(port, "/api/voice-probe", payload={**bound, "target_seconds": target})
    assert response.status == 200, response.body
    return response.json["probe"]


def _probe_audio(probe: dict) -> list[bytes]:
    count = len(probe["parts"])
    seconds = -(-150 // count)
    return [generate_silence_wav(seconds) for _ in range(count)]


def _save_payload(probe: dict, bound: dict[str, str], audio: list[bytes]) -> dict:
    return {
        **bound,
        "action": "save",
        "target_seconds": probe["target_seconds"],
        "probe_sha256": probe["probe_sha256"],
        "allow_retention": True,
        "fallback_part_index": 2,
        "parts": [
            {
                "index": index,
                "audio": base64.b64encode(part).decode("ascii"),
                "transcript": f"Synthetic confirmed probe part {index}.",
                "confirmed": True,
            }
            for index, part in enumerate(audio, 1)
        ],
    }


def test_voice_probe_generation_is_read_only_deterministic_and_context_bound(probe_server):
    port, source, handler = probe_server
    bound = _context(source, handler)
    before = set(source.parent.iterdir())
    first = _generate(port, bound)
    second = _generate(port, bound)
    assert first == second
    assert first["schema_version"] == "lixity-voice-probe-script/1"
    assert first["status"] == "ready"
    assert 120 <= first["estimated_seconds"] <= 180
    assert 3 <= len(first["parts"]) <= 6
    assert first["source_sha256"] == bound["source_sha256"]
    assert len(first["settings_sha256"]) == len(first["probe_sha256"]) == 64
    assert set(source.parent.iterdir()) == before
    response = send(port, "/api/voice-probe", payload={**bound, "project_token": "0" * 64})
    assert response.status == 409
    assert response.json["code"] == "stale-context"


def test_probe_identity_uses_original_source_bytes_for_crlf(probe_server):
    port, source, handler = probe_server
    source.write_bytes(_manuscript().replace("\n", "\r\n").encode("utf-8"))
    handler.refresh()
    bound = _context(source, handler)
    probe = _generate(port, bound)
    assert probe["source_sha256"] == bound["source_sha256"]


def test_reference_set_requires_confirmed_parts_and_retention(probe_server):
    port, source, handler = probe_server
    bound = _context(source, handler)
    probe = _generate(port, bound)
    audio = _probe_audio(probe)
    payload = _save_payload(probe, bound, audio)
    denied = send(port, "/api/audio-reference-set", payload={**payload, "allow_retention": False})
    assert denied.status == 400 and denied.json["code"] == "retention-required"
    unconfirmed = json.loads(json.dumps(payload))
    unconfirmed["parts"][1]["confirmed"] = False
    response = send(port, "/api/audio-reference-set", payload=unconfirmed)
    assert response.status == 400 and response.json["code"] == "invalid-reference-set"
    assert not (source.parent / ".lixity" / "audio-references").exists()


def test_reference_set_round_trip_playback_and_delete_retains_members(probe_server):
    from lixity.speech_references import list_reference_sets, list_references, load_reference_set

    port, source, handler = probe_server
    bound = _context(source, handler)
    probe = _generate(port, bound)
    audio = _probe_audio(probe)
    payload = _save_payload(probe, bound, audio)
    response = send(port, "/api/audio-reference-set", payload=payload)
    assert response.status == 200, response.body
    created = response.json
    reference = created["reference_set"]
    assert created["schema_version"] == "lixity-audio-reference-set-created/1"
    assert reference["part_count"] == len(audio)
    assert 120 <= reference["duration_seconds"] <= 180
    assert reference["fallback_part_index"] == 2
    assert sum(part["fallback"] for part in reference["parts"]) == 1
    assert reference["parts"][1]["fallback"] is True
    assert all(part["quality"]["schema_version"] == "lixity-audio-reference-quality/1"
               for part in reference["parts"])
    loaded = load_reference_set(source.parent, reference["id"])
    assert loaded.probe_sha256 == probe["probe_sha256"]
    assert loaded.fallback_part_index == 2
    assert len(list_reference_sets(source.parent)) == 1
    assert len(list_references(source.parent)) == len(audio)

    inspected = send(port, "/api/audio-reference-set", payload={
        **bound, "action": "inspect", "reference_id": reference["id"],
    })
    assert inspected.status == 200
    assert inspected.json["reference_set"] == reference
    query = urlencode({**bound, "reference_id": reference["id"], "part_index": "2"})
    playback = send(port, "/api/speech-audio?" + query)
    assert playback.status == 200 and playback.body == audio[1]
    assert send(port, "/api/speech-audio?" + urlencode({**bound, "reference_id": reference["id"]})).status == 400

    stale = send(port, "/api/audio-reference-set", payload={
        **bound, "action": "save", "target_seconds": probe["target_seconds"],
        "probe_sha256": "0" * 64, "allow_retention": True,
        "fallback_part_index": 1, "parts": payload["parts"],
    })
    assert stale.status == 400 and stale.json["code"] == "stale-probe"

    deleted = send(port, "/api/audio-reference-set", payload={
        **bound, "action": "delete", "reference_id": reference["id"],
    })
    assert deleted.status == 200
    assert list_reference_sets(source.parent) == []
    assert len(list_references(source.parent)) == len(audio)


def test_changed_manuscript_cannot_publish_an_old_probe(probe_server):
    port, source, handler = probe_server
    bound = _context(source, handler)
    probe = _generate(port, bound)
    payload = _save_payload(probe, bound, _probe_audio(probe))
    source.write_text(source.read_text(encoding="utf-8") + "\nA changed final sentence.\n", encoding="utf-8")
    response = send(port, "/api/audio-reference-set", payload=payload)
    assert response.status == 409 and response.json["code"] == "stale-context"
    assert not (source.parent / ".lixity" / "audio-references").exists()


def test_reference_set_can_activate_a_supported_profile(probe_server):
    from lixity.config import prepare_project_settings

    port, source, handler = probe_server
    prepare_project_settings(source.parent, {"audio": {
        "selected": "narrator",
        "profiles": {
            "narrator": {
                "name": "Synthetic narrator", "engine": "qwen3-base", "language": "en",
                "voice": "reference", "reference_id": "a" * 64,
            },
        },
    }}).commit()
    handler.refresh()
    bound = _context(source, handler)
    probe = _generate(port, bound)
    response = send(port, "/api/audio-reference-set", payload={
        **_save_payload(probe, bound, _probe_audio(probe)), "profile_id": "narrator",
    })
    assert response.status == 200, response.body
    assert response.json["activation"]["state"] == "activated"
    reference_id = response.json["reference_set"]["id"]
    assert reference_id in (source.parent / "lixity.toml").read_text(encoding="utf-8")


def test_speech_index_advertises_probe_and_reference_sets(probe_server):
    port, source, handler = probe_server
    response = send(port, "/api/speech?" + urlencode(_context(source, handler)))
    assert response.status == 200
    data = response.json
    assert data["voice_probe_format"]["schema_version"] == "lixity-voice-probe-script/1"
    assert data["reference_set_format"] == "lixity-audio-reference-set/1"
    assert data["reference_sets"] == []
