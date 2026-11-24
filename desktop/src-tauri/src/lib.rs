//! Lixity cross-platform Rust desktop host (macOS, Windows, Linux).

pub mod audio_capture;
pub mod commands;
mod desktop_state;
pub mod dirty_state;
pub mod downloads;
pub mod menu;
pub mod preferences;
pub mod recent;
pub mod security;
pub mod sidecar;
pub mod updater;
mod window_chrome;
pub mod window_state;

use audio_capture::InteractiveRecorder;
use commands::{spawn_desktop_window, DesktopState, WindowLaunchSpec};
use dirty_state::{AudioJobStatus, CloseAttempt, CloseRequest, DirtyRegistry};
use downloads::RevealAllowlist;
use menu::{build_app_menu, labels_for_locale, MenuLabels};
use preferences::{load_preferences, step_zoom, DEFAULT_ZOOM, ZOOM_STEP};
use recent::list_recent;
use sidecar::{log_desktop_event, PythonSidecar};
use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tauri::{
    AppHandle, CloseRequestApi, DragDropEvent, Manager, RunEvent, State, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons, MessageDialogKind};
use tauri_plugin_opener::OpenerExt;
use window_state::{save_window_geometry, WindowGeometry};

#[cfg(all(target_os = "macos", feature = "webview-smoke"))]
pub mod webview_smoke;

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

#[derive(Default)]
struct OpenPathRequests(Mutex<VecDeque<(Option<String>, PathBuf)>>);

impl OpenPathRequests {
    fn enqueue(&self, label: Option<&str>, path: PathBuf) {
        self.0
            .lock()
            .unwrap()
            .push_back((label.map(str::to_owned), path));
    }

    fn take(&self, label: &str) -> Option<PathBuf> {
        let mut requests = self.0.lock().unwrap();
        let index = requests
            .iter()
            .position(|(target, _)| target.as_deref().is_none_or(|target| target == label))?;
        requests.remove(index).map(|(_, path)| path)
    }

    fn release_window(&self, label: &str) -> bool {
        let mut released = false;
        for (target, _) in self.0.lock().unwrap().iter_mut() {
            if target.as_deref() == Some(label) {
                *target = None;
                released = true;
            }
        }
        released
    }
}

fn notify_open_paths(window: &WebviewWindow) {
    let _ = window.eval("window.dispatchEvent(new Event('lixity:desktop-open-path'));");
}

fn queue_open_path(app: &AppHandle, preferred_label: Option<&str>, path: PathBuf) {
    let target = find_target_workspace_window(app, preferred_label);
    app.state::<OpenPathRequests>()
        .enqueue(target.as_ref().map(WebviewWindow::label), path);
    if let Some(window) = target {
        notify_open_paths(&window);
    }
}

#[tauri::command]
fn take_open_path(
    window: WebviewWindow,
    requests: State<'_, OpenPathRequests>,
    state: State<'_, DesktopState>,
) -> Option<String> {
    let path = requests.take(window.label())?;
    state.reveal.allow(&path);
    Some(path.to_string_lossy().into_owned())
}

fn dispatch_dom_event_to_window(
    app: &AppHandle,
    preferred_label: Option<&str>,
    event_name: &str,
    detail: &str,
) {
    if let Some(window) = find_target_workspace_window(app, preferred_label) {
        dispatch_desktop_event(&window, event_name, detail);
    }
}

fn dispatch_desktop_event(window: &WebviewWindow, event_name: &str, detail: impl serde::Serialize) {
    let Ok(encoded) = serde_json::to_string(&detail) else {
        return;
    };
    let _ = window.eval(format!(
        "window.dispatchEvent(new CustomEvent({event_name:?}, {{ detail: {encoded} }}));"
    ));
}

fn apply_menu_zoom(app: &AppHandle, factor: f64) {
    if commands::set_preference(app.clone(), "zoom".to_string(), serde_json::json!(factor)).is_err() {
        log_desktop_event("WARN", "Could not save the desktop zoom preference");
    }
}

#[derive(Debug)]
pub(crate) enum StartupFailure {
    RuntimeMissing,
    RuntimeLaunch(std::io::ErrorKind),
    RuntimeReadiness,
    WorkspaceWindow,
}

impl StartupFailure {
    fn message<'a>(&self, labels: &'a MenuLabels) -> &'a str {
        match self {
            Self::RuntimeMissing => &labels.startup_runtime_missing,
            Self::RuntimeLaunch(_) | Self::RuntimeReadiness => &labels.startup_runtime_failed,
            Self::WorkspaceWindow => &labels.startup_window_failed,
        }
    }

    fn diagnostic(&self) -> String {
        // Subprocess and WebView errors may include local paths or handshake URLs.
        let phase = match self {
            Self::RuntimeMissing => "runtime-files",
            Self::RuntimeLaunch(_) => "runtime-launch",
            Self::RuntimeReadiness => "runtime-readiness",
            Self::WorkspaceWindow => "workspace-window",
        };
        let mut entry = format!("event=desktop_startup_failed phase={phase}");
        if let Self::RuntimeLaunch(kind) = self {
            entry.push_str(&format!(" kind={kind:?}"));
        }
        entry
    }
}

fn show_fatal_startup_error(app: &AppHandle, locale: &str, failure: StartupFailure) {
    log_desktop_event("ERROR", &failure.diagnostic());
    let labels = labels_for_locale(locale);
    let dialog = app
        .dialog()
        .message(failure.message(&labels))
        .title("Lixity")
        .kind(MessageDialogKind::Error)
        .buttons(MessageDialogButtons::OkCancelCustom(
            labels.item_open_logs,
            labels.item_quit.clone(),
        ));
    let dialog = match app.get_webview_window("splashscreen") {
        Some(splash) => dialog.parent(&splash),
        None => dialog,
    };
    let handle = app.clone();
    dialog.show(move |open_logs| {
        if open_logs && commands::open_logs_folder(handle.clone()).is_err() {
            log_desktop_event("WARN", "event=desktop_startup_logs_unavailable");
            let exit_handle = handle.clone();
            handle
                .dialog()
                .message(labels.startup_logs_unavailable)
                .title("Lixity")
                .kind(MessageDialogKind::Error)
                .buttons(MessageDialogButtons::OkCustom(labels.item_quit))
                .show(move |_| exit_handle.exit(1));
        } else {
            handle.exit(1);
        }
    });
}

fn handle_menu_event(app: &AppHandle, id: &str) {
    if let Some(idx_str) = id.strip_prefix("recent-open-") {
        if let Ok(idx) = idx_str.parse::<usize>() {
            if let Some(entry) = list_recent().get(idx) {
                let path = PathBuf::from(&entry.path);
                if path.exists() {
                    queue_open_path(app, None, path);
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

#[derive(Debug, PartialEq, Eq)]
enum CloseAction {
    Close,
    CheckAudio,
    ConfirmWork,
    ConfirmUnavailableAudio,
}

fn close_action(
    window_has_work: bool,
    other_workspace_remains: bool,
    audio_status: Option<AudioJobStatus>,
) -> CloseAction {
    if window_has_work {
        return CloseAction::ConfirmWork;
    }
    if other_workspace_remains {
        return CloseAction::Close;
    }
    match audio_status {
        None => CloseAction::CheckAudio,
        Some(AudioJobStatus::Idle) => CloseAction::Close,
        Some(AudioJobStatus::Active) => CloseAction::ConfirmWork,
        Some(AudioJobStatus::Unavailable) => CloseAction::ConfirmUnavailableAudio,
    }
}

fn resume_after_audio_check(window: tauri::Window, state: &DesktopState, attempt: CloseAttempt) {
    let sidecar = Arc::clone(&state.sidecar);
    let dirty = Arc::clone(&state.dirty);
    tauri::async_runtime::spawn(async move {
        let check = tauri::async_runtime::spawn_blocking(move || sidecar.has_active_audio_jobs());
        let status = match check.await {
            Ok(Some(false)) => AudioJobStatus::Idle,
            Ok(Some(true)) => AudioJobStatus::Active,
            Ok(None) | Err(_) => AudioJobStatus::Unavailable,
        };
        // Replay the close event so it evaluates the current editor, recording and windows.
        if dirty.audio_checked(window.label(), &attempt, status) && window.close().is_err() {
            dirty.cancel_close(window.label(), &attempt);
        }
    });
}

fn confirm_window_close(
    window: &tauri::Window,
    state: &DesktopState,
    attempt: CloseAttempt,
    audio_unavailable: bool,
) {
    let labels = labels_for_locale(&state.locale);
    let message = if audio_unavailable {
        labels.close_guard_audio_unavailable
    } else {
        labels.close_guard_body
    };
    let closing_window = window.clone();
    let dirty = Arc::clone(&state.dirty);
    window
        .dialog()
        .message(message)
        .title(labels.close_guard_title)
        .kind(MessageDialogKind::Warning)
        .buttons(MessageDialogButtons::OkCancel)
        .parent(window)
        .show(move |confirmed| {
            let label = closing_window.label();
            if confirmed {
                if dirty.confirm_close(label, &attempt) && closing_window.close().is_err() {
                    dirty.cancel_close(label, &attempt);
                }
            } else {
                dirty.cancel_close(label, &attempt);
            }
        });
}

fn handle_close_request(window: &tauri::Window, api: &CloseRequestApi) {
    let Some(state) = window.try_state::<DesktopState>() else {
        return;
    };
    let label = window.label();
    let (attempt, audio_status) = match state.dirty.request_close(label) {
        CloseRequest::Evaluate(attempt, audio_status) => (attempt, audio_status),
        CloseRequest::Authorized => {
            persist_main_window_geometry(window);
            return;
        }
        CloseRequest::KeepOpen => {
            api.prevent_close();
            return;
        }
    };
    let window_has_work = state.dirty.is_window_dirty(label) || state.recorder.owns_capture(label);
    let other_workspace_remains =
        window.app_handle().webview_windows().keys().any(|other| {
            other != label && other != "splashscreen" && !state.dirty.is_closing(other)
        });
    let action = close_action(window_has_work, other_workspace_remains, audio_status);
    match action {
        CloseAction::Close => {
            if state.dirty.commit_close(label, &attempt) {
                persist_main_window_geometry(window);
            } else {
                api.prevent_close();
            }
        }
        CloseAction::CheckAudio => {
            api.prevent_close();
            resume_after_audio_check(window.clone(), &state, attempt);
        }
        CloseAction::ConfirmWork | CloseAction::ConfirmUnavailableAudio => {
            api.prevent_close();
            confirm_window_close(
                window,
                &state,
                attempt,
                action == CloseAction::ConfirmUnavailableAudio,
            );
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
                queue_open_path(window.app_handle(), Some(window.label()), target.clone());
            }
        }
        WindowEvent::CloseRequested { api, .. } => handle_close_request(window, api),
        #[cfg(target_os = "macos")]
        WindowEvent::ThemeChanged(theme) => {
            let _ = window.set_background_color(window_chrome::backdrop(*theme));
        }
        WindowEvent::Destroyed => {
            if let Some(state) = window.try_state::<DesktopState>() {
                state.recorder.discard_window(window.label());
                state.dirty.remove_window(window.label());
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

fn desktop_context() -> tauri::Context<tauri::Wry> {
    tauri::generate_context!()
}

pub fn run() {
    let locale = detect_system_locale();
    let app_version = env!("CARGO_PKG_VERSION").to_string();

    let app = tauri::Builder::default()
        .manage(OpenPathRequests::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_single_instance::init(|app, argv, cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
            if let Some(path) = argv
                .iter()
                .skip(1)
                .map(|argument| Path::new(&cwd).join(argument))
                .find(|p| is_openable_project_path(p))
            {
                queue_open_path(app, None, path);
            }
        }))
        .invoke_handler(tauri::generate_handler![
            take_open_path,
            commands::pick_project_directory,
            commands::pick_import_file,
            commands::read_sample_manuscript,
            commands::save_blob,
            commands::save_export_stream,
            commands::open_project_window,
            commands::open_logs_folder,
            commands::open_external_url,
            commands::reveal_in_file_manager,
            commands::set_dirty_state,
            commands::set_workspace_title,
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
            app.set_theme(window_chrome::preferred_theme(load_preferences().theme.as_deref()));
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
                        let startup_locale = locale.clone();

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
                                Err(_) => {
                                    show_fatal_startup_error(
                                        &main_handle,
                                        &startup_locale,
                                        StartupFailure::WorkspaceWindow,
                                    );
                                }
                            }
                        });
                    }
                    Err(failure) => {
                        show_fatal_startup_error(&handle, &locale, failure);
                    }
                }
            });

            Ok(())
        })
        .on_menu_event(|app, event| handle_menu_event(app, event.id().as_ref()))
        .on_window_event(handle_window_event)
        .build(desktop_context())
        .expect("error while building Lixity desktop host");

    app.run(|app_handle, event| match event {
        #[cfg(target_os = "macos")]
        RunEvent::Opened { urls } => {
            let mut queued = false;
            for url in urls {
                if let Ok(path) = url.to_file_path() {
                    if is_openable_project_path(&path) {
                        queue_open_path(app_handle, None, path);
                        queued = true;
                    }
                }
            }
            if queued && app_handle.webview_windows().is_empty() {
                open_fresh_window_async(app_handle.clone(), Some("main"));
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
        RunEvent::WindowEvent {
            label,
            event: WindowEvent::Destroyed,
            ..
        } => {
            if app_handle
                .state::<OpenPathRequests>()
                .release_window(&label)
            {
                if let Some(window) = find_target_workspace_window(app_handle, None) {
                    notify_open_paths(&window);
                }
            }
        }
        RunEvent::Exit => {
            if let Some(state) = app_handle.try_state::<DesktopState>() {
                state.recorder.cancel_all();
                state.sidecar.shutdown();
            }
        }
        _ => {}
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_failures_have_localized_recovery_and_fixed_diagnostics() {
        use std::io::ErrorKind;

        let cases = [
            (StartupFailure::RuntimeMissing, "runtime-files"),
            (
                StartupFailure::RuntimeLaunch(ErrorKind::PermissionDenied),
                "runtime-launch kind=PermissionDenied",
            ),
            (StartupFailure::RuntimeReadiness, "runtime-readiness"),
            (StartupFailure::WorkspaceWindow, "workspace-window"),
        ];
        let english = labels_for_locale("en");
        for (failure, phase) in cases {
            assert_eq!(
                failure.diagnostic(),
                format!("event=desktop_startup_failed phase={phase}")
            );
            for locale in ["de-DE", "fr-FR", "es-ES", "it-IT", "pt-PT", "nl-NL"] {
                let labels = labels_for_locale(locale);
                assert!(!failure.message(&labels).is_empty());
                assert_ne!(failure.message(&labels), failure.message(&english));
                assert!(!labels.startup_logs_unavailable.is_empty());
            }
        }
    }

    #[test]
    fn cold_open_paths_wait_for_the_workspace_and_survive_its_redirect() {
        let requests = OpenPathRequests::default();
        requests.enqueue(None, PathBuf::from("Cold launch/lixity.toml"));
        requests.enqueue(None, PathBuf::from("Second manuscript.md"));

        assert_eq!(
            requests.take("main"),
            Some(PathBuf::from("Cold launch/lixity.toml"))
        );
        assert_eq!(
            requests.take("main"),
            Some(PathBuf::from("Second manuscript.md"))
        );
        assert_eq!(requests.take("main"), None);
    }

    #[test]
    fn open_request_uses_the_target_workspace_or_moves_when_it_closes() {
        let requests = OpenPathRequests::default();
        requests.enqueue(Some("project-1"), PathBuf::from("Pending.md"));

        assert_eq!(requests.take("main"), None);
        assert!(requests.release_window("project-1"));
        assert_eq!(requests.take("main"), Some(PathBuf::from("Pending.md")));
        assert!(!requests.release_window("project-1"));
    }

    #[test]
    fn final_window_waits_for_audio_status_and_rechecks_its_own_work() {
        assert_eq!(close_action(false, false, None), CloseAction::CheckAudio);
        assert_eq!(
            close_action(false, false, Some(AudioJobStatus::Idle)),
            CloseAction::Close
        );
        assert_eq!(
            close_action(true, false, Some(AudioJobStatus::Idle)),
            CloseAction::ConfirmWork
        );
        assert_eq!(
            close_action(false, false, Some(AudioJobStatus::Active)),
            CloseAction::ConfirmWork
        );
        assert_eq!(
            close_action(false, false, Some(AudioJobStatus::Unavailable)),
            CloseAction::ConfirmUnavailableAudio
        );
    }

    #[test]
    fn other_workspaces_keep_audio_jobs_running_but_do_not_cover_local_work() {
        assert_eq!(close_action(false, true, None), CloseAction::Close);
        assert_eq!(
            close_action(false, true, Some(AudioJobStatus::Active)),
            CloseAction::Close
        );
        assert_eq!(close_action(true, true, None), CloseAction::ConfirmWork);
    }
}
