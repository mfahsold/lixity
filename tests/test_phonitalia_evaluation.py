"""The optional PhonItalia benchmark reports aggregate row agreement only."""

import json
import subprocess
import sys
from pathlib import Path


def test_phonitalia_benchmark_counts_rows_and_does_not_emit_source_words(tmp_path):
    data = tmp_path / "wordforms.tsv"
    data.write_text("word\tSumSylls\ncane\t2\nfiore\t2\nfiore\t2\nnot-a-word\t4\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed interpreter and local benchmark script
        [sys.executable, "scripts/evaluate_phonitalia.py", str(data)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report["evaluated_rows"] == 3
    assert report["unique_spellings"] == 2
    assert report["excluded_rows"] == 1
    assert report["exact_rows"] == 1
    assert report["absolute_error_sum"] == 2
    assert "fiore" not in result.stdout
    assert len(report["source_sha256"]) == 64


def test_phonitalia_benchmark_reports_empty_measurement_as_unknown(tmp_path):
    data = tmp_path / "empty.tsv"
    data.write_text("word\tSumSylls\nxyz-123\t1\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed interpreter and local benchmark script
        [sys.executable, "scripts/evaluate_phonitalia.py", str(data)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report["evaluated_rows"] == 0
    assert report["exact_fraction"] is None
    assert report["mean_absolute_error"] is None
