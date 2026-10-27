"""Malformed annotation guards, independent of parser/model accuracy."""

from dataclasses import replace

import pytest

from lixity.linguistic_models import SyntaxToken


def _valid_pair():
    return (
        SyntaxToken(7, 4, 7, "has", "have", "AUX", "", "Fin", "Ind", "Pres", 91, "aux"),
        SyntaxToken(91, 8, 12, "sung", "sing", "VERB", "", "Part", "", "Past", 91, "ROOT"),
    )


@pytest.mark.parametrize("malformation", ["duplicate_id", "missing_head", "cycle", "bad_nonverb_span"])
def test_invalid_annotations_are_rejected_before_composition(malformation):
    from lixity.grammatical_tense import compose_verbs

    text = "She has sung."
    auxiliary, participle = _valid_pair()
    tokens = auxiliary, participle
    if malformation == "duplicate_id":
        tokens = auxiliary, replace(participle, i=7, head=7)
    elif malformation == "missing_head":
        tokens = auxiliary, replace(participle, head=300)
    elif malformation == "cycle":
        tokens = auxiliary, replace(participle, head=7)
    else:
        tokens += (SyntaxToken(300, 0, 3, "Not", "she", "PRON", "", "", "", "", 91, "nsubj"),)
    with pytest.raises(ValueError):
        compose_verbs(text, tokens, "en")


def test_shared_validator_accepts_sparse_indices_and_multiple_sentence_roots():
    from lixity.grammatical_tense import compose_verbs
    from lixity.linguistic_models import validate_tokens

    text = "She sings. He danced."
    tokens = (
        SyntaxToken(7, 4, 9, "sings", "sing", "VERB", "", "Fin", "Ind", "Pres", 7, "ROOT"),
        SyntaxToken(91, 14, 20, "danced", "dance", "VERB", "", "Fin", "Ind", "Past", 91, "ROOT"),
    )
    validate_tokens(text, tokens)
    validate_tokens(text, tuple(reversed(tokens)))
    assert [group.tense for group in compose_verbs(text, tokens, "en")] == ["present", "preterite"]


def test_shared_validator_allows_expanded_words_with_equal_original_spans():
    from lixity.linguistic_models import validate_tokens

    text = "Farlo"
    tokens = (
        SyntaxToken(7, 0, 5, "Farlo", "fare", "VERB", "", "Inf", "", "", 7, "ROOT"),
        SyntaxToken(91, 0, 5, "Farlo", "lo", "PRON", "", "", "", "", 7, "obj"),
    )
    validate_tokens(text, tokens)


def test_shared_validator_rejects_long_nonverbal_dependency_cycle():
    from lixity.linguistic_models import validate_tokens

    text = "a b c"
    tokens = (
        SyntaxToken(7, 0, 1, "a", "a", "NOUN", "", "", "", "", 91, "dep"),
        SyntaxToken(91, 2, 3, "b", "b", "NOUN", "", "", "", "", 300, "dep"),
        SyntaxToken(300, 4, 5, "c", "c", "NOUN", "", "", "", "", 7, "dep"),
    )
    with pytest.raises(ValueError):
        validate_tokens(text, tokens)
