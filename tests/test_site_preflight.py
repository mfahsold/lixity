"""Export checks measure the actual package without creating a destination."""

import json

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.site_export import prepare_site
from tests.test_research_images import png
from tests.test_site_export import file_bytes


def test_response_limit_identifies_first_crossing_without_source_text_or_token(monkeypatch):
    import lixity.site_export as export

    reads = export._Reads("private-operational-token")
    payload = {"text": "Synthetic source sentence."}
    one = len(export._json(payload)) + len("/api/research/sources?id=synthetic-id")
    monkeypatch.setattr(export, "MAX_SITE_DATA_BYTES", one)
    with pytest.raises(export.SiteExportLimitError) as caught:
        reads.add("sources", payload, id="synthetic-id")
    report = caught.value.diagnostic
    assert report["schema_version"] == "lixity-site-preflight-error/1"
    assert report["ok"] is False and report["complete"] is False
    assert report["limit"] == "research_response_bytes"
    assert report["limit_bytes"] == one
    assert "first limit crossing" in report["message"]
    assert "total package size is unknown" in report["message"]
    assert report["observed_bytes"] > one
    assert report["overflow_bytes"] == report["observed_bytes"] - one
    assert report["accepted_responses"] == 1
    assert report["response_route"] == "/api/research/sources"
    assert report["response_parameters"] == {"id": "synthetic-id"}
    assert report["files_written"] is False
    assert reads.size == one
    assert "private-operational-token" not in json.dumps(report)
    assert payload["text"] not in json.dumps(report)


def test_response_count_limit_is_distinct_from_byte_limit(monkeypatch):
    import lixity.site_export as export

    monkeypatch.setattr(export, "MAX_SITE_RESPONSES", 1)
    reads = export._Reads("operational-token")
    with pytest.raises(export.SiteExportLimitError) as caught:
        reads.add("status", {"ok": True})
    report = caught.value.diagnostic
    assert report["limit"] == "research_response_count"
    assert report["limit_count"] == 1 and report["observed_count"] == 2
    assert report["overflow_count"] == 1 and len(reads.responses) == 1


def test_cli_preflight_limit_returns_json_and_never_writes(tmp_path, capsys, monkeypatch):
    import lixity.site_export as export

    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    api.init(tmp_path, title="Synthetic")
    before = file_bytes(tmp_path)
    monkeypatch.setattr(export, "MAX_SITE_RESPONSES", 1)
    assert main(["export-site", "--project", str(tmp_path), "--include-research", "--preflight", "--json"]) == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["ok"] is False and report["files_written"] is False
    assert report["limit"] == "research_response_count"
    assert file_bytes(tmp_path) == before


def test_native_preflight_limit_has_same_structured_diagnostic(tmp_path, monkeypatch):
    import lixity.site_export as export
    from lixity.server.pdf_context import manuscript_pdf_token
    from tests.support import recording_handler

    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    api.init(tmp_path, title="Synthetic")
    handler = recording_handler(tmp_path, source_input=manuscript, research_project=tmp_path)
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title, thresholds=handler.thresholds)
    before = file_bytes(tmp_path)
    monkeypatch.setattr(export, "MAX_SITE_RESPONSES", 1)
    handler._handle_site_preflight({"project_token": token, "include_research": True, "include_source_files": False})
    status, response = handler.response
    assert status == 413 and response["ok"] is False
    assert response["preflight"]["limit"] == "research_response_count"
    assert response["preflight"]["files_written"] is False
    assert file_bytes(tmp_path) == before


def test_export_limit_never_creates_destination(tmp_path, monkeypatch):
    import lixity.site_export as export

    project = tmp_path / "project"
    project.mkdir()
    (project / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (project / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    api.init(project, title="Synthetic")
    before = file_bytes(project)
    destination = tmp_path / "destination"
    monkeypatch.setattr(export, "MAX_SITE_RESPONSES", 1)
    with pytest.raises(export.SiteExportLimitError):
        export.export_site(project, destination, include_research=True)
    assert not destination.exists() and file_bytes(project) == before


def test_cli_byte_limit_reports_a_lower_bound_instead_of_fake_package_totals(tmp_path, capsys, monkeypatch):
    import lixity.site_export as export
    from lixity.research.repository import Repository

    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    api.init(tmp_path, title="Synthetic")
    for index in range(6):
        api.create_dossier(tmp_path, f"Notes {index}", "Synthetic notes. " * 100)
    repository = Repository(tmp_path)
    snapshot = repository.snapshot()
    record_bytes = sum(repository.record_path(entry).stat().st_size for entry in snapshot.manifest.entries)
    cap = record_bytes + 8192
    before = file_bytes(tmp_path)
    monkeypatch.setattr(export, "MAX_SITE_DATA_BYTES", cap)
    assert main(["export-site", "--project", str(tmp_path), "--include-research", "--preflight", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["limit"] == "research_response_bytes"
    assert report["limit_bytes"] == cap
    assert report["observed_bytes"] == report["accepted_bytes"] + report["response_bytes"]
    assert report["measurement"] == "first_limit_crossing" and report["complete"] is False
    assert "sizes" not in report and file_bytes(tmp_path) == before


def test_bundle_limit_is_reported_separately_from_research_limits(tmp_path, monkeypatch):
    import lixity.site_export as export

    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    monkeypatch.setattr(export, "MAX_SITE_BYTES", 1024)
    with pytest.raises(export.SiteExportLimitError) as caught:
        export.prepare_site(tmp_path).preflight()
    report = caught.value.diagnostic
    assert report["limit"] == "bundle_bytes" and report["limit_bytes"] == 1024
    assert report["observed_bytes"] > 1024


def test_preflight_measures_prepared_files_and_zip_without_project_writes(tmp_path):
    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    before = file_bytes(tmp_path)
    bundle = prepare_site(tmp_path)
    report = bundle.preflight()
    assert report["schema_version"] == "lixity-site-preflight/1"
    assert report["sizes"]["html_bytes"] == len(bundle.files["index.html"])
    assert report["sizes"]["total_bytes"] == sum(map(len, bundle.files.values()))
    assert report["sizes"]["zip_bytes"] == len(bundle.to_zip())
    assert report["mobile_layout_check"] == "not_run"
    assert file_bytes(tmp_path) == before


def test_preflight_reports_unpackaged_media_and_credit_presence(tmp_path):
    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    api.init(tmp_path, title="Synthetic")
    dossier = api.create_dossier(tmp_path, "Notes", "![Loose](unreadable.png)\n")["dossier_id"]
    current = api.get_dossier(tmp_path, dossier)
    api.attach_dossier_image(tmp_path, dossier, png(), filename="sample.png", allow_retention=True,
        expected_snapshot=current["snapshot"], expected_revision=current["revision"])
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    before = file_bytes(tmp_path)
    report = prepare_site(tmp_path, include_research=True).preflight()
    assert report["media"]["references"] == 1
    assert report["media"]["not_packaged"] == 1
    assert report["media"]["missing_attribution"] == 1
    assert report["media"]["ordinary_image_references"] == 2  # Both exported dossier revisions.
    assert "media_not_packaged" in report["warnings"]
    packaged = prepare_site(tmp_path, include_research=True, include_source_files=True).preflight()
    assert packaged["media"]["not_packaged"] == 0
    assert packaged["sizes"]["source_file_bytes"] == len(png())
    assert file_bytes(tmp_path) == before


def test_cli_preflight_requires_no_output_and_never_creates_a_directory(tmp_path, capsys):
    (tmp_path / "manuscript.md").write_text("## One\n\nSynthetic prose.\n")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n')
    before = file_bytes(tmp_path)
    assert main(["export-site", "--project", str(tmp_path), "--preflight", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["sizes"]["zip_bytes"] > 0
    assert file_bytes(tmp_path) == before


def test_native_preflight_uses_same_context_guard_without_download(tmp_path):
    from lixity.server.pdf_context import manuscript_pdf_token
    from tests.support import recording_handler

    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = recording_handler(tmp_path, source_input=manuscript)
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title, thresholds=handler.thresholds)
    before = file_bytes(tmp_path)
    payload = {"project_token": token, "include_research": False, "include_source_files": False}
    handler._handle_site_preflight(payload)
    assert handler.response[0] == 200
    report = handler.response[1]
    assert report["ok"] and report["preflight"]["sizes"]["zip_bytes"] > 0
    assert file_bytes(tmp_path) == before
    handler.__class__.language = "de"
    handler._handle_site_preflight(payload)
    assert handler.response[0] == 409
    assert file_bytes(tmp_path) == before


def test_native_preflight_applies_the_actual_download_limit(tmp_path):
    from unittest.mock import patch

    from lixity.server.pdf_context import manuscript_pdf_token
    from tests.support import recording_handler

    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## One\n\nSynthetic prose.\n")
    handler = recording_handler(tmp_path, source_input=manuscript)
    token = manuscript_pdf_token(handler.source_input, project_root=handler.workspace_root,
                                 language=handler.language, title=handler.title, thresholds=handler.thresholds)
    with patch('lixity.server.routes_site.MAX_ARTIFACT_BYTES', 1):
        handler._handle_site_preflight({"project_token":token, "include_research":False, "include_source_files":False})
    assert handler.response[0] == 413
