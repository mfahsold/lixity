"""Project audio validation and root-only atomic persistence."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.config import configuration_metadata, load_project_config, prepare_project_settings
from lixity.speech_profiles import (
    AudioProfile,
    AudioSettings,
    audio_capabilities,
    migrate_audio_settings,
    parse_audio_settings,
    resolve_audio_profile,
)


def test_defaults_selection_and_serialization():
    settings = parse_audio_settings(None, language="de")
    assert settings.selected == "narrator"
    assert settings.profiles["narrator"].voice == "Ryan"
    assert settings.profiles["narrator"].engine == "qwen3"
    assert settings.model_dump(by_alias=True)["schema_version"] == "lixity-audio-settings/1"
    assert resolve_audio_profile(None).language == "en"
    raw = settings.model_dump(by_alias=True)
    raw["profiles"]["second"] = AudioProfile(name="Second").model_dump()
    assert resolve_audio_profile({"audio": raw}, "second").name == "Second"
    with pytest.raises(ValueError, match="Unknown audio profile"):
        resolve_audio_profile({"audio": raw}, "missing")


@pytest.mark.parametrize("raw", [[], "audio", {}, {"schema_version": "future"},
    {"selected": "absent", "profiles": {"narrator": {}}},
    {"selected": "narrator", "profiles": {"narrator": {}}, "endpoint": "http://example.test"},
    {"selected": "bad/id", "profiles": {"bad/id": {}}},
])
def test_malformed_settings_fail_explicitly(raw):
    with pytest.raises(ValueError):
        parse_audio_settings(raw)


@pytest.mark.parametrize("changes", [
    {"engine": "remote"}, {"language": "auto"}, {"voice": "../voice"},
    {"voice": "de_DE-thorsten-medium"}, {"engine": "piper"},
    {"speed": True}, {"speed": "1"}, {"speed": float("nan")},
    {"paragraph_pause": -1}, {"scene_pause": float("inf")},
    {"pronunciations": {"": "say"}}, {"pronunciations": {"term": ""}},
    {"pronunciations": {"term": "two\nlines"}}, {"endpoint": "http://localhost"},
    {"engine": "qwen3", "voice": "Ryan", "speed": 0.49},
    {"engine": "qwen3", "voice": "Ryan", "speed": 2.01},
    {"engine": "qwen3", "voice": "invented"},
])
def test_unsupported_profile_values_fail(changes):
    with pytest.raises(ValueError):
        AudioProfile.model_validate(changes)


def test_capabilities_drive_multilingual_voice_validation():
    capabilities = audio_capabilities()
    assert set(capabilities) == {"qwen3", "qwen3-design", "qwen3-base"}
    for language in ("en", "de", "fr", "es", "it", "pt", "ru", "zh", "ja", "ko"):
        profile = AudioProfile(engine="qwen3", language=language, voice="Ryan", instructions="Calm")
        assert profile.language == language
    assert capabilities["qwen3"]["instructions"] is True
    assert capabilities["qwen3"]["speed"]["supported"] is True
    assert capabilities["qwen3"]["speed"]["implementation"] == "ffmpeg-atempo"
    json.dumps(capabilities, allow_nan=False)
    capabilities["qwen3"]["languages"].append("invented")
    assert "invented" not in audio_capabilities()["qwen3"]["languages"]


def test_audio_persistence_is_atomic_preserves_source_and_other_configuration(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    original = '# Keep\nlanguage = "de"\n[custom]\nvalue = "untouched"\n'
    path.write_text(original)
    source = tmp_path / "manuscript.md"
    source.write_text("# Synthetic\n\nA door opens.\n")
    before = source.read_bytes()
    raw = parse_audio_settings(None, language="de").model_dump(by_alias=True)
    prepared = prepare_project_settings(tmp_path, {"audio": raw})
    assert path.read_text() == original
    prepared.commit()
    assert load_project_config(tmp_path)["audio"] == raw
    assert original in path.read_text()
    assert source.read_bytes() == before
    prepared = prepare_project_settings(tmp_path, {"audio": raw})
    with patch("lixity.io.os.replace") as replace:
        prepared.commit()
    replace.assert_not_called()
    with pytest.raises(ValueError):
        prepare_project_settings(tmp_path, {"title": "Changed", "audio": {}})
    assert load_project_config(tmp_path).get("title") is None
    assert source.read_bytes() == before


def test_audio_excludes_user_and_ancestor_configuration(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    raw = parse_audio_settings(None).model_dump(by_alias=True)
    prepare_project_settings(root, {"audio": raw}).commit()
    user = tmp_path / "user.toml"
    user.write_bytes((root / "lixity.toml").read_bytes())
    with patch("lixity.config.os.path.expanduser", return_value=str(user)):
        assert load_project_config(root)["audio"] == raw
        assert "audio" not in load_project_config(nested)
        assert "audio" not in load_project_config(tmp_path)
    metadata = configuration_metadata()
    assert "audio" in metadata["project_only_keys"]
    assert "audio" in metadata["native_settings"]["persisted_keys"]
    assert "audio_schema" in metadata


def test_settings_reject_empty_selection_and_validate_complete_round_trip():
    raw = parse_audio_settings(None).model_dump(by_alias=True)
    assert AudioSettings.model_validate(raw).model_dump(by_alias=True) == raw
    raw["profiles"] = {}
    with pytest.raises(ValueError):
        parse_audio_settings(raw)


@pytest.mark.parametrize("language", ["en", "de", "fr", "es", "it", "pt", "ru", "zh", "ja", "ko"])
def test_default_qwen_language_is_explicit(language):
    profile = parse_audio_settings(None, language=language).profiles["narrator"]
    assert profile.language == language and profile.engine == "qwen3"
    assert profile.voice == "Ryan" and profile.speed == 1.2


def test_unsupported_default_language_does_not_silently_select_english():
    with pytest.raises(ValueError, match="Unsupported Qwen language"):
        parse_audio_settings(None, language="auto")


def test_audio_root_update_preserves_output_on_race_and_replace_failure(tmp_path: Path):
    path = tmp_path / "lixity.toml"
    raw = parse_audio_settings(None).model_dump(by_alias=True)
    prepare_project_settings(tmp_path, {"audio": raw}).commit()
    original = path.read_bytes()
    raw["profiles"]["narrator"]["instructions"] = "Read calmly"
    prepared = prepare_project_settings(tmp_path, {"audio": raw})
    with patch("lixity.io.os.replace", side_effect=OSError("Synthetic failure")), pytest.raises(OSError):
        prepared.commit()
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]
    prepared = prepare_project_settings(tmp_path, {"audio": raw})
    (tmp_path / "pyproject.toml").write_text('[tool.lixity]\ntitle = "Concurrent"\n')
    with pytest.raises(ValueError, match="changed"):
        prepared.commit()
    assert path.read_bytes() == original


def test_static_reports_do_not_ship_inactive_native_audio_assets():
    from lixity.ui import render_dashboard
    marker = 'Project-local listening drafts share one token-bound native dialog'
    for document in (render_dashboard([], [], controls=False),
                     render_dashboard([], [], controls=True, read_only=True, enabled_actions=('speech-render',))):
        assert marker not in document
        assert '&quot;speech_title&quot;' not in document
    native = render_dashboard([], [], controls=True, enabled_actions=('speech-render',))
    assert marker in native and '&quot;speech_title&quot;' in native


@pytest.mark.parametrize("engine,voice", [("qwen3", "Ryan")])
def test_execution_target_is_not_portable_profile_configuration(engine, voice):
    profile = AudioProfile(engine=engine, voice=voice).model_dump()
    for target in ("local", "jetson"):
        with pytest.raises(ValueError, match="Extra inputs"):
            AudioProfile.model_validate({**profile, "target": target})
    assert audio_capabilities()[engine]["targets"] == ["local", "jetson"]


def legacy_audio_settings():
    return {"schema_version": "lixity-audio-settings/1", "selected": "narrator", "profiles": {
        "narrator": {"name": "Narrator", "engine": "piper", "language": "de",
                     "voice": "de_DE-thorsten-medium", "speed": 1.2},
        "other": {"name": "Other", "engine": "qwen3", "voice": "Aiden", "language": "fr"},
    }}


def test_saved_piper_profiles_fail_with_actionable_migration_guidance():
    raw = legacy_audio_settings()
    before = deepcopy(raw)
    with pytest.raises(ValueError, match=r"(?s)Piper.*backup.*Qwen.*voice.*speed"):
        parse_audio_settings(raw)
    assert raw == before
    with pytest.raises(ValueError, match="Piper"):
        AudioProfile(engine="piper", voice="de_DE-thorsten-medium")


def test_saved_profiles_without_explicit_engine_do_not_silently_convert():
    raw = {"selected": "narrator", "profiles": {"narrator": {}}}
    with pytest.raises(ValueError, match=r"explicit.*engine"):
        parse_audio_settings(raw)


def test_explicit_migration_builds_valid_candidate_preserves_original_and_selection():
    raw = legacy_audio_settings()
    before = deepcopy(raw)
    migrated = migrate_audio_settings(raw, replacements={"narrator": "Ryan"}, instructions={"narrator": "Calm"})
    assert raw == before
    assert migrated.selected == "narrator"
    assert migrated.profiles["narrator"].voice == "Ryan"
    assert migrated.profiles["narrator"].speed == 1.0
    assert migrated.profiles["other"].voice == "Aiden"
    assert migrated.profiles["other"].language == "fr"
    assert parse_audio_settings(migrated.model_dump(by_alias=True)) == migrated


@pytest.mark.parametrize("replacements", [{}, {"unknown": "Ryan"}, {"narrator": "invented"}, {"narrator": 1},
])
def test_migration_requires_every_explicit_supported_replacement(replacements):
    raw = legacy_audio_settings()
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        migrate_audio_settings(raw, replacements=replacements)
    assert raw == before


@pytest.mark.parametrize("model,raw,message", [
    (AudioProfile, {"name": "PRIVATE", "voice": "invalid", "instructions": "STYLE_PRIVATE",
                    "pronunciations": {"word": "LEXICON_PRIVATE"}}, "Unsupported Qwen preset"),
    (AudioSettings, {"private_extra": "STYLE_PRIVATE", "selected": "missing", "profiles": {
        "narrator": {"engine": "qwen3", "name": "PRIVATE", "pronunciations": {"word": "LEXICON_PRIVATE"}},
    }}, "Extra inputs"),
])
def test_validation_messages_hide_private_profile_input_values(model, raw, message):
    with pytest.raises(ValueError) as error:
        model.model_validate(raw)
    text = str(error.value)
    assert message in text
    assert all(marker not in text for marker in ("PRIVATE", "STYLE_PRIVATE", "LEXICON_PRIVATE"))


def test_voice_design_is_explicit_and_requires_a_description():
    from lixity.speech_profiles import AudioProfile, audio_capabilities

    profile = AudioProfile(engine='qwen3-design', voice='design', language='de',
                           voice_description='A natural German narrator.')
    assert profile.voice_description == 'A natural German narrator.'
    assert 'qwen3-design' in audio_capabilities()
    with pytest.raises(ValueError):
        AudioProfile(engine='qwen3-design', voice='design')
    with pytest.raises(ValueError):
        AudioProfile(engine='qwen3', voice='Ryan', voice_description='ignored')
