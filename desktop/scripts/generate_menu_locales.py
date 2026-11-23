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
        "close_guard_title": "Ungespeicherte Änderungen",
        "close_guard_body": "Im Editor gibt es ungespeicherte Änderungen oder laufende Audio-Aufträge. Fenster trotzdem schließen?",
    },
    "en": {
        "menu_file": "File",
        "menu_edit": "Edit",
        "menu_view": "View",
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
        "close_guard_title": "Unsaved Changes",
        "close_guard_body": "There are unsaved editor changes or active audio jobs. Close this window anyway?",
    },
    "fr": {
        "menu_file": "Fichier",
        "menu_edit": "Édition",
        "menu_view": "Affichage",
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
        "close_guard_title": "Modifications non enregistrées",
        "close_guard_body": "Des modifications ou des tâches audio sont en cours. Fermer cette fenêtre malgré tout ?",
    },
    "es": {
        "menu_file": "Archivo",
        "menu_edit": "Edición",
        "menu_view": "Ver",
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
        "close_guard_title": "Cambios sin guardar",
        "close_guard_body": "Hay cambios sin guardar en el editor o tareas de audio activas. ¿Cerrar esta ventana de todos modos?",
    },
    "it": {
        "menu_file": "File",
        "menu_edit": "Modifica",
        "menu_view": "Vista",
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
        "close_guard_title": "Modifiche non salvate",
        "close_guard_body": "Ci sono modifiche non salvate nell'editor o processi audio attivi. Chiudere comunque questa finestra?",
    },
    "pt": {
        "menu_file": "Arquivo",
        "menu_edit": "Editar",
        "menu_view": "Exibir",
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
        "close_guard_title": "Alterações não salvas",
        "close_guard_body": "Existem alterações não salvas no editor ou tarefas de áudio ativas. Fechar esta janela mesmo assim?",
    },
    "nl": {
        "menu_file": "Bestand",
        "menu_edit": "Bewerken",
        "menu_view": "Beeld",
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
        "close_guard_title": "Niet-opgeslagen wijzigingen",
        "close_guard_body": "Er zijn niet-opgeslagen wijzigingen in de editor of actieve audiotaken. Dit venster toch sluiten?",
    },
}

CATALOG_BINDINGS: dict[str, str] = {
    "item_view_analysis": "cmd_view_analysis_title",
    "item_view_research": "cmd_view_research_title",
    "item_view_project": "cmd_view_project_title",
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
