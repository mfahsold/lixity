"""Low-level reports share English defaults and require explicit detection."""

import pytest

from lixity.characters import character_presence, presence_report
from lixity.dialogue import dialogue_report
from lixity.models import CorpusConfig
from lixity.motifs import motif_report
from lixity.pacing import pacing_report
from lixity.showing import showing_report

TEXT = "## Unit\n\n12345.\n\n## Next\n\nMara.\n"


@pytest.mark.parametrize("report", [dialogue_report, pacing_report, motif_report, showing_report])
def test_low_level_report_defaults_to_english_and_preserves_explicit_auto(report):
    implicit = report(TEXT)
    english = report(TEXT, config=CorpusConfig())
    automatic = report(TEXT, config=CorpusConfig(language="auto"))
    assert implicit.language == english.language == "en"
    assert implicit.to_dict() == english.to_dict()
    assert automatic.language == "generic"


@pytest.mark.parametrize("report", [dialogue_report, pacing_report, motif_report, showing_report])
def test_low_level_explicit_auto_still_detects_supported_language(report):
    text = "## Beispiel\n\nDer Wagen steht an der Tür. Die Frau wartet und der Mann geht.\n"
    assert report(text, config=CorpusConfig(language="auto")).language == "de"


@pytest.mark.parametrize("report", [character_presence, presence_report])
def test_character_defaults_preserve_english_chapter_identity(report):
    def mentioned_chapters(config):
        result = report(TEXT, ["Mara"], config=config)
        return (result[0].chapters_present if isinstance(result, list)
                else result["figures"][0]["chapters_present"])

    assert mentioned_chapters(None) == [2]
    assert mentioned_chapters(CorpusConfig()) == [2]
    assert mentioned_chapters(CorpusConfig(language="auto")) == [1]


def test_configurable_dialogue_and_sentence_bins():
    from lixity.analyzer import CorpusAnalyzer

    dialogue_text = '## Chapter 1\n\n"Hello," she said. "This is a slightly longer sentence than before."\n\n"Yes."\n'
    default_rep = dialogue_report(dialogue_text)
    # Default short_turn_max_words = 12: all 3 turns (1 word, 8 words, 1 word) are <= 12
    assert default_rep.short_turns == 3
    assert default_rep.long_turns == 0

    tight_config = CorpusConfig(short_turn_max_words=1, long_turn_min_words=5)
    tight_rep = dialogue_report(dialogue_text, tight_config)
    # 2 turns with 1 word ("Hello", "Yes") are <= 1; the 8-word turn is >= 5 (long_turns)
    assert tight_rep.short_turns == 2
    assert tight_rep.long_turns == 1

    sample = "## One\n\nOne two three four. One two three four five six seven eight nine ten.\n"
    analyzer_default = CorpusAnalyzer(CorpusConfig())
    metrics_default = analyzer_default.analyze_text(sample)
    # default short_sentence_max = 6 (sentence 1 is short, sentence 2 is medium)
    assert metrics_default.chapters[0].staccato_pct == 50.0

    analyzer_tuned = CorpusAnalyzer(CorpusConfig(short_sentence_max=3, medium_sentence_max=8, long_sentence_max=15))
    metrics_tuned = analyzer_tuned.analyze_text(sample)
    # sentence 1 has 4 words > 3 -> medium; sentence 2 has 10 words > 8 -> long
    assert metrics_tuned.chapters[0].staccato_pct == 0.0


@pytest.mark.parametrize("kwargs", [
    {"short_sentence_max": 10, "medium_sentence_max": 5},
    {"short_turn_max_words": 100, "long_turn_min_words": 50},
    {"dialogue_paragraph_share": 1.5},
    {"hook_short_sentence": 0},
    {"monotony_min_run": 1},
])
def test_invalid_corpus_config_thresholds_rejected(kwargs):
    with pytest.raises(ValueError):
        CorpusConfig(**kwargs)
