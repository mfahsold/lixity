"""Deterministic tests for sticky sentences, dialogue tags, scene hooks, POV gaps, and genre corridors."""

from __future__ import annotations

import json

import pytest

from lixity import api, cli, mcp
from lixity.characters import pov_chapters_map, presence_report
from lixity.config import resolve_thresholds
from lixity.corridors import (
    GENRE_CORRIDOR_KEYS,
    evaluate_genre_corridor,
    list_genre_corridors,
    resolve_genre_corridor,
)
from lixity.dialogue import dialogue_report
from lixity.models import CorpusConfig
from lixity.pacing import pacing_report
from lixity.pipeline import analyze_document, supplementary_reports
from lixity.scenes import scene_report

MANUSCRIPT = """\
## Chapter One

"Where did you hide the key?" she asked.

He sprinted down the stairs and slammed the door. It is what it is in the end for all of them to be there with us.

Did he ever look back?

---

She wondered if the letter would arrive in time.

"Go," he said, "now."

He kicked the crate open and grabbed the map.

## Chapter Two

"Wait for me!" Matteo shouted.

Clara felt a sudden chill in the corridor. She had been in the room with the man who was going to be at the gate for them.

## Chapter Three

Elena checked her watch. The train pulled away from the platform.
"""


def test_sticky_sentences_detection_and_generic_guard() -> None:
    report = pacing_report(MANUSCRIPT, CorpusConfig(language="en"))
    assert report.sticky_available is True
    assert report.sticky_sentences >= 2
    assert report.sticky_sentence_pct > 0.0
    assert report.mean_glue_pct > 0.0
    assert len(report.sticky_items) == report.sticky_sentences
    assert all(item["glue_pct"] >= 45.0 and item["words"] >= 8 for item in report.sticky_items)
    # Sorted descending by glue_pct
    glue_values = [item["glue_pct"] for item in report.sticky_items]
    assert glue_values == sorted(glue_values, reverse=True)

    generic_report = pacing_report(MANUSCRIPT, CorpusConfig(language="generic"))
    assert generic_report.sticky_available is False
    assert generic_report.sticky_sentences == 0
    assert generic_report.sticky_items == []


def test_dialogue_tag_density_en_de_and_generic() -> None:
    report = dialogue_report(MANUSCRIPT, CorpusConfig(language="en"))
    assert report.dialogue_tag_available is True
    # "asked", "said" (split turn not double-counted), "shouted" -> 3 tags
    assert report.dialogue_tags == 3
    assert report.dialogue_tag_pct > 0.0
    assert report.dialogue_tags_per_1000 > 0.0

    de_text = "## Eins\n\n»Kommst du mit?«, fragte Clara.\n\n»Ja«, sagte Matteo.\n"
    de_report = dialogue_report(de_text, CorpusConfig(language="de"))
    assert de_report.dialogue_tag_available is True
    assert de_report.dialogue_tags == 2

    generic_report = dialogue_report(MANUSCRIPT, CorpusConfig(language="generic"))
    assert generic_report.dialogue_tag_available is False
    assert generic_report.dialogue_tags == 0


def test_scene_entry_and_exit_hook_classification() -> None:
    pacing = pacing_report(MANUSCRIPT, CorpusConfig(language="en"))
    ch1_scenes = pacing.chapter_list[0].scene_list
    assert len(ch1_scenes) == 2
    assert ch1_scenes[0].entry_hook_type == "dialogue"
    assert ch1_scenes[0].exit_hook_type == "question"
    assert ch1_scenes[1].entry_hook_type == "reflection"
    assert ch1_scenes[1].exit_hook_type == "action"

    scenes = scene_report(MANUSCRIPT, CorpusConfig(language="en"))
    assert len(scenes["items"]) == 4
    assert scenes["items"][0]["entry_hook_type"] == "dialogue"
    assert scenes["items"][0]["exit_hook_type"] == "question"
    assert scenes["items"][1]["entry_hook_type"] == "reflection"
    assert scenes["items"][1]["exit_hook_type"] == "action"
    assert scenes["hook_distribution"]["entry"]["dialogue"] >= 1
    assert scenes["hook_distribution"]["exit"]["question"] >= 1


def test_pov_chapter_absence_gaps_and_scene_pov_mapping() -> None:
    text = (
        "## One\n\nClara walked.\n\n"
        "## Two\n\nMatteo waited.\n\n"
        "## Three\n\nElena read.\n\n"
        "## Four\n\nClara returned.\n"
    )
    declared = {"Clara": [1, 4], "Matteo": [2]}
    report = presence_report(
        text, ["Clara", "Matteo", "Elena"], CorpusConfig(language="en"), declared_pov=declared
    )
    by_name = {fig["name"]: fig for fig in report["figures"]}
    assert by_name["Clara"]["pov_gaps"] == [
        {"from_chapter": 1, "to_chapter": 4, "gap_chapters": 2, "missing_chapters": [2, 3]}
    ]
    assert by_name["Clara"]["pov_longest_gap"] == 2
    assert by_name["Clara"]["pov_leading_gap"] == 0
    assert by_name["Clara"]["pov_trailing_gap"] == 0
    assert by_name["Clara"]["pov_share"] == 0.5

    assert by_name["Matteo"]["pov_gaps"] == []
    assert by_name["Matteo"]["pov_longest_gap"] == 0
    assert by_name["Matteo"]["pov_leading_gap"] == 1
    assert by_name["Matteo"]["pov_trailing_gap"] == 2
    assert "pov_gaps" not in by_name["Elena"]

    assert report["pov_summary"] == {
        "declared_figures": 2,
        "pov_coverage_chapters": [1, 2, 4],
        "chapters_without_declared_pov": [3],
    }

    pov_map = pov_chapters_map(declared)
    scenes = scene_report(text, CorpusConfig(language="en"), pov_by_chapter=pov_map)
    assert scenes["items"][0]["pov_characters"] == ["Clara"]
    assert scenes["items"][2]["pov_characters"] == []


def test_genre_reference_corridors_non_prescriptive() -> None:
    assert set(GENRE_CORRIDOR_KEYS) == {"crime_thriller", "literary", "romance", "speculative"}
    corridors = list_genre_corridors()
    assert len(corridors) == 4
    assert all(c["non_prescriptive"] is True for c in corridors)

    resolved = resolve_genre_corridor("Crime-Thriller")
    assert resolved.key == "crime_thriller"

    evaluated = evaluate_genre_corridor(
        "crime_thriller",
        {"asl": 12.0, "dialogue_pct": 10.0, "staccato_pct": 40.0, "avg_scene_words": None},
    )
    assert evaluated["non_prescriptive"] is True
    assert "score" not in evaluated
    assert evaluated["metrics"]["asl"]["position"] == "within"
    assert evaluated["metrics"]["dialogue_pct"]["position"] == "below"
    assert evaluated["metrics"]["staccato_pct"]["position"] == "above"
    assert evaluated["metrics"]["avg_scene_words"]["position"] == "unavailable"

    with pytest.raises(ValueError):
        resolve_genre_corridor("nonexistent_genre")


def test_pipeline_api_cli_and_mcp_integration(tmp_path, capsys) -> None:
    cfg = CorpusConfig(language="en", genre_corridor="literary")
    analysis = analyze_document(MANUSCRIPT, cfg, resolve_thresholds())
    supp = supplementary_reports(MANUSCRIPT, cfg, analysis)
    assert supp["genre_corridor"]["genre"] == "literary"
    assert supp["pacing"]["sticky_available"] is True
    assert supp["dialogue"]["dialogue_tag_available"] is True
    assert "hook_distribution" in supp["scenes"]

    api_pacing = api.pacing(MANUSCRIPT, language="en", genre="crime_thriller")
    assert api_pacing["genre_corridor"]["genre"] == "crime_thriller"
    assert api_pacing["pacing"]["sticky_sentences"] >= 2

    api_corridors = api.corridors(MANUSCRIPT, genre="romance", language="en")
    assert len(api_corridors["corridors"]) == 4
    assert api_corridors["genre_corridor"]["genre"] == "romance"

    # CLI pacing --genre --json
    ms_file = tmp_path / "sample.md"
    ms_file.write_text(MANUSCRIPT, encoding="utf-8")
    exit_code = cli.main(["pacing", str(ms_file), "--genre", "speculative", "--json"])
    assert exit_code == 0
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["genre_corridor"]["genre"] == "speculative"
    assert "sticky_sentences" in cli_payload["pacing"]

    # Read-only MCP tools
    mcp_pacing = mcp.handle_message({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "lixity_pacing", "arguments": {"text": MANUSCRIPT, "genre": "crime_thriller"}},
    })
    assert mcp_pacing is not None
    mcp_pacing_data = json.loads(mcp_pacing["result"]["content"][0]["text"])
    assert mcp_pacing_data["genre_corridor"]["genre"] == "crime_thriller"

    mcp_scenes = mcp.handle_message({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "lixity_scenes", "arguments": {"text": MANUSCRIPT}},
    })
    assert mcp_scenes is not None
    mcp_scenes_data = json.loads(mcp_scenes["result"]["content"][0]["text"])
    assert "hook_distribution" in mcp_scenes_data["scenes"]

    mcp_corridors = mcp.handle_message({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "lixity_corridors", "arguments": {"text": MANUSCRIPT, "genre": "literary"}},
    })
    assert mcp_corridors is not None
    mcp_corridors_data = json.loads(mcp_corridors["result"]["content"][0]["text"])
    assert mcp_corridors_data["genre_corridor"]["genre"] == "literary"
