"""Independently annotated synthetic German verb-group regression cases."""

from typing import ClassVar

import pytest
from pydantic import ValidationError

from lixity.models import CorpusConfig


def test_model_selection_is_validated_instead_of_ignored():
    config = CorpusConfig(language="de", tense_model="de_core_news_sm", tense_scope="narration")
    assert config.model_dump()["tense_model"] == "de_core_news_sm"
    with pytest.raises(ValidationError):
        CorpusConfig(tense_model="")
    with pytest.raises(ValidationError):
        CorpusConfig(tense_scope="guess")
    with pytest.raises(ValidationError):
        CorpusConfig(tense_model="de_core_news_sm", praeteritum_regex="test")


def test_long_perfect_owns_auxiliary_and_head_without_absorbing_subordinate_clause():
    from lixity.grammatical_tense import compose_german
    from lixity.linguistic_models import SyntaxToken

    text = "Sie hat nach vielen langen Tagen gesungen, weil er übt."
    def token(i, word, lemma, pos, tag, form, mood, tense, head, dep):
        start = text.index(word)
        return SyntaxToken(i, start, start + len(word), word, lemma, pos, tag,
                         form, mood, tense, head, dep)
    tokens = (
        token(1, "hat", "haben", "AUX", "VAFIN", "Fin", "Ind", "Pres", 1, "ROOT"),
        token(7, "gesungen", "singen", "VERB", "VVPP", "Part", "", "", 1, "oc"),
        token(11, "übt", "üben", "VERB", "VVFIN", "Fin", "Ind", "Pres", 7, "mo"),
    )
    result = compose_german(text, tokens)
    assert [(g.tense, g.mood, g.components) for g in result] == [
        ("perfect", "indicative", ((4, 7), (33, 41))),
        ("present", "indicative", ((51, 54),)),
    ]


def test_missing_selected_model_fails_without_lexical_fallback():
    from lixity.language import resolve_language
    from lixity.tense import TenseMatcher

    config = CorpusConfig(language="de", tense_model="de_nonexistent_lixity_model")
    with pytest.raises(ValueError, match="unavailable"):
        TenseMatcher(config, resolve_language(config)).count("Sie übt in der feuchten Erde.")


def test_parser_backed_profile_and_evidence_use_one_group_result(monkeypatch):
    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup
    from lixity.pipeline import analyze_document
    from lixity.style_fingerprint import FingerprintThresholds

    # The expensive optional model is replaced only at its inference boundary;
    # composition has independent tests. Consumer contracts are exercised here.
    def annotated(text, _model):
        if "##" in text:
            raise AssertionError("Markdown must not reach the syntax model")
        start = text.index("übt")
        past = text.index("fand")
        return (VerbGroup(((start, start + 3),), "present", "indicative", "active"),
                VerbGroup(((past, past + 4),), "preterite", "indicative", "active"))
    monkeypatch.setattr(grammatical_tense, "analyze_verbs", annotated)
    monkeypatch.setattr(grammatical_tense, "model_identity", lambda _: {
        "policy": "german-verb-groups/1", "model": "de_test", "version": "1"})
    config = CorpusConfig(language="de", tense_model="de_test", tense_scope="narration")
    analysis = analyze_document('## Test\n\nSie übt. „Ich fand das gut.“\n', config,
                                FingerprintThresholds(), include_evidence=True)
    paragraph = analysis.paragraphs[0]
    assert (paragraph.present_hits, paragraph.past_hits) == (1, 0)
    assert analysis.evidence[0]["tense"]["grammar"]["groups"][1]["scope"] == "quotation"
    assert analysis.evidence[0]["tense"]["grammar"]["groups"][1]["selected"] is False
    assert analysis.evidence[0]["tense"]["present"]["spans"] == [
        {"start": 4, "end": 7, "count": 1}]


def test_future_passive_does_not_become_future_perfect():
    from lixity.grammatical_tense import compose_german
    from lixity.linguistic_models import SyntaxToken

    text = "Sie wird gerufen werden."
    tokens = (
        SyntaxToken(1, 4, 8, "wird", "werden", "AUX", "VAFIN", "Fin", "Ind", "Pres", 1, "ROOT"),
        SyntaxToken(2, 9, 16, "gerufen", "rufen", "VERB", "VVPP", "Part", "", "", 3, "oc"),
        SyntaxToken(3, 17, 23, "werden", "werden", "AUX", "VAINF", "Inf", "", "", 1, "oc"),
    )
    assert [(g.tense, g.voice) for g in compose_german(text, tokens)] == [("future", "passive")]


def test_cli_missing_model_returns_error_without_traceback_or_output(tmp_path, capsys):
    from lixity.cli import main

    manuscript = tmp_path / "draft.md"
    manuscript.write_text("## Test\n\nSie übt.\n", encoding="utf-8")
    before = manuscript.read_bytes()
    assert main(["profile", str(manuscript), "--language", "de", "--tense-model",
                 "de_nonexistent_lixity_model"]) == 1
    output = capsys.readouterr()
    assert "unavailable" in output.err and "Traceback" not in output.err
    assert not output.out
    assert manuscript.read_bytes() == before


@pytest.mark.parametrize(("sentence", "specs", "expected"), [
    ("Sie hat gesungen.", [("hat","haben","AUX","Fin","Ind","Pres",0,"ROOT"), ("gesungen","singen","VERB","Part","","",0,"oc")], ("perfect","indicative","active")),
    ("Sie hatte gesungen.", [("hatte","haben","AUX","Fin","Ind","Past",0,"ROOT"), ("gesungen","singen","VERB","Part","","",0,"oc")], ("pluperfect","indicative","active")),
    ("Sie hätte gesungen.", [("hätte","haben","AUX","Fin","Sub","Past",0,"ROOT"), ("gesungen","singen","VERB","Part","","",0,"oc")], ("pluperfect","subjunctive","active")),
    ("Sie wird gesungen haben.", [("wird","werden","AUX","Fin","Ind","Pres",0,"ROOT"), ("gesungen","singen","VERB","Part","","",2,"oc"), ("haben","haben","AUX","Inf","","",0,"oc")], ("future_perfect","indicative","active")),
    ("Sie ist gerufen worden.", [("ist","sein","AUX","Fin","Ind","Pres",0,"ROOT"), ("gerufen","rufen","VERB","Part","","",2,"oc"), ("worden","werden","AUX","Part","","",0,"oc")], ("perfect","indicative","passive")),
    ("Sie wird gerufen.", [("wird","werden","AUX","Fin","Ind","Pres",0,"ROOT"), ("gerufen","rufen","VERB","Part","","",0,"oc")], ("present","indicative","passive")),
    ("Sie hat kommen wollen.", [("hat","haben","AUX","Fin","Ind","Pres",0,"ROOT"), ("kommen","kommen","VERB","Inf","","",2,"oc"), ("wollen","wollen","AUX","Fin","Ind","Pres",0,"oc")], ("perfect","indicative","active")),
    ("Die Tür ist geschlossen.", [("ist","sein","AUX","Fin","Ind","Pres",0,"ROOT"), ("geschlossen","schließen","VERB","Part","","",0,"pd")], ("present","indicative","state_or_adjectival")),
    ("Sie ist gebaut.", [("ist","sein","AUX","Fin","Ind","Pres",0,"ROOT"), ("gebaut","bauen","VERB","Part","","",0,"oc")], ("unresolved","indicative","unresolved")),
    ("Übe!", [("Übe","üben","VERB","Fin","Imp","",0,"ROOT")], ("imperative","imperative","active")),
])
def test_composition_follows_verbal_periphrases(sentence, specs, expected):
    from lixity.grammatical_tense import compose_german
    from lixity.linguistic_models import SyntaxToken

    tokens = []
    for i, (word, lemma, pos, form, mood, tense, head, dep) in enumerate(specs):
        start = sentence.index(word)
        tokens.append(SyntaxToken(i,start,start+len(word),word,lemma,pos,"",form,mood,tense,head,dep))
    groups = compose_german(sentence, tuple(tokens))
    assert len(groups) == 1
    assert (groups[0].tense, groups[0].mood, groups[0].voice) == expected
    for start, end in groups[0].components:
        assert sentence[start:end] in [s[0] for s in specs]


def test_quotation_scope_survives_paragraph_boundaries_and_repeated_text(monkeypatch):
    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup
    from lixity.pipeline import analyze_document
    from lixity.style_fingerprint import FingerprintThresholds

    def annotate(text, _model):
        word = "sagt" if "sagt" in text else "war"
        start = text.index(word)
        return (VerbGroup(((start,start+len(word)),), "present" if word == "sagt" else "preterite",
                          "indicative", "active"),)
    monkeypatch.setattr(grammatical_tense,"analyze_verbs",annotate)
    monkeypatch.setattr(grammatical_tense,"model_identity",lambda _: {"policy":"test","model":"de_test","version":"1"})
    config = CorpusConfig(language="de",tense_model="de_test",tense_scope="narration")
    text = '## Test\n\nSie sagt: „Es war schön.\n\nEs war schön.“\n\nEs war schön.\n'
    result = analyze_document(text,config,FingerprintThresholds(),include_evidence=True)
    assert [(p.present_hits,p.past_hits) for p in result.paragraphs] == [(1,0),(0,0),(0,1)]
    assert result.evidence[1]["tense"]["grammar"]["groups"][0]["scope"] == "quotation"
    assert result.evidence[2]["tense"]["grammar"]["groups"][0]["scope"] == "narration"


@pytest.mark.parametrize("command", ["build", "dashboard"])
def test_cli_export_reports_missing_model_without_replacing_output(tmp_path, capsys, command):
    from lixity.cli import main

    source = tmp_path / "draft.md"
    source.write_text("## Test\n\nSie übt.\n",encoding="utf-8")
    output = tmp_path / "copy.html"
    output.write_text("previous",encoding="utf-8")
    args = [command,str(source),"--language","de","--tense-model","de_nonexistent_lixity_model"]
    if command == "dashboard":
        args += ["-o",str(output)]
    assert main(args) == 1
    assert "unavailable" in capsys.readouterr().err
    assert output.read_text(encoding="utf-8") == "previous"


def test_quote_capture_contract_does_not_exclude_reporting_clause(monkeypatch):
    import re

    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup, grammatical_parts

    monkeypatch.setattr(grammatical_tense,"analyze_verbs",lambda *_: (
        VerbGroup(((3,8),),"preterite","indicative","active"),
        VerbGroup(((15,18),),"present","indicative","active")))
    monkeypatch.setattr(grammatical_tense,"model_identity",lambda _: {})
    result = grammatical_parts(['Er sagte: „Sie übt.“'],"de_test","narration",re.compile(r'Er sagte: „([^“]+)“'))[0]
    assert [g["scope"] for g in result["groups"]] == ["narration","quotation"]


def test_quotation_context_stops_at_chapter_boundary_and_includes_block_quotes(monkeypatch):
    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup
    from lixity.pipeline import analyze_document
    from lixity.style_fingerprint import FingerprintThresholds

    def annotate(text, _model):
        word = "war" if "war" in text else "übt"
        start = text.index(word)
        return (VerbGroup(((start,start+len(word)),), "preterite" if word == "war" else "present",
                          "indicative","active"),)
    monkeypatch.setattr(grammatical_tense,"analyze_verbs",annotate)
    monkeypatch.setattr(grammatical_tense,"model_identity",lambda _: {})
    config = CorpusConfig(language="de",tense_model="de_test",tense_scope="narration")
    # Unmatched quote marks in different chapters must not form one quotation.
    text = '## One\n\n„Es war gut.\n\n## Two\n\nEs war gut.“\n\nSie übt.\n'
    result = analyze_document(text,config,FingerprintThresholds())
    assert [(p.present_hits,p.past_hits) for p in result.paragraphs] == [(0,1),(0,1),(1,0)]
    # The profile omits blockquote paragraphs, but retains their quotation context.
    text = '## One\n\n> „Es war gut.\n\nSie übt.“\n\nSie übt.\n'
    result = analyze_document(text,config,FingerprintThresholds())
    assert [(p.present_hits,p.past_hits) for p in result.paragraphs] == [(0,0),(1,0)]


def test_native_startup_model_override_is_consumed_without_writing_project(tmp_path):
    from lixity.server.handler import LixityServerHandler

    source = tmp_path / "draft.md"
    source.write_text("## Test\n\nSie übt.\n",encoding="utf-8")
    config = tmp_path / "lixity.toml"
    config.write_text('language = "de"\n',encoding="utf-8")
    class Handler(LixityServerHandler):
        source_input = str(source)
        project_root = str(tmp_path)
        language = "de"
        project_open_overrides: ClassVar[dict[str,str]] = {"tense_model":"de_nonexistent_lixity_model", "tense_scope":"narration"}
    with pytest.raises(ValueError,match="unavailable"):
        Handler.refresh()
    assert config.read_text(encoding="utf-8") == 'language = "de"\n'


def test_installed_recommended_model_on_synthetic_constructions():
    import json
    from pathlib import Path

    pytest.importorskip("de_core_news_md", reason="Optional locally installed German model")
    from lixity.grammatical_tense import analyze_verbs

    cases = json.loads((Path(__file__).parent / "fixtures/german_verb_groups.json").read_text(encoding="utf-8"))["cases"]
    # Known upstream imperative error is disclosed in STABILITY.md and remains
    # in the comparison tool's score. Do not turn it into an accepted gold label.
    for case in cases:
        if case["text"] == "Übe jeden Tag!":
            continue
        groups = analyze_verbs(case["text"], "de_core_news_md")
        assert [[g.tense,g.mood] for g in groups if g.reason != "missing_finite"] == case["groups"], case["text"]


def test_all_scope_keeps_resolved_group_with_partially_quoted_components(monkeypatch):
    import re

    from lixity import grammatical_tense
    from lixity.grammatical_tense import VerbGroup, grammatical_parts

    monkeypatch.setattr(grammatical_tense,"analyze_verbs",lambda *_: (
        VerbGroup(((4,7),(9,17)),"perfect","indicative","active"),))
    monkeypatch.setattr(grammatical_tense,"model_identity",lambda _: {})
    pattern=re.compile(r'„([^“]+)“')
    group=grammatical_parts(['Sie hat „gesungen“.'],"de_test","all",pattern)[0]["groups"][0]
    assert group["scope"] == "unresolved"
    assert group["selected"] is True and group["bucket"] == "past"
    group=grammatical_parts(['Sie hat „gesungen“.'],"de_test","narration",pattern)[0]["groups"][0]
    assert group["selected"] is False


def test_german_perfect_state_passive_does_not_count_as_present():
    from lixity.grammatical_tense import compose_german
    from lixity.linguistic_models import SyntaxToken

    text="Die Tür ist geschlossen gewesen."
    tokens=(
        SyntaxToken(0,8,11,"ist","sein","AUX","VAFIN","Fin","Ind","Pres",0,"ROOT"),
        SyntaxToken(1,12,23,"geschlossen","schließen","VERB","VVPP","Part","","",2,"pd"),
        SyntaxToken(2,24,31,"gewesen","sein","AUX","VAPP","Part","","",0,"oc"))
    assert [g.tense for g in compose_german(text,tokens)] == ["perfect"]


def test_unflagged_grammatical_paragraph_keeps_counts_for_inspector():
    from lixity.pipeline import analyze_document
    from lixity.style_fingerprint import FingerprintThresholds
    from lixity.ui import render_dashboard
    from tests.support import HtmlControls

    analysis=analyze_document('## Test\n\nSie geht.\n',CorpusConfig(language="de"),FingerprintThresholds())
    paragraph=analysis.paragraphs[0]
    assert not paragraph.is_flagged
    paragraph.tense_analysis={"schema_version":"grammatical-tense/1","groups":[]}
    html=render_dashboard(analysis.chapters,analysis.paragraphs,metrics=analysis.metrics,
                          fingerprint=analysis.fingerprint,controls=True)
    attrs=HtmlControls(html).elements["p-0"]
    assert (attrs["data-pre"],attrs["data-pas"]) == ("1","0")
    assert "data-severity" not in attrs


def test_website_export_applies_explicit_grammatical_model(tmp_path):
    from lixity.site_export import prepare_site

    (tmp_path / "draft.md").write_text('## Test\n\nSie übt.\n',encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript="draft.md"\nlanguage="de"\n',encoding="utf-8")
    with pytest.raises(ValueError,match="unavailable"):
        prepare_site(tmp_path,tense_model="de_nonexistent_lixity_model")
