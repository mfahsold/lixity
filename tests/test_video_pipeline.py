"""The homepage transcript and published video share one complete timeline."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import make_videos
from scripts.build_public_site import render_pages

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
MEDIA_TOOLS = FFMPEG and FFPROBE


def test_all_homepage_transcripts_follow_the_full_48_second_tour() -> None:
    for name, page in render_pages().items():
        starts = [int(value) for value in re.findall(r'<li data-start="(\d+)">', page)]
        assert starts == [0, 8, 16, 24, 32, 40], name
        title = re.search(r'<video[^>]+aria-label="([^"]+)"', page)
        assert title and "48" in title.group(1), name


@pytest.fixture
def short_tour_recording(
    tmp_path: Path, monkeypatch,
) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    source = raw / "product-tour.webm"
    assert FFMPEG
    subprocess.run(  # noqa: S603 - fixed synthetic media fixture invocation
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=160x100:rate=25",
         "-t", "0.4", "-c:v", "libvpx", str(source)], check=True,
    )
    ids = [scene["id"] for scene in make_videos._tour_plan()["scenes"]]
    timing = {
        "schema_version": "lixity-product-tour-recording/1", "fps": 25, "duration": 48,
        "segments": [{"id": name, "file": source.name, "startFrame": 2, "frames": 200,
                      "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                     for name in ids],
        # The old pipeline accepts this contradictory short source.
        "trim": 0,
        "scenes": [{"name": name, "start": index * 8, "x": .5, "y": .5, "zoom": 1}
                   for index, name in enumerate(ids)],
    }
    source.with_suffix(".json").write_text(json.dumps(timing), encoding="utf-8")
    monkeypatch.setattr(make_videos, "RAW_DIR", raw)
    monkeypatch.setattr(make_videos, "OUT_DIR", tmp_path / "output")
    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    return source


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
def test_encoder_rejects_a_source_without_eight_seconds_after_its_anchor(
    short_tour_recording: Path,
) -> None:
    assert short_tour_recording.is_file()
    with pytest.raises(SystemExit, match=r"needs .* frames"):
        make_videos.convert_product_tour()


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
def test_encoder_rejects_raw_bytes_changed_after_the_frame_anchor_was_measured(
    short_tour_recording: Path,
) -> None:
    with short_tour_recording.open("ab") as source:
        source.write(b"Changed after capture")
    with pytest.raises(SystemExit, match="source hash mismatch"):
        make_videos.convert_product_tour()


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
def test_export_validation_rejects_non_square_pixels(tmp_path: Path, monkeypatch) -> None:
    assert FFMPEG
    source = tmp_path / "stretched.mp4"
    subprocess.run(  # noqa: S603 - fixed synthetic media fixture invocation
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=160x100:rate=25",
         "-vf", "setsar=2", "-t", "0.4", "-c:v", "libx264", str(source)], check=True,
    )
    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    with pytest.raises(SystemExit, match="unexpected geometry"):
        make_videos._verify_export(source, fps=25, frames=10, width=160, height=100)


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
@pytest.mark.parametrize(
    ("filename", "frames", "width", "height"),
    [("product-tour.mp4", 1200, 1440, 900), ("product-tour.webm", 1200, 1440, 900),
     ("social-hook-16x9.mp4", 300, 1600, 900), ("social-hook-9x16.mp4", 300, 1080, 1920)],
)
def test_published_video_has_complete_constant_frame_timing_and_geometry(
    filename: str, frames: int, width: int, height: int,
) -> None:
    path = Path(__file__).resolve().parents[1] / "docs" / "videos" / filename
    assert FFPROBE
    result = subprocess.run(  # noqa: S603 - fixed local published video validation
        [FFPROBE, "-v", "error", "-count_frames", "-show_streams", "-show_format",
         "-of", "json", str(path)], check=True, capture_output=True, text=True,
    )
    media = json.loads(result.stdout)
    assert len(media["streams"]) == 1, "The tour must remain silent"
    video = media["streams"][0]
    assert (video["width"], video["height"]) == (width, height)
    assert video["sample_aspect_ratio"] == "1:1"
    assert video["avg_frame_rate"] == "25/1"
    assert int(video["nb_read_frames"]) == frames
    assert float(media["format"]["duration"]) == pytest.approx(frames / 25, abs=.002)
    assert int(media["format"]["size"]) <= 4_000_000
