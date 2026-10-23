"""Export checks measure the actual package without creating a destination."""

import json

from lixity.cli import main
from lixity.research import api
from lixity.site_export import prepare_site
from tests.test_research_images import png
from tests.test_site_export import file_bytes


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
