"""The optional Lexique comparison emits aggregates, not source words."""

import json
import subprocess
import sys
from pathlib import Path


def test_lexique_compares_unique_unambiguous_words_and_reports_regressions(tmp_path):
    data = tmp_path / "lexique.tsv"
    data.write_text(
        "1_Mot\t26_SyllNb\nmoment\t2\nMOMENT\t2\nvraiment\t2\nparlent\t1\n"
        "agent\t1\nagent\t2\nword-form\t2\n",
        encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and local benchmark script
        [sys.executable, "scripts/evaluate_lexique.py", str(data)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report["forms"] == 3
    assert report["ambiguous_spellings_excluded"] == 1
    assert report["excluded_rows"] == 1
    assert report["baseline_exact"] == 1
    assert report["candidate_exact"] == 2
    assert report["improved"] == 2
    assert report["regressed"] == 1
    assert "moment" not in result.stdout


def test_lexique_comparison_treats_empty_rates_as_unknown(tmp_path):
    data = tmp_path / "empty.tsv"
    data.write_text("1_Mot\t26_SyllNb\n", encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed interpreter and local benchmark script
        [sys.executable, "scripts/evaluate_lexique.py", str(data)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    report = json.loads(result.stdout)
    assert report["forms"] == 0
    assert report["baseline_mean_absolute_error"] is None
    assert report["candidate_mean_absolute_error"] is None
