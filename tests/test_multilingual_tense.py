"""Hand-annotated verbal periphrases; token features are explicit test inputs."""

import pytest


def _tokens(text, specs):
    from lixity.linguistic_models import SyntaxToken

    result = []
    for i,(word,lemma,pos,form,mood,tense,head,dep) in enumerate(specs):
        start=text.index(word)
        result.append(SyntaxToken(i,start,start+len(word),word,lemma,pos,"",form,mood,tense,head,dep))
    return tuple(result)


@pytest.mark.parametrize(("lang","text","specs","want"),[
    ("en","She has written.",[("has","have","AUX","Fin","Ind","Pres",1,"aux"),("written","write","VERB","Part","","Past",1,"ROOT")],("perfect","indicative")),
    ("en","She had written.",[("had","have","AUX","Fin","","Past",1,"aux"),("written","write","VERB","Part","","Past",1,"ROOT")],("pluperfect","unmarked")),
    ("en","She will write.",[("will","will","AUX","Fin","","",1,"aux"),("write","write","VERB","Inf","","",1,"ROOT")],("future","unmarked")),
    ("en","She would write.",[("would","would","AUX","Fin","","",1,"aux"),("write","write","VERB","Inf","","",1,"ROOT")],("conditional","conditional")),
    ("fr","Elle a écrit.",[("a","avoir","AUX","Fin","Ind","Pres",1,"aux:tense"),("écrit","écrire","VERB","Part","","Past",1,"ROOT")],("perfect","indicative")),
    ("fr","Elle aurait écrit.",[("aurait","avoir","AUX","Fin","Cnd","Pres",1,"aux:tense"),("écrit","écrire","VERB","Part","","Past",1,"ROOT")],("conditional_perfect","conditional")),
    ("es","Ella había escrito.",[("había","haber","AUX","Fin","Ind","Imp",1,"aux"),("escrito","escribir","VERB","Part","","Past",1,"ROOT")],("pluperfect","indicative")),
    ("es","Ella habría escrito.",[("habría","haber","AUX","Fin","Cnd","",1,"aux"),("escrito","escribir","VERB","Part","","Past",1,"ROOT")],("conditional_perfect","conditional")),
    ("it","Lei ha scritto.",[("ha","avere","AUX","Fin","Ind","Pres",1,"aux"),("scritto","scrivere","VERB","Part","","Past",1,"ROOT")],("perfect","indicative")),
    ("it","Lei avrebbe scritto.",[("avrebbe","avere","AUX","Fin","Cnd","Pres",1,"aux"),("scritto","scrivere","VERB","Part","","Past",1,"ROOT")],("conditional_perfect","conditional")),
    ("pt","Ela tem escrito.",[("tem","ter","AUX","Fin","Ind","Pres",1,"aux"),("escrito","escrever","VERB","Part","","",1,"ROOT")],("perfect","indicative")),
    ("pt","Ela teria escrito.",[("teria","ter","AUX","Fin","Cnd","",1,"aux"),("escrito","escrever","VERB","Part","","",1,"ROOT")],("conditional_perfect","conditional")),
    ("nl","Zij heeft geschreven.",[("heeft","hebben","AUX","Fin","","Pres",1,"aux"),("geschreven","schrijven","VERB","Part","","",1,"ROOT")],("perfect","unmarked")),
    ("nl","Zij zou schrijven.",[("zou","zullen","AUX","Fin","","Past",1,"aux"),("schrijven","schrijven","VERB","Inf","","",1,"ROOT")],("conditional","conditional")),
])
def test_language_specific_periphrases(lang,text,specs,want):
    from lixity.grammatical_tense import compose_verbs

    groups=compose_verbs(text,_tokens(text,specs),lang)
    assert [(g.tense,g.mood)for g in groups] == [want]


def test_auxiliaries_of_nonverbal_predicate_share_one_perfect_group():
    from lixity.grammatical_tense import compose_verbs

    text="They have been happy."
    specs=[("have","have","AUX","Fin","","Pres",2,"aux"),
           ("been","be","AUX","Part","","Past",2,"cop"),
           ("happy","happy","ADJ","","","",2,"ROOT")]
    groups=compose_verbs(text,_tokens(text,specs),"en")
    assert [(g.tense,g.mood)for g in groups] == [("perfect","unmarked")]


def test_spanish_perfect_auxiliary_licenses_verbal_complement_not_a_noun():
    from lixity.grammatical_tense import compose_verbs

    text="Ella habrá escrito."
    specs=[("habrá","haber","AUX","Fin","Ind","Fut",0,"ROOT"),
           ("escrito","escribir","VERB","Part","","Past",0,"obj")]
    assert [g.tense for g in compose_verbs(text,_tokens(text,specs),"es")] == ["future_perfect"]
    text="Hay un escrito."
    specs=[("Hay","haber","AUX","Fin","Ind","Pres",0,"ROOT"),
           ("escrito","escrito","NOUN","","","",0,"obj")]
    assert [g.tense for g in compose_verbs(text,_tokens(text,specs),"es")] == ["present"]


def test_italian_perfect_copula_is_not_present_state():
    from lixity.grammatical_tense import compose_verbs

    text="Lei è stata felice."
    specs=[("è","essere","AUX","Fin","Ind","Pres",2,"aux"),
           ("stata","essere","AUX","Part","","Past",2,"cop"),
           ("felice","felice","ADJ","","","",2,"ROOT")]
    assert [g.tense for g in compose_verbs(text,_tokens(text,specs),"it")] == ["perfect"]


def test_french_reflexive_etre_perfect_and_spanish_passive_compound():
    from lixity.grammatical_tense import compose_verbs

    text="Elle se serait lavée."
    specs=[("se","se","PRON","","","",2,"expl:comp"),
           ("serait","être","AUX","Fin","Cnd","Pres",2,"aux:tense"),
           ("lavée","laver","VERB","Part","","Past",2,"ROOT")]
    groups=compose_verbs(text,_tokens(text,specs),"fr")
    assert [(g.tense,g.voice)for g in groups] == [("conditional_perfect","active")]
    text="La nota ha sido escrita."
    specs=[("ha","haber","AUX","Fin","Ind","Pres",2,"aux"),
           ("sido","ser","AUX","Part","","Past",2,"aux"),
           ("escrita","escribir","VERB","Part","","Past",2,"ROOT")]
    assert [(g.tense,g.voice)for g in compose_verbs(text,_tokens(text,specs),"es")] == [("perfect","passive")]


@pytest.mark.parametrize(("language", "text", "specs"), [
    ("en", "She has sung and danced or smiled.", [
        ("has", "have", "AUX", "Fin", "Ind", "Pres", 1, "aux"),
        ("sung", "sing", "VERB", "Part", "", "Past", 1, "ROOT"),
        ("danced", "dance", "VERB", "Part", "", "Past", 1, "conj"),
        ("smiled", "smile", "VERB", "Part", "", "Past", 2, "conj"),
    ]),
    ("fr", "Elle a chanté et dansé ou souri.", [
        ("a", "avoir", "AUX", "Fin", "Ind", "Pres", 1, "aux:tense"),
        ("chanté", "chanter", "VERB", "Part", "", "Past", 1, "ROOT"),
        ("dansé", "danser", "VERB", "Part", "", "Past", 1, "conj"),
        ("souri", "sourire", "VERB", "Part", "", "Past", 2, "conj"),
    ]),
    ("de", "Sie hat gesungen und getanzt oder gelächelt.", [
        ("hat", "haben", "AUX", "Fin", "Ind", "Pres", 0, "ROOT"),
        ("gesungen", "singen", "VERB", "Part", "", "", 0, "oc"),
        ("und", "und", "CCONJ", "", "", "", 1, "cd"),
        ("getanzt", "tanzen", "VERB", "Part", "", "", 2, "cj"),
        ("oder", "oder", "CCONJ", "", "", "", 3, "cd"),
        ("gelächelt", "lächeln", "VERB", "Part", "", "", 4, "cj"),
    ]),
])
def test_nested_coordination_inherits_shared_auxiliary(language, text, specs):
    """UD right-nesting A,(B,C) gives C a conjunct parent B, not A."""
    from lixity.grammatical_tense import compose_verbs

    tokens = _tokens(text, specs)
    groups = compose_verbs(text, tokens, language)
    assert [group.tense for group in groups] == ["perfect", "perfect", "perfect"]
    # Auxiliary inheritance must not depend on tuple order or previous calls.
    assert compose_verbs(text, tuple(reversed(tokens)), language) == groups
    assert compose_verbs(text, tokens, language) == groups


def test_finite_conjunct_owns_its_auxiliary_and_blocks_earlier_inheritance():
    from lixity.grammatical_tense import compose_verbs

    text = "She has sung, but he will dance or smile."
    specs = [
        ("has", "have", "AUX", "Fin", "Ind", "Pres", 1, "aux"),
        ("sung", "sing", "VERB", "Part", "", "Past", 1, "ROOT"),
        ("will", "will", "AUX", "Fin", "", "", 3, "aux"),
        ("dance", "dance", "VERB", "Inf", "", "", 1, "conj"),
        ("smile", "smile", "VERB", "Inf", "", "", 3, "conj"),
    ]
    groups = compose_verbs(text, _tokens(text, specs), "en")
    assert [group.tense for group in groups] == ["perfect", "future", "future"]
    assert groups[-1].components == ((21, 25), (35, 40))


def test_coordinated_compound_finds_anchor_after_nonfinite_auxiliary():
    from lixity.grammatical_tense import compose_verbs

    text = "She has sung and been praised."
    specs = [
        ("has", "have", "AUX", "Fin", "Ind", "Pres", 1, "aux"),
        ("sung", "sing", "VERB", "Part", "", "Past", 1, "ROOT"),
        ("been", "be", "AUX", "Part", "", "Past", 3, "aux:pass"),
        ("praised", "praise", "VERB", "Part", "", "Past", 1, "conj"),
    ]
    tokens = _tokens(text, specs)
    groups = compose_verbs(text, tokens, "en")
    assert [(group.tense, group.voice) for group in groups] == [
        ("perfect", "active"), ("perfect", "passive"),
    ]
    assert groups[-1].components == ((4, 7), (17, 21), (22, 29))
    assert compose_verbs(text, tuple(reversed(tokens)), "en") == groups


def test_malformed_coordination_cycle_terminates_without_a_tense_claim():
    """A malformed parser graph must neither hang nor invent a finite tense."""
    import subprocess
    import sys

    code = """
from lixity.grammatical_tense import compose_verbs
from lixity.linguistic_models import SyntaxToken
text = 'sung danced'
tokens = (
    SyntaxToken(0, 0, 4, 'sung', 'sing', 'VERB', '', 'Part', '', 'Past', 1, 'conj'),
    SyntaxToken(1, 5, 11, 'danced', 'dance', 'VERB', '', 'Part', '', 'Past', 0, 'conj'),
)
try:
    groups = compose_verbs(text, tokens, 'en')
except ValueError:
    print('rejected')
else:
    assert groups and all(group.tense == 'unresolved' for group in groups)
    print('unresolved')
"""
    # Constant synthetic code in an isolated interpreter bounds a broken loop.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=5, check=True,
    )
    assert result.stdout.strip() in {"rejected", "unresolved"}
