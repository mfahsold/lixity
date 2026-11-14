"""Deterministic tests for Phase 2 core features."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from lixity import cli, mcp
from lixity.characters import presence_report
from lixity.dialogue import character_voice_profiles
from lixity.manuscript_editing import ManuscriptStore, _digest, compare_texts
from lixity.models import CorpusConfig
from lixity.scenes import scene_report


def test_lexical_cohesion_drop_standalone_combined_and_explicit_divider():
    text = (
        "# Chapter 1\n\n"
        "The wooden vessel rocked violently beneath the dark storm clouds while sailors hauled "
        "heavy canvas ropes across the slick deck. Saltwater crashed over the bowsprit and "
        "drenched every lantern hanging along the starboard railing.\n\n"
        "Captain Vance gripped the brass compass near the helm, watching storm clouds and "
        "foaming waves batter the wooden deck. Seagulls wheeled above the harbor breakwater "
        "as thunder rolled across the churning bay.\n\n"
        "Three days later, velvet curtains framed quiet bookshelves inside the dusty archive. "
        "Inkwells, parchment ledgers, and brass candlesticks rested upon mahogany tables "
        "beneath tall stained-glass windows.\n\n"
        "---\n\n"
        "Snowflakes drifted silently past frosted pine branches along the northern mountain ridge. "
        "Wolves tracked elk footprints across frozen granite ledges above the timberline.\n"
    )
    report = scene_report(text, CorpusConfig(language="en"))
    breaks = report["implicit_breaks"]
    assert len(breaks) == 1
    item = breaks[0]
    assert item["chapter"] == 1
    assert item["scene"] == 1
    assert item["paragraph_index"] == 3
    assert item["cue_type"] == "time+cohesion_drop"
    assert isinstance(item["cohesion_similarity"], float)
    assert item["cohesion_similarity"] <= 0.05

    # Without the "Three days later," prefix, cohesion_drop fires standalone.
    no_time_text = text.replace("Three days later, velvet", "Velvet")
    no_time_breaks = scene_report(no_time_text, CorpusConfig(language="en"))["implicit_breaks"]
    assert len(no_time_breaks) == 1
    assert no_time_breaks[0]["cue_type"] == "cohesion_drop"
    assert no_time_breaks[0]["cohesion_similarity"] <= 0.05


def test_character_interaction_matrix_pairs_and_turn_dominance():
    text = (
        "## Chapter 1\n\n"
        '"Where is the ledger?" Alice asked.\n\n'
        '"Behind the clock," Bob replied.\n\n'
        '"Are you certain?" Alice whispered.\n\n'
        '"Completely certain," Bob answered.\n\n'
        '"Who else knows?" a stranger muttered.\n\n'
        '"Nobody else," Claire added.\n\n'
        "## Chapter 2\n\n"
        '"We leave at dawn," Alice declared.\n\n'
        "Claire nodded beside the gate while Bob stayed behind in the archive.\n"
    )
    cfg = CorpusConfig(language="en")
    voices = character_voice_profiles(text, ["Alice", "Bob", "Claire"], cfg)
    interactions = voices["character_interactions"]
    pairs = {(p["a"], p["b"]): p for p in interactions["pairs"]}

    # Alice <-> Bob: 3 adjacent turn exchanges in Ch1, co-occur in Ch1 and Ch2 (2 chapters).
    assert pairs[("Alice", "Bob")]["turn_exchanges"] == 3
    assert pairs[("Alice", "Bob")]["co_chapters"] == 2
    # Unattributed turn ("a stranger") resets adjacency, so Bob <-> Claire has 0 exchanges.
    assert pairs[("Bob", "Claire")]["turn_exchanges"] == 0
    assert pairs[("Bob", "Claire")]["co_chapters"] == 2

    dominance = {d["name"]: d for d in interactions["turn_dominance"]}
    assert dominance["Alice"]["turns"] == 3
    assert dominance["Bob"]["turns"] == 2
    assert dominance["Claire"]["turns"] == 1
    assert round(sum(d["turn_share"] for d in interactions["turn_dominance"]), 1) == 100.0
    assert round(sum(d["word_share"] for d in interactions["turn_dominance"]), 1) == 100.0

    pres = presence_report(text, ["Alice", "Bob", "Claire"], cfg)
    assert pres["character_interactions"] == interactions


def test_enriched_revision_diff_store_cli_and_mcp(tmp_path: Path, capsys):
    base_text = (
        "# Chapter 1\n\n"
        "The cat sat on the mat. The dog sat on the rug. "
        "It was a very quiet and very long day in the old house by the hill.\n"
    )
    target_text = (
        "# Chapter 1\n\n"
        "Rain fell. She said that the train had already departed.\n\n"
        "He thought that the old lantern on the wooden table might still burn through the night, "
        "illuminating the dusty floorboards and the forgotten manuscripts stacked beside the window.\n"
    )
    diff = compare_texts(base_text, target_text, language="en")
    assert diff["schema_version"] == "lixity-diff/1"
    assert diff["has_baseline"] is True
    for key in ("length_entropy", "sticky_pct", "indirect_speech_per_1000"):
        assert key in diff["base"]
        assert key in diff["current"]
        assert key in diff["deltas"]
        assert diff["deltas"][key] is not None

    # ManuscriptStore persistence + SQLite migration from Phase 1 schema
    ms_path = tmp_path / "novel.md"
    ms_path.write_text(base_text, encoding="utf-8")
    db_dir = tmp_path / ".lixity" / "editing"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "recovery.sqlite3"
    with closing(sqlite3.connect(db_path)) as db:
        db.execute(
            "CREATE TABLE manuscript_revisions ("
            "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
            "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
            "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
            "flags_count INTEGER NOT NULL DEFAULT 0, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
            "PRIMARY KEY(document, revision))"
        )
        db.commit()

    store = ManuscriptStore(tmp_path, ms_path, language="en")
    rev1 = _digest(base_text.encode("utf-8"))
    store.save(store.document, rev1, "a" * 32, target_text)
    timeline_delta = store.delta()
    assert timeline_delta["has_baseline"] is True
    assert timeline_delta["deltas"]["indirect_speech_per_1000"] is not None

    # CLI `lixity diff` two-file mode
    base_file = tmp_path / "base.md"
    target_file = tmp_path / "target.md"
    base_file.write_text(base_text, encoding="utf-8")
    target_file.write_text(target_text, encoding="utf-8")
    rc = cli.main(["diff", str(base_file), str(target_file), "--language", "en", "--json"])
    assert rc == cli.EXIT_OK
    cli_payload = json.loads(capsys.readouterr().out)
    assert cli_payload["deltas"]["indirect_speech_per_1000"] == diff["deltas"]["indirect_speech_per_1000"]

    # MCP `revision_diff` tool
    resp = mcp.handle_message({
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {
            "name": "revision_diff",
            "arguments": {"base_text": base_text, "target_text": target_text, "language": "en"},
        },
    })
    assert resp is not None
    assert "error" not in resp
    mcp_payload = json.loads(resp["result"]["content"][0]["text"])
    assert mcp_payload["deltas"]["length_entropy"] == diff["deltas"]["length_entropy"]
