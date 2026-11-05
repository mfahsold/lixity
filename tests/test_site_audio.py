"""Static audio uses explicit current chapter artifacts, never caches or references."""
import hashlib
import io
import json
import wave
import zipfile
from copy import deepcopy

import pytest
from pydantic import ValidationError

from lixity.config import prepare_project_settings
from lixity.research import api
from lixity.site_contracts import SiteManifest
from lixity.site_export import prepare_site
from lixity.speech_artifacts import retain_chapter_audio


@pytest.fixture
def audio_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "manuscript.md"
    source.write_text("## Arrival\n\nA bird lands in the garden.\n\n## Later\n\nA gate closes.\n")
    (root / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n')
    api.init(root, title="Synthetic project")
    prepare_project_settings(root, {"site_publications": {"readers": {"title": "Public reading copy"}}}).commit()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    recordings = []
    for chapter in (1, 2):
        output = io.BytesIO()
        with wave.open(output, "wb") as writer:
            writer.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
            writer.writeframes(bytes((chapter, 0)) * 24000 * chapter)
        content = output.getvalue()
        entry = retain_chapter_audio(root, content, source_sha256=digest, chapter=chapter,
                                     origin="generated" if chapter == 1 else "imported")
        recordings.append((entry, content))
    reference = root / ".lixity/audio/references/private.wav"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_bytes(b"PRIVATE_VOICE_REFERENCE_MUST_NOT_SHIP")
    return root, source, digest, recordings


def test_audio_is_opt_in_and_chapter_cap_is_applied_before_reading_later_artifacts(audio_project):
    root, _source, digest, recordings = audio_project
    ordinary = prepare_site(root, mode="reader", publication_profile="readers", max_chapter=1)
    assert "audio" not in ordinary.manifest
    assert not any(name.startswith("assets/audio/") for name in ordinary.files)
    # An unexported corrupt chapter must not block or enter the selected reading copy.
    (root / ".lixity/audio/exports/chapter-2.json").write_text("BROKEN_LATER_PRIVATE_METADATA")
    exported = prepare_site(root, mode="reader", publication_profile="readers", max_chapter=1, include_audio=True)
    assert exported.manifest["schema_version"] == "lixity-read-only-site/3"
    audio = exported.manifest["audio"]
    assert audio["source_sha256"] == digest
    assert len(audio["tracks"]) == 1
    track = audio["tracks"][0]
    assert track["chapter"] == 1 and track["title"] == "Arrival"
    assert track["duration_seconds"] == 1 and track["origin"] == "generated"
    assert exported.files[track["file"]] == recordings[0][1]
    assert exported.manifest["files"][track["file"]]["sha256"] == track["sha256"]
    for private in (b"PRIVATE_VOICE_REFERENCE_MUST_NOT_SHIP", b"BROKEN_LATER_PRIVATE_METADATA", recordings[1][1]):
        assert all(private not in content for content in exported.files.values())
    html = exported.files["index.html"].decode()
    assert 'id="publication-audio-player" controls' in html
    assert "window.createSpeechPlayer" in html
    assert 'id="speech-record"' not in html
    SiteManifest.model_validate(exported.manifest)


def test_audio_can_be_combined_with_selected_analysis_and_roundtrip_zip(audio_project):
    root, *_ = audio_project
    bundle = prepare_site(root, mode="reader", publication_profile="readers", include_audio=True,
                          analysis_sections=["chapters"])
    assert bundle.manifest["schema_version"] == "lixity-read-only-site/3"
    assert bundle.manifest["capabilities"]["analysis"] is True
    assert "analysis.html" in bundle.files
    assert [track["chapter"] for track in bundle.manifest["audio"]["tracks"]] == [1, 2]
    assert bundle.manifest["audio"]["tracks"][1]["origin"] == "imported"
    with zipfile.ZipFile(io.BytesIO(bundle.to_zip())) as archive:
        for track in bundle.manifest["audio"]["tracks"]:
            assert hashlib.sha256(archive.read(track["file"])).hexdigest() == track["sha256"]


def test_stale_or_empty_audio_selection_is_an_explicit_error(audio_project):
    root, source, *_ = audio_project
    source.write_text(source.read_text() + "\nThe manuscript changed.\n")
    with pytest.raises(ValueError, match="No saved chapter audio matches"):
        prepare_site(root, mode="reader", publication_profile="readers", include_audio=True)
    # A normal reading copy still exports without implicitly exposing stale audio.
    assert "audio" not in prepare_site(root, mode="reader", publication_profile="readers").manifest


@pytest.mark.parametrize("mutation", ["cap", "hash", "version", "duplicate", "source", "analysis", "extra_audio"])
def test_audio_manifest_rejects_inconsistent_scope_or_inventory(audio_project, mutation):
    root, *_ = audio_project
    manifest = deepcopy(prepare_site(root, mode="reader", publication_profile="readers", include_audio=True).manifest)
    track = manifest["audio"]["tracks"][0]
    if mutation == "cap":
        manifest["publication"]["max_chapter"] = 0
    elif mutation == "hash":
        track["sha256"] = "a" * 64
    elif mutation == "version":
        manifest["schema_version"] = "lixity-read-only-site/1"
    elif mutation == "duplicate":
        manifest["audio"]["tracks"].append(dict(track))
    elif mutation == "source":
        manifest["audio"]["source_sha256"] = "c" * 64
    elif mutation == "extra_audio":
        manifest["files"]["assets/audio/" + "d" * 64 + ".wav"] = {"sha256": "d" * 64, "byte_length": 100}
    else:
        manifest["capabilities"]["analysis"] = True
    with pytest.raises(ValidationError):
        SiteManifest.model_validate(manifest)


def test_cli_and_native_download_use_the_same_explicit_audio_selection(audio_project, tmp_path, capsys):
    from lixity.cli import main
    from lixity.server.pdf_context import manuscript_pdf_token
    from tests.support import LoopbackServer, make_handler, send

    root, source, *_ = audio_project
    destination = tmp_path / "reading-copy"
    assert main(["export-site", "--project", str(root), "--mode", "reader",
                 "--publication-profile", "readers", "--max-chapter", "1", "--include-audio",
                 "--output", str(destination), "--json"]) == 0
    cli_manifest = json.loads(capsys.readouterr().out)
    assert (destination / cli_manifest["audio"]["tracks"][0]["file"]).is_file()
    handler = make_handler(root, source_input=source, language="en")
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                  language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with LoopbackServer(handler) as server:
        response = send(server.port, "/api/site-export", payload={"project_token": token,
            "include_research": False, "include_source_files": False, "mode": "reader",
            "publication_profile": "readers", "max_chapter": 1, "include_audio": True})
    assert response.status == 200, response.body[:200]
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        native_manifest = json.loads(archive.read("manifest.json"))
        assert native_manifest["audio"] == cli_manifest["audio"]
        track = native_manifest["audio"]["tracks"][0]
        assert archive.read(track["file"]) == (destination / track["file"]).read_bytes()
