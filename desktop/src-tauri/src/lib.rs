//! Lixity cross-platform Rust desktop host (macOS, Windows, Linux).

pub mod audio_capture;
pub mod commands;
pub mod dirty_state;
pub mod downloads;
pub mod menu;
pub mod preferences;
pub mod recent;
pub mod security;
pub mod sidecar;
pub mod updater;
pub mod window_state;

use audio_capture::InteractiveRecorder;
use commands::{spawn_desktop_window, DesktopState, WindowLaunchSpec};
use dirty_state::DirtyRegistry;
use downloads::RevealAllowlist;
use menu::{build_app_menu, labels_for_locale};
use preferences::{load_preferences, step_zoom, DEFAULT_ZOOM, ZOOM_STEP};
use recent::list_recent;
use sidecar::{log_desktop_event, PythonSidecar};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tauri::{
    AppHandle, DragDropEvent, Manager, RunEvent, WebviewUrl, WebviewWindow, WebviewWindowBuilder,
    WindowEvent,
};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_opener::OpenerExt;
use window_state::{save_window_geometry, WindowGeometry};

fn detect_system_locale() -> String {
    for key in ["LIXITY_LANG", "LC_ALL", "LC_MESSAGES", "LANG"] {
        if let Ok(val) = std::env::var(key) {
            let trimmed = val.trim();
            if !trimmed.is_empty() && trimmed != "C" && trimmed != "POSIX" {
                return trimmed.to_string();
            }
        }
    }
    "en".to_string()
}

fn startup_project_from_args() -> Option<PathBuf> {
    std::env::args_os()
        .skip(1)
        .map(PathBuf::from)
        .find(|p| is_openable_project_path(p))
}

fn is_openable_project_path(path: &Path) -> bool {
    if !path.exists() {
        return false;
    }
    if path.is_dir() {
        return true;
    }
    if path.file_name().and_then(|n| n.to_str()) == Some("lixity.toml") {
        return true;
    }
    matches!(
        path.extension()
            .and_then(|e| e.to_str())
            .map(str::to_ascii_lowercase)
            .as_deref(),
        Some("md" | "markdown" | "txt")
    )
}

fn find_target_workspace_window(
    app: &AppHandle,
    preferred_label: Option<&str>,
) -> Option<WebviewWindow> {
    let windows = app.webview_windows();
    preferred_label
        .filter(|label| *label != "splashscreen")
        .and_then(|label| windows.get(label))
        .or_else(|| {
            windows
                .values()
                .find(|w| w.label() != "splashscreen" && w.is_focused().unwrap_or(false))
        })
        .or_else(|| windows.get("main"))
        .or_else(|| windows.values().find(|w| w.label() != "splashscreen"))
        .cloned()
}

fn dispatch_dom_event_to_window(
    app: &AppHandle,
    preferred_label: Option<&str>,
    event_name: &str,
    detail: &str,
) {
    let Ok(encoded) = serde_json::to_string(detail) else {
        return;
    };
    let script = format!(
        "window.dispatchEvent(new CustomEvent({event_name:?}, {{ detail: {encoded} }}));"
    );
    if let Some(window) = find_target_workspace_window(app, preferred_label) {
        let _ = window.eval(&script);
    }
}

fn apply_menu_zoom(app: &AppHandle, factor: f64) {
    if commands::set_preference(app.clone(), "zoom".to_string(), serde_json::json!(factor)).is_err() {
        log_desktop_event("WARN", "Could not save the desktop zoom preference");
    }
}

fn show_fatal_startup_error(app: &AppHandle, summary: &str, err: &str) {
    log_desktop_event("ERROR", summary);
    let dialog = app
        .dialog()
        .message(format!("{summary}:\n\n{err}"))
        .title("Lixity")
        .kind(MessageDialogKind::Error);
    let dialog = match app.get_webview_window("splashscreen") {
        Some(splash) => dialog.parent(&splash),
        None => dialog,
    };
    let handle = app.clone();
    dialog.show(move |_| handle.exit(1));
}

fn handle_menu_event(app: &AppHandle, id: &str) {
    if let Some(idx_str) = id.strip_prefix("recent-open-") {
        if let Ok(idx) = idx_str.parse::<usize>() {
            if let Some(entry) = list_recent().get(idx) {
                let path = PathBuf::from(&entry.path);
                if path.exists() {
                    if let Some(state) = app.try_state::<DesktopState>() {
                        state.reveal.allow(&path);
                    }
                    dispatch_dom_event_to_window(
                        app,
                        None,
                        "lixity:desktop-open-path",
                        &entry.path,
                    );
                }
            }
        }
        return;
    }
    match id {
        "help-documentation" => {
            let _ = app
                .opener()
                .open_url("https://mfahsold.github.io/lixity/", None::<&str>);
        }
        "tools-open-logs" => {
            let _ = commands::open_logs_folder(app.clone());
        }
        "file-new-window" => {
            open_fresh_window_async(app.clone(), None);
        }
        "view-zoom-in" => {
            let next = step_zoom(load_preferences().zoom, ZOOM_STEP);
            apply_menu_zoom(app, next);
        }
        "view-zoom-out" => {
            let next = step_zoom(load_preferences().zoom, -ZOOM_STEP);
            apply_menu_zoom(app, next);
        }
        "view-zoom-reset" => {
            apply_menu_zoom(app, DEFAULT_ZOOM);
        }
        _ => {
            dispatch_dom_event_to_window(app, None, "lixity:desktop-menu", id);
        }
    }
}

fn handle_window_event(window: &tauri::Window, event: &WindowEvent) {
    if window.label() == "splashscreen" {
        return;
    }
    match event {
        WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) => {
            if let Some(target) = paths.iter().find(|p| is_openable_project_path(p)) {
                if let Some(state) = window.try_state::<DesktopState>() {
                    state.reveal.allow(target);
                }
                dispatch_dom_event_to_window(
                    window.app_handle(),
                    Some(window.label()),
                    "lixity:desktop-open-path",
                    &target.display().to_string(),
                );
            }
        }
        WindowEvent::CloseRequested { api, .. } => {
            persist_main_window_geometry(window);
            let Some(state) = window.try_state::<DesktopState>() else {
                return;
            };
            let label = window.label().to_string();
            if state.dirty.take_force_closing(&label) {
                state.dirty.remove_window(&label);
                return;
            }
            if state.dirty.awaiting_close_confirmation(&label) {
                api.prevent_close();
                return;
            }
            let is_dirty = state.dirty.is_window_dirty(&label);
            let workspace_windows = window
                .app_handle()
                .webview_windows()
                .keys()
                .filter(|k| k.as_str() != "splashscreen")
                .count();
            let active_jobs = if workspace_windows <= 1 {
                state.sidecar.active_audio_jobs()
            } else {
                0
            };
            if is_dirty || active_jobs > 0 {
                api.prevent_close();
                if !state.dirty.begin_close_confirmation(&label) {
                    return;
                }
                let labels = labels_for_locale(&state.locale);
                let closing_window = window.clone();
                let dirty = Arc::clone(&state.dirty);
                window
                    .dialog()
                    .message(labels.close_guard_body)
                    .title(labels.close_guard_title)
                    .kind(MessageDialogKind::Warning)
                    .buttons(MessageDialogButtons::OkCancel)
                    .parent(window)
                    .show(move |confirmed| {
                        dirty.finish_close_confirmation(&label, confirmed);
                        if confirmed && closing_window.close().is_err() {
                            dirty.finish_close_confirmation(&label, false);
                        }
                    });
            } else {
                state.dirty.remove_window(&label);
            }
        }
        _ => {}
    }
}

fn persist_main_window_geometry(window: &tauri::Window) {
    if window.label() != "main" {
        return;
    }
    let scale = window.scale_factor().unwrap_or(1.0).max(0.5);
    let maximized = window.is_maximized().unwrap_or(false);
    let Ok(size) = window.inner_size() else {
        return;
    };
    let logical_size = size.to_logical::<f64>(scale);
    let (x, y) = window
        .outer_position()
        .ok()
        .map(|pos| {
            let logical = pos.to_logical::<f64>(scale);
            (Some(logical.x), Some(logical.y))
        })
        .unwrap_or((None, None));
    save_window_geometry(WindowGeometry {
        schema_version: String::new(),
        width: logical_size.width,
        height: logical_size.height,
        x,
        y,
        maximized,
    });
}

fn open_fresh_window_async(app: AppHandle, explicit_label: Option<&'static str>) {
    tauri::async_runtime::spawn(async move {
        if let Some(state) = app.try_state::<DesktopState>() {
            let sidecar = Arc::clone(&state.sidecar);
            let version = state.app_version.clone();
            let port = state.sidecar.port;
            if let Ok(Ok(nonce)) =
                tauri::async_runtime::spawn_blocking(move || sidecar.mint_handshake_nonce()).await
            {
                let _ = spawn_desktop_window(
                    &app,
                    WindowLaunchSpec {
                        port,
                        nonce: &nonce,
                        workspace_url: "/",
                        title: "Lixity",
                        app_version: &version,
                        explicit_label,
                    },
                );
            }
        }
    });
}

pub fn run() {
    let locale = detect_system_locale();
    let app_version = env!("CARGO_PKG_VERSION").to_string();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
            if let Some(path) = argv
                .iter()
                .skip(1)
                .map(PathBuf::from)
                .find(|p| is_openable_project_path(p))
            {
                if let Some(state) = app.try_state::<DesktopState>() {
                    state.reveal.allow(&path);
                }
                dispatch_dom_event_to_window(
                    app,
                    None,
                    "lixity:desktop-open-path",
                    &path.display().to_string(),
                );
            }
        }))
        .invoke_handler(tauri::generate_handler![
            commands::pick_project_directory,
            commands::pick_import_file,
            commands::save_blob,
            commands::save_export_stream,
            commands::open_project_window,
            commands::open_logs_folder,
            commands::open_external_url,
            commands::reveal_in_file_manager,
            commands::set_dirty_state,
            commands::list_recent_projects,
            commands::record_recent_project,
            commands::remove_recent_project,
            commands::clear_recent_projects,
            commands::get_preferences,
            commands::set_preference,
            commands::check_for_updates,
            commands::audio_capture_list_devices,
            commands::audio_capture_calibrate,
            commands::audio_capture_record_take,
            commands::audio_capture_start_recording,
            commands::audio_capture_status,
            commands::audio_capture_stop_recording,
            commands::audio_capture_cancel_recording,
        ])
        .setup(move |app| {
            let app_menu = build_app_menu(app.handle(), &locale)?;
            app.set_menu(app_menu)?;

            // Show an instant, zero-IPC frameless splash screen while the local
            // Python 3.12 engine boots on a background thread.
            let _ = WebviewWindowBuilder::new(
                app,
                "splashscreen",
                WebviewUrl::App("splash.html".into()),
            )
            .title("Lixity")
            .inner_size(420.0, 250.0)
            .resizable(false)
            .decorations(false)
            .center()
            .build();

            let handle = app.handle().clone();
            let resource_dir = app.path().resource_dir().ok();
            let startup_project = startup_project_from_args();

            std::thread::spawn(move || {
                match PythonSidecar::spawn(resource_dir.as_deref(), startup_project.as_deref()) {
                    Ok(started) => {
                        let sidecar = Arc::new(started);
                        let dirty = Arc::new(DirtyRegistry::default());
                        let reveal = Arc::new(RevealAllowlist::default());
                        let recorder = Arc::new(InteractiveRecorder::default());
                        if let Some(ref project) = startup_project {
                            reveal.allow(project);
                        }

                        let port = sidecar.port;
                        let initial_nonce = sidecar.initial_nonce.as_str().to_string();

                        handle.manage(DesktopState {
                            sidecar,
                            dirty,
                            reveal,
                            recorder,
                            app_version: app_version.clone(),
                            locale,
                        });

                        let main_handle = handle.clone();
                        let _ = handle.run_on_main_thread(move || {
                            let launch = spawn_desktop_window(
                                &main_handle,
                                WindowLaunchSpec {
                                    port,
                                    nonce: &initial_nonce,
                                    workspace_url: "/",
                                    title: "Lixity",
                                    app_version: &app_version,
                                    explicit_label: Some("main"),
                                },
                            );
                            match launch {
                                Ok(main_window) => {
                                    if let Some(splash) =
                                        main_handle.get_webview_window("splashscreen")
                                    {
                                        let _ = splash.close();
                                    }
                                    let _ = main_window.set_focus();
                                }
                                Err(err) => {
                                    show_fatal_startup_error(
                                        &main_handle,
                                        "Lixity could not open its workspace window",
                                        &err,
                                    );
                                }
                            }
                        });
                    }
                    Err(err) => {
                        show_fatal_startup_error(
                            &handle,
                            "Lixity could not start its local analysis engine",
                            &err,
                        );
                    }
                }
            });

            Ok(())
        })
        .on_menu_event(|app, event| handle_menu_event(app, event.id().as_ref()))
        .on_window_event(handle_window_event)
        .build(tauri::generate_context!())
        .expect("error while building Lixity desktop host");

    app.run(|app_handle, event| match event {
        #[cfg(target_os = "macos")]
        RunEvent::Opened { urls } => {
            for url in urls {
                if let Ok(path) = url.to_file_path() {
                    if is_openable_project_path(&path) {
                        if let Some(state) = app_handle.try_state::<DesktopState>() {
                            state.reveal.allow(&path);
                        }
                        dispatch_dom_event_to_window(
                            app_handle,
                            None,
                            "lixity:desktop-open-path",
                            &path.display().to_string(),
                        );
                    }
                }
            }
        }
        #[cfg(target_os = "macos")]
        RunEvent::Reopen {
            has_visible_windows,
            ..
        } => {
            if !has_visible_windows {
                open_fresh_window_async(app_handle.clone(), Some("main"));
            }
        }
        RunEvent::Exit => {
            if let Some(state) = app_handle.try_state::<DesktopState>() {
                state.recorder.cancel();
                state.sidecar.shutdown();
            }
        }
        _ => {}
    });
}
