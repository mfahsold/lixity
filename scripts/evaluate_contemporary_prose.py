"""Offline, deterministic contemporary-style prose benchmark for Lixity (EN & DE).

Evaluates Lixity's default heuristic engine (no optional spaCy/Stanza models)
on a freshly authored, synthetic held-out contemporary-style prose set covering:

1. Sentence boundaries (``lixity.sentences.split_sentence_spans``)
   Scored on internal sentence boundaries (excluding forced passage-final ends)
   across abbreviations, ellipses, dialogue punctuation, numbers/initials, and
   short staccato sentences.
2. Dialogue cues (``lixity.quotation.scan_quotations``)
   Scored at word-token level across standard quotation marks, non-speech
   quotes (scare quotes / signs), dash-introduced speech, unquoted interior
   thoughts, and free indirect speech.
3. Tense cues (``lixity.tense.TenseMatcher.spans``)
   Scored at cue-span level (present and past cues) across simple past,
   present, compound perfect, mixed narration/dialogue, and lexically
   ambiguous forms.

Computes Precision, Recall, F1, and 95% Wilson score confidence intervals
using only the Python standard library and the ``lixity`` package.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from lixity.language import compile_word_pattern, resolve_language
from lixity.models import CorpusConfig
from lixity.quotation import merge_quotation_spans, scan_quotations
from lixity.sentences import split_sentence_spans
from lixity.tense import TenseMatcher

#: Standard-normal 97.5% quantile for a two-sided 95% Wilson score interval.
WILSON_Z_95 = 1.959963984540054


@dataclass(frozen=True)
class SentenceCase:
    """Multi-sentence passage with explicit gold sentence segments."""

    case_id: str
    category: str
    sentences: tuple[str, ...]
    separator: str = " "


@dataclass(frozen=True)
class DialogueCase:
    """Passage with gold dialogue spans marked inline as ``[[...]]``."""

    case_id: str
    category: str  # "standard_quoted", "non_speech_quote", "dash_speech", "interior_thought", "free_indirect"
    annotated: str


@dataclass(frozen=True)
class TenseCase:
    """Passage with gold tense cues marked inline as ``{past:...}`` or ``{pres:...}``."""

    case_id: str
    category: str  # "past", "present", "perfect", "mixed", "ambiguous"
    annotated: str


# ---------------------------------------------------------------------------
# Held-out contemporary-style prose benchmark: English (EN)
# ---------------------------------------------------------------------------

EN_SENTENCE_CASES: tuple[SentenceCase, ...] = (
    SentenceCase(
        "en_s01",
        "abbreviations",
        (
            "Dr. Patel checked the chart twice before calling Prof. Lindholm.",
            "Neither of them trusted the midnight printout.",
        ),
    ),
    SentenceCase(
        "en_s02",
        "abbreviations",
        (
            "Ms. Alvarez packed only essentials, e.g. wool socks and a spare charger.",
            "Mr. Cho brought two thermoses of burnt coffee.",
            "The ferry left St. Jude Pier at six.",
        ),
    ),
    SentenceCase(
        "en_s03",
        "abbreviations_edge",
        (
            "She worked in Dept. 4 until the merger.",
            "The badge still read Acme Ltd.",
            "Nobody bothered to update the lobby directory.",
        ),
    ),
    SentenceCase(
        "en_s04",
        "abbreviations_edge",
        (
            "He listed three side effects, i.e. dizziness, tinnitus, and dry mouth.",
            "Then he folded the leaflet into his coat pocket.",
        ),
    ),
    SentenceCase(
        "en_s05",
        "ellipses",
        (
            "Wait... no, leave the window cracked.",
            "The paint fumes still hung in the hallway.",
        ),
    ),
    SentenceCase(
        "en_s06",
        "ellipses",
        (
            "She watched the last commuter train disappear into the tunnel…",
            "Then the platform lights flickered once and dimmed.",
        ),
    ),
    SentenceCase(
        "en_s07",
        "ellipses",
        (
            "He started to apologize...",
            "She raised two fingers and shut the cab door.",
        ),
    ),
    SentenceCase(
        "en_s08",
        "dialogue_punct",
        (
            '"Are you coming?" she asked from the stairwell.',
            '"Give me thirty seconds!" he called back.',
            "His keys rattled against the railing.",
        ),
    ),
    SentenceCase(
        "en_s09",
        "dialogue_punct",
        (
            '"That bridge is closed." he muttered under his breath.',
            '"We take the harbor tunnel instead."',
            "Nobody argued with him after dark.",
        ),
    ),
    SentenceCase(
        "en_s10",
        "dialogue_punct",
        (
            '“Don’t touch the thermostat,” Mira warned.',
            '“Last time it tripped the breaker.”',
            "The radiator ticked softly in agreement.",
        ),
    ),
    SentenceCase(
        "en_s11",
        "staccato",
        (
            "Rain.",
            "Glass.",
            "Static.",
            "A siren faded three blocks east.",
        ),
    ),
    SentenceCase(
        "en_s12",
        "staccato",
        (
            "No signal.",
            "No cab.",
            "Just wet pavement and a flickering ATM.",
        ),
    ),
    SentenceCase(
        "en_s13",
        "numbers_initials",
        (
            "The meter stopped at 14.80 near J. R. Bennett Square.",
            "She paid with a crumpled twenty and kept walking.",
        ),
    ),
    SentenceCase(
        "en_s14",
        "numbers_initials",
        (
            "Version 2.4 crashed on startup at 8.15 every Monday.",
            "Only K. L. Ortega knew which script reset the queue.",
        ),
    ),
    SentenceCase(
        "en_s15",
        "mixed_contemporary",
        (
            "Look at the sky!",
            "Did the storm turn south?",
            "Half the harbor had already gone gray.",
        ),
    ),
)

EN_DIALOGUE_CASES: tuple[DialogueCase, ...] = (
    DialogueCase(
        "en_d01",
        "standard_quoted",
        '"[[Leave the umbrella by the radiator,]]" Nora said. "[[The floor is already slick.]]"',
    ),
    DialogueCase(
        "en_d02",
        "standard_quoted",
        'He tapped the receipt. “[[You overcharged us for the parking pass.]]”',
    ),
    DialogueCase(
        "en_d03",
        "standard_quoted",
        '"[[Did anyone lock the loading dock?]]" Jonas asked, already reaching for his coat.',
    ),
    DialogueCase(
        "en_d04",
        "standard_quoted",
        '“[[Wait until Tuesday,]]” she told him, “[[the clinic never answers on Mondays.]]”',
    ),
    DialogueCase(
        "en_d05",
        "standard_quoted",
        'She whispered, "[[Keep your voice down, the baby just fell asleep.]]" Then she stepped back.',
    ),
    DialogueCase(
        "en_d06",
        "standard_quoted",
        '"[[Three espresso shots and a plain croissant,]]" he ordered without looking up.',
    ),
    DialogueCase(
        "en_d07",
        "non_speech_quote",
        'The elevator bore a laminated "Out of Service" placard taped over the buttons.',
    ),
    DialogueCase(
        "en_d08",
        "non_speech_quote",
        'Her landlord called the damp basement a “garden studio” in the listing.',
    ),
    DialogueCase(
        "en_d09",
        "dash_speech",
        "— [[You missed the last ferry,]] the ticket clerk said without sympathy.",
    ),
    DialogueCase(
        "en_d10",
        "dash_speech",
        "— [[Is this seat taken?]]\n— [[Only by my backpack,]] she replied.",
    ),
    DialogueCase(
        "en_d11",
        "dash_speech",
        "— [[We should have left before dusk,]] Tariq murmured into his scarf.",
    ),
    DialogueCase(
        "en_d12",
        "interior_thought",
        "She stared at the blinking cursor. [[If I send this email tonight, I cannot take it back tomorrow.]]",
    ),
    DialogueCase(
        "en_d13",
        "interior_thought",
        "The hallway smelled of bleach. [[Do not look at the clock, just count the tiles.]]",
    ),
    DialogueCase(
        "en_d14",
        "free_indirect",
        "He checked his watch again. [[Where on earth was she? The train had arrived twenty minutes ago.]]",
    ),
    DialogueCase(
        "en_d15",
        "free_indirect",
        "Hannah folded the eviction notice. [[Of course they would raise the rent in winter, when moving was impossible.]]",
    ),
    DialogueCase(
        "en_d16",
        "free_indirect",
        "No one answered the intercom. [[Maybe he had written down the wrong building number after all.]]",
    ),
)

EN_TENSE_CASES: tuple[TenseCase, ...] = (
    TenseCase("en_t01", "past", "Maya {past:walked} past the closed bakery and {past:checked} her phone."),
    TenseCase("en_t02", "past", "The harbor lights {past:flickered} while the ferry {past:turned} toward the pier."),
    TenseCase("en_t03", "past", "He {past:spoke} softly and {past:handed} her the rusted padlock."),
    TenseCase("en_t04", "past", "Three cyclists {past:swerved} around the puddle and {past:vanished} down the alley."),
    TenseCase("en_t05", "past", "She {past:knew} the shortcut, yet she {past:took} the longer avenue anyway."),
    TenseCase("en_t06", "past", "Rain {past:tapped} against the skylight while the kettle {past:boiled}."),
    TenseCase("en_t07", "past", "They {past:drove} past the refinery and {past:parked} beside the seawall."),
    TenseCase("en_t08", "past", "He {past:forgot} his scarf and {past:shivered} on the windy platform."),
    TenseCase("en_t09", "present", "Nora {pres:stands} by the sink and {pres:watches} the traffic crawl."),
    TenseCase("en_t10", "present", "The barista {pres:wipes} the counter while the grinder {pres:hums}."),
    TenseCase("en_t11", "present", "Every morning he {pres:takes} the blue line and {pres:reads} two pages."),
    TenseCase("en_t12", "present", "She {pres:knows} the route by heart and never {pres:checks} the map."),
    TenseCase("en_t13", "present", "A stray dog {pres:sleeps} under the bench while commuters {pres:hurry} past."),
    TenseCase("en_t14", "present", "The radiator {pres:clicks} and {pres:warms} the narrow studio."),
    TenseCase("en_t15", "present", "We {pres:wait} outside the pharmacy until the shutters {pres:rise}."),
    TenseCase("en_t16", "present", "He {pres:looks} at the receipt and {pres:shakes} his head."),
    TenseCase("en_t17", "perfect", "She {past:has finished} the draft and {past:has sent} it to her editor."),
    TenseCase("en_t18", "perfect", "They {past:had left} the keys before the locksmith {past:arrived}."),
    TenseCase("en_t19", "perfect", "I {past:have waited} three hours and the parcel still {pres:remains} missing."),
    TenseCase("en_t20", "perfect", "He {past:had already forgotten} the password when the screen {past:locked}."),
    TenseCase("en_t21", "perfect", "The neighbors {past:have painted} the stairwell twice this year."),
    TenseCase("en_t22", "perfect", "By noon the fog {past:had lifted} over the container terminal."),
    TenseCase("en_t23", "mixed", 'She {past:opened} the window and {past:said}, "The air {pres:smells} like salt."'),
    TenseCase("en_t24", "mixed", 'He {past:pointed} at the schedule. "The express {pres:leaves} in four minutes."'),
    TenseCase("en_t25", "mixed", "Yesterday the elevator {past:stopped} twice, and today it still {pres:rattles}."),
    TenseCase("en_t26", "mixed", "She {past:bought} the coat in Prague; it {pres:keeps} out the wind."),
    TenseCase("en_t27", "mixed", 'They {past:laughed}, though nobody {pres:remembers} who {past:started} the rumor.'),
    TenseCase("en_t28", "mixed", "He {past:wrote} the note in haste; the ink still {pres:looks} wet."),
    TenseCase("en_t29", "ambiguous", "Yesterday she {past:read} the whole contract and {past:put} it in the safe."),
    TenseCase("en_t30", "ambiguous", "Every Friday he {pres:cuts} the sourdough and {pres:sets} the table."),
    TenseCase("en_t31", "ambiguous", "Last winter the storm {past:hit} the roof and {past:split} the gutter."),
    TenseCase("en_t32", "ambiguous", "She {past:shut} the laptop and {past:let} the room go dark."),
)


# ---------------------------------------------------------------------------
# Held-out contemporary-style prose benchmark: German (DE)
# ---------------------------------------------------------------------------

DE_SENTENCE_CASES: tuple[SentenceCase, ...] = (
    SentenceCase(
        "de_s01",
        "abbreviations",
        (
            "Dr. Brandt prüfte den Befund gemeinsam mit Prof. Seidel.",
            "Keiner von beiden vertraute dem späten Laborbericht.",
        ),
    ),
    SentenceCase(
        "de_s02",
        "abbreviations",
        (
            "Sie packte nur das Nötigste ein, z. B. Wollsocken und ein Ladegerät.",
            "Das reichte für drei Tage, d. h. bis zum Rückflug am Freitag.",
        ),
    ),
    SentenceCase(
        "de_s03",
        "abbreviations_edge",
        (
            "Der Brief enthielt u. a. eine Mahnung über ca. 42 Euro.",
            "Auf dem Umschlag stand noch Tel. 030.",
            "Niemand hatte die alte Nummer gelöscht.",
        ),
    ),
    SentenceCase(
        "de_s04",
        "abbreviations_edge",
        (
            "In Haus Nr. 14 wohnte früher eine Klavierlehrerin.",
            "Heute hängen dort Klingelschilder von Agenturen usw.",
            "Nur im Dachgeschoss brennt abends noch Licht.",
        ),
    ),
    SentenceCase(
        "de_s05",
        "ellipses",
        (
            "Warte... nein, lass das Fenster lieber einen Spalt offen.",
            "Der Geruch nach frischer Farbe hing noch im Flur.",
        ),
    ),
    SentenceCase(
        "de_s06",
        "ellipses",
        (
            "Er sah dem letzten Regionalzug hinterher…",
            "Dann gingen am Bahnsteig die Anzeigen aus.",
        ),
    ),
    SentenceCase(
        "de_s07",
        "ellipses",
        (
            "Sie wollte etwas erwidern...",
            "Doch der Fahrer schloss bereits die Tür.",
        ),
    ),
    SentenceCase(
        "de_s08",
        "dialogue_punct",
        (
            "„Kommst du mit?“, fragte sie aus dem Treppenhaus.",
            "„Gib mir eine Minute!“, rief er zurück.",
            "Sein Schlüsselbund klirrte am Geländer.",
        ),
    ),
    SentenceCase(
        "de_s09",
        "dialogue_punct",
        (
            "»Halt!«",
            "Er griff nach ihrem Ärmel.",
            "»Die Ampel ist längst rot.«",
            "Ein Lieferwagen rauschte über die Kreuzung.",
        ),
    ),
    SentenceCase(
        "de_s10",
        "dialogue_punct",
        (
            "„Das stimmt nicht.“ murmelte Lukas leise.",
            "„Ich war gestern gar nicht in der Stadt.“",
            "Niemand im Raum glaubte ihm.",
        ),
    ),
    SentenceCase(
        "de_s11",
        "staccato",
        (
            "Regen.",
            "Glas.",
            "Stille.",
            "In der Ferne heulte eine Sirene auf.",
        ),
    ),
    SentenceCase(
        "de_s12",
        "staccato",
        (
            "Kein Empfang.",
            "Kein Taxi.",
            "Nur nasser Asphalt und ein flackernder Automat.",
        ),
    ),
    SentenceCase(
        "de_s13",
        "numbers_initials",
        (
            "Der Zähler blieb bei 12.500 Kilometern vor dem K. M. Richter-Platz stehen.",
            "Sie zog die Handbremse an und atmete aus.",
        ),
    ),
    SentenceCase(
        "de_s14",
        "numbers_initials",
        (
            "Um 8.30 Uhr begann der Vortrag von A. L. Brenner.",
            "Die Version 3.14 lief endlich ohne Absturz.",
        ),
    ),
    SentenceCase(
        "de_s15",
        "mixed_contemporary",
        (
            "Sieh dir den Himmel an!",
            "Zieht das Gewitter nach Osten ab?",
            "Über dem Hafen riss die Wolkendecke langsam auf.",
        ),
    ),
)

DE_DIALOGUE_CASES: tuple[DialogueCase, ...] = (
    DialogueCase(
        "de_d01",
        "standard_quoted",
        "„[[Stell den Schirm an die Heizung,]]“ sagte Katrin. „[[Der Flur ist schon ganz nass.]]“",
    ),
    DialogueCase(
        "de_d02",
        "standard_quoted",
        "Er tippte auf den Kassenbon. »[[Sie haben die Pfandflaschen zweimal berechnet.]]«",
    ),
    DialogueCase(
        "de_d03",
        "standard_quoted",
        "„[[Hat jemand das Hoftor abgeschlossen?]]“ fragte Tobias und griff nach seiner Jacke.",
    ),
    DialogueCase(
        "de_d04",
        "standard_quoted",
        "»[[Warte bis Dienstag,]]« riet sie ihm, »[[montags geht dort niemand ans Telefon.]]«",
    ),
    DialogueCase(
        "de_d05",
        "standard_quoted",
        'Sie flüsterte: "[[Sprich leiser, das Kind schläft gerade ein.]]" Dann schloss sie die Tür.',
    ),
    DialogueCase(
        "de_d06",
        "standard_quoted",
        "„[[Zwei Filterkaffee und ein Laugenbrötchen,]]“ bestellte er, ohne aufzusehen.",
    ),
    DialogueCase(
        "de_d07",
        "non_speech_quote",
        "Am Aufzug klebte ein laminiertes Schild mit der Aufschrift „Außer Betrieb“.",
    ),
    DialogueCase(
        "de_d08",
        "non_speech_quote",
        "Der Vermieter nannte das feuchte Kellerzimmer im Inserat ein »Gartenatelier«.",
    ),
    DialogueCase(
        "de_d09",
        "dash_speech",
        "– [[Du hast die letzte Fähre verpasst,]] sagte der Kartenverkäufer trocken.",
    ),
    DialogueCase(
        "de_d10",
        "dash_speech",
        "– [[Ist hier noch frei?]]\n– [[Nur mein Rucksack liegt dort,]] antwortete sie.",
    ),
    DialogueCase(
        "de_d11",
        "dash_speech",
        "— [[Wir hätten vor Einbruch der Dunkelheit fahren sollen,]] murmelte Samir.",
    ),
    DialogueCase(
        "de_d12",
        "interior_thought",
        "Sie starrte auf den blinkenden Cursor. [[Wenn ich diese Mail jetzt abschicke, gibt es kein Zurück.]]",
    ),
    DialogueCase(
        "de_d13",
        "interior_thought",
        "Der Korridor roch nach Desinfektionsmittel. [[Nicht auf die Uhr schauen, einfach weitergehen.]]",
    ),
    DialogueCase(
        "de_d14",
        "free_indirect",
        "Er sah wieder auf sein Handy. [[Wo blieb sie denn nur? Der ICE war doch längst eingelaufen.]]",
    ),
    DialogueCase(
        "de_d15",
        "free_indirect",
        "Hannah faltete die Mieterhöhung zusammen. [[Natürlich kamen sie damit mitten im Winter, wenn niemand umziehen konnte.]]",
    ),
    DialogueCase(
        "de_d16",
        "free_indirect",
        "Niemand öffnete auf das Klingeln. [[Vielleicht hatte er sich doch in der Hausnummer geirrt.]]",
    ),
)

DE_TENSE_CASES: tuple[TenseCase, ...] = (
    TenseCase("de_t01", "past", "Lena {past:ging} an der geschlossenen Bäckerei vorbei und {past:sah} auf ihr Handy."),
    TenseCase("de_t02", "past", "Die Hafenlichter {past:flackerten}, während die Fähre langsam {past:wendete}."),
    TenseCase("de_t03", "past", "Er {past:sprach} leise und {past:gab} ihr den verrosteten Schlüssel."),
    TenseCase("de_t04", "past", "Zwei Radfahrer {past:klingelten} laut und {past:verschwanden} im Nebel."),
    TenseCase("de_t05", "past", "Sie {past:kannte} den Weg, doch sie {past:nahm} trotzdem die längere Straße."),
    TenseCase("de_t06", "past", "Regen {past:klopfte} ans Dachfenster, während die Fahnen im Hof {past:flatterten}."),
    TenseCase("de_t07", "past", "Er {past:stolperte} über die Stufe und {past:blieb} kurz stehen."),
    TenseCase("de_t08", "past", "Sie {past:wusste} keinen Rat und {past:schrieb} eine kurze Nachricht."),
    TenseCase("de_t09", "present", "Nora {pres:steht} am Fenster und {pres:beobachtet} den stockenden Verkehr."),
    TenseCase("de_t10", "present", "Der Kellner {pres:wischt} den Tresen ab, während die Maschine {pres:brummt}."),
    TenseCase("de_t11", "present", "Jeden Morgen {pres:nimmt} er die S-Bahn und {pres:liest} zwei Kapitel."),
    TenseCase("de_t12", "present", "Sie {pres:kennt} die Abkürzung und {pres:braucht} keinen Stadtplan."),
    TenseCase("de_t13", "present", "Ein Hund {pres:schläft} unter der Bank, während Pendler {pres:vorbeieilen}."),
    TenseCase("de_t14", "present", "Die Heizung {pres:knackt} leise und {pres:wärmt} das schmale Zimmer."),
    TenseCase("de_t15", "present", "Wir {pres:warten} vor der Apotheke, bis das Rollo {pres:hochfährt}."),
    TenseCase("de_t16", "present", "Er {pres:schaut} auf die Rechnung und {pres:schüttelt} den Kopf."),
    TenseCase("de_t17", "perfect", "Sie {past:hat den Entwurf beendet} und ihn sofort {past:verschickt}."),
    TenseCase("de_t18", "perfect", "Er {past:ist gestern gelaufen} und {past:hat anschließend eingekauft}."),
    TenseCase("de_t19", "perfect", "Sie {past:blieb} ruhig, weil sie den Brief schon {past:gelesen hat}."),
    TenseCase("de_t20", "perfect", "Das Treppenhaus {past:ist letztes Jahr renoviert worden}."),
    TenseCase("de_t21", "perfect", "Wir {past:haben drei Stunden gewartet}, doch niemand {past:kam}."),
    TenseCase("de_t22", "perfect", "Am Mittag {past:hatte der Nebel sich verzogen}."),
    TenseCase("de_t23", "mixed", "Sie {past:öffnete} das Fenster und {past:sagte}: „Die Luft {pres:riecht} nach Salz.“"),
    TenseCase("de_t24", "mixed", "Er {past:zeigte} auf die Tafel. „Der Zug {pres:fährt} in vier Minuten.“"),
    TenseCase("de_t25", "mixed", "Gestern {past:blieb} der Aufzug stehen, und heute {pres:klappert} er noch immer."),
    TenseCase("de_t26", "mixed", "Sie {past:kaufte} den Mantel in Wien; er {pres:hält} den Wind gut ab."),
    TenseCase("de_t27", "mixed", "Alle {past:lachten}, obwohl niemand {pres:weiß}, wer das Gerücht {past:erfand}."),
    TenseCase("de_t28", "mixed", "Er {past:schrieb} den Zettel hastig; die Tinte {pres:wirkt} noch feucht."),
    TenseCase("de_t29", "ambiguous", "Beim Lesen {pres:bleibt} der Mantel im feuchten Flur hängen."),
    TenseCase("de_t30", "ambiguous", "Ich {pres:habe} gelben Stoff für die Vorhänge im Atelier."),
    TenseCase("de_t31", "ambiguous", "Sie {pres:halten} das Schild hoch, während der Bus {pres:bremst}."),
    TenseCase("de_t32", "ambiguous", "Das Hemd {pres:ist} blau und weiß gestreift."),
)


# ---------------------------------------------------------------------------
# Pure-stdlib statistics (Wilson 95% CI, P/R/F1)
# ---------------------------------------------------------------------------


def wilson_interval(successes: int, total: int, *, z: float = WILSON_Z_95) -> tuple[float | None, float | None]:
    """Return the two-sided Wilson score interval ``(low, high)`` in ``[0, 1]``.

    Returns ``(None, None)`` when ``total <= 0`` (undefined denominator).
    """
    if total <= 0:
        return None, None
    if successes < 0 or successes > total:
        raise ValueError(f"successes ({successes}) must be in [0, total ({total})]")
    p = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    half = (z * math.sqrt((p * (1.0 - p)) / total + z2 / (4.0 * total * total))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def prf_metrics(tp: int, fp: int, fn: int) -> dict[str, Any]:
    """Compute Precision, Recall, F1, and 95% Wilson CIs for Precision and Recall."""
    prec_n = tp + fp
    rec_n = tp + fn
    precision = tp / prec_n if prec_n > 0 else None
    recall = tp / rec_n if rec_n > 0 else None
    f1 = (2.0 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else None
    p_lo, p_hi = wilson_interval(tp, prec_n)
    r_lo, r_hi = wilson_interval(tp, rec_n)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "precision_ci95": [p_lo, p_hi] if p_lo is not None else None,
        "recall": recall,
        "recall_ci95": [r_lo, r_hi] if r_lo is not None else None,
        "f1": f1,
    }


# ---------------------------------------------------------------------------
# Inline annotation parsers
# ---------------------------------------------------------------------------

_DIALOGUE_TAG_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
_TENSE_TAG_RE = re.compile(r"\{(past|pres):([^{}]+)\}")


def parse_dialogue_annotation(annotated: str) -> tuple[str, list[tuple[int, int]]]:
    """Strip ``[[...]]`` markers and return ``(plain_text, gold_char_ranges)``."""
    parts: list[str] = []
    spans: list[tuple[int, int]] = []
    pos = 0
    out_len = 0
    for match in _DIALOGUE_TAG_RE.finditer(annotated):
        before = annotated[pos : match.start()]
        parts.append(before)
        out_len += len(before)
        inner = match.group(1)
        start = out_len
        parts.append(inner)
        out_len += len(inner)
        spans.append((start, out_len))
        pos = match.end()
    parts.append(annotated[pos:])
    return "".join(parts), spans


def parse_tense_annotation(
    annotated: str,
) -> tuple[str, list[tuple[int, int]], list[tuple[int, int]]]:
    """Strip ``{past:...}`` / ``{pres:...}`` markers into plain text and gold spans."""
    parts: list[str] = []
    gold_present: list[tuple[int, int]] = []
    gold_past: list[tuple[int, int]] = []
    pos = 0
    out_len = 0
    for match in _TENSE_TAG_RE.finditer(annotated):
        before = annotated[pos : match.start()]
        parts.append(before)
        out_len += len(before)
        label, inner = match.group(1), match.group(2)
        start = out_len
        parts.append(inner)
        out_len += len(inner)
        if label == "pres":
            gold_present.append((start, out_len))
        else:
            gold_past.append((start, out_len))
        pos = match.end()
    parts.append(annotated[pos:])
    return "".join(parts), gold_present, gold_past


# ---------------------------------------------------------------------------
# Task evaluators
# ---------------------------------------------------------------------------


def evaluate_sentences(language: str, cases: Sequence[SentenceCase]) -> dict[str, Any]:
    """Score internal sentence-boundary precision/recall (excluding passage-final ends)."""
    tp = fp = fn = 0
    total_gold_sentences = 0
    error_examples: list[dict[str, Any]] = []

    for case in cases:
        total_gold_sentences += len(case.sentences)
        text = case.separator.join(case.sentences)
        gold_ends: set[int] = set()
        cursor = 0
        for idx, sent in enumerate(case.sentences):
            end = cursor + len(sent)
            if idx < len(case.sentences) - 1:
                gold_ends.add(end)
            cursor = end + len(case.separator)

        pred_spans = split_sentence_spans(text, language)
        pred_ends = {end for _, end in pred_spans[:-1]}

        case_tp = len(gold_ends & pred_ends)
        case_fp = len(pred_ends - gold_ends)
        case_fn = len(gold_ends - pred_ends)
        tp += case_tp
        fp += case_fp
        fn += case_fn

        if case_fp or case_fn:
            error_examples.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "fp": case_fp,
                    "fn": case_fn,
                    "predicted_sentences": [text[a:b] for a, b in pred_spans],
                }
            )

    return {
        "n_passages": len(cases),
        "n_gold_sentences": total_gold_sentences,
        "n_gold_internal_boundaries": tp + fn,
        **prf_metrics(tp, fp, fn),
        "error_cases": error_examples,
    }


def _in_any_range(start: int, end: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(r_start <= start and end <= r_end for r_start, r_end in ranges)


def evaluate_dialogue(language: str, cases: Sequence[DialogueCase]) -> dict[str, Any]:
    """Score word-token dialogue detection against ``scan_quotations``."""
    resolved = resolve_language(CorpusConfig(language=language))
    word_re = compile_word_pattern(resolved.word_regex)
    group = 1 if word_re.groups else 0

    tp = fp = fn = tn = 0
    by_category: dict[str, dict[str, int]] = {}

    for case in cases:
        text, gold_ranges = parse_dialogue_annotation(case.annotated)
        analysis = scan_quotations(text, language)
        pred_ranges = merge_quotation_spans(analysis.spans)

        cat_counts = by_category.setdefault(case.category, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        for match in word_re.finditer(text):
            w_start, w_end = match.span(group)
            if w_end <= w_start:
                continue
            is_gold = _in_any_range(w_start, w_end, gold_ranges)
            is_pred = _in_any_range(w_start, w_end, pred_ranges)
            if is_gold and is_pred:
                tp += 1
                cat_counts["tp"] += 1
            elif is_pred and not is_gold:
                fp += 1
                cat_counts["fp"] += 1
            elif is_gold and not is_pred:
                fn += 1
                cat_counts["fn"] += 1
            else:
                tn += 1
                cat_counts["tn"] += 1

    breakdown = {
        cat: prf_metrics(c["tp"], c["fp"], c["fn"])
        for cat, c in sorted(by_category.items())
    }
    return {
        "n_passages": len(cases),
        "n_tokens": tp + fp + fn + tn,
        "tn": tn,
        **prf_metrics(tp, fp, fn),
        "by_category": breakdown,
    }


def _match_spans_1to1(
    gold_spans: Sequence[tuple[int, int]],
    pred_spans: Sequence[tuple[int, int]],
) -> tuple[int, int, int]:
    """Greedy 1-to-1 overlap matching between gold and predicted spans."""
    used_pred: set[int] = set()
    tp = 0
    for g_start, g_end in gold_spans:
        for idx, (p_start, p_end) in enumerate(pred_spans):
            if idx in used_pred:
                continue
            if p_start < g_end and g_start < p_end:
                used_pred.add(idx)
                tp += 1
                break
    fp = len(pred_spans) - tp
    fn = len(gold_spans) - tp
    return tp, fp, fn


def evaluate_tense(language: str, cases: Sequence[TenseCase]) -> dict[str, Any]:
    """Score finite tense-cue detection against default ``TenseMatcher``."""
    config = CorpusConfig(language=language)
    resolved = resolve_language(config)
    matcher = TenseMatcher(config, resolved)

    pres_tp = pres_fp = pres_fn = 0
    past_tp = past_fp = past_fn = 0
    error_examples: list[dict[str, Any]] = []

    for case in cases:
        text, gold_pres, gold_past = parse_tense_annotation(case.annotated)
        pred_pres, pred_past = matcher.spans(text)

        ptp, pfp, pfn = _match_spans_1to1(gold_pres, pred_pres)
        btp, bfp, bfn = _match_spans_1to1(gold_past, pred_past)
        pres_tp += ptp
        pres_fp += pfp
        pres_fn += pfn
        past_tp += btp
        past_fp += bfp
        past_fn += bfn

        if pfp or pfn or bfp or bfn:
            error_examples.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "present_fp": pfp,
                    "present_fn": pfn,
                    "past_fp": bfp,
                    "past_fn": bfn,
                }
            )

    return {
        "n_passages": len(cases),
        "combined": prf_metrics(pres_tp + past_tp, pres_fp + past_fp, pres_fn + past_fn),
        "present": prf_metrics(pres_tp, pres_fp, pres_fn),
        "past": prf_metrics(past_tp, past_fp, past_fn),
        "error_cases": error_examples,
    }


def run_benchmark() -> dict[str, Any]:
    """Run the complete EN + DE held-out contemporary-style prose benchmark."""
    return {
        "benchmark": "contemporary-style-prose-heldout/1",
        "ci_method": "wilson-95",
        "languages": {
            "en": {
                "sentence_boundaries": evaluate_sentences("en", EN_SENTENCE_CASES),
                "dialogue_cues": evaluate_dialogue("en", EN_DIALOGUE_CASES),
                "tense_cues": evaluate_tense("en", EN_TENSE_CASES),
            },
            "de": {
                "sentence_boundaries": evaluate_sentences("de", DE_SENTENCE_CASES),
                "dialogue_cues": evaluate_dialogue("de", DE_DIALOGUE_CASES),
                "tense_cues": evaluate_tense("de", DE_TENSE_CASES),
            },
        },
    }


def _fmt_rate(value: float | None, ci: Sequence[float] | None = None) -> str:
    if value is None:
        return "n/a"
    if ci is None:
        return f"{value * 100:.1f}%"
    return f"{value * 100:.1f}% [{ci[0] * 100:.1f}%, {ci[1] * 100:.1f}%]"


def format_markdown(report: dict[str, Any]) -> str:
    """Format the benchmark report as human-readable Markdown tables."""
    lines = [
        "# Contemporary-Style Prose Benchmark (Synthetic Held-Out Set)",
        "",
        "| Language | Task | Sample | TP / FP / FN | Precision (95% Wilson CI) | Recall (95% Wilson CI) | F1 |",
        "| --- | --- | --- | ---: | --- | --- | ---: |",
    ]
    for lang in ("en", "de"):
        data = report["languages"][lang]
        sent = data["sentence_boundaries"]
        lines.append(
            f"| {lang.upper()} | Sentence boundaries | "
            f"{sent['n_passages']} passages / {sent['n_gold_sentences']} sents / {sent['n_gold_internal_boundaries']} bounds | "
            f"{sent['tp']} / {sent['fp']} / {sent['fn']} | "
            f"{_fmt_rate(sent['precision'], sent['precision_ci95'])} | "
            f"{_fmt_rate(sent['recall'], sent['recall_ci95'])} | "
            f"{_fmt_rate(sent['f1'])} |"
        )
        dlg = data["dialogue_cues"]
        lines.append(
            f"| {lang.upper()} | Dialogue cues (all) | "
            f"{dlg['n_passages']} passages / {dlg['n_tokens']} tokens | "
            f"{dlg['tp']} / {dlg['fp']} / {dlg['fn']} | "
            f"{_fmt_rate(dlg['precision'], dlg['precision_ci95'])} | "
            f"{_fmt_rate(dlg['recall'], dlg['recall_ci95'])} | "
            f"{_fmt_rate(dlg['f1'])} |"
        )
        tense = data["tense_cues"]
        tc = tense["combined"]
        lines.append(
            f"| {lang.upper()} | Tense cues (combined) | "
            f"{tense['n_passages']} passages / {tc['tp'] + tc['fn']} cues | "
            f"{tc['tp']} / {tc['fp']} / {tc['fn']} | "
            f"{_fmt_rate(tc['precision'], tc['precision_ci95'])} | "
            f"{_fmt_rate(tc['recall'], tc['recall_ci95'])} | "
            f"{_fmt_rate(tc['f1'])} |"
        )
        for sub_name, sub_label in (("past", "Tense cues (past)"), ("present", "Tense cues (present)")):
            sub = tense[sub_name]
            lines.append(
                f"| {lang.upper()} | {sub_label} | "
                f"{sub['tp'] + sub['fn']} gold cues | "
                f"{sub['tp']} / {sub['fp']} / {sub['fn']} | "
                f"{_fmt_rate(sub['precision'], sub['precision_ci95'])} | "
                f"{_fmt_rate(sub['recall'], sub['recall_ci95'])} | "
                f"{_fmt_rate(sub['f1'])} |"
            )

    lines.extend(
        [
            "",
            "## Dialogue recall breakdown by category",
            "",
            "| Language | Category | TP / FP / FN | Precision (95% Wilson CI) | Recall (95% Wilson CI) |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for lang in ("en", "de"):
        by_cat = report["languages"][lang]["dialogue_cues"]["by_category"]
        for cat, metrics in by_cat.items():
            lines.append(
                f"| {lang.upper()} | `{cat}` | "
                f"{metrics['tp']} / {metrics['fp']} / {metrics['fn']} | "
                f"{_fmt_rate(metrics['precision'], metrics['precision_ci95'])} | "
                f"{_fmt_rate(metrics['recall'], metrics['recall_ci95'])} |"
            )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    args = parser.parse_args(argv)
    report = run_benchmark()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
