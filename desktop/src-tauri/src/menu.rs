//! Localized 7-language native OS menu bar built from `generated/menu-locales.json`.

use crate::recent::list_recent;
use serde::Deserialize;
use std::collections::HashMap;
use std::path::Path;
use tauri::menu::{Menu, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Runtime};

const MENU_LOCALES_JSON: &str = include_str!("../generated/menu-locales.json");
const MAX_MENU_RECENT: usize = 8;

#[derive(Clone, Debug, Deserialize)]
pub struct MenuLabels {
    pub menu_file: String,
    pub menu_edit: String,
    pub menu_view: String,
    pub menu_tools: String,
    pub menu_help: String,
    pub item_new_window: String,
    pub item_open_project: String,
    pub item_recent_projects: String,
    pub item_recent_empty: String,
    pub item_import_manuscript: String,
    pub item_quit: String,
    pub item_undo: String,
    pub item_redo: String,
    pub item_cut: String,
    pub item_copy: String,
    pub item_paste: String,
    pub item_select_all: String,
    pub item_view_analysis: String,
    pub item_view_analysis_overview: String,
    pub item_view_research: String,
    pub item_view_project: String,
    pub item_toggle_theme: String,
    pub item_teleprompter: String,
    pub item_zoom_in: String,
    pub item_zoom_out: String,
    pub item_zoom_reset: String,
    pub item_export_pdf: String,
    pub item_system_status: String,
    pub item_open_logs: String,
    pub item_check_updates: String,
    pub item_documentation: String,
    pub close_guard_title: String,
    pub close_guard_body: String,
}

pub fn labels_for_locale(locale: &str) -> MenuLabels {
    let catalogs: HashMap<String, MenuLabels> =
        serde_json::from_str(MENU_LOCALES_JSON).expect("generated menu-locales.json must be valid");
    let short = locale
        .split(['-', '_'])
        .next()
        .unwrap_or("en")
        .to_ascii_lowercase();
    catalogs
        .get(&short)
        .or_else(|| catalogs.get("en"))
        .cloned()
        .expect("en fallback locale must exist")
}

fn recent_item_label(title: Option<&str>, path: &str) -> String {
    if let Some(t) = title.map(str::trim).filter(|t| !t.is_empty()) {
        return t.chars().take(64).collect();
    }
    Path::new(path)
        .file_name()
        .and_then(|n| n.to_str())
        .filter(|s| !s.is_empty())
        .unwrap_or(path)
        .chars()
        .take(64)
        .collect()
}

pub fn build_app_menu<R: Runtime>(app: &AppHandle<R>, locale: &str) -> tauri::Result<Menu<R>> {
    let l = labels_for_locale(locale);

    let recent_entries = list_recent();
    let mut recent_builder = SubmenuBuilder::new(app, &l.item_recent_projects);
    if recent_entries.is_empty() {
        let empty_item = MenuItemBuilder::with_id("recent-empty", &l.item_recent_empty)
            .enabled(false)
            .build(app)?;
        recent_builder = recent_builder.item(&empty_item);
    } else {
        for (idx, entry) in recent_entries.iter().take(MAX_MENU_RECENT).enumerate() {
            let label = recent_item_label(entry.title.as_deref(), &entry.path);
            let item = MenuItemBuilder::with_id(format!("recent-open-{idx}"), label)
                .enabled(entry.exists)
                .build(app)?;
            recent_builder = recent_builder.item(&item);
        }
    }
    let recent_submenu = recent_builder.build()?;

    let file_menu = SubmenuBuilder::new(app, &l.menu_file)
        .item(
            &MenuItemBuilder::with_id("file-new-window", &l.item_new_window)
                .accelerator("CmdOrCtrl+Shift+N")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("file-open-project", &l.item_open_project)
                .accelerator("CmdOrCtrl+O")
                .build(app)?,
        )
        .item(&recent_submenu)
        .item(
            &MenuItemBuilder::with_id("file-import-manuscript", &l.item_import_manuscript)
                .accelerator("CmdOrCtrl+I")
                .build(app)?,
        )
        .separator()
        .item(
            &MenuItemBuilder::with_id("file-export-pdf", &l.item_export_pdf)
                .accelerator("CmdOrCtrl+Shift+E")
                .build(app)?,
        )
        .separator()
        .item(&PredefinedMenuItem::quit(app, Some(&l.item_quit))?)
        .build()?;

    let edit_menu = SubmenuBuilder::new(app, &l.menu_edit)
        .item(&PredefinedMenuItem::undo(app, Some(&l.item_undo))?)
        .item(&PredefinedMenuItem::redo(app, Some(&l.item_redo))?)
        .separator()
        .item(&PredefinedMenuItem::cut(app, Some(&l.item_cut))?)
        .item(&PredefinedMenuItem::copy(app, Some(&l.item_copy))?)
        .item(&PredefinedMenuItem::paste(app, Some(&l.item_paste))?)
        .item(&PredefinedMenuItem::select_all(app, Some(&l.item_select_all))?)
        .build()?;

    let view_menu = SubmenuBuilder::new(app, &l.menu_view)
        .item(
            &MenuItemBuilder::with_id("view-analysis", &l.item_view_analysis)
                .accelerator("CmdOrCtrl+1")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-analysis-overview", &l.item_view_analysis_overview)
                .accelerator("CmdOrCtrl+Shift+A")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-research", &l.item_view_research)
                .accelerator("CmdOrCtrl+2")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-project", &l.item_view_project)
                .accelerator("CmdOrCtrl+3")
                .build(app)?,
        )
        .separator()
        .item(
            &MenuItemBuilder::with_id("view-teleprompter", &l.item_teleprompter)
                .accelerator("CmdOrCtrl+Shift+T")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-toggle-theme", &l.item_toggle_theme)
                .accelerator("CmdOrCtrl+Shift+D")
                .build(app)?,
        )
        .separator()
        .item(
            &MenuItemBuilder::with_id("view-zoom-in", &l.item_zoom_in)
                .accelerator("CmdOrCtrl+=")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-zoom-out", &l.item_zoom_out)
                .accelerator("CmdOrCtrl+-")
                .build(app)?,
        )
        .item(
            &MenuItemBuilder::with_id("view-zoom-reset", &l.item_zoom_reset)
                .accelerator("CmdOrCtrl+0")
                .build(app)?,
        )
        .build()?;

    let tools_menu = SubmenuBuilder::new(app, &l.menu_tools)
        .item(&MenuItemBuilder::with_id("tools-system-status", &l.item_system_status).build(app)?)
        .item(&MenuItemBuilder::with_id("tools-open-logs", &l.item_open_logs).build(app)?)
        .build()?;

    let help_menu = SubmenuBuilder::new(app, &l.menu_help)
        .item(&MenuItemBuilder::with_id("help-documentation", &l.item_documentation).build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("help-check-updates", &l.item_check_updates).build(app)?)
        .build()?;

    MenuBuilder::new(app)
        .items(&[&file_menu, &edit_menu, &view_menu, &tools_menu, &help_menu])
        .build()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_all_seven_locales_and_falls_back_to_english() {
        assert_eq!(labels_for_locale("de_DE.UTF-8").menu_file, "Datei");
        assert_eq!(
            labels_for_locale("de_DE.UTF-8").item_view_analysis_overview,
            "Analyseübersicht"
        );
        assert_eq!(
            labels_for_locale("en_US.UTF-8").item_view_analysis_overview,
            "Analysis overview"
        );
        assert_eq!(labels_for_locale("fr-CA").menu_file, "Fichier");
        assert_eq!(labels_for_locale("es_ES").menu_file, "Archivo");
        assert_eq!(labels_for_locale("it_IT").menu_file, "File");
        assert_eq!(labels_for_locale("pt_BR").menu_file, "Arquivo");
        assert_eq!(labels_for_locale("nl_NL").menu_file, "Bestand");
        assert_eq!(labels_for_locale("ja_JP").menu_file, "File");
        for loc in ["de", "en", "fr", "es", "it", "pt", "nl"] {
            let labels = labels_for_locale(loc);
            assert!(!labels.item_view_analysis_overview.trim().is_empty());
            assert!(!labels.item_toggle_theme.trim().is_empty());
        }
    }

    #[test]
    fn formats_recent_item_label_with_title_or_basename() {
        assert_eq!(recent_item_label(Some("My Novel"), "/tmp/book"), "My Novel");
        assert_eq!(recent_item_label(None, "/tmp/manuscripts/draft.md"), "draft.md");
    }
}
