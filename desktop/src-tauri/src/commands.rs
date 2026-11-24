//! Audited Tauri IPC commands exposed through the frozen `window.lixityDesktop` bridge.

use crate::audio_capture::{
    calibrate_microphone, list_input_devices, record_wav_take, CalibrationReport,
    CaptureDeviceInfo, InteractiveRecorder, RecordedTakeResult, RecordingLiveStatus,
};
use crate::dirty_state::DirtyRegistry;
use crate::downloads::{
    sanitize_suggested_filename, stream_loopback_export, write_base64_blob, ExportError,
    ExportRequestSpec, RevealAllowlist, SaveOutcome,
};
use crate::menu::build_app_menu;
use crate::preferences::{load_preferences, update_preference, DesktopPreferences, DEFAULT_ZOOM};
use crate::recent::{clear_recent, import_legacy_recent, record_recent, remove_recent, RecentProject};
use crate::security::{
    bridge_init_script, handshake_url, is_allowed_external_url, is_valid_workspace_path,
    route_webview_navigation,
};
use crate::sidecar::{sidecar_log_dir, PythonSidecar};
use crate::updater::{check_latest_release, UpdateCheckResult};
use crate::window_chrome::{preferred_theme, workspace_title};
use crate::window_state::{load_window_geometry, DEFAULT_HEIGHT, DEFAULT_WIDTH, MIN_HEIGHT, MIN_WIDTH};
use serde::Serialize;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tauri::webview::NewWindowResponse;
use tauri::{AppHandle, Manager, State, Url, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, FilePath};
use tauri_plugin_opener::OpenerExt;

static WINDOW_COUNTER: AtomicU64 = AtomicU64::new(1);

pub struct DesktopState {
    pub sidecar: Arc<PythonSidecar>,
    pub dirty: Arc<DirtyRegistry>,
    pub reveal: Arc<RevealAllowlist>,
    pub recorder: Arc<InteractiveRecorder>,
    pub app_version: String,
    pub locale: String,
}

#[derive(Debug, Serialize)]
pub struct PickedPath {
    pub path: String,
}

#[derive(Serialize)]
pub struct SampleManuscript {
    filename: &'static str,
    language: &'static str,
    content: &'static str,
}

pub struct WindowLaunchSpec<'a> {
    pub port: u16,
    pub nonce: &'a str,
    pub workspace_url: &'a str,
    pub title: &'a str,
    pub app_version: &'a str,
    pub explicit_label: Option<&'a str>,
}

fn file_path_to_pathbuf(fp: FilePath) -> Result<PathBuf, String> {
    fp.into_path()
        .map_err(|_| "Selected OS path could not be converted to a local filesystem path".to_string())
}

fn refresh_app_menu(app: &AppHandle, locale: &str) {
    if let Ok(app_menu) = build_app_menu(app, locale) {
        let _ = app.set_menu(app_menu);
    }
}

#[tauri::command]
pub async fn pick_project_directory(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<Option<PickedPath>, String> {
    let picked = app.dialog().file().blocking_pick_folder();
    match picked {
        Some(fp) => {
            let path = file_path_to_pathbuf(fp)?;
            state.reveal.allow(&path);
            Ok(Some(PickedPath {
                path: path.display().to_string(),
            }))
        }
        None => Ok(None),
    }
}

#[tauri::command]
pub async fn pick_import_file(
    app: AppHandle,
    kind: String,
) -> Result<Option<PickedPath>, String> {
    let (filter_name, extensions): (&str, &[&str]) = match kind.as_str() {
        "pdf" => ("PDF Document", &["pdf"]),
        "audio" => ("WAV Audio", &["wav"]),
        "notes" => ("Lixity Reader Notes", &["json"]),
        _ => ("Manuscript Files", &["md", "markdown", "txt", "docx"]),
    };
    let picked = app
        .dialog()
        .file()
        .add_filter(filter_name, extensions)
        .blocking_pick_file();
    match picked {
        Some(fp) => {
            let path = file_path_to_pathbuf(fp)?;
            Ok(Some(PickedPath {
                path: path.display().to_string(),
            }))
        }
        None => Ok(None),
    }
}

#[tauri::command]
pub fn read_sample_manuscript() -> SampleManuscript {
    SampleManuscript {
        filename: "first-look.md",
        language: "en",
        content: include_str!("../../../samples/first-look.md"),
    }
}

#[tauri::command]
pub async fn save_blob(
    app: AppHandle,
    state: State<'_, DesktopState>,
    filename: String,
    payload_base64: String,
) -> Result<SaveOutcome, String> {
    let suggested = sanitize_suggested_filename(&filename);
    let chosen = app.dialog().file().set_file_name(&suggested).blocking_save_file();
    let Some(fp) = chosen else {
        return Ok(SaveOutcome::cancelled());
    };
    let dest = file_path_to_pathbuf(fp)?;
    let outcome = write_base64_blob(&payload_base64, &dest)?;
    state.reveal.allow(&dest);
    Ok(outcome)
}

#[tauri::command]
pub async fn save_export_stream(
    app: AppHandle,
    state: State<'_, DesktopState>,
    request: ExportRequestSpec,
    filename: String,
) -> Result<SaveOutcome, ExportError> {
    let artifact = request.artifact()?;
    let suggested = sanitize_suggested_filename(&filename);
    let chosen = app.dialog().file().set_file_name(&suggested).blocking_save_file();
    let Some(fp) = chosen else {
        return Ok(SaveOutcome::cancelled());
    };
    let dest = file_path_to_pathbuf(fp)?;
    let sidecar = Arc::clone(&state.sidecar);
    let outcome = tauri::async_runtime::spawn_blocking(move || {
        stream_loopback_export(&sidecar, artifact, &request, &dest)
    })
    .await
    .map_err(|e| format!("Export task failed: {e}"))??;
    if let Some(ref saved_path) = outcome.path {
        state.reveal.allow(std::path::Path::new(saved_path));
    }
    Ok(outcome)
}

pub fn spawn_desktop_window(
    app: &AppHandle,
    spec: WindowLaunchSpec<'_>,
) -> Result<WebviewWindow, String> {
    let target = handshake_url(spec.port, spec.nonce, spec.workspace_url)?;
    let is_main = spec.explicit_label == Some("main");
    let label = match spec.explicit_label {
        Some(fixed) => fixed.to_string(),
        None => format!("project-{}", WINDOW_COUNTER.fetch_add(1, Ordering::Relaxed)),
    };
    let navigation_app = app.clone();
    let popup_app = app.clone();
    let init_script = bridge_init_script(std::env::consts::OS, spec.app_version);
    let port = spec.port;

    let mut builder = WebviewWindowBuilder::new(app, label, WebviewUrl::External(target))
        .title(workspace_title(spec.title))
        .min_inner_size(MIN_WIDTH, MIN_HEIGHT)
        .initialization_script(&init_script)
        .on_navigation(move |url| keep_in_webview(&navigation_app, url, port))
        .on_new_window(move |url, _| {
            if keep_in_webview(&popup_app, &url, port) {
                NewWindowResponse::Allow
            } else {
                NewWindowResponse::Deny
            }
        });

    #[cfg(target_os = "macos")]
    {
        builder = crate::window_chrome::native_title_bar(builder).visible(false);
    }

    if is_main {
        let geom = load_window_geometry();
        builder = builder.inner_size(geom.width, geom.height);
        if let (Some(x), Some(y)) = (geom.x, geom.y) {
            builder = builder.position(x, y);
        }
        if geom.maximized {
            builder = builder.maximized(true);
        }
    } else {
        builder = builder.inner_size(DEFAULT_WIDTH, DEFAULT_HEIGHT);
    }

    let window = builder
        .build()
        .map_err(|e| format!("Failed opening desktop window: {e}"))?;
    let prefs = load_preferences();
    if (prefs.zoom - DEFAULT_ZOOM).abs() > f64::EPSILON {
        let _ = window.set_zoom(prefs.zoom);
    }
    #[cfg(target_os = "macos")]
    {
        if let Ok(theme) = window.theme() {
            let _ = window.set_background_color(crate::window_chrome::backdrop(theme));
        }
        window.show().map_err(|e| format!("Failed showing desktop window: {e}"))?;
    }
    Ok(window)
}

#[tauri::command]
pub fn set_workspace_title(window: WebviewWindow, project: String) -> Result<(), String> {
    window.set_title(&workspace_title(&project)).map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn open_project_window(
    app: AppHandle,
    state: State<'_, DesktopState>,
    workspace_url: String,
    title: String,
) -> Result<(), String> {
    if !is_valid_workspace_path(&workspace_url) {
        return Err("Invalid workspace path".to_string());
    }
    let sidecar = Arc::clone(&state.sidecar);
    let nonce = tauri::async_runtime::spawn_blocking(move || sidecar.mint_handshake_nonce())
        .await
        .map_err(|e| format!("Failed minting desktop nonce: {e}"))??;
    spawn_desktop_window(
        &app,
        WindowLaunchSpec {
            port: state.sidecar.port,
            nonce: &nonce,
            workspace_url: &workspace_url,
            title: &title,
            app_version: &state.app_version,
            explicit_label: None,
        },
    )?;
    Ok(())
}

#[tauri::command]
pub fn open_logs_folder(app: AppHandle) -> Result<(), String> {
    let logs_dir = sidecar_log_dir()
        .ok_or_else(|| "Unable to locate local Lixity state directory".to_string())?;
    app.opener()
        .open_path(logs_dir.to_string_lossy().as_ref(), None::<&str>)
        .map_err(|e| format!("Failed opening logs folder: {e}"))
}

#[tauri::command]
pub async fn get_runtime_environment(
    state: State<'_, DesktopState>,
) -> Result<serde_json::Value, String> {
    let sidecar = Arc::clone(&state.sidecar);
    tauri::async_runtime::spawn_blocking(move || sidecar.runtime_environment())
        .await
        .map_err(|_| "Could not complete the desktop runtime environment request".to_string())?
}

fn open_system_url(app: &AppHandle, url: &Url) -> Result<(), String> {
    app.opener()
        .open_url(url.as_str(), None::<&str>)
        .map_err(|e| format!("Failed opening external URL: {e}"))
}

fn keep_in_webview(app: &AppHandle, url: &Url, port: u16) -> bool {
    route_webview_navigation(url, port, |external| {
        let _ = open_system_url(app, external);
    })
}

#[tauri::command]
pub fn open_external_url(app: AppHandle, url: String) -> Result<(), String> {
    open_system_url(&app, &is_allowed_external_url(&url)?)
}

#[tauri::command]
pub fn reveal_in_file_manager(
    app: AppHandle,
    state: State<'_, DesktopState>,
    path: String,
) -> Result<(), String> {
    let allowed = state.reveal.is_allowed(std::path::Path::new(&path))?;
    app.opener()
        .reveal_item_in_dir(allowed)
        .map_err(|e| format!("Failed revealing file: {e}"))
}

#[tauri::command]
pub fn set_dirty_state(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
    unsaved_editor: bool,
) {
    state.dirty.set_editor_dirty(window.label(), unsaved_editor);
}

#[tauri::command]
pub fn list_recent_projects(
    app: AppHandle,
    state: State<'_, DesktopState>,
    legacy_paths: Option<Vec<String>>,
) -> Result<Vec<RecentProject>, String> {
    let (entries, imported) = import_legacy_recent(legacy_paths.as_deref().unwrap_or_default())?;
    if imported {
        refresh_app_menu(&app, &state.locale);
    }
    Ok(entries)
}

#[tauri::command]
pub fn record_recent_project(
    app: AppHandle,
    state: State<'_, DesktopState>,
    path: String,
    title: Option<String>,
    language: Option<String>,
) -> Result<Vec<RecentProject>, String> {
    state.reveal.allow(std::path::Path::new(&path));
    let updated = record_recent(&path, title, language)?;
    refresh_app_menu(&app, &state.locale);
    Ok(updated)
}

#[tauri::command]
pub fn remove_recent_project(
    app: AppHandle,
    state: State<'_, DesktopState>,
    path: String,
) -> Result<Vec<RecentProject>, String> {
    let updated = remove_recent(&path)?;
    refresh_app_menu(&app, &state.locale);
    Ok(updated)
}

#[tauri::command]
pub fn clear_recent_projects(
    app: AppHandle,
    state: State<'_, DesktopState>,
) -> Result<Vec<RecentProject>, String> {
    let updated = clear_recent()?;
    refresh_app_menu(&app, &state.locale);
    Ok(updated)
}

#[tauri::command]
pub fn get_preferences() -> DesktopPreferences {
    load_preferences()
}

#[tauri::command]
pub fn set_preference(
    app: AppHandle,
    key: String,
    value: serde_json::Value,
) -> Result<DesktopPreferences, String> {
    let updated = update_preference(&key, value)?;
    if key == "zoom" {
        for window in app.webview_windows().values() {
            if window.label() != "splashscreen" {
                let _ = window.set_zoom(updated.zoom);
            }
        }
    } else if key == "theme" {
        app.set_theme(preferred_theme(updated.theme.as_deref()));
        for window in app.webview_windows().values() {
            if window.label() != "splashscreen" {
                crate::dispatch_desktop_event(window, "lixity:desktop-theme", &updated.theme);
            }
        }
    }
    Ok(updated)
}

#[tauri::command]
pub async fn check_for_updates(state: State<'_, DesktopState>) -> Result<UpdateCheckResult, String> {
    let version = state.app_version.clone();
    tauri::async_runtime::spawn_blocking(move || check_latest_release(&version))
        .await
        .map_err(|e| format!("Update check task failed: {e}"))?
}

#[tauri::command]
pub fn audio_capture_list_devices() -> Result<Vec<CaptureDeviceInfo>, String> {
    list_input_devices()
}

#[tauri::command]
pub async fn audio_capture_calibrate(
    device_name: Option<String>,
    duration_seconds: f32,
) -> Result<CalibrationReport, String> {
    tauri::async_runtime::spawn_blocking(move || {
        calibrate_microphone(device_name.as_deref(), duration_seconds)
    })
    .await
    .map_err(|e| format!("Calibration task failed: {e}"))?
}

#[tauri::command]
pub async fn audio_capture_record_take(
    device_name: Option<String>,
    duration_seconds: f32,
    filename: String,
) -> Result<RecordedTakeResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        record_wav_take(device_name.as_deref(), duration_seconds, &filename)
    })
    .await
    .map_err(|e| format!("Recording task failed: {e}"))?
}

#[tauri::command]
pub async fn audio_capture_start_recording(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
    device_name: Option<String>,
    filename: String,
) -> Result<(), String> {
    let recorder = Arc::clone(&state.recorder);
    tauri::async_runtime::spawn_blocking(move || {
        let open = || {
            window
                .app_handle()
                .get_webview_window(window.label())
                .is_some()
        };
        if !open() {
            return Err("The recording window has closed".to_string());
        }
        recorder.start(window.label().to_string(), device_name, filename)?;
        if !open() {
            recorder.cancel(window.label());
            return Err("The recording window has closed".to_string());
        }
        Ok(())
    })
    .await
    .map_err(|e| format!("Failed starting recording task: {e}"))?
}

#[tauri::command]
pub fn audio_capture_status(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
) -> RecordingLiveStatus {
    state.recorder.status(window.label())
}

#[tauri::command]
pub async fn audio_capture_stop_recording(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
) -> Result<RecordedTakeResult, String> {
    let recorder = Arc::clone(&state.recorder);
    tauri::async_runtime::spawn_blocking(move || recorder.stop(window.label()))
        .await
        .map_err(|e| format!("Failed finishing recording task: {e}"))?
}

#[tauri::command]
pub async fn audio_capture_cancel_recording(
    window: WebviewWindow,
    state: State<'_, DesktopState>,
) -> Result<(), String> {
    let recorder = Arc::clone(&state.recorder);
    tauri::async_runtime::spawn_blocking(move || {
        recorder.cancel(window.label());
    })
    .await
    .map_err(|e| format!("Failed cancelling recording task: {e}"))
}
