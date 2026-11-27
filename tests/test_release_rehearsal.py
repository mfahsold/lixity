"""Release evidence records the observed source and comparable corpus results."""

import json
import shutil
import subprocess

import pytest

from scripts import run_release_rehearsal as rehearsal
from scripts.build_evidence import build_output_parent, source_state


@pytest.fixture
def checkout(tmp_path):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git is required for build evidence")
    root = tmp_path / "source"
    root.mkdir()
    (root / ".gitignore").write_text("/.artifacts/\n", encoding="utf-8")
    for args in (("init",), ("add", ".gitignore"), (
        "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "-c", "commit.gpgsign=false", "commit", "-m", "Add ignore rules",
    )):
        subprocess.run([git, *args], cwd=root, check=True, capture_output=True)  # noqa: S603
    return root


def test_source_state_hashes_same_name_untracked_edits_and_ignores_output(checkout):
    assert source_state(checkout)["dirty"] is False
    new_source = checkout / "new module.py"
    new_source.write_text("x = 1\n", encoding="utf-8")
    before = source_state(checkout)
    assert before["dirty"] is True
    new_source.write_text("x = 2\n", encoding="utf-8")
    after = source_state(checkout)
    assert before["status_sha256"] == after["status_sha256"]
    assert before["tracked_diff_sha256"] == after["tracked_diff_sha256"]
    assert before["untracked_files_sha256"] != after["untracked_files_sha256"]
    (checkout / ".artifacts").mkdir()
    (checkout / ".artifacts/results.json").write_text("ignored", encoding="utf-8")
    assert source_state(checkout) == after


def test_build_output_root_precedence_and_git_boundary(checkout, tmp_path, monkeypatch):
    default = checkout / ".artifacts/release-rehearsal"
    monkeypatch.delenv("LIXITY_BUILD_OUTPUT_ROOT", raising=False)
    assert build_output_parent(checkout, default, None) == default.resolve()
    outside = (tmp_path / "shared evidence").resolve()
    monkeypatch.setenv("LIXITY_BUILD_OUTPUT_ROOT", str(outside))
    assert build_output_parent(checkout, default, None) == outside / "release-rehearsal"
    explicit = checkout / ".artifacts/shared"
    assert build_output_parent(checkout, default, explicit) == explicit.resolve() / "release-rehearsal"
    with pytest.raises(ValueError, match="Git-ignored build output"):
        build_output_parent(checkout, default, checkout / "docs")


def test_rehearsal_rejects_dirty_promotion_before_creating_artifacts(checkout, monkeypatch):
    monkeypatch.setattr(rehearsal, "ROOT", checkout)
    (checkout / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    dist = checkout / "dist"
    with pytest.raises(ValueError, match="clean checkout of the reviewed commit"):
        rehearsal.rehearse(jobs=1, tag=None, dist=dist, skip_wheel=False)
    assert not dist.exists()
    assert not (checkout / ".artifacts").exists()


@pytest.mark.parametrize("drift", ["none", "before wheel", "after wheel"])
def test_rehearsal_keeps_independent_results_and_skips_drifted_candidate(
    tmp_path, checkout, monkeypatch, drift,
):
    monkeypatch.setattr(rehearsal, "ROOT", checkout)
    monkeypatch.setattr(rehearsal, "source_version", lambda *_: "0.9.3")
    clean = {"commit": "a" * 40, "dirty": False}
    changed = {**clean, "dirty": True}
    states = iter([clean, changed if drift == "before wheel" else clean,
                   clean if drift == "none" else changed])
    monkeypatch.setattr(rehearsal, "source_state", lambda _: next(states))
    for name in ("samples/first-look.md", "scripts/example_project.py", "tests/fixtures/literary_reference.json"):
        fixture = checkout / name
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(name, encoding="utf-8")
    called, promotions = [], []

    def observe(directory, receipt, name, command, **_):
        called.append(name)
        receipt["stages"][name]["status"] = "passed"
        if name == "wheel":
            dist = directory / "dist"
            assert str(dist) in command
            dist.mkdir()
            (dist / "SHA256SUMS").write_text(f"{'b' * 64}  lixity-0.9.3.whl\n", encoding="ascii")
        return True

    monkeypatch.setattr(rehearsal, "run_stage", observe)
    monkeypatch.setattr(rehearsal, "promote_artifacts", lambda *args: promotions.append(args))
    final_dist = tmp_path / "final-dist"
    output_root = tmp_path / "shared"
    result = rehearsal.rehearse(jobs=1, tag=None, dist=final_dist, skip_wheel=False,
                                output_root=output_root)
    run, = (output_root / "release-rehearsal").iterdir()
    receipt = rehearsal.read_receipt(run)
    assert result == int(drift != "none")
    assert receipt["stages"]["browser"]["status"] == receipt["stages"]["corpus"]["status"] == "passed"
    if drift != "none":
        assert receipt["reviewed_commit"] is None
        assert receipt["promotion"] == "not_run"
        assert promotions == []
        if drift == "before wheel":
            assert called == ["browser", "corpus"]
            assert receipt["stages"]["wheel"]["status"] == "not_run"
        else:
            assert called == ["browser", "corpus", "wheel"]
            assert receipt["stages"]["wheel"]["status"] == "passed"
    else:
        assert receipt["reviewed_commit"] == clean["commit"]
        assert called == ["browser", "corpus", "wheel"]
        assert receipt["wheel_checksums"] == {"lixity-0.9.3.whl": "b" * 64}
        assert receipt["promotion"] == "passed"
        assert promotions == [(checkout, run / "dist", final_dist, None)]


def test_comparison_rejects_different_inputs_and_separates_timing_environment(tmp_path, capsys):
    previous, current, other_platform = [tmp_path / name for name in ("base", "current", "other")]
    for directory, adjusted, platform in (
        (previous, False, "Darwin"), (current, True, "Darwin"), (other_platform, True, "Linux"),
    ):
        directory.mkdir()
        rehearsal.write_receipt(directory, {
            "schema_version": rehearsal.SCHEMA, "version": "0.9.3", "source": {"commit": "a" * 40},
            "fixtures": {"example": "changed" if adjusted else "original"},
            "stages": {name: {"status": "passed"} for name in rehearsal.STAGES},
        })
        corpus = {
            "python": "3.12.1", "machine": "arm64", "platform": platform,
            "mode": "workspace", "iterations": 3,
            "results": [
                {"file": "sample.md", "language": "en", "source_sha256": "same",
                 "digests": {"workspace": str(adjusted)}, "median_ms": {"total": 12 if adjusted else 10}},
                {"file": "changed.md", "language": "de", "source_sha256": str(adjusted),
                 "digests": {"workspace": "same"}, "median_ms": {"total": 30}},
            ],
        }
        (directory / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")

    rehearsal.compare(previous, current)
    report = capsys.readouterr().out
    assert "Fixture changed: example" in report
    assert "sample.md (en): result digest changed" in report
    assert "10.00 -> 12.00 ms" in report
    assert "changed.md (de): input changed or has no baseline" in report
    assert "30.00" not in report

    rehearsal.compare(previous, other_platform)
    report = capsys.readouterr().out
    assert "Timing comparison unavailable" in report
    assert "sample.md (en): result digest changed" in report
    assert "10.00 ->" not in report
