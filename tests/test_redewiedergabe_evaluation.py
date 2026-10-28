"""The optional TEI evaluation compares tokens without retaining source text."""

import json
import subprocess
import sys
from pathlib import Path


def run_corpus(tmp_path, body, fictional="yes"):
    source = tmp_path / "sample.xml"
    source.write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><fs type="metadata">'
        f'<f name="fictional">{fictional}</f></fs><body><p>{body}</p></body>'
        '</text></TEI>', encoding="utf-8"
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, "scripts/evaluate_redewiedergabe.py", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout), result.stdout


def test_reference_speech_and_quotation_disagree_for_thought(tmp_path):
    report, output = run_corpus(tmp_path,
        'Zoë sagte: <said mode="direct" content="speech">„Hallo Welt.“</said> '
        'Dann dachte sie <said mode="direct" content="thought">„morgen“</said>.')
    assert report["files"] == 1
    assert (report["tp"], report["fp"], report["fn"], report["tn"]) == (2, 1, 0, 5)
    assert report["precision"] == 2 / 3
    assert report["recall"] == 1
    assert "Zoë" not in output and "morgen" not in output


def test_nested_speech_and_ambiguous_or_split_tokens(tmp_path):
    report, _ = run_corpus(tmp_path,
        '<said mode="direct" content="speech">„äußerst <seg>hell</seg> '
        '<said mode="direct" content="speech">klar</said> und '
        '<said mode="direct" content="speech thought">leise</said>“</said> '
        'Wor<said mode="direct" content="speech">t</said>')
    assert report["tp"] == 4
    assert report["excluded_ambiguous"] == 1
    assert report["excluded_boundary"] == 1


def test_nonfiction_is_excluded_and_empty_rates_are_unknown(tmp_path):
    report, _ = run_corpus(tmp_path, '<said mode="direct" content="speech">„Hi“</said>', "no")
    assert report["files"] == 0
    assert report["precision"] is None
    assert report["recall"] is None


def test_codepoint_offsets_preserve_decomposed_characters_and_emoji(tmp_path):
    report, _ = run_corpus(tmp_path,
        '🪶 <said mode="direct" content="speech">„a\u0308 <seg>ü</seg>“</said>')
    assert (report["tp"], report["fp"], report["fn"], report["tn"]) == (2, 0, 0, 0)
    assert report["excluded_boundary"] == 0


def test_tei_with_dtd_is_rejected(tmp_path):
    (tmp_path / "sample.xml").write_text('<!DOCTYPE TEI [<!ENTITY x "text">]><TEI/>')
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, "scripts/evaluate_redewiedergabe.py", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "DTD" in result.stderr


def test_missing_corpus_is_rejected(tmp_path):
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, "scripts/evaluate_redewiedergabe.py", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "No TEI XML" in result.stderr
