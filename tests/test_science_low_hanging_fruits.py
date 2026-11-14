"""Deterministic tests for the 4 scientific low-hanging-fruit features."""

from __future__ import annotations

import json
import math
import sys
from io import StringIO

from lixity import cli, mcp
from lixity.characters import presence_report
from lixity.dialogue import character_voice_profiles, dialogue_report
from lixity.models import CorpusConfig
from lixity.pacing import compute_rhythm_profile, pacing_report
from lixity.paragraph_evidence import paragraph_evidence
from lixity.pipeline import profile_document
from lixity.scenes import scene_report
from lixity.style_fingerprint import FingerprintThresholds


def test_implicit_breaks_en_and_de_and_explicit_divider_guard():
    en_text = (
        "# Chapter 1\n\n"
        "Marcus examined the old map on the oak table.\n\n"
        "Three days later, the harbor bells rang across the fog.\n\n"
        "Back in the library, the candles had burned down.\n\n"
        "---\n\n"
        "Next morning, Marcus opened the shutter.\n"
    )
    en_report = scene_report(en_text, CorpusConfig(language="en"))
    breaks = en_report["implicit_breaks"]
    assert len(breaks) == 2
    assert breaks[0]["chapter"] == 1
    assert breaks[0]["scene"] == 1
    assert breaks[0]["paragraph_index"] == 2
    assert "time" in breaks[0]["cue_type"]
    assert "Three days later" in breaks[0]["snippet"]
    assert breaks[1]["paragraph_index"] == 3
    assert "place" in breaks[1]["cue_type"]
    # Paragraph after explicit --- divider is in scene 2 as its first paragraph -> not flagged.
    assert all(b["scene"] == 1 for b in breaks)

    de_text = (
        "# Kapitel 1\n\n"
        "Der Tisch stand am Fenster im ruhigen Zimmer.\n\n"
        "Der Stuhl daneben war leer und kalt.\n\n"
        "Am nächsten Morgen wehte ein kalter Wind über den Hof.\n"
    )
    de_report = scene_report(de_text, CorpusConfig(language="de"))
    de_breaks = de_report["implicit_breaks"]
    assert len(de_breaks) == 1
    assert de_breaks[0]["paragraph_index"] == 3
    assert de_breaks[0]["cue_type"] == "time"


def test_character_voices_attribution_deltas_and_insufficient_turns():
    text = (
        "# Chapter 1\n\n"
        'The hall remained silent beneath the vaulted ceiling while dusk settled.\n\n'
        '"Where is the key? Tell me now!" Marcus demanded.\n\n'
        '"Wait here!" Marcus shouted.\n\n'
        '"Run!" Marcus yelled.\n\n'
        '"I believe the archive still holds the ledger," Elena replied calmly.\n\n'
        '"We should check the eastern wing," Elena and Marcus agreed.\n'
    )
    config = CorpusConfig(language="en")
    voices = character_voice_profiles(text, ["Marcus", "Elena"], config)
    assert voices["min_turns"] == 3
    assert voices["narrator"]["words"] > 0
    assert voices["narrator"]["asl"] is not None

    by_name = {c["name"]: c for c in voices["characters"]}
    marcus = by_name["Marcus"]
    assert marcus["status"] == "available"
    # The joint "Elena and Marcus agreed" turn is ambiguous and must be skipped.
    assert marcus["turns"] == 3
    assert marcus["dialogue_asl"] is not None
    assert marcus["question_excl_rate"] == 100.0
    assert marcus["function_word_share"] is not None
    assert marcus["narrator_asl_delta"] is not None
    assert marcus["narrator_question_excl_delta"] is not None
    assert marcus["narrator_function_word_delta"] is not None

    elena = by_name["Elena"]
    assert elena["status"] == "insufficient_turns"
    assert elena["turns"] == 1
    assert elena["dialogue_asl"] is None
    assert elena["question_excl_rate"] is None
    assert elena["function_word_share"] is None
    assert elena["narrator_asl_delta"] is None

    pres = presence_report(text, ["Marcus", "Elena"], config)
    assert "character_voices" in pres
    assert len(pres["character_voices"]["characters"]) == 2


def test_rhythm_profile_math_and_pacing_report():
    empty = compute_rhythm_profile([5])
    assert empty["available"] is False
    assert empty["asl_cv"] is None
    assert empty["asl_iqr"] is None
    assert empty["length_entropy"] is None

    flat = compute_rhythm_profile([10, 10, 10, 10])
    assert flat["available"] is True
    assert flat["asl_cv"] == 0.0
    assert flat["asl_iqr"] == 0.0
    assert flat["length_entropy"] == 0.0
    assert flat["normalized_entropy"] == 0.0

    # 1 short (4), 1 medium (12), 1 long (25) -> equal 1/3 shares -> max entropy log2(3)
    varied = compute_rhythm_profile([4, 12, 25])
    assert varied["available"] is True
    assert abs(varied["length_entropy"] - math.log2(3.0)) < 1e-3
    assert abs(varied["normalized_entropy"] - 1.0) < 1e-3
    assert varied["asl_iqr"] == 10.5
    assert varied["asl_cv"] > 0.5

    text = (
        "# Chapter 1\n\n"
        "Stop. Now. "
        "The quiet lantern swung gently beside the wooden door. "
        "Beneath the ancient stone arches of the cathedral, the weary travelers paused to listen to the distant bells.\n"
    )
    report = pacing_report(text, CorpusConfig(language="en")).to_dict()
    assert report["rhythm_profile"]["available"] is True
    assert report["rhythm_profile"]["sentences"] == 4
    assert report["chapter_list"][0]["rhythm_profile"]["available"] is True


def test_indirect_speech_en_de_and_generic_unavailable():
    en_text = (
        '## Scene\n\n'
        'Marcus said that the gate was locked. '
        'Elena wondered why he smiled. '
        '"He said that yesterday," she replied.\n'
    )
    en_cfg = CorpusConfig(language="en")
    paragraphs, _ = profile_document(en_text, en_cfg, FingerprintThresholds())
    ev = paragraph_evidence(en_text, en_cfg, paragraphs)
    ind = ev[0]["layers"]["indirect_speech"]
    assert ind["status"] == "available"
    # Quoted "said that" must NOT be counted as indirect speech.
    assert ind["count"] == 2
    assert ind["mapped_count"] == 2

    dlg = dialogue_report(en_text, en_cfg).to_dict()
    assert dlg["indirect_speech_available"] is True
    assert dlg["indirect_speech"] == 2
    assert dlg["indirect_speech_per_1000"] > 0.0

    de_text = (
        "# Kapitel 1\n\n"
        "Sie erklärte, dass der Brief angekommen sei. Er habe nichts gewusst.\n"
    )
    de_dlg = dialogue_report(de_text, CorpusConfig(language="de")).to_dict()
    assert de_dlg["indirect_speech_available"] is True
    assert de_dlg["indirect_speech"] >= 2

    gen_cfg = CorpusConfig(language="generic")
    gen_paragraphs, _ = profile_document(en_text, gen_cfg, FingerprintThresholds())
    gen_ev = paragraph_evidence(en_text, gen_cfg, gen_paragraphs)
    assert gen_ev[0]["layers"]["indirect_speech"]["status"] == "unavailable"
    assert gen_ev[0]["layers"]["indirect_speech"]["reason"] == "language_unavailable"


def test_cli_and_mcp_expose_new_scientific_fields(tmp_path, capsys, monkeypatch):
    ms = tmp_path / "manuscript.md"
    ms.write_text(
        "# Chapter 1\n\n"
        'Marcus said that the key was missing. "Where is it?" Marcus asked.\n\n'
        "Three days later, the storm arrived. Run now. "
        "The long dark corridor stretched endlessly beneath the ancient castle walls.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["lixity", "pacing", str(ms), "--json"])
    assert cli.main() == 0
    pacing_json = json.loads(capsys.readouterr().out)
    assert "rhythm_profile" in pacing_json["pacing"]

    monkeypatch.setattr(sys, "argv", ["lixity", "scenes", str(ms), "--json"])
    assert cli.main() == 0
    scenes_json = json.loads(capsys.readouterr().out)
    assert len(scenes_json["scenes"]["implicit_breaks"]) == 1

    monkeypatch.setattr(sys, "argv", ["lixity", "dialogue", str(ms), "--json"])
    assert cli.main() == 0
    dlg_json = json.loads(capsys.readouterr().out)
    assert dlg_json["dialogue"]["indirect_speech"] == 1

    monkeypatch.setattr(sys, "argv", ["lixity", "characters", str(ms), "--names", "Marcus", "--json"])
    assert cli.main() == 0
    chr_json = json.loads(capsys.readouterr().out)
    assert "character_voices" in chr_json

    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "lixity_characters", "arguments": {"text": ms.read_text(encoding="utf-8"), "names": ["Marcus"]}},
        },
    ]
    out = StringIO()
    assert mcp.serve(StringIO("\n".join(json.dumps(r) for r in requests) + "\n"), out) == 0
    resp = json.loads(out.getvalue().strip().splitlines()[0])
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert "character_voices" in payload
