"""Deterministic unit tests for deep dialogue, scene dynamics, CLI, and MCP."""

from __future__ import annotations

import json
import sys
from io import StringIO

from lixity import cli, mcp
from lixity.dialogue import dialogue_report
from lixity.models import CorpusConfig
from lixity.scenes import scene_report


def test_voice_separation_and_adverbial_tags_english():
    text = (
        "# Chapter 1\n\n"
        '"Run now! Where is the key?" Marcus shouted loudly.\n\n'
        '"I left it quietly inside the vault," Elena replied.\n\n'
        "The corridor stretched beneath the ancient stone arches while shadows gathered along the damp walls.\n"
    )
    report = dialogue_report(text, CorpusConfig(language="en"))
    data = report.to_dict()

    assert data["dialogue_tags"] == 2
    assert data["adverbial_tag_available"] is True
    # Only "shouted loudly" has a manner adverb outside quotes; "quietly" is inside quotes.
    assert data["adverbial_tags"] == 1
    assert data["adverbial_tag_pct"] == 50.0

    vs = data["voice_separation"]
    assert vs["available"] is True
    assert vs["dialogue_words"] > 0
    assert vs["narrative_words"] > 0
    assert abs(vs["asl_delta"] - (vs["dialogue_asl"] - vs["narrative_asl"])) <= 0.02
    assert vs["dialogue_question_excl_pct"] > vs["narrative_question_excl_pct"]
    assert 0.0 <= vs["cosine_similarity"] <= 1.0
    assert vs["separation_label"] in {"distinct", "moderate", "blended"}


def test_voice_separation_unavailable_without_dialogue():
    text = "# Chapter 1\n\nOnly narrative prose appears here without any spoken lines.\n"
    data = dialogue_report(text, CorpusConfig(language="en")).to_dict()
    vs = data["voice_separation"]
    assert vs["available"] is False
    assert vs["cosine_similarity"] is None
    assert vs["asl_delta"] is None
    assert vs["separation_label"] == "unavailable"


def test_adverbial_tags_german_and_generic_unavailable():
    de_text = '# Kapitel 1\n\n"Komm her," sagte er leise. "Nein," rief sie.\n'
    de_data = dialogue_report(de_text, CorpusConfig(language="de")).to_dict()
    assert de_data["adverbial_tag_available"] is True
    assert de_data["dialogue_tags"] == 2
    assert de_data["adverbial_tags"] == 1
    assert de_data["adverbial_tag_pct"] == 50.0

    gen_data = dialogue_report(de_text, CorpusConfig(language="generic")).to_dict()
    assert gen_data["dialogue_tag_available"] is False
    assert gen_data["adverbial_tag_available"] is False
    assert gen_data["adverbial_tags"] == 0


def test_scene_dynamics_showing_and_pacing_plateaus():
    long_slow_sent = "The old stone bridge stretched across the quiet valley under a pale gray autumn sky. "
    short_fast_sent = "He ran. Sparks flew. Doors slammed. "
    dlg_sent = '"Stop right there!" she cried. "Drop the lantern!" he yelled. '

    # Scene 1: accelerating (long sentences first half, short sentences second half), >= 120 words, low exit hook.
    scene1 = (long_slow_sent * 5) + (short_fast_sent * 12) + "He felt the cold wind."
    # Scene 2: decelerating (short sentences first half, long sentences second half), >= 120 words, low exit hook.
    scene2 = (short_fast_sent * 12) + (long_slow_sent * 5) + "The evening ended quietly."
    # Scene 3: dialogue_surge (narrative first half, heavy dialogue second half), >= 120 words, low exit hook.
    scene3 = (long_slow_sent * 5) + (dlg_sent * 8) + "Then she walked away."
    # Scene 4: short scene (< 120 words) -> insufficient_length, strong question hook.
    scene4 = "Would anyone ever return?"

    manuscript = (
        "# Chapter 1\n\n"
        f"{scene1}\n\n---\n\n"
        f"{scene2}\n\n---\n\n"
        f"{scene3}\n\n---\n\n"
        f"{scene4}\n"
    )
    report = scene_report(manuscript, CorpusConfig(language="en"))
    items = report["items"]
    assert len(items) == 4

    assert items[0]["scene_dynamic"] == "accelerating"
    assert items[0]["asl_shift"] < -2.5
    assert items[1]["scene_dynamic"] == "decelerating"
    assert items[1]["asl_shift"] > 2.5
    assert items[2]["scene_dynamic"] == "dialogue_surge"
    assert items[2]["dialogue_shift"] >= 15.0
    assert items[3]["scene_dynamic"] == "insufficient_length"
    assert items[3]["asl_shift"] is None
    assert items[3]["dialogue_shift"] is None

    for item in items:
        assert "filter_per_1000" in item
        assert "sensory_per_1000" in item
        assert item["filter_per_1000"] >= 0.0
        assert item["sensory_per_1000"] >= 0.0

    # Scenes 1..3 all have exit_hook_score <= 1 -> 1 plateau of 3 scenes.
    plateaus = report["pacing_plateaus"]
    assert len(plateaus) >= 1
    assert plateaus[0]["start_id"] == "1:1"
    assert plateaus[0]["end_id"] == "1:3"
    assert plateaus[0]["scene_count"] == 3
    assert plateaus[0]["reason"] == "low_exit_hooks"


def test_cli_and_mcp_expose_deep_analytics(tmp_path, capsys, monkeypatch):
    ms = tmp_path / "sample.md"
    ms.write_text(
        '# Chapter 1\n\n"Wait!" she whispered softly. The dark hall echoed.\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["lixity", "dialogue", str(ms), "--json"])
    assert cli.main() == 0
    dlg_json = json.loads(capsys.readouterr().out)
    assert "voice_separation" in dlg_json["dialogue"]
    assert "adverbial_tags" in dlg_json["dialogue"]

    monkeypatch.setattr(sys, "argv", ["lixity", "scenes", str(ms), "--json"])
    assert cli.main() == 0
    scn_json = json.loads(capsys.readouterr().out)
    assert "pacing_plateaus" in scn_json["scenes"]
    assert scn_json["scenes"]["items"][0]["scene_dynamic"] == "insufficient_length"
    assert "filter_per_1000" in scn_json["scenes"]["items"][0]

    # MCP server round-trip
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "lixity_dialogue", "arguments": {"text": ms.read_text(encoding="utf-8")}},
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "lixity_scenes", "arguments": {"text": ms.read_text(encoding="utf-8")}},
        },
    ]
    stdin_buf = StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout_buf = StringIO()
    mcp.serve(stdin_buf, stdout_buf)
    responses = [json.loads(line) for line in stdout_buf.getvalue().splitlines() if line.strip()]
    tools = {t["name"]: t for t in responses[0]["result"]["tools"]}
    assert "voice_separation" in tools["lixity_dialogue"]["description"]
    assert "pacing_plateaus" in tools["lixity_scenes"]["description"]
    dlg_mcp = json.loads(responses[1]["result"]["content"][0]["text"])
    assert "voice_separation" in dlg_mcp["dialogue"]
    scn_mcp = json.loads(responses[2]["result"]["content"][0]["text"])
    assert "pacing_plateaus" in scn_mcp["scenes"]
