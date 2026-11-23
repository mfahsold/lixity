//! Lixity cross-platform Rust desktop host (macOS, Windows, Linux).

pub mod audio_capture;
pub mod commands;
pub mod dirty_state;
pub mod downloads;
pub mod menu;
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
use recent::list_recent;
use sidecar::PythonSidecar;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tauri::{AppHandle, DragDropEvent, Manager, RunEvent, WindowEvent};
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
    let windows = app.webview_windows();
    let target = preferred_label
        .and_then(|label| windows.get(label))
        .or_else(|| windows.values().find(|w| w.is_focused().unwrap_or(false)))
        .or_else(|| windows.get("main"))
        .or_else(|| windows.values().next());
    if let Some(window) = target {
        let _ = window.eval(&script);
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
            let resource_dir = app.path().resource_dir().ok();
            let startup_project = startup_project_from_args();
            let sidecar = match PythonSidecar::spawn(
                resource_dir.as_deref(),
                startup_project.as_deref(),
            ) {
                Ok(started) => Arc::new(started),
                Err(err) => {
                    app.dialog()
                        .message(format!(
                            "Lixity could not start its local analysis engine:\n\n{err}"
                        ))
                        .title("Lixity")
                        .kind(MessageDialogKind::Error)
                        .blocking_show();
                    return Err(std::io::Error::other(err).into());
                }
            };
            let dirty = Arc::new(DirtyRegistry::default());
            let reveal = Arc::new(RevealAllowlist::default());
            let recorder = Arc::new(InteractiveRecorder::default());
            if let Some(ref project) = startup_project {
                reveal.allow(project);
            }

            let port = sidecar.port;
            let initial_nonce = sidecar.initial_nonce.as_str().to_string();

            app.manage(DesktopState {
                sidecar: Arc::clone(&sidecar),
                dirty: Arc::clone(&dirty),
                reveal: Arc::clone(&reveal),
                recorder: Arc::clone(&recorder),
                app_version: app_version.clone(),
                locale: locale.clone(),
            });

            let app_menu = build_app_menu(app.handle(), &locale)?;
            app.set_menu(app_menu)?;

            spawn_desktop_window(
                app.handle(),
                WindowLaunchSpec {
                    port,
                    nonce: &initial_nonce,
                    workspace_url: "/",
                    title: "Lixity",
                    app_version: &app_version,
                    explicit_label: Some("main"),
                },
            )
            .map_err(std::io::Error::other)?;

            Ok(())
        })
        .on_menu_event(|app, event| {
            let id = event.id().as_ref();
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
                _ => {
                    dispatch_dom_event_to_window(app, None, "lixity:desktop-menu", id);
                }
            }
        })
        .on_window_event(|window, event| match event {
            WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) => {
                if let Some(target) = paths.iter().find(|p| is_openable_project_path(p)) {
                    let state = window.state::<DesktopState>();
                    state.reveal.allow(target);
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
                let state = window.state::<DesktopState>();
                let label = window.label().to_string();
                if state.dirty.take_force_closing(&label) {
                    state.dirty.remove_window(&label);
                    return;
                }
                let is_dirty = state.dirty.is_window_dirty(&label);
                let active_jobs = if window.app_handle().webview_windows().len() <= 1 {
                    state.sidecar.active_audio_jobs()
                } else {
                    0
                };
                if is_dirty || active_jobs > 0 {
                    api.prevent_close();
                    let labels = labels_for_locale(&state.locale);
                    let confirmed = window
                        .dialog()
                        .message(labels.close_guard_body)
                        .title(labels.close_guard_title)
                        .kind(MessageDialogKind::Warning)
                        .buttons(MessageDialogButtons::OkCancel)
                        .blocking_show();
                    if confirmed {
                        state.dirty.mark_force_closing(&label);
                        let _ = window.close();
                    }
                } else {
                    state.dirty.remove_window(&label);
                }
            }
            _ => {}
        })
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
