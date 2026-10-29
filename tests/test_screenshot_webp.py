"""Screenshot capture stages PNG input for reviewed WebP output."""

from pathlib import Path

from scripts.make_screenshots import _queue_capture, _reviewed_capture_name


def test_webp_capture_uses_png_staging_and_keeps_reviewed_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.make_screenshots.WORK_DIR", tmp_path)
    monkeypatch.setattr("scripts.make_screenshots.CAPTURES", [])
    import scripts.make_screenshots as screenshots

    _queue_capture(tmp_path / "input.html", tmp_path / "dashboard-dossier-photo.webp", 100, 100)
    capture = screenshots.CAPTURES[0]
    assert Path(str(capture["target"])).suffix == ".png"
    assert _reviewed_capture_name(capture) == "dashboard-dossier-photo.webp"
