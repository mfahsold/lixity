"""Tests for German common-noun guard in scene character break detection."""

from __future__ import annotations

from lixity.models import CorpusConfig
from lixity.scenes import _chapter_recurring_names, scene_report


def test_german_capitalized_common_nouns_do_not_trigger_character_breaks() -> None:
    paragraphs = [
        "Hoffnung lag in der Luft, während Schatten über die Straße fielen.",
        "Hoffnung kehrte zurück, doch alte Gedanken blieben.",
        "Stimme um Stimme erhob sich in der Halle.",
        "Stimme klang laut, während Schatten verschwanden.",
    ]
    assert _chapter_recurring_names(paragraphs, language_key="de") == set()

    text = "# Kapitel 1\n\n" + "\n\n".join(paragraphs) + "\n"
    report = scene_report(text, CorpusConfig(language="de"))
    for brk in report["implicit_breaks"]:
        assert "character" not in brk["cue_type"]


def test_english_recurring_names_still_detected() -> None:
    paragraphs = [
        "Elena opened the door.",
        "Marcus waited outside.",
        "Elena nodded slowly.",
        "Marcus smiled back.",
    ]
    assert _chapter_recurring_names(paragraphs, language_key="en") == {"Elena", "Marcus"}
