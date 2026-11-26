"""Release evidence records the observed source and comparable corpus results."""

import json

import pytest

from scripts import run_release_rehearsal as rehearsal


@pytest.mark.parametrize("drift", ["none", "before wheel", "after wheel"])
def test_rehearsal_keeps_independent_results_and_skips_drifted_candidate(
    tmp_path, monkeypatch, drift,
):
    monkeypatch.setattr(rehearsal, "ROOT", tmp_path)
    monkeypatch.setattr(rehearsal, "source_version", lambda *_: "0.9.3")
    clean = {"commit": "a" * 40, "dirty": False}
    changed = {**clean, "dirty": True}
    states = iter([clean, changed if drift == "before wheel" else clean,
                   clean if drift == "none" else changed])
    monkeypatch.setattr(rehearsal, "source_state", lambda: next(states))
    for name in ("samples/first-look.md", "scripts/example_project.py", "tests/fixtures/literary_reference.json"):
        fixture = tmp_path / name
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
    result = rehearsal.rehearse(jobs=1, tag=None, dist=final_dist, skip_wheel=False)
    run, = (tmp_path / ".artifacts/release-rehearsal").iterdir()
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
        assert promotions == [(tmp_path, run / "dist", final_dist, None)]


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
