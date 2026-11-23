//! Localized 7-language native OS menu bar built from `generated/menu-locales.json`.

use serde::Deserialize;
use std::collections::HashMap;
use tauri::menu::{Menu, MenuBuilder, MenuItemBuilder, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Runtime};

const MENU_LOCALES_JSON: &str = include_str!("../generated/menu-locales.json");

#[derive(Clone, Debug, Deserialize)]
pub struct MenuLabels {
    pub menu_file: String,
    pub menu_edit: String,
    pub menu_view: String,
    pub menu_tools: String,
    pub menu_help: String,
    pub item_new_window: String,
    pub item_open_project: String,
    pub item_import_manuscript: String,
    pub item_quit: String,
    pub item_undo: String,
    pub item_redo: String,
    pub item_cut: String,
    pub item_copy: String,
    pub item_paste: String,
    pub item_select_all: String,
    pub item_view_analysis: String,
    pub item_view_research: String,
    pub item_view_project: String,
    pub item_teleprompter: String,
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

pub fn build_app_menu<R: Runtime>(app: &AppHandle<R>, locale: &str) -> tauri::Result<Menu<R>> {
    let l = labels_for_locale(locale);

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
