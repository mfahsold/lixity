"""Project lexicons are opt-in and remain distinct from saved profiles."""

import pytest

from lixity.speech_direction import Direction, build_speech_plan, speech_passages
from lixity.speech_profiles import AudioProfile, parse_audio_settings


def settings():
    return {
        "schema_version": "lixity-audio-settings/2",
        "selected": "narrator",
        "pronunciations": {"river": "riwer", "bird": "birrd"},
        "profiles": {
            "narrator": {"engine": "qwen3", "pronunciations": {"river": "rivver"}},
            "other": {"engine": "qwen3", "voice": "Aiden", "pronunciations": {"bird": "berd"}},
        },
    }


def test_project_lexicon_applies_to_all_profiles_and_overrides_are_local():
    raw = settings()
    parsed = parse_audio_settings(raw)
    assert parsed.profiles["narrator"].pronunciations == {"river": "rivver"}
    assert parsed.model_dump(by_alias=True)["pronunciations"] == raw["pronunciations"]
    text = "## One\n\nriver bird\n\nriver bird\n"
    direction = Direction(anchor=speech_passages(text, "en")[1]["anchor"], profile_id="other")
    plan = build_speech_plan(text, parsed.profiles["narrator"], directions=[direction],
                             profiles=parsed.profiles, project_config={"audio": raw})
    assert [row.text for row in plan if row.anchor] == ["rivver birrd", "riwer berd"]
    assert parsed.profiles["other"].pronunciations == {"bird": "berd"}


def test_global_lexicon_requires_explicit_new_schema_and_old_schema_is_unchanged():
    old = parse_audio_settings(None).model_dump(by_alias=True)
    assert old["schema_version"] == "lixity-audio-settings/1"
    assert "pronunciations" not in old
    with pytest.raises(ValueError, match="schema"):
        parse_audio_settings({**old, "pronunciations": {"river": "riwer"}})


@pytest.mark.parametrize("lexicon", [{"": "word"}, {"word": ""}, {"word": "two\nlines"}])
def test_global_lexicon_validates_like_profile_rules(lexicon):
    with pytest.raises(ValueError):
        parse_audio_settings({**settings(), "pronunciations": lexicon})


def test_combined_lexicon_limit_counts_unique_keys_after_overrides():
    raw = settings()
    raw["pronunciations"] = {f"term{n}": f"spoken{n}" for n in range(200)}
    raw["profiles"]["narrator"]["pronunciations"] = {"term0": "override"}
    raw["profiles"]["other"]["pronunciations"] = {}
    parse_audio_settings(raw)
    raw["profiles"]["narrator"]["pronunciations"]["extra"] = "spoken"
    with pytest.raises(ValueError, match="Combined"):
        parse_audio_settings(raw)


def test_effective_lexicon_applies_to_draft_profile_without_mutating_it():
    draft = AudioProfile(pronunciations={"river": "override"})
    plan = build_speech_plan("## One\n\nriver bird\n", draft, project_config={"audio": settings()})
    assert [row.text for row in plan if row.anchor] == ["override birrd"]
    assert draft.pronunciations == {"river": "override"}


def test_settings_roundtrip_preserves_global_and_profile_rules(tmp_path):
    from lixity.config import prepare_project_settings, read_explicit_project_config

    (tmp_path / "lixity.toml").write_text('language = "en"\n')
    audio = parse_audio_settings(settings()).model_dump(by_alias=True)
    prepare_project_settings(tmp_path, {"audio": audio}).commit()
    saved = read_explicit_project_config(tmp_path)["audio"]
    assert saved == audio
    saved["profiles"]["narrator"]["voice"] = "Vivian"
    prepare_project_settings(tmp_path, {"audio": saved}).commit()
    saved_again = read_explicit_project_config(tmp_path)["audio"]
    assert saved_again["schema_version"] == "lixity-audio-settings/2"
    assert saved_again["pronunciations"] == settings()["pronunciations"]
    assert saved_again["profiles"]["narrator"]["pronunciations"] == {"river": "rivver"}


def test_changed_global_rule_changes_only_affected_cache_keys(tmp_path):
    from lixity.speech import generate_silence_wav
    from lixity.speech_cache import SpeechSegmentCache

    config = settings()
    text = "## One\n\nriver bird\n\nNo match here.\n"
    profile = parse_audio_settings(config).profiles["narrator"]
    before = build_speech_plan(text, profile, project_config={"audio": config})
    updated = {**config, "pronunciations": {**config["pronunciations"], "bird": "changed"}}
    after = build_speech_plan(text, profile, project_config={"audio": updated})
    cache = SpeechSegmentCache(tmp_path / "cache")
    before_rows = [row for row in before if row.anchor]
    after_rows = [row for row in after if row.anchor]
    for row in before_rows:
        cache.put(row.text, row.profile, generate_silence_wav(.01, 24000))
    assert cache.get(after_rows[0].text, after_rows[0].profile) is None
    assert cache.get(after_rows[1].text, after_rows[1].profile) is not None


@pytest.mark.parametrize("preview", [True, False])
def test_cli_uses_global_lexicon_in_preview_and_full_plan(tmp_path, capsys, preview):
    import json

    from lixity.cli import main

    (tmp_path / "draft.md").write_text("## One\n\nriver bird\n")
    (tmp_path / "lixity.toml").write_text('''language = "en"
manuscript = "draft.md"
[audio]
schema_version = "lixity-audio-settings/2"
selected = "narrator"
pronunciations = { BIRD = "berd" }
pronunciation_matching = { case_sensitive = false, whole_words = true }
[audio.profiles.narrator]
engine = "qwen3"
pronunciations = { river = "rivver" }
''')
    args = ['read-aloud', '--project', str(tmp_path), '--plan-only']
    if preview:
        args.append('--preview')
    assert main(args) == 0
    plan = json.loads(capsys.readouterr().out)
    assert any(row['text'] == 'rivver berd' for row in plan['segments'])
