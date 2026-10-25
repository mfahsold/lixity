"""Regular passive agreement cues remain consistent across measured scopes.

UD's Italian aux:pass example includes plural ``sono determinate``;
its French example includes ``fut assassiné``. These fixtures use synthetic
sentences and test cue coverage, not syntactic voice classification.
"""

import pytest

from lixity.analyzer import CorpusAnalyzer
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.paragraph_evidence import paragraph_evidence
from lixity.scenes import scene_report
from lixity.style_profile import ParagraphProfiler


@pytest.mark.parametrize(("language", "text", "words", "cue"), [
    ("es", "Los libros fueron enviados.", 4, "fueron enviados"),
    ("es", "Los libros fueron vendidos.", 4, "fueron vendidos"),
    ("es", "Las cartas fueron enviadas.", 4, "fueron enviadas"),
    ("es", "Las cartas fueron vendidas.", 4, "fueron vendidas"),
    ("pt", "Os livros foram enviados.", 4, "foram enviados"),
    ("pt", "Os livros foram vendidos.", 4, "foram vendidos"),
    ("pt", "As cartas foram enviadas.", 4, "foram enviadas"),
    ("pt", "As cartas foram vendidas.", 4, "foram vendidas"),
    ("it", "I libri sono inviati.", 4, "sono inviati"),
    ("it", "I beni sono venduti.", 4, "sono venduti"),
    ("it", "I beni sono restituiti.", 4, "sono restituiti"),
    ("it", "Le lettere sono inviate.", 4, "sono inviate"),
    ("it", "Le case sono vendute.", 4, "sono vendute"),
    ("it", "Le lettere sono restituite.", 4, "sono restituite"),
    ("fr", "La lettre fut envoyée.", 4, "fut envoyée"),
    ("fr", "Les lettres furent envoyées.", 4, "furent envoyées"),
    ("es", "La carta fue enviada.", 4, "fue enviada"),
    ("pt", "A carta foi enviada.", 4, "foi enviada"),
    ("it", "La lettera è inviata.", 4, "è inviata"),
    ("fr", "La lettre est envoyée.", 4, "est envoyée"),
    ("es", "Las cartas enviadas llegaron.", 4, None),
    ("pt", "As cartas enviadas chegaram.", 4, None),
    ("it", "Le lettere inviate arrivarono.", 4, None),
    ("fr", "Les lettres envoyées arrivent.", 4, None),
    ("fr", "La lettre fut longue.", 4, None),
    ("es", "Las cartas fueron usadas.", 4, "fueron usadas"),
    ("es", "Las cartas fueron rotas.", 4, "fueron rotas"),
    ("es", "Las cartas fueron leídas.", 4, "fueron leídas"),
    ("pt", "As cartas foram usadas.", 4, "foram usadas"),
    ("pt", "As cartas foram rotas.", 4, "foram rotas"),
    ("pt", "As cartas foram lidas.", 4, "foram lidas"),
    ("it", "Le lettere furono usate.", 4, "furono usate"),
    ("it", "Le lettere furono rotte.", 4, "furono rotte"),
    ("it", "Le lettere furono lette.", 4, "furono lette"),
    ("fr", "Les lettres furent usées.", 4, "furent usées"),
    ("fr", "Les lettres furent brisées.", 4, "furent brisées"),
    ("fr", "Les lettres furent lues.", 4, "furent lues"),
    ("en", "The tools were used.", 4, "were used"),
    ("de", "Die Tür wird geöffnet.", 4, "wird"),
    ("de", "Die Tür ist geöffnet.", 4, None),
    ("nl", "De brief wordt gelezen.", 4, "wordt"),
    ("es", "Estas palabras son vida.", 4, None),
    ("pt", "Estas palavras são vida.", 4, None),
    ("fr", "La lettre est si longue.", 5, None),
    ("en", "The wall was red.", 4, None),
    ("fr", "Il est ici.", 3, None),
    ("fr", "Il est plus grand.", 4, None),
    ("it", "Sono stati a casa.", 4, None),
    ("it", "È stato a casa.", 4, None),
    ("it", "Le lettere sono state inviate.", 5, "state inviate"),
    ("it", "I libri sono stati letti.", 5, "stati letti"),
])
def test_passive_agreement_cues_across_scopes(language, text, words, cue):
    config = CorpusConfig(language=language)
    markdown = "## Example\n\n" + text
    metrics = CorpusAnalyzer(config).analyze_text(markdown)
    paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(markdown))
    scenes = scene_report(markdown, config)
    count = 0 if cue is None else 1
    expected_density = 1000 * count / words
    assert metrics.passive_density == expected_density
    assert metrics.chapters[0].passive_density == expected_density
    assert paragraphs[0].passive_density == expected_density
    assert scenes["items"][0]["features"]["passive_density"] == expected_density
    layer = paragraph_evidence(markdown, config, paragraphs)[0]["layers"]["passive"]
    assert layer["count"] == layer["mapped_count"] == count
    assert layer["status"] == "available"
    assert [paragraphs[0].text[s["start"]:s["end"]] for s in layer["spans"]] == (
        [] if cue is None else [cue]
    )


@pytest.mark.parametrize("pattern", ["", r"\bMARK\b"])
def test_explicit_passive_override_replaces_extended_default(pattern):
    config = CorpusConfig(language="es", passive_regex=pattern)
    markdown = "## Example\n\nLas cartas fueron enviadas."
    metrics = CorpusAnalyzer(config).analyze_text(markdown)
    paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(markdown))
    assert metrics.passive_density == metrics.chapters[0].passive_density == 0
    assert paragraphs[0].passive_density == 0
