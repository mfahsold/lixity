"""Local parser boundaries, independent of grammatical classification quality."""

import os
import sys
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest


def _adapter():
    from lixity import linguistic_models

    return linguistic_models


@pytest.fixture
def adapter(monkeypatch):
    module = _adapter()
    module._model.cache_clear()
    monkeypatch.setattr(module, "version", lambda name: "test-runtime")
    yield module
    module._model.cache_clear()


class _Morph:
    def get(self, name):
        return {"VerbForm": ["Fin"], "Mood": ["Ind"], "Tense": ["Pres"]}.get(name, [])


class _Doc(list):
    def has_annotation(self, name):
        return name in {"POS", "MORPH", "DEP", "LEMMA"}


def _spacy_pipeline(lang="en", pipes=("parser", "tagger"), doc=None):
    token = SimpleNamespace(i=0, idx=0, text="Writes", lemma_="write", pos_="VERB",
                            tag_="VBZ", morph=_Morph(), dep_="ROOT")
    token.head = token
    parsed = _Doc([token]) if doc is None else doc

    class Pipeline:
        def __init__(self):
            self.meta = {"version": "test-model-1"}
            self.pipe_names = list(pipes)

        def __call__(self, text):
            return parsed

    pipeline = Pipeline()
    pipeline.lang = lang
    return pipeline


def _install_spacy(monkeypatch, pipeline):
    def load(name, **kwargs):
        assert kwargs == {"exclude": ["ner"]}
        return pipeline

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(load=load, __version__="test-runtime"))


def test_english_tagger_pipeline_produces_immutable_tokens_and_identity(adapter, monkeypatch):
    _install_spacy(monkeypatch, _spacy_pipeline())
    result = adapter.parse_tokens("Writes", "en_test")
    assert len(result) == 1
    token = result[0]
    assert (token.text, token.lemma, token.form, token.tense, token.head) == (
        "Writes", "write", "Fin", "Pres", 0,
    )
    assert token.start == 0 and token.end == 6
    with pytest.raises(FrozenInstanceError):
        token.tense = "Past"
    identity = adapter.model_identity("en_test")
    assert identity["model"] == "en_test"
    assert identity["version"] == "test-model-1"
    assert identity["runtime"] == "spacy"
    assert identity["language"] == "en"
    assert identity["spacy_version"] == identity["runtime_version"]
    assert adapter.parser_language("en_test") == "en"


@pytest.mark.parametrize("lang,pipes", [
    ("xx", ("parser", "morphologizer")),
    ("en", ("tagger",)),
    ("fr", ("parser",)),
])
def test_rejects_unsupported_language_or_incomplete_pipeline(adapter, monkeypatch, lang, pipes):
    _install_spacy(monkeypatch, _spacy_pipeline(lang, pipes))
    with pytest.raises(ValueError):
        adapter.parse_tokens("Writes", f"{lang}_test")


def test_missing_annotations_and_wrong_offsets_fail_explicitly(adapter, monkeypatch):
    class MissingDoc(_Doc):
        def has_annotation(self, name):
            return name != "MORPH"

    _install_spacy(monkeypatch, _spacy_pipeline(doc=MissingDoc([object()])))
    with pytest.raises(ValueError, match="annotation"):
        adapter.parse_tokens("Writes", "en_missing_annotations")
    adapter._model.cache_clear()
    _install_spacy(monkeypatch, _spacy_pipeline())
    with pytest.raises(ValueError, match="offset"):
        adapter.parse_tokens("Wrong!", "en_wrong_offsets")


def test_missing_model_never_invokes_download_and_interrupts_propagate(adapter, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("not installed")

    def forbidden(*args, **kwargs):
        pytest.fail("Model adapter must not request any download")

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(
        load=unavailable, cli=SimpleNamespace(download=forbidden), __version__="test",
    ))
    with pytest.raises(ValueError, match="unavailable"):
        adapter.parse_tokens("Writes", "en_missing_model")

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(sys.modules["spacy"], "load", interrupted)
    with pytest.raises(KeyboardInterrupt):
        adapter.parse_tokens("Writes", "en_missing_model")


def test_cache_reuses_two_models_and_evicts_oldest(adapter, monkeypatch):
    loaded = []

    def load(name, **kwargs):
        loaded.append(name)
        return _spacy_pipeline()

    monkeypatch.setitem(sys.modules, "spacy", SimpleNamespace(load=load, __version__="test"))
    for name in ("en_one", "en_two", "en_one", "en_three", "en_two"):
        adapter.parser_language(name)
    assert loaded == ["en_one", "en_two", "en_three", "en_two"]


def _word(i, text, lemma, head, *, start=None, end=None, feats=""):
    return SimpleNamespace(id=i, text=text, lemma=lemma, upos="VERB", xpos="V",
                           feats=feats, head=head, deprel="root" if head == 0 else "aux",
                           start_char=start, end_char=end)


def test_stanza_mwt_spans_use_original_text_and_global_heads(adapter, monkeypatch, tmp_path):
    # The two expanded words must both refer to the same actual source span.
    text = "Farlo. Scrive."
    first = _word(1, "Fare", "fare", 0, feats="VerbForm=Inf")
    clitic = _word(2, "lo", "lo", 1)
    clitic.upos = "PRON"
    final = _word(1, "Scrive", "scrivere", 0, start=7, end=13,
                  feats="Mood=Ind|Tense=Pres|VerbForm=Fin|Aspect=Imp")
    sentences = [
        SimpleNamespace(words=[first, clitic], tokens=[
            SimpleNamespace(start_char=0, end_char=5, words=[first, clitic]),
        ]),
        SimpleNamespace(words=[final], tokens=[
            SimpleNamespace(start_char=7, end_char=13, words=[final]),
        ]),
    ]

    def pipeline(**kwargs):
        assert kwargs["lang"] == "it"
        assert kwargs["package"] is None
        assert kwargs["download_method"] is None
        assert kwargs["use_gpu"] is False
        assert kwargs["dir"] == str(tmp_path)
        assert kwargs["processors"] == {
            "tokenize": "markit_nocharlm", "mwt": "markit", "pos": "markit_nocharlm",
            "lemma": "markit_nocharlm", "depparse": "markit_nocharlm",
        }
        return lambda text: SimpleNamespace(sentences=sentences)

    def forbidden(*args, **kwargs):
        pytest.fail("Model adapter must not request any download")

    monkeypatch.setenv("STANZA_RESOURCES_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "stanza", SimpleNamespace(
        Pipeline=pipeline, download=forbidden, __version__="test-stanza",
        __resources_version__="test-resources-1",
    ))
    tokens = adapter.parse_tokens(text, "stanza:it_markit")
    assert [(t.i, t.head, t.start, t.end, t.text, t.lemma) for t in tokens] == [
        (0, 0, 0, 5, "Farlo", "fare"),
        (1, 0, 0, 5, "Farlo", "lo"),
        (2, 2, 7, 13, "Scrive", "scrivere"),
    ]
    assert tokens[-1].aspect == "Imp"
    assert adapter.model_identity("stanza:it_markit")["runtime"] == "stanza"
    assert adapter.model_identity("stanza:it_markit")["version"] == "test-resources-1"


def test_stanza_unknown_profile_is_not_silently_defaulted(adapter):
    with pytest.raises(ValueError):
        adapter.parse_tokens("Scrive.", "stanza:it_unknown")


def test_real_italian_local_offsets_when_explicitly_enabled(adapter):
    if not os.environ.get("STANZA_RESOURCES_DIR"):
        pytest.skip("Set STANZA_RESOURCES_DIR to explicitly installed MarkIT resources")
    pytest.importorskip("stanza")
    text = "Farlo sarebbe utile. Lei aveva scritto una nota."
    tokens = adapter.parse_tokens(text, "stanza:it_markit")
    assert tokens
    assert all(text[t.start:t.end] == t.text for t in tokens)
    assert len({t.i for t in tokens}) == len(tokens)
    assert all(t.head in {item.i for item in tokens} for t in tokens)
    assert any(t.lemma == "scrivere" for t in tokens)


def test_stanza_unknown_word_morphology_is_exposed_as_unresolved(adapter, monkeypatch):
    from lixity.grammatical_tense import compose_verbs

    first = _word(1,"Scrive","scrivere",0,start=0,end=6,
                  feats="Mood=Ind|Tense=Pres|VerbForm=Fin")
    unknown = _word(2,"X","x",0,start=7,end=8)
    sentence = SimpleNamespace(words=[first,unknown],tokens=[
        SimpleNamespace(start_char=0,end_char=6,words=[first]),
        SimpleNamespace(start_char=7,end_char=8,words=[unknown])])
    monkeypatch.setitem(sys.modules,"stanza",SimpleNamespace(
        Pipeline=lambda **_: lambda _:SimpleNamespace(sentences=[sentence]),
        __resources_version__="test"))
    tokens = adapter.parse_tokens("Scrive X","stanza:it_markit")
    groups = compose_verbs("Scrive X",tokens,"it")
    assert [(g.tense,g.reason)for g in groups] == [("present",""),("unresolved","missing_finite")]
