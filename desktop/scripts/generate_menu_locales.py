#!/usr/bin/env python3
"""Generate localized desktop OS menu labels from Lixity's 7 canonical locale catalogs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCALES_DIR = ROOT / "src" / "lixity" / "locales"
OUTPUT_PATH = ROOT / "desktop" / "src-tauri" / "generated" / "menu-locales.json"
LANGUAGES = ("de", "en", "fr", "es", "it", "pt", "nl")

# Base OS menu headings & desktop-only items across all 7 supported interface languages.
# Workspace-specific labels are pulled directly from src/lixity/locales/<lang>.json so
# the native OS menu bar and the embedded workspace stay terminology-consistent.
DESKTOP_MENU_BASE: dict[str, dict[str, str]] = {
    "de": {
        "menu_file": "Datei",
        "menu_edit": "Bearbeiten",
        "menu_view": "Ansicht",
        "menu_window": "Fenster",
        "item_about": "Über Lixity",
        "item_hide": "Lixity ausblenden",
        "item_fullscreen": "Vollbild ein/aus",
        "item_minimize": "Minimieren",
        "menu_tools": "Werkzeuge",
        "menu_help": "Hilfe",
        "item_new_window": "Neues Fenster",
        "item_open_project": "Projekt öffnen…",
        "item_recent_projects": "Zuletzt geöffnete Projekte",
        "item_recent_empty": "Keine zuletzt geöffneten Projekte",
        "item_import_manuscript": "Manuskript importieren…",
        "item_quit": "Beenden",
        "item_undo": "Rückgängig",
        "item_redo": "Wiederholen",
        "item_cut": "Ausschneiden",
        "item_copy": "Kopieren",
        "item_paste": "Einfügen",
        "item_select_all": "Alles auswählen",
        "item_zoom_in": "Vergrößern",
        "item_zoom_out": "Verkleinern",
        "item_zoom_reset": "Originalgröße",
        "item_system_status": "Systemstatus & Erweiterungen",
        "item_open_logs": "Protokollordner öffnen",
        "item_check_updates": "Nach neuer Version suchen…",
        "item_documentation": "Dokumentation (Website)",
        "close_guard_title": "Fenster schließen",
        "close_guard_body": "Im Editor gibt es ungespeicherte Änderungen oder laufende Audioaufträge. Fenster trotzdem schließen?",
        "close_guard_audio_unavailable": "Der Status der Audioaufträge ist unbekannt. Beim Schließen können laufende Aufträge unterbrochen werden.",
        "startup_runtime_missing": "Lixity findet die mitgelieferten Programmdateien nicht. Installiere Lixity erneut mit dem Paket für dein Betriebssystem.",
        "startup_runtime_failed": "Die lokale Analyse konnte nicht gestartet werden. Öffne den Protokollordner für Einzelheiten.",
        "startup_window_failed": "Lixity konnte das Arbeitsfenster nicht öffnen. Prüfe die Installationshinweise für dein System und starte Lixity erneut.",
        "startup_logs_unavailable": "Lixity konnte den Protokollordner nicht öffnen. Starte Lixity erneut und melde das Problem, falls es bestehen bleibt.",
    },
    "en": {
        "menu_file": "File",
        "menu_edit": "Edit",
        "menu_view": "View",
        "menu_window": "Window",
        "item_about": "About Lixity",
        "item_hide": "Hide Lixity",
        "item_fullscreen": "Toggle Full Screen",
        "item_minimize": "Minimize",
        "menu_tools": "Tools",
        "menu_help": "Help",
        "item_new_window": "New Window",
        "item_open_project": "Open Project…",
        "item_recent_projects": "Recent Projects",
        "item_recent_empty": "No recent projects",
        "item_import_manuscript": "Import Manuscript…",
        "item_quit": "Quit",
        "item_undo": "Undo",
        "item_redo": "Redo",
        "item_cut": "Cut",
        "item_copy": "Copy",
        "item_paste": "Paste",
        "item_select_all": "Select All",
        "item_zoom_in": "Zoom In",
        "item_zoom_out": "Zoom Out",
        "item_zoom_reset": "Actual Size",
        "item_system_status": "System Status & Extensions",
        "item_open_logs": "Open Logs Folder",
        "item_check_updates": "Check for Updates…",
        "item_documentation": "Documentation (Website)",
        "close_guard_title": "Close Window",
        "close_guard_body": "There are unsaved editor changes or active audio jobs. Close this window anyway?",
        "close_guard_audio_unavailable": "The audio job status is unavailable. Closing the window may interrupt jobs in progress.",
        "startup_runtime_missing": "Lixity could not find its bundled program files. Reinstall Lixity from the package for your operating system.",
        "startup_runtime_failed": "The local analysis engine did not start. Open the logs folder for details.",
        "startup_window_failed": "Lixity could not open its workspace window. Check the installation guide for your system and open Lixity again.",
        "startup_logs_unavailable": "Lixity could not open the logs folder. Try launching Lixity again and report the problem if it continues.",
    },
    "fr": {
        "menu_file": "Fichier",
        "menu_edit": "Édition",
        "menu_view": "Affichage",
        "menu_window": "Fenêtre",
        "item_about": "À propos de Lixity",
        "item_hide": "Masquer Lixity",
        "item_fullscreen": "Activer ou quitter le plein écran",
        "item_minimize": "Réduire",
        "menu_tools": "Outils",
        "menu_help": "Aide",
        "item_new_window": "Nouvelle fenêtre",
        "item_open_project": "Ouvrir un projet…",
        "item_recent_projects": "Projets récents",
        "item_recent_empty": "Aucun projet récent",
        "item_import_manuscript": "Importer un manuscrit…",
        "item_quit": "Quitter",
        "item_undo": "Annuler",
        "item_redo": "Rétablir",
        "item_cut": "Couper",
        "item_copy": "Copier",
        "item_paste": "Coller",
        "item_select_all": "Tout sélectionner",
        "item_zoom_in": "Zoom avant",
        "item_zoom_out": "Zoom arrière",
        "item_zoom_reset": "Taille réelle",
        "item_system_status": "État du système et extensions",
        "item_open_logs": "Ouvrir le dossier des journaux",
        "item_check_updates": "Rechercher des mises à jour…",
        "item_documentation": "Documentation (site web)",
        "close_guard_title": "Fermer la fenêtre",
        "close_guard_body": "Des modifications ne sont pas enregistrées ou des tâches audio sont en cours. Fermer cette fenêtre malgré tout ?",
        "close_guard_audio_unavailable": "L’état des tâches audio est indisponible. Fermer la fenêtre peut interrompre les tâches en cours.",
        "startup_runtime_missing": "Lixity ne trouve pas les fichiers fournis avec l’application. Réinstalle Lixity à partir du paquet pour ton système.",
        "startup_runtime_failed": "Le moteur d’analyse locale n’a pas démarré. Ouvre le dossier des journaux pour en savoir plus.",
        "startup_window_failed": "Lixity n’a pas pu ouvrir sa fenêtre de travail. Consulte le guide d’installation de ton système, puis relance Lixity.",
        "startup_logs_unavailable": "Lixity n’a pas pu ouvrir le dossier des journaux. Relance Lixity et signale le problème s’il persiste.",
    },
    "es": {
        "menu_file": "Archivo",
        "menu_edit": "Edición",
        "menu_view": "Ver",
        "menu_window": "Ventana",
        "item_about": "Acerca de Lixity",
        "item_hide": "Ocultar Lixity",
        "item_fullscreen": "Activar o salir de pantalla completa",
        "item_minimize": "Minimizar",
        "menu_tools": "Herramientas",
        "menu_help": "Ayuda",
        "item_new_window": "Nueva ventana",
        "item_open_project": "Abrir proyecto…",
        "item_recent_projects": "Proyectos recientes",
        "item_recent_empty": "No hay proyectos recientes",
        "item_import_manuscript": "Importar manuscrito…",
        "item_quit": "Salir",
        "item_undo": "Deshacer",
        "item_redo": "Rehacer",
        "item_cut": "Cortar",
        "item_copy": "Copiar",
        "item_paste": "Pegar",
        "item_select_all": "Seleccionar todo",
        "item_zoom_in": "Acercar",
        "item_zoom_out": "Alejar",
        "item_zoom_reset": "Tamaño real",
        "item_system_status": "Estado del sistema y extensiones",
        "item_open_logs": "Abrir carpeta de registros",
        "item_check_updates": "Buscar actualizaciones…",
        "item_documentation": "Documentación (sitio web)",
        "close_guard_title": "Cerrar ventana",
        "close_guard_body": "Hay cambios sin guardar en el editor o tareas de audio activas. ¿Cerrar esta ventana de todos modos?",
        "close_guard_audio_unavailable": "Se desconoce el estado de las tareas de audio. Cerrar la ventana puede interrumpir las tareas en curso.",
        "startup_runtime_missing": "Lixity no encuentra los archivos incluidos en la aplicación. Reinstala Lixity con el paquete para tu sistema operativo.",
        "startup_runtime_failed": "El motor de análisis local no se inició. Abre la carpeta de registros para ver los detalles.",
        "startup_window_failed": "Lixity no pudo abrir su ventana de trabajo. Consulta la guía de instalación de tu sistema y vuelve a abrir Lixity.",
        "startup_logs_unavailable": "Lixity no pudo abrir la carpeta de registros. Vuelve a iniciar Lixity y avisa si el problema continúa.",
    },
    "it": {
        "menu_file": "File",
        "menu_edit": "Modifica",
        "menu_view": "Vista",
        "menu_window": "Finestra",
        "item_about": "Informazioni su Lixity",
        "item_hide": "Nascondi Lixity",
        "item_fullscreen": "Attiva o disattiva schermo intero",
        "item_minimize": "Minimizza",
        "menu_tools": "Strumenti",
        "menu_help": "Aiuto",
        "item_new_window": "Nuova finestra",
        "item_open_project": "Apri progetto…",
        "item_recent_projects": "Progetti recenti",
        "item_recent_empty": "Nessun progetto recente",
        "item_import_manuscript": "Importa manoscritto…",
        "item_quit": "Esci",
        "item_undo": "Annulla",
        "item_redo": "Ripeti",
        "item_cut": "Taglia",
        "item_copy": "Copia",
        "item_paste": "Incolla",
        "item_select_all": "Seleziona tutto",
        "item_zoom_in": "Ingrandisci",
        "item_zoom_out": "Riduci",
        "item_zoom_reset": "Dimensione reale",
        "item_system_status": "Stato del sistema ed estensioni",
        "item_open_logs": "Apri cartella dei log",
        "item_check_updates": "Controlla aggiornamenti…",
        "item_documentation": "Documentazione (sito web)",
        "close_guard_title": "Chiudi finestra",
        "close_guard_body": "Ci sono modifiche non salvate nell'editor o processi audio attivi. Chiudere comunque questa finestra?",
        "close_guard_audio_unavailable": "Lo stato delle attività audio non è disponibile. Chiudere la finestra può interrompere le attività in corso.",
        "startup_runtime_missing": "Lixity non trova i file inclusi nell’applicazione. Reinstalla Lixity con il pacchetto per il tuo sistema operativo.",
        "startup_runtime_failed": "Il motore di analisi locale non si è avviato. Apri la cartella dei registri per i dettagli.",
        "startup_window_failed": "Lixity non ha potuto aprire la finestra di lavoro. Consulta la guida di installazione per il tuo sistema e riapri Lixity.",
        "startup_logs_unavailable": "Lixity non ha potuto aprire la cartella dei registri. Riapri Lixity e segnala il problema se persiste.",
    },
    "pt": {
        "menu_file": "Arquivo",
        "menu_edit": "Editar",
        "menu_view": "Exibir",
        "menu_window": "Janela",
        "item_about": "Sobre o Lixity",
        "item_hide": "Ocultar o Lixity",
        "item_fullscreen": "Ativar ou sair do ecrã inteiro",
        "item_minimize": "Minimizar",
        "menu_tools": "Ferramentas",
        "menu_help": "Ajuda",
        "item_new_window": "Nova janela",
        "item_open_project": "Abrir projeto…",
        "item_recent_projects": "Projetos recentes",
        "item_recent_empty": "Nenhum projeto recente",
        "item_import_manuscript": "Importar manuscrito…",
        "item_quit": "Sair",
        "item_undo": "Desfazer",
        "item_redo": "Refazer",
        "item_cut": "Recortar",
        "item_copy": "Copiar",
        "item_paste": "Colar",
        "item_select_all": "Selecionar tudo",
        "item_zoom_in": "Ampliar",
        "item_zoom_out": "Reduzir",
        "item_zoom_reset": "Tamanho real",
        "item_system_status": "Estado do sistema e extensões",
        "item_open_logs": "Abrir pasta de registos",
        "item_check_updates": "Verificar atualizações…",
        "item_documentation": "Documentação (site)",
        "close_guard_title": "Fechar janela",
        "close_guard_body": "Existem alterações não salvas no editor ou tarefas de áudio ativas. Fechar esta janela mesmo assim?",
        "close_guard_audio_unavailable": "O estado das tarefas de áudio é desconhecido. Fechar a janela pode interromper as tarefas em andamento.",
        "startup_runtime_missing": "O Lixity não encontrou os ficheiros incluídos na aplicação. Reinstala o Lixity com o pacote para o teu sistema operativo.",
        "startup_runtime_failed": "O motor de análise local não arrancou. Abre a pasta de registos para ver os detalhes.",
        "startup_window_failed": "O Lixity não conseguiu abrir a janela de trabalho. Consulta o guia de instalação do teu sistema e volta a abrir o Lixity.",
        "startup_logs_unavailable": "O Lixity não conseguiu abrir a pasta de registos. Volta a abrir o Lixity e comunica o problema se continuar.",
    },
    "nl": {
        "menu_file": "Bestand",
        "menu_edit": "Bewerken",
        "menu_view": "Beeld",
        "menu_window": "Venster",
        "item_about": "Over Lixity",
        "item_hide": "Verberg Lixity",
        "item_fullscreen": "Schakel schermvullende weergave in of uit",
        "item_minimize": "Minimaliseer",
        "menu_tools": "Hulpmiddelen",
        "menu_help": "Help",
        "item_new_window": "Nieuw venster",
        "item_open_project": "Project openen…",
        "item_recent_projects": "Recente projecten",
        "item_recent_empty": "Geen recente projecten",
        "item_import_manuscript": "Manuscript importeren…",
        "item_quit": "Afsluiten",
        "item_undo": "Ongedaan maken",
        "item_redo": "Opnieuw",
        "item_cut": "Knippen",
        "item_copy": "Kopiëren",
        "item_paste": "Plakken",
        "item_select_all": "Alles selecteren",
        "item_zoom_in": "Inzoomen",
        "item_zoom_out": "Uitzoomen",
        "item_zoom_reset": "Werkelijke grootte",
        "item_system_status": "Systeemstatus en uitbreidingen",
        "item_open_logs": "Logmap openen",
        "item_check_updates": "Controleren op updates…",
        "item_documentation": "Documentatie (website)",
        "close_guard_title": "Venster sluiten",
        "close_guard_body": "Er zijn niet-opgeslagen wijzigingen in de editor of actieve audiotaken. Dit venster toch sluiten?",
        "close_guard_audio_unavailable": "De status van de audiotaken is onbekend. Als je het venster sluit, kunnen lopende taken worden onderbroken.",
        "startup_runtime_missing": "Lixity kan de meegeleverde programmabestanden niet vinden. Installeer Lixity opnieuw met het pakket voor je besturingssysteem.",
        "startup_runtime_failed": "De lokale analyse kon niet starten. Open de logmap voor meer informatie.",
        "startup_window_failed": "Lixity kon het werkvenster niet openen. Raadpleeg de installatiehandleiding voor je systeem en open Lixity opnieuw.",
        "startup_logs_unavailable": "Lixity kon de logmap niet openen. Open Lixity opnieuw en meld het probleem als het zich blijft voordoen.",
    },
}

CATALOG_BINDINGS: dict[str, str] = {
    "item_view_analysis": "cmd_view_analysis_title",
    "item_view_analysis_overview": "reading_overview",
    "item_view_research": "cmd_view_research_title",
    "item_view_project": "cmd_view_project_title",
    "item_toggle_theme": "cmd_toggle_theme_title",
    "item_teleprompter": "cmd_audio_teleprompter_title",
    "item_export_pdf": "cmd_export_pdf_title",
}


def build_payload() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for lang in LANGUAGES:
        catalog = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
        entry = dict(DESKTOP_MENU_BASE[lang])
        for target_key, source_key in CATALOG_BINDINGS.items():
            value = catalog.get(source_key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Missing locale key {source_key!r} in {lang}.json")
            entry[target_key] = value
        result[lang] = dict(sorted(entry.items()))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated output matches disk")
    args = parser.parse_args(argv)

    rendered = json.dumps(build_payload(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                f"{OUTPUT_PATH} is out of date; run desktop/scripts/generate_menu_locales.py"
            )
        print(f"[OK] {OUTPUT_PATH} is synchronized across {len(LANGUAGES)} locales.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"[OK] Wrote {OUTPUT_PATH} ({len(LANGUAGES)} locales).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
