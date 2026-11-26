"""Localized, self-contained reference for the app and the public guides."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import NamedTuple

from ..diversity import MIN_TOKENS_LD
from ..format import pct
from ..language import LANGUAGE_PROFILES
from ..models import CorpusConfig
from ..site import docs_url
from ..status import DEFAULT_MIN_CHAPTERS
from ..style_fingerprint import MIN_COMPARABLE_SENTENCES, MIN_COMPARABLE_WORDS

METRIC_REFERENCE_PATH = "/guides/metrics/"


class Entry(NamedTuple):
    key: str
    title: str
    explanation: str
    review: str = ""


class Section(NamedTuple):
    key: str
    title: str
    notes: tuple[str, ...] = ()
    entries: tuple[Entry, ...] = ()


_SECTIONS = (
    Section("analysis-review", "analysis_guide_title", ("review", "analysis_guide_compare")),
    Section("measurements", "analysis_measurements", (
        "measurement_vocabulary_guide",
    ), (
        Entry("words", "readability_tokens", "help_corpus_words"),
        Entry("asl", "measurement_words_per_sentence", "help_asl", "asl_example"),
        Entry("ttr", "TTR", "help_ttr"),
        Entry("yules", "Yule’s K", "help_yules"),
        Entry("hd_d", "feat_hd_d", "help_hd_d", "measurement_vocabulary_sample"),
        Entry("guiraud_r", "feat_guiraud", "help_guiraud"),
        Entry("mtld", "feat_mtld", "help_mtld"),
        Entry("mattr", "feat_mattr", "help_mattr"),
        Entry("maas_a2", "feat_maas", "help_maas"),
        Entry("flesch", "Flesch", "help_flesch"),
        Entry("lix", "LIX", "help_lix"),
        Entry("long_word_pct", "feat_long_words", "help_long_words"),
    )),
    Section("flags", "panel_flags", ("help_flagged", "flags"), (
        Entry("severity", "flag_min_severity", "help_severity", "help_flag_min_severity"),
        Entry("chapter_tense", "cmd_layer_tense_hint", "help_chapter_tense", "help_neutral"),
    )),
    Section("pacing", "analysis_nav_pacing", ("pacing_scale",), (
        Entry("sentence_cv", "heatmap_sentence_variation", "help_cv"),
        Entry("pacing_cohesion", "pac_cohesion", "help_pacing_cohesion"),
        Entry("pacing_monotony", "pac_monotony", "help_pacing_monotony"),
        Entry("pacing_hook", "pac_hook", "help_pacing_hook"),
        Entry("start_entropy", "feat_start_entropy", "help_start_entropy"),
        Entry("first_person_start_rate", "feat_ich_start", "help_first_start"),
    )),
    Section("dist", "sentence_dist", ("analysis_sentence_dist_guide", "sentence_bins"), (
        Entry("staccato_pct", "measurement_short_sentences", "help_staccato"),
        Entry("kaskade_pct", "feat_kaskade", "help_kaskade"),
    )),
    Section("sticky", "pac_sticky_items", ("sticky_share", "pac_sticky_read"), (
        Entry("sticky", "pac_sticky_pct", "pac_sticky_rule", "sticky_example"),
        Entry("function", "feat_function", "help_function_words", "evidence_review_function"),
    )),
    Section("dialogue", "panel_dialogue", (
        "analysis_dialogue_guide", "measurement_language_guide",
    ), (
        Entry("dialogue", "feat_dialog", "help_dialogue", "evidence_review_dialogue"),
        Entry("dlg_short_turns", "dlg_short_turns", "help_dlg_short_turns"),
        Entry("dlg_long_turns", "dlg_long_turns", "help_dlg_long_turns"),
        Entry("dlg_voice_contrast", "dlg_voice_contrast", "help_dlg_voice_contrast"),
        Entry("dialogue_tag", "evidence_layer_dialogue_tag", "evidence_reason_dialogue_tag", "evidence_review_dialogue_tag"),
        Entry("indirect_speech", "evidence_layer_indirect_speech", "evidence_reason_indirect_speech", "evidence_review_indirect_speech"),
    )),
    Section("showing", "analysis_nav_showing", ("showing",), (
        Entry("filter", "feat_filter", "help_perception", "evidence_review_filter"),
        Entry("sensory", "show_sensory", "help_sensory", "evidence_review_sensory"),
        Entry("modal", "feat_modal", "help_modal", "evidence_review_modal"),
        Entry("nominal", "feat_nominal", "help_nominal", "evidence_review_nominal"),
        Entry("passive", "feat_passive", "help_passive", "evidence_review_passive"),
        Entry("adjective_density", "feat_adjective", "help_adjective"),
    )),
    Section("motifs", "panel_motifs", ("motifs",), (
        Entry("echo", "evidence_layer_echo", "evidence_reason_echo", "evidence_review_echo"),
    )),
    Section("characters", "panel_characters", ("chr_hint", "characters"), (
        Entry("chr_gap", "chr_gap", "help_chr_gap"),
        Entry("chr_share", "chr_share", "help_chr_share"),
        Entry("chr_voices", "chr_voices_title", "chr_voices_hint"),
        Entry("chr_interactions", "chr_interactions_title", "chr_interactions_hint"),
    )),
    Section("scenes", "panel_scenes", ("scene_guidance", "scene_support", "scene_implicit_breaks_hint")),
    Section("style", "group_style", ("style", "style_support", "heatmap_author_guide"), (
        Entry("heatmap", "cockpit_switch_heatmap", "help_heatmap"),
        Entry("fingerprint", "style_fingerprint", "help_fingerprint"),
        Entry("passport", "style_passport", "help_passport"),
        Entry("consistency", "consistency", "help_consistency"),
        Entry("dimensions", "style_dimensions", "help_dimensions"),
        Entry("structural", "panel_structural", "help_structural"),
        Entry("fdr", "fdr_flagged", "help_fdr"),
    )),
    Section("matrix", "chapter_table", ("matrix",), (
        Entry("chapter_flags", "panel_flags", "help_chapter_flags"),
        Entry("chapter_deviation", "deviation", "help_chapter_deviation"),
        Entry("layer", "layer_guide", "help_layer"),
    )),
    Section("register-targets", "register_title", ("register_hint", "register_scope_hint")),
    Section("revisions", "editor_compare_versions", ("revisions", "editor_compare_chapters_unclear")),
)

# Feature IDs in chapter tables and paragraph readers can identify the same measure.
_ENTRY_ALIASES = {
    "function": ("function_word_pct", "function_words"),
    "dialogue": ("dialog_pct",),
    "filter": ("filter_density", "perception"),
    "sensory": ("sensory_density",),
    "modal": ("modal_density", "modals"),
    "nominal": ("nominalization_density",),
    "passive": ("passive_density",),
    "staccato_pct": ("staccato",),
    "kaskade_pct": ("kaskade",),
    "sentence_cv": ("cv",),
    "first_person_start_rate": ("first_start",),
    "long_word_pct": ("long_words",),
    "guiraud_r": ("guiraud",),
    "maas_a2": ("maas",),
}

METRIC_REFERENCE_SECTIONS = frozenset(section.key for section in _SECTIONS)
METRIC_REFERENCE_ENTRIES = frozenset(
    f"measure-{key}"
    for section in _SECTIONS for entry in section.entries
    for key in (entry.key, *_ENTRY_ALIASES.get(entry.key, ()))
)

_INVARIANT_TITLES = frozenset({"Flesch", "LIX", "TTR", "Yule’s K"})

_NOTES: dict[str, dict[str, str]] = {
    "de": {
        "title": "Was Lixity misst",
        "defaults": "Die Zahlen in dieser Übersicht sind Voreinstellungen. Im Projekt können andere Grenzen, Wortlisten oder Erkennungsmuster gelten.",
        "review": "Wähle im Manuskript einen Messwert und öffne eine markierte Stelle. Lies den ganzen Absatz. Welche Wirkung passt zur Stimme, zur Szene oder zum Sprecherwechsel?",
        "asl_example": "Ein Satz mit 8 und einer mit 16 Wörtern ergeben 12 Wörter pro Satz im Schnitt. Die Verteilung zeigt zusätzlich, wie oft kurze und lange Sätze vorkommen.",
        "flags": "Lies am Übergang auch die Nachbarabsätze. Ein Wechsel kann zu einer Rückblende oder zu wörtlicher Rede gehören. Die Prüfung erfasst nur Tempusmuster.",
        "sentence_bins": "Die vier Gruppen zählen bis {short}, von {medium_start} bis {medium}, von {long_start} bis {long} sowie mehr als {long} Wörter je Satz.",
        "sticky_share": "Der Überblick zeigt, wie viele der erkannten Sätze zum Filter passen. Der Wert am einzelnen Satz zeigt den Anteil der Funktionswörter in diesem Satz.",
        "sticky_example": "Fünf von acht Wörtern ergeben 62,5 %. So kann auch ein einfacher Hauptsatz markiert sein: «In der Stadt haben wir ihn gestern gesehen.» Lies ihn im Absatz und achte auf den Gedankengang und die Bezüge.",
        "showing": "Die Listen zählen Treffer von Wortmustern je 1.000 Wörter. Das macht Kapitel unterschiedlicher Länge leichter vergleichbar. Lies die Fundstelle, um zu erkennen, was das Wort dort leistet.",
        "motifs": "Ein Projektmotiv zählt Treffer eines hinterlegten Suchmusters. Die Wiederholungssuche findet wiederkehrende Wortfolgen. Beim Lesen zeigt sich, ob etwa «am Fenster» als Leitmotiv, Ortsangabe oder unbeabsichtigte Wiederholung wirkt.",
        "characters": "Hinterlege die Namen oder Namensmuster der Figuren im Projekt. Bei einer längeren Lücke in den Namensnennungen kannst du im Text prüfen, ob die Figur weiter über Pronomen auftaucht.",
        "style": "Vergleiche ein Kapitel mit den typischen Werten messbarer Kapitel desselben Manuskripts. Prüfe zunächst den Rohwert und die Textmenge. Ein Briefkapitel darf sich bewusst vom Erzähltext abheben.",
        "style_support": "Für den Vergleich braucht ein Merkmal standardmäßig mindestens {min_chapters} messbare Kapitel. Sind ihre Werte gleich, fehlt die Streuung für den Vergleich.",
        "matrix": "Jede Zeile fasst ein Kapitel zusammen. Ein Strich steht für einen fehlenden Vergleichswert. Öffne eine markierte Stelle und prüfe, ob das Muster zur Funktion des Kapitels passt.",
        "revisions": "Im Fassungsvergleich werden bestätigter Text, aktuelle Datei und Entwurf mit denselben Einstellungen gemessen. Sinkt die mittlere Satzlänge von 12 auf 8 Wörter, beträgt die Änderung −4 Wörter pro Satz. Schau im Textvergleich, ob beispielsweise lange Sätze gestrichen oder kurze ergänzt wurden. Lücken im gespeicherten Verlauf bedeuten fehlende vergleichbare Messwerte.",
        "methods": "Formeln, Bezugsgrößen und statistische Grenzen",
    },
    "en": {
        "title": "What Lixity measures",
        "defaults": "The thresholds in this reference are defaults. Your project may use different cutoffs, word lists or detection patterns.",
        "review": "Choose a measure in the manuscript and open a marked passage. Read the whole paragraph. How does the pattern fit the voice, scene or change of speaker?",
        "asl_example": "One 8-word sentence and one 16-word sentence average 12 words per sentence. The distribution also shows how often short and long sentences occur.",
        "flags": "Read the paragraphs on either side of a change. A tense shift may belong to a flashback or a quotation. The check covers tense patterns only.",
        "sentence_bins": "The four groups contain up to {short}, {medium_start} to {medium}, {long_start} to {long}, and more than {long} words per sentence.",
        "sticky_share": "The overview shows the fraction of detected sentences that match the filter. An individual sentence shows its own share of function words.",
        "sticky_example": "Five out of eight words is 62.5%. Even a simple sentence can match, as in “In the city, we had seen him yesterday.” Read it in context and check whether the train of thought and references are clear.",
        "showing": "Pattern counts are scaled to 1,000 words to make chapters of different lengths easier to compare. Read the passage to see what the matched word does there.",
        "motifs": "A project motif counts matches to a saved search pattern. The repeat search finds recurring word sequences. Read each passage to see whether a phrase such as “at the window” acts as a motif, sets the scene or repeats unintentionally.",
        "characters": "Enter the names or name patterns in the project. When a name drops out for several chapters, check whether the character is still referred to with pronouns.",
        "style": "Compare a chapter with typical values from measurable chapters of the same manuscript. Start with the raw value and the amount of text measured. A chapter written as a letter may deliberately sound different from the surrounding narrative.",
        "style_support": "By default, each measure needs at least {min_chapters} measurable chapters. If every value is identical, there is no spread to use for comparison.",
        "matrix": "Each row summarizes one chapter. A dash indicates that a comparison value is unavailable. Open a marked passage and check whether the pattern fits what the chapter is doing.",
        "revisions": "The comparison measures the confirmed text, current file and draft with the same settings. If the average falls from 12 to 8, the change is −4 words per sentence. Read the text changes to see whether long sentences were removed or short ones were added. Gaps in saved history indicate unavailable comparable measurements.",
        "methods": "Formulas, reference groups and statistical limits",
    },
    "fr": {
        "title": "Ce que mesure Lixity",
        "defaults": "Les seuils indiqués ici sont les valeurs par défaut. Votre projet peut utiliser d’autres seuils, listes de mots ou règles de détection.",
        "review": "Choisissez une mesure dans le manuscrit et ouvrez un passage marqué. Lisez tout le paragraphe. Comment ce motif s’accorde-t-il avec la voix, la scène ou le changement d’interlocuteur ?",
        "asl_example": "Une phrase de 8 mots et une de 16 mots donnent une moyenne de 12 mots par phrase. La répartition indique aussi la fréquence des phrases courtes et longues.",
        "flags": "Lisez aussi les paragraphes voisins. Un changement de temps peut appartenir à un retour en arrière ou à une réplique. Le repérage porte uniquement sur les temps verbaux.",
        "sentence_bins": "Les quatre groupes comptent jusqu’à {short}, de {medium_start} à {medium}, de {long_start} à {long}, puis plus de {long} mots par phrase.",
        "sticky_share": "La vue d’ensemble montre la part des phrases reconnues qui correspondent au filtre. Pour une phrase, la valeur indique sa propre part de mots-outils.",
        "sticky_example": "Cinq mots sur huit représentent 62,5 %. Une phrase simple peut donc être marquée. Relisez le paragraphe pour vérifier si le fil du récit et les renvois sont clairs.",
        "showing": "Les occurrences sont rapportées à 1 000 mots pour comparer des chapitres de longueurs différentes. Lisez le passage pour comprendre le rôle du mot repéré.",
        "motifs": "Un motif du projet compte les correspondances avec une règle de recherche enregistrée. La recherche de répétitions repère des suites de mots récurrentes. Relisez chaque passage pour voir si « à la fenêtre » forme un motif, situe la scène ou se répète par hasard.",
        "characters": "Saisissez les noms ou les formes de noms dans le projet. Si un nom disparaît pendant plusieurs chapitres, vérifiez si des pronoms désignent encore le personnage.",
        "style": "Comparez un chapitre aux valeurs typiques des chapitres mesurables du même manuscrit. Regardez d’abord la valeur brute et la quantité de texte. Un chapitre épistolaire peut avoir une voix voulue distincte.",
        "style_support": "Par défaut, chaque mesure demande au moins {min_chapters} chapitres mesurables. Si toutes les valeurs sont identiques, la dispersion nécessaire à la comparaison est absente.",
        "matrix": "Chaque ligne résume un chapitre. Un tiret indique une valeur de comparaison indisponible. Ouvrez un passage signalé et vérifiez l’effet de ce motif dans le chapitre.",
        "revisions": "La comparaison applique les mêmes réglages au texte confirmé, au fichier actuel et au brouillon. Si la moyenne passe de 12 à 8, l’écart est de −4 mots par phrase. Lisez les modifications pour voir si des phrases longues ont disparu ou si des phrases courtes ont été ajoutées. Une lacune dans l’historique indique l’absence de mesures comparables.",
        "methods": "Formules, groupes de référence et limites statistiques",
    },
    "es": {
        "title": "Qué mide Lixity",
        "defaults": "Los umbrales de esta guía son valores predeterminados. Tu proyecto puede usar otros límites, listas de palabras o patrones de detección.",
        "review": "Elige una medida en el manuscrito y abre un pasaje marcado. Lee todo el párrafo. ¿Cómo encaja el patrón con la voz, la escena o el cambio de hablante?",
        "asl_example": "Una oración de 8 palabras y otra de 16 dan un promedio de 12 palabras por oración. La distribución también muestra la frecuencia de oraciones cortas y largas.",
        "flags": "Lee también los párrafos vecinos. Un cambio de tiempo verbal puede formar parte de un recuerdo o de una cita. La revisión se limita a los patrones de tiempo verbal.",
        "sentence_bins": "Los cuatro grupos abarcan hasta {short}, de {medium_start} a {medium}, de {long_start} a {long} y más de {long} palabras por oración.",
        "sticky_share": "El resumen muestra la proporción de oraciones detectadas que cumplen el filtro. En una oración, el valor indica su propia proporción de palabras funcionales.",
        "sticky_example": "Cinco de ocho palabras equivalen al 62,5 %. Hasta una oración simple puede quedar marcada. Lee el párrafo y comprueba si el hilo de la idea y las referencias se entienden.",
        "showing": "Las coincidencias se expresan por cada 1.000 palabras para comparar capítulos de distinta extensión. Lee el pasaje para ver qué función cumple la palabra marcada.",
        "motifs": "Un motivo del proyecto cuenta las coincidencias con un patrón de búsqueda guardado. La búsqueda de repeticiones localiza secuencias recurrentes. Lee los pasajes para ver si «en la ventana» funciona como motivo, sitúa la escena o se repite sin querer.",
        "characters": "Introduce los nombres o patrones de nombres en el proyecto. Si un nombre desaparece varios capítulos, comprueba si el personaje todavía aparece mediante pronombres.",
        "style": "Compara un capítulo con los valores típicos de los capítulos medibles del mismo manuscrito. Empieza por el valor original y la cantidad de texto. Un capítulo en forma de carta puede sonar distinto a propósito.",
        "style_support": "Por defecto, cada medida requiere al menos {min_chapters} capítulos medibles. Si todos los valores son idénticos, falta la dispersión necesaria para la comparación.",
        "matrix": "Cada fila resume un capítulo. Un guion indica que no hay un valor de comparación disponible. Abre el pasaje marcado y comprueba el efecto del patrón en ese capítulo.",
        "revisions": "La comparación mide el texto confirmado, el archivo actual y el borrador con los mismos ajustes. Si el promedio pasa de 12 a 8, la diferencia es de −4 palabras por oración. Lee los cambios para ver si se eliminaron oraciones largas o se añadieron cortas. Los huecos del historial indican que faltan mediciones comparables.",
        "methods": "Fórmulas, grupos de referencia y límites estadísticos",
    },
    "it": {
        "title": "Che cosa misura Lixity",
        "defaults": "Le soglie riportate qui sono quelle predefinite. Il progetto può usare soglie, elenchi di parole o criteri di rilevamento diversi.",
        "review": "Scegli una misura nel manoscritto e apri un passaggio evidenziato. Leggi tutto il paragrafo. Come si accorda il motivo con la voce, la scena o il cambio di interlocutore?",
        "asl_example": "Una frase di 8 parole e una di 16 danno una media di 12 parole per frase. La distribuzione mostra anche la frequenza delle frasi brevi e lunghe.",
        "flags": "Leggi anche i paragrafi vicini. Un cambio di tempo verbale può far parte di un flashback o di una battuta. Il controllo riguarda solo i tempi verbali.",
        "sentence_bins": "I quattro gruppi contano fino a {short}, da {medium_start} a {medium}, da {long_start} a {long} e oltre {long} parole per frase.",
        "sticky_share": "Il riepilogo mostra la quota di frasi rilevate che rientrano nel filtro. Il valore di una frase indica la sua quota di parole funzionali.",
        "sticky_example": "Cinque parole su otto sono il 62,5%. Anche una frase semplice può essere segnalata. Rileggi il paragrafo e verifica che siano chiari il filo del discorso e i riferimenti.",
        "showing": "Le occorrenze sono riportate per 1.000 parole per confrontare capitoli di lunghezze diverse. Leggi il passaggio per capire il ruolo della parola segnalata.",
        "motifs": "Un motivo di progetto conta le corrispondenze con un criterio di ricerca salvato. La ricerca di ripetizioni trova sequenze di parole ricorrenti. Rileggi i passaggi per capire se «alla finestra» è un motivo, un riferimento al luogo o una ripetizione involontaria.",
        "characters": "Inserisci i nomi o le loro forme nel progetto. Se un nome non compare per diversi capitoli, verifica se il personaggio viene ancora indicato con pronomi.",
        "style": "Confronta un capitolo con i valori tipici dei capitoli misurabili dello stesso manoscritto. Parti dal dato originale e dalla quantità di testo. Un capitolo in forma di lettera può avere volutamente una voce diversa.",
        "style_support": "Per impostazione predefinita servono almeno {min_chapters} capitoli misurabili per ogni misura. Se tutti i valori coincidono, manca la dispersione necessaria per il confronto.",
        "matrix": "Ogni riga riassume un capitolo. Un trattino indica che manca il dato di confronto. Apri un passaggio segnalato e verifica l’effetto del motivo nel capitolo.",
        "revisions": "Il confronto misura con le stesse impostazioni il testo confermato, il file attuale e la bozza. Se la media passa da 12 a 8, la variazione è di −4 parole per frase. Leggi le modifiche per vedere se sono state tolte frasi lunghe o aggiunte frasi brevi. Le lacune nella cronologia indicano che mancano misure comparabili.",
        "methods": "Formule, gruppi di riferimento e limiti statistici",
    },
    "pt": {
        "title": "O que o Lixity mede",
        "defaults": "Os limiares deste guia são valores predefinidos. O teu projeto pode usar outros limites, listas de palavras ou padrões de deteção.",
        "review": "Escolhe uma medida no manuscrito e abre um trecho marcado. Lê o parágrafo inteiro. Como se encaixa o padrão na voz, na cena ou na mudança de interlocutor?",
        "asl_example": "Uma frase com 8 palavras e outra com 16 dão uma média de 12 palavras por frase. A distribuição também mostra com que frequência aparecem frases curtas e longas.",
        "flags": "Lê também os parágrafos vizinhos. Uma mudança de tempo verbal pode fazer parte de um recuo no tempo ou de uma citação. A verificação abrange só os tempos verbais.",
        "sentence_bins": "Os quatro grupos abrangem até {short}, de {medium_start} a {medium}, de {long_start} a {long} e mais de {long} palavras por frase.",
        "sticky_share": "O resumo mostra a proporção de frases detetadas que passam no filtro. Numa frase, o valor indica a sua própria proporção de palavras funcionais.",
        "sticky_example": "Cinco em oito palavras correspondem a 62,5%. Uma frase simples também pode ficar marcada. Lê o parágrafo e verifica se o fio do pensamento e as referências estão claros.",
        "showing": "As ocorrências são expressas por 1.000 palavras para comparar capítulos de extensões diferentes. Lê o trecho para ver a função da palavra marcada.",
        "motifs": "Um motivo do projeto conta as correspondências com um padrão de pesquisa guardado. A procura de repetições encontra sequências de palavras recorrentes. Lê os trechos para ver se «à janela» funciona como motivo, situa a cena ou se repete sem intenção.",
        "characters": "Regista nomes ou padrões de nomes no projeto. Se um nome desaparecer durante vários capítulos, verifica se a personagem continua a aparecer através de pronomes.",
        "style": "Compara um capítulo com os valores típicos dos capítulos mensuráveis do mesmo manuscrito. Começa pelo valor original e pela quantidade de texto. Um capítulo em forma de carta pode ter de propósito uma voz diferente.",
        "style_support": "Por defeito, cada medida precisa de pelo menos {min_chapters} capítulos mensuráveis. Se todos os valores forem iguais, falta a dispersão necessária para comparar.",
        "matrix": "Cada linha resume um capítulo. Um travessão indica que falta um valor para a comparação. Abre um trecho marcado e verifica o efeito do padrão no capítulo.",
        "revisions": "A comparação mede o texto confirmado, o ficheiro atual e o rascunho com as mesmas definições. Se a média passar de 12 para 8, a variação é de −4 palavras por frase. Lê as alterações para ver se desapareceram frases longas ou se foram acrescentadas curtas. As lacunas no histórico indicam que faltam medições comparáveis.",
        "methods": "Fórmulas, grupos de referência e limites estatísticos",
    },
    "nl": {
        "title": "Wat Lixity meet",
        "defaults": "De drempels in dit overzicht zijn standaardwaarden. Je project kan andere grenzen, woordenlijsten of herkenningspatronen gebruiken.",
        "review": "Kies een meting in het manuscript en open een gemarkeerde passage. Lees de hele alinea. Hoe past het patroon bij de stem, de scène of de wisseling van spreker?",
        "asl_example": "Een zin van 8 woorden en een van 16 woorden geven gemiddeld 12 woorden per zin. De verdeling laat ook zien hoe vaak korte en lange zinnen voorkomen.",
        "flags": "Lees ook de alinea’s eromheen. Een wisseling van werkwoordstijd kan bij een terugblik of een citaat horen. Deze controle kijkt alleen naar tijdspatronen.",
        "sentence_bins": "De vier groepen lopen tot en met {short}, van {medium_start} tot {medium}, van {long_start} tot {long} en boven {long} woorden per zin.",
        "sticky_share": "Het overzicht geeft het aandeel herkende zinnen dat bij het filter past. Bij één zin staat het aandeel functiewoorden in die zin.",
        "sticky_example": "Vijf van de acht woorden is 62,5%. Ook een eenvoudige zin kan dus gemarkeerd zijn. Lees de alinea en kijk of de gedachtegang en de verwijzingen duidelijk zijn.",
        "showing": "De aantallen zijn omgerekend naar 1.000 woorden, zodat je hoofdstukken van verschillende lengtes kunt vergelijken. Lees de passage om te zien wat het gemarkeerde woord daar doet.",
        "motifs": "Een projectmotief telt treffers van een opgeslagen zoekpatroon. De zoekfunctie voor herhalingen zoekt terugkerende woordreeksen. Lees de passages om te zien of «bij het raam» als motief werkt, de plaats aangeeft of onbedoeld terugkomt.",
        "characters": "Voer namen of naampatronen in het project in. Als een naam een paar hoofdstukken wegvalt, kijk dan of de figuur via voornaamwoorden nog aanwezig is.",
        "style": "Vergelijk een hoofdstuk met de kenmerkende waarden van meetbare hoofdstukken uit hetzelfde manuscript. Begin bij de ruwe waarde en de hoeveelheid tekst. Een briefhoofdstuk kan bewust anders klinken.",
        "style_support": "De standaard is minstens {min_chapters} meetbare hoofdstukken per meting. Bij gelijke waarden ontbreekt de spreiding die nodig is voor de vergelijking.",
        "matrix": "Elke rij vat één hoofdstuk samen. Een streepje geeft aan dat een vergelijkingswaarde ontbreekt. Open een gemarkeerde passage en kijk welk effect het patroon in het hoofdstuk heeft.",
        "revisions": "De vergelijking meet de bevestigde tekst, het huidige bestand en het concept met dezelfde instellingen. Daalt het gemiddelde van 12 naar 8, dan is het verschil −4 woorden per zin. Lees de wijzigingen om te zien of lange zinnen zijn geschrapt of korte zinnen zijn toegevoegd. Gaten in de bewaarde geschiedenis wijzen op ontbrekende vergelijkbare metingen.",
        "methods": "Formules, referentiegroepen en statistische grenzen",
    },
}

_STYLE = """
body { margin: 0; background: var(--bg); color: var(--fg); font: var(--text-body)/var(--line-body) var(--font); }
main { max-inline-size: 70ch; margin-inline: auto; padding: var(--space-5); overflow-wrap: anywhere; }
header, section, footer { margin-block: 0 var(--section-gap); }
section { padding: var(--panel-padding); background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
h1, h2 { margin-block: 0 var(--space-3); line-height: var(--line-tight); }
h1 { font: var(--weight-bold) var(--text-display)/var(--line-tight) var(--font-title); }
h2 { font-size: var(--text-heading); }
p { margin-block: 0 var(--space-3); }
a { color: var(--accent); text-underline-offset: 0.15em; }
a:hover { color: var(--accent-hover); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
nav ul { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-4); list-style: none; padding: 0; }
nav a { display: inline-block; padding-block: var(--space-1); }
dl { margin-block: var(--space-3) 0; }
dl > div { border-block-start: 1px solid var(--line); padding-block: var(--space-3); }
dl > div:last-child { padding-block-end: 0; }
dt { font-weight: var(--weight-bold); }
dd { margin: 0; }
section > :last-child, dd > :last-child { margin-block-end: 0; }
[id] { scroll-margin-block-start: var(--space-4); }
section:target, dl > div:target, dl > div:has([id]:target) { border-color: var(--accent); }
"""


def _placeholders(language: str, config: CorpusConfig) -> dict[str, dict[str, str | int]]:
    return {
        "sentence_bins": {
            "short": config.short_sentence_max,
            "medium_start": config.short_sentence_max + 1,
            "medium": config.medium_sentence_max,
            "long_start": config.medium_sentence_max + 1,
            "long": config.long_sentence_max,
        },
        "pac_sticky_rule": {
            "min_words": config.sticky_min_words,
            "min_pct": pct(config.sticky_glue_pct, language, 0, precise=config.sticky_glue_pct % 1 != 0),
        },
        "dlg_short_turns": {"max_words": config.short_turn_max_words},
        "help_dlg_short_turns": {"max_words": config.short_turn_max_words},
        "dlg_long_turns": {"min_words": config.long_turn_min_words},
        "help_dlg_long_turns": {"min_words": config.long_turn_min_words},
        "help_pacing_hook": {"max_words": config.hook_short_sentence},
        "help_pacing_monotony": {"min_run": config.monotony_min_run},
        "style_support": {"min_chapters": DEFAULT_MIN_CHAPTERS},
        "help_heatmap": {"min_words": MIN_COMPARABLE_WORDS, "min_sentences": MIN_COMPARABLE_SENTENCES},
        "scene_support": {"min_tokens": MIN_TOKENS_LD},
        "measurement_vocabulary_sample": {"min_tokens": MIN_TOKENS_LD},
    }


def _metric_section(section: Section, labels: Mapping[str, str]) -> str:
    paragraphs = [f"<p>{labels[key]}</p>" for key in section.notes]
    entries = []
    for entry in section.entries:
        aliases = "".join(f'<span id="measure-{alias}"></span>' for alias in _ENTRY_ALIASES.get(entry.key, ()))
        review = f"<p>{labels[entry.review]}</p>" if entry.review else ""
        title = entry.title if entry.title in _INVARIANT_TITLES else labels[entry.title]
        entries.append(
            f'<div id="measure-{entry.key}"><dt>{aliases}{title}</dt>'
            f"<dd><p>{labels[entry.explanation]}</p>{review}</dd></div>"
        )
    if entries:
        paragraphs.append("<dl>\n" + "\n".join(entries) + "\n</dl>")
    return (
        f'<section id="{section.key}" aria-labelledby="heading-{section.key}">\n'
        f'<h2 id="heading-{section.key}">{labels[section.title]}</h2>\n'
        + "\n".join(paragraphs) + "\n</section>"
    )


def _render(language: str, config: CorpusConfig | None = None) -> str:
    raw_labels = {**LANGUAGE_PROFILES[language].labels, **_NOTES[language]}
    for key, fields in _placeholders(language, config or CorpusConfig()).items():
        raw_labels[key] = raw_labels[key].format(**fields)
    labels = {key: escape(text) for key, text in raw_labels.items()}
    title = labels["title"]
    navigation = "\n".join(
        f'<li><a href="#{section.key}">{labels[section.title]}</a></li>' for section in _SECTIONS
    )
    sections = "\n".join(_metric_section(section, labels) for section in _SECTIONS)
    foundation = Path(__file__).with_name("assets").joinpath("design-tokens.css").read_text(encoding="utf-8")
    canonical = docs_url(f"{METRIC_REFERENCE_PATH}{language}.html")
    methods = docs_url("METHODS.md")
    return f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{canonical}">
<title>{title}</title>
<style>
{foundation}{_STYLE}</style>
</head>
<body>
<main>
<header>
<h1>{title}</h1>
<p>{labels["metric_reference_project_limits" if config is not None else "defaults"]}</p>
<nav aria-label="{labels['sections']}">
<ul>
{navigation}
</ul>
</nav>
</header>
{sections}
<footer><a href="{methods}" hreflang="en">{labels["methods"]}</a></footer>
</main>
</body>
</html>
"""


@lru_cache(maxsize=len(_NOTES))
def _render_defaults(language: str) -> str:
    return _render(language)


def metric_reference_document(language: str, config: CorpusConfig | None = None) -> str:
    """Render the metric reference in a supported UI locale, defaulting to English."""
    locale = language.strip().lower()
    locale = locale if locale in _NOTES else "en"
    return _render_defaults(locale) if config is None else _render(locale, config)
