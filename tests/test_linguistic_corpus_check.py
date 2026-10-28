"""Independent synthetic CoNLL-U alignment and denominator regressions."""

import hashlib

import pytest

from lixity.linguistic_models import SyntaxToken


def _row(i, form, lemma="_", pos="PUNCT", feats="_", misc="_"):
    return f"{i}\t{form}\t{lemma}\t{pos}\t_\t{feats}\t0\troot\t_\t{misc}"


def _script():
    from scripts import check_linguistic_corpus

    return check_linguistic_corpus


def test_reconstruction_preserves_multiword_surface_and_spaceafter():
    checker = _script()
    corpus = "\n".join([
        "# sent_id = synthetic-1", _row("1-2", "Farlo", misc="SpaceAfter=No"),
        _row(1, "Fare", "fare", "VERB", "VerbForm=Inf"), _row(2, "lo", "lo", "PRON"),
        _row(3, "."), "", "",
    ])
    sentence = next(checker.read_conllu(corpus))
    assert sentence.text == "Farlo."
    assert [(w.start, w.end) for w in sentence.words] == [(0, 5), (0, 5), (5, 6)]


def test_authoritative_text_alignment_does_not_guess_normalized_offsets():
    checker = _script()
    corpus = "# text = She  writes.\n" + "\n".join([
        _row(1, "She", "she", "PRON"),
        _row(2, "writes", "write", "VERB", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        _row(3, "."), "", "",
    ])
    sentence = next(checker.read_conllu(corpus))
    assert sentence.text == "She  writes."
    assert (sentence.words[1].start, sentence.words[1].end) == (5, 11)
    bad = next(checker.read_conllu(corpus.replace("# text = She  writes.", "# text = She wrote.")))
    assert bad.source_error == "surface_text_mismatch"


def test_failures_and_missing_predictions_stay_in_gold_denominator(tmp_path, monkeypatch):
    checker = _script()
    corpus = "\n\n".join(
        f"# sent_id = {word}\n# text = {word}\n" + _row(
            1, word, "write", "VERB", "Mood=Ind|Tense=Pres|VerbForm=Fin",
        ) for word in ("Writes", "Fails", "Misses", "Unknown")
    ) + "\n\n"
    path = tmp_path / "synthetic.conllu"
    path.write_text(corpus, encoding="utf-8")

    def parse(text, model):
        if text == "Fails":
            raise ValueError("unavailable")
        if text == "Misses":
            return ()
        return (SyntaxToken(0, 0, len(text), text, "write", "VERB", "VBZ", "Fin", "Ind",
                          "" if text == "Unknown" else "Pres", 0, "root"),)

    monkeypatch.setattr(checker, "parse_tokens", parse)
    monkeypatch.setattr(checker, "model_identity", lambda name: {"model": name, "language": "en"})
    report = checker.check_corpus(path, "en", "test", limit=4, provenance={"corpus": "synthetic"})
    assert report["corpus_sha256"] == hashlib.sha256(corpus.encode()).hexdigest()
    assert report["sentences_selected"] == 4
    assert report["parse_failures"] == 1
    assert report["finite_verb_detection"]["parse_unscored_tokens"] == 1
    assert report["finite_verb_detection"]["gold_alignment_misses"] == 1
    assert report["alignment_misses"] == 1
    assert report["metrics"]["Tense"] == {
        "eligible": 4, "compared": 2, "correct": 1, "missing_prediction": 1,
        "match_rate_all_eligible": 0.25,
    }
    assert report["benchmark_kind"] == "token_features_not_verb_group_tense"


def test_missing_gold_features_and_nonindicative_forms_are_reported(tmp_path, monkeypatch):
    checker = _script()
    path = tmp_path / "synthetic.conllu"
    path.write_text("\n".join([
        "# text = Go wrote maybe", _row(1, "Go", "go", "VERB", "Mood=Imp|VerbForm=Fin"),
        _row(2, "wrote", "write", "VERB", "Tense=Past|VerbForm=Fin"),
        _row(3, "maybe", "_", "VERB"), "", "",
    ]))
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: ())
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    report = checker.check_corpus(path, "en", "test", limit=1, provenance={})
    assert report["missing_gold_features"]["VerbForm"] == 1
    assert report["missing_gold_features"]["Mood"] == 2
    assert report["metrics"]["Tense"]["eligible"] == 0
    assert report["metrics"]["Tense"]["match_rate_all_eligible"] is None
    assert report["gold_finite_tokens"] == 2


def test_first_n_selection_language_validation_and_malformed_input(tmp_path, monkeypatch):
    checker = _script()
    path = tmp_path / "synthetic.conllu"
    path.write_text("# text = Hi\n" + _row(1, "Hi", "hi", "INTJ") + "\n\n" +
                    "# text = Bye\n" + _row(1, "Bye", "bye", "INTJ") + "\n\n")
    seen = []
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: seen.append(text) or ())
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    checker.check_corpus(path, "en", "test", limit=1, provenance={})
    assert seen == ["Hi"]
    with pytest.raises(ValueError, match="language"):
        checker.check_corpus(path, "fr", "test", limit=1, provenance={})
    with pytest.raises(ValueError):
        checker.check_corpus(path, "en", "test", limit=0, provenance={})
    with pytest.raises(ValueError, match="10"):
        list(checker.read_conllu("1\tbroken\n\n"))


def test_multiword_and_bad_source_alignment_never_raise_the_match_rate(tmp_path, monkeypatch):
    checker = _script()
    path = tmp_path / "synthetic.conllu"
    path.write_text("\n".join([
        "# text = Can't", _row("1-2", "Can't"),
        _row(1, "Can", "can", "AUX", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        _row(2, "not", "not", "PART"), "",
        "# text = Wrong", _row(1, "writes", "write", "VERB", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        "", "",
    ]))
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: (
        SyntaxToken(0, 0, 5, text, "can", "AUX", "MD", "Fin", "Ind", "Pres", 0, "root"),
    ))
    report = checker.check_corpus(path, "en", "test", limit=2, provenance={})
    assert report["alignment_misses"] == 1
    assert report["source_alignment_failures"] == 1
    assert report["finite_verb_detection"]["source_unscored_tokens"] == 1
    assert report["metrics"]["Tense"]["eligible"] == 2
    assert report["metrics"]["Tense"]["compared"] == 0
    assert report["metrics"]["Tense"]["match_rate_all_eligible"] == 0


def test_finite_detection_counts_false_positive_on_gold_adjective(tmp_path, monkeypatch):
    checker = _script()
    path = tmp_path / "detection.conllu"
    path.write_text("\n".join([
        "# text = White writes danced quietly .",
        _row(1, "White", "white", "ADJ"),
        _row(2, "writes", "write", "VERB", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        _row(3, "danced", "dance", "VERB", "Mood=Ind|Tense=Past|VerbForm=Fin"),
        _row(4, "quietly", "quietly", "ADV"), _row(5, "."), "", "",
    ]))
    predicted = (
        SyntaxToken(0, 0, 5, "White", "white", "VERB", "VB", "Fin", "Ind", "Pres", 0, "root"),
        SyntaxToken(1, 6, 12, "writes", "write", "VERB", "VBZ", "Fin", "Ind", "Pres", 1, "root"),
        SyntaxToken(2, 13, 19, "danced", "dance", "ADJ", "JJ", "", "", "", 1, "amod"),
        SyntaxToken(3, 20, 27, "quietly", "quietly", "ADV", "RB", "", "", "", 1, "advmod"),
        SyntaxToken(4, 28, 29, ".", ".", "PUNCT", ".", "", "", "", 1, "punct"),
    )
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: predicted)
    report = checker.check_corpus(path, "en", "test", limit=1, provenance={})
    detection = report["finite_verb_detection"]
    assert (detection["true_positive"], detection["false_positive"],
            detection["false_negative"], detection["true_negative"]) == (1, 1, 1, 2)
    assert detection["precision"] == 0.5 and detection["recall"] == 0.5
    assert detection["aligned_tokens"] == 5
    # The extra false-positive adjective must not change the existing Tense denominator.
    assert report["metrics"]["Tense"] == {
        "eligible": 2, "compared": 2, "correct": 1, "missing_prediction": 1,
        "match_rate_all_eligible": 0.5,
    }


@pytest.mark.parametrize("unknown_form", ["_", "VerbForm=Fin,Inf"])
def test_unknown_gold_finiteness_is_not_invented_and_prediction_abstention_is_visible(tmp_path, monkeypatch, unknown_form):
    checker = _script()
    path = tmp_path / "unknown.conllu"
    path.write_text("\n".join([
        "# text = Writes Maybe Hidden",
        _row(1, "Writes", "write", "VERB", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        _row(2, "Maybe", "maybe", "VERB", unknown_form), _row(3, "Hidden", "hidden", "ADJ"), "", "",
    ]))
    predicted = (
        SyntaxToken(0, 0, 6, "Writes", "write", "VERB", "VB", "", "", "", 0, "root"),
        SyntaxToken(1, 7, 12, "Maybe", "maybe", "VERB", "VB", "Fin", "Ind", "Pres", 0, "conj"),
        SyntaxToken(2, 13, 19, "Hidden", "hide", "VERB", "VB", "", "", "", 0, "conj"),
    )
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: predicted)
    report = checker.check_corpus(path, "en", "test", limit=1, provenance={})
    detection = report["finite_verb_detection"]
    assert detection["unknown_gold_finiteness"] == 1
    assert detection["unknown_prediction_finiteness"] == 2
    assert detection["false_negative"] == 1 and detection["false_positive"] == 0
    assert detection["true_negative"] == 1 and detection["true_positive"] == 0
    assert detection["precision"] is None and detection["recall"] == 0
    assert detection["aligned_tokens"] == 3


def test_ambiguous_alignment_stays_outside_detection_scores(tmp_path, monkeypatch):
    checker = _script()
    path = tmp_path / "alignment.conllu"
    path.write_text("\n".join([
        "# text = Can't", _row("1-2", "Can't"),
        _row(1, "Can", "can", "AUX", "Mood=Ind|Tense=Pres|VerbForm=Fin"),
        _row(2, "not", "not", "PART"), "", "",
    ]))
    monkeypatch.setattr(checker, "model_identity", lambda name: {"language": "en"})
    monkeypatch.setattr(checker, "parse_tokens", lambda text, name: (
        SyntaxToken(0, 0, 5, text, "can", "AUX", "MD", "Fin", "Ind", "Pres", 0, "root"),
    ))
    report = checker.check_corpus(path, "en", "test", limit=1, provenance={})
    detection = report["finite_verb_detection"]
    assert detection["gold_tokens"] == 2 and detection["aligned_tokens"] == 0
    assert detection["gold_alignment_misses"] == 2 and detection["prediction_alignment_misses"] == 1
    assert detection["true_positive"] == detection["false_positive"] == detection["false_negative"] == 0
    assert detection["precision"] is None and detection["recall"] is None
    assert report["metrics"]["Tense"]["eligible"] == 1
