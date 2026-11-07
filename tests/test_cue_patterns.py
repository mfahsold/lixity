"""Cue configuration errors stay inside the shared ValueError/CLI boundary."""

import pytest

from lixity import api
from lixity.cli import main
from lixity.language import compile_pattern
from lixity.models import CorpusConfig

CUE_FIELDS = (
    "dialogue_regex", "filter_verbs_regex", "praesens_regex", "praeteritum_regex",
    "passive_regex", "nominal_regex", "adjective_regex", "sensory_regex",
)
PATTERN_TABLES = ("signal_keywords", "motif_regexes")


@pytest.mark.parametrize("pattern", ["(", "[a-"])
def test_cue_compiler_rejects_malformed_syntax_as_value_error(pattern):
    with pytest.raises(ValueError, match="valid regular expression"):
        compile_pattern(pattern)


@pytest.mark.parametrize("field", CUE_FIELDS)
def test_corpus_config_rejects_malformed_cues_before_analysis(field):
    with pytest.raises(ValueError, match=field):
        CorpusConfig(**{field: "("})


@pytest.mark.parametrize("field", PATTERN_TABLES)
def test_corpus_config_identifies_invalid_named_pattern(field):
    with pytest.raises(ValueError, match=field) as error:
        CorpusConfig(**{field: {"Synthetic cue": "("}})
    assert "Synthetic cue" in str(error.value)


@pytest.mark.parametrize("field", (*CUE_FIELDS, *PATTERN_TABLES))
def test_public_analysis_api_keeps_invalid_pattern_errors_actionable(field):
    value = {"Synthetic cue": "("} if field in PATTERN_TABLES else "("
    with pytest.raises(ValueError, match=field):
        api.analyze("## One\n\nMara waits.", **{field: value})


@pytest.mark.parametrize("configuration,field", [
    ('filter_verbs_regex = "("\n', "filter_verbs_regex"),
    ('[signal_keywords]\nSynthetic = "("\n', "signal_keywords"),
    ('[motif_regexes]\nSynthetic = "("\n', "motif_regexes"),
])
def test_invalid_cue_cli_reports_error_without_output_or_traceback(tmp_path, capsys, configuration, field):
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text("## One\n\nMara waits.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(configuration, encoding="utf-8")
    destination = tmp_path / "report.json"
    destination.write_text("keep existing report", encoding="utf-8")
    assert main(["analyze", str(manuscript), "--project", str(tmp_path), "--json",
                 "-o", str(destination)]) == 1
    output = capsys.readouterr()
    assert output.out == "" and field in output.err and "Traceback" not in output.err
    assert destination.read_text(encoding="utf-8") == "keep existing report"


def test_valid_cues_keep_empty_capture_and_scoped_flag_semantics():
    assert compile_pattern("").findall("door") == []
    assert compile_pattern(r"(door)|(window)").findall("DOOR window") == [("DOOR", ""), ("", "window")]
    patterns = {"Folded": "(door)", "Exact": "(?-i:Door)"}
    result = api.analyze(
        '## One\n\nDOOR door. "Door"?\n',
        signal_keywords=patterns, motif_regexes=patterns,
        filter_verbs_regex=r"(door)|(window)", passive_regex="", nominal_regex="",
        dialogue_regex=r'"(Door)"(\?)?',
    )["metrics"]
    assert result["signal_counts"] == {"Folded": 3, "Exact": 1}
    assert result["chapters"][0]["motif_counts"] == {"Folded": 3, "Exact": 1}
    assert result["filter_count"] == 3 and result["dialog_words"] == 1
    assert result["passive_density"] == result["nominalization_density"] == 0.0


@pytest.mark.parametrize(
    "language,text",
    [
        ("de", "## Kapitel 1\n\nDer Duft von frischem Kaffee und das kalte Licht drangen durch den Raum."),
        ("en", "## Chapter 1\n\nThe cold light and sweet scent of coffee filled the silent room."),
        ("fr", "## Chapitre 1\n\nLa lumière froide et le parfum doux du café remplissaient la pièce."),
        ("es", "## Capítulo 1\n\nLa luz fría y el aroma dulce del café llenaban la habitación."),
        ("it", "## Capitolo 1\n\nLa luce fredda e il profumo dolce del caffè riempivano la stanza."),
        ("pt", "## Capítulo 1\n\nA luz fria e o aroma doce do café enchiam o quarto."),
        ("nl", "## Hoofdstuk 1\n\nHet koude licht en de geur van koffie vulden de kamer."),
    ],
)
def test_sensory_cues_multilingual_coverage(language: str, text: str):
    result = api.analyze(text, language=language)["metrics"]
    assert result["sensory_count"] > 0
    assert result["sensory_density"] > 0.0
    assert result["chapters"][0]["sensory_count"] == result["sensory_count"]
    assert result["chapters"][0]["sensory_density"] == result["sensory_density"]

