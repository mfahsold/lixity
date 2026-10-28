"""Common speech controls keep literal substitutions and model limits explicit."""

import pytest

from lixity.speech_controls import apply_pronunciation, combine_delivery, speech_control_support


def test_literal_pronunciation_is_longest_first_case_sensitive_and_nonrecursive():
    rules = {"Via": "Wia", "Via Roma": "Via=Rome", "Rome": "unexpected"}
    assert apply_pronunciation("Via Roma, Via; via Rome.", rules) == "Via=Rome, Wia; via unexpected."
    assert rules["Via Roma"] == "Via=Rome"


def test_delivery_combines_authored_text_without_interpreting_tags():
    assert combine_delivery("Calm.", "A little faster.") == "Calm. A little faster."
    assert combine_delivery("", "Read [quietly].") == "Read [quietly]."


def test_qwen_control_support_distinguishes_exact_text_and_model_interpretation():
    from lixity.speech_profiles import audio_capabilities

    for variant in ("qwen3", "qwen3-design"):
        support = speech_control_support(variant)
        assert support.pronunciation == "text_substitution"
        assert support.direction == "model_interpreted"
        assert support.pauses == "explicit_silence"
        assert not support.phonemes and not support.ssml and not support.precise_rate
        assert audio_capabilities()[variant]["control_support"] == support.as_dict()
    with pytest.raises(ValueError, match="Unknown"):
        speech_control_support("invented")
