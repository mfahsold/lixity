"""Common speech controls keep literal substitutions and model limits explicit."""

import pytest

from lixity.speech_controls import apply_pronunciation, combine_delivery, speech_control_support


def test_literal_pronunciation_is_longest_first_case_sensitive_and_nonrecursive():
    rules = {"Via": "Wia", "Via Roma": "Via=Rome", "Rome": "unexpected"}
    assert apply_pronunciation("Via Roma, Via; via Rome.", rules) == "Via=Rome, Wia; via unexpected."
    assert rules["Via Roma"] == "Via=Rome"


def test_pronunciation_spans_preserve_original_offsets_and_identity_matches():
    from lixity.speech_controls import pronunciation_spans

    assert pronunciation_spans('Via Roma, Via; Rome.', {'Via': 'Wia', 'Via Roma': 'Rome', 'Rome': 'Rome'}) == [
        (0, 8, 'Rome'), (10, 13, 'Wia'), (15, 19, 'Rome'),
    ]


def test_pronunciation_spans_respect_unicode_and_context_word_boundaries():
    from lixity.speech_controls import pronunciation_spans

    rules = {'via': 'Wia'}
    assert pronunciation_spans('Via, vial via\u0301 via', rules, case_sensitive=False, whole_words=True) == [(0, 3, 'Wia'), (15, 18, 'Wia')]
    assert pronunciation_spans('via', rules, whole_words=True, left_context='x') == []
    assert pronunciation_spans('via', rules, whole_words=True, right_context='\u0301') == []
    assert pronunciation_spans('via', {}, whole_words=True) == []


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
