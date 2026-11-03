"""Read-aloud keeps one narrator; passage direction shapes delivery only."""
import pytest

from lixity.speech_direction import (
    Direction,
    NarratorConflict,
    build_speech_plan,
    same_narrator,
    speech_passages,
)
from lixity.speech_profiles import AudioProfile

TEXT = "## Scene\n\nNarration. Dialogue.\n"
BASE = AudioProfile(engine="qwen3-base", language="de", voice="reference", reference_id="a" * 64)


@pytest.mark.parametrize(("delivery", "expected"), [
    (AudioProfile(voice="Ryan", instructions="Leise.", speed=0.9), True),
    (AudioProfile(voice="Aiden"), False),
    (AudioProfile(voice="Ryan", language="de"), False),
    (AudioProfile(engine="qwen3-design", voice="design", voice_description="Warm."), False),
])
def test_preset_narrator_allows_delivery_but_not_another_voice(delivery, expected):
    assert same_narrator(AudioProfile(voice="Ryan"), delivery) is expected


def test_design_narrator_requires_identical_description():
    narrator = AudioProfile(engine="qwen3-design", voice="design", voice_description="Warm baritone.")
    same = narrator.model_copy(update={"instructions": "Tense."})
    other = narrator.model_copy(update={"voice_description": "Bright tenor."})
    assert same_narrator(narrator, same) and not same_narrator(narrator, other)


def test_base_delivery_reference_varies_intonation_with_one_narrator():
    delivery = BASE.model_copy(update={"reference_id": "b" * 64})
    passage = speech_passages(TEXT, "de")[0]
    start = passage["text"].index("Dialogue.")
    direction = Direction(anchor=passage["anchor"], start=start, end=start + len("Dialogue."),
                          profile_id="leise", pause_before=0.3)
    plan = build_speech_plan(TEXT, BASE, directions=[direction], profiles={"leise": delivery})
    spoken = [(row.text.strip(), row.profile.reference_id) for row in plan if row.anchor and row.text.strip()]
    assert spoken == [("Narration.", "a" * 64), ("Dialogue.", "b" * 64)]


@pytest.mark.parametrize("for_export", [False, True])
def test_other_engine_is_refused_for_render_and_export(for_export):
    passage = speech_passages(TEXT, "de")[0]
    direction = Direction(anchor=passage["anchor"], profile_id="preset")
    with pytest.raises(NarratorConflict):
        build_speech_plan(TEXT, BASE, directions=[direction], for_export=for_export,
                          profiles={"preset": AudioProfile(language="de")})


def test_saving_a_direction_with_another_voice_is_refused(tmp_path):
    from lixity.config import prepare_project_settings
    from lixity.speech_direction import direction_state, save_direction

    source = tmp_path / "manuscript.md"
    source.write_text(TEXT)
    prepare_project_settings(tmp_path, {"audio": {"selected": "narrator", "profiles": {
        "narrator": {"engine": "qwen3", "voice": "Ryan", "language": "en"},
        "other": {"engine": "qwen3", "voice": "Aiden", "language": "en"},
    }}}).commit()
    state = direction_state(tmp_path, source)
    with pytest.raises(NarratorConflict):
        save_direction(tmp_path, source, {"anchor": state["passages"][0]["anchor"], "profile_id": "other"},
                       expected_source_sha256=state["source_sha256"],
                       expected_settings_sha256=state["settings_sha256"],
                       expected_direction_sha256=state["direction_sha256"])
    assert not (tmp_path / ".lixity" / "audio-directions.json").exists()
