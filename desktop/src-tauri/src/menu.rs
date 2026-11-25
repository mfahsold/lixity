//! Localized 7-language native OS menu bar built from `generated/menu-locales.json`.

use crate::recent::{list_recent, RecentProject};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::Path;
use tauri::menu::{Menu, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Runtime};

const MENU_LOCALES_JSON: &str = include_str!("../generated/menu-locales.json");
const MAX_MENU_RECENT: usize = 8;
pub(crate) const RECENT_MENU_PREFIX: &str = "recent-open-";

#[derive(Clone, Debug, Deserialize)]
pub struct MenuLabels {
    pub menu_file: String,
    pub menu_edit: String,
    pub menu_view: String,
    #[cfg(target_os = "macos")]
    pub menu_window: String,
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
    #[cfg(target_os = "macos")]
    pub item_about: String,
    #[cfg(target_os = "macos")]
    pub item_hide: String,
    #[cfg(target_os = "macos")]
    pub item_fullscreen: String,
    #[cfg(target_os = "macos")]
    pub item_minimize: String,
    pub close_guard_title: String,
    pub close_guard_body: String,
    pub close_guard_audio_unavailable: String,
    pub startup_runtime_missing: String,
    pub startup_runtime_failed: String,
    pub startup_window_failed: String,
    pub startup_logs_unavailable: String,
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

fn recent_menu_id(path: &str) -> String {
    format!("{RECENT_MENU_PREFIX}{:x}", Sha256::digest(path.as_bytes()))
}

pub(crate) fn recent_menu_path<'a>(id: &str, entries: &'a [RecentProject]) -> Option<&'a str> {
    entries
        .iter()
        .find(|entry| entry.exists && recent_menu_id(&entry.path) == id)
        .map(|entry| entry.path.as_str())
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
        for entry in recent_entries.iter().take(MAX_MENU_RECENT) {
            let label = recent_item_label(entry.title.as_deref(), &entry.path);
            let item = MenuItemBuilder::with_id(recent_menu_id(&entry.path), label)
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
                .accelerator("CmdOrCtrl+Shift+I")
                .build(app)?,
        )
        .separator()
        .item(
            &MenuItemBuilder::with_id("file-export-pdf", &l.item_export_pdf)
                .accelerator("CmdOrCtrl+Shift+E")
                .build(app)?,
        )
        .separator();
    #[cfg(target_os = "macos")]
    let file_menu = file_menu.item(&PredefinedMenuItem::close_window(app, Some(&l.close_guard_title))?);
    #[cfg(not(target_os = "macos"))]
    let file_menu = file_menu.item(&PredefinedMenuItem::quit(app, Some(&l.item_quit))?);
    let file_menu = file_menu.build()?;

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
        );
    #[cfg(target_os = "macos")]
    let view_menu = view_menu
        .separator()
        .item(&PredefinedMenuItem::fullscreen(app, Some(&l.item_fullscreen))?);
    let view_menu = view_menu.build()?;

    let tools_menu = SubmenuBuilder::new(app, &l.menu_tools)
        .item(&MenuItemBuilder::with_id("tools-system-status", &l.item_system_status).build(app)?)
        .item(&MenuItemBuilder::with_id("tools-open-logs", &l.item_open_logs).build(app)?)
        .build()?;

    let help_menu = SubmenuBuilder::new(app, &l.menu_help)
        .item(&MenuItemBuilder::with_id("help-documentation", &l.item_documentation).build(app)?)
        .separator()
        .item(&MenuItemBuilder::with_id("help-check-updates", &l.item_check_updates).build(app)?)
        .build()?;

    let menu = MenuBuilder::new(app);
    #[cfg(target_os = "macos")]
    let (menu, window_menu) = {
        let app_menu = SubmenuBuilder::new(app, "Lixity")
            .item(&PredefinedMenuItem::about(app, Some(&l.item_about), None)?)
            .separator()
            .item(&PredefinedMenuItem::hide(app, Some(&l.item_hide))?)
            .separator()
            .item(&PredefinedMenuItem::quit(app, Some(&l.item_quit))?)
            .build()?;
        let window_menu = SubmenuBuilder::new(app, &l.menu_window)
            .item(&PredefinedMenuItem::minimize(app, Some(&l.item_minimize))?)
            .build()?;
        (menu.item(&app_menu), window_menu)
    };
    let menu = menu.items(&[&file_menu, &edit_menu, &view_menu, &tools_menu]);
    #[cfg(target_os = "macos")]
    let menu = menu.item(&window_menu);
    let menu = menu.item(&help_menu).build()?;
    #[cfg(target_os = "macos")]
    {
        window_menu.set_as_windows_menu_for_nsapp()?;
        help_menu.set_as_help_menu_for_nsapp()?;
    }
    Ok(menu)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recent_menu_selection_keeps_its_path_after_reordering() {
        let entry = |path: &str, exists| RecentProject {
            path: path.to_owned(),
            title: None,
            language: None,
            last_opened_unix: 0,
            exists,
        };
        let id = recent_menu_id("/synthetic/first");
        let other = entry("/synthetic/newer", true);
        let selected = entry("/synthetic/first", true);
        assert_eq!(recent_menu_path(&id, &[other.clone(), selected]), Some("/synthetic/first"));
        assert_eq!(recent_menu_path(&id, std::slice::from_ref(&other)), None);
        assert_eq!(recent_menu_path(&id, &[entry("/synthetic/first", false)]), None);
    }

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
