"""Lixity – command line: corpus analysis, style profile, style reference and dashboard."""

import argparse
import math
import os
import re
import sys
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout
from io import StringIO
from time import monotonic as _monotonic
from typing import Any

import orjson
from rich import box
from rich.console import Console
from rich.table import Table

from . import __version__
from .analyzer import CorpusAnalyzer
from .config import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    load_project_config,
    read_explicit_project_config,
    resolve_thresholds,
)
from .formatters import ReportFormatter
from .io import FileUtils
from .language import ResolvedLanguage
from .models import SCHEMA_VERSION, CorpusConfig
from .paragraph_evidence import ParagraphEvidence
from .pipeline import (
    analyze_document,
    fingerprint_document,
    profile_document,
    resolve_document_config,
)
from .project_identity import project_title
from .scenes import scene_report_for_display
from .site import docs_url
from .status import SCHEMA_VERSION_STYLE
from .style_fingerprint import (
    LAYER_FEATURES,
    FingerprintThresholds,
    paragraph_layer_projection,
)
from .ui import render_analysis
from .ui.manuscript_document import reader_blocks
from .workspace import resolve_manuscript_target

EXIT_OK = 0
EXIT_ERROR = 1


def _audio_progress() -> Callable[[int, int], None]:
    """Report segment progress and a coarse estimate, without changing the render."""
    started: float | None = None

    def report(done: int, total: int) -> None:
        nonlocal started
        now = _monotonic()
        if started is None:
            started = now
        message = f"Audio: {done}/{total}"
        if 2 <= done < total:
            remaining = max(0, math.ceil((now - started) * (total - done) / done))
            message += f" (ETA ~{remaining}s)"
        print(message, file=sys.stderr)

    return report


def _document_title(args: argparse.Namespace, manuscript: str, text: str) -> str:
    return project_title(manuscript, text, args._project_config)


def _thresholds_from_args(
    args: argparse.Namespace, config: dict[str, Any] | None = None
) -> FingerprintThresholds:
    """Builds FingerprintThresholds from CLI flags (defaults = documented heuristics).

    Precedence: CLI flag > project config (``[tool.lixity]`` / ``lixity.toml``) >
    built-in default — shared builder ``config.resolve_thresholds``.
    """
    return resolve_thresholds(
        project_config=config,
        z_mild=getattr(args, "z_mild", None),
        z_strong=getattr(args, "z_strong", None),
        fdr_q=getattr(args, "fdr_q", None),
        fdr_method=getattr(args, "fdr_method", None),
        dim_score_threshold=getattr(args, "dim_threshold", None),
        flag_min_severity=getattr(args, "flag_min_severity", None),
        min_chapters=getattr(args, "min_chapters", None),
    )


def _json(payload: object, indent: bool = False) -> str:
    """Serialises to UTF-8 JSON with orjson (one serializer for the whole CLI)."""
    option = orjson.OPT_NON_STR_KEYS | (orjson.OPT_INDENT_2 if indent else 0)
    return orjson.dumps(payload, option=option).decode("utf-8")


_META = {
    "tool": "lixity",
    "version": __version__,
    "schema_version": SCHEMA_VERSION,
}

# User-facing CLI messages: English is the engine default, German via
# LIXITY_LANG=de.
CLI_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "audio_status_project": "Project",
        "audio_status_selected": "Selected profile",
        "audio_status_unavailable": "Profile unavailable",
        "audio_status_match": "model match",
        "audio_status_comparison": "Comparison model",
        "audio_status_unknown": "unknown",
        "audio_status_yes": "yes",
        "audio_status_no": "no",
        "audio_status_design_hint": "VoiceDesign generates each section independently, so the voice may vary even with the same description. Different direction can also affect the voice. Compare short listening samples. Base can use a reference, but does not accept free-form direction.",
        "audio_status_base_hint": "Base reuses a voice reference but does not guarantee identical delivery; free-form direction is unsupported. Compare short listening samples.",
        "audio_no_direction_help": "Ignore saved passage direction; profile, pronunciation, speed and default pauses remain",
        "audio_instructions_help": "Explicit Qwen delivery instructions (not supported by Base)",
        "audio_engine_help": "qwen3: preset voices; qwen3-design: described voice; qwen3-base: saved reference; coqui: Thorsten; coqui-reference: converted reference voice. Worker must match",
        "audio_voice_help": "CustomVoice presets: {voices}. Qwen lists no German-native preset; audition pronunciation. Base uses reference and VoiceDesign uses design",
        "audio_base_reference_required": "Qwen Base needs a saved reference: create one with 'lixity audio-reference create' and pass --reference-id ID",
        "audio_base_instructions_inherited": "Qwen Base cannot use the selected profile's delivery instructions; pass --instructions '' to clear them for this run or select a Base profile. --no-direction only excludes passage directions",
        "audio_base_instructions_explicit": "Qwen Base does not support delivery instructions; pass --instructions '' or select another model",
        "audio_design_description_required": "VoiceDesign needs a voice description: pass --voice-description TEXT or select a VoiceDesign profile",
        "audio_custom_voice_required": "CustomVoice needs a preset voice: pass --voice with a supported preset or select a CustomVoice profile",
        "audio_reference_wrong_engine": "--reference-id is only supported by Qwen Base; select --engine qwen3-base or omit the reference",
        "audio_read_help": "VoiceDesign generates segments independently; a voice description and direction can affect the perceived voice. For a consistent narrator, compare short --preview samples with fewer role-specific directions. Base reuses an explicit voice reference, but does not accept free-form direction; neither option guarantees continuity. --no-direction ignores saved passage direction only: the selected profile, pronunciation rules, tempo and default pauses remain active. Models and matching local workers are installed separately.",
        "audio_direction_help": "With VoiceDesign, role-specific instructions may change the perceived voice between independently generated segments. Use short listening previews; Base does not support free-form direction. Pauses and explicit saved profile choices remain separate.",
        "layer_reference": 'Reference: all measurable paragraphs within each chapter; median/MAD robust z. Requires at least 3 measurable paragraphs and nonzero MAD.',
        "layer_notable": 'Notable: |round(z, 2)| >= {cutoff}; descriptive heuristic for human review.',
        "layer_counts": '{total_count} total · {comparable_count} comparable · {notable_count} notable · {selected_count} shown',
        "layer_unavailable": 'comparison unavailable',
        "layer_local": 'local z {z}',
        "layer_flag": 'notable',
        "layer_empty": 'No paragraphs selected. This is not a finding that the text has no issues.',
        "layer_empty_source": 'No paragraphs available.',
        "layer_empty_cutoff": 'No comparable paragraph reaches the selected cutoff.',
        "layer_short": 'Chapters with fewer than 3 measurable paragraphs: {count}',
        "layer_constant": 'Chapters with MAD = 0: {count}',
        "layer_unmeasured": 'Chapters without measurable values: {count}',
        "layer_full": 'Full evidence: {command}',
        "layer_evidence": 'Evidence: {status} · {mapped}/{count} {unit} mapped{reason}',
        "layer_available": 'available',
        "layer_partial": 'partial',
        "layer_missing": 'unavailable',
        "layer_sentence": 'sentences',
        "layer_word": 'word cues',
        "layer_pattern": 'pattern matches',
        "layer_dialogue": 'quoted words',
        "layer_words": 'words',
        "layer_more": 'further spans; use --json for all offsets',
        "about_title": "lixity {version} – quantitative text linguistics & stylometry",
        "about_languages": "Languages: {languages}",
        "about_features": "Features ({count}):",
        "about_heuristics": (
            "Heuristics: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, dimensions={n_dimensions}, "
            "min_words={min_comparable_words}, min_sentences={min_comparable_sentences}"
        ),
        "about_commands": "Commands:",
        "about_license": "License: {license}",
        'doctor_cli_version': 'CLI version',
        'doctor_distribution_version': 'Package metadata',
        'doctor_module_path': 'Imported module',
        'doctor_interpreter': 'Python interpreter',
        'doctor_service': 'Service state',
        'doctor_unknown': 'Unavailable',
        'doctor_ok': 'Installation checks passed.',
        'doctor_invalid_service_port': 'Service port must be an integer between 1 and 65535.',
        'doctor_service_version_unavailable': 'The running service version is unavailable. Inspect its installation before deciding whether to restart it.',
        'doctor_distribution_version_mismatch': 'Imported Lixity and package metadata have different versions. Reinstall Lixity in the intended environment.',
        'doctor_distribution_metadata_unavailable': 'Package metadata is unavailable. Repair the installation before relying on its version.',
        'doctor_service_inspection_unavailable': 'Service state could not be verified. Inspect service status before restarting it.',
        'doctor_service_version_mismatch': 'The running service uses another version. Restart it after updating the installation.',
        "err_prefix": "[error]",
        "err_shell": "Unknown shell: {shell} (bash|zsh)",
        "err_file": "File not readable: {file} ({exc})",
        "err_build_target": (
            "Cannot write to the exports folder {dir}: {exc}. Exports need a writable "
            "folder – read-only mounts and sandboxes block builds; use --dry-run to "
            "preview changes without writing."
        ),
        "build_workspace": "Workspace: {root}",
        "build_manuscript": "Manuscript: {file} (language: {language})",
        "state_written": "written",
        "state_unchanged": "unchanged",
        "build_dry_run": ("Dry run: {changed} to write, {unchanged} unchanged – no files changed."),
        "build_done": "Done: {changed} written, {unchanged} unchanged.",
        "dashboard_written": "Dashboard written: {output}",
        "site_export_done": "Read-only website exported. Review included content before sharing.",
        "dashboard_unchanged": "Dashboard unchanged: {output}",
        "pdf_written": "PDF written: {output}",
        "pdf_unchanged": "PDF unchanged: {output}",
        "speech_written": "Audio written: {output}",
        "err_no_names": "No figure names selected (use --name, --names or project characters settings).",
        "dlg_metric": "Quotation measurement",
        "dlg_value": "Value",
        "dlg_turns": "Quoted spans",
        "dlg_dialogue_pct": "Quoted-word share",
        "dlg_avg_turn": "Mean quoted-span length (words)",
        "dlg_median_turn": "Median quoted-span length (words)",
        "dlg_longest_turn": "Longest quoted span (words)",
        "dlg_turns_per_1000": "Quoted spans per 1,000 words",
        "dlg_paragraph_pct": "Paragraphs with quoted text",
        "dlg_chapter": "Ch.",
        "dlg_title": "Title",
        "chr_name": "Figure",
        "chr_mentions": "Mentions",
        "chr_chapters": "Chapters with mentions",
        "chr_span": "Chapter span",
        "chr_gap": "Internal gap",
        "chr_share": "Mention coverage",
        "chr_pov": "Declared POV chapters",
        "pac_metric": "Pacing metric",
        "pac_value": "Value",
        "pac_chapters": "Chapters",
        "pac_scenes": "Scenes",
        "pac_avg_scene": "Average scene (words)",
        "pac_hook_mean": "Mean ending-cue count",
        "pac_fastest": "Chapter with shortest sentences (mean)",
        "pac_slowest": "Chapter with longest sentences (mean)",
        "pac_chapter": "Ch.",
        "pac_title": "Title",
        "pac_asl": "ASL",
        "pac_dialogue": "Quoted words",
        "pac_hook": "Hook",
        "pac_no_breaks": (
            "No explicit scene dividers found — scenes = chapters "
            "(scene structure is uninformative)."
        ),
        "err_motif_spec": "Invalid motif (expected NAME=REGEX): {spec}",
        "mot_name": "Motif",
        "mot_mentions": "Mentions",
        "mot_density": "Per 1,000 words",
        "mot_span": "Chapter span",
        "mot_gap": "Longest gap",
        "mot_top_words": "Most frequent content words:",
        "mot_phrase": "Repeated phrase",
        "mot_count": "Count",
        "mot_chapters": "Chapters",
        "show_metric": "Signal-group comparison",
        "show_value": "Value",
        "show_chapters": "Chapters",
        "show_tell_z": "Word-pattern cues (mean z)",
        "show_show_z": "Quotes / short sentences (mean z)",
        "show_balance": "Difference (second - first)",
        "show_most_telling": "Lowest difference: chapters",
        "show_most_showing": "Highest difference: chapters",
        "show_chapter": "Ch.",
        "show_title": "Title",
    },
    "de": {
        "audio_status_project": "Projekt",
        "audio_status_selected": "Gewähltes Profil",
        "audio_status_unavailable": "Profil nicht verfügbar",
        "audio_status_match": "Modell passt",
        "audio_status_comparison": "Vergleichsmodell",
        "audio_status_unknown": "unbekannt",
        "audio_status_yes": "ja",
        "audio_status_no": "nein",
        "audio_status_design_hint": "VoiceDesign erzeugt Abschnitte einzeln; die Stimme kann trotz gleicher Beschreibung variieren. Unterschiedliche Regie kann den Klang zusätzlich beeinflussen. Kurze Hörproben vergleichen. Base nutzt eine Referenz, unterstützt aber keine freie Regie.",
        "audio_status_base_hint": "Base nutzt eine Stimmreferenz, garantiert aber keine gleichbleibende Darbietung; freie Regie wird nicht unterstützt. Kurze Hörproben vergleichen.",
        "audio_no_direction_help": "Gespeicherte Passagenregie ignorieren; Profil, Aussprache, Tempo und Standardpausen bleiben aktiv",
        "audio_instructions_help": "Ausdrückliche Qwen-Regieanweisungen (von Base nicht unterstützt)",
        "audio_engine_help": "qwen3: feste Stimmen; qwen3-design: beschriebene Stimme; qwen3-base: Referenz; coqui: Thorsten; coqui-reference: Thorsten mit Referenzstimme. Worker muss zum Modell passen",
        "audio_voice_help": "CustomVoice-Stimmen: {voices}. Qwen nennt keine deutschsprachige Mutterstimme; Aussprache anhören. Base verwendet reference, VoiceDesign design",
        "audio_base_reference_required": "Qwen Base benötigt eine gespeicherte Referenz: mit 'lixity audio-reference create' anlegen und --reference-id ID angeben",
        "audio_base_instructions_inherited": "Qwen Base unterstützt die Regieanweisung des gewählten Profils nicht; für diesen Lauf --instructions '' angeben oder ein Base-Profil wählen. --no-direction schaltet nur die Passagenregie aus",
        "audio_base_instructions_explicit": "Qwen Base unterstützt keine Regieanweisungen; --instructions '' angeben oder ein anderes Modell wählen",
        "audio_design_description_required": "VoiceDesign benötigt eine Stimmbeschreibung: --voice-description TEXT angeben oder ein VoiceDesign-Profil wählen",
        "audio_custom_voice_required": "CustomVoice benötigt eine feste Stimme: mit --voice eine unterstützte Stimme angeben oder ein CustomVoice-Profil wählen",
        "audio_reference_wrong_engine": "--reference-id wird nur von Qwen Base unterstützt; --engine qwen3-base wählen oder die Referenz weglassen",
        "audio_read_help": "VoiceDesign erzeugt Abschnitte einzeln; Stimmbeschreibung und Regie können die wahrgenommene Stimme beeinflussen. Für eine einheitliche Erzählstimme kurze --preview-Hörproben mit weniger rollenspezifischer Regie vergleichen. Base verwendet eine ausdrückliche Stimmreferenz, unterstützt aber keine freie Regie; beide Wege garantieren keine Stimmkonstanz. --no-direction ignoriert nur gespeicherte Passagenregie: Profil, Ausspracheregeln, Tempo und Standardpausen bleiben aktiv. Modelle und passende lokale Worker werden separat installiert.",
        "audio_direction_help": "Bei VoiceDesign können rollenspezifische Anweisungen die wahrgenommene Stimme zwischen einzeln erzeugten Abschnitten verändern. Kurze Hörproben vergleichen; Base unterstützt keine freie Regie. Pausen und ausdrücklich gespeicherte Profilzuweisungen bleiben getrennt.",
        "layer_reference": 'Referenz: alle messbaren Absätze innerhalb jedes Kapitels; robuster z-Wert aus Median/MAD. Mindestens 3 messbare Absätze und MAD größer als 0 erforderlich.',
        "layer_notable": 'Auffällig: |round(z, 2)| >= {cutoff}; beschreibende Heuristik zur menschlichen Prüfung.',
        "layer_counts": '{total_count} gesamt · {comparable_count} vergleichbar · {notable_count} auffällig · {selected_count} angezeigt',
        "layer_unavailable": 'Vergleich nicht verfügbar',
        "layer_local": 'lokaler z-Wert {z}',
        "layer_flag": 'auffällig',
        "layer_empty": 'Keine Absätze ausgewählt. Das bedeutet nicht, dass der Text keine Probleme enthält.',
        "layer_empty_source": 'Keine Absätze vorhanden.',
        "layer_empty_cutoff": 'Kein vergleichbarer Absatz erreicht den gewählten Schwellenwert.',
        "layer_short": 'Kapitel mit weniger als 3 messbaren Absätzen: {count}',
        "layer_constant": 'Kapitel mit MAD = 0: {count}',
        "layer_unmeasured": 'Kapitel ohne messbare Werte: {count}',
        "layer_full": 'Vollständige Belege: {command}',
        "layer_evidence": 'Belege: {status} · {mapped}/{count} {unit} zugeordnet{reason}',
        "layer_available": 'verfügbar',
        "layer_partial": 'teilweise',
        "layer_missing": 'nicht verfügbar',
        "layer_sentence": 'Sätze',
        "layer_word": 'Wortbelege',
        "layer_pattern": 'Mustertreffer',
        "layer_dialogue": 'Wörter in Anführungszeichen',
        "layer_words": 'Wörter',
        "layer_more": 'weitere Bereiche; --json zeigt alle Positionen',
        "about_title": "lixity {version} – quantitative Textlinguistik & Stilometrie",
        "about_languages": "Sprachen: {languages}",
        "about_features": "Merkmale ({count}):",
        "about_heuristics": (
            "Heuristiken: z_mild={z_mild}, z_strong={z_strong}, FDR q={fdr_q}, "
            "min_chapters={min_chapters}, Dimensionen={n_dimensions}, "
            "min_words={min_comparable_words}, min_sentences={min_comparable_sentences}"
        ),
        "about_commands": "Kommandos:",
        "about_license": "Lizenz: {license}",
        'doctor_cli_version': 'CLI-Version',
        'doctor_distribution_version': 'Paketmetadaten',
        'doctor_module_path': 'Importiertes Modul',
        'doctor_interpreter': 'Python-Interpreter',
        'doctor_service': 'Dienststatus',
        'doctor_unknown': 'Nicht verfügbar',
        'doctor_ok': 'Installationsprüfung erfolgreich.',
        'doctor_invalid_service_port': 'Der Dienstport muss eine ganze Zahl zwischen 1 und 65535 sein.',
        'doctor_service_version_unavailable': 'Die Version des laufenden Dienstes ist nicht verfügbar. Prüfe seine Installation vor einem möglichen Neustart.',
        'doctor_distribution_version_mismatch': 'Importiertes Lixity und Paketmetadaten haben unterschiedliche Versionen. Installiere Lixity in der gewünschten Umgebung neu.',
        'doctor_distribution_metadata_unavailable': 'Paketmetadaten sind nicht verfügbar. Repariere die Installation, bevor du dich auf deren Versionsangabe verlässt.',
        'doctor_service_inspection_unavailable': 'Der Dienststatus konnte nicht geprüft werden. Prüfe service status vor einem Neustart.',
        'doctor_service_version_mismatch': 'Der laufende Dienst verwendet eine andere Version. Starte ihn nach dem Aktualisieren der Installation neu.',
        "err_prefix": "[Fehler]",
        "err_shell": "Unbekannte Shell: {shell} (bash|zsh)",
        "err_file": "Datei nicht lesbar: {file} ({exc})",
        "err_build_target": (
            "Der Export-Ordner {dir} ist nicht beschreibbar: {exc}. Exporte brauchen "
            "einen beschreibbaren Ordner – schreibgeschützte Mounts und Sandboxes "
            "blockieren Builds; mit --dry-run vorab prüfen."
        ),
        "build_workspace": "Workspace: {root}",
        "build_manuscript": "Manuskript: {file} (Sprache: {language})",
        "state_written": "geschrieben",
        "state_unchanged": "unverändert",
        "build_dry_run": (
            "Dry-Run: {changed} zu schreiben, {unchanged} unverändert – keine Dateien geändert."
        ),
        "build_done": "Fertig: {changed} geschrieben, {unchanged} unverändert.",
        "dashboard_written": "Dashboard geschrieben: {output}",
        "site_export_done": "Website-Lesekopie exportiert. Prüfe die enthaltenen Inhalte vor der Weitergabe.",
        "dashboard_unchanged": "Dashboard unverändert: {output}",
        "pdf_written": "PDF geschrieben: {output}",
        "pdf_unchanged": "PDF unverändert: {output}",
        "speech_written": "Audio geschrieben: {output}",
        "err_no_names": "Keine Figurennamen ausgewählt (--name, --names oder characters in der Projektkonfiguration).",
        "dlg_metric": "Text in Anführungszeichen",
        "dlg_value": "Wert",
        "dlg_turns": "Zitatabschnitte",
        "dlg_dialogue_pct": "Anteil zitierter Wörter",
        "dlg_avg_turn": "Mittlere Zitatlänge (Wörter)",
        "dlg_median_turn": "Mediane Zitatlänge (Wörter)",
        "dlg_longest_turn": "Längster Zitatabschnitt (Wörter)",
        "dlg_turns_per_1000": "Zitatabschnitte je 1.000 Wörter",
        "dlg_paragraph_pct": "Absätze mit zitiertem Text",
        "dlg_chapter": "Kap.",
        "dlg_title": "Titel",
        "chr_name": "Figur",
        "chr_mentions": "Erwähnungen",
        "chr_chapters": "Kapitel mit Nennung",
        "chr_span": "Kapitelspanne",
        "chr_gap": "Interne Lücke",
        "chr_share": "Nennungsanteil",
        "chr_pov": "Deklarierte Perspektivkapitel",
        "pac_metric": "Pacing-Metrik",
        "pac_value": "Wert",
        "pac_chapters": "Kapitel",
        "pac_scenes": "Szenen",
        "pac_avg_scene": "Ø Szene (Wörter)",
        "pac_hook_mean": "Mittlere Zahl der Schlussmerkmale",
        "pac_fastest": "Kapitel mit kürzesten Sätzen (Mittelwert)",
        "pac_slowest": "Kapitel mit längsten Sätzen (Mittelwert)",
        "pac_chapter": "Kap.",
        "pac_title": "Titel",
        "pac_asl": "ASL",
        "pac_dialogue": "Zitierte Wörter",
        "pac_hook": "Haken",
        "pac_no_breaks": (
            "Keine expliziten Szenentrenner gefunden — Szenen = Kapitel "
            "(Szenenstruktur ohne Aussagekraft)."
        ),
        "err_motif_spec": "Ungültiges Motiv (erwartet NAME=REGEX): {spec}",
        "mot_name": "Motiv",
        "mot_mentions": "Treffer",
        "mot_density": "Je 1.000 Wörter",
        "mot_span": "Kapitelspanne",
        "mot_gap": "Größte Lücke",
        "mot_top_words": "Häufigste Inhaltswörter:",
        "mot_phrase": "Wiederholte Phrase",
        "mot_count": "Anzahl",
        "mot_chapters": "Kapitel",
        "show_metric": "Signalgruppen im Vergleich",
        "show_value": "Wert",
        "show_chapters": "Kapitel",
        "show_tell_z": "Wortmuster (Ø z)",
        "show_show_z": "Zitate / kurze Sätze (Ø z)",
        "show_balance": "Differenz (zweite - erste Gruppe)",
        "show_most_telling": "Niedrigste Differenz: Kapitel",
        "show_most_showing": "Höchste Differenz: Kapitel",
        "show_chapter": "Kap.",
        "show_title": "Titel",
    },
}


def _lang() -> str:
    value = os.environ.get("LIXITY_LANG", "en").strip().lower()
    return value if value in CLI_TEXTS else "en"


def _m(key: str, **fmt: object) -> str:
    pack = CLI_TEXTS[_lang()]
    text = pack.get(key) or CLI_TEXTS["en"].get(key, key)
    return text.format(**fmt) if fmt else text


def _completion_scripts() -> tuple[str, str]:
    """Bash and Zsh scripts with live command and research-action lists."""
    from .research.cli import command_metadata

    research_actions = " ".join(name for command in command_metadata()
                                for name in (command["name"], *command.get("aliases", [])))
    names = " ".join(name for name, _help in _COMMANDS)
    descriptors = "\n".join(f"    '{name}:{help_text}'" for name, help_text in _COMMANDS)
    sections = " ".join(_ABOUT_SECTIONS)
    bash = _BASH_COMPLETION.replace("__LIXITY_COMMANDS__", names).replace(
        "__LIXITY_RESEARCH_COMMANDS__", research_actions
    ).replace("__LIXITY_ABOUT_SECTIONS__", sections).replace(
        "__LIXITY_PARAGRAPH_LAYERS__", " ".join(LAYER_FEATURES)
    )
    zsh = _ZSH_COMPLETION.replace("__LIXITY_ZSH_COMMANDS__", descriptors).replace(
        "__LIXITY_RESEARCH_COMMANDS__", research_actions
    ).replace("__LIXITY_ABOUT_SECTIONS__", sections).replace(
        "__LIXITY_PARAGRAPH_LAYERS__", " ".join(LAYER_FEATURES)
    )
    return bash, zsh


#: Top-level commands: name and help text drive the parser and both emitted
#: completion scripts, so adding a command lists it everywhere at once.
_COMMANDS: tuple[tuple[str, str], ...] = (
    ("project", "Inspect project sources, output locations and structural issues without writing"),
    ("research", "Local sources, dossiers, citations and lexical search (JSON)"),
    ("service", "Manage an owned local dashboard process"),
    ("analyze", "Corpus metrics (text/JSON, self-describing meta block)"),
    ("profile", "Paragraph tense/style estimates (JSON; --layer text/JSON)"),
    ("analysis-review", "Review tense observations and save explicit project-local author decisions"),
    ("dialogue", "Recognized quoted passages and word shares (text/JSON)"),
    ("characters", "Curated name mentions and declared POV across chapters (text/JSON)"),
    ("pacing", "Scene structure, pacing and chapter hooks (text/JSON)"),
    ("scenes", "Scene features, register references and author targets (text/JSON)"),
    ("motifs", "Motif tracking, repetition and local phrase echoes (text/JSON)"),
    ("showing", "Compare word-pattern and quotation/short-sentence signals (text/JSON)"),
    ("style", f"Self-calibrated style reference of the manuscript (text/JSON, schema v{SCHEMA_VERSION_STYLE})"),
    ("dashboard", "Generate a single-file HTML dashboard"),
    ("export-site", "Export a static read-only project website"),
    ("pdf", "Compose a PDF for editing, reading, submission or analysis"),
    ("read-aloud", "Create a local listening copy with project voice profiles"),
    ("audio-status", "Inspect audio profiles and worker readiness"),
    ("audio-reference", "Create a private project-local voice reference (JSON)"),
    ("audio-direction", "Inspect and save project-local passage speech direction (JSON)"),
    ("audio-migrate", "Preview or apply explicit backed-up Qwen profile replacements (JSON)"),
    ("serve", "Run local HTTP development server and interactive dashboard"),
    ("build", "Idempotent workspace build of analysis exports and artifact archive"),
    ("doctor", "Inspect installed versions, module location and local service without changing them"),
    ("about", "Installed metadata: commands, configuration, languages, features and heuristics"),
    ("schema", "Installed metadata: commands, configuration, languages, features and heuristics"),
    ("completion", "Shell completion script (bash or zsh)"),
)

_ABOUT_SECTIONS = ("languages", "features", "heuristics", "commands", "configuration")

_BASH_COMPLETION = """# bash completion for lixity – source this file or add it to bash_completion.d/
#   lixity completion bash > /etc/bash_completion.d/lixity   # system
#   lixity completion bash > ~/.local/share/bash-completion/completions/lixity
_lixity_complete() {
    local cur prev
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    local cmds="__LIXITY_COMMANDS__"
    local opts="--help --version --project --language --json --output -o --dry-run --names --motif --phrases --name"
    local style_opts="--z-mild --z-strong --fdr-q --fdr-method --dim-threshold --flag-min-severity --min-chapters"
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$cmds --help --version" -- "$cur") )
        return 0
    fi
    case "${COMP_WORDS[1]}" in
        read-aloud)
            case "$prev" in
                --language) COMPREPLY=( $(compgen -W "zh en ja ko de fr ru pt es it" -- "$cur") ) ;;
                --speech-target) COMPREPLY=( $(compgen -W "local jetson" -- "$cur") ) ;;
                --voice) COMPREPLY=( $(compgen -W "Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee design reference thorsten" -- "$cur") ) ;;
                --engine) COMPREPLY=( $(compgen -W "qwen3 qwen3-design qwen3-base coqui coqui-reference" -- "$cur") ) ;;
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                -o|--output) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --profile|--instructions|--voice-description|--reference-id|--chapter|--preview-line|--speed) ;;
                *)
                    COMPREPLY=( $(compgen -W "--help --project -o --output --chapter --language --profile --engine --instructions --voice --voice-description --reference-id --speed --speech-target --no-audio-cache --fresh-audio --keep-markers --plan-only --no-direction --preview --preview-line --progress" -- "$cur") )
                    COMPREPLY+=( $(compgen -f -- "$cur") )
                    ;;
            esac
            return 0
            ;;
        audio-status)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --engine) COMPREPLY=( $(compgen -W "qwen3 qwen3-design qwen3-base coqui coqui-reference" -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "--help --project --engine --json" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-reference)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --audio|--transcript-file) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                *) COMPREPLY=( $(compgen -W "create --help --project --audio --transcript-file" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-direction)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --input|--manuscript) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --id|--replace-id|--expected-source|--expected-settings|--expected-direction|--chapter|--line|--instruction|--profile-id|--pause-before|--pause-after|--start|--end) ;;
                *) COMPREPLY=( $(compgen -W "inspect add save remove --help --project --manuscript --input --id --replace-id --expected-source --expected-settings --expected-direction --chapter --line --instruction --profile-id --pause-before --pause-after --start --end" -- "$cur") ) ;;
            esac
            return 0
            ;;
        audio-migrate)
            case "$prev" in
                --project) COMPREPLY=( $(compgen -d -- "$cur") ) ;;
                --backup) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                --replace)
                    if [[ $cur == *=* ]]; then
                        local candidate replacement="${cur%%=*}="
                        for candidate in $(compgen -W "Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee" -- "${cur#*=}"); do
                            COMPREPLY+=( "$replacement$candidate" )
                        done
                    fi
                    ;;
                --instructions|--expected-snapshot) ;;
                *) COMPREPLY=( $(compgen -W "--help --project --to-schema-3 --replace --instructions --apply --backup --expected-snapshot" -- "$cur") ) ;;
            esac
            return 0
            ;;
    esac
    case "$prev" in
        service)
            COMPREPLY=( $(compgen -W "start stop restart status" -- "$cur") )
            return 0
            ;;
        research)
            COMPREPLY=( $(compgen -W "__LIXITY_RESEARCH_COMMANDS__" -- "$cur") )
            return 0
            ;;
        --project|--research-project|--research-dir)
            COMPREPLY=( $(compgen -d -- "$cur") )
            return 0
            ;;
        --file|--manuscript)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        --language)
            COMPREPLY=( $(compgen -W "auto de en fr es it pt nl generic" -- "$cur") )
            return 0
            ;;
        --layer)
            if [[ ${COMP_WORDS[1]} == profile ]]; then
                COMPREPLY=( $(compgen -W "__LIXITY_PARAGRAPH_LAYERS__" -- "$cur") )
                return 0
            fi
            ;;
        --section)
            if [[ ${COMP_WORDS[1]} == about || ${COMP_WORDS[1]} == schema ]]; then
                COMPREPLY=( $(compgen -W "__LIXITY_ABOUT_SECTIONS__" -- "$cur") )
                return 0
            fi
            ;;
        --fdr-method)
            COMPREPLY=( $(compgen -W "bh by" -- "$cur") )
            return 0
            ;;
        --backend)
            COMPREPLY=( $(compgen -W "auto process systemd" -- "$cur") )
            return 0
            ;;
        --flag-min-severity)
            COMPREPLY=( $(compgen -W "1 2 3" -- "$cur") )
            return 0
            ;;
        -o|--output)
            COMPREPLY=( $(compgen -f -- "$cur") )
            return 0
            ;;
        completion)
            COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") )
            return 0
            ;;
    esac
    if [[ ${COMP_WORDS[1]} == about || ${COMP_WORDS[1]} == schema ]]; then
        COMPREPLY=( $(compgen -W "--json --section --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == doctor ]]; then
        COMPREPLY=( $(compgen -W "--json --port --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == research ]]; then
        COMPREPLY=( $(compgen -W "--project --file --title --language --actor --source-id --version-id --reason --allow-retention --dry-run --context --thresholds --query --limit --passage --help" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == project ]]; then
        COMPREPLY=( $(compgen -W "--help --project --json" -- "$cur") )
        COMPREPLY+=( $(compgen -d -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == analysis-review ]]; then
        COMPREPLY=( $(compgen -W "--help --project --manuscript --language --tense-model --tense-scope --json --observation --status --expected-source-sha256 --expected-analysis-sha256 --expected-review-sha256" -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == scenes ]]; then
        COMPREPLY=( $(compgen -W "--help --project --language --json --chapter --scene --latest" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == export-site ]]; then
        if [[ $prev == --analysis ]]; then COMPREPLY=( $(compgen -W "chapters language full all" -- "$cur") ); return 0; fi
        COMPREPLY=( $(compgen -W "--help --project --language --json -o --output --include-research --include-source-files --mode --publication-profile --max-chapter --analysis" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    if [[ ${COMP_WORDS[1]} == profile ]]; then
        COMPREPLY=( $(compgen -W "$opts $style_opts --layer --only-notable --evidence" -- "$cur") )
        COMPREPLY+=( $(compgen -f -- "$cur") )
        return 0
    fi
    COMPREPLY=( $(compgen -W "$opts $style_opts" -- "$cur") )
    COMPREPLY+=( $(compgen -f -- "$cur") )
}
complete -F _lixity_complete lixity
"""

_ZSH_COMPLETION = """#compdef lixity
# zsh completion for lixity – place in a directory of $fpath
#   lixity completion zsh > "${fpath[1]}/_lixity"
_lixity_style_flags=(
  '--z-mild[Notable |z*| threshold]:threshold:'
  '--z-strong[Strong |z*| threshold]:threshold:'
  '--fdr-q[FDR q]:q:'
  '--fdr-method[FDR method]:method:(bh by)'
  '--min-chapters[Minimum chapters for baseline]:count:'
  '--dim-threshold[Dimension score threshold]:threshold:'
  '--flag-min-severity[Minimum severity]:severity:(1 2 3)'
)
_lixity() {
  local -a cmds
  cmds=(
__LIXITY_ZSH_COMMANDS__
  )
  _arguments -C \
    '--version[Print version and exit]' \
    '1: :->command' \
    '*:: :->args'
  case $state in
    command)
      _describe -t commands 'lixity command' cmds
      ;;
    args)
      case $words[1] in
        read-aloud)
          _arguments \
            '1:manuscript:_files' \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '-o[Audio WAV or MP3 output]:file:_files' \
            '--output[Audio WAV or MP3 output]:file:_files' \
            '--chapter[Canonical chapter number]:chapter:' \
            '--language[Qwen speech language]:language:(zh en ja ko de fr ru pt es it)' \
            '--profile[Saved narrator profile]:profile:' \
            '--instructions[Explicit Qwen delivery instructions]:text:' \
            '--engine[Speech model variant]:engine:(qwen3 qwen3-design qwen3-base coqui coqui-reference)' \
            '--voice[Speech voice]:voice:(Vivian Serena Uncle_Fu Dylan Eric Ryan Aiden Ono_Anna Sohee design reference thorsten)' \
            '--voice-description[VoiceDesign description]:text:' \
            '--reference-id[Saved project reference]:id:' \
            '--speed[Postprocessing tempo factor]:speed:' \
            '--speech-target[Execution target]:target:(local jetson)' \
            '--plan-only[Inspect the effective speech plan without synthesis]' \
            '--no-direction[Explicitly ignore saved passage direction]' \
            '--preview[Preview the first spoken paragraph]' \
            '--preview-line[Preview paragraph at source line]:line:' \
            '--progress[Report progress to stderr]' \
            '--no-audio-cache[Do not read or retain reusable audio segments]' \
            '--fresh-audio[Recompute completed audio segments]' \
            '--keep-markers[Read editorial markers aloud]'
          ;;
        audio-status)
          _arguments \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--engine[Compare a model variant]:engine:(qwen3 qwen3-design qwen3-base coqui coqui-reference)' \
            '--json[Machine-readable status]'
          ;;
        audio-reference)
          _arguments \
            '1:action:(create)' \
            '--project[Explicit project root]:directory:_files -/' \
            '--audio[Reference WAV]:file:_files' \
            '--transcript-file[Exact UTF-8 transcript]:file:_files'
          ;;
        audio-direction)
          _arguments \
            '1:action:(inspect add save remove)' \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--manuscript[Selected manuscript]:file:_files' \
            '--input[Direction JSON file]:file:_files' \
            '--id[Observed direction ID]:id:' \
            '--replace-id[Original range ID for bounds edits]:id:' \
            '--expected-source[Observed manuscript hash]:sha256:' \
            '--expected-settings[Observed settings hash]:sha256:' \
            '--expected-direction[Observed direction state hash]:sha256:' \
            '--chapter[Chapter number]:number:' \
            '--line[Source line]:number:' \
            '--instruction[Delivery instruction]:text:' \
            '--profile-id[Saved voice profile]:id:' \
            '--pause-before[Pause before in seconds]:seconds:' \
            '--pause-after[Pause after in seconds]:seconds:' \
            '--start[Spoken code-point start offset]:offset:' \
            '--end[Spoken code-point end offset]:offset:'
          ;;
        audio-migrate)
          _arguments \
            '--help[Help]' \
            '--project[Explicit project root]:directory:_files -/' \
            '--to-schema-3[Prepare audio schema upgrade for Coqui]' \
            '*--replace[Explicit PROFILE=VOICE replacement]:profile=preset:' \
            '*--instructions[Explicit PROFILE=TEXT delivery]:profile=text:' \
            '--apply[Apply the reviewed candidate]' \
            '--backup[New backup ZIP outside the project]:file:_files' \
            '--expected-snapshot[Reviewed preview snapshot token]:sha256:'
          ;;
        research)
          _arguments \
            '1:action:(__LIXITY_RESEARCH_COMMANDS__)' \
            '--project[Explicit project root]:directory:_files -/' \
            '--file[UTF-8 source]:file:_files' \
            '--manuscript[Path to manuscript file]:file:_files' \
            '--title[Source or project title]:title:' \
            '--language[Language]:language:(en de fr es it pt nl generic)' \
            '--actor[Local actor]:actor:' \
            '--source-id[Source identifier]:id:' \
            '--version-id[Explicit source version identifier]:id:' \
            '--reason[Reason for action]:reason:' \
            '--allow-retention[Confirm local retention permission]' \
            '--dry-run[Preview without writing]' \
            '--context[Source criticism context JSON file]:file:_files' \
            '--thresholds[Analysis thresholds]:thresholds:' \
            '--query[Literal search words]:query:' \
            '--limit[Maximum hits]:limit:' \
            '--passage[Immutable passage ID]:id:'
          ;;
        completion)
          _values 'shell' bash zsh sh
          ;;
        project)
          _arguments '1:project directory:_files -/' \\
            '--project[Explicit project root]:directory:_files -/' '--json[JSON inspection]' '--help[Help]'
          ;;
        analysis-review)
          _arguments \
            '--project[Explicit project root]:directory:_files -/' \
            '--manuscript[Selected manuscript]:file:_files' \
            '--language[Analysis language]:language:(en de fr es it pt nl generic auto)' \
            '--tense-model[Installed local syntax model]:model:' \
            '--tense-scope[Grammatical tense scope]:scope:(all narration)' \
            '--json[Versioned observations and state]' \
            '--observation[Reviewed observation identity]:sha256:' \
            '--status[Author assertion]:status:(kept changed later)' \
            '--expected-source-sha256[Reviewed manuscript digest]:sha256:' \
            '--expected-analysis-sha256[Reviewed analysis digest]:sha256:' \
            '--expected-review-sha256[Reviewed decision digest]:sha256:' \
            '--help[Help]'
          ;;
        doctor)
          _arguments '--json[JSON diagnostics]' '--port[Service port]:port:' '--help[Help]'
          ;;
        about|schema)
          _arguments '--json[JSON output]' '--help[Help]' \
            '--section[One metadata section as JSON]:section:(__LIXITY_ABOUT_SECTIONS__)'
          ;;
        scenes)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--help[Help]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[Scene JSON with selection scope]' \
            '--chapter[Canonical chapter number]:chapter:' \
            '(--latest)--scene[Exact measured or planned scene ID]:scene:' \
            '(--scene)--latest[Last measured scene in document order]'
          ;;
        profile)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--help[Help]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]' \
            '--layer[Paragraph metric]:layer:(__LIXITY_PARAGRAPH_LAYERS__)' \
            '--only-notable[With a layer, select notable paragraphs after comparison]' \
            '--evidence[With a layer, show exact counted passage evidence]' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
        serve)
          _arguments \
            '1:path:_files' \
            '--host[Bind address]:host:' \
            '--port[Port]:port:' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--title[Dashboard title]:title:' \
            '--open[Open in browser]' \
            '--no-project[Start without preloading a project]' \
            '--research-project[Explicit research project root]:directory:_files -/' \
            "${_lixity_style_flags[@]}"
          ;;
        export-site)
          _arguments \
            '1:manuscript:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--mode[Reading format]:mode:(review reader companion)' \
            '--publication-profile[Root-local reading profile]:name:' \
            '--max-chapter[Omit content after this chapter]:chapter:' \
            '*--analysis[Optional reader analysis]:section:(chapters language full all)' \
            '--include-research[Include authored history and cited excerpts]' \
            '--include-source-files[Also include original source files and full text]' \
            '--json[Print the export manifest]' \
            '--help[Help]' \
            '-o[New website directory]:directory:_files -/' \
            '--output[New website directory]:directory:_files -/'
          ;;
        service)
          _arguments \
            '1:action:(start stop restart status)' \
            '2:project:_files' \
            '--port[Port]:port:' \
            '--host[Loopback host]:host:(127.0.0.1 localhost)' \
            '--no-project[Start an empty workspace]' \
            '--open[Open browser]' \
            '--backend[Runtime backend]:backend:(auto process systemd)' \
            '--json[Machine-readable lifecycle result]' \
            '--language[Language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--title[Project title]:title:' \
            '--research-project[Explicit research root]:directory:_files -/' \
            '--debug[Enable diagnostics]' \
            "${_lixity_style_flags[@]}"
          ;;
        build)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--dry-run[Show planned artifacts only]' \
            "${_lixity_style_flags[@]}"
          ;;
        motifs)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--motif[NAME=REGEX]' \
            '--phrases[Phrase size]:n:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        characters)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--name[Figure name or alias]' \
            '--names[Comma-separated names]:names:' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]'
          ;;
        dashboard)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--names[Character names]:names:' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
        *)
          _arguments \
            '1:file:_files' \
            '--project[Explicit project root]:directory:_files -/' \
            '--language[language profile]:profile:(auto de en fr es it pt nl generic)' \
            '--json[JSON output]' \
            '-o[output file]:file:_files' \
            '--output[output file]:file:_files' \
            "${_lixity_style_flags[@]}"
          ;;
      esac
      ;;
  esac
}
_lixity "$@"
"""


def _meta_payload(language_key: str, **body: Any) -> dict[str, Any]:
    payload = {"meta": {**_META, "language": language_key}}
    payload.update(body)
    return payload


def _print_paragraph_layer(
    report: dict[str, Any], source: str, language_key: str, labels: Mapping[str, str],
    *, paragraphs: list[Any] | None = None,
) -> None:
    """Print measurements and anchors, with literal snippets only when requested."""
    from .format import num, safe_text
    from .style_fingerprint import FEATURE_UNITS, FEATURES, paragraph_layer_projection

    pack = CLI_TEXTS.get(language_key, CLI_TEXTS["en"])

    def message(key: str, **values: object) -> str:
        return pack[key].format(**values)

    feature = report["feature"]
    label_key = next(label for field, label, _unit in FEATURES if field == feature)
    unit = FEATURE_UNITS.get(language_key, {}).get(feature, report["unit"])
    print(f"{labels.get(label_key, feature)} ({unit})")
    print(message("layer_reference"))
    cutoff = num(report["comparison"]["notable_abs_z"], language_key, 2)
    print(message("layer_notable", cutoff=cutoff))
    counts = report["selection"]
    print(message("layer_counts", **counts))
    if counts["selected_count"] == 0:
        print(message("layer_empty"))
        if counts["total_count"] == 0:
            print(message("layer_empty_source"))
        if counts["comparable_count"]:
            print(message("layer_empty_cutoff"))
        if paragraphs:
            rows = paragraph_layer_projection(paragraphs, report["layer"])["paragraphs"]
            chapters: dict[int, list[dict[str, Any]]] = {}
            for row in rows:
                chapters.setdefault(row["chapter_num"], []).append(row)
            reasons = {"layer_short": 0, "layer_constant": 0, "layer_unmeasured": 0}
            for chapter in chapters.values():
                measured = [row for row in chapter if row["value"] is not None]
                if not measured:
                    reasons["layer_unmeasured"] += 1
                elif len(measured) < report["comparison"]["minimum_paragraphs"]:
                    reasons["layer_short"] += 1
                elif not any(row["comparable"] for row in measured):
                    reasons["layer_constant"] += 1
            for reason_key, count in reasons.items():
                if count:
                    print(message(reason_key, count=count))
        from shlex import join

        command = join(["lixity", "profile", source, "--language", language_key,
                        "--layer", report["layer"], "--evidence", "--json"])
        print(message("layer_full", command=safe_text(command)))
    for row in report["paragraphs"]:
        value = "—" if row["value"] is None else num(row["value"], language_key, 2)
        comparison = (
            message("layer_unavailable") if row["z"] is None
            else message("layer_local", z=num(row["z"], language_key, 2, signed=True))
        )
        notable = " · " + message("layer_flag") if row["notable"] is True else ""
        anchor = safe_text(f"{source}:{row['start_line']}-{row['end_line']}")
        title = safe_text(row["chapter_title"])
        print(
            f"{anchor} · {row['chapter_num']}: {title} · "
            f"{value} {unit} · {comparison}{notable}"
        )
        if paragraphs is not None and "evidence" in row:
            evidence = row["evidence"]["layers"][report["layer"]]
            reason = f" · {evidence['reason']}" if evidence.get("reason") else ""
            evidence_unit = message("layer_" + evidence["kind"])
            status_key = {"available": "layer_available", "partial": "layer_partial",
                          "unavailable": "layer_missing"}[evidence["status"]]
            print("  " + message("layer_evidence", status=message(status_key),
                                 mapped=evidence["mapped_count"], count=evidence["count"],
                                 unit=evidence_unit, reason=reason))
            for span in evidence["spans"][:8]:
                snippet = paragraphs[row["index"]].text[span["start"]:span["end"]]
                snippet = snippet[:120] + ("…" if len(snippet) > 120 else "")
                sentence_words = f" · {span['words']} {message('layer_words')}" if "words" in span else ""
                print(f"    [{span['start']}:{span['end']}] x{span['count']}{sentence_words} "
                      f"{safe_text(snippet)}")
            if len(evidence["spans"]) > 8:
                print(f"    … {len(evidence['spans']) - 8} {message('layer_more')}")


def _print_about_json(section: str | None = None) -> None:
    from .api import about

    data = about()
    if section is not None:
        data = {"meta": data["meta"], section: data[section]}
    print(_json(data, indent=True))


def _print_about_text() -> None:
    from .api import about

    data = about()
    print(_m("about_title", version=data["meta"]["version"]))
    print(_m("about_languages", languages=", ".join(data["languages"])))
    print(_m("about_features", count=len(data["features"])))
    for feat in data["features"]:
        print(f"  {feat['field']:<24} [{feat['unit']}]")
    heuristics = data["heuristics"]
    print(
        _m(
            "about_heuristics",
            z_mild=heuristics["z_mild"],
            z_strong=heuristics["z_strong"],
            fdr_q=heuristics["fdr_q"],
            min_chapters=heuristics["min_chapters"],
            n_dimensions=heuristics["n_dimensions"],
            min_comparable_words=heuristics["min_comparable_words"],
            min_comparable_sentences=heuristics["min_comparable_sentences"],
        )
    )
    if data.get("commands"):
        print(_m("about_commands"))
        for command in data["commands"]:
            print(f"  {command['name']:<12} {command['purpose']} [{command['output']}]")
    print(_m("about_license", license=data["license"]))


def _cmd_dialogue(args: argparse.Namespace) -> int:
    """Dialogue turn structure as a Rich table or JSON."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .dialogue import dialogue_report

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = dialogue_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, dialogue=report.to_dict()), indent=True))
        return EXIT_OK

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("dlg_metric"), style="bold white")
    summary.add_column(_m("dlg_value"), justify="right", style="cyan")
    for key, value in (
        ("dlg_turns", str(report.turns)),
        ("dlg_dialogue_pct", f"{report.dialogue_pct:.1f} %"),
        ("dlg_avg_turn", f"{report.avg_turn_words:.1f}"),
        ("dlg_median_turn", f"{report.median_turn_words:.0f}"),
        ("dlg_longest_turn", str(report.longest_turn_words)),
        ("dlg_turns_per_1000", f"{report.turns_per_1000:.1f}"),
        ("dlg_paragraph_pct", f"{report.dialogue_paragraph_pct:.1f} %"),
    ):
        summary.add_row(_m(key), value)
    con.print(summary)

    if report.chapters:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("dlg_chapter"), justify="right")
        table.add_column(_m("dlg_title"))
        table.add_column(_m("dlg_turns"), justify="right")
        table.add_column(_m("dlg_dialogue_pct"), justify="right")
        table.add_column(_m("dlg_avg_turn"), justify="right")
        table.add_column(_m("dlg_longest_turn"), justify="right")
        for chapter in report.chapters:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                str(chapter.turns),
                f"{chapter.dialogue_pct:.1f} %",
                f"{chapter.avg_turn_words:.1f}",
                str(chapter.longest_turn_words),
            )
        con.print(table)
    return EXIT_OK


def _cmd_characters(args: argparse.Namespace) -> int:
    """Curated name mentions and declared POV as a Rich table or JSON."""
    from .characters import presence_report, resolve_character_settings

    names: list[str] = list(args.name or [])
    if args.names is not None:
        names.extend(part.strip() for part in args.names.split(",") if part.strip())
    try:
        selection = resolve_character_settings(
            names if args.name or args.names is not None else None, args._project_config)
        if not selection.names:
            print(f"{_m('err_prefix')} {_m('err_no_names')}", file=sys.stderr)
            return EXIT_ERROR
        with open(args.file, encoding="utf-8") as f:
            text = f.read()
        config, resolved = resolve_document_config(text, args.language, project_config=args._project_config)
        report = presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
    except (OSError, UnicodeError) as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(_json(_meta_payload(resolved.key, **report), indent=True))
        return EXIT_OK

    con = Console()
    table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    table.add_column(_m("chr_name"), style="bold white")
    table.add_column(_m("chr_mentions"), justify="right", style="cyan")
    table.add_column(_m("chr_chapters"), justify="right")
    table.add_column(_m("chr_span"))
    table.add_column(_m("chr_gap"), justify="right")
    table.add_column(_m("chr_share"), justify="right")
    if selection.declared_pov:
        table.add_column(_m("chr_pov"))
    for figure in report["figures"]:
        span = (
            f"{figure['first_chapter']}–{figure['last_chapter']}"
            if figure["first_chapter"]
            else "–"
        )
        row = [
            figure["name"],
            str(figure["mentions"]),
            f"{len(figure['chapters_present'])} / {report['chapters']}",
            span,
            str(figure["longest_gap"]),
            f"{figure['presence_ratio'] * 100:.0f} %",
        ]
        if selection.declared_pov:
            row.append(", ".join(str(number) for number in figure.get("declared_pov_chapters", [])) or "–")
        table.add_row(*row)
    con.print(table)
    return EXIT_OK


def _cmd_pacing(args: argparse.Namespace) -> int:
    """Scene structure, pacing signals and chapter hooks (Rich table or JSON)."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .pacing import pacing_report

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = pacing_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, pacing=report.to_dict()), indent=True))
        return EXIT_OK

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("pac_metric"), style="bold white")
    summary.add_column(_m("pac_value"), justify="right", style="cyan")
    for key, value in (
        ("pac_chapters", str(report.chapters)),
        ("pac_scenes", str(report.scenes)),
        ("pac_avg_scene", f"{report.avg_scene_words:.0f}"),
        ("pac_hook_mean", f"{report.hook_score_mean:.2f}"),
        ("pac_fastest", str(report.fastest_chapter or "–")),
        ("pac_slowest", str(report.slowest_chapter or "–")),
    ):
        summary.add_row(_m(key), value)
    con.print(summary)
    if report.scenes_are_chapters and report.chapters:
        con.print(f"[yellow]{_m('pac_no_breaks')}[/yellow]")

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("pac_chapter"), justify="right")
        table.add_column(_m("pac_title"))
        table.add_column(_m("pac_scenes"), justify="right")
        table.add_column(_m("pac_asl"), justify="right")
        table.add_column(_m("pac_dialogue"), justify="right")
        table.add_column(_m("pac_hook"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                str(chapter.scenes),
                f"{chapter.asl:.1f}",
                f"{chapter.dialogue_pct:.1f} %",
                str(chapter.hook_score),
            )
        con.print(table)
    return EXIT_OK


def _cmd_motifs(args: argparse.Namespace) -> int:
    """Motif presence and repetition signals (Rich tables or JSON)."""
    motifs: dict[str, str] = {}
    for spec in args.motif or []:
        name, separator, pattern = spec.partition("=")
        if not separator or not name.strip() or not pattern.strip():
            print(f"{_m('err_prefix')} {_m('err_motif_spec', spec=spec)}", file=sys.stderr)
            return EXIT_ERROR
        motifs[name.strip()] = pattern.strip()
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .motifs import motif_report

    try:
        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config,
            **({"motif_regexes": motifs} if args.motif else {}),
        )
        report = motif_report(text, motifs if args.motif else None, config, phrase_size=max(2, args.phrases))
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(_json(_meta_payload(resolved.key, **report.to_dict()), indent=True))
        return EXIT_OK

    con = Console()
    if report.motifs:
        table = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
        table.add_column(_m("mot_name"), style="bold white")
        table.add_column(_m("mot_mentions"), justify="right", style="cyan")
        table.add_column(_m("mot_density"), justify="right")
        table.add_column(_m("mot_span"))
        table.add_column(_m("mot_gap"), justify="right")
        for motif in report.motifs:
            span = f"{motif.first_chapter}–{motif.last_chapter}" if motif.first_chapter else "–"
            table.add_row(
                motif.name,
                str(motif.mentions),
                f"{motif.density_per_1000:.2f}",
                span,
                str(motif.longest_gap),
            )
        con.print(table)

    if report.top_words:
        words = ", ".join(f"{word} ({count})" for word, count in report.top_words)
        con.print(f"[bold]{_m('mot_top_words')}[/bold] {words}")

    from .language_data import UI_LABELS

    labels = UI_LABELS[_lang()]
    if report.repeated_phrases:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("mot_phrase"))
        table.add_column(labels["mot_global_count"], justify="right")
        table.add_column(_m("mot_chapters"))
        for phrase in report.repeated_phrases:
            table.add_row(phrase.phrase, str(phrase.count), ", ".join(map(str, phrase.chapters)))
        con.print(table)

    if report.echoes:
        con.print(f"[bold]{labels['mot_echoes']}[/bold]")
        con.print(labels["mot_echo_note"])
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("mot_phrase"))
        table.add_column(labels["mot_echo_chapter"], justify="right")
        table.add_column(labels["mot_echo_count"], justify="right")
        table.add_column(labels["mot_echo_words"], justify="right")
        for echo in report.echoes:
            table.add_row(echo.term, str(echo.chapter), str(echo.count),
                          f"{echo.first_word}–{echo.last_word}")
        con.print(table)
        con.print(labels["mot_echo_limits"])
    return EXIT_OK


def _cmd_showing(args: argparse.Namespace) -> int:
    """Compare measured cue groups (Rich table or stable showing JSON)."""
    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    from .showing import showing_report

    config, resolved = resolve_document_config(
        text, args.language, project_config=args._project_config
    )
    report = showing_report(text, config)

    if args.json:
        print(_json(_meta_payload(resolved.key, showing=report.to_dict()), indent=True))
        return EXIT_OK

    def signed(value: "float | None") -> str:
        # Below the comparability floor no z-score is derived; keep it visible.
        return "–" if value is None else f"{value:+.2f}"

    con = Console()
    summary = Table(box=box.SIMPLE_HEAVY, header_style="bold cyan")
    summary.add_column(_m("show_metric"), style="bold white")
    summary.add_column(_m("show_value"), justify="right", style="cyan")
    for key, value in (
        ("show_chapters", str(report.chapters)),
        ("show_tell_z", signed(report.tell_z_mean)),
        ("show_show_z", signed(report.show_z_mean)),
        ("show_balance", signed(report.balance_mean)),
        ("show_most_telling", ", ".join(map(str, report.most_telling))),
        ("show_most_showing", ", ".join(map(str, report.most_showing))),
    ):
        summary.add_row(_m(key), value)
    con.print(summary)

    if report.chapter_list:
        table = Table(box=box.SIMPLE, header_style="bold green")
        table.add_column(_m("show_chapter"), justify="right")
        table.add_column(_m("show_title"))
        table.add_column(_m("show_tell_z"), justify="right")
        table.add_column(_m("show_show_z"), justify="right")
        table.add_column(_m("show_balance"), justify="right")
        for chapter in report.chapter_list:
            table.add_row(
                str(chapter.chapter_num),
                chapter.title,
                signed(chapter.tell_z),
                signed(chapter.show_z),
                signed(chapter.balance),
            )
        con.print(table)
    return EXIT_OK


def _cmd_pdf(args: argparse.Namespace) -> int:
    """Compose one of the PDF layouts from the manuscript or the analysis."""
    from .pdf_document import PdfError
    from .pdf_export import compose_pdf
    from .pdf_layouts import FontChoice

    workspace = args._workspace
    output = args.output or os.path.join(workspace.root, f"{workspace.slug}-{args.layout}.pdf")
    try:
        FileUtils.require_distinct_output(workspace.manuscript, output)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    choice = FontChoice(
        serif=args.serif_font,
        serif_bold=args.bold_font,
        mono=args.mono_font,
        sans=args.sans_font,
        sans_bold=args.sans_bold_font,
        serif_italic=args.italic_font,
        serif_bold_italic=args.bold_italic_font,
    )
    try:
        text = workspace.read_manuscript()
        thresholds = (
            _thresholds_from_args(args, getattr(args, "_project_config", None))
            if args.layout == "report"
            else None
        )
        payload = compose_pdf(
            text,
            manuscript=workspace.manuscript,
            layout=args.layout,
            language=args.language,
            project_config=args._project_config,
            title=args.title,
            author=args.author,
            draft_notice=args.draft_notice,
            thresholds=thresholds,
            choice=choice,
        )
    except (OSError, PdfError, ValueError, RuntimeError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    try:
        changed = FileUtils.atomic_write_bytes_if_changed(
            output, payload,
            before_replace=lambda: FileUtils.require_distinct_output(workspace.manuscript, output),
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(_m("pdf_written" if changed else "pdf_unchanged", output=output))
    return EXIT_OK


def _cmd_read_aloud(args: argparse.Namespace) -> int:
    """Create a local manuscript listening copy with a validated project profile."""
    import warnings

    from .speech import render_speech_audio
    from .speech_cache import project_audio_cache
    from .speech_profiles import AudioProfile, parse_audio_settings, resolve_audio_profile
    from .speech_references import SpeechReference, references_for_plan, references_unchanged

    workspace = args._workspace
    preview = args.preview or args.preview_line is not None
    output = args.output or os.path.join(
        workspace.root,
        f"{workspace.slug}-preview.wav" if preview else
        f"{workspace.slug}-chapter-{args.chapter}.wav" if args.chapter is not None else f"{workspace.slug}.wav",
    )
    try:
        FileUtils.require_distinct_output(workspace.manuscript, output)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        profile = resolve_audio_profile(args._project_config, args.profile, language=args.language)
        changes = profile.model_dump()
        for name, value in (("engine", args.engine),
                            ("voice", args.voice),
                            ("voice_description", args.voice_description),
                            ("reference_id", args.reference_id),
                            ("instructions", args.instructions),
                            ("speed", args.speed),
                            ("language", getattr(args, "_speech_explicit_language", None))):
            if value is not None:
                changes[name] = value
        if args.engine == "qwen3-design" and args.voice is None and profile.engine != "qwen3-design":
            changes["voice"] = "design"
        if args.engine == "qwen3-base" and args.voice is None and profile.engine != "qwen3-base":
            changes["voice"] = "reference"
        if args.engine in ("coqui", "coqui-reference") and args.voice is None:
            changes["voice"] = "reference" if args.engine == "coqui-reference" else "thorsten"
        if args.engine in ("qwen3", "qwen3-base", "coqui", "coqui-reference") and profile.engine == "qwen3-design" and args.voice_description is None:
            changes.pop("voice_description", None)
        if args.engine in ("qwen3", "qwen3-design", "coqui") and profile.engine in ("qwen3-base", "coqui-reference") and args.reference_id is None:
            changes.pop("reference_id", None)
        if changes["engine"] not in ("qwen3-base", "coqui-reference") and args.reference_id:
            raise ValueError(_m("audio_reference_wrong_engine"))
        if changes["engine"] in ("qwen3-base", "coqui-reference"):
            if not changes.get("reference_id"):
                raise ValueError(_m("audio_base_reference_required"))
            if changes.get("instructions"):
                raise ValueError(_m("audio_base_instructions_inherited" if args.instructions is None
                                    else "audio_base_instructions_explicit"))
        if changes["engine"] == "qwen3-design" and not changes.get("voice_description"):
            raise ValueError(_m("audio_design_description_required"))
        if args.engine == "qwen3" and profile.engine != "qwen3" and args.voice is None:
            raise ValueError(_m("audio_custom_voice_required"))
        profile = AudioProfile.model_validate(changes)
        from .speech_direction import (
            build_speech_plan,
            direction_snapshot,
            direction_state,
            plan_json,
            saved_directions,
        )
        text, source_hash = FileUtils.read_source_snapshot(workspace.manuscript)
        view = None if args.no_direction else direction_state(workspace.root, workspace.manuscript, language=profile.language)
        if view is not None and view["source_sha256"] != source_hash:
            raise ValueError("Manuscript changed while preparing speech; retry")
        direction_hash = view["direction_sha256"] if view is not None else None
        references: dict[str, SpeechReference] = {}

        def check_context() -> bool:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", UserWarning)
                    use_explicit, start = args._speech_config_selection
                    current_settings = (read_explicit_project_config(start) if use_explicit
                                        else load_project_config(start))
                valid = (FileUtils.read_source_snapshot(workspace.manuscript)[1] == source_hash
                         and current_settings == args._project_config
                         and (direction_hash is None or direction_snapshot(workspace.root) == direction_hash)
                         and references_unchanged(workspace.root, references))
            except (OSError, ValueError, UserWarning) as exc:
                raise ValueError("Manuscript, settings or speech directions changed or became unreadable; retry") from exc
            if not valid:
                raise ValueError("Manuscript, settings or speech directions changed during rendering; retry")
            return False

        check_context()
        profiles = parse_audio_settings(args._project_config.get("audio"), language=profile.language).profiles
        if args.speed is not None:
            profiles = {key: AudioProfile.model_validate({**item.model_dump(), "speed": args.speed})
                        for key, item in profiles.items()}
        plan = build_speech_plan(text, profile,
            directions=saved_directions(view) if view is not None else [], profiles=profiles,
            chapter=args.chapter, project_config=args._project_config, skip_markers=not args.keep_markers)
        if preview:
            anchors = [row.anchor for row in plan if row.text and row.anchor]
            selected = next((anchor for anchor in anchors if args.preview_line is None or
                             anchor["start_line"] <= args.preview_line <= anchor["end_line"]), None)
            if selected is None:
                raise ValueError("No anchored paragraph or list item found at the selected line or chapter; quote blocks cannot currently be selected for preview")
            plan = [row for row in plan if row.anchor == selected]
            if sum(len(row.text) for row in plan) > 6000:
                raise ValueError("Passage preview exceeds 6000 characters; render the chapter")
        references = references_for_plan(workspace.root, plan)
        if args.plan_only:
            check_context()
            print(_json(plan_json(plan), indent=True))
            return EXIT_OK
        render_options: dict[str, Any] = {"references": references} if references else {}
        out_path = render_speech_audio(
            manuscript_path=workspace.manuscript,
            output_path=output,
            language=profile.language,
            chapter=args.chapter,
            profile=profile,
            skip_markers=not args.keep_markers,
            cache_dir=project_audio_cache(workspace.root) if not args.no_audio_cache and not preview else None,
            fresh_audio=args.fresh_audio,
            target=args.speech_target,
            plan=plan,
            cancelled=check_context,
            progress=_audio_progress() if args.progress else None,
            **render_options,
        )
    except (OSError, ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(_m("speech_written", output=str(out_path)))
    return EXIT_OK


def _cmd_build(args: argparse.Namespace) -> int:
    """Idempotent workspace build: analyzes the manuscript and publishes artifacts."""
    from .motifs import motif_report

    workspace = args._workspace

    try:
        text = workspace.read_manuscript()
        title = _document_title(args, workspace.manuscript, text)
        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics
    paragraphs, chapters = analysis.paragraphs, analysis.chapters
    fingerprint = analysis.fingerprint

    artifacts = {
        f"{workspace.slug}_metrics.json": _json(
            _meta_payload(resolved.key, metrics=metrics.model_dump()),
            indent=True,
        )
        + "\n",
        f"{workspace.slug}_profile.json": _json(
            _meta_payload(
                resolved.key,
                chapters=[c.__dict__ for c in chapters],
                paragraphs=[
                    {k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs
                ],
            ),
            indent=True,
        )
        + "\n",
        f"{workspace.slug}_style.json": _json(fingerprint.passport(), indent=True) + "\n",
        f"{workspace.slug}_style_passport.txt": fingerprint.passport_text(
            labels=resolved.labels, language_key=resolved.key
        )
        + "\n",
        f"{workspace.slug}_report.md": ReportFormatter.format_markdown_report(
            metrics, labels=resolved.labels, language_key=resolved.key
        ),
        f"{workspace.slug}_dashboard.html": render_analysis(
            analysis,
            resolved,
            reader_document=reader_blocks(text, config, analysis.paragraphs),
            title=title,
            flag_min_severity=fp_thresholds.flag_min_severity,
            motifs=motif_report(text, config=config).to_dict(),
            scenes=scene_report_for_display(
                text,
                config,
                args._project_config.get("scene_analysis"),
                premeasured_chapters=metrics.chapters,
            ),
        ),
    }

    print(_m("build_workspace", root=workspace.root))
    print(
        _m(
            "build_manuscript",
            file=os.path.basename(workspace.manuscript),
            language=resolved.key,
        )
    )
    if not args.dry_run:
        try:
            workspace.ensure_layout()
        except OSError as exc:
            print(
                f"{_m('err_prefix')} {_m('err_build_target', dir=workspace.exports_dir, exc=exc)}",
                file=sys.stderr,
            )
            return EXIT_ERROR
    changed = 0
    for name, content in artifacts.items():
        try:
            is_changed = workspace.publish(name, content, dry_run=args.dry_run)
        except OSError as exc:
            print(
                f"{_m('err_prefix')} {_m('err_build_target', dir=workspace.exports_dir, exc=exc)}",
                file=sys.stderr,
            )
            return EXIT_ERROR
        changed += is_changed
        prefix = "(dry-run) " if args.dry_run else ""
        state = _m("state_written") if is_changed else _m("state_unchanged")
        print(f"  {prefix}{state:<13} exports/{name}")
    unchanged = len(artifacts) - changed
    if args.dry_run:
        print(_m("build_dry_run", changed=changed, unchanged=unchanged))
    else:
        print(_m("build_done", changed=changed, unchanged=unchanged))
    return EXIT_OK


def _cmd_project(args: argparse.Namespace) -> int:
    """Print the same bounded, metadata-only observation used by the native UI."""
    from .format import safe_text
    from .project_structure import inspect_project
    from .workspace_labels import (
        PROJECT_STRUCTURE_ISSUE_LABELS,
        PROJECT_STRUCTURE_ROLE_LABELS,
        PROJECT_STRUCTURE_STATE_LABELS,
        WORKSPACE_LABELS,
    )

    try:
        result = inspect_project(getattr(args, "project_path", "."))
    except (OSError, ValueError, RuntimeError) as exc:
        print(safe_text(f"{_m('err_prefix')} {exc}"), file=sys.stderr)
        return EXIT_ERROR
    if args.json:
        print(_json(result, indent=True))
    else:
        labels = WORKSPACE_LABELS[_lang()]
        def text(key: str) -> str:
            return labels.get(key, key)
        print(text("project_structure_title"))
        print(safe_text(result["root"]))
        for role in result["roles"]:
            name = text(PROJECT_STRUCTURE_ROLE_LABELS[role["role"]])
            state = text(PROJECT_STRUCTURE_STATE_LABELS[role["state"]])
            print(safe_text(f"{name}: {role['path'] or '—'} · {state}"))
        if result["artifacts"]:
            print("\n" + text("project_structure_outputs"))
            for artifact in result["artifacts"]:
                print(safe_text(f"  {artifact['path']} · " + text("project_structure_provenance_unknown")))
        for issue in result["issues"]:
            message = text(PROJECT_STRUCTURE_ISSUE_LABELS[issue["code"]])
            path = f" · {issue['path']}" if issue["path"] is not None else ""
            severity = text("project_structure_issue_" + issue["severity"])
            print(safe_text(f"[{severity}] {message}{path}"))
    return EXIT_ERROR if result["has_errors"] else EXIT_OK


def _positive_chapter(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("Chapter must be a positive number")
    return value


def _scene_identifier(raw: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", raw):
        raise argparse.ArgumentTypeError("Scene must be a chapter:scene ID, for example 1:2")
    return raw


def _select_scenes(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Select output after validation, retaining full-manuscript comparisons."""
    if args.chapter is None and args.scene is None and not args.latest:
        return report
    if args.chapter is not None and args.scene is not None and int(args.scene.split(":")[0]) != args.chapter:
        raise ValueError("--chapter must match the chapter in --scene")

    def matches(item: dict[str, Any]) -> bool:
        return ((args.chapter is None or item["chapter"] == args.chapter)
                and (args.scene is None or item["id"] == args.scene))

    items = [item for item in report["items"] if matches(item)]
    planned = [item for item in report.get("planned_items", []) if matches(item)]
    if args.latest:
        items = items[-1:]
        planned = []
    if not items and not planned:
        kind = "measured scene" if args.latest else "measured or planned scene"
        raise ValueError(f"No {kind} matches the requested selection; use the chapter:scene IDs from scenes")
    selection = {
        "chapter": args.chapter, "scene": args.scene, "latest": args.latest,
        "selected_count": len(items), "total_count": len(report["items"]),
        "reference_scope": "full_manuscript",
    }
    selected = {**report, "items": items, "selection": selection}
    if "planned_items" in report:
        selected["planned_items"] = planned
        selection.update(selected_planned_count=len(planned), total_planned_count=len(report["planned_items"]))
    return selected


def _threshold_number(key: str) -> Callable[[str], float]:
    def parse(raw: str) -> float:
        try:
            value = float(raw)
            FingerprintThresholds.numeric_inputs[key].validate(key, value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc
        return value

    return parse


def _add_threshold_arguments(parser: argparse.ArgumentParser) -> None:
    """Use the backend's defaults and bounds for CLI help and scalar validation."""
    defaults = FingerprintThresholds()
    for key, flag, description in (
        ("z_mild", "--z-mild", "Notable |z*| threshold"),
        ("z_strong", "--z-strong", "Strong |z*| threshold"),
        ("fdr_q", "--fdr-q", "Nominal q for the selected FDR method"),
        ("dim_score_threshold", "--dim-threshold", "Per-axis |score| cutoff in standardized midrank PCA space"),
    ):
        policy = FingerprintThresholds.numeric_inputs[key]
        bounds = f"{'>' if policy.minimum_exclusive else '>='} {policy.minimum:g}"
        if policy.maximum is not None:
            bounds += f" and {'<' if policy.maximum_exclusive else '<='} {policy.maximum:g}"
        parser.add_argument(
            flag, type=_threshold_number(key), default=None,
            help=f"{description}; finite, {bounds} (default: {getattr(defaults, key)})",
        )
    parser.add_argument(
        "--fdr-method", choices=FingerprintThresholds.fdr_methods, default=None,
        help=f"FDR method: bh (Benjamini-Hochberg) or by (Benjamini-Yekutieli); default: {defaults.fdr_method}",
    )
    parser.add_argument(
        "--flag-min-severity", type=int, choices=FingerprintThresholds.flag_severities, default=None,
        help=f"Minimum paragraph severity for flags panel (default: {defaults.flag_min_severity})",
    )


def _run_text_report(args: argparse.Namespace, render: Callable[[], int]) -> int:
    """Write successful report data atomically, leaving diagnostics on stderr."""
    output = getattr(args, "output", None)
    try:
        if output is None:
            return render()
        FileUtils.require_distinct_output(args.file, output)
        with StringIO() as captured, redirect_stdout(captured):
            status = render()
            content = captured.getvalue()
        if status != EXIT_OK:
            return status
        FileUtils.atomic_write_if_changed(
            output, content,
            before_replace=lambda: FileUtils.require_distinct_output(args.file, output),
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def _cmd_analysis_report(
    args: argparse.Namespace, text: str, config: CorpusConfig, resolved: ResolvedLanguage,
) -> int:
    """Render the shared document analysis reports without choosing a destination."""
    if args.command == "scenes":
        from .api import scenes

        try:
            report = scenes(text, resolved.key, project_config=args._project_config)
            report["scenes"] = _select_scenes(report["scenes"], args)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(report, indent=True))
        else:
            from .diversity import MIN_TOKENS_LD
            from .format import num, safe_text
            from .style_fingerprint import FEATURE_UNITS, FEATURES

            labels = resolved.labels
            units = FEATURE_UNITS.get(resolved.key, {})

            for item in report["scenes"]["items"]:
                group = item["group"] or labels["scene_unassigned"]
                print(safe_text(f"{item['id']} · {item['chapter_title']} · {group}"))
                print(
                    f"  {num(item['words'], resolved.key, 0)} {labels['words']} · "
                    f"{num(item['sentences'], resolved.key, 0)} {labels['sentences']}"
                )
                for field, label_key, unit in FEATURES:
                    value = item["features"][field]
                    target = item["targets"].get(field)
                    detail = ""
                    if target:
                        lower = (
                            "…"
                            if target["lower"] is None
                            else num(target["lower"], resolved.key, 2)
                        )
                        upper = (
                            "…"
                            if target["upper"] is None
                            else num(target["upper"], resolved.key, 2)
                        )
                        detail = f" · {labels['scene_' + target['position']]} [{lower} – {upper}]"
                    rendered = "—" if value is None else num(value, resolved.key, 2)
                    print(
                        f"  {labels.get(label_key, field)}: {rendered} {units.get(field, unit)}{detail}"
                    )
            planned_items = report["scenes"].get("planned_items", [])
            if planned_items:
                print(labels["scene_planned"])
                for item in planned_items:
                    print(safe_text(f"  {item['id']} · {item['group']}"))
                print(labels["scene_planned_note"])
            print(labels["scene_guidance"])
            print(labels["scene_support"].replace("{min_tokens}", str(MIN_TOKENS_LD)))
        return EXIT_OK

    if args.command == "analyze":
        metrics = CorpusAnalyzer(config, sample_text=text).analyze_text(text)
        if args.json:
            payload = _meta_payload(resolved.key, metrics=metrics.model_dump())
            print(_json(payload))
        else:
            ReportFormatter.print_rich_report(metrics, language_key=resolved.key)
        return EXIT_OK

    if args.command == "profile":
        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        evidence: dict[int, ParagraphEvidence] | None = {} if args.evidence else None
        paragraphs, chapters = profile_document(text, config, fp_thresholds, evidence=evidence)
        if args.layer is not None:
            payload = _meta_payload(
                resolved.key,
                **paragraph_layer_projection(paragraphs, args.layer, only_notable=args.only_notable),
            )
            payload["meta"]["schema_version"] = "paragraph-layer/1"
            if evidence is not None:
                payload["meta"]["schema_version"] = "paragraph-layer-evidence/1"
                for row in payload["paragraphs"]:
                    row["evidence"] = evidence[row["index"]]
            if args.json:
                print(_json(payload, indent=True))
            else:
                _print_paragraph_layer(payload, args.file, resolved.key, resolved.labels,
                                       paragraphs=paragraphs)
            return EXIT_OK
        payload = _meta_payload(
            resolved.key,
            chapters=[c.__dict__ for c in chapters],
            paragraphs=[{k: v for k, v in p.__dict__.items() if k != "text"} for p in paragraphs],
        )
        print(_json(payload, indent=True))
        return EXIT_OK

    if args.command == "style":
        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        fingerprint = fingerprint_document(text, config, fp_thresholds)
        if args.json:
            print(_json(fingerprint.passport(), indent=True))
        else:
            print(fingerprint.passport_text(labels=resolved.labels, language_key=resolved.key))
        return EXIT_OK

    raise ValueError("Unknown textual analysis report")


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lixity",
        description=(
            "Lixity – quantitative text linguistics, stylometry, self-calibrating "
            "style references and single-file dashboards for literary manuscripts."
        ),
        epilog=(
            "Open the local app:  lixity service start --open\n"
            "Read a report:      lixity analyze manuscript.md --language en\n"
            "Inspect commands:   lixity COMMAND --help  |  lixity about --json\n"
            f"Docs: {docs_url()}  ·  "
            "Report language: LIXITY_LANG=de"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"lixity {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    from .research.cli import configure as configure_research
    from .service import configure as configure_service

    for name, help_text in _COMMANDS:
        if name == "research":
            configure_research(sub.add_parser(name, help=help_text))
            continue
        if name == "service":
            configure_service(sub.add_parser(name, help=help_text))
            continue
        p = sub.add_parser(name, help=help_text, description=help_text)
        if name == "audio-status":
            p.add_argument("--project", help="Explicit project root; omit to inspect workers only")
            p.add_argument("--engine", choices=("qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference"), help="Compare this model variant instead of the selected profile")
            p.add_argument("--json", action="store_true", help="Machine-readable status")
            continue
        if name == "audio-reference":
            p.add_argument("action", choices=("create",))
            p.add_argument("--project", required=True, help="Explicit existing project root")
            p.add_argument("--audio", required=True, help="Reference WAV, 1–30 seconds, mono PCM 24 kHz")
            p.add_argument("--transcript-file", required=True, help="Exact UTF-8 transcript of the reference WAV")
            continue
        if name == "audio-direction":
            from .speech_direction_cli import configure
            p.epilog = _m("audio_direction_help")
            configure(p)
            continue
        if name == "audio-migrate":
            p.add_argument("--project", required=True, help="Explicit project root")
            p.add_argument("--to-schema-3", action="store_true", help="Prepare a backed-up upgrade for Coqui profiles")
            p.add_argument("--replace", action="append", default=[], metavar="PROFILE=VOICE",
                           help="Explicit Qwen preset for each removed engine profile; repeat for multiple profiles")
            p.add_argument("--instructions", action="append", default=[], metavar="PROFILE=TEXT",
                           help="Explicit delivery instructions for a replaced profile")
            p.add_argument("--apply", action="store_true", help="Apply the reviewed candidate; default only previews")
            p.add_argument("--backup", help="New backup ZIP outside the project; required with --apply")
            p.add_argument("--expected-snapshot", help="Snapshot token from the reviewed preview; required with --apply")
            continue
        if name == "analysis-review":
            p.add_argument("--project", required=True, help="Explicit project root")
            p.add_argument("--manuscript", help="Manuscript within project (default: configured manuscript)")
            p.add_argument("--language", default=None, help="Explicit analysis language; default: project setting or en")
            p.add_argument("--tense-model", default=None, help="Explicit installed local syntax model; no download or fallback")
            p.add_argument("--tense-scope", choices=("all", "narration"), default=None,
                           help="Grammatical tense scope: all predicates or outside recognized quotations")
            p.add_argument("--json", action="store_true", help="Complete versioned observation and review identities")
            p.add_argument("--observation", help="Exact observation ID from a current read")
            p.add_argument("--status", choices=("kept", "changed", "later"), help="Your decision, never a verified text edit")
            for name_part in ("source", "analysis", "review"):
                p.add_argument("--expected-" + name_part + "-sha256", help="Reviewed exact identity required for saving")
            p.epilog = ("Reads write nothing. To save, supply --observation, --status and all three reviewed "
                        "--expected-*-sha256 values. Decisions live in .lixity/analysis-review.json, not manuscript prose. "
                        "Changed text or analysis makes prior decisions stale; deferred items stay open.")
            continue
        if name == "project":
            selector = p.add_mutually_exclusive_group()
            selector.add_argument("project_path", nargs="?", default=argparse.SUPPRESS,
                                  help="Explicit project folder (default: current directory)")
            selector.add_argument("--project", dest="project_path", default=argparse.SUPPRESS,
                                  metavar="PATH", help="Explicit project folder (same as positional)")
            p.add_argument("--json", action="store_true", help="Metadata observation and structural findings as JSON")
            p.epilog = ("Reads only the selected root and bounded export metadata. No files are moved, "
                        "created or repaired; research integrity and output freshness are not inferred. "
                        "Exit 1 indicates structural errors or an unavailable project. "
                        "Example: lixity project --project ./novel --json")
            continue
        if name == "doctor":
            p.add_argument("--json", action="store_true", help="Machine-readable installation diagnostics")
            p.add_argument("--port", type=int, default=None, help=f"Service port (default: LIXITY_PORT or {DEFAULT_PORT})")
            continue
        if name == "export-site":
            from .site_contracts import SITE_MODES

            p.add_argument("file", nargs="?", help="Manuscript inside the selected project (default: project manuscript)")
            p.add_argument("--project", required=True, metavar="PATH", help="Explicit project root")
            p.add_argument("-o", "--output", help="A new directory for the reading website; existing paths are never overwritten")
            p.add_argument("--preflight", action="store_true", help="Measure the prepared package without writing it; omit --output")
            p.add_argument("--language", default=None, help="Analysis language (default: project language or en)")
            p.add_argument("--include-research", action="store_true", help="Include authored research, revision history, cited excerpts and manuscript links")
            p.add_argument("--include-source-files", action="store_true", help="Include selected source files with redistribution permission; review mode also requires --include-research")
            p.add_argument("--mode", choices=SITE_MODES, default="review", help="Review workspace, novel with curated notes, or companion without novel text")
            p.add_argument("--publication-profile", metavar="NAME", help="Root-local site_publications profile for reader/companion mode")
            p.add_argument("--max-chapter", type=int, metavar="N", help="In publication modes, omit later chapters, notes and their assets from the exported files")
            p.add_argument("--analysis", action="append", choices=("chapters", "language", "full", "all"),
                           help="Reader analysis to disclose; repeat chapters/language or select full (all is an alias); default none")
            p.add_argument("--json", action="store_true", help="Print the versioned export manifest as JSON")
            p.epilog = (
                "Creates a portable read-only snapshot, not an authenticated website or backup. "
                "Open index.html locally or serve the exported directory with static hosting. "
                "Review all included content before sharing; copying cannot be prevented. "
                "Exporting does not publish, upload or change the source project."
            )
            continue
        if name not in ("serve", "completion", "about", "schema"):
            p.add_argument("--project", metavar="PATH",
                           help="Select an explicit project root; relative manuscript files resolve inside it; settings are root-local (no user or ancestor configuration)")
        if name in ("analyze", "profile", "style", "dashboard", "serve", "build", "scenes"):
            p.add_argument("--tense-model", default=None,
                           help="Explicit installed local syntax model for grammatical verb groups (no download/fallback)")
            p.add_argument("--tense-scope", choices=("all", "narration"), default=None,
                           help="Grammatical tense scope: all predicates or outside recognized quotations")
        if name == "style":
            p.epilog = (
                "Dimensions compare complete chapters using standardized midranks. "
                "Text output explains coverage, chapter scores and signed loadings; "
                "JSON dimension_diagnostics reports support and unavailable-data reasons. "
                "The per-axis cutoff box is not a confidence region or a literary-quality target."
            )
        if name == "completion":
            p.add_argument(
                "shell",
                nargs="?",
                default="bash",
                choices=("bash", "zsh", "sh"),
                help="Target shell (default: bash)",
            )
            continue
        if name in ("about", "schema"):
            p.add_argument(
                "--json", action="store_true",
                help="JSON output" if name == "about" else "Tool metadata as JSON (default; same as about --json)",
            )
            p.add_argument(
                "--section", choices=_ABOUT_SECTIONS,
                help="Return one metadata section as JSON, retaining version metadata",
            )
            continue
        if name == "scenes":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: selected workspace manuscript)")
            p.add_argument(
                "--language", default=None, help="Language profile (default: project setting or en)"
            )
            p.add_argument("--json", action="store_true", help="JSON output (scene schema v1)")
            p.add_argument("--chapter", type=_positive_chapter, metavar="N",
                           help="Select a canonical chapter number; comparisons retain the full manuscript")
            scene_selector = p.add_mutually_exclusive_group()
            scene_selector.add_argument("--scene", type=_scene_identifier, metavar="CHAPTER:SCENE",
                                        help="Select an exact measured or planned scene ID; --chapter must agree when supplied")
            scene_selector.add_argument("--latest", action="store_true",
                                        help="Last measured scene in document order, optionally within --chapter (not modification time)")
            continue
        if name in ("style", "dashboard", "serve", "build"):
            p.add_argument(
                "--min-chapters",
                type=int,
                default=None,
                help="Minimum chapters required for a style baseline (default: 2)",
            )
        if name not in ("motifs", "characters", "read-aloud"):
            _add_threshold_arguments(p)
        if name == "build":
            p.epilog = (
                "Writes metrics, paragraph profile and style JSON, a style passport, "
                "a Markdown report and an HTML dashboard under the project's exports/ "
                "folder. Changed artifacts are archived; identical content is not "
                "rewritten. Use --dry-run to inspect planned paths without writing. "
                "This does not switch a running app's project."
            )
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: configured manuscript or folder discovery)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)"
            )
            p.add_argument("--dry-run", action="store_true", help="Show planned artifacts only")
            continue
        if name == "motifs":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--motif",
                action="append",
                default=[],
                help="Motif as NAME=REGEX (repeatable)",
            )
            p.add_argument("--phrases", type=int, default=3, help="Phrase size (default 3)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)"
            )
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name == "characters":
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--name",
                action="append",
                default=[],
                help="Figure name or alias regex (repeatable; overrides project selection)",
            )
            p.add_argument("--names", help="Comma-separated names; omitted uses project characters or legacy names")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)"
            )
            p.add_argument("--json", action="store_true", help="JSON output")
            continue
        if name == "dashboard":
            p.description = "Generate a self-contained offline HTML report containing manuscript text, measurements and work-marker notes."
            p.epilog = (
                "Open the written HTML file in your browser. It embeds manuscript "
                "text and notes: review it before sharing. Project changes and "
                "research writes require the local app: lixity service start --open."
            )
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
            p.add_argument(
                "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)"
            )
            p.add_argument("--names", help="Comma-separated figure names (character panel)")
            p.add_argument("-o", "--output", help="HTML target file (default: lixity-dashboard.html)")
            continue
        if name == "read-aloud":
            from .speech_profiles import QWEN_VOICES

            p.epilog = _m("audio_read_help")
            p.add_argument("file", nargs="?", help="Markdown manuscript (default: configured manuscript or folder discovery)")
            p.add_argument("-o", "--output", help="Audio target file (WAV or MP3, default: <workspace-slug>.wav)")
            p.add_argument("--chapter", type=int, default=None, help="Synthesize only a specific 1-based chapter number")
            p.add_argument("--language", default=None, help="Speech language code (default: saved profile, then project setting)")
            p.add_argument("--profile", default=None, help="Saved project audio profile (default: selected project profile)")
            p.add_argument("--plan-only", action="store_true", help="Inspect effective speech text and direction as JSON; no synthesis or output")
            previews = p.add_mutually_exclusive_group()
            previews.add_argument("--preview", action="store_true", help="Preview the first anchored paragraph or list item")
            previews.add_argument("--preview-line", type=int, help="Preview the anchored paragraph or list item containing this source line")
            p.add_argument("--progress", action="store_true", help="Report segment progress and estimated remaining time to stderr")
            p.add_argument("--no-direction", action="store_true", help=_m("audio_no_direction_help"))
            p.add_argument("--instructions", default=None, help=_m("audio_instructions_help"))
            p.add_argument("--engine", choices=("qwen3", "qwen3-design", "qwen3-base", "coqui", "coqui-reference"), default=None, help=_m("audio_engine_help"))
            p.add_argument("--voice-description", default=None, help="VoiceDesign voice description")
            p.add_argument("--reference-id", default=None, help="Project-local Base voice reference identity")
            p.add_argument("--voice", default=None, help=_m("audio_voice_help", voices=", ".join(QWEN_VOICES)))
            p.add_argument("--speed", type=float, default=None, help="Override all profile tempo factors for this render (0.5–2.0; FFmpeg required unless 1.0)")
            p.add_argument("--speech-target", choices=("local", "jetson"), default="local", help="Execution target for this run (default: local); Jetson requires its configured SSH forward")
            p.add_argument("--no-audio-cache", action="store_true", help="Render without reading or retaining reusable audio segments")
            p.add_argument("--fresh-audio", action="store_true", help="Recompute Qwen segments instead of reusing completed project audio")
            p.add_argument("--keep-markers", action="store_true", help="Read editorial markers aloud instead of omitting them")
            continue
        if name == "serve":
            p.epilog = (
                "Keeps the server in this terminal; Ctrl+C stops it. Use "
                "--no-project to start an empty workspace. For the managed app, "
                "use lixity service start --open; service stop only manages "
                "instances created by that controller."
            )
            p.add_argument("--_service-token", help=argparse.SUPPRESS)
            p.add_argument(
                "path",
                nargs="?",
                default=None,
                help="Manuscript file or workspace folder (default: LIXITY_DIR or current folder)",
            )
            p.add_argument(
                "--host", default=DEFAULT_HOST, help=f"Bind address (default: {DEFAULT_HOST})"
            )
            p.add_argument(
                "--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})"
            )
            p.add_argument(
                "--language",
                default=None,
                help="Language profile (default: project setting or en; auto is explicit)",
            )
            p.add_argument("--title", default=None, help="Dashboard title (default: filename)")
            p.add_argument("--open", action="store_true", help="Open dashboard in browser")
            p.add_argument(
                "--no-project",
                action="store_true",
                help="Start without preloading a project",
            )
            p.add_argument(
                "--research-project",
                "--research-dir",
                dest="research_project",
                default=None,
                help="Explicit research project root for evidence management",
            )
            p.add_argument(
                "--debug",
                action="store_true",
                help="Enable verbose request logging, stack traces, and browser devtools debugging",
            )
            continue
        p.add_argument("file", nargs="?", help="Markdown manuscript (default: manuscript in root-local project config)")
        p.add_argument(
            "--language", default=None, help="de|en|fr|es|it|pt|nl|generic|auto (default: en)"
        )
        p.add_argument(
            "--json", action="store_true", help=argparse.SUPPRESS if name == "pdf" else "JSON output"
        )
        if name == "profile":
            p.formatter_class = argparse.RawDescriptionHelpFormatter
            p.epilog = (
                "Start with one question, such as sentence rhythm:\n"
                "  lixity profile manuscript.md --language en --layer asl --only-notable\n"
                "Then inspect the counted text:\n"
                "  lixity profile manuscript.md --language en --layer asl --only-notable --evidence\n\n"
                "ASL means words per sentence. Read the reported source lines before deciding.\n"
                "Paragraph comparisons use the same chapter, not the manuscript-wide chapter baseline.\n"
                "Notable means a descriptive difference, not an error or quality verdict.\n"
                "Unavailable comparison is not a measured zero. English is the default;\n"
                "choose the manuscript language explicitly. Add --json for structured output."
            )
            p.add_argument(
                "--layer", choices=tuple(LAYER_FEATURES),
                help="Inspect one paragraph metric and its within-chapter comparison (text; --json for paragraph-layer/1)",
            )
            p.add_argument(
                "--only-notable", action="store_true",
                help="With --layer, show only notable paragraphs; retain the full chapter reference",
            )
            p.add_argument(
                "--evidence", action="store_true",
                help="With --layer, include literal counted spans (JSON: paragraph-layer-evidence/1)",
            )
        p.add_argument("-o", "--output", help="PDF target file" if name == "pdf" else "Write report text or JSON to a file instead of stdout")
        if name == "pdf":
            from .pdf_export import PDF_LAYOUTS

            p.epilog = (
                "Manuscript layouts retain headings, scene breaks, lists, quotations and endnotes. "
                r"Embedded LaTeX supports \emph, \textit, \textbf, \texttt and \textnormal; "
                r"standalone \newpage/\clearpage request page breaks. "
                "No TeX execution, mathematics typesetting or image placement. "
                "Unsupported TeX constructs fail before the output file is written."
            )
            p.add_argument(
                "--layout",
                choices=PDF_LAYOUTS,
                default="report",
                help="editor: A4 editorial copy with line numbers and comment margins · "
                "book: A5 reading copy · sheet: 30 lines of 60 characters · report: A4 analysis · "
                "document: neutral A4 text without line numbers or a generated cover",
            )
            p.add_argument(
                "--title",
                default=None,
                help="Document title override (default: project or manuscript title)",
            )
            p.add_argument("--author", default=None, help="Author byline and running header")
            p.add_argument(
                "--draft-notice",
                default=None,
                help="Running-header notice on every layout (default: project draft_notice)",
            )
            p.add_argument("--serif-font", default=None, help="TrueType file for running text")
            p.add_argument("--bold-font", default=None, help="TrueType file for headings")
            p.add_argument("--italic-font", default=None, help="TrueType file for italic manuscript text")
            p.add_argument("--bold-italic-font", default=None, help="TrueType file for bold italic manuscript text")
            p.add_argument("--mono-font", default=None, help="TrueType file for the sheet grid")
            p.add_argument("--sans-font", default=None, help="TrueType file for the report text")
            p.add_argument(
                "--sans-bold-font", default=None, help="TrueType file for report headings"
            )
    args = parser.parse_args(argv)
    if args.command == "analysis-review":
        from .analysis_review import record_analysis_review, review_analysis
        from .format import safe_text

        fields = (args.observation, args.status, args.expected_source_sha256,
                  args.expected_analysis_sha256, args.expected_review_sha256)
        if any(value is not None for value in fields) and not all(value is not None for value in fields):
            parser.error("Saving requires --observation, --status and all three --expected-*-sha256 values")
        try:
            if args.status:
                triage_report = record_analysis_review(args.project, args.observation, args.status,
                    manuscript=args.manuscript, language=args.language,
                    tense_model=args.tense_model, tense_scope=args.tense_scope,
                    expected_source_sha256=args.expected_source_sha256,
                    expected_analysis_sha256=args.expected_analysis_sha256,
                    expected_review_sha256=args.expected_review_sha256)
            else:
                triage_report = review_analysis(args.project, manuscript=args.manuscript, language=args.language,
                                               tense_model=args.tense_model, tense_scope=args.tense_scope)
            if args.json:
                print(orjson.dumps(triage_report, option=orjson.OPT_INDENT_2).decode())
            else:
                print(f"Tense-pattern review: {triage_report['completed']} / {triage_report['total']} decisions completed.")
                print("Differences are not errors; changed is your assertion, and later remains open.")
                unmatched = triage_report["unmatched_decisions"]
                if unmatched:
                    noun, verb, retained = (("decision", "matches", "it is") if unmatched == 1
                                            else ("decisions", "match", "they are"))
                    print(f"{unmatched} previously saved {noun} for this manuscript no longer {verb} current observations; "
                          f"{retained} retained in the project.")
                for observation in triage_report["observations"][:20]:
                    print(safe_text(f"{triage_report['source_path']}:{observation['start_line']}-{observation['end_line']} · "
                        f"{observation['status']} · present {observation['present_hits']} / past {observation['past_hits']} · {observation['id']}"))
                if triage_report["total"] > 20:
                    print("First 20 observations shown; use --json for the complete guarded report.")
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as error:
            print(f"{_m('err_prefix')} {safe_text(str(error))}", file=sys.stderr)
            return EXIT_ERROR
    if args.command == "project":
        return _cmd_project(args)
    if args.command == "service":
        from .service import run as run_service

        return run_service(args)
    if args.command == "research":
        from .research.cli import run as run_research

        return run_research(args)
    if args.command == "doctor":
        from .diagnostics import DOCTOR_SCHEMA, doctor

        try:
            port = args.port if args.port is not None else int(os.environ.get("LIXITY_PORT") or DEFAULT_PORT)
            result = doctor(port=port)
        except ValueError:
            result = {"schema_version": DOCTOR_SCHEMA, "ok": False,
                      "error": {"code": "invalid-service-port", "message": _m("doctor_invalid_service_port")}}
        if args.json:
            print(orjson.dumps(result).decode("utf-8"))
        elif "error" in result:
            print(f"{_m('err_prefix')} {result['error']['message']}", file=sys.stderr)
        else:
            installation = result["installation"]
            for key in ("cli_version", "distribution_version", "module_path", "interpreter"):
                print(f"{_m('doctor_' + key)}: {installation[key] if installation[key] is not None else _m('doctor_unknown')}")
            service = result["service"]
            print(f"{_m('doctor_service')}: {service['state']} ({service['port']})")
            for issue in result["issues"]:
                print("- " + _m("doctor_" + issue["code"].replace("-", "_")))
            if result["ok"]:
                print(_m("doctor_ok"))
        return EXIT_OK if result["ok"] else EXIT_ERROR
    if args.command == "about":
        _print_about_json(args.section) if args.json or args.section else _print_about_text()
        return EXIT_OK
    if args.command == "schema":
        _print_about_json(args.section)
        return EXIT_OK
    if args.command == "completion":
        shell = (args.shell or "bash").strip().lower()
        if shell in ("bash", "sh"):
            sys.stdout.write(_completion_scripts()[0])
            return EXIT_OK
        if shell == "zsh":
            sys.stdout.write(_completion_scripts()[1])
            return EXIT_OK
        # argparse choices already rejected unknown shells; keep a defensive path
        print(f"{_m('err_prefix')} {_m('err_shell', shell=args.shell)}", file=sys.stderr)
        return EXIT_ERROR
    if args.command == "audio-reference":
        from .speech_qwen import MAX_REFERENCE_BYTES
        from .speech_references import read_reference_input, save_reference
        try:
            audio = read_reference_input(args.audio, MAX_REFERENCE_BYTES)
            transcript = read_reference_input(args.transcript_file, 8000).decode("utf-8")
            reference = save_reference(args.project, audio, transcript)
        except (OSError, ValueError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_json({"schema_version": "lixity-audio-reference-created/1", "id": reference.id}, indent=True))
        return EXIT_OK
    if args.command == "audio-status":
        from .format import safe_text
        from .speech_status import audio_status
        try:
            status = audio_status(args.project, engine=args.engine)
        except (OSError, ValueError, RuntimeError, UserWarning) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(status, indent=True))
        else:
            if status['comparison_engine'] is not None:
                print(f"{_m('audio_status_comparison')}: {status['comparison_engine']}")
            if status['project'] is not None:
                print(f"{_m('audio_status_project')}: {safe_text(status['project']['root'])}")
                print(f"{_m('audio_status_selected')}: {status['project']['selected_profile'] or _m('audio_status_unknown')}")
                for item in status['project']['profiles']:
                    print(safe_text(f"  {item['id']}: {item['name']} · {item['engine']} · {item['voice']} · {item['language']}"))
                if status['project'].get('profile_issue'):
                    print(f"{_m('audio_status_unavailable')}: {status['project']['profile_issue']}")
            for target in status['targets']:
                match = target['model_matches']
                matching = _m('audio_status_yes' if match is True else 'audio_status_no' if match is False else 'audio_status_unknown')
                print(f"{target['target']}: {target['state']} · {target.get('model') or _m('audio_status_unknown')} · "
                      f"{_m('audio_status_match')}: {matching}")
            if status['comparison_engine'] == 'qwen3-design':
                print(_m('audio_status_design_hint'))
            elif status['comparison_engine'] == 'qwen3-base':
                print(_m('audio_status_base_hint'))
        return EXIT_OK
    if args.command == "audio-direction":
        from .speech_direction_cli import run
        try:
            print(_json(run(args), indent=True))
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(_json({"ok": False, "message": str(exc)}, indent=True))
            return EXIT_ERROR
    if args.command == "audio-migrate":
        from .speech_migration import prepare_audio_migration, prepare_schema3_migration

        def pairs(values: list[str]) -> dict[str, str]:
            result: dict[str, str] = {}
            for value in values:
                key, separator, item = value.partition("=")
                if not separator or not key or not item or key in result:
                    raise ValueError("Supply unique PROFILE=VALUE entries")
                result[key] = item
            return result

        if args.apply and (not args.backup or not args.expected_snapshot):
            parser.error("audio-migrate --apply requires --backup and --expected-snapshot from a reviewed preview")
        if not args.apply and (args.backup or args.expected_snapshot):
            parser.error("Omit --backup and --expected-snapshot for a read-only preview")
        try:
            if args.to_schema_3 and (args.replace or args.instructions):
                raise ValueError("Schema upgrade cannot be combined with profile replacements")
            prepared = (prepare_schema3_migration(args.project) if args.to_schema_3 else
                        prepare_audio_migration(args.project, pairs(args.replace), instructions=pairs(args.instructions)))
            if args.apply and args.expected_snapshot != prepared.snapshot:
                raise ValueError("Migration snapshot changed; prepare and review the migration again")
            result = prepared.apply(args.backup) if args.apply else prepared.public_dict()
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(_json(result, indent=True))
        return EXIT_OK
    if args.command == "export-site":
        from .site_contracts import SiteExportOptions
        from .site_export import SiteExportLimitError, export_site, prepare_site

        if args.preflight and args.output:
            parser.error("--preflight does not write an output directory; omit --output")
        if not args.preflight and not args.output:
            parser.error("export-site requires --output, or --preflight to check without writing")
        try:
            sections = args.analysis or []
            if "all" in sections:
                if sections != ["all"]:
                    raise ValueError("The all-analysis choice cannot be combined with other sections")
                sections = ["full"]
            options = SiteExportOptions(include_research=args.include_research,
                                        include_source_files=args.include_source_files,
                                        mode=args.mode, publication_profile=args.publication_profile,
                                        max_chapter=args.max_chapter, analysis_sections=sections)
            if args.preflight:
                report = prepare_site(args.project, manuscript=args.file, language=args.language,
                                      **options.model_dump(exclude_defaults=True)).preflight()
                if args.json:
                    print(_json(report, indent=True))
                else:
                    sizes, media = report["sizes"], report["media"]
                    print(f"HTML: {sizes['html_bytes']:,} bytes; ZIP: {sizes['zip_bytes']:,} bytes; "
                          f"all files: {sizes['total_bytes']:,} bytes ({sizes['file_count']} files)")
                    print(f"Media references: {media['references']}; unavailable: {media['unavailable']}; "
                          f"not packaged: {media['not_packaged']}; attribution incomplete: {media['missing_attribution']}; "
                          f"ordinary images unchecked: {media['ordinary_image_references']}")
                    print("Mobile layout: not checked. Rights: not verified. No output written.")
                    if report["warnings"]:
                        print("Warnings: " + ", ".join(report["warnings"]))
                return EXIT_OK
            manifest = export_site(
                args.project, args.output, manuscript=args.file, language=args.language,
                **options.model_dump(exclude_defaults=True),
            )
        except SiteExportLimitError as exc:
            if args.json:
                print(_json(exc.diagnostic, indent=True))
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        if args.json:
            print(_json(manifest, indent=True))
        else:
            from pathlib import Path

            from .format import safe_text

            print(safe_text(str(Path(args.output).expanduser().resolve() / "index.html")))
            print(_m("site_export_done"))
        return EXIT_OK
    if getattr(args, "min_chapters", None) is not None and args.min_chapters < 2:
        parser.error("--min-chapters must be at least 2")
    if args.command == "profile" and args.only_notable and args.layer is None:
        parser.error("--only-notable requires --layer")
    if args.command == "profile" and args.evidence and args.layer is None:
        parser.error("--evidence requires --layer")
    if args.command == "pdf" and args.json:
        parser.error("--json is not supported for PDF output; use analyze or style --json for measurements")
    if args.command == "serve":
        project_config = {} if args.no_project else load_project_config(args.path)
    else:
        explicit_file = args.file
        try:
            workspace = resolve_manuscript_target(
                explicit_file, project=args.project,
                allow_discovery=args.command in ("scenes", "build", "read-aloud"),
            )
            args._workspace = workspace
            # Keep the legacy spelling for explicit files without --project.
            if explicit_file is None or args.project is not None:
                args.file = workspace.manuscript
                project_config = read_explicit_project_config(workspace.root)
                speech_config_selection = (True, workspace.root)
                if (args.project is None and args.command in ("scenes", "build", "read-aloud")
                        and "manuscript" not in project_config):
                    # Preserve conventional folder users' defaults, rooted at
                    # the selected workspace rather than an implicit cwd.
                    project_config = load_project_config(workspace.root)
                    speech_config_selection = (False, workspace.root)
            else:
                project_config = load_project_config(explicit_file)
                speech_config_selection = (False, explicit_file)
            if args.command == "read-aloud":
                args._speech_config_selection = speech_config_selection
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_ERROR
    project_config = {**project_config, **{key: value for key in ("tense_model", "tense_scope")
                      if (value := getattr(args, key, None)) is not None}}
    args._project_config = project_config
    explicit_language = getattr(args, "language", None)
    if args.command == "read-aloud":
        args._speech_explicit_language = explicit_language
    if hasattr(args, "language") and args.language is None:
        args.language = project_config.get("language", "en")

    if args.command == "serve":
        from .server import run_server
        from .service import ManagedServe

        fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
        project_open_overrides = {
            key: value
            for key, value in (
                ("language", explicit_language),
                ("title", args.title),
                ("z_mild", args.z_mild),
                ("z_strong", args.z_strong),
                ("fdr_q", args.fdr_q),
                ("fdr_method", args.fdr_method),
                ("min_chapters", getattr(args, "min_chapters", None)),
                ("dim_score_threshold", args.dim_threshold),
                ("flag_min_severity", args.flag_min_severity),
                ("tense_model", args.tense_model),
                ("tense_scope", args.tense_scope),
            )
            if value is not None
        }
        managed = None
        try:
            if args._service_token is not None:
                managed = ManagedServe(args._service_token, args.port)
            run_server(
                target_path=args.path,
                host=args.host,
                port=args.port,
                language=args.language,
                title=args.title or project_config.get("title"),
                no_project=args.no_project,
                thresholds=fp_thresholds,
                open_browser=args.open,
                research_dir=args.research_project,
                project_open_overrides=project_open_overrides,
                debug=args.debug,
                announce=True,
                on_ready=managed.ready if managed is not None else None,
            )
            return EXIT_OK
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
            return EXIT_ERROR
        finally:
            if managed is not None:
                managed.close()

    if args.command == "pdf":
        return _cmd_pdf(args)

    if args.command == "read-aloud":
        return _cmd_read_aloud(args)

    if args.command == "build":
        return _cmd_build(args)

    if args.command == "dialogue":
        return _run_text_report(args, lambda: _cmd_dialogue(args))

    if args.command == "characters":
        return _cmd_characters(args)

    if args.command == "pacing":
        return _run_text_report(args, lambda: _cmd_pacing(args))

    if args.command == "motifs":
        return _cmd_motifs(args)

    if args.command == "showing":
        return _run_text_report(args, lambda: _cmd_showing(args))

    try:
        text = FileUtils.read_file(args.file)
    except OSError as exc:
        print(f"{_m('err_prefix')} {_m('err_file', file=args.file, exc=exc)}", file=sys.stderr)
        return EXIT_ERROR

    try:
        config, resolved = resolve_document_config(
            text, args.language, project_config=args._project_config
        )
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.command in ("scenes", "analyze", "profile", "style"):
        return _run_text_report(args, lambda: _cmd_analysis_report(args, text, config, resolved))

    fp_thresholds = _thresholds_from_args(args, getattr(args, "_project_config", None))
    analysis = analyze_document(text, config, fp_thresholds)
    metrics = analysis.metrics
    from .characters import presence_report, resolve_character_settings
    from .dialogue import dialogue_report

    try:
        raw_names = getattr(args, "names", None)
        selection = resolve_character_settings(
            [part.strip() for part in raw_names.split(",") if part.strip()] if raw_names is not None else None,
            args._project_config,
        )
        character_report = (presence_report(text, selection.names, config, declared_pov=selection.declared_pov)
                            if selection.names else None)
        title = _document_title(args, args.file, text)
    except ValueError as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    html = render_analysis(
        analysis,
        resolved,
        reader_document=reader_blocks(text, config, analysis.paragraphs),
        title=title,
        flag_min_severity=fp_thresholds.flag_min_severity,
        scenes=scene_report_for_display(
            text,
            config,
            args._project_config.get("scene_analysis"),
            premeasured_chapters=metrics.chapters,
        ),
        dialogue=dialogue_report(text, config).to_dict(),
        characters=character_report,
    )
    output = args.output or "lixity-dashboard.html"
    try:
        FileUtils.require_distinct_output(args.file, output)
        changed = FileUtils.atomic_write_if_changed(
            output, html, before_replace=lambda: FileUtils.require_distinct_output(args.file, output),
        )
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(_m("dashboard_written" if changed else "dashboard_unchanged", output=output))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Keep ordinary configuration/model failures inside the CLI error contract."""
    try:
        return _main(argv)
    except (OSError, ValueError) as exc:
        print(f"{_m('err_prefix')} {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
