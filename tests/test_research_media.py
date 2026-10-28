"""Synthetic retained media share source identity, lifecycle and disclosure."""

import base64
import json
import struct
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lixity.research import api
from lixity.research.images import extract_image_references
from lixity.research.media import validate_media
from lixity.research.models import Extraction, SourceVersion
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from lixity.site_export import prepare_site
from tests.media_fixtures import make_synthetic_pdf
from tests.support import LoopbackServer, make_handler
from tests.test_site_export import response, site_data


def mp4():
    def box(kind, content):
        return struct.pack(">I4s", len(content) + 8, kind) + content
    return box(b"ftyp", b"isom\0\0\0\0mp42") + box(b"moov", b"synthetic metadata") + box(b"mdat", b"synthetic media")


def webm():
    def element(identifier, content):
        assert len(content) < 127
        return identifier + bytes([0x80 + len(content)]) + content
    return (element(b"\x1a\x45\xdf\xa3", element(b"\x42\x82", b"webm")) +
            element(b"\x18\x53\x80\x67", element(b"\x16\x54\xae\x6b", b"tracks") +
                    element(b"\x1f\x43\xb6\x75", b"frames")))


@pytest.fixture(params=[("note.pdf", make_synthetic_pdf("Synthetic retained document."), "application/pdf"),
                        ("clip.mp4", mp4(), "video/mp4"), ("clip.webm", webm(), "video/webm")])
def media(request):
    return request.param


@pytest.fixture
def project(tmp_path):
    api.init(tmp_path, title="Synthetic media")
    (tmp_path / "manuscript.md").write_text("# Gate\n\n## Arrival\n\nThe gate was open.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\nlanguage = "en"\n')
    return tmp_path


def attach(project, media, **overrides):
    filename, content, _ = media
    dossier = api.create_dossier(project, "Media notes", "## Notes\n\nOriginal note.")["dossier_id"]
    loaded = api.get_record(project, "dossier", dossier)
    values = {"filename": filename, "expected_snapshot": loaded["snapshot"], "expected_revision": 1,
              "allow_retention": True, "alt": "Synthetic attachment", "section": "Notes",
              "context": {"provenance_note": "Synthetic specimen; not a licensing decision."}}
    values.update(overrides)
    return api.attach_dossier_media(project, dossier, content, **values)


def test_shared_atomic_attachment_and_immutable_versions(project, media, tmp_path):
    result = attach(project, media)
    dossier = result["record"]["id"]
    assert result["record"]["revision"] == 2
    assert "lixity:media/" in result["record"]["body"]
    assert result["images"] == []
    retained = result["media"][0]
    assert retained["media_type"] == media[2]
    assert retained["context"]["provenance_note"].startswith("Synthetic specimen")
    assert api.get_dossier(project, dossier, section="Notes")["media"] == result["media"]
    assert api.get_dossier(project, dossier, summary=True)["media"] == result["media"]
    assert api.list_dossier_images(project)["total"] == 0
    assert api.get_record(project, "dossier", dossier, revision=1)["media"] == []
    assert api.record_history(project, "dossier", dossier)["revisions"][0]["media"] == result["media"]
    assert api.read_media(project, project_id=result["project_id"], source_id=retained["source_id"],
                          version_id=retained["source_version_id"])["content"] == media[1]
    snapshot = Repository(project).snapshot()
    assert not any(isinstance(record, Extraction) for record in snapshot.records.values())
    assert snapshot.manifest.schema_version == "research-manifest-local/9"
    version = snapshot.records[retained["source_version_id"]]
    assert version.schema_version == "research-local/9"
    if media[2].startswith("video/"):
        with pytest.raises(ValidationError):
            SourceVersion.model_validate({**version.model_dump(), "schema_version": "research-local/1"})
    assert api.audit(project)["ok"]
    archive = tmp_path / "media.tar.gz"
    restored = tmp_path / "restored"
    api.export_archive(project, archive)
    api.restore_archive(archive, restored)
    assert api.audit(restored)["ok"]
    assert api.get_record(restored, "dossier", dossier)["media"] == result["media"]
    before = Repository(project).snapshot().digest
    with pytest.raises(ResearchConflictError):
        api.attach_dossier_media(project, dossier, media[1], filename=media[0], allow_retention=True,
                                 expected_snapshot=before, expected_revision=1)
    assert Repository(project).snapshot().digest == before


def test_containers_limits_permissions_and_references(project, media):
    with pytest.raises(ResearchError, match="retention"):
        api.ingest_media(project, media[1], filename=media[0])
    for content, filename in [(media[1][:-3], media[0]), (b"<html>not media</html>", media[0]),
                              (b"x" * (50 * 1024 * 1024 + 1), media[0]),
                              (media[1], "wrong.png")]:
        with pytest.raises(ResearchError):
            api.ingest_media(project, content, filename=filename, allow_retention=True)
    result = attach(project, media)
    token = next(line for line in result["record"]["body"].splitlines() if line.startswith("!["))
    assert len(extract_image_references(token, media=True)) == 1
    assert extract_image_references("`" + token + "`", media=True) == []
    with pytest.raises(ResearchError):
        api.create_dossier(project, "Wrong source", token.replace(result["media"][0]["source_id"], uuid4().urn))
    with pytest.raises(ResearchError):
        api.create_dossier(project, "Malformed reserved data", "![media](lixity:media/not-a-pin)")


def test_media_withdrawal_and_purge_preserve_historical_placeholders(project, media):
    result = attach(project, media)
    entry = result["media"][0]
    dossier = result["record"]["id"]
    api.withdraw(project, source_id=entry["source_id"], reason="Synthetic withdrawal")
    assert api.get_record(project, "dossier", dossier)["media"][0]["availability"] == "withdrawn"
    assert api.read_media(project, project_id=result["project_id"], source_id=entry["source_id"],
                          version_id=entry["source_version_id"])["content"] == media[1]
    api.purge(project, entry["source_id"], reason="Synthetic removal")
    pinned = api.get_record(project, "dossier", dossier, revision=2)["media"][0]
    assert pinned["availability"] == "purged" and pinned["url"] is None
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/9"
    assert api.audit(project)["ok"]


def test_media_exports_are_opt_in_exact_and_publication_scoped(project, media):
    result = attach(project, media)
    dossier = result["record"]["id"]
    without = prepare_site(project, include_research=True)
    assert not any(name.startswith("assets/sources/") for name in without.files)
    assert not site_data(without)["resources"]
    with_files = prepare_site(project, include_research=True, include_source_files=True)
    assert media[1] in with_files.files.values()
    data = site_data(with_files)
    assert response(data, "record", kind="dossier", id=dossier, revision=2)["media"][0]["media_type"] == media[2]
    assert result["media"][0]["url"].split("?")[0] == "/api/research/media"
    assert len([key for key in data["resources"] if key.startswith("/api/research/media?")]) == 1
    from lixity.config import prepare_project_settings
    prepare_project_settings(project, {"site_publications": {"readers": {"title": "Media companion",
        "entries": [{"dossier_id": dossier, "section": "Notes"}]}}}).commit()
    curated = prepare_site(project, mode="companion", publication_profile="readers", include_source_files=True)
    public = site_data(curated)["publication"]["entries"][0]["media"][0]
    assert public["source_version_id"] == result["media"][0]["source_version_id"]
    assert "context" not in public
    assert media[1] in curated.files.values()


def test_media_http_ranges_and_same_origin(project, media):
    project_id = Repository(project).snapshot().project.id
    values = {"project_id": project_id, "filename": media[0], "allow_retention": True,
              "content_base64": base64.b64encode(media[1]).decode()}
    with LoopbackServer(make_handler(project, research_dir=project)) as server:
        captured = server.request("/api/research-media-ingest", payload=values)
        assert captured.status == 200, captured.body
        result = json.loads(captured.body)
        url = "/api/research/media?" + urlencode({"project_id": project_id, "source_id": result["source_id"],
                                                "version_id": result["source_version_id"]})
        full = server.request(url)
        assert full.status == 200 and full.body == media[1]
        assert full.headers["content-type"] == media[2]
        if media[2] == "application/pdf":
            assert full.headers["content-disposition"].startswith("attachment;")
            assert "sandbox" in full.headers["content-security-policy"]
        for requested, expected in [("bytes=2-5", media[1][2:6]), ("bytes=-4", media[1][-4:]),
                                    ("bytes=2-", media[1][2:])]:
            sliced = server.request(url, headers={"Range": requested})
            assert sliced.status == 206 and sliced.body == expected
        for requested in ["bytes=100000-", "bytes=2-1", "bytes=-0", "bytes=1-2,4-5", "bytes=-"]:
            failed = server.request(url, headers={"Range": requested})
            assert failed.status == 416 and failed.headers["content-range"] == f"bytes */{len(media[1])}"
        assert server.request(url, headers={"Origin": "https://foreign.invalid"}).status == 403
        assert server.request(url, headers={"Sec-Fetch-Site": "cross-site"}).status == 403
        assert server.request("/api/research-media-ingest", payload={},
                              headers={"Content-Length": str(72 * 1024 * 1024 + 1)}).status == 413


def test_wrong_container_families_and_unbounded_elements_are_rejected():
    for data in [webm().replace(b"webm", b"mkv "), mp4().replace(b"mp42", b"XXXX").replace(b"isom", b"XXXX"),
                 mp4().replace(b"mdat", b"junk"), b"\x1a\x45\xdf\xa3\xff",
                 b"\x1a\x45\xdf\xa3\x80" + b"\xec\x80" * 10001]:
        with pytest.raises(ResearchError):
            validate_media(data)


def test_retained_only_pdf_requires_extraction_and_uses_verified_text_after_ingest(project):
    from lixity.research.ocr import OCRBlock, OCRExtractionResult
    text = "The synthetic gate was open. The keeper read the register."
    content = make_synthetic_pdf(text)
    captured = api.ingest_media(project, content, filename="note.pdf", allow_retention=True)
    with pytest.raises(ResearchError, match="no extracted text"):
        api.analyze_source(project, captured["source_id"])
    path = project / "note.pdf"
    path.write_bytes(content)
    extraction = OCRExtractionResult(pages=[], full_text=text, blocks=[OCRBlock(page_number=1, text=text)],
                                    spans=[(0, len(text))], warnings=[])
    with patch("lixity.research.api.extract_pdf_document", return_value=extraction):
        api.ingest(project, path, source_id=captured["source_id"], allow_retention=True)
    result = api.analyze_source(project, captured["source_id"])
    assert result["provenance"]["source_id"] == captured["source_id"]
    comparison = api.compare_source(project, captured["source_id"], text)
    assert comparison
    assert api.audit(project)["ok"]


@pytest.mark.parametrize("filename,content", [("clip.mp4", mp4()), ("clip.webm", webm())])
def test_video_checkpoint_is_resumable_without_text_records(project, filename, content):
    path = project / filename
    path.write_bytes(content)
    captured = api.ingest_checkpoint(project, [path], checkpoint="media.json", allow_retention=True)
    assert captured["complete"] and captured["succeeded"] == 1
    resumed = api.ingest_checkpoint(project, checkpoint="media.json", resume=True, allow_retention=True)
    assert resumed["complete"] and resumed["succeeded"] == 1
    assert len(api.list_sources(project)["sources"]) == 1
    assert api.audit(project)["ok"]
