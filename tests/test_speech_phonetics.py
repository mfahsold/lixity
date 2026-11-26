"""True phonetic overrides and structured delivery retain explicit semantics."""
# ruff: noqa: RUF001 -- IPA symbols are intentionally different from Latin letters.

import json

import pytest

from lixity.config import prepare_project_settings, read_explicit_project_config
from lixity.speech_direction import (
    Direction,
    build_speech_plan,
    direction_id,
    plan_json,
    speech_passages,
)
from lixity.speech_export import ssml_export, timeline_json
from lixity.speech_profiles import AudioProfile, parse_audio_settings


def toucan(**changes):
    return AudioProfile.model_validate({"engine": "ims-toucan", "voice": "reference",
        "reference_id": "a" * 64, "language": "de", **changes})


def test_existing_profiles_and_direction_identity_remain_byte_compatible():
    profile = AudioProfile().model_dump()
    assert "phonemes" not in profile and "prosody" not in profile
    anchor = speech_passages("A river flows.", "en")[0]["anchor"]
    old = Direction(anchor=anchor)
    assert "prosody" not in old.model_dump()
    assert direction_id(old) == direction_id(Direction(anchor=anchor, prosody={"pitch_variance_scale": 1.2}))
    assert plan_json(build_speech_plan("A river flows.", AudioProfile()))["schema_version"] == "lixity-speech-plan/1"


def test_toucan_settings_require_version_five_and_roundtrip_sparse_controls():
    profile = toucan(phonemes={"Lixity": "ˈlɪksɪti"}, prosody={"duration_scaling_factor": 1.1})
    raw = {"schema_version": "lixity-audio-settings/5", "selected": "n", "profiles": {"n": profile.model_dump()}}
    assert parse_audio_settings(raw).model_dump(by_alias=True)["profiles"]["n"]["prosody"] == {"duration_scaling_factor": 1.1}
    for version in range(1, 5):
        with pytest.raises(ValueError, match=r"schema.*5"):
            parse_audio_settings({**raw, "schema_version": f"lixity-audio-settings/{version}"})


def test_toucan_plan_reports_phonetic_support_without_requiring_an_override():
    plan = plan_json(build_speech_plan("Der Fluss ist still.", toucan()))
    assert plan["schema_version"] == "lixity-speech-plan/2"
    assert plan["controls"]["phonemes"] is True


def project_lexicon(profile, entries):
    return {"audio": {
        "schema_version": "lixity-audio-settings/5", "selected": "n",
        "profiles": {"n": profile.model_dump()},
        "pronunciations": {"New York": "Niu York", "river": "rivver"},
        "pronunciation_lexicon": {"schema_version": "lixity-pronunciation-lexicon/1", "entries": entries},
    }}


def test_project_entry_compiles_ipa_or_explicit_respelling():
    text = "New York is where the river winds."
    entries = {"New York": {"ipa": "nuː jɔʁk", "respelling": "Neu Jork"}}
    actor = toucan(phonemes={"New York": "njuː jɔːk"})
    phonetic_plan = build_speech_plan(text, actor, project_config=project_lexicon(actor, entries))
    assert phonetic_plan[0].text == "New York is where the rivver winds."
    assert phonetic_plan[0].profile.phonemes == {"New York": "nuː jɔʁk"}
    assert actor.phonemes == {"New York": "njuː jɔːk"}
    mlx = AudioProfile(engine="mlx-audio")
    fallback_plan = build_speech_plan(text, mlx, project_config=project_lexicon(mlx, entries), for_export=True)
    assert fallback_plan[0].text == "Neu Jork is where the rivver winds."
    assert not fallback_plan[0].profile.phonemes
    timeline = timeline_json(fallback_plan)
    assert timeline["warnings"][0]["code"] == "pronunciation_respelling_used"
    assert timeline["segments"][0]["substitutions"][0] == {
        "start": 0, "end": 8, "original": "New York", "replacement": "Neu Jork",
    }


def test_project_entry_without_respelling_preserves_export_and_blocks_unsupported_render():
    profile = AudioProfile(engine="mlx-audio")
    config = project_lexicon(profile, {"New York": {"ipa": "nuː jɔʁk"}})
    with pytest.raises(ValueError, match="explicit respelling"):
        build_speech_plan("New York.", profile, project_config=config)
    plan = build_speech_plan("New York.", profile, project_config=config, for_export=True)
    timeline = timeline_json(plan)
    assert timeline["warnings"][0]["code"] == "pronunciation_ipa_unsupported"
    assert timeline["segments"][0]["phonemes"] == [{"start": 0, "end": 8, "text": "New York", "ipa": "nuː jɔʁk"}]
    assert '<phoneme alphabet="ipa" ph="nuː jɔʁk">New York</phoneme>' in ssml_export(plan)["ssml"]
    assert build_speech_plan("New Yorkshire.", profile, project_config=config)[0].text == "Niu Yorkshire."


def test_project_ipa_rejects_a_longer_profile_phoneme_that_masks_it():
    profile = toucan(phonemes={"in New York": "ɪn njuː jɔːk"})
    config = project_lexicon(profile, {"New York": {"ipa": "nuː jɔʁk"}})
    with pytest.raises(ValueError, match="conflicts with the project IPA"):
        build_speech_plan("She lives in New York.", profile, project_config=config)


def test_pronunciation_offsets_survive_skipped_whitespace_between_directions():
    profile = AudioProfile(engine="mlx-audio")
    text = "The day a river crosses New York."
    anchor = speech_passages(text, "en")[0]["anchor"]
    directions = [Direction(anchor=anchor, start=0, end=3), Direction(anchor=anchor, start=4, end=7)]
    config = project_lexicon(profile, {"New York": {"ipa": "nuː jɔʁk"}})
    timeline = timeline_json(build_speech_plan(text, profile, directions=directions,
                                             project_config=config, for_export=True))
    first, second, tail = timeline["segments"]
    assert (first["source_range"]["end"], second["source_range"]["start"]) == (3, 4)
    assert second["source_range"]["end"] == tail["source_range"]["start"] == 7
    phone = tail["phonemes"][0]
    assert tail["spoken_text"][phone["start"]:phone["end"]] == "New York"
    assert phone["start"] == tail["original_text"].index("New York") + 1
    assert tail["substitutions"] == [{"start": 3, "end": 8, "original": "river", "replacement": "rivver"}]


def test_project_entry_rejects_split_range_and_roundtrips_other_setting_edits(tmp_path):
    profile = toucan()
    config = project_lexicon(profile, {"New York": {"ipa": "nuː jɔʁk"}})
    text = "New York remains still."
    direction = Direction(anchor=speech_passages(text, "de")[0]["anchor"], start=4)
    with pytest.raises(ValueError, match="splits a pronunciation term"):
        build_speech_plan(text, profile, directions=[direction], project_config=config)
    (tmp_path / "lixity.toml").write_text('language = "de"\n', encoding="utf-8")
    prepare_project_settings(tmp_path, config).commit()
    saved = read_explicit_project_config(tmp_path)["audio"]
    saved["profiles"]["n"]["name"] = "A different name"
    prepare_project_settings(tmp_path, {"audio": saved}).commit()
    assert read_explicit_project_config(tmp_path)["audio"]["pronunciation_lexicon"] == config["audio"]["pronunciation_lexicon"]


@pytest.mark.parametrize("changes", [
    {"voice": "Ryan"}, {"reference_id": ""}, {"language": "fr"},
    {"phonemes": {"Name": ""}}, {"phonemes": {"Name": "a\nb"}},
    {"prosody": {"pitch_variance_scale": float("nan")}},
    {"prosody": {"duration_scaling_factor": 0.0}},
    {"prosody": {"energy_variance_scale": True}},
    {"prosody": {"pitch_hz": 200.0}},
])
def test_invalid_toucan_controls_are_rejected(changes):
    with pytest.raises(ValueError):
        toucan(**changes)


@pytest.mark.parametrize("field", [{"phonemes": {"Name": "naːmə"}}, {"prosody": {"energy_variance_scale": 1.2}}])
def test_other_engines_never_silently_accept_phonetic_or_prosody_controls(field):
    with pytest.raises(ValueError, match="IMS-Toucan"):
        AudioProfile.model_validate(field)


def test_passage_prosody_merges_over_profile_without_changing_other_spans():
    text = "Der Fluss ist still. Der Vogel singt."
    profile = toucan(prosody={"duration_scaling_factor": 1.1, "pitch_variance_scale": 0.8})
    direction = Direction(anchor=speech_passages(text, "de")[0]["anchor"], end=20,
                          prosody={"pitch_variance_scale": 1.3}, pause_before=0.2, pause_after=0.7)
    rows = build_speech_plan(text, profile, directions=[direction])
    assert rows[0].profile.model_dump()["prosody"] == {"duration_scaling_factor": 1.1, "pitch_variance_scale": 1.3}
    assert rows[1].profile.model_dump()["prosody"] == {"duration_scaling_factor": 1.1, "pitch_variance_scale": 0.8}
    assert rows[0].pause_before == 0.2 and rows[0].pause_after == 0.7
    assert profile.prosody.model_dump() == {"duration_scaling_factor": 1.1, "pitch_variance_scale": 0.8}


def test_phonetic_multiword_override_survives_transport_boundary_and_text_substitution():
    text = "Wort " * 119 + "New York bleibt still."
    profile = toucan(pronunciations={"New York": "Neu York"}, phonemes={"Neu York": "nɔɪ jɔʁk"})
    rows = build_speech_plan(text, profile)
    assert len(rows) >= 2
    assert sum("Neu York" in row.text for row in rows) == 1
    assert all(len(row.text) <= 600 for row in rows)
    assert all("nɔɪ" not in row.text for row in rows)
    exported = plan_json(build_speech_plan(text, profile, for_export=True))
    assert exported["schema_version"] == "lixity-speech-plan/2"
    assert exported["controls"]["phonemes"] is True
    assert sum("Neu York" in row["text"] for row in exported["segments"]) == 1


def test_toucan_free_text_is_exported_but_rejected_before_render():
    profile = toucan(instructions="Mit zurückhaltender Freude.")
    with pytest.raises(ValueError, match=r"IMS-Toucan.*instructions"):
        build_speech_plan("Der Vogel singt.", profile)
    plan = build_speech_plan("Der Vogel singt.", profile, for_export=True)
    assert timeline_json(plan)["segments"][0]["instructions"] == "Mit zurückhaltender Freude."
    assert "unsupported_instructions" in {warning["code"] for warning in ssml_export(plan)["warnings"]}


def test_timeline_and_ssml_export_actual_phonemes_and_warn_about_numeric_prosody():
    profile = toucan(phonemes={"Lixity": "ˈlɪksɪti"}, prosody={"pitch_variance_scale": 1.3})
    plan = build_speech_plan("Lixity bleibt still.", profile, for_export=True)
    timeline = timeline_json(plan)
    assert timeline["schema_version"] == "lixity-audio-timeline/2"
    assert timeline["segments"][0]["phonemes"] == [{"start": 0, "end": 6, "text": "Lixity", "ipa": "ˈlɪksɪti"}]
    output = ssml_export(plan)
    assert '<phoneme alphabet="ipa" ph="ˈlɪksɪti">Lixity</phoneme>' in output["ssml"]
    assert "unsupported_structured_prosody" in {warning["code"] for warning in output["warnings"]}
    json.dumps(timeline, allow_nan=False)


def test_phonetic_matching_respects_unicode_words_case_and_longest_phrase():
    from lixity.speech_controls import phoneme_spans

    rules = {"York": "jɔʁk", "New York": "nuː jɔʁk", "a": "aː"}
    assert phoneme_spans("New York york Yorkshire a\u0301 a", rules) == [(0, 8, "nuː jɔʁk"), (27, 28, "aː")]


def test_transport_never_splits_an_overlong_phonetic_phrase_or_word():
    from lixity.speech_controls import phonetic_segments

    with pytest.raises(ValueError, match="not split"):
        phonetic_segments("Eine lange Phrase", {"Eine lange Phrase": "aː"}, maximum=10)
    with pytest.raises(ValueError, match="not split"):
        phonetic_segments("sehrlangeswort", {}, maximum=5)


def test_unsupported_passage_prosody_exports_with_warning_instead_of_rendering():
    text = "A river flows."
    direction = Direction(anchor=speech_passages(text, "en")[0]["anchor"], prosody={"energy_variance_scale": 0.8})
    with pytest.raises(ValueError, match="IMS-Toucan"):
        build_speech_plan(text, AudioProfile(), directions=[direction])
    plan = build_speech_plan(text, AudioProfile(), directions=[direction], for_export=True)
    assert timeline_json(plan)["segments"][0]["prosody"] == {"energy_variance_scale": 0.8}
    assert plan_json(plan)["segments"][0]["prosody"] == {"energy_variance_scale": 0.8}
    assert "unsupported_structured_prosody" in {item["code"] for item in ssml_export(plan)["warnings"]}


def test_direction_storage_versions_only_explicit_structured_controls(tmp_path):
    from lixity.speech_direction import direction_state, save_direction

    source = tmp_path / "synthetic.md"
    source.write_text("A river flows.")
    (tmp_path / "lixity.toml").write_text('language = "en"\n')
    original = source.read_bytes()
    state = direction_state(tmp_path, source)
    value = {"anchor": state["passages"][0]["anchor"], "pause_before": 0.5}

    def save(value, state):
        return save_direction(tmp_path, source, value,
            expected_source_sha256=state["source_sha256"],
            expected_settings_sha256=state["settings_sha256"],
            expected_direction_sha256=state["direction_sha256"])

    state = save(value, state)
    path = tmp_path / ".lixity/audio-directions.json"
    assert json.loads(path.read_text())["schema_version"] == "lixity-audio-directions/1"
    identifier = state["directions"][0]["id"]
    state = save({**value, "prosody": {"pitch_variance_scale": 1.1}}, state)
    assert json.loads(path.read_text())["schema_version"] == "lixity-audio-directions/2"
    assert state["schema_version"] == "lixity-audio-direction-view/2"
    assert state["directions"][0]["id"] == identifier
    assert state["directions"][0]["prosody"] == {"pitch_variance_scale": 1.1}
    assert source.read_bytes() == original
