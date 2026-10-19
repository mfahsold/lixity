"""Settings retain project author identity without rewriting manuscript data."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.io import FileUtils
from lixity.server import views
from lixity.server.views import build_server_dashboard
from tests.support import HtmlControls, make_handler, recording_handler


def test_loaded_project_view_uses_author_and_read_only_identity_check(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    text = "# Synthetic Project\n\nvon Synthetic Author\n\n## Scene\n\nPublic synthetic prose.\n"
    manuscript.write_text(text, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert 'id="set-author-name"' in html
    assert 'value="Synthetic Author"' in html
    assert info["identity_check"]["author_name"]["status"] == "matched"
    assert info["identity_check"]["title"]["status"] == "matched"
    assert manuscript.read_text(encoding="utf-8") == text


@pytest.mark.parametrize("research_only,author", [
    (False, "Synthetic Author"), (False, ""), (True, "Research Author"),
])
def test_settings_save_persists_only_author_in_the_explicit_project(tmp_path: Path, research_only: bool, author: str):
    manuscript = tmp_path / "manuscript.md"
    text = "# Synthetic Project\n\n## Scene\n\nPublic synthetic prose.\n"
    manuscript.write_text(text, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Before"\n', encoding="utf-8")
    if research_only:
        (tmp_path / "research").mkdir()
    handler = recording_handler(tmp_path, source_input=None if research_only else manuscript,
                                research_dir=tmp_path if research_only else None,
                                title="Synthetic Project")
    before = handler.thresholds
    handler._handle_settings({"author_name": author, "language": "de"})
    assert handler.response[0] == 200
    from lixity.config import load_project_config
    assert load_project_config(tmp_path)["author_name"] == author
    assert handler.thresholds == before
    assert handler.title == "Synthetic Project"
    assert manuscript.read_text(encoding="utf-8") == text


def test_no_project_rejects_author_persistence_without_mutating_session(tmp_path: Path):
    # An archive in the idle working directory is not an explicitly open project.
    (tmp_path / "research").mkdir()
    handler = recording_handler(tmp_path)
    handler._handle_settings({"author_name": "Synthetic Author", "language": "de"})
    assert handler.response[0] == 400
    assert handler.language == "en"
    assert not (tmp_path / "lixity.toml").exists()



def test_project_identity_stays_at_selected_root_for_nested_manuscript(tmp_path: Path):
    nested = tmp_path / "exports" / "manuscripts"
    nested.mkdir(parents=True)
    manuscript = nested / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\nby Project Writer\n\n## Scene\n\nSynthetic prose.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Project Writer"\n', encoding="utf-8")
    (nested / "lixity.toml").write_text('author_name = "Other Writer"\n', encoding="utf-8")

    handler = make_handler(tmp_path, source_input=manuscript)
    assert handler.get_author_project_root() == tmp_path
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", project_root=tmp_path)
    assert 'value="Project Writer"' in html
    assert info["identity_check"]["author_name"]["status"] == "matched"


def test_invalid_configured_author_does_not_abort_analysis_view(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\n## Scene\n\nPublic synthetic prose.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text("author_name = true\n", encoding="utf-8")
    html, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert "Synthetic Project" in html
    assert info["identity_check"]["author_name"]["status"] == "unsupported"


def test_missing_manuscript_keeps_project_author_without_claiming_a_match(tmp_path: Path):
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    html, info = build_server_dashboard(str(tmp_path / "missing.md"), title="Synthetic Project", language="en")
    assert 'value="Synthetic Author"' in html
    assert info["identity_check"]["author_name"]["status"] == "unavailable"


def test_unreadable_manuscript_reports_unavailable_identity(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic Project\n\nby Synthetic Author\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('author_name = "Synthetic Author"\n', encoding="utf-8")
    with patch("lixity.server.views.FileUtils.read_source_snapshot", side_effect=PermissionError("Synthetic read failure")):
        _, info = build_server_dashboard(str(manuscript), title="Synthetic Project", language="en")
    assert info["identity_check"]["title"]["status"] == "unavailable"
    assert info["identity_check"]["author_name"]["status"] == "unavailable"


def test_nda_default_uses_the_same_resolved_h1_as_the_project_header(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic target title\n\n## Morning\n\nA synthetic sentence.\n", encoding="utf-8")
    html, _ = build_server_dashboard(str(manuscript), project_root=tmp_path, language="en")
    assert '<h1>Synthetic target title</h1>' in html
    assert HtmlControls(html).elements["nda-project-name"]["value"] == "Synthetic target title"


def test_project_open_reads_the_manuscript_once_through_the_shared_snapshot_reader(tmp_path: Path):
    source = tmp_path / "target.md"
    source.write_text("# Synthetic target\n\n## Morning\n\nA synthetic sentence.\n", encoding="utf-8")

    handler = recording_handler(tmp_path / "previous")
    reads = []
    path_read = Path.read_text
    snapshot_read = FileUtils.read_source_snapshot

    def reading_path(path, *args, **kwargs):
        if path == source:
            reads.append("path")
        return path_read(path, *args, **kwargs)

    def reading_snapshot(path, *args, **kwargs):
        if Path(path) == source:
            reads.append("snapshot")
        return snapshot_read(path, *args, **kwargs)

    with patch.object(Path, "read_text", reading_path), patch.object(FileUtils, "read_source_snapshot", reading_snapshot):
        handler._handle_project_open({"path": str(source)})
    assert handler.response[0] == 200
    assert reads == ["snapshot"]


def test_dashboard_reads_shared_project_configuration_once(tmp_path: Path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic title\n\n## Morning\n\nA synthetic sentence.\n", encoding="utf-8")
    calls: list[str | None] = []
    original = views.load_project_config

    def counting(start=None):
        calls.append(str(start) if start is not None else None)
        return original(start)

    with patch.object(views, "load_project_config", counting):
        build_server_dashboard(str(manuscript), project_root=tmp_path, language="en")
    assert calls == [str(manuscript)]
