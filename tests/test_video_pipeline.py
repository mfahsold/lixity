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
from scripts.product_tour_edit import (
    MAX_CSS_SCALE,
    Take,
    _take,
    inspect_cut_plan,
    prepare_project_path,
    prune_stale_tour_artifacts,
)

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
MEDIA_TOOLS = FFMPEG and FFPROBE
PUBLISHED_VIDEOS = Path(__file__).resolve().parents[1] / "docs" / "videos"


def test_reframing_uses_settled_footage_and_keeps_the_cue_duration() -> None:
    segment = {"id": "reader", "startFrame": 1000, "frames": 225}
    assert _take(segment, {"sourceSeconds": 0}, scene_frame=1350, begin=0, end=29,
                 destination_frames=175, rate=25) == Take(1350, 1379, 1000, 1)
    assert _take(segment, {"sourceSeconds": 1.84}, scene_frame=1350, begin=29, end=175,
                 destination_frames=175, rate=25) == Take(1379, 1525, 1047, 0)
    comparison = {"id": "compare", "startFrame": 832, "frames": 300}
    assert _take(comparison, {"sourceSeconds": 3.061, "comparison": {"current": {}}},
                 scene_frame=650, begin=75, end=133, destination_frames=250, rate=25) == Take(725, 783, 910, 2)
    assert _take(comparison, {"sourceSeconds": 3.0, "noBuffer": True, "comparison": {"current": {}}},
                 scene_frame=650, begin=75, end=133, destination_frames=250, rate=25) == Take(725, 783, 907, 1)


def test_all_homepage_transcripts_follow_the_full_tour() -> None:
    plan = make_videos._tour_plan()
    for name, page in render_pages().items():
        starts = [int(value) for value in re.findall(r'<li data-start="(\d+)">', page)]
        assert starts == [scene["start"] for scene in plan["scenes"]], name
        title = re.search(r'<video[^>]+aria-label="([^"]+)"', page)
        assert title and str(plan["duration"]) in title.group(1), name


@pytest.fixture
def short_tour_recording(
    tmp_path: Path, monkeypatch,
) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    source = raw / "product-tour.webm"
    assert FFMPEG
    subprocess.run(  # noqa: S603 - fixed synthetic media fixture invocation
        [FFMPEG, "-v", "error", "-f", "lavfi", "-i", "color=size=2880x1800:rate=25",
         "-t", "0.4", "-c:v", "libvpx", str(source)], check=True,
    )
    plan = make_videos._tour_plan()
    timing = {
        "schema_version": "lixity-product-tour-recording/5", "fps": plan["fps"], "duration": plan["duration"],
        "segments": [{"id": scene["id"], "theme": scene["theme"], "file": source.name, "startFrame": 2,
                      "frames": scene["record_duration"] * plan["fps"],
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


@pytest.mark.parametrize("first_gif_size", [3, 5])
def test_guide_retries_gif_only_when_over_budget(tmp_path: Path, monkeypatch, first_gif_size: int) -> None:
    source = tmp_path / "guide.webm"
    source.write_bytes(b"synthetic guide take")
    source.with_suffix(".json").write_text(json.dumps({
        "schema_version": "lixity-guide-recording/1", "file": source.name, "startFrame": 2,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    output = tmp_path / "output"
    gif_filters: list[str] = []

    def fake_encode(command: list[str]) -> None:
        target = Path(command[-1])
        size = 3
        if target.suffix == ".gif":
            if not gif_filters:
                size = first_gif_size
            gif_filters.append(command[command.index("-vf") + 1])
        target.write_bytes(b"x" * size)

    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "RAW_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "OUT_DIR", output)
    monkeypatch.setattr(make_videos.shutil, "which", lambda name: name)
    monkeypatch.setattr(make_videos, "_video_info", lambda _: ({"avg_frame_rate": "25/1", "nb_read_frames": "50"}, {}))
    monkeypatch.setattr(make_videos, "run", fake_encode)
    make_videos.convert("guide", "1", max_mp4=4, max_gif=4)

    assert (output / "guide.gif").stat().st_size == 3
    assert len(gif_filters) == (1 if first_gif_size <= 4 else 2)
    assert "paletteuse=dither=bayer" in gif_filters[0]
    if len(gif_filters) == 2:
        assert "max_colors=192" in gif_filters[1]
        assert "paletteuse=dither=none" in gif_filters[1]
    assert all("trim=start_frame=2,setpts=PTS-STARTPTS,fps=10,scale=800:" in filters for filters in gif_filters)


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
    source = tmp_path / make_videos.ICON
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"test artwork")
    recording = {"segments": []}
    (tmp_path / "product-tour.json").write_text(json.dumps(recording), encoding="utf-8")
    rendered = []

    class FakeEdit:
        def __init__(self, _project, width, height, _fps):
            rendered.append((width, height))

        def export_markers(self, path, plan):
            assert plan == make_videos._tour_plan()
            path.write_bytes(b"FilmCraft marker report")

        def render(self, frames, *, duration):
            assert duration == make_videos._tour_plan()["duration"]
            self.review_frames = [0, duration * 25 - 1]
            return frames / "frame%04d.png"

    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "OUT_DIR", output)
    monkeypatch.setattr(make_videos, "RAW_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "_tour_recordings", lambda _plan: (recording, []))
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
    expected_frames = [0, make_videos._tour_plan()["duration"] * 25 - 1]
    assert receipt["review_frames"][master] == receipt["review_frames"][alias] == expected_frames
    assert (horizontal in receipt["review_frames"]) == (selection == "social")
    marker_reports = receipt["filmcraft_marker_reports_sha256"]
    assert len(marker_reports) == len(rendered)
    assert all(hashlib.sha256((receipt_path.parent / name).read_bytes()).hexdigest() == digest
               for name, digest in marker_reports.items())
    assert receipt["selection"] == selection
    assert "product-tour-timing.json" in receipt["inputs_sha256"]


def test_prepare_project_path_and_prune_stale_artifacts(tmp_path: Path) -> None:
    review = tmp_path / "warehouse-4-tour"
    review.mkdir()
    old_proj = review / "warehouse-4-1440x900.fcproj"
    old_lock = review / ".warehouse-4-1440x900.fcproj.lock"
    stale_receipt = review / "receipt-abc12345.json"
    keep_receipt = review / "receipt-product-tour.json"
    stale_marker = review / "warehouse-4-1440x900-markers-abc12345.csv"
    keep_marker = review / "warehouse-4-1440x900-markers.csv"
    for path in (old_proj, old_lock, stale_receipt, keep_receipt, stale_marker, keep_marker):
        path.write_text("x", encoding="utf-8")

    prepared = prepare_project_path(review, 1440, 900)
    assert prepared == old_proj
    assert not old_proj.exists()
    assert not old_lock.exists()

    removed = prune_stale_tour_artifacts(
        review,
        keep_receipts={"receipt-product-tour.json"},
        keep_markers={"warehouse-4-1440x900-markers.csv"},
    )
    assert {path.name for path in removed} == {"receipt-abc12345.json", "warehouse-4-1440x900-markers-abc12345.csv"}
    assert keep_receipt.exists()
    assert keep_marker.exists()


def test_inspect_cut_plan_enforces_2x_scale_cap_and_low_holds() -> None:
    plan = make_videos._tour_plan()
    footage = [
        (
            {
                "id": cap["id"],
                "startFrame": 100,
                "frames": cap["record_duration"] * plan["fps"],
                "sourceSize": (2880, 1800),
                "actionEnd": cap["duration"] - 2,
                "focus": [
                    {"seconds": 0, "sourceSeconds": 0, "x": 100, "y": 100, "width": 200, "height": 50},
                    {"seconds": 2.0, "sourceSeconds": 2.04, "x": 50, "y": 50, "width": 600, "height": 400},
                ],
            },
            Path("product-tour.webm"),
            Path("still.png"),
        )
        for cap in plan["captures"]
    ]
    rows = inspect_cut_plan(plan, footage, width=1440, height=900, fps=plan["fps"])
    assert len(rows) == 2 * len(plan["captures"])
    assert all(row["css_scale"] <= MAX_CSS_SCALE for row in rows)
    assert all(row["physical_scale"] <= 1.0 for row in rows)
    assert all(row["hold_frames"] <= 2 for row in rows)


def test_variant_build_targets_single_layout_and_honors_no_keep_projects(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "videos"
    output.mkdir()
    source = tmp_path / make_videos.ICON
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"test artwork")
    recording = {"segments": []}
    (tmp_path / "product-tour.json").write_text(json.dumps(recording), encoding="utf-8")
    rendered: list[tuple[int, int]] = []

    class FakeEdit:
        def __init__(self, project: Path, width: int, height: int, _fps: int):
            self.project = project
            project.write_text("fcproj", encoding="utf-8")
            project.with_name(f"{project.stem}-cuts").mkdir(exist_ok=True)
            rendered.append((width, height))

        def export_markers(self, path: Path, _plan: dict) -> None:
            path.write_bytes(b"markers")

        def render(self, frames: Path, *, duration: int) -> Path:
            self.review_frames = [0, duration * 25 - 1]
            return frames / "frame%04d.png"

    monkeypatch.setattr(make_videos, "BASE_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "OUT_DIR", output)
    monkeypatch.setattr(make_videos, "RAW_DIR", tmp_path)
    monkeypatch.setattr(make_videos, "_tour_recordings", lambda _plan: (recording, []))
    monkeypatch.setattr(make_videos, "Edit", FakeEdit)
    monkeypatch.setattr(make_videos, "compose", lambda *_args: None)
    monkeypatch.setattr(make_videos, "run", lambda command: Path(command[-1]).write_bytes(b"new"))
    monkeypatch.setattr(make_videos, "_verify_export", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(make_videos.shutil, "which", lambda name: name)
    monkeypatch.setattr(make_videos, "_tour_tool_versions", lambda tools: dict.fromkeys(tools, "test"))

    make_videos.convert_product_tour(variant="social-16x9", keep_projects=False)
    assert rendered == [(1600, 900)]
    assert (output / make_videos.LANDSCAPE_SOCIAL).is_file()
    assert not (output / make_videos.PORTRAIT_MASTER).exists()
    review = tmp_path / ".artifacts/filmcraft/warehouse-4-tour"
    assert not (review / "warehouse-4-1600x900.fcproj").exists()
    assert not (review / "warehouse-4-1600x900-cuts").exists()
    assert (review / "receipt-social-16x9.json").is_file()


def test_published_portrait_destinations_are_byte_identical() -> None:
    assert (PUBLISHED_VIDEOS / make_videos.PORTRAIT_MASTER).read_bytes() == (
        PUBLISHED_VIDEOS / make_videos.PORTRAIT_SOCIAL
    ).read_bytes()


@pytest.mark.skipif(not MEDIA_TOOLS, reason="ffmpeg and ffprobe are required for video validation")
@pytest.mark.parametrize(
    ("filename", "width", "height"),
    [("product-tour.mp4", 1440, 900), ("product-tour.webm", 1440, 900),
     ("product-tour-portrait.mp4", 1080, 1920),
     ("social-hook-16x9.mp4", 1600, 900), ("social-hook-9x16.mp4", 1080, 1920)],
)
def test_published_video_has_complete_constant_frame_timing_and_geometry(
    filename: str, width: int, height: int,
) -> None:
    plan = make_videos._tour_plan()
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
    assert video["avg_frame_rate"] == f'{plan["fps"]}/1'
    assert int(video["nb_read_frames"]) == plan["duration"] * plan["fps"]
    assert float(media["format"]["duration"]) == pytest.approx(plan["duration"], abs=.002)
    assert int(media["format"]["size"]) <= make_videos.TOUR_VIDEO_LIMITS.get(filename, make_videos.DEFAULT_TOUR_VIDEO_LIMIT)
