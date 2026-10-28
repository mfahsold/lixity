"""Opt-in pronunciation matching preserves legacy and rejects ambiguous keys."""

import pytest

from lixity.speech_controls import apply_pronunciation
from lixity.speech_direction import Direction, build_speech_plan, speech_passages
from lixity.speech_profiles import parse_audio_settings


def test_opt_in_unicode_term_boundaries_and_case():
    rules = {"via": "Wia", "N.N.": "unbekannt"}
    assert apply_pronunciation("VIA, via; deviated; N.N.!", rules,
                               case_sensitive=False, whole_words=True) == "Wia, Wia; deviated; unbekannt!"
    assert apply_pronunciation("Via deviated", {"via": "Wia"}) == "Via deWiated"


def test_insensitive_matching_rejects_regex_equivalent_keys():
    with pytest.raises(ValueError, match="ambiguous"):
        apply_pronunciation("İ", {"i": "one", "İ": "two"}, case_sensitive=False)


def test_project_matching_applies_to_profile_overrides_and_directions():
    audio = {
        "schema_version": "lixity-audio-settings/2", "selected": "narrator",
        "pronunciation_matching": {"case_sensitive": False, "whole_words": True},
        "pronunciations": {"via": "Wia"},
        "profiles": {"narrator": {"engine": "qwen3", "pronunciations": {"via": "Vija"}},
                     "other": {"engine": "qwen3"}},
    }
    settings = parse_audio_settings(audio)
    text = "## One\n\nVIA devia.\n\nVIA devia.\n"
    direction = Direction(anchor=speech_passages(text, "en")[1]["anchor"], profile_id="other")
    plan = build_speech_plan(text, settings.profiles["narrator"], directions=[direction],
                             profiles=settings.profiles, project_config={"audio": audio})
    assert [row.text for row in plan if row.anchor] == ["Vija devia.", "Wia devia."]


def test_matching_settings_require_schema_two_and_refuse_conflicting_profile_rules():
    audio = {"schema_version": "lixity-audio-settings/2", "selected": "narrator",
             "pronunciation_matching": {"case_sensitive": False}, "pronunciations": {"Via": "one"},
             "profiles": {"narrator": {"engine": "qwen3", "pronunciations": {"via": "two"}}}}
    with pytest.raises(ValueError, match="ambiguous"):
        parse_audio_settings(audio)
    with pytest.raises(ValueError, match="schema"):
        parse_audio_settings({**audio, "schema_version": "lixity-audio-settings/1"})


def test_term_boundaries_do_not_split_combining_characters_or_directed_words():
    assert apply_pronunciation("e\u0301 e", {"e": "E"}, whole_words=True) == "e\u0301 E"
    audio = {"schema_version": "lixity-audio-settings/2", "selected": "narrator",
             "pronunciation_matching": {"whole_words": True}, "pronunciations": {"via": "Wia"},
             "profiles": {"narrator": {"engine": "qwen3"}}}
    text = "## One\n\ndevia via\n"
    profile = parse_audio_settings(audio).profiles["narrator"]
    direction = Direction(anchor=speech_passages(text, "en")[0]["anchor"], start=2, end=5,
                          instructions="Calm.")
    plan = build_speech_plan(text, profile, directions=[direction], project_config={"audio": audio})
    assert "".join(row.text for row in plan if row.anchor) == "deviaWia"
