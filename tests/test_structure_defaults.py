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
