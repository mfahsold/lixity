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
PUBLISHED_VIDEOS = Path(__file__).resolve().parents[1] / "docs" / "videos"


def test_all_homepage_transcripts_follow_the_full_minute_tour() -> None:
    for name, page in render_pages().items():
        starts = [int(value) for value in re.findall(r'<li data-start="(\d+)">', page)]
        assert starts == [0, 5, 14, 27, 42, 52], name
        title = re.search(r'<video[^>]+aria-label="([^"]+)"', page)
        assert title and "60" in title.group(1), name


@pytest.fixture
def short_tour_recording(
    tmp_path: Path, monkeypatch,
) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    source = raw / "product-tour.webm"
    assert FFMPEG
    subprocess.run(  # noqa: S603 - fixed synthetic media fixture invocation
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=1440x900:rate=25",
         "-t", "0.4", "-c:v", "libvpx", str(source)], check=True,
    )
    plan = make_videos._tour_plan()
    timing = {
        "schema_version": "lixity-product-tour-recording/3", "fps": plan["fps"], "duration": plan["duration"],
        "segments": [{"id": scene["id"], "theme": scene["theme"], "file": source.name, "startFrame": 2,
                      "frames": scene["duration"] * plan["fps"],
                      "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
                     for scene in plan["captures"]],
    }
    source.with_suffix(".json").write_text(json.dumps(timing), encoding="utf-8")
    monkeypatch.setattr(make_videos, "RAW_DIR", raw)
    monkeypatch.setattr(make_videos, "OUT_DIR", tmp_path / "output")
    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    return source


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
def test_encoder_rejects_a_source_without_the_scene_duration_after_its_anchor(
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


@pytest.mark.parametrize("selection", ["portrait", "social"])
def test_partial_tour_refreshes_one_portrait_and_both_destinations(tmp_path: Path, monkeypatch, selection: str) -> None:
    master = make_videos.PORTRAIT_MASTER
    alias = make_videos.PORTRAIT_SOCIAL
    poster = make_videos.PORTRAIT_POSTER
    horizontal = make_videos.LANDSCAPE_SOCIAL
    output = tmp_path / "videos"
    output.mkdir()
    untouched = output / "product-tour.webm"
    untouched.write_bytes(b"untouched website landscape")
    for name in (master, alias, poster, horizontal):
        (output / name).write_bytes(b"old " + name.encode())
    for asset in (make_videos.RECEIPT, make_videos.LEDGER, make_videos.ICON):
        source = tmp_path / asset
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"test artwork")
    recording = {"segments": [], "exhibitPage": {"file": "exhibit.png", "sha256": "example"}}
    (tmp_path / "product-tour.json").write_text(json.dumps(recording), encoding="utf-8")
    rendered = []

    class FakeEdit:
        def __init__(self, _project, width, height, _fps):
            rendered.append((width, height))

        def render(self, frames, _preview_times):
            return frames / "frame%04d.png"

    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "OUT_DIR", output)
    monkeypatch.setattr(make_videos, "RAW_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "_tour_recordings", lambda _plan: (recording, [], None))
    monkeypatch.setattr(make_videos, "Edit", FakeEdit)
    monkeypatch.setattr(make_videos, "compose", lambda *_args: None)
    monkeypatch.setattr(make_videos, "run", lambda command: Path(command[-1]).write_bytes(b"new " + Path(command[-1]).name.encode()))
    monkeypatch.setattr(make_videos, "_verify_export", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(make_videos.shutil, "which", lambda name: name)
    monkeypatch.setattr(make_videos, "_tour_tool_versions", lambda tools: dict.fromkeys(tools, "test version"))
    make_videos.convert_product_tour(selection)

    if selection == "social":
        assert sorted(rendered) == [(1080, 1920), (1600, 900)]
        assert (output / horizontal).read_bytes() == b"new " + horizontal.encode()
    else:
        assert rendered == [(1080, 1920)]
        assert (output / horizontal).read_bytes() == b"old " + horizontal.encode()
    assert untouched.read_bytes() == b"untouched website landscape"
    assert (output / alias).read_bytes() == (output / master).read_bytes() == b"new " + master.encode()
    assert (output / poster).read_bytes() == b"new " + poster.encode()

    receipt_path, = (tmp_path / ".artifacts/filmcraft/warehouse-4-tour").glob("receipt-*.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    portrait_hash = hashlib.sha256((output / master).read_bytes()).hexdigest()
    assert receipt["outputs_sha256"][master] == receipt["outputs_sha256"][alias] == portrait_hash
    assert receipt["selection"] == selection
    assert "product-tour-timing.json" in receipt["inputs_sha256"]


def test_published_portrait_destinations_are_byte_identical() -> None:
    assert (PUBLISHED_VIDEOS / make_videos.PORTRAIT_MASTER).read_bytes() == (
        PUBLISHED_VIDEOS / make_videos.PORTRAIT_SOCIAL
    ).read_bytes()


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
@pytest.mark.parametrize(
    ("filename", "frames", "width", "height"),
    [("product-tour.mp4", 1500, 1440, 900), ("product-tour.webm", 1500, 1440, 900),
     ("product-tour-portrait.mp4", 1500, 1080, 1920),
     ("social-hook-16x9.mp4", 1500, 1600, 900), ("social-hook-9x16.mp4", 1500, 1080, 1920)],
)
def test_published_video_has_complete_constant_frame_timing_and_geometry(
    filename: str, frames: int, width: int, height: int,
) -> None:
    path = PUBLISHED_VIDEOS / filename
    assert FFPROBE
    result = subprocess.run(  # noqa: S603 - fixed local published video validation
        [FFPROBE, "-v", "error", "-count_frames", "-show_streams", "-show_format",
         "-of", "json", str(path)], check=True, capture_output=True, text=True,
    )
    media = json.loads(result.stdout)
    assert len(media["streams"]) == 1, "The tour must remain silent"
    video = media["streams"][0]
    assert video["codec_name"] == ("av1" if filename.endswith(".webm") else "h264")
    assert (video["width"], video["height"]) == (width, height)
    assert video["sample_aspect_ratio"] == "1:1"
    assert video["color_range"] == "tv"
    assert video["color_space"] == video["color_primaries"] == "bt709"
    assert video["color_transfer"] == "iec61966-2-1"
    assert video["avg_frame_rate"] == "25/1"
    assert int(video["nb_read_frames"]) == frames
    assert float(media["format"]["duration"]) == pytest.approx(frames / 25, abs=.002)
    assert int(media["format"]["size"]) <= make_videos.TOUR_VIDEO_LIMITS.get(filename, make_videos.DEFAULT_TOUR_VIDEO_LIMIT)
