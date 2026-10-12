"""Synthetic export history and stable publication failure regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.publishing import prune_archive, update_stable_link
from lixity.workspace import Workspace


def test_same_instant_changed_exports_retain_every_version_and_latest_stable(tmp_path):
    workspace = Workspace(str(tmp_path), str(tmp_path / "manuscript.md"))
    fixed_time = datetime(2026, 10, 12, 10, 15, tzinfo=timezone.utc)
    with patch("lixity.workspace.datetime") as clock:
        clock.now.return_value = fixed_time
        for content in ("First version.\n", "Second version.\n", "Third version.\n"):
            assert workspace.publish("example_report.md", content) is True
        assert workspace.publish("example_report.md", "Third version.\n") is False
    stable = Path(workspace.artifact_path("example_report.md"))
    assert stable.read_text(encoding="utf-8") == "Third version.\n"
    archived = sorted(Path(workspace.archive_dir).glob("example_report_*.md"))
    assert [path.read_text(encoding="utf-8") for path in archived] == [
        "First version.\n", "Second version.\n",
    ]
    current = list(Path(workspace.exports_dir).glob("example_report_*.md"))
    assert len(current) == 1
    assert current[0].read_text(encoding="utf-8") == "Third version.\n"


def test_same_instant_archive_pruning_keeps_latest_ten_versions(tmp_path):
    workspace = Workspace(str(tmp_path), str(tmp_path / "manuscript.md"))
    fixed_time = datetime(2026, 10, 12, 10, 15, tzinfo=timezone.utc)
    with patch("lixity.workspace.datetime") as clock:
        clock.now.return_value = fixed_time
        for version in range(16):
            assert workspace.publish("example_report.md", f"Version {version}.\n") is True
    archived = sorted(Path(workspace.archive_dir).glob("example_report_*.md"))
    assert [path.read_text(encoding="utf-8") for path in archived] == [
        f"Version {version}.\n" for version in range(5, 15)
    ]
    assert Path(workspace.artifact_path("example_report.md")).read_text() == "Version 15.\n"


@pytest.mark.parametrize("copy_fallback", [False, True])
def test_stable_replace_failure_preserves_old_artifact_and_cleans_staging(tmp_path, copy_fallback):
    stable = tmp_path / "example.pdf"
    stable.write_bytes(b"old synthetic PDF bytes\x00\xff")
    source = tmp_path / "example_version.pdf"
    source.write_bytes(b"new synthetic PDF bytes\x00\xfe")
    with patch("lixity.publishing.os.replace", side_effect=OSError("replace failed")):
        if copy_fallback:
            with patch("lixity.publishing.os.symlink", side_effect=NotImplementedError):
                assert update_stable_link(str(stable), str(source)) is False
        else:
            assert update_stable_link(str(stable), str(source)) is False
    assert stable.read_bytes() == b"old synthetic PDF bytes\x00\xff"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["example.pdf", "example_version.pdf"]


def test_failed_copy_fallback_preserves_old_stable(tmp_path):
    stable = tmp_path / "example.pdf"
    stable.write_bytes(b"old synthetic PDF bytes")
    source = tmp_path / "example_version.pdf"
    source.write_bytes(b"new synthetic PDF bytes")
    with (
        patch("lixity.publishing.os.symlink", side_effect=NotImplementedError),
        patch("lixity.publishing.shutil.copyfile", side_effect=OSError("copy failed")),
    ):
        assert update_stable_link(str(stable), str(source)) is False
    assert stable.read_bytes() == b"old synthetic PDF bytes"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["example.pdf", "example_version.pdf"]


def test_successful_copy_fallback_publishes_exact_binary_bytes(tmp_path):
    stable = tmp_path / "example.pdf"
    stable.write_bytes(b"old synthetic PDF bytes")
    source = tmp_path / "example_version.pdf"
    source.write_bytes(bytes(range(256)))
    with patch("lixity.publishing.os.symlink", side_effect=NotImplementedError):
        assert update_stable_link(str(stable), str(source)) is True
    assert stable.read_bytes() == bytes(range(256))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["example.pdf", "example_version.pdf"]


def test_workspace_reports_failed_stable_publication_without_archiving_old_target(tmp_path):
    workspace = Workspace(str(tmp_path), str(tmp_path / "manuscript.md"))
    assert workspace.publish("example_report.md", "Original version.\n") is True
    stable = Path(workspace.artifact_path("example_report.md"))
    original_versions = set(Path(workspace.exports_dir).glob("example_report_*.md"))
    with (
        patch("lixity.workspace.update_stable_link", return_value=False),
        pytest.raises(OSError, match="stable"),
    ):
        workspace.publish("example_report.md", "Updated version.\n")
    assert stable.read_text(encoding="utf-8") == "Original version.\n"
    assert all(path.exists() for path in original_versions)
    assert list(Path(workspace.archive_dir).iterdir()) == []


def test_new_and_legacy_timestamp_names_remain_one_archive_family(tmp_path):
    names = [
        "example_report_2026-01-01_10-00.md",
        "example_report_2026-01-02_10-00-00-000000.md",
        "example_report_2026-01-02_10-00-00-000000_000001.md",
    ]
    for name in names:
        (tmp_path / name).write_text("Synthetic export.\n", encoding="utf-8")
    assert prune_archive(str(tmp_path), keep_last=2) == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == names[1:]
