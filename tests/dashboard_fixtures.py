"""Shared synthetic manuscript and fully populated dashboard for UI tests."""

from lixity import CorpusAnalyzer, CorpusConfig
from lixity.markdown_parser import parse_markdown_blocks
from lixity.markers import add_marker
from lixity.style_fingerprint import StyleFingerprint
from lixity.style_profile import ParagraphProfiler
from lixity.ui import render_dashboard

SAMPLE = (
    "## Kap 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen. Ich trinke Tee. "
    "Ich höre die Straße. Ich sehe die Lichter. Ich trinke noch einen Schluck.\n\n"
    "Ich trinke noch einen Schluck. Ich gehe zur Tür. Ich sehe die Straße und den "
    "Regen auf dem Asphalt, der glänzt. Ich höre ein fernes Lied. Ich sehe den "
    "Abend über den Dächern.\n\n"
    "Ich spüre die Kälte. Ich merke den Wind. Ich fühle den Regen auf der Haut und "
    "ich glaube, es wird kalt. Ich spüre das Zittern. Ich sehe den Mond.\n\n"
    "Die Straße liegt still. Die Stadt schweigt. Der Abend kommt. Die Lichter "
    "gehen an. Ein Wagen fährt vorbei.\n\n"
    "Ich trinke Kaffee und ich ging zum Laden. Ich sehe den Regen und ich kaufte Brot. "
    "Ich gehe nach Hause und ich trank den Tee. Ich höre den Wind und ich sehe "
    "die Tropfen an der Scheibe.\n\n"
    "## Kap 2\n\n"
    "Das Haus wurde verkauft und die Tür war verschlossen worden. Die Zeitung lag "
    "auf dem Tisch. Die Entscheidung fiel schwer. Die Beschreibung der Wohnung "
    "war ausführlich. Das Haus wurde besichtigt und die Miete war bezahlt worden. "
    "Die Zeitung lag auf dem Boden und die Entscheidung war gefallen. Die "
    "Beschreibung der Wohnung wirkte sachlich und die Miete war hoch.\n\n"
    "Die Wohnung wurde gestrichen und die Fenster waren geputzt worden. Die Kaution "
    "wurde überwiesen und der Vertrag war unterschrieben worden. Die Nachbarn wurden "
    "gefragt und die Antwort war freundlich gewesen. Die Möbel wurden geliefert und "
    "die Kartons waren ausgepackt worden.\n\n"
    "Ich trinke Kaffee und ich sehe den Regen. Ich gehe zum Fenster und ich spüre "
    "die Kälte. Ich merke den Wind und ich fühle die Sonne. Ich trinke Tee und ich "
    "warte auf den Abend über den Dächern.\n"
)


def full_dashboard(enabled_actions: tuple[str, ...] | None = None) -> str:
    # Three complete, varying chapters exercise the optional rank-space panel.
    complete = SAMPLE.replace(
        "## Kap 2",
        "Ich schaue hinaus. Vor dem Fenster ziehen dunkle Wolken vorbei. " * 3 + "\n\n## Kap 2",
    )
    complete += "\n" + "Im Zimmer wartet eine Frau neben dem Fenster. " * 8
    complete += "\n\n## Kap 3\n\n" + "Der Morgen beginnt. Regen fällt auf die Straße. " * 15
    text, _marker = add_marker(complete, kind="todo", note="Prüfen", target_line=3)
    config = CorpusConfig(language="de", chapter_regex=r"(?m)^##\s+")
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    metrics = CorpusAnalyzer(config).analyze_text(text)
    fingerprint = StyleFingerprint.from_metrics(metrics)
    from lixity.characters import presence_report
    from lixity.dialogue import dialogue_report
    from lixity.markers import list_markers
    from lixity.motifs import motif_report
    from lixity.pacing import pacing_report
    from lixity.showing import showing_report

    return render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        markers=list_markers(text),
        artifacts=[{"name": "buch.pdf", "size_kb": 1200.0, "href": "buch.pdf", "pages": 184}],
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, ["Ich"], config),
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, {"Ich": r"\bIch\b"}, config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        title="Testroman",
        controls=True,
        **({"enabled_actions": enabled_actions} if enabled_actions is not None else {}),
    )
